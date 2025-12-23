import os
import json
import time
import logging
import pandas as pd
from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "transactions_topic")
CSV_FILE = 'transactions.csv'
STREAM_DELAY_SECONDS = 1  # Delay between sending messages

def create_producer():
    """Creates a Kafka producer, retrying if brokers are not available."""
    for attempt in range(1, 11): # Increased retries
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info(
                "Kafka Producer connected successfully",
                extra={'bootstrap_servers': KAFKA_BOOTSTRAP_SERVERS}
            )
            return producer
        except NoBrokersAvailable as e:
            logger.warning(
                f"Waiting for Kafka brokers to be available (attempt {attempt}/10)",
                extra={'error': str(e)}
            )
            time.sleep(15) # Increased wait time
    raise ConnectionError("Could not connect to Kafka brokers after multiple retries.")

def stream_transactions():
    """Reads transactions from a CSV and streams them to a Kafka topic."""

    if not os.path.exists(CSV_FILE):
        err_msg = f"Error: The file '{CSV_FILE}' was not found. Please ensure 'generate_data.py' has been run to create this file."
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)

    producer = create_producer()

    try:
        df = pd.read_csv(CSV_FILE)
        total_transactions = len(df)
        logger.info(
            f"Starting to stream transactions",
            extra={
                'total_transactions': total_transactions,
                'source_file': CSV_FILE,
                'topic': KAFKA_TOPIC,
                'delay_seconds': STREAM_DELAY_SECONDS
            }
        )

        for idx, row in df.iterrows():
            transaction = row.to_dict()
            producer.send(KAFKA_TOPIC, value=transaction)

            logger.info(
                f"Sent transaction ({idx+1}/{total_transactions})",
                extra={
                    'transaction_id': transaction['transaction_id'],
                    'progress': f"{((idx+1)/total_transactions)*100:.1f}%"
                }
            )
            time.sleep(STREAM_DELAY_SECONDS)

        producer.flush() # Ensure all messages are sent
        logger.info("Finished streaming all transactions successfully")

    except Exception as e:
        logger.error("An error occurred during streaming", exc_info=True)
        raise
    finally:
        if producer:
            producer.close()
            logger.info("Kafka producer closed")

if __name__ == "__main__":
    try:
        stream_transactions()
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
    except ConnectionError as e:
        logger.error(f"Failed to connect to Kafka: {e}")
    except Exception as e:
        logger.error("An unexpected error occurred", exc_info=True)
