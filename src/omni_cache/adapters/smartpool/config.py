"""
Configuration module for the SmartPool adapter in omni-cache.

This module defines the `SmartPoolAdapterConfig` dataclass, which holds all
the necessary settings for creating and managing a SmartPool adapter instance.
It includes parameters for pool sizing, memory management, performance tuning,
and factory function configuration.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any, TypeVar

from omni_cache.adapters.base import AdapterConfig
from omni_cache.core.interfaces.enum_dataclasses import CacheBackend

T = TypeVar("T")


@dataclass
class SmartPoolAdapterConfig(AdapterConfig):
    """Enhanced configuration for SmartPool adapter."""

    # Basic pool configuration
    factory_function: Callable[..., Any] | None = None
    factory_validate_function: Callable[..., Any] | None = None
    factory_args: tuple = field(default_factory=tuple)
    factory_kwargs: dict = field(default_factory=dict)

    # Pool sizing
    initial_size: int = 5
    max_size: int = 20
    min_size: int = 2
    max_size_per_key: int | None = None

    # Memory management
    memory_preset: str | None = None  # "HIGH_THROUGHPUT", "LOW_MEMORY", "BALANCED"
    max_age_seconds: int = 300
    cleanup_interval: int = 30
    enable_background_cleanup: bool = True
    backend: str | CacheBackend = CacheBackend.SMARTPOOL.value
    # Performance and tuning
    enable_performance_metrics: bool = True
    enable_auto_tuning: bool = True
    auto_tuning_interval: int = 60

    # Object management
    auto_wrap_objects: bool = True

    # Additional configuration for factory functions
    extra_config: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Normalize derived defaults after dataclass initialization."""
        if self.max_size_per_key is None:
            # By default, allow full pool capacity per key unless explicitly constrained.
            self.max_size_per_key = self.max_size

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary, handling dataclass properly."""
        return asdict(self)
