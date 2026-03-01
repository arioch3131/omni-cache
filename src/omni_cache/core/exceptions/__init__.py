"""
Declaration of all exceptions.
"""

from .adapter_exceptions import (
    AdapterConnectionError,
    AdapterError,
    AdapterNotConnectedError,
    AdapterNotFoundError,
    AdapterRegistrationError,
)
from .cache_exceptions import CacheError, CacheExpiredError, CacheFullError, CacheKeyError
from .config_exceptions import (
    ConfigurationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)
from .connection_exceptions import (
    ConnectionFailedError,
    ConnectionTimeoutError,
    OmniConnectionError,
)
from .exceptions import (
    exception_context,
    get_exception_summary,
    handle_and_wrap_exception,
    is_retriable_error,
)
from .factory_exceptions import (
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    FactoryRegistrationError,
)
from .omni_cache_error import OmniCacheError
from .operation_exceptions import (
    OperationError,
    OperationFailedError,
    OperationNotSupportedError,
    OperationTimeoutError,
)
from .other_exceptions import HealthCheckError, InvalidRouteError, RouteNotFoundError, RoutingError
from .pool_exceptions import PoolEmptyError, PoolError, PoolFullError, PoolObjectError
from .serialization_exceptions import (
    DeserializationFailedError,
    SerializationError,
    SerializationFailedError,
)

__all__ = [
    # Base exceptions
    "OmniCacheError",
    # Adapter exceptions
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterRegistrationError",
    "AdapterNotConnectedError",
    "AdapterConnectionError",
    # Configuration exceptions
    "ConfigurationError",
    "InvalidConfigurationError",
    "MissingConfigurationError",
    # Connection exceptions
    "OmniConnectionError",
    "ConnectionTimeoutError",
    "ConnectionFailedError",
    # Operation exceptions
    "OperationError",
    "OperationTimeoutError",
    "OperationNotSupportedError",
    "OperationFailedError",
    # Cache exceptions
    "CacheError",
    "CacheKeyError",
    "CacheFullError",
    "CacheExpiredError",
    # Pool exceptions
    "PoolError",
    "PoolEmptyError",
    "PoolFullError",
    "PoolObjectError",
    # Serialization exceptions
    "SerializationError",
    "SerializationFailedError",
    "DeserializationFailedError",
    # Factory exceptions
    "FactoryError",
    "FactoryNotFoundError",
    "FactoryRegistrationError",
    "FactoryCreationError",
    # Health check exceptions
    "HealthCheckError",
    # Routing exceptions
    "RoutingError",
    "RouteNotFoundError",
    "InvalidRouteError",
    # Utility functions
    "handle_and_wrap_exception",
    "exception_context",
    "is_retriable_error",
    "get_exception_summary",
]
