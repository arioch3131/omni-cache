"""
Tests for the core functionality of the BaseAdapter.
"""

import logging
from unittest.mock import Mock, patch

import pytest

from omni_cache.adapters.base.base import (
    ConnectionState,
)
from omni_cache.core.interfaces import (
    CacheBackend,
)

from .conftest import MockBaseAdapter


class TestBaseAdapterCore:
    """Tests for the BaseAdapter base class core functionality."""

    def test_initialization_with_dict_config(self, default_config):
        """Test BaseAdapter initialization with dictionary configuration."""
        adapter = MockBaseAdapter(default_config)

        assert adapter._config.name == "test_adapter"
        assert adapter._config.backend == CacheBackend.MEMORY
        assert adapter._state == ConnectionState.DISCONNECTED
        assert adapter._last_error is None
        assert adapter._connection_time is None
        assert adapter._cache_stats is not None  # Should track cache stats
        assert adapter._pool_stats is None  # Should not track pool stats

    def test_initialization_with_adapter_config(self, adapter_config):
        """Test BaseAdapter initialization with AdapterConfig instance."""
        adapter = MockBaseAdapter(adapter_config)

        assert adapter._config == adapter_config
        assert adapter._state == ConnectionState.DISCONNECTED

    def test_initialization_with_none_config(self):
        """Test BaseAdapter initialization with None configuration."""
        adapter = MockBaseAdapter(None)

        assert adapter._config.name == "default"
        assert adapter._config.backend == CacheBackend.MEMORY
        assert adapter._state == ConnectionState.DISCONNECTED

    @patch("logging.getLogger")
    def test_logger_setup(self, mock_get_logger):
        """Test that logger is set up correctly."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Create a new adapter to trigger logger setup
        MockBaseAdapter()

        mock_get_logger.assert_called_with("omni_cache.adapters.mockbaseadapter")
        mock_logger.setLevel.assert_called_with(logging.INFO)

    def test_repr(self, mock_base_adapter):
        """Test string representation of adapter."""
        repr_str = repr(mock_base_adapter)

        assert "MockBaseAdapter" in repr_str
        assert f"name='{mock_base_adapter._config.name}'" in repr_str
        assert f"backend='{mock_base_adapter._config.backend.value}'" in repr_str
        assert f"state='{mock_base_adapter._state.value}'" in repr_str

    def test_configure_existing_attribute(self, mock_base_adapter):
        """Test configuring an existing attribute."""
        initial_retries = mock_base_adapter._config.max_retries
        result = mock_base_adapter.configure({"max_retries": initial_retries + 1})

        assert result is True
        assert mock_base_adapter._config.max_retries == initial_retries + 1

    def test_configure_new_attribute(self, mock_base_adapter):
        """Test configuring a new attribute not in config."""
        result = mock_base_adapter.configure({"new_setting": "value"})

        assert result is True
        assert mock_base_adapter._config.extra_config["new_setting"] == "value"

    def test_configure_log_level_change(self, mock_base_adapter):
        """Test configuring log level change."""
        with patch.object(mock_base_adapter._logger, "setLevel") as mock_set_level:
            result = mock_base_adapter.configure({"log_level": "DEBUG"})

            assert result is True
            mock_set_level.assert_called_once_with(logging.DEBUG)

    def test_configure_no_log_level_change(self, mock_base_adapter):
        """Test configuring without log level change."""
        with patch.object(mock_base_adapter._logger, "setLevel") as mock_set_level:
            result = mock_base_adapter.configure({"max_retries": 10})

            assert result is True
            mock_set_level.assert_not_called()

    def test_get_config(self, mock_base_adapter):
        """Test getting the current configuration."""
        config = mock_base_adapter.get_config()

        assert config == mock_base_adapter._config

    def test_get_backend_info(self, mock_base_adapter):
        """Test getting backend information."""
        info = mock_base_adapter.get_backend_info()

        assert info["backend"] == mock_base_adapter._config.backend.value

    def test_get_backend_info_no_stats(self, mock_base_adapter):
        """Test getting backend information when get_stats returns None."""
        with patch.object(mock_base_adapter, "get_stats", return_value=None):
            info = mock_base_adapter.get_backend_info()

            assert "statistics" not in info
            assert info["backend"] == mock_base_adapter._config.backend.value

    def test_connection_context_manager(self, mock_base_adapter):
        """Test the connection context manager."""
        # Test successful connection and disconnection
        assert not mock_base_adapter.is_connected()
        with mock_base_adapter.connection():
            assert mock_base_adapter.is_connected()
        assert not mock_base_adapter.is_connected()

        # Test already connected (should not disconnect automatically)
        mock_base_adapter.connect()
        assert mock_base_adapter.is_connected()
        with mock_base_adapter.connection():
            assert mock_base_adapter.is_connected()
        assert mock_base_adapter.is_connected()  # Should still be connected
        mock_base_adapter.disconnect()  # Clean up

        # Test connection failure within context manager
        mock_base_adapter.connect_should_succeed = False
        assert not mock_base_adapter.is_connected()
        with pytest.raises(
            RuntimeError, match=f"Failed to connect to {mock_base_adapter._config.backend}"
        ):
            with mock_base_adapter.connection():
                pass
        assert not mock_base_adapter.is_connected()
