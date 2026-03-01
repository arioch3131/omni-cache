"""
Performance metrics tests for SmartPoolAdapter.

This module contains tests for performance monitoring, metrics collection,
and health assessment capabilities of the SmartPoolAdapter by running it
under load and inspecting the generated metrics.
"""

import time

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter


# Fixture for a test object
@pytest.fixture
def metrics_test_object():
    """A simple object for metrics testing."""

    class MetricsTestObject:
        def reset(self):
            pass

    return MetricsTestObject


# Fixture for adapter configuration with metrics enabled
@pytest.fixture
def metrics_enabled_config(metrics_test_object):
    """Configuration with performance metrics enabled."""
    return SmartPoolAdapterConfig(
        name="metrics_test_adapter",
        factory_function=metrics_test_object,
        initial_size=5,
        max_size=20,
        min_size=2,
        enable_performance_metrics=True,
        enable_stats=True,
        enable_auto_tuning=False,  # Disable for predictable test
    )


# Fixture for a connected adapter
@pytest.fixture
def connected_metrics_adapter(metrics_enabled_config):
    """A connected SmartPoolAdapter with metrics enabled."""
    adapter = SmartPoolAdapter(metrics_enabled_config)
    adapter.connect()
    # Run some initial load to generate metrics
    for _ in range(100):
        with adapter.borrow():
            time.sleep(0.001)
    yield adapter
    adapter.disconnect()


class TestSmartPoolAdapterMetricsRealUsage:
    """Test SmartPoolAdapter performance metrics by generating real load."""

    def test_get_performance_metrics_after_load(self, connected_metrics_adapter):
        """Test get_performance_metrics returns valid data after load."""
        metrics = connected_metrics_adapter.get_performance_metrics()

        assert "error" not in metrics
        assert "current_snapshot" in metrics
        assert "trends" in metrics
        assert "alerts" in metrics
        assert "recommendations" in metrics

        snapshot = metrics["current_snapshot"]
        assert snapshot["total_acquisitions"] >= 100
        assert snapshot["hit_rate"] is not None

        timing = snapshot["timing_metrics"]
        assert timing["avg_acquisition_time_ms"] > 0
        assert timing["p95_acquisition_time_ms"] > 0

        throughput = snapshot["throughput_metrics"]
        assert throughput["acquisitions_per_second"] > 0

    def test_get_dashboard_summary_after_load(self, connected_metrics_adapter):
        """Test get_dashboard_summary returns a valid summary after load."""
        summary = connected_metrics_adapter.get_dashboard_summary()

        assert "error" not in summary
        assert summary["status"] == "healthy"
        assert summary["metrics"]["hit_rate"] is not None
        assert summary["metrics"]["total_objects"] > 0
        assert summary["performance"]["avg_response_time_ms"] > 0
        assert summary["performance"]["throughput_ops_sec"] > 0

    def test_get_health_report_after_load(self, connected_metrics_adapter):
        """Test get_health_report provides a status after load."""
        report = connected_metrics_adapter.get_health_report()

        assert report["status"] in ["healthy", "warning", "critical"]
        assert "issues" in report
        assert "warnings" in report

    def test_get_detailed_smartpool_stats_after_load(self, connected_metrics_adapter):
        """Test get_detailed_smartpool_stats returns data after load."""
        stats = connected_metrics_adapter.get_detailed_smartpool_stats()

        assert "error" not in stats
        assert stats["basic_stats"]["counters"]["borrows"] >= 100
        assert stats["computed_metrics"]["hit_rate_calculated"] is not None
        assert stats["performance_metrics"] is not None

    def test_metrics_disabled(self, metrics_test_object):
        """Test that no performance metrics are returned when disabled."""
        config = SmartPoolAdapterConfig(
            factory_function=metrics_test_object,
            enable_performance_metrics=False,
            enable_stats=True,
        )
        adapter = SmartPoolAdapter(config)
        adapter.connect()

        for _ in range(10):
            with adapter.borrow():
                pass

        metrics = adapter.get_performance_metrics()
        assert "error" in metrics
        assert "not enabled" in metrics["error"]

        dashboard = adapter.get_dashboard_summary()
        assert dashboard["performance"]["avg_response_time_ms"] == 0

        adapter.disconnect()
