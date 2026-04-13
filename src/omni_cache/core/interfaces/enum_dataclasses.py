"""Enums and dataclasses for omni-cache interfaces."""

from dataclasses import dataclass
from enum import Enum


class CacheBackend(Enum):
    """Enumeration of supported cache backends."""

    MEMORY = "memory"
    DISK = "disk"
    REDIS = "redis"
    MEMCACHED = "memcached"
    SMARTPOOL = "smartpool"
    CUSTOM = "custom"


@dataclass
# pylint: disable=too-many-instance-attributes
class CacheStats:
    """Statistics for cache operations."""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    size: int = 0
    max_size: int | None = None
    hit_rate: float = 0.0

    def update_hit_rate(self) -> None:
        """Update the hit rate based on hits and misses."""
        total = self.hits + self.misses
        self.hit_rate = self.hits / total if total > 0 else 0.0


@dataclass
# pylint: disable=too-many-instance-attributes
class PoolStats:
    """Statistics for pool operations."""

    created: int = 0
    borrowed: int = 0
    returned: int = 0
    destroyed: int = 0
    active: int = 0
    idle: int = 0
    max_size: int | None = None
    min_size: int | None = None
