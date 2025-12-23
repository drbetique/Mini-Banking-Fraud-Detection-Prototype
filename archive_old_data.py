"""
Data Archival and Retention Policy Script
==========================================

Implements tiered data retention strategy:
- Hot storage (0-90 days): PostgreSQL - Full access
- Warm storage (91-365 days): Compressed PostgreSQL partition - Limited access
- Cold storage (365+ days): S3/File archive - Archive only
- Purge (7+ years): Deleted per compliance requirements

Usage:
    python archive_old_data.py [--retention-days DAYS] [--dry-run]

Arguments:
    --retention-days: Days to keep in hot storage (default: 90)
    --archive-days: Days to keep in warm storage (default: 365)
    --purge-days: Days before purging data (default: 2555 / 7 years)
    --dry-run: Show what would be archived without making changes
"""

import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Tuple
import gzip
import json

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configuration
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
TABLE_NAME = "transactions"
ARCHIVE_PATH = os.environ.get("ARCHIVE_PATH", "/backups/fraud-detection/archives")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_archival.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ArchivalError(Exception):
    """Raised when archival operation fails."""
    pass


def create_archive_tables(engine) -> None:
    """
    Creates archive table if it doesn't exist.

    The archive table has the same schema as the main table but is optimized
    for storage (compressed, no indexes for fast writes).
    """
    logger.info("Ensuring archive table exists...")

    create_archive_sql = f"""
    CREATE TABLE IF NOT EXISTS {TABLE_NAME}_archive (
        LIKE {TABLE_NAME} INCLUDING ALL
    );

    -- Add archival metadata
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = '{TABLE_NAME}_archive'
            AND column_name = 'archived_at'
        ) THEN
            ALTER TABLE {TABLE_NAME}_archive
            ADD COLUMN archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
        END IF;
    END $$;

    -- Create index on archived_at for efficient queries
    CREATE INDEX IF NOT EXISTS idx_archive_archived_at
    ON {TABLE_NAME}_archive(archived_at);
    """

    with engine.connect() as conn:
        conn.execute(text(create_archive_sql))
        conn.commit()

    logger.info("Archive table ready")


def get_archival_stats(engine, retention_days: int, archive_days: int, purge_days: int) -> dict:
    """
    Gets statistics on data eligible for archival/purge.

    Args:
        engine: Database engine
        retention_days: Days to keep in hot storage
        archive_days: Days to keep in warm storage
        purge_days: Days before purging data

    Returns:
        Dictionary with counts for each tier
    """
    hot_cutoff = datetime.now() - timedelta(days=retention_days)
    warm_cutoff = datetime.now() - timedelta(days=archive_days)
    purge_cutoff = datetime.now() - timedelta(days=purge_days)

    stats_query = text(f"""
    SELECT
        COUNT(*) FILTER (WHERE timestamp >= :hot_cutoff) as hot_storage_count,
        COUNT(*) FILTER (WHERE timestamp < :hot_cutoff AND timestamp >= :warm_cutoff) as warm_storage_count,
        COUNT(*) FILTER (WHERE timestamp < :warm_cutoff AND timestamp >= :purge_cutoff) as cold_storage_count,
        COUNT(*) FILTER (WHERE timestamp < :purge_cutoff) as purge_eligible_count,
        COUNT(*) as total_count,
        MIN(timestamp) as oldest_record,
        MAX(timestamp) as newest_record
    FROM {TABLE_NAME}
    """)

    with engine.connect() as conn:
        result = conn.execute(stats_query, {
            "hot_cutoff": hot_cutoff,
            "warm_cutoff": warm_cutoff,
            "purge_cutoff": purge_cutoff
        }).fetchone()

    stats = {
        'hot_storage_count': result[0],
        'warm_storage_count': result[1],
        'cold_storage_count': result[2],
        'purge_eligible_count': result[3],
        'total_count': result[4],
        'oldest_record': result[5],
        'newest_record': result[6],
        'hot_cutoff': hot_cutoff,
        'warm_cutoff': warm_cutoff,
        'purge_cutoff': purge_cutoff
    }

    return stats


def archive_to_warm_storage(engine, retention_days: int, dry_run: bool = False) -> int:
    """
    Moves old transactions from hot to warm storage (archive table).

    Args:
        engine: Database engine
        retention_days: Days to keep in hot storage
        dry_run: If True, only show what would be archived

    Returns:
        Number of records archived
    """
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    logger.info(f"Archiving transactions older than {cutoff_date.date()}...")

    if dry_run:
        # Count records that would be archived
        count_query = text(f"""
        SELECT COUNT(*) FROM {TABLE_NAME}
        WHERE timestamp < :cutoff_date
        AND transaction_id NOT IN (SELECT transaction_id FROM {TABLE_NAME}_archive)
        """)

        with engine.connect() as conn:
            count = conn.execute(count_query, {"cutoff_date": cutoff_date}).scalar()

        logger.info(f"DRY RUN: Would archive {count} records to warm storage")
        return count

    # Move data to archive table
    archive_query = text(f"""
    INSERT INTO {TABLE_NAME}_archive
    SELECT *, CURRENT_TIMESTAMP as archived_at
    FROM {TABLE_NAME}
    WHERE timestamp < :cutoff_date
    AND transaction_id NOT IN (SELECT transaction_id FROM {TABLE_NAME}_archive)
    ON CONFLICT (transaction_id) DO NOTHING
    """)

    with engine.connect() as conn:
        result = conn.execute(archive_query, {"cutoff_date": cutoff_date})
        archived_count = result.rowcount
        conn.commit()

    logger.info(f"Archived {archived_count} records to warm storage")

    # Optionally delete from main table to free space
    # Commented out by default for safety
    # delete_query = text(f"""
    # DELETE FROM {TABLE_NAME}
    # WHERE timestamp < :cutoff_date
    # AND transaction_id IN (SELECT transaction_id FROM {TABLE_NAME}_archive)
    # """)
    #
    # with engine.connect() as conn:
    #     result = conn.execute(delete_query, {"cutoff_date": cutoff_date})
    #     conn.commit()
    # logger.info(f"Deleted {result.rowcount} records from hot storage")

    return archived_count


def export_to_cold_storage(engine, archive_days: int, dry_run: bool = False) -> Tuple[int, str]:
    """
    Exports very old transactions to cold storage (compressed files).

    Args:
        engine: Database engine
        archive_days: Days after which to move to cold storage
        dry_run: If True, only show what would be exported

    Returns:
        Tuple of (record count, file path)
    """
    cutoff_date = datetime.now() - timedelta(days=archive_days)

    logger.info(f"Exporting transactions older than {cutoff_date.date()} to cold storage...")

    # Fetch data to export
    export_query = text(f"""
    SELECT * FROM {TABLE_NAME}_archive
    WHERE timestamp < :cutoff_date
    ORDER BY timestamp
    """)

    with engine.connect() as conn:
        df = pd.read_sql_query(export_query, conn, params={"cutoff_date": cutoff_date})

    if df.empty:
        logger.info("No records eligible for cold storage")
        return 0, ""

    if dry_run:
        logger.info(f"DRY RUN: Would export {len(df)} records to cold storage")
        return len(df), ""

    # Create archive directory
    os.makedirs(ARCHIVE_PATH, exist_ok=True)

    # Export to compressed JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"transactions_archive_{cutoff_date.strftime('%Y%m%d')}_{timestamp}.json.gz"
    filepath = os.path.join(ARCHIVE_PATH, filename)

    # Convert to JSON and compress
    json_data = df.to_json(orient='records', date_format='iso')

    with gzip.open(filepath, 'wt', encoding='utf-8') as f:
        f.write(json_data)

    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    logger.info(f"Exported {len(df)} records to {filepath} ({file_size_mb:.2f} MB)")

    # TODO: Upload to S3/Azure Blob Storage
    # upload_to_cloud_storage(filepath)

    return len(df), filepath


def purge_old_data(engine, purge_days: int, dry_run: bool = False) -> int:
    """
    Permanently deletes data older than retention policy (e.g., 7 years).

    Args:
        engine: Database engine
        purge_days: Days before purging data
        dry_run: If True, only show what would be purged

    Returns:
        Number of records purged
    """
    cutoff_date = datetime.now() - timedelta(days=purge_days)

    logger.warning(f"Purging transactions older than {cutoff_date.date()} (PERMANENT)...")

    if dry_run:
        # Count records that would be purged
        count_query = text(f"""
        SELECT COUNT(*) FROM {TABLE_NAME}_archive
        WHERE timestamp < :cutoff_date
        """)

        with engine.connect() as conn:
            count = conn.execute(count_query, {"cutoff_date": cutoff_date}).scalar()

        logger.info(f"DRY RUN: Would purge {count} records (older than {purge_days} days)")
        return count

    # Delete from archive table
    purge_query = text(f"""
    DELETE FROM {TABLE_NAME}_archive
    WHERE timestamp < :cutoff_date
    """)

    with engine.connect() as conn:
        result = conn.execute(purge_query, {"cutoff_date": cutoff_date})
        purged_count = result.rowcount
        conn.commit()

    logger.warning(f"PURGED {purged_count} records older than {purge_days} days")

    return purged_count


def run_archival_pipeline(
    retention_days: int = 90,
    archive_days: int = 365,
    purge_days: int = 2555,  # 7 years
    dry_run: bool = False
) -> None:
    """
    Main archival pipeline.

    Args:
        retention_days: Days to keep in hot storage
        archive_days: Days to keep in warm storage before cold archival
        purge_days: Days before purging data permanently
        dry_run: If True, only show what would be done
    """
    logger.info("=" * 60)
    logger.info("Data Archival and Retention Pipeline")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Hot Storage Retention: {retention_days} days")
    logger.info(f"Warm Storage Retention: {archive_days} days")
    logger.info(f"Purge After: {purge_days} days ({purge_days / 365:.1f} years)")
    logger.info("=" * 60)

    engine = create_engine(DATABASE_URL)

    try:
        # Step 1: Create archive tables if needed
        if not dry_run:
            create_archive_tables(engine)

        # Step 2: Get current statistics
        stats = get_archival_stats(engine, retention_days, archive_days, purge_days)

        logger.info("Current Data Distribution:")
        logger.info(f"  Hot Storage (0-{retention_days} days): {stats['hot_storage_count']:,} records")
        logger.info(f"  Warm Storage ({retention_days}-{archive_days} days): {stats['warm_storage_count']:,} records")
        logger.info(f"  Cold Storage ({archive_days}-{purge_days} days): {stats['cold_storage_count']:,} records")
        logger.info(f"  Purge Eligible ({purge_days}+ days): {stats['purge_eligible_count']:,} records")
        logger.info(f"  Total: {stats['total_count']:,} records")
        logger.info(f"  Oldest Record: {stats['oldest_record']}")
        logger.info(f"  Newest Record: {stats['newest_record']}")
        logger.info("")

        # Step 3: Archive to warm storage
        archived_count = archive_to_warm_storage(engine, retention_days, dry_run)

        # Step 4: Export to cold storage
        exported_count, export_path = export_to_cold_storage(engine, archive_days, dry_run)

        # Step 5: Purge old data
        if stats['purge_eligible_count'] > 0:
            purged_count = purge_old_data(engine, purge_days, dry_run)
        else:
            purged_count = 0
            logger.info("No records eligible for purging")

        # Summary
        logger.info("=" * 60)
        logger.info("Archival Pipeline Summary:")
        logger.info(f"  Records Archived (Hot → Warm): {archived_count}")
        logger.info(f"  Records Exported (Warm → Cold): {exported_count}")
        logger.info(f"  Records Purged: {purged_count}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Archival pipeline failed: {e}", exc_info=True)
        raise

    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Data archival and retention policy implementation"
    )
    parser.add_argument(
        '--retention-days',
        type=int,
        default=90,
        help='Days to keep in hot storage (default: 90)'
    )
    parser.add_argument(
        '--archive-days',
        type=int,
        default=365,
        help='Days to keep in warm storage before cold archival (default: 365)'
    )
    parser.add_argument(
        '--purge-days',
        type=int,
        default=2555,  # ~7 years
        help='Days before purging data permanently (default: 2555 / 7 years)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be archived without making changes'
    )

    args = parser.parse_args()

    run_archival_pipeline(
        retention_days=args.retention_days,
        archive_days=args.archive_days,
        purge_days=args.purge_days,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
