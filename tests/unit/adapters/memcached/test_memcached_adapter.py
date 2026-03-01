"""Tests for Memcached adapter core behavior."""

from unittest.mock import MagicMock, patch

import pytest

from omni_cache.adapters.base.base import ConnectionState
from omni_cache.adapters.memcached.config import MemcachedAdapterConfig
from omni_cache.adapters.memcached.memcached import MemcachedAdapter
from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError
from omni_cache.core.exceptions.operation_exceptions import OperationFailedError


class TestMemcachedAdapter:
    """Unit tests for MemcachedAdapter."""

    @patch("omni_cache.adapters.memcached.memcached.HAS_MEMCACHED", True)
    @patch("omni_cache.adapters.memcached.memcached.Client")
    def test_connect_success(self, mock_client_class):
        mock_client = MagicMock()
        mock_client.get.return_value = b"ping"
        mock_client_class.return_value = mock_client

        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        assert adapter.connect() is True
        assert adapter.is_connected() is True

    @patch("omni_cache.adapters.memcached.memcached.HAS_MEMCACHED", False)
    def test_connect_returns_false_when_dependency_missing(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        assert adapter._do_connect() is False

    @patch("omni_cache.adapters.memcached.memcached.HAS_MEMCACHED", True)
    @patch("omni_cache.adapters.memcached.memcached.Client", side_effect=OSError("boom"))
    def test_connect_exception_resets_client(self, _mock_client_class):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        assert adapter._do_connect() is False
        assert adapter._client is None

    def test_init_with_dict_and_default_config(self):
        adapter_from_dict = MemcachedAdapter({"host": "127.0.0.1", "port": 22122})
        assert adapter_from_dict._config.host == "127.0.0.1"
        assert adapter_from_dict._config.port == 22122

        adapter_default = MemcachedAdapter()
        assert adapter_default._config.host == "localhost"
        assert adapter_default._config.port == 11211

    def test_disconnect_handles_close_exception(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        client = MagicMock()
        client.close.side_effect = RuntimeError("close failed")
        adapter._client = client

        assert adapter._do_disconnect() is False

    def test_basic_get_set_delete_with_mocked_client(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        client = MagicMock()
        adapter._client = client
        adapter._state = ConnectionState.CONNECTED

        client.set.return_value = True
        client.get.return_value = b'"value-1"'

        assert adapter.set("k1", "value-1") is True
        assert adapter.get("k1") == "value-1"

        client.delete.return_value = True
        assert adapter.delete("k1") is True

    def test_health_check_paths(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())

        assert adapter._do_health_check() is False

        client = MagicMock()
        adapter._client = client

        client.get.return_value = None
        assert adapter._do_health_check() is False

        client.get.return_value = b"mismatch"
        assert adapter._do_health_check() is False

        client.get.side_effect = RuntimeError("health error")
        assert adapter._do_health_check() is False

    def test_serialization_and_deserialization_branches(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())

        assert adapter._serialize_json({"a": 1}) == '{"a": 1}'
        assert adapter._deserialize_json(b'{"a": 1}') == {"a": 1}

        assert adapter._serialize_string(12) == "12"
        assert adapter._deserialize_string(b"abc") == "abc"

        adapter._config.serialization_method = "invalid"
        with pytest.raises(ValueError):
            adapter._serialize_value("x")
        with pytest.raises(ValueError):
            adapter._deserialize_value("x")

    def test_key_and_ttl_helpers(self):
        adapter = MemcachedAdapter(
            MemcachedAdapterConfig(key_prefix="pref", key_separator="|", default_ttl=8)
        )

        assert adapter._make_key("k") == "pref|k"
        assert adapter._normalize_ttl(None) == 8
        assert adapter._normalize_ttl(3.8) == 3
        assert adapter._normalize_ttl(-5) == 0

    def test_safe_operation_raises_when_not_connected(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())

        with pytest.raises(AdapterNotConnectedError):
            adapter._safe_operation(lambda: True, "test")

    def test_safe_operation_retries_and_returns_default(self, monkeypatch):
        adapter = MemcachedAdapter(MemcachedAdapterConfig(max_retries=3, retry_delay=0.0))
        adapter._client = MagicMock()

        class MemcacheBoom(Exception):
            pass

        monkeypatch.setattr(
            "omni_cache.adapters.memcached.memcached.MemcacheClientError",
            MemcacheBoom,
        )

        attempts = {"count": 0}

        def _always_fails():
            attempts["count"] += 1
            raise MemcacheBoom("fail")

        assert adapter._safe_operation(_always_fails, "op", default=False) is False
        assert attempts["count"] == 3

    def test_safe_operation_raises_operation_failed_without_default(self, monkeypatch):
        adapter = MemcachedAdapter(MemcachedAdapterConfig(max_retries=2, retry_delay=0.0))
        adapter._client = MagicMock()

        class MemcacheBoom(Exception):
            pass

        monkeypatch.setattr(
            "omni_cache.adapters.memcached.memcached.MemcacheClientError",
            MemcacheBoom,
        )

        with pytest.raises(OperationFailedError):
            adapter._safe_operation(lambda: (_ for _ in ()).throw(MemcacheBoom("boom")), "op")

    def test_set_delete_clear_keys_and_size_branches(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        client = MagicMock()
        adapter._client = client
        adapter._state = ConnectionState.CONNECTED

        client.set.return_value = False
        assert adapter.set("k_fail", "v") is False
        assert adapter._known_keys == set()

        adapter._known_keys = {"k1", "k2"}

        def _delete_side_effect(key):
            return key == "k1"

        client.delete.side_effect = _delete_side_effect
        assert adapter.clear() is False
        assert adapter._known_keys == {"k2"}

        client.get.side_effect = lambda key: b"v" if key == "k2" else None
        assert list(adapter.keys()) == ["k2"]
        assert adapter.size() == 1

    def test_exists_and_bulk_methods(self):
        adapter = MemcachedAdapter(MemcachedAdapterConfig())
        client = MagicMock()
        adapter._client = client
        adapter._state = ConnectionState.CONNECTED

        client.get.side_effect = [b'"v1"', None, b'"v1"', None]
        client.set.return_value = True
        client.delete.return_value = True

        assert adapter.exists("a") is True
        assert adapter.exists("b") is False

        set_result = adapter.set_many({"a": "v1", "b": "v2"})
        assert set_result == {"a": True, "b": True}

        get_result = adapter.get_many(["a", "b"])
        assert get_result == {"a": "v1", "b": None}

        delete_result = adapter.delete_many(["a", "b"])
        assert delete_result == {"a": True, "b": True}
