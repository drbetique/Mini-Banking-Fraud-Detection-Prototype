import os
import json
import time
import logging
import signal
import sys
import pandas as pd
from kafka import KafkaConsumer
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import TEXT, REAL, INTEGER, TIMESTAMP
import mlflow
import mlflow.pyfunc
import mlflow.sklearn
import mlflow.tracking
from prometheus_client import start_http_server, Counter, Gauge # Import Prometheus client

from detection_logic import get_account_aggregates, score_transaction
from notification_service import send_fraud_alert

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_flag
    logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
    shutdown_flag = True

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "transactions_topic")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
TABLE_NAME = "transactions"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
PROMETHEUS_PORT = int(os.environ.get("PROMETHEUS_PORT", 8001)) # Port for Prometheus metrics

# Globals for the loaded MLflow model
LOADED_MODEL = None
MODEL_MIN_SCORE = None
MODEL_MAX_SCORE = None

# --- Prometheus Metrics ---
TRANSACTIONS_PROCESSED = Counter(
    'transactions_processed_total',
    'Total number of transactions processed by the detection service.'
)
ANOMALIES_DETECTED = Counter(
    'anomalies_detected_total',
    'Total number of anomalies detected by the detection service.'
)
TRANSACTION_PROCESSING_ERRORS = Counter(
    'transaction_processing_errors_total',
    'Total number of errors encountered while processing transactions.'
)

def create_kafka_consumer():
    """Creates a Kafka consumer, retrying if brokers are not available."""
    for attempt in range(1, 6):
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                auto_offset_reset='earliest',
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                group_id='fraud-detectors'
            )
            logger.info("Kafka Consumer connected successfully", extra={
                'bootstrap_servers': KAFKA_BOOTSTRAP_SERVERS,
                'topic': KAFKA_TOPIC
            })
            return consumer
        except Exception as e:
            logger.warning(
                f"Waiting for Kafka brokers (attempt {attempt}/5)",
                extra={'error': str(e)},
                exc_info=True
            )
            time.sleep(10)
    raise ConnectionError("Could not connect to Kafka brokers after multiple retries.")

def load_mlflow_model():
    """Loads the latest model version from MLflow Model Registry."""
    global LOADED_MODEL, MODEL_MIN_SCORE, MODEL_MAX_SCORE

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    model_name = "fraud-detection-model"

    for attempt in range(1, 6): # Retry loading model
        try:
            logger.info(
                f"Attempting to load '{model_name}' model (latest version) from MLflow (attempt {attempt}/5)",
                extra={'mlflow_uri': MLFLOW_TRACKING_URI, 'model_name': model_name}
            )

            # Get the latest version of the model
            client = mlflow.tracking.MlflowClient()
            model_versions = client.search_model_versions(f"name='{model_name}'")

            if not model_versions:
                raise ValueError(f"No versions found for model '{model_name}'")

            # Sort by version number and get the latest
            latest_version = sorted(model_versions, key=lambda x: int(x.version), reverse=True)[0]

            # Load the model using the latest version number (sklearn loader for direct access to methods)
            LOADED_MODEL = mlflow.sklearn.load_model(f"models:/{model_name}/{latest_version.version}")

            # Retrieve min_score and max_score from the model's MLflow run
            run_id = latest_version.run_id
            run = client.get_run(run_id)
            MODEL_MIN_SCORE = run.data.metrics.get("min_decision_score")
            MODEL_MAX_SCORE = run.data.metrics.get("max_decision_score")

            if MODEL_MIN_SCORE is None or MODEL_MAX_SCORE is None:
                raise ValueError("Min/Max scores not found in MLflow run metrics for the model.")

            logger.info(
                "MLflow model loaded successfully",
                extra={
                    'model_version': latest_version.version,
                    'run_id': run_id,
                    'min_score': MODEL_MIN_SCORE,
                    'max_score': MODEL_MAX_SCORE
                }
            )
            return
        except Exception as e:
            logger.error(
                f"Error loading model from MLflow (attempt {attempt}/5)",
                extra={'error': str(e)},
                exc_info=True
            )
            time.sleep(10)

    raise RuntimeError("Could not load MLflow model after multiple retries. Ensure it is trained and registered.")


def validate_transaction(transaction: dict) -> tuple[bool, str]:
    """
    Validates transaction data structure.
    Returns (is_valid, error_message).
    """
    required_fields = ['transaction_id', 'account_id', 'amount', 'merchant_category', 'location', 'timestamp']

    for field in required_fields:
        if field not in transaction or transaction[field] is None:
            return False, f"Missing required field: {field}"

    # Validate amount
    try:
        amount = float(transaction['amount'])
        if amount <= 0:
            return False, f"Invalid amount: {amount} (must be positive)"
    except (ValueError, TypeError):
        return False, f"Invalid amount format: {transaction.get('amount')}"

    return True, ""


def process_transaction(transaction: dict, db_conn):
    """
    Processes a single transaction to detect anomalies and inserts it into the database.
    Includes comprehensive error handling and validation.
    """
    TRANSACTIONS_PROCESSED.inc() # Increment total processed transactions

    transaction_id = transaction.get('transaction_id', 'UNKNOWN')
    account_id = transaction.get('account_id', 'UNKNOWN')

    try:
        # Validate transaction data
        is_valid, error_msg = validate_transaction(transaction)
        if not is_valid:
            TRANSACTION_PROCESSING_ERRORS.inc()
            logger.error(
                f"Transaction validation failed: {error_msg}",
                extra={'transaction_id': transaction_id, 'transaction': transaction}
            )
            return

        logger.info(
            "Processing transaction",
            extra={
                'transaction_id': transaction_id,
                'account_id': account_id,
                'amount': transaction.get('amount')
            }
        )

        # 1. Get historical aggregates for the account
        aggregates = get_account_aggregates(account_id, db_conn)

        # 2. Score the transaction using the loaded MLflow model
        try:
            score, reason = score_transaction(
                transaction,
                aggregates,
                LOADED_MODEL,
                MODEL_MIN_SCORE,
                MODEL_MAX_SCORE
            )
        except Exception as e:
            logger.error(
                "Scoring failed, using fallback",
                extra={'transaction_id': transaction_id},
                exc_info=True
            )
            # Fallback: mark as score 0 (normal) if ML fails
            score, reason = 0.0, None

        # 3. Populate the transaction record with detection results
        transaction['ml_anomaly_score'] = score
        transaction['alert_reason'] = reason
        transaction['is_anomaly'] = 1 if reason else 0
        transaction['status'] = 'NEW' if reason else None

        # Increment anomaly counter if detected
        if transaction['is_anomaly'] == 1:
            ANOMALIES_DETECTED.inc()
            logger.warning(
                "Anomaly detected",
                extra={
                    'transaction_id': transaction_id,
                    'score': score,
                    'reason': reason,
                    'account_id': account_id
                }
            )

            # Send real-time fraud alert notifications
            try:
                notification_results = send_fraud_alert(transaction, score)
                if notification_results:
                    logger.info(
                        "Fraud alert notifications sent",
                        extra={
                            'transaction_id': transaction_id,
                            'channels': list(notification_results.keys())
                        }
                    )
            except Exception as notif_error:
                # Don't fail transaction processing if notification fails
                logger.error(
                    f"Failed to send fraud alert notification: {notif_error}",
                    extra={'transaction_id': transaction_id}
                )

        # 4. Insert the scored transaction into the database
        df = pd.DataFrame([transaction])
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Define dtypes for all columns to ensure consistency
        dtype = {
            'transaction_id': TEXT, 'account_id': TEXT, 'timestamp': TIMESTAMP,
            'amount': REAL, 'merchant_category': TEXT, 'location': TEXT,
            'is_fraud': INTEGER, 'ml_anomaly_score': REAL, 'alert_reason': TEXT,
            'is_anomaly': INTEGER, 'status': TEXT
        }
        # Filter df to only include columns that are in dtype, to avoid errors
        df = df[list(dtype.keys())]

        df.to_sql(TABLE_NAME, db_conn, if_exists='append', index=False, dtype=dtype)

        logger.info(
            "Successfully processed and inserted transaction",
            extra={
                'transaction_id': transaction_id,
                'is_anomaly': transaction['is_anomaly'],
                'score': score
            }
        )

    except KeyError as e:
        TRANSACTION_PROCESSING_ERRORS.inc()
        logger.error(
            f"Missing required field in transaction: {e}",
            extra={'transaction_id': transaction_id},
            exc_info=True
        )

    except SQLAlchemyError as e:
        TRANSACTION_PROCESSING_ERRORS.inc()
        db_conn.rollback()  # Rollback the failed transaction
        logger.error(
            "Database error processing transaction",
            extra={'transaction_id': transaction_id},
            exc_info=True
        )

    except Exception as e:
        TRANSACTION_PROCESSING_ERRORS.inc()
        try:
            db_conn.rollback()  # Attempt rollback on any error
        except:
            pass  # Connection might already be closed
        logger.error(
            "Unexpected error processing transaction",
            extra={'transaction_id': transaction_id, 'error_type': type(e).__name__},
            exc_info=True
        )


def main():
    """Main consumer loop with graceful shutdown handling."""
    # Start Prometheus HTTP server for metrics
    start_http_server(PROMETHEUS_PORT)
    logger.info(f"Prometheus metrics exposed on port {PROMETHEUS_PORT}")

    consumer = None
    engine = None

    try:
        consumer = create_kafka_consumer()
        engine = create_engine(DATABASE_URL)

        # Load the MLflow model once on startup
        load_mlflow_model()

        logger.info("Detection service started. Waiting for messages...")

        with engine.connect() as connection:
            for message in consumer:
                # Check shutdown flag
                if shutdown_flag:
                    logger.info("Shutdown flag set. Stopping message consumption...")
                    break

                transaction_data = message.value
                process_transaction(transaction_data, connection)
                connection.commit()  # Commit after each transaction

    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt. Shutting down...")

    except Exception as e:
        logger.error("Fatal error in main loop", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup resources
        logger.info("Cleaning up resources...")

        if consumer:
            try:
                consumer.close()
                logger.info("Kafka consumer closed successfully")
            except Exception as e:
                logger.error("Error closing Kafka consumer", exc_info=True)

        if engine:
            try:
                engine.dispose()
                logger.info("Database engine disposed successfully")
            except Exception as e:
                logger.error("Error disposing database engine", exc_info=True)

        logger.info("Shutdown complete. Exiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()

