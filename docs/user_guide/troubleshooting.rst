Troubleshooting
===============

This guide helps you diagnose and resolve common issues with Omni-Cache, from connection problems to performance issues.

Common Issues
-------------

Connection Problems
~~~~~~~~~~~~~~~~~~~

**Redis Connection Failed**

.. code-block:: python

   # Error: ConnectionError: Error connecting to Redis
   
   # Diagnosis
   from omni_cache import OmniCache
   from omni_cache.core.exceptions import ConnectionError
   
   try:
       cache = OmniCache.create_cache(
           adapter="redis",
           config={
               "host": "localhost",
               "port": 6379,
               "socket_connect_timeout": 5
           }
       )
   except ConnectionError as e:
       print(f"Connection failed: {e}")
       
       # Check Redis server status
       import subprocess
       result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True)
       if result.returncode != 0:
           print("Redis server is not running")
       
       # Check network connectivity
       import socket
       try:
           sock = socket.create_connection(("localhost", 6379), timeout=5)
           sock.close()
           print("Network connection OK")
       except socket.error as e:
           print(f"Network error: {e}")

**Solutions:**
- Verify Redis server is running: ``redis-server``
- Check firewall settings
- Verify connection parameters (host, port, password)
- Increase connection timeout values

**Memory Adapter Out of Memory**

.. code-block:: python

   # Error: MemoryError: Cache size limit exceeded
   
   # Diagnosis
   cache = OmniCache.create_cache(adapter="memory")
   stats = cache.get_stats()
   
   print(f"Current size: {stats['item_count']}")
   print(f"Memory usage: {stats['memory_usage']} bytes")
   print(f"Max size: {stats['max_size']}")
   
   # Solutions
   # 1. Increase cache size
   cache = OmniCache.create_cache(
       adapter="memory",
       config={"max_size": 10000}
   )
   
   # 2. Enable LRU eviction
   cache = OmniCache.create_cache(
       adapter="memory", 
       config={
           "max_size": 5000,
           "eviction_policy": "lru"
       }
   )
   
   # 3. Set TTL for automatic cleanup
   cache = OmniCache.create_cache(
       adapter="memory",
       config={
           "default_ttl": 3600,  # 1 hour
           "ttl_check_interval": 300  # Check every 5 minutes
       }
   )

Performance Issues
~~~~~~~~~~~~~~~~~~

**Slow Cache Operations**

.. code-block:: python

   # Diagnosis: Measure operation latency
   import time
   from omni_cache import OmniCache
   
   cache = OmniCache.create_cache(adapter="redis", config={"enable_metrics": True})
   
   # Test operation performance
   start = time.perf_counter()
   cache.set("test_key", "test_value")
   set_time = (time.perf_counter() - start) * 1000
   
   start = time.perf_counter()
   value = cache.get("test_key")
   get_time = (time.perf_counter() - start) * 1000
   
   print(f"SET time: {set_time:.2f}ms")
   print(f"GET time: {get_time:.2f}ms")
   
   if set_time > 10 or get_time > 10:
       print("Performance issue detected!")
       
       # Get detailed metrics
       perf = cache.get_performance_metrics()
       print(f"Average latency: {perf.get('avg_latency', 0):.2f}ms")
       print(f"P95 latency: {perf.get('p95_latency', 0):.2f}ms")

**Common Causes and Solutions:**

1. **Network Latency**
   - Move cache closer to application
   - Use connection pooling
   - Enable keepalive connections

2. **Large Object Serialization**
   - Use more efficient serializers (msgpack, orjson)
   - Compress large objects
   - Split large objects into smaller chunks

3. **Memory Pressure**
   - Increase available memory
   - Optimize eviction policies  
   - Reduce cache size if necessary

**Low Hit Rate**

.. code-block:: python

   # Diagnosis
   stats = cache.get_stats()
   hit_rate = stats.get('hit_rate', 0)
   
   if hit_rate < 0.5:  # Less than 50% hit rate
       print(f"Low hit rate: {hit_rate:.2%}")
       
       # Analyze access patterns
       print(f"Hits: {stats.get('hits', 0)}")
       print(f"Misses: {stats.get('misses', 0)}")
       print(f"Evictions: {stats.get('evictions', 0)}")
       
       # Check TTL settings
       print(f"Average TTL: {stats.get('avg_ttl', 0)} seconds")

**Solutions:**
- Increase cache size
- Adjust TTL values
- Review key generation logic
- Implement cache warming strategies
- Analyze access patterns

Threading Issues
~~~~~~~~~~~~~~~~

**Thread Safety Problems**

.. code-block:: python

   # Error: Concurrent access causing data corruption
   
   # Diagnosis: Enable thread-safe mode
   cache = OmniCache.create_cache(
       adapter="memory",
       config={
           "thread_safe": True,
           "lock_timeout": 5.0
       }
   )
   
   # Use locks for critical sections
   import threading
   
   cache_lock = threading.RLock()
   
   def thread_safe_operation(key, value):
       with cache_lock:
           existing = cache.get(key)
           if existing is None:
               cache.set(key, value)
               return True
           return False

**Deadlock Detection**

.. code-block:: python

   # Enable deadlock detection
   from omni_cache.core.config import get_config_manager
   
   config_manager = get_config_manager()
   
   # Check for recursive calls
   if hasattr(threading.current_thread(), '_omni_cache_depth'):
       depth = getattr(threading.current_thread(), '_omni_cache_depth', 0)
       if depth > 3:
           print(f"Warning: Recursive cache call depth: {depth}")

Serialization Issues
~~~~~~~~~~~~~~~~~~~~

**Serialization Errors**

.. code-block:: python

   # Error: TypeError: Object of type X is not JSON serializable
   
   from omni_cache.core.exceptions import SerializationError
   
   try:
       cache.set("key", non_serializable_object)
   except SerializationError as e:
       print(f"Serialization failed: {e}")
       
       # Solution 1: Use pickle serializer
       import pickle
       cache = OmniCache.create_cache(
           adapter="redis",
           config={
               "serializer": pickle.dumps,
               "deserializer": pickle.loads
           }
       )
       
       # Solution 2: Custom serializer
       def custom_serializer(obj):
           if hasattr(obj, 'to_dict'):
               return json.dumps(obj.to_dict())
           return pickle.dumps(obj)
       
       def custom_deserializer(data):
           try:
               return json.loads(data)
           except:
               return pickle.loads(data)

**Version Compatibility Issues**

.. code-block:: python

   # Error: Can't deserialize data from different Python version
   
   # Solution: Version-aware serialization
   import pickle
   import sys
   
   def version_aware_serializer(obj):
       return pickle.dumps({
           'data': obj,
           'python_version': sys.version_info[:2],
           'pickle_protocol': pickle.HIGHEST_PROTOCOL
       })
   
   def version_aware_deserializer(data):
       try:
           unpickled = pickle.loads(data)
           if isinstance(unpickled, dict) and 'data' in unpickled:
               return unpickled['data']
           return unpickled
       except:
           # Fallback for old format
           return pickle.loads(data)

Debugging Tools
---------------

Enable Debug Logging
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   
   # Enable debug logging
   logging.basicConfig(level=logging.DEBUG)
   
   # Omni-Cache specific logging
   cache_logger = logging.getLogger('omni_cache')
   cache_logger.setLevel(logging.DEBUG)
   
   # Create handler with detailed format
   handler = logging.StreamHandler()
   formatter = logging.Formatter(
       '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   handler.setFormatter(formatter)
   cache_logger.addHandler(handler)

Cache Inspector
~~~~~~~~~~~~~~~

.. code-block:: python

   class CacheInspector:
       def __init__(self, cache):
           self.cache = cache
       
       def inspect_cache_state(self):
           """Get detailed cache state information"""
           stats = self.cache.get_stats()
           
           return {
               "basic_stats": stats,
               "connection_info": self.cache.get_info(),
               "configuration": self._get_safe_config(),
               "health_status": self._check_health()
           }
       
       def _get_safe_config(self):
           """Get config without sensitive information"""
           config = self.cache.get_config()
           safe_config = config.copy()
           
           # Remove sensitive fields
           sensitive_fields = ['password', 'auth_token', 'secret_key']
           for field in sensitive_fields:
               if field in safe_config:
                   safe_config[field] = '*' * 8
           
           return safe_config
       
       def _check_health(self):
           """Perform basic health checks"""
           try:
               # Test basic operations
               test_key = "__health_check__"
               test_value = "test"
               
               self.cache.set(test_key, test_value, ttl=60)
               retrieved = self.cache.get(test_key)
               self.cache.delete(test_key)
               
               return {
                   "status": "healthy" if retrieved == test_value else "unhealthy",
                   "basic_operations": "ok",
                   "last_check": time.time()
               }
           except Exception as e:
               return {
                   "status": "unhealthy",
                   "error": str(e),
                   "last_check": time.time()
               }

Performance Profiler
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import cProfile
   import pstats
   from functools import wraps
   
   def profile_cache_operations(func):
       """Decorator to profile cache operations"""
       @wraps(func)
       def wrapper(*args, **kwargs):
           profiler = cProfile.Profile()
           profiler.enable()
           
           try:
               result = func(*args, **kwargs)
           finally:
               profiler.disable()
               
               # Print top 10 time-consuming functions
               stats = pstats.Stats(profiler)
               stats.sort_stats('cumtime').print_stats(10)
           
           return result
       return wrapper
   
   # Usage
   @profile_cache_operations
   def heavy_cache_operation():
       for i in range(1000):
           cache.set(f"key_{i}", f"value_{i}")
           cache.get(f"key_{i}")

Memory Profiler
~~~~~~~~~~~~~~~

.. code-block:: python

   import tracemalloc
   import psutil
   import os
   
   class MemoryProfiler:
       def __init__(self):
           self.process = psutil.Process(os.getpid())
           
       def start_tracing(self):
           tracemalloc.start()
           
       def get_memory_snapshot(self):
           # System memory
           memory_info = self.process.memory_info()
           
           # Python memory tracing
           snapshot = tracemalloc.take_snapshot()
           top_stats = snapshot.statistics('lineno')
           
           return {
               "rss_memory": memory_info.rss,
               "vms_memory": memory_info.vms,
               "python_memory": sum(stat.size for stat in top_stats),
               "top_allocations": [
                   {
                       "filename": stat.traceback.format()[0],
                       "size": stat.size,
                       "count": stat.count
                   }
                   for stat in top_stats[:10]
               ]
           }

Diagnostic Commands
-------------------

Health Check Command
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def run_health_check(cache):
       """Comprehensive health check"""
       print("=== Omni-Cache Health Check ===")
       
       # Basic connectivity
       try:
           cache.set("__health__", "ok", ttl=60)
           value = cache.get("__health__")
           cache.delete("__health__")
           print("✓ Basic operations: OK")
       except Exception as e:
           print(f"✗ Basic operations: FAILED - {e}")
           return False
       
       # Performance check
       import time
       start = time.perf_counter()
       for i in range(100):
           cache.set(f"__perf_{i}__", "test", ttl=60)
       perf_time = (time.perf_counter() - start) * 1000
       print(f"✓ Performance: {perf_time:.2f}ms for 100 operations")
       
       # Cleanup
       for i in range(100):
           cache.delete(f"__perf_{i}__")
       
       # Statistics
       stats = cache.get_stats()
       print(f"✓ Statistics: {stats.get('item_count', 0)} items, "
             f"{stats.get('hit_rate', 0):.1%} hit rate")
       
       return True

Configuration Validator
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def validate_configuration(cache_config):
       """Validate cache configuration"""
       issues = []
       
       adapter = cache_config.get('adapter')
       config = cache_config.get('config', {})
       
       if adapter == 'redis':
           # Redis-specific validation
           if not config.get('host'):
               issues.append("Redis host not specified")
           
           if config.get('connection_pool_size', 10) > 100:
               issues.append("Connection pool size too large (>100)")
           
           if config.get('socket_timeout', 5) < 1:
               issues.append("Socket timeout too low (<1s)")
       
       elif adapter == 'memory':
           # Memory-specific validation
           if config.get('max_size', 1000) > 100000:
               issues.append("Memory cache size very large (>100k items)")
           
           if not config.get('eviction_policy'):
               issues.append("No eviction policy specified for memory cache")
       
       # General validation
       if config.get('ttl', 0) > 86400 * 7:  # 7 days
           issues.append("TTL very long (>7 days)")
       
       return issues

Recovery Procedures
-------------------

Cache Recovery
~~~~~~~~~~~~~~

.. code-block:: python

   def recover_cache(cache, backup_cache=None):
       """Attempt to recover from cache failures"""
       print("Starting cache recovery...")
       
       try:
           # Test current cache
           cache.set("__recovery_test__", "ok")
           cache.get("__recovery_test__")
           cache.delete("__recovery_test__")
           print("✓ Primary cache is working")
           return cache
           
       except Exception as e:
           print(f"✗ Primary cache failed: {e}")
           
           if backup_cache:
               try:
                   backup_cache.set("__recovery_test__", "ok")
                   backup_cache.get("__recovery_test__")
                   backup_cache.delete("__recovery_test__")
                   print("✓ Using backup cache")
                   return backup_cache
               except Exception as e2:
                   print(f"✗ Backup cache also failed: {e2}")
           
           # Create emergency memory cache
           print("Creating emergency memory cache...")
           emergency_cache = OmniCache.create_cache(
               adapter="memory",
               config={"max_size": 1000}
           )
           return emergency_cache

Data Migration
~~~~~~~~~~~~~~

.. code-block:: python

   def migrate_cache_data(source_cache, target_cache, batch_size=100):
       """Migrate data between caches"""
       print("Starting cache data migration...")
       
       # Get all keys (implementation depends on adapter)
       try:
           keys = source_cache.get_all_keys()  # May not be available for all adapters
       except AttributeError:
           print("Cannot enumerate keys, migration not possible")
           return False
       
       migrated = 0
       failed = 0
       
       for i in range(0, len(keys), batch_size):
           batch_keys = keys[i:i + batch_size]
           
           for key in batch_keys:
               try:
                   value = source_cache.get(key)
                   if value is not None:
                       target_cache.set(key, value)
                       migrated += 1
               except Exception as e:
                   print(f"Failed to migrate key {key}: {e}")
                   failed += 1
           
           print(f"Migrated: {migrated}, Failed: {failed}")
       
       print(f"Migration complete: {migrated} keys migrated, {failed} failed")
       return failed == 0

Common Error Messages
---------------------

Error Reference Table
~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1

   * - Error Message
     - Cause
     - Solution
   * - ``ConnectionError: Redis timeout``
     - Redis server is slow or overloaded
     - Increase timeout and check server health
   * - ``MemoryError: Cache full``
     - Memory cache reached capacity
     - Increase cache size or enable eviction policy
   * - ``SerializationError: Cannot serialize``
     - Object cannot be serialized with current serializer
     - Use pickle or provide a custom serializer
   * - ``KeyError: Key not found``
     - Cache miss or expired key
     - Verify TTL and implement fallback behavior
   * - ``ConfigurationError: Invalid adapter config``
     - Invalid configuration parameter
     - Validate configuration values before startup

Getting Help
------------

Enable Verbose Logging
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import logging
   
   # Maximum verbosity
   logging.basicConfig(
       level=logging.DEBUG,
       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
   )
   
   # Enable all Omni-Cache loggers
   for logger_name in ['omni_cache', 'omni_cache.core', 'omni_cache.adapters']:
       logger = logging.getLogger(logger_name)
       logger.setLevel(logging.DEBUG)

Collect Diagnostic Information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def collect_diagnostics(cache):
       """Collect comprehensive diagnostic information"""
       import platform
       import sys
       
       diagnostics = {
           "system_info": {
               "python_version": sys.version,
               "platform": platform.platform(),
               "architecture": platform.architecture()
           },
           "cache_info": {
               "adapter": cache.get_adapter_name(),
               "configuration": cache.get_config(),
               "statistics": cache.get_stats(),
               "health": cache.is_connected()
           },
           "performance": cache.get_performance_metrics() if hasattr(cache, 'get_performance_metrics') else None
       }
       
       return diagnostics

Next Steps
----------

* Check :doc:`../examples/index` for working examples
* Review :doc:`performance` for optimization techniques
* Consult :doc:`../developer_guide/index` for advanced topics
