"""
Unit tests for cache-related exception classes.
"""

import time
from unittest.mock import patch

import pytest

from omni_cache.core.exceptions.cache_exceptions import (
    CacheError,
    CacheExpiredError,
    CacheFullError,
    CacheKeyError,
)
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestCacheError:
    """Test cases for CacheError base class."""

    def test_inheritance(self):
        """Test that CacheError inherits from OmniCacheError."""
        error = CacheError("Test cache error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, CacheError)

    def test_basic_initialization(self):
        """Test basic initialization of CacheError."""
        message = "Cache error occurred"
        error = CacheError(message)
        assert error.message == message


class TestCacheKeyError:
    """Test cases for CacheKeyError."""

    def test_basic_initialization(self):
        """Test basic initialization without reason."""
        key = "test_key"
        operation = "get"
        error = CacheKeyError(key, operation)

        expected_message = f"Cache key error during {operation} for key '{key}'"
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["operation"] == operation
        assert "reason" not in error.details

    def test_initialization_with_reason(self):
        """Test initialization with specific reason."""
        key = "user:123"
        operation = "set"
        reason = "Key already exists"
        error = CacheKeyError(key, operation, reason)

        expected_message = f"Cache key error during {operation} for key '{key}': {reason}"
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["operation"] == operation
        assert error.details["reason"] == reason

    def test_complex_key_types(self):
        """Test with complex key types that need string conversion."""
        test_cases = [
            (123, "123"),
            (("tuple", "key"), "('tuple', 'key')"),
            ({"dict": "key"}, "{'dict': 'key'}"),
            ([1, 2, 3], "[1, 2, 3]"),
        ]

        for key, expected_str in test_cases:
            error = CacheKeyError(key, "test_operation")
            assert error.details["key"] == expected_str

    def test_empty_operation(self):
        """Test with empty operation string."""
        key = "test_key"
        operation = ""
        error = CacheKeyError(key, operation)

        expected_message = f"Cache key error during  for key '{key}'"
        assert error.message == expected_message
        assert error.details["operation"] == ""

    def test_none_reason(self):
        """Test with explicit None reason."""
        key = "test_key"
        operation = "delete"
        error = CacheKeyError(key, operation, None)

        expected_message = f"Cache key error during {operation} for key '{key}'"
        assert error.message == expected_message
        assert "reason" not in error.details


class TestCacheFullError:
    """Test cases for CacheFullError."""

    def test_basic_initialization(self):
        """Test basic initialization with max_size only."""
        max_size = 1000
        error = CacheFullError(max_size)

        expected_message = f"Cache is full (max size: {max_size})"
        assert error.message == expected_message
        assert error.details["max_size"] == max_size
        assert "current_size" not in error.details
        assert "eviction_policy" not in error.details

    def test_initialization_with_current_size(self):
        """Test initialization with current size."""
        max_size = 500
        current_size = 500
        error = CacheFullError(max_size, current_size)

        expected_message = f"Cache is full (max size: {max_size})"
        assert error.message == expected_message
        assert error.details["max_size"] == max_size
        assert error.details["current_size"] == current_size
        assert "eviction_policy" not in error.details

    def test_initialization_with_eviction_policy(self):
        """Test initialization with eviction policy."""
        max_size = 100
        eviction_policy = "lru"
        error = CacheFullError(max_size, eviction_policy=eviction_policy)

        expected_message = (
            f"Cache is full (max size: {max_size}) and eviction policy '{eviction_policy}' failed"
        )
        assert error.message == expected_message
        assert error.details["max_size"] == max_size
        assert error.details["eviction_policy"] == eviction_policy
        assert "current_size" not in error.details

    def test_initialization_with_all_parameters(self):
        """Test initialization with all parameters."""
        max_size = 1000
        current_size = 1000
        eviction_policy = "fifo"
        error = CacheFullError(max_size, current_size, eviction_policy)

        expected_message = (
            f"Cache is full (max size: {max_size}) and eviction policy '{eviction_policy}' failed"
        )
        assert error.message == expected_message
        assert error.details["max_size"] == max_size
        assert error.details["current_size"] == current_size
        assert error.details["eviction_policy"] == eviction_policy

    def test_none_current_size(self):
        """Test with explicit None current_size."""
        max_size = 100
        error = CacheFullError(max_size, None)

        expected_message = f"Cache is full (max size: {max_size})"
        assert error.message == expected_message
        assert "current_size" not in error.details

    def test_zero_max_size(self):
        """Test with zero max_size."""
        max_size = 0
        error = CacheFullError(max_size)

        expected_message = f"Cache is full (max size: {max_size})"
        assert error.message == expected_message
        assert error.details["max_size"] == 0

    def test_negative_sizes(self):
        """Test with negative sizes."""
        max_size = -1
        current_size = -5
        error = CacheFullError(max_size, current_size)

        assert error.details["max_size"] == -1
        assert error.details["current_size"] == -5


class TestCacheExpiredError:
    """Test cases for CacheExpiredError."""

    @patch("time.time")
    def test_basic_initialization(self, mock_time):
        """Test basic initialization with mocked time."""
        mock_current_time = 1000.0
        mock_time.return_value = mock_current_time

        key = "expired_key"
        expired_at = 999.0
        error = CacheExpiredError(key, expired_at)

        expected_message = f"Cache item '{key}' has expired"
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["expired_at"] == expired_at
        assert error.details["current_time"] == mock_current_time

    def test_real_time_initialization(self):
        """Test initialization with real time values."""
        key = "test_key"
        expired_at = time.time() - 100  # Expired 100 seconds ago
        error = CacheExpiredError(key, expired_at)

        expected_message = f"Cache item '{key}' has expired"
        assert error.message == expected_message
        assert error.details["key"] == str(key)
        assert error.details["expired_at"] == expired_at
        assert "current_time" in error.details
        assert error.details["current_time"] > expired_at

    def test_complex_key_types(self):
        """Test with complex key types."""
        test_cases = [42, ("composite", "key"), {"type": "dict"}, [1, 2, 3]]

        expired_at = time.time() - 10
        for key in test_cases:
            error = CacheExpiredError(key, expired_at)
            assert error.details["key"] == str(key)

    def test_future_expiration_time(self):
        """Test with expiration time in the future (edge case)."""
        key = "future_key"
        expired_at = time.time() + 100  # "Expired" in the future
        error = CacheExpiredError(key, expired_at)

        assert error.details["expired_at"] == expired_at
        assert error.details["current_time"] < expired_at

    def test_zero_expiration_time(self):
        """Test with zero expiration time."""
        key = "zero_key"
        expired_at = 0.0
        error = CacheExpiredError(key, expired_at)

        assert error.details["expired_at"] == 0.0
        assert error.details["current_time"] > 0.0

    def test_negative_expiration_time(self):
        """Test with negative expiration time."""
        key = "negative_key"
        expired_at = -100.0
        error = CacheExpiredError(key, expired_at)

        assert error.details["expired_at"] == -100.0


class TestCacheExceptionsInheritance:
    """Test inheritance hierarchy of cache exceptions."""

    def test_all_inherit_from_cache_error(self):
        """Test that all cache exceptions inherit from CacheError."""
        exceptions = [
            CacheKeyError("key", "operation"),
            CacheFullError(100),
            CacheExpiredError("key", time.time()),
        ]

        for exception in exceptions:
            assert isinstance(exception, CacheError)
            assert isinstance(exception, OmniCacheError)

    def test_exception_hierarchy_chain(self):
        """Test the complete inheritance chain."""
        error = CacheKeyError("test", "get")

        # Test MRO (Method Resolution Order)
        mro = type(error).__mro__
        assert CacheKeyError in mro
        assert CacheError in mro
        assert OmniCacheError in mro
        assert Exception in mro
        assert BaseException in mro

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (CacheKeyError, ("key", "operation")),
            (CacheFullError, (100,)),
            (CacheExpiredError, ("key", time.time())),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all cache exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, CacheError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")

    def test_cache_exceptions_are_catchable_as_cache_error(self):
        """Test that specific cache exceptions can be caught as CacheError."""
        exceptions = [
            CacheKeyError("key", "get"),
            CacheFullError(100),
            CacheExpiredError("key", time.time()),
        ]

        for exception in exceptions:
            try:
                raise exception
            except CacheError as caught:
                assert caught is exception
            except Exception:
                pytest.fail("Exception should be catchable as CacheError")

    def test_cache_exceptions_details_structure(self):
        """Test that all cache exceptions have proper details structure."""
        key_error = CacheKeyError("test", "get", "reason")
        full_error = CacheFullError(100, 90, "lru")
        expired_error = CacheExpiredError("key", time.time())

        # Test that all have required details
        assert isinstance(key_error.details, dict)
        assert isinstance(full_error.details, dict)
        assert isinstance(expired_error.details, dict)

        # Test specific details
        assert "key" in key_error.details
        assert "operation" in key_error.details
        assert "max_size" in full_error.details
        assert "expired_at" in expired_error.details
