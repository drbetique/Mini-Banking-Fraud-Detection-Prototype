"""
Notification Service - Fraud Alert Webhooks
===========================================

Sends real-time notifications when high-risk fraud is detected.

Supported channels:
- Slack webhooks
- Discord webhooks
- Microsoft Teams webhooks
- Custom HTTP webhooks
- Email (SMTP)

Usage:
    from notification_service import NotificationService

    notifier = NotificationService()
    notifier.send_fraud_alert(transaction_data, anomaly_score=0.95)
"""

import os
import logging
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# Configuration
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")
CUSTOM_WEBHOOK_URL = os.environ.get("CUSTOM_WEBHOOK_URL", "")

# Email configuration
SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "fraud-alerts@company.com")
EMAIL_TO = os.environ.get("EMAIL_TO", "security-team@company.com").split(",")

# Alert thresholds
HIGH_RISK_THRESHOLD = float(os.environ.get("HIGH_RISK_THRESHOLD", 0.8))
CRITICAL_RISK_THRESHOLD = float(os.environ.get("CRITICAL_RISK_THRESHOLD", 0.9))
HIGH_VALUE_THRESHOLD = float(os.environ.get("HIGH_VALUE_THRESHOLD", 5000.0))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Available notification channels."""
    SLACK = "slack"
    DISCORD = "discord"
    TEAMS = "teams"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationService:
    """Service for sending fraud alert notifications."""

    def __init__(self):
        """Initialize notification service."""
        self.enabled_channels = self._detect_enabled_channels()
        logger.info(f"Notification service initialized. Enabled channels: {[c.value for c in self.enabled_channels]}")

    def _detect_enabled_channels(self) -> List[NotificationChannel]:
        """Detect which notification channels are configured."""
        channels = []

        if SLACK_WEBHOOK_URL:
            channels.append(NotificationChannel.SLACK)

        if DISCORD_WEBHOOK_URL:
            channels.append(NotificationChannel.DISCORD)

        if TEAMS_WEBHOOK_URL:
            channels.append(NotificationChannel.TEAMS)

        if SMTP_USERNAME and SMTP_PASSWORD:
            channels.append(NotificationChannel.EMAIL)

        if CUSTOM_WEBHOOK_URL:
            channels.append(NotificationChannel.WEBHOOK)

        return channels

    def determine_severity(self, anomaly_score: float, amount: float) -> AlertSeverity:
        """
        Determine alert severity based on risk score and transaction amount.

        Args:
            anomaly_score: ML anomaly score (0-1)
            amount: Transaction amount

        Returns:
            AlertSeverity level
        """
        if anomaly_score >= CRITICAL_RISK_THRESHOLD:
            return AlertSeverity.CRITICAL
        elif anomaly_score >= HIGH_RISK_THRESHOLD or amount >= HIGH_VALUE_THRESHOLD:
            return AlertSeverity.HIGH
        elif anomaly_score >= 0.6:
            return AlertSeverity.WARNING
        else:
            return AlertSeverity.INFO

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _send_slack_notification(self, message: Dict) -> bool:
        """Send notification to Slack."""
        try:
            response = requests.post(
                SLACK_WEBHOOK_URL,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Slack notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _send_discord_notification(self, message: Dict) -> bool:
        """Send notification to Discord."""
        try:
            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Discord notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _send_teams_notification(self, message: Dict) -> bool:
        """Send notification to Microsoft Teams."""
        try:
            response = requests.post(
                TEAMS_WEBHOOK_URL,
                json=message,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Teams notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Teams notification: {e}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _send_custom_webhook(self, payload: Dict) -> bool:
        """Send notification to custom webhook endpoint."""
        try:
            response = requests.post(
                CUSTOM_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            logger.info("Custom webhook notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send custom webhook notification: {e}")
            raise

    def _send_email_notification(self, subject: str, body: str) -> bool:
        """Send email notification."""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = EMAIL_FROM
            msg['To'] = ', '.join(EMAIL_TO)

            # Plain text version
            text_part = MIMEText(body, 'plain')
            msg.attach(text_part)

            # HTML version
            html_body = body.replace('\n', '<br>')
            html_part = MIMEText(f'<html><body>{html_body}</body></html>', 'html')
            msg.attach(html_part)

            # Send email
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email notification sent to {EMAIL_TO}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return False

    def _format_slack_message(
        self,
        transaction: Dict,
        severity: AlertSeverity,
        anomaly_score: float
    ) -> Dict:
        """Format message for Slack."""
        # Color coding by severity
        color_map = {
            AlertSeverity.CRITICAL: "#FF0000",  # Red
            AlertSeverity.HIGH: "#FF6600",      # Orange
            AlertSeverity.WARNING: "#FFCC00",   # Yellow
            AlertSeverity.INFO: "#0099FF"       # Blue
        }

        emoji_map = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.HIGH: "⚠️",
            AlertSeverity.WARNING: "⚡",
            AlertSeverity.INFO: "ℹ️"
        }

        return {
            "text": f"{emoji_map[severity]} *Fraud Alert - {severity.value.upper()}*",
            "attachments": [
                {
                    "color": color_map[severity],
                    "fields": [
                        {
                            "title": "Transaction ID",
                            "value": transaction.get('transaction_id', 'N/A'),
                            "short": True
                        },
                        {
                            "title": "Anomaly Score",
                            "value": f"{anomaly_score:.2%}",
                            "short": True
                        },
                        {
                            "title": "Amount",
                            "value": f"€{transaction.get('amount', 0):.2f}",
                            "short": True
                        },
                        {
                            "title": "Account ID",
                            "value": transaction.get('account_id', 'N/A'),
                            "short": True
                        },
                        {
                            "title": "Merchant Category",
                            "value": transaction.get('merchant_category', 'N/A'),
                            "short": True
                        },
                        {
                            "title": "Location",
                            "value": transaction.get('location', 'N/A'),
                            "short": True
                        },
                        {
                            "title": "Timestamp",
                            "value": transaction.get('timestamp', 'N/A'),
                            "short": False
                        },
                        {
                            "title": "Alert Reason",
                            "value": transaction.get('alert_reason', 'N/A'),
                            "short": False
                        }
                    ],
                    "footer": "Fraud Detection System",
                    "ts": int(datetime.now().timestamp())
                }
            ]
        }

    def _format_discord_message(
        self,
        transaction: Dict,
        severity: AlertSeverity,
        anomaly_score: float
    ) -> Dict:
        """Format message for Discord."""
        color_map = {
            AlertSeverity.CRITICAL: 16711680,  # Red
            AlertSeverity.HIGH: 16737792,      # Orange
            AlertSeverity.WARNING: 16776960,   # Yellow
            AlertSeverity.INFO: 43775          # Blue
        }

        return {
            "embeds": [
                {
                    "title": f"🚨 Fraud Alert - {severity.value.upper()}",
                    "color": color_map[severity],
                    "fields": [
                        {"name": "Transaction ID", "value": transaction.get('transaction_id', 'N/A'), "inline": True},
                        {"name": "Anomaly Score", "value": f"{anomaly_score:.2%}", "inline": True},
                        {"name": "Amount", "value": f"€{transaction.get('amount', 0):.2f}", "inline": True},
                        {"name": "Account ID", "value": transaction.get('account_id', 'N/A'), "inline": True},
                        {"name": "Category", "value": transaction.get('merchant_category', 'N/A'), "inline": True},
                        {"name": "Location", "value": transaction.get('location', 'N/A'), "inline": True},
                        {"name": "Alert Reason", "value": transaction.get('alert_reason', 'N/A'), "inline": False}
                    ],
                    "timestamp": datetime.now().isoformat(),
                    "footer": {"text": "Fraud Detection System"}
                }
            ]
        }

    def _format_teams_message(
        self,
        transaction: Dict,
        severity: AlertSeverity,
        anomaly_score: float
    ) -> Dict:
        """Format message for Microsoft Teams."""
        color_map = {
            AlertSeverity.CRITICAL: "attention",
            AlertSeverity.HIGH: "warning",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "accent"
        }

        return {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": f"Fraud Alert - {severity.value.upper()}",
            "themeColor": color_map[severity],
            "title": f"🚨 Fraud Alert - {severity.value.upper()}",
            "sections": [
                {
                    "facts": [
                        {"name": "Transaction ID", "value": transaction.get('transaction_id', 'N/A')},
                        {"name": "Anomaly Score", "value": f"{anomaly_score:.2%}"},
                        {"name": "Amount", "value": f"€{transaction.get('amount', 0):.2f}"},
                        {"name": "Account ID", "value": transaction.get('account_id', 'N/A')},
                        {"name": "Category", "value": transaction.get('merchant_category', 'N/A')},
                        {"name": "Location", "value": transaction.get('location', 'N/A')},
                        {"name": "Alert Reason", "value": transaction.get('alert_reason', 'N/A')}
                    ]
                }
            ]
        }

    def send_fraud_alert(
        self,
        transaction: Dict,
        anomaly_score: float,
        channels: Optional[List[NotificationChannel]] = None
    ) -> Dict[str, bool]:
        """
        Send fraud alert notification across configured channels.

        Args:
            transaction: Transaction data dictionary
            anomaly_score: ML anomaly score (0-1)
            channels: Specific channels to use (None = all enabled)

        Returns:
            Dictionary mapping channel name to success status
        """
        severity = self.determine_severity(anomaly_score, transaction.get('amount', 0))

        # Only send notifications for HIGH and CRITICAL alerts
        if severity not in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            logger.debug(f"Alert severity {severity.value} below notification threshold - skipping")
            return {}

        # Use specified channels or all enabled channels
        target_channels = channels if channels else self.enabled_channels

        results = {}

        for channel in target_channels:
            try:
                if channel == NotificationChannel.SLACK and channel in self.enabled_channels:
                    message = self._format_slack_message(transaction, severity, anomaly_score)
                    results['slack'] = self._send_slack_notification(message)

                elif channel == NotificationChannel.DISCORD and channel in self.enabled_channels:
                    message = self._format_discord_message(transaction, severity, anomaly_score)
                    results['discord'] = self._send_discord_notification(message)

                elif channel == NotificationChannel.TEAMS and channel in self.enabled_channels:
                    message = self._format_teams_message(transaction, severity, anomaly_score)
                    results['teams'] = self._send_teams_notification(message)

                elif channel == NotificationChannel.EMAIL and channel in self.enabled_channels:
                    subject = f"🚨 Fraud Alert - {severity.value.upper()}: €{transaction.get('amount', 0):.2f}"
                    body = f"""
High-risk fraud transaction detected:

Transaction ID: {transaction.get('transaction_id', 'N/A')}
Anomaly Score: {anomaly_score:.2%}
Amount: €{transaction.get('amount', 0):.2f}
Account ID: {transaction.get('account_id', 'N/A')}
Merchant Category: {transaction.get('merchant_category', 'N/A')}
Location: {transaction.get('location', 'N/A')}
Timestamp: {transaction.get('timestamp', 'N/A')}
Alert Reason: {transaction.get('alert_reason', 'N/A')}

Severity: {severity.value.upper()}

Please investigate immediately.
                    """
                    results['email'] = self._send_email_notification(subject, body.strip())

                elif channel == NotificationChannel.WEBHOOK and channel in self.enabled_channels:
                    payload = {
                        "event": "fraud_alert",
                        "severity": severity.value,
                        "transaction": transaction,
                        "anomaly_score": anomaly_score,
                        "timestamp": datetime.now().isoformat()
                    }
                    results['webhook'] = self._send_custom_webhook(payload)

            except Exception as e:
                logger.error(f"Failed to send notification via {channel.value}: {e}")
                results[channel.value] = False

        logger.info(f"Fraud alert sent: {transaction.get('transaction_id')} - Severity: {severity.value} - Channels: {list(results.keys())}")

        return results


# Singleton instance
_notification_service = None


def get_notification_service() -> NotificationService:
    """Get singleton notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


# Convenience function
def send_fraud_alert(transaction: Dict, anomaly_score: float) -> Dict[str, bool]:
    """
    Convenience function to send fraud alert.

    Args:
        transaction: Transaction data
        anomaly_score: Anomaly score (0-1)

    Returns:
        Dictionary of channel results
    """
    service = get_notification_service()
    return service.send_fraud_alert(transaction, anomaly_score)


if __name__ == "__main__":
    # Test notification
    test_transaction = {
        'transaction_id': 'TRX_TEST_001',
        'account_id': 'ACC_TEST',
        'amount': 9500.0,
        'merchant_category': 'Gambling',
        'location': 'Unknown',
        'timestamp': datetime.now().isoformat(),
        'alert_reason': 'High-value gambling transaction'
    }

    service = NotificationService()
    results = service.send_fraud_alert(test_transaction, anomaly_score=0.95)
    print(f"Notification results: {results}")
