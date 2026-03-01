"""This module provides an in-memory caching adapter for Omni-Cache."""

from .config import CacheItem, MemoryAdapterConfig
from .memory import MemoryAdapter

__all__ = ["CacheItem", "MemoryAdapterConfig", "MemoryAdapter"]
