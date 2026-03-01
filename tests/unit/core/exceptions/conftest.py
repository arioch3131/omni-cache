"""
Pytest configuration and fixtures for exception tests.
"""

import time
from unittest.mock import Mock, patch

import pytest

from omni_cache.core.exceptions import (
    AdapterConnectionError,
    AdapterError,
    AdapterNotConnectedError,
    AdapterNotFoundError,
    AdapterRegistrationError,
    CacheError,
    CacheExpiredError,
    CacheFullError,
    CacheKeyError,
    ConfigurationError,
    ConnectionFailedError,
    ConnectionTimeoutError,
    DeserializationFailedError,
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    FactoryRegistrationError,
    HealthCheckError,
    InvalidConfigurationError,
    InvalidRouteError,
    MissingConfigurationError,
    OmniCacheError,
    OmniConnectionError,
    OperationError,
    OperationFailedError,
    OperationNotSupportedError,
    OperationTimeoutError,
    PoolEmptyError,
    PoolError,
    PoolFullError,
    PoolObjectError,
    RouteNotFoundError,
    RoutingError,
    SerializationError,
    SerializationFailedError,
)


@pytest.fixture
def sample_details():
    """Fixture providing sample exception details."""
    return {
        "operation": "test_operation",
        "timeout": 5.0,
        "key": "test_key",
        "adapter": "test_adapter",
        "count": 42,
        "config": {"host": "localhost", "port": 6379},
    }


@pytest.fixture
def sample_cause():
    """Fixture providing sample exception cause."""
    return ValueError("Original error that caused the problem")


@pytest.fixture
def mock_time():
    """Fixture providing mocked time for consistent timestamps."""
    with patch("time.time") as mock:
        mock.return_value = 1234567890.0
        yield mock


@pytest.fixture
def all_exception_classes():
    """Fixture providing all exception classes for comprehensive testing."""
    return {
        # Base
        "OmniCacheError": (OmniCacheError, ("Base error",)),
        # Adapter exceptions
        "AdapterError": (AdapterError, ("Adapter error",)),
        "AdapterNotFoundError": (AdapterNotFoundError, ("test_adapter",)),
        "AdapterRegistrationError": (AdapterRegistrationError, ("adapter", "reason")),
        "AdapterNotConnectedError": (AdapterNotConnectedError, ("adapter",)),
        "AdapterConnectionError": (AdapterConnectionError, ("adapter", "backend")),
        # Cache exceptions
        "CacheError": (CacheError, ("Cache error",)),
        "CacheKeyError": (CacheKeyError, ("key", "operation")),
        "CacheFullError": (CacheFullError, (100,)),
        "CacheExpiredError": (CacheExpiredError, ("key", time.time())),
        # Configuration exceptions
        "ConfigurationError": (ConfigurationError, ("Config error",)),
        "InvalidConfigurationError": (InvalidConfigurationError, ("key", "value")),
        "MissingConfigurationError": (MissingConfigurationError, ("key",)),
        # Connection exceptions
        "OmniConnectionError": (OmniConnectionError, ("Connection error",)),
        "ConnectionTimeoutError": (ConnectionTimeoutError, ("operation", 5.0)),
        "ConnectionFailedError": (ConnectionFailedError, ("target",)),
        # Factory exceptions
        "FactoryError": (FactoryError, ("Factory error",)),
        "FactoryNotFoundError": (FactoryNotFoundError, ("backend",)),
        "FactoryRegistrationError": (FactoryRegistrationError, ("backend", "reason")),
        "FactoryCreationError": (FactoryCreationError, ("backend", {})),
        # Operation exceptions
        "OperationError": (OperationError, ("Operation error",)),
        "OperationTimeoutError": (OperationTimeoutError, ("operation", 5.0)),
        "OperationNotSupportedError": (OperationNotSupportedError, ("operation", "adapter")),
        "OperationFailedError": (OperationFailedError, ("operation",)),
        # Pool exceptions
        "PoolError": (PoolError, ("Pool error",)),
        "PoolEmptyError": (PoolEmptyError, ()),
        "PoolFullError": (PoolFullError, ()),
        "PoolObjectError": (PoolObjectError, ("reason",)),
        # Serialization exceptions
        "SerializationError": (SerializationError, ("Serialization error",)),
        "SerializationFailedError": (SerializationFailedError, ("type", "serializer")),
        "DeserializationFailedError": (DeserializationFailedError, ("type", "deserializer")),
        # Other exceptions
        "HealthCheckError": (HealthCheckError, ("component", "check")),
        "RoutingError": (RoutingError, ("Routing error",)),
        "RouteNotFoundError": (RouteNotFoundError, ("key",)),
        "InvalidRouteError": (InvalidRouteError, ("pattern", "reason")),
    }


@pytest.fixture
def base_exception_classes():
    """Fixture providing base exception classes for inheritance testing."""
    return {
        AdapterError: [
            AdapterNotFoundError,
            AdapterRegistrationError,
            AdapterNotConnectedError,
            AdapterConnectionError,
        ],
        CacheError: [
            CacheKeyError,
            CacheFullError,
            CacheExpiredError,
        ],
        ConfigurationError: [
            InvalidConfigurationError,
            MissingConfigurationError,
        ],
        OmniConnectionError: [
            ConnectionTimeoutError,
            ConnectionFailedError,
        ],
        FactoryError: [
            FactoryNotFoundError,
            FactoryRegistrationError,
            FactoryCreationError,
        ],
        OperationError: [
            OperationTimeoutError,
            OperationNotSupportedError,
            OperationFailedError,
        ],
        PoolError: [
            PoolEmptyError,
            PoolFullError,
            PoolObjectError,
        ],
        SerializationError: [
            SerializationFailedError,
            DeserializationFailedError,
        ],
        RoutingError: [
            RouteNotFoundError,
            InvalidRouteError,
        ],
    }


@pytest.fixture
def retriable_exceptions():
    """Fixture providing exceptions that should be considered retriable."""
    return [
        ConnectionTimeoutError("test", 5.0),
        ConnectionFailedError("test"),
        OperationTimeoutError("test", 5.0),
        PoolEmptyError("test"),
        CacheFullError(100),
    ]


@pytest.fixture
def non_retriable_exceptions():
    """Fixture providing exceptions that should not be considered retriable."""
    return [
        ConfigurationError("test"),
        InvalidConfigurationError("key", "value"),
        MissingConfigurationError("key"),
        OperationNotSupportedError("op", "adapter"),
        FactoryNotFoundError("backend"),
        FactoryRegistrationError("backend", "reason"),
    ]


@pytest.fixture
def mock_logger():
    """Fixture providing a mock logger for testing logging behavior."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    return logger


@pytest.fixture
def complex_exception_chain():
    """Fixture providing a complex exception chain for testing."""
    # Create a chain of exceptions
    root_cause = ValueError("Root cause error")

    intermediate_cause = RuntimeError("Intermediate error")
    intermediate_cause.__cause__ = root_cause

    final_exception = OperationFailedError(
        "final_operation", "Chain of failures", {"level": 3}, intermediate_cause
    )

    return final_exception, intermediate_cause, root_cause


@pytest.fixture
def unicode_test_data():
    """Fixture providing unicode test data for internationalization testing."""
    return {
        "messages": [
            "Erreur de configuration",
            "配置错误",
            "Конфигурационная ошибка",
            "🚀 Rocket error with emoji",
            "Error with special chars: àáâãäåæçèéêë",
        ],
        "keys": [
            "clé_française",
            "中文键",
            "русский_ключ",
            "emoji_key_🔑",
        ],
        "components": [
            "composant_système",
            "系统组件",
            "системный_компонент",
        ],
    }


@pytest.fixture(
    params=[
        None,
        {},
        {"simple": "value"},
        {"nested": {"deep": {"value": 42}}},
        {"list": [1, 2, 3]},
        {"mixed": {"str": "value", "int": 42, "bool": True, "none": None}},
    ]
)
def various_details(request):
    """Fixture providing various types of details dictionaries."""
    return request.param


@pytest.fixture(
    params=[
        ValueError("Test ValueError"),
        TypeError("Test TypeError"),
        RuntimeError("Test RuntimeError"),
        ConnectionError("Test ConnectionError"),
        TimeoutError("Test TimeoutError"),
        KeyError("test_key"),
        AttributeError("Test AttributeError"),
    ]
)
def various_causes(request):
    """Fixture providing various types of exception causes."""
    return request.param


@pytest.fixture
def performance_test_data():
    """Fixture providing data for performance testing."""
    return {
        "large_details": {f"key_{i}": f"value_{i}" for i in range(1000)},
        "deep_nesting": {
            f"level_{i}": {f"sublevel_{j}": f"value_{i}_{j}" for j in range(10)} for i in range(100)
        },
        "large_message": "A" * 10000,
        "many_exceptions": 1000,
    }


# Parametrized fixtures for comprehensive testing
@pytest.fixture(
    params=[
        ("", ""),
        ("simple", "simple"),
        ("with spaces", "with spaces"),
        ("with-dashes", "with-dashes"),
        ("with_underscores", "with_underscores"),
        ("with.dots", "with.dots"),
        ("with/slashes", "with/slashes"),
        ("MixedCaseString", "MixedCaseString"),
        ("123numbers", "123numbers"),
    ]
)
def string_variations(request):
    """Fixture providing various string formats for testing."""
    return request.param


@pytest.fixture(
    params=[
        0,
        0.0,
        1,
        1.5,
        -1,
        -1.5,
        float("inf"),
        1e6,
        3.14159265359,
    ]
)
def numeric_variations(request):
    """Fixture providing various numeric values for testing."""
    return request.param


# Helper functions for tests
def assert_exception_structure(exception, expected_message_contains=None):
    """Helper function to assert common exception structure."""
    assert isinstance(exception, OmniCacheError)
    assert hasattr(exception, "message")
    assert hasattr(exception, "details")
    assert hasattr(exception, "timestamp")
    assert hasattr(exception, "cause")

    assert isinstance(exception.message, str)
    assert isinstance(exception.details, dict)
    assert isinstance(exception.timestamp, float)

    if expected_message_contains:
        assert expected_message_contains in exception.message


def create_exception_with_all_params(exception_class, *args, **kwargs):
    """Helper function to create exceptions with maximum parameters."""
    try:
        return exception_class(*args, **kwargs)
    except TypeError:
        # If too many parameters, try with fewer
        if len(args) > 1:
            return create_exception_with_all_params(exception_class, *args[:-1], **kwargs)
        elif kwargs:
            # Remove one kwarg and try again
            key_to_remove = next(iter(kwargs))
            new_kwargs = {k: v for k, v in kwargs.items() if k != key_to_remove}
            return create_exception_with_all_params(exception_class, *args, **new_kwargs)
        else:
            # Minimum parameters
            return exception_class(*args)


# Custom markers for test categories
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "unicode: mark test as unicode/i18n test")
    config.addinivalue_line("markers", "edge_case: mark test as edge case test")
