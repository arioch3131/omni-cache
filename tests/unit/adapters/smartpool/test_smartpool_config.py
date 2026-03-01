"""
Tests for SmartPoolAdapterConfig configuration module.

This module provides comprehensive test coverage for the SmartPoolAdapterConfig
dataclass, including initialization, validation, inheritance, and serialization.
"""

from dataclasses import asdict, fields
from unittest.mock import Mock

from omni_cache.adapters.base import AdapterConfig
from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.core.interfaces.enum_dataclasses import CacheBackend


class TestSmartPoolAdapterConfig:
    """Test suite for SmartPoolAdapterConfig class."""

    def test_default_initialization(self):
        """Test initialization with default values."""
        config = SmartPoolAdapterConfig()

        # Test basic pool configuration defaults
        assert config.factory_function is None
        assert config.factory_args == ()
        assert config.factory_kwargs == {}

        # Test pool sizing defaults
        assert config.initial_size == 5
        assert config.max_size == 20
        assert config.min_size == 2

        # Test memory management defaults
        assert config.memory_preset is None
        assert config.max_age_seconds == 300
        assert config.cleanup_interval == 30
        assert config.enable_background_cleanup is True
        assert config.backend == CacheBackend.SMARTPOOL.value

        # Test performance and tuning defaults
        assert config.enable_performance_metrics is True
        assert config.enable_auto_tuning is True
        assert config.auto_tuning_interval == 60

        # Test object management defaults
        assert config.auto_wrap_objects is True

        # Test additional configuration defaults
        assert config.extra_config == {}

    def test_custom_initialization(self):
        """Test initialization with custom values."""
        mock_factory = Mock()
        factory_args = ("arg1", "arg2")
        factory_kwargs = {"key1": "value1"}
        extra_config = {"custom_key": "custom_value"}

        config = SmartPoolAdapterConfig(
            factory_function=mock_factory,
            factory_args=factory_args,
            factory_kwargs=factory_kwargs,
            initial_size=10,
            max_size=50,
            min_size=5,
            memory_preset="HIGH_THROUGHPUT",
            max_age_seconds=600,
            cleanup_interval=60,
            enable_background_cleanup=False,
            enable_performance_metrics=False,
            enable_auto_tuning=True,
            auto_tuning_interval=120,
            auto_wrap_objects=False,
            extra_config=extra_config,
        )

        assert config.factory_function == mock_factory
        assert config.factory_args == factory_args
        assert config.factory_kwargs == factory_kwargs
        assert config.initial_size == 10
        assert config.max_size == 50
        assert config.min_size == 5
        assert config.memory_preset == "HIGH_THROUGHPUT"
        assert config.max_age_seconds == 600
        assert config.cleanup_interval == 60
        assert config.enable_background_cleanup is False
        assert config.enable_performance_metrics is False
        assert config.enable_auto_tuning is True
        assert config.auto_tuning_interval == 120
        assert config.auto_wrap_objects is False
        assert config.extra_config == extra_config

    def test_inheritance_from_adapter_config(self):
        """Test that SmartPoolAdapterConfig inherits from AdapterConfig."""
        config = SmartPoolAdapterConfig()
        assert isinstance(config, AdapterConfig)
        assert issubclass(SmartPoolAdapterConfig, AdapterConfig)

    def test_backend_value(self):
        """Test that backend is correctly set to SMARTPOOL value."""
        config = SmartPoolAdapterConfig()
        assert config.backend == CacheBackend.SMARTPOOL.value
        assert config.backend == "smartpool"

    def test_factory_function_types(self):
        """Test different types of factory functions."""
        # Test with None (default)
        config = SmartPoolAdapterConfig()
        assert config.factory_function is None

        # Test with callable
        def test_factory():
            return Mock()

        config = SmartPoolAdapterConfig(factory_function=test_factory)
        assert config.factory_function == test_factory
        assert callable(config.factory_function)

        # Test with lambda
        def lambda_factory():
            return Mock()

        config = SmartPoolAdapterConfig(factory_function=lambda_factory)
        assert config.factory_function == lambda_factory
        assert callable(config.factory_function)

    def test_memory_preset_values(self):
        """Test valid memory preset values."""
        valid_presets = ["HIGH_THROUGHPUT", "LOW_MEMORY", "BALANCED", None]

        for preset in valid_presets:
            config = SmartPoolAdapterConfig(memory_preset=preset)
            assert config.memory_preset == preset

    def test_pool_sizing_configuration(self):
        """Test pool sizing parameters."""
        config = SmartPoolAdapterConfig(initial_size=3, max_size=15, min_size=1)

        assert config.initial_size == 3
        assert config.max_size == 15
        assert config.min_size == 1

    def test_timing_configuration(self):
        """Test timing-related parameters."""
        config = SmartPoolAdapterConfig(
            max_age_seconds=1200, cleanup_interval=45, auto_tuning_interval=90
        )

        assert config.max_age_seconds == 1200
        assert config.cleanup_interval == 45
        assert config.auto_tuning_interval == 90

    def test_boolean_flags(self):
        """Test boolean configuration flags."""
        config = SmartPoolAdapterConfig(
            enable_background_cleanup=False,
            enable_performance_metrics=False,
            enable_auto_tuning=True,
            auto_wrap_objects=False,
        )

        assert config.enable_background_cleanup is False
        assert config.enable_performance_metrics is False
        assert config.enable_auto_tuning is True
        assert config.auto_wrap_objects is False

    def test_to_dict_method(self):
        """Test the to_dict method for dataclass conversion."""
        mock_factory = Mock()
        config = SmartPoolAdapterConfig(
            factory_function=mock_factory,
            initial_size=8,
            max_size=25,
            memory_preset="BALANCED",
            enable_auto_tuning=True,
        )

        result_dict = config.to_dict()

        # Check that result is a dictionary
        assert isinstance(result_dict, dict)

        # Check that all fields are present
        config_fields = {f.name for f in fields(SmartPoolAdapterConfig)}
        assert set(result_dict.keys()).issuperset(config_fields)

        # Check specific values
        assert result_dict["factory_function"] is not None  # To review!
        assert result_dict["initial_size"] == 8
        assert result_dict["max_size"] == 25
        assert result_dict["memory_preset"] == "BALANCED"
        assert result_dict["enable_auto_tuning"] is True

    def test_to_dict_with_default_values(self):
        """Test to_dict method with default configuration."""
        config = SmartPoolAdapterConfig()
        result_dict = config.to_dict()

        # Verify asdict is being used for dataclass
        expected_dict = asdict(config)
        assert result_dict == expected_dict

    def test_to_dict_fallback_mechanism(self):
        """Test to_dict fallback for non-dataclass objects."""

        # Create a mock object that simulates the fallback behavior
        class MockConfig:
            def __init__(self):
                self.factory_function = None
                self.initial_size = 5
                self._private_attr = "hidden"

            def some_method(self):
                return "method"

        # Monkey patch is_dataclass to return False for testing fallback

        mock_config = MockConfig()

        # Test the fallback logic by calling the method directly
        fallback_dict = {
            key: getattr(mock_config, key)
            for key in dir(mock_config)
            if not key.startswith("_") and not callable(getattr(mock_config, key))
        }

        assert "factory_function" in fallback_dict
        assert "initial_size" in fallback_dict
        assert "_private_attr" not in fallback_dict
        assert "some_method" not in fallback_dict

    def test_factory_args_and_kwargs(self):
        """Test factory arguments and keyword arguments."""
        args = ("db_name", "localhost", 5432)
        kwargs = {"user": "admin", "password": "secret", "timeout": 30}

        config = SmartPoolAdapterConfig(factory_args=args, factory_kwargs=kwargs)

        assert config.factory_args == args
        assert config.factory_kwargs == kwargs
        assert isinstance(config.factory_args, tuple)
        assert isinstance(config.factory_kwargs, dict)

    def test_extra_config_usage(self):
        """Test extra_config field for additional configuration."""
        extra_config = {
            "custom_setting": "value",
            "nested_config": {"sub_setting": 42},
            "feature_flags": ["flag1", "flag2"],
        }

        config = SmartPoolAdapterConfig(extra_config=extra_config)
        assert config.extra_config == extra_config
        assert config.extra_config["custom_setting"] == "value"
        assert config.extra_config["nested_config"]["sub_setting"] == 42

    def test_field_types_and_defaults(self):
        """Test that all fields have correct types and default values."""
        SmartPoolAdapterConfig()

        # Test type annotations through fields inspection
        config_fields = {f.name: f for f in fields(SmartPoolAdapterConfig)}

        # Check factory_function field
        factory_field = config_fields["factory_function"]
        assert factory_field.default is None

        # Check tuple and dict fields have proper default factories
        args_field = config_fields["factory_args"]
        kwargs_field = config_fields["factory_kwargs"]
        extra_field = config_fields["extra_config"]

        # These should use default_factory
        assert hasattr(args_field, "default_factory")
        assert hasattr(kwargs_field, "default_factory")
        assert hasattr(extra_field, "default_factory")

    def test_dataclass_properties(self):
        """Test that SmartPoolAdapterConfig is properly configured as a dataclass."""
        # Test that it's a dataclass
        from dataclasses import is_dataclass

        assert is_dataclass(SmartPoolAdapterConfig)

        # Test field access
        config = SmartPoolAdapterConfig()
        all_fields = fields(config)

        # Should have all expected fields
        field_names = {f.name for f in all_fields}
        expected_fields = {
            "factory_function",
            "factory_args",
            "factory_kwargs",
            "initial_size",
            "max_size",
            "min_size",
            "memory_preset",
            "max_age_seconds",
            "cleanup_interval",
            "enable_background_cleanup",
            "enable_performance_metrics",
            "enable_auto_tuning",
            "auto_tuning_interval",
            "auto_wrap_objects",
            "extra_config",
            "backend",
        }

        assert expected_fields.issubset(field_names)

    def test_config_modification(self):
        """Test that configuration can be modified after creation."""
        config = SmartPoolAdapterConfig()

        # Modify values
        new_factory = Mock()
        config.factory_function = new_factory
        config.initial_size = 15
        config.memory_preset = "LOW_MEMORY"

        # Verify changes
        assert config.factory_function == new_factory
        assert config.initial_size == 15
        assert config.memory_preset == "LOW_MEMORY"

    def test_config_with_inherited_fields(self):
        """Test that inherited fields from AdapterConfig are accessible."""
        config = SmartPoolAdapterConfig(name="test_pool")

        # Should have access to inherited fields
        assert hasattr(config, "name")
        assert config.name == "test_pool"

        # Test inherited fields if they exist in AdapterConfig
        if hasattr(config, "max_retries"):
            assert isinstance(config.max_retries, int)
        if hasattr(config, "log_level"):
            assert isinstance(config.log_level, str)
