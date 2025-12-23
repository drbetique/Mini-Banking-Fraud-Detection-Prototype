# Production Deployment Guide
## Fraud Detection System with Real-time Monitoring

**Version:** 1.0
**Last Updated:** 2025-12-20
**Target Audience:** DevOps Engineers, SREs, System Administrators

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Pre-Deployment Setup](#pre-deployment-setup)
4. [Deployment Steps](#deployment-steps)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring Setup](#monitoring-setup)
7. [Troubleshooting](#troubleshooting)
8. [Rollback Procedure](#rollback-procedure)
9. [Maintenance](#maintenance)

---

## System Overview

### Architecture

The fraud detection system consists of:

**Core Services:**
- **PostgreSQL Database** - Transaction storage (port 5432)
- **Kafka + Zookeeper** - Event streaming (ports 9092, 2181)
- **MLflow** - ML model management (port 5001)
- **Detection Service** - Real-time fraud scoring (metrics on 8001)
- **FastAPI** - REST API (port 8000)

**Monitoring Stack:**
- **Prometheus** - Metrics collection (port 9090)
- **Grafana** - Visualization and alerting (port 3000/3001)

**Optional:**
- **Streamlit** - Analyst dashboard (port 8501/8502)

### System Requirements

**Minimum (Development):**
- CPU: 4 cores
- RAM: 8 GB
- Disk: 50 GB
- OS: Linux/Windows/macOS with Docker

**Recommended (Production):**
- CPU: 8+ cores
- RAM: 16+ GB
- Disk: 200+ GB SSD
- OS: Ubuntu 22.04 LTS or RHEL 8+
- Docker: 24.0+
- Docker Compose: 2.20+

---

## Prerequisites

### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Verify installations
docker --version
docker compose version
```

### 2. Domain and SSL Setup

**Option A: Let's Encrypt (Free)**
```bash
sudo apt install certbot
sudo certbot certonly --standalone -d fraud-api.yourcompany.com
```

**Option B: Commercial SSL**
- Purchase certificate from CA
- Place files in `/etc/ssl/certs/` and `/etc/ssl/private/`

### 3. Network Configuration

```bash
# Configure firewall
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP (for cert renewal)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# Verify firewall status
sudo ufw status
```

---

## Pre-Deployment Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourcompany/fraud-detection.git
cd fraud-detection
```

### 2. Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Generate secure API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Edit .env with your values
nano .env
```

**Required variables:**
```env
DATABASE_URL=postgresql://fraud_user:SECURE_PASSWORD_HERE@db/bankdb
AZURE_API_KEY=YOUR_GENERATED_API_KEY_HERE
STRIPE_API_KEY=sk_live_YOUR_STRIPE_LIVE_KEY
ENVIRONMENT=production
FRONTEND_ORIGIN=https://fraud-dashboard.yourcompany.com
```

### 3. Initialize Database

**Create production database user:**
```sql
CREATE USER fraud_api WITH PASSWORD 'secure-password-here';
CREATE DATABASE bankdb OWNER fraud_api;
GRANT ALL PRIVILEGES ON DATABASE bankdb TO fraud_api;
```

### 4. Train ML Model

```bash
# Train the fraud detection model
python train_model.py

# Verify model in MLflow
# Model should appear at http://localhost:5001
```

---

## Deployment Steps

### 1. Build Docker Images

```bash
# Build all services
docker compose build

# Verify images
docker images | grep fraud-detection
```

### 2. Start Infrastructure Services

```bash
# Start database, Kafka, Zookeeper, MLflow
docker compose up -d db zookeeper kafka mlflow

# Wait for services to be ready (2-3 minutes)
docker compose ps

# Verify database is accessible
docker exec -it fraud-detection-db-1 pg_isready -U fraud_api
```

### 3. Initialize Database Schema

```bash
# Run database setup script
python setup_db.py

# Verify tables exist
docker exec -it fraud-detection-db-1 psql -U fraud_api -d bankdb -c "\dt"
```

### 4. Start Application Services

```bash
# Start detection service and API
docker compose up -d detection_service api

# Check logs for startup
docker compose logs -f detection_service api
```

### 5. Start Monitoring Stack

```bash
# Start Prometheus and Grafana
docker compose up -d prometheus grafana

# Verify metrics are being collected
curl http://localhost:9090/api/v1/targets
```

### 6. Configure Reverse Proxy (nginx)

**Install nginx:**
```bash
sudo apt install nginx
```

**Create config file: `/etc/nginx/sites-available/fraud-api`**
```nginx
upstream fraud_api {
    server localhost:8000;
}

server {
    listen 80;
    server_name fraud-api.yourcompany.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name fraud-api.yourcompany.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/fraud-api.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/fraud-api.yourcompany.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # API endpoints
    location /api/ {
        proxy_pass http://fraud_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (public)
    location /health {
        proxy_pass http://fraud_api;
        access_log off;
    }
}
```

**Enable site:**
```bash
sudo ln -s /etc/nginx/sites-available/fraud-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Post-Deployment Verification

### 1. Health Checks

```bash
# API health
curl https://fraud-api.yourcompany.com/health
# Expected: {"status":"healthy","timestamp":"...","service":"fraud-detection-api"}

# Database connectivity
curl https://fraud-api.yourcompany.com/health/ready
# Expected: {"status":"ready","checks":{"database":"ok"}}

# Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job, health}'
```

### 2. Test API Endpoint

```bash
# Authenticate and fetch anomalies
curl -H "X-API-Key: YOUR_API_KEY" \\
  https://fraud-api.yourcompany.com/api/v1/anomalies?limit=5
# Expected: {"data":[...],"count":5}
```

### 3. Verify Monitoring

- **Prometheus**: http://localhost:9090/alerts (all alerts should be green)
- **Grafana**: http://localhost:3001 (login: admin/admin)
- Navigate to "Fraud Detection - Production Monitoring" dashboard

### 4. Test Alert Flow

**Trigger a test alert:**
```bash
# Temporarily stop the API to trigger "APIServiceDown" alert
docker compose stop api

# Wait 2 minutes, check Prometheus alerts
curl http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'

# Restart API
docker compose start api
```

### 5. Process Test Transaction

```bash
# Send a test Stripe transaction
python producer_stripe.py

# Verify it appears in database
docker exec -it fraud-detection-db-1 psql -U fraud_api -d bankdb \\
  -c "SELECT transaction_id, amount, ml_anomaly_score FROM transactions ORDER BY timestamp DESC LIMIT 5;"
```

---

## Monitoring Setup

### Grafana Alert Notifications

**1. Configure Slack notifications:**
```bash
# In Grafana UI:
# Alerting → Contact points → New contact point
# Type: Slack
# Webhook URL: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**2. Configure PagerDuty:**
```bash
# Alerting → Contact points → New contact point
# Type: PagerDuty
# Integration Key: YOUR_PAGERDUTY_INTEGRATION_KEY
```

**3. Test notifications:**
```bash
# Alerting → Contact points → Test
# Should receive alert in Slack/PagerDuty
```

### Log Aggregation (Optional but Recommended)

**Option A: ELK Stack**
```yaml
# Add to docker-compose.yml
  elasticsearch:
    image: elasticsearch:8.11.0
    environment:
      - discovery.type=single-node

  logstash:
    image: logstash:8.11.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf

  kibana:
    image: kibana:8.11.0
    ports:
      - "5601:5601"
```

**Option B: Cloud Logging**
- AWS CloudWatch Logs
- Azure Monitor
- Google Cloud Logging

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
docker compose logs <service_name>
```

**Common issues:**

| Issue | Solution |
|-------|----------|
| Port already in use | `sudo lsof -i :8000` then kill process or change port |
| Out of memory | Increase Docker memory limit or add swap |
| Database connection failed | Verify DATABASE_URL and database is running |
| MLflow model not found | Run `train_model.py` and check MLflow UI |

### High Error Rate

**Check API logs:**
```bash
docker compose logs api | grep ERROR
```

**Check database connections:**
```bash
docker exec -it fraud-detection-db-1 psql -U fraud_api -d bankdb \\
  -c "SELECT count(*) FROM pg_stat_activity;"
```

### Kafka Consumer Lag

**Check consumer group status:**
```bash
docker exec fraud-detection-kafka-1 kafka-consumer-groups \\
  --bootstrap-server localhost:9092 \\
  --group fraud-detectors \\
  --describe
```

**Reset offset if needed:**
```bash
docker exec fraud-detection-kafka-1 kafka-consumer-groups \\
  --bootstrap-server localhost:9092 \\
  --group fraud-detectors \\
  --topic transactions_topic \\
  --reset-offsets --to-latest --execute
```

### Model Performance Degradation

**Check model metrics:**
```python
# Access MLflow UI at http://localhost:5001
# Compare current model metrics with historical baselines
```

**Retrain model:**
```bash
python train_model.py
docker compose restart detection_service
```

---

## Rollback Procedure

### 1. Quick Rollback (Container-based)

```bash
# Tag current state
docker compose down
git tag -a v1.0.1-rollback -m "Pre-update snapshot"

# Checkout previous version
git checkout <previous_commit_hash>

# Rebuild and restart
docker compose build
docker compose up -d
```

### 2. Database Rollback

```bash
# Restore from backup
docker exec -i fraud-detection-db-1 psql -U fraud_api -d bankdb < /backups/bankdb_YYYYMMDD.sql

# Verify restore
docker exec -it fraud-detection-db-1 psql -U fraud_api -d bankdb -c "SELECT count(*) FROM transactions;"
```

### 3. ML Model Rollback

```bash
# In MLflow UI (http://localhost:5001):
# Models → fraud-detection-model → Version X → Stage: Production
# Or via API:
curl -X POST http://localhost:5001/api/2.0/mlflow/model-versions/transition-stage \\
  -d '{"name":"fraud-detection-model","version":"2","stage":"Production"}'

# Restart detection service
docker compose restart detection_service
```

---

## Maintenance

### Daily Tasks

- Monitor Grafana dashboard for anomalies
- Review Prometheus alerts
- Check disk space: `df -h`

### Weekly Tasks

- Review security logs for suspicious activity
- Check for Docker image updates
- Verify backup integrity

### Monthly Tasks

- Test backup restoration
- Review and optimize database indexes
- Update dependencies and security patches
- Performance review and capacity planning

### Quarterly Tasks

- Rotate API keys and passwords (see SECURITY.md)
- Security audit
- Disaster recovery drill
- Review and update documentation

### Database Backup Automation

**Create backup script: `/opt/fraud-detection/backup.sh`**
```bash
#!/bin/bash
BACKUP_DIR="/backups/fraud-detection"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Database backup
docker exec fraud-detection-db-1 pg_dump -U fraud_api bankdb | \\
  gzip > $BACKUP_DIR/bankdb_$DATE.sql.gz

# Encrypt backup
gpg --encrypt --recipient backups@yourcompany.com $BACKUP_DIR/bankdb_$DATE.sql.gz

# Upload to S3 (optional)
aws s3 cp $BACKUP_DIR/bankdb_$DATE.sql.gz.gpg \\
  s3://yourcompany-fraud-detection-backups/

# Clean up old backups (keep last 30 days)
find $BACKUP_DIR -name "bankdb_*.sql.gz*" -mtime +30 -delete

echo "Backup completed: bankdb_$DATE.sql.gz"
```

**Add to crontab:**
```bash
sudo crontab -e
# Add line:
0 2 * * * /opt/fraud-detection/backup.sh >> /var/log/fraud-backup.log 2>&1
```

### Monitoring Alert Tuning

Review and adjust alert thresholds based on actual system performance:

**Edit `prometheus_alerts.yml`:**
```yaml
# Example: Adjust fraud spike threshold based on observed rates
- alert: HighRiskFraudSpike
  expr: rate(anomalies_detected_total[5m]) > 0.5  # Increased from 0.1
  for: 5m  # Increased from 2m to reduce false positives
```

**Reload Prometheus:**
```bash
docker compose restart prometheus
```

---

## Performance Optimization

### Database Indexing

```sql
-- Add indexes for common queries
CREATE INDEX idx_transactions_anomaly_score ON transactions(ml_anomaly_score DESC) WHERE is_anomaly = 1;
CREATE INDEX idx_transactions_status ON transactions(status) WHERE status IS NOT NULL;
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp DESC);
```

### API Caching (Optional)

For high-traffic deployments, add Redis caching:

```yaml
# docker-compose.yml
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

Update `api.py` to cache anomaly queries.

### Horizontal Scaling

**Scale detection service:**
```bash
docker compose up -d --scale detection_service=3
```

**Load balance API:**
```nginx
upstream fraud_api {
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}
```

---

## Compliance and Auditing

### Audit Log Queries

**View recent transaction status changes:**
```bash
docker compose logs api | grep "Transaction status updated"
```

**Export audit trail:**
```bash
docker compose logs api --since "2025-01-01" | \\
  grep "Transaction status updated" > audit_trail.log
```

### PCI DSS Compliance Checklist

- [ ] Database encrypted at rest
- [ ] TLS/SSL for all connections
- [ ] API key authentication enforced
- [ ] Audit logs retained for 1 year
- [ ] Regular security scans performed
- [ ] Access controls documented and enforced

---

## Support and Escalation

### Support Contacts

- **On-call Engineer**: oncall@yourcompany.com
- **Security Team**: security@yourcompany.com
- **Database Admin**: dba@yourcompany.com

### Escalation Matrix

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical (System down) | 15 minutes | Immediately notify on-call + manager |
| High (Performance degraded) | 1 hour | Notify on-call |
| Medium (Non-critical errors) | 4 hours | Create ticket |
| Low (Informational) | Next business day | Create ticket |

---

## Appendix

### A. Port Reference

| Service | Port | Public? | Purpose |
|---------|------|---------|---------|
| PostgreSQL | 5432 | No | Database |
| Kafka | 9092 | No | Event streaming |
| Zookeeper | 2181 | No | Kafka coordination |
| MLflow | 5001 | No | ML model registry |
| API | 8000 | Yes (via nginx) | REST API |
| Detection Service Metrics | 8001 | No | Prometheus scraping |
| Prometheus | 9090 | No | Metrics database |
| Grafana | 3001 | No (VPN only) | Monitoring dashboard |
| Streamlit | 8502 | No (VPN only) | Analyst dashboard |

### B. Environment Variables Reference

See `.env.example` for complete list with descriptions.

### C. API Endpoints

**Public Endpoints:**
- `GET /health` - Basic health check
- `GET /health/ready` - Readiness check with DB verification
- `GET /health/live` - Liveness check

**Authenticated Endpoints** (require X-API-Key):
- `GET /api/v1/anomalies` - Retrieve flagged transactions
- `PUT /api/v1/anomalies/{transaction_id}` - Update transaction status

**Full API documentation:** https://fraud-api.yourcompany.com/api/docs

---

**Document Version:** 1.0
**Last Review:** 2025-12-20
**Next Review Due:** 2025-03-20
**Maintained By:** DevOps Team
