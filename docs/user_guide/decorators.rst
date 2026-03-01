Decorators
==========

Omni-Cache provides a powerful decorator interface for function-level caching and object pooling.

Caching Decorators
------------------

@cached
~~~~~~~

The primary caching decorator for function results:

.. code-block:: python

   from omni_cache import cached

   @cached(ttl=300)  # Cache for 5 minutes
   def expensive_function(x, y):
       return complex_computation(x, y)

   # Usage
   result = expensive_function(1, 2)  # Computed
   result = expensive_function(1, 2)  # Cached

**Parameters:**

* **ttl** (int): Time-to-live in seconds
* **namespace** (str): Namespace for organizing keys
* **adapter** (str): Specific adapter to use
* **ignore_args** (set): Positional arguments to ignore
* **ignore_kwargs** (set): Keyword arguments to ignore
* **key_generator** (callable): Custom key generation function
* **serializer** (callable): Custom value serializer
* **deserializer** (callable): Custom value deserializer
* **on_hit** (callable): Callback for cache hits
* **on_miss** (callable): Callback for cache misses
* **on_error** (callable): Callback for errors

@memoize
~~~~~~~~

LRU-style memoization with size limits:

.. code-block:: python

   from omni_cache import memoize

   @memoize(maxsize=1000)
   def fibonacci(n):
       if n < 2:
           return n
       return fibonacci(n-1) + fibonacci(n-2)

   # Fast computation due to memoization
   result = fibonacci(100)

**Parameters:**

* **maxsize** (int): Maximum number of cached results
* **ttl** (int): Optional time-to-live
* **ignore_args** (set): Arguments to ignore in key generation
* **typed** (bool): Distinguish arguments by type

@timed_cache
~~~~~~~~~~~~

Time-based caching with automatic expiration:

.. code-block:: python

   from omni_cache import timed_cache

   @timed_cache(seconds=60)  # Cache for 1 minute
   def get_current_weather():
       return weather_api.get_current_conditions()

   # Multiple calls within 60 seconds return cached result
   weather = get_current_weather()

**Parameters:**

* **seconds** (int): Cache duration in seconds
* **minutes** (int): Cache duration in minutes
* **hours** (int): Cache duration in hours
* **days** (int): Cache duration in days

Advanced Caching Options
------------------------

Custom Key Generation
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache import cached, cache_key

   # Method 1: Custom key function
   @cache_key(lambda user_id, include_deleted: f"user:{user_id}:deleted:{include_deleted}")
   @cached(ttl=300)
   def get_user_with_options(user_id, include_deleted=False):
       return database.get_user(user_id, include_deleted)

   # Method 2: Key generator parameter
   def my_key_generator(func, args, kwargs):
       return f"custom:{func.__name__}:{hash(args)}"

   @cached(ttl=300, key_generator=my_key_generator)
   def my_function(data):
       return process_data(data)

Ignoring Arguments
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   @cached(
       ttl=300,
       ignore_args={0},           # Ignore first argument (self)
       ignore_kwargs={"debug"}    # Ignore debug parameter
   )
   def process_data(self, data, debug=False):
       return expensive_processing(data)

Custom Serialization
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import pickle
   import json

   @cached(
       ttl=300,
       serializer=pickle.dumps,
       deserializer=pickle.loads
   )
   def get_complex_object():
       return ComplexObject()

   # JSON serialization for simple objects
   @cached(
       ttl=300,
       serializer=json.dumps,
       deserializer=json.loads
   )
   def get_json_data():
       return {"key": "value", "number": 42}

Event Callbacks
~~~~~~~~~~~~~~~

.. code-block:: python

   import logging

   logger = logging.getLogger(__name__)

   @cached(
       ttl=300,
       on_hit=lambda key, value: logger.info(f"Cache hit: {key}"),
       on_miss=lambda key: logger.info(f"Cache miss: {key}"),
       on_error=lambda exc: logger.error(f"Cache error: {exc}")
   )
   def monitored_function(param):
       return get_data(param)

Namespace Organization
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Group related functions by namespace
   @cached(ttl=300, namespace="users")
   def get_user(user_id):
       return database.get_user(user_id)

   @cached(ttl=60, namespace="sessions")
   def get_session(session_id):
       return database.get_session(session_id)

   # Clear specific namespace
   from omni_cache.utils.decorators import clear_cache
   clear_cache(namespace="users")

Async Caching
-------------

@async_cached
~~~~~~~~~~~~~

Caching for async functions:

.. code-block:: python

   from omni_cache import async_cached
   import aiohttp

   @async_cached(ttl=300, namespace="api")
   async def fetch_data(url):
       async with aiohttp.ClientSession() as session:
           async with session.get(url) as response:
               return await response.json()

   # Usage
   import asyncio

   async def main():
       data = await fetch_data("https://api.example.com/data")
       return data

   result = asyncio.run(main())

**Parameters:**
All parameters from ``@cached`` are supported for async functions.

Pooling Decorators
------------------

@pooled
~~~~~~~

Object pooling with automatic lifecycle management:

.. code-block:: python

   from omni_cache import pooled

   @pooled(adapter="db_pool", timeout=5.0, max_retries=3)
   def query_database(connection, query, params):
       # Connection automatically borrowed and returned
       return connection.execute(query, params).fetchall()

   # Usage
   results = query_database("SELECT * FROM users WHERE age > ?", (18,))

**Parameters:**

* **adapter** (str): Pool adapter name
* **timeout** (float): Timeout for acquiring object
* **max_retries** (int): Maximum retry attempts
* **retry_delay** (float): Delay between retries
* **on_error** (callable): Error callback

Retry Logic
-----------

@retry_with_cache
~~~~~~~~~~~~~~~~~

Combines retry logic with failure caching:

.. code-block:: python

   from omni_cache import retry_with_cache

   @retry_with_cache(
       max_retries=3,
       retry_delay=1.0,
       exponential_backoff=True,
       cache_failures=True,     # Cache failures to avoid repeated attempts
       failure_ttl=60          # Cache failures for 60 seconds
   )
   def unreliable_api_call(endpoint):
       response = requests.get(f"https://unreliable-api.com/{endpoint}")
       if response.status_code != 200:
           raise requests.HTTPError("API request failed")
       return response.json()

   # Won't retry for 60 seconds after failure
   try:
       data = unreliable_api_call("data")
   except requests.HTTPError:
       print("API is down, using fallback")

**Parameters:**

* **max_retries** (int): Maximum retry attempts
* **retry_delay** (float): Base delay between retries
* **exponential_backoff** (bool): Use exponential backoff
* **cache_failures** (bool): Cache failure results
* **failure_ttl** (int): TTL for cached failures
* **retriable_exceptions** (tuple): Exception types to retry

Cache Management
----------------

Decorator Cache Control
~~~~~~~~~~~~~~~~~~~~~~~

All cached decorators provide cache management methods:

.. code-block:: python

   @cached(ttl=300)
   def my_function(param):
       return expensive_operation(param)

   # Clear entire cache for function
   my_function.clear_cache()

   # Invalidate specific call
   my_function.invalidate(param_value)

   # Get cache statistics
   stats = my_function.cache_info()
   print(f"Hits: {stats['hits']}, Misses: {stats['misses']}")
   print(f"Hit rate: {stats['hit_rate']:.2%}")

   # Get current cache size
   size = my_function.cache_size()

Global Cache Management
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.utils.decorators import clear_cache, invalidate_cache, get_cache_stats

   # Clear by namespace
   cleared_count = clear_cache(namespace="user_data")

   # Clear by pattern
   invalidate_cache(pattern="user:*")

   # Clear specific adapter
   clear_cache(adapter="redis")

   # Clear everything
   clear_cache()

   # Global statistics
   global_stats = get_cache_stats()

Decorator Configuration
-----------------------

You can configure decorator behavior globally:

.. code-block:: python

   from omni_cache.utils.decorators import set_default_config

   # Set global defaults
   set_default_config({
       "default_ttl": 300,
       "default_adapter": "redis",
       "enable_stats": True,
       "cache_none_values": False
   })

   # Now all decorators use these defaults
   @cached()  # Uses ttl=300, adapter="redis"
   def my_function():
       return get_data()

Configuration Classes
---------------------

CacheConfig
~~~~~~~~~~~

.. code-block:: python

   from omni_cache.utils.decorators import CacheConfig

   config = CacheConfig(
       ttl=300,
       namespace="api",
       adapter="redis",
       enable_stats=True,
       cache_none_values=False
   )

   @cached(config=config)
   def my_function():
       return get_data()

PoolConfig
~~~~~~~~~~

.. code-block:: python

   from omni_cache.utils.decorators import PoolConfig

   pool_config = PoolConfig(
       adapter="db_pool",
       timeout=5.0,
       max_retries=3,
       retry_delay=1.0
   )

   @pooled(config=pool_config)
   def database_operation(connection):
       return connection.execute("SELECT 1")

KeyGenerator
~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.utils.decorators import KeyGenerator

   # Custom key generation strategy
   key_gen = KeyGenerator(
       include_module=True,
       include_class=True,
       hash_long_keys=True,
       max_key_length=250
   )

   @cached(key_generator=key_gen.generate)
   def my_function(complex_param):
       return process(complex_param)

Error Handling
--------------

Graceful Degradation
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Function executes even if caching fails
   @cached(ttl=300, on_error=lambda exc: None)
   def resilient_function(param):
       return expensive_computation(param)

   # Log errors but continue execution
   @cached(
       ttl=300,
       on_error=lambda exc: logging.error(f"Cache error: {exc}")
   )
   def logged_function(param):
       return get_data(param)

Exception Handling
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.core.exceptions import CacheError

   @cached(ttl=300)
   def my_function(param):
       return get_data(param)

   try:
       result = my_function("test")
   except CacheError as e:
       print(f"Caching failed: {e}")
       # Fallback logic
       result = get_data_fallback("test")

Performance Considerations
--------------------------

Best Practices
~~~~~~~~~~~~~~

1. **Choose appropriate TTL values**
   - Short TTL for frequently changing data
   - Long TTL for stable data
   - No TTL for immutable data

2. **Use namespaces for organization**
   - Group related functions
   - Enable selective clearing
   - Avoid key collisions

3. **Consider serialization overhead**
   - Use efficient serializers for large objects
   - Consider compression for bulky data
   - Avoid caching very large objects

4. **Monitor cache performance**
   - Track hit rates
   - Monitor memory usage
   - Set up alerts for low hit rates

5. **Handle cache failures gracefully**
   - Always provide fallback logic
   - Log cache errors appropriately
   - Don't let cache failures break functionality

Advanced Patterns
-----------------

Layered Caching
~~~~~~~~~~~~~~~

.. code-block:: python

   # Fast local cache with Redis fallback
   @cached(ttl=60, adapter="memory", namespace="l1")
   def get_user_l1(user_id):
       return get_user_l2(user_id)

   @cached(ttl=300, adapter="redis", namespace="l2")  
   def get_user_l2(user_id):
       return database.get_user(user_id)

   # Usage automatically uses both layers
   user = get_user_l1(123)

Conditional Caching
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def should_cache(result):
       # Only cache successful results
       return result is not None and result.get('status') == 'success'

   @cached(
       ttl=300,
       condition=should_cache
   )
   def api_call(endpoint):
       response = requests.get(endpoint)
       return response.json()

Cache Warming
~~~~~~~~~~~~~

.. code-block:: python

   @cached(ttl=3600)
   def expensive_computation(param):
       return complex_calculation(param)

   # Warm cache for common parameters
   def warm_cache():
       common_params = [1, 2, 3, 4, 5]
       for param in common_params:
           expensive_computation(param)

   # Call during application startup
   warm_cache()

Next Steps
----------

* Learn about :doc:`configuration` for decorator configuration options
* Explore :doc:`monitoring` for tracking decorator performance
* Check :doc:`../examples/index` for real-world decorator usage patterns
