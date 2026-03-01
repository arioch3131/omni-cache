# Omni-Cache

**Universal cache and pool manager with pluggable backends**

Omni-Cache is a comprehensive caching and object pooling library that provides a unified interface for multiple backends, intelligent routing, and production-ready features. Whether you need simple function memoization or enterprise-grade distributed caching, Omni-Cache scales with your needs.

## Important Notice

**This is a personal project.** While the code is provided as-is and functional, please note:
- There will be **limited to no ongoing maintenance** of this project
- You are **free to fork** this repository and adapt it to your needs
- All usage must comply with the **MIT license** (see [LICENSE](LICENSE))

Feel free to use, modify, and distribute this code according to the license terms.
External changes are not actively managed and may not be reviewed or merged.

## Overview

Omni-Cache follows a modular architecture similar to SmartPool, with clear separation between core services, adapter implementations, and user-facing utilities.

## Features

- **Multiple Backends**: Memory, Redis, Memcached, AdaptiveMemoryPool, and custom adapters
- **Unified Interface**: Single API for all cache and pool operations
- **Intelligent Routing**: Namespace-based routing with automatic fallback
- **Comprehensive Monitoring**: Built-in statistics, health checks, and performance metrics
- **Hot-Reloadable Configuration**: YAML, JSON, TOML, and environment variable support
- **Production-Ready Decorators**: `@cached`, `@pooled`, `@memoize` with advanced features
- **Async Support**: Full async/await compatibility
- **Type Safety**: Complete type hints and runtime validation
- **Enterprise Features**: Connection pooling, retry logic, circuit breakers

## When Should You Use This?

### Perfect For
- High-throughput APIs with repeated expensive reads
- Multi-backend systems (in-memory + Redis + pooled resources)
- Services that need observability on cache/pool behavior
- Projects requiring routing and centralized cache configuration

### Probably Overkill For
- Small scripts with minimal recomputation cost
- Single-threaded workloads with low cache churn
- Short-lived one-off jobs where setup overhead dominates

### Rule of Thumb
If your application repeatedly computes or fetches costly values and you need operational control (routing, monitoring, retries), Omni-Cache is a good fit.

## Installation

```bash
# Basic installation
pip install omni_cache

# With Redis support
pip install omni_cache[redis]

# With all optional dependencies
pip install omni_cache[all]
```

## Quick Start

### Ultra-Simple Usage

```python
from omni_cache import cached

@cached(ttl=300)  # Cache for 5 minutes
def expensive_function(x, y):
    # This will only run once per unique (x, y) combination
    return complex_computation(x, y)

# Use it normally
result = expensive_function(1, 2)  # Computed and cached
result = expensive_function(1, 2)  # Retrieved from cache
```

### Quick Setup

```python
from omni_cache import setup, cached

# One-line setup with auto-discovery
manager = setup(auto_discover=True)

@cached(ttl=300, namespace="api")
def fetch_user_data(user_id):
    return requests.get(f"/api/users/{user_id}").json()
```

## Basic Usage

### Function Caching

```python
from omni_cache import cached, memoize, timed_cache

# Basic caching with TTL
@cached(ttl=300, namespace="database")
def get_user(user_id):
    return database.query("SELECT * FROM users WHERE id = ?", user_id)

# Simple memoization
@memoize(maxsize=1000)
def fibonacci(n):
    if n < 2: return n
    return fibonacci(n-1) + fibonacci(n-2)

# Time-based caching
@timed_cache(seconds=60)
def get_current_weather():
    return weather_api.get_current()

# Cache management
get_user.invalidate(123)        # Invalidate specific call
get_user.invalidate_all()       # Clear all cached results
stats = get_user.cache_info()   # Get cache statistics
```

### Object Pooling

```python
from omni_cache import pooled

@pooled(adapter="db_pool", timeout=5.0, max_retries=3)
def query_database(connection, query, params):
    # Connection automatically borrowed and returned
    return connection.execute(query, params).fetchall()

# Context manager for manual control
from omni_cache import get_global_manager

manager = get_global_manager()
with manager.borrow(adapter="db_pool") as connection:
    result = connection.execute("SELECT 1").fetchone()
    # Connection automatically returned to pool
```

### Direct Manager Usage

```python
from omni_cache import get_global_manager

manager = get_global_manager()

# Cache operations
manager.set("user:123", user_data, ttl=300)
user = manager.get("user:123")
exists = manager.exists("user:123")
manager.delete("user:123")

# Batch operations
users = manager.get_many(["user:123", "user:456"])
manager.set_many({"user:789": data1, "user:101": data2}, ttl=300)

# Pool operations
obj = manager.get(timeout=5.0, adapter="pool")
manager.put(obj, adapter="pool")
```

## Advanced Usage

### Multi-Backend Setup

```python
from omni_cache import CacheManager, create_adapter, CacheBackend

# Create manager
manager = CacheManager()

# Add memory cache for hot data
memory_adapter = create_adapter(CacheBackend.MEMORY, {
    "max_size": 10000,
    "eviction_policy": "lru"
})
manager.register_adapter("fast", memory_adapter)

# Add Redis for persistent cache
redis_adapter = create_adapter(CacheBackend.REDIS, {
    "host": "localhost",
    "port": 6379,
    "db": 0
})
manager.register_adapter("persistent", redis_adapter)

# Add SmartPool for database connections
def create_db_connection():
    return psycopg2.connect(DATABASE_URL)

pool_adapter = create_adapter(CacheBackend.SMARTPOOL, {
    "factory_function": create_db_connection,
    "initial_size": 5,
    "max_size": 20
})
manager.register_adapter("db_pool", pool_adapter)
```

### Intelligent Routing

```python
# Set up routing rules
manager.add_routing_rule("cache", "fast")        # cache:* → memory
manager.add_routing_rule("store", "persistent")  # store:* → redis
manager.add_routing_rule("session", "fast")      # session:* → memory

# Automatic routing based on key patterns
manager.set("cache:temp_data", data)      # → fast (memory)
manager.set("store:user_profile", user)   # → persistent (redis)
manager.set("session:abc123", session)    # → fast (memory)

# Use with decorators
@cached(ttl=60, namespace="cache")     # → routed to memory
def get_temporary_data():
    return generate_temp_data()

@cached(ttl=3600, namespace="store")   # → routed to redis
def get_user_profile(user_id):
    return database.get_user(user_id)
```

### Configuration-Driven Setup

```yaml
# config.yaml
global:
  log_level: "INFO"
  enable_routing: true
  default_cache_adapter: "redis"
  health_check_interval: 60

adapters:
  memory:
    backend: "memory"
    enabled: true
    extra_config:
      max_size: 10000
      eviction_policy: "lru"
  
  redis:
    backend: "redis"
    enabled: true
    extra_config:
      host: "localhost"
      port: 6379
      db: 0
  
  db_pool:
    backend: "smartpool"
    enabled: true
    extra_config:
      initial_size: 5
      max_size: 20
      factory_function: "myapp.database.create_connection"
```

```python
from omni_cache import ConfigManager, CacheManager

# Load configuration
config_manager = ConfigManager("config.yaml")
config_manager.enable_hot_reload()  # Auto-reload on file changes

# Create manager from configuration
manager = setup(config_file="config.yaml", enable_hot_reload=True)

# Configuration is automatically applied
@cached(ttl=300)  # Uses configured routing and backends
def my_function():
    return expensive_operation()
```

## Configuration

### Configuration Files

Omni-Cache supports YAML, JSON, and TOML configuration files:

```yaml
# omni_cache.yaml
global:
  log_level: "INFO"
  default_cache_adapter: "memory"
  enable_routing: true
  namespace_separator: ":"
  health_check_interval: 60.0
  debug_mode: false

adapters:
  memory:
    backend: "memory"
    enabled: true
    auto_connect: true
    extra_config:
      max_size: 10000
      default_ttl: 3600
      eviction_policy: "lru"
      cleanup_interval: 60
  
  redis:
    backend: "redis"
    enabled: true
    extra_config:
      host: "localhost"
      port: 6379
      db: 0
      password: null
      socket_timeout: 5.0
      connection_pool_max_connections: 10
```

### Environment Variables

```bash
# Global settings
export OMNI_CACHE_LOG_LEVEL=DEBUG
export OMNI_CACHE_DEFAULT_CACHE_ADAPTER=redis
export OMNI_CACHE_ENABLE_ROUTING=true

# Adapter settings
export OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_HOST=redis.example.com
export OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_PORT=6380

# Auto-setup
export OMNI_CACHE_AUTO_SETUP=true
```

### Programmatic Configuration

```python
from omni_cache import ConfigManager, GlobalConfig, AdapterConfig

# Create configuration manager
config_manager = ConfigManager()

# Update global configuration
config_manager.update_global_config({
    "log_level": "DEBUG",
    "enable_routing": True
})

# Add adapter configuration
config_manager.add_adapter_config("redis", {
    "backend": "redis",
    "enabled": True,
    "extra_config": {
        "host": "redis.example.com",
        "port": 6379
    }
})

# Hot reload from file
config_manager.load_config("new_config.yaml")
```

## Available Backends

### Memory (Built-in)
- **No dependencies**: Always available
- **Features**: LRU/FIFO/Random eviction, TTL support, size limits
- **Use case**: Single-process caching, development, testing

```python
memory_adapter = create_adapter(CacheBackend.MEMORY, {
    "max_size": 10000,
    "eviction_policy": "lru",
    "default_ttl": 3600
})
```

### Redis (Optional)
- **Dependency**: `pip install redis`
- **Features**: Distributed caching, persistence, pub/sub
- **Use case**: Multi-process/server caching, session storage

```python
redis_adapter = create_adapter(CacheBackend.REDIS, {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": "secret"
})
```

### SmartPool (Optional)
- **Dependency**: The `smartpool` package  
- **Features**: Dynamic sizing, object lifecycle management, adaptive pooling
- **Use case**: Database connections, expensive object pooling

```python
def create_connection():
    return psycopg2.connect(DATABASE_URL)

pool_adapter = create_adapter(CacheBackend.SMARTPOOL, {
    "factory_function": create_connection,
    "initial_size": 5,
    "max_size": 20,
    "min_size": 2
})
```

### Custom Backends
Create your own adapters by implementing the appropriate base class:

```python
from omni_cache.adapters.base import BaseCacheAdapter

class MyCustomAdapter(BaseCacheAdapter):
    def _do_connect(self) -> bool:
        # Implementation
        return True
    
    def _do_disconnect(self) -> bool:
        # Implementation
        return True
    
    def _do_health_check(self) -> bool:
        # Implementation
        return True
    
    def _set_internal(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        # Your cache set implementation
        return True
    
    def _get_internal(self, key: str) -> Any:
        # Your cache get implementation
        return None
    
    def _delete_internal(self, key: str) -> bool:
        # Your cache delete implementation
        return True
    
    def _clear_internal(self) -> bool:
        # Your cache clear implementation
        return True
```

### Adapter Scaffold Script
For simple adapters, you can generate a full boilerplate with:

```bash
python scripts/new_adapter.py my_backend --dependency my-lib
```

This generates:
- `src/omni_cache/adapters/my_backend/{__init__.py,config.py,my_backend.py,factory.py}`
- `tests/unit/adapters/my_backend/{test_my_backend_config.py,test_my_backend_factory.py,test_my_backend_adapter.py}`

Then complete the integration by:
1. Exporting the adapter in `src/omni_cache/adapters/__init__.py`
2. Registering the factory in `src/omni_cache/core/factories/factory_registry.py`
3. Exporting the factory in `src/omni_cache/core/factories/__init__.py`
4. Adding dependency and entry point in `pyproject.toml`

## Monitoring and Statistics

### Cache Statistics

```python
from omni_cache import get_global_manager
from omni_cache.utils.decorators import get_cache_stats

# Function-level statistics
@cached(ttl=300)
def my_function():
    return expensive_operation()

stats = my_function.cache_info()
print(f"Hit rate: {stats['hit_rate']:.2%}")

# Manager-level statistics
manager = get_global_manager()
global_stats = manager.get_global_stats()
print(f"Total hits: {global_stats['cache'].hits}")
print(f"Total misses: {global_stats['cache'].misses}")

# Adapter-specific statistics
redis_stats = manager.get_adapter_stats("redis")
```

### Health Monitoring

```python
# Health checks
manager = get_global_manager()

# Check specific adapter
redis_adapter = manager.get_adapter("redis")
is_healthy = redis_adapter.health_check()

# Get backend information
info = redis_adapter.get_backend_info()
print(f"Connection state: {info['state']}")
print(f"Last health check: {info['last_health_check']}")

# Global health monitoring runs automatically
# Check logs for health status updates
```

### Performance Profiling

```python
# Enable detailed logging and profiling
from omni_cache import setup

manager = setup(
    config_file="config.yaml",
    log_level="DEBUG"  # Shows detailed operation logs
)

# Use profile_operations in configuration
global_config = {
    "profile_operations": True,
    "enable_detailed_logging": True
}
```

## Decorator Features

### Advanced Caching Options

```python
from omni_cache import cached, cache_key

# Custom key generation
@cache_key(lambda user_id, include_inactive: f"user:{user_id}:active:{not include_inactive}")
@cached(ttl=300)
def get_user_data(user_id, include_inactive=False):
    return database.get_user(user_id, include_inactive)

# Ignore specific arguments
@cached(
    ttl=300,
    ignore_args={0},           # Ignore first argument (self)
    ignore_kwargs={"debug"}    # Ignore debug flag
)
def process_data(self, data, debug=False):
    return expensive_processing(data)

# Custom serialization
import pickle

@cached(
    ttl=300,
    serializer=pickle.dumps,
    deserializer=pickle.loads
)
def get_complex_object():
    return ComplexObject()

# Event callbacks
@cached(
    ttl=300,
    on_hit=lambda key, value: logger.info(f"Cache hit: {key}"),
    on_miss=lambda key: logger.info(f"Cache miss: {key}"),
    on_error=lambda exc: logger.error(f"Cache error: {exc}")
)
def monitored_function():
    return get_data()
```

### Retry Logic with Caching

```python
from omni_cache import retry_with_cache

@retry_with_cache(
    max_retries=3,
    retry_delay=1.0,
    exponential_backoff=True,
    cache_failures=True,     # Cache failures to avoid repeated attempts
    failure_ttl=60          # Cache failures for 60 seconds
)
def unreliable_api_call():
    response = requests.get("https://unreliable-api.com/data")
    return response.json()
```

### Async Support

```python
from omni_cache import async_cached
import aiohttp

@async_cached(ttl=300, namespace="api")
async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Usage
data = await fetch_data("https://api.example.com/data")
```

## Utilities

### Cache Management

```python
from omni_cache.utils.decorators import clear_cache, invalidate_cache

# Clear by namespace
cleared_count = clear_cache(namespace="user_data")

# Invalidate by pattern
invalidate_cache(pattern="user:*")

# Clear specific adapter
clear_cache(adapter="redis")

# Clear everything
clear_cache()
```

### Discovery and Information

```python
from omni_cache import discover_backends, get_version_info, info

# See available backends
backends = discover_backends()
print(f"Available: {list(backends.keys())}")

# Version information
version_info = get_version_info()
print(f"Version: {version_info['version']}")
print(f"Redis support: {version_info['capabilities']['redis_adapter']}")

# Print detailed information
info()  # Prints comprehensive system info
```

## Real-World Examples

### Web Application Cache

```python
from flask import Flask
from omni_cache import setup, cached, pooled

app = Flask(__name__)

# Setup caching
setup(config_file="web_cache.yaml", auto_discover=True)

@cached(ttl=300, namespace="api")
def get_user_profile(user_id):
    return database.get_user_profile(user_id)

@cached(ttl=60, namespace="analytics")
def get_page_stats():
    return analytics.get_daily_stats()

@pooled(adapter="db_pool", timeout=5.0)
def execute_query(connection, query, params):
    return connection.execute(query, params).fetchall()

@app.route('/users/<int:user_id>')
def user_profile(user_id):
    profile = get_user_profile(user_id)
    return jsonify(profile)
```

### Data Processing Pipeline

```python
from omni_cache import cached, memoize, get_global_manager
import pandas as pd

# Setup manager with multiple backends
manager = setup(config_file="pipeline.yaml")

@cached(ttl=3600, namespace="raw_data", adapter="persistent")
def load_dataset(filename):
    """Cache expensive data loading operations"""
    return pd.read_csv(filename)

@memoize(maxsize=1000)
def calculate_statistics(data_hash):
    """Memoize statistical calculations"""
    return data.describe()

@cached(ttl=1800, namespace="processed", adapter="fast")
def process_batch(batch_id):
    """Cache processed results"""
    raw_data = load_dataset(f"batch_{batch_id}.csv")
    return expensive_processing(raw_data)

# Pipeline execution
for batch_id in range(100):
    result = process_batch(batch_id)  # Cached on subsequent runs
    stats = calculate_statistics(hash(str(result)))
```

### Microservices Communication

```python
from omni_cache import cached, async_cached, retry_with_cache
import aiohttp

# Cache service responses
@async_cached(ttl=300, namespace="service_a")
async def call_service_a(endpoint, params):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://service-a/{endpoint}", params=params) as response:
            return await response.json()

@retry_with_cache(max_retries=3, cache_failures=True, failure_ttl=60)
@cached(ttl=60, namespace="service_b")
def call_service_b(data):
    response = requests.post("http://service-b/process", json=data)
    return response.json()

# Circuit breaker pattern with cached fallbacks
@cached(ttl=3600, namespace="fallback")
def get_fallback_data(key):
    return default_responses.get(key)

def resilient_service_call(key):
    try:
        return call_service_a(key)
    except Exception:
        return get_fallback_data(key)
```

## Documentation

Build the documentation locally:

```bash
bash scripts/build_docs.sh
```

Or with Sphinx directly:

```bash
cd docs
make html
```

Generated docs are available in `docs/_build/html/`.

## Examples

Example programs are available in [`examples/`](examples/) with usage patterns for:
- Web applications
- Data processing pipelines
- Microservice communication
- Adapter and routing configurations

Start with [`examples/README.md`](examples/README.md) for an index.

## Testing

### Test Configuration

```python
# test_config.yaml
global:
  log_level: "DEBUG"
  default_cache_adapter: "memory"

adapters:
  memory:
    backend: "memory"
    enabled: true
    extra_config:
      max_size: 100  # Small cache for testing
```

### Unit Tests

```python
import pytest
from omni_cache import setup, cached, temporary_config

def test_caching():
    # Setup test environment
    setup(config_file="test_config.yaml")
    
    call_count = 0
    
    @cached(ttl=60)
    def test_function(x):
        nonlocal call_count
        call_count += 1
        return x * 2
    
    # Test caching behavior
    result1 = test_function(5)
    result2 = test_function(5)
    
    assert result1 == result2 == 10
    assert call_count == 1  # Function called only once

def test_with_temporary_config():
    with temporary_config({"debug_mode": True}):
        # Test with debug configuration
        pass
    # Original configuration restored
```

### Run Test Suites

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Performance tests
pytest tests/performance/
```

## Migration Guide

### From functools.lru_cache

```python
# Before (functools)
from functools import lru_cache

@lru_cache(maxsize=128)
def expensive_function(x):
    return complex_computation(x)

# After (omni-cache)
from omni_cache import memoize

@memoize(maxsize=128)
def expensive_function(x):
    return complex_computation(x)

# Benefits: TTL support, statistics, invalidation, persistence
```

### From Redis Direct Usage

```python
# Before (direct Redis)
import redis
r = redis.Redis()

def get_user(user_id):
    key = f"user:{user_id}"
    cached = r.get(key)
    if cached:
        return json.loads(cached)
    
    user = database.get_user(user_id)
    r.setex(key, 300, json.dumps(user))
    return user

# After (omni-cache)
from omni_cache import cached

@cached(ttl=300, namespace="user", adapter="redis")
def get_user(user_id):
    return database.get_user(user_id)

# Benefits: Automatic serialization, routing, fallback, monitoring
```

## Project Maintenance Policy

There is no active maintenance process for this repository.
Issues or pull requests may remain unanswered. If you need long-term evolution,
forking is the recommended path.

### Development Setup

```bash
# Navigate to project directory
cd omni-cache

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install development dependencies
pip install -e .[dev]

# Run tests
pytest

# Run linting
flake8 src/
mypy src/

# Run benchmarks (if available)
python scripts/benchmark.py
```

## Project Structure

```
omni_cache/
├── core/           # Core interfaces and manager
├── adapters/       # Backend implementations
├── utils/          # Decorators and utilities
└── __init__.py     # Public API
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by Django's cache framework
- Built on the shoulders of Redis, Memcached, and other great projects
- Thanks to all users

## Resources

- **Documentation**: See `docs/` directory and inline docstrings
- **GitHub**: This repository
- **Issues**: Please file issues in this repository
- **Examples**: See `examples/` directory
