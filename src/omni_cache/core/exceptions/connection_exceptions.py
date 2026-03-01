"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from .omni_cache_error import OmniCacheError


# Connection-related exceptions
class OmniConnectionError(OmniCacheError):
    """Base class for connection-related errors."""


class ConnectionTimeoutError(OmniConnectionError):
    """Raised when connection operations timeout."""

    def __init__(self, operation: str, timeout: float, target: str | None = None) -> None:
        details = {"operation": operation, "timeout": timeout}
        if target is not None:
            details["target"] = target

        message = f"Connection timeout after {timeout}s during {operation}"
        if target is not None:
            message += f" to {target}"

        super().__init__(message, details)


class ConnectionFailedError(OmniConnectionError):
    """Raised when connection establishment fails."""

    def __init__(
        self, target: str, reason: str | None = None, cause: Exception | None = None
    ) -> None:
        details = {"target": target}
        if reason is not None:
            details["reason"] = reason

        message = f"Failed to connect to {target}"
        if reason is not None:
            message += f": {reason}"

        super().__init__(message, details, cause)
