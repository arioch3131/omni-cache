"""
Unit tests for src/omni_cache/core/adapter_registry.py

Tests for ManagerConfig and AdapterRegistry classes using pytest.
"""

import threading
from unittest.mock import MagicMock

import pytest

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheStats,
    KeyValueInterface,
    PoolInterface,
    PoolStats,
    StatisticsInterface,
)


class TestManagerConfig:
    """Test cases for ManagerConfig dataclass."""

    def test_manager_config_default_values(self):
        """Test ManagerConfig with default values."""
        config = ManagerConfig()

        assert config.default_adapter is None
        assert config.auto_connect is True
        assert config.enable_global_stats is True
        assert config.health_check_interval == 60.0
        assert config.adapter_timeout == 5.0
        assert config.log_level == "INFO"
        assert config.namespace_separator == ":"
        assert config.enable_routing is True
        assert config.fallback_adapter is None
        assert config.extra_config == {}

    def test_manager_config_custom_values(self):
        """Test ManagerConfig with custom values."""
        custom_extra = {"custom_key": "custom_value"}
        config = ManagerConfig(
            default_adapter="redis",
            auto_connect=False,
            enable_global_stats=False,
            health_check_interval=30.0,
            adapter_timeout=10.0,
            log_level="DEBUG",
            namespace_separator="|",
            enable_routing=False,
            fallback_adapter="memory",
            extra_config=custom_extra,
        )

        assert config.default_adapter == "redis"
        assert config.auto_connect is False
        assert config.enable_global_stats is False
        assert config.health_check_interval == 30.0
        assert config.adapter_timeout == 10.0
        assert config.log_level == "DEBUG"
        assert config.namespace_separator == "|"
        assert config.enable_routing is False
        assert config.fallback_adapter == "memory"
        assert config.extra_config == custom_extra

    def test_manager_config_extra_config_is_mutable(self):
        """Test that extra_config is properly initialized as mutable dict."""
        config1 = ManagerConfig()
        config2 = ManagerConfig()

        config1.extra_config["test"] = "value"

        # Ensure configs don't share the same dict instance
        assert "test" not in config2.extra_config


class TestAdapterRegistry:
    """Test cases for AdapterRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh AdapterRegistry instance for each test."""
        return AdapterRegistry()

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock AdapterInterface."""
        # Don't use spec to avoid restrictions
        adapter = MagicMock()
        # Explicitly set all required methods and properties
        adapter.is_connected.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = True
        adapter.health_check.return_value = True
        adapter.get_backend_info.return_value = {}
        # Make isinstance work for AdapterInterface
        adapter.__class__ = type("MockAdapter", (AdapterInterface,), {})
        return adapter

    @pytest.fixture
    def mock_cache_adapter(self):
        """Create a mock KeyValueInterface adapter."""
        # Don't use spec to avoid restrictions
        adapter = MagicMock()
        # Set all required methods and properties FIRST
        adapter.is_connected.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = True
        adapter.health_check.return_value = True
        adapter.get_backend_info.return_value = {}
        adapter.get.return_value = None
        adapter.set.return_value = None
        adapter.delete.return_value = True
        adapter.exists.return_value = False
        adapter.clear.return_value = None
        adapter.size.return_value = 0
        adapter.keys.return_value = []
        adapter.get_many.return_value = {}
        adapter.set_many.return_value = None
        adapter.delete_many.return_value = None
        adapter.get_stats.return_value = CacheStats(hits=100, misses=50)
        adapter.reset_stats.return_value = True
        adapter._is_cache_adapter = True

        # Make isinstance() work correctly - set AFTER configuring methods
        adapter.__class__ = type("MockCacheAdapter", (KeyValueInterface, AdapterInterface), {})
        return adapter

    @pytest.fixture
    def mock_pool_adapter(self):
        """Create a mock PoolInterface adapter."""
        # Don't use spec to avoid restrictions
        adapter = MagicMock()
        # Set all required methods and properties FIRST
        adapter.is_connected.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = True
        adapter.health_check.return_value = True
        adapter.get_backend_info.return_value = {}
        adapter.put.return_value = None
        adapter.get.return_value = "pool_object"
        adapter.is_empty.return_value = False
        adapter.is_full.return_value = False
        adapter.size.return_value = 0
        adapter.borrow.return_value = "pool_object"
        adapter.clear.return_value = None
        adapter.reset_stats.return_value = True
        adapter.get_stats.return_value = PoolStats(
            created=0, borrowed=0, returned=0, destroyed=0, active=0, idle=0
        )
        adapter._is_pool_adapter = True

        # Make isinstance() work correctly - set AFTER configuring methods
        adapter.__class__ = type("MockPoolAdapter", (PoolInterface, AdapterInterface), {})
        return adapter

    @pytest.fixture
    def mock_stats_adapter(self):
        """Create a mock adapter with StatisticsInterface."""
        # Don't use spec to avoid restrictions
        adapter = MagicMock()
        # Set all required methods and properties FIRST
        adapter.is_connected.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = True
        adapter.health_check.return_value = True
        adapter.get_backend_info.return_value = {}
        adapter.get_stats.return_value = CacheStats(hits=100, misses=50)
        adapter.reset_stats.return_value = True

        # Make isinstance() work correctly - set AFTER configuring methods
        adapter.__class__ = type("MockStatsAdapter", (StatisticsInterface, AdapterInterface), {})
        return adapter

    def test_registry_initialization(self, registry):
        """Test AdapterRegistry initialization."""
        assert isinstance(registry._adapters, dict)
        assert isinstance(registry._cache_adapters, dict)
        assert isinstance(registry._pool_adapters, dict)
        assert isinstance(registry._adapter_configs, dict)
        assert isinstance(registry._adapter_stats, dict)
        assert registry._lock is not None

        # All collections should be empty initially
        assert len(registry._adapters) == 0
        assert len(registry._cache_adapters) == 0
        assert len(registry._pool_adapters) == 0
        assert len(registry._adapter_configs) == 0
        assert len(registry._adapter_stats) == 0

    def test_register_basic_adapter(self, registry, mock_adapter):
        """Test registering a basic adapter."""
        config = {"setting1": "value1"}

        registry.register("test_adapter", mock_adapter, config)

        assert "test_adapter" in registry._adapters
        assert registry._adapters["test_adapter"] == mock_adapter
        assert "test_adapter" in registry._adapter_configs
        assert registry._adapter_configs["test_adapter"] == config

    def test_register_cache_adapter(self, registry, mock_cache_adapter):
        """Test registering a cache adapter (KeyValueInterface)."""
        registry.register("cache_adapter", mock_cache_adapter)

        assert "cache_adapter" in registry._adapters
        assert "cache_adapter" in registry._cache_adapters
        assert registry._cache_adapters["cache_adapter"] == mock_cache_adapter

    def test_register_pool_adapter(self, registry, mock_pool_adapter):
        """Test registering a pool adapter (PoolInterface)."""
        registry.register("pool_adapter", mock_pool_adapter)

        assert "pool_adapter" in registry._adapters
        assert "pool_adapter" in registry._pool_adapters
        assert registry._pool_adapters["pool_adapter"] == mock_pool_adapter

    def test_register_adapter_without_config(self, registry, mock_adapter):
        """Test registering adapter without configuration."""
        registry.register("no_config_adapter", mock_adapter)

        assert "no_config_adapter" in registry._adapters
        assert "no_config_adapter" not in registry._adapter_configs

    def test_register_adapter_with_none_config(self, registry, mock_adapter):
        """Test registering adapter with None config explicitly."""
        registry.register("none_config_adapter", mock_adapter, None)

        assert "none_config_adapter" in registry._adapters
        assert "none_config_adapter" not in registry._adapter_configs

    def test_unregister_existing_adapter(self, registry, mock_cache_adapter):
        """Test unregistering an existing adapter."""
        config = {"test": "value"}
        registry.register("test_adapter", mock_cache_adapter, config)

        # Verify it's registered
        assert "test_adapter" in registry._adapters
        assert "test_adapter" in registry._cache_adapters
        assert "test_adapter" in registry._adapter_configs

        # Unregister
        result = registry.unregister("test_adapter")

        assert result is True
        assert "test_adapter" not in registry._adapters
        assert "test_adapter" not in registry._cache_adapters
        assert "test_adapter" not in registry._adapter_configs

    def test_unregister_nonexistent_adapter(self, registry):
        """Test unregistering a non-existent adapter."""
        result = registry.unregister("nonexistent")
        assert result is False

    def test_get_existing_adapter(self, registry, mock_adapter):
        """Test getting an existing adapter."""
        registry.register("test_adapter", mock_adapter)

        result = registry.get("test_adapter")
        assert result == mock_adapter

    def test_get_nonexistent_adapter(self, registry):
        """Test getting a non-existent adapter."""
        result = registry.get("nonexistent")
        assert result is None

    def test_get_cache_adapter_existing(self, registry, mock_cache_adapter):
        """Test getting an existing cache adapter."""
        registry.register("cache_adapter", mock_cache_adapter)

        result = registry.get_cache_adapter("cache_adapter")
        assert result == mock_cache_adapter

    def test_get_cache_adapter_nonexistent(self, registry):
        """Test getting a non-existent cache adapter."""
        result = registry.get_cache_adapter("nonexistent")
        assert result is None

    def test_get_pool_adapter_existing(self, registry, mock_pool_adapter):
        """Test getting an existing pool adapter."""
        registry.register("pool_adapter", mock_pool_adapter)

        result = registry.get_pool_adapter("pool_adapter")
        assert result == mock_pool_adapter

    def test_get_pool_adapter_nonexistent(self, registry):
        """Test getting a non-existent pool adapter."""
        result = registry.get_pool_adapter("nonexistent")
        assert result is None

    def test_list_all_empty(self, registry):
        """Test listing all adapters when registry is empty."""
        result = registry.list_all()
        assert result == []

    def test_list_all_with_adapters(self, registry, mock_adapter, mock_cache_adapter):
        """Test listing all adapters with registered adapters."""
        registry.register("adapter1", mock_adapter)
        registry.register("adapter2", mock_cache_adapter)

        result = registry.list_all()
        assert set(result) == {"adapter1", "adapter2"}

    def test_list_cache_adapters_empty(self, registry):
        """Test listing cache adapters when none registered."""
        result = registry.list_cache_adapters()
        assert result == []

    def test_list_cache_adapters_with_adapters(self, registry, mock_adapter, mock_cache_adapter):
        """Test listing cache adapters with mixed adapter types."""
        registry.register("basic_adapter", mock_adapter)
        registry.register("cache_adapter", mock_cache_adapter)

        result = registry.list_cache_adapters()
        assert result == ["cache_adapter"]

    def test_list_pool_adapters_empty(self, registry):
        """Test listing pool adapters when none registered."""
        result = registry.list_pool_adapters()
        assert result == []

    def test_list_pool_adapters_with_adapters(self, registry, mock_adapter, mock_pool_adapter):
        """Test listing pool adapters with mixed adapter types."""
        registry.register("basic_adapter", mock_adapter)
        registry.register("pool_adapter", mock_pool_adapter)

        result = registry.list_pool_adapters()
        assert result == ["pool_adapter"]

    def test_get_stats_with_statistics_interface(self, registry, mock_stats_adapter):
        """Test getting stats from adapter with StatisticsInterface."""
        registry.register("stats_adapter", mock_stats_adapter)

        result = registry.get_stats("stats_adapter")

        assert result == CacheStats(hits=100, misses=50).__dict__
        mock_stats_adapter.get_stats.assert_called_once()

    def test_get_stats_without_statistics_interface(self, registry, mock_adapter):
        """Test getting stats from adapter without StatisticsInterface."""
        registry.register("basic_adapter", mock_adapter)
        mock_adapter.get_stats.return_value = None

        result = registry.get_stats("basic_adapter")
        assert result is None

    def test_get_stats_nonexistent_adapter(self, registry):
        """Test getting stats from non-existent adapter."""
        result = registry.get_stats("nonexistent")
        assert result is None

    def test_get_stats_with_none_stats(self, registry):
        """Test getting stats when adapter returns None."""
        # Don't use spec to avoid restrictions
        mock_adapter = MagicMock()
        # Set all required methods and properties FIRST
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True
        mock_adapter.disconnect.return_value = True
        mock_adapter.health_check.return_value = True
        mock_adapter.get_backend_info.return_value = {}
        mock_adapter.get_stats.return_value = None
        mock_adapter.reset_stats.return_value = True

        # Make isinstance() work correctly - set AFTER configuring methods
        mock_adapter.__class__ = type(
            "MockNullStatsAdapter", (StatisticsInterface, AdapterInterface), {}
        )

        registry.register("null_stats_adapter", mock_adapter)

        result = registry.get_stats("null_stats_adapter")
        assert result is None

    def test_thread_safety_register_unregister(self, registry):
        """Test thread safety of register/unregister operations."""
        mock_adapters = []
        for i in range(10):
            # Don't use spec to avoid restrictions
            adapter = MagicMock()
            # Set all required methods and properties
            adapter.is_connected.return_value = True
            adapter.connect.return_value = True
            adapter.disconnect.return_value = True
            adapter.health_check.return_value = True
            adapter.get_backend_info.return_value = {}
            # Make isinstance work for AdapterInterface
            adapter.__class__ = type(f"MockThreadAdapter{i}", (AdapterInterface,), {})
            mock_adapters.append(adapter)

        results = []

        def register_adapter(index):
            adapter = mock_adapters[index]
            registry.register(f"adapter_{index}", adapter)
            results.append(f"registered_{index}")

        def unregister_adapter(index):
            registry.unregister(f"adapter_{index}")
            results.append(f"unregistered_{index}")

        # Create threads for concurrent registration
        threads = []
        for i in range(5):
            thread = threading.Thread(target=register_adapter, args=(i,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all adapters were registered
        assert len(registry.list_all()) == 5

        # Create threads for concurrent unregistration
        threads = []
        for i in range(5):
            thread = threading.Thread(target=unregister_adapter, args=(i,))
            threads.append(thread)

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify all adapters were unregistered
        assert len(registry.list_all()) == 0

    def test_config_copying_behavior(self, registry, mock_adapter):
        """Test that configuration dictionaries are properly copied."""
        original_config = {"setting": "value", "nested": {"key": "value"}}

        registry.register("test_adapter", mock_adapter, original_config)

        # Modify original config
        original_config["setting"] = "modified"
        original_config["nested"]["key"] = "modified"

        # Stored config should be unchanged
        stored_config = registry._adapter_configs["test_adapter"]
        assert stored_config["setting"] == "value"
        assert stored_config["nested"]["key"] == "value"

    def test_multiple_interface_adapter(self, registry):
        """Test adapter that implements multiple interfaces."""
        # Create adapter that implements both KeyValueInterface and PoolInterface
        mock_adapter = MagicMock()

        # Make isinstance() work correctly for multiple interfaces
        # This is the key fix: we need to make isinstance() return True
        # for each interface the adapter should implement
        mock_adapter.__class__ = type(
            "MockMultiAdapter", (AdapterInterface, KeyValueInterface, PoolInterface), {}
        )

        # Set up all required methods and properties
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True
        mock_adapter.disconnect.return_value = True
        mock_adapter.health_check.return_value = True
        mock_adapter.get_backend_info.return_value = {}

        # KeyValueInterface methods
        mock_adapter.get.return_value = None
        mock_adapter.set.return_value = None
        mock_adapter.delete.return_value = True
        mock_adapter.exists.return_value = False
        mock_adapter.clear.return_value = None
        mock_adapter.size.return_value = 0
        mock_adapter.keys.return_value = []
        mock_adapter.get_many.return_value = {}
        mock_adapter.set_many.return_value = None
        mock_adapter.delete_many.return_value = None

        # PoolInterface methods
        mock_adapter.put.return_value = None
        mock_adapter.get.return_value = "pool_object"  # This will override the cache get
        mock_adapter.is_empty.return_value = False
        mock_adapter.is_full.return_value = False
        mock_adapter.borrow.return_value = "pool_object"

        registry.register("multi_adapter", mock_adapter)

        assert "multi_adapter" in registry._adapters
        assert "multi_adapter" in registry._cache_adapters
        assert "multi_adapter" in registry._pool_adapters

        # Should be retrievable through all methods
        assert registry.get("multi_adapter") == mock_adapter
        assert registry.get_cache_adapter("multi_adapter") == mock_adapter
        assert registry.get_pool_adapter("multi_adapter") == mock_adapter

    def test_unregister_cleans_all_collections(self, registry):
        """Test that unregister removes adapter from all relevant collections."""
        # Create adapter with stats
        mock_adapter = MagicMock()

        # Make isinstance() work correctly for multiple interfaces including StatisticsInterface
        mock_adapter.__class__ = type(
            "MockMultiStatsAdapter",
            (AdapterInterface, KeyValueInterface, PoolInterface, StatisticsInterface),
            {},
        )

        # Set up all required methods and properties
        mock_adapter.is_connected.return_value = True
        mock_adapter.connect.return_value = True
        mock_adapter.disconnect.return_value = True
        mock_adapter.health_check.return_value = True
        mock_adapter.get_backend_info.return_value = {}
        mock_adapter.get_stats.return_value = CacheStats(hits=100, misses=50)
        mock_adapter.reset_stats.return_value = True

        # KeyValueInterface methods
        mock_adapter.get.return_value = None
        mock_adapter.set.return_value = None
        mock_adapter.delete.return_value = True
        mock_adapter.exists.return_value = False
        mock_adapter.clear.return_value = None
        mock_adapter.size.return_value = 0
        mock_adapter.keys.return_value = []
        mock_adapter.get_many.return_value = {}
        mock_adapter.set_many.return_value = None
        mock_adapter.delete_many.return_value = None

        # PoolInterface methods
        mock_adapter.put.return_value = None
        mock_adapter.is_empty.return_value = False
        mock_adapter.is_full.return_value = False
        mock_adapter.borrow.return_value = "pool_object"

        config = {"test": "config"}

        registry.register("multi_adapter", mock_adapter, config)

        # Add some stats manually (simulating stats collection)
        registry._adapter_stats["multi_adapter"] = {"test_stat": "value"}

        # Verify everything is registered
        assert "multi_adapter" in registry._adapters
        assert "multi_adapter" in registry._cache_adapters
        assert "multi_adapter" in registry._pool_adapters
        assert "multi_adapter" in registry._adapter_configs
        assert "multi_adapter" in registry._adapter_stats

        # Unregister
        result = registry.unregister("multi_adapter")

        assert result is True
        assert "multi_adapter" not in registry._adapters
        assert "multi_adapter" not in registry._cache_adapters
        assert "multi_adapter" not in registry._pool_adapters
        assert "multi_adapter" not in registry._adapter_configs
        assert "multi_adapter" not in registry._adapter_stats
