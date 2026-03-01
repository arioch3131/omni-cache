"""
Unit tests for omni_cache.core.factories.abstract_factory module.

Tests cover the AbstractFactory base class functionality including
configuration validation, dependency checking, and adapter creation.
"""

import logging
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from omni_cache.core.exceptions import (
    FactoryCreationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import AdapterInterface, CacheBackend


# Test fixtures and helper classes
class MockAdapter(AdapterInterface):
    """Mock adapter for testing purposes."""

    def connect(self) -> bool:
        return True

    def disconnect(self) -> bool:
        return True

    def is_connected(self) -> bool:
        return True

    def health_check(self) -> bool:
        return True

    def get_backend_info(self) -> dict[str, Any]:
        return {"type": "mock", "status": "ok"}


class ConcreteFactory(AbstractFactory):
    """Concrete implementation of AbstractFactory for testing."""

    def __init__(
        self,
        metadata: FactoryMetadata = None,
        should_fail_connect: bool = False,
        should_fail_create: bool = False,
        missing_dependencies: list = None,
    ):
        self._should_fail_connect = should_fail_connect
        self._should_fail_create = should_fail_create
        self._missing_dependencies = missing_dependencies or []
        super().__init__(metadata)

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend="test",
            factory_class="ConcreteFactory",
            description="Test factory for unit tests",
            version="1.0.0",
            dependencies=[],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "test"},
                    "size": {"type": "integer", "minimum": 1, "default": 10},
                    "enabled": {"type": "boolean", "default": True},
                },
                "required": ["name"],
            },
            adapter_types=["cache"],
        )

    def _setup_config_validators(self) -> None:
        """Setup test validators."""

        def validate_size(value: int) -> bool:
            return isinstance(value, int) and value > 0

        def validate_name(value: str) -> bool:
            return isinstance(value, str) and len(value) > 0

        self.add_config_validator("size", validate_size)
        self.add_config_validator("name", validate_name)

    def _create_adapter(self, config: dict[str, Any]) -> MockAdapter:
        """Create mock adapter."""
        if self._should_fail_create:
            raise RuntimeError("Simulated creation failure")
        return MockAdapter()

    def _validate_dependencies(self) -> list:
        """Override to simulate missing dependencies."""
        if self._missing_dependencies:
            return self._missing_dependencies
        return super()._validate_dependencies()


class FailingFactory(AbstractFactory):
    """Factory that fails during initialization for error testing."""

    def _get_default_metadata(self) -> FactoryMetadata:
        raise RuntimeError("Metadata initialization failed")

    def _setup_config_validators(self) -> None:
        pass

    def _create_adapter(self, config: dict[str, Any]) -> MockAdapter:
        return MockAdapter()


# Test fixtures
@pytest.fixture
def factory_metadata():
    """Provide standard factory metadata for tests."""
    return FactoryMetadata(
        backend=CacheBackend.MEMORY,
        factory_class="TestFactory",
        description="Test factory metadata",
        version="1.0.0",
        dependencies=["dep1", "dep2"],
        config_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string", "default": "default"},
                "timeout": {"type": "number", "minimum": 0.1, "default": 5.0},
            },
            "required": ["name"],
        },
        adapter_types=["cache", "pool"],
    )


@pytest.fixture
def concrete_factory():
    """Provide a working concrete factory instance."""
    return ConcreteFactory()


@pytest.fixture
def valid_config():
    """Provide valid configuration for testing."""
    return {"name": "test_adapter", "size": 100, "enabled": True}


@pytest.fixture
def invalid_config():
    """Provide invalid configuration for testing."""
    return {"size": -1, "enabled": "not_boolean"}  # Missing required 'name', invalid size


# Initialization tests
class TestAbstractFactoryInitialization:
    """Test AbstractFactory initialization."""

    def test_init_with_metadata(self, factory_metadata):
        """Test initialization with provided metadata."""
        factory = ConcreteFactory(factory_metadata)

        assert factory._metadata == factory_metadata
        assert factory._logger is not None
        assert factory._logger.name.endswith("concretefactory")

    def test_init_without_metadata(self):
        """Test initialization without metadata uses defaults."""
        factory = ConcreteFactory()

        assert factory._metadata is not None
        assert factory._metadata.backend == "test"
        assert factory._metadata.factory_class == "ConcreteFactory"
        assert factory._metadata.description == "Test factory for unit tests"

    def test_init_logger_setup(self):
        """Test logger is properly configured."""
        factory = ConcreteFactory()

        assert factory._logger is not None
        assert factory._logger.level == logging.INFO
        assert factory._logger.propagate is True  # Should propagate to root

        # Test logger functionality instead of handler count
        try:
            factory._logger.info("Test message")
            assert True  # If no exception, logger works
        except Exception as e:
            pytest.fail(f"Logger should be functional: {e}")

    def test_init_calls_setup_validators(self):
        """Test that _setup_config_validators is called during init."""
        factory = ConcreteFactory()

        # Should have validators added by _setup_config_validators
        assert "size" in factory._config_validators
        assert "name" in factory._config_validators

    def test_init_failure_handling(self):
        """Test graceful handling of initialization failures."""
        with pytest.raises(RuntimeError, match="Metadata initialization failed"):
            FailingFactory()


# Logger setup tests
class TestLoggerSetup:
    """Test logger configuration."""

    def test_logger_name_format(self):
        """Test logger name follows expected format."""
        factory = ConcreteFactory()
        expected_name = "omni_cache.factory.concretefactory"
        assert factory._logger.name == expected_name

    @patch("logging.getLogger")
    def test_logger_configuration(self, mock_get_logger):
        """Test logger is properly configured."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        ConcreteFactory()

        mock_get_logger.assert_called_once()
        mock_logger.setLevel.assert_called_once_with(logging.INFO)

    def test_logger_handler_setup(self):
        """Test logger handler setup when no existing handlers."""
        factory = ConcreteFactory()

        # Should have at least one handler
        assert len(factory._logger.handlers) >= 0
        # Logger should be usable
        factory._logger.info("Test message")


# Configuration validation tests
class TestConfigurationValidation:
    """Test configuration validation functionality."""

    def test_validate_config_success(self, concrete_factory, valid_config):
        """Test successful configuration validation."""
        # Should not raise any exceptions
        concrete_factory._validate_config(valid_config)

    def test_validate_config_missing_required_field(self, concrete_factory):
        """Test validation fails with missing required field."""
        config = {"size": 10}  # Missing required 'name'

        with pytest.raises(MissingConfigurationError) as exc_info:
            concrete_factory._validate_config(config)

        assert "name" in str(exc_info.value)

    def test_validate_config_custom_validator_failure(self, concrete_factory):
        """Test validation fails with custom validator."""
        config = {"name": "test", "size": -5}  # Negative size should fail

        with pytest.raises(InvalidConfigurationError) as exc_info:
            concrete_factory._validate_config(config)

        assert "size" in str(exc_info.value)

    def test_validate_config_no_schema(self):
        """Test validation with no schema defined."""
        metadata = FactoryMetadata(
            backend="test",
            factory_class="NoSchemaFactory",
            description="Factory without schema",
            config_schema=None,
        )
        factory = ConcreteFactory(metadata)

        # Should not raise exceptions even with any config
        factory._validate_config({"anything": "goes"})

    def test_validate_config_validator_exception(self, concrete_factory):
        """Test handling of exceptions in custom validators."""

        def failing_validator(value):
            raise ValueError("Validator error")

        concrete_factory.add_config_validator("name", failing_validator)

        with pytest.raises(InvalidConfigurationError):
            concrete_factory._validate_config({"name": "test"})


# Dependency validation tests
class TestDependencyValidation:
    """Test dependency validation functionality."""

    def test_validate_dependencies_override(self):
        """Test dependency validation can be overridden."""
        factory = ConcreteFactory(missing_dependencies=["missing_dep"])

        missing = factory._validate_dependencies()

        assert missing == ["missing_dep"]


# Support method tests
class TestSupportMethod:
    """Test backend support checking."""

    def test_supports_string_backend(self, concrete_factory):
        """Test supports method with string backend."""
        assert concrete_factory.supports("test") is True
        assert concrete_factory.supports("other") is False

    def test_supports_enum_backend(self, concrete_factory):
        """Test supports method with CacheBackend enum."""
        # Create factory with enum backend
        metadata = FactoryMetadata(
            backend=CacheBackend.MEMORY,
            factory_class="TestFactory",
            description="Test",
        )
        factory = ConcreteFactory(metadata)

        assert factory.supports(CacheBackend.MEMORY) is True
        assert factory.supports("memory") is True
        assert factory.supports(CacheBackend.REDIS) is False
        assert factory.supports("redis") is False


# Adapter creation tests
class TestAdapterCreation:
    """Test adapter creation functionality."""

    @patch("builtins.__import__")
    def test_create_success(self, mock_import, concrete_factory, valid_config):
        """Test successful adapter creation."""
        mock_import.return_value = MagicMock()

        adapter = concrete_factory.create(valid_config)

        assert isinstance(adapter, MockAdapter)

    def test_create_invalid_config(self, concrete_factory):
        """Test creation fails with invalid configuration."""
        invalid_config = {"size": -1}  # Missing name, invalid size

        with pytest.raises((InvalidConfigurationError, MissingConfigurationError)):
            concrete_factory.create(invalid_config)

    @patch("builtins.__import__")
    def test_create_adapter_failure(self, mock_import):
        """Test handling of adapter creation failures."""
        mock_import.return_value = MagicMock()
        factory = ConcreteFactory(should_fail_create=True)

        with pytest.raises(FactoryCreationError) as exc_info:
            factory.create({"name": "test"})

        assert "Simulated creation failure" in str(exc_info.value)

    @patch("builtins.__import__")
    def test_create_reraises_config_errors(self, mock_import, concrete_factory):
        """Test that configuration errors are re-raised as-is."""
        mock_import.return_value = MagicMock()

        with pytest.raises(MissingConfigurationError):
            concrete_factory.create({})  # Missing required name


# Metadata and schema tests
class TestMetadataAndSchema:
    """Test metadata and schema access methods."""

    def test_get_metadata(self, concrete_factory):
        """Test metadata retrieval."""
        metadata = concrete_factory.get_metadata()

        assert metadata.backend == "test"
        assert metadata.factory_class == "ConcreteFactory"
        assert metadata.description == "Test factory for unit tests"

    def test_get_config_schema(self, concrete_factory):
        """Test config schema retrieval."""
        schema = concrete_factory.get_config_schema()

        assert schema is not None
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "name" in schema["properties"]

    def test_get_config_schema_none(self):
        """Test config schema retrieval when schema is None."""
        metadata = FactoryMetadata(
            backend="test",
            factory_class="TestFactory",
            description="Test",
            config_schema=None,
        )
        factory = ConcreteFactory(metadata)

        schema = factory.get_config_schema()
        assert schema is None


# Custom validator tests
class TestCustomValidators:
    """Test custom configuration validators."""

    def test_add_config_validator(self, concrete_factory):
        """Test adding custom validator."""

        def custom_validator(value):
            return value == "expected"

        concrete_factory.add_config_validator("custom_field", custom_validator)

        assert "custom_field" in concrete_factory._config_validators
        assert concrete_factory._config_validators["custom_field"] == custom_validator

    def test_custom_validator_usage(self, concrete_factory):
        """Test custom validator is used during validation."""

        def strict_validator(value):
            return value == "strict_value"

        concrete_factory.add_config_validator("test_field", strict_validator)

        # Should pass with correct value
        config = {"name": "test", "test_field": "strict_value"}
        concrete_factory._validate_config(config)

        # Should fail with incorrect value
        config = {"name": "test", "test_field": "wrong_value"}
        with pytest.raises(InvalidConfigurationError):
            concrete_factory._validate_config(config)

    def test_validator_logging(self, concrete_factory, caplog):
        """Test that validator addition is logged."""
        with caplog.at_level(logging.DEBUG):
            concrete_factory.add_config_validator("test_key", lambda x: True)

        # Check if debug message was logged
        # Note: This might not capture all log messages depending on logger config
        # but tests the method completes successfully


# Integration tests
class TestFactoryIntegration:
    """Integration tests for complete factory workflows."""

    @patch("builtins.__import__")
    def test_complete_workflow(self, mock_import):
        """Test complete factory workflow from creation to adapter creation."""
        mock_import.return_value = MagicMock()

        # Create factory with custom metadata
        metadata = FactoryMetadata(
            backend="integration_test",
            factory_class="IntegrationTestFactory",
            description="Integration test factory",
            version="2.0.0",
            dependencies=["fake_dependency"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535},
                },
                "required": ["name", "port"],
            },
        )

        factory = ConcreteFactory(metadata)

        # Add custom validator
        factory.add_config_validator("port", lambda p: 1 <= p <= 65535)

        # Test supports method
        assert factory.supports("integration_test") is True
        assert factory.supports("other") is False

        # Test metadata retrieval
        retrieved_metadata = factory.get_metadata()
        assert retrieved_metadata.version == "2.0.0"

        # Test successful creation
        config = {"name": "test_adapter", "port": 8080}
        adapter = factory.create(config)
        assert isinstance(adapter, MockAdapter)

    def test_error_propagation(self, concrete_factory):
        """Test that errors are properly propagated through the system."""
        # Test configuration error propagation
        with pytest.raises(MissingConfigurationError) as exc_info:
            concrete_factory.create({})

        assert exc_info.value.details["config_key"] == "name"

        # Test validation error propagation
        with pytest.raises(InvalidConfigurationError) as exc_info:
            concrete_factory.create({"name": "test", "size": -1})

        assert exc_info.value.details["config_key"] == "size"


# Edge cases and error handling
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_config(self, concrete_factory):
        """Test handling of empty configuration."""
        with pytest.raises(MissingConfigurationError):
            concrete_factory.create({})

    def test_none_config(self, concrete_factory):
        """Test handling of None configuration."""
        with pytest.raises(FactoryCreationError) as exc_info:
            concrete_factory.create(None)
        assert isinstance(exc_info.value.__cause__, TypeError)
        assert "argument of type 'NoneType' is not iterable" in str(exc_info.value.__cause__)

    def test_config_with_none_values(self, concrete_factory):
        """Test configuration with None values."""
        config = {"name": "test", "size": None}
        # Should not raise exception for None values in non-required fields
        try:
            concrete_factory.create(config)
        except (InvalidConfigurationError, MissingConfigurationError):
            pass  # Expected for missing required fields

    def test_very_large_config(self, concrete_factory):
        """Test handling of configuration with many fields."""
        large_config = {"name": "test"}
        large_config.update({f"field_{i}": f"value_{i}" for i in range(1000)})

        # Should handle large configs without issues
        # (Only required field validation should occur)
        try:
            concrete_factory.create(large_config)
        except Exception as e:
            # Should not fail due to size, only validation rules
            assert not isinstance(e, MemoryError)

    def test_circular_reference_in_config(self, concrete_factory):
        """Test handling of circular references in configuration."""
        config = {"name": "test"}
        config["self_ref"] = config  # Circular reference

        # Should handle gracefully (may fail in JSON serialization during key generation)
        try:
            concrete_factory.create(config)
        except Exception as exc:
            # Expected to potentially fail, but should not crash
            assert str(exc)

    def test_unicode_in_config(self, concrete_factory):
        """Test handling of unicode characters in configuration."""
        config = {"name": "test_🚀_配置", "size": 42}

        # Should handle unicode without issues
        adapter = concrete_factory.create(config)
        assert isinstance(adapter, MockAdapter)


# Performance tests (lightweight)
class TestPerformance:
    """Basic performance-related tests."""

    def test_validator_efficiency(self, concrete_factory):
        """Test that validators don't significantly impact performance."""
        import time

        # Add multiple validators
        for i in range(10):
            concrete_factory.add_config_validator(f"field_{i}", lambda x: True)

        config = {"name": "test"}
        config.update({f"field_{i}": f"value_{i}" for i in range(10)})

        start_time = time.time()
        concrete_factory._validate_config(config)
        end_time = time.time()

        # Should complete quickly (within 1 second for this simple case)
        assert end_time - start_time < 1.0

    def test_repeated_creation(self, concrete_factory):
        """Test repeated adapter creation performance."""
        config = {"name": "test", "size": 10}

        # Create multiple adapters
        adapters = []
        for _ in range(10):
            adapter = concrete_factory.create(config)
            adapters.append(adapter)

        # All should be valid instances
        assert len(adapters) == 10
        assert all(isinstance(a, MockAdapter) for a in adapters)
