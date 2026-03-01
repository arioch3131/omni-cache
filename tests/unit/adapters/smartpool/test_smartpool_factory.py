"""
Tests for SimpleSmartPoolFactory class.

This module contains comprehensive tests for the SimpleSmartPoolFactory class,
covering all methods, error cases, and edge cases.
"""

from unittest.mock import Mock, patch

import pytest

from omni_cache.adapters.smartpool.factory_smartpool import SimpleSmartPoolFactory
from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper


class TestSimpleSmartPoolFactory:
    """Test cases for SimpleSmartPoolFactory class."""

    @pytest.fixture
    def mock_factory_function(self):
        """Mock factory function that returns a simple object."""
        return Mock(return_value={"data": "test_object"})

    @pytest.fixture
    def basic_factory(self, mock_factory_function):
        """Basic factory instance for testing."""
        return SimpleSmartPoolFactory(factory_func=mock_factory_function)

    def test_init_with_defaults(self, mock_factory_function):
        """Test initialization with default parameters."""
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function)

        assert factory.factory_func == mock_factory_function
        assert factory.factory_args == ()
        assert factory.factory_kwargs == {}
        assert factory.auto_wrap is True
        assert factory.reset_func is None
        assert factory.validate_func is None
        assert factory.destroy_func is None
        assert factory._logger is not None

    def test_init_with_custom_parameters(self, mock_factory_function):
        """Test initialization with custom parameters."""
        reset_func = Mock()
        validate_func = Mock()
        destroy_func = Mock()
        factory_args = ("arg1", "arg2")
        factory_kwargs = {"key1": "value1", "key2": "value2"}

        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function,
            factory_args=factory_args,
            factory_kwargs=factory_kwargs,
            auto_wrap=False,
            reset_func=reset_func,
            validate_func=validate_func,
            destroy_func=destroy_func,
        )

        assert factory.factory_func == mock_factory_function
        assert factory.factory_args == factory_args
        assert factory.factory_kwargs == factory_kwargs
        assert factory.auto_wrap is False
        assert factory.reset_func == reset_func
        assert factory.validate_func == validate_func
        assert factory.destroy_func == destroy_func

    def test_init_with_none_kwargs(self, mock_factory_function):
        """Test initialization with None factory_kwargs."""
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, factory_kwargs=None)
        assert factory.factory_kwargs == {}

    def test_create_object_with_auto_wrap_enabled(self, mock_factory_function):
        """Test create_object with auto_wrap enabled."""
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, auto_wrap=True)

        obj = factory.create_object()

        mock_factory_function.assert_called_once_with()
        assert isinstance(obj, AutoWeakRefWrapper)

    def test_create_object_with_auto_wrap_disabled(self, mock_factory_function):
        """Test create_object with auto_wrap disabled."""
        expected_obj = {"data": "test_object"}
        mock_factory_function.return_value = expected_obj

        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, auto_wrap=False)

        obj = factory.create_object()

        mock_factory_function.assert_called_once_with()
        assert obj == expected_obj
        assert not isinstance(obj, AutoWeakRefWrapper)

    def test_create_object_already_wrapped(self, mock_factory_function):
        """Test create_object when factory returns already wrapped object."""
        wrapped_obj = AutoWeakRefWrapper({"data": "test"})
        mock_factory_function.return_value = wrapped_obj

        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, auto_wrap=True)

        obj = factory.create_object()

        mock_factory_function.assert_called_once_with()
        assert obj == wrapped_obj  # Should not double-wrap

    def test_create_object_with_class_args_kwargs(self, mock_factory_function):
        """Test create_object using class-level args and kwargs."""
        factory_args = ("class_arg1", "class_arg2")
        factory_kwargs = {"class_key": "class_value"}

        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function,
            factory_args=factory_args,
            factory_kwargs=factory_kwargs,
            auto_wrap=False,
        )

        factory.create_object()

        mock_factory_function.assert_called_once_with(
            "class_arg1", "class_arg2", class_key="class_value"
        )

    def test_create_object_with_override_args_kwargs(self, mock_factory_function):
        """Test create_object with method-level args and kwargs override."""
        factory_args = ("class_arg",)
        factory_kwargs = {"class_key": "class_value"}

        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function,
            factory_args=factory_args,
            factory_kwargs=factory_kwargs,
            auto_wrap=False,
        )

        # Override with method arguments
        factory.create_object("method_arg", method_key="method_value")

        mock_factory_function.assert_called_once_with(
            "method_arg", class_key="class_value", method_key="method_value"
        )

    @patch("omni_cache.adapters.smartpool.factory_smartpool.logging.getLogger")
    def test_create_object_exception_handling(self, mock_get_logger, mock_factory_function):
        """Test create_object exception handling and logging."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # Make factory_func raise an exception
        expected_error = ValueError("Factory function failed")
        mock_factory_function.side_effect = expected_error

        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function)
        factory._logger = mock_logger

        with pytest.raises(ValueError, match="Factory function failed"):
            factory.create_object()

        mock_logger.error.assert_called_once_with("Object creation failed: %s", expected_error)

    def test_create_interface_method(self, basic_factory):
        """Test create method (ObjectFactory interface)."""
        result = basic_factory.create("arg1", key="value")

        basic_factory.factory_func.assert_called_once_with("arg1", key="value")
        assert isinstance(result, AutoWeakRefWrapper)

    def test_reset_with_reset_func(self, mock_factory_function):
        """Test reset method with reset_func provided."""
        reset_func = Mock()
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, reset_func=reset_func)

        # Test with regular object
        test_obj = {"data": "test"}
        result = factory.reset(test_obj)

        assert result is True
        reset_func.assert_called_once_with(test_obj)

    def test_reset_with_wrapped_object(self, mock_factory_function):
        """Test reset method with wrapped object."""
        reset_func = Mock()
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, reset_func=reset_func)

        # Test with wrapped object
        wrapped_obj = Mock()
        wrapped_obj._obj = {"data": "wrapped_test"}

        result = factory.reset(wrapped_obj)

        assert result is True
        reset_func.assert_called_once_with(wrapped_obj._obj)

    def test_reset_without_reset_func(self, basic_factory):
        """Test reset method without reset_func."""
        test_obj = {"data": "test"}
        result = basic_factory.reset(test_obj)

        assert result is True

    @patch("omni_cache.adapters.smartpool.factory_smartpool.logging.getLogger")
    def test_reset_exception_handling(self, mock_get_logger, mock_factory_function):
        """Test reset method exception handling."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        reset_func = Mock(side_effect=Exception("Reset failed"))
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function, reset_func=reset_func)
        factory._logger = mock_logger

        result = factory.reset({"data": "test"})

        assert result is False
        mock_logger.warning.assert_called_once()

    def test_validate_with_validate_func(self, mock_factory_function):
        """Test validate method with validate_func provided."""
        validate_func = Mock(return_value=True)
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, validate_func=validate_func
        )

        test_obj = {"data": "test"}
        result = factory.validate(test_obj)

        assert result is True
        validate_func.assert_called_once_with(test_obj)

    def test_validate_with_wrapped_object(self, mock_factory_function):
        """Test validate method with wrapped object."""
        validate_func = Mock(return_value=False)
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, validate_func=validate_func
        )

        wrapped_obj = Mock()
        wrapped_obj._obj = {"data": "wrapped_test"}

        result = factory.validate(wrapped_obj)

        assert result is False
        validate_func.assert_called_once_with(wrapped_obj._obj)

    def test_validate_without_validate_func(self, basic_factory):
        """Test validate method without validate_func."""
        test_obj = {"data": "test"}
        result = basic_factory.validate(test_obj)

        assert result is True

    @patch("omni_cache.adapters.smartpool.factory_smartpool.logging.getLogger")
    def test_validate_exception_handling(self, mock_get_logger, mock_factory_function):
        """Test validate method exception handling."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        validate_func = Mock(side_effect=Exception("Validation failed"))
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, validate_func=validate_func
        )
        factory._logger = mock_logger

        result = factory.validate({"data": "test"})

        assert result is False
        mock_logger.warning.assert_called_once()

    def test_destroy_with_destroy_func(self, mock_factory_function):
        """Test destroy method with destroy_func provided."""
        destroy_func = Mock()
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, destroy_func=destroy_func
        )

        test_obj = {"data": "test"}
        factory.destroy(test_obj)

        destroy_func.assert_called_once_with(test_obj)

    def test_destroy_with_wrapped_object(self, mock_factory_function):
        """Test destroy method with wrapped object."""
        destroy_func = Mock()
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, destroy_func=destroy_func
        )

        wrapped_obj = Mock()
        wrapped_obj._obj = {"data": "wrapped_test"}

        factory.destroy(wrapped_obj)

        destroy_func.assert_called_once_with(wrapped_obj._obj)

    def test_destroy_without_destroy_func(self, basic_factory):
        """Test destroy method without destroy_func."""
        test_obj = {"data": "test"}
        # Should not raise any exception
        basic_factory.destroy(test_obj)

    @patch("omni_cache.adapters.smartpool.factory_smartpool.logging.getLogger")
    def test_destroy_exception_handling(self, mock_get_logger, mock_factory_function):
        """Test destroy method exception handling."""
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        destroy_func = Mock(side_effect=Exception("Destroy failed"))
        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function, destroy_func=destroy_func
        )
        factory._logger = mock_logger

        factory.destroy({"data": "test"})

        mock_logger.warning.assert_called_once()

    def test_get_key_with_no_args(self, basic_factory):
        """Test get_key with no arguments."""
        key = basic_factory.get_key()
        assert key == "default_pool_key"

    def test_get_key_with_args_only(self, basic_factory):
        """Test get_key with positional arguments only."""
        key = basic_factory.get_key("arg1", "arg2", 123)
        assert key == "arg1_arg2_123"

    def test_get_key_with_kwargs_only(self, basic_factory):
        """Test get_key with keyword arguments only."""
        key = basic_factory.get_key(key1="value1", key2="value2")
        assert key == "key1=value1_key2=value2"

    def test_get_key_with_args_and_kwargs(self, basic_factory):
        """Test get_key with both positional and keyword arguments."""
        key = basic_factory.get_key("arg1", "arg2", key1="value1", key2="value2")
        assert key == "arg1_arg2_key1=value1_key2=value2"

    def test_get_key_kwargs_sorted(self, basic_factory):
        """Test get_key ensures kwargs are sorted for consistency."""
        key1 = basic_factory.get_key(z="z_value", a="a_value", m="m_value")
        key2 = basic_factory.get_key(a="a_value", m="m_value", z="z_value")
        assert key1 == key2 == "a=a_value_m=m_value_z=z_value"

    def test_estimate_size_regular_object(self, basic_factory):
        """Test estimate_size with regular object."""
        test_obj = {"data": "test", "number": 42}

        with patch("sys.getsizeof", return_value=1024) as mock_getsizeof:
            size = basic_factory.estimate_size(test_obj)

            assert size == 1024
            mock_getsizeof.assert_called_once_with(test_obj)

    def test_estimate_size_wrapped_object(self, basic_factory):
        """Test estimate_size with wrapped object."""
        wrapped_obj = Mock()
        wrapped_obj._obj = {"data": "wrapped_test"}

        with patch("sys.getsizeof", return_value=2048) as mock_getsizeof:
            size = basic_factory.estimate_size(wrapped_obj)

            assert size == 2048
            mock_getsizeof.assert_called_once_with(wrapped_obj._obj)

    def test_estimate_size_exception_handling(self, basic_factory):
        """Test estimate_size exception handling."""
        test_obj = {"data": "test"}

        with patch("sys.getsizeof", side_effect=Exception("Size calculation failed")):
            size = basic_factory.estimate_size(test_obj)

            assert size == 1024  # Default estimate

    def test_estimate_size_object_without_obj_attr(self, basic_factory):
        """Test estimate_size with object that doesn't have _obj attribute."""
        test_obj = "simple_string"

        with patch("sys.getsizeof", return_value=512) as mock_getsizeof:
            size = basic_factory.estimate_size(test_obj)

            assert size == 512
            mock_getsizeof.assert_called_once_with(test_obj)

    def test_logger_initialization(self, mock_factory_function):
        """Test logger is properly initialized."""
        factory = SimpleSmartPoolFactory(factory_func=mock_factory_function)

        expected_logger_name = f"{factory.__module__}.{factory.__class__.__name__}"
        assert factory._logger.name == expected_logger_name

    def test_inheritance_from_object_factory(self, basic_factory):
        """Test that SimpleSmartPoolFactory inherits from ObjectFactory."""
        from smartpool import ObjectFactory

        assert isinstance(basic_factory, ObjectFactory)

    def test_full_workflow_integration(self, mock_factory_function):
        """Test full workflow integration with all features enabled."""
        reset_func = Mock()
        validate_func = Mock(return_value=True)
        destroy_func = Mock()

        factory = SimpleSmartPoolFactory(
            factory_func=mock_factory_function,
            factory_args=("test_arg",),
            factory_kwargs={"test_key": "test_value"},
            auto_wrap=True,
            reset_func=reset_func,
            validate_func=validate_func,
            destroy_func=destroy_func,
        )

        # Create object
        obj = factory.create("override_arg", override_key="override_value")
        assert isinstance(obj, AutoWeakRefWrapper)
        mock_factory_function.assert_called_with(
            "override_arg", test_key="test_value", override_key="override_value"
        )

        # Validate object
        assert factory.validate(obj) is True
        validate_func.assert_called_once()

        # Reset object
        assert factory.reset(obj) is True
        reset_func.assert_called_once()

        # Get key
        key = factory.get_key("key_arg", key_kwarg="key_value")
        assert "key_arg" in key
        assert "key_kwarg=key_value" in key

        # Estimate size
        size = factory.estimate_size(obj)
        assert isinstance(size, int)
        assert size > 0

        # Destroy object
        factory.destroy(obj)
        destroy_func.assert_called_once()
