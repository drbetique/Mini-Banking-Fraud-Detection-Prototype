-- Migration: Add performance indexes to transactions table
-- Purpose: Improve query performance for common access patterns
-- Author: Auto-generated from optimization plan
-- Date: 2025-12-14

-- Start transaction
BEGIN;

-- Add index for anomaly filtering (most common query pattern)
CREATE INDEX IF NOT EXISTS idx_transactions_is_anomaly
    ON transactions(is_anomaly)
    WHERE is_anomaly = 1;

-- Add index for status filtering
CREATE INDEX IF NOT EXISTS idx_transactions_status
    ON transactions(status);

-- Add index for account lookup (used in aggregates)
CREATE INDEX IF NOT EXISTS idx_transactions_account_id
    ON transactions(account_id);

-- Add index for timestamp ordering (used in time-based queries)
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp
    ON transactions(timestamp DESC);

-- Add composite index for score-based anomaly queries
CREATE INDEX IF NOT EXISTS idx_transactions_score
    ON transactions(ml_anomaly_score DESC)
    WHERE is_anomaly = 1;

-- Add composite index for account + timestamp (for aggregates)
CREATE INDEX IF NOT EXISTS idx_transactions_account_timestamp
    ON transactions(account_id, timestamp DESC);

-- Update table statistics for query planner
ANALYZE transactions;

-- Commit transaction
COMMIT;

-- Verification query (shows index usage)
-- SELECT schemaname, tablename, indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename = 'transactions'
-- ORDER BY indexname;
