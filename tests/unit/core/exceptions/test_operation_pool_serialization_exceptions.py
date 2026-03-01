"""
Unit tests for operation, pool, and serialization exception classes.
"""

import pytest

from omni_cache.core.exceptions.omni_cache_error import OmniCacheError
from omni_cache.core.exceptions.operation_exceptions import (
    OperationError,
    OperationFailedError,
    OperationNotSupportedError,
    OperationTimeoutError,
)
from omni_cache.core.exceptions.pool_exceptions import (
    PoolEmptyError,
    PoolError,
    PoolFullError,
    PoolObjectError,
)
from omni_cache.core.exceptions.serialization_exceptions import (
    DeserializationFailedError,
    SerializationError,
    SerializationFailedError,
)

# ============================================================================
# Operation Exceptions Tests
# ============================================================================


class TestOperationError:
    """Test cases for OperationError base class."""

    def test_inheritance(self):
        """Test that OperationError inherits from OmniCacheError."""
        error = OperationError("Test operation error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, OperationError)


class TestOperationTimeoutError:
    """Test cases for OperationTimeoutError."""

    def test_basic_initialization(self):
        """Test basic initialization without context."""
        operation = "cache_get"
        timeout = 5.0
        error = OperationTimeoutError(operation, timeout)

        expected_message = f"Operation '{operation}' timed out after {timeout}s"
        assert error.message == expected_message
        assert error.details["operation"] == operation
        assert error.details["timeout"] == timeout

    def test_initialization_with_context(self):
        """Test initialization with context information."""
        operation = "database_query"
        timeout = 30.0
        context = {"query": "SELECT * FROM users", "connection_id": "conn_123"}
        error = OperationTimeoutError(operation, timeout, context)

        expected_message = f"Operation '{operation}' timed out after {timeout}s"
        assert error.message == expected_message
        assert error.details["operation"] == operation
        assert error.details["timeout"] == timeout
        assert error.details["query"] == "SELECT * FROM users"
        assert error.details["connection_id"] == "conn_123"

    def test_zero_timeout(self):
        """Test with zero timeout value."""
        error = OperationTimeoutError("instant_fail", 0.0)
        assert error.details["timeout"] == 0.0

    def test_float_timeout_precision(self):
        """Test with precise float timeout values."""
        timeout = 2.71828
        error = OperationTimeoutError("precise", timeout)
        assert error.details["timeout"] == timeout

    def test_empty_context(self):
        """Test with empty context dictionary."""
        error = OperationTimeoutError("test", 1.0, {})
        assert error.details["operation"] == "test"
        assert error.details["timeout"] == 1.0
        # Empty context should not add extra keys

    def test_none_context(self):
        """Test with None context."""
        error = OperationTimeoutError("test", 1.0, None)
        assert "operation" in error.details
        assert "timeout" in error.details


class TestOperationNotSupportedError:
    """Test cases for OperationNotSupportedError."""

    def test_basic_initialization(self):
        """Test basic initialization without reason."""
        operation = "bulk_delete"
        adapter_type = "memory_cache"
        error = OperationNotSupportedError(operation, adapter_type)

        expected_message = f"Operation '{operation}' not supported by adapter type '{adapter_type}'"
        assert error.message == expected_message
        assert error.details["operation"] == operation
        assert error.details["adapter_type"] == adapter_type
        assert "reason" not in error.details

    def test_initialization_with_reason(self):
        """Test initialization with specific reason."""
        operation = "atomic_transaction"
        adapter_type = "simple_cache"
        reason = "Transactions require ACID compliance"
        error = OperationNotSupportedError(operation, adapter_type, reason)

        expected_message = (
            f"Operation '{operation}' not supported by adapter type '{adapter_type}': {reason}"
        )
        assert error.message == expected_message
        assert error.details["reason"] == reason

    def test_empty_reason(self):
        """Test with empty reason string."""
        error = OperationNotSupportedError("test", "adapter", "")
        assert error.details["reason"] == ""

    def test_none_reason(self):
        """Test with None reason."""
        error = OperationNotSupportedError("test", "adapter", None)
        assert "reason" not in error.details


class TestOperationFailedError:
    """Test cases for OperationFailedError."""

    def test_basic_initialization(self):
        """Test basic initialization with operation only."""
        operation = "cache_flush"
        error = OperationFailedError(operation)

        expected_message = f"Operation '{operation}' failed"
        assert error.message == expected_message
        assert error.details["operation"] == operation
        assert "reason" not in error.details
        assert error.cause is None

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        operation = "connection_pool_acquire"
        reason = "Pool exhausted"
        context = {"pool_size": 10, "active_connections": 10}
        cause = TimeoutError("No connections available")
        error = OperationFailedError(operation, reason, context, cause)

        expected_message = f"Operation '{operation}' failed: {reason}"
        assert error.message == expected_message
        assert error.details["operation"] == operation
        assert error.details["reason"] == reason
        assert error.details["pool_size"] == 10
        assert error.details["active_connections"] == 10
        assert error.cause == cause


# ============================================================================
# Pool Exceptions Tests
# ============================================================================


class TestPoolError:
    """Test cases for PoolError base class."""

    def test_inheritance(self):
        """Test that PoolError inherits from OmniCacheError."""
        error = PoolError("Test pool error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, PoolError)


class TestPoolEmptyError:
    """Test cases for PoolEmptyError."""

    def test_basic_initialization(self):
        """Test basic initialization without parameters."""
        error = PoolEmptyError()

        expected_message = "Pool is empty"
        assert error.message == expected_message
        assert not error.details  # Should be empty

    def test_initialization_with_pool_name(self):
        """Test initialization with pool name."""
        pool_name = "database_connections"
        error = PoolEmptyError(pool_name)

        expected_message = f"Pool '{pool_name}' is empty"
        assert error.message == expected_message
        assert error.details["pool_name"] == pool_name

    def test_initialization_with_timeout(self):
        """Test initialization with timeout."""
        timeout = 5.0
        error = PoolEmptyError(timeout=timeout)

        expected_message = f"Pool is empty (waited {timeout}s)"
        assert error.message == expected_message
        assert error.details["timeout"] == timeout

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        pool_name = "worker_pool"
        timeout = 10.0
        error = PoolEmptyError(pool_name, timeout)

        expected_message = f"Pool '{pool_name}' is empty (waited {timeout}s)"
        assert error.message == expected_message
        assert error.details["pool_name"] == pool_name
        assert error.details["timeout"] == timeout

    def test_none_values(self):
        """Test with None values."""
        error = PoolEmptyError(None, None)
        expected_message = "Pool is empty"
        assert error.message == expected_message


class TestPoolFullError:
    """Test cases for PoolFullError."""

    def test_basic_initialization(self):
        """Test basic initialization without parameters."""
        error = PoolFullError()

        expected_message = "Pool is full"
        assert error.message == expected_message

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        pool_name = "connection_pool"
        max_size = 20
        timeout = 3.0
        error = PoolFullError(pool_name, max_size, timeout)

        expected_message = f"Pool '{pool_name}' is full (max size: {max_size}) (waited {timeout}s)"
        assert error.message == expected_message
        assert error.details["pool_name"] == pool_name
        assert error.details["max_size"] == max_size
        assert error.details["timeout"] == timeout

    def test_partial_initialization(self):
        """Test with some parameters."""
        max_size = 100
        error = PoolFullError(max_size=max_size)

        expected_message = f"Pool is full (max size: {max_size})"
        assert error.message == expected_message
        assert error.details["max_size"] == max_size


class TestPoolObjectError:
    """Test cases for PoolObjectError."""

    def test_basic_initialization(self):
        """Test basic initialization without object type."""
        reason = "Object validation failed"
        error = PoolObjectError(reason)

        expected_message = f"Pool object error: {reason}"
        assert error.message == expected_message
        assert error.details["reason"] == reason
        assert "object_type" not in error.details

    def test_initialization_with_object_type(self):
        """Test initialization with object type."""
        reason = "Connection is closed"
        object_type = "DatabaseConnection"
        error = PoolObjectError(reason, object_type)

        expected_message = f"Pool object error: {reason} (object type: {object_type})"
        assert error.message == expected_message
        assert error.details["reason"] == reason
        assert error.details["object_type"] == object_type

    def test_empty_reason(self):
        """Test with empty reason."""
        error = PoolObjectError("")
        expected_message = "Pool object error: "
        assert error.message == expected_message

    def test_none_object_type(self):
        """Test with None object type."""
        error = PoolObjectError("test", None)
        assert "object_type" not in error.details


# ============================================================================
# Serialization Exceptions Tests
# ============================================================================


class TestSerializationError:
    """Test cases for SerializationError base class."""

    def test_inheritance(self):
        """Test that SerializationError inherits from OmniCacheError."""
        error = SerializationError("Test serialization error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, SerializationError)


class TestSerializationFailedError:
    """Test cases for SerializationFailedError."""

    def test_basic_initialization(self):
        """Test basic initialization without cause."""
        object_type = "CustomObject"
        serializer = "json"
        error = SerializationFailedError(object_type, serializer)

        expected_message = (
            f"Failed to serialize object of type '{object_type}' using '{serializer}'"
        )
        assert error.message == expected_message
        assert error.details["object_type"] == object_type
        assert error.details["serializer"] == serializer
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        object_type = "ComplexObject"
        serializer = "pickle"
        cause = TypeError("Object is not serializable")
        error = SerializationFailedError(object_type, serializer, cause)

        expected_message = (
            f"Failed to serialize object of type '{object_type}' using '{serializer}'"
        )
        assert error.message == expected_message
        assert error.cause == cause

    def test_empty_strings(self):
        """Test with empty strings."""
        error = SerializationFailedError("", "")
        expected_message = "Failed to serialize object of type '' using ''"
        assert error.message == expected_message

    def test_none_cause(self):
        """Test with explicit None cause."""
        error = SerializationFailedError("Test", "json", None)
        assert error.cause is None


class TestDeserializationFailedError:
    """Test cases for DeserializationFailedError."""

    def test_basic_initialization(self):
        """Test basic initialization without cause."""
        data_type = "json_string"
        deserializer = "json"
        error = DeserializationFailedError(data_type, deserializer)

        expected_message = (
            f"Failed to deserialize data of type '{data_type}' using '{deserializer}'"
        )
        assert error.message == expected_message
        assert error.details["data_type"] == data_type
        assert error.details["deserializer"] == deserializer
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        data_type = "corrupted_pickle"
        deserializer = "pickle"
        cause = ValueError("Invalid pickle data")
        error = DeserializationFailedError(data_type, deserializer, cause)

        expected_message = (
            f"Failed to deserialize data of type '{data_type}' using '{deserializer}'"
        )
        assert error.message == expected_message
        assert error.cause == cause


# ============================================================================
# Inheritance and Cross-Category Tests
# ============================================================================


class TestExceptionHierarchies:
    """Test inheritance hierarchies across exception categories."""

    @pytest.mark.parametrize(
        "exception_class,base_class,args",
        [
            # Operation exceptions
            (OperationTimeoutError, OperationError, ("op", 1.0)),
            (OperationNotSupportedError, OperationError, ("op", "adapter")),
            (OperationFailedError, OperationError, ("op",)),
            # Pool exceptions
            (PoolEmptyError, PoolError, ()),
            (PoolFullError, PoolError, ()),
            (PoolObjectError, PoolError, ("reason",)),
            # Serialization exceptions
            (SerializationFailedError, SerializationError, ("type", "serializer")),
            (DeserializationFailedError, SerializationError, ("type", "deserializer")),
        ],
    )
    def test_inheritance_hierarchy(self, exception_class, base_class, args):
        """Test that exceptions inherit from their base classes correctly."""
        exception = exception_class(*args)
        assert isinstance(exception, base_class)
        assert isinstance(exception, OmniCacheError)

    def test_all_exceptions_have_required_attributes(self):
        """Test that all exceptions have required OmniCacheError attributes."""
        exceptions = [
            # Operation exceptions
            OperationTimeoutError("op", 1.0),
            OperationNotSupportedError("op", "adapter"),
            OperationFailedError("op"),
            # Pool exceptions
            PoolEmptyError(),
            PoolFullError(),
            PoolObjectError("reason"),
            # Serialization exceptions
            SerializationFailedError("type", "serializer"),
            DeserializationFailedError("type", "deserializer"),
        ]

        for exception in exceptions:
            assert hasattr(exception, "message")
            assert hasattr(exception, "details")
            assert hasattr(exception, "timestamp")
            assert hasattr(exception, "cause")
            assert isinstance(exception.details, dict)

    def test_exception_string_representations(self):
        """Test that all exceptions have proper string representations."""
        exceptions = [
            OperationTimeoutError("test_op", 5.0),
            PoolEmptyError("test_pool"),
            SerializationFailedError("TestClass", "json"),
        ]

        for exception in exceptions:
            str_repr = str(exception)
            assert isinstance(str_repr, str)
            assert len(str_repr) > 0
            # Should contain the main error information
            assert exception.message in str_repr

    def test_exception_categories_are_distinct(self):
        """Test that exceptions from different categories don't cross-inherit."""
        operation_error = OperationError("test")
        pool_error = PoolError("test")
        serialization_error = SerializationError("test")

        # Operation errors should not be pool or serialization errors
        assert not isinstance(operation_error, PoolError)
        assert not isinstance(operation_error, SerializationError)

        # Pool errors should not be operation or serialization errors
        assert not isinstance(pool_error, OperationError)
        assert not isinstance(pool_error, SerializationError)

        # Serialization errors should not be operation or pool errors
        assert not isinstance(serialization_error, OperationError)
        assert not isinstance(serialization_error, PoolError)

    def test_exception_details_types(self):
        """Test that exception details contain appropriate data types."""
        timeout_error = OperationTimeoutError("test", 5.5, {"key": "value"})
        assert isinstance(timeout_error.details["timeout"], float)
        assert isinstance(timeout_error.details["operation"], str)

        pool_error = PoolFullError("pool", 10, 2.0)
        if "max_size" in pool_error.details:
            assert isinstance(pool_error.details["max_size"], int)
        if "timeout" in pool_error.details:
            assert isinstance(pool_error.details["timeout"], float)

        serialization_error = SerializationFailedError("TestClass", "json")
        assert isinstance(serialization_error.details["object_type"], str)
        assert isinstance(serialization_error.details["serializer"], str)
