"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

import logging
import threading
from typing import Any, TypeVar, cast

from omni_cache.adapters.file_cache.factory import FileCacheFactory
from omni_cache.adapters.memcached.factory import MemcachedAdapterFactory
from omni_cache.adapters.memory.factory import MemoryAdapterFactory
from omni_cache.adapters.redis.factory import RedisAdapterFactory
from omni_cache.adapters.smartpool.factory import SmartPoolAdapterFactory
from omni_cache.core.exceptions import (
    FactoryNotFoundError,
    FactoryRegistrationError,
)
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

from .abstract_factory import AbstractFactory
from .factory_metadata import FactoryMetadata

# Type variables
T = TypeVar("T", bound=AdapterInterface)


class FactoryRegistry:
    """
    Thread-safe registry for managing adapter factories.

    Provides factory registration, discovery, and adapter creation services.
    """

    def __init__(self) -> None:
        """Initialize the factory registry."""
        self._factories: dict[str, AbstractFactory] = {}
        self._metadata_cache: dict[str, FactoryMetadata] = {}
        self._lock = threading.RLock()
        self._logger = logging.getLogger("omni_cache.factory.registry")

        # Auto-register built-in factories
        self._register_builtin_factories()

    def _register_builtin_factories(self) -> None:
        """Register built-in factories."""
        try:
            # Always register memory factory (no dependencies)
            self.register(MemoryAdapterFactory())

            # Register FileCache factory (no dependencies)
            self.register(FileCacheFactory())

            # Register Redis factory if dependencies available
            try:
                self.register(RedisAdapterFactory())
            except ImportError:
                self._logger.debug("Redis not available, skipping Redis factory registration")

            # Register Memcached factory if dependencies available
            try:
                self.register(MemcachedAdapterFactory())
            except ImportError:
                self._logger.debug(
                    "Memcached not available, skipping Memcached factory registration"
                )

            # Register AdaptiveMemoryPool factory if available
            try:
                self.register(SmartPoolAdapterFactory())
            except ImportError:
                self._logger.debug(
                    "AdaptiveMemoryPool not available, skipping factory registration"
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.warning("Error registering built-in factories: %s", e)

    def register(self, factory: AbstractFactory) -> None:
        """
        Register a factory.

        Args:
            factory: Factory instance to register

        Raises:
            FactoryRegistrationError: If registration fails
        """
        try:
            metadata = factory.get_metadata()
            backend = str(metadata.backend)

            with self._lock:
                if backend in self._factories:
                    self._logger.warning("Replacing existing factory for backend: %s", backend)

                self._factories[backend] = factory
                self._metadata_cache[backend] = metadata

            self._logger.info("Registered factory for backend: %s", backend)

        except Exception as e:
            raise FactoryRegistrationError(
                getattr(factory, "_metadata", {}).get("backend", "unknown"), str(e), e
            ) from e

    def unregister(self, backend: str | CacheBackend) -> bool:
        """
        Unregister a factory.

        Args:
            backend: Backend type to unregister

        Returns:
            True if factory was registered and removed, False otherwise
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)

        with self._lock:
            factory_removed = self._factories.pop(backend_str, None) is not None
            self._metadata_cache.pop(backend_str, None)

        if factory_removed:
            self._logger.info("Unregistered factory for backend: %s", backend_str)

        return factory_removed

    def get_factory(self, backend: str | CacheBackend) -> AbstractFactory | None:
        """
        Get a factory by backend type.

        Args:
            backend: Backend type

        Returns:
            Factory instance or None if not found
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)

        with self._lock:
            return self._factories.get(backend_str)

    def list_backends(self) -> list[str]:
        """
        List all registered backend types.

        Returns:
            List of backend type strings
        """
        with self._lock:
            return list(self._factories.keys())

    def get_metadata(self, backend: str | CacheBackend) -> FactoryMetadata | None:
        """
        Get metadata for a backend.

        Args:
            backend: Backend type

        Returns:
            Factory metadata or None if not found
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)

        with self._lock:
            return self._metadata_cache.get(backend_str)

    def get_all_metadata(self) -> dict[str, FactoryMetadata]:
        """
        Get metadata for all registered factories.

        Returns:
            Dictionary mapping backend to metadata
        """
        with self._lock:
            return self._metadata_cache.copy()

    def create_adapter(
        self, backend: str | CacheBackend, config: dict[str, Any]
    ) -> AdapterInterface:
        """
        Create an adapter using the registered factory.

        Args:
            backend: Backend type
            config: Configuration for the adapter

        Returns:
            Created adapter instance

        Raises:
            FactoryNotFoundError: If no factory registered for backend
            FactoryCreationError: If adapter creation fails
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)

        factory = self.get_factory(backend_str)
        if factory is None:
            available_backends = self.list_backends()
            raise FactoryNotFoundError(backend_str, available_backends)

        return cast(AdapterInterface, factory.create(config))

    def supports_backend(self, backend: str | CacheBackend) -> bool:
        """
        Check if a backend is supported.

        Args:
            backend: Backend type to check

        Returns:
            True if backend is supported, False otherwise
        """
        return self.get_factory(backend) is not None

    def get_config_schema(self, backend: str | CacheBackend) -> dict[str, Any] | None:
        """
        Get configuration schema for a backend.

        Args:
            backend: Backend type

        Returns:
            Configuration schema or None if not found
        """
        factory = self.get_factory(backend)
        return factory.get_config_schema() if factory else None

    def discover_adapters(self) -> dict[str, list[str]]:
        """
        Discover available adapter types by backend.

        Returns:
            Dictionary mapping backend to list of adapter types
        """
        result = {}

        with self._lock:
            for backend, metadata in self._metadata_cache.items():
                result[backend] = metadata.adapter_types.copy()

        return result
