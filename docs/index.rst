.. Omni-Cache documentation master file, created by
   sphinx-quickstart on Thu Aug 31 12:00:00 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Omni-Cache Documentation
========================

**Universal cache and pool manager with pluggable backends**

Omni-Cache is a comprehensive caching and object pooling library that provides a unified interface for multiple backends, intelligent routing, and production-ready features. Whether you need simple function memoization or enterprise-grade distributed caching, Omni-Cache scales with your needs.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   quickstart
   user_guide/index
   api/index
   developer_guide/index
   examples/index

Key Features
============

* **🔌 Multiple Backends**: Memory, Redis, SmartPool, and custom adapters
* **🎯 Unified Interface**: Single API for all cache and pool operations
* **🧠 Intelligent Routing**: Namespace-based routing with automatic fallback
* **📊 Comprehensive Monitoring**: Built-in statistics, health checks, and performance metrics
* **⚙️ Hot-Reloadable Configuration**: YAML, JSON, TOML, and environment variable support
* **🎭 Production-Ready Decorators**: ``@cached``, ``@pooled``, ``@memoize`` with advanced features
* **🔄 Async Support**: Full async/await compatibility
* **🛡️ Type Safety**: Complete type hints and runtime validation
* **📈 Enterprise Features**: Connection pooling, retry logic, circuit breakers

Quick Start
===========

Installation
------------

.. code-block:: bash

   # Basic installation
   pip install omni_cache

   # With Redis support
   pip install omni_cache[redis]

   # With all optional dependencies
   pip install omni_cache[all]

Ultra-Simple Usage
------------------

.. code-block:: python

   from omni_cache import cached

   @cached(ttl=300)  # Cache for 5 minutes
   def expensive_function(x, y):
       # This will only run once per unique (x, y) combination
       return complex_computation(x, y)

   # Use it normally
   result = expensive_function(1, 2)  # Computed and cached
   result = expensive_function(1, 2)  # Retrieved from cache

Available Backends
==================

Built-in Backends
-----------------

* **Memory**: In-memory LRU cache with TTL support (always available)
* **Redis**: Distributed caching with persistence (optional: ``pip install redis``)
* **SmartPool**: Advanced object pooling with adaptive sizing (optional: ``pip install smartpool``)

Custom Backends
---------------

Create your own adapters by implementing the appropriate base classes. See :doc:`developer_guide/custom_adapters` for details.

Getting Help
============

* :doc:`quickstart` - Get up and running quickly
* :doc:`user_guide/index` - Comprehensive user documentation
* :doc:`api/index` - Complete API reference
* :doc:`developer_guide/index` - Extend and implement Omni-Cache internals
* :doc:`examples/index` - Real-world usage examples

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
