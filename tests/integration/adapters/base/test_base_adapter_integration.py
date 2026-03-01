"""
Tests for the integration and thread safety of the BaseAdapter.
"""

import threading

import pytest

from omni_cache.adapters.base import (
    ConnectionState,
)
from omni_cache.core.interfaces import (
    CacheStats,
)
from tests.integration.adapters.conftest import MockBaseAdapter


class TestBaseAdapterIntegration:
    """Integration tests for BaseAdapter functionality."""

    def test_concurrent_connections(self, adapter_config):
        """Test concurrent connection attempts."""
        adapter = MockBaseAdapter(adapter_config)
        adapter.connect_delay = 0.1
        results = []

        def connect_thread():
            result = adapter.connect()
            results.append(result)

        # Start multiple connection threads
        threads = [threading.Thread(target=connect_thread) for _ in range(5)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Only one should succeed, others should fail
        assert sum(results) == 1
        assert adapter.is_connected() is True

    def test_concurrent_health_checks(self, adapter_config):
        """Test concurrent health check operations."""
        adapter = MockBaseAdapter(adapter_config)
        adapter.connect()
        adapter._config.health_check_interval = 0.01  # Very short for testing

        results = []

        def health_check_thread():
            result = adapter.health_check()
            results.append(result)

        # Start multiple health check threads
        threads = [threading.Thread(target=health_check_thread) for _ in range(10)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All should succeed
        assert all(results)
        assert len(results) == 10

    def test_stats_thread_safety(self, mock_base_adapter):
        """Test statistics updates are thread-safe."""
        mock_base_adapter.connect()

        def update_stats():
            for _ in range(100):
                mock_base_adapter._update_cache_stats("get", success=True)

        # Start multiple threads updating stats
        threads = [threading.Thread(target=update_stats) for _ in range(5)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        stats = mock_base_adapter.get_stats()
        assert stats.hits == 500  # 5 threads × 100 updates each

    def test_configuration_thread_safety(self, mock_base_adapter):
        """Test configuration updates are thread-safe."""
        results = []

        def update_config(retry_count):
            result = mock_base_adapter.configure({"max_retries": retry_count})
            results.append(result)

        # Start multiple configuration update threads
        threads = [threading.Thread(target=update_config, args=(i,)) for i in range(1, 6)]
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All updates should succeed
        assert all(results)
        assert len(results) == 5

        # Final value should be one of the configured values
        assert 1 <= mock_base_adapter._config.max_retries <= 5

    @pytest.mark.parametrize(
        "connection_success,expected_state",
        [
            (True, ConnectionState.CONNECTED),
            (False, ConnectionState.ERROR),
        ],
    )
    def test_connection_state_transitions(self, adapter_config, connection_success, expected_state):
        """Test connection state transitions."""
        adapter = MockBaseAdapter(adapter_config)
        adapter.connect_should_succeed = connection_success

        # Initial state
        assert adapter._state == ConnectionState.DISCONNECTED

        # Connect
        result = adapter.connect()
        assert result == connection_success
        assert adapter._state == expected_state

        if connection_success:
            # Disconnect
            result = adapter.disconnect()
            assert result is True
            assert adapter._state == ConnectionState.DISCONNECTED

    def test_full_lifecycle(self, adapter_config):
        """Test full adapter lifecycle."""
        adapter = MockBaseAdapter(adapter_config)

        # Initial state
        assert adapter._state == ConnectionState.DISCONNECTED
        assert adapter.is_connected() is False
        assert adapter._connection_time is None

        # Connect
        assert adapter.connect() is True
        assert adapter.is_connected() is True
        assert adapter._connection_time is not None
        connection_time = adapter._connection_time

        # Health check
        assert adapter.health_check() is True

        # Update configuration
        assert adapter.configure({"max_retries": 5}) is True
        assert adapter._config.max_retries == 5

        # Get stats
        stats = adapter.get_stats()
        assert isinstance(stats, CacheStats)

        # Reset stats
        assert adapter.reset_stats() is True

        # Get backend info
        info = adapter.get_backend_info()
        assert info["connected"] is True
        assert info["connection_time"] == connection_time

        # Disconnect
        assert adapter.disconnect() is True
        assert adapter.is_connected() is False
        assert adapter._connection_time is None
