# Stripe API Integration Guide

## Quick Setup (5 minutes)

### Step 1: Create Stripe Account (Free)

1. **Go to:** https://dashboard.stripe.com/register
2. **Sign up** with your email (free, no credit card required)
3. **Skip** the business setup questions for now (you can fill them later)
4. You'll land on the Stripe Dashboard

---

### Step 2: Get Your Test API Key

1. **Make sure you're in TEST MODE:**
   - Look at the top-left corner of the dashboard
   - You should see a toggle that says **"Test mode"** (should be ON/orange)
   - If not, click it to enable test mode

2. **Get your API key:**
   - Click on **"Developers"** in the left sidebar
   - Click on **"API keys"**
   - You'll see two keys:
     - **Publishable key** (starts with `pk_test_...`) - NOT needed
     - **Secret key** (starts with `sk_test_...`) - **THIS IS WHAT WE NEED**
   - Click **"Reveal test key"** to see your secret key
   - **Copy** the entire key (should look like: `sk_test_51Abc...xyz`)

3. **IMPORTANT:** Keep this key secret! It's like a password.

---

### Step 3: Set the API Key in Your Environment

**Option A: Set temporarily (for this session only)**

In your terminal:
```bash
# Windows (Command Prompt)
set STRIPE_API_KEY=sk_test_YOUR_KEY_HERE

# Windows (PowerShell)
$env:STRIPE_API_KEY="sk_test_YOUR_KEY_HERE"

# Mac/Linux
export STRIPE_API_KEY="sk_test_YOUR_KEY_HERE"
```

**Option B: Set permanently in .env file (Recommended)**

Add to your `.env` file:
```bash
STRIPE_API_KEY=sk_test_YOUR_KEY_HERE
```

---

### Step 4: Create Test Transactions in Stripe

You need some test transactions for the producer to fetch. Here's how:

#### Method 1: Use Stripe Dashboard (Easiest)

1. Go to: https://dashboard.stripe.com/test/payments
2. Click **"Create payment"** button
3. Fill in:
   - **Amount:** Any amount (e.g., €50.00)
   - **Card number:** Use test card `4242 4242 4242 4242`
   - **Expiry:** Any future date (e.g., 12/25)
   - **CVC:** Any 3 digits (e.g., 123)
   - **ZIP:** Any 5 digits (e.g., 12345)
4. Click **"Create payment"**
5. Repeat 5-10 times with different amounts

#### Method 2: Use Python Script (Automated)

We can create a script to generate test transactions automatically!

---

### Step 5: Test the Integration

Run the new Stripe producer:
```bash
python producer_stripe.py
```

You should see:
```
=== Stripe Transaction Producer ===
Kafka Bootstrap Servers: localhost:9092
Kafka Topic: transactions_topic
Fetching transactions from Stripe Test Mode...
Retrieved 10 charges from Stripe
Sent transaction (1/10): STRIPE_ch_xxx - €50.00 - Food
```

---

## Test Cards for Different Scenarios

Use these test cards in Stripe Dashboard to create different transaction types:

| Card Number | Scenario | Risk Level |
|-------------|----------|------------|
| 4242 4242 4242 4242 | Normal transaction | Normal |
| 4000 0000 0000 0002 | Charge declined | High Risk |
| 4000 0000 0000 9995 | Insufficient funds | Medium Risk |
| 4000 0027 6000 3184 | 3D Secure required | Normal |

---

## Stripe Transaction Fields Mapping

Our system maps Stripe data to our fraud detection format:

| Our Field | Stripe Field | Notes |
|-----------|--------------|-------|
| transaction_id | charge.id | Prefixed with "STRIPE_" |
| account_id | charge.customer | Or "GUEST_xxx" if no customer |
| amount | charge.amount / 100 | Converted from cents |
| merchant_category | charge.metadata.category | Can be set in dashboard |
| location | charge.billing_details.address.city | From billing info |
| timestamp | charge.created | Unix timestamp converted |
| stripe_risk_score | charge.outcome.risk_score | Stripe's fraud score |
| stripe_risk_level | charge.outcome.risk_level | normal/elevated/highest |

---

## Adding Metadata to Transactions

To make transactions more realistic, add metadata when creating payments:

1. When creating a payment in dashboard, scroll down to **"Metadata"**
2. Add key-value pairs:
   - Key: `category` → Value: `Food` or `Travel` or `Gambling`
   - Key: `location` → Value: `Helsinki` or `Espoo` or `London`

This helps our fraud detection system categorize transactions properly!

---

## Troubleshooting

### "Authentication failed"
- Check that your API key starts with `sk_test_`
- Make sure test mode is enabled in dashboard
- Verify the key is set correctly: `echo $STRIPE_API_KEY`

### "No transactions fetched"
- Create some test payments in the dashboard first
- Wait a few seconds after creating payments
- Check that you're in test mode (not live mode)

### "Rate limit exceeded"
- Stripe test mode allows 100 requests/second
- Add delay between requests if needed

---

## Next Steps

Once Stripe integration is working:

1. ✅ **Create 20-30 test transactions** with varying amounts
2. ✅ **Add metadata** (category, location) to make them realistic
3. ✅ **Run the producer** and see real Stripe data flow through your system
4. ✅ **Watch Grafana** - metrics will update with real transaction data
5. ✅ **Check Streamlit** - anomalies detected from real payment patterns!

---

## Resources

- **Stripe Dashboard:** https://dashboard.stripe.com/test
- **Stripe API Docs:** https://docs.stripe.com/api
- **Test Cards:** https://docs.stripe.com/testing
- **Python Library:** https://github.com/stripe/stripe-python

---

**You're now ready to process real payment transaction data through your fraud detection system!** 🎉
