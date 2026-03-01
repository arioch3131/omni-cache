"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .cache_exceptions import CacheFullError, CacheKeyError
from .config_exceptions import ConfigurationError, InvalidConfigurationError
from .connection_exceptions import (
    ConnectionFailedError,
    ConnectionTimeoutError,
)
from .factory_exceptions import FactoryNotFoundError
from .omni_cache_error import OmniCacheError
from .operation_exceptions import (
    OperationFailedError,
    OperationNotSupportedError,
    OperationTimeoutError,
)
from .pool_exceptions import PoolEmptyError


# Utility functions for exception handling
def handle_and_wrap_exception(
    operation: str, exc: Exception, context: dict[str, Any] | None = None
) -> OmniCacheError:
    """
    Wrap a generic exception in an appropriate OmniCacheError.

    Args:
        operation: The operation that was being performed
        exc: The original exception
        context: Additional context information

    Returns:
        Wrapped OmniCacheError
    """
    if isinstance(exc, OmniCacheError):
        return exc

    # Map common exception types to appropriate omni-cache exceptions
    if isinstance(exc, TimeoutError):
        return OperationTimeoutError(operation, timeout=0.0, context=context)
    if isinstance(exc, ConnectionError):
        return ConnectionFailedError("unknown", cause=exc)
    if isinstance(exc, KeyError):
        key = exc.args[0] if exc.args else "unknown"
        return CacheKeyError(key, operation, str(exc))
    if isinstance(exc, ValueError):
        return InvalidConfigurationError("unknown", exc.args[0] if exc.args else "unknown")
    return OperationFailedError(operation, str(exc), context, exc)


@contextmanager
def exception_context(operation: str, **context: Any) -> Iterator[None]:
    """
    Context manager for consistent exception handling.

    Args:
        operation: Description of the operation being performed
        **context: Additional context to include in exceptions
    """
    try:
        yield
    except OmniCacheError:
        # Re-raise omni-cache exceptions as-is
        raise
    except Exception as e:
        # Wrap other exceptions
        raise handle_and_wrap_exception(operation, e, context) from e


def is_retriable_error(exc: Exception) -> bool:
    """
    Determine if an exception represents a retriable error.

    Args:
        exc: Exception to check

    Returns:
        True if the error is retriable, False otherwise
    """
    # Network/connection errors are usually retriable
    if isinstance(exc, (ConnectionError, ConnectionTimeoutError, ConnectionFailedError)):
        return True

    # Timeout errors might be retriable
    if isinstance(exc, (OperationTimeoutError, ConnectionTimeoutError)):
        return True

    # Temporary resource exhaustion might be retriable
    if isinstance(exc, (PoolEmptyError, CacheFullError, CacheKeyError)):
        return True

    # Configuration and permanent errors are not retriable
    if isinstance(
        exc,
        (
            ConfigurationError,
            InvalidConfigurationError,
            OperationNotSupportedError,
            FactoryNotFoundError,
        ),
    ):
        return False

    # For generic exceptions, be conservative
    return False


def get_exception_summary(exc: Exception) -> dict[str, Any]:
    """
    Get a summary of an exception for logging/monitoring.

    Args:
        exc: Exception to summarize

    Returns:
        Dictionary with exception summary
    """
    summary = {
        "type": exc.__class__.__name__,
        "message": str(exc),
        "retriable": is_retriable_error(exc),
    }
    # pylint: disable=unnecessary-dunder-call
    if isinstance(exc, OmniCacheError):
        summary.update(
            {
                "details": exc.details,
                "timestamp": exc.timestamp,
                "cause": exc.cause.__repr__() if exc.cause else None,
            }
        )

    return summary
