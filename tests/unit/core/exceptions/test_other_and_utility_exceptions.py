"""
Unit tests for other exceptions and exception utility functions.
"""

from unittest.mock import patch

import pytest

from omni_cache.core.exceptions.cache_exceptions import CacheFullError, CacheKeyError
from omni_cache.core.exceptions.config_exceptions import (
    ConfigurationError,
    InvalidConfigurationError,
)
from omni_cache.core.exceptions.connection_exceptions import (
    ConnectionFailedError,
    ConnectionTimeoutError,
)
from omni_cache.core.exceptions.exceptions import (
    exception_context,
    get_exception_summary,
    handle_and_wrap_exception,
    is_retriable_error,
)
from omni_cache.core.exceptions.factory_exceptions import FactoryNotFoundError
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError
from omni_cache.core.exceptions.operation_exceptions import (
    OperationFailedError,
    OperationNotSupportedError,
    OperationTimeoutError,
)
from omni_cache.core.exceptions.other_exceptions import (
    HealthCheckError,
    InvalidRouteError,
    RouteNotFoundError,
    RoutingError,
)
from omni_cache.core.exceptions.pool_exceptions import PoolEmptyError

# ============================================================================
# Other Exceptions Tests
# ============================================================================


class TestHealthCheckError:
    """Test cases for HealthCheckError."""

    def test_basic_initialization(self):
        """Test basic initialization without reason or cause."""
        component = "redis_adapter"
        check_type = "connectivity"
        error = HealthCheckError(component, check_type)

        expected_message = f"Health check failed for {component} ({check_type})"
        assert error.message == expected_message
        assert error.details["component"] == component
        assert error.details["check_type"] == check_type
        assert "reason" not in error.details
        assert error.cause is None

    def test_initialization_with_reason(self):
        """Test initialization with failure reason."""
        component = "database_pool"
        check_type = "connection_pool"
        reason = "All connections are busy"
        error = HealthCheckError(component, check_type, reason)

        expected_message = f"Health check failed for {component} ({check_type}): {reason}"
        assert error.message == expected_message
        assert error.details["reason"] == reason

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        component = "cache_server"
        check_type = "ping"
        cause = TimeoutError("Connection timeout")
        error = HealthCheckError(component, check_type, cause=cause)

        assert error.cause == cause

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        component = "message_queue"
        check_type = "queue_health"
        reason = "Queue is full"
        cause = RuntimeError("Queue overflow")
        error = HealthCheckError(component, check_type, reason, cause)

        expected_message = f"Health check failed for {component} ({check_type}): {reason}"
        assert error.message == expected_message
        assert error.details["component"] == component
        assert error.details["check_type"] == check_type
        assert error.details["reason"] == reason
        assert error.cause == cause

    def test_empty_strings(self):
        """Test with empty component and check_type."""
        error = HealthCheckError("", "")
        expected_message = "Health check failed for  ()"
        assert error.message == expected_message

    def test_none_reason_and_cause(self):
        """Test with explicit None reason and cause."""
        error = HealthCheckError("test", "check", None, None)
        assert "reason" not in error.details
        assert error.cause is None


class TestRoutingError:
    """Test cases for RoutingError base class."""

    def test_inheritance(self):
        """Test that RoutingError inherits from OmniCacheError."""
        error = RoutingError("Test routing error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, RoutingError)

    def test_basic_initialization(self):
        """Test basic initialization of RoutingError."""
        message = "Routing error occurred"
        error = RoutingError(message)
        assert error.message == message


class TestRouteNotFoundError:
    """Test cases for RouteNotFoundError."""

    def test_basic_initialization(self):
        """Test basic initialization without namespace or routes."""
        key = "user:123"
        error = RouteNotFoundError(key)

        expected_message = f"No route found for key '{key}'"
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert "namespace" not in error.details
        assert "available_routes" not in error.details

    def test_initialization_with_namespace(self):
        """Test initialization with namespace."""
        key = "session:abc123"
        namespace = "session"
        error = RouteNotFoundError(key, namespace)

        expected_message = "No route found for key 'session:abc123'"
        expected_str = (
            "No route found for key 'session:abc123' (key=session:abc123, namespace=session)"
        )
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["namespace"] == namespace
        assert str(error) == expected_str

    def test_initialization_with_available_routes(self):
        """Test initialization with available routes."""
        key = "unknown:key"
        available_routes = ["user", "session", "cache"]
        error = RouteNotFoundError(key, available_routes=available_routes)

        expected_message = f"No route found for key '{key}'"
        expected_str = (
            "No route found for key 'unknown:key' "
            "(key=unknown:key, available_routes=['user', 'session', 'cache'])"
        )
        assert error.message == expected_message
        assert error.details["available_routes"] == available_routes
        assert str(error) == expected_str

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        key = "temp:data"
        namespace = "temporary"
        available_routes = ["user", "session", "permanent"]
        error = RouteNotFoundError(key, namespace, available_routes)

        expected_message = f"No route found for key '{key}'"
        expected_str = (
            "No route found for key 'temp:data' "
            "(key=temp:data, namespace=temporary, "
            "available_routes=['user', 'session', 'permanent'])"
        )
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["namespace"] == namespace
        assert error.details["available_routes"] == available_routes
        assert str(error) == expected_str

    def test_complex_key_types(self):
        """Test with complex key types."""
        test_keys = [
            123,
            ("tuple", "key"),
            {"dict": "key"},
            [1, 2, 3],
        ]

        for key in test_keys:
            error = RouteNotFoundError(key)
            assert error.details["key"] == str(key)

    def test_empty_available_routes(self):
        """Test with empty available routes list."""
        error = RouteNotFoundError("key", available_routes=[])
        assert error.details["available_routes"] == []

    def test_none_values(self):
        """Test with None namespace and available routes."""
        error = RouteNotFoundError("key", None, None)
        assert "namespace" not in error.details
        assert "available_routes" not in error.details


class TestInvalidRouteError:
    """Test cases for InvalidRouteError."""

    def test_basic_initialization(self):
        """Test basic initialization."""
        route_pattern = "user:*:invalid"
        reason = "Pattern contains invalid characters"
        error = InvalidRouteError(route_pattern, reason)

        expected_message = f"Invalid routing rule '{route_pattern}': {reason}"
        assert error.message == expected_message
        assert error.details["route_pattern"] == route_pattern
        assert error.details["reason"] == reason

    def test_empty_strings(self):
        """Test with empty strings."""
        error = InvalidRouteError("", "")
        expected_message = "Invalid routing rule '': "
        assert error.message == expected_message

    def test_complex_patterns_and_reasons(self):
        """Test with complex route patterns and reasons."""
        test_cases = [
            ("**invalid**", "Double wildcards not supported"),
            ("user:{id}/profile", "Curly braces not allowed in patterns"),
            ("", "Empty pattern not allowed"),
            ("a" * 1000, "Pattern too long"),
        ]

        for pattern, reason in test_cases:
            error = InvalidRouteError(pattern, reason)
            assert error.details["route_pattern"] == pattern
            assert error.details["reason"] == reason


# ============================================================================
# Exception Utility Functions Tests
# ============================================================================


class TestHandleAndWrapException:
    """Test cases for handle_and_wrap_exception function."""

    def test_omni_cache_error_passthrough(self):
        """Test that OmniCacheError instances are returned as-is."""
        original_error = CacheKeyError("key", "get", "test reason")
        result = handle_and_wrap_exception("test_op", original_error)

        assert result is original_error
        assert isinstance(result, CacheKeyError)

    def test_timeout_error_wrapping(self):
        """Test that TimeoutError is wrapped as OperationTimeoutError."""
        original_error = TimeoutError("Operation timed out")
        result = handle_and_wrap_exception("cache_get", original_error)

        assert isinstance(result, OperationTimeoutError)
        assert result.details["operation"] == "cache_get"
        assert result.details["timeout"] == 0.0

    def test_connection_error_wrapping(self):
        """Test that ConnectionError is wrapped as ConnectionFailedError."""
        original_error = ConnectionError("Network unreachable")
        result = handle_and_wrap_exception("connect", original_error)

        assert isinstance(result, ConnectionFailedError)
        assert result.details["target"] == "unknown"
        assert result.cause == original_error

    def test_key_error_wrapping(self):
        """Test that KeyError is wrapped as CacheKeyError."""
        original_error = KeyError("missing_key")
        result = handle_and_wrap_exception("get_item", original_error)

        assert isinstance(result, CacheKeyError)
        assert result.details["key"] == "missing_key"
        assert result.details["operation"] == "get_item"

    def test_value_error_wrapping(self):
        """Test that ValueError is wrapped as InvalidConfigurationError."""
        original_error = ValueError("Invalid value")
        result = handle_and_wrap_exception("validate", original_error)

        assert isinstance(result, InvalidConfigurationError)
        assert result.details["config_key"] == "unknown"
        assert result.details["config_value"] == "Invalid value"

    def test_generic_exception_wrapping(self):
        """Test that generic exceptions are wrapped as OperationFailedError."""
        original_error = RuntimeError("Something went wrong")
        result = handle_and_wrap_exception("process", original_error)

        assert isinstance(result, OperationFailedError)
        assert result.details["operation"] == "process"
        assert result.details["reason"] == "Something went wrong"
        assert result.cause == original_error

    def test_with_context(self):
        """Test wrapping with additional context."""
        original_error = RuntimeError("Error with context")
        context = {"key": "value", "count": 42}
        result = handle_and_wrap_exception("test_op", original_error, context)

        assert isinstance(result, OperationFailedError)
        assert result.details["operation"] == "test_op"
        assert result.details["key"] == "value"
        assert result.details["count"] == 42

    def test_empty_key_error(self):
        """Test handling of KeyError with no arguments."""
        original_error = KeyError()
        result = handle_and_wrap_exception("test", original_error)

        assert isinstance(result, CacheKeyError)
        assert result.details["key"] == "unknown"


class TestExceptionContext:
    """Test cases for exception_context context manager."""

    def test_successful_operation(self):
        """Test that successful operations don't raise exceptions."""
        with exception_context("test_operation"):
            result = "success"

        assert result == "success"

    def test_omni_cache_error_reraise(self):
        """Test that OmniCacheError exceptions are re-raised as-is."""
        original_error = CacheKeyError("key", "get")

        with pytest.raises(CacheKeyError) as exc_info:
            with exception_context("test_op"):
                raise original_error

        assert exc_info.value is original_error

    def test_generic_exception_wrapping(self):
        """Test that generic exceptions are wrapped."""
        with pytest.raises(OperationFailedError) as exc_info:
            with exception_context("test_operation"):
                raise RuntimeError("Test error")

        wrapped_error = exc_info.value
        assert wrapped_error.details["operation"] == "test_operation"
        assert wrapped_error.details["reason"] == "Test error"


class TestIsRetriableError:
    """Test cases for is_retriable_error function."""

    def test_retriable_connection_errors(self):
        """Test that connection errors are considered retriable."""
        retriable_errors = [
            ConnectionError("Network error"),
            ConnectionTimeoutError(5.0, "connect"),
            ConnectionFailedError("host"),
        ]

        for error in retriable_errors:
            assert is_retriable_error(error) is True

    def test_retriable_timeout_errors(self):
        """Test that timeout errors are considered retriable."""
        retriable_errors = [
            OperationTimeoutError("op", 5.0),
            ConnectionTimeoutError(1.0, "test"),
        ]

        for error in retriable_errors:
            assert is_retriable_error(error) is True

    def test_retriable_resource_errors(self):
        """Test that resource exhaustion errors are considered retriable."""
        retriable_errors = [
            PoolEmptyError("pool"),
            CacheFullError(100),
        ]

        for error in retriable_errors:
            assert is_retriable_error(error) is True

    def test_non_retriable_config_errors(self):
        """Test that configuration errors are not retriable."""
        non_retriable_errors = [
            ConfigurationError("Invalid config"),
            InvalidConfigurationError("key", "value"),
            OperationNotSupportedError("op", "adapter"),
            FactoryNotFoundError("backend"),
        ]

        for error in non_retriable_errors:
            assert is_retriable_error(error) is False

    def test_generic_exceptions(self):
        """Test that generic exceptions are not retriable by default."""
        non_retriable_errors = [
            ValueError("Invalid value"),
            TypeError("Type error"),
            RuntimeError("Runtime error"),
        ]

        for error in non_retriable_errors:
            assert is_retriable_error(error) is False


class TestGetExceptionSummary:
    """Test cases for get_exception_summary function."""

    @patch("time.time")
    def test_omni_cache_error_summary(self, mock_time):
        """Test summary for OmniCacheError instances."""
        mock_time.return_value = 1000.0

        details = {"key": "value", "count": 42}
        cause = ValueError("Original error")
        error = CacheKeyError("test_key", "get", "reason")
        error.details.update(details)
        error.cause = cause

        summary = get_exception_summary(error)

        assert summary["type"] == "CacheKeyError"
        assert summary["message"] == str(error)
        assert summary["retriable"] is True  # Cache errors are retriable
        assert summary["details"] == error.details
        assert summary["timestamp"] == error.timestamp
        assert summary["cause"] == "ValueError('Original error')"

    def test_generic_exception_summary(self):
        """Test summary for generic exceptions."""
        error = RuntimeError("Test runtime error")
        summary = get_exception_summary(error)

        assert summary["type"] == "RuntimeError"
        assert summary["message"] == "Test runtime error"
        assert summary["retriable"] is False
        # Generic exceptions don't have omni-cache specific fields
        assert "details" not in summary
        assert "timestamp" not in summary
        assert "cause" not in summary

    def test_omni_cache_error_without_cause(self):
        """Test summary for OmniCacheError without cause."""
        error = OperationFailedError("test_op", "failed")
        summary = get_exception_summary(error)

        assert summary["cause"] is None

    def test_various_exception_types(self):
        """Test summary generation for various exception types."""
        exceptions = [
            (ValueError("test"), "ValueError", False),
            (ConnectionTimeoutError(5.0, "test"), "ConnectionTimeoutError", True),
            (ConfigurationError("test"), "ConfigurationError", False),
            (PoolEmptyError(), "PoolEmptyError", True),
        ]

        for exception, expected_type, expected_retriable in exceptions:
            summary = get_exception_summary(exception)
            assert summary["type"] == expected_type
            assert summary["retriable"] == expected_retriable


class TestOtherExceptionsInheritance:
    """Test inheritance hierarchy of other exceptions."""

    def test_routing_exceptions_inherit_from_routing_error(self):
        """Test that routing exceptions inherit from RoutingError."""
        exceptions = [
            RouteNotFoundError("key"),
            InvalidRouteError("pattern", "reason"),
        ]

        for exception in exceptions:
            assert isinstance(exception, RoutingError)
            assert isinstance(exception, OmniCacheError)

    def test_health_check_error_inheritance(self):
        """Test that HealthCheckError inherits from OmniCacheError."""
        error = HealthCheckError("component", "check")
        assert isinstance(error, OmniCacheError)

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (HealthCheckError, ("component", "check")),
            (RouteNotFoundError, ("key",)),
            (InvalidRouteError, ("pattern", "reason")),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all other exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, OmniCacheError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")

    def test_exception_categories_comprehensive_test(self):
        """Test that all exception utility functions work with all exception types."""
        all_exceptions = [
            # Health check
            HealthCheckError("comp", "check", "reason"),
            # Routing
            RouteNotFoundError("key", "namespace"),
            InvalidRouteError("pattern", "invalid"),
            # Generic for comparison
            ValueError("generic error"),
        ]

        for exception in all_exceptions:
            # Test that utility functions don't crash
            summary = get_exception_summary(exception)
            assert isinstance(summary, dict)
            assert "type" in summary
            assert "message" in summary
            assert "retriable" in summary

            # Test wrapping doesn't crash
            wrapped = handle_and_wrap_exception("test_op", exception)
            assert isinstance(wrapped, Exception)
