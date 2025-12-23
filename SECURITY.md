# Security Best Practices - Fraud Detection System

## Table of Contents
1. [Secrets Management](#secrets-management)
2. [API Security](#api-security)
3. [Database Security](#database-security)
4. [Container Security](#container-security)
5. [Network Security](#network-security)
6. [Monitoring & Incident Response](#monitoring--incident-response)
7. [Production Deployment Checklist](#production-deployment-checklist)

---

## Secrets Management

### Environment Variables

**CRITICAL: Never commit secrets to version control**

1. **Copy the template:**
   ```bash
   cp .env.example .env
   ```

2. **Generate secure API keys:**
   ```bash
   # Generate a secure random API key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Update all default values in `.env`:**
   - DATABASE_URL password
   - AZURE_API_KEY / API_KEY
   - STRIPE_API_KEY (use live key for production)

### Docker Secrets (Production)

For production environments, use Docker secrets instead of environment variables:

1. **Create secrets:**
   ```bash
   echo "your-secure-db-password" | docker secret create db_password -
   echo "your-secure-api-key" | docker secret create api_key -
   echo "your-stripe-live-key" | docker secret create stripe_key -
   ```

2. **Update docker-compose.yml:**
   ```yaml
   services:
     api:
       secrets:
         - api_key
         - db_password
       environment:
         - DATABASE_URL=postgresql://user:DOCKER-SECRET:db_password@db/bankdb
         - AZURE_API_KEY=DOCKER-SECRET:api_key

   secrets:
     api_key:
       external: true
     db_password:
       external: true
     stripe_key:
       external: true
   ```

### Secret Rotation Schedule

- **API Keys:** Rotate every 90 days
- **Database Passwords:** Rotate every 180 days
- **Stripe API Keys:** Rotate when team members leave or every 90 days
- **After any suspected compromise:** Immediate rotation

---

## API Security

### Authentication

All API endpoints (except health checks) require the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-secure-api-key" \\
  http://localhost:8000/api/v1/anomalies
```

### Rate Limiting

Current limits (configured via SlowAPI):
- Health checks: 100 requests/minute
- Anomaly retrieval: 100 requests/minute
- Status updates: 30 requests/minute

**Production recommendations:**
- Lower limits for public endpoints
- Implement per-user rate limiting
- Add exponential backoff

### CORS Configuration

**Development:**
```env
FRONTEND_ORIGIN=*
```

**Production:**
```env
FRONTEND_ORIGIN=https://fraud-dashboard.yourcompany.com
```

### TLS/SSL

**Production deployment MUST use HTTPS:**

1. **Obtain SSL certificates:**
   ```bash
   # Using Let's Encrypt (free)
   certbot certonly --standalone -d fraud-api.yourcompany.com
   ```

2. **Configure reverse proxy (nginx):**
   ```nginx
   server {
       listen 443 ssl;
       server_name fraud-api.yourcompany.com;

       ssl_certificate /etc/letsencrypt/live/fraud-api.yourcompany.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/fraud-api.yourcompany.com/privkey.pem;

       location / {
           proxy_pass http://localhost:8000;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

---

## Database Security

### Access Control

1. **Create dedicated database users with minimal privileges:**
   ```sql
   -- API service user (read/write on transactions table only)
   CREATE USER fraud_api WITH PASSWORD 'secure-password';
   GRANT CONNECT ON DATABASE bankdb TO fraud_api;
   GRANT SELECT, INSERT, UPDATE ON TABLE transactions TO fraud_api;

   -- Detection service user (full access to transactions)
   CREATE USER fraud_detector WITH PASSWORD 'another-secure-password';
   GRANT CONNECT ON DATABASE bankdb TO fraud_detector;
   GRANT ALL PRIVILEGES ON TABLE transactions TO fraud_detector;

   -- Read-only analytics user
   CREATE USER fraud_analyst WITH PASSWORD 'readonly-password';
   GRANT CONNECT ON DATABASE bankdb TO fraud_analyst;
   GRANT SELECT ON TABLE transactions TO fraud_analyst;
   ```

2. **Disable default postgres superuser for application access**

### Network Isolation

**Production:**
- Database should NOT be exposed on public network
- Use private network for Docker services
- Only allow connections from application servers

```yaml
# docker-compose.yml
services:
  db:
    networks:
      - backend
    # Remove ports: - "5432:5432" in production

networks:
  backend:
    driver: bridge
    internal: true  # No external access
```

### Encryption

- **At rest:** Enable PostgreSQL encryption for data files
- **In transit:** Use SSL for database connections

```env
DATABASE_URL=postgresql://user:password@db/bankdb?sslmode=require
```

### Backups

1. **Automated daily backups:**
   ```bash
   # Cron job for daily backups
   0 2 * * * docker exec postgres pg_dump -U user bankdb | gzip > /backups/bankdb_$(date +\%Y\%m\%d).sql.gz
   ```

2. **Encrypt backups:**
   ```bash
   gpg --encrypt --recipient security@yourcompany.com backup.sql.gz
   ```

3. **Store off-site** (AWS S3, Azure Blob Storage, etc.)

4. **Test restore procedures monthly**

---

## Container Security

### Image Scanning

Scan Docker images for vulnerabilities before deployment:

```bash
# Using Trivy
docker run aquasec/trivy image fraud-detection-api:latest

# Using Snyk
snyk container test fraud-detection-api:latest
```

### Running as Non-Root

Update Dockerfiles to run as non-root user:

```dockerfile
# Add to Dockerfile.api
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
```

### Resource Limits

Prevent resource exhaustion attacks:

```yaml
# docker-compose.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          memory: 512M
```

---

## Network Security

### Firewall Rules

**Production server firewall (iptables/ufw):**

```bash
# Allow only necessary ports
sudo ufw allow 443/tcp  # HTTPS
sudo ufw allow 22/tcp   # SSH (restrict to specific IPs in production)
sudo ufw deny 5432/tcp  # Block direct database access
sudo ufw deny 9092/tcp  # Block direct Kafka access
sudo ufw enable
```

### Internal Service Communication

Use Docker networks to isolate services:

```yaml
networks:
  frontend:  # For API and web services
  backend:   # For database, Kafka, internal services
```

### VPN/Bastion Host

For accessing monitoring dashboards (Grafana, Prometheus):
- Use VPN or bastion host
- Do NOT expose to public internet
- Implement IP whitelist if necessary

---

## Monitoring & Incident Response

### Alert Configuration

**High-priority alerts should trigger immediate notifications:**

1. **Set up Grafana alert notifications:**
   - **Slack:** For team awareness
   - **PagerDuty:** For on-call engineers
   - **Email:** For stakeholders

2. **Configure in Grafana UI:**
   - Go to Alerting → Contact points
   - Add Slack webhook: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`
   - Add PagerDuty integration key

### Log Aggregation

Centralize logs for security analysis:

```yaml
# docker-compose.yml
services:
  api:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**Production:** Use ELK stack, Datadog, or cloud-native logging (CloudWatch, Azure Monitor)

### Audit Trail

All transaction status updates are logged with:
- Transaction ID
- User/API key used
- Timestamp
- Previous and new status

Check logs: `api.py:300-306`

### Incident Response Procedure

1. **Detection:** Prometheus alerts → Grafana → Notification
2. **Triage:** Check Grafana dashboard for root cause
3. **Containment:**
   - If API compromised: Rotate API keys immediately
   - If DB compromised: Isolate database, take snapshot
4. **Eradication:** Apply security patches, update configs
5. **Recovery:** Restore from clean backup if necessary
6. **Post-mortem:** Document incident, update runbooks

---

## Production Deployment Checklist

### Pre-Deployment

- [ ] All secrets rotated from defaults
- [ ] `.env` file not in version control
- [ ] SSL/TLS certificates obtained and configured
- [ ] Firewall rules applied
- [ ] Database users created with minimal privileges
- [ ] Backups configured and tested
- [ ] Log aggregation set up
- [ ] Alert notifications configured

### Deployment

- [ ] Run on private network (no public database/Kafka ports)
- [ ] Use Docker secrets or environment management service
- [ ] Enable container resource limits
- [ ] Scan images for vulnerabilities
- [ ] Run containers as non-root users
- [ ] Configure reverse proxy with HTTPS

### Post-Deployment

- [ ] Verify all health checks pass
- [ ] Test alert notifications
- [ ] Perform security scan of deployed system
- [ ] Document deployment for team
- [ ] Set up monitoring dashboards
- [ ] Schedule first security review (30 days)

### Ongoing Maintenance

- [ ] Weekly: Review security logs for anomalies
- [ ] Monthly: Test backup restoration
- [ ] Quarterly: Rotate API keys and passwords
- [ ] Annually: Full security audit

---

## Vulnerability Reporting

If you discover a security vulnerability:

1. **Do NOT open a public GitHub issue**
2. Email: security@yourcompany.com
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if known)

We aim to respond within 24 hours and patch critical issues within 7 days.

---

## Compliance

This fraud detection system should be deployed in compliance with:
- **PCI DSS** (if handling payment card data)
- **GDPR** (if processing EU citizen data)
- **SOC 2** (for SaaS deployments)
- **ISO 27001** (for information security management)

Consult with your legal and compliance teams before production deployment.

---

**Last Updated:** 2025-12-20
**Version:** 1.0
**Maintained By:** Security Team
