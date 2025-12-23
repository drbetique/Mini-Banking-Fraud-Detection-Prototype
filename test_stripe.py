"""
Quick test script to verify Stripe API connection
Run this before using producer_stripe.py
"""

import os
import stripe
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_stripe_connection():
    """Test if Stripe API key is valid and can fetch data."""

    # Get API key from environment
    api_key = os.environ.get("STRIPE_API_KEY", "")

    print("=" * 60)
    print("STRIPE API CONNECTION TEST")
    print("=" * 60)

    # Check if API key is set
    if not api_key or api_key == "sk_test_YOUR_KEY_HERE":
        print("❌ STRIPE_API_KEY not set!")
        print("\nHow to fix:")
        print("1. Get your test API key from: https://dashboard.stripe.com/test/apikeys")
        print("2. Set it in your terminal:")
        print("   Windows CMD:        set STRIPE_API_KEY=sk_test_...")
        print("   Windows PowerShell: $env:STRIPE_API_KEY='sk_test_...'")
        print("   Mac/Linux:          export STRIPE_API_KEY='sk_test_...'")
        return False

    # Check if it's a test key
    if not api_key.startswith("sk_test_"):
        print("⚠️  WARNING: This appears to be a LIVE API key!")
        print("   For this project, please use a TEST key (starts with sk_test_)")
        return False

    print(f"✅ API Key found: {api_key[:20]}...{api_key[-4:]}")
    print()

    # Test authentication
    print("Testing Stripe API authentication...")
    stripe.api_key = api_key

    try:
        # Try to fetch balance (simple test)
        balance = stripe.Balance.retrieve()
        print(f"✅ Authentication successful!")
        print(f"   Test mode balance: {balance.available[0].amount / 100:.2f} {balance.available[0].currency.upper()}")
        print()
    except stripe.error.AuthenticationError as e:
        print(f"❌ Authentication failed: {e}")
        print("   Please check your API key is correct")
        return False
    except Exception as e:
        print(f"⚠️  Unexpected error: {e}")

    # Try to fetch some charges
    print("Fetching recent test transactions...")
    try:
        charges = stripe.Charge.list(limit=5)

        if len(charges.data) == 0:
            print("⚠️  No transactions found in Stripe test mode")
            print("\nTo create test transactions:")
            print("1. Go to: https://dashboard.stripe.com/test/payments")
            print("2. Click 'Create payment'")
            print("3. Use test card: 4242 4242 4242 4242")
            print("4. Create 5-10 test payments with different amounts")
            print()
        else:
            print(f"✅ Found {len(charges.data)} test transactions:")
            for idx, charge in enumerate(charges.data, 1):
                amount = charge.amount / 100
                status = charge.status
                created = charge.created
                print(f"   {idx}. {charge.id[:20]}... - €{amount:.2f} - {status}")
            print()

    except Exception as e:
        print(f"❌ Error fetching charges: {e}")
        return False

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✅ Stripe API connection: WORKING")
    print(f"✅ Test transactions available: {len(charges.data)}")

    if len(charges.data) > 0:
        print("\n🎉 You're ready to run: python producer_stripe.py")
    else:
        print("\n⚠️  Create some test transactions first (see instructions above)")

    print("=" * 60)

    return True

if __name__ == "__main__":
    test_stripe_connection()
