"""
Tests for MemoryAdapter automatic cleanup functionality including expired item removal,
cleanup thread management, and error handling during cleanup operations.
"""

import time
from unittest.mock import patch

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig

# pylint: disable=protected-access


class TestMemoryAdapterCleanup:
    """Tests for automatic cleanup functionality."""

    def test_automatic_cleanup_of_expired_items(self):
        """Test that cleanup thread removes expired items."""
        config = MemoryAdapterConfig(
            cleanup_interval=0.1,
            default_ttl=0.15,  # Fast cleanup for testing
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Set items that will expire
            for i in range(5):
                adapter.set(f"key_{i}", f"value_{i}")

            assert adapter.size() == 5

            # Wait for expiration and cleanup
            time.sleep(0.3)

            # Items should be cleaned up
            assert adapter.size() == 0
        finally:
            adapter.disconnect()

    def test_mixed_ttl_cleanup(self):
        """Test cleanup with mixed TTL values."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Set items with different TTLs
            adapter.set("short", "value1", ttl=0.1)  # Expires quickly
            adapter.set("medium", "value2", ttl=0.3)  # Expires later
            adapter.set("persistent", "value3")  # Never expires

            assert adapter.size() == 3

            # Wait for short TTL to expire
            time.sleep(0.2)

            # Only short-lived item should be gone
            assert not adapter.exists("short")
            assert adapter.exists("medium")
            assert adapter.exists("persistent")
            assert adapter.size() == 2

            # Wait for medium TTL to expire
            time.sleep(0.2)

            assert not adapter.exists("medium")
            assert adapter.exists("persistent")
            assert adapter.size() == 1
        finally:
            adapter.disconnect()

    def test_cleanup_thread_error_handling(self):
        """Test that cleanup thread handles errors gracefully."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Add some test data
            adapter.set("test", "value")

            # Simulate error in cleanup by corrupting data structure
            with patch.object(adapter._data, "items", side_effect=RuntimeError("Test error")):
                time.sleep(0.2)  # Let cleanup run with error

            # Adapter should still be functional after cleanup error
            assert adapter.get("test") == "value"
            adapter.set("test2", "value2")
            assert adapter.get("test2") == "value2"
        finally:
            adapter.disconnect()

    def test_cleanup_thread_lifecycle(self):
        """Test cleanup thread start and stop."""
        config = MemoryAdapterConfig(cleanup_interval=0.1)
        adapter = MemoryAdapter(config)

        # Initially no cleanup thread
        assert adapter._cleanup_thread is None

        # Connect should start cleanup thread
        adapter.connect()
        assert adapter._cleanup_thread is not None
        assert adapter._cleanup_thread.is_alive()

        # Disconnect should stop cleanup thread
        adapter.disconnect()
        time.sleep(0.2)  # Give time for thread to stop
        assert not adapter._cleanup_thread.is_alive()


if __name__ == "__main__":
    pytest.main([__file__])
