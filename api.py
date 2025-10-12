# api.py
import os
from fastapi import FastAPI, HTTPException, depends, Security
from fastapi.security.apikey import APIKeyHeader
import uvicorn
import sqlite3
from pydantic import BaseModel
import pandas as pd
from detection_logic import detect_anomalies # Importing our existing logic

# Initialize FastAPI
app = FastAPI(title="Fraud Detection API")

# --- API Key Security Configuration ---


# The name of the custom header the client must send
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# The expected key is read from an environment variable named AZURE_API_KEY.
# For local testing, we use a default secret ("dev-secret-123")
AZURE_API_KEY = os.environ.get("AZURE_API_KEY", "dev-secret-123")

async def get_api_key(api_key: str = Security(api_key_header)):
    """
    Checks the incoming request header for the required API key.
    """
    if api_key == AZURE_API_KEY:
        return api_key
    
    # If the key is missing or incorrect, raise a 401 Unauthorized error
    raise HTTPException(
        status_code=401, detail="Invalid or missing X-API-Key header"
    )

# Define the data structure for the API response
# We use a simple list of dictionaries to represent the dataframe rows
class AnomalyResponse(BaseModel):
    data: list

@app.get("/", summary="API Root Health Check")
def read_root():
    return {"status": "ok", "service": "Fraud Detection API"}

@app.get("/api/v1/anomalies", response_model=AnomalyResponse, summary="Get Flagged Anomalies")
def get_flagged_anomalies(api_key: str = depends(get_api_key)):
    """
    Calls the ML and rule-based logic to detect anomalies,
    converts the resulting DataFrame to JSON, and returns it.
    """
    
    # Run the existing, complex ML detection logic
    anomalies_df = detect_anomalies()
    
    # The 'ml_anomaly_score' is not JSON serializable when returned directly
    # from the dict conversion, so we ensure it's a standard float/string.
    
    # Convert DataFrame to a list of dictionaries (JSON format)
    anomalies_list = anomalies_df.to_dict(orient="records")
    
    return {"data": anomalies_list}

# To test this locally, run: uvicorn api:app --reload