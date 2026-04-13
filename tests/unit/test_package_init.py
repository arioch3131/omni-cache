"""
Tests for the omni_cache package __init__.py file.
"""

import importlib.util
import logging
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest


# Helper function to import omni_cache cleanly for each test
def _import_omni_cache_clean():
    # Clear omni_cache from sys.modules to ensure a fresh import
    keys_to_delete = [k for k in sys.modules if k.startswith("omni_cache")]
    for key in keys_to_delete:
        del sys.modules[key]

    # Manually load the module spec and execute it
    spec = importlib.util.spec_from_file_location("omni_cache", "src/omni_cache/__init__.py")
    omni_cache = importlib.util.module_from_spec(spec)
    sys.modules["omni_cache"] = omni_cache
    spec.loader.exec_module(omni_cache)
    return omni_cache


class TestInitFile:
    def test_version_and_metadata_exist(self):
        omni_cache = _import_omni_cache_clean()
        assert hasattr(omni_cache, "__version__")
        assert hasattr(omni_cache, "__author__")
        assert hasattr(omni_cache, "__license__")
        assert hasattr(omni_cache, "__description__")

    def test_logging_configured_on_import(self):
        # Ensure logging is not configured before import
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        root_logger.handlers = []

        _import_omni_cache_clean()

        assert len(root_logger.handlers) > 0
        assert root_logger.level == logging.WARNING

        # Restore original handlers
        root_logger.handlers = original_handlers

    def test_logging_level_set_to_warning(self):
        _import_omni_cache_clean()
        logger = logging.getLogger("omni_cache")
        assert logger.level == logging.WARNING

    @pytest.mark.parametrize(
        "env_value, expected_call",
        [
            ("true", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
            (None, False),  # Default case
        ],
    )
    def test_auto_setup_from_env(self, monkeypatch, env_value, expected_call):
        # Set environment variable
        if env_value is not None:
            monkeypatch.setenv("OMNI_CACHE_AUTO_SETUP", env_value)
        else:
            monkeypatch.delenv("OMNI_CACHE_AUTO_SETUP", raising=False)

        # Import module first but prevent auto-setup from running by mocking the env check
        with patch("os.getenv", return_value="false"):
            omni_cache = _import_omni_cache_clean()

        # Create mocks for the functions
        mock_configure_from_env = Mock()
        mock_setup_function = Mock()

        # Patch the module's functions and test _run_auto_setup behavior
        with (
            patch.object(omni_cache, "configure_from_env", mock_configure_from_env),
            patch.object(omni_cache, "setup", mock_setup_function),
            patch(
                "omni_cache.core.config.load_config_from_env", return_value={"log_level": "INFO"}
            ),
            patch("os.getenv", return_value=env_value or "false"),
        ):
            # Test the auto-setup logic directly
            omni_cache._run_auto_setup()

            if expected_call:
                mock_configure_from_env.assert_called_once_with()
                mock_setup_function.assert_called_once_with(auto_discover=True)
            else:
                mock_configure_from_env.assert_not_called()
                mock_setup_function.assert_not_called()

    def test_auto_setup_failure_warns(self, monkeypatch):
        # Import module first but prevent auto-setup from running
        with patch("os.getenv", return_value="false"):
            omni_cache = _import_omni_cache_clean()

        # Create mocks that raise exceptions
        mock_configure_from_env = Mock(side_effect=Exception("Configure failed"))
        mock_setup_function = Mock(side_effect=Exception("Setup failed"))

        # Test that failures produce warnings
        with (
            patch.object(omni_cache, "configure_from_env", mock_configure_from_env),
            patch.object(omni_cache, "setup", mock_setup_function),
            patch("os.getenv", return_value="true"),
            pytest.warns(UserWarning, match="Auto-setup failed"),
        ):
            omni_cache._run_auto_setup()

        # Should have tried to call configure_from_env
        mock_configure_from_env.assert_called_once_with()

    def test_setup_function_call(self, monkeypatch):
        # Import first to avoid auto-setup interference
        omni_cache = _import_omni_cache_clean()

        with patch.object(omni_cache, "setup") as mock_setup_function:
            omni_cache.setup()
            mock_setup_function.assert_called_once()

    def test_discover_backends_function_call(self, monkeypatch):
        # Import first
        omni_cache = _import_omni_cache_clean()

        # Patch the imported function in the module's namespace
        with patch.object(omni_cache, "get_global_registry") as mock_get_registry:
            mock_registry = MagicMock()
            mock_get_registry.return_value = mock_registry
            mock_registry.get_all_metadata.return_value = {"memory": MagicMock(backend="memory")}

            backends = omni_cache.discover_backends()

            mock_get_registry.assert_called_once()
            mock_registry.get_all_metadata.assert_called_once()
            assert "memory" in backends

    def test_quick_cache_function_call(self, monkeypatch):
        omni_cache = _import_omni_cache_clean()

        with patch.object(omni_cache, "create_adapter") as mock_create_adapter:
            omni_cache.quick_cache(backend="memory", max_size=100)
            mock_create_adapter.assert_called_once_with("memory", {"max_size": 100})

    def test_quick_pool_function_call(self, monkeypatch):
        omni_cache = _import_omni_cache_clean()

        mock_factory_func = MagicMock()
        with patch.object(omni_cache, "create_adapter") as mock_create_adapter:
            omni_cache.quick_pool(
                backend="smartpool", factory_function=mock_factory_func, max_size=10
            )
            mock_create_adapter.assert_called_once_with(
                "smartpool", {"factory_function": mock_factory_func, "max_size": 10}
            )

    def test_get_version_info_function_call(self, monkeypatch):
        omni_cache = _import_omni_cache_clean()

        with patch.object(
            omni_cache, "list_available_backends", return_value=["memory"]
        ) as mock_list_backends:
            info = omni_cache.get_version_info()
            assert "version" in info
            assert "python_version" in info
            assert "capabilities" in info
            assert "available_backends" in info
            mock_list_backends.assert_called_once()

    def test_configure_from_env_function_call(self, monkeypatch):
        omni_cache = _import_omni_cache_clean()

        # Patch the imported functions in the module's namespace
        with (
            patch.object(
                omni_cache,
                "load_config_from_env",
                return_value={"log_level": "DEBUG", "default_adapter": "redis"},
            ) as mock_load_env,
            patch.object(omni_cache, "get_global_config_manager") as mock_get_manager,
            patch("logging.getLogger") as mock_get_logger,
        ):
            mock_manager = MagicMock()
            mock_get_manager.return_value = mock_manager
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            omni_cache.configure_from_env("CUSTOM_PREFIX_")

            mock_load_env.assert_called_once_with("CUSTOM_PREFIX_")
            mock_get_manager.assert_called_once()
            mock_manager.update_global_config.assert_called_once_with(
                {"log_level": "DEBUG", "default_adapter": "redis"}
            )
            mock_get_logger.assert_called_with("omni_cache")
            mock_logger.setLevel.assert_called_with(logging.DEBUG)

    def test_info_function_call(self, monkeypatch):
        omni_cache = _import_omni_cache_clean()

        with (
            patch("builtins.print") as mock_print,
            patch.object(
                omni_cache,
                "get_version_info",
                return_value={
                    "version": "2.0.0",
                    "python_version": "3.9",
                    "capabilities": {"redis_adapter": True, "adaptive_adapter": False},
                    "available_backends": ["memory", "redis"],
                },
            ) as mock_get_version_info,
        ):
            omni_cache.info()
            mock_print.assert_called()
            mock_get_version_info.assert_called_once()
