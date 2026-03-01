"""
SmartPool Adapter Configuration Integration Testing.

This module contains integration tests for how the SmartPoolAdapter uses the
SmartPoolAdapterConfig. It verifies that the adapter correctly initializes
its internal components based on the provided configuration.
"""

from unittest.mock import Mock, patch

from smartpool import MemoryPressure, ObjectCreationCost

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.factory_smartpool import SimpleSmartPoolFactory
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter

# Mock SmartPool classes if not available
try:
    from smartpool import MemoryConfig, PoolConfiguration, SmartObjectManager

    SMARTPOOL_AVAILABLE = True
except ImportError:
    SMARTPOOL_AVAILABLE = False
    MemoryConfig = Mock
    PoolConfiguration = Mock
    SmartObjectManager = Mock


class TestSmartPoolAdapterConfigurationIntegration:
    """Test suite for SmartPoolAdapter and SmartPoolAdapterConfig integration."""

    def test_create_memory_config(self):
        """Test creation of MemoryConfig for SmartPool."""

        # Create adapter with specific configuration
        def test_factory():
            return Mock()

        config = SmartPoolAdapterConfig(
            factory_function=test_factory,
            max_size=50,
            max_age_seconds=600,
            cleanup_interval=60,
            enable_background_cleanup=True,
            enable_performance_metrics=True,
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch(
                "omni_cache.adapters.smartpool.smartpool.MemoryConfig"
            ) as mock_memory_config:
                adapter = SmartPoolAdapter(config)

                # Test _create_memory_config method
                adapter._create_memory_config()

                # Verify MemoryConfig was called with correct parameters
                mock_memory_config.assert_called_once_with(
                    max_objects_per_key=50,
                    ttl_seconds=600,
                    cleanup_interval_seconds=60,
                    enable_background_cleanup=True,
                    enable_performance_metrics=True,
                    enable_logging=False,  # Should be disabled for SmartPool logs
                    max_validation_attempts=1,
                    max_corrupted_objects=3,
                    enable_acquisition_tracking=True,
                    enable_lock_contention_tracking=True,
                    max_performance_history_size=100,
                    max_expected_concurrency=10,
                    object_creation_cost=ObjectCreationCost.LOW,
                    memory_pressure=MemoryPressure.LOW,
                )

    def test_create_pool_config(self):
        """Test creation of PoolConfiguration for SmartPool."""

        def test_factory():
            return Mock()

        config = SmartPoolAdapterConfig(
            factory_function=test_factory,
            max_size=30,
            enable_performance_metrics=True,
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch(
                "omni_cache.adapters.smartpool.smartpool.PoolConfiguration"
            ) as mock_pool_config:
                adapter = SmartPoolAdapter(config)

                # Test _create_pool_config method
                adapter._create_pool_config()

                # Verify PoolConfiguration was called with correct parameters
                mock_pool_config.assert_called_once_with(
                    max_total_objects=30,
                    enable_monitoring=True,
                    register_atexit=False,
                )

    def test_create_factory(self):
        """Test creation of SimpleSmartPoolFactory."""

        def test_factory(param1, param2="default"):
            return Mock(param1=param1, param2=param2)

        def reset_func(obj):
            obj.reset_called = True

        def validate_func(obj):
            return hasattr(obj, "param1")

        def destroy_func(obj):
            obj.destroyed = True

        config = SmartPoolAdapterConfig(
            factory_function=test_factory,
            factory_args=("arg1",),
            factory_kwargs={"param2": "custom"},
            auto_wrap_objects=True,
            extra_config={
                "reset_func": reset_func,
                "validate_func": validate_func,
                "destroy_func": destroy_func,
            },
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(config)

            # Test _create_factory method
            factory = adapter._create_factory()

            # Verify factory is of correct type
            assert isinstance(factory, SimpleSmartPoolFactory)

            # Verify factory configuration
            assert factory.factory_func == test_factory
            assert factory.factory_args == ("arg1",)
            assert factory.factory_kwargs == {"param2": "custom"}
            assert factory.auto_wrap is True
            assert factory.reset_func == reset_func
            assert factory.validate_func == validate_func
            assert factory.destroy_func == destroy_func

    def test_config_validation_with_adapter_creation(self):
        """Test configuration validation during adapter creation."""

        def test_factory():
            return Mock()

        # Valid configuration should create adapter successfully
        valid_config = SmartPoolAdapterConfig(
            factory_function=test_factory,
            initial_size=5,
            max_size=10,
            min_size=2,
        )

        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            with patch("omni_cache.adapters.smartpool.smartpool.SmartObjectManager"):
                adapter = SmartPoolAdapter(valid_config)
                assert adapter.config == valid_config
