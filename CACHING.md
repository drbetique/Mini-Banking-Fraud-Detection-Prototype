# Redis Caching System

## Overview

The fraud detection API uses Redis as an in-memory caching layer to optimize performance under high traffic. Caching reduces database load and improves response times for frequently accessed anomaly queries.

**Key Features:**
- Connection pooling for efficient Redis connections
- Automatic cache invalidation on data updates
- Prometheus metrics for cache monitoring
- Configurable TTL (time-to-live) per endpoint
- Graceful degradation (API continues to work if Redis is unavailable)

---

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│         FastAPI Application         │
│  ┌───────────────────────────────┐  │
│  │   Cache Middleware Layer      │  │
│  │  (cache_wrapper.py)           │  │
│  └───────┬──────────────┬────────┘  │
│          │              │            │
│     CACHE HIT      CACHE MISS        │
│          │              │            │
│          │              ▼            │
│          │    ┌──────────────────┐  │
│          │    │   PostgreSQL DB  │  │
│          │    └──────────────────┘  │
│          │              │            │
│          │              ▼            │
│          │    ┌──────────────────┐  │
│          └───>│  Response + Cache│  │
│               └──────────────────┘  │
└─────────────────────────────────────┘
           │
           ▼
    ┌──────────────┐
    │  Redis Cache │
    │  (in-memory) │
    └──────────────┘
```

---

## How It Works

### 1. Cache Key Generation

Cache keys are generated from endpoint names and query parameters:

```python
from cache_wrapper import cache_key

# Generate cache key
key = cache_key(
    "anomalies",
    limit=100,
    offset=0,
    min_score=0.8,
    status="NEW"
)
# Returns: "anomalies:5f4dcc3b5aa765d61d8327deb882cf99"
```

**Key features:**
- Parameters are sorted for consistency
- MD5 hash ensures compact keys
- Same parameters always generate the same key

---

### 2. Cache Lookup Flow

**GET `/api/v1/anomalies` Request:**

1. **Generate cache key** from query parameters
2. **Check Redis cache** for existing result
3. **If CACHE HIT:**
   - Return cached result immediately
   - Log cache hit with Prometheus metrics
   - Response time: ~5-10ms
4. **If CACHE MISS:**
   - Query PostgreSQL database
   - Store result in Redis with TTL
   - Return result to client
   - Log cache miss with Prometheus metrics
   - Response time: ~50-200ms (depends on query complexity)

---

### 3. Cache Invalidation

**PUT `/api/v1/anomalies/{transaction_id}` Request:**

When a transaction status is updated, all cached anomaly queries are invalidated:

```python
# In api.py - update_anomaly_status()
db.execute(update_query)
db.commit()

# Invalidate all anomalies cache entries
invalidate_anomalies_cache()  # Deletes all keys matching "anomalies:*"
```

**Why invalidate all keys?**
- A status update affects multiple query results (filtered by status, score, etc.)
- Pattern-based invalidation ensures consistency
- Next request will fetch fresh data from database

---

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# Redis connection settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=your-redis-password  # Optional
REDIS_POOL_SIZE=10

# Cache TTL (seconds)
CACHE_TTL_ANOMALIES=60    # 60 seconds for anomaly queries
CACHE_TTL_SHORT=30        # 30 seconds for frequently changing data
```

### Docker Compose

Redis service is already configured in `docker-compose.yml`:

```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

**Configuration details:**
- `--appendonly yes`: Persistence enabled (survives restarts)
- `--maxmemory 256mb`: Memory limit (adjust based on your needs)
- `--maxmemory-policy allkeys-lru`: Evict least recently used keys when full
- Health check: Ensures Redis is responsive

---

## Usage

### Starting the System

```bash
# Start all services including Redis
docker-compose up -d

# Verify Redis is running
docker-compose ps redis

# Check Redis logs
docker-compose logs redis
```

### Testing the Cache

**Test 1: Basic caching**

```bash
# First request (cache miss - slow)
time curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/anomalies?limit=100"
# Expected: ~100-200ms

# Second request (cache hit - fast)
time curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/anomalies?limit=100"
# Expected: ~5-10ms
```

**Test 2: Cache invalidation**

```bash
# Get anomalies (cached)
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/anomalies?limit=10"

# Update a transaction status
curl -X PUT -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"new_status": "INVESTIGATED"}' \
  "http://localhost:8000/api/v1/anomalies/STRIPE_ch_3Sg..."

# Get anomalies again (cache invalidated, fresh data)
curl -H "X-API-Key: your-api-key" \
  "http://localhost:8000/api/v1/anomalies?limit=10"
```

---

## Monitoring

### Prometheus Metrics

The cache system exposes the following metrics:

**1. Cache Hits**
```
cache_hits_total{cache_key_type="anomalies"} 150
```

**2. Cache Misses**
```
cache_misses_total{cache_key_type="anomalies"} 25
```

**3. Cache Errors**
```
cache_errors_total{operation="get"} 0
cache_errors_total{operation="set"} 0
```

**4. Operation Duration**
```
cache_operation_duration_seconds{operation="get"} 0.005
cache_operation_duration_seconds{operation="set"} 0.003
```

### Calculating Cache Hit Rate

**Cache Hit Rate = Hits / (Hits + Misses)**

Example Prometheus query:
```promql
# Cache hit rate percentage
(
  sum(rate(cache_hits_total[5m]))
  /
  (
    sum(rate(cache_hits_total[5m])) +
    sum(rate(cache_misses_total[5m]))
  )
) * 100
```

**Interpreting results:**
- **90-100%**: Excellent caching performance
- **70-90%**: Good caching, most requests served from cache
- **50-70%**: Moderate caching, consider increasing TTL
- **<50%**: Poor caching, investigate TTL settings or query patterns

---

## Performance Tuning

### Adjusting TTL

**Default TTL:** 60 seconds

**When to increase TTL:**
- Low cache hit rate (<70%)
- Anomaly data doesn't change frequently
- High database load

```env
# Increase to 5 minutes
CACHE_TTL_ANOMALIES=300
```

**When to decrease TTL:**
- Need near real-time data freshness
- Frequent status updates
- Low traffic (caching less beneficial)

```env
# Decrease to 30 seconds
CACHE_TTL_ANOMALIES=30
```

---

### Adjusting Memory Limit

**Default:** 256MB

**Calculate required memory:**

```
Memory = (Avg Response Size) × (Cache Entries) × (Overhead Factor)

Example:
- Avg response size: 50KB (100 transactions × 500 bytes each)
- Cache entries: 100 (different query combinations)
- Overhead factor: 1.5 (Redis metadata)

Required = 50KB × 100 × 1.5 = 7.5MB
```

**To increase memory limit:**

```yaml
# In docker-compose.yml
redis:
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

---

### Adjusting Connection Pool Size

**Default:** 10 connections

**When to increase:**
- High concurrent API requests (>100 req/s)
- Connection timeout errors in logs
- Slow cache operations

```env
# Increase to 20
REDIS_POOL_SIZE=20
```

**When to decrease:**
- Low traffic
- Limited server resources
- Reduce Redis connection overhead

```env
# Decrease to 5
REDIS_POOL_SIZE=5
```

---

## Troubleshooting

### Issue 1: Cache Not Working

**Symptoms:**
- All requests show cache misses
- No performance improvement

**Diagnosis:**

```bash
# Check Redis is running
docker-compose ps redis
# Should show "Up" status

# Check Redis connectivity
docker-compose exec redis redis-cli ping
# Should return "PONG"

# Check API logs
docker-compose logs api | grep -i cache
# Should see "Cache initialized successfully"
```

**Solutions:**

1. **Redis not running:**
   ```bash
   docker-compose up -d redis
   ```

2. **Connection refused:**
   - Check `REDIS_HOST` and `REDIS_PORT` in `.env`
   - Ensure `redis` service is in same Docker network

3. **Cache disabled:**
   - Check API logs for Redis connection errors
   - If Redis fails to connect, caching is automatically disabled

---

### Issue 2: Stale Data After Updates

**Symptoms:**
- Updated transactions show old status
- Cache not invalidated after PUT requests

**Diagnosis:**

```bash
# Check logs for cache invalidation
docker-compose logs api | grep "cache invalidated"
# Should appear after PUT /api/v1/anomalies/{id}

# Manually check Redis keys
docker-compose exec redis redis-cli
> KEYS anomalies:*
# Should show cache keys (or empty after invalidation)
```

**Solutions:**

1. **Cache invalidation not working:**
   - Verify `invalidate_anomalies_cache()` is called in `update_anomaly_status()`
   - Check for errors in API logs

2. **Manual cache flush:**
   ```bash
   docker-compose exec redis redis-cli FLUSHDB
   ```

---

### Issue 3: High Memory Usage

**Symptoms:**
- Redis memory at 100% of limit
- Eviction of recently used keys
- Degraded performance

**Diagnosis:**

```bash
# Check Redis memory usage
docker-compose exec redis redis-cli INFO memory
# Look for: used_memory_human, maxmemory_human

# Check eviction stats
docker-compose exec redis redis-cli INFO stats | grep evicted
# evicted_keys should be low
```

**Solutions:**

1. **Increase memory limit:**
   ```yaml
   # docker-compose.yml
   command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
   ```

2. **Decrease TTL (reduce cache entries):**
   ```env
   CACHE_TTL_ANOMALIES=30  # Reduce from 60 to 30 seconds
   ```

3. **Monitor key count:**
   ```bash
   docker-compose exec redis redis-cli DBSIZE
   ```

---

### Issue 4: Cache Poisoning (Corrupted Data)

**Symptoms:**
- JSON decode errors in logs
- API returns 500 errors intermittently

**Diagnosis:**

```bash
# Check for JSON decode errors
docker-compose logs api | grep "JSONDecodeError"
```

**Solutions:**

1. **Automatic cleanup:**
   - Cache wrapper automatically deletes corrupted entries
   - Next request will fetch fresh data

2. **Manual flush:**
   ```bash
   docker-compose exec redis redis-cli FLUSHDB
   ```

3. **Prevent recurrence:**
   - Ensure all cached data is JSON-serializable
   - Update cache_wrapper.py if storing complex objects

---

## Best Practices

### 1. Cache Warming

Pre-populate cache with frequently accessed queries on startup:

```python
# In api.py startup event
@app.on_event("startup")
async def warm_cache():
    """Pre-populate cache with common queries."""
    cache = get_cache_service()

    if cache.is_available():
        # Warm up with common queries
        common_queries = [
            {"limit": 100, "offset": 0, "status": "NEW"},
            {"limit": 100, "offset": 0, "min_score": 0.8},
        ]

        for query in common_queries:
            # Execute query to populate cache
            # ... query logic ...
            pass
```

---

### 2. Cache Monitoring Dashboard

Add to Grafana dashboard:

```promql
# Cache Hit Rate
(
  sum(rate(cache_hits_total[5m]))
  /
  (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))
) * 100

# Cache Operation Latency (p95)
histogram_quantile(0.95, rate(cache_operation_duration_seconds_bucket[5m]))

# Cache Error Rate
sum(rate(cache_errors_total[5m]))
```

---

### 3. Production Checklist

**Before deploying to production:**

- [ ] Set strong `REDIS_PASSWORD` in production
- [ ] Adjust `CACHE_TTL_ANOMALIES` based on data freshness requirements
- [ ] Configure `maxmemory` based on expected traffic
- [ ] Set up Redis persistence (already enabled with `--appendonly yes`)
- [ ] Monitor cache hit rate (target >70%)
- [ ] Set up alerts for cache errors
- [ ] Test cache invalidation thoroughly
- [ ] Document cache key patterns for your team

---

## Advanced Usage

### Custom Cache Keys

Create custom cache keys for new endpoints:

```python
from cache_wrapper import cache_key

# In your endpoint
@app.get("/api/v1/transactions/{account_id}")
def get_transactions(account_id: str, cache: CacheService = Depends(get_cache)):
    key = cache_key("transactions", account_id=account_id)

    # Check cache
    cached = cache.get(key, key_type="transactions")
    if cached:
        return cached

    # Query database
    result = query_database(account_id)

    # Store in cache
    cache.set(key, result, ttl=30)

    return result
```

---

### Conditional Caching

Cache only for specific conditions:

```python
# Don't cache for admin users (always fresh data)
@app.get("/api/v1/anomalies")
def get_anomalies(
    user_role: str = Header(...),
    cache: CacheService = Depends(get_cache)
):
    # Skip cache for admins
    if user_role == "admin":
        return query_database()

    # Use cache for regular users
    key = cache_key("anomalies", ...)
    # ... caching logic ...
```

---

### Cache Statistics Endpoint

Expose cache stats via API:

```python
@app.get("/api/v1/cache/stats")
def get_cache_stats(cache: CacheService = Depends(get_cache)):
    """Get cache statistics."""
    return cache.get_stats()
```

**Response:**
```json
{
  "available": true,
  "total_connections": 1523,
  "total_commands": 8945,
  "keyspace_hits": 7234,
  "keyspace_misses": 1711,
  "keys_count": 42,
  "hit_rate": 80.88
}
```

---

## References

- **Redis Documentation:** https://redis.io/documentation
- **Redis Python Client:** https://redis-py.readthedocs.io/
- **Prometheus Metrics:** http://localhost:8000/metrics
- **Cache Wrapper Source:** `cache_wrapper.py`

---

**Last Updated:** 2025-12-23
**Version:** 1.0
**Maintained By:** Engineering Team
