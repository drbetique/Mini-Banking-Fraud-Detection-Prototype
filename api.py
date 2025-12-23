import os
import logging
from typing import List, Optional, Literal
from datetime import datetime

import pandas as pd
from fastapi import FastAPI, Depends, Security, HTTPException, Query, Request
from fastapi import status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from prometheus_fastapi_instrumentator import Instrumentator # Import for Prometheus
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from database import engine, get_db
from cache_wrapper import get_cache, cache_key, invalidate_anomalies_cache, CacheService, CACHE_TTL_ANOMALIES

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fraud-api")

# --- Configuration ---
TABLE_NAME = "transactions"

# --- API Key Security Configuration ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

AZURE_API_KEY = os.environ.get("AZURE_API_KEY")

async def get_api_key(api_key: str = Security(api_key_header)):
    if not AZURE_API_KEY:
        logger.error("AZURE_API_KEY environment variable is not set.")
        raise HTTPException(status_code=500, detail="Server configuration error: API key not configured")
    if api_key and api_key == AZURE_API_KEY:
        return api_key
    raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")

# --- Pydantic Models ---
class UpdateStatusRequest(BaseModel):
    new_status: Literal["NEW", "INVESTIGATED", "FRAUD", "DISMISSED"] = Field(
        ...,
        description="New status for the transaction"
    )

    @validator('new_status')
    def validate_status(cls, v):
        """Ensure status is uppercase."""
        return v.upper()

class UpdateStatusResponse(BaseModel):
    transaction_id: str
    new_status: str
    message: str

class Anomaly(BaseModel):
    transaction_id: str
    account_id: Optional[str] = None
    timestamp: Optional[str] = None
    amount: Optional[float] = None
    merchant_category: Optional[str] = None
    location: Optional[str] = None
    is_fraud: Optional[int] = None
    status: Optional[str] = None
    ml_anomaly_score: Optional[float] = None
    alert_reason: Optional[str] = None

class AnomaliesResponse(BaseModel):
    data: List[Anomaly]
    count: int = Field(..., description="Total number of anomalies returned")

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str

class ReadinessResponse(BaseModel):
    status: str
    checks: dict

# --- Utilities ---
def ensure_schema():
    """Ensure derived columns required by the API exist in the database."""
    try:
        inspector = inspect(engine)
        with engine.connect() as connection:
            if not inspector.has_table(TABLE_NAME):
                logger.warning(f"Table '{TABLE_NAME}' not found. Please run setup_db.py first.")
                return

            existing_cols = {col['name'] for col in inspector.get_columns(TABLE_NAME)}
            
            to_add = {
                "status": "ALTER TABLE transactions ADD COLUMN status TEXT",
                "ml_anomaly_score": "ALTER TABLE transactions ADD COLUMN ml_anomaly_score REAL",
                "alert_reason": "ALTER TABLE transactions ADD COLUMN alert_reason TEXT",
                "is_anomaly": "ALTER TABLE transactions ADD COLUMN is_anomaly INTEGER"
            }

            for col_name, alter_stmt in to_add.items():
                if col_name not in existing_cols:
                    logger.info(f"Applying schema migration: Adding column '{col_name}'")
                    connection.execute(text(alter_stmt))
            
            connection.commit()

    except Exception as e:
        logger.exception(f"Schema ensure failed: {e}")
        raise

# --- App Initialization ---
app = FastAPI(
    title="Banking Fraud Detection API",
    description="Real-time fraud detection system with ML-powered anomaly scoring",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN")
allow_origins = [FRONTEND_ORIGIN] if FRONTEND_ORIGIN else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False if allow_origins == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Prometheus Instrumentator
Instrumentator().instrument(app).expose(app)

@app.on_event("startup")
def _on_startup():
    try:
        ensure_schema()
        logger.info("Schema check completed.")
    except Exception:
        logger.error("Failed to ensure database schema on startup.")

# --- Health Check Endpoints ---

@app.get("/health", response_model=HealthResponse)
@limiter.limit("100/minute")
def health_check(request: Request):
    """
    Basic health check endpoint.
    Returns 200 if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "fraud-detection-api"
    }

@app.get("/health/ready", response_model=ReadinessResponse)
@limiter.limit("30/minute")
def readiness_check(request: Request, db: Session = Depends(get_db)):
    """
    Readiness check - verifies service can handle requests.
    Checks database connectivity.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "checks": {
                "database": "ok"
            }
        }
    except Exception as e:
        logger.error("Readiness check failed", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "checks": {
                    "database": "failed"
                },
                "error": str(e)
            }
        )

@app.get("/health/live")
@limiter.limit("100/minute")
def liveness_check(request: Request):
    """
    Liveness check - verifies service is alive.
    Does not check dependencies.
    """
    return {"status": "alive"}

# --- API Endpoints ---

@app.get(
    "/api/v1/anomalies",
    response_model=AnomaliesResponse,
    summary="Retrieve flagged anomalies",
    description="Returns a list of transactions flagged as potential fraud, sorted by anomaly score"
)
@limiter.limit("100/minute")
def get_anomalies(
    request: Request,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum anomaly score filter"),
    status: Optional[Literal["NEW", "INVESTIGATED", "FRAUD", "DISMISSED"]] = Query(None, description="Filter by status"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache)
):
    """Fetches flagged anomalies from the database with optional filtering and caching."""
    # Generate cache key from query parameters
    key = cache_key(
        "anomalies",
        limit=limit,
        offset=offset,
        min_score=min_score,
        status=status
    )

    # Try to get from cache first
    cached_result = cache.get(key, key_type="anomalies")
    if cached_result is not None:
        logger.info(
            "Anomalies retrieved from cache",
            extra={
                "count": cached_result.get("count", 0),
                "cache_key": key
            }
        )
        return cached_result

    # Cache miss - query database
    try:
        # Build dynamic query with filters
        query_str = f"SELECT * FROM {TABLE_NAME} WHERE is_anomaly = 1 "
        query_params = {}

        if min_score is not None:
            query_str += "AND ml_anomaly_score >= :min_score "
            query_params["min_score"] = min_score

        if status is not None:
            query_str += "AND status = :status "
            query_params["status"] = status.upper()

        query_str += "ORDER BY ml_anomaly_score DESC NULLS LAST LIMIT :limit OFFSET :offset"
        query_params["limit"] = limit
        query_params["offset"] = offset

        query = text(query_str)
        anomaly_df = pd.read_sql_query(query, db.connection(), params=query_params)

        if "ml_anomaly_score" in anomaly_df.columns:
            anomaly_df["ml_anomaly_score"] = pd.to_numeric(anomaly_df["ml_anomaly_score"], errors="coerce")
        if "status" in anomaly_df.columns:
            anomaly_df["status"] = anomaly_df["status"].fillna("NEW").str.upper()
        if "timestamp" in anomaly_df.columns:
            anomaly_df["timestamp"] = anomaly_df["timestamp"].astype(str)

        data = anomaly_df.to_dict(orient="records")

        result = {"data": data, "count": len(data)}

        # Store in cache
        cache.set(key, result, ttl=CACHE_TTL_ANOMALIES)

        logger.info(
            "Anomalies retrieved from database and cached",
            extra={
                "count": len(data),
                "limit": limit,
                "offset": offset,
                "min_score": min_score,
                "status_filter": status,
                "cache_key": key
            }
        )

        return result
    except Exception as e:
        logger.exception("Database error during retrieval")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database retrieval failed"
        )

@app.put(
    "/api/v1/anomalies/{transaction_id}",
    response_model=UpdateStatusResponse,
    summary="Update transaction status",
    description="Updates the review status of a specific transaction"
)
@limiter.limit("30/minute")
def update_anomaly_status(
    request: Request,
    transaction_id: str,
    payload: UpdateStatusRequest,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache)
):
    """Updates the 'status' of a specific transaction in the database and invalidates cache."""
    status_upper = payload.new_status.upper()

    try:
        stmt = text(f"UPDATE {TABLE_NAME} SET status = :status WHERE transaction_id = :tid")
        result = db.execute(stmt, {"status": status_upper, "tid": transaction_id})
        db.commit()

        if result.rowcount == 0:
            logger.warning(f"Transaction not found: {transaction_id}")
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Transaction ID '{transaction_id}' not found."
            )

        # Invalidate all anomalies cache since data has changed
        invalidate_anomalies_cache()

        logger.info(
            "Transaction status updated and cache invalidated",
            extra={
                "transaction_id": transaction_id,
                "new_status": status_upper
            }
        )

        return UpdateStatusResponse(
            transaction_id=transaction_id,
            new_status=status_upper,
            message="Transaction status updated successfully.",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.exception(f"Database update failed for {transaction_id}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update database"
        )
