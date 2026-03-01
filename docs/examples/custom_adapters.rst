Custom Adapters
===============

This section documents practical scripts related to custom adapter usage
and adapter scaffolding.

Relevant Scripts
----------------

- ``examples/getting_started/custom_file_cache_adapter.py``
- ``scripts/new_adapter.py``

Generate a New Adapter Scaffold
-------------------------------

.. code-block:: bash

   python scripts/new_adapter.py my_backend --dependency my-lib

The generator creates:

- ``src/omni_cache/adapters/my_backend/__init__.py``
- ``src/omni_cache/adapters/my_backend/config.py``
- ``src/omni_cache/adapters/my_backend/my_backend.py``
- ``src/omni_cache/adapters/my_backend/factory.py``
- ``tests/unit/adapters/my_backend/test_my_backend_config.py``
- ``tests/unit/adapters/my_backend/test_my_backend_factory.py``
- ``tests/unit/adapters/my_backend/test_my_backend_adapter.py``

Manual Integration Steps
------------------------

1. Export adapter in ``src/omni_cache/adapters/__init__.py``.
2. Register factory in ``src/omni_cache/core/factories/factory_registry.py``.
3. Export factory in ``src/omni_cache/core/factories/__init__.py``.
4. Add dependency and entry point in ``pyproject.toml``.
