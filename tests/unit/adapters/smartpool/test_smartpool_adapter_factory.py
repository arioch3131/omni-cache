"""
Tests for SmartPool adapter factory.

This module provides comprehensive tests for the SmartPoolAdapterFactory class,
covering all functionality including metadata, configuration validation,
adapter creation, and error handling.
"""

from unittest.mock import Mock, patch

import pytest

from omni_cache.core.exceptions import (
    FactoryCreationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import CacheBackend


class TestSmartPoolAdapterFactory:
    """Tests for the SmartPoolAdapterFactory class."""

    @pytest.fixture
    def factory(self):
        """Create a SmartPoolAdapterFactory instance for testing."""
        # Import inside fixture to handle conditional imports
        from omni_cache.adapters.smartpool.factory import SmartPoolAdapterFactory

        return SmartPoolAdapterFactory()

    @pytest.fixture
    def mock_factory_function(self):
        """Mock factory function for creating objects."""
        return Mock(return_value=Mock())

    @pytest.fixture
    def valid_config(self, mock_factory_function):
        """Valid configuration for SmartPool adapter."""
        return {
            "factory_function": mock_factory_function,
            "name": "test_pool",
            "initial_size": 5,
            "max_size": 20,
            "min_size": 2,
            "growth_factor": 1.5,
            "shrink_threshold": 0.5,
        }

    @pytest.fixture
    def minimal_config(self, mock_factory_function):
        """Minimal valid configuration."""
        return {
            "factory_function": mock_factory_function,
        }

    def test_factory_initialization(self, factory):
        """Test that the factory initializes correctly."""
        assert factory is not None
        assert hasattr(factory, "_metadata")
        assert hasattr(factory, "_config_validators")

    def test_get_default_metadata(self, factory):
        """Test that default metadata is correctly configured."""
        metadata = factory._get_default_metadata()

        assert isinstance(metadata, FactoryMetadata)
        assert metadata.backend == CacheBackend.SMARTPOOL.value
        assert metadata.factory_class == "SmartPoolAdapterFactory"
        assert metadata.description == "Factory for SmartPool adapters"
        assert metadata.version == "2.0.0"
        assert "smartpool" in metadata.dependencies
        assert "pool" in metadata.adapter_types

        # Test config schema
        config_schema = metadata.config_schema
        assert config_schema["type"] == "object"
        assert "factory_function" in config_schema["required"]

        properties = config_schema["properties"]
        assert "name" in properties
        assert "initial_size" in properties
        assert "max_size" in properties
        assert "min_size" in properties
        assert "growth_factor" in properties
        assert "shrink_threshold" in properties
        assert "factory_function" in properties

        # Test default values
        assert properties["name"]["default"] == "adaptive"
        assert properties["initial_size"]["default"] == 5
        assert properties["max_size"]["default"] == 20
        assert properties["min_size"]["default"] == 2
        assert properties["growth_factor"]["default"] == 1.5
        assert properties["shrink_threshold"]["default"] == 0.5

        # Test constraints
        assert properties["initial_size"]["minimum"] == 0
        assert properties["max_size"]["minimum"] == 1
        assert properties["min_size"]["minimum"] == 0
        assert properties["growth_factor"]["minimum"] == 1.0
        assert properties["shrink_threshold"]["minimum"] == 0.0
        assert properties["shrink_threshold"]["maximum"] == 1.0

    def test_setup_config_validators(self, factory):
        """Test that config validators are properly set up."""
        validators = factory._config_validators

        # Check that all expected validators are present
        assert "initial_size" in validators
        assert "max_size" in validators
        assert "min_size" in validators
        assert "factory_function" in validators

        # Check that validators are callable
        assert callable(validators["initial_size"])
        assert callable(validators["max_size"])
        assert callable(validators["min_size"])
        assert callable(validators["factory_function"])

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, True),
            (1, True),
            (5, True),
            (100, True),
            (-1, False),
            (1.5, False),
            ("5", False),
            (None, False),
        ],
    )
    def test_non_negative_initial_size_validator(self, factory, value, expected):
        """Test non-negative integer validator for initial_size."""
        validator = factory._config_validators["initial_size"]
        assert validator(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (1, True),
            (5, True),
            (100, True),
            (0, False),
            (-1, False),
            (1.5, False),
            ("5", False),
            (None, False),
        ],
    )
    def test_positive_max_size_validator(self, factory, value, expected):
        """Test positive integer validator for max_size."""
        validator = factory._config_validators["max_size"]
        assert validator(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (0, True),
            (1, True),
            (5, True),
            (-1, False),
            (1.5, False),
            ("0", False),
            (None, False),
        ],
    )
    def test_non_negative_integer_validator(self, factory, value, expected):
        """Test non-negative integer validator for min_size."""
        validator = factory._config_validators["min_size"]
        assert validator(value) == expected

    @pytest.mark.parametrize(
        "value,expected",
        [
            (lambda: None, True),
            (Mock(), True),
            (print, True),
            ("not_callable", False),
            (123, False),
            (None, False),
            ([], False),
        ],
    )
    def test_callable_validator(self, factory, value, expected):
        """Test callable validator for factory_function."""
        validator = factory._config_validators["factory_function"]
        assert validator(value) == expected

    def test_validate_config_valid_sizes(self, factory, valid_config):
        """Test config validation with valid size relationships."""
        # Should not raise any exception
        factory._validate_config(valid_config)

    def test_validate_config_invalid_size_relationships(self, factory, mock_factory_function):
        """Test config validation with invalid size relationships."""
        # min_size > initial_size
        config = {
            "factory_function": mock_factory_function,
            "initial_size": 5,
            "max_size": 20,
            "min_size": 10,
        }
        with pytest.raises(InvalidConfigurationError) as exc_info:
            factory._validate_config(config)
        assert "size_config" in str(exc_info.value)

        # initial_size > max_size
        config = {
            "factory_function": mock_factory_function,
            "initial_size": 25,
            "max_size": 20,
            "min_size": 2,
        }
        with pytest.raises(InvalidConfigurationError) as exc_info:
            factory._validate_config(config)
        assert "size_config" in str(exc_info.value)

    def test_validate_config_missing_required_field(self, factory):
        """Test config validation with missing required field."""
        config = {
            "initial_size": 5,
            "max_size": 20,
            "min_size": 2,
        }
        with pytest.raises(MissingConfigurationError):
            factory._validate_config(config)

    def test_validate_config_uses_defaults(self, factory, mock_factory_function):
        """Test that validation uses default values when fields are missing."""
        config = {
            "factory_function": mock_factory_function,
            # Only required field, others should use defaults
        }
        # Should not raise exception - uses defaults for size validation
        factory._validate_config(config)

    def test_validate_config_accepts_zero_initial_size(self, factory, mock_factory_function):
        """Test that zero initial_size is allowed for lazily populated pools."""
        config = {
            "factory_function": mock_factory_function,
            "initial_size": 0,
            "max_size": 20,
            "min_size": 0,
        }

        factory._validate_config(config)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_create_adapter_success(self, factory, valid_config):
        """Test successful adapter creation when SmartPool is available."""
        with (
            patch("omni_cache.adapters.smartpool.factory.SmartPoolAdapter") as mock_adapter_class,
            patch(
                "omni_cache.adapters.smartpool.factory.SmartPoolAdapterConfig"
            ) as mock_config_class,
        ):
            mock_adapter_instance = Mock()
            mock_adapter_class.return_value = mock_adapter_instance
            mock_config_instance = Mock()
            mock_config_class.return_value = mock_config_instance

            result = factory._create_adapter(valid_config)

            assert result == mock_adapter_instance
            mock_config_class.assert_called_once_with(**valid_config)
            mock_adapter_class.assert_called_once_with(mock_config_instance)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", False)
    def test_create_adapter_smartpool_not_available(self, factory, valid_config):
        """Test adapter creation when SmartPool library is not available."""
        with pytest.raises(FactoryCreationError) as exc_info:
            factory._create_adapter(valid_config)

        assert "smartpool" in str(exc_info.value)
        assert isinstance(exc_info.value.cause, ImportError)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_create_adapter_invalid_config(self, factory, mock_factory_function):
        """Test adapter creation with invalid configuration."""
        invalid_config = {
            "factory_function": mock_factory_function,
            "initial_size": -1,  # Invalid value
        }

        with pytest.raises(InvalidConfigurationError):
            factory._create_adapter(invalid_config)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_create_adapter_missing_config(self, factory):
        """Test adapter creation with missing required configuration."""
        incomplete_config = {
            "initial_size": 5,
            # Missing factory_function
        }

        with pytest.raises(MissingConfigurationError):
            factory._create_adapter(incomplete_config)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_create_adapter_creation_error(self, factory, valid_config):
        """Test adapter creation when SmartPoolAdapter constructor fails."""
        with (
            patch("omni_cache.adapters.smartpool.factory.SmartPoolAdapter") as mock_adapter_class,
            patch("omni_cache.adapters.smartpool.factory.SmartPoolAdapterConfig"),
        ):
            mock_adapter_class.side_effect = RuntimeError("Adapter creation failed")

            with pytest.raises(FactoryCreationError) as exc_info:
                factory._create_adapter(valid_config)

            assert "smartpool" in str(exc_info.value)
            assert isinstance(exc_info.value.cause, RuntimeError)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_create_adapter_config_creation_error(self, factory, valid_config):
        """Test adapter creation when SmartPoolAdapterConfig constructor fails."""
        with patch(
            "omni_cache.adapters.smartpool.factory.SmartPoolAdapterConfig"
        ) as mock_config_class:
            mock_config_class.side_effect = ValueError("Invalid config parameter")

            with pytest.raises(FactoryCreationError) as exc_info:
                factory._create_adapter(valid_config)

            assert "smartpool" in str(exc_info.value)
            assert isinstance(exc_info.value.cause, ValueError)

    def test_supports_cache_backend_enum(self, factory):
        """Test supports method with CacheBackend enum."""
        assert factory.supports(CacheBackend.SMARTPOOL) is True
        assert factory.supports(CacheBackend.MEMORY) is False
        assert factory.supports(CacheBackend.REDIS) is False

    def test_supports_string_backend(self, factory):
        """Test supports method with string backend."""
        assert factory.supports("smartpool") is True
        assert factory.supports("memory") is False
        assert factory.supports("redis") is False
        assert factory.supports("invalid") is False

    def test_supports_backend_with_value_attribute(self, factory):
        """Test supports method with object that has value attribute."""
        mock_backend = Mock()
        mock_backend.value = CacheBackend.SMARTPOOL.value

        assert factory.supports(mock_backend) is True

        mock_backend.value = CacheBackend.MEMORY.value
        assert factory.supports(mock_backend) is False

    def test_config_validation_integration(self, factory, mock_factory_function):
        """Test complete config validation workflow."""
        # Test with valid config
        config = {
            "factory_function": mock_factory_function,
            "name": "integration_test",
            "initial_size": 3,
            "max_size": 10,
            "min_size": 1,
            "growth_factor": 2.0,
            "shrink_threshold": 0.3,
        }
        factory._validate_config(config)  # Should not raise

        # Test with config that violates custom validation
        config["min_size"] = 5  # Now min > initial
        with pytest.raises(InvalidConfigurationError):
            factory._validate_config(config)

    def test_error_handling_preserves_config_errors(self, factory, mock_factory_function):
        """Test that configuration errors are preserved and not wrapped."""
        config = {
            "factory_function": mock_factory_function,
            "initial_size": -1,  # Invalid
        }

        # Should raise InvalidConfigurationError, not FactoryCreationError
        with pytest.raises(InvalidConfigurationError):
            factory._create_adapter(config)

    @patch("omni_cache.adapters.smartpool.factory.SMARTPOOL_ADAPTER_AVAILABLE", True)
    def test_minimal_config_with_defaults(self, factory, minimal_config):
        """Test adapter creation with minimal config using defaults."""
        with (
            patch("omni_cache.adapters.smartpool.factory.SmartPoolAdapter") as mock_adapter_class,
            patch(
                "omni_cache.adapters.smartpool.factory.SmartPoolAdapterConfig"
            ) as mock_config_class,
        ):
            mock_adapter_instance = Mock()
            mock_adapter_class.return_value = mock_adapter_instance

            result = factory._create_adapter(minimal_config)

            assert result == mock_adapter_instance
            # Verify config was called with minimal config
            mock_config_class.assert_called_once_with(**minimal_config)
