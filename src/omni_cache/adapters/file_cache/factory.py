"""
This module defines the factory for creating FileCacheAdapter instances.

It provides a concrete implementation of the AbstractFactory, allowing for the
creation and configuration of file-based cache adapters.
"""

from typing import Any

from omni_cache.adapters.file_cache.file_cache import FileCacheAdapter, FileCacheConfig
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import CacheBackend


class FileCacheFactory(AbstractFactory[FileCacheAdapter]):
    """Factory for creating FileCacheAdapter instances."""

    def _get_default_metadata(self) -> FactoryMetadata:
        """
        Returns the default metadata for the FileCacheFactory.
        """
        return FactoryMetadata(
            backend=CacheBackend.FILE_CACHE.value,
            factory_class=self.__class__.__name__,
            adapter_types=[FileCacheAdapter.__name__],
            description="Factory for File-system based cache adapter.",
            dependencies=[],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "file_cache"},
                    "cache_dir": {"type": "string", "default": "omni_cache_files"},
                    "log_level": {"type": "string", "default": "INFO"},
                    "enable_stats": {"type": "boolean", "default": True},
                },
                "required": ["cache_dir"],
            },
        )

    def _create_adapter(self, config: dict[str, Any]) -> FileCacheAdapter:
        """
        Create a FileCacheAdapter instance.

        Args:
            config: Configuration dictionary for the adapter.

        Returns:
            Configured FileCacheAdapter instance.
        """
        return FileCacheAdapter(FileCacheConfig(**config))

    def _setup_config_validators(self) -> None:
        """
        Set up configuration validators for the FileCacheFactory.
        """
