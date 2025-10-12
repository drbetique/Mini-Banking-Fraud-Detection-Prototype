import os
import sqlite3
import pandas as pd
from fastapi import FastAPI, Depends, Security, HTTPException
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware

# --- Configuration ---
DB_NAME = 'bank_data.db'
TABLE_NAME = 'transactions'

# --- API Key Security Configuration ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# The expected key is read from an environment variable named AZURE_API_KEY.
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "dev-secret-123")

async def get_api_key(api_key: str = Security(api_key_header)):
    """Checks the incoming request header for the required API key."""
    if api_key == AZURE_API_KEY:
        return api_key
    
    raise HTTPException(
        status_code=401, detail="Invalid or missing X-API-Key header"
    )

# --- App Initialization ---
app = FastAPI()

# Add CORS Middleware to allow the Streamlit frontend domain to access the API
# IMPORTANT: Replace "*" with your Streamlit domain for production!
origins = [
    "*", 
    # Add your specific Streamlit app domain here: e.g., "https://drbetique-mini-banking-fraud.streamlit.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Protected Endpoint: Retrieve Anomalies ---

@app.get("/api/v1/anomalies")
def get_anomalies(api_key: str = Depends(get_api_key)):
    """Fetches all flagged anomalies from the database."""
    conn = None
    try:
        # 1. Database Connection
        conn = sqlite3.connect(DB_NAME)
        
        # 2. Fetch Data
        # Ensure you select the 'status' column if you've added it to your DB!
        query = f"SELECT * FROM {TABLE_NAME} WHERE is_anomaly = 1"
        anomaly_df = pd.read_sql_query(query, conn)
        
        # 3. Clean and Prepare Data (if necessary)
        if 'ml_anomaly_score' in anomaly_df.columns:
            # Clean up newlines/whitespace before returning (based on previous issues)
            anomaly_df['ml_anomaly_score'] = anomaly_df['ml_anomaly_score'].astype(str).str.replace('\n', '', regex=False).str.strip()
            anomaly_df['ml_anomaly_score'] = pd.to_numeric(anomaly_df['ml_anomaly_score'], errors='coerce').fillna(0)

        # 4. Return as JSON
        anomalies_data = anomaly_df.to_dict(orient='records')
        
        return {"data": anomalies_data}
        
    except sqlite3.Error as e:
        print(f"Database error during retrieval: {e}")
        raise HTTPException(status_code=500, detail="Database retrieval failed")
    finally:
        if conn:
            conn.close()


# --- NEW Protected Endpoint: Update Anomaly Status ---

@app.put("/api/v1/anomalies/{transaction_id}")
def update_anomaly_status(
    transaction_id: str, 
    new_status: str, 
    api_key: str = Depends(get_api_key) # Requires API Key
):
    """Updates the 'status' of a specific transaction in the database."""
    
    # 1. Input Validation
    allowed_statuses = ["NEW", "INVESTIGATED", "FRAUD", "DISMISSED"]
    status_upper = new_status.upper()
    
    if status_upper not in allowed_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid status provided. Must be one of: {', '.join(allowed_statuses)}"
        )

    conn = None
    try:
        # 2. Database Connection
        conn = sqlite3.connect(DB_NAME) 
        cursor = conn.cursor()
        
        # 3. Execute the Update
        # IMPORTANT: This assumes you have added a 'status' column to your transactions table
        sql_update = "UPDATE transactions SET status = ? WHERE transaction_id = ?"
        cursor.execute(sql_update, (status_upper, transaction_id))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Transaction ID not found.")

        # 4. Commit Changes
        conn.commit()

        return {
            "transaction_id": transaction_id, 
            "new_status": status_upper,
            "message": "Transaction status updated successfully."
        }
        
    except sqlite3.Error as e:
        print(f"Database update failed for {transaction_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to update database: {e}"
        )
    finally:
        if conn:
            conn.close()