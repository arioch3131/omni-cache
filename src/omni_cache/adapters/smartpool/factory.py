"""
Factory system for SmartPool adapters.

This module provides factory functionality for creating and managing
SmartPool adapters dynamically.
"""

from typing import Any, TypeVar

from omni_cache.core.exceptions import (
    FactoryCreationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

try:
    from .smartpool import SmartPoolAdapter, SmartPoolAdapterConfig

    SMARTPOOL_ADAPTER_AVAILABLE = True
except ImportError:
    SMARTPOOL_ADAPTER_AVAILABLE = False

# Type variables
T = TypeVar("T", bound=AdapterInterface)


class SmartPoolAdapterFactory(AbstractFactory):
    """Factory for creating SmartPool adapters."""

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=CacheBackend.SMARTPOOL,
            factory_class="SmartPoolAdapterFactory",
            description="Factory for SmartPool adapters",  # Correction: SmartPool avec majuscule
            version="1.2.0",
            dependencies=["smartpool"],
            adapter_types=["pool"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "adaptive"},
                    "initial_size": {"type": "integer", "minimum": 0, "default": 5},
                    "max_size": {"type": "integer", "minimum": 1, "default": 20},
                    "min_size": {"type": "integer", "minimum": 0, "default": 2},
                    "growth_factor": {"type": "number", "minimum": 1.0, "default": 1.5},
                    "shrink_threshold": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5,
                    },
                    "factory_function": {"type": "string"},  # Name of factory function
                },
                "required": ["factory_function"],
            },
        )

    def _setup_config_validators(self) -> None:
        """Setup custom validators for SmartPoolAdapterConfig."""

        def validate_positive_integer(value: Any) -> bool:
            return isinstance(value, int) and value > 0

        def validate_non_negative_integer(value: Any) -> bool:
            return isinstance(value, int) and value >= 0

        def validate_callable(value: Any) -> bool:
            return callable(value)

        self.add_config_validator("initial_size", validate_non_negative_integer)
        self.add_config_validator("max_size", validate_positive_integer)
        self.add_config_validator("min_size", validate_non_negative_integer)
        self.add_config_validator("factory_function", validate_callable)

    def _validate_config(self, config: dict[str, Any]) -> None:
        """Extended validation for size relationships."""
        super()._validate_config(config)

        # Validate size relationships (only if all required values are present)
        initial = config.get("initial_size", 5)
        max_size = config.get("max_size", 20)
        min_size = config.get("min_size", 2)

        if not min_size <= initial <= max_size:
            raise InvalidConfigurationError(
                config_key="size_config",
                config_value=f"min({min_size}) <= initial({initial}) <= max({max_size})",
                expected_type=None,
                valid_values=None,
            )

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        """Create a SmartPool adapter instance."""
        if not SMARTPOOL_ADAPTER_AVAILABLE:
            raise FactoryCreationError(
                backend="smartpool",
                adapter_config=config,
                cause=ImportError("SmartPool library is not installed."),
            )

        try:
            # Validate configuration first
            self._validate_config(config)

            # Convert config to SmartPoolAdapterConfig
            adapter_config = SmartPoolAdapterConfig(**config)

            # Create the adapter
            return SmartPoolAdapter(adapter_config)

        except (InvalidConfigurationError, MissingConfigurationError):
            # Re-raise configuration errors as-is (don't wrap them)
            raise
        except Exception as e:
            # Wrap other exceptions in FactoryCreationError
            raise FactoryCreationError(backend="smartpool", adapter_config=config, cause=e) from e

    def supports(self, backend: CacheBackend | str) -> bool:
        """Check if this factory supports the given backend."""
        if hasattr(backend, "value"):
            return str(backend.value) == str(CacheBackend.SMARTPOOL.value)
        return backend == "smartpool"
