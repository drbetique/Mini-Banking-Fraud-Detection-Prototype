"""
Automated Model Retraining Pipeline
====================================

This script:
1. Fetches recent transaction data from the database
2. Validates data quality before training
3. Trains a new Isolation Forest model
4. Evaluates performance against current production model
5. Promotes new model only if it performs better
6. Logs comprehensive metrics to MLflow
7. Sends alerts on training failures or performance degradation

Usage:
    python retrain_model.py [--min-samples MIN] [--lookback-days DAYS] [--force-promotion]

Arguments:
    --min-samples: Minimum samples required for training (default: 1000)
    --lookback-days: Days of historical data to use (default: 90)
    --force-promotion: Skip performance comparison and force promotion
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
TABLE_NAME = "transactions"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001")
MODEL_NAME = "fraud-detection-model"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Raised when data quality checks fail."""
    pass


class ModelTrainingError(Exception):
    """Raised when model training fails."""
    pass


def validate_data_quality(df: pd.DataFrame, min_samples: int = 1000) -> None:
    """
    Validates data quality before training.

    Args:
        df: Training dataframe
        min_samples: Minimum number of samples required

    Raises:
        DataQualityError: If data quality checks fail
    """
    logger.info("Running data quality checks...")

    # Check 1: Sufficient samples
    if len(df) < min_samples:
        raise DataQualityError(
            f"Insufficient data: {len(df)} samples (minimum: {min_samples})"
        )

    # Check 2: Required columns present
    required_cols = ['transaction_id', 'account_id', 'amount', 'timestamp', 'is_fraud']
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise DataQualityError(f"Missing required columns: {missing_cols}")

    # Check 3: No excessive nulls
    null_pct = df[required_cols].isnull().sum() / len(df)
    high_null_cols = null_pct[null_pct > 0.1].index.tolist()
    if high_null_cols:
        raise DataQualityError(
            f"Excessive null values (>10%) in columns: {high_null_cols}"
        )

    # Check 4: Valid value ranges
    if (df['amount'] <= 0).any():
        raise DataQualityError("Found transactions with amount <= 0")

    # Check 5: Fraud label distribution
    fraud_rate = df['is_fraud'].mean()
    if fraud_rate == 0:
        logger.warning("No fraud labels in dataset - model may not learn fraud patterns")
    elif fraud_rate > 0.5:
        logger.warning(f"Unusually high fraud rate: {fraud_rate:.2%}")

    logger.info(f"Data quality checks passed: {len(df)} samples, {fraud_rate:.2%} fraud rate")


def fetch_training_data(lookback_days: int = 90) -> pd.DataFrame:
    """
    Fetches recent transaction data from the database.

    Args:
        lookback_days: Number of days of historical data to fetch

    Returns:
        DataFrame with transaction data
    """
    logger.info(f"Fetching training data (last {lookback_days} days)...")

    engine = create_engine(DATABASE_URL)
    cutoff_date = datetime.now() - timedelta(days=lookback_days)

    query = text(f"""
        SELECT
            transaction_id,
            account_id,
            amount,
            merchant_category,
            location,
            timestamp,
            is_fraud,
            ml_anomaly_score
        FROM {TABLE_NAME}
        WHERE timestamp >= :cutoff_date
        ORDER BY timestamp DESC
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"cutoff_date": cutoff_date})

    engine.dispose()

    logger.info(f"Fetched {len(df)} transactions from {cutoff_date.date()} onwards")
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineers features for model training (consistent with detection_logic.py).

    Args:
        df: Raw transaction dataframe

    Returns:
        DataFrame with engineered features
    """
    logger.info("Engineering features...")

    # Account-level aggregations
    df['account_avg_amount'] = df.groupby('account_id')['amount'].transform('mean')
    df['account_tx_count'] = df.groupby('account_id')['amount'].transform('count')
    df['account_max_amount'] = df.groupby('account_id')['amount'].transform('max')

    # Deviation features
    df['deviation_from_avg'] = (df['amount'] - df['account_avg_amount']) / (df['account_avg_amount'] + 1e-6)
    df['amount_to_max_ratio'] = df['amount'] / (df['account_max_amount'] + 1e-6)

    # Time-based features
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    df['is_night'] = ((df['hour'] >= 22) | (df['hour'] <= 6)).astype(int)

    logger.info("Feature engineering complete")
    return df


def train_model(X_train: pd.DataFrame) -> IsolationForest:
    """
    Trains Isolation Forest model.

    Args:
        X_train: Training features

    Returns:
        Trained IsolationForest model
    """
    logger.info("Training Isolation Forest model...")

    model = IsolationForest(
        n_estimators=100,
        contamination='auto',
        random_state=42,
        n_jobs=-1  # Use all available cores
    )

    model.fit(X_train)
    logger.info("Model training complete")

    return model


def evaluate_model(
    model: IsolationForest,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> Dict[str, float]:
    """
    Evaluates model performance on test set.

    Args:
        model: Trained model
        X_test: Test features
        y_test: True labels (1 = fraud, 0 = normal)

    Returns:
        Dictionary of evaluation metrics
    """
    logger.info("Evaluating model performance...")

    # Get anomaly scores and predictions
    anomaly_scores = model.decision_function(X_test)
    # Isolation Forest: -1 = anomaly, 1 = normal
    # Convert to: 1 = fraud, 0 = normal (matching our labels)
    predictions = (model.predict(X_test) == -1).astype(int)

    # Calculate metrics
    metrics = {
        'precision': precision_score(y_test, predictions, zero_division=0),
        'recall': recall_score(y_test, predictions, zero_division=0),
        'f1_score': f1_score(y_test, predictions, zero_division=0),
        'fraud_detection_rate': predictions.mean(),
        'min_anomaly_score': anomaly_scores.min(),
        'max_anomaly_score': anomaly_scores.max(),
        'mean_anomaly_score': anomaly_scores.mean(),
        'std_anomaly_score': anomaly_scores.std()
    }

    # Calculate AUC if possible
    try:
        metrics['roc_auc'] = roc_auc_score(y_test, -anomaly_scores)  # Negative because lower = more anomalous
    except ValueError:
        logger.warning("Could not calculate ROC AUC (insufficient fraud samples)")
        metrics['roc_auc'] = 0.0

    logger.info(f"Model evaluation: Precision={metrics['precision']:.3f}, "
                f"Recall={metrics['recall']:.3f}, F1={metrics['f1_score']:.3f}")

    return metrics


def get_production_model_metrics(client: MlflowClient) -> Optional[Dict[str, float]]:
    """
    Retrieves metrics of the current production model.

    Args:
        client: MLflow client

    Returns:
        Dictionary of production model metrics, or None if no production model
    """
    try:
        # Get production model version
        prod_versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])

        if not prod_versions:
            logger.warning("No production model found")
            return None

        prod_version = prod_versions[0]
        run_id = prod_version.run_id

        # Get metrics from the run
        run = client.get_run(run_id)
        metrics = run.data.metrics

        logger.info(f"Production model version {prod_version.version}: "
                   f"F1={metrics.get('f1_score', 0):.3f}")

        return metrics

    except Exception as e:
        logger.error(f"Error fetching production model metrics: {e}")
        return None


def should_promote_model(
    new_metrics: Dict[str, float],
    prod_metrics: Optional[Dict[str, float]],
    min_improvement: float = 0.02
) -> Tuple[bool, str]:
    """
    Determines if new model should be promoted to production.

    Args:
        new_metrics: New model's metrics
        prod_metrics: Production model's metrics (None if no prod model)
        min_improvement: Minimum F1 improvement required for promotion

    Returns:
        (should_promote, reason) tuple
    """
    # If no production model, always promote
    if prod_metrics is None:
        return True, "No existing production model"

    # Compare F1 scores
    new_f1 = new_metrics.get('f1_score', 0)
    prod_f1 = prod_metrics.get('f1_score', 0)

    improvement = new_f1 - prod_f1

    if improvement >= min_improvement:
        return True, f"F1 improvement: {improvement:.3f} (>{min_improvement})"
    elif improvement > 0:
        return False, f"F1 improvement: {improvement:.3f} (<{min_improvement} threshold)"
    else:
        return False, f"F1 degradation: {improvement:.3f}"


def retrain_pipeline(
    min_samples: int = 1000,
    lookback_days: int = 90,
    force_promotion: bool = False
) -> None:
    """
    Main retraining pipeline.

    Args:
        min_samples: Minimum samples required for training
        lookback_days: Days of historical data to use
        force_promotion: Skip performance comparison and force promotion
    """
    logger.info("=" * 60)
    logger.info("Starting Automated Model Retraining Pipeline")
    logger.info("=" * 60)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("Fraud Detection - Automated Retraining")
    client = MlflowClient()

    try:
        # Step 1: Fetch data
        df = fetch_training_data(lookback_days)

        # Step 2: Validate data quality
        validate_data_quality(df, min_samples)

        # Step 3: Engineer features
        df = engineer_features(df)

        # Step 4: Prepare training data
        feature_cols = [
            'amount', 'account_avg_amount', 'deviation_from_avg',
            'account_tx_count', 'amount_to_max_ratio',
            'hour', 'day_of_week', 'is_weekend', 'is_night'
        ]

        X = df[feature_cols].fillna(0)
        y = df['is_fraud']

        # Split for evaluation
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        logger.info(f"Training set: {len(X_train)} samples")
        logger.info(f"Test set: {len(X_test)} samples")

        # Step 5: Train model
        with mlflow.start_run(run_name=f"retrain_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
            model = train_model(X_train)

            # Step 6: Evaluate model
            new_metrics = evaluate_model(model, X_test, y_test)

            # Log parameters
            mlflow.log_param("n_estimators", 100)
            mlflow.log_param("contamination", "auto")
            mlflow.log_param("lookback_days", lookback_days)
            mlflow.log_param("training_samples", len(X_train))
            mlflow.log_param("test_samples", len(X_test))

            # Log metrics
            for metric_name, metric_value in new_metrics.items():
                mlflow.log_metric(metric_name, metric_value)

            # Log decision score bounds (needed by detection service)
            mlflow.log_metric("min_decision_score", new_metrics['min_anomaly_score'])
            mlflow.log_metric("max_decision_score", new_metrics['max_anomaly_score'])

            # Log model
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="isolation_forest_model",
                registered_model_name=MODEL_NAME
            )

            # Step 7: Decide on promotion
            prod_metrics = get_production_model_metrics(client)

            if force_promotion:
                should_promote = True
                reason = "Force promotion flag enabled"
            else:
                should_promote, reason = should_promote_model(new_metrics, prod_metrics)

            logger.info(f"Promotion decision: {should_promote} - {reason}")
            mlflow.log_param("promotion_decision", should_promote)
            mlflow.log_param("promotion_reason", reason)

            # Step 8: Promote if appropriate
            if should_promote:
                # Get the newly registered model version
                model_versions = client.search_model_versions(f"name='{MODEL_NAME}'")
                latest_version = sorted(model_versions, key=lambda x: int(x.version), reverse=True)[0]

                # Archive old production model
                if prod_metrics:
                    prod_versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
                    if prod_versions:
                        client.transition_model_version_stage(
                            name=MODEL_NAME,
                            version=prod_versions[0].version,
                            stage="Archived"
                        )
                        logger.info(f"Archived old production model v{prod_versions[0].version}")

                # Promote new model
                client.transition_model_version_stage(
                    name=MODEL_NAME,
                    version=latest_version.version,
                    stage="Production"
                )

                logger.info(f"✅ Model v{latest_version.version} promoted to Production")
                logger.info(f"   Reason: {reason}")

            else:
                logger.info(f"❌ Model NOT promoted to Production")
                logger.info(f"   Reason: {reason}")

                # Tag as Staging for manual review
                model_versions = client.search_model_versions(f"name='{MODEL_NAME}'")
                latest_version = sorted(model_versions, key=lambda x: int(x.version), reverse=True)[0]

                client.transition_model_version_stage(
                    name=MODEL_NAME,
                    version=latest_version.version,
                    stage="Staging"
                )
                logger.info(f"   Model v{latest_version.version} tagged as Staging for manual review")

        logger.info("=" * 60)
        logger.info("Retraining pipeline completed successfully")
        logger.info("=" * 60)

    except DataQualityError as e:
        logger.error(f"Data quality check failed: {e}")
        sys.exit(1)

    except ModelTrainingError as e:
        logger.error(f"Model training failed: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error in retraining pipeline: {e}", exc_info=True)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Automated model retraining pipeline for fraud detection"
    )
    parser.add_argument(
        '--min-samples',
        type=int,
        default=1000,
        help='Minimum samples required for training (default: 1000)'
    )
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=90,
        help='Days of historical data to use (default: 90)'
    )
    parser.add_argument(
        '--force-promotion',
        action='store_true',
        help='Skip performance comparison and force promotion to production'
    )

    args = parser.parse_args()

    retrain_pipeline(
        min_samples=args.min_samples,
        lookback_days=args.lookback_days,
        force_promotion=args.force_promotion
    )


if __name__ == "__main__":
    main()
