"""
Memory adapter implementation for omni-cache.

This module provides a simple in-memory cache adapter using Python dictionaries.
Supports TTL (time-to-live) functionality and provides a reference implementation
for other adapters.
"""

import time
from dataclasses import dataclass, field
from typing import Any, TypeVar

from omni_cache.adapters.base import AdapterConfig
from omni_cache.core.interfaces import CacheBackend

# Type variables
K = TypeVar("K")
V = TypeVar("V")


@dataclass
class MemoryAdapterConfig(AdapterConfig):
    """Configuration specific to the memory adapter."""

    max_size: int | None = None  # Maximum number of items (None = unlimited)
    default_ttl: float | None = None  # Default TTL in seconds
    cleanup_interval: float = 60.0  # How often to clean expired items (seconds)
    eviction_policy: str = "lru"  # Eviction policy: "lru", "fifo", "random"

    def __post_init__(self) -> None:
        """Set the backend to memory after initialization."""
        self.backend = CacheBackend.MEMORY


@dataclass
class CacheItem:
    """Internal representation of a cached item."""

    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self, now: float | None = None) -> bool:
        """Check if the item has expired."""
        if self.expires_at is None:
            return False

        if now is None:
            now = time.time()

        return now >= self.expires_at

    def access(self) -> None:
        """Mark the item as accessed."""
        self.access_count += 1
        self.last_accessed = time.time()
