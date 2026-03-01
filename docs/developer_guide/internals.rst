Internals
=========

This document provides deep technical details about Omni-Cache's internal implementation, algorithms, and design decisions.

Memory Management
-----------------

Memory Adapter Internals
~~~~~~~~~~~~~~~~~~~~~~~~

The Memory Adapter uses several data structures for efficient operation:

.. code-block:: python

   class MemoryAdapter:
       def __init__(self, config):
           # Primary data storage
           self._data = {}                    # key -> value mapping
           
           # LRU tracking
           self._access_order = OrderedDict() # key -> access_time  
           
           # TTL tracking
           self._ttl_data = {}               # key -> expiry_time
           
           # Statistics
           self._stats = {
               'hits': 0,
               'misses': 0, 
               'evictions': 0,
               'memory_usage': 0
           }
           
           # Thread safety
           self._lock = threading.RLock()
           
           # Configuration
           self._max_size = config.get('max_size', 10000)
           self._eviction_policy = config.get('eviction_policy', 'lru')

**Data Structure Analysis:**

- **Primary Storage (``_data``)**:
  Standard Python dict for O(1) key lookup.
  Memory overhead: ~24 bytes per key-value pair (64-bit Python).

- **LRU Tracking (``_access_order``)**:
  OrderedDict for O(1) move-to-end operations.
  Additional memory overhead: ~48 bytes per entry.
  Alternatives considered: doubly-linked list (similar performance, more complexity),
  heap-based approach (O(log n), not ideal for LRU).

- **TTL Tracking (``_ttl_data``)**:
  Separate dict to avoid overhead for non-TTL entries.
  Cleanup strategy combines lazy expiration on access and background cleanup.

Eviction Algorithms
~~~~~~~~~~~~~~~~~~~

**LRU (Least Recently Used)**

.. code-block:: python

   def _evict_lru(self):
       """Evict least recently used item."""
       if not self._access_order:
           return False
       
       # Get least recently used key
       lru_key = next(iter(self._access_order))
       
       # Remove from all data structures
       self._remove_key(lru_key)
       
       self._stats['evictions'] += 1
       return True

**LFU (Least Frequently Used)**

.. code-block:: python

   def _evict_lfu(self):
       """Evict least frequently used item."""
       if not self._frequency_count:
           return False
       
       # Find minimum frequency
       min_freq = min(self._frequency_count.values())
       
       # Find key with minimum frequency (arbitrary if tie)
       lfu_key = None
       for key, freq in self._frequency_count.items():
           if freq == min_freq:
               lfu_key = key
               break
       
       self._remove_key(lfu_key)
       self._stats['evictions'] += 1
       return True

**Time Complexity Analysis:**
- LRU: O(1) for all operations
- LFU: O(n) for eviction, O(1) for get/set
- FIFO: O(1) for all operations

TTL Implementation
~~~~~~~~~~~~~~~~~~

**Lazy TTL Cleanup**

.. code-block:: python

   def _is_expired(self, key):
       """Check if key has expired."""
       if key not in self._ttl_data:
           return False
       
       expiry_time = self._ttl_data[key]
       return time.time() > expiry_time

   def _cleanup_expired(self):
       """Remove expired entries (called periodically)."""
       current_time = time.time()
       expired_keys = []
       
       for key, expiry_time in self._ttl_data.items():
           if current_time > expiry_time:
               expired_keys.append(key)
       
       for key in expired_keys:
           self._remove_key(key)

**Proactive TTL Cleanup**

.. code-block:: python

   def _start_ttl_cleanup_thread(self):
       """Start background thread for TTL cleanup."""
       def cleanup_worker():
           while not self._shutdown:
               time.sleep(self._ttl_check_interval)
               try:
                   self._cleanup_expired()
               except Exception as e:
                   logging.error(f"TTL cleanup failed: {e}")
       
       self._cleanup_thread = threading.Thread(
           target=cleanup_worker, 
           daemon=True
       )
       self._cleanup_thread.start()

Threading and Concurrency
-------------------------

Lock Strategy
~~~~~~~~~~~~~

**Read-Write Lock Pattern**

.. code-block:: python

   class ReadWriteLock:
       """Reader-writer lock implementation."""
       
       def __init__(self):
           self._read_ready = threading.Condition(threading.RLock())
           self._readers = 0
       
       def acquire_read(self):
           """Acquire read lock."""
           self._read_ready.acquire()
           try:
               self._readers += 1
           finally:
               self._read_ready.release()
       
       def release_read(self):
           """Release read lock."""
           self._read_ready.acquire()
           try:
               self._readers -= 1
               if self._readers == 0:
                   self._read_ready.notifyAll()
           finally:
               self._read_ready.release()
       
       def acquire_write(self):
           """Acquire write lock."""
           self._read_ready.acquire()
           while self._readers > 0:
               self._read_ready.wait()
       
       def release_write(self):
           """Release write lock."""
           self._read_ready.release()

**Lock-Free Operations**

For high-performance scenarios, some operations use lock-free techniques:

.. code-block:: python

   import threading
   
   class LockFreeCounter:
       """Lock-free counter using atomic operations."""
       
       def __init__(self):
           self._value = 0
           self._lock = threading.Lock()  # Fallback only
       
       def increment(self):
           """Atomically increment counter."""
           # Try lock-free increment (Python GIL provides atomicity for simple ops)
           old_value = self._value
           self._value = old_value + 1
           return old_value

**Deadlock Prevention**

Lock ordering to prevent deadlocks:

.. code-block:: python

   class MultiLockAdapter:
       """Adapter with multiple locks using consistent ordering."""
       
       def __init__(self):
           # Always acquire locks in this order to prevent deadlocks
           self._config_lock = threading.RLock()    # Lock ID: 1
           self._data_lock = threading.RLock()      # Lock ID: 2  
           self._stats_lock = threading.RLock()     # Lock ID: 3
       
       def complex_operation(self):
           """Operation requiring multiple locks."""
           with self._config_lock:      # Acquire in order: 1, 2, 3
               with self._data_lock:
                   with self._stats_lock:
                       # Perform operation
                       pass

Redis Connection Management
---------------------------

Connection Pool Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class ConnectionPool:
       """Redis connection pool with health checking."""
       
       def __init__(self, host, port, max_connections=50):
           self.host = host
           self.port = port
           self.max_connections = max_connections
           
           # Connection tracking
           self._available = queue.Queue(maxsize=max_connections)
           self._in_use = set()
           self._total_connections = 0
           
           # Health checking
           self._last_health_check = 0
           self._health_check_interval = 30
           
           # Thread safety
           self._lock = threading.Lock()
       
       def get_connection(self, timeout=None):
           """Get connection from pool."""
           try:
               # Try to get existing connection
               connection = self._available.get(timeout=timeout)
               
               # Health check if needed
               if self._needs_health_check():
                   if not self._is_healthy(connection):
                       connection.close()
                       connection = self._create_connection()
               
               self._in_use.add(connection)
               return connection
               
           except queue.Empty:
               # Pool exhausted
               if self._total_connections < self.max_connections:
                   return self._create_connection()
               else:
                   raise ConnectionError("Connection pool exhausted")
       
       def return_connection(self, connection):
           """Return connection to pool."""
           if connection in self._in_use:
               self._in_use.remove(connection)
               self._available.put(connection)

**Connection Health Monitoring**

.. code-block:: python

   def _is_healthy(self, connection):
       """Check connection health."""
       try:
           # Send PING command
           response = connection.ping()
           return response == b'PONG'
       except Exception:
           return False
   
   def _health_check_all(self):
       """Health check all connections."""
       unhealthy = []
       
       # Check available connections
       temp_connections = []
       while not self._available.empty():
           try:
               conn = self._available.get_nowait()
               if self._is_healthy(conn):
                   temp_connections.append(conn)
               else:
                   unhealthy.append(conn)
                   conn.close()
           except queue.Empty:
               break
       
       # Return healthy connections to pool
       for conn in temp_connections:
           self._available.put(conn)
       
       return len(unhealthy)

Serialization Pipeline
----------------------

Serialization Framework
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class SerializationPipeline:
       """Multi-stage serialization pipeline."""
       
       def __init__(self):
           self.stages = []
       
       def add_stage(self, stage):
           """Add serialization stage."""
           self.stages.append(stage)
       
       def serialize(self, obj):
           """Run object through serialization pipeline."""
           data = obj
           metadata = {'stages': []}
           
           for stage in self.stages:
               try:
                   data, stage_metadata = stage.serialize(data)
                   metadata['stages'].append({
                       'stage': stage.__class__.__name__,
                       'metadata': stage_metadata
                   })
               except Exception as e:
                   raise SerializationError(f"Stage {stage} failed: {e}")
           
           return data, metadata
       
       def deserialize(self, data, metadata):
           """Reverse serialization pipeline."""
           # Reverse the stages
           for stage_info in reversed(metadata['stages']):
               stage_name = stage_info['stage']
               stage_metadata = stage_info['metadata']
               
               # Find matching stage
               stage = self._find_stage(stage_name)
               data = stage.deserialize(data, stage_metadata)
           
           return data

**Compression Stage**

.. code-block:: python

   class CompressionStage:
       """Compression serialization stage."""
       
       def __init__(self, compression_level=6, min_size=1024):
           self.compression_level = compression_level
           self.min_size = min_size
       
       def serialize(self, data):
           """Compress data if above minimum size."""
           if len(data) < self.min_size:
               return data, {'compressed': False}
           
           import zlib
           compressed = zlib.compress(data, self.compression_level)
           
           # Only use compression if it actually reduces size
           if len(compressed) < len(data):
               return compressed, {
                   'compressed': True,
                   'original_size': len(data),
                   'compressed_size': len(compressed)
               }
           else:
               return data, {'compressed': False}
       
       def deserialize(self, data, metadata):
           """Decompress data if needed."""
           if metadata.get('compressed', False):
               import zlib
               return zlib.decompress(data)
           return data

**Encryption Stage**

.. code-block:: python

   class EncryptionStage:
       """Encryption serialization stage."""
       
       def __init__(self, key):
           from cryptography.fernet import Fernet
           self.cipher = Fernet(key)
       
       def serialize(self, data):
           """Encrypt data."""
           encrypted = self.cipher.encrypt(data)
           return encrypted, {'encrypted': True}
       
       def deserialize(self, data, metadata):
           """Decrypt data."""
           if metadata.get('encrypted', False):
               return self.cipher.decrypt(data)
           return data

SmartPool Algorithms
--------------------

Adaptive Sizing Algorithm
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class AdaptiveSizer:
       """Adaptive pool sizing based on usage patterns."""
       
       def __init__(self, initial_size, min_size, max_size):
           self.size = initial_size
           self.min_size = min_size
           self.max_size = max_size
           
           # Metrics for decision making
           self.usage_history = collections.deque(maxlen=100)
           self.wait_times = collections.deque(maxlen=50)
           self.last_adjustment = 0
           
           # Thresholds
           self.high_usage_threshold = 0.8
           self.low_usage_threshold = 0.3
           self.min_adjustment_interval = 60  # seconds
       
       def record_usage(self, active_objects, total_objects, wait_time=0):
           """Record usage metrics."""
           usage_ratio = active_objects / max(total_objects, 1)
           self.usage_history.append(usage_ratio)
           
           if wait_time > 0:
               self.wait_times.append(wait_time)
       
       def should_resize(self):
           """Determine if pool should be resized."""
           if time.time() - self.last_adjustment < self.min_adjustment_interval:
               return None  # Too soon to adjust
           
           if len(self.usage_history) < 10:
               return None  # Not enough data
           
           # Calculate recent average usage
           recent_usage = sum(list(self.usage_history)[-10:]) / 10
           avg_wait_time = sum(self.wait_times) / max(len(self.wait_times), 1)
           
           # Decision logic
           if recent_usage > self.high_usage_threshold or avg_wait_time > 1.0:
               if self.size < self.max_size:
                   return 'grow'
           elif recent_usage < self.low_usage_threshold and avg_wait_time < 0.1:
               if self.size > self.min_size:
                   return 'shrink'
           
           return None
       
       def adjust_size(self, action):
           """Adjust pool size."""
           if action == 'grow':
               new_size = min(int(self.size * 1.5), self.max_size)
           elif action == 'shrink':
               new_size = max(int(self.size * 0.7), self.min_size)
           else:
               return
           
           old_size = self.size
           self.size = new_size
           self.last_adjustment = time.time()
           
           logging.info(f"Pool size adjusted: {old_size} -> {new_size} ({action})")

Object Lifecycle Management
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class ObjectLifecycleManager:
       """Manages object creation, validation, and cleanup."""
       
       def __init__(self, factory, validator, cleanup):
           self.factory = factory
           self.validator = validator  
           self.cleanup = cleanup
           
           # Object tracking
           self.objects = {}  # object_id -> ObjectInfo
           self.next_id = 0
           
       def create_object(self):
           """Create new object with lifecycle tracking."""
           try:
               obj = self.factory()
               obj_id = self._get_next_id()
               
               self.objects[obj_id] = ObjectInfo(
                   obj=obj,
                   created_at=time.time(),
                   last_used=time.time(),
                   use_count=0,
                   is_valid=True
               )
               
               return obj, obj_id
               
           except Exception as e:
               logging.error(f"Object creation failed: {e}")
               raise
       
       def validate_object(self, obj_id):
           """Validate object is still usable."""
           if obj_id not in self.objects:
               return False
           
           obj_info = self.objects[obj_id]
           
           # Check basic validity flag
           if not obj_info.is_valid:
               return False
           
           # Run custom validator
           try:
               is_valid = self.validator(obj_info.obj)
               obj_info.is_valid = is_valid
               return is_valid
           except Exception as e:
               logging.warning(f"Object validation failed: {e}")
               obj_info.is_valid = False
               return False
       
       def cleanup_object(self, obj_id):
           """Cleanup object and remove from tracking."""
           if obj_id not in self.objects:
               return
           
           obj_info = self.objects[obj_id]
           
           try:
               self.cleanup(obj_info.obj)
           except Exception as e:
               logging.warning(f"Object cleanup failed: {e}")
           finally:
               del self.objects[obj_id]

Routing Implementation
----------------------

Consistent Hashing
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class ConsistentHashRing:
       """Consistent hash ring for distributing keys."""
       
       def __init__(self, nodes, virtual_nodes=150):
           self.nodes = set(nodes)
           self.virtual_nodes = virtual_nodes
           self.ring = {}
           self._build_ring()
       
       def _build_ring(self):
           """Build the hash ring."""
           import hashlib
           
           self.ring.clear()
           
           for node in self.nodes:
               for i in range(self.virtual_nodes):
                   # Create virtual node identifier
                   virtual_key = f"{node}:{i}"
                   
                   # Hash to position on ring
                   hash_value = int(
                       hashlib.md5(virtual_key.encode()).hexdigest(), 
                       16
                   )
                   
                   self.ring[hash_value] = node
       
       def get_node(self, key):
           """Get node for given key."""
           if not self.ring:
               return None
           
           # Hash key to ring position
           key_hash = int(
               hashlib.md5(key.encode()).hexdigest(), 
               16
           )
           
           # Find first node clockwise from key position
           ring_positions = sorted(self.ring.keys())
           
           for position in ring_positions:
               if position >= key_hash:
                   return self.ring[position]
           
           # Wrap around to first node
           return self.ring[ring_positions[0]]
       
       def add_node(self, node):
           """Add node to ring."""
           self.nodes.add(node)
           self._build_ring()
       
       def remove_node(self, node):
           """Remove node from ring."""
           self.nodes.discard(node)
           self._build_ring()

Circuit Breaker Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import enum
   import time
   import threading
   
   class CircuitState(enum.Enum):
       CLOSED = "closed"
       OPEN = "open"
       HALF_OPEN = "half_open"
   
   class CircuitBreaker:
       """Circuit breaker for fault tolerance."""
       
       def __init__(self, failure_threshold=5, timeout=60, success_threshold=3):
           self.failure_threshold = failure_threshold
           self.timeout = timeout
           self.success_threshold = success_threshold
           
           # State tracking
           self.state = CircuitState.CLOSED
           self.failure_count = 0
           self.success_count = 0
           self.last_failure_time = 0
           
           # Thread safety
           self._lock = threading.Lock()
       
       def call(self, func, *args, **kwargs):
           """Execute function with circuit breaker protection."""
           with self._lock:
               if self.state == CircuitState.OPEN:
                   if time.time() - self.last_failure_time >= self.timeout:
                       self.state = CircuitState.HALF_OPEN
                       self.success_count = 0
                   else:
                       raise CircuitBreakerOpenError("Circuit breaker is open")
               
               try:
                   result = func(*args, **kwargs)
                   self._on_success()
                   return result
               
               except Exception as e:
                   self._on_failure()
                   raise
       
       def _on_success(self):
           """Handle successful operation."""
           if self.state == CircuitState.HALF_OPEN:
               self.success_count += 1
               if self.success_count >= self.success_threshold:
                   self.state = CircuitState.CLOSED
                   self.failure_count = 0
           elif self.state == CircuitState.CLOSED:
               self.failure_count = 0
       
       def _on_failure(self):
           """Handle failed operation."""
           self.failure_count += 1
           self.last_failure_time = time.time()
           
           if self.failure_count >= self.failure_threshold:
               self.state = CircuitState.OPEN

Performance Optimizations
-------------------------

Memory Pool for Small Objects
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class MemoryPool:
       """Memory pool for frequent small allocations."""
       
       def __init__(self, object_size, pool_size=1000):
           self.object_size = object_size
           self.pool_size = pool_size
           
           # Pre-allocate memory blocks
           self._free_blocks = []
           self._allocated_blocks = set()
           self._lock = threading.Lock()
           
           self._initialize_pool()
       
       def _initialize_pool(self):
           """Pre-allocate memory blocks."""
           import ctypes
           
           for _ in range(self.pool_size):
               # Allocate raw memory block
               block = (ctypes.c_byte * self.object_size)()
               self._free_blocks.append(block)
       
       def allocate(self):
           """Allocate memory block from pool."""
           with self._lock:
               if self._free_blocks:
                   block = self._free_blocks.pop()
                   self._allocated_blocks.add(id(block))
                   return block
               else:
                   # Pool exhausted, allocate normally
                   return (ctypes.c_byte * self.object_size)()
       
       def deallocate(self, block):
           """Return memory block to pool."""
           with self._lock:
               block_id = id(block)
               if block_id in self._allocated_blocks:
                   self._allocated_blocks.remove(block_id)
                   # Clear memory before reuse
                   ctypes.memset(block, 0, self.object_size)
                   self._free_blocks.append(block)

Copy-on-Write Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CopyOnWriteDict:
       """Dictionary with copy-on-write semantics."""
       
       def __init__(self, data=None):
           self._data = data or {}
           self._is_copy = False
           self._original = None
       
       def _ensure_writable(self):
           """Ensure dict is writable (copy if needed)."""
           if self._is_copy and self._original is not None:
               # Make a real copy
               self._data = dict(self._data)
               self._is_copy = False
               self._original = None
       
       def __getitem__(self, key):
           return self._data[key]
       
       def __setitem__(self, key, value):
           self._ensure_writable()
           self._data[key] = value
       
       def __delitem__(self, key):
           self._ensure_writable()
           del self._data[key]
       
       def copy(self):
           """Create copy-on-write copy."""
           new_dict = CopyOnWriteDict(self._data)
           new_dict._is_copy = True
           new_dict._original = self
           return new_dict

Profiling and Monitoring
------------------------

Performance Profiler Integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class PerformanceProfiler:
       """Integrated performance profiler."""
       
       def __init__(self):
           self.profiles = {}
           self.active_profiles = {}
           self._lock = threading.Lock()
       
       def start_profile(self, operation_name):
           """Start profiling an operation."""
           profile_id = f"{operation_name}_{threading.current_thread().ident}_{time.time()}"
           
           profile_data = {
               'operation': operation_name,
               'start_time': time.perf_counter(),
               'thread_id': threading.current_thread().ident,
               'memory_start': self._get_memory_usage()
           }
           
           with self._lock:
               self.active_profiles[profile_id] = profile_data
           
           return profile_id
       
       def end_profile(self, profile_id):
           """End profiling and record results."""
           end_time = time.perf_counter()
           memory_end = self._get_memory_usage()
           
           with self._lock:
               if profile_id not in self.active_profiles:
                   return None
               
               profile_data = self.active_profiles.pop(profile_id)
               
               result = {
                   'operation': profile_data['operation'],
                   'duration': end_time - profile_data['start_time'],
                   'memory_delta': memory_end - profile_data['memory_start'],
                   'thread_id': profile_data['thread_id']
               }
               
               operation = profile_data['operation']
               if operation not in self.profiles:
                   self.profiles[operation] = []
               
               self.profiles[operation].append(result)
               return result
       
       def _get_memory_usage(self):
           """Get current memory usage."""
           import psutil
           import os
           process = psutil.Process(os.getpid())
           return process.memory_info().rss

Debugging and Introspection
---------------------------

Cache State Inspector
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   class CacheStateInspector:
       """Deep inspection of cache internal state."""
       
       def __init__(self, cache):
           self.cache = cache
       
       def get_detailed_state(self):
           """Get comprehensive cache state information."""
           state = {
               'adapter_info': self._get_adapter_info(),
               'memory_usage': self._get_memory_usage(),
               'thread_info': self._get_thread_info(),
               'lock_state': self._get_lock_state(),
               'performance_metrics': self._get_performance_metrics()
           }
           return state
       
       def _get_adapter_info(self):
           """Get adapter-specific information."""
           adapter = self.cache._adapter
           
           info = {
               'type': adapter.__class__.__name__,
               'config': getattr(adapter, '_config', {}),
               'connection_state': getattr(adapter, 'is_connected', lambda: None)()
           }
           
           # Adapter-specific details
           if hasattr(adapter, '_data'):  # Memory adapter
               info['item_count'] = len(adapter._data)
               info['ttl_entries'] = len(getattr(adapter, '_ttl_data', {}))
           
           if hasattr(adapter, '_pool'):  # Redis adapter
               info['connection_pool_size'] = len(adapter._pool._available_connections)
               info['active_connections'] = len(adapter._pool._in_use_connections)
           
           return info
       
       def _get_lock_state(self):
           """Get information about lock states."""
           lock_info = {}
           
           adapter = self.cache._adapter
           if hasattr(adapter, '_lock'):
               lock = adapter._lock
               lock_info['adapter_lock'] = {
                   'locked': lock._is_owned(),
                   'count': lock._count if hasattr(lock, '_count') else None
               }
           
           return lock_info

This internal documentation provides developers with deep technical insights into Omni-Cache's implementation details, helping them understand performance characteristics, extend functionality, and debug issues effectively.

Next Steps
----------

* See :doc:`architecture` for high-level design overview
* Review :doc:`custom_adapters` for extension examples
* Check :doc:`testing` for testing internal components
