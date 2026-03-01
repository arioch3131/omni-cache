"""
Factory system for omni-cache.

This module provides a comprehensive factory system for creating and managing
adapters dynamically. It includes factory registration, discovery, and
configuration validation.
"""

from dataclasses import dataclass, field
from typing import Any, TypeVar

from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
)

# Type variables
T = TypeVar("T", bound=AdapterInterface)


@dataclass
class FactoryMetadata:
    """Metadata about a factory."""

    backend: str | CacheBackend
    factory_class: str
    description: str
    version: str = "1.0.0"
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None
    adapter_types: list[str] = field(default_factory=list)  # ["cache", "pool"]

    def __post_init__(self) -> None:
        """Normalize backend to string."""
        if isinstance(self.backend, CacheBackend):
            self.backend = self.backend.value
