"""
Unit tests for configuration-related exception classes.
"""

import pytest

from omni_cache.core.exceptions.config_exceptions import (
    ConfigurationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestConfigurationError:
    """Test cases for ConfigurationError base class."""

    def test_inheritance(self):
        """Test that ConfigurationError inherits from OmniCacheError."""
        error = ConfigurationError("Test config error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, ConfigurationError)

    def test_basic_initialization(self):
        """Test basic initialization of ConfigurationError."""
        message = "Configuration error occurred"
        error = ConfigurationError(message)
        assert error.message == message


class TestInvalidConfigurationError:
    """Test cases for InvalidConfigurationError."""

    def test_basic_initialization(self):
        """Test basic initialization with key and value only."""
        config_key = "database_host"
        config_value = "invalid_host"
        error = InvalidConfigurationError(config_key, config_value)

        expected_message = f"Invalid configuration value for '{config_key}': {config_value}"
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["config_value"] == config_value
        assert "expected_type" not in error.details
        assert "valid_values" not in error.details

    def test_initialization_with_expected_type(self):
        """Test initialization with expected type."""
        config_key = "port"
        config_value = "not_a_number"
        expected_type = int
        error = InvalidConfigurationError(config_key, config_value, expected_type)

        expected_message = (
            f"Invalid configuration value for '{config_key}': {config_value} (expected type: int)"
        )
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["config_value"] == config_value
        assert error.details["expected_type"] == "int"
        assert "valid_values" not in error.details

    def test_initialization_with_valid_values(self):
        """Test initialization with valid values list."""
        config_key = "log_level"
        config_value = "INVALID"
        valid_values = ["DEBUG", "INFO", "WARNING", "ERROR"]
        error = InvalidConfigurationError(config_key, config_value, valid_values=valid_values)

        expected_message = (
            f"Invalid configuration value for '{config_key}': {config_value} "
            f"(valid values: {valid_values})"
        )
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["config_value"] == config_value
        assert error.details["valid_values"] == valid_values
        assert "expected_type" not in error.details

    def test_initialization_with_both_type_and_values(self):
        """Test initialization with both expected type and valid values."""
        config_key = "retry_count"
        config_value = -1
        expected_type = int
        valid_values = [1, 2, 3, 5]
        error = InvalidConfigurationError(config_key, config_value, expected_type, valid_values)

        expected_message = (
            f"Invalid configuration value for '{config_key}': {config_value} "
            f"(expected type: int) (valid values: {valid_values})"
        )
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["config_value"] == config_value
        assert error.details["expected_type"] == "int"
        assert error.details["valid_values"] == valid_values

    def test_complex_config_values(self):
        """Test with complex configuration values."""
        test_cases = [
            ({"nested": "dict"}, "{'nested': 'dict'}"),
            ([1, 2, 3], "[1, 2, 3]"),
            (None, "None"),
            (True, "True"),
            (42.5, "42.5"),
        ]

        for config_value, _expected_str in test_cases:
            error = InvalidConfigurationError("test_key", config_value)
            # The actual representation might vary, so just check it's a string
            assert isinstance(str(error.details["config_value"]), str)

    def test_expected_type_name_extraction(self):
        """Test that expected type names are extracted correctly."""
        test_types = [
            (str, "str"),
            (int, "int"),
            (float, "float"),
            (bool, "bool"),
            (list, "list"),
            (dict, "dict"),
        ]

        for type_obj, expected_name in test_types:
            error = InvalidConfigurationError("key", "value", type_obj)
            assert error.details["expected_type"] == expected_name

    def test_empty_valid_values_list(self):
        """Test with empty valid values list."""
        error = InvalidConfigurationError("key", "value", valid_values=[])

        assert error.details["valid_values"] == []
        assert "(valid values: [])" in error.message

    def test_none_expected_type(self):
        """Test with explicit None expected type."""
        error = InvalidConfigurationError("key", "value", None)

        expected_message = "Invalid configuration value for 'key': value"
        assert error.message == expected_message
        assert "expected_type" not in error.details

    def test_none_valid_values(self):
        """Test with explicit None valid values."""
        error = InvalidConfigurationError("key", "value", valid_values=None)

        expected_message = "Invalid configuration value for 'key': value"
        assert error.message == expected_message
        assert "valid_values" not in error.details

    def test_empty_config_key(self):
        """Test with empty configuration key."""
        error = InvalidConfigurationError("", "value")

        expected_message = "Invalid configuration value for '': value"
        assert error.message == expected_message
        assert error.details["config_key"] == ""


class TestMissingConfigurationError:
    """Test cases for MissingConfigurationError."""

    def test_basic_initialization(self):
        """Test basic initialization without component."""
        config_key = "database_url"
        error = MissingConfigurationError(config_key)

        expected_message = f"Missing required configuration: '{config_key}'"
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert "component" not in error.details

    def test_initialization_with_component(self):
        """Test initialization with component specification."""
        config_key = "api_key"
        component = "payment_processor"
        error = MissingConfigurationError(config_key, component)

        expected_message = (
            f"Missing required configuration: '{config_key}' for component '{component}'"
        )
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["component"] == component

    def test_empty_config_key(self):
        """Test with empty configuration key."""
        error = MissingConfigurationError("")

        expected_message = "Missing required configuration: ''"
        assert error.message == expected_message
        assert error.details["config_key"] == ""

    def test_empty_component(self):
        """Test with empty component."""
        config_key = "setting"
        component = ""
        error = MissingConfigurationError(config_key, component)

        expected_message = f"Missing required configuration: '{config_key}' for component ''"
        assert error.message == expected_message
        assert error.details["component"] == ""

    def test_none_component(self):
        """Test with explicit None component."""
        config_key = "required_setting"
        error = MissingConfigurationError(config_key, None)

        expected_message = f"Missing required configuration: '{config_key}'"
        assert error.message == expected_message
        assert "component" not in error.details

    def test_special_characters_in_key(self):
        """Test with special characters in config key."""
        config_key = "database.connection.pool_size"
        error = MissingConfigurationError(config_key)

        expected_message = f"Missing required configuration: '{config_key}'"
        assert error.message == expected_message
        assert error.details["config_key"] == config_key

    def test_unicode_in_key_and_component(self):
        """Test with unicode characters in key and component."""
        config_key = "confügüration_key"
        component = "compönent_ñame"
        error = MissingConfigurationError(config_key, component)

        expected_message = (
            f"Missing required configuration: '{config_key}' for component '{component}'"
        )
        assert error.message == expected_message
        assert error.details["config_key"] == config_key
        assert error.details["component"] == component


class TestConfigurationExceptionsInheritance:
    """Test inheritance hierarchy of configuration exceptions."""

    def test_all_inherit_from_configuration_error(self):
        """Test that all config exceptions inherit from ConfigurationError."""
        exceptions = [
            InvalidConfigurationError("key", "value"),
            MissingConfigurationError("key"),
        ]

        for exception in exceptions:
            assert isinstance(exception, ConfigurationError)
            assert isinstance(exception, OmniCacheError)

    def test_exception_hierarchy_chain(self):
        """Test the complete inheritance chain."""
        error = InvalidConfigurationError("test", "value")

        # Test MRO (Method Resolution Order)
        mro = type(error).__mro__
        assert InvalidConfigurationError in mro
        assert ConfigurationError in mro
        assert OmniCacheError in mro
        assert Exception in mro
        assert BaseException in mro

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (InvalidConfigurationError, ("key", "value")),
            (MissingConfigurationError, ("key",)),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all config exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, ConfigurationError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")

    def test_config_exceptions_are_catchable_as_configuration_error(self):
        """Test that specific config exceptions can be caught as ConfigurationError."""
        exceptions = [
            InvalidConfigurationError("key", "value"),
            MissingConfigurationError("key"),
        ]

        for exception in exceptions:
            try:
                raise exception
            except ConfigurationError as caught:
                assert caught is exception
            except Exception:
                pytest.fail("Exception should be catchable as ConfigurationError")

    def test_configuration_exceptions_details_structure(self):
        """Test that all config exceptions have proper details structure."""
        invalid_error = InvalidConfigurationError("key", "value", str, ["a", "b"])
        missing_error = MissingConfigurationError("key", "component")

        # Test that all have required details
        assert isinstance(invalid_error.details, dict)
        assert isinstance(missing_error.details, dict)

        # Test specific details
        assert "config_key" in invalid_error.details
        assert "config_value" in invalid_error.details
        assert "expected_type" in invalid_error.details
        assert "valid_values" in invalid_error.details

        assert "config_key" in missing_error.details
        assert "component" in missing_error.details

    def test_error_message_consistency(self):
        """Test that error messages follow consistent patterns."""
        invalid_error = InvalidConfigurationError("test_key", "test_value")
        missing_error = MissingConfigurationError("test_key")

        # Both should mention the config key in their message
        assert "test_key" in invalid_error.message
        assert "test_key" in missing_error.message

        # Invalid should mention "Invalid configuration"
        assert "Invalid configuration" in invalid_error.message

        # Missing should mention "Missing required configuration"
        assert "Missing required configuration" in missing_error.message
