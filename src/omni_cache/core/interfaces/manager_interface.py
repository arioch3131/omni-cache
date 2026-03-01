"""Interface for the main cache/pool manager."""

from abc import ABC, abstractmethod

from .adapter_interface import AdapterInterface

# pylint: disable=duplicate-code


class ManagerInterface(ABC):
    """Interface for the main cache/pool manager."""

    @abstractmethod
    def register_adapter(self, name: str, adapter: AdapterInterface) -> bool:
        """
        Register an adapter with the manager.

        Args:
            name: Name to register the adapter under
            adapter: The adapter instance

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError

    @abstractmethod
    def get_adapter(self, name: str) -> AdapterInterface | None:
        """
        Get a registered adapter by name.

        Args:
            name: Name of the adapter

        Returns:
            The adapter instance, or None if not found
        """
        raise NotImplementedError

    @abstractmethod
    def list_adapters(self) -> list[str]:
        """
        List all registered adapter names.

        Returns:
            List of adapter names
        """
        raise NotImplementedError

    @abstractmethod
    def remove_adapter(self, name: str) -> bool:
        """
        Remove an adapter from the manager.

        Args:
            name: Name of the adapter to remove

        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError
