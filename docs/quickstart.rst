Quickstart
==========

This guide gets you running with Omni-Cache in minutes.

Installation
------------

.. code-block:: bash

   pip install omni_cache
   pip install omni_cache[redis]
   pip install omni_cache[all]

Minimal Example
---------------

.. code-block:: python

   from omni_cache import cached

   @cached(ttl=300)
   def get_user_data(user_id):
       return database.query(f"SELECT * FROM users WHERE id = {user_id}")

   # First call computes, second call is cached
   user = get_user_data(123)
   user = get_user_data(123)

Manager Example
---------------

.. code-block:: python

   from omni_cache import CacheManager

   manager = CacheManager()

   manager.set("user:123", {"name": "Alice"}, ttl=300)
   user = manager.get("user:123")
   exists = manager.exists("user:123")

   manager.delete("user:123")

Multi-Backend Setup
-------------------

.. code-block:: python

   from omni_cache import CacheBackend, CacheManager, create_adapter

   manager = CacheManager()

   memory_adapter = create_adapter(CacheBackend.MEMORY, {
       "max_size": 10000,
       "eviction_policy": "lru",
   })
   manager.register_adapter("fast", memory_adapter)

   try:
       redis_adapter = create_adapter(CacheBackend.REDIS, {
           "host": "localhost",
           "port": 6379,
           "db": 0,
       })
       manager.register_adapter("persistent", redis_adapter)
   except ImportError:
       print("Redis not available")

Routing
-------

.. code-block:: python

   manager.add_routing_rule("cache", "fast")
   manager.add_routing_rule("store", "persistent")

   manager.set("cache:session", session_data)
   manager.set("store:user", user_data)

Object Pooling
--------------

.. code-block:: python

   from omni_cache import pooled

   @pooled(adapter="db_pool", timeout=5.0)
   def query_database(connection, query, params):
       return connection.execute(query, params).fetchall()

   result = query_database("SELECT 1", ())

Environment Setup
-----------------

.. code-block:: bash

   export OMNI_CACHE_LOG_LEVEL=INFO
   export OMNI_CACHE_ENABLE_ROUTING=true
   export OMNI_CACHE_AUTO_SETUP=true

Next Steps
----------

- :doc:`user_guide/index`
- :doc:`examples/index`
- :doc:`developer_guide/index`
- :doc:`api/index`
