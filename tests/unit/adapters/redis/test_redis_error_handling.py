"""
Tests for Redis adapter error handling and robustness.

This module tests the RedisAdapter's error handling capabilities,
including retry logic, timeout handling, connection failures,
and graceful degradation under various error conditions.
"""

from unittest.mock import MagicMock, patch

import pytest

from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError
from omni_cache.core.exceptions.operation_exceptions import OperationFailedError

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


class TestRedisAdapterErrorHandling:
    """Tests for Redis adapter error handling and robustness."""

    @pytest.fixture
    def adapter(self):
        """Create a RedisAdapter instance."""
        config = RedisAdapterConfig()
        return RedisAdapter(config)

    @pytest.fixture
    def mock_redis_classes(self):
        """Mock Redis classes for testing."""
        with (
            patch("omni_cache.adapters.redis.redis.Redis") as mock_redis,
            patch("omni_cache.adapters.redis.redis.ConnectionPool") as mock_pool,
        ):
            # Import real exceptions instead of mocking them
            from redis.exceptions import ConnectionError as RedisConnectionError
            from redis.exceptions import RedisError, ResponseError
            from redis.exceptions import TimeoutError as RedisTimeoutError

            yield (
                mock_redis,
                mock_pool,
                RedisConnectionError,
                RedisTimeoutError,
                RedisError,
                ResponseError,
            )

    @pytest.fixture
    def connected_adapter_with_retry(self, mock_redis_classes):
        """Create connected RedisAdapter with retry configuration."""
        mock_redis, _, _, _, _, _ = mock_redis_classes
        mock_redis_instance = MagicMock()
        mock_redis.return_value = mock_redis_instance

        config = RedisAdapterConfig(
            retry_on_error=True,
            max_retries=3,
            retry_delay=0.01,  # Very short for testing
            retry_backoff_factor=2.0,
        )
        adapter = RedisAdapter(config)
        adapter.connect()
        return adapter, mock_redis_instance

    def test_connection_error_handling_no_retry(self, adapter, mock_redis_classes):
        """Test connection error handling without retry."""
        mock_redis, _, conn_err, _, _, _ = mock_redis_classes
        mock_redis_instance = mock_redis.return_value

        # Configure no retries
        adapter._config.retry_on_error = False

        # Mock connect to succeed
        adapter.connect()

        mock_redis_instance.get.side_effect = conn_err("Connection lost")

        # Should raise OperationFailedError immediately
        with pytest.raises(OperationFailedError):
            adapter.get("test_key")

        assert mock_redis_instance.get.call_count == 1

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_error_with_successful_retry(
        self,
        connected_adapter_with_retry,
        mock_redis_classes,
    ):
        """Test connection error that succeeds on retry."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, mock_conn_err, _, _, _ = mock_redis_classes

        # First call fails, second succeeds
        mock_redis.get.side_effect = [mock_conn_err("Connection lost"), '"success"']

        with patch("time.sleep") as mock_sleep:
            result = adapter.get("test_key")

        assert result == "success"
        assert mock_redis.get.call_count == 2
        mock_sleep.assert_called_once_with(0.01)  # retry_delay

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_error_exhausted_retries(
        self,
        connected_adapter_with_retry,
        mock_redis_classes,
    ):
        """Test connection error that exhausts all retries."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, mock_conn_err, _, _, _ = mock_redis_classes

        # All calls fail
        mock_redis.get.side_effect = mock_conn_err("Persistent connection error")

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(OperationFailedError):
                adapter.get("test_key")

        # Should try 3 times (initial + 2 retries)
        assert mock_redis.get.call_count == 3
        # Should sleep 2 times (between retries)
        assert mock_sleep.call_count == 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_timeout_error_with_retry(self, connected_adapter_with_retry, mock_redis_classes):
        """Test timeout error handling with retry."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, _, mock_timeout_err, _, _ = mock_redis_classes

        # First call times out, second succeeds
        mock_redis.get.side_effect = [mock_timeout_err("Operation timed out"), '"success"']

        with patch("time.sleep"):
            result = adapter.get("test_key")

        assert result == "success"
        assert mock_redis.get.call_count == 2

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_exponential_backoff(self, connected_adapter_with_retry, mock_redis_classes):
        """Test exponential backoff in retry logic."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, mock_conn_err, _, _, _ = mock_redis_classes

        # All calls fail to test backoff
        mock_redis.get.side_effect = mock_conn_err("Connection error")

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(OperationFailedError):
                adapter.get("test_key")

        # Verify exponential backoff: 0.01, 0.02
        expected_delays = [0.01, 0.02]
        actual_delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_redis_error_no_retry(self, connected_adapter_with_retry, mock_redis_classes):
        """Test that RedisError (non-connection) doesn't trigger retry."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, _, _, mock_redis_err, _ = mock_redis_classes

        # Non-connection Redis error should not retry
        mock_redis.get.side_effect = mock_redis_err("Invalid command")

        with pytest.raises(OperationFailedError):
            adapter.get("test_key")

        # Should only try once (no retries for RedisError)
        assert mock_redis.get.call_count == 1

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_operation_without_connection(self, adapter):
        """Test operations when not connected to Redis."""
        with pytest.raises(AdapterNotConnectedError):
            adapter.get("some_key")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_safe_operation_redis_error(self, connected_adapter_with_retry, mock_redis_classes):
        """Test _safe_operation with a generic RedisError."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, _, _, redis_err, _ = mock_redis_classes

        mock_redis.get.side_effect = redis_err("Generic Redis Error")

        with pytest.raises(OperationFailedError):
            adapter.get("test_key")

        assert mock_redis.get.call_count == 1

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_safe_operation_connection_error_with_default(
        self, connected_adapter_with_retry, mock_redis_classes
    ):
        """Test _safe_operation with a ConnectionError and a default value."""
        adapter, mock_redis = connected_adapter_with_retry
        _, _, conn_err, _, _, _ = mock_redis_classes

        mock_redis.get.side_effect = conn_err("Connection Error")

        result = adapter.get("test_key", default="default_value")

        assert result == "default_value"
        assert mock_redis.get.call_count == 3

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_safe_operation_no_retries(self, adapter, mock_redis_classes):
        """Test _safe_operation when max_retries is 0."""
        mock_redis, _, conn_err, _, _, _ = mock_redis_classes
        mock_redis_instance = mock_redis.return_value

        adapter._config.max_retries = 0
        adapter.connect()  # Connect the adapter to ensure _redis is not None

        mock_redis_instance.get.side_effect = conn_err("Connection Error")

        with pytest.raises(OperationFailedError):
            adapter.get("test_key")

        assert mock_redis_instance.get.call_count == 0
