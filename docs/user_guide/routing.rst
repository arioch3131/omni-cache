Routing
=======

Omni-Cache supports intelligent routing between multiple adapters, allowing you to distribute cache operations based on keys, namespaces, or custom rules.

Overview
--------

Routing enables:
- Load distribution across multiple backends
- Fallback mechanisms for high availability
- Namespace-based adapter selection
- Custom routing logic for specific use cases

Basic Routing
-------------

Multi-Adapter Setup
~~~~~~~~~~~~~~~~~~~

Configure multiple adapters with routing:

.. code-block:: python

   from omni_cache import OmniCache
   from omni_cache.core.routing import RoutingConfig

   # Configure routing
   routing_config = RoutingConfig([
       {
           "name": "fast_cache",
           "adapter": "memory",
           "config": {"max_size": 1000}
       },
       {
           "name": "persistent_cache", 
           "adapter": "redis",
           "config": {"host": "localhost"}
       }
   ])

   cache = OmniCache.create_cache(routing=routing_config)

Routing Strategies
------------------

Namespace Routing
~~~~~~~~~~~~~~~~~

Route based on key namespaces:

.. code-block:: python

   from omni_cache.core.routing import NamespaceRouter

   router = NamespaceRouter({
       "users:*": "redis_cache",
       "sessions:*": "memory_cache",
       "default": "redis_cache"
   })

   cache = OmniCache.create_cache(router=router)

   # These go to different adapters based on namespace
   cache.set("users:123", user_data)      # -> redis_cache
   cache.set("sessions:abc", session)     # -> memory_cache
   cache.set("other:key", data)          # -> redis_cache (default)

Hash-Based Routing
~~~~~~~~~~~~~~~~~~

Distribute keys across adapters using hashing:

.. code-block:: python

   from omni_cache.core.routing import HashRouter

   router = HashRouter([
       "redis_cache_1",
       "redis_cache_2", 
       "redis_cache_3"
   ])

   cache = OmniCache.create_cache(router=router)

   # Keys are distributed across the three caches
   cache.set("key1", "value1")  # -> redis_cache_2
   cache.set("key2", "value2")  # -> redis_cache_1
   cache.set("key3", "value3")  # -> redis_cache_3

Load-Based Routing
~~~~~~~~~~~~~~~~~~

Route based on adapter load and performance:

.. code-block:: python

   from omni_cache.core.routing import LoadBalancedRouter

   router = LoadBalancedRouter([
       "memory_cache_1",
       "memory_cache_2"
   ], strategy="round_robin")

   cache = OmniCache.create_cache(router=router)

**Available Strategies:**
- ``round_robin``: Cycle through adapters
- ``least_connections``: Route to adapter with fewest active connections
- ``response_time``: Route to fastest responding adapter

Fallback Mechanisms
-------------------

Hierarchical Fallback
~~~~~~~~~~~~~~~~~~~~~

Set up fallback chains for high availability:

.. code-block:: python

   from omni_cache.core.routing import FallbackRouter

   router = FallbackRouter([
       "redis_primary",      # Try first
       "redis_secondary",    # Fallback 1
       "memory_cache"        # Fallback 2 (always available)
   ])

   cache = OmniCache.create_cache(router=router)

   # Automatically falls back if primary is unavailable
   value = cache.get("key")

Conditional Fallback
~~~~~~~~~~~~~~~~~~~~

Fallback based on conditions:

.. code-block:: python

   from omni_cache.core.routing import ConditionalRouter

   def fallback_condition(adapter_name, error):
       # Only fallback on connection errors, not data errors
       return isinstance(error, ConnectionError)

   router = ConditionalRouter({
       "primary": "redis_cache",
       "fallback": "memory_cache",
       "condition": fallback_condition
   })

Custom Routing
--------------

Custom Router Implementation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create your own routing logic:

.. code-block:: python

   from omni_cache.core.routing import BaseRouter

   class RegionRouter(BaseRouter):
       def __init__(self, region_map):
           self.region_map = region_map
           
       def route(self, operation, key, **kwargs):
           # Extract region from key
           if ":" in key:
               region = key.split(":")[0]
               if region in self.region_map:
                   return self.region_map[region]
           
           return "default_cache"

   router = RegionRouter({
       "us": "us_redis_cache",
       "eu": "eu_redis_cache", 
       "asia": "asia_redis_cache"
   })

Time-Based Routing
~~~~~~~~~~~~~~~~~~

Route based on time patterns:

.. code-block:: python

   import datetime
   from omni_cache.core.routing import BaseRouter

   class TimeBasedRouter(BaseRouter):
       def route(self, operation, key, **kwargs):
           hour = datetime.datetime.now().hour
           
           # Use fast cache during business hours
           if 9 <= hour <= 17:
               return "memory_cache"
           else:
               return "redis_cache"

Monitoring and Metrics
----------------------

Router Statistics
~~~~~~~~~~~~~~~~~

Track routing performance:

.. code-block:: python

   # Get routing statistics
   stats = cache.get_router_stats()
   
   print(f"Total requests: {stats['total_requests']}")
   print(f"Fallback rate: {stats['fallback_rate']:.2%}")
   
   # Per-adapter statistics
   for adapter_name, adapter_stats in stats['adapters'].items():
       print(f"{adapter_name}: {adapter_stats['requests']} requests")

Health Monitoring
~~~~~~~~~~~~~~~~~

Monitor adapter health for routing decisions:

.. code-block:: python

   from omni_cache.core.routing import HealthCheckRouter

   router = HealthCheckRouter({
       "adapters": ["redis_1", "redis_2", "redis_3"],
       "health_check_interval": 30,  # seconds
       "failure_threshold": 3,
       "recovery_threshold": 2
   })

Advanced Configuration
----------------------

Weighted Routing
~~~~~~~~~~~~~~~~

Assign weights to control traffic distribution:

.. code-block:: python

   from omni_cache.core.routing import WeightedRouter

   router = WeightedRouter([
       {"adapter": "redis_large", "weight": 70},
       {"adapter": "redis_small", "weight": 20},
       {"adapter": "memory_cache", "weight": 10}
   ])

Circuit Breaker
~~~~~~~~~~~~~~~

Prevent cascading failures with circuit breakers:

.. code-block:: python

   from omni_cache.core.routing import CircuitBreakerRouter

   router = CircuitBreakerRouter({
       "failure_threshold": 5,
       "timeout": 60,  # seconds
       "fallback_adapter": "memory_cache"
   })

Configuration Examples
----------------------

Multi-Region Setup
~~~~~~~~~~~~~~~~~~

.. code-block:: python

   config = {
       "routing": {
           "strategy": "namespace",
           "rules": {
               "us:*": {
                   "primary": "us_redis",
                   "fallback": "us_memory"
               },
               "eu:*": {
                   "primary": "eu_redis", 
                   "fallback": "eu_memory"
               }
           }
       },
       "adapters": {
           "us_redis": {"adapter": "redis", "host": "us.redis.com"},
           "eu_redis": {"adapter": "redis", "host": "eu.redis.com"},
           "us_memory": {"adapter": "memory", "max_size": 1000},
           "eu_memory": {"adapter": "memory", "max_size": 1000}
       }
   }

High Availability Setup
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   config = {
       "routing": {
           "strategy": "fallback",
           "chain": [
               "redis_primary",
               "redis_secondary", 
               "memory_backup"
           ]
       },
       "adapters": {
           "redis_primary": {
               "adapter": "redis",
               "host": "primary.redis.com"
           },
           "redis_secondary": {
               "adapter": "redis", 
               "host": "secondary.redis.com"
           },
           "memory_backup": {
               "adapter": "memory",
               "max_size": 5000
           }
       }
   }

Next Steps
----------

* Learn about :doc:`monitoring` for tracking routing performance
* Explore :doc:`performance` for routing optimization
* Check :doc:`../examples/index` for routing examples
