"""Circuit breaker implementation for external API calls.

This module provides circuit breaker functionality to protect against
cascading failures when external APIs are unavailable or slow.
"""
import functools
from typing import Any, Callable, Optional, TypeVar

import pybreaker

from src.config import settings
from src.logging_config import get_logger
from src.utils import ExternalServiceUnavailable

logger = get_logger(__name__)

# Type variable for generic function return type
T = TypeVar("T")

# Global circuit breaker instances for each adapter
_breakers = {}


def get_circuit_breaker(name: str) -> pybreaker.CircuitBreaker:
    """Get or create a circuit breaker instance for the given adapter."""
    if name not in _breakers:
        logger.info(
            "Creating circuit breaker '%s' (fail_max=%d, timeout=%ds)",
            name,
            settings.CIRCUIT_BREAKER_MAX_FAILURES,
            settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
        )
        
        def on_open(breaker, remaining):
            """Called when circuit breaker opens."""
            logger.warning(
                "Circuit breaker '%s' OPENED (failures=%d, will reset in %ds)",
                name,
                breaker.fail_counter,
                remaining,
            )
        
        def on_close(breaker):
            """Called when circuit breaker closes."""
            logger.info("Circuit breaker '%s' CLOSED (service recovered)", name)
        
        def on_half_open(breaker):
            """Called when circuit breaker enters half-open state."""
            logger.info("Circuit breaker '%s' HALF-OPEN (testing service)", name)
        
        # Create custom listener class
        class CustomListener(pybreaker.CircuitBreakerListener):
            def state_change(self, cb, old_state, new_state):
                if new_state.name == 'open':
                    on_open(cb, cb._reset_timeout)
                elif new_state.name == 'closed':
                    on_close(cb)
                elif new_state.name == 'half_open':
                    on_half_open(cb)
        
        _breakers[name] = pybreaker.CircuitBreaker(
            fail_max=settings.CIRCUIT_BREAKER_MAX_FAILURES,
            reset_timeout=settings.CIRCUIT_BREAKER_RESET_TIMEOUT,
            exclude=[KeyboardInterrupt, SystemExit],
            listeners=[CustomListener()],
            name=name,
        )
    
    return _breakers[name]


def with_circuit_breaker(
    name: str,
    fallback_value: Optional[Any] = None,
    use_cache: bool = False,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to wrap functions with a circuit breaker.
    
    Args:
        name: Name of the circuit breaker (e.g., "theodds_api")
        fallback_value: Value to return if circuit is open (if None, raises exception)
        use_cache: Whether to attempt cache fallback (requires cache_key param in function)
    
    Returns:
        Decorated function that uses circuit breaker
    
    Raises:
        ExternalServiceUnavailable: When circuit is open and no fallback is available
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = get_circuit_breaker(name)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return breaker.call(func, *args, **kwargs)
            except pybreaker.CircuitBreakerError as e:
                logger.warning(
                    "Circuit breaker '%s' is OPEN, external service unavailable",
                    name,
                )
                
                # Try cache fallback if enabled
                if use_cache:
                    try:
                        from src.cache import get_cached_odds
                        
                        cache_key = kwargs.get("cache_key") or (args[0] if args else None)
                        if cache_key:
                            cached_data = get_cached_odds(cache_key)
                            if cached_data:
                                logger.info(
                                    "Circuit breaker '%s': Using cached data for key '%s'",
                                    name,
                                    cache_key,
                                )
                                return cached_data
                    except Exception as cache_err:
                        logger.debug(
                            "Cache fallback failed for '%s': %s",
                            name,
                            str(cache_err),
                        )
                
                # Use fallback value if provided
                if fallback_value is not None:
                    logger.info(
                        "Circuit breaker '%s': Using fallback value",
                        name,
                    )
                    return fallback_value
                
                # No fallback available, raise exception
                raise ExternalServiceUnavailable(
                    f"External service '{name}' is currently unavailable (circuit breaker open)"
                ) from e
        
        return wrapper
    
    return decorator


def reset_circuit_breaker(name: str) -> None:
    """Manually reset a circuit breaker (for testing or admin purposes)."""
    if name in _breakers:
        _breakers[name].close()
        logger.info("Circuit breaker '%s' manually reset", name)


def get_circuit_breaker_status(name: Optional[str] = None) -> dict:
    """Get status of circuit breakers.
    
    Args:
        name: Specific breaker name, or None for all breakers
    
    Returns:
        Dictionary with breaker status information
    """
    if name:
        if name not in _breakers:
            return {"name": name, "status": "not_initialized"}
        
        breaker = _breakers[name]
        return {
            "name": name,
            "status": breaker.current_state,
            "fail_counter": breaker.fail_counter,
            "fail_max": breaker.fail_max,
            "reset_timeout": breaker._reset_timeout,
        }
    
    # Return status for all breakers
    return {
        name: {
            "status": breaker.current_state,
            "fail_counter": breaker.fail_counter,
            "fail_max": breaker.fail_max,
        }
        for name, breaker in _breakers.items()
    }
