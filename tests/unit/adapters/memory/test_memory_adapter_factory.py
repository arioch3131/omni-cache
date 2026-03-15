"""
Unit tests for omni_cache.core.factories.memory_adapter_factory module.

Tests cover the MemoryAdapterFactory class functionality including
metadata configuration, validators setup, and adapter creation.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from omni_cache.adapters.memory.factory import MemoryAdapterFactory
from omni_cache.core.exceptions import FactoryCreationError
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import CacheBackend

# pylint: disable=protected-access,import-outside-toplevel,consider-using-from-import


class TestMemoryAdapterFactoryInitialization:
    """Test MemoryAdapterFactory initialization."""

    def test_memory_adapter_import_failure(self):
        """Test that MEMORY_ADAPTER_AVAILABLE is False when import fails."""

        # Save original modules if they exist
        factory_module = sys.modules.get("omni_cache.adapters.memory.factory")
        memory_module = sys.modules.get("omni_cache.adapters.memory.memory")

        try:
            # Remove modules from cache
            for module_name in [
                "omni_cache.adapters.memory.factory",
                "omni_cache.adapters.memory.memory",
            ]:
                if module_name in sys.modules:
                    del sys.modules[module_name]

            # Mock the memory module to not exist
            with patch.dict("sys.modules", {"omni_cache.adapters.memory.memory": None}):
                # Import factory module fresh
                import omni_cache.adapters.memory.factory as factory

                # Verify MEMORY_ADAPTER_AVAILABLE is False
                assert factory.MEMORY_ADAPTER_AVAILABLE is False

        finally:
            # Restore original modules
            if factory_module is not None:
                sys.modules["omni_cache.adapters.memory.factory"] = factory_module
            if memory_module is not None:
                sys.modules["omni_cache.adapters.memory.memory"] = memory_module

    def test_factory_initialization_default(self):
        """Test factory initialization with default metadata."""
        factory = MemoryAdapterFactory()

        assert factory._metadata is not None
        assert factory._metadata.backend == CacheBackend.MEMORY.value
        assert factory._metadata.factory_class == "MemoryAdapterFactory"
        assert factory._metadata.description == "Factory for in-memory cache adapters"
        assert factory._metadata.version == "1.1.0"
        assert factory._metadata.dependencies == []
        assert factory._metadata.adapter_types == ["cache"]

    def test_factory_initialization_custom_metadata(self):
        """Test factory initialization with custom metadata."""
        custom_metadata = FactoryMetadata(
            backend=CacheBackend.MEMORY,
            factory_class="CustomMemoryFactory",
            description="Custom memory factory",
            version="2.0.0",
        )

        factory = MemoryAdapterFactory(custom_metadata)

        assert factory._metadata == custom_metadata
        assert factory._metadata.factory_class == "CustomMemoryFactory"
        assert factory._metadata.description == "Custom memory factory"
        assert factory._metadata.version == "2.0.0"

    def test_factory_supports_memory_backend(self):
        """Test that factory supports memory backend."""
        factory = MemoryAdapterFactory()

        assert factory.supports(CacheBackend.MEMORY) is True
        assert factory.supports("memory") is True
        assert factory.supports(CacheBackend.REDIS) is False
        assert factory.supports("redis") is False


class TestMemoryAdapterFactoryMetadata:
    """Test MemoryAdapterFactory metadata configuration."""

    def test_get_default_metadata(self):
        """Test _get_default_metadata method."""
        factory = MemoryAdapterFactory()
        metadata = factory._get_default_metadata()

        assert isinstance(metadata, FactoryMetadata)
        assert metadata.backend == CacheBackend.MEMORY.value
        assert metadata.factory_class == "MemoryAdapterFactory"
        assert metadata.description == "Factory for in-memory cache adapters"
        assert metadata.version == "1.1.0"
        assert metadata.dependencies == []
        assert metadata.adapter_types == ["cache"]

    def test_config_schema_properties(self):
        """Test configuration schema properties."""
        factory = MemoryAdapterFactory()
        schema = factory.get_config_schema()

        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema

        properties = schema["properties"]
        assert "name" in properties
        assert "max_size" in properties
        assert "default_ttl" in properties
        assert "eviction_policy" in properties
        assert "cleanup_interval" in properties

        # Check name property
        assert properties["name"]["type"] == "string"
        assert properties["name"]["default"] == "memory"

        # Check max_size property
        assert properties["max_size"]["type"] == ["integer", "null"]
        assert properties["max_size"]["minimum"] == 1

        # Check default_ttl property
        assert properties["default_ttl"]["type"] == ["number", "null"]
        assert properties["default_ttl"]["minimum"] == 0

        # Check eviction_policy property
        assert properties["eviction_policy"]["type"] == "string"
        assert properties["eviction_policy"]["enum"] == ["lru", "fifo", "random"]
        assert properties["eviction_policy"]["default"] == "lru"

        # Check cleanup_interval property
        assert properties["cleanup_interval"]["type"] == "number"
        assert properties["cleanup_interval"]["minimum"] == 1
        assert properties["cleanup_interval"]["default"] == 60

    def test_config_schema_required_fields(self):
        """Test configuration schema required fields."""
        factory = MemoryAdapterFactory()
        schema = factory.get_config_schema()

        assert "required" in schema
        assert schema["required"] == []  # No required fields for memory adapter


class TestMemoryAdapterFactoryValidators:
    """Test MemoryAdapterFactory configuration validators."""

    def test_setup_config_validators(self):
        """Test _setup_config_validators method."""
        factory = MemoryAdapterFactory()

        # Validators should be set up during initialization
        assert "eviction_policy" in factory._config_validators
        assert "max_size" in factory._config_validators
        assert "cleanup_interval" in factory._config_validators

    def test_eviction_policy_validator(self):
        """Test eviction policy validator."""
        factory = MemoryAdapterFactory()
        validator = factory._config_validators["eviction_policy"]

        # Valid policies
        assert validator("lru") is True
        assert validator("fifo") is True
        assert validator("random") is True

        # Invalid policies
        assert validator("invalid") is False
        assert validator("lfu") is False
        assert validator("") is False

    def test_max_size_validator(self):
        """Test max_size validator."""
        factory = MemoryAdapterFactory()
        validator = factory._config_validators["max_size"]

        # Valid values
        assert validator(None) is True
        assert validator(1) is True
        assert validator(100) is True
        assert validator(1000) is True

        # Invalid values
        assert validator(0) is False
        assert validator(-1) is False
        assert validator("100") is False
        assert validator(1.5) is False

    def test_cleanup_interval_validator(self):
        """Test cleanup_interval validator."""
        factory = MemoryAdapterFactory()
        validator = factory._config_validators["cleanup_interval"]

        # Valid values
        assert validator(1) is True
        assert validator(60) is True
        assert validator(1.5) is True
        assert validator(0.1) is True

        # Invalid values
        assert validator(0) is False
        assert validator(-1) is False
        assert validator("60") is False


class TestMemoryAdapterFactoryAdapterCreation:
    """Test MemoryAdapterFactory adapter creation."""

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    def test_create_adapter_success(self, mock_config_class, mock_adapter_class):
        """Test successful adapter creation."""
        factory = MemoryAdapterFactory()
        config = {
            "name": "test_memory",
            "max_size": 100,
            "eviction_policy": "lru",
            "cleanup_interval": 30,
        }

        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        result = factory._create_adapter(config)

        mock_config_class.assert_called_once_with(**config)
        mock_adapter_class.assert_called_once_with(mock_config_instance)
        assert result == mock_adapter_instance

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", False)
    def test_create_adapter_unavailable(self):
        """Test adapter creation when memory adapter is unavailable."""
        factory = MemoryAdapterFactory()
        config = {"name": "test_memory"}

        with pytest.raises(FactoryCreationError) as exc_info:
            factory._create_adapter(config)
        assert "Memory adapter not available" in str(exc_info.value)
        assert exc_info.value.details["backend"] == CacheBackend.MEMORY.value
        assert exc_info.value.details["adapter_config"] == config

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", False)
    def test_create_adapter_unavailable_backend_value_used(self):
        """Test adapter creation when memory adapter is unavailable and backend value is used."""
        factory = MemoryAdapterFactory()
        config = {"name": "test_memory"}

        # Explicitly set backend to enum member for this test
        factory._metadata.backend = CacheBackend.MEMORY

        with pytest.raises(FactoryCreationError) as exc_info:
            factory._create_adapter(config)

        # Assert that the backend in the error details is the value of the enum
        assert exc_info.value.details["backend"] == CacheBackend.MEMORY.value
        assert exc_info.value.details["backend"] == "memory"

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    def test_create_adapter_with_minimal_config(self, mock_config_class, mock_adapter_class):
        """Test adapter creation with minimal configuration."""
        factory = MemoryAdapterFactory()
        config = {}  # Empty config should work due to defaults

        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        result = factory._create_adapter(config)

        mock_config_class.assert_called_once_with(**config)
        mock_adapter_class.assert_called_once_with(mock_config_instance)
        assert result == mock_adapter_instance

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    # pylint: disable=unused-argument
    def test_create_adapter_config_error(self, mock_config_class, mock_adapter_class):
        """Test adapter creation when config creation fails."""
        factory = MemoryAdapterFactory()
        config = {"name": "test_memory"}

        mock_config_class.side_effect = ValueError("Invalid configuration")

        with pytest.raises(ValueError, match="Invalid configuration"):
            factory._create_adapter(config)

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    def test_create_adapter_instantiation_error(self, mock_config_class, mock_adapter_class):
        """Test adapter creation when adapter instantiation fails."""
        factory = MemoryAdapterFactory()
        config = {"name": "test_memory"}

        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance
        mock_adapter_class.side_effect = RuntimeError("Adapter creation failed")

        with pytest.raises(RuntimeError, match="Adapter creation failed"):
            factory._create_adapter(config)


class TestMemoryAdapterFactoryIntegration:
    """Test MemoryAdapterFactory integration scenarios."""

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    def test_create_full_workflow(self, mock_config_class, mock_adapter_class):
        """Test complete adapter creation workflow through create method."""
        factory = MemoryAdapterFactory()
        config = {
            "name": "test_memory",
            "max_size": 500,
            "eviction_policy": "fifo",
            "default_ttl": 300,
            "cleanup_interval": 120,
        }

        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        # Call the public create method which includes validation
        result = factory.create(config)

        mock_config_class.assert_called_once_with(**config)
        mock_adapter_class.assert_called_once_with(mock_config_instance)
        assert result == mock_adapter_instance

    def test_get_metadata(self):
        """Test getting factory metadata."""
        factory = MemoryAdapterFactory()
        metadata = factory.get_metadata()

        assert isinstance(metadata, FactoryMetadata)
        assert metadata.backend == CacheBackend.MEMORY.value
        assert metadata.factory_class == "MemoryAdapterFactory"

    def test_get_config_schema(self):
        """Test getting configuration schema."""
        factory = MemoryAdapterFactory()
        schema = factory.get_config_schema()

        assert isinstance(schema, dict)
        assert "type" in schema
        assert "properties" in schema
        assert "required" in schema


class TestMemoryAdapterFactoryValidation:
    """Test MemoryAdapterFactory configuration validation."""

    def test_validation_with_valid_config(self):
        """Test validation passes with valid configuration."""
        factory = MemoryAdapterFactory()
        config = {
            "name": "test_memory",
            "max_size": 100,
            "eviction_policy": "lru",
            "cleanup_interval": 60,
        }

        # Should not raise any exception
        factory._validate_config(config)

    def test_validation_with_empty_config(self):
        """Test validation passes with empty configuration (all optional)."""
        factory = MemoryAdapterFactory()
        config = {}

        # Should not raise any exception since all fields are optional
        factory._validate_config(config)

    def test_validation_with_invalid_eviction_policy(self):
        """Test validation fails with invalid eviction policy."""
        factory = MemoryAdapterFactory()
        config = {"eviction_policy": "invalid_policy"}

        from omni_cache.core.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError):
            factory._validate_config(config)

    def test_validation_with_invalid_max_size(self):
        """Test validation fails with invalid max_size."""
        factory = MemoryAdapterFactory()
        config = {"max_size": -1}

        from omni_cache.core.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError):
            factory._validate_config(config)

    def test_validation_with_invalid_cleanup_interval(self):
        """Test validation fails with invalid cleanup_interval."""
        factory = MemoryAdapterFactory()
        config = {"cleanup_interval": 0}

        from omni_cache.core.exceptions import InvalidConfigurationError

        with pytest.raises(InvalidConfigurationError):
            factory._validate_config(config)


class TestMemoryAdapterFactoryDependencies:
    """Test MemoryAdapterFactory dependency management."""

    def test_validate_dependencies_success(self):
        """Test dependency validation when all dependencies are available."""
        factory = MemoryAdapterFactory()
        missing_deps = factory._validate_dependencies()

        # Memory adapter has no external dependencies
        assert not missing_deps

    def test_no_external_dependencies(self):
        """Test that memory adapter factory has no external dependencies."""
        factory = MemoryAdapterFactory()
        metadata = factory.get_metadata()

        assert metadata.dependencies == []


class TestMemoryAdapterFactoryEdgeCases:
    """Test MemoryAdapterFactory edge cases and error handling."""

    def test_factory_with_none_config(self):
        """Test factory behavior with None values in config."""
        factory = MemoryAdapterFactory()
        config = {"name": "test", "max_size": None, "default_ttl": None}

        # Should pass validation since None is allowed for these fields
        factory._validate_config(config)

    def test_config_with_unexpected_fields(self):
        """Test factory behavior with unexpected configuration fields."""
        factory = MemoryAdapterFactory()
        config = {"name": "test", "unexpected_field": "value", "another_unexpected": 123}

        # Should pass validation - unexpected fields are typically ignored
        factory._validate_config(config)

    @patch("omni_cache.adapters.memory.factory.MEMORY_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.memory.factory.MemoryAdapter")
    @patch("omni_cache.adapters.memory.factory.MemoryAdapterConfig")
    def test_create_with_complex_config(self, mock_config_class, mock_adapter_class):
        """Test adapter creation with all possible configuration options."""
        factory = MemoryAdapterFactory()
        config = {
            "name": "complex_memory",
            "max_size": 1000,
            "default_ttl": 600.5,
            "eviction_policy": "random",
            "cleanup_interval": 30.5,
            # Additional fields that might be passed through
            "extra_field": "extra_value",
        }

        mock_config_instance = MagicMock()
        mock_config_class.return_value = mock_config_instance
        mock_adapter_instance = MagicMock()
        mock_adapter_class.return_value = mock_adapter_instance

        result = factory._create_adapter(config)

        mock_config_class.assert_called_once_with(**config)
        assert result == mock_adapter_instance


if __name__ == "__main__":
    pytest.main([__file__])
