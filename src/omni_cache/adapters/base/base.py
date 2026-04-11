"""
Base adapter implementation for omni-cache.

This module provides the foundational BaseAdapter class that all specific
adapters inherit from, implementing common functionality and patterns.
"""

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Self, TypeVar

from omni_cache.core.exceptions import AdapterNotConnectedError
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
    CacheStats,
    Configurable,
    PoolStats,
    StatisticsInterface,
)

# Type variables
T = TypeVar("T")


class ConnectionState(Enum):
    """Connection states for adapters."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


@dataclass
class AdapterConfig:
    """Base configuration for all adapters."""

    name: str = "default"
    backend: str | CacheBackend = CacheBackend.MEMORY
    max_retries: int = 3
    retry_delay: float = 0.1
    connection_timeout: float = 5.0
    health_check_interval: float = 30.0
    enable_stats: bool = True
    log_level: str = "INFO"
    extra_config: dict[str, Any] = field(default_factory=dict)


class BaseAdapter(AdapterInterface, StatisticsInterface, Configurable, ABC):
    """
    Base class for all cache and pool adapters.

    Provides common functionality including:
    - Connection state management
    - Statistics tracking
    - Configuration handling
    - Retry logic
    - Health checking
    - Logging
    - Thread safety
    """

    def __init__(self, config: dict[str, Any] | AdapterConfig | None = None):
        """
        Initialize the base adapter.

        Args:
            config: Configuration dictionary or AdapterConfig instance
        """
        # Parse configuration
        if isinstance(config, dict):
            self._config = AdapterConfig(**config)
        elif isinstance(config, AdapterConfig):
            self._config = config
        else:
            self._config = AdapterConfig()

        # Setup logging
        self._logger = self._setup_logger()

        # Connection state management
        self._state = ConnectionState.DISCONNECTED
        self._state_lock = threading.RLock()
        self._last_error: Exception | None = None
        self._connection_time: float | None = None

        # Statistics
        self._stats_lock = threading.RLock()
        self._cache_stats = CacheStats() if self._should_track_cache_stats() else None
        self._pool_stats = PoolStats() if self._should_track_pool_stats() else None

        # Health checking
        self._last_health_check: float | None = None
        self._health_check_result: bool = False

        self._logger.info("Initialized %s adapter: %s", self.__class__.__name__, self._config.name)

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for the adapter."""
        logger = logging.getLogger(f"omni_cache.adapters.{self.__class__.__name__.lower()}")
        logger.setLevel(getattr(logging, self._config.log_level.upper(), logging.INFO))
        logger.propagate = True  # Ensure propagation to root logger
        return logger

    @abstractmethod
    def _should_track_cache_stats(self) -> bool:
        """Determine if this adapter should track cache statistics."""

    @abstractmethod
    def _should_track_pool_stats(self) -> bool:
        """Determine if this adapter should track pool statistics."""

    @abstractmethod
    def _do_connect(self) -> bool:
        """Perform the actual connection logic. Subclasses must implement."""

    @abstractmethod
    def _do_disconnect(self) -> bool:
        """Perform the actual disconnection logic. Subclasses must implement."""

    @abstractmethod
    def _do_health_check(self) -> bool:
        """Perform the actual health check logic. Subclasses must implement."""

    # Connection management
    def connect(self) -> bool:
        """
        Establish connection to the backend with retry logic.

        Returns:
            True if connection successful, False otherwise
        """
        with self._state_lock:
            if self._state == ConnectionState.CONNECTED:
                return True

            if self._state == ConnectionState.CONNECTING:
                self._logger.warning("Connection already in progress")
                return False

            self._state = ConnectionState.CONNECTING
            self._last_error = None

        try:
            success = self._connect_with_retry()

            with self._state_lock:
                if success:
                    self._state = ConnectionState.CONNECTED
                    self._connection_time = time.time()
                    self._logger.info("Successfully connected to %s", self._config.backend)
                else:
                    self._state = ConnectionState.ERROR
                    self._logger.error("Failed to connect to %s", self._config.backend)

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            with self._state_lock:
                self._state = ConnectionState.ERROR
                self._last_error = e

            self._logger.error("Connection failed with exception: %s", e)
            return False

    def disconnect(self) -> bool:
        """
        Close connection to the backend.

        Returns:
            True if disconnection successful, False otherwise
        """
        with self._state_lock:
            if self._state == ConnectionState.DISCONNECTED:
                return True

            if self._state == ConnectionState.DISCONNECTING:
                self._logger.warning("Disconnection already in progress")
                return False

            self._state = ConnectionState.DISCONNECTING

        try:
            success = self._do_disconnect()

            with self._state_lock:
                self._state = ConnectionState.DISCONNECTED
                self._connection_time = None

                if success:
                    self._logger.info("Successfully disconnected from %s", self._config.backend)
                else:
                    self._logger.warning("Disconnection completed with warnings")

            return success

        except Exception as e:  # pylint: disable=broad-exception-caught
            with self._state_lock:
                self._state = ConnectionState.ERROR
                self._last_error = e

            self._logger.error("Disconnection failed with exception: %s", e)
            return False

    def is_connected(self) -> bool:
        """
        Check if adapter is connected to backend.

        Returns:
            True if connected, False otherwise
        """
        with self._state_lock:
            return self._state == ConnectionState.CONNECTED

    def is_connected_fast(self) -> bool:
        """
        Fast-path connectivity check for hot paths.

        This avoids lock acquisition and may be marginally stale during
        concurrent state transitions, but is suitable for routing fast paths.
        """
        return self._state == ConnectionState.CONNECTED

    def _connect_with_retry(self) -> bool:
        """Connect with retry logic."""
        for attempt in range(self._config.max_retries + 1):
            try:
                if self._do_connect():
                    return True

            except Exception as e:  # pylint: disable=broad-exception-caught
                self._last_error = e
                self._logger.warning("Connection attempt %d failed: %s", attempt + 1, e)

            if attempt < self._config.max_retries:
                delay = self._config.retry_delay * (2**attempt)  # Exponential backoff
                self._logger.info("Retrying connection in %.2f seconds...", delay)
                time.sleep(delay)

        return False

    # Health checking
    def health_check(self) -> bool:
        """
        Perform a health check on the backend.

        Returns:
            True if backend is healthy, False otherwise
        """
        now = time.time()

        # Use cached result if recent enough
        if (
            self._last_health_check
            and now - self._last_health_check < self._config.health_check_interval
        ):
            return self._health_check_result

        try:
            if not self.is_connected():
                self._health_check_result = False
            else:
                self._health_check_result = self._do_health_check()

            self._last_health_check = now

            if not self._health_check_result:
                self._logger.warning("Health check failed")

            return self._health_check_result

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Health check failed with exception: %s", e)
            self._health_check_result = False
            self._last_health_check = now
            return False

    # Statistics
    def get_stats(self) -> CacheStats | PoolStats | None:
        """
        Get current statistics.

        Returns:
            Statistics object with current metrics
        """
        if not self._config.enable_stats:
            return None

        with self._stats_lock:
            if self._cache_stats:
                # Update hit rate before returning
                self._cache_stats.update_hit_rate()
                return self._cache_stats
            if self._pool_stats:
                return self._pool_stats
            return None

    def reset_stats(self) -> bool:
        """
        Reset all statistics to zero.

        Returns:
            True if successful, False otherwise
        """
        if not self._config.enable_stats:
            return False

        try:
            with self._stats_lock:
                if self._cache_stats:
                    self._cache_stats = CacheStats()
                if self._pool_stats:
                    self._pool_stats = PoolStats()

            self._logger.info("Statistics reset successfully")
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to reset statistics: %s", e)
            return False

    def _update_cache_stats(self, operation: str, success: bool = True, **kwargs: Any) -> None:
        """Update cache statistics for an operation."""
        if not self._config.enable_stats or not self._cache_stats:
            return

        with self._stats_lock:
            if operation == "get":
                if success:
                    self._cache_stats.hits += 1
                else:
                    self._cache_stats.misses += 1
            elif operation == "set":
                self._cache_stats.sets += 1
            elif operation == "delete":
                self._cache_stats.deletes += 1
            elif operation == "eviction":
                self._cache_stats.evictions += 1

            # Update size if provided
            if "size" in kwargs:
                self._cache_stats.size = kwargs["size"]

    def _update_pool_stats(self, operation: str, **kwargs: Any) -> None:
        """Update pool statistics for an operation."""
        if not self._config.enable_stats or not self._pool_stats:
            return

        with self._stats_lock:
            if operation == "create":
                self._pool_stats.created += 1
            elif operation == "borrow":
                self._pool_stats.borrowed += 1
            elif operation == "return":
                self._pool_stats.returned += 1
            elif operation == "destroy":
                self._pool_stats.destroyed += 1

            # Update counts if provided
            if "active" in kwargs:
                self._pool_stats.active = kwargs["active"]
            if "idle" in kwargs:
                self._pool_stats.idle = kwargs["idle"]

    # Configuration
    def configure(self, config: dict[str, Any]) -> bool:
        """
        Configure the adapter with given settings.

        Args:
            config: Configuration dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update configuration
            for key, value in config.items():
                if hasattr(self._config, key):
                    setattr(self._config, key, value)
                else:
                    self._config.extra_config[key] = value

            # Reconfigure logger if level changed
            if "log_level" in config:
                self._logger.setLevel(
                    getattr(logging, self._config.log_level.upper(), logging.INFO)
                )

            self._logger.info("Configuration updated successfully")
            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to update configuration: %s", e)
            return False

    def get_config(self) -> AdapterConfig:
        """
        Get current configuration.

        Returns:
            AdapterConfig instance
        """
        return self._config

    # Backend info
    def get_backend_info(self) -> dict[str, Any]:
        """
        Get information about the backend.

        Returns:
            Dictionary containing backend information
        """
        info: dict[str, Any] = {
            "adapter_class": self.__class__.__name__,
            "backend": (
                self._config.backend.value
                if isinstance(self._config.backend, CacheBackend)
                else self._config.backend
            ),
            "name": self._config.name,
            "state": self._state.value,
            "connected": self.is_connected(),
            "connection_time": self._connection_time,
            "last_health_check": self._last_health_check,
            "health_check_result": self._health_check_result,
            "last_error": str(self._last_error) if self._last_error else None,
            "stats_enabled": self._config.enable_stats,
        }

        # Add statistics if available
        stats = self.get_stats()
        if stats:
            info["statistics"] = stats.__dict__

        return info

    # Context manager support
    @contextmanager
    def connection(self) -> Iterator[Self]:
        """
        Context manager for connection lifecycle.

        Yields:
            self: The adapter instance
        """
        if not self.is_connected():
            connected = self.connect()
            if not connected:
                raise RuntimeError(f"Failed to connect to {self._config.backend}")
            auto_disconnect = True
        else:
            auto_disconnect = False

        try:
            yield self
        finally:
            if auto_disconnect:
                self.disconnect()

    # Utility methods
    def _safe_operation(
        self, operation: Callable[[], T], operation_name: str, default: T | None = None
    ) -> T:
        """
        Safely execute an operation with error handling and logging.

        Args:
            operation: The operation function to execute
            operation_name: Name of the operation for logging
            default: Default value to return on error

        Returns:
            Operation result or default value
        """
        if not self.is_connected():
            raise AdapterNotConnectedError(self._config.name, operation_name)

        try:
            return operation()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Operation '%s' failed: %s", operation_name, e)
            self._last_error = e

            if default is not None:
                return default
            raise

    def __enter__(self) -> "BaseAdapter":
        """Context manager entry."""
        if not self.connect():
            raise RuntimeError(f"Failed to connect to {self._config.backend}")
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()

    def __repr__(self) -> str:
        """String representation of the adapter."""
        backend_name = (
            self._config.backend.value
            if isinstance(self._config.backend, CacheBackend)
            else self._config.backend
        )
        return (
            f"{self.__class__.__name__}("
            f"name='{self._config.name}', "
            f"backend='{backend_name}', "
            f"state='{self._state.value}')"
        )


class BaseCacheAdapter(BaseAdapter):
    """Base class specifically for cache adapters."""

    def _should_track_cache_stats(self) -> bool:
        return True

    def _should_track_pool_stats(self) -> bool:
        return False


class BasePoolAdapter(BaseAdapter):
    """Base class specifically for pool adapters."""

    def _should_track_cache_stats(self) -> bool:
        return False

    def _should_track_pool_stats(self) -> bool:
        return True
