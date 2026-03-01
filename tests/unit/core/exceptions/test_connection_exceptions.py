"""
Unit tests for connection-related exception classes.
"""

import pytest

from omni_cache.core.exceptions.connection_exceptions import (
    ConnectionFailedError,
    ConnectionTimeoutError,
    OmniConnectionError,
)
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestOmniConnectionError:
    """Test cases for OmniConnectionError base class."""

    def test_inheritance(self):
        """Test that OmniConnectionError inherits from OmniCacheError."""
        error = OmniConnectionError("Test connection error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, OmniConnectionError)

    def test_basic_initialization(self):
        """Test basic initialization of OmniConnectionError."""
        message = "Connection error occurred"
        error = OmniConnectionError(message)
        assert error.message == message


class TestConnectionTimeoutError:
    """Test cases for ConnectionTimeoutError."""

    def test_basic_initialization(self):
        """Test basic initialization without target."""
        timeout = 5.0
        operation = "connect"
        error = ConnectionTimeoutError(operation, timeout)

        expected_message = f"Connection timeout after {timeout}s during {operation}"
        assert error.message == expected_message
        assert error.details["timeout"] == timeout
        assert error.details["operation"] == operation
        assert "target" not in error.details

    def test_initialization_with_target(self):
        """Test initialization with target specification."""
        timeout = 10.5
        operation = "handshake"
        target = "redis://localhost:6379"
        error = ConnectionTimeoutError(operation, timeout, target)

        expected_message = f"Connection timeout after {timeout}s during {operation} to {target}"
        assert error.message == expected_message
        assert error.details["timeout"] == timeout
        assert error.details["operation"] == operation
        assert error.details["target"] == target

    def test_zero_timeout(self):
        """Test with zero timeout value."""
        timeout = 0.0
        operation = "instant_fail"
        error = ConnectionTimeoutError(operation, timeout)

        expected_message = f"Connection timeout after {timeout}s during {operation}"
        assert error.message == expected_message
        assert error.details["timeout"] == 0.0

    def test_negative_timeout(self):
        """Test with negative timeout value."""
        timeout = -1.0
        operation = "invalid_timeout"
        error = ConnectionTimeoutError(operation, timeout)

        expected_message = f"Connection timeout after {timeout}s during {operation}"
        assert error.message == expected_message
        assert error.details["timeout"] == -1.0

    def test_float_timeout_precision(self):
        """Test with precise float timeout values."""
        timeout = 3.14159
        operation = "precise_timeout"
        error = ConnectionTimeoutError(operation, timeout)

        assert error.details["timeout"] == 3.14159
        assert "3.14159" in error.message

    def test_empty_operation(self):
        """Test with empty operation string."""
        timeout = 5.0
        operation = ""
        error = ConnectionTimeoutError(operation, timeout)

        expected_message = f"Connection timeout after {timeout}s during "
        assert error.message == expected_message
        assert error.details["operation"] == ""

    def test_empty_target(self):
        """Test with empty target string."""
        timeout = 2.0
        operation = "connect"
        target = ""
        error = ConnectionTimeoutError(operation, timeout, target)

        expected_message = f"Connection timeout after {timeout}s during {operation} to "
        assert error.message == expected_message
        assert error.details["target"] == ""

    def test_none_target(self):
        """Test with explicit None target."""
        timeout = 3.0
        operation = "test"
        error = ConnectionTimeoutError(operation, timeout, None)

        expected_message = f"Connection timeout after {timeout}s during {operation}"
        assert error.message == expected_message
        assert "target" not in error.details

    def test_complex_target_formats(self):
        """Test with various target format strings."""
        test_targets = [
            "localhost:6379",
            "redis://user:pass@host:port/db",
            "postgresql://localhost/mydb",
            "mongodb://cluster.example.com:27017",
            "file:///path/to/socket",
        ]

        timeout = 5.0
        operation = "connect"

        for target in test_targets:
            error = ConnectionTimeoutError(operation, timeout, target)
            assert error.details["target"] == target
            assert target in error.message


class TestConnectionFailedError:
    """Test cases for ConnectionFailedError."""

    def test_basic_initialization(self):
        """Test basic initialization without reason or cause."""
        target = "redis://localhost:6379"
        error = ConnectionFailedError(target)

        expected_message = f"Failed to connect to {target}"
        assert error.message == expected_message
        assert error.details["target"] == target
        assert "reason" not in error.details
        assert error.cause is None

    def test_initialization_with_reason(self):
        """Test initialization with failure reason."""
        target = "postgresql://localhost/mydb"
        reason = "Authentication failed"
        error = ConnectionFailedError(target, reason)

        expected_message = f"Failed to connect to {target}: {reason}"
        assert error.message == expected_message
        assert error.details["target"] == target
        assert error.details["reason"] == reason
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        target = "memcached://localhost:11211"
        cause = OSError("Connection refused")
        error = ConnectionFailedError(target, cause=cause)

        expected_message = f"Failed to connect to {target}"
        assert error.message == expected_message
        assert error.details["target"] == target
        assert "reason" not in error.details
        assert error.cause == cause

    def test_initialization_with_reason_and_cause(self):
        """Test initialization with both reason and cause."""
        target = "mysql://localhost:3306/db"
        reason = "Network unreachable"
        cause = TimeoutError("Connection timed out")
        error = ConnectionFailedError(target, reason, cause)

        expected_message = f"Failed to connect to {target}: {reason}"
        assert error.message == expected_message
        assert error.details["target"] == target
        assert error.details["reason"] == reason
        assert error.cause == cause

    def test_empty_target(self):
        """Test with empty target string."""
        target = ""
        error = ConnectionFailedError(target)

        expected_message = "Failed to connect to "
        assert error.message == expected_message
        assert error.details["target"] == ""

    def test_empty_reason(self):
        """Test with empty reason string."""
        target = "localhost:8080"
        reason = ""
        error = ConnectionFailedError(target, reason)

        expected_message = f"Failed to connect to {target}: "
        assert error.message == expected_message
        assert error.details["reason"] == ""

    def test_none_reason(self):
        """Test with explicit None reason."""
        target = "localhost:5432"
        error = ConnectionFailedError(target, None)

        expected_message = f"Failed to connect to {target}"
        assert error.message == expected_message
        assert "reason" not in error.details

    def test_none_cause(self):
        """Test with explicit None cause."""
        target = "localhost:27017"
        error = ConnectionFailedError(target, cause=None)

        expected_message = f"Failed to connect to {target}"
        assert error.message == expected_message
        assert error.cause is None

    def test_cause_chain_preservation(self):
        """Test that exception cause chain is preserved."""
        original_error = ValueError("Invalid address")
        intermediate_error = RuntimeError("DNS resolution failed")
        intermediate_error.__cause__ = original_error

        target = "invalid.host.com:80"
        error = ConnectionFailedError(target, cause=intermediate_error)

        assert error.cause == intermediate_error
        assert hasattr(intermediate_error, "__cause__")
        assert intermediate_error.__cause__ == original_error

    def test_various_target_formats(self):
        """Test with various target format styles."""
        test_cases = [
            "simple.host.com",
            "host:8080",
            "https://api.example.com",
            "tcp://messaging.service:9092",
            "unix:///var/run/socket",
            "127.0.0.1:3000",
            "[::1]:8080",  # IPv6
            "localhost",
        ]

        for target in test_cases:
            error = ConnectionFailedError(target)
            assert error.details["target"] == target
            assert target in error.message

    def test_unicode_in_target_and_reason(self):
        """Test with unicode characters in target and reason."""
        target = "hôst.exämple.com:pört"
        reason = "Connexion échouée avec caractères spéciaux"
        error = ConnectionFailedError(target, reason)

        assert error.details["target"] == target
        assert error.details["reason"] == reason
        assert target in error.message
        assert reason in error.message


class TestConnectionExceptionsInheritance:
    """Test inheritance hierarchy of connection exceptions."""

    def test_all_inherit_from_connection_error(self):
        """Test that all connection exceptions inherit from OmniConnectionError."""
        exceptions = [
            ConnectionTimeoutError(5.0, "connect"),
            ConnectionFailedError("localhost"),
        ]

        for exception in exceptions:
            assert isinstance(exception, OmniConnectionError)
            assert isinstance(exception, OmniCacheError)

    def test_exception_hierarchy_chain(self):
        """Test the complete inheritance chain."""
        error = ConnectionTimeoutError(5.0, "test")

        # Test MRO (Method Resolution Order)
        mro = type(error).__mro__
        assert ConnectionTimeoutError in mro
        assert OmniConnectionError in mro
        assert OmniCacheError in mro
        assert Exception in mro
        assert BaseException in mro

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (ConnectionTimeoutError, (5.0, "operation")),
            (ConnectionFailedError, ("target",)),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all connection exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, OmniConnectionError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")

    def test_connection_exceptions_are_catchable_as_connection_error(self):
        """Test that specific connection exceptions can be caught as OmniConnectionError."""
        exceptions = [
            ConnectionTimeoutError(1.0, "test"),
            ConnectionFailedError("test_target"),
        ]

        for exception in exceptions:
            try:
                raise exception
            except OmniConnectionError as caught:
                assert caught is exception
            except Exception:
                pytest.fail("Exception should be catchable as OmniConnectionError")

    def test_connection_exceptions_details_structure(self):
        """Test that all connection exceptions have proper details structure."""
        timeout_error = ConnectionTimeoutError(5.0, "connect", "target")
        failed_error = ConnectionFailedError("target", "reason")

        # Test that all have required details
        assert isinstance(timeout_error.details, dict)
        assert isinstance(failed_error.details, dict)

        # Test specific details
        assert "timeout" in timeout_error.details
        assert "operation" in timeout_error.details
        assert "target" in timeout_error.details

        assert "target" in failed_error.details
        assert "reason" in failed_error.details

    def test_timeout_values_handling(self):
        """Test various timeout value types and edge cases."""
        timeout_values = [
            0.0,
            0.1,
            1.0,
            30.5,
            999999.99,
        ]

        for timeout in timeout_values:
            error = ConnectionTimeoutError("test", timeout)
            assert error.details["timeout"] == timeout
            assert str(timeout) in error.message

    def test_connection_error_message_patterns(self):
        """Test that error messages follow expected patterns."""
        timeout_error = ConnectionTimeoutError("connect", 5.0)
        failed_error = ConnectionFailedError("localhost")

        # Timeout error should mention "timeout" and duration
        assert "timeout" in timeout_error.message.lower()
        assert "5.0s" in timeout_error.message

        # Failed error should mention "failed to connect"
        assert "failed to connect" in failed_error.message.lower()
        assert "localhost" in failed_error.message
