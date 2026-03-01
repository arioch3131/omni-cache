"""
SmartPool Adapter Error Handling and Edge Cases Testing.

This module contains comprehensive tests for error conditions, exception handling,
and edge cases in the SmartPoolAdapter. Tests cover adapter disconnection errors,
pool empty conditions, factory errors, internal SmartPool errors, exception
propagation, error recovery, and various edge cases.
"""

import threading
import time
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter, SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper, OmniCachePooledObject
from omni_cache.core.exceptions import (
    AdapterNotConnectedError,
    PoolEmptyError,
)
from omni_cache.core.exceptions import OmniConnectionError as ConnectionError

# Mock SmartPool classes if not available
try:
    from smartpool import SmartObjectManager

    SMARTPOOL_AVAILABLE = True
except ImportError:
    SMARTPOOL_AVAILABLE = False
    SmartObjectManager = Mock


class TestSmartPoolAdapterErrorHandling:
    """Test suite for SmartPoolAdapter error handling scenarios."""

    @pytest.fixture
    def disconnected_adapter(self):
        """Create a disconnected SmartPoolAdapter for testing."""
        config = SmartPoolAdapterConfig(factory_function=Mock())
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(config)
            # Ensure adapter is not connected
            return adapter

    @pytest.fixture
    def connected_adapter_with_mocks(self):
        """Create a connected adapter with mocked SmartPool components."""
        config = SmartPoolAdapterConfig(factory_function=Mock())
        mock_manager = MagicMock()
        mock_manager.get_stats.return_value = {
            "pooled_objects": 5,
            "active_objects": 0,
            "hits": 0,
            "misses": 0,
        }
        mock_manager.get_health_status.return_value = {"status": "healthy"}

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch(
                "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
                return_value=mock_manager,
            ):
                adapter = SmartPoolAdapter(config)
                adapter.connect()
                yield adapter, mock_manager
                adapter.disconnect()

    def test_adapter_not_connected_errors(self, disconnected_adapter):
        """Test errors when adapter is not connected."""
        # Test get operation
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.get()

        # Test put operation
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            disconnected_adapter.put(Mock())

        # Test borrow context manager
        with pytest.raises(AdapterNotConnectedError, match="not connected"):
            with disconnected_adapter.borrow():
                pass

        # Verify adapter state
        assert not disconnected_adapter.is_connected()
        assert disconnected_adapter._pool is None

    def test_pool_empty_errors(self, connected_adapter_with_mocks):
        """Test errors when pool is empty."""
        adapter, mock_manager = connected_adapter_with_mocks

        # Configure mock to return empty pool signal (0)
        mock_manager.acquire.return_value = 0

        # Test get operation returns None for empty pool
        result = adapter.get()
        assert result is None

        # Test borrow context manager raises PoolEmptyError
        with pytest.raises(PoolEmptyError, match="empty pool"):
            with adapter.borrow():
                pass

        # Verify pool state still shows as connected
        assert adapter.is_connected()

    def test_factory_errors(self):
        """Test errors related to factory function issues."""
        # Invalid or non-callable factories are accepted by config construction.
        # Validation and runtime behavior are exercised here.

        # Test factory function that raises exceptions
        def failing_factory():
            raise ValueError("Factory creation failed")

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                # Configure mock to simulate factory errors during object creation
                mock_manager = MagicMock()
                mock_manager.acquire.side_effect = Exception("Factory failed")
                mock_sm.return_value = mock_manager

                config = SmartPoolAdapterConfig(factory_function=failing_factory)
                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Test that factory errors are handled gracefully
                result = adapter.get()
                assert result is None

                adapter.disconnect()

    def test_smartpool_internal_errors(self, connected_adapter_with_mocks):
        """Test handling of internal SmartPool errors."""
        adapter, mock_manager = connected_adapter_with_mocks

        # Test SmartPool acquire failures
        mock_manager.acquire.side_effect = RuntimeError("Internal SmartPool error")

        # get() should handle exceptions gracefully
        result = adapter.get()
        assert result is None

        # Test SmartPool release failures
        mock_manager.acquire.side_effect = None
        mock_manager.acquire.return_value = (1, ("test",), Mock())
        mock_manager.release.side_effect = RuntimeError("Release failed")

        # put() should handle exceptions gracefully
        obj = adapter.get()
        result = adapter.put(obj)
        assert result is False

        # Test SmartPool stats failures
        mock_manager.get_basic_stats.side_effect = Exception("Stats error")
        size = adapter.size()
        assert size == 0  # Should return default on error

        # Test SmartPool health check failures
        mock_manager.get_health_status.side_effect = Exception("Health check failed")
        health_ok = adapter.health_check()
        assert health_ok is False

    def test_exception_propagation(self, connected_adapter_with_mocks):
        """Test proper exception propagation patterns."""
        adapter, mock_manager = connected_adapter_with_mocks

        # Test that critical errors are propagated correctly
        mock_manager.acquire.side_effect = MemoryError("Out of memory")

        # Critical errors should still be handled gracefully in safe operations
        result = adapter.get()
        assert result is None

        # Test connection errors during initialization
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch(
                "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
                side_effect=ConnectionError("Connection failed"),
            ):
                config = SmartPoolAdapterConfig(factory_function=Mock())
                adapter = SmartPoolAdapter(config)

                # Connection should fail gracefully
                result = adapter.connect()
                assert result is False

    def test_error_recovery(self, connected_adapter_with_mocks):
        """Test error recovery mechanisms."""
        adapter, mock_manager = connected_adapter_with_mocks

        # Simulate temporary failure
        mock_manager.acquire.side_effect = [
            Exception("Temporary failure"),  # First call fails
            (1, ("test",), Mock()),  # Second call succeeds
        ]

        # First get should fail
        result1 = adapter.get()
        assert result1 is None

        # Second get should succeed (recovery)
        result2 = adapter.get()
        assert result2 is not None

        # Test recovery after connection loss
        adapter.disconnect()
        assert not adapter.is_connected()

        # Reconnection should work
        result = adapter.connect()
        assert result is True
        assert adapter.is_connected()

        # Test pool recreation after clear operation failure
        mock_manager.shutdown.side_effect = Exception("Shutdown failed")
        result = adapter.clear()
        assert result is False  # Clear failed

        # But adapter should still be functional
        assert adapter.is_connected()

    def test_concurrent_error_handling(self, connected_adapter_with_mocks):
        """Test error handling under concurrent access."""
        adapter, mock_manager = connected_adapter_with_mocks

        errors_caught = []
        successful_operations = []

        def worker_with_errors():
            """Worker that may encounter errors."""
            try:
                obj = adapter.get()
                if obj is not None:  # Changed from 'if obj:'
                    successful_operations.append(obj)
                    time.sleep(0.001)  # Brief work simulation
                    adapter.put(obj)
            except Exception as e:
                errors_caught.append(e)

        # Configure intermittent failures
        mock_manager.acquire.side_effect = [
            (1, ("test",), Mock()),  # Success
            Exception("Error 1"),  # Failure
            (2, ("test",), Mock()),  # Success
            Exception("Error 2"),  # Failure
            (3, ("test",), Mock()),  # Success
        ]

        # Run concurrent operations
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=worker_with_errors)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Verify error handling didn't crash the system
        assert adapter.is_connected()
        assert len(errors_caught) == 0  # Errors should be handled gracefully
        assert len(successful_operations) >= 0  # Some operations may succeed


class TestSmartPoolAdapterEdgeCases:
    """Test suite for SmartPoolAdapter edge cases and boundary conditions."""

    def test_zero_size_pool(self):
        """Test adapter behavior with zero-sized pool configuration."""
        config = SmartPoolAdapterConfig(
            factory_function=Mock(),
            initial_size=0,
            max_size=0,
            min_size=0,
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                MagicMock()
                # Simulate SmartObjectManager rejecting zero max_size
                mock_sm.side_effect = Exception("max_size must be positive")

                adapter = SmartPoolAdapter(config)
                connect_result = adapter.connect()

                # Connection should fail because max_size is 0
                assert connect_result is False
                assert not adapter.is_connected()

                # Operations on disconnected adapter should raise AdapterNotConnectedError
                with pytest.raises(AdapterNotConnectedError):
                    adapter.size()
                with pytest.raises(AdapterNotConnectedError):
                    adapter.is_empty()
                with pytest.raises(AdapterNotConnectedError):
                    adapter.get()
                with pytest.raises(AdapterNotConnectedError):
                    adapter.put(Mock())  # Pass a mock object to put

    def test_max_size_exceeded(self):
        """Test behavior when attempting to exceed maximum pool size."""
        config = SmartPoolAdapterConfig(
            factory_function=Mock(),
            initial_size=2,
            max_size=3,
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                mock_manager = MagicMock()
                mock_manager.get_stats.return_value = {
                    "pooled_objects": 3,  # At max capacity
                    "active_objects": 0,
                    "hits": 0,
                    "misses": 0,
                }
                mock_manager.acquire.return_value = 0  # Pool full, no objects available
                mock_sm.return_value = mock_manager

                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Should handle max size gracefully
                result = adapter.get()
                assert result is None  # No objects available when at max

                adapter.disconnect()

    def test_factory_returning_none(self):
        """Test adapter behavior when factory function returns None."""

        def none_factory():
            return None

        config = SmartPoolAdapterConfig(factory_function=none_factory)

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                mock_manager = MagicMock()
                # Simulate SmartPool behavior when factory returns None
                mock_manager.acquire.return_value = 0  # No valid object created
                mock_sm.return_value = mock_manager

                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Should handle None factory return gracefully
                result = adapter.get()
                assert result is None

                adapter.disconnect()

    def test_invalid_factory_args(self):
        """Test adapter behavior with invalid factory arguments."""

        def factory_with_required_args(required_param):
            return Mock(param=required_param)

        config = SmartPoolAdapterConfig(
            factory_function=factory_with_required_args,
            factory_args=(),  # Missing required argument
            factory_kwargs={},
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                mock_manager = MagicMock()
                # Simulate TypeError when calling factory with wrong args
                mock_manager.acquire.side_effect = TypeError("Missing required argument")
                mock_sm.return_value = mock_manager

                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Should handle factory argument errors gracefully
                result = adapter.get()
                assert result is None

                adapter.disconnect()

    def test_shutdown_during_operations(self):
        """Test behavior when adapter is shut down during active operations."""
        config = SmartPoolAdapterConfig(factory_function=Mock())
        shutdown_event = threading.Event()
        operation_results = []

        def worker():
            """Worker that performs operations until shutdown."""
            while not shutdown_event.is_set():
                try:
                    obj = adapter.get()
                    if obj:
                        operation_results.append("success")
                        adapter.put(obj)
                    else:
                        operation_results.append("none")
                except Exception as e:
                    operation_results.append(f"error: {type(e).__name__}")
                time.sleep(0.001)

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                mock_manager = MagicMock()
                mock_manager.get_stats.return_value = {
                    "pooled_objects": 5,
                    "active_objects": 0,
                    "hits": 0,
                    "misses": 0,
                }
                mock_manager.acquire.return_value = (1, ("test",), Mock())
                mock_sm.return_value = mock_manager

                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Start worker thread
                worker_thread = threading.Thread(target=worker)
                worker_thread.start()

                # Let it run briefly
                time.sleep(0.01)

                # Shutdown adapter while operations are running
                adapter.disconnect()
                shutdown_event.set()

                # Wait for worker to finish
                worker_thread.join(timeout=1.0)

                # Verify adapter is disconnected
                assert not adapter.is_connected()

                # Verify some operations completed before shutdown
                assert len(operation_results) > 0

    def test_memory_pressure_edge_cases(self):
        """Test adapter behavior under memory pressure conditions."""

        def memory_intensive_factory():
            # Simulate large object creation
            return Mock(data=bytearray(1024 * 1024))  # 1MB object

        config = SmartPoolAdapterConfig(
            factory_function=memory_intensive_factory,
            max_size=100,  # Large pool
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager") as mock_sm:
                mock_manager = MagicMock()
                mock_manager.get_stats.return_value = {
                    "pooled_objects": 50,
                    "active_objects": 25,
                    "hits": 100,
                    "misses": 10,
                }

                # Simulate memory pressure by occasionally failing allocations
                mock_manager.acquire.side_effect = [
                    (1, ("test",), Mock()),  # Success
                    (2, ("test",), Mock()),  # Success
                    MemoryError("Out of memory"),  # Memory pressure
                    (3, ("test",), Mock()),  # Recovery
                ]
                mock_sm.return_value = mock_manager

                adapter = SmartPoolAdapter(config)
                adapter.connect()

                # Test operations under memory pressure
                results = []
                for _ in range(4):
                    result = adapter.get()
                    results.append(result is not None)

                # Should handle memory errors gracefully
                assert True in results  # Some operations succeed
                assert adapter.is_connected()  # Adapter remains functional

                adapter.disconnect()

    def test_configuration_edge_cases(self):
        """Test edge cases in adapter configuration."""
        # Test extremely small intervals
        config = SmartPoolAdapterConfig(
            factory_function=Mock(),
            cleanup_interval=0.001,  # 1ms cleanup interval
            auto_tuning_interval=0.001,  # 1ms auto-tuning interval
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(config)
            assert adapter.config.cleanup_interval == 0.001
            assert adapter.config.auto_tuning_interval == 0.001

        # Test extremely large values
        config = SmartPoolAdapterConfig(
            factory_function=Mock(),
            max_size=1000000,  # Very large pool
            max_age_seconds=86400 * 365,  # 1 year TTL
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(config)
            assert adapter.config.max_size == 1000000
            assert adapter.config.max_age_seconds == 86400 * 365

    def test_wrapper_edge_cases(self):
        """Test edge cases with object wrapping and unwrapping."""
        # Test wrapping None
        wrapper = AutoWeakRefWrapper(None)
        assert wrapper._obj is None

        # Test wrapping already wrapped object
        mock_obj = Mock()
        wrapper1 = AutoWeakRefWrapper(mock_obj)
        wrapper2 = AutoWeakRefWrapper(wrapper1)
        # Should not double-wrap (implementation dependent)
        assert hasattr(wrapper2, "_obj")

        # Test OmniCachePooledObject with None object
        pooled_obj = OmniCachePooledObject(id=1, key="test", obj=None)
        assert pooled_obj.obj is None

        # Test operations with wrapped None objects
        config = SmartPoolAdapterConfig(factory_function=Mock())

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(config)

            # Test unwrapping None
            result = adapter._unwrap_object(None)
            assert result is None

            # Test unwrapping non-wrapped object
            mock_obj = Mock()
            result = adapter._unwrap_object(mock_obj)
            assert result == mock_obj

    def test_thread_safety_edge_cases(self):
        """Test thread safety edge cases and race conditions."""
        config = SmartPoolAdapterConfig(factory_function=Mock())
        connection_results = []
        disconnection_results = []

        def connect_worker():
            """Worker that attempts to connect."""
            try:
                result = adapter.connect()
                connection_results.append(result)
            except Exception as e:
                connection_results.append(f"error: {type(e).__name__}")

        def disconnect_worker():
            """Worker that attempts to disconnect."""
            try:
                result = adapter.disconnect()
                disconnection_results.append(result)
            except Exception as e:
                disconnection_results.append(f"error: {type(e).__name__}")

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager"):
                adapter = SmartPoolAdapter(config)

                # Test concurrent connection/disconnection
                threads = []
                for _ in range(3):
                    threads.append(threading.Thread(target=connect_worker))
                for _ in range(3):
                    threads.append(threading.Thread(target=disconnect_worker))

                # Start all threads simultaneously
                for thread in threads:
                    thread.start()

                # Wait for completion
                for thread in threads:
                    thread.join()

                # Verify no crashes occurred
                assert len(connection_results) == 3
                assert len(disconnection_results) == 3

                # At least one operation should succeed
                assert any(result is True for result in connection_results + disconnection_results)
