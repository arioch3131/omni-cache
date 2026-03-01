Examples
========

This section documents the runnable scripts in ``examples/``.

.. toctree::
   :maxdepth: 2
   :caption: Examples:

   basic_examples
   web_applications
   data_processing
   microservices
   custom_adapters
   performance

Quick Start
-----------

Run one script at a time from repository root:

.. code-block:: bash

   python examples/getting_started/basic_usage.py
   python examples/getting_started/basic_memory_adapter.py
   python examples/getting_started/basic_redis_adapter.py
   python examples/getting_started/basic_async_redis_adapter.py
   python examples/getting_started/basic_memcached_adapter.py
   python examples/getting_started/basic_smartpool_adapter.py

Notes
-----

- Some scripts require optional dependencies or local services (Redis, Memcached, SmartPool).
- Scripts are written to degrade gracefully when optional backends are unavailable.
- For the full script list, see ``examples/README.md``.
