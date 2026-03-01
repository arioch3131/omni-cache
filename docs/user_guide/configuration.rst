Configuration
=============

This guide covers all configuration options and methods in Omni-Cache.

Configuration Overview
----------------------

Omni-Cache supports hierarchical configuration from multiple sources:

1. **Explicit parameters** (highest priority)
2. **Configuration files** (YAML, JSON, TOML)
3. **Environment variables**
4. **Default values** (lowest priority)

Configuration Files
-------------------

Supported Formats
~~~~~~~~~~~~~~~~~

Omni-Cache supports three configuration file formats:

* **YAML** (recommended): ``config.yaml``
* **JSON**: ``config.json``
* **TOML**: ``config.toml``

Basic Configuration Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # config.yaml
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

Loading Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache import setup, ConfigManager

   # Method 1: Using setup function
   manager = setup(config_file="config.yaml")

   # Method 2: Using ConfigManager directly
   config_manager = ConfigManager("config.yaml")
   manager = CacheManager(config_manager.get_manager_config())

   # Method 3: Auto-discovery
   # Looks for: omni_cache.yaml, omni_cache.json, omni_cache.toml
   manager = setup()

Global Configuration
--------------------

Global configuration affects the entire Omni-Cache system:

.. code-block:: yaml

   global:
     # Logging configuration
     log_level: "INFO"                    # DEBUG, INFO, WARNING, ERROR
     
     # Manager behavior
     default_cache_adapter: "memory"      # Default adapter name
     fallback_adapter: "memory"           # Fallback if primary fails
     enable_routing: true                 # Enable namespace routing
     namespace_separator: ":"            # Separator for namespace:key
     
     # Monitoring
     health_check_interval: 60.0         # Health check frequency (seconds)
     enable_global_stats: true           # Collect global statistics
     
     # Development
     debug_mode: false                    # Enable debug logging
     profile_operations: false           # Profile cache operations

Configuration Options Reference
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**log_level** (string, default: "INFO")
  Logging level for Omni-Cache components.

**default_cache_adapter** (string, default: None)
  Name of the default adapter to use when none specified.

**fallback_adapter** (string, default: None)
  Name of the fallback adapter when primary adapter fails.

**enable_routing** (boolean, default: false)
  Enable intelligent routing based on namespace patterns.

**namespace_separator** (string, default: ":")
  Character used to separate namespace from key.

**health_check_interval** (float, default: 60.0)
  Interval in seconds between health checks.

**enable_global_stats** (boolean, default: true)
  Whether to collect and maintain global statistics.

**debug_mode** (boolean, default: false)
  Enable verbose debug logging.

**profile_operations** (boolean, default: false)
  Enable operation profiling for performance analysis.

Adapter Configuration
---------------------

Each adapter can be configured individually:

Memory Adapter
~~~~~~~~~~~~~~

.. code-block:: yaml

   adapters:
     memory:
       backend: "memory"
       enabled: true
       auto_connect: true
       extra_config:
         max_size: 10000              # Maximum number of items
         default_ttl: 3600            # Default TTL in seconds
         eviction_policy: "lru"       # lru, fifo, random
         cleanup_interval: 60         # Cleanup frequency
         thread_safe: true            # Enable thread safety

**Configuration Options:**

* **max_size** (int): Maximum number of cached items
* **default_ttl** (int): Default time-to-live in seconds
* **eviction_policy** (str): Eviction strategy ("lru", "fifo", "random")
* **cleanup_interval** (int): Background cleanup interval in seconds
* **thread_safe** (bool): Enable thread-safe operations

Redis Adapter
~~~~~~~~~~~~~

.. code-block:: yaml

   adapters:
     redis:
       backend: "redis"
       enabled: true
       extra_config:
         host: "localhost"            # Redis host
         port: 6379                   # Redis port
         db: 0                        # Database number
         password: null               # Authentication password
         username: null               # Username (Redis 6+)
         socket_timeout: 5.0          # Socket timeout
         socket_connect_timeout: 5.0  # Connection timeout
         socket_keepalive: true       # Enable keepalive
         socket_keepalive_options: {} # Keepalive options
         connection_pool_max_connections: 10
         retry_on_timeout: true       # Retry on timeout
         health_check_interval: 30    # Health check frequency
         decode_responses: true       # Decode responses to strings

**Configuration Options:**

* **host** (str): Redis server hostname
* **port** (int): Redis server port
* **db** (int): Redis database number
* **password** (str): Authentication password
* **socket_timeout** (float): Socket operation timeout
* **connection_pool_max_connections** (int): Max pool connections
* **retry_on_timeout** (bool): Retry operations on timeout

SmartPool Adapter
~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   adapters:
     db_pool:
       backend: "smartpool"
       enabled: true
       extra_config:
         factory_function: "myapp.db.create_connection"
         initial_size: 5              # Initial pool size
         max_size: 20                 # Maximum pool size
         min_size: 2                  # Minimum pool size
         timeout: 30.0                # Acquisition timeout
         idle_timeout: 300            # Idle object timeout
         validation_interval: 60      # Validation frequency
         enable_jmx: false            # Enable JMX monitoring

**Configuration Options:**

* **factory_function** (str): Dotted path to object factory function
* **initial_size** (int): Number of objects created at startup
* **max_size** (int): Maximum number of objects in pool
* **min_size** (int): Minimum number of objects to maintain
* **timeout** (float): Timeout for acquiring objects
* **idle_timeout** (float): Timeout for idle objects

Environment Variables
---------------------

All configuration can be overridden via environment variables:

Variable Naming Pattern
~~~~~~~~~~~~~~~~~~~~~~~

Environment variables follow this pattern:
``OMNI_CACHE_<SECTION>_<KEY>``

.. code-block:: bash

   # Global configuration
   export OMNI_CACHE_GLOBAL_LOG_LEVEL=DEBUG
   export OMNI_CACHE_GLOBAL_DEFAULT_CACHE_ADAPTER=redis
   export OMNI_CACHE_GLOBAL_ENABLE_ROUTING=true

   # Adapter configuration
   export OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_HOST=redis.example.com
   export OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_PORT=6380
   export OMNI_CACHE_ADAPTERS_REDIS_EXTRA_CONFIG_DB=1

Auto-Setup Environment
~~~~~~~~~~~~~~~~~~~~~~

Enable automatic setup on import:

.. code-block:: bash

   export OMNI_CACHE_AUTO_SETUP=true

This automatically configures Omni-Cache when the module is imported.

Programmatic Configuration
--------------------------

Dynamic Configuration
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache import ConfigManager, GlobalConfig

   # Create configuration manager
   config_manager = ConfigManager()

   # Update global configuration
   config_manager.update_global_config({
       "log_level": "DEBUG",
       "enable_routing": True,
       "default_cache_adapter": "redis"
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

Configuration Classes
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from omni_cache.core.config import GlobalConfig, AdapterConfig

   # Global configuration
   global_config = GlobalConfig(
       log_level="INFO",
       enable_routing=True,
       default_cache_adapter="memory"
   )

   # Adapter configuration
   redis_config = AdapterConfig(
       name="redis",
       backend="redis",
       enabled=True,
       extra_config={
           "host": "localhost",
           "port": 6379
       }
   )

Hot Reloading
-------------

Enable configuration hot reloading:

.. code-block:: python

   from omni_cache import ConfigManager

   # Enable hot reload
   config_manager = ConfigManager("config.yaml")
   config_manager.enable_hot_reload()

   # Configuration automatically updates when file changes
   # Adapters are reconfigured as needed

Disable hot reload:

.. code-block:: python

   config_manager.disable_hot_reload()

Configuration Validation
------------------------

Omni-Cache validates configuration at load time:

.. code-block:: python

   try:
       config_manager = ConfigManager("invalid_config.yaml")
   except ConfigurationError as e:
       print(f"Configuration error: {e}")

Custom validation can be added:

.. code-block:: python

   def validate_redis_host(host):
       # Custom validation logic
       if not host or len(host) < 3:
           raise ValueError("Redis host must be at least 3 characters")
       return True

   config_manager.add_validator("adapters.redis.extra_config.host", validate_redis_host)

Routing Configuration
---------------------

Configure intelligent routing rules:

.. code-block:: yaml

   global:
     enable_routing: true

   routing:
     rules:
       - pattern: "cache:*"
         adapter: "memory"
       - pattern: "user:*"
         adapter: "redis"
       - pattern: "session:*"
         adapter: "memory"
     fallback_adapter: "memory"

Programmatic routing:

.. code-block:: python

   # Add routing rules
   manager.add_routing_rule("cache", "memory")
   manager.add_routing_rule("user", "redis")
   manager.add_routing_rule("session", "memory")

   # Set fallback
   manager.set_fallback_adapter("memory")

Configuration Templates
-----------------------

Production Template
~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # production.yaml
   global:
     log_level: "INFO"
     default_cache_adapter: "redis"
     enable_routing: true
     health_check_interval: 30.0
     enable_global_stats: true

   adapters:
     memory:
       backend: "memory"
       enabled: true
       extra_config:
         max_size: 50000
         eviction_policy: "lru"
         cleanup_interval: 300

     redis:
       backend: "redis"
       enabled: true
       extra_config:
         host: "redis-primary.example.com"
         port: 6379
         db: 0
         connection_pool_max_connections: 50
         socket_timeout: 2.0
         retry_on_timeout: true

   routing:
     rules:
       - pattern: "cache:*"
         adapter: "memory"
       - pattern: "user:*"
         adapter: "redis"
     fallback_adapter: "memory"

Development Template
~~~~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # development.yaml
   global:
     log_level: "DEBUG"
     default_cache_adapter: "memory"
     enable_routing: false
     debug_mode: true
     profile_operations: true

   adapters:
     memory:
       backend: "memory"
       enabled: true
       extra_config:
         max_size: 1000
         eviction_policy: "lru"

Testing Template
~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # testing.yaml
   global:
     log_level: "WARNING"
     default_cache_adapter: "memory"
     enable_routing: false
     enable_global_stats: false

   adapters:
     memory:
       backend: "memory"
       enabled: true
       extra_config:
         max_size: 100
         cleanup_interval: 10

Configuration Best Practices
----------------------------

1. **Use appropriate log levels**
   - DEBUG for development
   - INFO for production
   - WARNING for critical systems

2. **Configure appropriate timeouts**
   - Set realistic socket timeouts
   - Configure health check intervals
   - Plan for network latency

3. **Size pools appropriately**
   - Memory: Based on available RAM
   - Redis: Based on concurrent connections
   - SmartPool: Based on resource costs

4. **Enable monitoring in production**
   - Global statistics
   - Health monitoring
   - Performance profiling when needed

5. **Use environment-specific configs**
   - Separate configs for dev/staging/production
   - Override with environment variables
   - Never commit secrets to version control

6. **Plan for scaling**
   - Configure connection pools
   - Set appropriate cache sizes
   - Enable routing for load distribution

Troubleshooting Configuration
-----------------------------

Common Issues
~~~~~~~~~~~~~

**Configuration not loading**
.. code-block:: python

   # Debug configuration loading
   import logging
   logging.getLogger("omni_cache.config").setLevel(logging.DEBUG)
   
   config_manager = ConfigManager("config.yaml")

**Invalid configuration values**
.. code-block:: python

   from omni_cache.core.exceptions import ConfigurationError
   
   try:
       config_manager = ConfigManager("config.yaml")
   except ConfigurationError as e:
       print(f"Configuration error: {e}")
       # Check the error details and fix configuration

**Environment variables not working**

.. code-block:: bash

   # Check if variables are set
   env | grep OMNI_CACHE
   
   # Test variable precedence
   export OMNI_CACHE_GLOBAL_LOG_LEVEL=DEBUG
   python -c "from omni_cache import setup; setup()"

**Hot reload not working**

.. code-block:: python

   # Verify hot reload is enabled
   if config_manager.is_hot_reload_enabled():
       print("Hot reload is active")
   else:
       config_manager.enable_hot_reload()

Next Steps
----------

* Learn about :doc:`routing` for intelligent backend selection
* Explore :doc:`monitoring` for configuration of statistics and health checks
* Check :doc:`../examples/index` for configuration examples
