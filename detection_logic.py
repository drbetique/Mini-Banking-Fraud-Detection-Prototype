import pandas as pd
import numpy as np
from sqlalchemy import text
import mlflow
import mlflow.sklearn

# --- Configuration ---
TABLE_NAME = 'transactions'
HIGH_VALUE_THRESHOLD = 5000.00
SUSPICIOUS_MERCHANT = 'Gambling'
STANDARD_LOCATION = 'Helsinki'

def get_account_aggregates(account_id: str, conn):
    """Fetches historical aggregates for a given account."""
    query = text(
        f"SELECT COUNT(*) as account_tx_count, AVG(amount) as account_avg_amount "
        f"FROM {TABLE_NAME} WHERE account_id = :account_id"
    )
    result = conn.execute(query, {"account_id": account_id}).first()
    if result and result.account_tx_count > 0:
        return {"account_tx_count": result.account_tx_count, "account_avg_amount": float(result.account_avg_amount)}
    return {"account_tx_count": 0, "account_avg_amount": 0.0}

def score_transaction(transaction: dict, aggregates: dict, model, min_score: float, max_score: float):
    """
    Scores a single transaction using a pre-loaded model and score boundaries.
    """
    if not model or min_score is None or max_score is None:
        raise RuntimeError("Model or score boundaries are not provided.")

    # 1. Engineer features for the single transaction
    tx_amount = transaction['amount']
    account_avg = aggregates['account_avg_amount']
    deviation = (tx_amount - account_avg) / (account_avg + 1e-6) if account_avg > 0 else 0
    
    # Create a DataFrame for the single transaction's features
    tx_features = pd.DataFrame([[tx_amount, account_avg, deviation]], 
                               columns=['amount', 'account_avg_amount', 'deviation_from_avg'])

    # 2. Score with the model and scale the score
    raw_score = model.decision_function(tx_features)[0]
    scaled_score = 1 - (raw_score - min_score) / (max_score - min_score)
    
    # 3. Apply rules to generate an alert reason
    reasons = []
    if tx_amount >= HIGH_VALUE_THRESHOLD: reasons.append("High Value")
    if transaction['merchant_category'] == SUSPICIOUS_MERCHANT and transaction['location'] != STANDARD_LOCATION:
        reasons.append("Suspicious Combo")
    if deviation >= 5.0 and aggregates['account_tx_count'] > 5:
        reasons.append("High Deviation")
    if scaled_score >= 0.7:
        reasons.append("ML Risk")
    
    alert_reason = None
    if reasons:
        if "ML Risk" in reasons: alert_reason = "ML Anomaly"
        elif "High Deviation" in reasons: alert_reason = "High Deviation from Avg"
        else: alert_reason = " & ".join(reasons)

    return scaled_score, alert_reason

# --- Main Execution for Testing ---
if __name__ == '__main__':
    import os
    from sqlalchemy import create_engine

    DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
    MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000")
    engine = create_engine(DATABASE_URL)
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)

    # In a real scenario, you'd load a specific version from the Model Registry
    # For testing, we'll try to load the latest Production model.
    model_name = "fraud-detection-model"
    try:
        loaded_model = mlflow.pyfunc.load_model(f"models:/{model_name}/Production")
        client = mlflow.tracking.MlflowClient()
        model_version = client.search_model_versions(f"name='{model_name}' AND stage='Production'")[0]
        
        # Extract min_score and max_score from the model's run parameters
        run_id = model_version.run_id
        run = client.get_run(run_id)
        model_min_score = run.data.metrics.get("min_decision_score")
        model_max_score = run.data.metrics.get("max_decision_score")

        if model_min_score is None or model_max_score is None:
            raise ValueError("Min/Max scores not found in MLflow run metrics.")

    except Exception as e:
        print(f"Error loading model from MLflow: {e}")
        print("Please ensure a model named 'fraud-detection-model' is registered in 'Production' stage.")
        print("You might need to run 'python train_model.py' first.")
        exit(1)

    print("Running anomaly detection in standalone test mode...")
    with engine.connect() as connection:
        # 1. Fetch a sample transaction to test
        sample_tx = pd.read_sql_query(text(f"SELECT * FROM {TABLE_NAME} LIMIT 1"), connection).to_dict('records')[0]
        account_id = sample_tx['account_id']
        
        # 2. Get aggregates for that account
        account_aggs = get_account_aggregates(account_id, connection)
        
        print("\n--- Testing Single Transaction Scoring ---")
        print(f"Sample Transaction: {sample_tx['transaction_id']}")
        print(f"Account Aggregates: {account_aggs}")
        
        # 3. Score the transaction using the loaded model
        final_score, final_reason = score_transaction(sample_tx, account_aggs, loaded_model, model_min_score, model_max_score)
        
        print(f"\nScore: {final_score:.3f}")
        print(f"Alert Reason: {final_reason}")
        print("-" * 50)
    
    engine.dispose()