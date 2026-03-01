"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Adapter-related exceptions
class AdapterError(OmniCacheError):
    """Base class for adapter-related errors."""


class AdapterNotFoundError(AdapterError):
    """Raised when a requested adapter is not found or registered."""

    def __init__(self, adapter_name: str, available_adapters: list[str] | None = None):
        details: dict[str, Any] = {"adapter_name": adapter_name}
        if available_adapters is not None:
            details["available_adapters"] = available_adapters

        message = f"Adapter '{adapter_name}' not found"
        if available_adapters is not None:
            message += f". Available adapters: {', '.join(available_adapters)}"

        super().__init__(message, details)


class AdapterRegistrationError(AdapterError):
    """Raised when adapter registration fails."""

    def __init__(self, adapter_name: str, reason: str, cause: Exception | None = None):
        details: dict[str, Any] = {"adapter_name": adapter_name, "reason": reason}
        message = f"Failed to register adapter '{adapter_name}': {reason}"
        super().__init__(message, details, cause)


class AdapterNotConnectedError(AdapterError):
    """Raised when attempting operations on a disconnected adapter."""

    def __init__(self, adapter_name: str, operation: str | None = None):
        details: dict[str, Any] = {"adapter_name": adapter_name}
        if operation is not None:
            details["operation"] = operation

        message = f"Adapter '{adapter_name}' is not connected"
        if operation is not None:
            message += f" (attempted operation: {operation})"

        super().__init__(message, details)


class AdapterConnectionError(AdapterError):
    """Raised when adapter connection fails."""

    def __init__(
        self,
        adapter_name: str,
        backend: str,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        details: dict[str, Any] = {"adapter_name": adapter_name, "backend": backend}
        if reason:
            details["reason"] = reason

        message = f"Failed to connect adapter '{adapter_name}' to backend '{backend}'"
        if reason:
            message += f": {reason}"

        super().__init__(message, details, cause)
