"""
Tests for basic MemoryAdapter functionality including
creation, connection lifecycle, and fundamental operations.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig
from omni_cache.core.interfaces import CacheBackend

# pylint: disable=protected-access


class TestMemoryAdapterBasics:
    """Tests for basic MemoryAdapter functionality."""

    @pytest.fixture
    def adapter(self):
        """Create a basic memory adapter for testing."""
        adapter = MemoryAdapter()
        adapter.connect()
        yield adapter
        adapter.disconnect()

    @pytest.fixture
    def configured_adapter(self):
        """Create a configured memory adapter for testing."""
        config = MemoryAdapterConfig(
            name="test_cache", max_size=10, default_ttl=60.0, cleanup_interval=1.0
        )
        adapter = MemoryAdapter(config)
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_adapter_creation_with_no_config(self):
        """Test adapter creation without configuration."""
        adapter = MemoryAdapter()
        assert adapter._config.name == "default"
        assert adapter._config.backend == CacheBackend.MEMORY

    def test_adapter_creation_with_dict_config(self):
        """Test adapter creation with dictionary configuration."""
        config_dict = {"name": "test_cache", "max_size": 100, "eviction_policy": "fifo"}
        adapter = MemoryAdapter(config_dict)

        assert adapter._config.name == "test_cache"
        assert adapter._config.max_size == 100
        assert adapter._config.eviction_policy == "fifo"

    def test_adapter_creation_with_config_object(self):
        """Test adapter creation with MemoryAdapterConfig object."""
        config = MemoryAdapterConfig(name="test_cache", max_size=50)
        adapter = MemoryAdapter(config)

        assert adapter._config.name == "test_cache"
        assert adapter._config.max_size == 50

    def test_connection_lifecycle(self):
        """Test adapter connection and disconnection."""
        adapter = MemoryAdapter()

        assert not adapter.is_connected()

        # Connect
        success = adapter.connect()
        assert success
        assert adapter.is_connected()

        # Disconnect
        success = adapter.disconnect()
        assert success
        assert not adapter.is_connected()

    def test_health_check(self, adapter):
        """Test health check functionality."""
        adapter._config.health_check_interval = 0.01
        assert adapter.health_check()

        # Health check should fail when disconnected
        adapter.disconnect()
        time.sleep(0.02)
        assert not adapter.health_check()

    def test_health_check_failure(self):
        """Test health check failure when accessing data structure fails."""
        adapter = MemoryAdapter()
        adapter.connect()

        class FailingDict:
            """Failing Dict Class."""

            def __len__(self):
                raise RuntimeError("Length operation failed")

        original_data = adapter._data
        try:
            # Replace _data with failing object
            adapter._data = FailingDict()

            result = adapter.health_check()
            assert result is False

        finally:
            # Restore original data
            adapter._data = original_data
            adapter.disconnect()

    def test_get_backend_info(self, adapter):
        """Test getting backend information."""
        info = adapter.get_backend_info()

        assert "adapter_class" in info
        assert info["adapter_class"] == "MemoryAdapter"
        assert info["backend"] == "memory"
        assert info["connected"] is True
        assert "storage_type" in info
        assert info["storage_type"] == "python_dict"

    def test_cleanup_thread_restart_after_death(self):
        """Test that cleanup thread is restarted if it dies."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)

        try:
            # First connection - should start thread
            adapter.connect()
            first_thread = adapter._cleanup_thread
            assert first_thread is not None
            assert first_thread.is_alive()

            # Force thread to stop without disconnecting adapter
            adapter._stop_cleanup.set()
            first_thread.join(timeout=0.2)
            assert not first_thread.is_alive()

            # Disconnect and reconnect to trigger thread restart
            adapter.disconnect()
            adapter.connect()

            second_thread = adapter._cleanup_thread
            assert second_thread is not None
            assert second_thread.is_alive()
            assert second_thread is not first_thread  # New thread instance

        finally:
            adapter.disconnect()

    def test_cleanup_thread_already_running(self):
        """Test that no new thread is created if one is already running."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)

        try:
            # First connection
            adapter.connect()
            first_thread = adapter._cleanup_thread
            assert first_thread.is_alive()

            # Connect again while already connected
            adapter.connect()
            second_thread = adapter._cleanup_thread

            # Should be the same thread
            assert second_thread is first_thread
            assert second_thread.is_alive()

        finally:
            adapter.disconnect()

    def test_cleanup_thread_reuse(self):
        """Test that _do_connect returns True when cleanup thread is already alive."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)

        try:
            # First connection - should start thread
            adapter.connect()
            first_thread = adapter._cleanup_thread
            assert first_thread is not None
            assert first_thread.is_alive()

            # Call _do_connect directly while thread is already alive
            # This should skip the if block and go directly to return True
            result = adapter._do_connect()

            assert result is True
            assert adapter._cleanup_thread is first_thread  # Same thread
            assert adapter._cleanup_thread.is_alive()

        finally:
            adapter.disconnect()

    def test_connect_handles_thread_error(self):
        """Test that _do_connect returns False when an exception is catch."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)
        with patch("threading.Thread", side_effect=threading.ThreadError("Thread Error")):
            result = adapter.connect()
            assert result is False

    def test_disconnect_handles_thread_error(self):
        """Test that _do_disconnect returns False when an exception is catch."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)
        adapter.connect()
        with patch("threading.Thread.join", side_effect=threading.ThreadError("Thread Error")):
            result = adapter.disconnect()
            assert result is False

    def test_context_manager_usage(self):
        """Test using adapter as context manager."""
        adapter = MemoryAdapter()

        with adapter:
            assert adapter.is_connected()
            adapter.set("key", "value")
            assert adapter.get("key") == "value"

        assert not adapter.is_connected()

    def test_string_representation(self, adapter):
        """Test string representation of adapter."""
        repr_str = repr(adapter)

        assert "MemoryAdapter" in repr_str
        assert "memory" in repr_str
        assert "connected" in repr_str

    @patch("omni_cache.adapters.base.base.logging.getLogger")
    def test_logging_configuration(self, mock_get_logger):
        """Test that logging is configured correctly."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        config = MemoryAdapterConfig(log_level="DEBUG")
        MemoryAdapter(config)

        mock_get_logger.assert_called()


if __name__ == "__main__":
    pytest.main([__file__])
