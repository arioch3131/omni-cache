Adapters
========

Omni-Cache supports multiple storage backends through its adapter system. Each adapter provides the same interface while optimizing for different use cases and storage technologies.

Available Adapters
------------------

Memory Adapter
~~~~~~~~~~~~~~

In-memory caching with optional size limits and TTL support:

.. code-block:: python

   from omni_cache import OmniCache

   # Create memory cache
   cache = OmniCache.create_cache(
       adapter="memory",
       config={
           "max_size": 1000,
           "ttl": 3600
       }
   )

   # Basic operations
   cache.set("key", "value")
   value = cache.get("key")

**Configuration Options:**

* **max_size** (int): Maximum number of items to store
* **ttl** (int): Default time-to-live in seconds
* **eviction_policy** (str): "lru", "lfu", or "fifo"

Redis Adapter
~~~~~~~~~~~~~

Redis backend for distributed caching:

.. code-block:: python

   cache = OmniCache.create_cache(
       adapter="redis",
       config={
           "host": "localhost",
           "port": 6379,
           "db": 0,
           "password": "secret"
       }
   )

**Configuration Options:**

* **host** (str): Redis server hostname
* **port** (int): Redis server port
* **db** (int): Redis database number
* **password** (str): Redis password
* **ssl** (bool): Use SSL connection
* **connection_pool_size** (int): Connection pool size

Disk Adapter
~~~~~~~~~~~~

Disk backend using binary payload files with an SQLite index:

.. code-block:: python

   from omni_cache import CacheBackend, create_adapter

   disk_adapter = create_adapter(
       CacheBackend.DISK,
       {
           "cache_dir": "./omni_cache_disk",
           "default_ttl": 3600,
           "renew_on_hit": True,
           "renew_threshold": 0.2,
       },
   )

**Configuration Options:**

* **cache_dir** (str): Base directory where payload files are stored
* **sqlite_path** (str | None): Optional path to SQLite index file
* **default_ttl** (float | None): Default TTL used when ``ttl`` is not passed to ``set``
* **renew_on_hit** (bool): Enable TTL extension on access
* **renew_threshold** (float): Renewal window ratio in ``(0, 1]``
* **cleanup_interval_sec** (float): Periodic cleanup interval
* **batch_flush_interval_sec** (float): Hit batch flush interval
* **batch_flush_max_pending** (int): Max pending hit keys before forced flush

SmartPool Adapter
~~~~~~~~~~~~~~~~~

Intelligent memory pool with adaptive sizing:

.. code-block:: python

   cache = OmniCache.create_cache(
       adapter="smartpool",
       config={
           "initial_size": 100,
           "max_size": 1000,
           "growth_factor": 1.5
       }
   )

**Configuration Options:**

* **initial_size** (int): Starting pool size
* **max_size** (int): Maximum pool size
* **growth_factor** (float): Pool growth multiplier
* **shrink_threshold** (float): Usage threshold for shrinking

Adapter Selection
-----------------

Choosing the Right Adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Memory Adapter** - Best for:
- Single-process applications
- Fast access requirements
- Limited data size
- Development and testing

**Redis Adapter** - Best for:
- Multi-process applications
- Distributed systems
- Persistence requirements
- Large datasets

**SmartPool Adapter** - Best for:
- Resource-intensive objects
- Connection pooling
- Adaptive resource management
- High-concurrency scenarios

Configuration Management
------------------------

Global Configuration
~~~~~~~~~~~~~~~~~~~~

Set default adapter configuration:

.. code-block:: python

   from omni_cache.core.config import get_config_manager

   config_manager = get_config_manager()
   config_manager.set_adapter_config("memory", {
       "max_size": 2000,
       "ttl": 7200
   })

Per-Instance Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

Override defaults for specific instances:

.. code-block:: python

   # Use global defaults
   cache1 = OmniCache.create_cache(adapter="memory")

   # Override specific settings
   cache2 = OmniCache.create_cache(
       adapter="memory",
       config={"max_size": 500}
   )

Connection Management
---------------------

Connection Pooling
~~~~~~~~~~~~~~~~~~

Adapters automatically manage connections:

.. code-block:: python

   # Redis adapter with connection pooling
   cache = OmniCache.create_cache(
       adapter="redis",
       config={
           "host": "redis.example.com",
           "connection_pool_size": 20,
           "socket_timeout": 5.0
       }
   )

Health Checks
~~~~~~~~~~~~~

Monitor adapter health:

.. code-block:: python

   # Check if adapter is connected
   if cache.is_connected():
       print("Cache is ready")
   
   # Get connection info
   info = cache.get_info()
   print(f"Adapter: {info['adapter']}")
   print(f"Status: {info['status']}")

Error Handling
--------------

Connection Failures
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.core.exceptions import ConnectionError

   try:
       cache = OmniCache.create_cache(
           adapter="redis",
           config={"host": "unreachable-host"}
       )
   except ConnectionError as e:
       print(f"Failed to connect: {e}")
       # Fallback to memory cache
       cache = OmniCache.create_cache(adapter="memory")

Operation Failures
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.core.exceptions import CacheError

   try:
       value = cache.get("key")
   except CacheError as e:
       print(f"Cache operation failed: {e}")
       # Handle fallback logic
       value = None

Performance Tuning
------------------

Memory Adapter Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   memory_config = {
       "max_size": 10000,
       "eviction_policy": "lru",
       "ttl_check_interval": 60
   }

Redis Adapter Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   redis_config = {
       "connection_pool_size": 50,
       "socket_timeout": 2.0,
       "socket_connect_timeout": 2.0,
       "retry_on_timeout": True,
       "max_connections": 100
   }

Custom Adapters
---------------

Creating Custom Adapters
~~~~~~~~~~~~~~~~~~~~~~~~

See :doc:`../developer_guide/custom_adapters` for detailed information on creating your own adapters.

Adapter Interface
~~~~~~~~~~~~~~~~~

All adapters implement the base interface:

.. code-block:: python

   from omni_cache.adapters.base import BaseAdapter

   class MyAdapter(BaseAdapter):
       def get(self, key):
           # Implementation
           pass

       def set(self, key, value, ttl=None):
           # Implementation
           pass

       def delete(self, key):
           # Implementation
           pass

Next Steps
----------

* Learn about :doc:`routing` for multi-adapter setups
* Explore :doc:`monitoring` for adapter performance tracking
* Check :doc:`../examples/index` for adapter-specific examples
