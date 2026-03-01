"""
Tests for the error handling of the BaseAdapter.
"""

import time
from unittest.mock import patch

import pytest

from omni_cache.adapters.base.base import (
    ConnectionState,
)
from omni_cache.core.exceptions.adapter_exceptions import AdapterNotConnectedError

from .conftest import MockBaseAdapter


class TestBaseAdapterErrorHandling:
    """Tests for error handling in BaseAdapter."""

    def test_connect_with_repeated_failures(self, adapter_config):
        """Test connection with repeated failures."""
        adapter = MockBaseAdapter(adapter_config)
        adapter._config.max_retries = 3
        adapter._config.retry_delay = 0.01
        adapter.connect_should_succeed = False

        start_time = time.time()
        result = adapter.connect()
        end_time = time.time()

        assert result is False
        assert adapter._state == ConnectionState.ERROR

        # Should have taken time for retries
        expected_min_time = 3 * 0.01  # 3 retries × 0.01s delay
        assert end_time - start_time >= expected_min_time

    def test_exception_in_configure(self, mock_base_adapter):
        """Test configuration update with exception."""
        # Mock setattr to raise exception
        original_setattr = setattr

        def failing_setattr(obj, name, value):
            if name == "max_retries":
                raise ValueError("Configuration error")
            return original_setattr(obj, name, value)

        with patch("builtins.setattr", side_effect=failing_setattr):
            result = mock_base_adapter.configure({"max_retries": 5})

        assert result is False

    def test_stats_update_with_disabled_stats(self, mock_base_adapter):
        """Test stats update when stats are disabled."""
        mock_base_adapter._config.enable_stats = False
        mock_base_adapter._cache_stats = None

        # Should not raise exception
        mock_base_adapter._update_cache_stats("get", success=True)

    def test_health_check_interval_edge_cases(self, mock_base_adapter):
        """Test health check with edge case intervals."""
        mock_base_adapter.connect()

        # Very long interval (should not cache)
        mock_base_adapter._config.health_check_interval = 0
        mock_base_adapter._last_health_check = time.time() - 1000

        result = mock_base_adapter.health_check()
        assert result is True
        assert mock_base_adapter.health_check_called is True

    def test_context_manager_exception_handling(self, mock_base_adapter):
        """Test context manager with exceptions in managed code."""
        exception_raised = False

        try:
            with mock_base_adapter as adapter:
                assert adapter.is_connected() is True
                raise ValueError("Test exception")
        except ValueError:
            exception_raised = True

        assert exception_raised is True
        assert mock_base_adapter.is_connected() is False  # Should still disconnect

    def test_safe_operation_not_connected(self, mock_base_adapter):
        """Test safe operation when not connected."""

        def test_operation():
            return "success"

        with pytest.raises(AdapterNotConnectedError):
            mock_base_adapter._safe_operation(test_operation, "test_op")

    def test_safe_operation_with_exception(self, mock_base_adapter):
        """Test safe operation with exception."""
        mock_base_adapter.connect()

        def failing_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            mock_base_adapter._safe_operation(failing_operation, "test_op")

        assert isinstance(mock_base_adapter._last_error, ValueError)

    def test_safe_operation_with_default(self, mock_base_adapter):
        """Test safe operation with default value on exception."""
        mock_base_adapter.connect()

        def failing_operation():
            raise ValueError("Test error")

        result = mock_base_adapter._safe_operation(
            failing_operation, "test_op", default="default_value"
        )

        assert result == "default_value"
