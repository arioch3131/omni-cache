"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Pool-specific exceptions
class PoolError(OmniCacheError):
    """Base class for pool-specific errors."""


class PoolEmptyError(PoolError):
    """Raised when attempting to get from an empty pool."""

    def __init__(self, pool_name: str | None = None, timeout: float | None = None) -> None:
        details: dict[str, Any] = {}
        if pool_name:
            details["pool_name"] = pool_name
        if timeout is not None:
            details["timeout"] = timeout

        message = "Pool is empty"
        if pool_name:
            message = f"Pool '{pool_name}' is empty"
        if timeout is not None:
            message += f" (waited {timeout}s)"

        super().__init__(message, details)


class PoolFullError(PoolError):
    """Raised when attempting to put into a full pool."""

    def __init__(
        self,
        pool_name: str | None = None,
        max_size: int | None = None,
        timeout: float | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if pool_name:
            details["pool_name"] = pool_name
        if max_size is not None:
            details["max_size"] = max_size
        if timeout is not None:
            details["timeout"] = timeout

        message = "Pool is full"
        if pool_name:
            message = f"Pool '{pool_name}' is full"
        if max_size is not None:
            message += f" (max size: {max_size})"
        if timeout is not None:
            message += f" (waited {timeout}s)"

        super().__init__(message, details)


class PoolObjectError(PoolError):
    """Raised when pool object validation fails."""

    def __init__(self, reason: str, object_type: str | None = None) -> None:
        details: dict[str, Any] = {"reason": reason}
        if object_type:
            details["object_type"] = object_type

        message = f"Pool object error: {reason}"
        if object_type:
            message += f" (object type: {object_type})"

        super().__init__(message, details)
