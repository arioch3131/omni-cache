"""
Unit tests for RedisAdapterFactory using pytest.

Tests cover factory initialization, metadata validation, config validation,
adapter creation, and error handling scenarios.
"""

import sys
from unittest.mock import Mock, patch

import pytest

from omni_cache.adapters.redis.factory import RedisAdapterFactory
from omni_cache.core.exceptions import FactoryCreationError
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import AdapterInterface, CacheBackend

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name
# pylint: disable=attribute-defined-outside-init


class TestFactoyRedisImport:
    def test_has_yaml_false_when_import_error(self):
        # Save original state
        redis_module = sys.modules.get("omni_cache.adapters.redis.redis")
        adapter_module = sys.modules.get("omni_cache.adapters.redis.factory")

        try:
            # Force yaml import to fail by setting it to None
            sys.modules["omni_cache.adapters.redis.redis"] = None

            # Remove config from sys.modules to force reload
            if "omni_cache.adapters.redis.factory" in sys.modules:
                del sys.modules["omni_cache.adapters.redis.factory"]

            # Import config which will try to import yaml and set HAS_YAML
            import omni_cache.adapters.redis.factory

            # Assert that HAS_YAML is False due to ImportError
            assert omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE is False

        finally:
            # Restore original state
            if redis_module is not None:
                sys.modules["omni_cache.adapters.redis.redis"] = redis_module
            elif "omni_cache.adapters.redis.redis" in sys.modules:
                del sys.modules["omni_cache.adapters.redis.redis"]

            if adapter_module is not None:
                sys.modules["omni_cache.adapters.redis.factory"] = adapter_module
            elif "omni_cache.adapters.redis.factory" in sys.modules:
                del sys.modules["omni_cache.adapters.redis.factory"]


class TestRedisAdapterFactory:
    """Test suite for RedisAdapterFactory."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.factory = RedisAdapterFactory()

    def test_factory_initialization(self):
        """Test that the factory initializes correctly."""
        assert isinstance(self.factory, RedisAdapterFactory)
        assert self.factory._metadata is not None
        assert self.factory._logger is not None
        assert isinstance(self.factory._config_validators, dict)

    def test_get_default_metadata(self):
        """Test that default metadata is correctly configured."""
        metadata = self.factory._get_default_metadata()

        assert isinstance(metadata, FactoryMetadata)
        assert metadata.backend == CacheBackend.REDIS.value
        assert metadata.factory_class == "RedisAdapterFactory"
        assert metadata.description == "Factory for Redis cache adapters"
        assert metadata.version == "2.0.0"
        assert "redis" in metadata.dependencies
        assert "cache" in metadata.adapter_types

        # Test config schema structure
        config_schema = metadata.config_schema
        assert config_schema is not None
        assert config_schema["type"] == "object"

        properties = config_schema["properties"]
        assert "name" in properties
        assert "host" in properties
        assert "port" in properties
        assert "db" in properties
        assert "password" in properties
        assert "socket_timeout" in properties
        assert "connection_pool_max_connections" in properties

        # Test default values
        assert properties["name"]["default"] == "redis"
        assert properties["host"]["default"] == "localhost"
        assert properties["port"]["default"] == 6379
        assert properties["db"]["default"] == 0
        assert properties["socket_timeout"]["default"] == 5.0
        assert properties["connection_pool_max_connections"]["default"] == 10

        # Test constraints
        assert properties["port"]["minimum"] == 1
        assert properties["port"]["maximum"] == 65535
        assert properties["db"]["minimum"] == 0

    def test_setup_config_validators(self):
        """Test that config validators are properly set up."""
        assert "port" in self.factory._config_validators
        assert "db" in self.factory._config_validators
        assert callable(self.factory._config_validators["port"])
        assert callable(self.factory._config_validators["db"])

    def test_port_validator_valid_values(self):
        """Test port validator with valid values."""
        port_validator = self.factory._config_validators["port"]

        assert port_validator(1) is True
        assert port_validator(6379) is True
        assert port_validator(65535) is True
        assert port_validator(8000) is True

    def test_port_validator_invalid_values(self):
        """Test port validator with invalid values."""
        port_validator = self.factory._config_validators["port"]

        assert port_validator(0) is False
        assert port_validator(65536) is False
        assert port_validator(-1) is False
        assert port_validator("6379") is False
        assert port_validator(3.14) is False
        assert port_validator(None) is False

    def test_db_validator_valid_values(self):
        """Test db validator with valid values."""
        db_validator = self.factory._config_validators["db"]

        assert db_validator(0) is True
        assert db_validator(1) is True
        assert db_validator(15) is True
        assert db_validator(100) is True

    def test_db_validator_invalid_values(self):
        """Test db validator with invalid values."""
        db_validator = self.factory._config_validators["db"]

        assert db_validator(-1) is False
        assert db_validator("0") is False
        assert db_validator(3.14) is False
        assert db_validator(None) is False

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.redis.factory.RedisAdapter")
    @patch("omni_cache.adapters.redis.factory.RedisAdapterConfig")
    def test_create_adapter_success(self, mock_config_class, mock_adapter_class):
        """Test successful adapter creation when Redis is available."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config

        mock_adapter = Mock(spec=AdapterInterface)
        mock_adapter_class.return_value = mock_adapter

        # Test configuration
        config = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None,
            "socket_timeout": 5.0,
        }

        # Call method
        result = self.factory._create_adapter(config)

        # Assertions
        mock_config_class.assert_called_once_with(**config)
        mock_adapter_class.assert_called_once_with(mock_config)
        assert result == mock_adapter

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", False)
    def test_create_adapter_redis_not_available(self):
        """Test adapter creation when Redis is not available."""
        config = {"host": "localhost", "port": 6379}

        with pytest.raises(FactoryCreationError) as exc_info:
            self.factory._create_adapter(config)

        assert "Redis adapter not available" in str(exc_info.value)

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", False)
    def test_create_adapter_backend_is_cachebackend_enum(self):
        """Test _create_adapter when backend is a CacheBackend enum and Redis is not available."""
        # Temporarily set _metadata.backend to a CacheBackend enum member
        original_backend = self.factory._metadata.backend
        self.factory._metadata.backend = CacheBackend.REDIS

        config = {"host": "localhost", "port": 6379}

        with pytest.raises(FactoryCreationError) as exc_info:
            self.factory._create_adapter(config)

        assert "Redis adapter not available" in str(exc_info.value)
        assert (
            exc_info.value.details["backend"] == CacheBackend.REDIS.value
        )  # Ensure the error message uses the value

        # Restore original backend
        self.factory._metadata.backend = original_backend

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.redis.factory.RedisAdapterConfig")
    def test_create_adapter_config_error(self, mock_config_class):
        """Test adapter creation when config validation fails."""
        # Setup mock to raise exception
        mock_config_class.side_effect = ValueError("Invalid configuration")

        config = {"invalid_param": "invalid_value"}

        with pytest.raises(ValueError):
            self.factory._create_adapter(config)

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.redis.factory.RedisAdapter")
    @patch("omni_cache.adapters.redis.factory.RedisAdapterConfig")
    def test_create_adapter_creation_error(self, mock_config_class, mock_adapter_class):
        """Test adapter creation when adapter instantiation fails."""
        # Setup mocks
        mock_config = Mock()
        mock_config_class.return_value = mock_config
        mock_adapter_class.side_effect = RuntimeError("Connection failed")

        config = {"host": "localhost", "port": 6379}

        with pytest.raises(RuntimeError, match="Connection failed"):
            self.factory._create_adapter(config)

    def test_create_adapter_with_minimal_config(self):
        """Test adapter creation with minimal configuration."""
        with (
            patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True),
            patch("omni_cache.adapters.redis.factory.RedisAdapter") as mock_adapter_class,
            patch("omni_cache.adapters.redis.factory.RedisAdapterConfig") as mock_config_class,
        ):
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            mock_adapter = Mock(spec=AdapterInterface)
            mock_adapter_class.return_value = mock_adapter

            # Empty config should work with defaults
            config = {}
            result = self.factory._create_adapter(config)

            mock_config_class.assert_called_once_with(**config)
            assert result == mock_adapter

    def test_create_adapter_with_full_config(self):
        """Test adapter creation with complete configuration."""
        with (
            patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True),
            patch("omni_cache.adapters.redis.factory.RedisAdapter") as mock_adapter_class,
            patch("omni_cache.adapters.redis.factory.RedisAdapterConfig") as mock_config_class,
        ):
            mock_config = Mock()
            mock_config_class.return_value = mock_config
            mock_adapter = Mock(spec=AdapterInterface)
            mock_adapter_class.return_value = mock_adapter

            config = {
                "name": "test_redis",
                "host": "redis.example.com",
                "port": 6380,
                "db": 2,
                "password": "secret",
                "socket_timeout": 10.0,
                "connection_pool_max_connections": 20,
            }

            result = self.factory._create_adapter(config)

            mock_config_class.assert_called_once_with(**config)
            assert result == mock_adapter

    def test_factory_metadata_consistency(self):
        """Test that factory metadata is consistent across instances."""
        factory1 = RedisAdapterFactory()
        factory2 = RedisAdapterFactory()

        metadata1 = factory1._get_default_metadata()
        metadata2 = factory2._get_default_metadata()

        assert metadata1.backend == metadata2.backend
        assert metadata1.factory_class == metadata2.factory_class
        assert metadata1.description == metadata2.description
        assert metadata1.version == metadata2.version
        assert metadata1.dependencies == metadata2.dependencies

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    def test_inheritance_from_abstract_factory(self):
        """Test that RedisAdapterFactory properly inherits from AbstractFactory."""
        from omni_cache.core.factories.abstract_factory import AbstractFactory

        assert isinstance(self.factory, AbstractFactory)
        assert hasattr(self.factory, "create")
        assert hasattr(self.factory, "get_metadata")
        assert hasattr(self.factory, "get_config_schema")

    def test_config_validators_type(self):
        """Test that config validators are properly typed and callable."""
        validators = self.factory._config_validators

        for name, validator in validators.items():
            assert isinstance(name, str)
            assert callable(validator)

        # Ensure we have the expected validators
        expected_validators = {"port", "db"}
        actual_validators = set(validators.keys())
        assert expected_validators.issubset(actual_validators)


class TestRedisAdapterFactoryIntegration:
    """Integration tests for RedisAdapterFactory."""

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    def test_factory_registration_compatibility(self):
        """Test that the factory can be registered in a registry."""
        from omni_cache.core.factories.factory_registry import FactoryRegistry

        registry = FactoryRegistry()
        factory = RedisAdapterFactory()

        # This should not raise an exception
        registry.register(factory)

        # Verify registration
        registered_factory = registry.get_factory(CacheBackend.REDIS)
        assert registered_factory is not None
        assert isinstance(registered_factory, RedisAdapterFactory)

    def test_metadata_backend_enum_compatibility(self):
        """Test that metadata backend works with CacheBackend enum."""
        factory = RedisAdapterFactory()
        metadata = factory._get_default_metadata()

        assert metadata.backend == CacheBackend.REDIS.value
        assert metadata.backend == "redis"  # String comparison should also work


# Edge case tests
class TestRedisAdapterFactoryEdgeCases:
    """Test edge cases and error conditions."""

    def test_factory_with_custom_metadata(self):
        """Test factory initialization with custom metadata."""
        custom_metadata = FactoryMetadata(
            backend=CacheBackend.REDIS,
            factory_class="CustomRedisFactory",
            description="Custom Redis factory",
            version="2.0.0",
            dependencies=["redis", "custom_lib"],
            adapter_types=["cache", "custom"],
        )

        factory = RedisAdapterFactory(metadata=custom_metadata)
        assert factory._metadata == custom_metadata
        assert factory._metadata.version == "2.0.0"
        assert "custom_lib" in factory._metadata.dependencies

    @patch("omni_cache.adapters.redis.factory.REDIS_ADAPTER_AVAILABLE", True)
    @patch("omni_cache.adapters.redis.factory.RedisAdapterConfig")
    def test_config_with_none_values(self, mock_config_class):
        """Test configuration with None values."""
        config = {"host": "localhost", "port": 6379, "password": None, "socket_timeout": None}

        mock_config = Mock()
        mock_config_class.return_value = mock_config

        with patch("omni_cache.adapters.redis.factory.RedisAdapter") as mock_adapter:
            mock_adapter_instance = Mock(spec=AdapterInterface)
            mock_adapter.return_value = mock_adapter_instance

            factory = RedisAdapterFactory()
            result = factory._create_adapter(config)

            mock_config_class.assert_called_once_with(**config)
            assert result == mock_adapter_instance

    def test_validator_edge_values(self):
        """Test validators with edge case values."""
        factory = RedisAdapterFactory()
        port_validator = factory._config_validators["port"]
        db_validator = factory._config_validators["db"]

        # Test boundary values
        assert port_validator(1) is True  # Minimum valid port
        assert port_validator(65535) is True  # Maximum valid port
        assert db_validator(0) is True  # Minimum valid db

        # Test just outside boundaries
        assert port_validator(0) is False
        assert port_validator(65536) is False
        assert db_validator(-1) is False
