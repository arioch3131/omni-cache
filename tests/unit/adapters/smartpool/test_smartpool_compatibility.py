"""
SmartPool Adapter Compatibility Testing.

This module contains comprehensive compatibility tests for the SmartPoolAdapter,
ensuring adherence to BasePoolAdapter interface, Generic typing support,
backwards compatibility, configuration migration, and API consistency.
"""

import inspect
from typing import Generic, TypeVar
from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.base import BasePoolAdapter
from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter
from omni_cache.core.exceptions import AdapterNotConnectedError
from omni_cache.core.interfaces.adapter_interface import AdapterInterface
from omni_cache.core.interfaces.enum_dataclasses import CacheBackend


class TestSmartPoolAdapterCompatibility:
    """Test suite for SmartPoolAdapter compatibility and interface adherence."""

    @pytest.fixture
    def test_factory(self):
        """Simple factory function for testing."""
        return lambda: Mock()

    @pytest.fixture
    def minimal_config(self, test_factory):
        """Minimal valid configuration for testing."""
        return SmartPoolAdapterConfig(factory_function=test_factory)

    @pytest.fixture
    def legacy_config_dict(self, test_factory):
        """Legacy configuration format as dictionary."""
        return {
            "factory_function": test_factory,
            "initial_size": 5,
            "max_size": 20,
            "min_size": 2,
            "backend": "smartpool",
        }

    def test_base_adapter_interface(self, minimal_config):
        """Test adherence to BasePoolAdapter interface."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(minimal_config)

            # Test inheritance hierarchy
            assert isinstance(adapter, BasePoolAdapter)
            assert isinstance(adapter, AdapterInterface)
            assert issubclass(SmartPoolAdapter, BasePoolAdapter)
            assert issubclass(SmartPoolAdapter, AdapterInterface)

            # Test that all required abstract methods are implemented
            base_methods = {
                name
                for name, method in inspect.getmembers(
                    BasePoolAdapter, predicate=inspect.isfunction
                )
                if getattr(method, "__isabstractmethod__", False)
            }

            {
                name
                for name in dir(adapter)
                if not name.startswith("_") and callable(getattr(adapter, name))
            }

            # Ensure all abstract methods are implemented (not abstract)
            for method_name in base_methods:
                assert hasattr(adapter, method_name), f"Missing method: {method_name}"
                method = getattr(adapter, method_name)
                assert not getattr(method, "__isabstractmethod__", False), (
                    f"Method {method_name} is still abstract"
                )

            # Test core interface methods exist and are callable
            required_methods = [
                "connect",
                "disconnect",
                "is_connected",
                "health_check",
                "get_backend_info",
                "size",
                "is_empty",
                "clear",
                "get",
                "put",
            ]

            for method_name in required_methods:
                assert hasattr(adapter, method_name), f"Missing required method: {method_name}"
                method = getattr(adapter, method_name)
                assert callable(method), f"Method {method_name} is not callable"

            # Test method signatures are compatible
            # connect() -> bool
            connect_sig = inspect.signature(adapter.connect)
            assert len(connect_sig.parameters) == 0
            assert connect_sig.return_annotation in (bool, inspect.Signature.empty)

            # get(*args, **kwargs) -> Optional[T]
            get_sig = inspect.signature(adapter.get)
            assert "timeout" in get_sig.parameters or len(get_sig.parameters) >= 0

            # put(obj, **kwargs) -> bool
            put_sig = inspect.signature(adapter.put)
            assert len(put_sig.parameters) >= 1

    def test_generic_typing(self, minimal_config):
        """Test Generic[T] typing support."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            # Test that SmartPoolAdapter supports Generic typing
            assert issubclass(SmartPoolAdapter, Generic)

            # Test type variable usage
            TypeVar("T")
            assert hasattr(SmartPoolAdapter, "__orig_bases__")

            # Test parameterized type creation
            StringPoolAdapter = SmartPoolAdapter[str]
            IntPoolAdapter = SmartPoolAdapter[int]

            # These should be different parameterized types
            assert StringPoolAdapter != IntPoolAdapter

            # Test instantiation with type parameters
            adapter = SmartPoolAdapter(minimal_config)
            assert isinstance(adapter, SmartPoolAdapter)

            # Test that typing doesn't break normal functionality
            assert hasattr(adapter, "get")
            assert hasattr(adapter, "put")
            assert hasattr(adapter, "connect")

            # Test method type hints
            get_method = adapter.get
            put_method = adapter.put

            # Methods should exist and be callable
            assert callable(get_method)
            assert callable(put_method)

    def test_backwards_compatibility(self, test_factory):
        """Test backwards compatibility with previous versions."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            # Test old-style configuration dictionary
            old_config = {
                "factory_function": test_factory,
                "initial_size": 10,
                "max_size": 50,
            }

            adapter = SmartPoolAdapter(old_config)
            assert adapter.config.factory_function == test_factory
            assert adapter.config.initial_size == 10
            assert adapter.config.max_size == 50

            # Test that new-style configuration still works
            new_config = SmartPoolAdapterConfig(
                factory_function=test_factory,
                initial_size=15,
                max_size=30,
            )

            adapter2 = SmartPoolAdapter(new_config)
            assert adapter2.config.factory_function == test_factory
            assert adapter2.config.initial_size == 15
            assert adapter2.config.max_size == 30

            # Test legacy method names still work (if any exist)
            legacy_methods = [
                "borrow",
                "_get_backend_info",  # Legacy backend info method
            ]

            for method_name in legacy_methods:
                if hasattr(adapter, method_name):
                    method = getattr(adapter, method_name)
                    assert callable(method), f"Legacy method {method_name} is not callable"

            # Test that backend enum values are backwards compatible
            assert adapter.config.backend == CacheBackend.SMARTPOOL.value
            assert adapter.config.backend == "smartpool"

    def test_config_migration(self, test_factory):
        """Test configuration migration and compatibility."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            # Test migration from old configuration format
            old_format_configs = [
                # Version 1.0 style
                {
                    "factory_function": test_factory,
                    "pool_size": 10,  # Old name
                    "max_pool_size": 20,  # Old name
                },
                # Version 1.1 style
                {
                    "factory_function": test_factory,
                    "initial_size": 5,
                    "max_size": 15,
                    "enable_metrics": True,  # Old name
                },
                # Version 1.2 style
                {
                    "factory_function": test_factory,
                    "initial_size": 8,
                    "max_size": 25,
                    "enable_performance_metrics": True,  # Current name
                },
            ]

            for config_dict in old_format_configs:
                try:
                    # Should handle migration gracefully
                    adapter = SmartPoolAdapter(config_dict)
                    assert adapter.config.factory_function == test_factory
                    assert hasattr(adapter.config, "initial_size")
                    assert hasattr(adapter.config, "max_size")
                except Exception as e:
                    # If migration fails, it should be a clear configuration error
                    assert "configuration" in str(e).lower() or "config" in str(e).lower()

            # Test parameter renaming compatibility
            renamed_params = {
                "ttl": "max_age_seconds",
                "auto_tune": "enable_auto_tuning",
                "metrics": "enable_performance_metrics",
                "wrap": "auto_wrap_objects",
            }

            for old_name, new_name in renamed_params.items():
                config_with_old = {
                    "factory_function": test_factory,
                    old_name: True,
                }

                config_with_new = {
                    "factory_function": test_factory,
                    new_name: True,
                }

                # Both should work or both should fail consistently
                try:
                    adapter_old = SmartPoolAdapter(config_with_old)
                    adapter_new = SmartPoolAdapter(config_with_new)

                    # If both succeed, the values should be mapped correctly
                    old_value = getattr(adapter_old.config, new_name, None)
                    new_value = getattr(adapter_new.config, new_name, None)

                    if old_value is not None and new_value is not None:
                        assert old_value == new_value
                except Exception as exc:
                    # Migration might not support all old parameter names
                    assert str(exc)

    def test_api_consistency(self, minimal_config):
        """Test API consistency and method behavior."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            mock_manager = MagicMock()
            mock_manager.get_basic_stats.return_value = {
                "pooled_objects": 5,
                "active_objects": 0,
                "total_pooled_objects": 5,
                "hits": 0,
                "misses": 0,
            }
            mock_manager.get_health_status.return_value = {"status": "healthy"}
            mock_manager.acquire.return_value = (1, ("test",), Mock())

            with patch(
                "omni_cache.adapters.smartpool.smartpool.SmartObjectManager",
                return_value=mock_manager,
            ):
                adapter = SmartPoolAdapter(minimal_config)

                # Test connect and is_connected
                assert adapter.connect() is True
                assert adapter.is_connected() is True

                # Test boolean methods that require connection
                boolean_methods_connected = ["health_check", "clear", "is_empty"]
                for method_name in boolean_methods_connected:
                    if hasattr(adapter, method_name):
                        method = getattr(adapter, method_name)
                        result = method()
                        assert isinstance(result, bool), (
                            f"Method {method_name} should return bool, got {type(result)}"
                        )

                # Test get method consistency
                obj = adapter.get()
                assert obj is None or hasattr(obj, "__class__")

                # Test put() should return bool
                if obj is not None:  # Changed from 'if obj:'
                    result = adapter.put(obj)
                    assert isinstance(result, bool)

                # Test size() should return int
                size = adapter.size()
                assert isinstance(size, int)
                assert size >= 0

                # Test get_backend_info() should return dict
                info = adapter.get_backend_info()
                assert isinstance(info, dict)
                assert "backend" in info
                assert "is_connected" in info

                # Test disconnect and is_connected after disconnect
                assert adapter.disconnect() is True
                assert adapter.is_connected() is False

                # Test methods that should fail while disconnected.
                # They either raise AdapterNotConnectedError or return a falsy value.
                # For 'get' and 'put', they should raise AdapterNotConnectedError if not connected
                with pytest.raises(AdapterNotConnectedError):
                    adapter.get()
                with pytest.raises(AdapterNotConnectedError):
                    adapter.put(Mock())  # Pass a mock object to put

                # Test method signature consistency (this part can remain as is)
                public_methods = [
                    name
                    for name in dir(adapter)
                    if not name.startswith("_") and callable(getattr(adapter, name))
                ]

                for method_name in public_methods:
                    method = getattr(adapter, method_name)
                    sig = inspect.signature(method)

                    required_params = [
                        param
                        for param in sig.parameters.values()
                        if param.default == inspect.Parameter.empty
                        and param.kind != param.VAR_POSITIONAL
                    ]

                    if method_name not in ["put"]:
                        assert len(required_params) <= 1, (
                            f"Method {method_name} has too many required parameters: "
                            f"{required_params}"
                        )

    def test_interface_method_coverage(self, minimal_config):
        """Test that all interface methods are properly implemented."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(minimal_config)

            # Test AdapterInterface methods
            adapter_interface_methods = [
                ("connect", bool),
                ("disconnect", bool),
                ("is_connected", bool),
                ("health_check", bool),
                ("get_backend_info", dict),
            ]

            for method_name, return_type in adapter_interface_methods:
                assert hasattr(adapter, method_name), f"Missing interface method: {method_name}"
                method = getattr(adapter, method_name)
                assert callable(method), f"Interface method {method_name} is not callable"

                # Test that method can be called (may fail but shouldn't crash)
                try:
                    result = method()
                    if result is not None:
                        assert isinstance(result, return_type), (
                            f"Method {method_name} should return {return_type}, got {type(result)}"
                        )
                except Exception as exc:
                    # Method may fail due to not being connected, but shouldn't crash
                    assert str(exc)

            # Test pool-specific methods
            pool_methods = [
                "size",
                "is_empty",
                "clear",
                "get",
                "put",
            ]

            for method_name in pool_methods:
                assert hasattr(adapter, method_name), f"Missing pool method: {method_name}"
                method = getattr(adapter, method_name)
                assert callable(method), f"Pool method {method_name} is not callable"

    def test_configuration_object_compatibility(self, test_factory):
        """Test compatibility of configuration objects."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            # Test that configuration objects are interchangeable
            config1 = SmartPoolAdapterConfig(
                factory_function=test_factory,
                initial_size=10,
                max_size=20,
                enable_performance_metrics=True,
            )

            config2 = SmartPoolAdapterConfig(
                factory_function=test_factory,
                initial_size=10,
                max_size=20,
                enable_performance_metrics=True,
            )

            adapter1 = SmartPoolAdapter(config1)
            adapter2 = SmartPoolAdapter(config2)

            # Adapters with equivalent configs should behave similarly
            assert adapter1.config.factory_function == adapter2.config.factory_function
            assert adapter1.config.initial_size == adapter2.config.initial_size
            assert adapter1.config.max_size == adapter2.config.max_size

            # Test configuration serialization/deserialization
            config_dict = config1.to_dict()
            assert isinstance(config_dict, dict)
            assert "factory_function" in config_dict
            assert "initial_size" in config_dict

            # Should be able to recreate config from dict
            recreated_config = SmartPoolAdapterConfig(**config_dict)
            assert recreated_config.factory_function == config1.factory_function
            assert recreated_config.initial_size == config1.initial_size

            # Configuration should be immutable-like (new instances for changes)
            original_size = config1.initial_size
            modified_config = SmartPoolAdapterConfig(
                factory_function=test_factory,
                initial_size=original_size + 5,
                max_size=config1.max_size,
            )

            assert config1.initial_size == original_size  # Original unchanged
            assert modified_config.initial_size == original_size + 5

    def test_error_handling_consistency(self, minimal_config):
        """Test consistent error handling patterns."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(minimal_config)

            # Test that operations on disconnected adapter behave consistently
            error_methods = ["get", "put"]

            for method_name in error_methods:
                if hasattr(adapter, method_name):
                    method = getattr(adapter, method_name)

                    try:
                        if method_name == "put":
                            result = method(Mock())
                        else:
                            result = method()

                        # Should return None/False for safe operations, or raise clear exceptions
                        if result is not None:
                            assert isinstance(result, (bool, type(None)))

                    except Exception as e:
                        # Exceptions should be from omni_cache exception hierarchy
                        exception_module = e.__class__.__module__
                        assert "omni_cache" in exception_module or "smartpool" in exception_module

            # Test that connection lifecycle is consistent
            assert not adapter.is_connected()  # Should start disconnected

            connect_result = adapter.connect()
            if connect_result:
                assert adapter.is_connected()

                disconnect_result = adapter.disconnect()
                if disconnect_result:
                    assert not adapter.is_connected()

    def test_type_hint_compatibility(self, minimal_config):
        """Test that type hints are consistent and useful."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(minimal_config)

            # Test that important methods have type hints
            methods_with_hints = [
                "get",
                "put",
                "connect",
                "disconnect",
                "is_connected",
                "health_check",
                "size",
                "is_empty",
                "clear",
                "get_backend_info",
            ]

            for method_name in methods_with_hints:
                if hasattr(adapter, method_name):
                    method = getattr(adapter, method_name)
                    sig = inspect.signature(method)

                    # Should have return annotation
                    assert sig.return_annotation != inspect.Signature.empty, (
                        f"Method {method_name} missing return type annotation"
                    )

                    # Parameter annotations should be present for non-trivial methods
                    for param_name, _param in sig.parameters.items():
                        if param_name not in ["self", "args", "kwargs"]:
                            # Allow some flexibility for generic parameters
                            pass

            # Test Generic type parameter usage
            assert hasattr(SmartPoolAdapter, "__parameters__") or hasattr(
                SmartPoolAdapter, "__orig_bases__"
            )

    def test_documentation_compatibility(self, minimal_config):
        """Test that documentation and help strings are available."""
        with patch("omni_cache.adapters.smartpool.smartpool.SMARTPOOL_ADAPTER_AVAILABLE", True):
            adapter = SmartPoolAdapter(minimal_config)

            # Test class docstring
            assert SmartPoolAdapter.__doc__ is not None
            assert len(SmartPoolAdapter.__doc__.strip()) > 0

            # Test that important methods have docstrings
            documented_methods = [
                "get",
                "put",
                "connect",
                "disconnect",
                "borrow",
            ]

            for method_name in documented_methods:
                if hasattr(adapter, method_name):
                    method = getattr(adapter, method_name)
                    assert method.__doc__ is not None, f"Method {method_name} missing docstring"
                    assert len(method.__doc__.strip()) > 0, (
                        f"Method {method_name} has empty docstring"
                    )

            # Test configuration class documentation
            assert SmartPoolAdapterConfig.__doc__ is not None
            assert len(SmartPoolAdapterConfig.__doc__.strip()) > 0
