"""
API Rate Limiting service.
Rate limits per IP address for API endpoints.
"""
import time
from typing import Optional
from dataclasses import dataclass

from app.logging_config import get_logger
from app.services.rate_limit import get_redis_client

logger = get_logger("api_rate_limit")


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10


class APIRateLimiter:
    """
    Rate limiter for API endpoints.
    
    Uses sliding window algorithm with Redis.
    """
    
    def __init__(self):
        self.redis = get_redis_client()
        self.config = RateLimitConfig()
    
    def is_allowed(self, client_id: str) -> tuple[bool, dict]:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: IP address or API key
        
        Returns:
            (allowed, headers) where headers contains rate limit info
        """
        now = time.time()
        
        # Check minute window
        minute_key = f"rate_limit:min:{client_id}"
        minute_count = self._get_window_count(minute_key, 60)
        
        # Check hour window
        hour_key = f"rate_limit:hour:{client_id}"
        hour_count = self._get_window_count(hour_key, 3600)
        
        # Determine if allowed
        allowed = (
            minute_count < self.config.requests_per_minute and
            hour_count < self.config.requests_per_hour
        )
        
        # Increment counters
        if allowed:
            self._increment_counter(minute_key, 60)
            self._increment_counter(hour_key, 3600)
        
        # Build headers
        headers = {
            "X-RateLimit-Limit-Minute": str(self.config.requests_per_minute),
            "X-RateLimit-Remaining-Minute": str(
                max(0, self.config.requests_per_minute - minute_count - (1 if allowed else 0))
            ),
            "X-RateLimit-Limit-Hour": str(self.config.requests_per_hour),
            "X-RateLimit-Remaining-Hour": str(
                max(0, self.config.requests_per_hour - hour_count - (1 if allowed else 0))
            ),
        }
        
        if not allowed:
            retry_after = self._calculate_retry_after(minute_key, hour_key)
            headers["Retry-After"] = str(retry_after)
        
        return allowed, headers
    
    def _get_window_count(self, key: str, window: int) -> int:
        """Get request count for time window."""
        try:
            # Remove old entries
            cutoff = time.time() - window
            self.redis.zremrangebyscore(key, 0, cutoff)
            
            # Count remaining
            return self.redis.zcard(key)
        except Exception as e:
            logger.error(f"Redis error: {e}")
            return 0
    
    def _increment_counter(self, key: str, window: int):
        """Increment request counter."""
        try:
            now = time.time()
            self.redis.zadd(key, {str(now): now})
            self.redis.expire(key, window)
        except Exception as e:
            logger.error(f"Redis error: {e}")
    
    def _calculate_retry_after(self, minute_key: str, hour_key: str) -> int:
        """Calculate seconds until next allowed request."""
        try:
            # Get oldest request in minute window
            oldest_minute = self.redis.zrange(minute_key, 0, 0, withscores=True)
            
            if oldest_minute:
                oldest_time = oldest_minute[0][1]
                retry_after = int(60 - (time.time() - oldest_time))
                return max(1, retry_after)
            
            return 60
        except Exception:
            return 60
    
    def get_client_stats(self, client_id: str) -> dict:
        """Get rate limit stats for client."""
        minute_key = f"rate_limit:min:{client_id}"
        hour_key = f"rate_limit:hour:{client_id}"
        
        return {
            "client_id": client_id,
            "requests_last_minute": self._get_window_count(minute_key, 60),
            "requests_last_hour": self._get_window_count(hour_key, 3600),
            "limit_per_minute": self.config.requests_per_minute,
            "limit_per_hour": self.config.requests_per_hour,
        }


class RateLimitMiddleware:
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app):
        self.app = app
        self.limiter = APIRateLimiter()
    
    async def __call__(self, scope, receive, send):
        """Process request with rate limiting."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Get client IP
        client_id = self._get_client_id(scope)
        
        # Check rate limit
        allowed, headers = self.limiter.is_allowed(client_id)
        
        if not allowed:
            # Return 429 Too Many Requests
            await send({
                "type": "http.response.start",
                "status": 429,
                "headers": [
                    (b"content-type", b"application/json"),
                    *[(k.encode(), v.encode()) for k, v in headers.items()],
                ],
            })
            await send({
                "type": "http.response.body",
                "body": b'{"error": "Rate limit exceeded"}',
            })
            return
        
        # Add rate limit headers to response
        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers_list = list(message.get("headers", []))
                for key, value in headers.items():
                    headers_list.append((key.encode(), value.encode()))
                message["headers"] = headers_list
            await send(message)
        
        await self.app(scope, receive, send_with_headers)
    
    def _get_client_id(self, scope) -> str:
        """Extract client ID from request."""
        # Try X-Forwarded-For first
        headers = dict(scope.get("headers", []))
        
        forwarded = headers.get(b"x-forwarded-for")
        if forwarded:
            return forwarded.decode().split(",")[0].strip()
        
        # Fall back to direct connection
        client = scope.get("client")
        if client:
            return client[0]
        
        return "unknown"


# Global instance
_api_rate_limiter: Optional[APIRateLimiter] = None


def get_api_rate_limiter() -> APIRateLimiter:
    """Get or create API rate limiter."""
    global _api_rate_limiter
    
    if _api_rate_limiter is None:
        _api_rate_limiter = APIRateLimiter()
    
    return _api_rate_limiter
