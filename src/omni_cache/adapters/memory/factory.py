"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

from typing import Any, TypeVar

from omni_cache.core.exceptions.factory_exceptions import FactoryCreationError
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

try:
    from .memory import MemoryAdapter, MemoryAdapterConfig

    MEMORY_ADAPTER_AVAILABLE = True
except ImportError:
    MEMORY_ADAPTER_AVAILABLE = False


# Type variables
T = TypeVar("T", bound=AdapterInterface)


class MemoryAdapterFactory(AbstractFactory):
    """Factory for creating memory adapters."""

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=CacheBackend.MEMORY,
            factory_class="MemoryAdapterFactory",
            description="Factory for in-memory cache adapters",
            version="2.0.0",
            dependencies=[],  # No external dependencies
            adapter_types=["cache"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "memory"},
                    "max_size": {"type": ["integer", "null"], "minimum": 1},
                    "default_ttl": {"type": ["number", "null"], "minimum": 0},
                    "eviction_policy": {
                        "type": "string",
                        "enum": ["lru", "fifo", "random"],
                        "default": "lru",
                    },
                    "cleanup_interval": {"type": "number", "minimum": 1, "default": 60},
                },
                "required": [],
            },
        )

    def _setup_config_validators(self) -> None:
        """Setup custom validators for memory adapter configuration."""

        def validate_eviction_policy(value: str) -> bool:
            return value in ["lru", "fifo", "random"]

        def validate_positive_number(value: int | float) -> bool:
            return isinstance(value, (int, float)) and value > 0

        self.add_config_validator("eviction_policy", validate_eviction_policy)
        self.add_config_validator("max_size", lambda x: x is None or (isinstance(x, int) and x > 0))
        self.add_config_validator("cleanup_interval", validate_positive_number)

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        """Create a memory adapter instance."""
        if MEMORY_ADAPTER_AVAILABLE:
            # Convert config to MemoryAdapterConfig
            adapter_config = MemoryAdapterConfig(**config)
            return MemoryAdapter(adapter_config)

        backend = self._metadata.backend
        if isinstance(backend, CacheBackend):
            backend = backend.value

        raise FactoryCreationError(backend, config, Exception("Memory adapter not available"))
