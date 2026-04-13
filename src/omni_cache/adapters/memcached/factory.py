"""
Factory for Memcached adapters.
"""

from typing import Any, TypeVar

from omni_cache.core.exceptions import FactoryCreationError
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import AdapterInterface, CacheBackend

try:
    from .config import MemcachedAdapterConfig
    from .memcached import MemcachedAdapter

    MEMCACHED_ADAPTER_AVAILABLE = True
except ImportError:
    MEMCACHED_ADAPTER_AVAILABLE = False

T = TypeVar("T", bound=AdapterInterface)


class MemcachedAdapterFactory(AbstractFactory):
    """Factory for creating Memcached adapters."""

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=CacheBackend.MEMCACHED,
            factory_class="MemcachedAdapterFactory",
            description="Factory for Memcached cache adapters",
            version="2.0.0",
            dependencies=["pymemcache"],
            adapter_types=["cache"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "memcached"},
                    "host": {"type": "string", "default": "localhost"},
                    "port": {"type": "integer", "minimum": 1, "maximum": 65535, "default": 11211},
                    "connect_timeout": {"type": "number", "minimum": 0, "default": 1.0},
                    "timeout": {"type": "number", "minimum": 0, "default": 2.0},
                    "default_ttl": {"type": ["integer", "null"], "minimum": 0},
                    "serialization_method": {
                        "type": "string",
                        "enum": ["json", "string"],
                        "default": "json",
                    },
                    "key_prefix": {"type": "string", "default": ""},
                },
                "required": [],
            },
        )

    def _setup_config_validators(self) -> None:
        """Setup custom validators for Memcached adapter configuration."""

        def validate_port(port: int) -> bool:
            return isinstance(port, int) and 1 <= port <= 65535

        def validate_serialization_method(value: str) -> bool:
            return value in ["json", "string"]

        self.add_config_validator("port", validate_port)
        self.add_config_validator("serialization_method", validate_serialization_method)

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        """Create a Memcached adapter instance."""
        if MEMCACHED_ADAPTER_AVAILABLE:
            adapter_config = MemcachedAdapterConfig(**config)
            return MemcachedAdapter(adapter_config)

        backend = self._metadata.backend
        if isinstance(backend, CacheBackend):
            backend = backend.value

        raise FactoryCreationError(backend, config, Exception("Memcached adapter not available"))
