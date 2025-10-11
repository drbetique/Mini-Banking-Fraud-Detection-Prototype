import pandas as pd
import sqlite3
import numpy as np 
from sklearn.ensemble import IsolationForest 

# --- Configuration (using constants from previous phases) ---
DB_NAME = 'bank_data.db'
TABLE_NAME = 'transactions'

# --- Detection Parameters ---
HIGH_VALUE_THRESHOLD = 5000.00
SUSPICIOUS_MERCHANT = 'Gambling'
STANDARD_LOCATION = 'Helsinki'


# ... (imports and DB constants remain the same) ...

def detect_anomalies():
    """
    we Loads data, applies rule-based flags, and runs Isolation Forest for anomaly scoring.
    """
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()

    if df.empty:
        return pd.DataFrame()

    # --- 1. Rule-Based Detection (Kept for combined score) ---
    high_value_threshold = 5000
    df['is_high_value'] = df['amount'] >= high_value_threshold
    
    suspicious_category = 'Gambling'
    suspicious_location = 'Helsinki'  # Assuming transactions OUTSIDE Helsinki are suspicious
    df['is_suspicious_combo'] = (df['merchant_category'] == suspicious_category) & (df['location'] != suspicious_location)
    
    # --- 2. Isolation Forest (Machine Learning) ---
    
    # we Feature Engineering (The model needs numerical features)
    # We use amount and one-hot encode the merchant category for the model
    features = df[['amount']].copy()
    
    # One-Hot Encode Merchant Category (Crucial for ML on categorical data)
    features = pd.get_dummies(features, columns=[], prefix='cat', dtype=int)
    
    # We fit the model using the features
    # contamination='auto' lets the model estimate the proportion of outliers (anomalies)
    model = IsolationForest(
        contamination='auto',
        random_state=42,
        n_estimators=100
    )
    
    model.fit(features)
    
    # The decision function returns a score: lower score means higher anomaly likelihood
    # We invert and scale this score for presentation: 0 (safe) to 1 (high risk)
    anomaly_scores = model.decision_function(features)
    
    # Scale the scores from 0 to 1 for easier interpretation
    min_score = anomaly_scores.min()
    max_score = anomaly_scores.max()
    df['ml_anomaly_score'] = 1 - (anomaly_scores - min_score) / (max_score - min_score)
    
    # --- 3. Final Flagging ---
    
    # Combine Flags for the UI: ML Score threshold is subjective, let's set it at 0.7 for "High ML Risk"
    df['is_ml_risk'] = df['ml_anomaly_score'] >= 0.7
    
    # Final combined alert reason logic
    def get_alert_reason(row):
        reasons = []
        if row['is_high_value']:
            reasons.append("High Value")
        if row['is_suspicious_combo']:
            reasons.append("Suspicious Combo")
        if row['is_ml_risk']:
            reasons.append("ML Risk")
            
        if not reasons:
            return None # Not an anomaly
            
        # Prioritize ML Risk in the reason for reporting
        if "ML Risk" in reasons:
            return "ML Anomaly"
            
        return " & ".join(reasons)

    df['alert_reason'] = df.apply(get_alert_reason, axis=1)

    # Filter to show only flagged transactions
    anomalies_df = df[df['alert_reason'].notna()].copy()
    
    # Format the score to two decimal places
    anomalies_df['ml_anomaly_score'] = anomalies_df['ml_anomaly_score'].round(3)

    return anomalies_df

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