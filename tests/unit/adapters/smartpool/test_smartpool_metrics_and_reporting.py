"""
Unit tests for SmartPoolAdapter metrics, reporting, and dashboard functionalities.
"""

import logging
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter


# Fixtures for testing
@pytest.fixture
def mock_factory_function():
    """Mock factory function for creating test objects."""
    return Mock(return_value=Mock())


@pytest.fixture
def mock_smart_object_manager():
    """Mock SmartObjectManager for unit testing."""
    mock_manager = MagicMock()
    mock_manager.acquire.return_value = (
        Mock(name="mock_id"),
        Mock(name="mock_key"),
        Mock(name="mock_obj"),
    )
    # Corrected: Mock get_basic_stats instead of get_stats
    mock_manager.get_basic_stats.return_value = {
        "pooled_objects": 2,
        "active_objects": 1,
        "total_managed_objects": 3,
        "counters": {
            "hits": 10,
            "misses": 2,
            "creates": 3,
            "reuses": 7,
            "destroys": 0,
            "borrows": 11,
            "releases": 10,
        },
    }
    mock_manager.get_health_status.return_value = {"status": "healthy", "issues": []}
    mock_manager.shutdown.return_value = None
    mock_manager.enable_auto_tuning.return_value = None

    # Mock performance_metrics with expected values for success tests
    mock_perf_metrics = MagicMock()
    mock_perf_metrics.create_snapshot.return_value = Mock(
        timestamp=Mock(isoformat=Mock(return_value="2025-01-01T12:00:00")),
        total_acquisitions=100,
        hit_rate=0.8,
        avg_acquisition_time_ms=10.0,
        min_acquisition_time_ms=1.0,
        max_acquisition_time_ms=20.0,
        p50_acquisition_time_ms=9.0,
        p95_acquisition_time_ms=18.0,
        p99_acquisition_time_ms=19.0,
        avg_lock_wait_time_ms=0.5,
        max_lock_wait_time_ms=2.0,
        lock_contention_rate=0.05,
        acquisitions_per_second=10.0,
        peak_concurrent_acquisitions=5,
        top_keys_by_usage=[("key1", 50)],
        slowest_keys=[("key2", 20.0)],
    )
    mock_perf_metrics.get_performance_report.return_value = {
        "trends": {"trend1": "data1"},
        "alerts": [{"level": "warning", "message": "High latency"}],
        "recommendations": ["Optimize queries"],
    }
    mock_manager.performance_metrics = mock_perf_metrics
    return mock_manager


@pytest.fixture
def basic_config_dict(mock_factory_function):
    """Basic configuration dictionary for testing."""
    return {
        "factory_function": mock_factory_function,
        "initial_size": 2,
        "max_size": 10,
        "min_size": 1,
        "enable_stats": True,
    }


@pytest.fixture
def smartpool_config(mock_factory_function):
    """SmartPoolAdapterConfig instance for testing."""
    return SmartPoolAdapterConfig(
        factory_function=mock_factory_function,
        initial_size=2,
        max_size=10,
        min_size=1,
        max_size_per_key=2,
        enable_stats=True,
    )


class TestSmartPoolMetricsAndReporting:
    """Test suite for SmartPoolAdapter metrics, reporting, and dashboard functionalities."""

    def test_get_performance_metrics_success(self, smartpool_config, mock_smart_object_manager):
        """Test successful retrieval of performance metrics."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            metrics = adapter.get_performance_metrics()

            assert "error" not in metrics
            assert "current_snapshot" in metrics
            assert "trends" in metrics
            assert "alerts" in metrics
            assert "recommendations" in metrics

            # Verify some key metrics
            assert metrics["current_snapshot"]["total_acquisitions"] == 100
            assert metrics["current_snapshot"]["hit_rate"] == 0.8
            assert metrics["current_snapshot"]["timing_metrics"]["avg_acquisition_time_ms"] == 10.0
            assert metrics["trends"]["trend1"] == "data1"
            assert metrics["alerts"][0]["message"] == "High latency"
            assert metrics["recommendations"][0] == "Optimize queries"

            mock_smart_object_manager.performance_metrics.create_snapshot.assert_called_once()
            mock_smart_object_manager.performance_metrics.get_performance_report.assert_called_once()

    def test_get_performance_metrics_not_enabled(self, smartpool_config, mock_smart_object_manager):
        """Test get_performance_metrics when performance metrics are not enabled."""
        # Scenario 1: pool_manager does not have performance_metrics attribute
        del mock_smart_object_manager.performance_metrics

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            metrics = adapter.get_performance_metrics()
            assert metrics == {"error": "Performance metrics not enabled"}

        # Scenario 2: pool_manager.performance_metrics is None
        mock_smart_object_manager.performance_metrics = None

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            metrics = adapter.get_performance_metrics()
            assert metrics == {"error": "Performance metrics not enabled"}

    def test_get_dashboard_summary_success(self, smartpool_config, mock_smart_object_manager):
        """Test successful retrieval of dashboard summary."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            summary = adapter.get_dashboard_summary()

            assert "status" in summary
            assert "metrics" in summary
            assert "performance" in summary
            assert "alerts" in summary
            assert "config" in summary

            assert summary["status"] == "healthy"
            assert summary["metrics"]["pooled_objects"] == 2
            assert summary["performance"]["avg_response_time_ms"] == 10.0
            assert summary["alerts"]["has_warnings"] is True
            assert summary["alerts"]["active_count"] == 1
            assert summary["config"]["max_size"] == 10

    def test_get_dashboard_summary_disconnected(self, smartpool_config):
        """Test get_dashboard_summary when adapter is disconnected."""
        adapter = SmartPoolAdapter(smartpool_config)
        summary = adapter.get_dashboard_summary()

        assert summary["error"] == "Pool not initialized"
        assert summary["status"] == "disconnected"

    def test_get_dashboard_summary_performance_metrics_error(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_dashboard_summary when performance metrics retrieval fails."""
        mock_smart_object_manager.performance_metrics.create_snapshot.side_effect = Exception(
            "Perf error"
        )

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            summary = adapter.get_dashboard_summary()

            assert summary["status"] == "error"
            assert summary["alerts"]["has_errors"] is True

    def test_get_dashboard_summary_general_exception(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_dashboard_summary when a general exception occurs."""
        mock_smart_object_manager.get_basic_stats.side_effect = Exception("General error")

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            summary = adapter.get_dashboard_summary()

            assert summary["status"] == "error"
            assert summary["alerts"]["has_errors"] is True

    def test_get_dashboard_summary_backend_info_exception(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_dashboard_summary handles exceptions during backend info retrieval."""
        # Make get_backend_info raise an exception
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartPoolAdapter.get_backend_info",
            side_effect=Exception("Backend info error"),
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            summary = adapter.get_dashboard_summary()

            assert summary["status"] == "error"
            assert summary["error"] == "Backend info error"
            assert summary["alerts"]["has_errors"] is True

    def test_get_dashboard_summary_no_recommendations(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_dashboard_summary when no recommendations are present in performance metrics."""
        # Configure mock_perf_metrics to not have a "recommendations" key
        with (
            patch(
                "omni_cache.adapters.smartpool.smartpool.SmartPoolAdapter.get_performance_metrics",
                return_value={
                    "trends": {"trend1": "data1"},
                    "alerts": [{"level": "warning", "message": "High latency"}],
                    # No "recommendations" key here
                },
            ),
            patch(
                "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
                return_value=mock_smart_object_manager,
            ),
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            summary = adapter.get_dashboard_summary()

            assert "recommendations" not in summary  # Ensure recommendations key is not added
            assert summary["status"] == "healthy"  # Assuming no other issues

    def test_get_backend_info_no_manager_attribute(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test get_backend_info when _pool.manager attribute is missing."""
        # Ensure _pool exists but does not have a 'manager' attribute
        if hasattr(mock_smart_object_manager, "manager"):
            del mock_smart_object_manager.manager

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("DEBUG"):
                backend_info = adapter.get_backend_info()

                # Assert that memory_manager_report is not in the result
                assert "memory_manager_report" not in backend_info
                # Ensure no error status is set due to this missing attribute
                assert "error" not in backend_info
                assert "performance_enrichment_error" not in backend_info

    def test_get_backend_info_manager_get_performance_report_exception(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test get_backend_info when _pool.manager.get_performance_report raises an exception."""
        # Set logger level to DEBUG for this test
        logging.getLogger("omni_cache.adapters.smartpooladapter").setLevel(logging.DEBUG)

        # Ensure _pool has a manager attribute
        mock_smart_object_manager.manager = MagicMock()
        # Make get_performance_report raise an exception
        mock_smart_object_manager.manager.get_performance_report.side_effect = RuntimeError(
            "Manager report error"
        )

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            mock_debug = MagicMock()
            adapter._logger.debug = mock_debug

            backend_info = adapter.get_backend_info()

            # Assert that memory_manager_report is not in the result
            assert "memory_manager_report" not in backend_info
            # Assert that the debug message is logged with the correct exception type and message
            mock_debug.assert_called_once()
            args, kwargs = mock_debug.call_args
            assert args[0] == "Memory manager report not available: %s"
            assert isinstance(args[1], RuntimeError)
            assert str(args[1]) == "Manager report error"

    def test_get_backend_info_exception_in_outer_try_block(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test get_backend_info when get_performance_metrics fails in outer try block."""
        # Make get_performance_metrics raise an exception
        with patch.object(
            SmartPoolAdapter,
            "get_performance_metrics",
            side_effect=RuntimeError("Simulated outer error"),
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("ERROR"):
                backend_info = adapter.get_backend_info()

                # Assert that performance_enrichment_error is set
                assert "performance_enrichment_error" in backend_info
                assert backend_info["performance_enrichment_error"] == "Simulated outer error"
                # Assert that the error message is logged
                assert (
                    "Error enriching backend info with performance metrics: Simulated outer error"
                    in caplog.text
                )

    def test_get_health_report_success(self, smartpool_config, mock_smart_object_manager):
        """Test successful retrieval of health report."""
        # Configure mocks for a healthy scenario
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 10
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = 5
        smartpool_config.max_size = 10  # Ensure pool utilization is moderate

        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 10.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = []
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "healthy"
            assert report["issues"] == []
            assert report["warnings"] == []
            assert report["recommendations"] == []
            assert report["summary"]["total_issues"] == 0
            assert report["summary"]["total_warnings"] == 0
            assert report["summary"]["total_recommendations"] == 0

    def test_get_health_report_disconnected(self, smartpool_config):
        """Test get_health_report when adapter is disconnected."""
        adapter = SmartPoolAdapter(smartpool_config)
        report = adapter.get_health_report()

        assert report["status"] == "disconnected"
        assert report["issues"] == ["Pool not initialized"]

    def test_get_health_report_low_hit_rate(self, smartpool_config, mock_smart_object_manager):
        """Test get_health_report with low hit rate."""
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 1
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 10
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []  # Clear recommendations for this test

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "critical"
            assert "Low hit rate" in report["issues"][0]
            assert (
                "Consider increasing pool size or reviewing object reuse patterns"
                in report["recommendations"][0]
            )

    def test_get_health_report_high_avg_response_time(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with high average response time."""
        # Configure mocks for this scenario
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 10
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = 1
        smartpool_config.max_size = 10

        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 60.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = []
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "warning"
            assert "High average response time" in report["warnings"][0]
            assert (
                "Investigate object creation time or pool contention"
                in report["recommendations"][0]
            )

    def test_get_health_report_high_lock_contention(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with high lock contention."""
        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.lock_contention_rate = 0.2
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = (
            5  # Ensure moderate utilization
        )
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = ["Consider optimizing concurrent access patterns"]

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "warning"
            assert "High lock contention" in report["warnings"][0]
            assert "Consider optimizing concurrent access patterns" in report["recommendations"][0]

    def test_get_health_report_high_pool_utilization(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with high pool utilization."""
        # Configure mocks for this scenario
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 10
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = 9
        smartpool_config.max_size = 9  # Ensure high pool utilization (1.0)

        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 10.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = []
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "warning"
            assert "High pool utilization" in report["warnings"][0]
            assert "Consider increasing max_size" in report["recommendations"][0]

    def test_get_health_report_low_pool_utilization(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with low pool utilization."""
        # Configure mocks for this scenario
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 10
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = 0
        smartpool_config.max_size = 10

        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 10.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = []
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "warning"
            assert "Low pool utilization" in report["warnings"][0]
            assert "Consider decreasing initial_size or max_size" in report["recommendations"][0]

    def test_get_health_report_performance_alert_error(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with performance alert at error level."""
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = [{"level": "error", "message": "Critical performance issue"}]

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "critical"
            assert "Critical performance issue" in report["issues"][0]

    def test_get_health_report_performance_alert_warning(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with performance alert at warning level."""
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = [{"level": "warning", "message": "Minor performance issue"}]

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "warning"
            assert "Minor performance issue" in report["warnings"][0]

    def test_get_health_report_general_exception(self, smartpool_config, mock_smart_object_manager):
        """Test get_health_report when a general exception occurs."""
        # Configure mocks for this scenario
        mock_smart_object_manager.get_basic_stats.side_effect = Exception(
            "General error in health report"
        )

        # Ensure performance metrics don't cause issues in this test
        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 10.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = []
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "critical"
            assert "Failed to retrieve detailed stats" in report["issues"][0]

    def test_get_health_report_performance_metrics_error_path(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report when get_performance_metrics returns an error."""
        # Ensure basic stats are healthy so they don't interfere
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 100
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0

        # Mock get_performance_metrics to return an error
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartPoolAdapter.get_performance_metrics",
            return_value={"error": "Simulated performance metrics error"},
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "critical"

    def test_get_health_report_non_error_warning_alert(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report with an alert level that is not error or warning."""
        # Configure mocks for a healthy scenario with an info-level alert
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["hits"] = 10
        mock_smart_object_manager.get_basic_stats.return_value["counters"]["misses"] = 0
        mock_smart_object_manager.get_basic_stats.return_value["active_objects"] = 5
        smartpool_config.max_size = 10

        snapshot = mock_smart_object_manager.performance_metrics.create_snapshot.return_value
        snapshot.avg_acquisition_time_ms = 10.0
        snapshot.lock_contention_rate = 0.0
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "alerts"
        ] = [{"level": "info", "message": "Informational alert: Pool operating normally"}]
        mock_smart_object_manager.performance_metrics.get_performance_report.return_value[
            "recommendations"
        ] = []

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "healthy"
            assert report["issues"] == []
            assert report["warnings"] == []
            assert report["recommendations"] == []
            assert report["summary"]["total_issues"] == 0
            assert report["summary"]["total_warnings"] == 0
            assert report["summary"]["total_recommendations"] == 0

    def test_get_health_report_exception_in_try_block(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report when an exception is raised within its try block."""
        # Configure mocks for a healthy scenario
        mock_smart_object_manager.get_basic_stats.return_value = {
            "pooled_objects": 5,
            "active_objects": 2,
            "total_managed_objects": 7,
            "counters": {
                "hits": 100,
                "misses": 10,
                "creates": 10,
                "reuses": 90,
                "destroys": 0,
                "borrows": 100,
                "releases": 100,
            },
        }
        mock_smart_object_manager.get_health_status.return_value = {
            "status": "healthy",
            "issues": [],
        }
        smartpool_config.max_size = 10

        # Mock get_detailed_smartpool_stats to raise an exception
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartPoolAdapter.get_detailed_smartpool_stats",
            side_effect=Exception("Simulated error in detailed stats retrieval"),
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            report = adapter.get_health_report()

            assert report["status"] == "error"
            assert "Failed to generate health report" in report["issues"][0]
            assert report["warnings"] == []
            assert report["recommendations"] == []

    def test_get_health_report_no_perf_metrics_error_or_recommendations(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test get_health_report when perf metrics has no error/recommendations keys."""
        # Configure mocks for a healthy scenario
        # The mock_smart_object_manager fixture already provides a default healthy basic_stats
        # We will ensure the adapter uses this mock.

        # Mock get_performance_metrics without 'error'/'recommendations' keys.
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            # Explicitly set the return value for get_basic_stats on the adapter's pool
            adapter._pool.get_basic_stats.return_value = {
                "pooled_objects": 5,
                "active_objects": 2,
                "total_managed_objects": 7,
                "counters": {
                    "hits": 100,
                    "misses": 10,
                    "creates": 10,
                    "reuses": 90,
                    "destroys": 0,
                    "borrows": 100,
                    "releases": 100,
                },
            }
            adapter._pool.get_health_status.return_value = {"status": "healthy", "issues": []}

            # Patch get_performance_metrics on the adapter instance
            with patch.object(
                adapter,
                "get_performance_metrics",
                return_value={
                    "current_snapshot": {
                        "timestamp": "2025-01-01T12:00:00",
                        "total_acquisitions": 100,
                        "hit_rate": 0.8,
                        "timing_metrics": {
                            "avg_acquisition_time_ms": 10.0,
                            "min_acquisition_time_ms": 1.0,
                            "max_acquisition_time_ms": 20.0,
                            "p50_acquisition_time_ms": 9.0,
                            "p95_acquisition_time_ms": 18.0,
                            "p99_acquisition_time_ms": 19.0,
                        },
                        "contention_metrics": {
                            "avg_lock_wait_time_ms": 0.5,
                            "max_lock_wait_time_ms": 2.0,
                            "lock_contention_rate": 0.05,
                        },
                        "throughput_metrics": {
                            "acquisitions_per_second": 10.0,
                            "peak_concurrent_acquisitions": 5,
                        },
                        "key_metrics": {
                            "top_keys_by_usage": [("key1", 50)],
                            "slowest_keys": [("key2", 20.0)],
                        },
                    },
                    "trends": {"trend1": "data1"},
                    "alerts": [],  # No alerts for this specific test
                },
            ):
                report = adapter.get_health_report()

                assert report["status"] == "healthy"
                assert report["issues"] == []
                assert report["warnings"] == []
                assert (
                    report["recommendations"] == []
                )  # Should be empty as 'recommendations' key is missing from perf_metrics
                assert report["summary"]["total_issues"] == 0
                assert report["summary"]["total_warnings"] == 0
                assert report["summary"]["total_recommendations"] == 0

    def test_enable_performance_monitoring_enable_when_not_running(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test enabling performance monitoring when it's not already active."""
        # Ensure performance_metrics is None and enable_performance_metrics is mockable
        mock_smart_object_manager.performance_metrics = None
        mock_smart_object_manager.enable_performance_metrics = MagicMock()

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("INFO"):
                adapter.enable_performance_monitoring()

                # Assert that enable_performance_metrics was called on the underlying pool
                mock_smart_object_manager.enable_performance_metrics.assert_called_once()
                assert "Performance monitoring enabled successfully" in caplog.text

    def test_enable_performance_monitoring_enable_when_already_running(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test enabling performance monitoring when it's already running."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()
            adapter.performance_monitor = MagicMock()
            adapter.performance_monitor.is_running.return_value = True

            adapter.enable_performance_monitoring()

            adapter.performance_monitor.start.assert_not_called()
            adapter.performance_monitor.stop.assert_not_called()

    def test_enable_performance_monitoring_disable_when_already_stopped(
        self, smartpool_config, mock_smart_object_manager
    ):
        """Test disabling performance monitoring when it's already stopped."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()
            adapter.performance_monitor = MagicMock()
            adapter.performance_monitor.is_running.return_value = False

            adapter.enable_performance_monitoring()

            adapter.performance_monitor.stop.assert_not_called()
            adapter.performance_monitor.start.assert_not_called()

    def test_enable_performance_monitoring_no_pool_initialized(self, smartpool_config, caplog):
        """Test enabling performance monitoring when the pool is not initialized."""
        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=None,  # Simulate pool not initialized
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            # Do not call connect() to keep _pool as None

            with caplog.at_level("ERROR"):
                adapter.enable_performance_monitoring()
                assert "Cannot enable performance monitoring: pool not initialized" in caplog.text

    def test_enable_performance_monitoring_pool_does_not_support_dynamic_activation(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test enabling performance monitoring when pool does not support dynamic activation."""
        # Ensure performance_metrics is None and enable_performance_metrics is removed
        mock_smart_object_manager.performance_metrics = None
        if hasattr(mock_smart_object_manager, "enable_performance_metrics"):
            del mock_smart_object_manager.enable_performance_metrics

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("WARNING"):
                adapter.enable_performance_monitoring()
                assert "Pool does not support dynamic performance metrics activation" in caplog.text

    def test_enable_performance_monitoring_exception_in_try_block(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test exception handling within the try block of enable_performance_monitoring."""
        # Ensure performance_metrics is None to force a call to enable_performance_metrics()
        mock_smart_object_manager.performance_metrics = None
        # Make enable_performance_metrics() raise an exception
        mock_smart_object_manager.enable_performance_metrics = MagicMock(
            side_effect=RuntimeError("Simulated error")
        )

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("ERROR"):
                result = adapter.enable_performance_monitoring()
                assert result is False
                assert "Error enabling performance monitoring: Simulated error" in caplog.text

    def test_get_detailed_smartpool_stats_no_manager_attribute(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test get_detailed_smartpool_stats when _pool.manager attribute is missing."""
        # Ensure _pool exists and its 'manager' attribute is None
        mock_smart_object_manager.manager = None

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            with caplog.at_level("DEBUG"):
                detailed_stats = adapter.get_detailed_smartpool_stats()

                # Assert that memory_manager_report is an empty dictionary
                assert detailed_stats["memory_manager_report"] == {}

    def test_get_detailed_smartpool_stats_manager_get_performance_report_exception(
        self, smartpool_config, mock_smart_object_manager, caplog
    ):
        """Test get_detailed_smartpool_stats when manager report retrieval fails."""
        # Set logger level to DEBUG for this test
        logging.getLogger("omni_cache.adapters.smartpooladapter").setLevel(logging.DEBUG)

        # Ensure _pool has a manager attribute
        mock_smart_object_manager.manager = MagicMock()
        # Make get_performance_report raise an exception
        mock_smart_object_manager.manager.get_performance_report.side_effect = RuntimeError(
            "Manager report error"
        )

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
            return_value=mock_smart_object_manager,
        ):
            adapter = SmartPoolAdapter(smartpool_config)
            adapter.connect()

            mock_debug = MagicMock()
            adapter._logger.debug = mock_debug

            detailed_stats = adapter.get_detailed_smartpool_stats()

            # memory_manager_report should be empty because exception is caught.
            assert detailed_stats["memory_manager_report"] == {}
            # Assert that the debug message is logged with the correct exception type and message
            mock_debug.assert_called_once()
            args, _ = mock_debug.call_args
            assert args[0] == "Memory manager report not available: %s"
            assert isinstance(args[1], RuntimeError)
            assert str(args[1]) == "Manager report error"
