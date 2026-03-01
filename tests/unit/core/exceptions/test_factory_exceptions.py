"""
Unit tests for factory-related exception classes.
"""

import pytest

from omni_cache.core.exceptions.factory_exceptions import (
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    FactoryRegistrationError,
)
from omni_cache.core.exceptions.omni_cache_error import OmniCacheError


class TestFactoryError:
    """Test cases for FactoryError base class."""

    def test_inheritance(self):
        """Test that FactoryError inherits from OmniCacheError."""
        error = FactoryError("Test factory error")
        assert isinstance(error, OmniCacheError)
        assert isinstance(error, FactoryError)

    def test_basic_initialization(self):
        """Test basic initialization of FactoryError."""
        message = "Factory error occurred"
        error = FactoryError(message)
        assert error.message == message


class TestFactoryNotFoundError:
    """Test cases for FactoryNotFoundError."""

    def test_basic_initialization(self):
        """Test basic initialization without available backends."""
        backend = "nonexistent_backend"
        error = FactoryNotFoundError(backend)

        expected_message = f"No factory found for backend '{backend}'"
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert "available_backends" not in error.details

    def test_initialization_with_available_backends(self):
        """Test initialization with available backends list."""
        backend = "missing_backend"
        available_backends = ["memory", "redis", "memcached"]
        error = FactoryNotFoundError(backend, available_backends)

        expected_message = (
            f"No factory found for backend '{backend}'. "
            "Available backends: memory, redis, memcached"
        )
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert error.details["available_backends"] == available_backends

    def test_empty_available_backends(self):
        """Test with empty available backends list."""
        backend = "test_backend"
        error = FactoryNotFoundError(backend, [])

        expected_message = f"No factory found for backend '{backend}'. Available backends: "
        assert error.message == expected_message
        assert error.details["available_backends"] == []

    def test_none_available_backends(self):
        """Test with None available backends."""
        backend = "test_backend"
        error = FactoryNotFoundError(backend, None)

        expected_message = f"No factory found for backend '{backend}'"
        assert error.message == expected_message
        assert "available_backends" not in error.details

    def test_empty_backend_name(self):
        """Test with empty backend name."""
        backend = ""
        error = FactoryNotFoundError(backend)

        expected_message = "No factory found for backend ''"
        assert error.message == expected_message
        assert error.details["backend"] == ""

    def test_single_available_backend(self):
        """Test with single available backend."""
        backend = "missing"
        available_backends = ["memory"]
        error = FactoryNotFoundError(backend, available_backends)

        expected_message = f"No factory found for backend '{backend}'. Available backends: memory"
        assert error.message == expected_message
        assert error.details["available_backends"] == ["memory"]

    def test_many_available_backends(self):
        """Test with many available backends."""
        backend = "custom"
        available_backends = [
            "memory",
            "redis",
            "memcached",
            "mongodb",
            "elasticsearch",
            "cassandra",
        ]
        error = FactoryNotFoundError(backend, available_backends)

        backends_str = ", ".join(available_backends)
        expected_message = (
            f"No factory found for backend '{backend}'. Available backends: {backends_str}"
        )
        assert error.message == expected_message
        assert error.details["available_backends"] == available_backends


class TestFactoryRegistrationError:
    """Test cases for FactoryRegistrationError."""

    def test_basic_initialization(self):
        """Test basic initialization without cause."""
        backend = "test_backend"
        reason = "Invalid factory configuration"
        error = FactoryRegistrationError(backend, reason)

        expected_message = f"Failed to register factory for backend '{backend}': {reason}"
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert error.details["reason"] == reason
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        backend = "redis"
        reason = "Dependency not found"
        cause = ImportError("No module named 'redis'")
        error = FactoryRegistrationError(backend, reason, cause)

        expected_message = f"Failed to register factory for backend '{backend}': {reason}"
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert error.details["reason"] == reason
        assert error.cause == cause

    def test_empty_backend(self):
        """Test with empty backend name."""
        backend = ""
        reason = "Empty backend name"
        error = FactoryRegistrationError(backend, reason)

        expected_message = f"Failed to register factory for backend '': {reason}"
        assert error.message == expected_message
        assert error.details["backend"] == ""

    def test_empty_reason(self):
        """Test with empty reason string."""
        backend = "test_backend"
        reason = ""
        error = FactoryRegistrationError(backend, reason)

        expected_message = f"Failed to register factory for backend '{backend}': "
        assert error.message == expected_message
        assert error.details["reason"] == ""

    def test_complex_reason_messages(self):
        """Test with complex reason messages."""
        backend = "custom_backend"
        reasons = [
            "Multiple validation errors: missing required field 'host', invalid port range",
            "Initialization failed during connection pool setup",
            "Configuration schema validation failed",
            "Circular dependency detected in factory chain",
        ]

        for reason in reasons:
            error = FactoryRegistrationError(backend, reason)
            assert error.details["reason"] == reason
            assert reason in error.message

    def test_cause_chain_preservation(self):
        """Test that exception cause chain is preserved."""
        original_error = ValueError("Invalid configuration")
        intermediate_error = RuntimeError("Factory creation failed")
        intermediate_error.__cause__ = original_error

        backend = "test_backend"
        reason = "Cascade failure"
        error = FactoryRegistrationError(backend, reason, intermediate_error)

        assert error.cause == intermediate_error
        assert hasattr(intermediate_error, "__cause__")
        assert intermediate_error.__cause__ == original_error


class TestFactoryCreationError:
    """Test cases for FactoryCreationError."""

    def test_basic_initialization(self):
        """Test basic initialization without cause."""
        backend = "redis"
        adapter_config = {"host": "localhost", "port": 6379}
        error = FactoryCreationError(backend, adapter_config)

        expected_message = f"Factory failed to create adapter for backend '{backend}'"
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert error.details["adapter_config"] == adapter_config
        assert error.cause is None

    def test_initialization_with_cause(self):
        """Test initialization with underlying cause."""
        backend = "database"
        adapter_config = {"url": "postgresql://localhost/test"}
        cause = ConnectionError("Database not reachable")
        error = FactoryCreationError(backend, adapter_config, cause)

        expected_message = f"Factory failed to create adapter for backend '{backend}'"
        assert error.message == expected_message
        assert error.details["backend"] == backend
        assert error.details["adapter_config"] == adapter_config
        assert error.cause == cause

    def test_empty_backend(self):
        """Test with empty backend name."""
        backend = ""
        adapter_config = {"setting": "value"}
        error = FactoryCreationError(backend, adapter_config)

        expected_message = "Factory failed to create adapter for backend ''"
        assert error.message == expected_message
        assert error.details["backend"] == ""

    def test_empty_adapter_config(self):
        """Test with empty adapter configuration."""
        backend = "memory"
        adapter_config = {}
        error = FactoryCreationError(backend, adapter_config)

        expected_message = f"Factory failed to create adapter for backend '{backend}'"
        assert error.message == expected_message
        assert error.details["adapter_config"] == {}

    def test_complex_adapter_config(self):
        """Test with complex adapter configuration."""
        backend = "redis_cluster"
        adapter_config = {
            "nodes": [
                {"host": "node1.redis.com", "port": 7000},
                {"host": "node2.redis.com", "port": 7001},
                {"host": "node3.redis.com", "port": 7002},
            ],
            "password": "secret123",
            "ssl": True,
            "connection_pool": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
            "decode_responses": True,
        }
        error = FactoryCreationError(backend, adapter_config)

        assert error.details["backend"] == backend
        assert error.details["adapter_config"] == adapter_config
        # Verify the complex structure is preserved
        assert len(error.details["adapter_config"]["nodes"]) == 3
        assert error.details["adapter_config"]["connection_pool"]["max_connections"] == 100

    def test_adapter_config_with_special_values(self):
        """Test adapter config with special Python values."""
        backend = "test"
        adapter_config = {
            "none_value": None,
            "boolean_true": True,
            "boolean_false": False,
            "zero": 0,
            "negative": -1,
            "float": 3.14159,
            "list": [1, 2, 3],
            "nested_dict": {"key": "value"},
        }
        error = FactoryCreationError(backend, adapter_config)

        assert error.details["adapter_config"] == adapter_config
        # Verify all special values are preserved correctly
        assert error.details["adapter_config"]["none_value"] is None
        assert error.details["adapter_config"]["boolean_true"] is True
        assert error.details["adapter_config"]["boolean_false"] is False


class TestFactoryExceptionsInheritance:
    """Test inheritance hierarchy of factory exceptions."""

    def test_all_inherit_from_factory_error(self):
        """Test that all factory exceptions inherit from FactoryError."""
        exceptions = [
            FactoryNotFoundError("backend"),
            FactoryRegistrationError("backend", "reason"),
            FactoryCreationError("backend", {}),
        ]

        for exception in exceptions:
            assert isinstance(exception, FactoryError)
            assert isinstance(exception, OmniCacheError)

    def test_exception_hierarchy_chain(self):
        """Test the complete inheritance chain."""
        error = FactoryNotFoundError("test")

        # Test MRO (Method Resolution Order)
        mro = type(error).__mro__
        assert FactoryNotFoundError in mro
        assert FactoryError in mro
        assert OmniCacheError in mro
        assert Exception in mro
        assert BaseException in mro

    @pytest.mark.parametrize(
        "exception_class,args",
        [
            (FactoryNotFoundError, ("backend",)),
            (FactoryRegistrationError, ("backend", "reason")),
            (FactoryCreationError, ("backend", {})),
        ],
    )
    def test_exception_instantiation(self, exception_class, args):
        """Test that all factory exceptions can be instantiated."""
        exception = exception_class(*args)
        assert isinstance(exception, FactoryError)
        assert hasattr(exception, "message")
        assert hasattr(exception, "details")
        assert hasattr(exception, "timestamp")

    def test_factory_exceptions_are_catchable_as_factory_error(self):
        """Test that specific factory exceptions can be caught as FactoryError."""
        exceptions = [
            FactoryNotFoundError("backend"),
            FactoryRegistrationError("backend", "reason"),
            FactoryCreationError("backend", {}),
        ]

        for exception in exceptions:
            try:
                raise exception
            except FactoryError as caught:
                assert caught is exception
            except Exception:
                pytest.fail("Exception should be catchable as FactoryError")

    def test_factory_exceptions_details_structure(self):
        """Test that all factory exceptions have proper details structure."""
        not_found_error = FactoryNotFoundError("backend", ["memory", "redis"])
        registration_error = FactoryRegistrationError("backend", "reason")
        creation_error = FactoryCreationError("backend", {"key": "value"})

        # Test that all have required details
        assert isinstance(not_found_error.details, dict)
        assert isinstance(registration_error.details, dict)
        assert isinstance(creation_error.details, dict)

        # Test specific details
        assert "backend" in not_found_error.details
        assert "available_backends" in not_found_error.details

        assert "backend" in registration_error.details
        assert "reason" in registration_error.details

        assert "backend" in creation_error.details
        assert "adapter_config" in creation_error.details

    def test_backend_name_consistency(self):
        """Test that backend names are handled consistently across exceptions."""
        backend_name = "test_backend_name"

        not_found = FactoryNotFoundError(backend_name)
        registration = FactoryRegistrationError(backend_name, "test reason")
        creation = FactoryCreationError(backend_name, {})

        # All should store the same backend name
        assert not_found.details["backend"] == backend_name
        assert registration.details["backend"] == backend_name
        assert creation.details["backend"] == backend_name

        # All should mention backend in their message
        assert backend_name in not_found.message
        assert backend_name in registration.message
        assert backend_name in creation.message
