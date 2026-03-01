"""
Health Monitor
"""

import logging
import threading

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig


class HealthMonitor:
    """
    Docstring Class
    """

    def __init__(
        self, config: ManagerConfig, registry: AdapterRegistry, logger: logging.Logger
    ) -> None:
        """
        Docstring Init
        """
        self._config = config
        self._registry = registry
        self._logger = logger
        self._health_monitor_thread: threading.Thread | None = None
        self._stop_health_monitor = threading.Event()

    def start(self) -> None:
        """
        Starts a health monitor thread.
        """
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            return

        self._stop_health_monitor.clear()
        self._health_monitor_thread = threading.Thread(
            target=self._health_monitor_loop, name="CacheManager-HealthMonitor", daemon=True
        )
        self._health_monitor_thread.start()
        self._logger.info("Started health monitoring")

    def stop(self) -> None:
        """
        Stops a health monitor thread.
        """
        if self._health_monitor_thread and self._health_monitor_thread.is_alive():
            self._stop_health_monitor.set()
            self._health_monitor_thread.join(timeout=1.0)
            self._logger.info("Stopped health monitoring")

    def _health_monitor_loop(self) -> None:
        """
        Loop on a health monitor.
        """
        while not self._stop_health_monitor.wait(self._config.health_check_interval):
            try:
                unhealthy_adapters = []

                for name in self._registry.list_all():
                    adapter = self._registry.get(name)
                    if adapter and not adapter.health_check():
                        unhealthy_adapters.append(name)

                if unhealthy_adapters:
                    self._logger.warning(f"Unhealthy adapters detected: {unhealthy_adapters}")

            except Exception as e:  # pylint: disable=W0718
                self._logger.error("Health monitoring error: %s", e)
