"""
Tests for the KeyValueInterface.
"""

import pytest

from omni_cache.core.interfaces.key_value_interface import KeyValueInterface


class MockKeyValueAdapter(KeyValueInterface):
    def __init__(self):
        self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value, ttl=None):
        self._data[key] = value
        return True

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False

    def exists(self, key):
        return key in self._data

    def clear(self):
        self._data.clear()
        return True

    def keys(self):
        return iter(self._data.keys())

    def size(self):
        return len(self._data)


@pytest.fixture
def key_value_adapter():
    return MockKeyValueAdapter()


class TestKeyValueInterface:
    def test_set_and_get(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        assert key_value_adapter.get("key1") == "value1"

    def test_get_nonexistent(self, key_value_adapter):
        assert key_value_adapter.get("nonexistent") is None
        assert key_value_adapter.get("nonexistent", "default") == "default"

    def test_delete(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        assert key_value_adapter.delete("key1") is True
        assert key_value_adapter.get("key1") is None

    def test_delete_nonexistent(self, key_value_adapter):
        assert key_value_adapter.delete("nonexistent") is False

    def test_exists(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        assert key_value_adapter.exists("key1") is True
        assert key_value_adapter.exists("nonexistent") is False

    def test_clear(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        key_value_adapter.set("key2", "value2")
        key_value_adapter.clear()
        assert key_value_adapter.size() == 0

    def test_keys(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        key_value_adapter.set("key2", "value2")
        assert set(key_value_adapter.keys()) == {"key1", "key2"}

    def test_size(self, key_value_adapter):
        assert key_value_adapter.size() == 0
        key_value_adapter.set("key1", "value1")
        assert key_value_adapter.size() == 1

    def test_get_many(self, key_value_adapter):
        key_value_adapter.set("key1", "value1")
        key_value_adapter.set("key2", "value2")
        assert key_value_adapter.get_many(["key1", "key2"]) == {"key1": "value1", "key2": "value2"}

    def test_set_many(self, key_value_adapter):
        key_value_adapter.set_many({"key1": "value1", "key2": "value2"})
        assert key_value_adapter.get("key1") == "value1"
        assert key_value_adapter.get("key2") == "value2"

    def test_delete_many(self, key_value_adapter):
        key_value_adapter.set_many({"key1": "value1", "key2": "value2", "key3": "value3"})
        assert key_value_adapter.delete_many(["key1", "key3"]) == {"key1": True, "key3": True}
        assert key_value_adapter.get("key1") is None
        assert key_value_adapter.get("key2") == "value2"
        assert key_value_adapter.get("key3") is None
