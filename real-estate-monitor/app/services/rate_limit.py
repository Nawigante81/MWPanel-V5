"""
Rate limiting service using Redis token bucket algorithm.
Provides per-source request pacing with distributed locking.
"""
import asyncio
import random
import time
from typing import Optional

import redis

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("rate_limit")


class TokenBucket:
    """
    Token bucket rate limiter using Redis.
    
    Each source gets its own bucket with configurable:
    - rate: tokens per second (request rate)
    - burst: maximum bucket size (burst capacity)
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self._lock = asyncio.Lock()
    
    def _bucket_key(self, source_name: str) -> str:
        """Generate Redis key for token bucket."""
        return f"rate_limit:bucket:{source_name}"
    
    def _last_request_key(self, source_name: str) -> str:
        """Generate Redis key for last request timestamp."""
        return f"rate_limit:last_request:{source_name}"
    
    async def acquire(
        self,
        source_name: str,
        rate_per_second: float,
        burst: int = 1,
        timeout: float = 60.0,
    ) -> bool:
        """
        Acquire a token from the bucket.
        
        Args:
            source_name: Unique identifier for the source
            rate_per_second: Token refill rate (requests per second)
            burst: Maximum bucket size
            timeout: Maximum time to wait for a token
        
        Returns:
            True if token acquired, False if timeout
        """
        bucket_key = self._bucket_key(source_name)
        last_request_key = self._last_request_key(source_name)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Try to acquire token using Redis Lua script for atomicity
            acquired = self._try_acquire_token(
                bucket_key, last_request_key, rate_per_second, burst
            )
            
            if acquired:
                logger.debug(
                    "Rate limit token acquired",
                    extra={"source": source_name, "rate": rate_per_second},
                )
                return True
            
            # Wait before retrying
            await asyncio.sleep(0.1)
        
        logger.warning(
            "Rate limit timeout",
            extra={"source": source_name, "timeout": timeout},
        )
        return False
    
    def _try_acquire_token(
        self,
        bucket_key: str,
        last_request_key: str,
        rate_per_second: float,
        burst: int,
    ) -> bool:
        """
        Atomically try to acquire a token using Redis.
        
        Uses Lua script for atomic check-and-update.
        """
        lua_script = """
            local bucket_key = KEYS[1]
            local last_request_key = KEYS[2]
            local rate = tonumber(ARGV[1])
            local burst = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            
            -- Get current bucket state
            local tokens = redis.call('GET', bucket_key)
            local last_request = redis.call('GET', last_request_key)
            
            if tokens == false then
                tokens = burst
            else
                tokens = tonumber(tokens)
            end
            
            if last_request == false then
                last_request = now
            else
                last_request = tonumber(last_request)
            end
            
            -- Calculate tokens to add based on time elapsed
            local elapsed = now - last_request
            local tokens_to_add = elapsed * rate
            tokens = math.min(tokens + tokens_to_add, burst)
            
            -- Try to consume a token
            if tokens >= 1 then
                tokens = tokens - 1
                redis.call('SET', bucket_key, tokens)
                redis.call('SET', last_request_key, now)
                redis.call('EXPIRE', bucket_key, 3600)
                redis.call('EXPIRE', last_request_key, 3600)
                return 1
            else
                redis.call('SET', bucket_key, tokens)
                redis.call('SET', last_request_key, now)
                redis.call('EXPIRE', bucket_key, 3600)
                redis.call('EXPIRE', last_request_key, 3600)
                return 0
            end
        """
        
        try:
            result = self.redis.eval(
                lua_script,
                2,  # number of keys
                bucket_key,
                last_request_key,
                rate_per_second,
                burst,
                time.time(),
            )
            return result == 1
        except redis.RedisError as e:
            logger.error("Redis error in rate limiter", extra={"error": str(e)})
            # Fail open - allow request on Redis error
            return True
    
    async def wait_if_needed(
        self,
        source_name: str,
        rate_per_second: float,
    ) -> None:
        """
        Wait if rate limit would be exceeded.
        
        This is a simpler approach - just ensure minimum interval between requests.
        """
        last_request_key = self._last_request_key(source_name)
        min_interval = 1.0 / rate_per_second if rate_per_second > 0 else 1.0
        
        # Add jitter to avoid thundering herd (±20%)
        jitter = random.uniform(0.8, 1.2)
        min_interval *= jitter
        
        last_request = self.redis.get(last_request_key)
        
        if last_request:
            last_time = float(last_request)
            elapsed = time.time() - last_time
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                logger.debug(
                    "Rate limit sleep",
                    extra={"source": source_name, "sleep": sleep_time},
                )
                await asyncio.sleep(sleep_time)
        
        # Update last request time
        self.redis.setex(last_request_key, 3600, time.time())


class DistributedLock:
    """
    Distributed lock using Redis for preventing stampede.
    
    Ensures only one worker processes a (source, filter) combination at a time.
    """
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def _lock_key(self, resource: str) -> str:
        """Generate Redis key for lock."""
        return f"lock:{resource}"
    
    def acquire(
        self,
        resource: str,
        ttl_seconds: int = 300,
    ) -> Optional[str]:
        """
        Try to acquire a distributed lock.
        
        Args:
            resource: Unique resource identifier
            ttl_seconds: Lock expiration time
        
        Returns:
            Lock token if acquired, None otherwise
        """
        lock_key = self._lock_key(resource)
        token = f"{time.time()}:{random.randint(1000, 9999)}"
        
        # Use SET NX EX for atomic lock acquisition
        acquired = self.redis.set(lock_key, token, nx=True, ex=ttl_seconds)
        
        if acquired:
            logger.debug("Lock acquired", extra={"resource": resource})
            return token
        
        return None
    
    def release(self, resource: str, token: str) -> bool:
        """
        Release a distributed lock.
        
        Uses Lua script to ensure we only release our own lock.
        """
        lock_key = self._lock_key(resource)
        
        lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
        """
        
        try:
            result = self.redis.eval(lua_script, 1, lock_key, token)
            released = result == 1
            
            if released:
                logger.debug("Lock released", extra={"resource": resource})
            
            return released
        except redis.RedisError as e:
            logger.error("Error releasing lock", extra={"error": str(e)})
            return False
    
    def extend(self, resource: str, token: str, ttl_seconds: int) -> bool:
        """Extend lock expiration."""
        lock_key = self._lock_key(resource)
        
        lua_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("EXPIRE", KEYS[1], ARGV[2])
            else
                return 0
            end
        """
        
        try:
            result = self.redis.eval(lua_script, 1, lock_key, token, ttl_seconds)
            return result == 1
        except redis.RedisError:
            return False


# Global instances
_redis_client: Optional[redis.Redis] = None
_token_bucket: Optional[TokenBucket] = None
_distributed_lock: Optional[DistributedLock] = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
    
    return _redis_client


def get_token_bucket() -> TokenBucket:
    """Get or create token bucket rate limiter."""
    global _token_bucket
    
    if _token_bucket is None:
        _token_bucket = TokenBucket(get_redis_client())
    
    return _token_bucket


def get_distributed_lock() -> DistributedLock:
    """Get or create distributed lock."""
    global _distributed_lock
    
    if _distributed_lock is None:
        _distributed_lock = DistributedLock(get_redis_client())
    
    return _distributed_lock
