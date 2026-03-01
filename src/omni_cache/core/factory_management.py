"""Factory Management."""

import logging
from typing import Any

from omni_cache.core.exceptions import ConfigurationError
from omni_cache.core.interfaces import AdapterInterface, CacheBackend, FactoryInterface


class AdapterFactoryManager:
    """Adapter Factory Manager."""

    def __init__(self, logger: logging.Logger) -> None:
        """
        Init

        Args:
            logger (logging.Logger): Logger

        Returns:
            None
        """
        self._logger = logger
        self._factories: dict[str, FactoryInterface[AdapterInterface]] = {}

    def register_factory(self, backend: str | CacheBackend, factory: FactoryInterface) -> None:
        """
        Register factory.

        Args:
            backend (Union[str, CacheBackend]): backend
            factory (FactoryInterface): A factory

        Returns:
            None
        """
        backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)
        self._factories[backend_str] = factory
        self._logger.info("Registered factory for backend: %s", backend_str)

    def create_adapter(
        self, name: str, backend: str | CacheBackend, config: dict[str, Any] | None = None
    ) -> AdapterInterface:
        """
        Create Adapter.

        Args:
            backend (Union[str, CacheBackend]): Backend
            config (Optional[Dict[str, Any]]): The config dict

        Returns:
            An Adpater Interface.
        """
        try:
            backend_str = backend.value if isinstance(backend, CacheBackend) else str(backend)

            if backend_str not in self._factories:
                raise ConfigurationError(f"No factory registered for backend: {backend_str}")

            factory = self._factories[backend_str]
            adapter = factory.create(config or {})
            return adapter

        except Exception as e:
            self._logger.error("Failed to create adapter %s: %s", name, e)
            raise  # Re-raise to be handled by CacheManager
