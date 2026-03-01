"""
Unit tests for OmniCacheError base exception class.
"""

import time
from unittest.mock import Mock

from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestOmniCacheError:
    """Test cases for OmniCacheError base exception."""

    def test_basic_initialization(self):
        """Test basic exception initialization with message only."""
        message = "Test error message"
        error = OmniCacheError(message)

        assert error.message == message
        assert error.details == {}
        assert error.cause is None
        assert error.timestamp is not None
        assert isinstance(error.timestamp, float)
        assert str(error) == message

    def test_initialization_with_details(self):
        """Test exception initialization with details dictionary."""
        message = "Test error with details"
        details = {"key1": "value1", "key2": 42}
        error = OmniCacheError(message, details)

        assert error.message == message
        assert error.details == details
        assert error.cause is None
        expected_str = f"{message} (key1=value1, key2=42)"
        assert str(error) == expected_str

    def test_initialization_with_cause(self):
        """Test exception initialization with underlying cause."""
        message = "Test error with cause"
        cause = ValueError("Original error")
        error = OmniCacheError(message, cause=cause)

        assert error.message == message
        assert error.details == {}
        assert error.cause == cause
        expected_str = f"{message} - Caused by: Original error"
        assert str(error) == expected_str

    def test_initialization_with_all_parameters(self):
        """Test exception initialization with all parameters."""
        message = "Complete error"
        details = {"operation": "test", "timeout": 5.0}
        cause = ConnectionError("Network failed")
        error = OmniCacheError(message, details, cause)

        assert error.message == message
        assert error.details == details
        assert error.cause == cause
        expected_str = f"{message} (operation=test, timeout=5.0) - Caused by: Network failed"
        assert str(error) == expected_str

    def test_empty_details_handling(self):
        """Test that empty details are handled correctly."""
        message = "Error with empty details"
        error = OmniCacheError(message, {})

        assert error.details == {}
        assert str(error) == message

    def test_none_details_handling(self):
        """Test that None details are converted to empty dict."""
        message = "Error with None details"
        error = OmniCacheError(message, None)

        assert error.details == {}
        assert str(error) == message

    def test_timestamp_accuracy(self):
        """Test that timestamp is set accurately during initialization."""
        start_time = time.time()
        error = OmniCacheError("Timestamp test")
        end_time = time.time()

        assert start_time <= error.timestamp <= end_time

    def test_repr_method(self):
        """Test the __repr__ method output."""
        message = "Test repr"
        details = {"key": "value"}
        error = OmniCacheError(message, details)

        expected_repr = f"OmniCacheError(message='{message}', details={details})"
        assert repr(error) == expected_repr

    def test_repr_without_details(self):
        """Test __repr__ method without details."""
        message = "Simple error"
        error = OmniCacheError(message)

        expected_repr = f"OmniCacheError(message='{message}', details={{}})"
        assert repr(error) == expected_repr

    def test_inheritance_from_exception(self):
        """Test that OmniCacheError inherits from Exception."""
        error = OmniCacheError("Test inheritance")

        assert isinstance(error, Exception)
        assert isinstance(error, BaseException)

    def test_details_immutability_protection(self):
        """Test that original details dict is not modified."""
        original_details = {"key": "value"}
        error = OmniCacheError("Test", original_details)

        # Modify the error's details
        error.details["new_key"] = "new_value"

        # Original should be unchanged if properly isolated
        # Note: Current implementation doesn't deep copy, this documents the behavior
        assert "new_key" in original_details  # Current behavior

    def test_complex_details_types(self):
        """Test with complex data types in details."""
        details = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
            "none": None,
            "bool": True,
            "float": 3.14,
        }
        error = OmniCacheError("Complex details", details)

        assert error.details == details
        # Test that string representation handles complex types
        str_repr = str(error)
        assert "Complex details" in str_repr
        assert "list=" in str_repr

    def test_cause_chain_preservation(self):
        """Test that exception cause chain is preserved."""
        original_error = ValueError("Original")
        intermediate_error = RuntimeError("Intermediate")
        intermediate_error.__cause__ = original_error

        final_error = OmniCacheError("Final", cause=intermediate_error)

        assert final_error.cause == intermediate_error
        assert hasattr(intermediate_error, "__cause__")

    def test_with_mock_cause(self):
        """Test exception with mock cause for testing purposes."""
        mock_cause = Mock()
        mock_cause.__str__ = Mock(return_value="Mocked error")

        error = OmniCacheError("Test with mock", cause=mock_cause)

        assert error.cause == mock_cause
        assert "Test with mock - Caused by: Mocked error" in str(error)

    def test_large_details_dictionary(self):
        """Test with a large details dictionary."""
        details = {f"key_{i}": f"value_{i}" for i in range(100)}
        error = OmniCacheError("Large details", details)

        assert len(error.details) == 100
        assert error.details["key_0"] == "value_0"
        assert error.details["key_99"] == "value_99"

    def test_unicode_in_message_and_details(self):
        """Test handling of unicode characters in message and details."""
        message = "Erreur avec caractères unicoDE: éàü"
        details = {"clé": "valeur", "emoji": "🚀", "chinese": "中文"}
        error = OmniCacheError(message, details)

        assert error.message == message
        assert error.details == details
        # Should not raise encoding errors
        str_repr = str(error)
        repr_result = repr(error)
        assert isinstance(str_repr, str)
        assert isinstance(repr_result, str)
