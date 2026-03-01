"""
Integration tests for exception system interactions and complex scenarios.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock

import pytest

from omni_cache.core.exceptions import (
    CacheFullError,
    CacheKeyError,
    ConfigurationError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    FactoryRegistrationError,
    HealthCheckError,
    InvalidConfigurationError,
    InvalidRouteError,
    MissingConfigurationError,
    OmniCacheError,
    OperationFailedError,
    OperationTimeoutError,
    exception_context,
    get_exception_summary,
    handle_and_wrap_exception,
    is_retriable_error,
)


@pytest.mark.integration
class TestExceptionChaining:
    """Test exception chaining and cause preservation across the system."""

    def test_complete_exception_chain(self, complex_exception_chain):
        """Test that complete exception chains are preserved properly."""
        final_exception, intermediate_cause, root_cause = complex_exception_chain

        # Test that the chain is preserved
        assert final_exception.cause == intermediate_cause
        assert intermediate_cause.__cause__ == root_cause

        # Test that each level has proper information
        assert "final_operation" in final_exception.message
        assert final_exception.details["level"] == 3

        # Test exception summary preserves chain info
        summary = get_exception_summary(final_exception)
        assert "Intermediate error" in summary["cause"]

    def test_exception_wrapping_preserves_chains(self):
        """Test that wrapping exceptions preserves original chains."""
        # Create original chain
        root = ValueError("Root error")
        intermediate = RuntimeError("Intermediate")
        intermediate.__cause__ = root

        # Wrap the intermediate exception
        wrapped = handle_and_wrap_exception("test_operation", intermediate)

        # Verify the original chain is preserved
        assert wrapped.cause == intermediate
        assert wrapped.cause.__cause__ == root

    def test_nested_exception_context_handling(self):
        """Test nested exception contexts work properly."""

        def inner_operation():
            with exception_context("inner_op", level="inner"):
                raise ValueError("Inner error")

        def outer_operation():
            with exception_context("outer_op", level="outer"):
                inner_operation()

        with pytest.raises(InvalidConfigurationError) as exc_info:
            outer_operation()

        # The outermost context should wrap the exception
        assert exc_info.value.details["config_key"] == "unknown"
        assert "Inner error" in str(exc_info.value)


@pytest.mark.integration
class TestExceptionSystemInteractions:
    """Test how different parts of the exception system interact."""

    def test_all_exceptions_work_with_utilities(self, all_exception_classes):
        """Test that all exception types work with utility functions."""
        for name, (exception_class, args) in all_exception_classes.items():
            # Create exception instance
            exception = exception_class(*args)

            # Test with get_exception_summary
            summary = get_exception_summary(exception)
            assert summary["type"] == name
            assert "message" in summary
            assert "retriable" in summary

            # Test with is_retriable_error
            retriable = is_retriable_error(exception)
            assert isinstance(retriable, bool)

            # Test with handle_and_wrap_exception (should pass through OmniCacheError)
            if isinstance(exception, OmniCacheError):
                wrapped = handle_and_wrap_exception("test", exception)
                assert wrapped is exception

            # Test with exception_context
            try:
                with exception_context("test_operation"):
                    raise exception
            except Exception as caught:
                if isinstance(exception, OmniCacheError):
                    assert caught is exception
                else:
                    assert isinstance(caught, OperationFailedError)

    def test_exception_inheritance_consistency(self, base_exception_classes, all_exception_classes):
        """Test that exception inheritance is consistent across the system."""
        for base_class, derived_classes in base_exception_classes.items():
            for derived_class in derived_classes:
                # Test MRO includes base class
                assert base_class in derived_class.__mro__

                # Get the exception class and arguments from the fixture
                derived_class_name = derived_class.__name__
                assert derived_class_name in all_exception_classes, (
                    f"Exception class '{derived_class_name}' not found in "
                    f"'all_exception_classes' fixture."
                )

                exception_class, args = all_exception_classes[derived_class_name]

                # Ensure the class from the fixture is the one we are testing
                assert exception_class is derived_class

                # Instantiate the exception
                instance = exception_class(*args)

                # Test that isinstance works as expected
                assert isinstance(instance, base_class)
                assert isinstance(instance, OmniCacheError)

    def test_exception_categorization_consistency(
        self, retriable_exceptions, non_retriable_exceptions
    ):
        """Test that exception retriability categorization is consistent."""
        # Test retriable exceptions
        for exception in retriable_exceptions:
            assert is_retriable_error(exception) is True
            summary = get_exception_summary(exception)
            assert summary["retriable"] is True

        # Test non-retriable exceptions
        for exception in non_retriable_exceptions:
            assert is_retriable_error(exception) is False
            summary = get_exception_summary(exception)
            assert summary["retriable"] is False


@pytest.mark.integration
class TestComplexScenarios:
    """Test complex real-world exception scenarios."""

    def test_cascade_failure_simulation(self):
        """Simulate a cascade of failures across different components."""

        def database_failure():
            raise ConnectionFailedError("database:5432", "Connection refused")

        def cache_fallback_failure():
            try:
                database_failure()
            except ConnectionFailedError as e:
                # Cache tries to handle DB failure but also fails
                raise OperationFailedError(
                    "cache_fallback", "Database unavailable", {"fallback_attempted": True}, e
                ) from e

        def service_layer_failure():
            try:
                cache_fallback_failure()
            except OperationFailedError as e:
                # Service layer wraps everything
                raise OperationFailedError(
                    "service_request",
                    "Complete system failure",
                    {"request_id": "req_123", "user_id": "user_456"},
                    e,
                ) from e

        with pytest.raises(OperationFailedError) as exc_info:
            service_layer_failure()

        # Verify the complete failure chain
        error = exc_info.value
        assert error.details["operation"] == "service_request"
        assert error.details["request_id"] == "req_123"

        # Check the cause chain
        assert isinstance(error.cause, OperationFailedError)
        assert error.cause.details["operation"] == "cache_fallback"

        assert isinstance(error.cause.cause, ConnectionFailedError)
        assert error.cause.cause.details["target"] == "database:5432"

    def test_multi_component_health_check_failure(self):
        """Test health check failures across multiple components."""
        components = [
            ("redis_cache", "ping", "Connection timeout"),
            ("database_pool", "connection_test", "All connections busy"),
            ("message_queue", "queue_check", "Queue is full"),
            ("external_api", "heartbeat", "Service unavailable"),
        ]

        health_errors = []
        for component, check_type, reason in components:
            error = HealthCheckError(component, check_type, reason)
            health_errors.append(error)

        # Verify all health errors are properly categorized
        for error in health_errors:
            assert isinstance(error, OmniCacheError)
            summary = get_exception_summary(error)
            assert summary["type"] == "HealthCheckError"

    def test_configuration_validation_cascade(self):
        """Test cascading configuration validation errors."""
        config_errors = []

        # Missing required config
        config_errors.append(MissingConfigurationError("database_url", "data_layer"))

        # Invalid config values
        config_errors.append(
            InvalidConfigurationError("port", "not_a_number", int, [3000, 5432, 6379])
        )

        # Complex nested config error
        config_errors.append(InvalidConfigurationError("redis.pool.max_connections", -5, int))

        # Verify all config errors are non-retriable
        for error in config_errors:
            assert is_retriable_error(error) is False
            assert isinstance(error, ConfigurationError)

    def test_factory_creation_failure_chain(self):
        """Test factory creation failure scenarios."""
        # Simulate factory not found
        try:
            raise FactoryNotFoundError("nonexistent_backend", ["memory", "redis"])
        except FactoryNotFoundError as e:
            factory_error = e

        # Simulate registration failure due to missing dependencies
        try:
            raise FactoryRegistrationError(
                "redis_backend", "Missing redis dependency", ImportError("No module named 'redis'")
            )
        except FactoryRegistrationError as e:
            registration_error = e

        # Simulate creation failure due to invalid config
        try:
            raise FactoryCreationError(
                "database_backend",
                {"host": None, "port": "invalid"},
                ValueError("Invalid configuration"),
            )
        except FactoryCreationError as e:
            creation_error = e

        # All should be factory errors and non-retriable
        factory_errors = [factory_error, registration_error, creation_error]
        for error in factory_errors:
            assert isinstance(error, FactoryError)
            assert is_retriable_error(error) is False


@pytest.mark.integration
@pytest.mark.performance
class TestExceptionPerformance:
    """Test exception system performance under load."""

    def test_exception_creation_performance(self, performance_test_data):
        """Test performance of creating many exceptions."""
        start_time = time.time()

        exceptions = []
        for i in range(performance_test_data["many_exceptions"]):
            error = OperationFailedError(
                f"operation_{i}", f"Error {i}", {"iteration": i, "batch": i // 100}
            )
            exceptions.append(error)

        end_time = time.time()
        duration = end_time - start_time

        # Should be able to create 1000 exceptions quickly
        assert duration < 1.0
        assert len(exceptions) == performance_test_data["many_exceptions"]

    def test_large_details_handling(self, performance_test_data):
        """Test handling of exceptions with large details dictionaries."""
        large_details = performance_test_data["large_details"]

        start_time = time.time()
        error = OperationFailedError("test_op", "test reason", large_details)
        end_time = time.time()

        # Should handle large details efficiently
        assert (end_time - start_time) < 0.1
        assert len(error.details) > 1000
        assert error.details["key_999"] == "value_999"

    def test_deep_nesting_handling(self, performance_test_data):
        """Test handling of deeply nested details."""
        deep_details = performance_test_data["deep_nesting"]

        error = CacheKeyError("nested_key", "complex_operation")
        error.details.update(deep_details)

        # Should handle deep nesting without issues
        summary = get_exception_summary(error)
        assert len(summary["details"]) > 100

    @pytest.mark.slow
    def test_concurrent_exception_handling(self):
        """Test exception handling under concurrent load."""

        def create_and_process_exception(thread_id):
            try:
                with exception_context(f"thread_operation_{thread_id}", thread_id=thread_id):
                    # Simulate various types of failures
                    if thread_id % 3 == 0:
                        raise ConnectionTimeoutError(5.0, f"connect_{thread_id}")
                    elif thread_id % 3 == 1:
                        raise CacheFullError(100, 100, "lru")
                    else:
                        raise ValueError(f"Generic error {thread_id}")
            except Exception as e:
                return get_exception_summary(e)

        # Run concurrent exception processing
        num_threads = 50
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_process_exception, i) for i in range(num_threads)]

            results = []
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        # Verify all threads completed successfully
        assert len(results) == num_threads

        # Verify different exception types were handled
        exception_types = {result["type"] for result in results}
        expected_types = {"ConnectionTimeoutError", "CacheFullError", "InvalidConfigurationError"}
        assert expected_types.issubset(exception_types)


@pytest.mark.integration
@pytest.mark.unicode
class TestInternationalization:
    """Test exception system with international/unicode content."""

    def test_unicode_messages_and_details(self, unicode_test_data):
        """Test exceptions with unicode messages and details."""
        for message in unicode_test_data["messages"]:
            error = OperationFailedError("unicode_test", message)

            # Should handle unicode in message
            assert error.message.endswith(message)
            assert isinstance(str(error), str)
            assert isinstance(repr(error), str)

        # Test unicode in details
        unicode_details = {
            "french_key": "valeur française",
            "chinese_key": "中文值",
            "russian_key": "русское значение",
            "emoji_key": "🚀🔑💾",
        }

        error = CacheKeyError("test", "get")
        error.details.update(unicode_details)

        summary = get_exception_summary(error)
        assert "french_key" in summary["details"]

    def test_unicode_exception_keys_and_components(self, unicode_test_data):
        """Test exceptions with unicode keys and component names."""
        for key in unicode_test_data["keys"]:
            error = CacheKeyError(key, "unicode_operation")
            assert key in error.details["key"]

        for component in unicode_test_data["components"]:
            error = HealthCheckError(component, "unicode_check")
            assert error.details["component"] == component

    def test_unicode_routing_patterns(self, unicode_test_data):
        """Test routing exceptions with unicode patterns."""
        unicode_patterns = [
            "utilisateur:*",
            "用户:*",
            "пользователь:*",
            "🚀rocket:*",
        ]

        for pattern in unicode_patterns:
            error = InvalidRouteError(pattern, "Invalid unicode pattern")
            assert error.details["route_pattern"] == pattern


@pytest.mark.integration
@pytest.mark.edge_case
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_extremely_long_messages(self, performance_test_data):
        """Test handling of extremely long error messages."""
        long_message = performance_test_data["large_message"]

        error = ConfigurationError(long_message)
        assert len(error.message) == len(long_message)

        # Should handle long messages in summaries
        summary = get_exception_summary(error)
        assert len(summary["message"]) == len(long_message)

    def test_circular_reference_in_details(self):
        """Test handling of circular references in details."""
        details = {"key": "value"}
        details["self"] = details  # Circular reference

        # Should not crash when creating exception
        error = OperationFailedError("test", "test", details)
        assert error.details["key"] == "value"

        # Summary generation might handle this differently
        summary = get_exception_summary(error)
        assert "details" in summary

    def test_none_and_empty_values_comprehensive(self):
        """Comprehensive test of None and empty value handling."""
        test_cases = [
            # (exception_class, args, expected_behavior)
            (CacheKeyError, (None, ""), "should handle None key"),
            (OperationTimeoutError, ("", 0.0), "should handle empty operation"),
            (ConnectionFailedError, ("", None), "should handle empty target"),
            (HealthCheckError, ("", "", None, None), "should handle all None/empty"),
        ]

        for exception_class, args, description in test_cases:
            # Should not crash on creation
            error = exception_class(*args)
            assert isinstance(error, OmniCacheError), description

            # Should not crash on string conversion
            str_repr = str(error)
            assert isinstance(str_repr, str), description

    def test_exception_with_mock_objects(self):
        """Test exceptions that contain mock objects in details."""
        mock_obj = Mock()
        mock_obj.name = "test_mock"
        mock_obj.__str__ = Mock(return_value="mock_string_representation")

        error = OperationFailedError("test", "mock test", {"mock": mock_obj})

        # Should handle mock objects without crashing
        summary = get_exception_summary(error)
        assert "details" in summary

    def test_thread_safety_of_exception_creation(self):
        """Test that exception creation is thread-safe."""
        results = []
        errors = []

        def create_exception_in_thread(thread_id):
            try:
                for i in range(100):
                    error = OperationTimeoutError(
                        f"thread_{thread_id}_op_{i}",
                        float(thread_id + i),
                        {"thread_id": thread_id, "iteration": i},
                    )
                    results.append(error.timestamp)
            except Exception as e:
                errors.append(e)

        # Run multiple threads creating exceptions
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_exception_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0

        # Should have created all expected exceptions
        assert len(results) == 1000  # 10 threads * 100 exceptions each
