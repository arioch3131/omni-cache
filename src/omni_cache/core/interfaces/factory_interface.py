"""Interfaces for cache and pool adapters."""

from abc import ABC, abstractmethod
from typing import (
    Any,
    Generic,
    TypeVar,
)

from .enum_dataclasses import CacheBackend

# pylint: disable=duplicate-code

# Type variables
T = TypeVar("T")


class FactoryInterface(ABC, Generic[T]):
    """Interface for creating adapter instances."""

    @abstractmethod
    def create(self, config: dict[str, Any]) -> T:
        """
        Create an adapter instance.

        Args:
            config: Configuration dictionary for the adapter

        Returns:
            Configured adapter instance
        """
        raise NotImplementedError

    @abstractmethod
    def supports(self, backend: str | CacheBackend) -> bool:
        """
        Check if this factory supports the given backend.

        Args:
            backend: Backend type to check

        Returns:
            True if supported, False otherwise
        """
        raise NotImplementedError
