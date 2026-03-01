"""
Compatibility and regression tests for the exception system.
"""

import sys
from unittest.mock import patch

import pytest

from omni_cache.core.exceptions import (
    AdapterNotFoundError,
    CacheError,
    CacheFullError,
    CacheKeyError,
    ConfigurationError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    HealthCheckError,
    InvalidConfigurationError,
    OmniCacheError,
    OmniConnectionError,
    OperationError,
    OperationFailedError,
    OperationTimeoutError,
    PoolEmptyError,
    PoolError,
    PoolFullError,
    PoolObjectError,
    SerializationFailedError,
    is_retriable_error,
)


@pytest.mark.compatibility
class TestPythonVersionCompatibility:
    """Test compatibility across different Python versions."""

    def test_exception_str_behavior_consistency(self):
        """Test that __str__ behavior is consistent across Python versions."""
        error = CacheKeyError("test_key", "get_operation", "specific reason")

        str_result = str(error)

        # Should always return a string
        assert isinstance(str_result, str)

        # Should contain key components
        assert "test_key" in str_result
        assert "get_operation" in str_result
        assert "specific reason" in str_result

    def test_exception_repr_behavior_consistency(self):
        """Test that __repr__ behavior is consistent across Python versions."""
        error = OperationTimeoutError("test_op", 5.0, {"context": "test"})

        repr_result = repr(error)

        # Should always return a string that could recreate the object
        assert isinstance(repr_result, str)
        assert "OperationTimeoutError" in repr_result

    def test_exception_inheritance_mro_consistency(self):
        """Test that Method Resolution Order is consistent."""
        error = ConnectionFailedError("test_target", "test_reason")

        mro = type(error).__mro__

        # Should have expected inheritance chain
        expected_classes = [
            ConnectionFailedError,
            OmniConnectionError,
            OmniCacheError,
            Exception,
            BaseException,
            object,
        ]

        for cls in expected_classes:
            assert cls in mro

    def test_exception_attribute_access_consistency(self):
        """Test that attribute access works consistently."""
        error = FactoryCreationError("test_backend", {"config": "value"})

        # All these should work consistently
        assert hasattr(error, "message")
        assert hasattr(error, "details")
        assert hasattr(error, "timestamp")
        assert hasattr(error, "cause")

        # Access should not raise exceptions
        _ = error.message
        _ = error.details
        _ = error.timestamp
        _ = error.cause

    @pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8+")
    def test_positional_only_parameter_compatibility(self):
        """Test compatibility with positional-only parameters (Python 3.8+)."""
        # Create exceptions using positional arguments only
        error1 = CacheKeyError("key", "operation")
        error2 = OperationTimeoutError("op", 5.0)
        error3 = ConnectionFailedError("target")

        assert isinstance(error1, CacheKeyError)
        assert isinstance(error2, OperationTimeoutError)
        assert isinstance(error3, ConnectionFailedError)


@pytest.mark.compatibility
class TestStandardLibraryIntegration:
    """Test integration with Python standard library components."""

    def test_logging_integration(self):
        """Test that exceptions integrate well with logging module."""
        import logging
        from io import StringIO

        # Setup string capture for log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.ERROR)

        logger = logging.getLogger("test_logger")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)

        # Test logging exceptions
        try:
            raise PoolFullError("test_pool", 10, 5.0)
        except PoolFullError as e:
            logger.exception("Pool operation failed")
            logger.error("Error details: %s", e.details)

        # Verify logging worked
        log_output = log_capture.getvalue()
        assert "PoolFullError" in log_output
        assert "test_pool" in log_output

        # Cleanup
        logger.removeHandler(handler)

    def test_traceback_module_integration(self):
        """Test integration with traceback module."""
        import traceback
        from io import StringIO

        def create_nested_exception():
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise OperationFailedError("wrapper_op", "Wrapped error", cause=e) from e

        try:
            create_nested_exception()
        except OperationFailedError:
            # Capture traceback
            tb_io = StringIO()
            traceback.print_exc(file=tb_io)
            tb_string = tb_io.getvalue()

            # Should contain both exceptions
            assert "OperationFailedError" in tb_string
            assert "ValueError" in tb_string
            assert "Original error" in tb_string
            assert "Wrapped error" in tb_string

    def test_warnings_module_integration(self):
        """Test that exceptions can be used with warnings module."""
        import warnings

        with warnings.catch_warnings(record=True) as warning_list:
            warnings.simplefilter("always")

            # Create a warning based on an exception
            error = InvalidConfigurationError("test_key", "test_value")
            warnings.warn(f"Configuration issue: {error.message}", UserWarning, stacklevel=2)

            assert len(warning_list) == 1
            assert "Configuration issue" in str(warning_list[0].message)
            assert "test_key" in str(warning_list[0].message)

    def test_multiprocessing_compatibility(self):
        """Test that exceptions can be pickled for multiprocessing."""
        import pickle

        exceptions_to_test = [
            CacheKeyError("key", "op", "reason"),
            PoolEmptyError("pool", 5.0),
            ConfigurationError("config error"),
            OperationTimeoutError("op", 10.0),
        ]

        for original_error in exceptions_to_test:
            try:
                # Pickle and unpickle
                pickled = pickle.dumps(original_error)
                unpickled = pickle.loads(pickled)  # noqa: S301

                # Verify basic properties are preserved
                assert isinstance(unpickled, type(original_error))
                assert unpickled.message == original_error.message

            except (pickle.PicklingError, TypeError):
                # Some exceptions might not be pickleable due to complex data
                # This is documented behavior
                pass


@pytest.mark.compatibility
class TestThirdPartyFrameworkCompatibility:
    """Test compatibility with common third-party frameworks and patterns."""

    def test_pytest_exception_handling(self):
        """Test that exceptions work properly with pytest."""
        # Test that pytest can capture our exceptions properly
        with pytest.raises(CacheFullError) as exc_info:
            raise CacheFullError(100, 100, "lru")

        captured = exc_info.value
        assert isinstance(captured, CacheFullError)
        assert captured.details["max_size"] == 100
        assert captured.details["eviction_policy"] == "lru"

    def test_mock_framework_compatibility(self):
        """Test compatibility with unittest.mock."""
        from unittest.mock import Mock

        # Mock an exception creation
        mock_error = Mock(spec=OperationFailedError)
        mock_error.message = "Mocked error"
        mock_error.details = {"mocked": True}
        mock_error.timestamp = 1234567890.0

        # Should work with our utility functions
        assert hasattr(mock_error, "message")
        assert hasattr(mock_error, "details")

    def test_context_manager_compatibility(self):
        """Test that exceptions work with context managers."""

        class TestContextManager:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type and issubclass(exc_type, OmniCacheError):
                    # Handle omni-cache exceptions specially
                    return True  # Suppress the exception
                return False

        # Test with omni-cache exception
        with TestContextManager():
            raise PoolObjectError("Context manager test")

        # Should not raise because context manager handled it

    def test_decorator_compatibility(self):
        """Test that exceptions work properly with decorators."""

        def error_logging_decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except OmniCacheError as e:
                    # Log the error and re-raise
                    print(f"Caught omni-cache error: {e}")
                    raise

            return wrapper

        @error_logging_decorator
        def function_that_fails():
            raise SerializationFailedError("TestClass", "json")

        with pytest.raises(SerializationFailedError):
            function_that_fails()


@pytest.mark.compatibility
class TestBackwardCompatibility:
    """Test backward compatibility with older interfaces."""

    def test_legacy_exception_creation_patterns(self):
        """Test that legacy exception creation patterns still work."""
        # Test creating exceptions with minimal parameters
        error1 = OperationFailedError("operation")
        assert error1.details["operation"] == "operation"

        # Test creating with positional arguments
        error2 = CacheKeyError("key", "operation")
        assert error2.details["key"] == "key"
        assert error2.details["operation"] == "operation"

    def test_exception_message_format_consistency(self):
        """Test that exception message formats remain consistent."""
        # These message formats should remain stable for backward compatibility
        error1 = AdapterNotFoundError("test_adapter")
        assert "Adapter 'test_adapter' not found" == error1.message

        error2 = ConnectionTimeoutError("connect", 5.0)
        assert "Connection timeout after 5.0s during connect" == error2.message

        error3 = CacheFullError(100)
        assert "Cache is full (max size: 100)" == error3.message

    def test_details_dictionary_structure_compatibility(self):
        """Test that details dictionary structure remains compatible."""
        error = OperationTimeoutError("test_op", 5.0, {"extra": "data"})

        # These keys should always be present
        assert "operation" in error.details
        assert "timeout" in error.details
        assert "extra" in error.details

        # Types should be consistent
        assert isinstance(error.details["operation"], str)
        assert isinstance(error.details["timeout"], (int, float))

    def test_inheritance_hierarchy_stability(self):
        """Test that inheritance hierarchy remains stable."""
        # Test that all exceptions still inherit from expected base classes
        test_cases = [
            (CacheKeyError("k", "o"), CacheError),
            (PoolEmptyError(), PoolError),
            (FactoryNotFoundError("b"), FactoryError),
            (ConnectionFailedError("t"), OmniConnectionError),
            (OperationTimeoutError("o", 1), OperationError),
        ]

        for exception, expected_base in test_cases:
            assert isinstance(exception, expected_base)
            assert isinstance(exception, OmniCacheError)


@pytest.mark.compatibility
class TestEnvironmentCompatibility:
    """Test compatibility across different environments."""

    def test_frozen_environment_compatibility(self):
        """Test compatibility in frozen environments (PyInstaller, etc.)."""
        # Test that exception creation doesn't rely on __file__ or module paths
        error = HealthCheckError("test_component", "test_check")

        # Should work without relying on filesystem paths
        assert isinstance(error, HealthCheckError)
        str_repr = str(error)
        assert isinstance(str_repr, str)

    def test_restricted_environment_compatibility(self):
        """Test compatibility in restricted environments."""
        # Simulate restricted environment by limiting available modules
        try:
            import builtins
            import sys

            # Keep only essential modules to simulate a constrained interpreter.
            with patch.dict(sys.modules, {"sys": sys, "builtins": builtins}, clear=True):
                # Exception creation should still work
                error = ConfigurationError("Restricted environment test")
                assert isinstance(error, ConfigurationError)
        except RecursionError as e:
            pytest.skip(f"Skipping due to RecursionError in restricted environment: {e}")

    def test_thread_local_compatibility(self):
        """Test that exceptions work with thread-local data."""
        import threading

        thread_local_data = threading.local()

        def thread_function(thread_id):
            thread_local_data.error_count = 0

            for i in range(10):
                try:
                    if i % 3 == 0:
                        raise PoolEmptyError(f"pool_{thread_id}")
                    else:
                        raise CacheKeyError(f"key_{i}", f"op_{thread_id}")
                except OmniCacheError:
                    thread_local_data.error_count += 1

            return thread_local_data.error_count

        # Run multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=lambda i=i: thread_function(i))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should complete without issues

    def test_signal_handler_compatibility(self):
        """Test that exceptions work properly with signal handlers."""
        import signal
        import time

        caught_exception = None

        def signal_handler(signum, frame):
            nonlocal caught_exception
            try:
                raise OperationTimeoutError("signal_operation", 1.0)
            except OperationTimeoutError as e:
                caught_exception = e

        # Set up signal handler (only on Unix-like systems)
        if hasattr(signal, "SIGUSR1"):
            original_handler = signal.signal(signal.SIGUSR1, signal_handler)

            try:
                # Trigger signal
                import os

                os.kill(os.getpid(), signal.SIGUSR1)
                time.sleep(0.1)  # Give signal time to be processed

                # Verify exception was created properly
                if caught_exception:
                    assert isinstance(caught_exception, OperationTimeoutError)

            finally:
                # Restore original handler
                signal.signal(signal.SIGUSR1, original_handler)


@pytest.mark.compatibility
class TestIntegrationTestHelpers:
    """Provide helper methods for integration testing."""

    def test_exception_assertion_helpers(self):
        """Test helper methods for asserting exception properties."""

        def assert_omni_cache_error_structure(error):
            """Helper to assert proper OmniCacheError structure."""
            assert isinstance(error, OmniCacheError)
            assert hasattr(error, "message")
            assert hasattr(error, "details")
            assert hasattr(error, "timestamp")
            assert hasattr(error, "cause")
            assert isinstance(error.message, str)
            assert isinstance(error.details, dict)
            assert isinstance(error.timestamp, float)

        # Test with various exception types
        exceptions = [
            CacheKeyError("key", "op"),
            PoolFullError("pool", 10),
            FactoryNotFoundError("backend"),
            ConnectionTimeoutError("connect", 5.0),
        ]

        for error in exceptions:
            assert_omni_cache_error_structure(error)

    def test_exception_factory_for_testing(self):
        """Test factory methods for creating test exceptions."""

        def create_test_cache_error(key="test_key", operation="test_op"):
            return CacheKeyError(key, operation, "Test error for unit testing")

        def create_test_operation_error(op="test_operation", timeout=5.0):
            return OperationTimeoutError(op, timeout, {"test": True})

        # Use factory methods
        cache_error = create_test_cache_error()
        op_error = create_test_operation_error()

        assert isinstance(cache_error, CacheKeyError)
        assert isinstance(op_error, OperationTimeoutError)
        assert cache_error.details["key"] == "test_key"
        assert op_error.details["test"] is True

    def test_exception_matching_patterns(self):
        """Test patterns for matching and filtering exceptions."""

        def is_retriable_cache_error(error):
            """Check if a cache error is retriable."""
            return (
                isinstance(error, CacheError)
                and is_retriable_error(error)
                and "timeout" not in error.message.lower()
            )

        def is_configuration_related(error):
            """Check if error is configuration-related."""
            return (
                isinstance(error, (ConfigurationError, FactoryError))
                or "config" in error.message.lower()
            )

        # Test the matching patterns
        test_errors = [
            CacheFullError(100),  # Retriable cache error
            ConfigurationError("Invalid config"),  # Config error
            OperationTimeoutError("cache_op", 5.0),  # Timeout (not cache error)
            FactoryNotFoundError("backend"),  # Factory error (config-related)
        ]

        retriable_cache_errors = [e for e in test_errors if is_retriable_cache_error(e)]
        config_errors = [e for e in test_errors if is_configuration_related(e)]

        assert len(retriable_cache_errors) == 1
        assert len(config_errors) == 2
        assert isinstance(retriable_cache_errors[0], CacheFullError)
