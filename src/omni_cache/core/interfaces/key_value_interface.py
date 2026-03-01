"""Interface for key-value cache operations."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import (
    Generic,
    TypeVar,
)

K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


class KeyValueInterface(ABC, Generic[K, V]):
    """Abstract interface for key-value cache operations."""

    @abstractmethod
    def get(self, key: K, default: V | None = None) -> V | None:
        """Retrieve a value by key."""
        raise NotImplementedError

    @abstractmethod
    def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:
        """Store a key-value pair."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: K) -> bool:
        """Delete a key-value pair."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: K) -> bool:
        """Check if a key exists."""
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> bool:
        """Clear all key-value pairs."""
        raise NotImplementedError

    @abstractmethod
    def keys(self) -> Iterator[K]:
        """Get an iterator over all keys."""
        raise NotImplementedError

    @abstractmethod
    def size(self) -> int:
        """Get the number of key-value pairs."""
        raise NotImplementedError

    def get_many(self, keys: list[K]) -> dict[K, V | None]:
        """
        Retrieve multiple values by keys.

        Returns:
            Dictionary mapping keys to values (None for missing keys)
        """
        result = {}
        for key in keys:
            result[key] = self.get(key)
        return result

    def set_many(self, mapping: dict[K, V], ttl: int | float | None = None) -> dict[K, bool]:
        """
        Store multiple key-value pairs.

        Returns:
            Dictionary mapping keys to success status
        """
        result = {}
        for key, value in mapping.items():
            result[key] = self.set(key, value, ttl)
        return result

    def delete_many(self, keys: list[K]) -> dict[K, bool]:
        """
        Delete multiple keys.

        Returns:
            Dictionary mapping keys to deletion success status
        """
        result = {}
        for key in keys:
            result[key] = self.delete(key)
        return result
