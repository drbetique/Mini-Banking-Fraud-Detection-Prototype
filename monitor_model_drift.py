"""
Model Drift Monitoring
======================

Monitors production model performance and detects model drift.

This script:
1. Fetches recent predictions from the database
2. Compares predicted fraud vs actual fraud labels
3. Calculates model performance metrics
4. Detects performance degradation (model drift)
5. Logs metrics to Prometheus for alerting

Usage:
    python monitor_model_drift.py [--lookback-days DAYS] [--alert-threshold THRESHOLD]
"""

import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
TABLE_NAME = "transactions"
PROMETHEUS_PUSHGATEWAY = os.environ.get("PROMETHEUS_PUSHGATEWAY", "localhost:9091")

# Prometheus metrics
registry = CollectorRegistry()
model_f1_score = Gauge('model_current_f1_score', 'Current F1 score of production model', registry=registry)
model_precision = Gauge('model_current_precision', 'Current precision of production model', registry=registry)
model_recall = Gauge('model_current_recall', 'Current recall of production model', registry=registry)
model_drift_detected = Gauge('model_drift_detected', 'Whether model drift is detected (1=yes, 0=no)', registry=registry)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def fetch_recent_predictions(lookback_days: int = 7) -> pd.DataFrame:
    """
    Fetches recent transactions with both predictions and actual labels.

    Args:
        lookback_days: Number of days to look back

    Returns:
        DataFrame with predictions and actual labels
    """
    logger.info(f"Fetching predictions from last {lookback_days} days...")

    engine = create_engine(DATABASE_URL)
    cutoff_date = datetime.now() - timedelta(days=lookback_days)

    query = text(f"""
        SELECT
            transaction_id,
            timestamp,
            is_fraud as actual_label,
            is_anomaly as predicted_label,
            ml_anomaly_score,
            status
        FROM {TABLE_NAME}
        WHERE timestamp >= :cutoff_date
          AND is_anomaly IS NOT NULL
        ORDER BY timestamp DESC
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"cutoff_date": cutoff_date})

    engine.dispose()

    logger.info(f"Fetched {len(df)} predictions")
    return df


def calculate_performance_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculates model performance metrics.

    Args:
        df: DataFrame with actual_label and predicted_label columns

    Returns:
        Dictionary of performance metrics
    """
    if len(df) == 0:
        logger.warning("No data available for performance calculation")
        return {
            'precision': 0.0,
            'recall': 0.0,
            'f1_score': 0.0,
            'accuracy': 0.0,
            'false_positive_rate': 0.0,
            'false_negative_rate': 0.0,
            'sample_count': 0
        }

    y_true = df['actual_label']
    y_pred = df['predicted_label']

    # Calculate metrics
    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    # Calculate confusion matrix
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

    # Calculate rates
    total_normal = tn + fp
    total_fraud = fn + tp

    fpr = fp / total_normal if total_normal > 0 else 0.0
    fnr = fn / total_fraud if total_fraud > 0 else 0.0
    accuracy = (tp + tn) / len(df) if len(df) > 0 else 0.0

    metrics = {
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'accuracy': accuracy,
        'false_positive_rate': fpr,
        'false_negative_rate': fnr,
        'true_positives': int(tp),
        'false_positives': int(fp),
        'true_negatives': int(tn),
        'false_negatives': int(fn),
        'sample_count': len(df),
        'fraud_rate': y_true.mean(),
        'prediction_rate': y_pred.mean()
    }

    return metrics


def detect_model_drift(
    current_metrics: Dict[str, float],
    baseline_f1: float = 0.7,
    degradation_threshold: float = 0.1
) -> Tuple[bool, str]:
    """
    Detects if model has drifted from baseline performance.

    Args:
        current_metrics: Current model performance metrics
        baseline_f1: Expected baseline F1 score
        degradation_threshold: Maximum acceptable F1 degradation

    Returns:
        (drift_detected, reason) tuple
    """
    current_f1 = current_metrics['f1_score']
    degradation = baseline_f1 - current_f1

    if current_metrics['sample_count'] < 100:
        return False, f"Insufficient samples ({current_metrics['sample_count']}) for drift detection"

    if degradation > degradation_threshold:
        return True, f"F1 degradation: {degradation:.3f} (threshold: {degradation_threshold})"

    # Check for extreme imbalance in predictions
    pred_rate = current_metrics['prediction_rate']
    if pred_rate > 0.8:
        return True, f"Excessive fraud predictions: {pred_rate:.1%} (possible model malfunction)"
    elif pred_rate < 0.001:
        return True, f"Too few fraud predictions: {pred_rate:.1%} (model may not be detecting fraud)"

    # Check false positive rate
    if current_metrics['false_positive_rate'] > 0.3:
        return True, f"High false positive rate: {current_metrics['false_positive_rate']:.1%}"

    # Check false negative rate
    if current_metrics['false_negative_rate'] > 0.5:
        return True, f"High false negative rate: {current_metrics['false_negative_rate']:.1%}"

    return False, "Model performance within acceptable range"


def push_metrics_to_prometheus(metrics: Dict[str, float], drift_detected: bool):
    """
    Pushes model performance metrics to Prometheus Pushgateway.

    Args:
        metrics: Performance metrics dictionary
        drift_detected: Whether drift was detected
    """
    try:
        model_f1_score.set(metrics['f1_score'])
        model_precision.set(metrics['precision'])
        model_recall.set(metrics['recall'])
        model_drift_detected.set(1 if drift_detected else 0)

        # Push to Prometheus Pushgateway
        push_to_gateway(PROMETHEUS_PUSHGATEWAY, job='model_monitoring', registry=registry)
        logger.debug("Metrics pushed to Prometheus")

    except Exception as e:
        logger.warning(f"Could not push metrics to Prometheus: {e}")


def monitor_model_drift(
    lookback_days: int = 7,
    baseline_f1: float = 0.7,
    alert_threshold: float = 0.1
) -> None:
    """
    Main monitoring function.

    Args:
        lookback_days: Days of recent data to analyze
        baseline_f1: Expected baseline F1 score
        alert_threshold: F1 degradation threshold for alerts
    """
    logger.info("=" * 60)
    logger.info("Model Drift Monitoring")
    logger.info("=" * 60)

    try:
        # Fetch recent predictions
        df = fetch_recent_predictions(lookback_days)

        if len(df) == 0:
            logger.warning("No recent predictions found - unable to monitor performance")
            return

        # Calculate performance metrics
        metrics = calculate_performance_metrics(df)

        # Log current performance
        logger.info("Current Model Performance:")
        logger.info(f"  Samples: {metrics['sample_count']}")
        logger.info(f"  Precision: {metrics['precision']:.3f}")
        logger.info(f"  Recall: {metrics['recall']:.3f}")
        logger.info(f"  F1 Score: {metrics['f1_score']:.3f}")
        logger.info(f"  Accuracy: {metrics['accuracy']:.3f}")
        logger.info(f"  False Positive Rate: {metrics['false_positive_rate']:.3f}")
        logger.info(f"  False Negative Rate: {metrics['false_negative_rate']:.3f}")

        # Confusion matrix
        logger.info("Confusion Matrix:")
        logger.info(f"  True Positives: {metrics['true_positives']}")
        logger.info(f"  False Positives: {metrics['false_positives']}")
        logger.info(f"  True Negatives: {metrics['true_negatives']}")
        logger.info(f"  False Negatives: {metrics['false_negatives']}")

        # Detect drift
        drift_detected, reason = detect_model_drift(metrics, baseline_f1, alert_threshold)

        if drift_detected:
            logger.warning("🚨 MODEL DRIFT DETECTED!")
            logger.warning(f"   Reason: {reason}")
            logger.warning("   Action: Consider retraining the model")
        else:
            logger.info(f"✅ Model performance stable - {reason}")

        # Push metrics to Prometheus
        push_metrics_to_prometheus(metrics, drift_detected)

        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in model drift monitoring: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Model drift monitoring")
    parser.add_argument(
        '--lookback-days',
        type=int,
        default=7,
        help='Days of recent data to analyze (default: 7)'
    )
    parser.add_argument(
        '--baseline-f1',
        type=float,
        default=0.7,
        help='Expected baseline F1 score (default: 0.7)'
    )
    parser.add_argument(
        '--alert-threshold',
        type=float,
        default=0.1,
        help='F1 degradation threshold for alerts (default: 0.1)'
    )

    args = parser.parse_args()

    monitor_model_drift(
        lookback_days=args.lookback_days,
        baseline_f1=args.baseline_f1,
        alert_threshold=args.alert_threshold
    )


if __name__ == "__main__":
    main()
