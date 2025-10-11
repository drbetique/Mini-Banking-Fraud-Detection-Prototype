import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# --- System onfiguration ---
NUM_TRANSACTIONS = 20000
NUM_ACCOUNTS = 500
FRAUD_RATE = 0.01  # 1% of transactions has been set to be fraudulent
DATE_RANGE_DAYS = 30 # Obtain Data from the last 30 days

# --- Data Generation Helper Lists ---
MERCHANT_CATEGORIES = [
    'Groceries', 'Gas Station', 'Online Retail', 'Fast Food',
    'Travel', 'Subscription', 'Utility Bill', 'ATM Withdrawal',
    'Jewelry', 'Electronics', 'Gambling' # Adding some categories often associated with high risk
]

LOCATIONS = ['Helsinki', 'Oulu', 'Tampere', 'Turku', 'Espoo', 'Vantaa']

def generate_synthetic_data(n_transactions):
    """Generates a DataFrame of synthetic banking transactions."""

    print("Generating transaction IDs...")
    data = {}
    data['transaction_id'] = [f'TRX_{i:07d}' for i in range(1, n_transactions + 1)]

    print("Generating account IDs...")
    # Generate 500 unique accounts and randomly assign them to transactions
    account_ids = [f'ACC_{i:04d}' for i in range(1, NUM_ACCOUNTS + 1)]
    data['account_id'] = np.random.choice(account_ids, n_transactions)

    print("Generating timestamps...")
    # Create timestamps over the last 30 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DATE_RANGE_DAYS)
    time_diff = end_date - start_date
    random_seconds = np.random.rand(n_transactions) * time_diff.total_seconds()
    data['timestamp'] = [start_date + timedelta(seconds=s) for s in random_seconds]

    print("Generating standard amounts...")
    # Most transactions are small/medium, following a log-normal distribution
    # Amounts will be between 5.00 and 500.00 typically
    normal_amounts = np.exp(np.random.normal(loc=4.5, scale=0.8, size=n_transactions))
    data['amount'] = np.round(normal_amounts, 2)

    print("Generating merchant data...")
    data['merchant_category'] = np.random.choice(MERCHANT_CATEGORIES, n_transactions)
    data['location'] = np.random.choice(LOCATIONS, n_transactions)

    # Start with no fraud
    data['is_fraud'] = np.zeros(n_transactions, dtype=int)

    df = pd.DataFrame(data)

    # --- Introduce Anomalous (Fraudulent) Transactions ---

    print(f"Introducing {int(n_transactions * FRAUD_RATE)} fraudulent transactions...")
    
    # 1. Identify transactions that will be marked as fraud
    fraud_indices = df.sample(frac=FRAUD_RATE).index

    # Rule 1: High Value Fraud (e.g., fraudulent electronics/jewelry purchases)
    # 50% of the fraudulent cases will be high value
    high_value_fraud_indices = fraud_indices[:len(fraud_indices)//2]
    
    # Increase the amount for these fraudulent transactions (e.g., $1,000 to $10,000)
    df.loc[high_value_fraud_indices, 'amount'] = np.random.uniform(1000.00, 10000.00, size=len(high_value_fraud_indices))
    df.loc[high_value_fraud_indices, 'merchant_category'] = np.random.choice(['Jewelry', 'Electronics'], size=len(high_value_fraud_indices))
    df.loc[high_value_fraud_indices, 'is_fraud'] = 1
    
    # Rule 2: Sudden, Small, Suspicious Activity (e.g., testing stolen card with small gambling payment)
    # The other 50% of fraudulent cases
    small_fraud_indices = fraud_indices[len(fraud_indices)//2:]
    df.loc[small_fraud_indices, 'amount'] = np.random.uniform(5.00, 50.00, size=len(small_fraud_indices))
    df.loc[small_fraud_indices, 'merchant_category'] = 'Gambling'
    df.loc[small_fraud_indices, 'is_fraud'] = 1
    
    # Ensure the timestamp is in a clean format for SQL
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')

    return df

# --- Main Execution ---
if __name__ == '__main__':
    transaction_df = generate_synthetic_data(NUM_TRANSACTIONS)
    
    # Save the generated data to a CSV file
    FILE_NAME = 'transactions.csv'
    transaction_df.to_csv(FILE_NAME, index=False)
    
    print("-" * 50)
    print(f"Data Generation Complete!")
    print(f"Total Transactions Generated: {len(transaction_df)}")
    print(f"Fraudulent Transactions: {transaction_df['is_fraud'].sum()}")
    print(f"Data saved to {FILE_NAME}")
    print("-" * 50)
    print("\nFirst 5 rows of data:")
    print(transaction_df.head())