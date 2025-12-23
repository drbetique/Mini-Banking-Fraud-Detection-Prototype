# Automated Model Retraining Pipeline

## Overview

The fraud detection system includes an automated model retraining pipeline that:
- **Monitors** model performance continuously
- **Detects** model drift and performance degradation
- **Retrains** models automatically on a schedule
- **Evaluates** new models against current production
- **Promotes** better-performing models automatically

---

## Components

### 1. `retrain_model.py` - Automated Retraining Script

**Features:**
- Fetches recent transaction data (configurable lookback period)
- Validates data quality before training
- Engineers features consistent with production detection
- Trains new Isolation Forest model
- Evaluates performance on test set
- Compares against current production model
- Promotes only if performance improves

**Usage:**
```bash
# Standard weekly retraining (90 days of data)
python retrain_model.py

# Custom configuration
python retrain_model.py --lookback-days 60 --min-samples 500

# Force promotion (skip performance check)
python retrain_model.py --force-promotion
```

**Arguments:**
- `--min-samples`: Minimum training samples required (default: 1000)
- `--lookback-days`: Days of historical data to use (default: 90)
- `--force-promotion`: Skip performance comparison and force promotion

**Output:**
- MLflow run with all metrics logged
- Model registered in MLflow Model Registry
- Automatic promotion to Production (if performance improves)
- Or tagged as Staging for manual review

---

### 2. `monitor_model_drift.py` - Performance Monitoring

**Features:**
- Calculates real-time model performance metrics
- Compares predictions vs actual fraud labels
- Detects model drift and performance degradation
- Pushes metrics to Prometheus for alerting
- Generates detailed performance reports

**Usage:**
```bash
# Monitor performance over last 7 days
python monitor_model_drift.py

# Custom monitoring window
python monitor_model_drift.py --lookback-days 14 --baseline-f1 0.75
```

**Arguments:**
- `--lookback-days`: Days of data to analyze (default: 7)
- `--baseline-f1`: Expected baseline F1 score (default: 0.7)
- `--alert-threshold`: F1 degradation threshold (default: 0.1)

**Metrics Calculated:**
- Precision, Recall, F1 Score
- False Positive/Negative Rates
- Confusion Matrix (TP, FP, TN, FN)
- Fraud detection rate

**Drift Detection Triggers:**
- F1 score drops below threshold
- Excessive fraud predictions (>80%)
- Too few fraud predictions (<0.1%)
- High false positive rate (>30%)
- High false negative rate (>50%)

---

### 3. `schedule_retraining.py` - Automated Scheduler

**Features:**
- Runs retraining on a weekly schedule (Sundays at 2 AM)
- Runs performance monitoring daily (midnight)
- Logs all activities
- Handles errors and timeouts gracefully

**Usage:**
```bash
# Run scheduler as a service
python schedule_retraining.py

# Run specific job once
python schedule_retraining.py --job weekly     # Retrain now
python schedule_retraining.py --job monitor    # Monitor now
```

**Schedule Configuration:**
- **Weekly Retraining**: Every Sunday at 02:00
- **Daily Monitoring**: Every day at 00:00

---

## Deployment

### Development/Testing

**1. Install dependencies:**
```bash
pip install -r requirements.txt
```

**2. Test retraining pipeline:**
```bash
# Ensure you have sufficient data (min 1000 transactions)
python retrain_model.py --min-samples 100 --lookback-days 30
```

**3. Test monitoring:**
```bash
python monitor_model_drift.py --lookback-days 7
```

---

### Production Deployment

#### Option 1: Docker Service

**Add to `docker-compose.yml`:**
```yaml
  retraining-scheduler:
    build:
      context: .
      dockerfile: Dockerfile.api
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://user:password@db/bankdb
      - MLFLOW_TRACKING_URI=http://mlflow:5000
    depends_on:
      - db
      - mlflow
    command: python schedule_retraining.py
    restart: unless-stopped
```

**Start the service:**
```bash
docker-compose up -d retraining-scheduler
```

---

#### Option 2: Cron Job (Linux)

**Create cron entries:**
```bash
# Edit crontab
crontab -e

# Add weekly retraining (Sundays at 2 AM)
0 2 * * 0 cd /opt/fraud-detection && /usr/bin/python3 retrain_model.py >> /var/log/fraud-retraining.log 2>&1

# Add daily monitoring (midnight)
0 0 * * * cd /opt/fraud-detection && /usr/bin/python3 monitor_model_drift.py >> /var/log/fraud-monitoring.log 2>&1
```

---

#### Option 3: Windows Task Scheduler

**Create scheduled task:**
```powershell
# Weekly retraining
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\fraud-detection\retrain_model.py"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "FraudModelRetraining" -Description "Weekly fraud detection model retraining"

# Daily monitoring
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\fraud-detection\monitor_model_drift.py"
$trigger = New-ScheduledTaskTrigger -Daily -At 12am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "FraudModelMonitoring" -Description "Daily model drift monitoring"
```

---

## Model Promotion Logic

### Automatic Promotion Criteria

A new model is automatically promoted to Production if:

1. **Data Quality Passed**: Minimum sample count met, no excessive nulls
2. **Training Succeeded**: Model trained without errors
3. **Performance Improved**: F1 score improvement ≥ 0.02 (2%)

### Manual Review Cases

New models are tagged as **Staging** for manual review when:

- F1 improvement < 2% (marginal improvement)
- F1 degradation (performance worse than production)
- First model being trained (no production baseline)

### Archival

When a new model is promoted to Production:
- Previous Production model → Archived
- Model versions retained in MLflow for rollback

---

## Monitoring & Alerting

### Prometheus Metrics

The monitoring script exposes these metrics:

| Metric | Description |
|--------|-------------|
| `model_current_f1_score` | Current F1 score of production model |
| `model_current_precision` | Current precision |
| `model_current_recall` | Current recall |
| `model_drift_detected` | Binary flag (1=drift, 0=stable) |

### Grafana Alerts

**Add to `prometheus_alerts.yml`:**
```yaml
- alert: ModelDriftDetected
  expr: model_drift_detected == 1
  for: 5m
  labels:
    severity: warning
    service: ml-model
  annotations:
    summary: "Model drift detected"
    description: "Production model performance has degraded. Consider retraining."

- alert: ModelF1ScoreLow
  expr: model_current_f1_score < 0.5
  for: 10m
  labels:
    severity: critical
    service: ml-model
  annotations:
    summary: "Model F1 score critically low"
    description: "F1 score is {{ $value }}. Immediate retraining required."
```

---

## MLflow Model Registry

### View Models

**Access MLflow UI:**
```bash
# http://localhost:5001
```

**Navigate to:** Models → `fraud-detection-model`

### Model Stages

| Stage | Description |
|-------|-------------|
| **None** | Newly trained, not yet evaluated |
| **Staging** | Awaiting manual review |
| **Production** | Currently deployed model |
| **Archived** | Previous production versions |

### Manual Model Promotion

```python
from mlflow.tracking import MlflowClient

client = MlflowClient(tracking_uri="http://localhost:5001")

# Promote specific version to Production
client.transition_model_version_stage(
    name="fraud-detection-model",
    version="5",
    stage="Production"
)
```

### Model Rollback

```bash
# In MLflow UI:
# 1. Navigate to Models → fraud-detection-model
# 2. Find desired version in Archived stage
# 3. Click "Transition to" → "Production"

# Restart detection service to load new model
docker-compose restart detection_service
```

---

## Performance Baselines

### Expected Metrics

Based on training data:

| Metric | Expected Value | Alert Threshold |
|--------|---------------|-----------------|
| F1 Score | 0.70 - 0.85 | < 0.60 |
| Precision | 0.65 - 0.80 | < 0.50 |
| Recall | 0.70 - 0.90 | < 0.60 |
| False Positive Rate | 0.05 - 0.15 | > 0.30 |
| False Negative Rate | 0.10 - 0.30 | > 0.50 |

### Performance Trends

Monitor these trends over time:
- **Declining F1 Score**: Indicates model drift, retrain needed
- **Increasing FPR**: Too many false alarms, adjust threshold
- **Increasing FNR**: Missing real fraud, retrain with more fraud examples

---

## Troubleshooting

### Retraining Fails

**Error: "Insufficient data"**
```bash
# Solution: Lower minimum sample requirement
python retrain_model.py --min-samples 500
```

**Error: "Data quality check failed"**
```bash
# Solution: Check database for null values or invalid data
docker exec -it fraud-detection-db-1 psql -U fraud_api -d bankdb -c "SELECT COUNT(*) FROM transactions WHERE amount IS NULL OR amount <= 0;"
```

**Error: "MLflow connection failed"**
```bash
# Solution: Ensure MLflow is running
docker-compose ps mlflow
docker-compose logs mlflow
```

### Model Not Promoted

**Check retraining logs:**
```bash
# View last retraining run in MLflow UI
# http://localhost:5001 → Experiments → "Fraud Detection - Automated Retraining"
```

**Common reasons:**
- F1 improvement < 2% threshold
- New model performs worse than production
- Insufficient test samples for reliable evaluation

**Force promotion if needed:**
```bash
python retrain_model.py --force-promotion
docker-compose restart detection_service
```

### Monitoring Shows Drift

**Immediate actions:**
1. Verify drift is real (check recent transaction data quality)
2. Run manual retraining: `python retrain_model.py`
3. Review new model performance in MLflow
4. If improved, model will auto-promote; otherwise investigate root cause

**Root cause analysis:**
- **Data distribution changed**: New fraud patterns emerged
- **Seasonal effects**: Holiday spending patterns differ
- **Labeling issues**: Incorrect fraud labels in recent data
- **System changes**: Detection thresholds modified

---

## Best Practices

### 1. Regular Monitoring

- Review MLflow runs weekly
- Check Grafana model performance dashboard daily
- Investigate any drift alerts immediately

### 2. Data Quality

- Ensure fraud labels are accurate
- Maintain minimum 1000 samples per retraining
- Use 90-day lookback to capture seasonal patterns

### 3. Model Versioning

- Never delete archived models (needed for rollback)
- Tag important model versions with descriptions
- Document any manual promotions/rollbacks

### 4. Testing

- Test retraining pipeline in staging environment first
- Validate new models on recent data before production
- Monitor performance for 24 hours after promotion

### 5. Incident Response

**If model promotes but causes issues:**
```bash
# 1. Immediate rollback
# In MLflow UI: Transition previous Archived version to Production

# 2. Restart detection service
docker-compose restart detection_service

# 3. Investigate root cause
python monitor_model_drift.py --lookback-days 1

# 4. Document incident for future prevention
```

---

## Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Review retraining logs | Weekly | Check `retraining_scheduler.log` |
| Verify model metrics | Weekly | MLflow UI review |
| Test manual retraining | Monthly | `python retrain_model.py --force-promotion` |
| Audit archived models | Quarterly | Clean up old versions (keep last 10) |
| Performance baseline review | Quarterly | Adjust alert thresholds if needed |

---

## References

- **MLflow Documentation**: https://mlflow.org/docs/latest/index.html
- **Scikit-learn Isolation Forest**: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- **Model Monitoring Best Practices**: https://www.evidentlyai.com/ml-in-production/model-monitoring

---

**Last Updated:** 2025-12-20
**Version:** 1.0
**Maintained By:** ML Engineering Team
