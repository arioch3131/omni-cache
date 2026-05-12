"""
Omni-Cache: Universal cache and pool manager with pluggable backends.

A comprehensive caching and object pooling library that provides:
- Multiple backend support (Memory, Redis, Memcached, AdaptiveMemoryPool)
- Unified interface for cache and pool operations
- Intelligent routing and fallback mechanisms
- Comprehensive statistics and health monitoring
- Hot-reloadable configuration system
- Production-ready decorators and utilities

Basic usage:
    >>> from omni_cache import cached, get_global_manager
    >>>
    >>> # Simple function caching
    >>> @cached(ttl=300)
    >>> def expensive_function(x):
    ...     return complex_computation(x)
    >>>
    >>> # Manager-based usage
    >>> manager = get_global_manager()
    >>> manager.set("key", "value", ttl=60)
    >>> value = manager.get("key")

Advanced usage:
    >>> from omni_cache import CacheManager, create_adapter, CacheBackend
    >>>
    >>> # Multi-backend setup
    >>> manager = CacheManager()
    >>>
    >>> # Add memory cache
    >>> memory_adapter = create_adapter(CacheBackend.MEMORY, {"max_size": 1000})
    >>> manager.register_adapter("fast", memory_adapter)
    >>>
    >>> # Add Redis cache (if available)
    >>> try:
    ...     redis_adapter = create_adapter(CacheBackend.REDIS, {
    ...         "host": "localhost", "port": 6379
    ...     })
    ...     manager.register_adapter("persistent", redis_adapter)
    ... except Exception:
    ...     pass  # Redis not available
    >>>
    >>> # Use with routing
    >>> manager.add_routing_rule("cache", "fast")
    >>> manager.add_routing_rule("store", "persistent")
    >>>
    >>> manager.set("cache:temp", data)    # -> fast (memory)
    >>> manager.set("store:user", user)    # -> persistent (redis)
"""

# Version information
__version__ = "2.1.0"
__author__ = "Omni-Cache Contributors"
__license__ = "MIT"
__description__ = "Universal cache and pool manager with pluggable backends"

# Standard library imports
import logging
import os
import warnings
from collections.abc import Callable
from typing import Any, cast

from .adapters.disk import (
    DiskAdapter,
    DiskAdapterConfig,
)
from .adapters.memory import (
    CacheItem,
    MemoryAdapter,
    MemoryAdapterConfig,
)
from .core.config import (  # Configuration classes; Manager and loader; Enums; Global functions
    AdapterConfig,
    BaseConfig,
    ConfigFormat,
    ConfigLoader,
    ConfigManager,
    GlobalConfig,
    get_global_config_manager,
    load_config_from_env,
    set_global_config_manager,
    temporary_config,
)
from .core.exceptions import (
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
    FactoryCreationError,
    FactoryError,
    FactoryNotFoundError,
    FactoryRegistrationError,
    InvalidConfigurationError,
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
    exception_context,
    get_exception_summary,
    handle_and_wrap_exception,
    is_retriable_error,
)
from .core.factories import (
    AbstractFactory,
    DiskAdapterFactory,
    FactoryMetadata,
    FactoryRegistry,
    MemcachedAdapterFactory,
    MemoryAdapterFactory,
    RedisAdapterFactory,
    SmartPoolAdapterFactory,
    create_adapter,
    get_global_registry,
    list_available_backends,
    set_global_registry,
    temporary_factory,
)
from .core.interfaces import (
    AdapterInterface,
    AnyAdapter,
    AsyncKeyValueInterface,
    AsyncPoolInterface,
    CacheAdapter,
    CacheBackend,
    CacheStats,
    Configurable,
    FactoryInterface,
    KeyValueInterface,
    ManagerInterface,
    PoolAdapter,
    PoolInterface,
    PoolStats,
    Serializable,
    StatisticsInterface,
)
from .core.manager import (
    AdapterRegistry,
    CacheManager,
    ManagerConfig,
    get_global_manager,
    set_global_manager,
)
from .utils.decorators import (
    CacheConfig,
    KeyGenerator,
    PoolConfig,
    async_cached,
    cache_key,
    cached,
    clear_cache,
    get_cache_stats,
    invalidate_cache,
    memoize,
    pooled,
    retry_with_cache,
    timed_cache,
)

# Configure basic logging if not already configured
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

# Suppress debug logs from omni_cache by default
logging.getLogger("omni_cache").setLevel(logging.WARNING)

# Optional adapters - import only if dependencies available
RedisAdapter: Any = None
RedisAdapterConfig: Any = None
try:
    from .adapters.redis import (
        RedisAdapter,
        RedisAdapterConfig,
    )

    HAS_REDIS_ADAPTER = True
except ImportError:
    HAS_REDIS_ADAPTER = False

MemcachedAdapter: Any = None
MemcachedAdapterConfig: Any = None
try:
    from .adapters.memcached import (
        MemcachedAdapter,
        MemcachedAdapterConfig,
    )

    HAS_MEMCACHED_ADAPTER = True
except ImportError:
    HAS_MEMCACHED_ADAPTER = False

SmartPoolAdapter: Any = None
SmartPoolAdapterConfig: Any = None
try:
    from .adapters.smartpool import (
        SmartPoolAdapter,
        SmartPoolAdapterConfig,
    )

    HAS_SMARTPOOL_ADAPTER = True
except ImportError:
    HAS_SMARTPOOL_ADAPTER = False

# ============================================================================
# Convenience Functions and Setup
# ============================================================================


def setup(
    config_file: str | None = None,
    log_level: str = "INFO",
    auto_discover: bool = True,
) -> CacheManager:
    """
    Quick setup function for omni-cache.

    Args:
        config_file: Optional configuration file path
        log_level: Logging level for omni-cache
        auto_discover: Whether to auto-discover and register available adapters
        enable_hot_reload: Whether to enable configuration hot reloading

    Returns:
        Configured CacheManager instance

    Example:
        >>> manager = setup(
        ...     config_file="cache_config.yaml",
        ...     log_level="INFO",
        ...     auto_discover=True
        ... )
        >>> manager.set("key", "value")
    """
    # Configure logging
    logging.getLogger("omni_cache").setLevel(getattr(logging, log_level.upper()))

    # Setup configuration manager
    if config_file:
        config_manager = ConfigManager(config_file)
        set_global_config_manager(config_manager)
        global_config = config_manager.get_global_config()
    else:
        config_manager = get_global_config_manager()
        global_config = GlobalConfig()

    # Create cache manager with configuration
    manager_config = ManagerConfig(
        default_adapter=global_config.default_cache_adapter,
        auto_connect=global_config.auto_connect_adapters,
        enable_global_stats=global_config.enable_global_stats,
        health_check_interval=global_config.health_check_interval,
        enable_routing=global_config.enable_routing,
        namespace_separator=global_config.namespace_separator,
        fallback_adapter=global_config.fallback_adapter,
        log_level=global_config.log_level,
        extra_config=global_config.extra,
    )

    manager: CacheManager[Any, Any] = CacheManager(manager_config)

    if auto_discover:
        # Auto-discover and register available adapters
        _auto_register_adapters(manager, config_manager)

    # Set as global manager
    set_global_manager(manager)

    return manager


def _auto_register_adapters(manager: CacheManager, config_manager: ConfigManager) -> None:
    """Auto-register available adapters based on configuration and availability."""

    # Get adapter configurations
    adapter_names = config_manager.list_adapters()
    adapter_configs = {}
    for name in adapter_names:
        config = config_manager.get_adapter_config(name)
        if config:
            adapter_configs[name] = config

    if not adapter_configs:
        # No configuration available, register basic memory adapter
        memory_adapter: MemoryAdapter[Any, Any] = MemoryAdapter()
        manager.register_adapter("memory", memory_adapter)
        return

    # Register adapters from configuration
    factory_registry = get_global_registry()

    for name, config in adapter_configs.items():
        if not config.enabled:
            continue

        try:
            # Create adapter using factory
            adapter = factory_registry.create_adapter(config.backend, config.extra_config)
            manager.register_adapter(name, adapter, config.to_dict())

        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.getLogger(__name__).warning(
                "Failed to register adapter '%s' (%s): %s", name, config.backend, e
            )


def discover_backends() -> dict[str, dict[str, Any]]:
    """
    Discover available backends and their capabilities.

    Returns:
        Dictionary mapping backend names to their metadata

    Example:
        >>> backends = discover_backends()
        >>> print(f"Available backends: {list(backends.keys())}")
        >>> print(f"Redis available: {'redis' in backends}")
    """
    registry = get_global_registry()
    return {backend: metadata.__dict__ for backend, metadata in registry.get_all_metadata().items()}


def quick_cache(
    backend: str | CacheBackend = CacheBackend.MEMORY, **config: Any
) -> KeyValueInterface:
    """
    Quickly create a cache adapter for simple use cases.

    Args:
        backend: Backend type to create
        **config: Configuration for the adapter

    Returns:
        Configured cache adapter

    Example:
        >>> cache = quick_cache("memory", max_size=1000)
        >>> cache.set("key", "value", ttl=60)
        >>> value = cache.get("key")
    """
    return cast(KeyValueInterface[Any, Any], create_adapter(backend, config))


def quick_pool(
    backend: str | CacheBackend, factory_function: Callable[..., Any], **config: Any
) -> PoolInterface:
    """
    Quickly create a pool adapter for simple use cases.

    Args:
        backend: Backend type to create
        factory_function: Function to create pool objects
        **config: Configuration for the adapter

    Returns:
        Configured pool adapter

    Example:
        >>> def create_connection():
        ...     return DatabaseConnection()
        >>> pool = quick_pool("adaptive", create_connection, max_size=10)
        >>> with pool.borrow() as conn:
        ...     conn.execute("SELECT 1")
    """
    config["factory_function"] = factory_function
    return cast(PoolInterface[Any], create_adapter(backend, config))


def get_version_info() -> dict[str, Any]:
    """
    Get version and environment information.

    Returns:
        Dictionary with version and capability information
    """
    python_version = f"{__import__('sys').version_info.major}"
    python_version += f".{__import__('sys').version_info.minor}"
    return {
        "version": __version__,
        "python_version": python_version,
        "capabilities": {
            "redis_adapter": HAS_REDIS_ADAPTER,
            "memcached_adapter": HAS_MEMCACHED_ADAPTER,
            "adaptive_adapter": HAS_SMARTPOOL_ADAPTER,
            "yaml_config": "yaml" in globals(),
            "toml_config": "tomllib" in globals(),
        },
        "available_backends": list_available_backends(),
    }


# ============================================================================
# Environment-based Configuration
# ============================================================================


def configure_from_env(prefix: str = "OMNI_CACHE_") -> None:
    """
    Configure omni-cache from environment variables.

    Args:
        prefix: Prefix for environment variables

    Environment variables:
        OMNI_CACHE_LOG_LEVEL: Logging level (DEBUG, INFO, WARNING, ERROR)
        OMNI_CACHE_DEFAULT_BACKEND: Default cache backend
        OMNI_CACHE_AUTO_SETUP: Whether to auto-setup on import

    Example:
        >>> import os
        >>> os.environ["OMNI_CACHE_LOG_LEVEL"] = "DEBUG"
        >>> os.environ["OMNI_CACHE_DEFAULT_BACKEND"] = "redis"
        >>> configure_from_env()
    """
    # Load configuration from environment
    # pylint: disable=too-many-function-args
    env_config = load_config_from_env(prefix)

    if not env_config:
        return

    # Apply logging configuration
    log_level = env_config.get("log_level", "INFO").upper()
    logging.getLogger("omni_cache").setLevel(getattr(logging, log_level, logging.INFO))

    # Update global configuration
    try:
        config_manager = get_global_config_manager()
        config_manager.update_global_config(env_config)
    except Exception as e:  # pylint: disable=broad-exception-caught
        warnings.warn(
            f"Failed to apply environment configuration: {e}",
            UserWarning,
            stacklevel=2,
        )


# ============================================================================
# Auto-setup based on environment
# ============================================================================


def _run_auto_setup() -> None:
    """Run auto-setup if requested via environment variable."""
    _auto_setup = os.getenv("OMNI_CACHE_AUTO_SETUP", "false").lower() in ("true", "1", "yes")

    if _auto_setup:
        try:
            # Configure from environment
            configure_from_env()

            # Auto-setup with default configuration
            setup(auto_discover=True)

        except Exception as e:  # pylint: disable=broad-exception-caught
            warnings.warn(f"Auto-setup failed: {e}", UserWarning, stacklevel=2)


_run_auto_setup()

# ============================================================================
# Public API Definition
# ============================================================================

__all__ = [
    # Version information
    "__version__",
    # Core interfaces
    "KeyValueInterface",
    "PoolInterface",
    "AdapterInterface",
    "StatisticsInterface",
    "FactoryInterface",
    "ManagerInterface",
    "AsyncKeyValueInterface",
    "AsyncPoolInterface",
    # Data classes and enums
    "CacheStats",
    "PoolStats",
    "CacheBackend",
    "Serializable",
    "Configurable",
    "CacheAdapter",
    "PoolAdapter",
    "AnyAdapter",
    # Manager and factory system
    "CacheManager",
    "ManagerConfig",
    "AdapterRegistry",
    "get_global_manager",
    "set_global_manager",
    "AbstractFactory",
    "FactoryRegistry",
    "FactoryMetadata",
    "DiskAdapterFactory",
    "MemoryAdapterFactory",
    "MemcachedAdapterFactory",
    "RedisAdapterFactory",
    "SmartPoolAdapterFactory",
    "get_global_registry",
    "set_global_registry",
    "create_adapter",
    "list_available_backends",
    "temporary_factory",
    # Configuration system
    "BaseConfig",
    "GlobalConfig",
    "AdapterConfig",
    "ConfigManager",
    "ConfigLoader",
    "ConfigFormat",
    "get_global_config_manager",
    "set_global_config_manager",
    "temporary_config",
    "load_config_from_env",
    # Exception system
    "OmniCacheError",
    "AdapterError",
    "AdapterNotFoundError",
    "AdapterRegistrationError",
    "AdapterNotConnectedError",
    "AdapterConnectionError",
    "ConfigurationError",
    "InvalidConfigurationError",
    "MissingConfigurationError",
    "OmniConnectionError",
    "ConnectionTimeoutError",
    "ConnectionFailedError",
    "OperationError",
    "OperationTimeoutError",
    "OperationNotSupportedError",
    "OperationFailedError",
    "CacheError",
    "CacheKeyError",
    "CacheFullError",
    "CacheExpiredError",
    "PoolError",
    "PoolEmptyError",
    "PoolFullError",
    "PoolObjectError",
    "FactoryError",
    "FactoryNotFoundError",
    "FactoryRegistrationError",
    "FactoryCreationError",
    "handle_and_wrap_exception",
    "exception_context",
    "is_retriable_error",
    "get_exception_summary",
    # Built-in adapters
    "MemoryAdapter",
    "MemoryAdapterConfig",
    "DiskAdapter",
    "DiskAdapterConfig",
    "CacheItem",
    "MemcachedAdapter",
    "MemcachedAdapterConfig",
    "RedisAdapter",
    "RedisAdapterConfig",
    "SmartPoolAdapter",
    "SmartPoolAdapterConfig",
    # Decorators and utilities
    "cached",
    "memoize",
    "timed_cache",
    "pooled",
    "async_cached",
    "cache_key",
    "invalidate_cache",
    "retry_with_cache",
    "CacheConfig",
    "PoolConfig",
    "KeyGenerator",
    "clear_cache",
    "get_cache_stats",
    # Convenience functions
    "setup",
    "discover_backends",
    "quick_cache",
    "quick_pool",
    "get_version_info",
    "configure_from_env",
]


# ============================================================================
# Backwards Compatibility and Aliases
# ============================================================================

# Common aliases for convenience
Cache = KeyValueInterface
Pool = PoolInterface
Manager = CacheManager


# pylint: disable=invalid-name
def CachePool(*args: Any, **kwargs: Any) -> CacheManager[Any, Any]:
    """
    Deprecated names (with warnings)
    """
    warnings.warn(
        "CachePool is deprecated, use CacheManager instead", DeprecationWarning, stacklevel=2
    )
    return CacheManager(*args, **kwargs)


# ============================================================================
# Module Metadata
# ============================================================================

# Additional metadata for introspection
_module_info = {
    "name": "omni-cache",
    "version": __version__,
    "description": __description__,
    "author": __author__,
    "license": __license__,
    "has_redis": HAS_REDIS_ADAPTER,
    "has_memcached": HAS_MEMCACHED_ADAPTER,
    "has_adaptive": HAS_SMARTPOOL_ADAPTER,
    "yaml_config": "yaml" in globals(),
    "toml_config": "tomllib" in globals(),
}


def info() -> None:
    """
    Print information about the omni-cache installation.

    Returns:
        None
    """
    print(f"Omni-Cache {__version__}")
    print(f"Description: {__description__}")
    print(f"Author: {__author__}")
    print(f"License: {__license__}")
    print()
    print("Capabilities:")
    version_info = get_version_info()
    for capability, available in version_info["capabilities"].items():
        status = "✓" if available else "✗"
        print(f"  {status} {capability}")
    print()
    print(f"Available backends: {', '.join(version_info['available_backends'])}")
    print()
    print("Quick start:")
    print("  from omni_cache import cached, setup")
    print("  manager = setup()  # Quick setup")
    print("  @cached(ttl=300)   # Simple caching")
    print("  def my_function(): pass")


# Set module-level attributes for inspection
globals().update(_module_info)
