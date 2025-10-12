# api.py
from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
from detection_logic import detect_anomalies # Importing our existing logic

# Initialize FastAPI
app = FastAPI(title="Fraud Detection API")

# Define the data structure for the API response
# We use a simple list of dictionaries to represent the dataframe rows
class AnomalyResponse(BaseModel):
    data: list

@app.get("/", summary="API Root Health Check")
def read_root():
    return {"status": "ok", "service": "Fraud Detection API"}

@app.get("/api/v1/anomalies", response_model=AnomalyResponse, summary="Get Flagged Anomalies")
def get_flagged_anomalies():
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