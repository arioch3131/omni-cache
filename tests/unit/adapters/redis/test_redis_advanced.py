"""
Tests for Redis adapter advanced and TTL operations.

This module tests Redis-specific operations like increment, expire, ttl,
ping, backend info, and comprehensive TTL functionality.
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


class TestRedisAdapterSpecificOperations:
    """Tests for Redis-specific operations."""

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
    def test_increment_integer(self, connected_adapter):
        """Test increment operation with integer amount."""
        adapter, mock_redis = connected_adapter
        mock_redis.incrby.return_value = 15

        result = adapter.increment("counter", 5)

        assert result == 15
        mock_redis.incrby.assert_called_once_with("counter", 5)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_float(self, connected_adapter):
        """Test increment operation with float amount."""
        adapter, mock_redis = connected_adapter
        mock_redis.incrbyfloat.return_value = 12.5

        result = adapter.increment("counter", 2.5)

        assert result == 12.5
        mock_redis.incrbyfloat.assert_called_once_with("counter", 2.5)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_default_amount(self, connected_adapter):
        """Test increment operation with default amount (1)."""
        adapter, mock_redis = connected_adapter
        mock_redis.incrby.return_value = 6

        result = adapter.increment("counter")

        assert result == 6
        mock_redis.incrby.assert_called_once_with("counter", 1)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_nonexistent_key(self, connected_adapter):
        """Test increment operation on non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.incrby.return_value = 10

        result = adapter.increment("new_counter", 10)

        assert result == 10
        mock_redis.incrby.assert_called_once_with("new_counter", 10)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_non_numeric_value(self, connected_adapter):
        """Test increment operation on key with non-numeric value."""
        adapter, mock_redis = connected_adapter

        # Import the specific Redis exception
        from omni_cache.adapters.redis.redis import ResponseError

        mock_redis.incrby.side_effect = ResponseError("value is not an integer")

        result = adapter.increment("string_key", 1)

        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_increment_with_key_prefix(self, mock_redis_classes):
        """Test increment operation with key prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.incrby.return_value = 20

        result = adapter.increment("counter", 5)

        assert result == 20
        mock_redis_instance.incrby.assert_called_once_with("app:counter", 5)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ping_success(self, connected_adapter):
        """Test successful ping operation."""
        adapter, mock_redis = connected_adapter
        mock_redis.reset_mock()

        mock_redis.ping.return_value = True

        result = adapter.ping()

        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ping_failure(self, connected_adapter):
        """Test failed ping operation."""
        adapter, mock_redis = connected_adapter
        mock_redis.ping.side_effect = Exception("Ping failed")

        result = adapter.ping()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ping_without_connection(self):
        """Test ping when not connected."""
        adapter = RedisAdapter()

        result = adapter.ping()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_backend_info_success(self, connected_adapter):
        """Test get_backend_info with successful Redis info."""
        adapter, mock_redis = connected_adapter

        # Mock Redis info response
        redis_info = {
            "redis_version": "6.2.0",
            "used_memory_human": "1.5M",
            "connected_clients": 5,
            "total_commands_processed": 1000,
            "keyspace_hits": 800,
            "keyspace_misses": 200,
            "uptime_in_seconds": 3600,
            "db0": {"keys": 100, "expires": 10},
        }
        mock_redis.info.return_value = redis_info

        result = adapter.get_backend_info()

        # Check server_info structure instead of direct fields
        assert "server_info" in result
        server_info = result["server_info"]
        assert server_info["redis_version"] == "6.2.0"
        assert server_info["used_memory_human"] == "1.5M"
        assert server_info["connected_clients"] == 5

        # Check adapter configuration fields
        assert result["host"] == "localhost"
        assert result["port"] == 6379
        assert result["db"] == 0  # Changed from 'database' to 'db'
        assert result["serialization_method"] == "json"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_backend_info_redis_error(self, connected_adapter):
        """Test get_backend_info with Redis info error."""
        adapter, mock_redis = connected_adapter
        mock_redis.info.side_effect = Exception("Info failed")

        result = adapter.get_backend_info()

        # Should still return basic info even if Redis info fails
        assert "host" in result
        assert "port" in result
        assert result["host"] == "localhost"
        assert result["port"] == 6379

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_backend_info_with_custom_config(self, mock_redis_classes):
        """Test get_backend_info with custom configuration."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            serialization_method="json",
            key_prefix="myapp",
            connection_pool_max_connections=20,
        )
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.info.return_value = {"redis_version": "6.2.0"}

        result = adapter.get_backend_info()

        assert result["host"] == "redis.example.com"
        assert result["port"] == 6380
        assert result["db"] == 1  # Changed from 'database' to 'db'
        assert result["serialization_method"] == "json"
        assert result["key_prefix"] == "myapp"
        assert (
            result["connection_pool_max_connections"] == 20
        )  # Changed from 'connection_pool_size'

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_backend_info_not_connected(self):
        """Test get_backend_info when not connected."""
        adapter = RedisAdapter()
        info = adapter.get_backend_info()
        assert info["status"] == "disconnected"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_specific_operations_without_connection(self):
        """Test Redis-specific operations when not connected."""
        adapter = RedisAdapter()

        # Updated regex pattern to match actual error message format
        with pytest.raises(
            AdapterNotConnectedError, match=r"Redis adapter not connected for increment"
        ):
            adapter.increment("counter")

        # ping() should return False, not raise exception
        assert adapter.ping() is False


class TestRedisAdapterTTL:
    """Tests for Redis adapter TTL (Time To Live) operations."""

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
    def test_expire_existing_key_integer_ttl(self, connected_adapter):
        """Test expire operation on existing key with integer TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.expire.return_value = True

        result = adapter.expire("test_key", 60)

        assert result is True
        mock_redis.expire.assert_called_once_with("test_key", 60)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_expire_existing_key_float_ttl(self, connected_adapter):
        """Test expire operation on existing key with float TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.pexpire.return_value = True

        result = adapter.expire("test_key", 1.5)

        assert result is True
        mock_redis.pexpire.assert_called_once_with("test_key", 1500)  # 1.5 seconds = 1500 ms

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_expire_nonexistent_key(self, connected_adapter):
        """Test expire operation on non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.expire.return_value = False

        result = adapter.expire("nonexistent_key", 60)

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_expire_with_key_prefix(self, mock_redis_classes):
        """Test expire operation with key prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.expire.return_value = True

        result = adapter.expire("test_key", 60)

        assert result is True
        mock_redis_instance.expire.assert_called_once_with("app:test_key", 60)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_key_with_expiration(self, connected_adapter):
        """Test ttl operation on key with expiration."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = 45000  # 45 seconds in milliseconds

        result = adapter.ttl("test_key")

        assert result == 45.0  # Converted to seconds
        mock_redis.pttl.assert_called_once_with("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_key_without_expiration(self, connected_adapter):
        """Test ttl operation on key without expiration."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = -1  # Key exists but has no expiration

        result = adapter.ttl("test_key")

        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_nonexistent_key(self, connected_adapter):
        """Test ttl operation on non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = -2  # Key doesn't exist

        result = adapter.ttl("nonexistent_key")

        assert result is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_precise_timing(self, connected_adapter):
        """Test ttl operation with precise millisecond timing."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = 1234  # 1.234 seconds

        result = adapter.ttl("test_key")

        assert result == 1.234

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_with_key_prefix(self, mock_redis_classes):
        """Test ttl operation with key prefix."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", key_separator=":")
        adapter = RedisAdapter(config)
        adapter.connect()

        mock_redis_instance.pttl.return_value = 30000

        result = adapter.ttl("test_key")

        assert result == 30.0
        mock_redis_instance.pttl.assert_called_once_with("app:test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_integer_ttl(self, connected_adapter):
        """Test set operation with integer TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=120)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_key", 120, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_float_ttl(self, connected_adapter):
        """Test set operation with float TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.psetex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=2.5)

        assert result is True
        mock_redis.psetex.assert_called_once_with("test_key", 2500, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_without_ttl(self, connected_adapter):
        """Test set operation without TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.set.return_value = True

        result = adapter.set("test_key", "test_value")

        assert result is True
        mock_redis.set.assert_called_once_with("test_key", '"test_value"')
        # Ensure TTL methods are not called
        mock_redis.setex.assert_not_called()
        mock_redis.psetex.assert_not_called()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_set_with_zero_ttl(self, connected_adapter):
        """Test set operation with zero TTL."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.return_value = True

        result = adapter.set("test_key", "test_value", ttl=0)

        assert result is True
        mock_redis.setex.assert_called_once_with("test_key", 0, '"test_value"')

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_edge_cases(self, connected_adapter):
        """Test TTL with various edge cases."""
        adapter, mock_redis = connected_adapter

        # Test with 1 millisecond
        mock_redis.pttl.return_value = 1
        result = adapter.ttl("test_key")
        assert result == 0.001

        # Test with exactly 1 second
        mock_redis.pttl.return_value = 1000
        result = adapter.ttl("test_key")
        assert result == 1.0

        # Test with large value
        mock_redis.pttl.return_value = 86400000  # 24 hours
        result = adapter.ttl("test_key")
        assert result == 86400.0

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_expire_edge_cases(self, connected_adapter):
        """Test expire with edge cases."""
        adapter, mock_redis = connected_adapter

        # Test with very small float
        mock_redis.pexpire.return_value = True
        result = adapter.expire("test_key", 0.001)
        assert result is True
        mock_redis.pexpire.assert_called_with("test_key", 1)

        # Test with large float
        mock_redis.pexpire.return_value = True
        result = adapter.expire("test_key", 3600.5)
        assert result is True
        mock_redis.pexpire.assert_called_with("test_key", 3600500)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_ttl_operations_without_connection(self):
        """Test TTL operations when not connected."""
        adapter = RedisAdapter()

        # Updated regex pattern to match actual error messages
        with pytest.raises(AdapterNotConnectedError, match=r"Redis adapter not connected for ttl"):
            adapter.ttl("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_comprehensive_ttl_workflow(self, connected_adapter):
        """Test complete TTL workflow: set with TTL, check TTL, extend TTL."""
        adapter, mock_redis = connected_adapter

        # Set key with TTL
        mock_redis.setex.return_value = True
        result = adapter.set("workflow_key", "value", ttl=60)
        assert result is True

        # Check TTL
        mock_redis.pttl.return_value = 45000  # 45 seconds remaining
        ttl = adapter.ttl("workflow_key")
        assert ttl == 45.0

        # Extend TTL
        mock_redis.expire.return_value = True
        result = adapter.expire("workflow_key", 120)
        assert result is True

        # Verify calls
        mock_redis.setex.assert_called_once_with("workflow_key", 60, '"value"')
        mock_redis.pttl.assert_called_once_with("workflow_key")
        mock_redis.expire.assert_called_once_with("workflow_key", 120)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_ttl_key_with_expiration(self, connected_adapter):
        """Test get_ttl operation on key with expiration."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = 45000  # 45 seconds in milliseconds

        result = adapter.get_ttl("test_key")

        assert result == 45.0  # Converted to seconds
        mock_redis.pttl.assert_called_once_with("test_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_ttl_nonexistent_key(self, connected_adapter):
        """Test get_ttl operation on non-existent key."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = -2  # Key doesn't exist

        result = adapter.get_ttl("nonexistent_key")

        assert result is None
        mock_redis.pttl.assert_called_once_with("nonexistent_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_get_ttl_key_without_expiration(self, connected_adapter):
        """Test get_ttl operation on key without expiration."""
        adapter, mock_redis = connected_adapter
        mock_redis.pttl.return_value = -1  # Key exists but has no expiration

        result = adapter.get_ttl("test_key")

        assert result is None
        mock_redis.pttl.assert_called_once_with("test_key")
