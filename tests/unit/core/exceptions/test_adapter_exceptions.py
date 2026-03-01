"""
Unit tests for adapter-related exception classes.
"""

import pytest

from omni_cache.core.exceptions.adapter_exceptions import (
    AdapterConnectionError,
    AdapterError,
    AdapterNotConnectedError,
    AdapterNotFoundError,
    AdapterRegistrationError,
)
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestAdapterError:
    """Test cases for AdapterError base class."""

    def test_inheritance(self):
        """Test that AdapterError inherits from OmniCacheError."""
        error = AdapterError("Test adapter error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, AdapterError)

    def test_basic_initialization(self):
        """Test basic initialization of AdapterError."""
        message = "Adapter error occurred"
        error = AdapterError(message)
        assert error.message == message


class TestAdapterNotFoundError:
    """Test cases for AdapterNotFoundError."""

    def test_basic_initialization(self):
        """Test basic initialization with adapter name only."""
        adapter_name = "redis_adapter"
        error = AdapterNotFoundError(adapter_name)

        assert error.message == f"Adapter '{adapter_name}' not found"
        assert error.details["adapter_name"] == adapter_name
        assert "available_adapters" not in error.details

    def test_initialization_with_available_adapters(self):
        """Test initialization with available adapters list."""
        adapter_name = "missing_adapter"
        available = ["memory", "redis", "memcached"]
        error = AdapterNotFoundError(adapter_name, available)

        expected_message = (
            f"Adapter '{adapter_name}' not found. Available adapters: memory, redis, memcached"
        )
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["available_adapters"] == available

    def test_empty_available_adapters(self):
        """Test with empty available adapters list."""
        adapter_name = "test_adapter"
        error = AdapterNotFoundError(adapter_name, [])

        expected_message = f"Adapter '{adapter_name}' not found. Available adapters: "
        assert error.message == expected_message
        assert error.details["available_adapters"] == []

    def test_none_available_adapters(self):
        """Test with None available adapters."""
        adapter_name = "test_adapter"
        error = AdapterNotFoundError(adapter_name, None)

        assert error.message == f"Adapter '{adapter_name}' not found"
        assert "available_adapters" not in error.details


class TestAdapterRegistrationError:
    """Test cases for AdapterRegistrationError."""

    def test_basic_initialization(self):
        """Test basic initialization without cause."""
        adapter_name = "test_adapter"
        reason = "Invalid configuration"
        error = AdapterRegistrationError(adapter_name, reason)

        expected_message = f"Failed to register adapter '{adapter_name}': {reason}"
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["reason"] == reason
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        adapter_name = "redis_adapter"
        reason = "Connection failed"
        cause = ConnectionError("Network unreachable")
        error = AdapterRegistrationError(adapter_name, reason, cause)

        expected_message = f"Failed to register adapter '{adapter_name}': {reason}"
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["reason"] == reason
        assert error.cause == cause

    def test_empty_reason(self):
        """Test with empty reason string."""
        adapter_name = "test_adapter"
        reason = ""
        error = AdapterRegistrationError(adapter_name, reason)

        expected_message = f"Failed to register adapter '{adapter_name}': "
        assert error.message == expected_message
        assert error.details["reason"] == ""


class TestAdapterNotConnectedError:
    """Test cases for AdapterNotConnectedError."""

    def test_basic_initialization(self):
        """Test basic initialization without operation."""
        adapter_name = "redis_adapter"
        error = AdapterNotConnectedError(adapter_name)

        expected_message = f"Adapter '{adapter_name}' is not connected"
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert "operation" not in error.details

    def test_initialization_with_operation(self):
        """Test initialization with attempted operation."""
        adapter_name = "database_pool"
        operation = "get_connection"
        error = AdapterNotConnectedError(adapter_name, operation)

        expected_message = (
            f"Adapter '{adapter_name}' is not connected (attempted operation: {operation})"
        )
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["operation"] == operation

    def test_empty_operation(self):
        """Test with empty operation string."""
        adapter_name = "test_adapter"
        operation = ""
        error = AdapterNotConnectedError(adapter_name, operation)

        expected_message = f"Adapter '{adapter_name}' is not connected (attempted operation: )"
        assert error.message == expected_message
        assert error.details["operation"] == ""

    def test_none_operation(self):
        """Test with None operation."""
        adapter_name = "test_adapter"
        error = AdapterNotConnectedError(adapter_name, None)

        expected_message = f"Adapter '{adapter_name}' is not connected"
        assert error.message == expected_message
        assert "operation" not in error.details


class TestAdapterConnectionError:
    """Test cases for AdapterConnectionError."""

    def test_basic_initialization(self):
        """Test basic initialization without reason or cause."""
        adapter_name = "redis_adapter"
        backend = "redis"
        error = AdapterConnectionError(adapter_name, backend)

        expected_message = f"Failed to connect adapter '{adapter_name}' to backend '{backend}'"
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["backend"] == backend
        assert "reason" not in error.details
        assert error.cause is None

    def test_initialization_with_reason(self):
        """Test initialization with connection reason."""
        adapter_name = "database_adapter"
        backend = "postgresql"
        reason = "Invalid credentials"
        error = AdapterConnectionError(adapter_name, backend, reason)

        expected_message = (
            f"Failed to connect adapter '{adapter_name}' to backend '{backend}': {reason}"
        )
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["backend"] == backend
        assert error.details["reason"] == reason
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        adapter_name = "redis_adapter"
        backend = "redis"
        cause = TimeoutError("Connection timed out")
        error = AdapterConnectionError(adapter_name, backend, cause=cause)

        expected_message = f"Failed to connect adapter '{adapter_name}' to backend '{backend}'"
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["backend"] == backend
        assert error.cause == cause

    def test_initialization_with_reason_and_cause(self):
        """Test initialization with both reason and cause."""
        adapter_name = "memcached_adapter"
        backend = "memcached"
        reason = "Server unavailable"
        cause = OSError("Connection refused")
        error = AdapterConnectionError(adapter_name, backend, reason, cause)

        expected_message = (
            f"Failed to connect adapter '{adapter_name}' to backend '{backend}': {reason}"
        )
        assert error.message == expected_message
        assert error.details["adapter_name"] == adapter_name
        assert error.details["backend"] == backend
        assert error.details["reason"] == reason
        assert error.cause == cause

    def test_empty_strings(self):
        """Test with empty adapter name and backend."""
        error = AdapterConnectionError("", "")

        expected_message = "Failed to connect adapter '' to backend ''"
        assert error.message == expected_message
        assert error.details["adapter_name"] == ""
        assert error.details["backend"] == ""

    def test_none_reason(self):
        """Test with explicit None reason."""
        adapter_name = "test_adapter"
        backend = "test_backend"
        error = AdapterConnectionError(adapter_name, backend, None)

        expected_message = f"Failed to connect adapter '{adapter_name}' to backend '{backend}'"
        assert error.message == expected_message
        assert "reason" not in error.details


class TestAdapterExceptionsInheritance:
    """Test inheritance hierarchy of adapter exceptions."""

    def test_all_inherit_from_adapter_error(self):
        """Test that all adapter exceptions inherit from AdapterError."""
        exceptions = [
            AdapterNotFoundError("test"),
            AdapterRegistrationError("test", "reason"),
            AdapterNotConnectedError("test"),
            AdapterConnectionError("test", "backend"),
        ]

        for exception in exceptions:
            assert isinstance(exception, AdapterError)
            assert isinstance(exception, OmniCacheError)

    def test_exception_hierarchy_chain(self):
        """Test the complete inheritance chain."""
        error = AdapterNotFoundError("test")

        # Test MRO (Method Resolution Order)
        mro = type(error).__mro__
        assert AdapterNotFoundError in mro
        assert AdapterError in mro
        assert OmniCacheError in mro
        assert Exception in mro
        assert BaseException in mro

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (AdapterNotFoundError, ("adapter",)),
            (AdapterRegistrationError, ("adapter", "reason")),
            (AdapterNotConnectedError, ("adapter",)),
            (AdapterConnectionError, ("adapter", "backend")),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all adapter exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, AdapterError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")
