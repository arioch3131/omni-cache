"""Asynchronous interface for object pool operations."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import (
    Generic,
    TypeVar,
)

from .base_pool import _async_borrow_logic

# pylint: disable=duplicate-code

# Type variables
T = TypeVar("T")


class AsyncPoolInterface(ABC, Generic[T]):
    """Async version of PoolInterface for async backends."""

    @abstractmethod
    async def get(self, timeout: float | None = None) -> T | None:
        """Async version of get."""
        raise NotImplementedError

    @abstractmethod
    async def put(self, obj: T, timeout: float | None = None) -> bool:
        """Async version of put."""
        raise NotImplementedError

    @abstractmethod
    async def clear(self) -> bool:
        """Async version of clear."""
        raise NotImplementedError

    @abstractmethod
    async def size(self) -> int:
        """Async version of size."""
        raise NotImplementedError

    @abstractmethod
    async def is_empty(self) -> bool:
        """Async version of is_empty."""
        raise NotImplementedError

    @asynccontextmanager
    async def borrow(self, timeout: float | None = None) -> AsyncGenerator[T, None]:
        """Async context manager for borrowing objects."""
        async with _async_borrow_logic(self.get, self.put, timeout) as obj:
            yield obj
