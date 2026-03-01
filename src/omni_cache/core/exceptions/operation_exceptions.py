"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Operation-related exceptions
class OperationError(OmniCacheError):
    """Base class for operation-related errors."""


class OperationTimeoutError(OperationError):
    """Raised when operations timeout."""

    def __init__(
        self, operation: str, timeout: float, context: dict[str, Any] | None = None
    ) -> None:
        details = {"operation": operation, "timeout": timeout}
        if context:
            details.update(context)

        message = f"Operation '{operation}' timed out after {timeout}s"
        super().__init__(message, details)


class OperationNotSupportedError(OperationError):
    """Raised when an operation is not supported by an adapter."""

    def __init__(self, operation: str, adapter_type: str, reason: str | None = None) -> None:
        details = {"operation": operation, "adapter_type": adapter_type}
        if reason is not None:
            details["reason"] = reason

        message = f"Operation '{operation}' not supported by adapter type '{adapter_type}'"
        if reason is not None:
            message += f": {reason}"

        super().__init__(message, details)


class OperationFailedError(OperationError):
    """Raised when an operation fails unexpectedly."""

    def __init__(
        self,
        operation: str,
        reason: str | None = None,
        context: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        details = {"operation": operation}
        if reason:
            details["reason"] = reason
        if context:
            details.update(context)

        message = f"Operation '{operation}' failed"
        if reason:
            message += f": {reason}"

        super().__init__(message, details, cause)
