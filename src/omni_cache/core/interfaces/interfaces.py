"""
Core interfaces for omni-cache.

This module defines the abstract base classes that establish contracts
for all components in the omni-cache system.
"""

from typing import (
    Any,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from .async_key_value_interface import AsyncKeyValueInterface
from .async_pool_interface import AsyncPoolInterface
from .key_value_interface import KeyValueInterface
from .pool_interface import PoolInterface

# Type variables
T = TypeVar("T")
K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


@runtime_checkable
class Serializable(Protocol):
    """Protocol for objects that can be serialized."""

    def serialize(self) -> bytes:
        """Serialize the object to bytes."""
        raise NotImplementedError

    @classmethod
    def deserialize(cls, data: bytes) -> "Serializable":
        """Deserialize bytes back to object."""
        raise NotImplementedError


@runtime_checkable
class Configurable(Protocol):
    """Protocol for configurable components."""

    def configure(self, config: dict[str, Any]) -> bool:
        """Configure the component with given settings."""
        raise NotImplementedError

    def get_config(self) -> Any:
        """Get current configuration."""
        raise NotImplementedError


# Convenience type aliases
CacheAdapter = KeyValueInterface | AsyncKeyValueInterface
PoolAdapter = PoolInterface | AsyncPoolInterface
AnyAdapter = CacheAdapter | PoolAdapter
