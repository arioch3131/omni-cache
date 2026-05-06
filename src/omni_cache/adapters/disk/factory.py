"""Factory for disk-backed adapters."""

from typing import Any

from omni_cache.core.exceptions.factory_exceptions import FactoryCreationError
from omni_cache.core.factories.abstract_factory import AbstractFactory
from omni_cache.core.factories.factory_metadata import FactoryMetadata
from omni_cache.core.interfaces import AdapterInterface, CacheBackend

from .config import DiskAdapterConfig
from .disk import DiskAdapter


class DiskAdapterFactory(AbstractFactory):
    """Factory for creating disk-backed cache adapters."""

    def _get_default_metadata(self) -> FactoryMetadata:
        return FactoryMetadata(
            backend=CacheBackend.DISK,
            factory_class="DiskAdapterFactory",
            description="Factory for disk-backed cache adapters (SQLite + files)",
            version="2.0.0",
            dependencies=[],
            adapter_types=["cache"],
            config_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "default": "disk"},
                    "cache_dir": {"type": "string", "default": "omni_cache_disk"},
                    "sqlite_path": {"type": ["string", "null"], "default": None},
                    "max_size_bytes": {"type": ["integer", "null"], "minimum": 1, "default": None},
                    "default_ttl": {"type": ["number", "null"], "minimum": 0},
                    "renew_on_hit": {"type": "boolean", "default": False},
                    "renew_threshold": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
                    "cleanup_interval_sec": {"type": "number", "minimum": 0.001, "default": 60},
                    "batch_flush_interval_sec": {
                        "type": "number",
                        "minimum": 0.001,
                        "default": 5,
                    },
                    "batch_flush_max_pending": {"type": "integer", "minimum": 1, "default": 1000},
                },
                "required": [],
            },
        )

    def _setup_config_validators(self) -> None:
        self.add_config_validator("cache_dir", lambda x: isinstance(x, str) and bool(x.strip()))
        self.add_config_validator("sqlite_path", lambda x: x is None or isinstance(x, str))
        self.add_config_validator(
            "max_size_bytes", lambda x: x is None or (isinstance(x, int) and x > 0)
        )
        self.add_config_validator(
            "default_ttl",
            lambda x: x is None or (isinstance(x, (int, float)) and x > 0),
        )
        self.add_config_validator(
            "renew_threshold",
            lambda x: isinstance(x, (int, float)) and 0 < float(x) <= 1,
        )
        self.add_config_validator(
            "cleanup_interval_sec",
            lambda x: isinstance(x, (int, float)) and float(x) > 0,
        )
        self.add_config_validator(
            "batch_flush_interval_sec",
            lambda x: isinstance(x, (int, float)) and float(x) > 0,
        )
        self.add_config_validator(
            "batch_flush_max_pending",
            lambda x: isinstance(x, int) and x > 0,
        )

    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:
        try:
            return DiskAdapter(DiskAdapterConfig(**config))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            backend = self._metadata.backend
            if isinstance(backend, CacheBackend):
                backend = backend.value
            raise FactoryCreationError(backend, config, exc) from exc
