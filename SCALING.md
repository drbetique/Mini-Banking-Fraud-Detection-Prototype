# Horizontal Scaling Guide

## Overview

The fraud detection system is designed for horizontal scaling to handle high traffic and ensure high availability. This guide covers scaling strategies for both Docker Compose (development/small production) and Kubernetes (enterprise production).

**Scaling Capabilities:**
- ✅ Multiple API instances with load balancing
- ✅ Auto-scaling based on CPU, memory, and traffic
- ✅ Zero-downtime deployments
- ✅ Database connection pooling
- ✅ Redis caching for performance
- ✅ Kafka consumer groups for parallel processing

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                        Load Balancer                           │
│                     (Nginx / Ingress)                          │
└─────────┬────────────────────────────────────────────────┬─────┘
          │                                                │
    ┌─────▼─────┐    ┌────────────┐    ┌────────────┐   │
    │  API-1    │    │   API-2    │    │   API-3    │   │
    │ (FastAPI) │    │ (FastAPI)  │    │ (FastAPI)  │  ... (auto-scaled)
    └─────┬─────┘    └─────┬──────┘    └─────┬──────┘   │
          │                │                  │          │
          └────────────────┴──────────────────┴──────────┘
                           │
          ┌────────────────┼──────────────────┐
          │                │                  │
    ┌─────▼─────┐    ┌─────▼──────┐    ┌─────▼──────┐
    │ PostgreSQL│    │   Redis    │    │   Kafka    │
    │ (shared)  │    │ (shared)   │    │ (partitioned)│
    └───────────┘    └────────────┘    └────────────┘
```

---

## Docker Compose Scaling

### 1. Basic Scaling (docker-compose.scaled.yml)

**Start the scaled environment:**

```bash
# Use the scaled compose file
docker-compose -f docker-compose.scaled.yml up -d

# Verify all instances are running
docker-compose -f docker-compose.scaled.yml ps

# Check nginx load balancer
curl http://localhost/health
```

**Current Configuration:**
- **API Instances:** 3 replicas
- **Detection Service:** 2 replicas
- **Load Balancer:** Nginx (least connections algorithm)
- **Database:** Single PostgreSQL instance with increased max_connections (200)
- **Redis:** Single instance with 512MB memory
- **Kafka:** 6 partitions for parallel processing

---

### 2. Dynamic Scaling

**Scale API instances:**

```bash
# Scale to 5 instances
docker-compose -f docker-compose.scaled.yml up -d --scale api-1=5

# Or using Docker Swarm mode (recommended for production):
docker stack deploy -c docker-compose.scaled.yml fraud-detection

# Scale using Swarm
docker service scale fraud-detection_api=10
```

**Scale detection services:**

```bash
# Kafka consumer groups auto-balance load
docker-compose -f docker-compose.scaled.yml up -d --scale detection-service-1=4
```

---

### 3. Monitoring Scaled Services

**Check instance health:**

```bash
# View all API containers
docker ps | grep api

# Check nginx upstream status
curl http://localhost:8080/nginx_status

# View logs from all instances
docker-compose -f docker-compose.scaled.yml logs -f api-1 api-2 api-3
```

**Prometheus metrics:**
```bash
# View request distribution across instances
curl http://localhost:9090/api/v1/query?query=rate(http_requests_total[5m])

# Check instance health
curl http://localhost:9090/api/v1/query?query=up{job="api"}
```

---

## Kubernetes Scaling

### 1. Deploy to Kubernetes

**Prerequisites:**
```bash
# Install kubectl
# Install cert-manager (for TLS certificates)
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Install ingress-nginx controller
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.9.0/deploy/static/provider/cloud/deploy.yaml
```

**Deploy application:**

```bash
# 1. Create namespace
kubectl apply -f k8s/api-deployment.yaml

# 2. Create secrets (update values first!)
# Edit k8s/secrets-configmap.yaml with your values
kubectl apply -f k8s/secrets-configmap.yaml

# 3. Create image pull secret (for private registry)
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_TOKEN \
  --namespace=fraud-detection

# 4. Deploy ingress controller
kubectl apply -f k8s/ingress.yaml

# 5. Verify deployment
kubectl get all -n fraud-detection
```

---

### 2. Horizontal Pod Autoscaler (HPA)

**The HPA automatically scales pods based on metrics:**

**Current Configuration:**
```yaml
minReplicas: 3
maxReplicas: 20

metrics:
  - CPU: 70% utilization
  - Memory: 80% utilization
  - HTTP requests: 1000 req/s per pod
```

**Monitor autoscaling:**

```bash
# Watch HPA status
kubectl get hpa fraud-api-hpa -n fraud-detection --watch

# View current metrics
kubectl describe hpa fraud-api-hpa -n fraud-detection

# Check pod resource usage
kubectl top pods -n fraud-detection
```

**Example scaling events:**

```
# Low traffic (3 pods)
NAME           REFERENCE             TARGETS          MINPODS   MAXPODS   REPLICAS
fraud-api-hpa  Deployment/fraud-api  45%/70% CPU      3         20        3

# Medium traffic (7 pods)
fraud-api-hpa  Deployment/fraud-api  75%/70% CPU      3         20        7

# High traffic (15 pods)
fraud-api-hpa  Deployment/fraud-api  85%/70% CPU      3         20        15
```

---

### 3. Custom Metrics Autoscaling

**Scale based on custom metrics (requests per second):**

**Install Prometheus Adapter:**

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --set prometheus.url=http://prometheus-service:9090

# Verify custom metrics
kubectl get --raw /apis/custom.metrics.k8s.io/v1beta1 | jq .
```

**View custom metrics:**

```bash
# HTTP requests per second
kubectl get --raw "/apis/custom.metrics.k8s.io/v1beta1/namespaces/fraud-detection/pods/*/http_requests_per_second" | jq .
```

---

### 4. Vertical Pod Autoscaler (VPA)

**Automatically adjust resource requests/limits:**

```bash
# Install VPA
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
./hack/vpa-up.sh

# Create VPA for fraud-api
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: fraud-api-vpa
  namespace: fraud-detection
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: fraud-api
  updatePolicy:
    updateMode: "Auto"
  resourcePolicy:
    containerPolicies:
      - containerName: fraud-api
        minAllowed:
          cpu: 250m
          memory: 256Mi
        maxAllowed:
          cpu: 2000m
          memory: 2Gi
EOF

# Check VPA recommendations
kubectl describe vpa fraud-api-vpa -n fraud-detection
```

---

## Load Balancing Strategies

### 1. Nginx Load Balancing Algorithms

**Least Connections (current):**
```nginx
upstream fraud_api {
    least_conn;  # Route to server with fewest active connections
    server api-1:8000;
    server api-2:8000;
    server api-3:8000;
}
```

**Round Robin:**
```nginx
upstream fraud_api {
    # Default: distribute requests evenly
    server api-1:8000;
    server api-2:8000;
    server api-3:8000;
}
```

**IP Hash (sticky sessions):**
```nginx
upstream fraud_api {
    ip_hash;  # Same client always goes to same server
    server api-1:8000;
    server api-2:8000;
    server api-3:8000;
}
```

**Weighted:**
```nginx
upstream fraud_api {
    server api-1:8000 weight=3;  # Gets 3x more requests
    server api-2:8000 weight=2;
    server api-3:8000 weight=1;
}
```

---

### 2. Kubernetes Service Load Balancing

**Current: ClusterIP with Round Robin**

```yaml
spec:
  type: ClusterIP  # Internal load balancing
  sessionAffinity: None  # No sticky sessions
```

**Enable sticky sessions:**

```yaml
spec:
  type: ClusterIP
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 3600  # 1 hour
```

---

## Database Connection Pooling

### 1. PostgreSQL Configuration

**Increase max connections:**

```yaml
# In docker-compose.scaled.yml or Kubernetes ConfigMap
environment:
  POSTGRES_MAX_CONNECTIONS: 200  # Increased from default 100
```

**Calculate required connections:**

```
Total Connections = (API Instances × Connections per Instance) + (Detection Services × Connections) + Buffer

Example:
= (10 API pods × 10 connections) + (5 detection pods × 5 connections) + 25 buffer
= 100 + 25 + 25
= 150 connections
```

---

### 2. Application-Level Pooling (SQLAlchemy)

**Configure connection pool in database.py:**

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,           # Connections per instance
    max_overflow=20,        # Additional connections during burst
    pool_timeout=30,        # Wait 30s for connection
    pool_recycle=3600,      # Recycle connections after 1 hour
    pool_pre_ping=True,     # Test connections before use
    echo_pool=True          # Log pool events (debug only)
)
```

**Monitor connection pool:**

```python
# Add to API startup
@app.on_event("startup")
def check_pool():
    logger.info(f"Connection pool size: {engine.pool.size()}")
    logger.info(f"Pool overflow: {engine.pool.overflow()}")
```

---

## Redis Scaling

### 1. Redis Cluster (High Availability)

**For production, use Redis Cluster:**

```yaml
# docker-compose.redis-cluster.yml
services:
  redis-1:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000

  redis-2:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000

  redis-3:
    image: redis:7-alpine
    command: redis-server --cluster-enabled yes --cluster-config-file nodes.conf --cluster-node-timeout 5000
```

**Create cluster:**

```bash
redis-cli --cluster create \
  redis-1:6379 redis-2:6379 redis-3:6379 \
  --cluster-replicas 1
```

---

### 2. Redis Sentinel (Auto-Failover)

**For automatic failover:**

```yaml
redis-master:
  image: redis:7-alpine
  command: redis-server --maxmemory 512mb

redis-sentinel-1:
  image: redis:7-alpine
  command: redis-sentinel /etc/redis/sentinel.conf
  volumes:
    - ./sentinel.conf:/etc/redis/sentinel.conf
```

**sentinel.conf:**

```conf
sentinel monitor mymaster redis-master 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel parallel-syncs mymaster 1
sentinel failover-timeout mymaster 10000
```

---

## Kafka Scaling

### 1. Increase Partitions

**More partitions = more parallel processing:**

```bash
# Increase to 12 partitions
kafka-topics.sh --alter \
  --zookeeper zookeeper:2181 \
  --topic transactions_topic \
  --partitions 12

# Verify
kafka-topics.sh --describe \
  --zookeeper zookeeper:2181 \
  --topic transactions_topic
```

**Rule of thumb:**
- **Partitions ≥ Consumer instances** for optimal parallelism
- Example: 12 partitions → can use up to 12 detection service instances

---

### 2. Consumer Group Scaling

**Kafka automatically balances partitions across consumers in a group:**

```python
# In detection_service.py
consumer = KafkaConsumer(
    'transactions_topic',
    bootstrap_servers=['kafka:29092'],
    group_id='fraud-detectors',  # All instances share same group
    auto_offset_reset='earliest'
)
```

**Scale detection services:**

```bash
# Docker Compose
docker-compose -f docker-compose.scaled.yml up -d --scale detection-service-1=12

# Kubernetes
kubectl scale deployment fraud-detection-service --replicas=12 -n fraud-detection
```

---

## Performance Tuning

### 1. Optimize API Response Times

**Target metrics:**
- p50 latency: <50ms
- p95 latency: <200ms
- p99 latency: <500ms

**Tuning strategies:**

**a) Enable caching:**
```env
CACHE_TTL_ANOMALIES=120  # Increase from 60 to 120 seconds
```

**b) Database query optimization:**
```sql
-- Add indexes
CREATE INDEX idx_transactions_anomaly_score ON transactions(ml_anomaly_score DESC) WHERE is_anomaly = 1;
CREATE INDEX idx_transactions_status ON transactions(status) WHERE is_anomaly = 1;
```

**c) Connection pooling:**
```python
pool_size=20  # Increase from 10
max_overflow=40  # Increase from 20
```

---

### 2. Optimize Detection Service Throughput

**Target metrics:**
- Transactions processed: >1000/sec
- Average processing time: <100ms
- Kafka lag: <1000 messages

**Tuning strategies:**

**a) Batch processing:**
```python
# Process messages in batches
consumer.poll(timeout_ms=1000, max_records=100)
```

**b) Async database writes:**
```python
# Use bulk inserts
df.to_sql(TABLE_NAME, db_conn, if_exists='append', method='multi', chunksize=1000)
```

**c) Increase consumer instances:**
```bash
# Match number of Kafka partitions
kubectl scale deployment fraud-detection-service --replicas=12
```

---

## Monitoring Scaled Infrastructure

### 1. Key Metrics to Monitor

**API Instances:**
- CPU usage per pod
- Memory usage per pod
- Request rate per pod
- Error rate per pod
- Response time (p50, p95, p99)

**Database:**
- Active connections
- Connection pool utilization
- Query latency
- Locks and deadlocks

**Redis:**
- Memory usage
- Cache hit rate
- Evicted keys
- Commands per second

**Kafka:**
- Consumer lag
- Partition assignment
- Messages per second
- Rebalance rate

---

### 2. Grafana Dashboards

**Create dashboard panels:**

```promql
# Request distribution across pods
sum by (pod) (rate(http_requests_total[5m]))

# Average response time per pod
avg by (pod) (rate(http_request_duration_seconds_sum[5m]) / rate(http_request_duration_seconds_count[5m]))

# Database connection pool usage
database_pool_size - database_pool_available

# Cache hit rate
(sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))) * 100

# Kafka consumer lag
kafka_consumer_lag{topic="transactions_topic"}
```

---

## Troubleshooting

### Issue 1: Uneven Load Distribution

**Symptoms:**
- Some API pods have high CPU while others are idle
- Requests not balanced across instances

**Diagnosis:**

```bash
# Check request count per pod
kubectl top pods -n fraud-detection

# Check nginx upstream status
curl http://localhost:8080/nginx_status
```

**Solutions:**

1. **Change load balancing algorithm:**
   ```nginx
   upstream fraud_api {
       least_conn;  # Use least connections instead of round robin
   }
   ```

2. **Verify health checks:**
   ```bash
   kubectl describe pod PODNAME -n fraud-detection
   # Check readinessProbe is passing
   ```

3. **Check pod resource limits:**
   ```yaml
   resources:
     limits:
       cpu: 1000m  # Ensure all pods have same limits
   ```

---

### Issue 2: Database Connection Pool Exhausted

**Symptoms:**
- "Too many connections" errors
- High latency on database queries
- Timeouts waiting for connections

**Diagnosis:**

```bash
# Check active connections
docker-compose exec db psql -U user -d bankdb -c "SELECT count(*) FROM pg_stat_activity;"

# Check max connections
docker-compose exec db psql -U user -d bankdb -c "SHOW max_connections;"
```

**Solutions:**

1. **Increase PostgreSQL max_connections:**
   ```yaml
   environment:
     POSTGRES_MAX_CONNECTIONS: 300
   ```

2. **Reduce connection pool size per instance:**
   ```python
   pool_size=5  # Reduce from 10
   max_overflow=10  # Reduce from 20
   ```

3. **Enable connection pooling proxy (PgBouncer):**
   ```yaml
   pgbouncer:
     image: pgbouncer/pgbouncer
     environment:
       - DATABASES_HOST=db
       - POOL_MODE=transaction
       - MAX_CLIENT_CONN=1000
       - DEFAULT_POOL_SIZE=25
   ```

---

### Issue 3: Kafka Consumer Lag Increasing

**Symptoms:**
- Detection service falling behind
- Lag metric growing
- Delayed fraud detection

**Diagnosis:**

```bash
# Check consumer group lag
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group fraud-detectors

# View lag in Prometheus
curl 'http://localhost:9090/api/v1/query?query=kafka_consumer_lag'
```

**Solutions:**

1. **Increase detection service instances:**
   ```bash
   kubectl scale deployment fraud-detection-service --replicas=12
   ```

2. **Increase Kafka partitions:**
   ```bash
   kafka-topics.sh --alter --topic transactions_topic --partitions 24
   ```

3. **Optimize message processing:**
   - Enable batch processing
   - Reduce per-message processing time
   - Increase consumer fetch size

---

## Best Practices

### 1. Gradual Scaling

**Don't scale from 3 to 100 pods instantly:**

```bash
# Scale gradually
kubectl scale deployment fraud-api --replicas=10  # First increase
# Monitor for 30 minutes
kubectl scale deployment fraud-api --replicas=20  # Second increase
# Monitor for 30 minutes
kubectl scale deployment fraud-api --replicas=40  # Final target
```

### 2. Set Resource Limits

**Always set both requests and limits:**

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi
```

### 3. Use Pod Disruption Budgets

**Prevent all pods from being terminated simultaneously:**

```yaml
minAvailable: 2  # Always keep at least 2 pods running
```

### 4. Enable Autoscaling for All Components

- ✅ API: HPA based on CPU + memory + requests
- ✅ Detection service: HPA based on Kafka lag
- ✅ Database: Use managed service with auto-scaling (RDS, Cloud SQL)
- ✅ Redis: Use managed service (ElastiCache, Cloud Memorystore)

---

## References

- **Docker Compose Scaling:** https://docs.docker.com/compose/compose-file/deploy/
- **Kubernetes HPA:** https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/
- **Nginx Load Balancing:** http://nginx.org/en/docs/http/load_balancing.html
- **PostgreSQL Connection Pooling:** https://www.postgresql.org/docs/current/runtime-config-connection.html

---

**Last Updated:** 2025-12-23
**Version:** 1.0
**Maintained By:** Infrastructure Team
