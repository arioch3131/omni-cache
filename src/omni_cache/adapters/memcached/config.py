"""
Memcached adapter configuration for omni-cache.
"""

from dataclasses import dataclass

from omni_cache.adapters.base import AdapterConfig
from omni_cache.core.interfaces import CacheBackend


@dataclass
class MemcachedAdapterConfig(AdapterConfig):
    """Configuration specific to the Memcached adapter."""

    # Connection settings
    host: str = "localhost"
    port: int = 11211
    connect_timeout: float = 1.0
    timeout: float = 2.0
    no_delay: bool = True
    ignore_exc: bool = False

    # Serialization settings
    serialization_method: str = "json"  # "json", "string"
    encoding: str = "utf-8"

    # Key settings
    key_prefix: str = ""
    key_separator: str = ":"

    # Cache behavior
    default_ttl: int | None = None
    retry_on_error: bool = True
    retry_backoff_factor: float = 1.0
    health_check_key: str = "_omni_cache_health_check"

    def __post_init__(self) -> None:
        """Set backend enum for this configuration."""
        self.backend = CacheBackend.MEMCACHED
