Basic Usage
===========

This guide covers the main usage patterns with the current Omni-Cache API.

Core Concepts
-------------

Omni-Cache exposes two operation families:

- Key-value caching via :class:`omni_cache.core.manager.CacheManager`
- Object pooling via adapter-level ``get``/``put`` and manager-level ``borrow``/``put``

Manager-Based Usage
-------------------

.. code-block:: python

   from omni_cache import CacheManager

   manager = CacheManager()

Basic Cache Operations
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   manager.set("user:123", {"name": "Alice", "age": 30}, ttl=300)
   user = manager.get("user:123")

   if manager.exists("user:123"):
       print("User found in cache")

   manager.delete("user:123")
   manager.clear()

   # Optional introspection helpers
   keys = list(manager.keys())
   cache_size = manager.size()

Pooling Operations
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Context-manager usage (recommended)
   with manager.borrow(adapter="db_pool") as connection:
       result = connection.execute("SELECT 1")

Decorator-Based Usage
---------------------

.. code-block:: python

   from omni_cache import cached, memoize, pooled

   @cached(ttl=300)
   def get_user_profile(user_id):
       return database.query(f"SELECT * FROM users WHERE id = {user_id}")

   @memoize(maxsize=1000)
   def fibonacci(n):
       if n < 2:
           return n
       return fibonacci(n - 1) + fibonacci(n - 2)

   @pooled(adapter="db_pool", timeout=5.0)
   def execute_query(connection, query, params):
       return connection.execute(query, params).fetchall()

Working with Adapters
---------------------

.. code-block:: python

   from omni_cache import CacheBackend, create_adapter

   memory_adapter = create_adapter(CacheBackend.MEMORY, {
       "max_size": 10000,
       "eviction_policy": "lru",
       "default_ttl": 3600,
   })

   manager.register_adapter("memory", memory_adapter)

   # Explicit adapter selection
   manager.set("k", "v", adapter="memory")

Redis and SmartPool are optional dependencies:

.. code-block:: python

   try:
       redis_adapter = create_adapter(CacheBackend.REDIS, {
           "host": "localhost",
           "port": 6379,
           "db": 0,
       })
       manager.register_adapter("redis", redis_adapter)
   except ImportError:
       print("Redis not available")

   try:
       pool_adapter = create_adapter(CacheBackend.SMARTPOOL, {
           "factory_function": create_db_connection,
           "initial_size": 5,
           "max_size": 20,
       })
       manager.register_adapter("db_pool", pool_adapter)
   except ImportError:
       print("SmartPool not available")

Routing
-------

.. code-block:: python

   manager.add_routing_rule("cache", "memory")
   manager.add_routing_rule("store", "redis")

   manager.set("cache:temp_data", data)  # routed to memory
   manager.set("store:user_profile", user)  # routed to redis (if configured)

Next Reading
------------

- :doc:`configuration`
- :doc:`decorators`
- :doc:`routing`
- :doc:`monitoring`
