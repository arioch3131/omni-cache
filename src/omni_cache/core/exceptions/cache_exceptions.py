"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

import time
from typing import Any

from .omni_cache_error import OmniCacheError


# Cache-specific exceptions
class CacheError(OmniCacheError):
    """Base class for cache-specific errors."""


class CacheKeyError(CacheError):
    """Raised when cache key operations fail."""

    def __init__(self, key: Any, operation: str, reason: str | None = None) -> None:
        details: dict[str, Any] = {"key": str(key), "operation": operation}
        if reason:
            details["reason"] = reason

        message = f"Cache key error during {operation} for key '{key}'"
        if reason:
            message += f": {reason}"

        super().__init__(message, details)


class CacheFullError(CacheError):
    """Raised when cache is full and cannot accept new items."""

    def __init__(
        self,
        max_size: int,
        current_size: int | None = None,
        eviction_policy: str | None = None,
    ) -> None:
        details: dict[str, Any] = {"max_size": max_size}
        if current_size is not None:
            details["current_size"] = current_size
        if eviction_policy:
            details["eviction_policy"] = eviction_policy

        message = f"Cache is full (max size: {max_size})"
        if eviction_policy:
            message += f" and eviction policy '{eviction_policy}' failed"

        super().__init__(message, details)


class CacheExpiredError(CacheError):
    """Raised when attempting to access expired cache items."""

    def __init__(self, key: Any, expired_at: float) -> None:
        details = {"key": str(key), "expired_at": expired_at, "current_time": time.time()}
        message = f"Cache item '{key}' has expired"
        super().__init__(message, details)
