"""Disk adapter configuration for omni-cache."""

from dataclasses import dataclass

from omni_cache.adapters.base import AdapterConfig
from omni_cache.core.interfaces import CacheBackend


@dataclass
class DiskAdapterConfig(AdapterConfig):
    """Configuration specific to the disk-backed adapter."""

    cache_dir: str = "omni_cache_disk"
    sqlite_path: str | None = None
    default_ttl: float | None = None
    renew_on_hit: bool = False
    renew_threshold: float = 0.2
    cleanup_interval_sec: float = 60.0
    batch_flush_interval_sec: float = 5.0
    batch_flush_max_pending: int = 1000

    def __post_init__(self) -> None:
        self.backend = CacheBackend.DISK

        if not self.cache_dir:
            raise ValueError("cache_dir must not be empty")

        if self.default_ttl is not None and self.default_ttl <= 0:
            raise ValueError("default_ttl must be > 0 when set")

        if not (0 < self.renew_threshold <= 1):
            raise ValueError("renew_threshold must be in (0, 1]")

        if self.cleanup_interval_sec <= 0:
            raise ValueError("cleanup_interval_sec must be > 0")

        if self.batch_flush_interval_sec <= 0:
            raise ValueError("batch_flush_interval_sec must be > 0")

        if self.batch_flush_max_pending <= 0:
            raise ValueError("batch_flush_max_pending must be > 0")
