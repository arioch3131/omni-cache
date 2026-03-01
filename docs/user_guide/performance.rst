Performance
===========

This guide covers performance optimization techniques, best practices, and troubleshooting for Omni-Cache to help you achieve optimal caching performance.

Performance Fundamentals
------------------------

Key Performance Metrics
~~~~~~~~~~~~~~~~~~~~~~~

Monitor these critical metrics:

.. code-block:: python

   from omni_cache import OmniCache

   cache = OmniCache.create_cache(adapter="redis", config={"enable_metrics": True})
   
   # Get comprehensive performance metrics
   perf = cache.get_performance_metrics()
   
   print(f"Hit Rate: {perf['hit_rate']:.2%}")           # Target: >80%
   print(f"Avg Response Time: {perf['avg_latency']:.2f}ms")  # Target: <10ms
   print(f"Throughput: {perf['ops_per_second']:.0f} ops/sec")
   print(f"Memory Usage: {perf['memory_usage_mb']:.1f}MB")
   print(f"Error Rate: {perf['error_rate']:.3%}")       # Target: <1%

Optimization Strategies
-----------------------

Memory Adapter Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configure memory adapter for optimal performance:

.. code-block:: python

   # High-performance memory configuration
   memory_config = {
       "max_size": 100000,              # Large cache size
       "eviction_policy": "lru",        # Efficient LRU eviction
       "ttl_check_interval": 300,       # Less frequent TTL checks
       "cleanup_threshold": 0.1,        # Clean 10% when threshold hit
       "enable_stats": False            # Disable stats in production
   }
   
   cache = OmniCache.create_cache(adapter="memory", config=memory_config)

Redis Adapter Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~

Optimize Redis adapter for high throughput:

.. code-block:: python

   # High-performance Redis configuration
   redis_config = {
       # Connection optimization
       "connection_pool_size": 50,
       "max_connections": 100,
       "socket_connect_timeout": 2,
       "socket_timeout": 2,
       "socket_keepalive": True,
       "socket_keepalive_options": {
           "TCP_KEEPIDLE": 30,
           "TCP_KEEPINTVL": 10, 
           "TCP_KEEPCNT": 3
       },
       
       # Performance tuning
       "retry_on_timeout": True,
       "health_check_interval": 30,
       "decode_responses": False,       # Use bytes for better performance
       
       # Pipelining
       "pipeline_size": 100,
       "pipeline_timeout": 1.0
   }
   
   cache = OmniCache.create_cache(adapter="redis", config=redis_config)

SmartPool Optimization
~~~~~~~~~~~~~~~~~~~~~~

Configure SmartPool for adaptive performance:

.. code-block:: python

   # Adaptive pool configuration
   smartpool_config = {
       "initial_size": 50,
       "max_size": 500,
       "min_size": 10,
       "growth_factor": 1.5,
       "shrink_factor": 0.7,
       "grow_threshold": 0.8,          # Grow when 80% utilization
       "shrink_threshold": 0.3,        # Shrink when 30% utilization
       "resize_check_interval": 60,    # Check every minute
       "max_idle_time": 300,          # 5 minutes idle timeout
   }
   
   cache = OmniCache.create_cache(adapter="smartpool", config=smartpool_config)

Caching Strategies
------------------

Cache-Aside Pattern
~~~~~~~~~~~~~~~~~~~

Implement efficient cache-aside pattern:

.. code-block:: python

   class OptimizedDataService:
       def __init__(self):
           self.cache = OmniCache.create_cache(
               adapter="redis",
               config={"ttl": 3600}
           )
           self.db = Database()
       
       def get_user(self, user_id):
           # Try cache first
           cache_key = f"user:{user_id}"
           user = self.cache.get(cache_key)
           
           if user is not None:
               return user
           
           # Cache miss - load from database
           user = self.db.get_user(user_id)
           
           if user:
               # Cache with appropriate TTL
               ttl = 3600 if user.is_active else 300
               self.cache.set(cache_key, user, ttl=ttl)
           
           return user

Write-Through Pattern
~~~~~~~~~~~~~~~~~~~~~

Implement write-through for consistency:

.. code-block:: python

   def update_user(self, user_id, data):
       # Update database first
       success = self.db.update_user(user_id, data)
       
       if success:
           # Update cache immediately
           cache_key = f"user:{user_id}"
           updated_user = self.db.get_user(user_id)
           self.cache.set(cache_key, updated_user)
       
       return success

Write-Behind Pattern
~~~~~~~~~~~~~~~~~~~~

Implement write-behind for high write performance:

.. code-block:: python

   import asyncio
   from queue import Queue
   import threading

   class WriteBehindCache:
       def __init__(self):
           self.cache = OmniCache.create_cache(adapter="memory")
           self.write_queue = Queue()
           self.batch_size = 100
           self.flush_interval = 5  # seconds
           self._start_background_writer()
       
       def set(self, key, value):
           # Immediate cache update
           self.cache.set(key, value)
           
           # Queue for background DB write
           self.write_queue.put((key, value))
       
       def _start_background_writer(self):
           def background_writer():
               batch = []
               while True:
                   try:
                       # Collect batch
                       item = self.write_queue.get(timeout=self.flush_interval)
                       batch.append(item)
                       
                       if len(batch) >= self.batch_size:
                           self._flush_batch(batch)
                           batch = []
                   
                   except:  # Timeout
                       if batch:
                           self._flush_batch(batch)
                           batch = []
           
           thread = threading.Thread(target=background_writer, daemon=True)
           thread.start()
       
       def _flush_batch(self, batch):
           # Batch write to database
           self.db.batch_update(batch)

Key Design Patterns
-------------------

Efficient Key Naming
~~~~~~~~~~~~~~~~~~~~

Use structured, efficient key naming:

.. code-block:: python

   class KeyManager:
       @staticmethod
       def user_key(user_id):
           return f"u:{user_id}"  # Short prefix
       
       @staticmethod
       def session_key(session_id):
           return f"s:{session_id}"
       
       @staticmethod
       def api_cache_key(endpoint, params_hash):
           return f"api:{endpoint}:{params_hash}"
       
       @staticmethod
       def search_result_key(query_hash, page, filters_hash):
           return f"search:{query_hash}:{page}:{filters_hash}"

# Usage
key_mgr = KeyManager()
cache.set(key_mgr.user_key(123), user_data)

Namespace Strategy
~~~~~~~~~~~~~~~~~~

Organize cache with efficient namespaces:

.. code-block:: python

   class NamespaceManager:
       # High-frequency, short TTL
       USER_SESSIONS = "sessions"
       
       # Medium-frequency, medium TTL
       USER_PROFILES = "users"
       API_RESPONSES = "api"
       
       # Low-frequency, long TTL
       STATIC_DATA = "static"
       CONFIGURATION = "config"
   
   # Configure different TTLs per namespace
   cache.set("sessions:abc123", session_data, ttl=1800)    # 30 min
   cache.set("users:456", user_data, ttl=3600)             # 1 hour
   cache.set("static:menu", menu_data, ttl=86400)          # 24 hours

Serialization Optimization
--------------------------

Choose Efficient Serializers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Compare serialization performance:

.. code-block:: python

   import pickle
   import json
   import msgpack
   import orjson
   from omni_cache.serializers import CompressedPickleSerializer

   # Performance comparison (rough order: fastest to slowest for most data)
   serializers = {
       "orjson": (orjson.dumps, orjson.loads),           # Fastest JSON
       "msgpack": (msgpack.packb, msgpack.unpackb),      # Compact binary
       "pickle": (pickle.dumps, pickle.loads),           # Python native
       "json": (json.dumps, json.loads),                 # Standard JSON
       "compressed": (CompressedPickleSerializer.dumps,  # Large objects
                     CompressedPickleSerializer.loads)
   }
   
   # Use appropriate serializer for your data
   cache = OmniCache.create_cache(
       adapter="redis",
       config={
           "serializer": orjson.dumps,
           "deserializer": orjson.loads
       }
   )

Custom Serializer
~~~~~~~~~~~~~~~~~

Create optimized custom serializer:

.. code-block:: python

   class OptimizedSerializer:
       @staticmethod
       def serialize(obj):
           # Use different serializers based on object type
           if isinstance(obj, str):
               return obj.encode('utf-8')
           elif isinstance(obj, (int, float)):
               return str(obj).encode('utf-8')
           elif isinstance(obj, dict):
               return orjson.dumps(obj)
           else:
               return pickle.dumps(obj)
       
       @staticmethod
       def deserialize(data):
           try:
               # Try JSON first (most common)
               return orjson.loads(data)
           except:
               try:
                   # Try string/number
                   text = data.decode('utf-8')
                   if text.isdigit():
                       return int(text)
                   elif '.' in text:
                       return float(text)
                   return text
               except:
                   # Fallback to pickle
                   return pickle.loads(data)

Concurrency Optimization
------------------------

Thread-Safe Operations
~~~~~~~~~~~~~~~~~~~~~~

Optimize for concurrent access:

.. code-block:: python

   import threading
   from concurrent.futures import ThreadPoolExecutor

   class ConcurrentCacheService:
       def __init__(self):
           self.cache = OmniCache.create_cache(
               adapter="redis",
               config={
                   "connection_pool_size": 20,  # Handle concurrent requests
                   "max_connections": 50
               }
           )
           self.executor = ThreadPoolExecutor(max_workers=10)
       
       def batch_get(self, keys):
           """Get multiple keys concurrently"""
           def get_single(key):
               return self.cache.get(key)
           
           futures = [self.executor.submit(get_single, key) for key in keys]
           return [f.result() for f in futures]
       
       def batch_set(self, items):
           """Set multiple items concurrently"""
           def set_single(key, value):
               return self.cache.set(key, value)
           
           futures = [
               self.executor.submit(set_single, k, v) 
               for k, v in items.items()
           ]
           return [f.result() for f in futures]

Async Optimization
~~~~~~~~~~~~~~~~~~

Optimize async operations:

.. code-block:: python

   import asyncio
   from omni_cache import OmniCache

   class AsyncCacheService:
       def __init__(self):
           self.cache = None
       
       async def initialize(self):
           self.cache = await OmniCache.create_async_cache(
               adapter="redis",
               config={
                   "connection_pool_size": 50,
                   "max_connections": 100
               }
           )
       
       async def batch_operations(self, operations):
           """Execute cache operations concurrently"""
           tasks = []
           
           for op in operations:
               if op['type'] == 'get':
                   tasks.append(self.cache.get(op['key']))
               elif op['type'] == 'set':
                   tasks.append(self.cache.set(op['key'], op['value']))
           
           return await asyncio.gather(*tasks)

Pipeline Optimization
~~~~~~~~~~~~~~~~~~~~~

Use pipelines for batch operations:

.. code-block:: python

   async def optimized_batch_update(cache, updates):
       """Use pipeline for efficient batch updates"""
       async with cache.pipeline() as pipe:
           for key, value in updates.items():
               pipe.set(key, value)
           
           # Execute all commands in single round-trip
           results = await pipe.execute()
       
       return results

Memory Management
-----------------

Memory Monitoring
~~~~~~~~~~~~~~~~~

Monitor memory usage patterns:

.. code-block:: python

   class MemoryMonitor:
       def __init__(self, cache):
           self.cache = cache
           
       def get_memory_report(self):
           stats = self.cache.get_stats()
           return {
               "total_memory": stats.get('memory_usage', 0),
               "item_count": stats.get('item_count', 0),
               "avg_item_size": stats.get('avg_item_size', 0),
               "memory_efficiency": stats.get('memory_efficiency', 0),
               "fragmentation": stats.get('fragmentation', 0)
           }
       
       def optimize_memory(self):
           report = self.get_memory_report()
           
           if report['fragmentation'] > 0.3:  # 30% fragmentation
               # Trigger cache compaction
               self.cache.compact()
           
           if report['memory_efficiency'] < 0.7:  # Low efficiency
               # Suggest reducing cache size or TTL
               print("Consider reducing cache size or TTL")

Eviction Strategies
~~~~~~~~~~~~~~~~~~~

Optimize eviction policies:

.. code-block:: python

   # LRU for general purpose (good hit rate)
   lru_config = {"eviction_policy": "lru", "max_size": 10000}
   
   # LFU for stable access patterns
   lfu_config = {"eviction_policy": "lfu", "max_size": 10000}
   
   # TTL-based for time-sensitive data
   ttl_config = {"eviction_policy": "ttl", "max_size": 10000, "default_ttl": 3600}
   
   # Custom eviction for specialized needs
   def custom_eviction_policy(items):
       # Prioritize evicting items by business logic
       return sorted(items, key=lambda x: x.access_count + x.size_penalty)

Performance Testing
-------------------

Benchmark Framework
~~~~~~~~~~~~~~~~~~~

Create performance benchmarks:

.. code-block:: python

   import time
   import statistics
   from concurrent.futures import ThreadPoolExecutor

   class CacheBenchmark:
       def __init__(self, cache):
           self.cache = cache
       
       def benchmark_operation(self, operation, iterations=1000):
           """Benchmark specific cache operation"""
           times = []
           
           for i in range(iterations):
               start = time.perf_counter()
               operation()
               end = time.perf_counter()
               times.append((end - start) * 1000)  # Convert to ms
           
           return {
               "avg_time": statistics.mean(times),
               "median_time": statistics.median(times), 
               "p95_time": statistics.quantiles(times, n=20)[18],  # 95th percentile
               "min_time": min(times),
               "max_time": max(times)
           }
       
       def benchmark_throughput(self, operation, duration=10):
           """Benchmark operation throughput"""
           start_time = time.time()
           operations = 0
           
           while time.time() - start_time < duration:
               operation()
               operations += 1
           
           return operations / duration  # ops per second

Load Testing
~~~~~~~~~~~~

Test cache under load:

.. code-block:: python

   def load_test_cache(cache, num_threads=10, operations_per_thread=1000):
       """Load test with multiple threads"""
       def worker():
           for i in range(operations_per_thread):
               # Mix of operations
               if i % 3 == 0:
                   cache.set(f"key_{i}", f"value_{i}")
               else:
                   cache.get(f"key_{i % 100}")  # Some hits, some misses
       
       start_time = time.time()
       
       with ThreadPoolExecutor(max_workers=num_threads) as executor:
           futures = [executor.submit(worker) for _ in range(num_threads)]
           for future in futures:
               future.result()
       
       end_time = time.time()
       total_ops = num_threads * operations_per_thread
       
       return {
           "total_time": end_time - start_time,
           "total_operations": total_ops,
           "throughput": total_ops / (end_time - start_time)
       }

Performance Monitoring
----------------------

Real-time Performance Dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class PerformanceDashboard:
       def __init__(self, cache):
           self.cache = cache
           self.metrics_history = []
       
       def collect_metrics(self):
           """Collect current performance metrics"""
           stats = self.cache.get_stats()
           perf = self.cache.get_performance_metrics()
           
           metrics = {
               "timestamp": time.time(),
               "hit_rate": stats.get("hit_rate", 0),
               "ops_per_second": perf.get("ops_per_second", 0),
               "avg_latency": perf.get("avg_latency", 0),
               "memory_usage": perf.get("memory_usage", 0),
               "error_rate": perf.get("error_rate", 0)
           }
           
           self.metrics_history.append(metrics)
           
           # Keep only last hour of metrics
           cutoff = time.time() - 3600
           self.metrics_history = [
               m for m in self.metrics_history 
               if m["timestamp"] > cutoff
           ]
           
           return metrics
       
       def get_performance_trends(self):
           """Analyze performance trends"""
           if len(self.metrics_history) < 2:
               return None
           
           recent = self.metrics_history[-10:]  # Last 10 samples
           older = self.metrics_history[-20:-10]  # Previous 10 samples
           
           return {
               "hit_rate_trend": self._calculate_trend(recent, older, "hit_rate"),
               "latency_trend": self._calculate_trend(recent, older, "avg_latency"),
               "throughput_trend": self._calculate_trend(recent, older, "ops_per_second")
           }

Best Practices Summary
----------------------

1. **Choose the Right Adapter**
   - Memory for single-process, low latency
   - Redis for distributed, persistent caching
   - SmartPool for adaptive resource management

2. **Optimize Configuration**
   - Set appropriate pool sizes
   - Configure TTLs based on data patterns
   - Use efficient serializers

3. **Design Effective Keys**
   - Use short, structured key names
   - Organize with namespaces
   - Avoid key collisions

4. **Monitor Performance**
   - Track hit rates, latency, and throughput
   - Set up alerts for performance degradation
   - Regular performance testing

5. **Handle Concurrency**
   - Use connection pooling
   - Implement appropriate locking
   - Consider async patterns for I/O bound operations

Next Steps
----------

* Explore :doc:`troubleshooting` for performance issue resolution
* Check :doc:`../examples/performance` for performance optimization examples
* Learn about :doc:`monitoring` for comprehensive performance tracking
