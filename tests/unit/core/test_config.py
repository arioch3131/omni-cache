"""
Unit tests for the simplified config.py module.

Tests cover all classes and functions including:
- BaseConfig, GlobalConfig, AdapterConfig
- ConfigLoader (file and environment loading)
- ConfigManager (main configuration management)
- Global functions and utilities
"""

import json
import os
import sys
import tempfile
from enum import Enum
from pathlib import Path
from unittest.mock import patch

import pytest

# Test dependencies - these would be installed in the test environment
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

from omni_cache.core.config import (
    AdapterConfig,
    BaseConfig,
    ConfigFormat,
    ConfigLoader,
    ConfigManager,
    GlobalConfig,
    get_global_config_manager,
    load_config_from_env,
    reset_global_config_manager,
    set_global_config_manager,
    temporary_config,
)
from omni_cache.core.exceptions import ConfigurationError


class TestYamlImport:
    def test_has_yaml_false_when_import_error(self):
        # Save original state
        yaml_module = sys.modules.get("yaml")
        config_module = sys.modules.get("omni_cache.core.config")

        try:
            # Force yaml import to fail by setting it to None
            sys.modules["yaml"] = None

            # Remove config from sys.modules to force reload
            if "omni_cache.core.config" in sys.modules:
                del sys.modules["omni_cache.core.config"]

            # Import config which will try to import yaml and set HAS_YAML
            import omni_cache.core.config

            # Assert that HAS_YAML is False due to ImportError
            assert omni_cache.core.config.HAS_YAML is False

        finally:
            # Restore original state
            if yaml_module is not None:
                sys.modules["yaml"] = yaml_module
            elif "yaml" in sys.modules:
                del sys.modules["yaml"]

            if config_module is not None:
                sys.modules["omni_cache.core.config"] = config_module
            elif "omni_cache.core.config" in sys.modules:
                del sys.modules["omni_cache.core.config"]


class TestBaseConfig:
    """Test cases for BaseConfig class."""

    def test_to_dict_basic(self):
        """Test converting configuration to dictionary."""
        config = BaseConfig()
        result = config.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_excludes_private_attributes(self):
        """Test that private attributes are excluded from dictionary."""
        config = BaseConfig()
        config._private = "should_not_appear"
        config.public = "should_appear"

        result = config.to_dict()

        assert "_private" not in result
        assert "public" in result
        assert result["public"] == "should_appear"

    def test_update_existing_attributes(self):
        """Test updating existing attributes."""
        config = BaseConfig()
        config.test_attr = "original"

        config.update({"test_attr": "updated"})

        assert config.test_attr == "updated"

    def test_update_ignores_nonexistent_attributes(self):
        """Test that update ignores attributes that don't exist."""
        config = BaseConfig()

        # Should not raise an error
        config.update({"nonexistent": "value"})

        # Should not create the attribute
        assert not hasattr(config, "nonexistent")


class TestGlobalConfig:
    """Test cases for GlobalConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = GlobalConfig()

        assert config.log_level == "INFO"
        assert config.auto_connect_adapters is True
        assert config.enable_global_stats is True
        assert config.health_check_interval == 60.0
        assert config.default_cache_adapter == "memory"
        assert config.default_cache_ttl is None
        assert config.default_pool_adapter is None
        assert config.default_pool_timeout == 5.0
        assert config.enable_routing is True
        assert config.namespace_separator == ":"
        assert config.fallback_adapter is None
        assert isinstance(config.extra, dict)
        assert len(config.extra) == 0

    def test_to_dict_includes_all_fields(self):
        """Test that to_dict includes all configuration fields."""
        config = GlobalConfig()
        result = config.to_dict()

        expected_keys = {
            "log_level",
            "log_format",
            "auto_connect_adapters",
            "enable_global_stats",
            "health_check_interval",
            "default_cache_adapter",
            "default_cache_ttl",
            "default_pool_adapter",
            "default_pool_timeout",
            "enable_routing",
            "namespace_separator",
            "fallback_adapter",
            "extra",
        }

        assert all(key in result for key in expected_keys)

    def test_update_modifies_values(self):
        """Test updating configuration values."""
        config = GlobalConfig()

        updates = {"log_level": "DEBUG", "health_check_interval": 30.0, "enable_routing": False}

        config.update(updates)

        assert config.log_level == "DEBUG"
        assert config.health_check_interval == 30.0
        assert config.enable_routing is False


class TestAdapterConfig:
    """Test cases for AdapterConfig class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = AdapterConfig()

        assert config.name == "default"
        assert config.backend == "memory"
        assert config.enabled is True
        assert config.auto_connect is True
        assert config.connection_timeout == 5.0
        assert config.max_retries == 3
        assert config.retry_delay == 0.1
        assert config.health_check_interval == 30.0
        assert config.enable_stats is True
        assert config.log_level == "INFO"
        assert isinstance(config.extra_config, dict)

    def test_custom_initialization(self):
        """Test creating adapter config with custom values."""
        config = AdapterConfig(
            name="redis", backend="redis", enabled=False, connection_timeout=10.0
        )

        assert config.name == "redis"
        assert config.backend == "redis"
        assert config.enabled is False
        assert config.connection_timeout == 10.0


class TestConfigLoader:
    """Test cases for ConfigLoader class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.loader = ConfigLoader()

    def test_load_from_file_json(self):
        """Test loading JSON configuration file."""
        config_data = {
            "global": {"log_level": "DEBUG"},
            "adapters": {"redis": {"backend": "redis"}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            result = self.loader.load_from_file(temp_path)
            assert result == config_data
        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not HAS_YAML, reason="YAML support not available")
    def test_load_from_file_yaml(self):
        """Test loading YAML configuration file."""
        config_data = {
            "global": {"log_level": "DEBUG"},
            "adapters": {"redis": {"backend": "redis"}},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            temp_path = f.name

        try:
            result = self.loader.load_from_file(temp_path)
            assert result == config_data
        finally:
            os.unlink(temp_path)

    def test_load_from_file_yaml_import_error(self):
        """Test loading YAML when yaml import fails."""
        config_data = "global:\n  log_level: DEBUG\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(config_data)
            temp_path = f.name

        try:
            with patch("omni_cache.core.config.HAS_YAML", False):
                with pytest.raises(
                    ConfigurationError, match="YAML support not available. Install PyYAML."
                ):
                    self.loader.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_from_file_nonexistent(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(ConfigurationError, match="Configuration file not found"):
            self.loader.load_from_file("/nonexistent/path.json")

    def test_load_from_file_invalid_json(self):
        """Test loading invalid JSON raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content {")
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="Failed to load configuration"):
                self.loader.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_from_file_unsupported_extension(self):
        """Test loading from a file with an unsupported extension."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("some content")
            temp_path = f.name

        try:
            with pytest.raises(ConfigurationError, match="Unsupported configuration file format"):
                self.loader.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_load_from_env_basic(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "OMNI_CACHE_LOG_LEVEL": "DEBUG",
            "OMNI_CACHE_ENABLE_ROUTING": "true",
            "OMNI_CACHE_ADAPTERS_REDIS_HOST": "localhost",
            "OMNI_CACHE_ADAPTERS_REDIS_PORT": "6379",
        }

        with patch.dict(os.environ, env_vars):
            result = self.loader.load_from_env()

        assert result["global"]["log_level"] == "DEBUG"
        assert result["global"]["enable_routing"] is True
        assert result["adapters"]["redis"]["host"] == "localhost"
        assert result["adapters"]["redis"]["port"] == 6379

    def test_load_from_env_custom_prefix(self):
        """Test loading with custom prefix."""
        env_vars = {"CUSTOM_LOG_LEVEL": "WARNING", "OTHER_SETTING": "ignored"}

        with patch.dict(os.environ, env_vars):
            result = self.loader.load_from_env(prefix="CUSTOM_")

        assert result["global"]["log_level"] == "WARNING"
        assert "other_setting" not in result["global"]

    def test_load_from_env_adapter_partial_key(self):
        """Test loading from environment with partial adapter key (len(parts) < 3)."""
        env_vars = {"OMNI_CACHE_ADAPTERS_REDIS": "should_be_ignored"}

        with patch.dict(os.environ, env_vars):
            result = self.loader.load_from_env()

        assert "adapters" not in result or "redis" not in result["adapters"]

    def test_parse_env_value_boolean(self):
        """Test parsing boolean values from environment."""
        assert self.loader._parse_env_value("true") is True
        assert self.loader._parse_env_value("True") is True
        assert self.loader._parse_env_value("TRUE") is True
        assert self.loader._parse_env_value("false") is False
        assert self.loader._parse_env_value("False") is False

    def test_parse_env_value_integer(self):
        """Test parsing integer values from environment."""
        assert self.loader._parse_env_value("123") == 123
        assert self.loader._parse_env_value("-456") == -456
        assert self.loader._parse_env_value("0") == 0

    def test_parse_env_value_float(self):
        """Test parsing float values from environment."""
        assert self.loader._parse_env_value("123.45") == 123.45
        assert self.loader._parse_env_value("-67.89") == -67.89

    def test_parse_env_value_json(self):
        """Test parsing JSON values from environment."""
        json_str = '{"key": "value", "number": 42}'
        result = self.loader._parse_env_value(json_str)
        assert result == {"key": "value", "number": 42}

    def test_parse_env_value_string(self):
        """Test parsing string values from environment."""
        assert self.loader._parse_env_value("simple_string") == "simple_string"
        assert self.loader._parse_env_value("") is None
        assert self.loader._parse_env_value("not_a_number_or_bool") == "not_a_number_or_bool"


class TestConfigManager:
    """Test cases for ConfigManager class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset global state before each test
        set_global_config_manager(None)

    def test_init_with_defaults(self):
        """Test initializing config manager with defaults."""
        manager = ConfigManager()

        assert isinstance(manager.get_global_config(), GlobalConfig)
        assert "memory" in manager.list_adapters()

        memory_config = manager.get_adapter_config("memory")
        assert memory_config is not None
        assert memory_config.backend == "memory"

    def test_init_with_config_file(self):
        """Test initializing with configuration file."""
        config_data = {
            "global": {"log_level": "DEBUG"},
            "adapters": {
                "redis": {
                    "backend": "redis",
                    "enabled": True,
                    "extra_config": {"host": "localhost"},
                }
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            temp_path = f.name

        try:
            manager = ConfigManager(temp_path)

            global_config = manager.get_global_config()
            assert global_config.log_level == "DEBUG"

            assert "redis" in manager.list_adapters()
            redis_config = manager.get_adapter_config("redis")
            assert redis_config.backend == "redis"
            assert redis_config.enabled is True

        finally:
            os.unlink(temp_path)

    def test_load_defaults(self):
        """Test loading default configuration."""
        manager = ConfigManager()
        manager._adapter_configs.clear()  # Clear first

        manager.load_defaults()

        global_config = manager.get_global_config()
        assert global_config.log_level == "INFO"
        assert "memory" in manager.list_adapters()

    def test_add_adapter_config(self):
        """Test adding adapter configuration."""
        manager = ConfigManager()

        config_data = {
            "backend": "redis",
            "enabled": True,
            "extra_config": {"host": "redis.example.com"},
        }

        manager.add_adapter_config("redis", config_data)

        assert "redis" in manager.list_adapters()
        redis_config = manager.get_adapter_config("redis")
        assert redis_config.name == "redis"
        assert redis_config.backend == "redis"
        assert redis_config.enabled is True
        assert redis_config.extra_config["host"] == "redis.example.com"

    def test_remove_adapter_config(self):
        """Test removing adapter configuration."""
        manager = ConfigManager()
        manager.add_adapter_config("test", {"backend": "memory"})

        assert "test" in manager.list_adapters()

        result = manager.remove_adapter_config("test")
        assert result is True
        assert "test" not in manager.list_adapters()

        # Test removing non-existent adapter
        result = manager.remove_adapter_config("nonexistent")
        assert result is False

    def test_update_global_config(self):
        """Test updating global configuration."""
        manager = ConfigManager()

        updates = {"log_level": "WARNING", "health_check_interval": 120.0, "enable_routing": False}

        manager.update_global_config(updates)

        global_config = manager.get_global_config()
        assert global_config.log_level == "WARNING"
        assert global_config.health_check_interval == 120.0
        assert global_config.enable_routing is False

    def test_get_adapter_config_nonexistent(self):
        """Test getting configuration for non-existent adapter."""
        manager = ConfigManager()

        result = manager.get_adapter_config("nonexistent")
        assert result is None

    def test_save_config_json(self):
        """Test saving configuration to JSON file."""
        manager = ConfigManager()
        manager.update_global_config({"log_level": "DEBUG"})
        manager.add_adapter_config("redis", {"backend": "redis"})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name

        try:
            manager.save_config(temp_path, ConfigFormat.JSON)

            # Verify saved content
            with open(temp_path) as f:
                saved_data = json.load(f)

            assert saved_data["global"]["log_level"] == "DEBUG"
            assert saved_data["adapters"]["redis"]["backend"] == "redis"

        finally:
            os.unlink(temp_path)

    @pytest.mark.skipif(not HAS_YAML, reason="YAML support not available")
    def test_save_config_yaml(self):
        """Test saving configuration to YAML file."""
        manager = ConfigManager()
        manager.update_global_config({"log_level": "DEBUG"})

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            manager.save_config(temp_path, ConfigFormat.YAML)

            # Verify saved content
            with open(temp_path) as f:
                saved_data = yaml.safe_load(f)

            assert saved_data["global"]["log_level"] == "DEBUG"

        finally:
            os.unlink(temp_path)

    def test_save_config_no_path(self):
        """Test saving configuration without specifying path."""
        manager = ConfigManager()

        with pytest.raises(ConfigurationError, match="No output file specified"):
            manager.save_config()

    def test_save_config_unsupported_format(self):
        """Test saving configuration with an unsupported format."""
        manager = ConfigManager()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            temp_path = f.name
        try:
            # Create a dummy ConfigFormat value that is neither JSON nor YAML
            class UnsupportedFormat(Enum):
                UNSUPPORTED = "unsupported"

            with pytest.raises(
                ConfigurationError, match="Unsupported configuration format: unsupported"
            ):
                manager.save_config(temp_path, UnsupportedFormat.UNSUPPORTED)
        finally:
            os.unlink(temp_path)

    def test_get_config_summary(self):
        """Test getting configuration summary."""
        manager = ConfigManager()
        manager.add_adapter_config("redis", {"backend": "redis", "enabled": False})

        summary = manager.get_config_summary()

        assert "global" in summary
        assert "adapters" in summary
        assert "stats" in summary

        assert summary["stats"]["total_adapters"] >= 2  # memory + redis
        assert summary["adapters"]["redis"]["backend"] == "redis"
        assert summary["adapters"]["redis"]["enabled"] is False

    def test_merge_configs(self):
        """Test merging file and environment configurations."""
        manager = ConfigManager()

        file_config = {
            "global": {"log_level": "INFO", "enable_routing": True},
            "adapters": {"redis": {"backend": "redis", "port": 6379}},
        }

        env_config = {
            "global": {"log_level": "DEBUG"},  # Should override file
            "adapters": {"redis": {"host": "localhost"}},  # Should merge with file
        }

        result = manager._merge_configs(file_config, env_config)

        assert result["global"]["log_level"] == "DEBUG"  # From env
        assert result["global"]["enable_routing"] is True  # From file
        assert result["adapters"]["redis"]["backend"] == "redis"  # From file
        assert result["adapters"]["redis"]["port"] == 6379  # From file
        assert result["adapters"]["redis"]["host"] == "localhost"  # From env

    def test_merge_configs_global_only(self):
        """Test merging configs when only global settings are in env_config."""
        manager = ConfigManager()

        file_config = {
            "global": {"log_level": "INFO", "enable_routing": True},
            "adapters": {"memory": {"backend": "memory"}},
        }

        env_config = {
            "global": {"log_level": "DEBUG"},  # Should override file
        }

        result = manager._merge_configs(file_config, env_config)

        assert result["global"]["log_level"] == "DEBUG"
        assert result["global"]["enable_routing"] is True
        assert result["adapters"]["memory"]["backend"] == "memory"
        assert "adapters" in result

    def test_merge_configs_adapters_only(self):
        """Test merging configs when only adapter settings are in env_config."""
        manager = ConfigManager()

        file_config = {
            "global": {"log_level": "INFO", "enable_routing": True},
            "adapters": {"memory": {"backend": "memory"}},
        }

        env_config = {
            "adapters": {"redis": {"host": "localhost"}},  # Should merge with file
        }

        result = manager._merge_configs(file_config, env_config)

        assert result["global"]["log_level"] == "INFO"  # Should remain from file
        assert result["global"]["enable_routing"] is True  # Should remain from file
        assert result["adapters"]["memory"]["backend"] == "memory"  # From file
        assert result["adapters"]["redis"]["host"] == "localhost"  # From env

    def test_load_adapter_configs_update_exception(self):
        """Test _load_adapter_configs when adapter_config.update raises an exception."""
        manager = ConfigManager()
        adapters_data = {"test_adapter": {"backend": "memory"}}

        with patch.object(AdapterConfig, "update", side_effect=Exception("Update error")):
            with pytest.raises(
                ConfigurationError,
                match="Failed to load adapter config for test_adapter: Update error",
            ):
                manager._load_adapter_configs(adapters_data)

    def test_load_config_no_file(self):
        """Test loading configuration without file specified."""
        manager = ConfigManager()
        manager._config_file = None

        with pytest.raises(ConfigurationError, match="No configuration file specified"):
            manager.load_config()

    def test_load_config_with_new_file_path(self):
        """Test loading configuration with a new file path provided to load_config."""
        # Create an initial config file
        initial_config_data = {"global": {"log_level": "INFO"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(initial_config_data, f)
            initial_path = f.name

        # Create a new config file
        new_config_data = {"global": {"log_level": "WARNING"}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(new_config_data, f)
            new_path = f.name

        try:
            manager = ConfigManager(initial_path)
            assert manager.get_global_config().log_level == "INFO"

            # Load config with new path
            manager.load_config(new_path)

            assert manager._config_file == Path(new_path)
            assert manager.get_global_config().log_level == "WARNING"
        finally:
            os.unlink(initial_path)
            os.unlink(new_path)


class TestGlobalFunctions:
    """Test cases for global utility functions."""

    def setup_method(self):
        """Reset global state before each test."""
        reset_global_config_manager()

    def test_get_global_config_manager_creates_default(self):
        """Test that get_global_config_manager creates default instance."""
        manager = get_global_config_manager()

        assert isinstance(manager, ConfigManager)

        # Should return same instance on subsequent calls
        manager2 = get_global_config_manager()
        assert manager is manager2

    def test_set_global_config_manager(self):
        """Test setting custom global config manager."""
        custom_manager = ConfigManager()

        set_global_config_manager(custom_manager)
        retrieved_manager = get_global_config_manager()

        assert retrieved_manager is custom_manager

    def test_load_config_from_env(self):
        """Test loading configuration from environment variables."""
        env_vars = {"OMNI_CACHE_LOG_LEVEL": "ERROR", "OMNI_CACHE_ADAPTERS_CUSTOM_BACKEND": "custom"}

        with patch.dict(os.environ, env_vars):
            result = load_config_from_env()

        assert result["global"]["log_level"] == "ERROR"
        assert result["adapters"]["custom"]["backend"] == "custom"

    def test_temporary_config_success(self):
        """Test temporary_config context manager for successful execution."""
        initial_manager = get_global_config_manager()
        initial_log_level = initial_manager.get_global_config().log_level

        with temporary_config({"global": {"log_level": "DEBUG"}}):
            temp_manager = get_global_config_manager()
            assert temp_manager.get_global_config().log_level == "DEBUG"
            assert temp_manager is not initial_manager  # Should be a new manager

        # After exiting, should revert to original manager and config
        final_manager = get_global_config_manager()
        assert final_manager is initial_manager
        assert final_manager.get_global_config().log_level == initial_log_level

    def test_temporary_config_with_exception(self):
        """Test temporary_config context manager when an exception occurs."""
        initial_manager = get_global_config_manager()
        initial_log_level = initial_manager.get_global_config().log_level

        with pytest.raises(ValueError, match="Test exception in temporary config"):
            with temporary_config({"global": {"log_level": "DEBUG"}}):
                temp_manager = get_global_config_manager()
                assert temp_manager.get_global_config().log_level == "DEBUG"
                raise ValueError("Test exception in temporary config")

        # After exiting (even with exception), should revert to original manager and config
        final_manager = get_global_config_manager()
        assert final_manager is initial_manager
        assert final_manager.get_global_config().log_level == initial_log_level


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    def test_config_manager_invalid_file(self):
        """Test ConfigManager with invalid configuration file."""
        with pytest.raises(ConfigurationError):
            ConfigManager("/nonexistent/path.json")

    def test_config_loader_yaml_without_support(self):
        """Test YAML loading when PyYAML is not available."""
        loader = ConfigLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("global:\n  log_level: DEBUG\n")
            temp_path = f.name

        try:
            with patch("omni_cache.core.config.HAS_YAML", False):
                with pytest.raises(ConfigurationError, match="YAML support not available"):
                    loader.load_from_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_save_config_yaml_without_support(self):
        """Test saving YAML when PyYAML is not available."""
        manager = ConfigManager()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            with patch("omni_cache.core.config.HAS_YAML", False):
                with pytest.raises(ConfigurationError, match="YAML support not available"):
                    manager.save_config(temp_path, ConfigFormat.YAML)
        finally:
            os.unlink(temp_path)


class TestThreadSafety:
    """Test cases for thread safety."""

    def test_concurrent_adapter_config_modifications(self):
        """Test concurrent modifications to adapter configurations."""
        import threading
        import time

        manager = ConfigManager()
        results = []

        def add_adapters(thread_id):
            for i in range(10):
                adapter_name = f"adapter_{thread_id}_{i}"
                manager.add_adapter_config(adapter_name, {"backend": "memory"})
                results.append(adapter_name)
                time.sleep(0.001)  # Small delay to increase chance of race conditions

        # Start multiple threads
        threads = []
        for thread_id in range(3):
            thread = threading.Thread(target=add_adapters, args=(thread_id,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all adapters were added
        adapters = manager.list_adapters()
        assert len(results) == 30

        for adapter_name in results:
            assert adapter_name in adapters

    def test_concurrent_global_config_updates(self):
        """Test concurrent global configuration updates."""
        import threading

        manager = ConfigManager()

        def update_config(value):
            manager.update_global_config({"log_level": f"LEVEL_{value}"})

        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_config, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not crash and should have some valid log level
        global_config = manager.get_global_config()
        assert global_config.log_level.startswith("LEVEL_")

    def test_get_global_config_manager_concurrent_access(self):
        """Test concurrent access to get_global_config_manager, ensuring single initialization."""
        import threading
        import time

        # Ensure the global manager is reset before the test
        reset_global_config_manager()

        results = []
        # Simple counter to track how many ConfigManager instances are created
        original_init = ConfigManager.__init__
        init_count = 0

        def counting_init(self, *args, **kwargs):
            nonlocal init_count
            init_count += 1
            time.sleep(0.05)  # Small delay to increase chance of race conditions
            return original_init(self, *args, **kwargs)

        # Patch ConfigManager.__init__ to count instantiations
        ConfigManager.__init__ = counting_init

        try:

            def get_manager_thread():
                manager = get_global_config_manager()
                results.append(manager)

            # Create and start multiple threads
            threads = []
            for _i in range(5):
                thread = threading.Thread(target=get_manager_thread)
                threads.append(thread)

            # Start all threads simultaneously
            for thread in threads:
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join(timeout=2)

            # Assertions
            assert len(results) == 5, "All threads should have retrieved a manager"
            assert init_count == 1, (
                "ConfigManager should be instantiated exactly once, "
                f"but was created {init_count} times"
            )

            # All results should be the same instance
            first_manager = results[0]
            for manager in results[1:]:
                assert manager is first_manager, (
                    "All threads should receive the same manager instance"
                )

            assert isinstance(first_manager, ConfigManager), (
                "The manager should be a ConfigManager instance"
            )

        finally:
            # Restore original __init__
            ConfigManager.__init__ = original_init


# Integration test
class TestConfigIntegration:
    """Integration tests combining multiple components."""

    def test_full_configuration_workflow(self):
        """Test complete configuration workflow."""
        # Create configuration data
        config_data = {
            "global": {
                "log_level": "WARNING",
                "enable_routing": False,
                "health_check_interval": 45.0,
                "extra": {"custom_setting": "value"},
            },
            "adapters": {
                "memory": {
                    "backend": "memory",
                    "enabled": True,
                    "extra_config": {"max_size": 5000},
                },
                "redis": {
                    "backend": "redis",
                    "enabled": False,
                    "connection_timeout": 10.0,
                    "extra_config": {"host": "redis.example.com", "port": 6380, "db": 1},
                },
            },
        }

        # Save to file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            config_file = f.name

        try:
            # Load configuration
            manager = ConfigManager(config_file)

            # Verify global configuration
            global_config = manager.get_global_config()
            assert global_config.log_level == "WARNING"
            assert global_config.enable_routing is False
            assert global_config.health_check_interval == 45.0
            assert global_config.extra["custom_setting"] == "value"

            # Verify adapter configurations
            adapters = manager.list_adapters()
            assert "memory" in adapters
            assert "redis" in adapters

            memory_config = manager.get_adapter_config("memory")
            assert memory_config.backend == "memory"
            assert memory_config.enabled is True
            assert memory_config.extra_config["max_size"] == 5000

            redis_config = manager.get_adapter_config("redis")
            assert redis_config.backend == "redis"
            assert redis_config.enabled is False
            assert redis_config.connection_timeout == 10.0
            assert redis_config.extra_config["host"] == "redis.example.com"
            assert redis_config.extra_config["port"] == 6380

            # Modify configuration
            manager.update_global_config({"log_level": "DEBUG"})
            manager.add_adapter_config("new_adapter", {"backend": "custom", "enabled": True})

            # Save modified configuration
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                new_config_file = f.name

            manager.save_config(new_config_file, ConfigFormat.JSON)

            # Verify saved configuration
            with open(new_config_file) as f:
                saved_config = json.load(f)

            assert saved_config["global"]["log_level"] == "DEBUG"
            assert saved_config["adapters"]["new_adapter"]["backend"] == "custom"

            os.unlink(new_config_file)

        finally:
            os.unlink(config_file)
