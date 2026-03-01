"""
Tests for MemoryAdapter error handling and edge cases
including disconnected operations, exception handling, and error recovery.
"""

import time

import pytest

from omni_cache.adapters.memory import MemoryAdapter
from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError


class TestMemoryAdapterErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.fixture
    def adapter(self):
        """Create a memory adapter for testing."""
        adapter = MemoryAdapter()
        adapter.connect()
        yield adapter
        adapter.disconnect()

    def test_operations_when_disconnected(self):
        """Test that operations fail gracefully when disconnected."""
        adapter = MemoryAdapter()

        with pytest.raises(AdapterNotConnectedError):
            adapter.get("key")
        with pytest.raises(AdapterNotConnectedError):
            adapter.set("key", "value")
        with pytest.raises(AdapterNotConnectedError):
            adapter.delete("key")
        with pytest.raises(AdapterNotConnectedError):
            adapter.exists("key")
        with pytest.raises(AdapterNotConnectedError):
            adapter.clear()
        with pytest.raises(AdapterNotConnectedError):
            adapter.size()
        with pytest.raises(AdapterNotConnectedError):
            list(adapter.keys())

    def test_get_item_info_for_expired_item(self, adapter):
        """Test getting info for expired item."""
        key = "test_key"
        value = "test_value"

        adapter.set(key, value, ttl=0.1)
        time.sleep(0.15)

        # Should return None for expired item
        info = adapter.get_item_info(key)
        assert info is None


if __name__ == "__main__":
    pytest.main([__file__])
