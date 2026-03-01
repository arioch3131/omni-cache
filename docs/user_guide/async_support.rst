Async Support
=============

Omni-Cache provides full support for asynchronous operations, allowing you to use async/await patterns with all cache adapters and features.

Async Cache Operations
----------------------

Basic Async Operations
~~~~~~~~~~~~~~~~~~~~~~

Use async methods for non-blocking cache operations:

.. code-block:: python

   import asyncio
   from omni_cache import OmniCache

   async def main():
       # Create async cache
       cache = await OmniCache.create_async_cache(
           adapter="redis",
           config={"host": "localhost"}
       )
       
       # Async operations
       await cache.set("key", "value")
       value = await cache.get("key")
       await cache.delete("key")
       
       print(f"Retrieved: {value}")

   # Run async code
   asyncio.run(main())

Async Context Manager
~~~~~~~~~~~~~~~~~~~~~

Use cache as an async context manager:

.. code-block:: python

   async def with_cache():
       async with OmniCache.create_async_cache(adapter="redis") as cache:
           await cache.set("session:123", {"user_id": 456})
           session = await cache.get("session:123")
           return session

Async Decorators
----------------

@async_cached
~~~~~~~~~~~~~

Cache async function results:

.. code-block:: python

   from omni_cache import async_cached
   import aiohttp

   @async_cached(ttl=300, namespace="api")
   async def fetch_user_data(user_id):
       async with aiohttp.ClientSession() as session:
           async with session.get(f"https://api.example.com/users/{user_id}") as response:
               return await response.json()

   # Usage
   async def get_user():
       user_data = await fetch_user_data(123)  # API call
       user_data = await fetch_user_data(123)  # Cached
       return user_data

@async_memoize
~~~~~~~~~~~~~~

Async LRU memoization:

.. code-block:: python

   from omni_cache import async_memoize

   @async_memoize(maxsize=1000)
   async def expensive_async_computation(n):
       await asyncio.sleep(0.1)  # Simulate work
       return n * n

   # Fast subsequent calls
   result = await expensive_async_computation(10)

Concurrent Operations
---------------------

Batch Operations
~~~~~~~~~~~~~~~~

Perform multiple cache operations concurrently:

.. code-block:: python

   async def batch_operations():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       # Concurrent sets
       await asyncio.gather(
           cache.set("key1", "value1"),
           cache.set("key2", "value2"), 
           cache.set("key3", "value3")
       )
       
       # Concurrent gets
       results = await asyncio.gather(
           cache.get("key1"),
           cache.get("key2"),
           cache.get("key3")
       )
       
       return results

Pipeline Operations
~~~~~~~~~~~~~~~~~~~

Use pipelines for efficient batch operations:

.. code-block:: python

   async def pipeline_example():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       # Create pipeline
       async with cache.pipeline() as pipe:
           pipe.set("user:1", {"name": "Alice"})
           pipe.set("user:2", {"name": "Bob"})
           pipe.get("user:1")
           pipe.get("user:2")
           
           # Execute all operations
           results = await pipe.execute()
       
       return results

Async Patterns
--------------

Producer-Consumer Pattern
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   from omni_cache import OmniCache

   async def producer(cache, queue_name):
       """Produce items and cache them"""
       for i in range(10):
           item = f"item_{i}"
           await cache.set(f"queue:{queue_name}:{i}", item)
           await asyncio.sleep(0.1)

   async def consumer(cache, queue_name):
       """Consume items from cache"""
       processed = []
       for i in range(10):
           item = await cache.get(f"queue:{queue_name}:{i}")
           if item:
               processed.append(item)
               await cache.delete(f"queue:{queue_name}:{i}")
           await asyncio.sleep(0.05)
       return processed

   async def producer_consumer_example():
       cache = await OmniCache.create_async_cache(adapter="memory")
       
       # Run producer and consumer concurrently
       producer_task = asyncio.create_task(producer(cache, "work"))
       consumer_task = asyncio.create_task(consumer(cache, "work"))
       
       results = await asyncio.gather(producer_task, consumer_task)
       return results[1]  # Consumer results

Cache-Aside Pattern
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class AsyncUserService:
       def __init__(self):
           self.cache = None
           self.db = AsyncDatabase()
       
       async def initialize(self):
           self.cache = await OmniCache.create_async_cache(
               adapter="redis",
               config={"ttl": 3600}
           )
       
       async def get_user(self, user_id):
           # Try cache first
           cached_user = await self.cache.get(f"user:{user_id}")
           if cached_user:
               return cached_user
           
           # Load from database
           user = await self.db.get_user(user_id)
           if user:
               # Store in cache
               await self.cache.set(f"user:{user_id}", user)
           
           return user

Error Handling in Async Context
-------------------------------

Exception Handling
~~~~~~~~~~~~~~~~~~

Handle async cache exceptions:

.. code-block:: python

   from omni_cache.core.exceptions import CacheError, ConnectionError

   async def safe_cache_operation():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       try:
           value = await cache.get("key")
       except ConnectionError:
           # Handle connection issues
           print("Cache unavailable, using fallback")
           return get_fallback_value()
       except CacheError as e:
           # Handle other cache errors
           print(f"Cache error: {e}")
           return None

Timeout Handling
~~~~~~~~~~~~~~~~

Set timeouts for cache operations:

.. code-block:: python

   import asyncio

   async def cache_with_timeout():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       try:
           # Set 2-second timeout
           value = await asyncio.wait_for(
               cache.get("slow_key"),
               timeout=2.0
           )
           return value
       except asyncio.TimeoutError:
           print("Cache operation timed out")
           return None

Async Monitoring
----------------

Real-time Metrics
~~~~~~~~~~~~~~~~~

Monitor async cache performance:

.. code-block:: python

   async def monitor_cache_performance():
       cache = await OmniCache.create_async_cache(
           adapter="redis",
           config={"enable_metrics": True}
       )
       
       # Start monitoring task
       async def metrics_reporter():
           while True:
               stats = await cache.get_stats()
               print(f"Hit rate: {stats['hit_rate']:.2%}")
               await asyncio.sleep(10)
       
       monitor_task = asyncio.create_task(metrics_reporter())
       
       # Your application logic here
       await cache.set("key", "value")
       
       monitor_task.cancel()

Event Streaming
~~~~~~~~~~~~~~~

Stream cache events asynchronously:

.. code-block:: python

   async def stream_cache_events():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       # Stream cache events
       async for event in cache.stream_events():
           if event['type'] == 'cache_miss':
               print(f"Cache miss for key: {event['key']}")
           elif event['type'] == 'eviction':
               print(f"Evicted key: {event['key']}")

Advanced Async Features
-----------------------

Async Pooling
~~~~~~~~~~~~~

Use async object pooling:

.. code-block:: python

   from omni_cache import async_pooled

   @async_pooled(adapter="db_pool", timeout=5.0)
   async def query_database(connection, query):
       return await connection.execute(query)

   # Connection automatically managed
   results = await query_database("SELECT * FROM users")

Async Locks
~~~~~~~~~~~

Implement distributed async locks:

.. code-block:: python

   async def with_distributed_lock():
       cache = await OmniCache.create_async_cache(adapter="redis")
       
       async with cache.lock("resource_lock", timeout=10):
           # Critical section - only one coroutine at a time
           await perform_critical_operation()

Async Retry Logic
~~~~~~~~~~~~~~~~~

Implement retry logic for async operations:

.. code-block:: python

   from omni_cache import async_retry_with_cache

   @async_retry_with_cache(
       max_retries=3,
       retry_delay=1.0,
       exponential_backoff=True
   )
   async def unreliable_api_call(endpoint):
       async with aiohttp.ClientSession() as session:
           async with session.get(endpoint) as response:
               if response.status != 200:
                   raise aiohttp.ClientError("API call failed")
               return await response.json()

Performance Optimization
------------------------

Connection Pooling
~~~~~~~~~~~~~~~~~~

Optimize async connections:

.. code-block:: python

   cache_config = {
       "adapter": "redis",
       "config": {
           "connection_pool_size": 20,
           "max_connections": 50,
           "socket_keepalive": True,
           "socket_keepalive_options": {}
       }
   }

   cache = await OmniCache.create_async_cache(**cache_config)

Batching Strategy
~~~~~~~~~~~~~~~~~

Batch operations for better performance:

.. code-block:: python

   class AsyncBatchProcessor:
       def __init__(self, cache, batch_size=100):
           self.cache = cache
           self.batch_size = batch_size
           self.batch = []
       
       async def add_operation(self, operation):
           self.batch.append(operation)
           
           if len(self.batch) >= self.batch_size:
               await self.flush_batch()
       
       async def flush_batch(self):
           if self.batch:
               await asyncio.gather(*self.batch)
               self.batch.clear()

Testing Async Code
------------------

Async Test Fixtures
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import pytest
   import asyncio

   @pytest.fixture
   async def async_cache():
       cache = await OmniCache.create_async_cache(adapter="memory")
       yield cache
       await cache.close()

   @pytest.mark.asyncio
   async def test_async_cache_operations(async_cache):
       await async_cache.set("test_key", "test_value")
       value = await async_cache.get("test_key")
       assert value == "test_value"

Mock Async Operations
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from unittest.mock import AsyncMock
   import pytest

   @pytest.mark.asyncio
   async def test_with_mock_cache():
       mock_cache = AsyncMock()
       mock_cache.get.return_value = "mocked_value"
       
       result = await mock_cache.get("any_key")
       assert result == "mocked_value"

Best Practices
--------------

1. **Use Async Context Managers**
   - Properly manage cache lifecycle
   - Ensure connections are closed

2. **Handle Timeouts**
   - Set reasonable timeouts
   - Implement fallback mechanisms

3. **Batch Operations**
   - Group related operations
   - Use pipelines for efficiency

4. **Monitor Performance**
   - Track async operation latency
   - Monitor connection pool usage

5. **Error Handling**
   - Handle connection failures gracefully
   - Implement retry logic for transient errors

Next Steps
----------

* Learn about :doc:`performance` for async optimization
* Explore :doc:`../examples/web_applications` for async web app patterns  
* Check :doc:`../developer_guide/testing` for async testing strategies
