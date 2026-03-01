"""Interfaces for cache and pool adapters."""

from abc import ABC, abstractmethod
from typing import (
    Any,
    TypeVar,
)

# pylint: disable=duplicate-code

# Type variables
T = TypeVar("T")


class AdapterInterface(ABC):
    """
    Base interface for all cache/pool adapters.

    This interface combines common functionality needed by all adapters.
    """

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the backend.

        Returns:
            True if connection successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection to the backend.

        Returns:
            True if disconnection successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if adapter is connected to backend.

        Returns:
            True if connected, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a health check on the backend.

        Returns:
            True if backend is healthy, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def get_backend_info(self) -> dict[str, Any]:
        """
        Get information about the backend.

        Returns:
            Dictionary containing backend information
        """
        raise NotImplementedError
