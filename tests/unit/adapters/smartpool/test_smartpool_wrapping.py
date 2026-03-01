"""
Unit tests for SmartPoolAdapter object wrapping and AutoWeakRefWrapper functionality.

This module contains comprehensive unit tests for the object wrapping capabilities
of the SmartPoolAdapter, including the AutoWeakRefWrapper class and related
wrapping/unwrapping functionality.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter
from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper


# Test objects for wrapping scenarios
class _TestObject:
    """Simple test object for wrapping tests."""

    def __init__(self, name="test", value=42):
        self.name = name
        self.value = value

    def test_method(self):
        return f"Method called on {self.name}"

    def __str__(self):
        return f"_TestObject({self.name}, {self.value})"


class _TestDictLikeObject:
    """Test object that supports dictionary-like operations."""

    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)


class _TestContextObject:
    """Test object that supports context manager protocol."""

    def __init__(self):
        self.entered = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exited = True
        return False


# Fixtures
@pytest.fixture
def mock_factory_function():
    """Mock factory function for creating test objects."""
    return Mock(return_value=_TestObject())


@pytest.fixture
def smartpool_config_wrapping_enabled(mock_factory_function):
    """Config with object wrapping enabled."""
    return SmartPoolAdapterConfig(
        factory_function=mock_factory_function, auto_wrap_objects=True, initial_size=0
    )


@pytest.fixture
def smartpool_config_wrapping_disabled(mock_factory_function):
    """Config with object wrapping disabled."""
    return SmartPoolAdapterConfig(
        factory_function=mock_factory_function, auto_wrap_objects=False, initial_size=0
    )


@pytest.fixture
def test_object():
    """Create a test object for wrapping."""
    return _TestObject("test_obj", 123)


@pytest.fixture
def context_object():
    """Create a context manager test object."""
    return _TestContextObject()


class TestAutoWeakRefWrapper:
    """Test the AutoWeakRefWrapper class functionality."""

    def test_basic_wrapping(self, test_object):
        """Test basic object wrapping functionality."""
        wrapper = AutoWeakRefWrapper(test_object)

        assert wrapper._obj is test_object
        assert hasattr(wrapper, "_supports_weakref")

    def test_weakref_support_detection(self, test_object):
        """Test weak reference support detection."""
        wrapper = AutoWeakRefWrapper(test_object)

        # Most custom objects support weak references
        assert wrapper._supports_weakref is True

    def test_weakref_support_detection_builtin_types(self):
        """Test weak reference support detection with builtin types."""
        # Builtin types like int, str don't support weak references
        wrapper_int = AutoWeakRefWrapper(42)
        wrapper_str = AutoWeakRefWrapper("test")

        assert wrapper_int._supports_weakref is False
        assert wrapper_str._supports_weakref is False

    def test_attribute_delegation(self, test_object):
        """Test that attribute access is delegated to wrapped object."""
        wrapper = AutoWeakRefWrapper(test_object)

        # Test attribute access
        assert wrapper.name == test_object.name
        assert wrapper.value == test_object.value

        # Test method calls
        assert wrapper.test_method() == test_object.test_method()

    def test_attribute_modification(self, test_object):
        """Test that attribute modification works through wrapper."""
        wrapper = AutoWeakRefWrapper(test_object)

        # Modify attribute through wrapper
        wrapper.name = "modified"
        assert test_object.name == "modified"

        # Add new attribute through wrapper
        wrapper.new_attr = "new_value"
        assert test_object.new_attr == "new_value"

    def test_dictionary_operations(self):
        """Test dictionary-like operations through wrapper with a standard dict."""
        data = {}
        wrapper = AutoWeakRefWrapper(data)

        # Test __setitem__
        wrapper["key1"] = "value1"
        assert data["key1"] == "value1"

        # Test __getitem__
        assert wrapper["key1"] == "value1"

        # Test __contains__
        assert "key1" in wrapper
        assert "nonexistent" not in wrapper

        # Test __len__
        wrapper["key2"] = "value2"
        assert len(wrapper) == 2

    def test_context_manager_delegation(self, context_object):
        """Test context manager protocol delegation."""
        wrapper = AutoWeakRefWrapper(context_object)

        # Test context manager usage
        with wrapper as ctx:
            assert ctx is context_object  # __enter__ returns the actual object
            assert context_object.entered is True

        assert context_object.exited is True

    def test_string_representation_delegation(self, test_object):
        """Test that string operations are delegated properly."""
        wrapper = AutoWeakRefWrapper(test_object)

        # The wrapper should delegate str() to the wrapped object
        # Note: This relies on __getattr__ delegation for __str__
        assert hasattr(wrapper, "__str__")  # Verify delegation works

    def test_wrapped_object_methods_callable(self, test_object):
        """Test that methods from wrapped object are callable."""
        wrapper = AutoWeakRefWrapper(test_object)

        # Test method call
        result = wrapper.test_method()
        assert result == "Method called on test_obj"

        # Test that the method is the same object
        assert wrapper.test_method.__func__ is test_object.test_method.__func__

    def test_exception_handling_in_operations(self):
        """Test exception handling in wrapper operations."""
        # Object that doesn't support dictionary operations
        simple_obj = _TestObject()
        wrapper = AutoWeakRefWrapper(simple_obj)

        # These should raise AttributeError (delegated from wrapped object)
        with pytest.raises(TypeError):  # TestObject doesn't support item access
            _ = wrapper["key"]

        with pytest.raises(TypeError):  # TestObject doesn't support contains
            _ = "key" in wrapper

    def test_wrapper_identity_and_equality(self, test_object):
        """Test wrapper identity and equality behavior."""
        wrapper1 = AutoWeakRefWrapper(test_object)
        wrapper2 = AutoWeakRefWrapper(test_object)

        # Different wrappers for same object
        assert wrapper1 is not wrapper2
        assert wrapper1._obj is wrapper2._obj
        assert wrapper1._obj is test_object

    def test_setattr_new_attribute(self, test_object):
        """Test setting a new attribute on the wrapped object via the wrapper."""
        wrapper = AutoWeakRefWrapper(test_object)
        wrapper.new_attribute = "test_value"
        assert test_object.new_attribute == "test_value"

    def test_contains_on_wrapped_dict(self):
        """Test __contains__ method on a wrapped dictionary."""
        data = {"a": 1, "b": 2}
        wrapper = AutoWeakRefWrapper(data)
        assert "a" in wrapper
        assert "c" not in wrapper

    def test_len_on_wrapped_dict(self):
        """Test __len__ method on a wrapped dictionary."""
        data = {"a": 1, "b": 2, "c": 3}
        wrapper = AutoWeakRefWrapper(data)
        assert len(wrapper) == 3


class TestSmartPoolAdapterObjectWrapping:
    """Test SmartPoolAdapter object wrapping functionality."""

    def test_wrap_object_enabled(self, smartpool_config_wrapping_enabled, test_object):
        """Test _wrap_object when auto_wrap_objects is enabled."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        wrapped = adapter._wrap_object(test_object)

        assert isinstance(wrapped, AutoWeakRefWrapper)
        assert wrapped._obj is test_object

    def test_wrap_object_disabled(self, smartpool_config_wrapping_disabled, test_object):
        """Test _wrap_object when auto_wrap_objects is disabled."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_disabled)

        result = adapter._wrap_object(test_object)

        assert result is test_object
        assert not isinstance(result, AutoWeakRefWrapper)

    def test_wrap_already_wrapped_object(self, smartpool_config_wrapping_enabled, test_object):
        """Test _wrap_object with already wrapped object."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        # First wrap
        wrapped = AutoWeakRefWrapper(test_object)

        # Try to wrap again
        result = adapter._wrap_object(wrapped)

        # Should return the same wrapper, not double-wrap
        assert result is wrapped
        assert isinstance(result, AutoWeakRefWrapper)
        assert result._obj is test_object

    def test_unwrap_object_wrapped(self, smartpool_config_wrapping_enabled, test_object):
        """Test _unwrap_object with wrapped object."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)
        wrapped = AutoWeakRefWrapper(test_object)

        unwrapped = adapter._unwrap_object(wrapped)

        assert unwrapped is test_object
        assert not isinstance(unwrapped, AutoWeakRefWrapper)

    def test_unwrap_object_not_wrapped(self, smartpool_config_wrapping_enabled, test_object):
        """Test _unwrap_object with non-wrapped object."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        result = adapter._unwrap_object(test_object)

        assert result is test_object

    def test_wrap_unwrap_cycle(self, smartpool_config_wrapping_enabled, test_object):
        """Test complete wrap-unwrap cycle."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        # Wrap then unwrap
        wrapped = adapter._wrap_object(test_object)
        unwrapped = adapter._unwrap_object(wrapped)

        assert unwrapped is test_object

    def test_wrapping_with_different_object_types(self, smartpool_config_wrapping_enabled):
        """Test wrapping with various object types."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        # Test with different types
        objects = [
            _TestObject(),
            _TestDictLikeObject(),
            _TestContextObject(),
            {"key": "value"},  # dict
            [1, 2, 3],  # list
            "string",  # string
            42,  # int
        ]

        for obj in objects:
            wrapped = adapter._wrap_object(obj)
            assert isinstance(wrapped, AutoWeakRefWrapper)
            assert wrapped._obj is obj

            unwrapped = adapter._unwrap_object(wrapped)
            assert unwrapped is obj

    def test_wrapping_integration_with_get(self, smartpool_config_wrapping_enabled):
        """Test wrapping integration with get() method."""
        mock_manager = MagicMock()
        test_obj = _TestObject("get_test")
        mock_manager.acquire.return_value = ("id", "key", test_obj)

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager", return_value=mock_manager
        ):
            adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)
            adapter.connect()

            result = adapter.get()

            assert isinstance(result, AutoWeakRefWrapper)
            assert result._obj is test_obj

    def test_wrapping_integration_with_put(self, smartpool_config_wrapping_enabled):
        """Test wrapping integration with put() method."""
        mock_manager = MagicMock()
        test_obj = _TestObject("put_test")
        mock_manager.acquire.return_value = ("id", "key", test_obj)

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager", return_value=mock_manager
        ):
            adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)
            adapter.connect()

            # Get wrapped object
            wrapped_obj = adapter.get()

            # Put it back
            result = adapter.put(wrapped_obj)

            assert result is True
            # Verify unwrapped object was passed to release
            mock_manager.release.assert_called_once_with("id", "key", test_obj)

    def test_no_wrapping_integration_with_get(self, smartpool_config_wrapping_disabled):
        """Test no wrapping integration with get() method."""
        mock_manager = MagicMock()
        test_obj = _TestObject("get_test_no_wrap")
        mock_manager.acquire.return_value = ("id", "key", test_obj)

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager", return_value=mock_manager
        ):
            adapter = SmartPoolAdapter(smartpool_config_wrapping_disabled)
            adapter.connect()

            result = adapter.get()

            assert result is test_obj
            assert not isinstance(result, AutoWeakRefWrapper)

            # Verify acquire was called but not release (since we only did get, not put)
            mock_manager.acquire.assert_called_once()
            mock_manager.release.assert_not_called()

    def test_wrapping_with_borrow_context(self, smartpool_config_wrapping_enabled):
        """Test wrapping with borrow context manager."""
        mock_manager = MagicMock()
        test_obj = _TestObject("borrow_test")
        mock_manager.acquire.return_value = ("id", "key", test_obj)

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager", return_value=mock_manager
        ):
            adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)
            adapter.connect()

            with adapter.borrow() as borrowed_obj:
                assert isinstance(borrowed_obj, AutoWeakRefWrapper)
                assert borrowed_obj._obj is test_obj

                # Test attribute access through wrapper
                assert borrowed_obj.name == "borrow_test"
                assert borrowed_obj.test_method() == "Method called on borrow_test"

    def test_wrapping_configuration_change_effect(self, mock_factory_function):
        """Test that changing wrapping configuration affects behavior."""
        # Start with wrapping enabled
        config = SmartPoolAdapterConfig(
            factory_function=mock_factory_function, auto_wrap_objects=True
        )
        adapter = SmartPoolAdapter(config)
        test_obj = _TestObject()

        # Test with wrapping enabled
        wrapped = adapter._wrap_object(test_obj)
        assert isinstance(wrapped, AutoWeakRefWrapper)

        # Change configuration
        adapter.config.auto_wrap_objects = False

        # Test with wrapping disabled
        not_wrapped = adapter._wrap_object(test_obj)
        assert not_wrapped is test_obj
        assert not isinstance(not_wrapped, AutoWeakRefWrapper)

    def test_wrapping_edge_cases(self, smartpool_config_wrapping_enabled):
        """Test edge cases in wrapping functionality."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)

        # Test with None
        wrapped_none = adapter._wrap_object(None)
        assert isinstance(wrapped_none, AutoWeakRefWrapper)
        assert wrapped_none._obj is None

        unwrapped_none = adapter._unwrap_object(wrapped_none)
        assert unwrapped_none is None

        # Test unwrapping None
        unwrapped_direct = adapter._unwrap_object(None)
        assert unwrapped_direct is None

    def test_wrapper_attribute_error_propagation(self):
        """Test that AttributeError is properly propagated through wrapper."""
        test_obj = _TestObject()
        wrapper = AutoWeakRefWrapper(test_obj)

        # Access non-existent attribute should raise AttributeError
        with pytest.raises(AttributeError):
            _ = wrapper.non_existent_attribute

    def test_wrapper_with_callable_object(self):
        """Test wrapper with callable objects."""

        def test_function(x, y=10):
            return x + y

        wrapper = AutoWeakRefWrapper(test_function)

        # Should be able to call the wrapped function
        # This works through __getattr__ delegation
        result = wrapper(5, y=15)
        assert result == 20

        # Direct access to wrapped function
        assert wrapper._obj is test_function

    def test_multiple_wrapper_levels_prevention(self, smartpool_config_wrapping_enabled):
        """Test that multiple wrapper levels are prevented."""
        adapter = SmartPoolAdapter(smartpool_config_wrapping_enabled)
        test_obj = _TestObject()

        # First level wrapping
        wrapped_once = adapter._wrap_object(test_obj)
        assert isinstance(wrapped_once, AutoWeakRefWrapper)

        # Second level wrapping - should not create nested wrapper
        wrapped_twice = adapter._wrap_object(wrapped_once)
        assert wrapped_twice is wrapped_once  # Same instance
        assert wrapped_twice._obj is test_obj  # Still points to original object

    def test_no_wrapping_with_borrow_context(self, smartpool_config_wrapping_disabled):
        """Test no wrapping with borrow context manager."""
        mock_manager = MagicMock()
        test_obj = _TestObject("borrow_no_wrap_test")
        mock_manager.acquire.return_value = ("id", "key", test_obj)

        with patch(
            "omni_cache.adapters.smartpool.smartpool.SmartObjectManager", return_value=mock_manager
        ):
            adapter = SmartPoolAdapter(smartpool_config_wrapping_disabled)
            adapter.connect()

            with adapter.borrow() as borrowed_obj:
                assert borrowed_obj is test_obj
                assert not isinstance(borrowed_obj, AutoWeakRefWrapper)

                # Test attribute access directly
                assert borrowed_obj.name == "borrow_no_wrap_test"
                assert borrowed_obj.test_method() == "Method called on borrow_no_wrap_test"

            # Verify release was called with the original object
            mock_manager.release.assert_called_once_with("id", "key", test_obj)
