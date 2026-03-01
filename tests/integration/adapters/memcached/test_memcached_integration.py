"""
Integration tests for Memcached adapter with a real Memcached instance.

These tests validate behavior against a live server (default localhost:11211):
connection lifecycle, CRUD, TTL expiration, batch operations, and key tracking.
"""

import time

import pytest

try:
    from omni_cache.adapters.memcached import MemcachedAdapter, MemcachedAdapterConfig

    HAS_MEMCACHED = True
except ImportError:
    HAS_MEMCACHED = False
    MemcachedAdapter = None
    MemcachedAdapterConfig = None


@pytest.mark.integration
class TestMemcachedAdapterIntegration:
    """Integration tests against a live Memcached server."""

    @pytest.fixture
    def real_memcached_config(self):
        """Configuration for integration tests."""
        return MemcachedAdapterConfig(
            host="localhost",
            port=11211,
            key_prefix="integration_test",
            key_separator=":",
            connect_timeout=2.0,
            timeout=2.0,
            default_ttl=60,
            serialization_method="json",
            retry_on_error=True,
            max_retries=2,
        )

    @pytest.fixture
    def real_adapter(self, real_memcached_config):
        """Connected Memcached adapter, skipped when backend is unavailable."""
        if not HAS_MEMCACHED:
            pytest.skip("Memcached dependency not available")

        adapter = MemcachedAdapter(real_memcached_config)

        try:
            if not adapter.connect():
                pytest.skip("Cannot connect to Memcached server at localhost:11211")

            adapter.clear()
            yield adapter
        except Exception as error:  # pylint: disable=broad-exception-caught
            pytest.skip(f"Memcached server not available: {error}")
        finally:
            if adapter.is_connected():
                adapter.clear()
                adapter.disconnect()

    def test_connection_and_backend_info(self, real_adapter):
        """Validate connection state, health check, and backend metadata."""
        assert real_adapter.is_connected() is True
        assert real_adapter.health_check() is True

        backend_info = real_adapter.get_backend_info()
        assert backend_info["backend"] == "memcached"
        assert backend_info["name"]

    def test_basic_crud_operations(self, real_adapter):
        """Validate set/get/exists/delete behavior on a real server."""
        assert real_adapter.set("user:1", {"name": "alice", "age": 31}) is True
        assert real_adapter.get("user:1") == {"name": "alice", "age": 31}

        assert real_adapter.exists("user:1") is True
        assert real_adapter.exists("user:missing") is False

        assert real_adapter.delete("user:1") is True
        assert real_adapter.get("user:1") is None
        assert real_adapter.exists("user:1") is False

    def test_ttl_and_default_ttl_behavior(self, real_adapter):
        """Validate explicit TTL and adapter default TTL behavior."""
        assert real_adapter.set("short_lived", "value", ttl=1) is True
        assert real_adapter.get("short_lived") == "value"

        time.sleep(1.2)

        assert real_adapter.get("short_lived") is None
        assert real_adapter.exists("short_lived") is False

        # Use default_ttl from fixture (60 seconds): key should still be available.
        assert real_adapter.set("default_ttl_key", "still_here") is True
        assert real_adapter.get("default_ttl_key") == "still_here"

    def test_batch_operations_and_partial_deletes(self, real_adapter):
        """Validate set_many/get_many/delete_many consistency."""
        payload = {f"item:{index}": {"index": index} for index in range(20)}

        set_result = real_adapter.set_many(payload)
        assert len(set_result) == len(payload)
        assert all(set_result.values())

        retrieved = real_adapter.get_many(list(payload.keys()))
        assert retrieved == payload

        keys_to_delete = list(payload.keys())[:8]
        delete_result = real_adapter.delete_many(keys_to_delete)
        assert len(delete_result) == len(keys_to_delete)
        assert all(delete_result.values())

        post_delete = real_adapter.get_many(list(payload.keys()))
        for key in keys_to_delete:
            assert post_delete[key] is None
        for key in payload.keys() - set(keys_to_delete):
            assert post_delete[key] == payload[key]

    def test_keys_size_and_stats_tracking(self, real_adapter):
        """Validate known key tracking and basic cache stats updates."""
        assert real_adapter.size() == 0

        assert real_adapter.set("k1", "v1") is True
        assert real_adapter.set("k2", "v2") is True
        assert real_adapter.set("k3", "v3", ttl=1) is True

        keys_before_expiry = list(real_adapter.keys())
        assert len(keys_before_expiry) == 3
        assert real_adapter.size() == 3

        # keys() returns backend keys, including prefix.
        assert all(key.startswith("integration_test:") for key in keys_before_expiry)

        time.sleep(1.2)

        keys_after_expiry = list(real_adapter.keys())
        assert len(keys_after_expiry) == 2
        assert real_adapter.size() == 2

        # Force at least one cache hit in this scenario before checking stats.
        assert real_adapter.get("k1") == "v1"

        stats = real_adapter.get_stats()
        assert stats.sets >= 3
        assert stats.hits >= 1
