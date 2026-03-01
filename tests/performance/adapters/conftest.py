"""
Pytest configuration and shared fixtures for adapter tests.

This module provides shared fixtures and configuration for testing
omni-cache adapters, particularly the memory adapter.
"""

import logging
import time
from unittest.mock import MagicMock

import pytest

from omni_cache.adapters.base import AdapterConfig, BaseAdapter, BaseCacheAdapter, BasePoolAdapter
from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig
from omni_cache.core.interfaces import (
    AdapterInterface,
    CacheBackend,
    CacheStats,
    StatisticsInterface,
)


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "concurrent: marks tests that test concurrency")
    config.addinivalue_line("markers", "cleanup: marks tests that test cleanup functionality")


# Logging configuration for tests
@pytest.fixture(scope="session", autouse=True)
def configure_test_logging():
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.WARNING,  # Reduce noise during testing
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Suppress debug logs from adapters during testing
    logging.getLogger("omni_cache.adapters").setLevel(logging.WARNING)
    logging.getLogger("omni_cache.core").setLevel(logging.WARNING)


# Basic adapter fixtures
@pytest.fixture
def magic_mock_adapter():
    """Create a mock adapter that simulates BaseAdapter behavior."""
    mock = MagicMock(spec=AdapterInterface)
    mock.add_spec(StatisticsInterface)
    mock.is_connected.return_value = True
    mock.connect.return_value = True
    mock.disconnect.return_value = True
    mock.health_check.return_value = True
    mock.get_stats.return_value = MagicMock(spec=CacheStats)  # Default to CacheStats
    mock.get_backend_info.return_value = {
        "name": "mock_adapter",
        "backend": "mock",
        "state": "connected",
    }
    # Mock abstract methods if they are called directly in tests
    mock._do_connect.return_value = True
    mock._do_disconnect.return_value = True
    mock._do_health_check.return_value = True
    mock._should_track_cache_stats.return_value = True
    mock._should_track_pool_stats.return_value = False
    return mock


class MockBaseAdapter(BaseAdapter):
    def __init__(self, config=None):
        super().__init__(config)
        self.connect_should_succeed = True
        self.disconnect_should_succeed = True
        self.health_check_should_succeed = True
        self.connect_called = False
        self.disconnect_called = False
        self.health_check_called = False
        self.connect_delay = 0

    def _should_track_cache_stats(self) -> bool:
        return True

    def _should_track_pool_stats(self) -> bool:
        return False

    def _do_connect(self) -> bool:
        self.connect_called = True
        time.sleep(self.connect_delay)
        return self.connect_should_succeed

    def _do_disconnect(self) -> bool:
        self.disconnect_called = True
        return self.disconnect_should_succeed

    def _do_health_check(self) -> bool:
        self.health_check_called = True
        return self.health_check_should_succeed


class MockBaseCacheAdapter(BaseCacheAdapter):
    def _do_connect(self) -> bool:
        return True

    def _do_disconnect(self) -> bool:
        return True

    def _do_health_check(self) -> bool:
        return True


class MockBasePoolAdapter(BasePoolAdapter):
    def _do_connect(self) -> bool:
        return True

    def _do_disconnect(self) -> bool:
        return True

    def _do_health_check(self) -> bool:
        return True


@pytest.fixture
def mock_base_adapter(adapter_config):
    """Create a mock adapter that simulates BaseAdapter behavior."""
    return MockBaseAdapter(adapter_config)


@pytest.fixture
def default_config():
    """Default configuration for testing."""
    return {
        "name": "test_adapter",
        "backend": CacheBackend.MEMORY,
        "max_retries": 3,
        "retry_delay": 0.1,
        "connection_timeout": 5.0,
        "health_check_interval": 30.0,
        "enable_stats": True,
        "log_level": "INFO",
    }


@pytest.fixture
def adapter_config(default_config):
    """Create an AdapterConfig instance for testing."""
    return AdapterConfig(**default_config)


@pytest.fixture
def mock_cache_adapter(adapter_config):
    """Create a mock cache adapter."""
    return MockBaseCacheAdapter(adapter_config)


@pytest.fixture
def mock_pool_adapter(adapter_config):
    """Create a mock pool adapter."""
    return MockBasePoolAdapter(adapter_config)


@pytest.fixture
def memory_adapter():
    """Create a basic memory adapter for testing."""
    adapter = MemoryAdapter()
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def memory_adapter_config():
    """Create a basic memory adapter configuration."""
    return MemoryAdapterConfig(
        name="test_adapter",
        max_size=100,
        cleanup_interval=0.1,  # Fast cleanup for testing
        enable_stats=True,
    )


@pytest.fixture
def configured_memory_adapter(memory_adapter_config):
    """Create a configured memory adapter for testing."""
    adapter = MemoryAdapter(memory_adapter_config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def large_adapter():
    """Create a memory adapter with larger capacity for performance tests."""
    config = MemoryAdapterConfig(name="large_test", max_size=10000, cleanup_interval=1.0)
    adapter = MemoryAdapter(config)
    adapter.connect()
    yield adapter
    adapter.disconnect()


@pytest.fixture
def performance_timer():
    """Provide a performance timer for benchmarking tests."""

    class PerformanceTimer:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.perf_counter()

        def stop(self):
            self.end_time = time.perf_counter()

        @property
        def elapsed(self):
            if self.start_time is None or self.end_time is None:
                return None
            return self.end_time - self.start_time

        def __enter__(self):
            self.start()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop()

    return PerformanceTimer
