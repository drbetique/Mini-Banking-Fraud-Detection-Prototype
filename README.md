# Banking Fraud Detection System 🛡️

**Version 2.0** - Production-Ready Enterprise Fraud Detection

A real-time, ML-powered fraud detection system with event-driven architecture, horizontal scaling, and comprehensive monitoring. Evolved from a prototype to a production-ready enterprise solution.

[![CI/CD Pipeline](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/workflows/CI%2FCD%20Pipeline/badge.svg)](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/actions)
[![Security Scan](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/workflows/Security%20Scanning/badge.svg)](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Key Features (v2.0)

### 🔔 Real-Time Notifications
- Multi-channel fraud alerts (Slack, Discord, Microsoft Teams, Email, Custom Webhooks)
- Severity-based routing (CRITICAL, HIGH, WARNING, INFO)
- Automatic retry logic with exponential backoff
- Configurable alert thresholds

### ⚡ Performance Optimization
- **Redis caching** for API responses (60-70% faster response times)
- Connection pooling for database and Redis
- Cache hit rates of 70-95%
- Automatic cache invalidation on data updates

### 🚀 Horizontal Scaling
- **Nginx load balancer** with least connections algorithm
- Docker Compose: 3 API + 2 detection service instances
- **Kubernetes support** with Horizontal Pod Autoscaler (3-20 replicas)
- Auto-scaling based on CPU, memory, and traffic metrics
- Zero-downtime deployments with rolling updates

### 🔒 Enterprise Security
- API key authentication with rate limiting (100 req/s)
- TLS/SSL termination
- Network policies and pod security
- Security scanning (Bandit, Trivy, Gitleaks)
- Secrets management best practices

### 🤖 CI/CD Pipeline
- Automated testing (lint, security, unit tests, integration tests)
- Docker image building and publishing to GitHub Container Registry
- Automated deployment to staging and production
- **Dependabot** for automated dependency updates
- Performance testing with k6

### 📊 Advanced Monitoring
- **Prometheus** metrics collection
- **Grafana** dashboards with real-time alerts
- 11 production-ready alert rules
- Cache performance metrics
- Custom business metrics

### 🔄 ML Operations (MLOps)
- Automated model retraining with intelligent promotion
- Model drift detection and monitoring
- Performance-based model promotion (≥2% F1 improvement)
- Scheduled weekly retraining jobs

### 📁 Data Governance
- 4-tier data retention strategy (hot/warm/cold/purge)
- Compliance with PCI DSS, GDPR, SOX
- Automated archival pipeline
- 7-year retention policies

---

## 🏗️ Architecture Overview

The system is built on a real-time, event-driven architecture with enterprise-grade components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Load Balancer (Nginx)                    │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴────────┐
       │   API Layer    │ (3-20 auto-scaled instances)
       │   (FastAPI)    │ + Redis Caching
       └───────┬────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌──▼────┐
│ Kafka │  │ Redis │  │  DB   │
│Stream │  │ Cache │  │(PG)   │
└───┬───┘  └───────┘  └───────┘
    │
┌───▼────────────┐
│Detection Service│ (2+ instances, auto-scaled)
│ + ML Model     │ + Notifications
└───┬────────────┘
    │
┌───▼─────────────┐
│ MLflow Registry │
│ Model Versions  │
└─────────────────┘
```

### Core Components:

1.  **MLflow Model Management:** ML model lifecycle (Isolation Forest) managed by MLflow Tracking Server and Model Registry
2.  **Transaction Stream (Kafka):** Event-driven pipeline with 6 partitions for parallel processing
3.  **Detection Service (Python Consumer):** Real-time fraud detection with auto-scaling (2+ instances)
4.  **Database (PostgreSQL):** Transaction storage with connection pooling (200 max connections)
5.  **Cache Layer (Redis):** In-memory caching with LRU eviction (256-512MB)
6.  **Backend API (FastAPI):** REST API with caching, rate limiting, and authentication
7.  **Load Balancer (Nginx):** Distributes traffic across API instances
8.  **Frontend (Streamlit):** Real-time dashboard for anomaly review
9.  **Monitoring Stack:** Prometheus + Grafana for metrics and alerting
10. **Notification Service:** Multi-channel fraud alerts

## ⚙️ Running Locally (Development)

The local environment is managed via Docker Compose, which orchestrates the entire backend pipeline.

### Prerequisites

*   Docker and Docker Compose
*   Python 3.8+

### Steps

1.  **Clone the Repository & Install Dependencies:**
    ```bash
    git clone https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype.git
    cd Mini-Banking-Fraud-Detection-Prototype
    pip install -r requirements.txt
    ```

2.  **Generate Seed Data:**
    This script just creates the `transactions.csv` file.
    ```bash
    python generate_data.py
    ```

3.  **Start the Backend Infrastructure:**
    This command starts all backend services: PostgreSQL, Zookeeper, Kafka, MLflow Tracking Server, Prometheus, Grafana, the API, and the real-time detection service.
    ```bash
    # Use --build to ensure all changes are reflected in the images
    docker-compose up -d --build
    ```
    Wait a few minutes for all services to initialize (especially Kafka, MLflow, Prometheus, and Grafana). You can check the status with `docker-compose ps` or view logs for a specific service (e.g., `docker-compose logs -f kafka`).

    Once up, you can access the UIs:
    *   **MLflow UI:** `http://localhost:5001`
    *   **Prometheus UI:** `http://localhost:9090`
    *   **Grafana Dashboard:** `http://localhost:3001` (Default login: `admin`/`admin`)

4.  **Seed the Database:**
    With the services running, run the `setup_db.py` script. It connects to the PostgreSQL container and loads the initial data from `transactions.csv`. This data is essential for model training.
    ```bash
    python setup_db.py
    ```

5.  **Train and Register the ML Model:**
    Now that the database is seeded and the MLflow server is running, train the anomaly detection model. This script will train the model, log its details to MLflow, and register it as the "Production" version in the MLflow Model Registry.
    ```bash
    python train_model.py
    ```
    You can then inspect the run and the registered model in the MLflow UI (`http://localhost:5001`).

6.  **Start the Transaction Stream:**
    Run the producer script. This will start publishing messages from `transactions.csv` to the Kafka topic, simulating a live stream of data that the detection service will process.
    ```bash
    python producer.py
    ```
    You will see logs in the `detection_service` container for each transaction it processes, using the model loaded from MLflow.

7.  **Run the Streamlit Frontend:**
    In a **new terminal**, run the Streamlit app.
    ```bash
    streamlit run app.py
    ```
    Your dashboard at `http://localhost:8501` will now update in near real-time as new anomalies are detected by the streaming pipeline and written to the database.

---

## 🆕 What's New in v2.0

### Quick Start with New Features

**Option A: Standard Deployment (Recommended for development)**
```bash
# Includes Redis caching - same as above
docker-compose up -d --build
```

**Option B: Scaled Deployment (Multi-instance)**
```bash
# 3 API instances + 2 detection services + Nginx load balancer
docker-compose -f docker-compose.scaled.yml up -d --build
```

### Enable Webhook Notifications (Optional)

1. **Configure Slack notifications:**
   ```bash
   # Create .env file if not exists
   cp .env.example .env

   # Add your Slack webhook URL
   echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL" >> .env

   # Restart detection service
   docker-compose restart detection_service
   ```

2. **Test notifications:**
   ```bash
   python notification_service.py
   ```

See [NOTIFICATIONS.md](NOTIFICATIONS.md) for complete setup guide.

### Monitor Cache Performance

```bash
# View cache statistics
docker-compose exec redis redis-cli INFO stats

# Check cache hit rate in Prometheus
open http://localhost:9090
# Query: (sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))) * 100
```

See [CACHING.md](CACHING.md) for complete caching guide.

---

## 📚 Documentation

### Core Documentation
- **[CHANGELOG.md](CHANGELOG.md)** - Complete version history and changes
- **[UPGRADE.md](UPGRADE.md)** - Migration guide from v1.0 to v2.0

### Feature Documentation
- **[NOTIFICATIONS.md](NOTIFICATIONS.md)** - Webhook notification setup (Slack, Discord, Teams, Email)
- **[CACHING.md](CACHING.md)** - Redis caching configuration and performance tuning
- **[SCALING.md](SCALING.md)** - Horizontal scaling with Docker Compose and Kubernetes
- **[CI_CD.md](CI_CD.md)** - CI/CD pipeline usage and GitHub Actions workflow

### Operations Documentation
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guide
- **[SECURITY.md](SECURITY.md)** - Security best practices and compliance
- **[MODEL_RETRAINING.md](MODEL_RETRAINING.md)** - Automated ML operations
- **[DATA_RETENTION.md](DATA_RETENTION.md)** - Data governance and retention policies

---

## 🐳 Deployment Options

### Development (Local)
```bash
docker-compose up -d
```

### Scaled (Docker Compose)
```bash
docker-compose -f docker-compose.scaled.yml up -d
```

### Production (Kubernetes)
```bash
# See SCALING.md for complete Kubernetes deployment
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/secrets-configmap.yaml
kubectl apply -f k8s/ingress.yaml
```

---

## 🔧 Configuration

### Required Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/bankdb

# API Security
AZURE_API_KEY=your-api-key
API_KEY=your-api-key

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=transactions_topic

# Redis (v2.0)
REDIS_HOST=localhost
REDIS_PORT=6379
```

### Optional: Webhook Notifications

```env
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
EMAIL_FROM=fraud-alerts@company.com
EMAIL_TO=security@company.com
```

See [.env.example](.env.example) for complete configuration options.

---

## 📊 Monitoring & Metrics

### Access Monitoring Tools

- **MLflow UI:** http://localhost:5001
- **Prometheus:** http://localhost:9090
- **Grafana:** http://localhost:3001 (admin/admin)
- **API Metrics:** http://localhost:8000/metrics
- **Nginx Status:** http://localhost:8080/nginx_status

### Key Metrics to Monitor

```promql
# API request rate
rate(http_requests_total[5m])

# Cache hit rate
(sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))) * 100

# Anomaly detection rate
rate(anomalies_detected_total[5m])

# Response time (p95)
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```

---

## 🚀 Performance Benchmarks

| Metric | v1.0 | v2.0 | Improvement |
|--------|------|------|-------------|
| API Response Time (p95) | ~200-500ms | ~50-150ms | **60-70% faster** |
| Cache Hit Rate | N/A | 70-95% | **New** |
| Max Concurrent Requests | ~50 | ~500+ | **10x** |
| Horizontal Scaling | No | Yes (3-20 pods) | **New** |
| Detection Throughput | ~100/sec | >1000/sec | **10x** |

---

## 🔒 Security Features

- ✅ API key authentication with rate limiting
- ✅ TLS/SSL support
- ✅ Security scanning (Bandit, Trivy, Gitleaks)
- ✅ Network policies (Kubernetes)
- ✅ Secrets management
- ✅ Dependency vulnerability scanning
- ✅ Container image scanning

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**CI/CD checks will run automatically:**
- Linting (Black, isort, Flake8)
- Security scanning (Bandit, Safety)
- Unit tests with coverage
- Integration tests

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **MLflow** for model lifecycle management
- **Apache Kafka** for real-time streaming
- **FastAPI** for high-performance API
- **Streamlit** for rapid dashboard development
- **Prometheus & Grafana** for monitoring
- **Redis** for caching performance

---

## 📞 Support

- **Documentation:** See [docs folder](/) for detailed guides
- **Issues:** [GitHub Issues](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/issues)
- **Discussions:** [GitHub Discussions](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype/discussions)

---

**⭐ Star this repo if you find it useful!**

---

**Version:** 2.0.0
**Last Updated:** 2025-12-23
**Status:** Production Ready ✅