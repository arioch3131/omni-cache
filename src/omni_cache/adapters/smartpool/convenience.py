"""
Convenience functions for creating SmartPool adapter instances.

This module provides helper functions to simplify the creation and configuration
of `SmartPoolAdapter` instances for common use cases, such as creating a
standard object pool or a dedicated connection pool.
"""

from collections.abc import Callable
from typing import Any, TypeVar

from .config import SmartPoolAdapterConfig
from .smartpool import SmartPoolAdapter

T = TypeVar("T")


# Convenience functions
# pylint: disable=too-many-positional-arguments
def create_smartpool_adapter(
    factory_function: Callable[..., T],
    validate_function: Callable[..., T],
    initial_size: int = 5,
    max_size: int = 20,
    min_size: int = 2,
    memory_preset: str | None = None,
    enable_auto_tuning: bool = False,
    **kwargs: Any,
) -> SmartPoolAdapter:
    """
    Convenience function to create a SmartPoolAdapter.

    Args:
        factory_function: Function to create objects
        initial_size: Initial number of objects in the pool
        max_size: Maximum number of objects in the pool
        min_size: Minimum number of objects in the pool
        memory_preset: Memory management preset ("HIGH_THROUGHPUT", "LOW_MEMORY", "BALANCED")
        enable_auto_tuning: Enable auto-tuning
        **kwargs: Additional configuration options

    Returns:
        Configured SmartPoolAdapter instance
    """
    config = SmartPoolAdapterConfig(
        factory_function=factory_function,
        factory_validate_function=validate_function,
        initial_size=initial_size,
        max_size=max_size,
        min_size=min_size,
        memory_preset=memory_preset,
        enable_auto_tuning=enable_auto_tuning,
        **kwargs,
    )

    return SmartPoolAdapter(config)


def create_connection_pool(
    connection_factory: Callable[..., T],
    pool_size: int = 10,
    max_pool_size: int = 20,
    **factory_kwargs: Any,
) -> SmartPoolAdapter:
    """
    Create a connection pool using SmartPool.

    Args:
        connection_factory: Function that creates new connections
        pool_size: Initial pool size
        max_pool_size: Maximum pool size
        **factory_kwargs: Additional arguments passed to the connection factory

    Returns:
        Configured SmartPoolAdapter for connection pooling
    """
    config = SmartPoolAdapterConfig(
        name="connection_pool",
        factory_function=connection_factory,
        factory_kwargs=factory_kwargs,
        initial_size=pool_size,
        max_size=max_pool_size,
        memory_preset="HIGH_THROUGHPUT",
        enable_auto_tuning=True,
        enable_performance_metrics=True,
    )

    return SmartPoolAdapter(config)
