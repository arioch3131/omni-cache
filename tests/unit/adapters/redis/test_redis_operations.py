"""
Tests for Redis adapter basic and batch operations.

This module tests the core CRUD operations and batch operations
of the RedisAdapter including get, set, delete, exists, clear, size, keys,
and their batch counterparts.
"""

from unittest.mock import MagicMock, patch

import pytest

from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError

# Test Redis availability
try:
    from omni_cache.adapters.redis import RedisAdapter, RedisAdapterConfig

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisAdapter = None
    RedisAdapterConfig = None

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name


class TestRedisAdapterBasicOperations:
    """Tests for RedisAdapter basic CRUD operations."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        with (
            patch("omni_cache.adapters.redis.redis.Redis") as mock_redis,
            patch("omni_cache.adapters.redis.redis.ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def connected_adapter(self, mock_redis_classes):
        """Create connected RedisAdapter instance."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())
        adapter.connect()
        return adapter, mock_redis_instance

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_existing_key(self, connected_adapter):
        """Test getting an existing key."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = '"test_value"'  # JSON serialized

        result = adapter.get("test_key")

        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_nonexistent_key(self, connected_adapter):
        """Test getting a non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = None

        result = adapter.get("nonexistent_key")

        assert result is None
        mock_redis.get.assert_called_once_with("nonexistent_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_with_default(self, connected_adapter):
        """Test getting a non-existent key with default value."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = None

        result = adapter.get("nonexistent_key", "default_value")

        assert result == "default_value"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_deserialization_error(self, connected_adapter):
        """Test get operation with deserialization error."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = "invalid_json"

        result = adapter.get("test_key", "default")

        assert result == "default"  # Should return default on error

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_deserialization_error_no_default(self, connected_adapter):
        """Test get operation with deserialization error and no default."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = "invalid_json"

        result = adapter.get("test_key")

        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_without_ttl(self, connected_adapter):
        """Test setting a key without TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.set.return_value = True

        result = adapter.set("test_key", "test_value")

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_ttl_seconds(self, connected_adapter):
        """Test setting a key with TTL in seconds."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=60)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_key", 60, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_ttl_float(self, connected_adapter):
        """Test setting a key with TTL as float (milliseconds)."""
        adapter, mock_redis = connected_adapter
        mock_redis.psetex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=1.5)

        assert result is True
        mock_redis.psetex.assert_called_once_with("test_key", 1500, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_ttl_zero(self, connected_adapter):
        """Test setting a key with TTL of zero."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=0)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_key", 0, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_serialization_error(self, connected_adapter):
        """Test set operation with serialization error."""
        adapter, mock_redis = connected_adapter

        # Mock serialization to raise error
        with patch.object(
            adapter, "_serialize_value", side_effect=ValueError("Serialization failed")
        ):
            result = adapter.set("test_key", "test_value")

        assert result is False
        mock_redis.set.assert_not_called()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_redis_error(self, connected_adapter):
        """Test set operation with Redis error."""
        adapter, mock_redis = connected_adapter
        mock_redis.set.return_value = False

        result = adapter.set("test_key", "test_value")

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_existing_key(self, connected_adapter):
        """Test deleting an existing key."""
        adapter, mock_redis = connected_adapter
        mock_redis.delete.return_value = 1  # One key deleted

        result = adapter.delete("test_key")

        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_nonexistent_key(self, connected_adapter):
        """Test deleting a non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.delete.return_value = 0  # No keys deleted

        result = adapter.delete("nonexistent_key")

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_exists_true(self, connected_adapter):
        """Test exists for an existing key."""
        adapter, mock_redis = connected_adapter
        mock_redis.exists.return_value = 1

        result = adapter.exists("test_key")

        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_exists_false(self, connected_adapter):
        """Test exists for a non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.exists.return_value = 0

        result = adapter.exists("test_key")

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_clear_without_prefix(self, connected_adapter):
        """Test clearing all keys without prefix."""
        adapter, mock_redis = connected_adapter
        mock_redis.flushdb.return_value = True

        result = adapter.clear()

        assert result is True
        mock_redis.flushdb.assert_called_once()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_clear_with_prefix(self, mock_redis_classes):
        """Test clearing keys with prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.keys.return_value = ["app:key1", "app:key2", "app:key3"]
        mock_redis_instance.delete.return_value = 3

        result = adapter.clear()

        assert result is True
        mock_redis_instance.keys.assert_called_once_with("app:*")
        mock_redis_instance.delete.assert_called_once_with("app:key1", "app:key2", "app:key3")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_clear_with_prefix_no_keys(self, mock_redis_classes):
        """Test clearing with prefix when no keys exist."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.keys.return_value = []

        result = adapter.clear()

        assert result is True
        mock_redis_instance.delete.assert_not_called()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_clear_with_prefix_no_match(self, mock_redis_classes):
        """Test clearing keys with prefix that matches no keys."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.keys.return_value = []

        result = adapter.clear()

        assert result is True
        mock_redis_instance.keys.assert_called_once_with("app:*")
        mock_redis_instance.delete.assert_not_called()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_keys_without_prefix(self, connected_adapter):
        """Test getting all keys without prefix."""
        adapter, mock_redis = connected_adapter
        mock_redis.keys.return_value = [b"key1", b"key2", b"key3"]

        result = list(adapter.keys())

        assert result == ["key1", "key2", "key3"]
        mock_redis.keys.assert_called_once_with("*")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_keys_with_prefix(self, mock_redis_classes):
        """Test getting keys with prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.keys.return_value = ["app:key1", "app:key2"]

        result = list(adapter.keys())

        assert result == ["key1", "key2"]  # Prefix removed
        mock_redis_instance.keys.assert_called_once_with("app:*")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_keys_empty(self, connected_adapter):
        """Test getting keys when no keys exist."""
        adapter, mock_redis = connected_adapter
        mock_redis.keys.return_value = []

        result = list(adapter.keys())

        assert result == []

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_size_without_prefix(self, connected_adapter):
        """Test getting size without prefix."""
        adapter, mock_redis = connected_adapter
        mock_redis.dbsize.return_value = 42

        result = adapter.size()

        assert result == 42
        mock_redis.dbsize.assert_called_once()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_size_with_prefix(self, mock_redis_classes):
        """Test getting size with prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.keys.return_value = ["app:key1", "app:key2", "app:key3"]

        result = adapter.size()

        assert result == 3
        mock_redis_instance.keys.assert_called_once_with("app:*")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_operations_without_connection(self):
        """Test operations when adapter is not connected."""
        adapter = RedisAdapter()

        # Updated regex pattern to match actual error messages
        with pytest.raises(AdapterNotConnectedError, match=r"Redis adapter not connected for get"):
            adapter.get("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_not_connected(self):
        """Test get operation when adapter is not connected."""
        adapter = RedisAdapter()

        with pytest.raises(AdapterNotConnectedError, match=r"Redis adapter not connected for get"):
            adapter.get("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_not_connected(self):
        """Test set operation when adapter is not connected."""
        adapter = RedisAdapter()
        with pytest.raises(AdapterNotConnectedError, match=r"Redis adapter not connected for set"):
            adapter.set("test_key", "test_value")


class TestRedisAdapterBatchOperations:
    """Tests for RedisAdapter batch operations."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        with (
            patch("omni_cache.adapters.redis.redis.Redis") as mock_redis,
            patch("omni_cache.adapters.redis.redis.ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def connected_adapter(self, mock_redis_classes):
        """Create connected RedisAdapter instance."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        adapter = RedisAdapter(RedisAdapterConfig())
        adapter.connect()
        return adapter, mock_redis_instance

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_all_exist(self, connected_adapter):
        """Test get_many when all keys exist."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        values = ['"value1"', '"value2"']
        mock_redis.mget.return_value = values

        result = adapter.get_many(keys)

        assert result == {"key1": "value1", "key2": "value2"}
        mock_redis.mget.assert_called_once_with(["key1", "key2"])

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_some_exist(self, connected_adapter):
        """Test get_many when some keys exist."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        values = ['"value1"', None]
        mock_redis.mget.return_value = values

        result = adapter.get_many(keys)

        assert result == {"key1": "value1", "key2": None}
        mock_redis.mget.assert_called_once_with(["key1", "key2"])

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_none_exist(self, connected_adapter):
        """Test get_many when no keys exist."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        values = [None, None]
        mock_redis.mget.return_value = values

        result = adapter.get_many(keys)

        assert result == {"key1": None, "key2": None}
        mock_redis.mget.assert_called_once_with(["key1", "key2"])

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_empty_list(self, connected_adapter):
        """Test get_many with an empty list of keys."""
        adapter, mock_redis = connected_adapter
        result = adapter.get_many([])
        assert result == {}
        mock_redis.mget.assert_not_called()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_success(self, connected_adapter):
        """Test set_many successfully."""
        adapter, mock_redis = connected_adapter
        mapping = {"key1": "value1", "key2": "value2"}
        mock_redis.mset.return_value = True

        result = adapter.set_many(mapping)

        assert result == {"key1": True, "key2": True}
        mock_redis.mset.assert_called_once_with({"key1": '"value1"', "key2": '"value2"'})

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_with_ttl(self, connected_adapter):
        """Test set_many with TTL."""
        adapter, mock_redis = connected_adapter
        mapping = {"key1": "value1", "key2": "value2"}
        mock_redis.mset.return_value = True

        result = adapter.set_many(mapping, ttl=60)

        assert result == {"key1": True, "key2": True}
        mock_redis.mset.assert_called_once_with({"key1": '"value1"', "key2": '"value2"'})
        assert mock_redis.expire.call_count == 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_with_ttl_float(self, connected_adapter):
        """Test set_many with float TTL."""
        adapter, mock_redis = connected_adapter
        mapping = {"key1": "value1", "key2": "value2"}
        mock_redis.mset.return_value = True

        result = adapter.set_many(mapping, ttl=1.5)

        assert result == {"key1": True, "key2": True}
        mock_redis.mset.assert_called_once_with({"key1": '"value1"', "key2": '"value2"'})
        assert mock_redis.pexpire.call_count == 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_many_success(self, connected_adapter):
        """Test delete_many successfully."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        mock_redis.delete.return_value = 2

        result = adapter.delete_many(keys)

        assert result == {"key1": True, "key2": True}
        mock_redis.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_many_some_exist(self, connected_adapter):
        """Test delete_many when some keys exist."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        mock_redis.delete.return_value = 1

        result = adapter.delete_many(keys)

        assert result == {"key1": True, "key2": True}
        mock_redis.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_many_none_exist(self, connected_adapter):
        """Test delete_many when no keys exist."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        mock_redis.delete.return_value = 0

        result = adapter.delete_many(keys)

        assert result == {"key1": False, "key2": False}
        mock_redis.delete.assert_called_once_with("key1", "key2")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_deserialization_error(self, connected_adapter):
        """Test get_many with deserialization error."""
        adapter, mock_redis = connected_adapter
        keys = ["key1", "key2"]
        values = ['"value1"', "invalid_json"]
        mock_redis.mget.return_value = values

        result = adapter.get_many(keys)

        assert result == {"key1": "value1", "key2": None}

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_with_exception(self, connected_adapter):
        """Test set_many with an exception."""
        adapter, mock_redis = connected_adapter
        mapping = {"key1": "value1", "key2": "value2"}
        mock_redis.mset.side_effect = Exception("mset failed")

        result = adapter.set_many(mapping)

        assert result == {"key1": False, "key2": False}

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_serialization_error(self, connected_adapter):
        """Test set_many with a serialization error."""
        adapter, mock_redis = connected_adapter
        mapping = {"key1": "value1", "key2": "value2"}

        with patch.object(
            adapter, "_serialize_value", side_effect=ValueError("Serialization failed")
        ):
            result = adapter.set_many(mapping)

        assert result == {"key1": False, "key2": False}
        mock_redis.mset.assert_not_called()


class TestRedisAdapterOperationsNoRedis:
    """Tests for RedisAdapter operations when self._redis is None within the operation."""

    @pytest.fixture
    def adapter_no_redis_mock_safe_op(self):
        """Create a RedisAdapter instance and mock _safe_operation to bypass its check."""
        adapter = RedisAdapter(RedisAdapterConfig())
        # Patch _safe_operation to directly execute the passed operation callable
        with patch.object(adapter, "_safe_operation", side_effect=lambda op, name, default: op()):
            adapter._redis = None  # Ensure _redis is None for the inner operation checks
            yield adapter

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test get operation when self._redis is None inside _get_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.get("test_key")
        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test set operation when self._redis is None inside _set_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.set("test_key", "test_value")
        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test delete operation when self._redis is None inside _delete_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.delete("test_key")
        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_exists_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test exists operation when self._redis is None inside _exists_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.exists("test_key")
        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_clear_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test clear operation when self._redis is None inside _clear_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.clear()
        assert result is False  # clear returns False if no redis and no prefix

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_size_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test size operation when self._redis is None inside _size_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.size()
        assert result == 0

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_keys_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test keys operation when self._redis is None inside _keys_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = list(adapter.keys())
        assert result == []

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_many_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test get_many operation when self._redis is None inside _get_many_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.get_many(["key1", "key2"])
        assert result == {}

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_many_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test set_many operation when self._redis is None inside _set_many_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.set_many({"key1": "value1"})
        assert result == {}

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_delete_many_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test delete_many operation when self._redis is None inside _delete_many_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.delete_many(["key1"])
        assert result == {}

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_ttl_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test get_ttl operation when self._redis is None inside _get_ttl_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.get_ttl("test_key")
        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test increment operation when self._redis is None inside _increment_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.increment("test_key")
        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test ttl operation when self._redis is None inside _ttl_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.ttl("test_key")
        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_expire_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test expire operation when self._redis is None inside _expire_operation."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.expire("test_key", 60)
        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ping_no_redis_in_operation(self, adapter_no_redis_mock_safe_op):
        """Test ping operation when self._redis is None inside ping."""
        adapter = adapter_no_redis_mock_safe_op
        result = adapter.ping()
        assert result is False


class TestRedisAdapterKeyMethods:
    """Tests for RedisAdapter key management methods."""

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_unmake_key(self):
        """Test _unmake_key method."""
        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        assert adapter._unmake_key("app:my_key") == "my_key"
        assert adapter._unmake_key("another_key") == "another_key"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_unmake_key_no_prefix(self):
        """Test _unmake_key method when no prefix is configured."""
        config = RedisAdapterConfig()
        adapter = RedisAdapter(config)
        assert adapter._unmake_key("my_key") == "my_key"
