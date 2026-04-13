Migration: file_cache to disk
=============================

Starting with version ``2.0.0`` (released on April 13, 2026), the legacy
``file_cache`` backend was removed and replaced by the ``disk`` backend.

What changed
------------

* ``CacheBackend.FILE_CACHE`` no longer exists.
* The supported persistent local backend is now ``CacheBackend.DISK`` / ``"disk"``.
* The new backend stores payloads as binary files and keeps metadata in SQLite.

Code migration
--------------

Before:

.. code-block:: python

   adapter = create_adapter("file_cache", {"cache_dir": "./cache"})

After:

.. code-block:: python

   from omni_cache import CacheBackend, create_adapter

   adapter = create_adapter(
       CacheBackend.DISK,
       {
           "cache_dir": "./cache",
           "default_ttl": 3600,
           "renew_on_hit": False,
       },
   )

Operational notes
-----------------

* If you had old ``file_cache`` data, plan a one-time warm-up/migration step.
* ``disk`` includes periodic cleanup and a manual ``cleanup()`` method.
* Disk-specific metrics are exposed through ``get_backend_info()`` under
  ``disk_metrics``.
