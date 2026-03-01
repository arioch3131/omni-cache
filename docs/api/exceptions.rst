Exceptions API
==============

This section documents the exception hierarchy and error handling utilities.

Exception Hierarchy
-------------------

Base Exception
~~~~~~~~~~~~~~

.. automodule:: omni_cache.core.exceptions.omni_cache_error
   :members:
   :undoc-members:
   :show-inheritance:

Adapter Exceptions
~~~~~~~~~~~~~~~~~~

Exceptions related to adapter functionality:

.. automodule:: omni_cache.core.exceptions.adapter_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Cache Exceptions
~~~~~~~~~~~~~~~~

Exceptions specific to cache operations:

.. automodule:: omni_cache.core.exceptions.cache_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Pool Exceptions
~~~~~~~~~~~~~~~

Exceptions specific to pool operations:

.. automodule:: omni_cache.core.exceptions.pool_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Configuration Exceptions
~~~~~~~~~~~~~~~~~~~~~~~~

Exceptions related to configuration:

.. automodule:: omni_cache.core.exceptions.config_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Connection Exceptions
~~~~~~~~~~~~~~~~~~~~~

Exceptions related to connections:

.. automodule:: omni_cache.core.exceptions.connection_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Factory Exceptions
~~~~~~~~~~~~~~~~~~

Exceptions related to the factory system:

.. automodule:: omni_cache.core.exceptions.factory_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Operation Exceptions
~~~~~~~~~~~~~~~~~~~~

Exceptions related to general operations:

.. automodule:: omni_cache.core.exceptions.operation_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Serialization Exceptions
~~~~~~~~~~~~~~~~~~~~~~~~

Exceptions related to serialization:

.. automodule:: omni_cache.core.exceptions.serialization_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Other Exceptions
~~~~~~~~~~~~~~~~

Miscellaneous exceptions:

.. automodule:: omni_cache.core.exceptions.other_exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Exception Utilities
-------------------

Utility functions for exception handling:

.. automodule:: omni_cache.core.exceptions.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Main Exception Module
---------------------

The main exceptions module that consolidates all exceptions:

.. automodule:: omni_cache.core.exceptions
   :members:
   :undoc-members:
   :show-inheritance:

Exception Categories
====================

Exceptions are organized into the following categories:

**Core Exceptions**
  - :exc:`~omni_cache.core.exceptions.OmniCacheError` - Base exception for all Omni-Cache errors

**Adapter Exceptions**
  - :exc:`~omni_cache.core.exceptions.AdapterError` - Base for adapter-related errors
  - :exc:`~omni_cache.core.exceptions.AdapterNotFoundError` - Adapter not found
  - :exc:`~omni_cache.core.exceptions.AdapterNotConnectedError` - Adapter not connected
  - :exc:`~omni_cache.core.exceptions.AdapterConnectionError` - Connection failure
  - :exc:`~omni_cache.core.exceptions.AdapterRegistrationError` - Registration failure

**Cache Exceptions**
  - :exc:`~omni_cache.core.exceptions.CacheError` - Base for cache-related errors
  - :exc:`~omni_cache.core.exceptions.CacheKeyError` - Key-related errors
  - :exc:`~omni_cache.core.exceptions.CacheFullError` - Cache full
  - :exc:`~omni_cache.core.exceptions.CacheExpiredError` - Cache expired

**Pool Exceptions**
  - :exc:`~omni_cache.core.exceptions.PoolError` - Base for pool-related errors
  - :exc:`~omni_cache.core.exceptions.PoolEmptyError` - Pool empty
  - :exc:`~omni_cache.core.exceptions.PoolFullError` - Pool full
  - :exc:`~omni_cache.core.exceptions.PoolObjectError` - Pool object errors

**Configuration Exceptions**
  - :exc:`~omni_cache.core.exceptions.ConfigurationError` - Base for configuration errors
  - :exc:`~omni_cache.core.exceptions.InvalidConfigurationError` - Invalid configuration
  - :exc:`~omni_cache.core.exceptions.MissingConfigurationError` - Missing configuration

**Connection Exceptions**
  - :exc:`~omni_cache.core.exceptions.OmniConnectionError` - Base for connection errors
  - :exc:`~omni_cache.core.exceptions.ConnectionTimeoutError` - Connection timeout
  - :exc:`~omni_cache.core.exceptions.ConnectionFailedError` - Connection failed

**Factory Exceptions**
  - :exc:`~omni_cache.core.exceptions.FactoryError` - Base for factory errors
  - :exc:`~omni_cache.core.exceptions.FactoryNotFoundError` - Factory not found
  - :exc:`~omni_cache.core.exceptions.FactoryRegistrationError` - Registration error
  - :exc:`~omni_cache.core.exceptions.FactoryCreationError` - Creation error

**Operation Exceptions**
  - :exc:`~omni_cache.core.exceptions.OperationError` - Base for operation errors
  - :exc:`~omni_cache.core.exceptions.OperationTimeoutError` - Operation timeout
  - :exc:`~omni_cache.core.exceptions.OperationNotSupportedError` - Operation not supported
  - :exc:`~omni_cache.core.exceptions.OperationFailedError` - Operation failed

Exception Handling Best Practices
=================================

When working with Omni-Cache, follow these exception handling patterns:

.. code-block:: python

   from omni_cache import create_adapter, CacheBackend
   from omni_cache.core.exceptions import (
       AdapterNotFoundError,
       AdapterConnectionError,
       CacheError
   )

   try:
       adapter = create_adapter(CacheBackend.REDIS, {"host": "localhost"})
       adapter.connect()
       adapter.set("key", "value")
   except AdapterNotFoundError:
       # Handle missing adapter
       print("Redis adapter not available")
   except AdapterConnectionError:
       # Handle connection issues
       print("Failed to connect to Redis")
   except CacheError as e:
       # Handle cache operation errors
       print(f"Cache operation failed: {e}")
   except Exception as e:
       # Handle unexpected errors
       print(f"Unexpected error: {e}")

Context Managers
================

Use context managers for automatic error handling:

.. code-block:: python

   from omni_cache.core.exceptions import exception_context

   with exception_context("Redis operation"):
       adapter.set("key", "value")
   # Exceptions are automatically logged and re-raised with context
