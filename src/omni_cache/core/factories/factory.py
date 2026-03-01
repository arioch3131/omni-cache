"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

from .abstract_factory import AbstractFactory
from .factory_registry import FactoryRegistry

# Global factory registry instance
# pylint: disable=global-statement
_global_registry: FactoryRegistry | None = None  # pylint: disable=invalid-name
_global_registry_lock = threading.Lock()


def get_global_registry() -> FactoryRegistry:
    """
    Get the global FactoryRegistry instance.

    Returns:
        Global FactoryRegistry instance
    """
    global _global_registry

    if _global_registry is None:
        with _global_registry_lock:
            if _global_registry is None:
                _global_registry = FactoryRegistry()

    return _global_registry


def set_global_registry(registry: FactoryRegistry) -> None:
    """
    Set the global FactoryRegistry instance.

    Args:
        registry: FactoryRegistry instance to set as global
    """
    global _global_registry

    with _global_registry_lock:
        _global_registry = registry


@contextmanager
def temporary_factory(factory: AbstractFactory) -> Iterator[AbstractFactory]:
    """
    Context manager for temporarily registering a factory.

    Args:
        factory: Factory to register temporarily
    """
    registry = get_global_registry()
    metadata = factory.get_metadata()
    backend = metadata.backend

    # Save existing factory if any
    existing_factory = registry.get_factory(backend)

    try:
        # Register temporary factory
        registry.register(factory)
        yield factory
    finally:
        # Restore original factory or unregister
        if existing_factory:
            registry.register(existing_factory)
        else:
            registry.unregister(backend)


def create_adapter(
    backend: str | CacheBackend,
    config: dict[str, Any],
    registry: FactoryRegistry | None = None,
) -> AdapterInterface:
    """
    Convenience function to create an adapter.

    Args:
        backend: Backend type
        config: Configuration for the adapter
        registry: Factory registry to use (uses global if None)

    Returns:
        Created adapter instance
    """
    if registry is None:
        registry = get_global_registry()

    return registry.create_adapter(backend, config)


def list_available_backends(registry: FactoryRegistry | None = None) -> list[str]:
    """
    List all available backend types.

    Args:
        registry: Factory registry to use (uses global if None)

    Returns:
        List of available backend type strings
    """
    if registry is None:
        registry = get_global_registry()

    return registry.list_backends()
