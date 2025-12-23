# Upgrade Guide: v1.0 → v2.0

This guide helps you migrate from the original Mini Banking Fraud Detection Prototype (v1.0) to the production-ready v2.0 system.

---

## Overview of Changes

**v1.0:** Basic prototype with core fraud detection
**v2.0:** Production-ready enterprise system with:
- ✅ Real-time webhook notifications
- ✅ Redis caching for performance
- ✅ CI/CD pipeline with automated testing
- ✅ Horizontal scaling (Docker + Kubernetes)
- ✅ Enhanced security and monitoring
- ✅ ML operations automation
- ✅ Data governance policies

---

## Breaking Changes

### 1. New Required Services

**v2.0 adds Redis as a required service:**

```yaml
# Old v1.0 docker-compose.yml (no Redis)
services:
  db:
    ...
  kafka:
    ...

# New v2.0 docker-compose.yml (includes Redis)
services:
  db:
    ...
  kafka:
    ...
  redis:  # NEW
    image: redis:7-alpine
```

### 2. New Environment Variables

**Required for v2.0:**

```env
# Redis Configuration (NEW)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_POOL_SIZE=10

# Cache TTL (NEW)
CACHE_TTL_ANOMALIES=60
CACHE_TTL_SHORT=30

# Webhook Notifications (OPTIONAL but recommended)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
# DISCORD_WEBHOOK_URL=...
# TEAMS_WEBHOOK_URL=...
# SMTP_SERVER=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USERNAME=...
# SMTP_PASSWORD=...

# Alert Thresholds (OPTIONAL)
HIGH_RISK_THRESHOLD=0.8
CRITICAL_RISK_THRESHOLD=0.9
HIGH_VALUE_THRESHOLD=5000.0
```

### 3. Updated Docker Compose Structure

**The docker-compose.yml has been enhanced with Redis.**

You have 2 options:
- **Option A:** Use standard `docker-compose.yml` (single instances + Redis)
- **Option B:** Use `docker-compose.scaled.yml` (multiple instances + load balancing)

---

## Step-by-Step Migration

### Step 1: Backup Current System

```bash
# Stop running services
docker-compose down

# Backup database
docker-compose exec db pg_dump -U user bankdb > backup_v1.sql

# Backup environment file
cp .env .env.v1.backup

# Commit current state to git
git add .
git commit -m "Backup: v1.0 state before upgrading to v2.0"
git tag v1.0.0-backup
```

---

### Step 2: Pull v2.0 Code

```bash
# Pull latest changes from repository
git pull origin main

# Or if you're upgrading manually, copy all new files:
# - cache_wrapper.py
# - notification_service.py
# - retrain_model.py
# - monitor_model_drift.py
# - schedule_retraining.py
# - archive_old_data.py
# - nginx.conf
# - docker-compose.scaled.yml
# - k8s/ directory
# - .github/ directory
# - All new documentation files
```

---

### Step 3: Update Environment Configuration

```bash
# Copy new environment template
cp .env.example .env.new

# Migrate your v1.0 settings to new .env
# 1. Copy existing values from .env.v1.backup
# 2. Add new required variables (Redis, notifications)
# 3. Rename .env.new to .env

# Example:
cat .env.v1.backup  # View old settings
nano .env           # Edit new file with old + new settings
```

**Minimum required additions:**

```env
# Add these to your .env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_POOL_SIZE=10
CACHE_TTL_ANOMALIES=60
CACHE_TTL_SHORT=30
```

---

### Step 4: Update Dependencies

```bash
# Install new Python dependencies
pip install -r requirements.txt

# New dependencies in v2.0:
# - redis==5.0.1
# - schedule==1.2.0
# - tenacity==8.2.3
```

---

### Step 5: Start Updated System

#### Option A: Standard Deployment (Single Instances)

```bash
# Start all services (includes Redis)
docker-compose up -d

# Verify Redis is running
docker-compose ps redis

# Check Redis connectivity
docker-compose exec redis redis-cli ping
# Should return: PONG

# Verify API can connect to Redis
docker-compose logs api | grep -i redis
# Should see: "Redis cache initialized successfully"
```

#### Option B: Scaled Deployment (Multiple Instances)

```bash
# Use scaled configuration
docker-compose -f docker-compose.scaled.yml up -d

# Verify all instances
docker-compose -f docker-compose.scaled.yml ps

# Check load balancer
curl http://localhost/health
```

---

### Step 6: Verify Migration

**1. Test API functionality:**

```bash
# Health check
curl http://localhost:8000/health

# Readiness check
curl http://localhost:8000/health/ready

# Get anomalies (should use cache)
curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/anomalies?limit=10
```

**2. Verify caching:**

```bash
# First request (cache miss)
time curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/anomalies?limit=100

# Second request (cache hit - should be faster)
time curl -H "X-API-Key: your-api-key" \
  http://localhost:8000/api/v1/anomalies?limit=100
```

**3. Check Redis cache:**

```bash
# View cached keys
docker-compose exec redis redis-cli KEYS "anomalies:*"

# Check cache stats
docker-compose exec redis redis-cli INFO stats
```

**4. Test notifications (if configured):**

```bash
# Send test notification
docker-compose exec api python -c "
from notification_service import NotificationService
from datetime import datetime

service = NotificationService()
test_tx = {
    'transaction_id': 'TEST_001',
    'account_id': 'ACC_TEST',
    'amount': 9500.0,
    'merchant_category': 'Gambling',
    'location': 'Unknown',
    'timestamp': datetime.now().isoformat(),
    'alert_reason': 'Test notification'
}
results = service.send_fraud_alert(test_tx, anomaly_score=0.95)
print(f'Sent to: {list(results.keys())}')
"
```

---

### Step 7: Restore Database (If Needed)

```bash
# If you need to restore from backup
docker-compose exec -T db psql -U user -d bankdb < backup_v1.sql
```

---

## Optional: Configure New Features

### 1. Enable Webhook Notifications

**Slack:**

```bash
# 1. Create Slack app: https://api.slack.com/apps
# 2. Enable Incoming Webhooks
# 3. Add webhook to workspace
# 4. Copy webhook URL
# 5. Add to .env:
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL" >> .env

# Restart services
docker-compose restart api detection_service
```

**Email:**

```bash
# Add to .env:
cat >> .env << EOF
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=fraud-alerts@company.com
EMAIL_TO=security@company.com
EOF

# Restart services
docker-compose restart detection_service
```

---

### 2. Set Up CI/CD Pipeline

**If using GitHub:**

```bash
# 1. Push code to GitHub
git remote add origin https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype.git
git push -u origin main

# 2. Add GitHub secrets (Settings → Secrets and variables → Actions):
# - AZURE_API_KEY
# - SLACK_WEBHOOK_URL (optional)
# - CODECOV_TOKEN (optional)

# 3. GitHub Actions will automatically run on next push
```

---

### 3. Enable Horizontal Scaling

**Docker Compose:**

```bash
# Use scaled deployment
docker-compose -f docker-compose.scaled.yml up -d

# Scale API instances dynamically
docker-compose -f docker-compose.scaled.yml up -d --scale api-1=5
```

**Kubernetes (Production):**

```bash
# See SCALING.md for full Kubernetes deployment guide

# Quick start:
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/secrets-configmap.yaml
kubectl apply -f k8s/ingress.yaml
```

---

## Troubleshooting

### Issue: "Connection refused" to Redis

**Cause:** Redis service not running

**Solution:**

```bash
# Check Redis status
docker-compose ps redis

# Start Redis
docker-compose up -d redis

# Verify connectivity
docker-compose exec redis redis-cli ping
```

---

### Issue: API still works but no cache hits

**Cause:** Cache is disabled if Redis connection fails

**Solution:**

```bash
# Check API logs for Redis errors
docker-compose logs api | grep -i redis

# Common issues:
# 1. Wrong REDIS_HOST (should be 'redis' in Docker Compose)
# 2. Wrong REDIS_PORT
# 3. Redis not started

# Verify environment variables
docker-compose exec api env | grep REDIS
```

---

### Issue: Notifications not sending

**Cause:** Webhook URLs not configured or invalid

**Solution:**

```bash
# Check detection service logs
docker-compose logs detection_service | grep -i notification

# Verify webhook URLs are set
docker-compose exec detection_service env | grep WEBHOOK

# Test webhook manually:
curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test message"}'
```

---

### Issue: Database connection errors after migration

**Cause:** Increased number of API instances

**Solution:**

```bash
# Increase PostgreSQL max_connections
# Edit docker-compose.yml:
db:
  environment:
    - POSTGRES_MAX_CONNECTIONS=200  # Increased from 100

# Restart database
docker-compose restart db
```

---

## Rollback to v1.0

**If you need to rollback:**

```bash
# Stop v2.0 services
docker-compose down

# Restore v1.0 environment
cp .env.v1.backup .env

# Restore v1.0 code
git checkout v1.0.0

# Restore database
docker-compose up -d db
docker-compose exec -T db psql -U user -d bankdb < backup_v1.sql

# Start v1.0 services
docker-compose up -d
```

---

## Performance Comparison

**Expected improvements in v2.0:**

| Metric | v1.0 | v2.0 (with caching) | Improvement |
|--------|------|---------------------|-------------|
| API Response Time (p95) | ~200-500ms | ~50-150ms | **60-70% faster** |
| Cache Hit Rate | N/A | 70-95% | **New feature** |
| Max Concurrent Requests | ~50 | ~500+ | **10x increase** |
| Horizontal Scaling | No | Yes (3-20 instances) | **New feature** |
| Notification Latency | N/A | <2s | **New feature** |
| Deployment Time | Manual | Automated (CI/CD) | **New feature** |

---

## Next Steps

After successful migration:

1. **Configure monitoring alerts** - See `NOTIFICATIONS.md`
2. **Set up CI/CD** - See `CI_CD.md`
3. **Plan horizontal scaling** - See `SCALING.md`
4. **Review security** - See `SECURITY.md`
5. **Configure data retention** - See `DATA_RETENTION.md`

---

## Support

**Documentation:**
- [NOTIFICATIONS.md](NOTIFICATIONS.md) - Webhook setup
- [CACHING.md](CACHING.md) - Redis caching
- [CI_CD.md](CI_CD.md) - CI/CD pipeline
- [SCALING.md](SCALING.md) - Horizontal scaling
- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment

**Issues:**
https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/issues

---

**Last Updated:** 2025-12-23
**Version:** 2.0.0
