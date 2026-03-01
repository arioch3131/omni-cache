"""Unit tests for AsyncRedisAdapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omni_cache.adapters.redis.async_redis import AsyncRedisAdapter


@pytest.mark.asyncio
class TestAsyncRedisAdapter:
    @patch("omni_cache.adapters.redis.async_redis.HAS_ASYNC_REDIS", True)
    @patch("omni_cache.adapters.redis.async_redis.redis_asyncio")
    async def test_connect_success(self, mock_redis_asyncio):
        mock_redis_asyncio.ConnectionPool.return_value = MagicMock()
        mock_client = AsyncMock()
        mock_client.ping.return_value = True
        mock_redis_asyncio.Redis.return_value = mock_client

        adapter = AsyncRedisAdapter()
        assert await adapter.connect() is True
        assert adapter.is_connected() is True

    @patch("omni_cache.adapters.redis.async_redis.HAS_ASYNC_REDIS", False)
    async def test_connect_returns_false_when_dependency_missing(self):
        adapter = AsyncRedisAdapter()
        assert await adapter.connect() is False

    async def test_basic_get_set_delete(self):
        adapter = AsyncRedisAdapter()
        client = AsyncMock()
        adapter._redis = client

        client.set.return_value = True
        client.get.return_value = b'"value-1"'
        client.delete.return_value = 1
        client.exists.return_value = 1

        assert await adapter.set("k1", "value-1") is True
        assert await adapter.get("k1") == "value-1"
        assert await adapter.exists("k1") is True
        assert await adapter.delete("k1") is True

    async def test_prefix_and_batch_operations(self):
        adapter = AsyncRedisAdapter({"key_prefix": "pref", "key_separator": ":"})
        client = AsyncMock()
        adapter._redis = client

        client.set.return_value = True
        client.get.side_effect = [b'"v1"', None]
        client.delete.return_value = 1
        client.keys.return_value = [b"pref:a", b"pref:b"]

        set_many = await adapter.set_many({"a": "v1", "b": "v2"})
        assert set_many == {"a": True, "b": True}

        get_many = await adapter.get_many(["a", "b"])
        assert get_many == {"a": "v1", "b": None}

        keys = await adapter.keys()
        assert sorted(keys) == ["a", "b"]

        deleted = await adapter.delete_many(["a", "b"])
        assert deleted == {"a": True, "b": True}

    async def test_clear_and_size(self):
        adapter = AsyncRedisAdapter({"key_prefix": "pref"})
        client = AsyncMock()
        adapter._redis = client

        client.keys.return_value = [b"pref:a", b"pref:b"]
        client.dbsize.return_value = 7

        assert await adapter.clear() is True
        assert await adapter.size() == 2

        adapter_no_prefix = AsyncRedisAdapter()
        adapter_no_prefix._redis = client
        assert await adapter_no_prefix.size() == 7

    async def test_disconnect_and_health_check(self):
        adapter = AsyncRedisAdapter()
        client = AsyncMock()
        pool = AsyncMock()
        adapter._redis = client
        adapter._pool = pool

        client.ping.return_value = True
        assert await adapter.health_check() is True
        assert await adapter.disconnect() is True
        assert adapter.is_connected() is False
