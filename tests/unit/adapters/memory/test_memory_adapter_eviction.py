"""
Tests for MemoryAdapter eviction policies including
LRU, FIFO, and random eviction strategies,
and eviction behavior under various conditions.
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig

# pylint: disable=protected-access


class TestMemoryAdapterEviction:
    """Tests for eviction policies."""

    def test_lru_eviction_policy(self):
        """Test LRU (Least Recently Used) eviction policy."""
        config = MemoryAdapterConfig(max_size=3, eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache
            adapter.set("key1", "value1")
            adapter.set("key2", "value2")
            adapter.set("key3", "value3")
            assert adapter.size() == 3

            # Access key1 to make it recently used
            adapter.get("key1")

            # Add new item - should evict key2 (least recently used)
            adapter.set("key4", "value4")
            assert adapter.size() == 3
            assert adapter.exists("key1")  # Recently accessed
            assert not adapter.exists("key2")  # Should be evicted
            assert adapter.exists("key3")
            assert adapter.exists("key4")
        finally:
            adapter.disconnect()

    def test_fifo_eviction_policy(self):
        """Test FIFO (First In, First Out) eviction policy."""
        config = MemoryAdapterConfig(max_size=3, eviction_policy="fifo")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache
            adapter.set("key1", "value1")
            time.sleep(0.01)  # Ensure different timestamps
            adapter.set("key2", "value2")
            time.sleep(0.01)
            adapter.set("key3", "value3")
            assert adapter.size() == 3

            # Add new item - should evict key1 (first in)
            adapter.set("key4", "value4")
            assert adapter.size() == 3
            assert not adapter.exists("key1")  # Should be evicted
            assert adapter.exists("key2")
            assert adapter.exists("key3")
            assert adapter.exists("key4")
        finally:
            adapter.disconnect()

    def test_random_eviction_policy(self):
        """Test random eviction policy."""
        config = MemoryAdapterConfig(max_size=3, eviction_policy="random")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache
            adapter.set("key1", "value1")
            adapter.set("key2", "value2")
            adapter.set("key3", "value3")
            assert adapter.size() == 3

            # Add new item - should evict one random item
            adapter.set("key4", "value4")
            assert adapter.size() == 3
            assert adapter.exists("key4")  # New item should be present

            # Count existing original keys
            original_keys = ["key1", "key2", "key3"]
            existing_count = sum(1 for key in original_keys if adapter.exists(key))
            assert existing_count == 2  # One should be evicted
        finally:
            adapter.disconnect()

    def test_no_eviction_when_under_limit(self):
        """Test that no eviction occurs when under size limit."""
        config = MemoryAdapterConfig(max_size=5, eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Add items under the limit
            for i in range(4):
                adapter.set(f"key{i}", f"value{i}")

            assert adapter.size() == 4

            # All items should still exist
            for i in range(4):
                assert adapter.exists(f"key{i}")
        finally:
            adapter.disconnect()

    def test_no_eviction_when_updating_existing_key(self):
        """Test that updating existing key doesn't trigger eviction."""
        config = MemoryAdapterConfig(max_size=2, eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill cache
            adapter.set("key1", "value1")
            adapter.set("key2", "value2")
            assert adapter.size() == 2

            # Update existing key
            adapter.set("key1", "new_value1")
            assert adapter.size() == 2
            assert adapter.get("key1") == "new_value1"
            assert adapter.exists("key2")
        finally:
            adapter.disconnect()

    def test_eviction_handles_missing_data_structure(self):
        """Test eviction with data not defined."""
        config = MemoryAdapterConfig(max_size=2, eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()
        adapter.set("key1", "value1")
        time.sleep(0.01)  # Ensure different timestamps
        adapter.set("key2", "value2")
        time.sleep(0.01)
        adapter.set("key3", "value3")
        original_data = adapter._data
        adapter._data = None
        result = adapter._evict_items(3)
        assert result == 0
        adapter._data = original_data
        adapter.disconnect()

    def test_evict_items_unknown_policy(self):
        """Test eviction with unknown policy (should not evict anything)."""
        config = MemoryAdapterConfig(eviction_policy="unknown", max_size=5)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Add some items
            adapter.set("key1", "value1")
            adapter.set("key2", "value2")

            # Try to evict with unknown policy
            evicted = adapter._evict_items(1)
            assert evicted == 0  # Nothing should be evicted
            assert adapter.size() == 2  # Items should still be there

        finally:
            adapter.disconnect()

    def test_evict_items_no_items_to_evict(self):
        """Test eviction when evicted count is 0 (no logging should occur)."""
        config = MemoryAdapterConfig(eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Don't add any items, so evicted will be 0
            with patch.object(adapter._logger, "debug") as mock_debug:
                evicted = adapter._evict_items(5)
                assert evicted == 0
                # debug should not be called since evicted <= 0
                mock_debug.assert_not_called()

        finally:
            adapter.disconnect()

    def test_evict_items_exception_handling(self):
        """Test eviction exception handling."""
        config = MemoryAdapterConfig(eviction_policy="lru")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Add some items
            adapter.set("key1", "value1")

            # Mock popitem to raise exception
            with patch.object(
                adapter._data, "popitem", side_effect=RuntimeError("Eviction failed")
            ):
                with patch.object(adapter._logger, "error") as mock_error:
                    evicted = adapter._evict_items(1)
                    assert evicted == 0  # No items evicted due to exception
                    mock_error.assert_called_once()

        finally:
            adapter.disconnect()

    @patch("omni_cache.adapters.memory.memory.CacheItem")
    def test_evict_items_fifo_key_not_in_data(self, MockCacheItem):
        """Test _evict_items FIFO policy when key_to_evict is not in self._data."""
        config = MemoryAdapterConfig(max_size=1, eviction_policy="fifo")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            mock_data = MagicMock(spec=dict)
            # Mock CacheItem for FIFO sorting
            mock_item = MockCacheItem()
            mock_item.created_at = 1

            # Mock items() method to return items for sorting
            mock_data.items.return_value = [("key_to_be_missing", mock_item)]
            # Mock __contains__ to return False for the key
            mock_data.__contains__.return_value = False
            # Mock __len__ for min() comparison
            mock_data.__len__.return_value = 1

            with patch.object(adapter, "_data", new=mock_data):
                evicted = adapter._evict_items(1)
                assert evicted == 0
                mock_data.__contains__.assert_called_with("key_to_be_missing")

        finally:
            adapter.disconnect()

    @patch("omni_cache.adapters.memory.memory.CacheItem")
    def test_evict_items_random_key_not_in_data(self, MockCacheItem):
        """Test _evict_items random policy when key_to_remove is not in self._data."""
        config = MemoryAdapterConfig(max_size=1, eviction_policy="random")
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            mock_data = MagicMock(spec=dict)
            # Mock keys() method to return a list of keys
            mock_data.keys.return_value = ["key_to_be_missing"]
            # Mock __contains__ to return False for the key
            mock_data.__contains__.return_value = False
            # Mock __len__ for min() comparison
            mock_data.__len__.return_value = 1

            with patch.object(adapter, "_data", new=mock_data):
                # Patch random.sample to return the key that will be "missing"
                with patch("random.sample", return_value=["key_to_be_missing"]):
                    evicted = adapter._evict_items(1)
                    assert evicted == 0
                    mock_data.__contains__.assert_called_with("key_to_be_missing")

        finally:
            adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
