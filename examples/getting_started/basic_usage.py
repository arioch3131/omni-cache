# =============================================================================
# EXAMPLE 1: Basic Usage - Getting Started with Omni-Cache
# File: examples/getting_started/basic_usage.py
# =============================================================================
"""
Basic usage examples demonstrating core omni-cache functionality.

This example shows:
- Simple function caching with @cached decorator
- Cache invalidation and management
- Basic statistics and monitoring
- Different TTL strategies
"""

import random
import time

from omni_cache import cached, get_cache_stats, memoize, setup, timed_cache

# Setup omni-cache (optional - works without setup too)
manager = setup(log_level="INFO")


# =============================================================================
# Basic Function Caching
# =============================================================================


@cached(ttl=60)  # Cache for 60 seconds
def expensive_computation(n):
    """Simulate an expensive computation."""
    print(f"Computing expensive_computation({n})...")
    time.sleep(1)  # Simulate work
    return n**2 + random.randint(1, 100)


@memoize(maxsize=100)  # Simple memoization
def fibonacci(n):
    """Compute fibonacci with memoization."""
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


@timed_cache(seconds=30)  # Cache for 30 seconds
def get_current_time():
    """Get current time (cached to show time-based caching)."""
    return time.strftime("%H:%M:%S")


# =============================================================================
# Cache with Namespace and Custom Keys
# =============================================================================


@cached(ttl=300, namespace="api", key_prefix="v1")
def api_call(endpoint, params=None):
    """Simulate API call with namespace and versioning."""
    print(f"Making API call to {endpoint} with {params}")
    time.sleep(0.5)  # Simulate network delay
    return {
        "endpoint": endpoint,
        "params": params,
        "timestamp": time.time(),
        "data": [1, 2, 3, 4, 5],
    }


# =============================================================================
# Cache with Error Handling
# =============================================================================


@cached(
    ttl=60,
    on_hit=lambda key, value: print(f"✓ Cache hit for key: {key}"),
    on_miss=lambda key: print(f"✗ Cache miss for key: {key}"),
    on_error=lambda exc: print(f"⚠ Cache error: {exc}"),
)
def unreliable_function(x):
    """Function that sometimes fails."""
    if random.random() < 0.3:  # 30% chance of failure
        raise Exception("Random failure occurred")  # pylint: disable=broad-exception-raised

    time.sleep(0.5)
    return f"Result for {x}"


# =============================================================================
# Demo Functions
# =============================================================================


def demo_basic_caching():
    """Demonstrate basic caching functionality."""
    print("=== Basic Caching Demo ===")

    # First call - will compute
    result1 = expensive_computation(5)
    print(f"First call result: {result1}")

    # Second call - will use cache
    result2 = expensive_computation(5)
    print(f"Second call result: {result2}")

    # Same result because it's cached
    assert result1 == result2
    print("✓ Results are identical (cached)")

    # Different parameter - will compute again
    result3 = expensive_computation(6)
    print(f"Different parameter result: {result3}")

    print()


def demo_memoization():
    """Demonstrate memoization with fibonacci."""
    print("=== Memoization Demo ===")

    start_time = time.time()
    result = fibonacci(30)
    first_duration = time.time() - start_time
    print(f"First fibonacci(30) = {result} (took {first_duration:.3f}s)")

    start_time = time.time()
    result = fibonacci(30)
    second_duration = time.time() - start_time
    print(f"Second fibonacci(30) = {result} (took {second_duration:.3f}s)")

    print(f"Speedup: {first_duration / second_duration:.1f}x faster")
    print()


def demo_cache_management():
    """Demonstrate cache invalidation and management."""
    print("=== Cache Management Demo ===")

    # Make some cached calls
    api_call("users", {"limit": 10})
    api_call("posts", {"page": 1})
    api_call("users", {"limit": 10})  # This will hit cache

    # Get cache statistics
    stats = api_call.cache_info()
    print(f"Cache info: {stats}")

    # Invalidate specific call
    print("Invalidating api_call('users', {'limit': 10})")
    api_call.invalidate("users", {"limit": 10})

    # This will miss cache now
    api_call("users", {"limit": 10})

    # Invalidate all cached results for this function
    print("Invalidating all cached results")
    invalidated_count = api_call.invalidate_all()
    print(f"Invalidated {invalidated_count} cache entries")

    print()


def demo_timed_cache():
    """Demonstrate time-based caching."""
    print("=== Timed Cache Demo ===")

    # Get time (first call)
    time1 = get_current_time()
    print(f"First call: {time1}")

    # Get time again immediately (cached)
    time2 = get_current_time()
    print(f"Second call: {time2}")

    assert time1 == time2
    print("✓ Times are identical (cached)")

    # Wait and try again (still cached if within 30 seconds)
    time.sleep(2)
    time3 = get_current_time()
    print(f"After 2 seconds: {time3}")

    print()


def demo_error_handling():
    """Demonstrate cache behavior with errors."""
    print("=== Error Handling Demo ===")

    for i in range(5):
        try:
            result = unreliable_function(f"test_{i}")
            print(f"Success: {result}")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Error: {e}")

    print()


def demo_statistics():
    """Demonstrate cache statistics."""
    print("=== Statistics Demo ===")

    # Generate some cache activity
    for i in range(10):
        expensive_computation(i % 3)  # Will create some hits and misses

    # Get function-level stats
    stats = expensive_computation.cache_info()
    print(f"expensive_computation stats: {stats}")

    # Get global stats
    global_stats = get_cache_stats()
    print(f"Global cache stats: {global_stats}")

    print()


# =============================================================================
# Main Demo
# =============================================================================

if __name__ == "__main__":
    print("🚀 Omni-Cache Basic Usage Examples")
    print("=" * 50)

    demo_basic_caching()
    demo_memoization()
    demo_cache_management()
    demo_timed_cache()
    demo_error_handling()
    demo_statistics()

    print("✅ All demos completed successfully!")
