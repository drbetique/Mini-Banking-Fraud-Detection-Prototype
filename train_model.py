import os
import pandas as pd
from sqlalchemy import create_engine
from sklearn.ensemble import IsolationForest
import mlflow
import mlflow.sklearn

# --- Configuration ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost/bankdb")
TABLE_NAME = "transactions"
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5001")

# --- Detection Parameters (from detection_logic.py) ---
HIGH_VALUE_THRESHOLD = 5000.00
SUSPICIOUS_MERCHANT = 'Gambling'
STANDARD_LOCATION = 'Helsinki'

def train_and_register_model():
    """
    Trains the Isolation Forest model on the full dataset, logs it to MLflow,
    and registers it in the MLflow Model Registry.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("Fraud Detection Model Training")

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        print("Loading data for model training...")
        df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
        
        if df.empty:
            raise ValueError("No data available for training. Please run setup_db.py.")

        # --- Feature Engineering (consistent with detection_logic.py) ---
        df['account_avg_amount'] = df.groupby('account_id')['amount'].transform('mean')
        df['account_tx_count'] = df.groupby('account_id')['amount'].transform('count')
        df['deviation_from_avg'] = (df['amount'] - df['account_avg_amount']) / (df['account_avg_amount'] + 1e-6)
        
        features_for_model = df[['amount', 'account_avg_amount', 'deviation_from_avg']].copy()

        # --- Model Training ---
        n_estimators = 100
        contamination = 'auto'
        random_state = 42

        with mlflow.start_run():
            print("Training Isolation Forest model...")
            model = IsolationForest(
                n_estimators=n_estimators,
                contamination=contamination,
                random_state=random_state
            )
            model.fit(features_for_model)

            # --- Log parameters and metrics ---
            mlflow.log_param("n_estimators", n_estimators)
            mlflow.log_param("contamination", contamination)
            mlflow.log_param("random_state", random_state)

            # Calculate and log score boundaries
            anomaly_scores = model.decision_function(features_for_model)
            min_score, max_score = anomaly_scores.min(), anomaly_scores.max()
            mlflow.log_metric("min_decision_score", min_score)
            mlflow.log_metric("max_decision_score", max_score)
            
            # Save the model and register it
            model_name = "fraud-detection-model"
            mlflow.sklearn.log_model(
                sk_model=model,
                artifact_path="isolation_forest_model",
                registered_model_name=model_name,
                conda_env={
                    "channels": ["conda-forge"],
                    "dependencies": [
                        "python=3.9.18", # Match your Python version
                        "pip",
                        {
                            "pip": [
                                "scikit-learn==1.0.2", # Pin to specific version if known
                                "pandas==1.5.3",
                                "numpy==1.23.5",
                                # Add any other specific versions used
                            ]
                        },
                    ],
                    "name": "mlflow-env",
                }
            )

            # Transition to Production stage
            client = mlflow.tracking.MlflowClient()
            model_version = client.search_model_versions(f"name='{model_name}'")[0].version
            client.transition_model_version_stage(
                name=model_name,
                version=model_version,
                stage="Production"
            )
            print(f"Model '{model_name}' version {model_version} registered and set to 'Production' stage.")

    engine.dispose()
    print("Model training and registration complete.")

if __name__ == "__main__":
    train_and_register_model()
