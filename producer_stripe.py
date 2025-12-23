"""
Kafka Producer - Stripe API Integration
Streams real payment transaction data from Stripe Test Mode to Kafka
"""

import os
import json
import time
import logging
from datetime import datetime
from kafka import KafkaProducer
import stripe
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- Configuration ---
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC", "transactions_topic")
STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "sk_test_YOUR_KEY_HERE")  # Get from dashboard.stripe.com
STREAM_DELAY_SECONDS = int(os.environ.get("STREAM_DELAY_SECONDS", 2))

# Initialize Stripe
stripe.api_key = STRIPE_API_KEY

# Merchant category mapping
CATEGORY_MAPPING = {
    'subscription': 'Subscription',
    'food_delivery': 'Food',
    'online_shopping': 'Shopping',
    'travel': 'Travel',
    'entertainment': 'Entertainment',
    'utilities': 'Utilities',
    'gas_station': 'Gas',
    'restaurant': 'Food',
    'hotel': 'Travel',
    'gambling': 'Gambling'
}

def create_kafka_producer():
    """Creates a Kafka producer with retry logic."""
    for attempt in range(1, 6):
        try:
            producer = KafkaProducer(
                bootstrap_servers=[KAFKA_BOOTSTRAP_SERVERS],
                value_serializer=lambda v: json.dumps(v).encode('utf-8')
            )
            logger.info("Kafka Producer connected successfully")
            return producer
        except Exception as e:
            logger.warning(f"Waiting for Kafka brokers (attempt {attempt}/5): {e}")
            time.sleep(10)
    raise ConnectionError("Could not connect to Kafka brokers after multiple retries.")

def fetch_stripe_transactions():
    """Fetch transactions from Stripe API."""
    try:
        logger.info("Fetching transactions from Stripe Test Mode...")

        # Fetch charges (payments)
        charges = stripe.Charge.list(limit=100)

        logger.info(f"Retrieved {len(charges.data)} charges from Stripe")
        return charges.data

    except stripe.error.AuthenticationError as e:
        logger.error(f"Stripe authentication failed: {e}")
        logger.error("Please set STRIPE_API_KEY environment variable with your test key from dashboard.stripe.com")
        return []
    except Exception as e:
        logger.error(f"Error fetching Stripe data: {e}")
        return []

def convert_stripe_to_transaction(charge):
    """Convert Stripe charge to transaction format."""

    # Extract location from billing details or metadata
    location = "Unknown"
    if charge.billing_details and charge.billing_details.address:
        location = charge.billing_details.address.city or charge.billing_details.address.country or "Unknown"

    # Get merchant category from metadata or description
    merchant_category = "Unknown"
    if charge.metadata and 'category' in charge.metadata:
        merchant_category = CATEGORY_MAPPING.get(charge.metadata['category'], charge.metadata['category'])
    elif charge.description:
        # Try to infer from description
        desc_lower = charge.description.lower()
        for key, value in CATEGORY_MAPPING.items():
            if key in desc_lower:
                merchant_category = value
                break

    # Convert Stripe charge to our transaction format
    transaction = {
        'transaction_id': f"STRIPE_{charge.id}",
        'account_id': charge.customer or f"GUEST_{charge.id[:8]}",
        'timestamp': datetime.fromtimestamp(charge.created).isoformat(),
        'amount': charge.amount / 100.0,  # Convert from cents to dollars
        'merchant_category': merchant_category,
        'location': location,
        'is_fraud': 0,  # Will be determined by our ML model
        # Additional Stripe-specific fields
        'stripe_risk_score': charge.outcome.risk_score if charge.outcome else None,
        'stripe_risk_level': charge.outcome.risk_level if charge.outcome else None,
        'payment_method': charge.payment_method_details.type if charge.payment_method_details else None
    }

    return transaction

def stream_stripe_transactions():
    """Stream Stripe transactions to Kafka."""
    producer = create_kafka_producer()

    try:
        # Fetch transactions from Stripe
        charges = fetch_stripe_transactions()

        if not charges:
            logger.warning("No transactions fetched from Stripe. Creating test charge...")
            logger.info("To create test transactions in Stripe dashboard:")
            logger.info("1. Go to https://dashboard.stripe.com/test/payments")
            logger.info("2. Click 'Create payment' to generate test charges")
            logger.info("3. Or use test card: 4242 4242 4242 4242")
            return

        logger.info(f"Starting to stream {len(charges)} Stripe transactions to Kafka topic '{KAFKA_TOPIC}'")

        for idx, charge in enumerate(charges, 1):
            try:
                # Convert to our format
                transaction = convert_stripe_to_transaction(charge)

                # Send to Kafka
                producer.send(KAFKA_TOPIC, value=transaction)

                logger.info(
                    f"Sent transaction ({idx}/{len(charges)}): {transaction['transaction_id']} - "
                    f"€{transaction['amount']:.2f} - {transaction['merchant_category']}"
                )

                # Delay between messages
                time.sleep(STREAM_DELAY_SECONDS)

            except Exception as e:
                logger.error(f"Error processing charge {charge.id}: {e}")
                continue

        logger.info(f"Completed streaming {len(charges)} transactions from Stripe")

    except KeyboardInterrupt:
        logger.info("Stream interrupted by user")
    finally:
        producer.flush()
        producer.close()
        logger.info("Kafka producer closed")

def create_test_stripe_charge():
    """Create a test charge in Stripe for demonstration."""
    try:
        logger.info("Creating test charge in Stripe...")

        # Create a test charge
        charge = stripe.Charge.create(
            amount=2000,  # $20.00
            currency="eur",
            source="tok_visa",  # Test token
            description="Test transaction for fraud detection",
            metadata={
                'category': 'food_delivery',
                'test': 'true'
            }
        )

        logger.info(f"Created test charge: {charge.id}")
        return charge

    except Exception as e:
        logger.error(f"Error creating test charge: {e}")
        return None

if __name__ == "__main__":
    logger.info("=== Stripe Transaction Producer ===")
    logger.info(f"Kafka Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Kafka Topic: {KAFKA_TOPIC}")
    logger.info(f"Stream Delay: {STREAM_DELAY_SECONDS}s")
    logger.info(f"Stripe API Key: {'*' * 20}{STRIPE_API_KEY[-4:]}" if len(STRIPE_API_KEY) > 4 else "NOT SET")

    if STRIPE_API_KEY == "sk_test_YOUR_KEY_HERE":
        logger.warning("⚠️  STRIPE_API_KEY not set!")
        logger.warning("Get your test API key from: https://dashboard.stripe.com/test/apikeys")
        logger.warning("Set it with: export STRIPE_API_KEY='sk_test_...'")
        logger.warning("")
        logger.info("Attempting to create a test charge anyway...")
        create_test_stripe_charge()

    stream_stripe_transactions()
