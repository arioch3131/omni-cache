"""
Exception classes for omni-cache.

Base exception for all omni-cache related errors.
"""

import time
from typing import Any


class OmniCacheError(Exception):
    """
    Base exception for all omni-cache related errors.

    All exceptions in the omni-cache system inherit from this base class,
    allowing for easy exception handling and categorization.
    """

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        """
        Initialize the exception.

        Args:
            message: Human-readable error message
            details: Additional context information
            cause: The underlying exception that caused this error
        """
        self.message = message
        self.details = details or {}
        self.cause = cause
        self.timestamp = time.time()

        # Build the full message
        full_message = message
        if details:
            detail_str = ", ".join(f"{k}={v}" for k, v in details.items())
            full_message = f"{message} ({detail_str})"

        if cause:
            full_message = f"{full_message} - Caused by: {cause}"

        super().__init__(full_message)

    def __repr__(self) -> str:
        """String representation of the exception."""
        return f"{self.__class__.__name__}(message='{self.message}', details={self.details})"
