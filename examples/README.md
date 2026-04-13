# Examples

This folder is organized into three levels:

- `getting_started/`: short practical examples to learn core usage quickly.
- `advanced/`: integration and scenario-driven examples.
- `benchmarks/`: performance and stress-oriented scripts.

## Getting Started

1. `python examples/getting_started/basic_usage.py`
2. `python examples/getting_started/basic_memory_adapter.py`
3. `python examples/getting_started/basic_redis_adapter.py`
4. `python examples/getting_started/basic_async_redis_adapter.py`
5. `python examples/getting_started/basic_memcached_adapter.py`
6. `python examples/getting_started/basic_smartpool_adapter.py`
8. `python examples/getting_started/cache_aside_pattern.py`
9. `python examples/getting_started/http_api_response_cache.py`
10. `python examples/getting_started/db_query_cache_with_invalidation.py`

## Advanced

1. `python examples/advanced/data_processing_pipeline.py`
2. `python examples/advanced/microservices_async_caching.py`
3. `python examples/advanced/multi_level_cache_memory_redis.py`
4. `python examples/advanced/stampede_protection.py`
5. `python examples/advanced/background_warming.py`
6. `python examples/advanced/rate_limit_with_cache.py`
7. `python examples/advanced/feature_flags_cached.py`
8. `python examples/advanced/observability_metrics_example.py`
9. `python examples/advanced/graceful_degradation.py`
10. `python examples/advanced/smartpool_integration.py`
11. `python examples/advanced/smartpool_diagnostics.py`

## Benchmarks

1. `python examples/benchmarks/performance_stress_comparison.py`
2. `python examples/benchmarks/performance_smartpool_comparison.py`
3. `python examples/benchmarks/refactored_adapter_comparison.py`
4. `python examples/benchmarks/long_running_performance.py`

## Optional dependencies

- `pandas`, `numpy` for data processing.
- `aiohttp` for microservices async example.
- Redis server for Redis-backed benchmark sections.
- Memcached server for Memcached-backed benchmark sections.
- SmartPool for SmartPool examples and benchmark sections.
