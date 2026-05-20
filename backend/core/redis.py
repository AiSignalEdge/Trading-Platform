"""
Redis Configuration - aioredis for caching, queue, and pub/sub.

Section 17: Tech Stack from PLAN-v2.md
"""

import json
from typing import Any, Optional
from contextlib import asynccontextmanager
from datetime import timedelta

import redis.asyncio as redis
from redis.asyncio import Redis, ConnectionPool

from .config import settings


class RedisManager:
    """
    Redis manager for caching, pub/sub, and rate limiting.
    Uses aioredis for async operations.
    """
    
    def __init__(self):
        self._pool: Optional[ConnectionPool] = None
        self._client: Optional[Redis] = None
    
    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        self._pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
        self._client = Redis(connection_pool=self._pool)
        await self._client.ping()
    
    async def disconnect(self) -> None:
        """Close Redis connections."""
        if self._client:
            await self._client.close()
        if self._pool:
            await self._pool.disconnect()
    
    @property
    def client(self) -> Redis:
        """Get Redis client."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client
    
    # ====================
    # Cache Operations
    # ====================
    
    async def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        return await self.client.get(key)
    
    async def get_json(self, key: str) -> Optional[Any]:
        """Get JSON value from cache."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None
    
    async def set(
        self,
        key: str,
        value: str,
        expire: Optional[int] = None,
    ) -> None:
        """Set value in cache with optional TTL in seconds."""
        if expire:
            await self.client.setex(key, expire, value)
        else:
            await self.client.set(key, value)
    
    async def set_json(
        self,
        key: str,
        value: Any,
        expire: Optional[int] = None,
    ) -> None:
        """Set JSON value in cache with optional TTL."""
        await self.set(key, json.dumps(value), expire)
    
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        await self.client.delete(key)
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return await self.client.exists(key) > 0
    
    # ====================
    # Pub/Sub Operations
    # ====================
    
    async def publish(self, channel: str, message: str) -> int:
        """Publish message to channel."""
        return await self.client.publish(channel, message)
    
    async def publish_json(self, channel: str, message: Any) -> int:
        """Publish JSON message to channel."""
        return await self.publish(channel, json.dumps(message))
    
    @asynccontextmanager
    async def subscribe(self, *channels: str):
        """Subscribe to channels (context manager for proper cleanup)."""
        pubsub = self.client.pubsub()
        await pubsub.subscribe(*channels)
        try:
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
    
    # ====================
    # Rate Limiting
    # ====================
    
    async def rate_limit_check(
        self,
        key: str,
        max_calls: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Token bucket rate limiter.
        Returns (allowed, remaining_calls).
        """
        bucket_key = f"rate_limit:{key}"
        current = await self.client.incr(bucket_key)
        
        if current == 1:
            # First call - set expiry
            await self.client.expire(bucket_key, window_seconds + 1)
        
        remaining = max(0, max_calls - current)
        allowed = current <= max_calls
        
        if not allowed:
            # Calculate sleep time until window resets
            ttl = await self.client.ttl(bucket_key)
            if ttl < 0:
                ttl = window_seconds
        
        return allowed, remaining
    
    # ====================
    # Queue Operations
    # ====================
    
    async def enqueue(self, queue: str, item: str) -> None:
        """Add item to queue."""
        await self.client.rpush(f"queue:{queue}", item)
    
    async def dequeue(self, queue: str, timeout: int = 0) -> Optional[str]:
        """Get item from queue (blocking if timeout > 0)."""
        if timeout > 0:
            result = await self.client.blpop(f"queue:{queue}", timeout=timeout)
            if result:
                return result[1]
            return None
        return await self.client.lpop(f"queue:{queue}")
    
    async def queue_length(self, queue: str) -> int:
        """Get queue length."""
        return await self.client.llen(f"queue:{queue}")
    
    # ====================
    # Key Operations
    # ====================
    
    async def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern."""
        return await self.client.keys(pattern)
    
    async def flush_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern. Returns count deleted."""
        keys = await self.keys(pattern)
        if keys:
            return await self.client.delete(*keys)
        return 0


# Global Redis manager instance
redis_manager = RedisManager()


async def get_redis() -> Redis:
    """Dependency for getting Redis client."""
    return redis_manager.client


async def init_redis() -> None:
    """Initialize Redis connection."""
    await redis_manager.connect()


async def close_redis() -> None:
    """Close Redis connection."""
    await redis_manager.disconnect()