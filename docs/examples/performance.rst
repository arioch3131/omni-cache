Performance
===========

These scripts provide benchmarks for cache adapters and pool workloads.

Benchmark Scripts
-----------------

- ``examples/benchmarks/performance_stress_comparison.py``
- ``examples/benchmarks/performance_smartpool_comparison.py``
- ``examples/benchmarks/refactored_adapter_comparison.py``
- ``examples/benchmarks/long_running_performance.py``

Run Benchmarks
--------------

.. code-block:: bash

   python examples/benchmarks/performance_stress_comparison.py
   python examples/benchmarks/performance_smartpool_comparison.py
   python examples/benchmarks/refactored_adapter_comparison.py
   python examples/benchmarks/long_running_performance.py

Backend Notes
-------------

- Redis-backed sections require a Redis server.
- Memcached-backed sections require a Memcached server.
- SmartPool sections require the SmartPool dependency.
- Scripts continue with available adapters when optional backends are missing.
