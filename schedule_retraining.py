"""
Model Retraining Scheduler
==========================

Runs automated model retraining on a schedule.

Schedules:
    - Weekly retraining: Every Sunday at 2:00 AM
    - Daily model performance monitoring: Every day at midnight

Usage:
    # Run as a service
    python schedule_retraining.py

    # Run specific job once
    python schedule_retraining.py --job weekly
    python schedule_retraining.py --job monitor
"""

import os
import time
import argparse
import logging
import subprocess
from datetime import datetime
import schedule

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('retraining_scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_weekly_retraining():
    """Runs weekly model retraining."""
    logger.info("=" * 60)
    logger.info("Starting Weekly Model Retraining")
    logger.info("=" * 60)

    try:
        # Run retraining with 90 days lookback
        result = subprocess.run(
            ['python', 'retrain_model.py', '--lookback-days', '90'],
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info("Weekly retraining completed successfully")
            logger.info(result.stdout)
        else:
            logger.error(f"Weekly retraining failed with code {result.returncode}")
            logger.error(result.stderr)
            # TODO: Send alert notification

    except subprocess.TimeoutExpired:
        logger.error("Weekly retraining timed out after 1 hour")
        # TODO: Send alert notification

    except Exception as e:
        logger.error(f"Error running weekly retraining: {e}", exc_info=True)
        # TODO: Send alert notification


def run_model_performance_monitor():
    """Monitors current production model performance."""
    logger.info("Running model performance monitoring...")

    try:
        result = subprocess.run(
            ['python', 'monitor_model_drift.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            logger.info("Model performance monitoring completed")
            logger.debug(result.stdout)
        else:
            logger.warning(f"Model monitoring reported issues: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error("Model monitoring timed out")

    except FileNotFoundError:
        logger.debug("monitor_model_drift.py not found - skipping")

    except Exception as e:
        logger.error(f"Error running model monitoring: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="Model retraining scheduler")
    parser.add_argument(
        '--job',
        choices=['weekly', 'monitor'],
        help='Run specific job once and exit'
    )

    args = parser.parse_args()

    # Run specific job once
    if args.job == 'weekly':
        run_weekly_retraining()
        return
    elif args.job == 'monitor':
        run_model_performance_monitor()
        return

    # Run scheduler continuously
    logger.info("Starting model retraining scheduler...")
    logger.info("Weekly retraining: Every Sunday at 02:00")
    logger.info("Performance monitoring: Daily at 00:00")

    # Schedule jobs
    schedule.every().sunday.at("02:00").do(run_weekly_retraining)
    schedule.every().day.at("00:00").do(run_model_performance_monitor)

    # Keep the script running
    logger.info("Scheduler is running. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute

    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


if __name__ == "__main__":
    main()
