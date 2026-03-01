"""Memcached adapter package."""

from .config import MemcachedAdapterConfig
from .memcached import MemcachedAdapter

try:
    from pymemcache.client.base import Client
    from pymemcache.exceptions import MemcacheClientError, MemcacheServerError, MemcacheUnknownError

    HAS_MEMCACHED = True
except ImportError:
    HAS_MEMCACHED = False
    Client = type("Client", (), {})
    MemcacheClientError = Exception
    MemcacheServerError = Exception
    MemcacheUnknownError = Exception

__all__ = ["MemcachedAdapter", "MemcachedAdapterConfig"]
