"""
A Cache Router.
"""

import logging
from typing import TypeVar

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.exceptions import AdapterNotFoundError
from omni_cache.core.interfaces import KeyValueInterface, PoolInterface

K = TypeVar("K")
T = TypeVar("T")


class CacheRouter:
    """
    A Cache Router.
    """

    def __init__(
        self, config: ManagerConfig, registry: AdapterRegistry, logger: logging.Logger
    ) -> None:
        """
        The class constructor.

        Args:
            config (ManagerConfig): The config of the manager.
            registry (AdapterRegistry): The adapter registrer.
            logger (logging.Logger): The logger.

        Returns:
            None
        """
        self._config = config
        self._registry = registry
        self._logger = logger
        self._routing_rules: dict[str, str] = {}  # namespace -> adapter_name
        self._cache_adapter_cache: dict[str, KeyValueInterface] = {}

    def add_routing_rule(self, namespace: str, adapter_name: str) -> None:
        """
        Add a routing rule.

        Args:
            namespace (str): The namespace.
            adapter_name (str): The Adapter Name.

        Returns:
            None
        """
        self._routing_rules[namespace] = adapter_name
        self._logger.info(f"Added routing rule: {namespace} -> {adapter_name}")

    def remove_routing_rule(self, namespace: str) -> bool:
        """
        Remove a routing rule.

        Args:
            namespace (str): The namespace.

        Returns:
            None
        """
        return self._routing_rules.pop(namespace, None) is not None

    def invalidate_cache_adapter(self, adapter_name: str | None = None) -> None:
        """Invalidate cached connected cache adapters."""
        if adapter_name is None:
            self._cache_adapter_cache.clear()
            return
        self._cache_adapter_cache.pop(adapter_name, None)

    def register_cache_adapter(self, adapter_name: str, adapter: KeyValueInterface) -> None:
        """Register a cache adapter directly in the router fast-path cache."""
        self._cache_adapter_cache[adapter_name] = adapter

    def get_cached_cache_adapter(self, adapter_name: str) -> KeyValueInterface | None:
        """Return cache adapter from hot-path cache without any fallback logic."""
        return self._cache_adapter_cache.get(adapter_name)

    def has_routing_rules(self) -> bool:
        """Return True when at least one namespace routing rule exists."""
        return bool(self._routing_rules)

    def _route_adapter(self, key: K | None = None, adapter_name: str | None = None) -> str | None:
        """
        A route to an adapter.

        Args:
            key: Key to route (can be exact namespace match or namespace:key format)
            adapter_name: Explicit adapter name (takes priority)

        Returns:
            Adapter name to use
        """
        if adapter_name:
            return adapter_name

        if self._config.enable_routing and self._routing_rules and key is not None:
            key_str = str(key)

            # First check: Direct namespace match (e.g., key="123" matches rule "123")
            if key_str in self._routing_rules:
                return self._routing_rules[key_str]

            # Second check: Namespace with separator (e.g., key="cache:user:123")
            if self._config.namespace_separator in key_str:
                namespace = key_str.split(self._config.namespace_separator, maxsplit=1)[0]
                if namespace in self._routing_rules:
                    return self._routing_rules[namespace]

        return self._config.default_adapter

    @staticmethod
    def _is_connected_adapter(adapter: object) -> bool:
        """Check adapter connectivity without static casts."""
        fast_attr = getattr(type(adapter), "is_connected_fast", None)
        if callable(fast_attr):
            return bool(fast_attr(adapter))

        check_attr = getattr(adapter, "is_connected", None)
        if callable(check_attr):
            return bool(check_attr())
        return False

    def _get_connected_cache_adapter(self, adapter_name: str | None) -> KeyValueInterface | None:
        """Return a connected cache adapter by name, else None."""
        if not adapter_name:
            return None

        cached = self._cache_adapter_cache.get(adapter_name)
        if cached is not None:
            # Hot path: trust router-level cache and avoid connectivity checks per request.
            return cached

        adapter = self._registry.get_cache_adapter(adapter_name)
        if adapter is None:
            return None

        if self._is_connected_adapter(adapter):
            self._cache_adapter_cache[adapter_name] = adapter
            return adapter
        return None

    def get_cache_adapter(
        self, key: K | None = None, adapter_name: str | None = None
    ) -> KeyValueInterface:
        """
        Getting the cache of an adapter.

        Args:
            key (Optional[K]): A key
            adapter_name (Optional[str]): An Adapter Name.

        Returns:
            A KeyValue Interface.
        """
        target_adapter = self._route_adapter(key, adapter_name)
        if target_adapter:
            # Fast-path: direct dictionary lookup for steady-state runtime.
            cached = self._cache_adapter_cache.get(target_adapter)
            if cached is not None:
                return cached

            adapter = self._get_connected_cache_adapter(target_adapter)
            if adapter:
                return adapter

        fallback_name = self._config.fallback_adapter
        if fallback_name and fallback_name != target_adapter:
            fallback = self._cache_adapter_cache.get(fallback_name)
            if fallback is None:
                fallback = self._get_connected_cache_adapter(fallback_name)
            if fallback:
                self._logger.warning("Using fallback adapter: %s", fallback_name)
                return fallback

        raise AdapterNotFoundError(f"No suitable cache adapter found for key: {key}")

    def get_pool_adapter(self, adapter_name: str | None = None) -> PoolInterface:
        """
        Getting the pool of an adapter.
        Args:
            key (Optional[K]): A key of a pool
            adapter_name (Optional[str]): An Adapter Name.

        Returns:
            A Pool Interface.
        """
        target_adapter = adapter_name or self._config.default_adapter

        if target_adapter:
            adapter = self._registry.get_pool_adapter(target_adapter)
            if adapter and self._is_connected_adapter(adapter):
                return adapter

        if self._config.fallback_adapter:
            fallback = self._registry.get_pool_adapter(self._config.fallback_adapter)
            if fallback and self._is_connected_adapter(fallback):
                self._logger.warning(
                    f"Using fallback pool adapter: {self._config.fallback_adapter}"
                )
                return fallback

        raise AdapterNotFoundError("No suitable pool adapter found")
