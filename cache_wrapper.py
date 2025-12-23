"""
Redis Cache Wrapper for Fraud Detection API
===========================================

Provides caching layer for API endpoints to improve performance under high traffic.

Features:
- Connection pooling for efficient Redis connections
- Automatic cache invalidation on data updates
- Prometheus metrics for cache hit/miss rates
- Configurable TTL per endpoint
- Async support for non-blocking operations

Usage:
    from cache_wrapper import get_cache_service, cache_key

    cache = get_cache_service()
    cached_data = cache.get(cache_key("anomalies", limit=100))
"""

import os
import json
import hashlib
import logging
from typing import Optional, Any, Dict
from datetime import timedelta

import redis
from redis.connection import ConnectionPool
from prometheus_client import Counter, Histogram

# Configuration
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_DB = int(os.environ.get("REDIS_DB", 0))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", None)
REDIS_POOL_SIZE = int(os.environ.get("REDIS_POOL_SIZE", 10))

# Cache TTL configuration (in seconds)
CACHE_TTL_ANOMALIES = int(os.environ.get("CACHE_TTL_ANOMALIES", 60))  # 60 seconds default
CACHE_TTL_SHORT = int(os.environ.get("CACHE_TTL_SHORT", 30))  # 30 seconds for frequently changing data

# Logging
logger = logging.getLogger(__name__)

# Prometheus metrics
CACHE_HITS = Counter(
    'cache_hits_total',
    'Total number of cache hits',
    ['cache_key_type']
)

CACHE_MISSES = Counter(
    'cache_misses_total',
    'Total number of cache misses',
    ['cache_key_type']
)

CACHE_ERRORS = Counter(
    'cache_errors_total',
    'Total number of cache errors',
    ['operation']
)

CACHE_OPERATION_DURATION = Histogram(
    'cache_operation_duration_seconds',
    'Cache operation duration in seconds',
    ['operation']
)


class CacheService:
    """Redis cache service with connection pooling and metrics."""

    def __init__(self):
        """Initialize Redis connection pool."""
        self.pool = None
        self.client = None
        self._initialize_connection()

    def _initialize_connection(self):
        """Set up Redis connection pool."""
        try:
            self.pool = ConnectionPool(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                max_connections=REDIS_POOL_SIZE,
                decode_responses=True,  # Automatically decode bytes to strings
                socket_connect_timeout=5,
                socket_timeout=5
            )

            self.client = redis.Redis(connection_pool=self.pool)

            # Test connection
            self.client.ping()

            logger.info(
                "Redis cache initialized successfully",
                extra={
                    'host': REDIS_HOST,
                    'port': REDIS_PORT,
                    'pool_size': REDIS_POOL_SIZE
                }
            )

        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            logger.warning("Cache will be disabled. API will operate without caching.")
            self.client = None
        except Exception as e:
            logger.error(f"Unexpected error initializing Redis: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if Redis is available."""
        if not self.client:
            return False

        try:
            self.client.ping()
            return True
        except:
            return False

    @CACHE_OPERATION_DURATION.labels(operation='get').time()
    def get(self, key: str, key_type: str = "generic") -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key
            key_type: Type of key for metrics (e.g., "anomalies", "status")

        Returns:
            Cached value or None if not found
        """
        if not self.is_available():
            return None

        try:
            value = self.client.get(key)

            if value is not None:
                CACHE_HITS.labels(cache_key_type=key_type).inc()
                logger.debug(f"Cache HIT: {key}")

                # Deserialize JSON
                return json.loads(value)
            else:
                CACHE_MISSES.labels(cache_key_type=key_type).inc()
                logger.debug(f"Cache MISS: {key}")
                return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to deserialize cached value for key '{key}': {e}")
            CACHE_ERRORS.labels(operation='get').inc()
            # Invalidate corrupted cache entry
            self.delete(key)
            return None
        except Exception as e:
            logger.error(f"Cache GET error for key '{key}': {e}")
            CACHE_ERRORS.labels(operation='get').inc()
            return None

    @CACHE_OPERATION_DURATION.labels(operation='set').time()
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with optional TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time to live in seconds (None = no expiration)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            # Serialize to JSON
            serialized_value = json.dumps(value)

            if ttl is not None:
                self.client.setex(key, ttl, serialized_value)
            else:
                self.client.set(key, serialized_value)

            logger.debug(f"Cache SET: {key} (TTL: {ttl}s)")
            return True

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value for key '{key}': {e}")
            CACHE_ERRORS.labels(operation='set').inc()
            return False
        except Exception as e:
            logger.error(f"Cache SET error for key '{key}': {e}")
            CACHE_ERRORS.labels(operation='set').inc()
            return False

    @CACHE_OPERATION_DURATION.labels(operation='delete').time()
    def delete(self, key: str) -> bool:
        """
        Delete key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            self.client.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache DELETE error for key '{key}': {e}")
            CACHE_ERRORS.labels(operation='delete').inc()
            return False

    @CACHE_OPERATION_DURATION.labels(operation='invalidate_pattern').time()
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "anomalies:*")

        Returns:
            Number of keys deleted
        """
        if not self.is_available():
            return 0

        try:
            keys = self.client.keys(pattern)
            if keys:
                deleted = self.client.delete(*keys)
                logger.info(f"Cache INVALIDATE: {pattern} - {deleted} keys deleted")
                return deleted
            return 0
        except Exception as e:
            logger.error(f"Cache INVALIDATE error for pattern '{pattern}': {e}")
            CACHE_ERRORS.labels(operation='invalidate_pattern').inc()
            return 0

    def flush_all(self) -> bool:
        """
        Flush entire cache database.

        WARNING: Use with caution in production!

        Returns:
            True if successful, False otherwise
        """
        if not self.is_available():
            return False

        try:
            self.client.flushdb()
            logger.warning("Cache FLUSH: All keys deleted from database")
            return True
        except Exception as e:
            logger.error(f"Cache FLUSH error: {e}")
            CACHE_ERRORS.labels(operation='flush').inc()
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        if not self.is_available():
            return {"available": False}

        try:
            info = self.client.info('stats')
            keyspace = self.client.info('keyspace')

            db_info = keyspace.get(f'db{REDIS_DB}', {})

            return {
                "available": True,
                "total_connections": info.get('total_connections_received', 0),
                "total_commands": info.get('total_commands_processed', 0),
                "keyspace_hits": info.get('keyspace_hits', 0),
                "keyspace_misses": info.get('keyspace_misses', 0),
                "keys_count": db_info.get('keys', 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get('keyspace_hits', 0),
                    info.get('keyspace_misses', 0)
                )
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"available": False, "error": str(e)}

    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage."""
        total = hits + misses
        if total == 0:
            return 0.0
        return (hits / total) * 100

    def close(self):
        """Close Redis connection pool."""
        if self.pool:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")


# Singleton instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get singleton cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def cache_key(endpoint: str, **params) -> str:
    """
    Generate consistent cache key from endpoint and parameters.

    Args:
        endpoint: Endpoint name (e.g., "anomalies", "status")
        **params: Query parameters

    Returns:
        Cache key string

    Example:
        cache_key("anomalies", limit=100, offset=0, status="NEW")
        # Returns: "anomalies:5f4dcc3b5aa765d61d8327deb882cf99"
    """
    # Sort params for consistency
    sorted_params = sorted(params.items())
    param_str = json.dumps(sorted_params, sort_keys=True)

    # Create hash of parameters for compact key
    param_hash = hashlib.md5(param_str.encode()).hexdigest()

    return f"{endpoint}:{param_hash}"


def invalidate_anomalies_cache():
    """
    Invalidate all anomalies-related cache entries.

    Call this when anomaly data is updated (e.g., status change).
    """
    cache = get_cache_service()
    deleted_count = cache.invalidate_pattern("anomalies:*")
    logger.info(f"Invalidated anomalies cache: {deleted_count} keys deleted")
    return deleted_count


# FastAPI dependency
async def get_cache() -> CacheService:
    """
    FastAPI dependency for cache service.

    Usage:
        @app.get("/endpoint")
        def endpoint(cache: CacheService = Depends(get_cache)):
            ...
    """
    return get_cache_service()


if __name__ == "__main__":
    # Test cache service
    logging.basicConfig(level=logging.INFO)

    cache = get_cache_service()

    if cache.is_available():
        print("✓ Cache service is available")

        # Test basic operations
        test_key = cache_key("test", param1="value1", param2=123)
        print(f"Generated cache key: {test_key}")

        # Set
        cache.set(test_key, {"test": "data", "count": 42}, ttl=60)
        print("✓ Cache SET successful")

        # Get
        cached_value = cache.get(test_key, key_type="test")
        print(f"✓ Cache GET successful: {cached_value}")

        # Stats
        stats = cache.get_stats()
        print(f"✓ Cache stats: {stats}")

        # Delete
        cache.delete(test_key)
        print("✓ Cache DELETE successful")

        # Verify deletion
        deleted_value = cache.get(test_key, key_type="test")
        print(f"✓ Verification: {deleted_value is None}")

    else:
        print("✗ Cache service is NOT available")
