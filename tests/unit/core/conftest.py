import time

import pytest

from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheStats,
    KeyValueInterface,
    PoolInterface,
    StatisticsInterface,
)


class MockAdapter(AdapterInterface, KeyValueInterface, PoolInterface, StatisticsInterface):
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
            obj = self._pool_objects.pop()
            return obj
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


StatisticsInterface.register(MockAdapter)


@pytest.fixture
def mock_adapter():
    """Create a mock adapter for testing."""
    return MockAdapter()
