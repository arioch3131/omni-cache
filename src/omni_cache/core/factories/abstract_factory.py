"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, TypeVar

from omni_cache.core.exceptions import (
    FactoryCreationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
    FactoryInterface,
)

from .factory_metadata import FactoryMetadata

# Type variables
T = TypeVar("T", bound=AdapterInterface)


class AbstractFactory(FactoryInterface[T], ABC):
    """
    Abstract base class for all adapter factories.

    Provides common functionality including configuration validation,
    dependency checking, and error handling.
    """

    def __init__(self, metadata: FactoryMetadata | None = None):
        """
        Initialize the factory.

        Args:
            metadata: Factory metadata information
        """
        self._metadata = metadata or self._get_default_metadata()
        self._logger = self._setup_logger()
        self._config_validators: dict[str, Callable[[Any], bool]] = {}
        self._setup_config_validators()

        self._logger.info("Initialized %s factory", self.__class__.__name__)

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for the factory."""
        logger = logging.getLogger(f"omni_cache.factory.{self.__class__.__name__.lower()}")
        logger.setLevel(logging.INFO)
        logger.propagate = True  # Ensure propagation to root logger
        return logger

    @abstractmethod
    def _get_default_metadata(self) -> FactoryMetadata:
        """Get default metadata for this factory. Subclasses must implement."""
        raise NotImplementedError

    @abstractmethod
    def _create_adapter(self, config: dict[str, Any]) -> T:
        """Create the actual adapter instance. Subclasses must implement."""
        raise NotImplementedError

    def _setup_config_validators(self) -> None:
        """Setup configuration validators. Subclasses must implement."""
        raise NotImplementedError

    def _validate_dependencies(self) -> list[str]:
        """
        Validate that all required dependencies are available.

        Returns:
            List of missing dependencies
        """
        missing_deps = []

        for dep in self._metadata.dependencies:
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(dep)

        return missing_deps

    def _validate_config(self, config: dict[str, Any]) -> None:
        """
        Validate configuration against schema and custom validators.

        Args:
            config: Configuration to validate

        Raises:
            InvalidConfigurationError: If configuration is invalid
            MissingConfigurationError: If required configuration is missing
        """
        # Check required fields if schema is defined
        if self._metadata.config_schema:
            required_fields = self._metadata.config_schema.get("required", [])
            for _field in required_fields:
                if _field not in config:
                    raise MissingConfigurationError(_field, self.__class__.__name__)

        # Run custom validators
        for key, validator in self._config_validators.items():
            if key in config:
                try:
                    if not validator(config[key]):
                        raise InvalidConfigurationError(
                            key, config[key], expected_type=None, valid_values=None
                        )
                except Exception as e:
                    if isinstance(e, (InvalidConfigurationError, MissingConfigurationError)):
                        raise
                    raise InvalidConfigurationError(key, config[key]) from e

    def supports(self, backend: str | CacheBackend) -> bool:
        """
        Check if this factory supports the given backend.

        Args:
            backend: Backend type to check

        Returns:
            True if supported, False otherwise
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)
        return backend_str == self._metadata.backend

    def create(self, config: dict[str, Any]) -> T:
        """
        Create an adapter instance with the given configuration.

        Args:
            config: Configuration dictionary for the adapter

        Returns:
            Configured adapter instance

        Raises:
            FactoryCreationError: If adapter creation fails
        """
        try:
            # Validate dependencies
            missing_deps = self._validate_dependencies()
            if missing_deps:
                raise FactoryCreationError(
                    str(self._metadata.backend),
                    config,
                    Exception(f"Missing dependencies: {missing_deps}"),
                )

            # Validate configuration
            self._validate_config(config)

            # Create adapter
            self._logger.info("Creating adapter for backend: %s", self._metadata.backend)
            adapter = self._create_adapter(config)

            self._logger.info("Successfully created adapter: %s", type(adapter).__name__)
            return adapter

        except (InvalidConfigurationError, MissingConfigurationError):
            # Re-raise configuration errors as-is
            raise
        except Exception as e:
            self._logger.error("Failed to create adapter: %s", e)
            raise FactoryCreationError(str(self._metadata.backend), config, e) from e

    def get_metadata(self) -> FactoryMetadata:
        """Get factory metadata."""
        return self._metadata

    def get_config_schema(self) -> dict[str, Any] | None:
        """Get configuration schema for this factory."""
        return self._metadata.config_schema

    def add_config_validator(self, key: str, validator: Callable[[Any], bool]) -> None:
        """
        Add a custom configuration validator.

        Args:
            key: Configuration key to validate
            validator: Validation function that returns True if valid
        """
        self._config_validators[key] = validator
        self._logger.debug("Added validator for config key: %s", key)
