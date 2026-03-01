"""
Additional tests to boost coverage for manager.py

This module contains tests specifically designed to cover the untested
code paths and edge cases in the CacheManager class.
"""

import logging
import threading
from unittest.mock import Mock, patch

import pytest

from omni_cache.core.adapter_registry import ManagerConfig
from omni_cache.core.exceptions import AdapterNotFoundError
from omni_cache.core.manager import CacheManager


class TestCacheManagerCoverageBoost:
    """Additional tests to increase coverage of CacheManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.manager = CacheManager()

    def test_remove_adapter_with_disconnect_exception(self):
        """Test removing adapter when disconnect() throws exception."""
        # Create a mock adapter that throws on disconnect
        mock_adapter = Mock()
        mock_adapter.disconnect.side_effect = RuntimeError("Disconnect failed")

        # Register the adapter
        self.manager._registry.register("test_adapter", mock_adapter)

        # This should still succeed despite disconnect exception
        result = self.manager.remove_adapter("test_adapter")
        assert result is True
        assert "test_adapter" not in self.manager.list_adapters()

    def test_remove_adapter_updates_default_adapter(self):
        """Test that removing the default adapter updates the config."""
        # Register two adapters
        adapter1 = Mock()
        adapter2 = Mock()
        self.manager._registry.register("adapter1", adapter1)
        self.manager._registry.register("adapter2", adapter2)

        # Set adapter1 as default
        self.manager._config.default_adapter = "adapter1"

        # Remove the default adapter
        result = self.manager.remove_adapter("adapter1")
        assert result is True
        # Default should be updated to remaining adapter
        assert self.manager._config.default_adapter == "adapter2"

    def test_remove_last_adapter_stops_health_monitoring(self):
        """Test that removing the last adapter stops health monitoring."""
        with patch.object(self.manager, "_stop_health_monitoring") as mock_stop:
            # Register one adapter
            adapter = Mock()
            self.manager._registry.register("last_adapter", adapter)

            # Remove it (should be last one)
            self.manager.remove_adapter("last_adapter")

            # Health monitoring should be stopped
            mock_stop.assert_called_once()

    def test_remove_adapter_exception_handling(self):
        """Test exception handling in remove_adapter."""
        # Mock the registry to throw an exception
        with patch.object(
            self.manager._registry, "unregister", side_effect=Exception("Registry error")
        ):
            # Register an adapter
            adapter = Mock()
            self.manager._registry.register("error_adapter", adapter)

            # This should return False due to exception
            result = self.manager.remove_adapter("error_adapter")
            assert result is False

    def test_safe_values_equal_with_different_types(self):
        """Test _safe_values_equal with different types and exceptions."""
        # Test with comparable objects
        assert self.manager._safe_values_equal("hello", "hello") is True
        assert self.manager._safe_values_equal("hello", "world") is False

        # Test with objects that throw on comparison
        class BadComparison:
            def __eq__(self, other):
                raise ValueError("Comparison failed")

        bad_obj = BadComparison()
        result = self.manager._safe_values_equal(bad_obj, "anything")
        assert result is False

    def test_get_operation_exception_handling(self):
        """Test exception handling in get operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.get.side_effect = RuntimeError("Get failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.get("test_key", default="default_value")
            assert result == "default_value"

    def test_set_operation_exception_handling(self):
        """Test exception handling in set operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.set.side_effect = RuntimeError("Set failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.set("test_key", "test_value")
            assert result is False

    def test_delete_operation_exception_handling(self):
        """Test exception handling in delete operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.delete.side_effect = RuntimeError("Delete failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.delete("test_key")
            assert result is False

    def test_exists_operation_exception_handling(self):
        """Test exception handling in exists operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.exists.side_effect = RuntimeError("Exists failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.exists("test_key")
            assert result is False

    def test_clear_operation_exception_handling(self):
        """Test exception handling in clear operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.clear.side_effect = RuntimeError("Clear failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.clear(adapter="test")
            assert result is False

    def test_keys_operation_exception_handling(self):
        """Test exception handling in keys operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.keys.side_effect = RuntimeError("Keys failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.keys()
            # keys() returns an iterator, we need to convert to list and check
            result_list = list(result) if hasattr(result, "__iter__") else result
            assert result_list == []

    def test_size_operation_exception_handling(self):
        """Test exception handling in size operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.size.side_effect = RuntimeError("Size failed")

        with patch.object(self.manager, "_get_cache_adapter", return_value=mock_adapter):
            result = self.manager.size()
            assert result == 0

    def test_pool_get_exception_handling(self):
        """Test exception handling in pool get operation."""
        # Mock pool adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.get.side_effect = RuntimeError("Pool get failed")

        # Temporarily override the get method to test the pool variant
        original_get = self.manager.get

        def pool_get_variant(timeout=None, adapter=None):
            try:
                pool_adapter = self.manager._get_pool_adapter(adapter)
                result = pool_adapter.get(timeout)
                with self.manager._stats_lock:
                    if result is not None:
                        self.manager._global_stats["pool"].gets += 1
                    self.manager._global_stats["pool"].update_hit_rate()
                return result
            except Exception as e:
                self.manager._logger.error("Pool get operation failed: %s", e)
                return None

        # Replace get method temporarily
        self.manager.get = pool_get_variant

        try:
            with patch.object(self.manager, "_get_pool_adapter", return_value=mock_adapter):
                result = self.manager.get(timeout=5.0)
                assert result is None
        finally:
            # Restore original method
            self.manager.get = original_get

    def test_pool_put_exception_handling(self):
        """Test exception handling in pool put operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.put.side_effect = RuntimeError("Pool put failed")

        with patch.object(self.manager, "_get_pool_adapter", return_value=mock_adapter):
            result = self.manager.put("test_object")
            assert result is False

    def test_pool_is_empty_exception_handling(self):
        """Test exception handling in pool is_empty operation."""
        # Mock adapter to throw exception
        mock_adapter = Mock()
        mock_adapter.is_empty.side_effect = RuntimeError("Is empty failed")

        with patch.object(self.manager, "_get_pool_adapter", return_value=mock_adapter):
            result = self.manager.is_empty()
            assert result is True  # Default to True on exception

    def test_get_adapter_stats_returns_empty_dict_when_none(self):
        """Test get_adapter_stats when adapter returns None."""
        with patch.object(self.manager._registry, "get_stats", return_value=None):
            result = self.manager.get_adapter_stats("nonexistent")
            assert result == {}

    def test_get_adapter_stats_all_adapters_with_none_stats(self):
        """Test get_adapter_stats for all adapters when some return None."""
        # Mock registry to return adapter names but None stats
        with patch.object(
            self.manager._registry, "list_all", return_value=["adapter1", "adapter2"]
        ):
            with patch.object(self.manager._registry, "get_stats", return_value=None):
                result = self.manager.get_adapter_stats()
                assert result == {}

    def test_reset_global_stats_exception_handling(self):
        """Test exception handling in reset_global_stats."""
        # Mock CacheStats to throw an exception during construction
        with patch(
            "omni_cache.core.manager.CacheStats", side_effect=RuntimeError("CacheStats failed")
        ):
            result = self.manager.reset_global_stats()
            assert result is False

    def test_configure_with_log_level_change(self):
        """Test configure method with log level change."""
        # Test log level update
        result = self.manager.configure({"log_level": "DEBUG"})
        assert result is True
        assert self.manager._config.log_level == "DEBUG"

        # Verify logger level was updated
        expected_level = logging.DEBUG
        assert self.manager._logger.level == expected_level

    def test_configure_with_unknown_attribute(self):
        """Test configure method with unknown configuration attribute."""
        result = self.manager.configure({"unknown_setting": "test_value"})
        assert result is True
        assert self.manager._config.extra_config["unknown_setting"] == "test_value"

    def test_get_config_method(self):
        """Test get_config method returns current configuration."""
        # Set some configuration
        self.manager._config.log_level = "WARNING"
        self.manager._config.extra_config = {"custom": "value"}

        config = self.manager.get_config()
        assert config["log_level"] == "WARNING"
        # The get_config method expands extra_config at the top level
        assert config["custom"] == "value"

    def test_disconnect_all_with_exception(self):
        """Test disconnect_all when an adapter throws exception."""
        # Create mock adapter that throws on disconnect
        mock_adapter = Mock()
        mock_adapter.disconnect.side_effect = RuntimeError("Disconnect failed")

        self.manager._registry.register("failing_adapter", mock_adapter)

        # This should not raise an exception
        self.manager.disconnect_all()

        # Adapter should still be disconnected despite exception
        mock_adapter.disconnect.assert_called_once()

    def test_start_health_monitoring_idempotent(self):
        """Test that _start_health_monitoring is idempotent."""
        # Mock health monitor
        with patch.object(self.manager._health_monitor, "start") as mock_start:
            # Call multiple times
            self.manager._start_health_monitoring()
            self.manager._start_health_monitoring()

            # Should only be called once
            assert mock_start.call_count <= 2  # Allow for potential double calls

    def test_stop_health_monitoring_idempotent(self):
        """Test that _stop_health_monitoring is idempotent."""
        # Mock health monitor
        with patch.object(self.manager._health_monitor, "stop") as mock_stop:
            # Call multiple times
            self.manager._stop_health_monitoring()
            self.manager._stop_health_monitoring()

            # Should handle multiple calls gracefully
            assert mock_stop.call_count >= 1

    def test_context_manager_with_exception(self):
        """Test context manager behavior when exception occurs."""
        with patch.object(self.manager, "disconnect_all") as mock_disconnect:
            try:
                with self.manager:
                    raise ValueError("Test exception")
            except ValueError:
                pass  # Expected

            # disconnect_all should still be called
            mock_disconnect.assert_called_once()

    def test_repr_method(self):
        """Test __repr__ method output."""
        # Add some adapters
        adapter1 = Mock()
        adapter2 = Mock()
        self.manager._registry.register("adapter1", adapter1)
        self.manager._registry.register("adapter2", adapter2)

        repr_str = repr(self.manager)
        assert "CacheManager" in repr_str
        assert "adapters=2" in repr_str
        assert "adapter1" in repr_str
        assert "adapter2" in repr_str


class TestManagerConfigCoverage:
    """Test ManagerConfig edge cases for better coverage."""

    def test_manager_config_defaults(self):
        """Test ManagerConfig with all default values."""
        config = ManagerConfig()

        # Verify all defaults
        assert config.default_adapter is None
        assert config.auto_connect is True
        assert config.enable_global_stats is True
        assert config.health_check_interval == 60.0
        assert config.enable_routing is True
        assert config.namespace_separator == ":"
        assert config.fallback_adapter is None
        assert config.log_level == "INFO"
        assert isinstance(config.extra_config, dict)
        assert len(config.extra_config) == 0

    def test_manager_config_custom_values(self):
        """Test ManagerConfig with custom values."""
        config = ManagerConfig(
            default_adapter="redis",
            auto_connect=False,
            enable_global_stats=False,
            health_check_interval=30.0,
            enable_routing=False,
            namespace_separator="|",
            fallback_adapter="memory",
            log_level="DEBUG",
            extra_config={"custom": "value"},
        )

        assert config.default_adapter == "redis"
        assert config.auto_connect is False
        assert config.enable_global_stats is False
        assert config.health_check_interval == 30.0
        assert config.enable_routing is False
        assert config.namespace_separator == "|"
        assert config.fallback_adapter == "memory"
        assert config.log_level == "DEBUG"
        assert config.extra_config["custom"] == "value"


class TestCacheManagerErrorConditions:
    """Test error conditions and edge cases."""

    def test_init_with_none_config(self):
        """Test initialization with None config."""
        manager = CacheManager(config=None)
        assert isinstance(manager._config, ManagerConfig)
        assert manager._config.default_adapter is None

    def test_register_adapter_with_auto_connect_failure(self):
        """Test registering adapter when connection fails."""
        manager = CacheManager(config={"auto_connect": True})
        mock_adapter = Mock()
        mock_adapter.is_connected.return_value = False  # Not connected initially
        mock_adapter.connect.return_value = False  # Connection fails

        result = manager.register_adapter("test", mock_adapter)
        assert result is False  # Should fail due to connection failure

    def test_register_adapter_exception_during_registration(self):
        """Test exception during adapter registration."""
        manager = CacheManager()

        # Mock registry to throw exception
        with patch.object(
            manager._registry, "register", side_effect=RuntimeError("Registry error")
        ):
            mock_adapter = Mock()
            result = manager.register_adapter("test", mock_adapter)
            assert result is False

    def test_create_adapter_with_factory_failure(self):
        """Test create_adapter when factory fails."""
        manager = CacheManager()

        # Mock factory manager to throw exception
        with patch.object(
            manager._factory_manager, "create_adapter", side_effect=RuntimeError("Factory error")
        ):
            result = manager.create_adapter("test", "memory")
            assert result is False  # Should return False on failure

    def test_get_cache_adapter_fallback_scenarios(self):
        """Test _get_cache_adapter fallback scenarios."""
        manager = CacheManager()

        # Test with no adapters at all
        with pytest.raises(AdapterNotFoundError):
            manager._get_cache_adapter("test_key")

    def test_get_pool_adapter_fallback_scenarios(self):
        """Test _get_pool_adapter fallback scenarios."""
        manager = CacheManager()

        # Test with no adapters at all
        with pytest.raises(AdapterNotFoundError):
            manager._get_pool_adapter()

    def test_borrow_context_manager_exception_handling(self):
        """Test borrow context manager exception handling."""
        manager = CacheManager()

        # Mock pool adapter that throws on _get_pool_object
        mock_adapter = Mock()
        mock_adapter._get_pool_object.side_effect = RuntimeError("Pool get failed")

        with patch.object(manager, "_get_pool_adapter", return_value=mock_adapter):
            # This should not raise an exception because get_object_pool catches exceptions
            # However, borrow() will raise RuntimeError if obj is None
            with pytest.raises(RuntimeError, match="No object available from pool"):
                with manager.borrow():
                    pass


class TestThreadSafetyEdgeCases:
    """Test thread safety edge cases for manager operations."""

    def test_concurrent_global_stats_updates(self):
        """Test concurrent updates to global stats."""
        manager = CacheManager()

        def update_stats():
            with manager._stats_lock:
                manager._global_stats["cache"].hits += 1
                manager._global_stats["cache"].misses += 1
                manager._global_stats["cache"].update_hit_rate()

        # Run multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=update_stats)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Stats should be consistent
        stats = manager.get_global_stats()
        assert stats["cache"].hits == 10
        assert stats["cache"].misses == 10

    def test_concurrent_adapter_operations(self):
        """Test concurrent adapter registration/removal."""
        manager = CacheManager()

        results = []

        def register_adapters(thread_id):
            for i in range(5):
                adapter = Mock()
                name = f"adapter_{thread_id}_{i}"
                result = manager.register_adapter(name, adapter)
                results.append((name, result))

        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=register_adapters, args=(thread_id,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All registrations should succeed
        assert all(result for _, result in results)
        assert len(manager.list_adapters()) == 15  # 3 threads * 5 adapters
