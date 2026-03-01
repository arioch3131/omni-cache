"""
Unit tests for the HealthMonitor class.
"""

import logging
import threading
import time
from unittest.mock import Mock, call, patch

import pytest

from omni_cache.core.adapter_registry import AdapterRegistry, ManagerConfig
from omni_cache.core.health_monitoring import HealthMonitor


class TestHealthMonitor:
    """Test cases for HealthMonitor class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock ManagerConfig for testing."""
        config = Mock(spec=ManagerConfig)
        config.health_check_interval = 1.0
        return config

    @pytest.fixture
    def mock_registry(self):
        """Create a mock AdapterRegistry for testing."""
        return Mock(spec=AdapterRegistry)

    @pytest.fixture
    def mock_logger(self):
        """Create a mock logger for testing."""
        return Mock(spec=logging.Logger)

    @pytest.fixture
    def health_monitor(self, mock_config, mock_registry, mock_logger):
        """Create a HealthMonitor instance for testing."""
        return HealthMonitor(mock_config, mock_registry, mock_logger)

    def test_init_creates_correct_attributes(self, mock_config, mock_registry, mock_logger):
        """Test that HealthMonitor initializes with correct attributes."""
        monitor = HealthMonitor(mock_config, mock_registry, mock_logger)

        assert monitor._config is mock_config
        assert monitor._registry is mock_registry
        assert monitor._logger is mock_logger
        assert monitor._health_monitor_thread is None
        assert isinstance(monitor._stop_health_monitor, threading.Event)
        assert not monitor._stop_health_monitor.is_set()

    def test_start_creates_and_starts_thread(self, health_monitor):
        """Test that start() creates and starts a monitoring thread."""
        health_monitor.start()

        # Verify thread was created and started
        assert health_monitor._health_monitor_thread is not None
        assert health_monitor._health_monitor_thread.is_alive()
        assert health_monitor._health_monitor_thread.name == "CacheManager-HealthMonitor"
        assert health_monitor._health_monitor_thread.daemon is True

        # Verify logger was called
        health_monitor._logger.info.assert_called_once_with("Started health monitoring")

        # Verify stop event was cleared
        assert not health_monitor._stop_health_monitor.is_set()

        # Clean up
        health_monitor.stop()

    def test_start_does_not_create_new_thread_if_already_running(self, health_monitor):
        """Test that start() doesn't create a new thread if one is already running."""
        # Start first time
        health_monitor.start()
        first_thread = health_monitor._health_monitor_thread

        # Start second time
        health_monitor.start()
        second_thread = health_monitor._health_monitor_thread

        # Should be the same thread
        assert first_thread is second_thread
        assert health_monitor._logger.info.call_count == 1

        # Clean up
        health_monitor.stop()

    def test_start_creates_new_thread_if_previous_thread_died(self, health_monitor):
        """Test that start() creates a new thread if the previous one died."""
        # Mock a dead thread
        dead_thread = Mock()
        dead_thread.is_alive.return_value = False
        health_monitor._health_monitor_thread = dead_thread

        # Start should create a new thread
        health_monitor.start()

        assert health_monitor._health_monitor_thread is not dead_thread
        assert health_monitor._health_monitor_thread.is_alive()
        health_monitor._logger.info.assert_called_once_with("Started health monitoring")

        # Clean up
        health_monitor.stop()

    def test_stop_stops_running_thread(self, health_monitor):
        """Test that stop() properly stops a running thread."""
        # Start monitoring
        health_monitor.start()
        thread = health_monitor._health_monitor_thread

        # Stop monitoring
        health_monitor.stop()

        # Verify stop event was set and thread joined
        assert health_monitor._stop_health_monitor.is_set()
        assert not thread.is_alive()
        health_monitor._logger.info.assert_called_with("Stopped health monitoring")

    def test_stop_does_nothing_if_no_thread(self, health_monitor):
        """Test that stop() does nothing if no thread is running."""
        # Call stop without starting
        health_monitor.stop()

        # Should not crash and should not log
        health_monitor._logger.info.assert_not_called()

    def test_stop_does_nothing_if_thread_not_alive(self, health_monitor):
        """Test that stop() does nothing if thread is not alive."""
        # Mock a dead thread
        dead_thread = Mock()
        dead_thread.is_alive.return_value = False
        health_monitor._health_monitor_thread = dead_thread

        # Stop should do nothing
        health_monitor.stop()

        health_monitor._logger.info.assert_not_called()

    @patch("threading.Event.wait")
    def test_health_monitor_loop_checks_all_adapters(self, mock_wait, health_monitor):
        """Test that the health monitor loop checks all registered adapters."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        # Mock adapters
        healthy_adapter = Mock()
        healthy_adapter.health_check.return_value = True

        unhealthy_adapter = Mock()
        unhealthy_adapter.health_check.return_value = False

        health_monitor._registry.list_all.return_value = ["healthy", "unhealthy"]
        health_monitor._registry.get.side_effect = lambda name: {
            "healthy": healthy_adapter,
            "unhealthy": unhealthy_adapter,
        }.get(name)

        # Run the loop
        health_monitor._health_monitor_loop()

        # Verify all adapters were checked
        health_monitor._registry.list_all.assert_called()
        health_monitor._registry.get.assert_has_calls([call("healthy"), call("unhealthy")])
        healthy_adapter.health_check.assert_called_once()
        unhealthy_adapter.health_check.assert_called_once()

        # Verify warning was logged for unhealthy adapter
        health_monitor._logger.warning.assert_called_once_with(
            "Unhealthy adapters detected: ['unhealthy']"
        )

    @patch("threading.Event.wait")
    def test_health_monitor_loop_handles_missing_adapter(self, mock_wait, health_monitor):
        """Test that the health monitor loop handles missing adapters gracefully."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        health_monitor._registry.list_all.return_value = ["missing"]
        health_monitor._registry.get.return_value = None  # Adapter not found

        # Run the loop - should not crash
        health_monitor._health_monitor_loop()

        # Should not log any warnings since no unhealthy adapters were found
        health_monitor._logger.warning.assert_not_called()

    @patch("threading.Event.wait")
    def test_health_monitor_loop_handles_all_healthy_adapters(self, mock_wait, health_monitor):
        """Test that the health monitor loop handles all healthy adapters."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        # Mock healthy adapter
        healthy_adapter = Mock()
        healthy_adapter.health_check.return_value = True

        health_monitor._registry.list_all.return_value = ["healthy"]
        health_monitor._registry.get.return_value = healthy_adapter

        # Run the loop
        health_monitor._health_monitor_loop()

        # Should not log any warnings since all adapters are healthy
        health_monitor._logger.warning.assert_not_called()

    @patch("threading.Event.wait")
    def test_health_monitor_loop_handles_exceptions(self, mock_wait, health_monitor):
        """Test that the health monitor loop handles exceptions gracefully."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        # Make list_all raise an exception
        test_error = RuntimeError("Test error")
        health_monitor._registry.list_all.side_effect = test_error

        # Run the loop - should not crash
        health_monitor._health_monitor_loop()

        # Should log the error - verify the call was made with the actual exception instance
        health_monitor._logger.error.assert_called_once_with(
            "Health monitoring error: %s", test_error
        )

    @patch("threading.Event.wait")
    def test_health_monitor_loop_uses_correct_interval(self, mock_wait, health_monitor):
        """Test that the health monitor loop uses the correct check interval."""
        # Setup mocks
        mock_wait.return_value = True  # Stop immediately

        # Run the loop
        health_monitor._health_monitor_loop()

        # Verify wait was called with correct interval
        mock_wait.assert_called_once_with(health_monitor._config.health_check_interval)

    @patch("threading.Event.wait")
    def test_health_monitor_loop_multiple_unhealthy_adapters(self, mock_wait, health_monitor):
        """Test that the health monitor loop reports multiple unhealthy adapters."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        # Mock multiple unhealthy adapters
        unhealthy1 = Mock()
        unhealthy1.health_check.return_value = False

        unhealthy2 = Mock()
        unhealthy2.health_check.return_value = False

        healthy = Mock()
        healthy.health_check.return_value = True

        health_monitor._registry.list_all.return_value = ["unhealthy1", "healthy", "unhealthy2"]
        health_monitor._registry.get.side_effect = lambda name: {
            "unhealthy1": unhealthy1,
            "healthy": healthy,
            "unhealthy2": unhealthy2,
        }.get(name)

        # Run the loop
        health_monitor._health_monitor_loop()

        # Verify warning was logged with all unhealthy adapters
        health_monitor._logger.warning.assert_called_once_with(
            "Unhealthy adapters detected: ['unhealthy1', 'unhealthy2']"
        )

    @patch("threading.Event.wait")
    def test_health_monitor_loop_adapter_health_check_exception(self, mock_wait, health_monitor):
        """Test that the health monitor loop handles adapter health check exceptions."""
        # Setup mocks
        mock_wait.side_effect = [False, True]  # Run once, then stop

        # Mock adapter that raises exception during health check
        test_error = RuntimeError("Health check failed")
        problematic_adapter = Mock()
        problematic_adapter.health_check.side_effect = test_error

        health_monitor._registry.list_all.return_value = ["problematic"]
        health_monitor._registry.get.return_value = problematic_adapter

        # Run the loop
        health_monitor._health_monitor_loop()

        # Should log the exception - verify the call was made with the actual exception instance
        health_monitor._logger.error.assert_called_once_with(
            "Health monitoring error: %s", test_error
        )

    def test_integration_start_stop_cycle(self, health_monitor):
        """Test a complete start/stop cycle integration."""
        # Start monitoring
        health_monitor.start()

        # Verify it's running
        assert health_monitor._health_monitor_thread.is_alive()

        # Let it run briefly
        time.sleep(0.1)

        # Stop monitoring
        health_monitor.stop()

        # Verify it's stopped
        assert not health_monitor._health_monitor_thread.is_alive()

        # Verify logs
        expected_calls = [call("Started health monitoring"), call("Stopped health monitoring")]
        health_monitor._logger.info.assert_has_calls(expected_calls)

    def test_multiple_start_stop_cycles(self, health_monitor):
        """Test multiple start/stop cycles."""
        for _ in range(3):
            health_monitor.start()
            assert health_monitor._health_monitor_thread.is_alive()

            health_monitor.stop()
            assert not health_monitor._health_monitor_thread.is_alive()

    @patch("threading.Thread.join")
    def test_stop_with_join_timeout(self, mock_join, health_monitor):
        """Test that stop() calls join with correct timeout."""
        # Start monitoring
        health_monitor.start()

        # Stop monitoring
        health_monitor.stop()

        # Verify join was called with correct timeout
        mock_join.assert_called_once_with(timeout=1.0)
