"""
Redis caching utilities
"""

import os
import json
from typing import Optional, Any
import redis.asyncio as redis
from loguru import logger


# Global Redis client
_redis_client = None


async def get_redis_client():
    """Get or create Redis client"""
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        logger.info(f"Connecting to Redis: {redis_url}")

        _redis_client = await redis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )

        logger.info("Redis client created")

    return _redis_client


async def close_redis_client():
    """Close Redis client"""
    global _redis_client

    if _redis_client:
        logger.info("Closing Redis client")
        await _redis_client.close()
        _redis_client = None


async def check_redis_health() -> bool:
    """Check Redis connectivity"""
    try:
        client = await get_redis_client()
        await client.ping()
        return True
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False


async def get_from_cache(key: str) -> Optional[Any]:
    """Get value from Redis cache"""
    try:
        client = await get_redis_client()
        value = await client.get(key)

        if value:
            return json.loads(value)

        return None

    except Exception as e:
        logger.error(f"Cache get error: {e}")
        return None


async def set_cache(key: str, value: Any, ttl_seconds: int = 3600):
    """Set value in Redis cache with TTL"""
    try:
        client = await get_redis_client()
        await client.setex(
            key,
            ttl_seconds,
            json.dumps(value)
        )

        logger.debug(f"Cached {key} for {ttl_seconds}s")

    except Exception as e:
        logger.error(f"Cache set error: {e}")


async def delete_from_cache(key: str):
    """Delete key from Redis"""
    try:
        client = await get_redis_client()
        await client.delete(key)

        logger.debug(f"Deleted {key} from cache")

    except Exception as e:
        logger.error(f"Cache delete error: {e}")
