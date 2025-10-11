import pandas as pd
import sqlite3

# --- Configuration (using constants from previous phases) ---
DB_NAME = 'bank_data.db'
TABLE_NAME = 'transactions'

# --- Detection Parameters ---
HIGH_VALUE_THRESHOLD = 5000.00
SUSPICIOUS_MERCHANT = 'Gambling'
STANDARD_LOCATION = 'Helsinki'

import pandas as pd
import sqlite3
import numpy as np # <-- Make sure this is imported at the top of your file

# --- Configuration and Detection Parameters remain the same ---
# ... (rest of your imports and definitions)

def detect_anomalies():
    """
    Connects to the SQL database, reads transactions, and applies
    rule-based logic to detect and return anomalous transactions.
    """
    try:
        # 1 & 2. Connect and Fetch Data (NO CHANGE HERE)
        print(f"Connecting to {DB_NAME} to fetch data...")
        conn = sqlite3.connect(DB_NAME)
        sql_query = f"SELECT * FROM {TABLE_NAME}"
        df = pd.read_sql_query(sql_query, conn)
        conn.close()
        print(f"Total transactions fetched: {len(df)}")
        
        # 3. Apply Anomaly Detection Rules (FIXED LOGIC)
        
        # Rule Definitions (Using >= as we agreed)
        HIGH_VALUE_THRESHOLD = 5000.00
        SUSPICIOUS_MERCHANT = 'Gambling'
        STANDARD_LOCATION = 'Helsinki'

        condition_high_value = df['amount'] >= HIGH_VALUE_THRESHOLD # Rule 1: High Value
        condition_suspicious_combo = (df['merchant_category'] == SUSPICIOUS_MERCHANT) & \
                                     (df['location'] != STANDARD_LOCATION) # Rule 2: Suspicious Combo
                                     
        # Combine the conditions to identify all anomalies
        is_anomalous = condition_high_value | condition_suspicious_combo
        
        # Create the new 'alert_reason' column for the entire DataFrame (initializing with empty strings)
        df['alert_reason'] = ''
        
        # Use a list to store the reasons for each row
        reasons = []
        for high_value, suspicious_combo in zip(condition_high_value, condition_suspicious_combo):
            reason = ''
            if high_value:
                reason += 'High Value Transaction'
            if suspicious_combo:
                # Add a separator if the previous reason exists
                if reason:
                    reason += ' & '
                reason += 'Suspicious Merchant/Location Combo'
            reasons.append(reason)
            
        # Assign the calculated reasons back to the DataFrame
        df['alert_reason'] = reasons

        # 4. Filter the DataFrame to only include transactions with an alert reason
        final_anomalies = df[is_anomalous].copy()
        
        return final_anomalies

    except Exception as e:
        # IMPORTANT: Keep this error handler for future issues
        print(f"An error occurred during anomaly detection: {e}") 
        return pd.DataFrame() # Return an empty DataFrame on failure

# --- Main Execution for Testing ---
if __name__ == '__main__':
    anomalies_df = detect_anomalies()
    
    print("-" * 50)
    print("Anomaly Detection Test Results:")
    if not anomalies_df.empty:
        print(f"Found {len(anomalies_df)} anomalous transactions!")
        
        # Display summary statistics of the detected fraud
        print("\nSummary of Fraud Reasons:")
        print(anomalies_df['alert_reason'].value_counts())
        
        print("\nFirst 10 Anomalous Transactions:")
        # Display the first 10 anomalous transactions, showing the reason
        print(anomalies_df[['transaction_id', 'amount', 'merchant_category', 'location', 'alert_reason']].head(10))
    else:
        print("No anomalies found (or an error occurred).")
    print("-" * 50)