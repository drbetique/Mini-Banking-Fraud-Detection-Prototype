# Data Retention and Archival Policy

## Overview

The fraud detection system implements a **tiered data retention strategy** to balance:
- **Performance**: Keep recent data readily accessible for fraud detection
- **Compliance**: Retain data for regulatory requirements (PCI DSS, GDPR, SOX)
- **Cost**: Archive old data to reduce database size and storage costs

---

## Retention Tiers

### Tier 1: Hot Storage (0-90 days)
**Location:** PostgreSQL primary database
**Access:** Real-time, full-speed queries
**Purpose:** Active fraud detection and investigation
**Retention:** 90 days

**Characteristics:**
- All API queries hit this tier
- Optimized indexes for fast retrieval
- Used by detection service for real-time scoring
- Analyst dashboard queries
- Immediately accessible

---

### Tier 2: Warm Storage (91-365 days)
**Location:** PostgreSQL archive table (`transactions_archive`)
**Access:** On-demand queries with moderate speed
**Purpose:** Historical analysis, compliance audits, model retraining
**Retention:** 365 days (1 year)

**Characteristics:**
- Separate table for performance isolation
- Fewer indexes (optimized for storage)
- Compressed storage where possible
- Accessible via SQL queries
- Used for annual fraud pattern analysis

---

### Tier 3: Cold Storage (1-7 years)
**Location:** Compressed files (S3/Azure Blob Storage/Local disk)
**Access:** Manual extraction and restoration required
**Purpose:** Long-term compliance, legal holds, forensic investigations
**Retention:** 7 years

**Characteristics:**
- Gzip-compressed JSON format
- Minimal cost per GB
- Infrequent access
- Restoration time: minutes to hours
- Immutable storage for compliance

---

### Tier 4: Purge (7+ years)
**Location:** Permanently deleted
**Access:** Not accessible
**Purpose:** Meet data minimization requirements
**Retention:** N/A

**Characteristics:**
- Irreversible deletion
- Documented purge audit trail
- Exception: legal holds prevent purging

---

## Compliance Requirements

### PCI DSS (Payment Card Industry)
**Requirement:** Retain transaction logs for minimum 1 year, available for 3 months

**Our Implementation:**
- ✅ 90 days in hot storage (immediate access)
- ✅ Additional 275 days in warm storage (on-demand access)
- ✅ Total: 365 days fully queryable

**Reference:** PCI DSS Requirement 10.7

---

### GDPR (General Data Protection Regulation)
**Requirement:** Data minimization and right to erasure

**Our Implementation:**
- ✅ 7-year maximum retention (unless legal hold)
- ✅ Automated purging after retention period
- ✅ Data subject deletion requests supported
- ✅ Audit trail of all archival/purge operations

**Reference:** GDPR Articles 5(1)(e), 17

---

### SOX (Sarbanes-Oxley Act)
**Requirement:** 7 years retention for financial records

**Our Implementation:**
- ✅ 7-year retention in tiered storage
- ✅ Immutable cold storage archives
- ✅ Audit trail of all data access

**Reference:** SOX Section 802

---

## Archival Pipeline

### Automated Archival

**Schedule:** Monthly (1st of each month at 2:00 AM)

**Process:**
```bash
# Automated via cron/scheduler
python archive_old_data.py
```

**Actions:**
1. **Hot → Warm**: Move transactions 90+ days old to archive table
2. **Warm → Cold**: Export transactions 365+ days old to compressed files
3. **Purge**: Delete transactions 7+ years old (after legal hold check)

---

### Manual Archival

**Trigger archival on-demand:**
```bash
# Dry run (preview changes)
python archive_old_data.py --dry-run

# Custom retention periods
python archive_old_data.py --retention-days 60 --archive-days 180

# Force archival
python archive_old_data.py
```

**Arguments:**
- `--retention-days`: Days in hot storage (default: 90)
- `--archive-days`: Days in warm storage (default: 365)
- `--purge-days`: Days before purge (default: 2555 / 7 years)
- `--dry-run`: Preview without changes

---

## Database Structure

### Primary Table

```sql
CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    account_id TEXT,
    timestamp TIMESTAMP,
    amount NUMERIC,
    merchant_category TEXT,
    location TEXT,
    is_fraud INTEGER,
    ml_anomaly_score REAL,
    alert_reason TEXT,
    is_anomaly INTEGER,
    status TEXT
);

-- Indexes for hot storage performance
CREATE INDEX idx_timestamp ON transactions(timestamp DESC);
CREATE INDEX idx_anomaly_score ON transactions(ml_anomaly_score DESC) WHERE is_anomaly = 1;
CREATE INDEX idx_status ON transactions(status) WHERE status IS NOT NULL;
```

### Archive Table

```sql
CREATE TABLE transactions_archive (
    LIKE transactions INCLUDING ALL,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Minimal indexes for storage efficiency
CREATE INDEX idx_archive_timestamp ON transactions_archive(timestamp);
CREATE INDEX idx_archive_archived_at ON transactions_archive(archived_at);
```

---

## Cold Storage Format

### File Structure

```
/backups/fraud-detection/archives/
├── transactions_archive_20240101_020000.json.gz
├── transactions_archive_20240201_020000.json.gz
├── transactions_archive_20240301_020000.json.gz
└── ...
```

### File Naming Convention

`transactions_archive_{CUTOFF_DATE}_{TIMESTAMP}.json.gz`

Example: `transactions_archive_20240101_020305.json.gz`
- Data older than: 2024-01-01
- Archived on: 2024-01-01 02:03:05

### File Format (JSON)

```json
[
  {
    "transaction_id": "TRX_0012512",
    "account_id": "ACC_0019",
    "timestamp": "2023-09-15T08:18:56",
    "amount": 7675.88,
    "merchant_category": "Electronics",
    "location": "Tampere",
    "is_fraud": 1,
    "ml_anomaly_score": 0.9656,
    "alert_reason": "ML Anomaly",
    "is_anomaly": 1,
    "status": "FRAUD"
  },
  ...
]
```

---

## Restoring Archived Data

### From Warm Storage (Archive Table)

**Query archived transactions:**
```sql
SELECT * FROM transactions_archive
WHERE timestamp BETWEEN '2024-01-01' AND '2024-12-31';
```

**Restore to hot storage:**
```sql
INSERT INTO transactions
SELECT transaction_id, account_id, timestamp, amount, merchant_category,
       location, is_fraud, ml_anomaly_score, alert_reason, is_anomaly, status
FROM transactions_archive
WHERE transaction_id IN ('TRX_0001', 'TRX_0002', ...);
```

---

### From Cold Storage (Compressed Files)

**Step 1: Download file**
```bash
# From S3
aws s3 cp s3://fraud-backups/transactions_archive_20240101_020000.json.gz .

# Or from local archive
cp /backups/fraud-detection/archives/transactions_archive_20240101_020000.json.gz .
```

**Step 2: Decompress and load**
```python
import gzip
import json
import pandas as pd
from sqlalchemy import create_engine

# Decompress
with gzip.open('transactions_archive_20240101_020000.json.gz', 'rt') as f:
    data = json.load(f)

# Load to DataFrame
df = pd.DataFrame(data)

# Insert to database
engine = create_engine("postgresql://user:password@localhost/bankdb")
df.to_sql('transactions_archive', engine, if_exists='append', index=False)
```

---

## Storage Estimations

### Hot Storage (90 days)

**Assumptions:**
- 10,000 transactions/day
- 500 bytes/transaction (avg)
- 90 days retention

**Calculation:**
```
10,000 tx/day × 90 days × 500 bytes = 450 MB
With indexes and overhead: ~1 GB
```

---

### Warm Storage (1 year)

**Assumptions:**
- 3.65 million transactions (10,000/day × 365 days)
- 500 bytes/transaction
- Minimal indexing

**Calculation:**
```
3,650,000 tx × 500 bytes = 1.8 GB
With minimal indexes: ~2.5 GB
```

---

### Cold Storage (7 years)

**Assumptions:**
- 25.5 million transactions (10,000/day × 7 years)
- 300 bytes/transaction (compressed)
- Gzip compression ratio: ~3:1

**Calculation:**
```
25,500,000 tx × 300 bytes / 3 = 2.5 GB compressed
Uncompressed: ~7.5 GB
```

**Total 7-year storage: ~11 GB**

---

## Monitoring & Alerts

### Database Size Monitoring

**Add to Prometheus:**
```yaml
# prometheus.yml
- job_name: 'postgres'
  static_configs:
    - targets: ['postgres-exporter:9187']
```

**Alert on size:**
```yaml
# prometheus_alerts.yml
- alert: DatabaseSizeExceeding
  expr: pg_database_size_bytes{datname="bankdb"} > 10737418240  # 10 GB
  for: 1h
  labels:
    severity: warning
  annotations:
    summary: "Database size exceeding 10 GB"
    description: "Consider running archival: python archive_old_data.py"
```

---

### Archival Pipeline Alerts

**Alert on failures:**
```bash
# In archive_old_data.py, add notification on error
# TODO: Send Slack/email notification on failure
```

**Track archival metrics:**
```python
# Add Prometheus metrics to archive_old_data.py
from prometheus_client import Counter, Gauge

archived_records = Counter('data_archived_total', 'Total records archived')
purged_records = Counter('data_purged_total', 'Total records purged')
hot_storage_size = Gauge('hot_storage_records', 'Records in hot storage')
```

---

## Deployment

### Automated Archival (Recommended)

**Option 1: Cron Job (Linux)**
```bash
# Edit crontab
crontab -e

# Run archival on 1st of each month at 2 AM
0 2 1 * * cd /opt/fraud-detection && /usr/bin/python3 archive_old_data.py >> /var/log/data-archival.log 2>&1
```

**Option 2: Windows Task Scheduler**
```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\fraud-detection\archive_old_data.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "DataArchival" -Description "Monthly data archival"
```

**Option 3: Docker Service**
```yaml
# Add to docker-compose.yml
  archival-scheduler:
    build:
      context: .
      dockerfile: Dockerfile.api
    volumes:
      - .:/app
      - /backups:/backups
    environment:
      - DATABASE_URL=postgresql://user:password@db/bankdb
      - ARCHIVE_PATH=/backups/fraud-detection/archives
    depends_on:
      - db
    command: sh -c "while true; do python archive_old_data.py; sleep 2592000; done"  # 30 days
```

---

## Best Practices

### 1. Regular Monitoring
- Review archival logs monthly
- Monitor database size weekly
- Verify cold storage backups quarterly

### 2. Test Restoration
- Test warm storage restoration monthly
- Test cold storage restoration quarterly
- Document restoration procedures

### 3. Legal Holds
Before purging data:
- Check for active legal holds
- Verify compliance retention requirements
- Document purge decisions

### 4. Access Controls
- Restrict cold storage access to authorized personnel
- Audit all archive/restore operations
- Encrypt cold storage files

### 5. Disaster Recovery
- Replicate cold storage to multiple locations
- Test disaster recovery procedures annually
- Maintain off-site backups

---

## Compliance Checklist

- [ ] Data retention policy documented
- [ ] Automated archival pipeline configured
- [ ] Cold storage backups tested
- [ ] Purge procedures documented
- [ ] Legal hold process defined
- [ ] Audit trail of all archival operations
- [ ] Access controls implemented
- [ ] Encryption enabled for archives
- [ ] Restoration procedures tested
- [ ] Compliance requirements validated

---

## Troubleshooting

### Archive Table Not Created

**Error:** "relation 'transactions_archive' does not exist"

**Solution:**
```bash
python archive_old_data.py  # Will create automatically
```

---

### Disk Space Issues

**Error:** "No space left on device"

**Solution:**
```bash
# Check current disk usage
df -h

# Run archival to free space
python archive_old_data.py

# Or manually delete old cold storage files
rm /backups/fraud-detection/archives/transactions_archive_2018*.json.gz
```

---

### Restoration Fails

**Error:** "Duplicate key value violates unique constraint"

**Solution:**
```sql
-- Check for duplicates before inserting
SELECT transaction_id, COUNT(*)
FROM transactions_archive
WHERE transaction_id IN (SELECT transaction_id FROM transactions)
GROUP BY transaction_id;

-- Insert only non-duplicates
INSERT INTO transactions
SELECT * FROM transactions_archive
WHERE transaction_id NOT IN (SELECT transaction_id FROM transactions);
```

---

## FAQ

**Q: Can I change retention periods?**
A: Yes, modify via command-line arguments:
```bash
python archive_old_data.py --retention-days 60 --archive-days 180
```

**Q: How do I restore a specific transaction?**
A: Query warm storage first, then cold storage if needed. See "Restoring Archived Data" section.

**Q: What happens if archival fails?**
A: No data is lost. The script uses transactions so partial failures are rolled back. Review logs and retry.

**Q: Can I pause archival temporarily?**
A: Yes, disable the cron job or scheduled task. Resume when ready.

**Q: How do I handle GDPR deletion requests?**
A: Delete from all tiers:
```sql
-- Hot storage
DELETE FROM transactions WHERE account_id = 'ACC_XXXXX';

-- Warm storage
DELETE FROM transactions_archive WHERE account_id = 'ACC_XXXXX';

-- Cold storage: Manual - find and delete affected archive files
```

---

## References

- **PCI DSS Requirements**: https://www.pcisecuritystandards.org/
- **GDPR Compliance**: https://gdpr.eu/
- **SOX Compliance**: https://www.sox-online.com/
- **PostgreSQL Table Partitioning**: https://www.postgresql.org/docs/current/ddl-partitioning.html

---

**Last Updated:** 2025-12-20
**Version:** 1.0
**Maintained By:** Data Governance Team
