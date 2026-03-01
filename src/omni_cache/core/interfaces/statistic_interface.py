"""Interfaces for cache and pool adapters."""

from abc import ABC, abstractmethod
from typing import (
    TypeVar,
)

from .enum_dataclasses import CacheStats, PoolStats

# pylint: disable=duplicate-code

# Type variables
T = TypeVar("T")


class StatisticsInterface(ABC):
    """Interface for components that provide statistics."""

    @abstractmethod
    def get_stats(self) -> CacheStats | PoolStats | None:
        """
        Get current statistics.

        Returns:
            Statistics object with current metrics
        """
        raise NotImplementedError

    @abstractmethod
    def reset_stats(self) -> bool:
        """
        Reset all statistics to zero.

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError
