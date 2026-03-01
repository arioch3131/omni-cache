Architecture
============

This document describes the current Omni-Cache architecture and module boundaries.

High-Level Layers
-----------------

Omni-Cache is split into four main layers:

1. Public API layer (``omni_cache.__init__``)
2. Core orchestration layer (manager, routing, registry, config)
3. Adapter implementations (memory, redis, smartpool, file_cache)
4. Utility layer (decorators)

Core Orchestration
------------------

Main modules:

- ``omni_cache.core.manager``: ``CacheManager`` orchestrates operations
- ``omni_cache.core.adapter_registry``: adapter lifecycle and lookup
- ``omni_cache.core.routing``: namespace-based adapter selection
- ``omni_cache.core.factory_management``: runtime adapter creation
- ``omni_cache.core.config``: configuration loading/merging
- ``omni_cache.core.health_monitoring``: periodic health checks

Interfaces and Contracts
------------------------

Contracts are defined in ``omni_cache.core.interfaces``:

- ``KeyValueInterface`` for cache adapters
- ``PoolInterface`` for object-pool adapters
- ``AdapterInterface`` for shared adapter lifecycle
- ``FactoryInterface`` for adapter factories
- ``ManagerInterface`` for manager behavior

Adapters
--------

Built-in adapters:

- ``omni_cache.adapters.memory``: in-memory cache with TTL and eviction
- ``omni_cache.adapters.redis``: Redis-backed distributed cache
- ``omni_cache.adapters.smartpool``: object pooling integration
- ``omni_cache.adapters.file_cache``: file-based cache example/reference

All adapters share connection/state/stats behavior through
``omni_cache.adapters.base.BaseAdapter`` and its specializations.

Factory System
--------------

Factory components live under ``omni_cache.core.factories``:

- ``FactoryRegistry`` stores available factories
- ``AbstractFactory`` standardizes validation and creation
- ``factory.py`` exposes convenience functions (``create_adapter`` etc.)

Routing and Fallback
--------------------

Routing is key-based and namespace-driven via ``CacheRouter``:

- explicit adapter parameter wins
- otherwise namespace rules are applied
- then default adapter
- optional fallback adapter if target is unavailable

Statistics and Monitoring
-------------------------

- Adapter-level stats come from ``BaseAdapter`` and related dataclasses.
- Manager-level aggregate stats are maintained by ``CacheManager``.
- Health monitoring is managed centrally by ``HealthMonitor``.

Extensibility
-------------

To add a backend:

1. Implement an adapter class against the right interface(s).
2. Implement a factory inheriting ``AbstractFactory``.
3. Register the factory in ``FactoryRegistry``.
4. Add tests (unit + integration) and docs.

Related Docs
------------

- :doc:`custom_adapters`
- :doc:`../adapter_creation`
- :doc:`testing`
- :doc:`../api/index`
