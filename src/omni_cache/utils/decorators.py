"""
Utility decorators for omni-cache.

This module provides convenient decorators for caching function results,
pooling objects, and other common patterns. These decorators integrate
seamlessly with the omni-cache system.
"""

import functools
import hashlib
import json
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import (
    Any,
    TypeVar,
    cast,
)

from omni_cache.core.exceptions import OperationTimeoutError, PoolEmptyError, exception_context
from omni_cache.core.exceptions.cache_exceptions import CacheError
from omni_cache.core.manager import CacheManager, get_global_manager

# Type variables
F = TypeVar("F", bound=Callable[..., Any])
T = TypeVar("T")

# pylint: disable=too-many-positional-arguments,redefined-outer-name,protected-access
# pylint: disable=too-many-statements,too-many-branches


@dataclass
class CacheConfig:
    """Configuration for cache decorators."""

    ttl: int | float | None = None
    namespace: str | None = None
    key_prefix: str = ""
    adapter: str | None = None
    ignore_args: set[int] = field(default_factory=set)
    ignore_kwargs: set[str] = field(default_factory=set)
    key_generator: Callable[..., str] | None = None
    serializer: Callable[[Any], str] | None = None
    deserializer: Callable[[str], Any] | None = None
    on_hit: Callable[[str, Any], None] | None = None
    on_miss: Callable[[str], None] | None = None
    on_error: Callable[[Exception], Any] | None = None
    enable_stats: bool = True


@dataclass
class PoolConfig:
    """Configuration for pool decorators."""

    adapter: str | None = None
    timeout: float | None = None
    max_retries: int = 3
    retry_delay: float = 0.1
    on_borrow: Callable[[Any], None] | None = None
    on_return: Callable[[Any], None] | None = None
    on_error: Callable[[Exception], Any] | None = None
    auto_create: bool = False
    factory_function: Callable[[], Any] | None = None


class KeyGenerator:
    """Utility class for generating cache keys."""

    @staticmethod
    def default_key_generator(
        func: Callable, args: tuple, kwargs: dict[str, Any], config: CacheConfig
    ) -> str:
        """Generate a default cache key based on function signature."""
        # Get function name and module
        func_name = f"{func.__module__}.{func.__qualname__}"

        # Filter out ignored arguments
        filtered_args = []
        for i, arg in enumerate(args):
            if i not in config.ignore_args:
                filtered_args.append(arg)

        filtered_kwargs = {k: v for k, v in kwargs.items() if k not in config.ignore_kwargs}

        # Create key components
        key_parts = [func_name]

        # Add arguments to key
        if filtered_args:
            try:
                if config.serializer:
                    args_str = config.serializer(filtered_args)
                else:
                    args_str = json.dumps(filtered_args, sort_keys=True, default=str)
                key_parts.append(f"args:{KeyGenerator._hash_string(args_str)}")
            except (TypeError, ValueError):
                # Fallback to string representation
                args_str = str(filtered_args)
                key_parts.append(f"args:{KeyGenerator._hash_string(args_str)}")

        # Add keyword arguments to key
        if filtered_kwargs:
            try:
                if config.serializer:
                    kwargs_str = config.serializer(filtered_kwargs)
                else:
                    kwargs_str = json.dumps(filtered_kwargs, sort_keys=True, default=str)
                key_parts.append(f"kwargs:{KeyGenerator._hash_string(kwargs_str)}")
            except (TypeError, ValueError):
                # Fallback to string representation
                kwargs_str = str(sorted(filtered_kwargs.items()))
                key_parts.append(f"kwargs:{KeyGenerator._hash_string(kwargs_str)}")

        # Combine parts
        key = ":".join(key_parts)

        # Add prefix and namespace
        if config.key_prefix:
            key = f"{config.key_prefix}:{key}"

        if config.namespace:
            key = f"{config.namespace}:{key}"

        return key

    @staticmethod
    def _hash_string(s: str) -> str:
        """Create a hash of a string for shorter keys."""
        return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def cached(
    ttl: int | float | None = None,
    namespace: str | None = None,
    key_prefix: str = "",
    adapter: str | None = None,
    ignore_args: int | list[int] | set[int] | None = None,
    ignore_kwargs: str | list[str] | set[str] | None = None,
    key_generator: Callable[..., str] | None = None,
    manager: CacheManager | None = None,
    on_hit: Callable[[str, Any], None] | None = None,
    on_miss: Callable[[str], None] | None = None,
    on_error: Callable[[Exception], Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for caching function results.

    Args:
        ttl: Time to live for cached results (seconds)
        namespace: Namespace for cache keys
        key_prefix: Prefix for cache keys
        adapter: Specific adapter to use for caching
        ignore_args: Arguments to ignore when generating cache keys
        ignore_kwargs: Keyword arguments to ignore when generating cache keys
        key_generator: Custom function for generating cache keys
        manager: CacheManager instance (uses global if None)
        on_hit: Callback when cache hit occurs
        on_miss: Callback when cache miss occurs
        on_error: Callback when cache error occurs

    Returns:
        Decorated function with caching functionality
    """

    def decorator(func: F) -> F:
        # Normalize ignore sets
        ignore_args_set = set()
        if ignore_args is not None:
            if isinstance(ignore_args, int):
                ignore_args_set = {ignore_args}
            else:
                ignore_args_set = set(ignore_args)

        ignore_kwargs_set = set()
        if ignore_kwargs is not None:
            if isinstance(ignore_kwargs, str):
                ignore_kwargs_set = {ignore_kwargs}
            else:
                ignore_kwargs_set = set(ignore_kwargs)

        # Create cache configuration
        cache_config = CacheConfig(
            ttl=ttl,
            namespace=namespace,
            key_prefix=key_prefix,
            adapter=adapter,
            ignore_args=ignore_args_set,
            ignore_kwargs=ignore_kwargs_set,
            key_generator=key_generator,
            on_hit=on_hit,
            on_miss=on_miss,
            on_error=on_error,
        )

        # Get cache manager
        cache_manager = manager or get_global_manager()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Generate cache key
            if cache_config.key_generator:
                cache_key = cache_config.key_generator(func, args, kwargs)
            else:
                cache_key = KeyGenerator.default_key_generator(func, args, kwargs, cache_config)

            try:
                # Try to get from cache
                with exception_context("cache_get", key=cache_key, adapter=cache_config.adapter):
                    cached_result = cache_manager.get(cache_key, adapter=cache_config.adapter)

                if cached_result is not None:
                    # Cache hit
                    if cache_config.on_hit:
                        cache_config.on_hit(cache_key, cached_result)

                    if cache_config.deserializer:
                        return cache_config.deserializer(cached_result)
                    return cached_result

                # Cache miss - call function
                if cache_config.on_miss:
                    cache_config.on_miss(cache_key)

                result = func(*args, **kwargs)

                # Cache the result
                try:
                    cache_value = result
                    if cache_config.serializer:
                        cache_value = cache_config.serializer(result)

                    with exception_context(
                        "cache_set", key=cache_key, adapter=cache_config.adapter
                    ):
                        cache_manager.set(
                            cache_key,
                            cache_value,
                            ttl=cache_config.ttl,
                            adapter=cache_config.adapter,
                        )

                except Exception as e:  # pylint: disable=broad-exception-caught
                    # Log cache set failure but don't fail the function
                    logging.getLogger(__name__).warning(
                        "Failed to cache result for key %s: %s", cache_key, e
                    )

                return result

            except Exception as e:  # pylint: disable=broad-exception-caught
                # Handle cache errors
                if cache_config.on_error:
                    fallback_result = cache_config.on_error(e)
                    if fallback_result is not None:
                        return fallback_result

                # Log error and fall back to function execution
                logging.getLogger(__name__).warning("Cache error for key %s: %s", cache_key, e)
                return func(*args, **kwargs)

        # Add cache management methods to the wrapper
        wrapper_any = cast(Any, wrapper)
        wrapper_any._cache_config = cache_config
        wrapper_any._cache_manager = cache_manager
        wrapper_any._original_func = func

        def invalidate(*args: Any, **kwargs: Any) -> bool:
            """Invalidate cache for specific arguments."""
            if cache_config.key_generator:
                cache_key = cache_config.key_generator(func, args, kwargs)
            else:
                cache_key = KeyGenerator.default_key_generator(func, args, kwargs, cache_config)

            return cache_manager.delete(cache_key, adapter=cache_config.adapter)

        def invalidate_all(_: str | None = None) -> int:
            """Invalidate all cached results for this function."""
            # This is a simplified implementation
            # In practice, you might want pattern matching
            count = 0
            try:
                cache_adapter = cache_manager._get_cache_adapter(adapter_name=cache_config.adapter)
                for key in cache_adapter.keys():
                    key_str = str(key)
                    func_prefix = f"{func.__module__}.{func.__qualname__}"
                    if cache_config.namespace:
                        func_prefix = f"{cache_config.namespace}:{func_prefix}"
                    if cache_config.key_prefix:
                        func_prefix = f"{cache_config.key_prefix}:{func_prefix}"

                    if key_str.startswith(func_prefix):
                        if cache_adapter.delete(key):
                            count += 1
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.getLogger(__name__).warning("Error during invalidate_all: %s", e)

            return count

        def get_cache_info() -> dict[str, Any]:
            """Get cache information for this function."""
            return {
                "function": f"{func.__module__}.{func.__qualname__}",
                "ttl": cache_config.ttl,
                "namespace": cache_config.namespace,
                "key_prefix": cache_config.key_prefix,
                "adapter": cache_config.adapter,
                "ignore_args": list(cache_config.ignore_args),
                "ignore_kwargs": list(cache_config.ignore_kwargs),
            }

        wrapper_any.invalidate = invalidate
        wrapper_any.invalidate_all = invalidate_all
        wrapper_any.cache_info = get_cache_info

        return cast(F, wrapper)

    return decorator


# pylint: disable=unused-argument
def memoize(
    maxsize: int | None = None,
    ttl: int | float | None = None,
    namespace: str | None = None,
) -> Callable[[F], F]:
    """
    Simple memoization decorator using memory cache.

    Args:
        maxsize: Maximum number of cached results
        ttl: Time to live for cached results
        namespace: Namespace for cache keys

    Returns:
        Decorated function with memoization
    """
    return cached(
        ttl=ttl,
        namespace=namespace or "memoize",
        adapter="memory",  # Force use of memory adapter
    )


def timed_cache(seconds: int | float, namespace: str | None = None) -> Callable[[F], F]:
    """
    Decorator for time-based caching.

    Args:
        seconds: Cache duration in seconds
        namespace: Namespace for cache keys

    Returns:
        Decorated function with time-based caching
    """
    return cached(ttl=seconds, namespace=namespace or "timed")


def pooled(
    adapter: str | None = None,
    timeout: float | None = None,
    max_retries: int = 3,
    retry_delay: float = 0.1,
    manager: CacheManager | None = None,
    on_borrow: Callable[[Any], None] | None = None,
    on_return: Callable[[Any], None] | None = None,
    on_error: Callable[[Exception], Any] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for functions that need pooled objects.

    The decorated function should accept the pooled object as its first argument.

    Args:
        adapter: Pool adapter to use
        timeout: Timeout for borrowing objects
        max_retries: Number of retry attempts
        retry_delay: Delay between retries
        manager: CacheManager instance
        on_borrow: Callback when object is borrowed
        on_return: Callback when object is returned
        on_error: Callback when pool error occurs

    Returns:
        Decorated function with pooled object management
    """

    def decorator(func: F) -> F:
        pool_config = PoolConfig(
            adapter=adapter,
            timeout=timeout,
            max_retries=max_retries,
            retry_delay=retry_delay,
            on_borrow=on_borrow,
            on_return=on_return,
            on_error=on_error,
        )

        pool_manager = manager or get_global_manager()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            for attempt in range(pool_config.max_retries + 1):
                try:
                    borrow_ctx: AbstractContextManager[Any] = pool_manager.borrow(
                        timeout=pool_config.timeout, adapter=pool_config.adapter
                    )
                    with borrow_ctx as pooled_obj:
                        if pool_config.on_borrow:
                            pool_config.on_borrow(pooled_obj)

                        try:
                            # Call function with pooled object as first argument
                            result = func(pooled_obj, *args, **kwargs)

                            if pool_config.on_return:
                                pool_config.on_return(pooled_obj)

                            return result

                        except Exception as e:  # pylint: disable=broad-exception-caught
                            if pool_config.on_error:
                                fallback_result = pool_config.on_error(e)
                                if fallback_result is not None:
                                    return fallback_result
                            raise

                except (PoolEmptyError, OperationTimeoutError) as e:
                    last_exception = e
                    if attempt < pool_config.max_retries:
                        time.sleep(pool_config.retry_delay * (2**attempt))
                        continue
                    break

                except Exception:  # pylint: disable=broad-exception-caught,try-except-raise
                    raise

            # All retries exhausted
            if last_exception is not None:
                if pool_config.on_error:
                    pool_config.on_error(last_exception)
                raise last_exception
            raise PoolEmptyError(adapter, timeout)

        wrapper_any = cast(Any, wrapper)
        wrapper_any._pool_config = pool_config
        wrapper_any._pool_manager = pool_manager
        wrapper_any._original_func = func

        return cast(F, wrapper)

    return decorator


def cache_key(key_func: Callable[..., str]) -> Callable[[F], F]:
    """
    Decorator to specify a custom cache key generator.

    Must be used with @cached decorator.

    Args:
        key_func: Function that generates cache keys

    Returns:
        Decorator that sets the key generator
    """

    def decorator(func: F) -> F:
        if hasattr(func, "_cache_config"):
            cast(Any, func)._cache_config.key_generator = key_func
        else:
            # Store for later use by @cached
            cast(Any, func)._custom_key_generator = key_func
        return func

    return decorator


def invalidate_cache(
    func: Callable | None = None,
    pattern: str | None = None,
    namespace: str | None = None,
    adapter: str | None = None,
    manager: CacheManager | None = None,
) -> Callable | int:
    """
    Decorator or function to invalidate cache entries.

    Can be used as:
    1. ``@invalidate_cache`` - invalidates cache when function is called
    2. ``invalidate_cache(func)`` - immediately invalidate cache for function
    3. ``invalidate_cache(pattern="user:*")`` - invalidate by pattern

    Args:
        func: Function to invalidate cache for
        pattern: Pattern to match cache keys
        namespace: Namespace to invalidate
        adapter: Adapter to use
        manager: CacheManager instance

    Returns:
        Decorator function or number of invalidated entries
    """
    cache_manager = manager or get_global_manager()

    if func is None:
        # Used as @invalidate_cache or invalidate_cache(pattern="...")
        def decorator(f: F) -> F:
            @functools.wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                result = f(*args, **kwargs)

                # Invalidate cache after function execution
                if hasattr(f, "invalidate_all"):
                    f.invalidate_all()

                return result

            return cast(F, wrapper)

        if pattern or namespace:
            # Direct invalidation by pattern/namespace
            count = 0
            try:
                cache_adapter = cache_manager._get_cache_adapter(adapter_name=adapter)
                for key in cache_adapter.keys():
                    key_str = str(key)
                    should_invalidate = False

                    if pattern and pattern in key_str:
                        should_invalidate = True
                    elif namespace and key_str.startswith(f"{namespace}:"):
                        should_invalidate = True

                    if should_invalidate and cache_adapter.delete(key):
                        count += 1
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.getLogger(__name__).warning("Error during cache invalidation: %s", e)

            return count

        return decorator
    # Direct function invalidation
    if hasattr(func, "invalidate_all"):
        return cast(int, cast(Any, func).invalidate_all())
    return 0


def retry_with_cache(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    exponential_backoff: bool = True,
    cache_failures: bool = True,
    failure_ttl: int | float = 60,
    manager: CacheManager | None = None,
) -> Callable[[F], F]:
    """
    Decorator that adds retry logic with optional failure caching.

    Args:
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries
        exponential_backoff: Whether to use exponential backoff
        cache_failures: Whether to cache failures to avoid repeated attempts
        failure_ttl: TTL for cached failures

    Returns:
        Decorated function with retry logic
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception = None

            # Check for cached failure if enabled
            if cache_failures:
                cache_key = (
                    f"failure:{func.__module__}.{func.__qualname__}:{hash(str(args) + str(kwargs))}"
                )
                current_manager = manager or get_global_manager()

                cached_failure = current_manager.get(cache_key, adapter="memory")
                if cached_failure:
                    raise CacheError(f"Cached failure: {cached_failure}")

            for attempt in range(max_retries + 1):
                print(f"Attempt {attempt + 1}")
                try:
                    return func(*args, **kwargs)

                except Exception as e:  # pylint: disable=broad-exception-caught
                    print(f"Exception in func: {e}")
                    last_exception = e

                    if attempt < max_retries:
                        delay = retry_delay
                        if exponential_backoff:
                            delay *= 2**attempt

                        logging.getLogger(__name__).warning(
                            "Attempt %d failed for %s: %s. Retrying in %.2fs...",
                            attempt + 1,
                            func.__name__,
                            e,
                            delay,
                        )
                        time.sleep(delay)
                    else:
                        # Cache the failure if enabled
                        if cache_failures:
                            try:
                                current_manager.set(
                                    cache_key, str(e), ttl=failure_ttl, adapter="memory"
                                )
                            except Exception:  # pylint: disable=broad-exception-caught
                                logging.getLogger(__name__).warning("Cache Failure ")

                        break

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("retry_with_cache failed without capturing an exception")

        return cast(F, wrapper)

    return decorator


# Async versions
def async_cached(
    ttl: int | float | None = None,
    namespace: str | None = None,
    manager: CacheManager | None = None,
    **kwargs: Any,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Async version of the cached decorator."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        cache_config = CacheConfig(ttl=ttl, namespace=namespace, **kwargs)
        cache_manager = manager or get_global_manager()

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            # Generate cache key
            cache_key = KeyGenerator.default_key_generator(func, args, kwargs, cache_config)

            try:
                # Try to get from cache (sync operation)
                cached_result = cache_manager.get(cache_key, adapter=cache_config.adapter)

                if cached_result is not None:
                    if cache_config.on_hit:
                        cache_config.on_hit(cache_key, cached_result)
                    return cast(T, cached_result)

                # Cache miss - call async function
                if cache_config.on_miss:
                    cache_config.on_miss(cache_key)

                result = await func(*args, **kwargs)

                # Cache the result (sync operation)
                try:
                    cache_manager.set(
                        cache_key, result, ttl=cache_config.ttl, adapter=cache_config.adapter
                    )
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logging.getLogger(__name__).warning("Failed to cache async result: %s", e)

                return result

            except Exception as e:  # pylint: disable=broad-exception-caught
                if cache_config.on_error:
                    fallback_result = cache_config.on_error(e)
                    if fallback_result is not None:
                        return cast(T, fallback_result)

                logging.getLogger(__name__).warning("Async cache error: %s", e)
                return await func(*args, **kwargs)

        return cast(Callable[..., Awaitable[T]], wrapper)

    return decorator


# Utility functions
def clear_cache(
    namespace: str | None = None,
    adapter: str | None = None,
    manager: CacheManager | None = None,
) -> int:
    """
    Clear cache entries by namespace or adapter.

    Args:
        namespace: Namespace to clear
        adapter: Adapter to clear
        manager: CacheManager instance

    Returns:
        Number of entries cleared
    """
    cache_manager = manager or get_global_manager()

    if namespace:
        result = invalidate_cache(pattern=f"{namespace}:", adapter=adapter, manager=cache_manager)
        if isinstance(result, int):
            return result
        return 0
    if adapter:
        try:
            cache_adapter = cache_manager._get_cache_adapter(adapter_name=adapter)
            cache_adapter.clear()
            return cache_adapter.size()  # Return previous size
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.getLogger(__name__).warning("Error clearing adapter %s: %s", adapter, e)
            return 0
    # Clear all
    return cache_manager.clear()


def get_cache_stats(
    func: Callable | None = None,
    adapter: str | None = None,
    manager: CacheManager | None = None,
) -> dict[str, Any]:
    """
    Get cache statistics for a function or adapter.

    Args:
        func: Function to get stats for
        adapter: Adapter to get stats for
        manager: CacheManager instance

    Returns:
        Dictionary with cache statistics
    """
    cache_manager = manager or get_global_manager()

    if func and hasattr(func, "cache_info"):
        return cast(dict[str, Any], cast(Any, func).cache_info())
    if adapter:
        return cache_manager.get_adapter_stats(adapter)
    return cache_manager.get_global_stats()


__all__ = [
    # Configuration classes
    "CacheConfig",
    "PoolConfig",
    "KeyGenerator",
    # Main decorators
    "cached",
    "memoize",
    "timed_cache",
    "pooled",
    "cache_key",
    "invalidate_cache",
    "retry_with_cache",
    # Async decorators
    "async_cached",
    # Utility functions
    "clear_cache",
    "get_cache_stats",
]
