"""
Tests for the base adapter configuration and connection state.
"""

from omni_cache.adapters.base.base import (
    AdapterConfig,
    ConnectionState,
)
from omni_cache.core.interfaces import (
    CacheBackend,
)

# Tests for AdapterConfig


class TestAdapterConfig:
    """Tests for the AdapterConfig class."""

    def test_default_initialization(self):
        """Test AdapterConfig with default values."""
        config = AdapterConfig()

        assert config.name == "default"
        assert config.backend == CacheBackend.MEMORY
        assert config.max_retries == 3
        assert config.retry_delay == 0.1
        assert config.connection_timeout == 5.0
        assert config.health_check_interval == 30.0
        assert config.enable_stats is True
        assert config.log_level == "INFO"
        assert config.extra_config == {}

    def test_custom_initialization(self, default_config):
        """Test AdapterConfig with custom values."""
        config = AdapterConfig(**default_config)

        assert config.name == "test_adapter"
        assert config.backend == CacheBackend.MEMORY
        assert config.max_retries == 3
        assert config.retry_delay == 0.1
        assert config.connection_timeout == 5.0
        assert config.health_check_interval == 30.0
        assert config.enable_stats is True
        assert config.log_level == "INFO"

    def test_extra_config(self):
        """Test AdapterConfig with extra configuration."""
        extra = {"custom_param": "value", "number_param": 42}
        config = AdapterConfig(extra_config=extra)

        assert config.extra_config == extra

    def test_backend_as_string(self):
        """Test AdapterConfig with backend as string."""
        config = AdapterConfig(backend="redis")
        assert config.backend == "redis"


# Tests for ConnectionState


class TestConnectionState:
    """Tests for the ConnectionState enum."""

    def test_all_states_exist(self):
        """Test that all expected connection states exist."""
        expected_states = ["DISCONNECTED", "CONNECTING", "CONNECTED", "DISCONNECTING", "ERROR"]

        for state_name in expected_states:
            assert hasattr(ConnectionState, state_name)

    def test_state_values(self):
        """Test connection state values."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTING.value == "disconnecting"
        assert ConnectionState.ERROR.value == "error"
