"""
SmartPool adapter module for omni-cache.

This module provides integration between SmartObjectManager and omni-cache,
allowing the use of SmartPool's advanced object pooling capabilities
through the standard omni-cache interfaces.

Example usage:

.. code-block:: python

   from omni_cache.adapters.smartpool import SmartPoolAdapter, SmartPoolAdapterConfig

   # Simple factory function
   def create_connection():
       import sqlite3
       return sqlite3.connect(":memory:")

   # Create adapter configuration
   config = SmartPoolAdapterConfig(
       name="db_pool",
       factory_function=create_connection,
       initial_size=5,
       max_size=20,
       memory_preset="HIGH_THROUGHPUT",
       enable_auto_tuning=True,
   )

   # Create and use the adapter
   adapter = SmartPoolAdapter(config)
   adapter.connect()

   # Use as context manager for safe object borrowing
   with adapter.borrow() as conn:
       cursor = conn.cursor()
       cursor.execute("SELECT 1")
       result = cursor.fetchone()

   # Or use get/put pattern
   conn = adapter.get()
   try:
       # Use connection
       pass
   finally:
       adapter.put(conn)

Integration with omni-cache factory system:

.. code-block:: python

   from omni_cache import CacheBackend, create_adapter

   adapter = create_adapter(
       CacheBackend.SMARTPOOL,
       {
           "factory_function": "sqlite3.connect",
           "factory_args": (":memory:",),
           "initial_size": 5,
           "max_size": 20,
           "enable_auto_tuning": True,
       },
   )
"""

from .config import SmartPoolAdapterConfig
from .convenience import create_smartpool_adapter
from .factory_smartpool import SimpleSmartPoolFactory
from .smartpool import (
    SmartPoolAdapter,
)

__all__ = [
    "SmartPoolAdapter",
    "SmartPoolAdapterConfig",
    "SimpleSmartPoolFactory",
    "create_smartpool_adapter",
]

# Version info
__version__ = "1.2.0"
__author__ = "omni-cache team"
__description__ = "SmartPool adapter for omni-cache object pooling"

# Check if SmartPool is available
try:
    from importlib.util import find_spec

    SMARTPOOL_AVAILABLE = find_spec("smartpool.core.smartpool_manager") is not None
except ImportError:
    SMARTPOOL_AVAILABLE = False


def is_available() -> bool:
    """Check if SmartPool dependencies are available."""
    return SMARTPOOL_AVAILABLE


def get_adapter_info() -> dict:
    """Get information about this adapter."""
    return {
        "name": "SmartPool",
        "version": __version__,
        "description": __description__,
        "available": SMARTPOOL_AVAILABLE,
        "interfaces": ["PoolInterface", "AdapterInterface"],
        "backend": "SMARTPOOL",
        "features": [
            "Advanced object pooling",
            "Automatic tuning",
            "Performance metrics",
            "Background cleanup",
            "Multiple memory presets",
            "LRU eviction",
            "Object validation",
            "Pool health monitoring",
        ],
    }
