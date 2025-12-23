# Production Optimization Roadmap
## Transforming the Fraud Detection Prototype into Production-Ready Software

This document outlines a comprehensive plan to optimize and productionize the banking fraud detection system.

---

## 1. Security & Authentication (CRITICAL - Priority 1)

### Current Issues
- Hardcoded API keys in code and docker-compose.yml
- No user authentication/authorization in Streamlit dashboard
- No rate limiting on API endpoints
- API key passed in plain text headers
- No secrets rotation strategy
- Database credentials in plain text

### Recommended Solutions

#### 1.1 Secrets Management
```bash
# Use environment-based secrets management
# For development: python-dotenv
# For production: AWS Secrets Manager, Azure Key Vault, or HashiCorp Vault

# Add to requirements.txt:
python-dotenv
hvac  # For HashiCorp Vault integration
```

**Implementation:**
- Remove all hardcoded secrets from code and docker-compose.yml
- Create `.env.example` template (never commit actual `.env`)
- Implement secrets rotation policy (90-day rotation)
- Use Docker secrets for container deployment

#### 1.2 API Authentication Enhancement
```python
# Replace simple API key with JWT tokens
# Add to requirements.txt:
python-jose[cryptography]
passlib[bcrypt]

# Implement OAuth2 with password flow
# Add role-based access control (RBAC):
# - ANALYST: View and update anomalies
# - ADMIN: Full access including model retraining
# - AUDITOR: Read-only access
```

#### 1.3 Add Rate Limiting
```python
# Add to requirements.txt:
slowapi

# In api.py:
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/api/v1/anomalies")
@limiter.limit("100/minute")  # Limit to 100 requests per minute
async def get_anomalies(...):
    pass
```

#### 1.4 Network Security
- Add HTTPS/TLS termination (use reverse proxy like Nginx)
- Implement CORS with specific allowed origins (no wildcards in production)
- Add security headers (HSTS, CSP, X-Frame-Options)
- Enable database SSL connections

---

## 2. Testing Infrastructure (CRITICAL - Priority 1)

### Current Issues
- **Zero test coverage**
- No validation of ML model performance
- No integration tests for Kafka pipeline
- No API contract tests
- No load testing

### Recommended Solutions

#### 2.1 Unit Tests
```bash
# Add to requirements.txt:
pytest==7.4.0
pytest-asyncio==0.21.0
pytest-cov==4.1.0
pytest-mock==3.11.1
httpx==0.24.1  # For FastAPI testing
```

**Create `tests/` structure:**
```
tests/
├── __init__.py
├── conftest.py
├── unit/
│   ├── test_detection_logic.py
│   ├── test_api.py
│   └── test_database.py
├── integration/
│   ├── test_kafka_pipeline.py
│   └── test_mlflow_integration.py
└── performance/
    └── test_load.py
```

**Example test file (`tests/unit/test_detection_logic.py`):**
```python
import pytest
import pandas as pd
from detection_logic import score_transaction, get_account_aggregates

class TestDetectionLogic:
    def test_score_transaction_high_value(self, mock_model):
        """Test that high-value transactions are flagged correctly."""
        transaction = {
            'transaction_id': 'TEST_001',
            'amount': 8000.00,
            'merchant_category': 'Electronics',
            'location': 'Helsinki'
        }
        aggregates = {'account_tx_count': 50, 'account_avg_amount': 150.0}

        score, reason = score_transaction(
            transaction, aggregates, mock_model, min_score=-0.5, max_score=0.5
        )

        assert score > 0.5, "High-value transaction should have elevated score"
        assert "High Value" in reason

    def test_suspicious_gambling_combo(self, mock_model):
        """Test suspicious merchant + location combination."""
        transaction = {
            'transaction_id': 'TEST_002',
            'amount': 100.00,
            'merchant_category': 'Gambling',
            'location': 'Turku'  # Not Helsinki
        }
        aggregates = {'account_tx_count': 30, 'account_avg_amount': 80.0}

        score, reason = score_transaction(
            transaction, aggregates, mock_model, min_score=-0.5, max_score=0.5
        )

        assert "Suspicious Combo" in reason

@pytest.fixture
def mock_model():
    """Fixture providing a mock ML model for testing."""
    from sklearn.ensemble import IsolationForest
    model = IsolationForest(random_state=42)
    # Train on dummy data
    X_train = pd.DataFrame({
        'amount': [100, 150, 200],
        'account_avg_amount': [120, 120, 120],
        'deviation_from_avg': [0.1, 0.2, 0.3]
    })
    model.fit(X_train)
    return model
```

#### 2.2 API Integration Tests
```python
# tests/integration/test_api.py
from fastapi.testclient import TestClient
from api import app
import os

os.environ['AZURE_API_KEY'] = 'test-key-123'

client = TestClient(app)

def test_get_anomalies_unauthorized():
    """Test API rejects requests without valid API key."""
    response = client.get("/api/v1/anomalies")
    assert response.status_code == 401

def test_get_anomalies_success():
    """Test successful anomaly retrieval."""
    response = client.get(
        "/api/v1/anomalies",
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 200
    assert "data" in response.json()

def test_update_status_invalid_transaction():
    """Test 404 for non-existent transaction."""
    response = client.put(
        "/api/v1/anomalies/INVALID_TRX",
        json={"new_status": "FRAUD"},
        headers={"X-API-Key": "test-key-123"}
    )
    assert response.status_code == 404
```

#### 2.3 ML Model Performance Tests
```python
# tests/unit/test_model_performance.py
def test_model_accuracy_threshold():
    """Ensure model meets minimum performance standards."""
    from train_model import train_and_register_model
    from sklearn.metrics import roc_auc_score

    # Load validation dataset
    # Evaluate model
    # Assert metrics meet thresholds
    assert auc >= 0.80, "Model AUC must be >= 0.80"
    assert precision >= 0.75, "Precision must be >= 0.75"
```

#### 2.4 Run Tests
```bash
# Run all tests with coverage
pytest tests/ -v --cov=. --cov-report=html --cov-report=term

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v -m "not slow"

# Add to CI/CD pipeline
pytest tests/ --junitxml=test-results.xml --cov-report=xml
```

---

## 3. Error Handling & Resilience (HIGH - Priority 2)

### Current Issues
- Minimal error handling in Kafka consumer
- No retry mechanisms for transient failures
- Detection service crashes if MLflow is unavailable
- No circuit breakers for downstream services
- Poor error messages to users

### Recommended Solutions

#### 3.1 Implement Retry Logic with Exponential Backoff
```python
# Add to requirements.txt:
tenacity==8.2.3

# In detection_service.py:
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from kafka.errors import KafkaError
from sqlalchemy.exc import OperationalError

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((OperationalError, KafkaError))
)
def process_transaction_with_retry(transaction: dict, db_conn):
    """Process transaction with automatic retry on transient failures."""
    return process_transaction(transaction, db_conn)
```

#### 3.2 Circuit Breaker Pattern
```python
# Add to requirements.txt:
pybreaker==0.8.0

# For external service calls (MLflow, Kafka)
from pybreaker import CircuitBreaker

mlflow_breaker = CircuitBreaker(
    fail_max=5,  # Open circuit after 5 failures
    timeout_duration=60  # Try again after 60 seconds
)

@mlflow_breaker
def load_mlflow_model():
    """Load model with circuit breaker protection."""
    # Existing model loading logic
```

#### 3.3 Graceful Degradation
```python
# In detection_service.py:
def process_transaction_safe(transaction: dict, db_conn):
    """
    Process transaction with fallback to rule-based detection
    if ML model is unavailable.
    """
    try:
        return process_transaction(transaction, db_conn)
    except Exception as e:
        logger.error(f"ML scoring failed: {e}. Falling back to rules only.")
        # Use only rule-based detection
        return process_transaction_rules_only(transaction, db_conn)
```

#### 3.4 Dead Letter Queue for Failed Messages
```python
# In detection_service.py:
FAILED_TRANSACTIONS_TOPIC = "transactions_dlq"

def send_to_dlq(transaction: dict, error: Exception):
    """Send failed transaction to Dead Letter Queue for manual review."""
    dlq_producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps({
            'transaction': v,
            'error': str(error),
            'timestamp': datetime.utcnow().isoformat()
        }).encode('utf-8')
    )
    dlq_producer.send(FAILED_TRANSACTIONS_TOPIC, transaction)
```

---

## 4. Database Management (HIGH - Priority 2)

### Current Issues
- No proper migration system (ALTER TABLE in app code)
- No database connection pooling optimization
- No indexing strategy
- No database backup/restore procedures
- No data retention policy

### Recommended Solutions

#### 4.1 Implement Alembic Migrations
```bash
# Add to requirements.txt:
alembic==1.11.1

# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Add detection columns"

# Apply migrations
alembic upgrade head
```

**Example migration (`alembic/versions/001_add_detection_columns.py`):**
```python
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('transactions', sa.Column('status', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('ml_anomaly_score', sa.Float(), nullable=True))
    op.add_column('transactions', sa.Column('alert_reason', sa.Text(), nullable=True))
    op.add_column('transactions', sa.Column('is_anomaly', sa.Integer(), nullable=True))

    # Add indexes for performance
    op.create_index('idx_transactions_status', 'transactions', ['status'])
    op.create_index('idx_transactions_is_anomaly', 'transactions', ['is_anomaly'])
    op.create_index('idx_transactions_timestamp', 'transactions', ['timestamp'])
    op.create_index('idx_transactions_account_id', 'transactions', ['account_id'])

def downgrade():
    op.drop_index('idx_transactions_account_id')
    op.drop_index('idx_transactions_timestamp')
    op.drop_index('idx_transactions_is_anomaly')
    op.drop_index('idx_transactions_status')
    op.drop_column('transactions', 'is_anomaly')
    op.drop_column('transactions', 'alert_reason')
    op.drop_column('transactions', 'ml_anomaly_score')
    op.drop_column('transactions', 'status')
```

#### 4.2 Optimize Database Configuration
```python
# In database.py:
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=20,  # Maintain 20 connections
    max_overflow=30,  # Allow 30 additional connections
    pool_pre_ping=True,  # Test connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False,  # Disable SQL logging in production
    connect_args={
        "options": "-c statement_timeout=30000"  # 30 second query timeout
    }
)
```

#### 4.3 Add Database Partitioning
```sql
-- For PostgreSQL, partition by month for better query performance
CREATE TABLE transactions_2024_01 PARTITION OF transactions
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Automate partition creation with a cron job or scheduler
```

#### 4.4 Implement Data Retention Policy
```python
# Create cleanup job (cleanup_old_data.py)
def archive_and_delete_old_transactions(days_to_keep=90):
    """
    Archive transactions older than X days to cold storage,
    then delete from operational database.
    """
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)

    # 1. Export to S3/Azure Blob
    # 2. Delete from PostgreSQL
    # 3. Log operation
```

---

## 5. Observability & Monitoring (HIGH - Priority 2)

### Current Issues
- Basic Prometheus metrics only
- No centralized logging
- No distributed tracing
- No alerting rules configured
- No SLA/SLO monitoring
- Print statements instead of structured logging

### Recommended Solutions

#### 5.1 Structured Logging
```python
# Add to requirements.txt:
python-json-logger==2.0.7

# Create logging_config.py:
import logging
from pythonjsonlogger import jsonlogger

def setup_logging(service_name: str):
    logger = logging.getLogger()
    handler = logging.StreamHandler()

    formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s %(service)s',
        timestamp=True
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Add service name to all logs
    logging.LoggerAdapter(logger, {'service': service_name})

    return logger

# In each service:
logger = setup_logging('detection-service')
logger.info('Processing transaction', extra={
    'transaction_id': txn_id,
    'account_id': account_id,
    'ml_score': score
})
```

#### 5.2 Enhanced Metrics
```python
# In detection_service.py, add more detailed metrics:
from prometheus_client import Histogram, Gauge

# Track processing latency
TRANSACTION_PROCESSING_DURATION = Histogram(
    'transaction_processing_duration_seconds',
    'Time spent processing a transaction',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Track ML model scoring time
ML_SCORING_DURATION = Histogram(
    'ml_scoring_duration_seconds',
    'Time spent on ML model scoring',
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

# Track anomaly score distribution
ANOMALY_SCORE_GAUGE = Gauge(
    'anomaly_score',
    'Current anomaly score distribution'
)

# Track Kafka consumer lag
KAFKA_CONSUMER_LAG = Gauge(
    'kafka_consumer_lag_messages',
    'Number of messages behind in Kafka topic'
)

# Usage:
with TRANSACTION_PROCESSING_DURATION.time():
    process_transaction(txn, conn)
```

#### 5.3 Alerting Rules (Prometheus)
```yaml
# Create prometheus_alerts.yml
groups:
  - name: fraud_detection
    interval: 30s
    rules:
      # Alert if detection service is down
      - alert: DetectionServiceDown
        expr: up{job="detection_service"} == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Detection service is down"
          description: "Detection service has been down for more than 2 minutes"

      # Alert on high error rate
      - alert: HighErrorRate
        expr: rate(transaction_processing_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High transaction processing error rate"
          description: "Error rate is {{ $value }} errors/sec"

      # Alert on consumer lag
      - alert: KafkaConsumerLag
        expr: kafka_consumer_lag_messages > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Kafka consumer lag is high"
          description: "Consumer is {{ $value }} messages behind"

      # Alert on high anomaly detection rate (potential attack)
      - alert: HighAnomalyRate
        expr: rate(anomalies_detected_total[10m]) > 100
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Unusually high anomaly detection rate"
          description: "Detected {{ $value }} anomalies/sec - potential fraud attack"
```

#### 5.4 Application Performance Monitoring (APM)
```python
# Add to requirements.txt:
opentelemetry-api==1.20.0
opentelemetry-sdk==1.20.0
opentelemetry-instrumentation-fastapi==0.41b0
opentelemetry-instrumentation-sqlalchemy==0.41b0
opentelemetry-exporter-jaeger==1.20.0

# In api.py:
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Initialize tracing
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument(engine=engine)
```

---

## 6. Performance Optimization (MEDIUM - Priority 3)

### Current Issues
- No caching layer
- Inefficient database queries (N+1 problems)
- Synchronous processing in API
- No query result pagination
- Streamlit app loads all data at once

### Recommended Solutions

#### 6.1 Add Caching Layer
```python
# Add to requirements.txt:
redis==5.0.0
fastapi-cache2[redis]==0.2.1

# In api.py:
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from fastapi_cache.decorator import cache
from redis import asyncio as aioredis

@app.on_event("startup")
async def startup():
    redis_client = aioredis.from_url(
        "redis://localhost:6379",
        encoding="utf8",
        decode_responses=True
    )
    FastAPICache.init(RedisBackend(redis_client), prefix="fraud-api")

@app.get("/api/v1/anomalies")
@cache(expire=60)  # Cache for 60 seconds
async def get_anomalies(...):
    pass
```

#### 6.2 Optimize Database Queries
```python
# In api.py - Add pagination
from fastapi import Query

@app.get("/api/v1/anomalies")
def get_anomalies(
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = text(
        f"SELECT * FROM {TABLE_NAME} "
        "WHERE is_anomaly = 1 "
        "ORDER BY ml_anomaly_score DESC NULLS LAST "
        "LIMIT :limit OFFSET :offset"
    )
    result = db.execute(query, {"limit": limit, "offset": offset})
    # ...

# Add count endpoint for pagination
@app.get("/api/v1/anomalies/count")
def get_anomalies_count(db: Session = Depends(get_db)):
    query = text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE is_anomaly = 1")
    count = db.execute(query).scalar()
    return {"count": count}
```

#### 6.3 Async Processing for API
```python
# Convert API to async where possible
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

async_engine = create_async_engine(DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://'))

@app.get("/api/v1/anomalies")
async def get_anomalies(db: AsyncSession = Depends(get_async_db)):
    # Use async database operations
    result = await db.execute(query)
    # ...
```

#### 6.4 Batch Processing in Detection Service
```python
# In detection_service.py:
def process_transactions_batch(transactions: list, db_conn):
    """Process multiple transactions in a single batch."""
    # Fetch all account aggregates in one query
    account_ids = [t['account_id'] for t in transactions]
    aggregates_query = text(
        f"SELECT account_id, COUNT(*) as tx_count, AVG(amount) as avg_amount "
        f"FROM {TABLE_NAME} WHERE account_id = ANY(:ids) GROUP BY account_id"
    )
    aggregates_df = pd.read_sql_query(aggregates_query, db_conn, params={'ids': account_ids})

    # Score all transactions
    # Insert in bulk using pd.DataFrame.to_sql()
```

---

## 7. Scalability Improvements (MEDIUM - Priority 3)

### Current Issues
- Single instance of detection service
- No horizontal scaling capability
- No load balancing
- Kafka has single partition
- PostgreSQL is single instance

### Recommended Solutions

#### 7.1 Kafka Partitioning Strategy
```yaml
# In docker-compose.yml - Update Kafka topic creation
version: '3.8'
services:
  kafka-setup:
    image: confluentinc/cp-kafka:7.0.1
    depends_on:
      - kafka
    command: |
      kafka-topics --create --if-not-exists \
        --bootstrap-server kafka:29092 \
        --topic transactions_topic \
        --partitions 10 \
        --replication-factor 1
```

#### 7.2 Scale Detection Service Horizontally
```yaml
# In docker-compose.yml:
services:
  detection_service:
    # ... existing config
    deploy:
      replicas: 3  # Run 3 instances
    environment:
      - KAFKA_CONSUMER_GROUP_ID=fraud-detectors  # Same group for load balancing
```

#### 7.3 Add API Load Balancer
```yaml
# docker-compose.yml - Add Nginx as load balancer
services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - api-1
      - api-2
      - api-3

  api-1:
    build: .
    # ...

  api-2:
    build: .
    # ...

  api-3:
    build: .
    # ...
```

**Nginx configuration (`nginx.conf`):**
```nginx
upstream api_backend {
    least_conn;  # Use least connections algorithm
    server api-1:8000 max_fails=3 fail_timeout=30s;
    server api-2:8000 max_fails=3 fail_timeout=30s;
    server api-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;

    location /api/ {
        proxy_pass http://api_backend;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Connection pooling
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location /metrics {
        # Expose aggregated metrics from all instances
        proxy_pass http://api_backend;
    }
}
```

#### 7.4 Database Read Replicas
```yaml
# For read-heavy workloads, add PostgreSQL read replicas
services:
  db-primary:
    image: postgres:13-alpine
    environment:
      - POSTGRES_REPLICATION_MODE=master

  db-replica-1:
    image: postgres:13-alpine
    environment:
      - POSTGRES_REPLICATION_MODE=slave
      - POSTGRES_MASTER_SERVICE=db-primary
```

---

## 8. CI/CD Pipeline (MEDIUM - Priority 3)

### Recommended GitHub Actions Workflow

Create `.github/workflows/ci.yml`:
```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: testpass
        options: >-
          --health-cmd pg_isready
          --health-interval 10s

      redis:
        image: redis:alpine

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:testpass@localhost/testdb
        run: |
          pytest tests/ --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Lint with flake8
        run: |
          pip install flake8
          flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Type check with mypy
        run: |
          pip install mypy
          mypy *.py --ignore-missing-imports

  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run security scan
        run: |
          pip install bandit safety
          bandit -r . -f json -o bandit-report.json
          safety check --json

  build:
    needs: [test, lint]
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Build Docker images
        run: |
          docker build -t fraud-api:${{ github.sha }} -f Dockerfile.api .

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker push fraud-api:${{ github.sha }}

  deploy:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - name: Deploy to production
        run: |
          # Deploy using Kubernetes, Docker Swarm, or your deployment tool
          kubectl set image deployment/fraud-api api=fraud-api:${{ github.sha }}
```

---

## 9. Model Lifecycle Management (MEDIUM - Priority 3)

### Recommended Improvements

#### 9.1 A/B Testing Framework
```python
# Create model_serving.py for A/B testing
class ModelRouter:
    def __init__(self):
        self.model_a = mlflow.pyfunc.load_model("models:/fraud-detection-model/Production")
        self.model_b = mlflow.pyfunc.load_model("models:/fraud-detection-model/Staging")
        self.ab_split = 0.1  # 10% traffic to model B

    def get_model(self, transaction_id: str):
        """Route traffic based on transaction ID hash."""
        if hash(transaction_id) % 100 < self.ab_split * 100:
            return self.model_b, "model_b"
        return self.model_a, "model_a"

    def score_with_logging(self, transaction, aggregates):
        """Score and log which model was used."""
        model, model_name = self.get_model(transaction['transaction_id'])
        score = model.score(transaction, aggregates)

        # Log to MLflow for comparison
        mlflow.log_metric(f"{model_name}_score", score)

        return score, model_name
```

#### 9.2 Model Monitoring & Drift Detection
```python
# Add to requirements.txt:
evidently==0.4.0

# Create model_monitoring.py
from evidently.metrics import DataDriftTable
from evidently.report import Report

def check_data_drift(reference_data: pd.DataFrame, current_data: pd.DataFrame):
    """Detect data drift in production traffic."""
    report = Report(metrics=[DataDriftTable()])
    report.run(reference_data=reference_data, current_data=current_data)

    # Alert if significant drift detected
    if report.as_dict()['metrics'][0]['result']['drift_detected']:
        logger.critical("Data drift detected! Model retraining may be required.")
        send_alert("Data drift detected in fraud detection model")
```

#### 9.3 Automated Retraining Pipeline
```python
# Create retrain_schedule.py
from datetime import datetime, timedelta

def should_retrain():
    """Determine if model should be retrained."""
    # Retrain every 7 days or if performance degrades
    last_training = get_last_training_date()
    days_since_training = (datetime.now() - last_training).days

    current_performance = get_model_performance_metrics()
    performance_threshold = 0.75

    return (
        days_since_training >= 7 or
        current_performance['precision'] < performance_threshold
    )

# Schedule with Apache Airflow or Prefect
```

---

## 10. Documentation & Operations (LOW - Priority 4)

### Recommended Documentation

#### 10.1 Runbooks
Create `docs/runbooks/`:
- `incident_response.md` - How to respond to alerts
- `disaster_recovery.md` - Backup/restore procedures
- `scaling_guide.md` - When and how to scale
- `troubleshooting.md` - Common issues and solutions

#### 10.2 API Documentation
```python
# Enhance FastAPI auto-docs in api.py:
app = FastAPI(
    title="Fraud Detection API",
    description="Real-time banking fraud detection system",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

@app.get("/api/v1/anomalies",
         summary="Retrieve flagged anomalies",
         description="Returns a list of transactions flagged as potential fraud",
         response_description="List of anomalous transactions with scores")
```

---

## Implementation Priority Summary

### Phase 1 (Weeks 1-2): Foundation
1. Add comprehensive test suite
2. Implement proper secrets management
3. Add database migrations with Alembic
4. Set up structured logging

### Phase 2 (Weeks 3-4): Resilience
1. Add error handling and retry logic
2. Implement circuit breakers
3. Set up monitoring and alerting
4. Add rate limiting

### Phase 3 (Weeks 5-6): Performance
1. Add caching layer
2. Optimize database queries
3. Implement pagination
4. Add database indexes

### Phase 4 (Weeks 7-8): Scale & Deploy
1. Set up CI/CD pipeline
2. Implement horizontal scaling
3. Add load balancing
4. Create comprehensive documentation

### Phase 5 (Weeks 9+): Advanced Features
1. A/B testing framework
2. Model drift detection
3. Automated retraining
4. Advanced analytics dashboard

---

## Estimated Resources

- **Development Time**: 8-12 weeks (1-2 engineers)
- **Infrastructure Cost Increase**: ~40% (caching, monitoring, replicas)
- **Ongoing Maintenance**: ~20% of development time

## Success Metrics

- Test coverage: >80%
- API response time: <200ms (p95)
- System uptime: >99.9%
- Alert response time: <5 minutes
- Zero security vulnerabilities (high/critical)
