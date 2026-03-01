"""
Tests for Redis adapter connection management and health checking.

This module tests the RedisAdapter connection lifecycle, pool management,
health checks, and connection state transitions.
"""

import threading
from unittest.mock import MagicMock, patch

import pytest

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


class TestRedisAdapterConnection:
    """Tests for RedisAdapter connection management."""

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        with (
            patch("omni_cache.adapters.redis.redis.Redis") as mock_redis,
            patch("omni_cache.adapters.redis.redis.ConnectionPool") as mock_pool,
        ):
            yield mock_redis, mock_pool

    @pytest.fixture
    def adapter(self, mock_redis_classes):
        """Create RedisAdapter instance with mocked Redis."""
        config = RedisAdapterConfig(host="localhost", port=6379, db=0)
        return RedisAdapter(config)

    @pytest.fixture
    def clean_connected_adapter(self, adapter):
        """Create connected RedisAdapter with clean mock."""
        adapter, mock_redis = adapter
        mock_redis.reset_mock()
        return adapter, mock_redis

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_successful_connection(self, adapter, mock_redis_classes):
        """Test successful connection to Redis server."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_adapter = adapter
        result = mock_adapter.connect()

        assert result is True
        assert mock_adapter.is_connected() is True
        assert mock_adapter._connection_pool is not None
        assert mock_adapter._redis is not None

        # Verify connection pool creation
        mock_pool.assert_called_once()
        pool_kwargs = mock_pool.call_args[1]
        assert pool_kwargs["host"] == "localhost"
        assert pool_kwargs["port"] == 6379
        assert pool_kwargs["db"] == 0
        assert pool_kwargs["max_connections"] == 10

        # Verify Redis client creation and ping
        mock_redis.assert_called_once()
        mock_redis_instance.ping.assert_called_once()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_failure_on_pool_creation(self, adapter, mock_redis_classes):
        """Test connection failure during pool creation."""
        _, mock_pool = mock_redis_classes
        mock_pool.side_effect = Exception("Pool creation failed")

        result = adapter.connect()

        assert result is False
        assert adapter.is_connected() is False
        assert adapter._connection_pool is None
        assert adapter._redis is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_failure_on_ping(self, adapter, mock_redis_classes):
        """Test connection failure during ping."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_redis_instance.ping.side_effect = Exception("Ping failed")

        result = adapter.connect()

        assert result is False
        assert adapter.is_connected() is False
        assert adapter._connection_pool is None
        assert adapter._redis is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_successful_disconnection(self, adapter, mock_redis_classes):
        """Test successful disconnection from Redis server."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_pool_instance = MagicMock()
        mock_pool.return_value = mock_pool_instance

        # First connect
        adapter.connect()
        assert adapter.is_connected() is True

        # Then disconnect
        result = adapter.disconnect()

        assert result is True
        assert adapter.is_connected() is False
        assert adapter._connection_pool is None
        assert adapter._redis is None

        # Verify pool cleanup
        mock_pool_instance.disconnect.assert_called_once()

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_disconnection_failure(self, adapter, mock_redis_classes):
        """Test disconnection failure handling."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        mock_pool_instance = MagicMock()
        mock_pool.return_value = mock_pool_instance

        adapter.connect()

        # Mock disconnection failure
        mock_pool_instance.disconnect.side_effect = Exception("Disconnection failed")

        result = adapter.disconnect()

        assert result is False
        assert adapter.is_connected() is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_disconnect_without_connection(self, adapter):
        """Test disconnection when not connected."""
        result = adapter.disconnect()

        assert result is True
        assert adapter.is_connected() is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_pool_configuration(self, mock_redis_classes):
        """Test connection pool configuration with custom settings."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance
        redis_credential = "redis-auth-for-tests"

        config = RedisAdapterConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password=redis_credential,
            username="user",
            connection_pool_max_connections=25,
            connection_timeout=10.0,
            socket_timeout=5.0,
        )
        adapter = RedisAdapter(config)

        adapter.connect()

        # Verify pool creation with custom configuration
        mock_pool.assert_called_once()
        pool_kwargs = mock_pool.call_args[1]
        assert pool_kwargs["host"] == "redis.example.com"
        assert pool_kwargs["port"] == 6380
        assert pool_kwargs["db"] == 1
        assert pool_kwargs["password"] == redis_credential
        assert pool_kwargs["username"] == "user"
        assert pool_kwargs["max_connections"] == 25

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_thread_safety(self, adapter, mock_redis_classes):
        """Test that connection operations are thread-safe."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        results = []
        errors = []

        def connect_thread():
            try:
                result = adapter.connect()
                results.append(result)
            except Exception as e:
                errors.append(e)

        def disconnect_thread():
            try:
                result = adapter.disconnect()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Start multiple connection/disconnection threads
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=connect_thread))
        for _ in range(5):
            threads.append(threading.Thread(target=disconnect_thread))

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0
        assert len(results) == 10

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_state_tracking(self, adapter, mock_redis_classes):
        """Test connection state is properly tracked."""
        mock_redis, mock_pool = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        # Initially disconnected
        assert adapter.is_connected() is False

        # After successful connection
        adapter.connect()
        assert adapter.is_connected() is True

        # After disconnection
        adapter.disconnect()
        assert adapter.is_connected() is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_cleanup_connection_method(self, adapter):
        """Test cleanup connection method."""
        # Set up mock objects
        adapter._redis = MagicMock()
        adapter._connection_pool = MagicMock()

        # Call cleanup
        adapter._cleanup_connection()

        # Verify cleanup sets references to None
        assert adapter._redis is None
        assert adapter._connection_pool is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_cleanup_connection_with_error(self, adapter):
        """Test cleanup connection with error handling."""
        mock_pool = MagicMock()
        mock_pool.disconnect.side_effect = Exception("Cleanup error")
        adapter._connection_pool = mock_pool

        # Should not raise exception, but handle error gracefully
        adapter._cleanup_connection()

        # Should still cleanup references
        assert adapter._connection_pool is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_disconnect_no_pool(self, adapter):
        """Test disconnection when there is no connection pool."""
        adapter._connection_pool = None
        result = adapter._do_disconnect()
        assert result is True


class TestRedisAdapterHealthCheck:
    """Tests for RedisAdapter health checking functionality."""

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

        config = RedisAdapterConfig(health_check_key="test_health")
        adapter = RedisAdapter(config)
        adapter.connect()
        return adapter, mock_redis_instance

    @pytest.fixture
    def clean_connected_adapter(self, connected_adapter):
        """Create connected RedisAdapter with clean mock."""
        adapter, mock_redis = connected_adapter
        mock_redis.reset_mock()
        return adapter, mock_redis

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_successful_health_check(self, connected_adapter):
        """Test successful health check."""
        adapter, mock_redis = connected_adapter
        with patch("time.time", return_value=12345.0):
            test_value = f"health_check_{12345.0:.1f}"
            serialized_value = adapter._serialize_value(test_value)
            mock_redis.get.return_value = serialized_value

            result = adapter._do_health_check()

            assert result is True
            mock_redis.setex.assert_called_once_with("test_health", 10, serialized_value)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_ping_failure(self, connected_adapter):
        """Test health check with ping failure."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.side_effect = Exception("Ping failed")

        result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_write_failure(self, connected_adapter):
        """Test health check with write operation failure."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.side_effect = Exception("Write failed")

        result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_read_failure(self, connected_adapter):
        """Test health check failure during read operation."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.side_effect = Exception("Read failed")

        result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_is_healthy_with_exceptions(self, connected_adapter):
        """Test is healthy with do_health_check exception."""
        adapter, mock_redis = connected_adapter
        with patch(
            "omni_cache.adapters.redis.RedisAdapter._do_health_check",
            side_effect=Exception("Health check failed"),
        ):
            result = adapter.is_healthy()
            assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_value_mismatch(self, clean_connected_adapter):
        """Test health check failure due to value mismatch."""
        adapter, mock_redis = clean_connected_adapter
        mock_redis.get.return_value = '"different_value"'  # Wrong value

        with patch("time.time", return_value=1234567890.0):
            result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_without_connection(self):
        """Test health check when not connected."""
        adapter = RedisAdapter()

        result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_with_key_prefix(self, mock_redis_classes):
        """Test health check with key prefix configuration."""
        mock_redis, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(key_prefix="app", health_check_key="health")
        adapter = RedisAdapter(config)
        adapter.connect()

        with patch("time.time", return_value=12345.0):
            test_value = f"health_check_{12345.0:.1f}"
            serialized_value = adapter._serialize_value(test_value)
            mock_redis_instance.get.return_value = serialized_value

            result = adapter._do_health_check()

            assert result is True
            # Check that prefixed key was used in operations
            mock_redis_instance.setex.assert_called_once()
            used_key = mock_redis_instance.setex.call_args[0][0]
            assert used_key == "app:health"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_concurrent_access(self, clean_connected_adapter):
        """Test health check with concurrent access."""
        adapter, mock_redis = clean_connected_adapter
        with patch("time.time", return_value=12345.0) as mock_time:
            test_value = f"health_check_{mock_time.return_value}"
            serialized_value = adapter._serialize_value(test_value)
            mock_redis.get.return_value = serialized_value

            results = []
            errors = []

            def health_check_thread():
                try:
                    result = adapter._do_health_check()
                    results.append(result)
                except Exception as e:
                    errors.append(e)

            # Start multiple health check threads
            threads = [threading.Thread(target=health_check_thread) for _ in range(10)]

            for thread in threads:
                thread.start()

            for thread in threads:
                thread.join()

            # All should succeed without errors
            assert len(errors) == 0
            assert all(results)
            assert len(results) == 10

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_serialization_error(self, clean_connected_adapter):
        """Test health check handles serialization errors."""
        adapter, mock_redis = clean_connected_adapter
        mock_redis.get.return_value = "invalid_json"  # Invalid JSON

        with patch("time.time", return_value=1234567890.0):
            result = adapter._do_health_check()

        assert result is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_delete_failure_ignored(self, clean_connected_adapter):
        """Test that health check ignores delete failures."""
        adapter, mock_redis = clean_connected_adapter
        with patch("time.time", return_value=1234567890.0):
            test_value = f"health_check_{1234567890.0}"
            serialized_value = adapter._serialize_value(test_value)
            mock_redis.get.return_value = serialized_value
            mock_redis.delete.side_effect = Exception("Delete failed")

            result = adapter._do_health_check()

        # Should still succeed despite delete failure
        assert result is True

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_is_healthy_exception(self, connected_adapter):
        """Test is_healthy when an exception is raised."""
        adapter, mock_redis = connected_adapter
        mock_redis.setex.side_effect = Exception("Some error")

        assert adapter.is_healthy() is False

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_health_check_get_none(self, connected_adapter):
        """Test health check when get returns None."""
        adapter, mock_redis = connected_adapter
        mock_redis.get.return_value = None

        result = adapter._do_health_check()

        assert result is False
