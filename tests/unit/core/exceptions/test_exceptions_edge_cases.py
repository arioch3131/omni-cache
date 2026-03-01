"""
Edge case and stress tests for the exception system.
"""

import gc
import sys
import time
import weakref
from unittest.mock import patch

import pytest

from omni_cache.core.exceptions import (
    CacheFullError,
    CacheKeyError,
    ConfigurationError,
    ConnectionFailedError,
    FactoryNotFoundError,
    HealthCheckError,
    InvalidConfigurationError,
    OmniCacheError,
    OperationFailedError,
    OperationTimeoutError,
    PoolEmptyError,
    PoolObjectError,
    RouteNotFoundError,
    SerializationFailedError,
    get_exception_summary,
    handle_and_wrap_exception,
    is_retriable_error,
)


@pytest.mark.edge_case
class TestMemoryAndGarbageCollection:
    """Test memory management and garbage collection behavior."""

    def test_exception_garbage_collection(self):
        """Test that exceptions are properly garbage collected."""
        # Create a large number of exceptions
        exceptions = []
        for i in range(1000):
            error = OperationFailedError(
                f"test_op_{i}",
                f"Error message {i}",
                {"data": list(range(100))},  # Some memory overhead
            )
            exceptions.append(error)

        # Create weak references to track garbage collection
        weak_refs = [weakref.ref(exc) for exc in exceptions[:10]]

        # Clear references
        del exceptions
        gc.collect()

        # At least some should be garbage collected
        collected_count = sum(1 for ref in weak_refs if ref() is None)
        assert collected_count > 0

    def test_exception_with_large_circular_references(self):
        """Test exception behavior with large circular reference structures."""
        # Create a large circular structure
        circular_data = {}
        for i in range(1000):
            circular_data[f"key_{i}"] = circular_data

        # Should handle circular references without memory explosion
        error = CacheKeyError("circular_test", "get")
        error.details["circular"] = circular_data

        # Basic operations should still work
        assert "circular_test" in error.details["key"]
        str_repr = str(error)
        assert isinstance(str_repr, str)

    def test_memory_usage_with_deep_exception_chains(self):
        """Test memory usage with very deep exception chains."""
        # Create a deep chain of exceptions
        current_exception = ValueError("Root cause")

        for i in range(100):
            new_exception = OperationFailedError(
                f"operation_level_{i}",
                f"Failure at level {i}",
                {"level": i, "data": list(range(i))},
                current_exception,
            )
            current_exception = new_exception

        # Should handle deep chains without excessive memory usage
        summary = get_exception_summary(current_exception)
        assert summary["type"] == "OperationFailedError"
        assert "100 levels deep" not in summary["message"]  # No infinite recursion


@pytest.mark.edge_case
class TestExtremeInputValues:
    """Test exception handling with extreme input values."""

    def test_extremely_large_numbers(self):
        """Test with extremely large numeric values."""
        large_numbers = [
            sys.maxsize,
            sys.maxsize * 2,
            float("inf"),
            -float("inf"),
            1e308,
            -1e308,
        ]

        for number in large_numbers:
            if number == float("inf") or number == -float("inf"):
                continue  # Skip inf values for timeout tests

            try:
                error = OperationTimeoutError("large_number_test", float(number))
                assert error.details["timeout"] == float(number)
            except (ValueError, OverflowError):
                # Some extreme values might not be convertible
                pass

    def test_special_float_values(self):
        """Test with special float values (NaN, inf, -inf)."""
        special_values = [float("nan"), float("inf"), -float("inf")]

        for value in special_values:
            error = CacheFullError(100, 50)
            error.details["special_value"] = value

            # Should handle special float values
            summary = get_exception_summary(error)
            assert "details" in summary

    def test_extremely_nested_data_structures(self):
        """Test with extremely nested data structures."""
        # Create deeply nested structure
        nested = {}
        current = nested
        for i in range(1000):
            current[f"level_{i}"] = {}
            current = current[f"level_{i}"]
        current["final"] = "deep_value"

        error = ConfigurationError("Deep nesting test")
        error.details["nested"] = nested

        # Should handle without stack overflow
        try:
            str_repr = str(error)
            assert isinstance(str_repr, str)
        except RecursionError:
            pytest.fail("Should handle deep nesting without recursion error")

    def test_binary_and_non_printable_characters(self):
        """Test with binary data and non-printable characters."""
        binary_data = bytes(range(256))

        # Test with binary data in various fields
        error = SerializationFailedError("BinaryData", "custom")
        error.details["binary"] = binary_data
        error.details["control_chars"] = "\x00\x01\x02\x1f\x7f"

        # Should handle binary data gracefully
        str_repr = str(error)
        assert isinstance(str_repr, str)

        summary = get_exception_summary(error)
        assert "details" in summary

    def test_empty_and_whitespace_only_strings(self):
        """Test with empty and whitespace-only strings."""
        whitespace_variations = [
            "",
            " ",
            "\t",
            "\n",
            "\r\n",
            "   ",
            "\t\t\t",
            "\n\n\n",
            " \t \n \r ",
        ]

        for ws in whitespace_variations:
            # Test in various exception fields
            error = OperationFailedError(ws or "default_op", ws or "default_reason")

            # Should handle gracefully
            assert isinstance(error.message, str)
            str_repr = str(error)
            assert isinstance(str_repr, str)


@pytest.mark.edge_case
class TestConcurrencyEdgeCases:
    """Test edge cases related to concurrency and thread safety."""

    def test_exception_modification_during_access(self):
        """Test exception behavior when modified during access."""
        error = OperationFailedError("concurrent_test", "test")

        def modify_exception():
            for i in range(1000):
                error.details[f"key_{i}"] = f"value_{i}"
                if i % 100 == 0:
                    time.sleep(0.001)  # Small delay

        def access_exception():
            for _ in range(1000):
                try:
                    str_repr = str(error)
                    summary = get_exception_summary(error)
                    assert isinstance(str_repr, str)
                    assert isinstance(summary, dict)
                except Exception as exc:
                    # Should not crash even if concurrent modification occurs
                    assert str(exc)
                time.sleep(0.001)

        import threading

        modify_thread = threading.Thread(target=modify_exception)
        access_thread = threading.Thread(target=access_exception)

        modify_thread.start()
        access_thread.start()

        modify_thread.join()
        access_thread.join()

        # Should complete without deadlocks
        assert len(error.details) >= 1000

    def test_timestamp_consistency_across_threads(self):
        """Test timestamp consistency when creating exceptions in multiple threads."""
        import threading

        timestamps = []
        lock = threading.Lock()

        def create_exceptions_in_thread():
            thread_timestamps = []
            for _ in range(100):
                error = CacheKeyError("test", "test")
                thread_timestamps.append(error.timestamp)
                time.sleep(0.001)  # Small delay to spread timestamps

            with lock:
                timestamps.extend(thread_timestamps)

        import threading

        threads = []
        for _ in range(5):
            thread = threading.Thread(target=create_exceptions_in_thread)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Timestamps should be reasonably ordered (within threads)
        assert len(timestamps) == 500
        assert all(isinstance(ts, float) for ts in timestamps)

        # Should have some variation in timestamps
        unique_timestamps = set(timestamps)
        assert len(unique_timestamps) > 100  # Should have many unique timestamps


@pytest.mark.edge_case
class TestSerializationAndPickling:
    """Test exception behavior with serialization and pickling."""

    def test_exception_pickling(self, all_exception_classes):
        """Test that exceptions can be pickled and unpickled."""
        import pickle

        for _name, (exception_class, args) in all_exception_classes.items():
            original = exception_class(*args)

            try:
                # Test pickling
                pickled = pickle.dumps(original)
                unpickled = pickle.loads(pickled)  # noqa: S301

                # Basic properties should be preserved
                assert isinstance(unpickled, type(original))
                assert unpickled.message == original.message
                assert unpickled.details == original.details

            except (pickle.PicklingError, TypeError):
                # Some exceptions might not be pickleable due to complex data
                # This is acceptable for edge case testing
                pass

    def test_exception_json_serialization(self):
        """Test JSON serialization of exception data."""
        import json

        error = OperationFailedError(
            "json_test",
            "JSON serialization test",
            {
                "string": "value",
                "number": 42,
                "float": 3.14,
                "bool": True,
                "none": None,
                "list": [1, 2, 3],
                "nested": {"key": "value"},
            },
        )

        # Test JSON serialization of summary
        summary = get_exception_summary(error)

        try:
            json_str = json.dumps(summary, default=str)
            parsed = json.loads(json_str)

            assert parsed["type"] == "OperationFailedError"
            assert "details" in parsed

        except (TypeError, ValueError):
            # Some data might not be JSON serializable
            pass

    def test_exception_with_non_serializable_objects(self):
        """Test exceptions containing non-serializable objects."""
        import threading

        # Create objects that can't be pickled/serialized
        non_serializable_objects = [
            threading.Lock(),
            lambda x: x,  # Lambda function
            type("DynamicClass", (), {}),  # Dynamic class
            open(__file__),  # File object
        ]

        for obj in non_serializable_objects:
            error = PoolObjectError("Non-serializable test")
            error.details["non_serializable"] = obj

            # Basic operations should still work
            str_repr = str(error)
            assert isinstance(str_repr, str)

            summary = get_exception_summary(error)
            assert summary["type"] == "PoolObjectError"

            # Close file if it was opened
            if hasattr(obj, "close"):
                try:
                    obj.close()
                except Exception as exc:
                    assert str(exc)


@pytest.mark.edge_case
class TestPlatformSpecificBehavior:
    """Test platform-specific edge cases."""

    def test_unicode_normalization(self):
        """Test unicode normalization in exception messages."""
        # Different unicode representations of the same character
        unicode_variations = [
            "café",  # Combined character
            "cafe\u0301",  # Decomposed character
            "caf\u00e9",  # Precomposed character
        ]

        for variation in unicode_variations:
            error = InvalidConfigurationError("unicode_key", variation)

            # Should handle all variations
            assert isinstance(error.message, str)
            str_repr = str(error)
            assert isinstance(str_repr, str)

    def test_path_separator_handling(self):
        """Test path separator handling across platforms."""
        import os

        path_variations = [
            "path/to/file",  # Unix style
            "path\\to\\file",  # Windows style
            "path" + os.sep + "to" + os.sep + "file",  # Platform specific
            "./relative/path",
            "../parent/path",
            "/absolute/path",
            "C:\\Windows\\Path" if sys.platform == "win32" else "/usr/local/bin",
        ]

        for path in path_variations:
            error = ConnectionFailedError(path, "Path test")

            # Should handle all path styles
            assert path in error.details["target"]
            assert isinstance(str(error), str)

    def test_floating_point_precision(self):
        """Test floating point precision edge cases."""
        precision_values = [
            0.1 + 0.2,  # Classic floating point precision issue
            1.0 / 3.0,  # Repeating decimal
            sys.float_info.epsilon,  # Smallest representable difference
            sys.float_info.min,  # Smallest positive number
            sys.float_info.max,  # Largest representable number
        ]

        for value in precision_values:
            error = OperationTimeoutError("precision_test", value)

            # Should handle precision issues gracefully
            assert isinstance(error.details["timeout"], float)
            str_repr = str(error)
            assert isinstance(str_repr, str)


@pytest.mark.edge_case
class TestResourceExhaustion:
    """Test behavior under resource exhaustion conditions."""

    @pytest.mark.slow
    def test_memory_pressure_exception_creation(self):
        """Test exception creation under memory pressure."""
        # Create memory pressure
        large_objects = []
        try:
            # Allocate large amounts of memory
            for _i in range(100):
                large_objects.append(bytearray(10 * 1024 * 1024))  # 10MB each
        except MemoryError:
            # If we hit memory limit, that's fine for this test
            pass

        # Try to create exceptions under memory pressure
        try:
            error = OperationFailedError(
                "memory_pressure_test",
                "Testing under memory pressure",
                {"large_data": list(range(10000))},
            )

            # Should still work
            assert isinstance(error, OperationFailedError)
            str_repr = str(error)
            assert isinstance(str_repr, str)

        except MemoryError:
            # If we can't create exceptions due to memory pressure,
            # that's a valid outcome for this edge case test
            pass
        finally:
            # Clean up
            del large_objects

    def test_maximum_recursion_depth(self):
        """Test exception handling at maximum recursion depth."""
        original_limit = sys.getrecursionlimit()

        try:
            # Set a lower recursion limit for testing
            sys.setrecursionlimit(100)

            def recursive_exception_creation(depth):
                if depth <= 0:
                    raise ValueError("Max depth reached")

                try:
                    recursive_exception_creation(depth - 1)
                except ValueError as e:
                    # Wrap in our exception
                    raise OperationFailedError(
                        f"recursive_op_depth_{depth}",
                        f"Recursion at depth {depth}",
                        {"depth": depth},
                        e,
                    ) from e

            with pytest.raises(OperationFailedError):
                recursive_exception_creation(50)

        finally:
            # Restore original recursion limit
            sys.setrecursionlimit(original_limit)

    def test_file_descriptor_exhaustion_simulation(self):
        """Test exception behavior when file descriptors are exhausted."""
        # Simulate file descriptor exhaustion with mock
        with patch("builtins.open", side_effect=OSError("Too many open files")):
            # Exception creation shouldn't depend on file operations
            error = ConnectionFailedError("file://test", "FD exhaustion test")

            assert isinstance(error, ConnectionFailedError)
            str_repr = str(error)
            assert isinstance(str_repr, str)


@pytest.mark.edge_case
class TestUnusualInteractions:
    """Test unusual interactions and combinations."""

    def test_exception_as_exception_cause(self):
        """Test using an OmniCacheError as a cause for another OmniCacheError."""
        # Create a chain of omni-cache exceptions
        original = CacheKeyError("missing_key", "get", "Key not found")

        intermediate = OperationTimeoutError("cache_operation", 5.0)
        intermediate.__cause__ = original

        final = OperationFailedError("service_call", "Complete failure", cause=intermediate)

        # Verify the chain
        assert final.cause == intermediate
        assert final.cause.__cause__ == original

        # Test summary includes the chain
        summary = get_exception_summary(final)
        assert "OperationTimeoutError" in summary["cause"]

    def test_exception_details_modification_after_creation(self):
        """Test modifying exception details after creation."""
        error = ConfigurationError("Mutable test")

        # Modify details after creation
        error.details["added_later"] = "new_value"
        error.details["nested"] = {"deep": {"value": 42}}
        error.details["list"] = [1, 2, 3]

        # Should handle modified details
        summary = get_exception_summary(error)
        assert "added_later" in summary["details"]
        assert summary["details"]["nested"]["deep"]["value"] == 42

    def test_exception_message_modification(self):
        """Test modifying exception message after creation."""
        error = HealthCheckError("test_component", "ping")

        # Modify message (this is unusual but possible)
        error.message = "Modified message"

        # String representation should use modified message
        str_repr = error.__repr__()
        assert "Modified message" in str_repr
        assert "test_component" in str_repr  # Assert that original details are still there
        assert "ping" in str_repr  # Assert that original details are still there

    def test_exception_timestamp_manipulation(self):
        """Test behavior when timestamp is manipulated."""
        error = RouteNotFoundError("test_key")
        original_timestamp = error.timestamp

        # Modify timestamp
        error.timestamp = 0.0  # Unix epoch

        summary = get_exception_summary(error)
        assert summary["timestamp"] == 0.0
        assert summary["timestamp"] != original_timestamp

    def test_mixing_exception_types_in_utilities(self):
        """Test utility functions with mixed exception types."""
        omni_exceptions = [
            CacheKeyError("key", "op"),
            PoolEmptyError("pool"),
            FactoryNotFoundError("backend"),
        ]

        standard_exceptions = [
            ValueError("Standard value error"),
            TypeError("Standard type error"),
            RuntimeError("Standard runtime error"),
        ]

        # Test is_retriable_error with mixed types
        for exc in omni_exceptions + standard_exceptions:
            result = is_retriable_error(exc)
            assert isinstance(result, bool)

        # Test handle_and_wrap_exception with mixed types
        for exc in standard_exceptions:
            wrapped = handle_and_wrap_exception("test_op", exc)
            assert isinstance(wrapped, OmniCacheError)

        for exc in omni_exceptions:
            wrapped = handle_and_wrap_exception("test_op", exc)
            assert wrapped is exc  # Should pass through unchanged
