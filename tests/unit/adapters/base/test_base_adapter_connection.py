"""
Tests for the connection management of the BaseAdapter.
"""

import threading
import time
from unittest.mock import ANY, patch

import pytest

from omni_cache.adapters.base.base import (
    ConnectionState,
)


class TestBaseAdapterConnection:
    """Tests for the BaseAdapter connection management."""

    def test_connect_success(self, mock_base_adapter):
        """Test successful connection."""
        mock_base_adapter.connect_should_succeed = True

        result = mock_base_adapter.connect()

        assert result is True
        assert mock_base_adapter.is_connected() is True
        assert mock_base_adapter._state == ConnectionState.CONNECTED
        assert mock_base_adapter._connection_time is not None
        assert mock_base_adapter.connect_called is True

    def test_connect_failure(self, mock_base_adapter):
        """Test failed connection."""
        mock_base_adapter.connect_should_succeed = False

        result = mock_base_adapter.connect()

        assert result is False
        assert mock_base_adapter.is_connected() is False
        assert mock_base_adapter._state == ConnectionState.ERROR
        assert mock_base_adapter._connection_time is None
        assert mock_base_adapter.connect_called is True

    def test_connect_already_connected(self, mock_base_adapter):
        """Test connecting when already connected."""
        # First connection
        mock_base_adapter.connect()
        assert mock_base_adapter.is_connected() is True

        # Reset call counter
        mock_base_adapter.connect_called = False

        # Second connection attempt
        result = mock_base_adapter.connect()

        assert result is True
        assert mock_base_adapter.connect_called is False  # Should not call _do_connect again

    def test_connect_already_connecting(self, mock_base_adapter):
        """Test connecting when connection is in progress."""
        # Simulate slow connection
        mock_base_adapter.connect_delay = 0.1

        # Start first connection in thread
        def slow_connect():
            mock_base_adapter.connect()

        thread = threading.Thread(target=slow_connect)
        thread.start()

        # Wait a bit for connection to start
        time.sleep(0.05)

        # Try to connect again while first is in progress
        result = mock_base_adapter.connect()

        assert result is False

        # Wait for first connection to complete
        thread.join()

    def test_connect_with_exception(self, mock_base_adapter):
        """Test connection with exception in _do_connect."""

        def failing_connect():
            raise RuntimeError("Connection failed")

        mock_base_adapter._do_connect = failing_connect

        result = mock_base_adapter.connect()

        assert result is False
        assert mock_base_adapter._state == ConnectionState.ERROR
        assert mock_base_adapter._last_error is not None
        assert isinstance(mock_base_adapter._last_error, RuntimeError)

    def test_connect_time_exception(self, mock_base_adapter):
        """Test connect method when time.time() raises an exception."""
        with patch("time.time", side_effect=Exception("Time error")):
            with patch.object(mock_base_adapter._logger, "error") as mock_error:
                result = mock_base_adapter.connect()

                assert result is False
                assert mock_base_adapter._state == ConnectionState.ERROR
                assert mock_base_adapter._last_error is not None
                assert isinstance(mock_base_adapter._last_error, Exception)
                mock_error.assert_called_once_with("Connection failed with exception: %s", ANY)

    def test_disconnect_success(self, mock_base_adapter):
        """Test successful disconnection."""
        # First connect
        mock_base_adapter.connect()
        assert mock_base_adapter.is_connected() is True

        # Then disconnect
        result = mock_base_adapter.disconnect()

        assert result is True
        assert mock_base_adapter.is_connected() is False
        assert mock_base_adapter._state == ConnectionState.DISCONNECTED
        assert mock_base_adapter._connection_time is None
        assert mock_base_adapter.disconnect_called is True

    def test_disconnect_not_connected(self, mock_base_adapter):
        """Test disconnecting when not connected."""
        assert mock_base_adapter.is_connected() is False

        result = mock_base_adapter.disconnect()

        assert result is True
        assert mock_base_adapter.disconnect_called is False  # Should not call _do_disconnect

    def test_disconnect_failure(self, mock_base_adapter):
        """Test failed disconnection."""
        # First connect
        mock_base_adapter.connect()

        # Set disconnect to fail
        mock_base_adapter.disconnect_should_succeed = False

        result = mock_base_adapter.disconnect()

        assert result is False
        assert mock_base_adapter._state == ConnectionState.DISCONNECTED  # State changes anyway
        assert mock_base_adapter.disconnect_called is True

    def test_disconnect_already_disconnecting(self, mock_base_adapter):
        """Test disconnecting when disconnection is already in progress."""
        mock_base_adapter.connect()
        mock_base_adapter._state = ConnectionState.DISCONNECTING  # Manually set state

        with patch.object(mock_base_adapter._logger, "warning") as mock_warning:
            result = mock_base_adapter.disconnect()

            assert result is False
            mock_warning.assert_called_once_with("Disconnection already in progress")
            assert (
                mock_base_adapter.disconnect_called is False
            )  # _do_disconnect should not be called

    def test_disconnect_with_exception(self, mock_base_adapter):
        """Test disconnection with exception in _do_disconnect."""
        mock_base_adapter.connect()

        def failing_disconnect():
            raise RuntimeError("Disconnection failed")

        mock_base_adapter._do_disconnect = failing_disconnect

        with patch.object(mock_base_adapter._logger, "error") as mock_error:
            result = mock_base_adapter.disconnect()

            assert result is False
            assert mock_base_adapter._state == ConnectionState.ERROR
            assert mock_base_adapter._last_error is not None
            assert isinstance(mock_base_adapter._last_error, RuntimeError)
            mock_error.assert_called_once_with(
                "Disconnection failed with exception: %s", mock_base_adapter._last_error
            )

    def test_enter_raises_runtime_error(self, mock_base_adapter):
        """Test __enter__ raises RuntimeError if connection fails."""
        mock_base_adapter.connect_should_succeed = False  # Ensure connect fails

        with pytest.raises(
            RuntimeError, match=f"Failed to connect to {mock_base_adapter._config.backend}"
        ):
            with mock_base_adapter:
                pass  # This block should not be entered if connection fails

    def test_connect_with_retry(self, mock_base_adapter):
        """Test connection with retry logic."""
        mock_base_adapter._config.max_retries = 2
        mock_base_adapter._config.retry_delay = 0.01

        call_count = 0
        original_do_connect = mock_base_adapter._do_connect

        def failing_then_succeeding_connect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return False
            return original_do_connect()

        mock_base_adapter._do_connect = failing_then_succeeding_connect

        result = mock_base_adapter.connect()

        assert result is True
        assert call_count == 3  # Failed twice, succeeded on third try
        assert mock_base_adapter.is_connected() is True

    def test_connect_retry_exhausted(self, mock_base_adapter):
        """Test connection when all retries are exhausted."""
        mock_base_adapter._config.max_retries = 2
        mock_base_adapter._config.retry_delay = 0.01
        mock_base_adapter.connect_should_succeed = False

        result = mock_base_adapter.connect()

        assert result is False
        assert mock_base_adapter._state == ConnectionState.ERROR

    def test_health_check_success(self, mock_base_adapter):
        """Test successful health check."""
        mock_base_adapter.connect()
        mock_base_adapter.health_check_should_succeed = True

        result = mock_base_adapter.health_check()

        assert result is True
        assert mock_base_adapter.health_check_called is True
        assert mock_base_adapter._health_check_result is True
        assert mock_base_adapter._last_health_check is not None

    def test_health_check_failure(self, mock_base_adapter):
        """Test failed health check."""
        mock_base_adapter.connect()
        mock_base_adapter.health_check_should_succeed = False

        result = mock_base_adapter.health_check()

        assert result is False
        assert mock_base_adapter.health_check_called is True
        assert mock_base_adapter._health_check_result is False

    def test_health_check_not_connected(self, mock_base_adapter):
        """Test health check when not connected."""
        assert mock_base_adapter.is_connected() is False

        result = mock_base_adapter.health_check()

        assert result is False
        assert mock_base_adapter.health_check_called is False  # Should not call _do_health_check
        assert mock_base_adapter._health_check_result is False

    def test_health_check_cached_result(self, mock_base_adapter):
        """Test health check with cached result."""
        mock_base_adapter.connect()
        mock_base_adapter._config.health_check_interval = 1.0

        # First health check
        result1 = mock_base_adapter.health_check()
        assert result1 is True

        # Reset call counter
        mock_base_adapter.health_check_called = False

        # Second health check (should use cached result)
        result2 = mock_base_adapter.health_check()

        assert result2 is True
        assert mock_base_adapter.health_check_called is False  # Should not call _do_health_check

    def test_health_check_with_exception(self, mock_base_adapter):
        """Test health check with exception."""
        mock_base_adapter.connect()

        def failing_health_check():
            raise RuntimeError("Health check failed")

        mock_base_adapter._do_health_check = failing_health_check

        result = mock_base_adapter.health_check()

        assert result is False
        assert mock_base_adapter._health_check_result is False
