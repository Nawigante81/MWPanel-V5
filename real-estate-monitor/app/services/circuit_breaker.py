"""
Circuit breaker pattern implementation using Redis.
Prevents cascading failures by pausing requests to failing sources.
"""
from enum import Enum
from typing import Optional

import redis

from app.logging_config import get_logger
from app.settings import settings

logger = get_logger("circuit_breaker")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """
    Circuit breaker for source protection.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Source failing, requests blocked
    - HALF_OPEN: Testing if source recovered
    
    Configuration:
    - failure_threshold: Number of consecutive failures to open
    - recovery_timeout: Seconds before attempting recovery
    """
    
    def __init__(
        self,
        redis_client: redis.Redis,
        failure_threshold: int = None,
        recovery_timeout: int = None,
    ):
        self.redis = redis_client
        self.failure_threshold = failure_threshold or settings.circuit_breaker_failure_threshold
        self.recovery_timeout = recovery_timeout or settings.circuit_breaker_recovery_timeout
    
    def _state_key(self, source_name: str) -> str:
        """Redis key for circuit state."""
        return f"circuit:{source_name}:state"
    
    def _failures_key(self, source_name: str) -> str:
        """Redis key for failure count."""
        return f"circuit:{source_name}:failures"
    
    def _last_failure_key(self, source_name: str) -> str:
        """Redis key for last failure timestamp."""
        return f"circuit:{source_name}:last_failure"
    
    def get_state(self, source_name: str) -> CircuitState:
        """Get current circuit state for a source."""
        state_key = self._state_key(source_name)
        state = self.redis.get(state_key)
        
        if state is None:
            return CircuitState.CLOSED
        
        return CircuitState(state)
    
    def can_execute(self, source_name: str) -> bool:
        """
        Check if request can be executed.
        
        Returns True if circuit is CLOSED or HALF_OPEN.
        """
        state = self.get_state(source_name)
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure_key = self._last_failure_key(source_name)
            last_failure = self.redis.get(last_failure_key)
            
            if last_failure:
                import time
                elapsed = time.time() - float(last_failure)
                
                if elapsed >= self.recovery_timeout:
                    # Transition to half-open
                    self._set_state(source_name, CircuitState.HALF_OPEN)
                    logger.info(
                        "Circuit breaker entering half-open state",
                        extra={"source": source_name},
                    )
                    return True
            
            logger.warning(
                "Circuit breaker open, request blocked",
                extra={"source": source_name},
            )
            return False
        
        if state == CircuitState.HALF_OPEN:
            # Allow one test request
            return True
        
        return True
    
    def record_success(self, source_name: str) -> None:
        """Record a successful request."""
        state = self.get_state(source_name)
        
        if state == CircuitState.HALF_OPEN:
            # Recovery successful, close circuit
            self._set_state(source_name, CircuitState.CLOSED)
            self._reset_failures(source_name)
            logger.info(
                "Circuit breaker closed after recovery",
                extra={"source": source_name},
            )
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self._reset_failures(source_name)
    
    def record_failure(self, source_name: str) -> None:
        """Record a failed request."""
        state = self.get_state(source_name)
        
        if state == CircuitState.HALF_OPEN:
            # Recovery failed, re-open circuit
            self._set_state(source_name, CircuitState.OPEN)
            self._update_last_failure(source_name)
            logger.warning(
                "Circuit breaker re-opened after failed recovery",
                extra={"source": source_name},
            )
        elif state == CircuitState.CLOSED:
            # Increment failure count
            failures = self._increment_failures(source_name)
            
            if failures >= self.failure_threshold:
                # Open circuit
                self._set_state(source_name, CircuitState.OPEN)
                self._update_last_failure(source_name)
                logger.error(
                    "Circuit breaker opened due to failures",
                    extra={
                        "source": source_name,
                        "failures": failures,
                        "threshold": self.failure_threshold,
                    },
                )
    
    def _set_state(self, source_name: str, state: CircuitState) -> None:
        """Set circuit state with TTL."""
        state_key = self._state_key(source_name)
        # State TTL = recovery timeout * 2 (generous)
        ttl = self.recovery_timeout * 2
        self.redis.setex(state_key, ttl, state.value)
    
    def _increment_failures(self, source_name: str) -> int:
        """Increment and return failure count."""
        failures_key = self._failures_key(source_name)
        failures = self.redis.incr(failures_key)
        
        # Set TTL on first increment
        if failures == 1:
            self.redis.expire(failures_key, self.recovery_timeout * 2)
        
        return int(failures)
    
    def _reset_failures(self, source_name: str) -> None:
        """Reset failure count."""
        failures_key = self._failures_key(source_name)
        self.redis.delete(failures_key)
    
    def _update_last_failure(self, source_name: str) -> None:
        """Update last failure timestamp."""
        import time
        last_failure_key = self._last_failure_key(source_name)
        self.redis.setex(
            last_failure_key,
            self.recovery_timeout * 2,
            str(time.time()),
        )
    
    def get_status(self, source_name: str) -> dict:
        """Get detailed circuit breaker status."""
        state = self.get_state(source_name)
        failures_key = self._failures_key(source_name)
        failures = int(self.redis.get(failures_key) or 0)
        
        return {
            "source": source_name,
            "state": state.value,
            "failures": failures,
            "threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }
    
    def manual_reset(self, source_name: str) -> None:
        """Manually reset circuit breaker (for admin use)."""
        self._set_state(source_name, CircuitState.CLOSED)
        self._reset_failures(source_name)
        
        last_failure_key = self._last_failure_key(source_name)
        self.redis.delete(last_failure_key)
        
        logger.info(
            "Circuit breaker manually reset",
            extra={"source": source_name},
        )


# Global instance
_circuit_breaker: Optional[CircuitBreaker] = None


def get_circuit_breaker() -> CircuitBreaker:
    """Get or create circuit breaker instance."""
    global _circuit_breaker
    
    if _circuit_breaker is None:
        from app.services.rate_limit import get_redis_client
        _circuit_breaker = CircuitBreaker(get_redis_client())
    
    return _circuit_breaker
