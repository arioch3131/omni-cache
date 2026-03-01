"""
Simplified configuration system for omni-cache.

This module provides a streamlined configuration system with just the essential
features for managing global and adapter configurations.
"""

import json
import logging
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast

# Optional dependencies
try:
    import yaml  # type: ignore[import-untyped]

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from omni_cache.core.exceptions import ConfigurationError


class ConfigFormat(Enum):
    """Supported configuration file formats."""

    JSON = "json"
    YAML = "yaml"


@dataclass
class BaseConfig:
    """Base configuration class with common functionality."""

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if not key.startswith("_"):
                result[key] = value
        return result

    def update(self, updates: dict[str, Any]) -> None:
        """Update configuration with new values."""
        for key, value in updates.items():
            if hasattr(self, key):
                setattr(self, key, value)


@dataclass
class GlobalConfig(BaseConfig):
    """Global configuration for omni-cache."""

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Manager settings
    auto_connect_adapters: bool = True
    enable_global_stats: bool = True
    health_check_interval: float = 60.0

    # Cache defaults
    default_cache_adapter: str = "memory"
    default_cache_ttl: float | None = None

    # Pool defaults
    default_pool_adapter: str | None = None
    default_pool_timeout: float = 5.0

    # Routing
    enable_routing: bool = True
    namespace_separator: str = ":"
    fallback_adapter: str | None = None

    # Extra config for extensions
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterConfig(BaseConfig):
    """Configuration for individual adapters."""

    name: str = "default"
    backend: str = "memory"
    enabled: bool = True
    auto_connect: bool = True

    # Connection settings
    connection_timeout: float = 5.0
    max_retries: int = 3
    retry_delay: float = 0.1

    # Health monitoring
    health_check_interval: float = 30.0

    # Statistics
    enable_stats: bool = True

    # Logging
    log_level: str = "INFO"

    # Adapter-specific configuration
    extra_config: dict[str, Any] = field(default_factory=dict)


class ConfigLoader:
    """Simple configuration loader supporting JSON and YAML."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)

    def load_from_file(self, file_path: str | Path) -> dict[str, Any]:
        """Load configuration from file."""
        file_path = Path(file_path)

        if not file_path.exists():
            raise ConfigurationError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, encoding="utf-8") as f:
                if file_path.suffix.lower() == ".json":
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        return cast(dict[str, Any], loaded)
                    raise ConfigurationError("Top-level JSON config must be an object")
                if file_path.suffix.lower() in (".yaml", ".yml"):
                    if not HAS_YAML:
                        raise ConfigurationError("YAML support not available. Install PyYAML.")
                    loaded = yaml.safe_load(f)
                    if isinstance(loaded, dict):
                        return cast(dict[str, Any], loaded)
                    raise ConfigurationError("Top-level YAML config must be a mapping")
                raise ConfigurationError(
                    f"Unsupported configuration file format: {file_path.suffix}"
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            raise ConfigurationError(f"Failed to load configuration from {file_path}: {e}") from e

    def load_from_env(self, prefix: str = "OMNI_CACHE_") -> dict[str, Any]:
        """Load configuration from environment variables."""
        config: dict[str, Any] = {"global": {}, "adapters": {}}

        for key, value in os.environ.items():
            if not key.startswith(prefix):
                continue

            # Remove prefix and convert to lowercase
            config_key = key[len(prefix) :].lower()
            parsed_value = self._parse_env_value(value)

            # Handle nested keys (e.g., OMNI_CACHE_ADAPTERS_REDIS_HOST)
            if config_key.startswith("adapters_"):
                parts = config_key.split("_", 2)  # ['adapters', 'redis', 'host']
                if len(parts) >= 3:
                    adapter_name = parts[1]
                    setting_key = "_".join(parts[2:])

                    if adapter_name not in config["adapters"]:
                        config["adapters"][adapter_name] = {}
                    config["adapters"][adapter_name][setting_key] = parsed_value
            else:
                config["global"][config_key] = parsed_value

        return config

    def _parse_env_value(self, value: str) -> Any:
        """Parse environment variable value to appropriate type."""
        if not value:
            return None

        # Try boolean
        if value.lower() in ("true", "false"):
            return value.lower() == "true"

        # Try integer
        try:
            return int(value)
        except ValueError:
            pass

        # Try float
        try:
            return float(value)
        except ValueError:
            pass

        # Try JSON for complex values
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

        # Return as string
        return value


class ConfigManager:
    """Simplified configuration manager."""

    def __init__(self, config_file: str | Path | None = None):
        """Initialize the configuration manager."""
        self._global_config = GlobalConfig()
        self._adapter_configs: dict[str, AdapterConfig] = {}
        self._config_file = Path(config_file) if config_file else None
        self._loader = ConfigLoader()
        self._logger = logging.getLogger(__name__)
        self._lock = threading.RLock()

        # Load configuration
        if self._config_file:
            self.load_config()
        else:
            self.load_defaults()

    def load_defaults(self) -> None:
        """Load default configuration."""
        with self._lock:
            self._global_config = GlobalConfig()
            self._adapter_configs.clear()
            # Add default memory adapter
            self._adapter_configs["memory"] = AdapterConfig(name="memory", backend="memory")

        self._logger.info("Loaded default configuration")

    def load_config(self, config_file: str | Path | None = None) -> None:
        """Load configuration from file and environment."""
        if config_file:
            self._config_file = Path(config_file)

        if not self._config_file:
            raise ConfigurationError("No configuration file specified")

        try:
            with self._lock:
                # Load from file
                file_config = self._loader.load_from_file(self._config_file)

                # Load from environment (overrides file)
                env_config = self._loader.load_from_env()

                # Merge configurations
                merged_config = self._merge_configs(file_config, env_config)

                # Update global config
                global_data = merged_config.get("global", {})
                self._global_config.update(global_data)

                # Update adapter configs
                adapters_data = merged_config.get("adapters", {})
                self._load_adapter_configs(adapters_data)

            self._logger.info("Loaded configuration from %s", self._config_file)

        except Exception as e:
            self._logger.error("Failed to load configuration: %s", e)
            raise ConfigurationError(f"Failed to load configuration: {e}") from e

    def _merge_configs(
        self, file_config: dict[str, Any], env_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge file and environment configurations."""
        merged = file_config.copy()

        # Merge global settings
        if "global" in env_config:
            merged.setdefault("global", {}).update(env_config["global"])

        # Merge adapter settings
        if "adapters" in env_config:
            merged.setdefault("adapters", {})
            for adapter_name, adapter_config in env_config["adapters"].items():
                merged["adapters"].setdefault(adapter_name, {}).update(adapter_config)

        return merged

    def _load_adapter_configs(self, adapters_config: dict[str, Any]) -> None:
        """Load adapter configurations from dictionary."""
        self._adapter_configs.clear()

        for name, config_data in adapters_config.items():
            try:
                # Create adapter config
                adapter_config = AdapterConfig(name=name)
                adapter_config.update(config_data)

                self._adapter_configs[name] = adapter_config
                self._logger.debug("Loaded adapter config: %s", name)

            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.warning("Failed to load adapter config '%s': %s", name, e)
                raise ConfigurationError(f"Failed to load adapter config for {name}: {e}") from e

    def get_global_config(self) -> GlobalConfig:
        """Get global configuration."""
        with self._lock:
            return self._global_config

    def get_adapter_config(self, name: str) -> AdapterConfig | None:
        """Get adapter configuration by name."""
        with self._lock:
            return self._adapter_configs.get(name)

    def list_adapters(self) -> list[str]:
        """List all configured adapters."""
        with self._lock:
            return list(self._adapter_configs.keys())

    def add_adapter_config(self, name: str, config: dict[str, Any]) -> None:
        """Add or update adapter configuration."""
        with self._lock:
            adapter_config = AdapterConfig(name=name)
            adapter_config.update(config)
            self._adapter_configs[name] = adapter_config

        self._logger.info("Added adapter config: %s", name)

    def remove_adapter_config(self, name: str) -> bool:
        """Remove adapter configuration."""
        with self._lock:
            if name in self._adapter_configs:
                del self._adapter_configs[name]
                self._logger.info("Removed adapter config: %s", name)
                return True
            return False

    def update_global_config(self, updates: dict[str, Any]) -> None:
        """Update global configuration."""
        with self._lock:
            self._global_config.update(updates)

        self._logger.info("Updated global configuration")

    def save_config(
        self,
        file_path: str | Path | None = None,
        format_type: ConfigFormat = ConfigFormat.YAML,
    ) -> None:
        """Save current configuration to file."""
        output_path = Path(file_path) if file_path else self._config_file

        if not output_path:
            raise ConfigurationError("No output file specified")

        config_data = {
            "global": self._global_config.to_dict(),
            "adapters": {name: config.to_dict() for name, config in self._adapter_configs.items()},
        }

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                if format_type == ConfigFormat.JSON:
                    json.dump(config_data, f, indent=2)
                elif format_type == ConfigFormat.YAML:
                    if not HAS_YAML:
                        raise ConfigurationError("YAML support not available")
                    yaml.dump(config_data, f, default_flow_style=False)
                else:
                    raise ConfigurationError(
                        f"Unsupported configuration format: {format_type.value}"
                    )

            self._logger.info("Saved configuration to %s", output_path)

        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}") from e

    def get_config_summary(self) -> dict[str, Any]:
        """Get configuration summary."""
        with self._lock:
            return {
                "global": self._global_config.to_dict(),
                "adapters": {
                    name: {
                        "backend": config.backend,
                        "enabled": config.enabled,
                        "auto_connect": config.auto_connect,
                    }
                    for name, config in self._adapter_configs.items()
                },
                "stats": {
                    "total_adapters": len(self._adapter_configs),
                    "enabled_adapters": sum(1 for c in self._adapter_configs.values() if c.enabled),
                    "config_file": str(self._config_file) if self._config_file else None,
                },
            }


# Global configuration manager instance
_global_config_manager: ConfigManager | None = None  # pylint: disable=invalid-name
_global_config_lock = threading.RLock()  # Changed to RLock to prevent deadlocks
_initializing_thread_local = threading.local()


@contextmanager
def temporary_config(config_updates: dict[str, Any]) -> Any:
    """
    Context manager for temporary configuration changes.

    Args:
        config_updates: Configuration updates to apply temporarily
    """
    original_manager = get_global_config_manager()
    new_manager = ConfigManager()
    new_manager.update_global_config(config_updates.get("global", {}))
    # For adapters, we'd need a more complex merge or replacement strategy
    # For simplicity, this example only handles global config updates

    set_global_config_manager(new_manager)

    try:
        yield new_manager
    finally:
        set_global_config_manager(original_manager)


def get_global_config_manager() -> ConfigManager:
    """
    Get the global ConfigManager instance.

    Uses RLock to prevent deadlocks and thread-local storage to detect
    recursive initialization attempts.
    """
    if _global_config_manager is None:
        # Check for recursive calls in current thread to prevent infinite loops
        if getattr(_initializing_thread_local, "in_progress", False):
            raise RuntimeError(
                "Recursive initialization detected. ConfigManager constructor "
                "should not call get_global_config_manager() during initialization."
            )

        with _global_config_lock:
            if _global_config_manager is None:
                _initializing_thread_local.in_progress = True
                try:
                    set_global_config_manager(ConfigManager())
                finally:
                    _initializing_thread_local.in_progress = False

    if _global_config_manager is None:
        raise RuntimeError("Global ConfigManager could not be initialized")
    return _global_config_manager


def set_global_config_manager(manager: ConfigManager | None) -> None:
    """Set the global ConfigManager instance."""
    # pylint: disable=global-statement
    global _global_config_manager
    with _global_config_lock:
        _global_config_manager = manager


def reset_global_config_manager() -> None:
    """
    Reset the global ConfigManager instance.

    This is primarily useful for testing to ensure clean state between tests.
    """
    # pylint: disable=global-statement
    global _global_config_manager
    with _global_config_lock:
        _global_config_manager = None


def load_config_from_env(prefix: str = "OMNI_CACHE_") -> dict[str, Any]:
    """Load configuration from environment variables.

    Args:
        prefix: Prefix for environment variables (default: ``OMNI_CACHE_``)

    Returns:
        Dictionary with configuration loaded from environment variables
    """
    return ConfigLoader().load_from_env(prefix)


__all__ = [
    "ConfigFormat",
    "BaseConfig",
    "GlobalConfig",
    "AdapterConfig",
    "ConfigLoader",
    "ConfigManager",
    "get_global_config_manager",
    "set_global_config_manager",
    "reset_global_config_manager",
    "load_config_from_env",
    "temporary_config",
]
