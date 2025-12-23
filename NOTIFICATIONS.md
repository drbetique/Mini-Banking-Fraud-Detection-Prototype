# Real-Time Fraud Alert Notifications

## Overview

The fraud detection system includes real-time webhook notifications that alert your team immediately when high-risk fraud transactions are detected. Notifications are sent automatically through multiple channels with rich, formatted alert messages.

---

## Supported Channels

### 1. Slack (Recommended)
**Best for:** Team collaboration and quick response

**Features:**
- Color-coded alerts by severity
- Rich formatted messages with all transaction details
- Emoji indicators (🚨 Critical, ⚠️ High, ⚡ Warning)
- Threaded discussions
- Mobile push notifications

**Setup:**
1. Create a Slack app: https://api.slack.com/apps
2. Enable Incoming Webhooks
3. Add webhook to workspace
4. Copy webhook URL
5. Set in `.env`: `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL`

**Example Alert:**
```
🚨 Fraud Alert - CRITICAL

Transaction ID: STRIPE_ch_3Sg...
Anomaly Score: 95%
Amount: €9,500.00
Account ID: ACC_0019
Merchant Category: Gambling
Location: Unknown
Timestamp: 2025-12-20 15:30:45
Alert Reason: High-value gambling transaction
```

---

### 2. Discord
**Best for:** Gaming/tech companies using Discord for operations

**Features:**
- Embedded rich messages
- Color-coded by severity
- Mobile and desktop notifications
- Channel-specific routing

**Setup:**
1. Go to Server Settings → Integrations → Webhooks
2. Create New Webhook
3. Choose channel for fraud alerts
4. Copy webhook URL
5. Set in `.env`: `DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/TOKEN`

---

### 3. Microsoft Teams
**Best for:** Enterprise organizations using Microsoft 365

**Features:**
- Adaptive card format
- Color-coded by severity
- Integrated with Teams notifications
- Enterprise security controls

**Setup:**
1. Open Teams channel for fraud alerts
2. Click ⋯ → Connectors → Incoming Webhook
3. Name the webhook "Fraud Detection Alerts"
4. Copy webhook URL
5. Set in `.env`: `TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...`

---

### 4. Email (SMTP)
**Best for:** Compliance, audit trail, non-technical stakeholders

**Features:**
- Plain text and HTML format
- Multiple recipients support
- Permanent audit trail
- Compatible with all email providers

**Setup (Gmail example):**
1. Enable 2-factor authentication on Gmail
2. Generate app password: https://myaccount.google.com/apppasswords
3. Configure in `.env`:
```env
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=fraud-alerts@yourcompany.com
EMAIL_TO=security@yourcompany.com,fraud@yourcompany.com
```

**Other SMTP Providers:**
- **Outlook/Office365:** `smtp.office365.com:587`
- **SendGrid:** `smtp.sendgrid.net:587`
- **AWS SES:** `email-smtp.us-east-1.amazonaws.com:587`

---

### 5. Custom Webhook
**Best for:** Integration with custom systems, SIEM, incident management

**Features:**
- JSON payload with full transaction data
- Custom HTTP endpoint
- Flexible integration
- Can trigger automated workflows

**Setup:**
1. Create HTTP endpoint that accepts POST requests
2. Implement JSON payload handler
3. Set in `.env`: `CUSTOM_WEBHOOK_URL=https://your-api.com/fraud-alerts`

**Payload Format:**
```json
{
  "event": "fraud_alert",
  "severity": "critical",
  "transaction": {
    "transaction_id": "STRIPE_ch_3Sg...",
    "account_id": "ACC_0019",
    "amount": 9500.0,
    "merchant_category": "Gambling",
    "location": "Unknown",
    "timestamp": "2025-12-20T15:30:45",
    "alert_reason": "High-value gambling transaction"
  },
  "anomaly_score": 0.95,
  "timestamp": "2025-12-20T15:30:46.123456"
}
```

---

## Alert Severity Levels

### Critical (🚨)
**Triggers:**
- Anomaly score ≥ 90% (configurable via `CRITICAL_RISK_THRESHOLD`)

**Characteristics:**
- Red color coding
- Immediate notification
- Requires urgent investigation

**Example:** €10,000 transfer to gambling site with score 0.95

---

### High (⚠️)
**Triggers:**
- Anomaly score ≥ 80% (configurable via `HIGH_RISK_THRESHOLD`)
- OR transaction amount ≥ €5,000 (configurable via `HIGH_VALUE_THRESHOLD`)

**Characteristics:**
- Orange color coding
- Priority notification
- Investigate within 1 hour

**Example:** €6,000 electronics purchase with score 0.75

---

### Warning (⚡)
**Triggers:**
- Anomaly score ≥ 60%

**Characteristics:**
- Yellow color coding
- Standard notification
- Review during business hours

**Note:** Warning level does NOT trigger notifications by default (only HIGH and CRITICAL do)

---

### Info (ℹ️)
**Triggers:**
- Anomaly score < 60%

**Characteristics:**
- Blue color coding
- Logged only, no notification

---

## Configuration

### Environment Variables

**Required (at least one channel):**
```env
# Slack (recommended)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/XXX

# Or Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123/abc

# Or Teams
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...

# Or Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=alerts@company.com
SMTP_PASSWORD=app-password
EMAIL_FROM=fraud-alerts@company.com
EMAIL_TO=team@company.com

# Or Custom Webhook
CUSTOM_WEBHOOK_URL=https://your-api.com/alerts
```

**Optional Thresholds:**
```env
HIGH_RISK_THRESHOLD=0.8          # Default: 0.8
CRITICAL_RISK_THRESHOLD=0.9      # Default: 0.9
HIGH_VALUE_THRESHOLD=5000.0      # Default: 5000.0 (in EUR)
```

---

## Testing Notifications

### Test Slack Webhook

```bash
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "🧪 Test: Fraud Detection System - Notifications Active"
  }'
```

### Test from Python

```python
from notification_service import NotificationService
from datetime import datetime

# Create test transaction
test_transaction = {
    'transaction_id': 'TRX_TEST_001',
    'account_id': 'ACC_TEST',
    'amount': 9500.0,
    'merchant_category': 'Gambling',
    'location': 'Unknown',
    'timestamp': datetime.now().isoformat(),
    'alert_reason': 'Test alert - High-value gambling'
}

# Send notification
service = NotificationService()
results = service.send_fraud_alert(test_transaction, anomaly_score=0.95)

print(f"Sent to channels: {list(results.keys())}")
print(f"Success: {all(results.values())}")
```

### Run Test Script

```bash
python notification_service.py
```

---

## Integration with Detection Service

Notifications are **automatically sent** when anomalies are detected:

**detection_service.py:242-258**
```python
if transaction['is_anomaly'] == 1:
    # Send real-time fraud alert notifications
    try:
        notification_results = send_fraud_alert(transaction, score)
        if notification_results:
            logger.info("Fraud alert notifications sent",
                       extra={'channels': list(notification_results.keys())})
    except Exception as notif_error:
        logger.error(f"Failed to send notification: {notif_error}")
```

**Key points:**
- Notifications sent asynchronously (don't block transaction processing)
- Failures logged but don't stop transaction processing
- Only HIGH and CRITICAL severity alerts trigger notifications
- All configured channels receive alerts simultaneously

---

## Monitoring & Troubleshooting

### Check Notification Status

**View detection service logs:**
```bash
docker-compose logs detection_service | grep "Fraud alert notifications"
```

**Expected output:**
```
INFO - Fraud alert notifications sent - extra={'channels': ['slack', 'email']}
```

---

### Common Issues

#### No notifications received

**Check 1: Verify channel configuration**
```python
from notification_service import NotificationService
service = NotificationService()
print(f"Enabled channels: {service.enabled_channels}")
```

**Check 2: Verify severity threshold**
```python
# Check if score is above threshold
anomaly_score = 0.75
severity = service.determine_severity(anomaly_score, amount=1000)
print(f"Severity: {severity}")  # Must be HIGH or CRITICAL to send
```

**Check 3: Test webhook manually**
```bash
# Slack example
curl -X POST $SLACK_WEBHOOK_URL -H 'Content-Type: application/json' \
  -d '{"text":"Test message"}'
```

---

#### Slack: "invalid_payload" error

**Cause:** Malformed JSON in webhook payload

**Solution:** Verify webhook URL is correct and complete
```bash
echo $SLACK_WEBHOOK_URL
# Should be: https://hooks.slack.com/services/T.../B.../XXX
```

---

#### Email: "Authentication failed"

**Cause:** Incorrect SMTP credentials or less secure apps blocked

**Solutions:**
1. Use app-specific password (not account password)
2. Enable 2FA and generate app password
3. Check SMTP server and port are correct

**Gmail troubleshooting:**
```bash
# Test SMTP connection
python -c "
import smtplib
server = smtplib.SMTP('smtp.gmail.com', 587)
server.starttls()
server.login('your-email@gmail.com', 'app-password')
print('SMTP connection successful')
server.quit()
"
```

---

#### Notifications delayed

**Cause:** Network latency or webhook endpoint slow

**Solution:** Notifications use retry logic (3 attempts with exponential backoff)

**Check retry logs:**
```bash
docker-compose logs detection_service | grep "retry"
```

---

## Best Practices

### 1. Channel Selection

**Recommended setup:**
- **Slack/Teams:** Primary channel for real-time team response
- **Email:** Secondary channel for audit trail and compliance
- **Custom Webhook:** Integration with incident management (PagerDuty, Opsgenie)

---

### 2. Alert Fatigue Prevention

**Adjust thresholds to reduce false positives:**
```env
# More conservative thresholds
HIGH_RISK_THRESHOLD=0.85         # Increase from 0.8
CRITICAL_RISK_THRESHOLD=0.92     # Increase from 0.9
HIGH_VALUE_THRESHOLD=10000.0     # Increase from 5000
```

**Monitor alert volume:**
```bash
# Count alerts in last 24 hours
docker-compose logs detection_service --since 24h | \
  grep "Fraud alert notifications sent" | wc -l
```

---

### 3. Response Procedures

**Document response workflow:**

**CRITICAL alerts (score ≥90%):**
1. Acknowledge alert in Slack (within 5 minutes)
2. Open Streamlit dashboard: http://localhost:8502
3. Review transaction details
4. Contact account holder immediately
5. Update transaction status to INVESTIGATED
6. If confirmed fraud, mark as FRAUD and block account

**HIGH alerts (score 80-89% or amount >€5,000):**
1. Acknowledge alert (within 30 minutes)
2. Review in dashboard
3. Cross-check with recent account activity
4. Contact account holder within 1 hour if suspicious
5. Update status accordingly

---

### 4. Testing & Validation

**Weekly test:**
```bash
# Send test notification every Monday
crontab -e
# Add: 0 9 * * 1 cd /opt/fraud-detection && python notification_service.py
```

**Load testing:**
```python
# Test notification performance under load
import time
from notification_service import send_fraud_alert

for i in range(100):
    transaction = {...}  # Test transaction
    send_fraud_alert(transaction, 0.95)
    time.sleep(0.1)
```

---

### 5. Security Considerations

**Protect webhook URLs:**
- Never commit webhook URLs to git
- Store in `.env` file (excluded from version control)
- Rotate webhooks quarterly
- Use secrets management in production (AWS Secrets Manager, Azure Key Vault)

**Webhook URL security:**
```bash
# Check if webhook URLs are exposed
grep -r "hooks.slack.com" . --exclude-dir=.env

# Should only find references in .env (not tracked)
```

---

## Compliance & Audit Trail

### Email Audit Trail

Email notifications provide a permanent audit trail required for:
- **PCI DSS** Requirement 10.6: Review logs and security events
- **GDPR** Article 33: Breach notification requirements
- **SOX** Section 404: Internal controls

**Email retention:** Configure email provider to retain fraud alerts for 7 years

---

### Notification Logging

All notifications are logged with details:
```json
{
  "timestamp": "2025-12-20T15:30:46",
  "transaction_id": "STRIPE_ch_3Sg...",
  "severity": "critical",
  "anomaly_score": 0.95,
  "channels": ["slack", "email"],
  "success": true
}
```

**Query notification history:**
```bash
docker-compose logs detection_service | grep "Fraud alert notifications sent"
```

---

## Advanced: Custom Notification Logic

### Conditional Routing

**Route different severities to different channels:**

```python
# In detection_service.py
from notification_service import NotificationService, NotificationChannel, AlertSeverity

service = NotificationService()
severity = service.determine_severity(score, amount)

if severity == AlertSeverity.CRITICAL:
    # Critical: Send to ALL channels including email
    service.send_fraud_alert(transaction, score)
elif severity == AlertSeverity.HIGH:
    # High: Send to Slack only (team can investigate)
    service.send_fraud_alert(transaction, score,
                            channels=[NotificationChannel.SLACK])
```

---

### Time-Based Routing

**Send email only during off-hours:**

```python
from datetime import datetime

hour = datetime.now().hour
is_business_hours = 9 <= hour <= 17

if not is_business_hours:
    # After hours: Include email for on-call
    service.send_fraud_alert(transaction, score)
else:
    # Business hours: Slack only
    service.send_fraud_alert(transaction, score,
                            channels=[NotificationChannel.SLACK])
```

---

## References

- **Slack Webhooks:** https://api.slack.com/messaging/webhooks
- **Discord Webhooks:** https://discord.com/developers/docs/resources/webhook
- **Teams Webhooks:** https://docs.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/
- **SMTP Configuration:** https://support.google.com/mail/answer/7126229

---

**Last Updated:** 2025-12-20
**Version:** 1.0
**Maintained By:** Security Operations Team
