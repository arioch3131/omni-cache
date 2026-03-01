"""
Unit tests for src/omni_cache/core/routing.py

This module contains comprehensive pytest-based unit tests for the CacheRouter class,
covering all methods, edge cases, and error conditions.
"""

import logging
from unittest.mock import MagicMock, Mock

import pytest

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.exceptions import AdapterNotFoundError
from omni_cache.core.routing import CacheRouter


@pytest.fixture
def mock_config():
    """Create a mock ManagerConfig for testing."""
    config = Mock(spec=ManagerConfig)
    config.enable_routing = True
    config.namespace_separator = ":"
    config.default_adapter = "default_adapter"
    config.fallback_adapter = "fallback_adapter"
    return config


@pytest.fixture
def mock_registry():
    """Create a mock AdapterRegistry for testing."""
    return Mock(spec=AdapterRegistry)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return Mock(spec=logging.Logger)


@pytest.fixture
def cache_router(mock_config, mock_registry, mock_logger):
    """Create a CacheRouter instance for testing."""
    return CacheRouter(mock_config, mock_registry, mock_logger)


class TestCacheRouterInit:
    """Test CacheRouter initialization."""

    def test_init_with_valid_parameters(self, mock_config, mock_registry, mock_logger):
        """Test CacheRouter initialization with valid parameters."""
        router = CacheRouter(mock_config, mock_registry, mock_logger)

        assert router._config is mock_config
        assert router._registry is mock_registry
        assert router._logger is mock_logger
        assert router._routing_rules == {}

    def test_init_creates_empty_routing_rules(self, cache_router):
        """Test that initialization creates empty routing rules dictionary."""
        assert isinstance(cache_router._routing_rules, dict)
        assert len(cache_router._routing_rules) == 0


class TestAddRoutingRule:
    """Test the add_routing_rule method."""

    def test_add_single_routing_rule(self, cache_router, mock_logger):
        """Test adding a single routing rule."""
        namespace = "test_namespace"
        adapter_name = "test_adapter"

        cache_router.add_routing_rule(namespace, adapter_name)

        assert cache_router._routing_rules[namespace] == adapter_name
        mock_logger.info.assert_called_once_with(
            f"Added routing rule: {namespace} -> {adapter_name}"
        )

    def test_add_multiple_routing_rules(self, cache_router):
        """Test adding multiple routing rules."""
        rules = [
            ("cache", "memory_adapter"),
            ("session", "redis_adapter"),
            ("temp", "temp_adapter"),
        ]

        for namespace, adapter_name in rules:
            cache_router.add_routing_rule(namespace, adapter_name)

        for namespace, adapter_name in rules:
            assert cache_router._routing_rules[namespace] == adapter_name

    def test_overwrite_existing_routing_rule(self, cache_router):
        """Test overwriting an existing routing rule."""
        namespace = "test_namespace"
        original_adapter = "original_adapter"
        new_adapter = "new_adapter"

        # Add original rule
        cache_router.add_routing_rule(namespace, original_adapter)
        assert cache_router._routing_rules[namespace] == original_adapter

        # Overwrite with new rule
        cache_router.add_routing_rule(namespace, new_adapter)
        assert cache_router._routing_rules[namespace] == new_adapter

    def test_add_routing_rule_with_empty_strings(self, cache_router):
        """Test adding routing rule with empty strings."""
        cache_router.add_routing_rule("", "")
        assert cache_router._routing_rules[""] == ""

    def test_add_routing_rule_with_special_characters(self, cache_router):
        """Test adding routing rule with special characters."""
        namespace = "test:namespace_with-special.chars"
        adapter_name = "adapter_with-special.chars"

        cache_router.add_routing_rule(namespace, adapter_name)
        assert cache_router._routing_rules[namespace] == adapter_name


class TestRemoveRoutingRule:
    """Test the remove_routing_rule method."""

    def test_remove_existing_routing_rule(self, cache_router):
        """Test removing an existing routing rule."""
        namespace = "test_namespace"
        adapter_name = "test_adapter"

        # Add rule first
        cache_router.add_routing_rule(namespace, adapter_name)
        assert namespace in cache_router._routing_rules

        # Remove rule
        result = cache_router.remove_routing_rule(namespace)

        assert result is True
        assert namespace not in cache_router._routing_rules

    def test_remove_non_existing_routing_rule(self, cache_router):
        """Test removing a non-existing routing rule."""
        result = cache_router.remove_routing_rule("non_existing_namespace")
        assert result is False

    def test_remove_from_empty_routing_rules(self, cache_router):
        """Test removing from empty routing rules."""
        assert len(cache_router._routing_rules) == 0
        result = cache_router.remove_routing_rule("any_namespace")
        assert result is False

    def test_remove_multiple_rules(self, cache_router):
        """Test removing multiple routing rules."""
        rules = [
            ("cache", "memory_adapter"),
            ("session", "redis_adapter"),
            ("temp", "temp_adapter"),
        ]

        # Add rules
        for namespace, adapter_name in rules:
            cache_router.add_routing_rule(namespace, adapter_name)

        # Remove rules
        for namespace, _ in rules:
            result = cache_router.remove_routing_rule(namespace)
            assert result is True
            assert namespace not in cache_router._routing_rules


class TestRouteAdapter:
    """Test the _route_adapter method."""

    def test_route_with_explicit_adapter_name(self, cache_router):
        """Test routing with explicit adapter name provided."""
        explicit_adapter = "explicit_adapter"
        result = cache_router._route_adapter(adapter_name=explicit_adapter)
        assert result == explicit_adapter

    def test_route_with_key_and_routing_enabled(self, cache_router):
        """Test routing with key when routing is enabled."""
        # Add routing rule
        cache_router.add_routing_rule("cache", "cache_adapter")

        # Test with matching key
        result = cache_router._route_adapter(key="cache:some_key")
        assert result == "cache_adapter"

    def test_route_with_key_no_matching_rule(self, cache_router):
        """Test routing with key but no matching routing rule."""
        result = cache_router._route_adapter(key="unknown:some_key")
        assert result == cache_router._config.default_adapter

    def test_route_with_key_without_namespace_separator(self, cache_router):
        """Test routing with key that doesn't contain namespace separator."""
        result = cache_router._route_adapter(key="simple_key")
        assert result == cache_router._config.default_adapter

    def test_route_with_routing_disabled(self, cache_router):
        """Test routing when routing is disabled in config."""
        cache_router._config.enable_routing = False
        cache_router.add_routing_rule("cache", "cache_adapter")

        result = cache_router._route_adapter(key="cache:some_key")
        assert result == cache_router._config.default_adapter

    def test_route_with_none_key(self, cache_router):
        """Test routing with None key."""
        result = cache_router._route_adapter(key=None)
        assert result == cache_router._config.default_adapter

    def test_route_with_empty_namespace(self, cache_router):
        """Test routing with empty namespace."""
        cache_router.add_routing_rule("", "empty_adapter")

        result = cache_router._route_adapter(key=":some_key")
        assert result == "empty_adapter"

    def test_route_with_multiple_separators(self, cache_router):
        """Test routing with key containing multiple separators."""
        cache_router.add_routing_rule("namespace", "test_adapter")

        result = cache_router._route_adapter(key="namespace:sub:key")
        assert result == "test_adapter"

    def test_route_with_different_separator(self, cache_router):
        """Test routing with different namespace separator."""
        cache_router._config.namespace_separator = "|"
        cache_router.add_routing_rule("namespace", "test_adapter")

        result = cache_router._route_adapter(key="namespace|some_key")
        assert result == "test_adapter"

    def test_route_priority_adapter_name_over_key(self, cache_router):
        """Test that explicit adapter name takes priority over key routing."""
        cache_router.add_routing_rule("cache", "cache_adapter")

        result = cache_router._route_adapter(key="cache:some_key", adapter_name="explicit_adapter")
        assert result == "explicit_adapter"


class TestGetCacheAdapter:
    """Test the get_cache_adapter method."""

    def setup_method(self):
        """Set up mock adapters for each test."""
        self.mock_adapter = MagicMock()
        self.mock_adapter.is_connected.return_value = True

        self.mock_fallback = MagicMock()
        self.mock_fallback.is_connected.return_value = True

    def test_get_cache_adapter_success(self, cache_router, mock_registry):
        """Test successful cache adapter retrieval."""
        mock_registry.get_cache_adapter.return_value = self.mock_adapter

        result = cache_router.get_cache_adapter(adapter_name="test_adapter")

        assert result is self.mock_adapter
        mock_registry.get_cache_adapter.assert_called_with("test_adapter")

    def test_get_cache_adapter_with_routing(self, cache_router, mock_registry):
        """Test cache adapter retrieval with routing."""
        cache_router.add_routing_rule("cache", "cache_adapter")
        mock_registry.get_cache_adapter.return_value = self.mock_adapter

        result = cache_router.get_cache_adapter(key="cache:some_key")

        assert result is self.mock_adapter
        mock_registry.get_cache_adapter.assert_called_with("cache_adapter")

    def test_get_cache_adapter_fallback_to_default(self, cache_router, mock_registry):
        """Test fallback to default adapter."""
        mock_registry.get_cache_adapter.return_value = self.mock_adapter

        result = cache_router.get_cache_adapter(key="unknown:key")

        assert result is self.mock_adapter
        mock_registry.get_cache_adapter.assert_called_with(cache_router._config.default_adapter)

    def test_get_cache_adapter_not_connected_uses_fallback(
        self, cache_router, mock_registry, mock_logger
    ):
        """Test using fallback when primary adapter is not connected."""
        # Primary adapter not connected
        self.mock_adapter.is_connected.return_value = False

        # Setup mock registry to return different adapters
        def mock_get_adapter(name):
            if name == "primary_adapter":
                return self.mock_adapter
            elif name == cache_router._config.fallback_adapter:
                return self.mock_fallback
            return None

        mock_registry.get_cache_adapter.side_effect = mock_get_adapter

        # Mock _route_adapter to return primary adapter
        cache_router._route_adapter = Mock(return_value="primary_adapter")

        result = cache_router.get_cache_adapter()

        assert result is self.mock_fallback
        mock_logger.warning.assert_called_once()

    def test_get_cache_adapter_no_adapter_found(self, cache_router, mock_registry):
        """Test exception when no suitable adapter is found."""
        mock_registry.get_cache_adapter.return_value = None

        with pytest.raises(AdapterNotFoundError) as exc_info:
            cache_router.get_cache_adapter(key="test_key")

        assert "No suitable cache adapter found for key: test_key" in str(exc_info.value)

    def test_get_cache_adapter_adapter_exists_but_not_connected(self, cache_router, mock_registry):
        """Test when adapter exists but is not connected and no fallback."""
        cache_router._config.fallback_adapter = None
        self.mock_adapter.is_connected.return_value = False
        mock_registry.get_cache_adapter.return_value = self.mock_adapter

        with pytest.raises(AdapterNotFoundError):
            cache_router.get_cache_adapter()

    def test_get_cache_adapter_fallback_not_connected(self, cache_router, mock_registry):
        """Test when both primary and fallback adapters are not connected."""
        # Primary adapter not connected
        self.mock_adapter.is_connected.return_value = False
        # Fallback adapter not connected
        self.mock_fallback.is_connected.return_value = False

        def mock_get_adapter(name):
            if name == "primary_adapter":
                return self.mock_adapter
            elif name == cache_router._config.fallback_adapter:
                return self.mock_fallback
            return None

        mock_registry.get_cache_adapter.side_effect = mock_get_adapter
        cache_router._route_adapter = Mock(return_value="primary_adapter")

        with pytest.raises(AdapterNotFoundError):
            cache_router.get_cache_adapter()


class TestGetPoolAdapter:
    """Test the get_pool_adapter method."""

    def setup_method(self):
        """Set up mock pool adapters for each test."""
        self.mock_pool = MagicMock()
        self.mock_pool.is_connected.return_value = True

        self.mock_fallback_pool = MagicMock()
        self.mock_fallback_pool.is_connected.return_value = True

    def test_get_pool_adapter_with_explicit_name(self, cache_router, mock_registry):
        """Test getting pool adapter with explicit name."""
        mock_registry.get_pool_adapter.return_value = self.mock_pool

        result = cache_router.get_pool_adapter(adapter_name="test_pool")

        assert result is self.mock_pool
        mock_registry.get_pool_adapter.assert_called_with("test_pool")

    def test_get_pool_adapter_default(self, cache_router, mock_registry):
        """Test getting default pool adapter."""
        mock_registry.get_pool_adapter.return_value = self.mock_pool

        result = cache_router.get_pool_adapter()

        assert result is self.mock_pool
        mock_registry.get_pool_adapter.assert_called_with(cache_router._config.default_adapter)

    def test_get_pool_adapter_fallback(self, cache_router, mock_registry, mock_logger):
        """Test fallback to fallback pool adapter."""
        # Primary pool not connected
        self.mock_pool.is_connected.return_value = False

        def mock_get_pool(name):
            if name == cache_router._config.default_adapter:
                return self.mock_pool
            elif name == cache_router._config.fallback_adapter:
                return self.mock_fallback_pool
            return None

        mock_registry.get_pool_adapter.side_effect = mock_get_pool

        result = cache_router.get_pool_adapter()

        assert result is self.mock_fallback_pool
        mock_logger.warning.assert_called_once()

    def test_get_pool_adapter_not_found(self, cache_router, mock_registry):
        """Test exception when no pool adapter is found."""
        mock_registry.get_pool_adapter.return_value = None

        with pytest.raises(AdapterNotFoundError) as exc_info:
            cache_router.get_pool_adapter()

        assert "No suitable pool adapter found" in str(exc_info.value)

    def test_get_pool_adapter_not_connected_no_fallback(self, cache_router, mock_registry):
        """Test when pool adapter is not connected and no fallback."""
        cache_router._config.fallback_adapter = None
        self.mock_pool.is_connected.return_value = False
        mock_registry.get_pool_adapter.return_value = self.mock_pool

        with pytest.raises(AdapterNotFoundError):
            cache_router.get_pool_adapter()


class TestCacheRouterIntegration:
    """Integration tests for CacheRouter."""

    def test_routing_rule_modification(self, cache_router, mock_registry):
        """Test adding and removing routing rules."""
        # Add rule
        cache_router.add_routing_rule("temp", "memory_adapter")
        assert "temp" in cache_router._routing_rules

        # Modify rule
        cache_router.add_routing_rule("temp", "redis_adapter")
        assert cache_router._routing_rules["temp"] == "redis_adapter"

        # Remove rule
        result = cache_router.remove_routing_rule("temp")
        assert result is True
        assert "temp" not in cache_router._routing_rules

        # Try to remove again
        result = cache_router.remove_routing_rule("temp")
        assert result is False

    def test_complete_routing_workflow(self, cache_router, mock_registry):
        """Test complete routing workflow from rule addition to adapter retrieval."""
        memory_adapter = MagicMock()  # Sans spec
        memory_adapter.is_connected.return_value = True

        redis_adapter = MagicMock()  # Sans spec
        redis_adapter.is_connected.return_value = True

        def mock_get_cache_adapter(name):
            if name == "memory":
                return memory_adapter
            elif name == "redis":
                return redis_adapter
            return None

        mock_registry.get_cache_adapter.side_effect = mock_get_cache_adapter

        # Add routing rules
        cache_router.add_routing_rule("cache", "memory")
        cache_router.add_routing_rule("session", "redis")

        # Test routing
        cache_result = cache_router.get_cache_adapter(key="cache:user_data")
        session_result = cache_router.get_cache_adapter(key="session:abc123")

        assert cache_result is memory_adapter
        assert session_result is redis_adapter

    def test_complex_key_routing(self, cache_router, mock_registry):
        """Test routing with complex key patterns."""
        # FIXÉ: ajout de is_connected
        mock_adapter = MagicMock()  # Sans spec
        mock_adapter.is_connected.return_value = True

        mock_registry.get_cache_adapter.return_value = mock_adapter

        # Test different key patterns
        cache_router.add_routing_rule("user", "user_adapter")
        cache_router.add_routing_rule("system", "system_adapter")

        test_cases = [
            ("user:profile:123", "user_adapter"),
            ("system:config:database", "system_adapter"),
            ("unknown:data", cache_router._config.default_adapter),
            ("simple_key", cache_router._config.default_adapter),
        ]

        for key, expected_adapter in test_cases:
            routed_adapter = cache_router._route_adapter(key=key)
            assert routed_adapter == expected_adapter


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_route_adapter_with_numeric_key(self, cache_router):
        """Test routing with numeric key."""
        cache_router.add_routing_rule("123", "numeric_adapter")
        result = cache_router._route_adapter(key=123)
        # Key will be converted to string "123"
        assert result == "numeric_adapter"

    def test_route_adapter_with_boolean_key(self, cache_router):
        """Test routing with boolean key."""
        result = cache_router._route_adapter(key=True)
        # Boolean will be converted to string "True"
        assert result == cache_router._config.default_adapter

    def test_route_adapter_with_none_values(self, cache_router):
        """Test routing with None values."""
        result = cache_router._route_adapter(key=None, adapter_name=None)
        assert result == cache_router._config.default_adapter

    def test_empty_namespace_in_key(self, cache_router):
        """Test key with empty namespace."""
        cache_router.add_routing_rule("", "empty_namespace_adapter")
        result = cache_router._route_adapter(key=":actual_key")
        assert result == "empty_namespace_adapter"

    def test_key_with_only_separator(self, cache_router):
        """Test key that is only the separator."""
        cache_router.add_routing_rule("", "separator_adapter")
        result = cache_router._route_adapter(key=":")
        assert result == "separator_adapter"

    def test_multiple_consecutive_separators(self, cache_router):
        """Test key with multiple consecutive separators."""
        cache_router.add_routing_rule("namespace", "test_adapter")
        result = cache_router._route_adapter(key="namespace::key")
        assert result == "test_adapter"
