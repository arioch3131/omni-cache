"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Configuration-related exceptions
class ConfigurationError(OmniCacheError):
    """Base class for configuration-related errors."""


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration values are invalid."""

    def __init__(
        self,
        config_key: str,
        config_value: Any,
        expected_type: type | None = None,
        valid_values: list[Any] | None = None,
    ) -> None:
        details = {"config_key": config_key, "config_value": config_value}

        message = f"Invalid configuration value for '{config_key}': {config_value}"

        if expected_type:
            details["expected_type"] = expected_type.__name__
            message += f" (expected type: {expected_type.__name__})"

        if valid_values is not None:
            details["valid_values"] = valid_values
            message += f" (valid values: {valid_values})"

        super().__init__(message, details)


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(self, config_key: str, component: str | None = None) -> None:
        details = {"config_key": config_key}
        if component is not None:
            details["component"] = component

        message = f"Missing required configuration: '{config_key}'"
        if component is not None:
            message += f" for component '{component}'"

        super().__init__(message, details)
