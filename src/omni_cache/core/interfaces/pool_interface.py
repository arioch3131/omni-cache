"""Interface for object pool operations."""

from abc import ABC, abstractmethod
from collections.abc import Generator
from contextlib import contextmanager
from typing import (
    Generic,
    TypeVar,
)

from .base_pool import _sync_borrow_logic

# pylint: disable=duplicate-code

# Type variables
T = TypeVar("T")


class PoolInterface(ABC, Generic[T]):
    """
    Abstract interface for object pool operations.

    This interface defines the contract for object pooling backends.
    """

    @abstractmethod
    def get(self, timeout: float | None = None) -> T | None:
        """
        Get an object from the pool.

        Args:
            timeout: Maximum time to wait for an object (None for no timeout)

        Returns:
            An object from the pool, or None if timeout/unavailable
        """
        raise NotImplementedError

    @abstractmethod
    def put(self, obj: T, timeout: float | None = None) -> bool:
        """
        Return an object to the pool.

        Args:
            obj: The object to return to the pool
            timeout: Maximum time to wait to return object (None for no expiration)

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def clear(self) -> bool:
        """
        Clear all objects from the pool.

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def size(self) -> int:
        """
        Get the current number of objects in the pool.

        Returns:
            Number of objects currently in the pool
        """
        raise NotImplementedError

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Check if the pool is empty.

        Returns:
            True if pool is empty, False otherwise
        """
        raise NotImplementedError

    @contextmanager
    def borrow(self, timeout: float | None = None) -> Generator[T, None, None]:
        """
        Context manager for borrowing an object from the pool.

        Args:
            timeout: Maximum time to wait for an object

        Yields:
            An object from the pool

        Raises:
            RuntimeError: If no object available within timeout
        """
        with _sync_borrow_logic(self.get, self.put, timeout) as obj:
            yield obj
