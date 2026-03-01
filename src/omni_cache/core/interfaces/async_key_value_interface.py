"""Asynchronous interface for key-value cache operations."""

from abc import ABC, abstractmethod
from typing import (
    Generic,
    TypeVar,
)

# pylint: disable=duplicate-code

# Type variables
K = TypeVar("K")  # Key type
V = TypeVar("V")  # Value type


class AsyncKeyValueInterface(ABC, Generic[K, V]):
    """Async version of KeyValueInterface for async backends."""

    @abstractmethod
    async def get(self, key: K, default: V | None = None) -> V | None:
        """Async version of get."""
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:
        """Async version of set."""
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: K) -> bool:
        """Async version of delete."""
        raise NotImplementedError

    @abstractmethod
    async def exists(self, key: K) -> bool:
        """Async version of exists."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self) -> bool:
        """Async version of clear."""
        raise NotImplementedError

    @abstractmethod
    async def keys(self) -> list[K]:
        """Async version of keys."""
        raise NotImplementedError

    @abstractmethod
    async def size(self) -> int:
        """Async version of size."""
        raise NotImplementedError
