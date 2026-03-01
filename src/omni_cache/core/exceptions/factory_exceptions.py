"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Factory exceptions
class FactoryError(OmniCacheError):
    """Base class for factory-related errors."""


class FactoryNotFoundError(FactoryError):
    """Raised when a factory for a backend is not found."""

    def __init__(self, backend: str, available_backends: list[str] | None = None) -> None:
        details: dict[str, Any] = {"backend": backend}
        if available_backends is not None:
            details["available_backends"] = available_backends

        message = f"No factory found for backend '{backend}'"
        if available_backends is not None:
            message += f". Available backends: {', '.join(available_backends)}"

        super().__init__(message, details)


class FactoryRegistrationError(FactoryError):
    """Raised when factory registration fails."""

    def __init__(self, backend: str, reason: str, cause: Exception | None = None) -> None:
        details: dict[str, Any] = {"backend": backend, "reason": reason}
        message = f"Failed to register factory for backend '{backend}': {reason}"
        super().__init__(message, details, cause)


class FactoryCreationError(FactoryError):
    """Raised when factory fails to create an adapter."""

    def __init__(
        self, backend: str, adapter_config: dict[str, Any], cause: Exception | None = None
    ) -> None:
        details: dict[str, Any] = {"backend": backend, "adapter_config": adapter_config}
        message = f"Factory failed to create adapter for backend '{backend}'"
        super().__init__(message, details, cause)
