"""
Unit tests for src/omni_cache/core/manager.py using pytest.

This module contains comprehensive tests for the CacheManager class,
covering all interfaces it implements and core functionality.
"""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
    CacheStats,
    FactoryInterface,
    KeyValueInterface,
    PoolInterface,
    PoolStats,
)
from omni_cache.core.manager import CacheManager, get_global_manager, set_global_manager


class MockAdapter(AdapterInterface, KeyValueInterface, PoolInterface):
    """Mock adapter for testing."""

    def __init__(self, name: str = "mock", auto_fail: bool = False):
        self.name = name
        self.auto_fail = auto_fail
        self._connected = False
        self._data = {}
        self._pool_objects = []
        self.connect_calls = 0
        self.disconnect_calls = 0

    # AdapterInterface
    def connect(self) -> bool:
        self.connect_calls += 1
        if self.auto_fail:
            return False
        self._connected = True
        return True

    def disconnect(self) -> bool:
        self.disconnect_calls += 1
        self._connected = False
        return True

    def is_connected(self) -> bool:
        return self._connected

    def health_check(self) -> bool:
        return self._connected and not self.auto_fail

    def get_backend_info(self) -> dict:
        return {
            "backend": "mock",
            "name": self.name,
            "connected": self._connected,
            "data_size": len(self._data),
            "pool_size": len(self._pool_objects),
        }

    def get_stats(self) -> CacheStats:
        return CacheStats(hits=10, misses=5, sets=8, deletes=3)

    # KeyValueInterface
    def get(self, key, default=None):
        if self.auto_fail:
            raise RuntimeError("Mock failure")
        return self._data.get(key, default)

    def set(self, key, value, ttl=None):
        if self.auto_fail:
            return False
        self._data[key] = value
        return True

    def delete(self, key):
        if self.auto_fail:
            return False
        return self._data.pop(key, None) is not None

    def exists(self, key):
        return key in self._data

    def clear(self):
        if self.auto_fail:
            return False
        self._data.clear()
        return True

    def keys(self):
        return iter(self._data.keys())

    def size(self):
        if hasattr(self, "_pool_objects") and self._pool_objects:
            return len(self._pool_objects)  # For pool operations
        return len(self._data)  # For cache operations

    # PoolInterface
    def _get_pool_object(self, timeout=None):  # Pool get
        if self.auto_fail:
            return None
        if self._pool_objects:
            return self._pool_objects.pop()
        return f"pool_object_{time.time()}"

    def put(self, obj, timeout=None):
        if self.auto_fail:
            return False
        self._pool_objects.append(obj)
        return True

    def is_empty(self):
        return len(self._pool_objects) == 0

    def borrow(self, timeout=None):
        # Mock context manager
        from contextlib import contextmanager

        @contextmanager
        def _borrow():
            obj = self._get_pool_object(timeout)
            try:
                yield obj
            finally:
                if obj:
                    self.put(obj)

        return _borrow()


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing."""
    return MockAdapter()


class TestManagerConfig:
    """Test cases for ManagerConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
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

    def test_custom_config(self):
        """Test custom configuration values."""
        custom_config = {
            "default_adapter": "test_adapter",
            "auto_connect": False,
            "enable_global_stats": False,
            "health_check_interval": 120.0,
            "adapter_timeout": 10.0,
            "log_level": "DEBUG",
            "namespace_separator": "|",
            "enable_routing": False,
            "fallback_adapter": "fallback",
            "extra_config": {"custom": "value"},
        }

        config = ManagerConfig(**custom_config)

        assert config.default_adapter == "test_adapter"
        assert config.auto_connect is False
        assert config.enable_global_stats is False
        assert config.health_check_interval == 120.0
        assert config.adapter_timeout == 10.0
        assert config.log_level == "DEBUG"
        assert config.namespace_separator == "|"
        assert config.enable_routing is False
        assert config.fallback_adapter == "fallback"
        assert config.extra_config == {"custom": "value"}


class TestCacheManager:
    @pytest.fixture
    def manager(self):
        """Create a fresh CacheManager for testing."""
        return CacheManager()

    def test_init_default_config(self):
        """Test CacheManager initialization with default config."""
        manager = CacheManager()

        assert isinstance(manager._config, ManagerConfig)
        assert manager._config.default_adapter is None
        assert manager._config.auto_connect is True
        assert isinstance(manager._registry, AdapterRegistry)
        assert manager._global_stats["cache"].hits == 0
        assert manager._global_stats["pool"].borrowed == 0

    def test_init_with_dict_config(self):
        """Test CacheManager initialization with dictionary config."""
        config = {"default_adapter": "test", "auto_connect": False, "log_level": "DEBUG"}
        manager = CacheManager(config)

        assert manager._config.default_adapter == "test"
        assert manager._config.auto_connect is False
        assert manager._config.log_level == "DEBUG"

    def test_init_with_manager_config(self):
        """Test CacheManager initialization with ManagerConfig instance."""
        config = ManagerConfig(default_adapter="test", auto_connect=False)
        manager = CacheManager(config)

        assert manager._config.default_adapter == "test"
        assert manager._config.auto_connect is False

    @patch("omni_cache.core.manager.logging.getLogger")
    def test_setup_logger(self, mock_get_logger, manager):
        """Test logger setup."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        logger = manager._setup_logger()

        mock_get_logger.assert_called_with("omni_cache.manager")
        assert logger == mock_logger

    def test_register_adapter_success(self, manager, mock_adapter):
        """Test successful adapter registration."""
        result = manager.register_adapter("test", mock_adapter)

        assert result is True
        assert manager.get_adapter("test") == mock_adapter
        assert "test" in manager.list_adapters()
        assert mock_adapter.connect_calls == 1  # auto_connect is True by default

    def test_register_adapter_no_auto_connect(self, mock_adapter):
        """Test adapter registration without auto-connect."""
        config = ManagerConfig(auto_connect=False)
        manager = CacheManager(config)

        result = manager.register_adapter("test", mock_adapter)

        assert result is True
        assert mock_adapter.connect_calls == 0

    def test_register_adapter_connect_failure(self, manager):
        """Test adapter registration when connection fails."""
        failing_adapter = MockAdapter(auto_fail=True)

        result = manager.register_adapter("test", failing_adapter)

        assert result is False
        assert manager.get_adapter("test") is None

    def test_register_adapter_exception(self, manager):
        """Test adapter registration with exception."""
        mock_adapter = Mock()
        mock_adapter.is_connected.side_effect = Exception("Connection error")

        result = manager.register_adapter("test", mock_adapter)

        assert result is False

    def test_register_adapter_replaces_existing(self, manager, mock_adapter):
        """Test that registering an adapter with existing name replaces it."""
        old_adapter = MockAdapter("old")
        new_adapter = MockAdapter("new")

        manager.register_adapter("test", old_adapter)
        result = manager.register_adapter("test", new_adapter)

        assert result is True
        assert manager.get_adapter("test") == new_adapter

    def test_get_adapter_exists(self, manager, mock_adapter):
        """Test getting an existing adapter."""
        manager.register_adapter("test", mock_adapter)

        adapter = manager.get_adapter("test")

        assert adapter == mock_adapter

    def test_get_adapter_not_exists(self, manager):
        """Test getting a non-existent adapter."""
        adapter = manager.get_adapter("nonexistent")

        assert adapter is None

    def test_list_adapters_empty(self, manager):
        """Test listing adapters when none are registered."""
        adapters = manager.list_adapters()

        assert adapters == []

    def test_list_adapters_multiple(self, manager):
        """Test listing multiple registered adapters."""
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        manager.register_adapter("test1", adapter1)
        manager.register_adapter("test2", adapter2)

        adapters = manager.list_adapters()

        assert len(adapters) == 2
        assert "test1" in adapters
        assert "test2" in adapters

    def test_remove_adapter_exists(self, manager, mock_adapter):
        """Test removing an existing adapter."""
        manager.register_adapter("test", mock_adapter)

        result = manager.remove_adapter("test")

        assert result is True
        assert manager.get_adapter("test") is None
        assert "test" not in manager.list_adapters()

    def test_remove_adapter_not_exists(self, manager):
        """Test removing a non-existent adapter."""
        result = manager.remove_adapter("nonexistent")

        assert result is False

    def test_remove_adapter_with_disconnect(self, manager, mock_adapter):
        """Test removing adapter calls disconnect."""
        manager.register_adapter("test", mock_adapter)

        result = manager.remove_adapter("test")

        assert result is True
        assert mock_adapter.disconnect_calls == 1

    def test_register_factory(self, manager):
        """Test factory registration."""
        with patch.object(manager, "_factory_manager") as mock_factory_manager:
            mock_factory = Mock(spec=FactoryInterface)

            manager.register_factory(CacheBackend.MEMORY, mock_factory)

            mock_factory_manager.register_factory.assert_called_once_with(
                CacheBackend.MEMORY, mock_factory
            )

    def test_create_adapter_success(self, manager):
        """Test successful adapter creation via factory."""
        with patch.object(manager._factory_manager, "create_adapter") as mock_create:
            mock_adapter = MockAdapter()
            mock_create.return_value = mock_adapter

            result = manager.create_adapter("test", CacheBackend.MEMORY, {"size": 100})

            assert result is True
            mock_create.assert_called_once_with("test", CacheBackend.MEMORY, {"size": 100})

    def test_create_adapter_failure(self, manager):
        """Test adapter creation failure via factory."""
        with patch.object(manager._factory_manager, "create_adapter") as mock_create:
            mock_create.side_effect = Exception("Creation failed")

            result = manager.create_adapter("test", CacheBackend.MEMORY)

            assert result is False

    def test_get_success(self, manager, mock_adapter):
        """Test successful cache get operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")

        result = manager.get("key1")

        assert result == "value1"

    def test_get_with_default(self, manager, mock_adapter):
        """Test cache get operation with default value."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"

        result = manager.get("nonexistent", "default")

        assert result == "default"

    def test_get_with_adapter_param(self, manager, mock_adapter):
        """Test cache get operation with specific adapter."""
        manager.register_adapter("specific", mock_adapter)
        mock_adapter.set("key1", "value1")

        result = manager.get("key1", adapter="specific")

        assert result == "value1"

    def test_get_exception_handling(self, manager):
        """Test cache get operation exception handling."""
        failing_adapter = MockAdapter(auto_fail=True)
        manager.register_adapter("test", failing_adapter)
        manager._config.default_adapter = "test"

        result = manager.get("key1", "default")

        assert result == "default"

    def test_set_success(self, manager, mock_adapter):
        """Test successful cache set operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"

        result = manager.set("key1", "value1", ttl=300)

        assert result is True
        assert mock_adapter.get("key1") == "value1"

    def test_set_failure(self, manager):
        """Test cache set operation failure."""
        failing_adapter = MockAdapter(auto_fail=True)
        manager.register_adapter("test", failing_adapter)
        manager._config.default_adapter = "test"

        result = manager.set("key1", "value1")

        assert result is False

    def test_delete_success(self, manager, mock_adapter):
        """Test successful cache delete operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")

        result = manager.delete("key1")

        assert result is True
        assert mock_adapter.get("key1") is None

    def test_delete_nonexistent_key(self, manager, mock_adapter):
        """Test deleting non-existent key."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"

        result = manager.delete("nonexistent")

        assert result is False

    def test_exists_true(self, manager, mock_adapter):
        """Test exists operation returns True for existing key."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")

        result = manager.exists("key1")

        assert result is True

    def test_exists_false(self, manager, mock_adapter):
        """Test exists operation returns False for non-existent key."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"

        result = manager.exists("nonexistent")

        assert result is False

    def test_clear_success(self, manager, mock_adapter):
        """Test successful clear operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")
        mock_adapter.set("key2", "value2")

        result = manager.clear()

        assert result is True
        assert mock_adapter.size() == 0

    def test_keys_operation(self, manager, mock_adapter):
        """Test keys operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")
        mock_adapter.set("key2", "value2")

        keys = list(manager.keys())

        assert len(keys) == 2
        assert "key1" in keys
        assert "key2" in keys

    def test_size_operation(self, manager, mock_adapter):
        """Test size operation."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")
        mock_adapter.set("key2", "value2")

        size = manager.size()

        assert size == 2

    # PoolInterface tests
    def test_pool_get_success(self, manager):
        """Test pool get operation."""
        pool_adapter = MockAdapter("pool")
        manager.register_adapter("pool", pool_adapter)

        # Ajouter un objet spécifique au pool
        pool_adapter.put("test_object")

        # Utiliser get_object_pool pour les opérations pool
        obj = manager.get_object_pool(adapter="pool")

        assert obj == "test_object"

    def test_pool_put_success(self, manager, mock_adapter):
        """Test successful pool put operation."""
        manager.register_adapter("pool", mock_adapter)

        result = manager.put("object1", adapter="pool")

        assert result is True
        assert "object1" in mock_adapter._pool_objects

    def test_pool_is_empty_true(self, manager, mock_adapter):
        """Test is_empty returns True for empty pool."""
        manager.register_adapter("pool", mock_adapter)
        manager._config.default_adapter = "pool"

        result = manager.is_empty()

        assert result is True

    def test_pool_is_empty_false(self, manager, mock_adapter):
        """Test is_empty returns False for non-empty pool."""
        manager.register_adapter("pool", mock_adapter)
        manager._config.default_adapter = "pool"
        mock_adapter.put("object1")

        result = manager.is_empty()

        assert result is False

    def test_pool_borrow_context_manager(self, manager):
        """Test pool borrow context manager."""
        pool_adapter = MockAdapter("pool")
        manager.register_adapter("pool", pool_adapter)

        # Ajouter un objet spécifique au pool
        pool_adapter.put("test_object")

        with manager.borrow(adapter="pool") as obj:
            assert obj == "test_object"

        # L'objet devrait être retourné au pool
        assert not pool_adapter.is_empty()

    def test_get_global_stats(self, manager):
        """Test getting global statistics."""
        stats = manager.get_global_stats()

        assert "cache" in stats
        assert "pool" in stats
        assert isinstance(stats["cache"], CacheStats)
        assert isinstance(stats["pool"], PoolStats)

    def test_get_adapter_stats(self, manager, mock_adapter):
        """Test getting adapter-specific statistics."""
        manager.register_adapter("test", mock_adapter)

        # Configurer le mock pour retourner des stats
        mock_stats = CacheStats(hits=10, misses=5)
        mock_adapter.get_stats = Mock(return_value=mock_stats)

        stats = manager.get_adapter_stats("test")

        assert stats is not None
        assert "hits" in stats
        assert stats["hits"] == 10

    def test_get_adapter_stats_nonexistent(self, manager):
        """Test getting stats for non-existent adapter."""
        stats = manager.get_adapter_stats("nonexistent")

        assert stats == {}

    def test_global_stats_updates_on_operations(self, manager, mock_adapter):
        """Test that global statistics are updated on cache operations."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"
        mock_adapter.set("key1", "value1")

        # Perform operations
        manager.get("key1")  # Hit
        manager.get("nonexistent")  # Miss
        manager.set("key2", "value2")  # Set

        stats = manager.get_global_stats()
        assert stats["cache"].hits == 1
        assert stats["cache"].misses == 1
        assert stats["cache"].sets == 1

    # Configuration tests
    def test_configure_method(self, manager):
        """Test configure method."""
        config = {"default_adapter": "new_default"}

        result = manager.configure(config)

        assert result is True
        assert manager._config.default_adapter == "new_default"

    def test_get_config_method(self, manager):
        """Test get_config method."""
        config = manager.get_config()

        assert isinstance(config, dict)
        assert "default_adapter" in config
        assert "auto_connect" in config
        assert "enable_global_stats" in config

    # Context manager tests
    def test_context_manager_entry_exit(self, manager, mock_adapter):
        """Test context manager behavior."""
        manager.register_adapter("test", mock_adapter)

        with manager:
            assert manager.get_adapter("test") is not None

        # Should disconnect all adapters on exit
        assert mock_adapter.disconnect_calls == 1

    def test_disconnect_all(self, manager):
        """Test disconnect_all method."""
        adapter1 = MockAdapter("adapter1")
        adapter2 = MockAdapter("adapter2")

        manager.register_adapter("test1", adapter1)
        manager.register_adapter("test2", adapter2)

        manager.disconnect_all()

        assert adapter1.disconnect_calls == 1
        assert adapter2.disconnect_calls == 1

    def test_disconnect_all_with_exception(self, manager):
        """Test disconnect_all handles exceptions gracefully."""
        mock_adapter = Mock()
        mock_adapter.disconnect.side_effect = Exception("Disconnect error")

        manager._registry.register("test", mock_adapter)

        # Should not raise exception
        manager.disconnect_all()

    def test_repr(self, manager, mock_adapter):
        """Test string representation of CacheManager."""
        manager.register_adapter("test", mock_adapter)
        manager._config.default_adapter = "test"

        repr_str = repr(manager)

        assert "CacheManager" in repr_str
        assert "adapters=1" in repr_str
        assert "default='test'" in repr_str
        assert "['test']" in repr_str


class TestGlobalManagerFunctions:
    """Test cases for global manager functions."""

    def teardown_method(self):
        """Clean up global manager after each test."""
        # Reset global manager
        import omni_cache.core.manager as manager_module

        manager_module._global_manager = None

    def test_get_global_manager_creates_new(self):
        """Test get_global_manager creates new instance if none exists."""
        manager = get_global_manager()

        assert isinstance(manager, CacheManager)

        # Should return same instance on subsequent calls
        manager2 = get_global_manager()
        assert manager is manager2

    def test_set_global_manager(self):
        """Test set_global_manager sets the global instance."""
        custom_manager = CacheManager()

        set_global_manager(custom_manager)

        retrieved_manager = get_global_manager()
        assert retrieved_manager is custom_manager

    def test_thread_safety_global_manager(self):
        """Test thread safety of global manager access."""
        managers = []

        def get_manager():
            managers.append(get_global_manager())

        threads = [threading.Thread(target=get_manager) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same manager instance
        assert all(manager is managers[0] for manager in managers)
        assert len(set(id(manager) for manager in managers)) == 1


class TestIntegrationScenarios:
    """Integration test scenarios."""

    def test_full_cache_workflow(self):
        """Test complete cache workflow with multiple adapters."""
        manager = CacheManager()

        # Register multiple adapters
        memory_adapter = MockAdapter("memory")
        redis_adapter = MockAdapter("redis")

        manager.register_adapter("memory", memory_adapter)
        manager.register_adapter("redis", redis_adapter)
        manager._config.default_adapter = "memory"

        # Set some data
        assert manager.set("user:123", {"name": "John", "age": 30})
        assert manager.set("user:456", {"name": "Jane", "age": 25}, adapter="redis")

        # Retrieve data
        user1 = manager.get("user:123")
        user2 = manager.get("user:456", adapter="redis")

        assert user1 == {"name": "John", "age": 30}
        assert user2 == {"name": "Jane", "age": 25}

        # Check existence
        assert manager.exists("user:123")
        assert manager.exists("user:456", adapter="redis")

        # Get statistics
        stats = manager.get_global_stats()
        assert stats["cache"].hits >= 2
        assert stats["cache"].sets >= 2

        # Clean up
        assert manager.delete("user:123")
        assert manager.delete("user:456", adapter="redis")
        assert not manager.exists("user:123")

    def test_pool_workflow(self):
        """Test complete pool workflow."""
        manager = CacheManager()
        pool_adapter = MockAdapter("pool")

        manager.register_adapter("pool", pool_adapter)

        # Add objects to pool
        assert manager.put("connection1", adapter="pool")
        assert manager.put("connection2", adapter="pool")

        # Pool should not be empty
        assert not manager.is_empty(adapter="pool")
        assert manager.size(adapter="pool") == 2

        # Get objects from pool
        obj1 = manager.get_object_pool(adapter="pool")
        obj2 = manager.get_object_pool(adapter="pool")

        assert obj1 in ["connection1", "connection2"]
        assert obj2 in ["connection1", "connection2"]
        assert obj1 != obj2

        # Pool should be empty now
        assert manager.is_empty(adapter="pool")

        # Use borrow context manager
        manager.put("connection3", adapter="pool")
        with manager.borrow(adapter="pool") as conn:
            assert conn == "connection3"

        # Connection should be back in pool
        assert not manager.is_empty(adapter="pool")

    def test_error_handling_and_fallback(self):
        """Test error handling and fallback scenarios."""
        manager = CacheManager()

        # Register a failing adapter
        failing_adapter = MockAdapter("failing", auto_fail=True)
        working_adapter = MockAdapter("working")

        manager.register_adapter("failing", failing_adapter)
        manager.register_adapter("working", working_adapter)

        # Operations on failing adapter should handle gracefully
        assert not manager.set("key", "value", adapter="failing")
        assert manager.get("key", "default", adapter="failing") == "default"

        # Working adapter should work normally
        assert manager.set("key", "value", adapter="working")
        assert manager.get("key", adapter="working") == "value"

    def test_health_monitoring_integration(self, mock_adapter):
        """Test integration with health monitoring."""
        manager = CacheManager(ManagerConfig(health_check_interval=0.1))

        manager.register_adapter("test", mock_adapter)

        # Adapter should be connected and healthy
        assert mock_adapter.is_connected()
        assert mock_adapter.health_check()

        # Verify health monitoring is working
        assert hasattr(manager, "_health_monitor")

        # Clean up
        manager.disconnect_all()

    @patch("omni_cache.core.manager.logging.getLogger")
    def test_logging_integration(self, mock_get_logger):
        """Test logging integration throughout operations."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        manager = CacheManager()
        adapter = MockAdapter()

        # Register adapter should log
        manager.register_adapter("test", adapter)

        # Verify logging calls were made
        mock_logger.info.assert_called()

        # Test error logging
        failing_adapter = MockAdapter(auto_fail=True)
        manager.register_adapter("failing", failing_adapter)

        mock_logger.error.assert_called()
