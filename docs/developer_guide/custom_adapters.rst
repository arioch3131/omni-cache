Custom Adapters
===============

This guide explains how to create custom adapters to extend Omni-Cache with new backend types.

Overview
--------

A custom adapter allows you to integrate Omni-Cache with any storage system or resource management system that is not natively supported. This gives you complete flexibility to adapt Omni-Cache to your specific needs.

Prerequisites
-------------

* Python 3.8+
* Understanding of abstract base classes and interfaces
* Familiarity with Omni-Cache core concepts

Architecture Requirements
-------------------------

Backend Type Registration
~~~~~~~~~~~~~~~~~~~~~~~~~

First, register your adapter in the backend enumeration:

.. code-block:: python

   # File: src/omni_cache/core/interfaces/enum_dataclasses.py
   class CacheBackend(Enum):
       YOUR_BACKEND = "your_backend_name"

Configuration Class
~~~~~~~~~~~~~~~~~~~

Define a configuration class inheriting from ``AdapterConfig``:

.. code-block:: python

   from dataclasses import dataclass
   from omni_cache.adapters.base import AdapterConfig

   @dataclass
   class YourAdapterConfig(AdapterConfig):
       # Define your configuration parameters
       parameter1: str = "default_value"
       parameter2: int = 100
       
       def __post_init__(self):
           super().__post_init__()
           # Add validation logic if needed

Adapter Implementation
----------------------

Base Classes
~~~~~~~~~~~~

Choose the appropriate base class:

* **For Cache**: Inherit from ``BaseCacheAdapter``
* **For Pool**: Inherit from ``BasePoolAdapter``

Both inherit from: ``BaseAdapter`` → ``AdapterInterface`` + ``StatisticsInterface`` + ``Configurable``

Mandatory Methods
~~~~~~~~~~~~~~~~~

All adapters MUST implement these abstract methods:

.. code-block:: python

   from omni_cache.adapters.base import BaseCacheAdapter

   class YourAdapter(BaseCacheAdapter):
       def __init__(self, config: Optional[Union[Dict, YourAdapterConfig]] = None):
           # Handle config conversion and call super().__init__()
           if isinstance(config, dict):
               config = YourAdapterConfig(**config)
           elif config is None:
               config = YourAdapterConfig()
           super().__init__(config)
       
       def _do_connect(self) -> bool:
           """Implement actual connection logic."""
           # Your connection code here
           return True  # or False if failed
       
       def _do_disconnect(self) -> bool:
           """Implement actual disconnection logic."""
           # Your disconnection code here
           return True  # or False if failed
       
       def _do_health_check(self) -> bool:
           """Implement health check logic."""
           # Your health check code here
           return True  # or False if unhealthy

Cache Adapter Methods
~~~~~~~~~~~~~~~~~~~~~

For ``BaseCacheAdapter``, implement these methods:

.. code-block:: python

   def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
       return self._safe_operation(
           lambda: self._set_internal(key, value, ttl), 
           "set", 
           default=False
       )

   def get(self, key: str) -> Any:
       return self._safe_operation(
           lambda: self._get_internal(key), 
           "get", 
           default=None
       )

   def delete(self, key: str) -> bool:
       return self._safe_operation(
           lambda: self._delete_internal(key), 
           "delete", 
           default=False
       )

   def clear(self) -> bool:
       return self._safe_operation(
           self._clear_internal, 
           "clear", 
           default=False
       )

   # Private implementation methods
   def _set_internal(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
       # Your set implementation
       self._update_cache_stats("set")  # Track statistics
       return True

   def _get_internal(self, key: str) -> Any:
       # Your get implementation
       self._update_cache_stats("get", success=True/False)  # Track statistics
       return value

   def _delete_internal(self, key: str) -> bool:
       # Your delete implementation
       self._update_cache_stats("delete")  # Track statistics
       return True

   def _clear_internal(self) -> bool:
       # Your clear implementation
       self._update_cache_stats("clear")  # Track statistics
       return True

Factory Implementation
----------------------

Create a factory class for your adapter:

.. code-block:: python

   from omni_cache.core.factories.abstract_factory import AbstractFactory
   from omni_cache.core.factories.factory_metadata import FactoryMetadata
   from omni_cache.core.interfaces import CacheBackend

   class YourAdapterFactory(AbstractFactory):
       def _get_default_metadata(self) -> FactoryMetadata:
           return FactoryMetadata(
               backend=CacheBackend.YOUR_BACKEND.value,  # String value, not enum
               factory_class=self.__class__.__name__,
               adapter_types=[YourAdapter.__name__],  # List of strings
               description="Your adapter description",
               dependencies=["optional-dependency"],  # List of module names
               config_schema={
                   "type": "object",
                   "properties": {
                       "parameter1": {"type": "string", "default": "default_value"},
                       "parameter2": {"type": "integer", "default": 100},
                   },
                   "required": ["parameter1"],
               },
               version="1.0.0"
           )
       
       def _create_adapter(self, config: Dict[str, Any]) -> YourAdapter:
           """Create adapter instance."""
           try:
               return YourAdapter(config)
           except Exception as e:
               raise FactoryCreationError(
                   self._metadata.backend, config, e
               ) from e
       
       def _setup_config_validators(self) -> None:
           """Optional: Add custom validators."""
           # Example custom validator
           def validate_parameter2(value: int) -> bool:
               return isinstance(value, int) and value > 0
           
           self.add_config_validator("parameter2", validate_parameter2)

Complete Example: File Cache Adapter
------------------------------------

Here's a complete example implementing a file-based cache:

.. code-block:: python

   # src/omni_cache/adapters/file_cache/file_cache.py
   import os
   import json
   import shutil
   import time
   from typing import Any, Dict, Optional, Union
   from dataclasses import dataclass

   from omni_cache.adapters.base import BaseCacheAdapter, AdapterConfig
   from omni_cache.core.exceptions import CacheError

   @dataclass
   class FileCacheConfig(AdapterConfig):
       """Configuration for the FileCache adapter."""
       cache_dir: str = "omni_cache_files"
       
       def __post_init__(self):
           super().__post_init__()
           # Validation
           if not self.cache_dir:
               raise ValueError("cache_dir cannot be empty")

   class FileCacheAdapter(BaseCacheAdapter):
       """File-system based cache adapter."""
       
       def __init__(self, config: Optional[Union[Dict[str, Any], FileCacheConfig]] = None):
           if isinstance(config, dict):
               config = FileCacheConfig(**config)
           elif config is None:
               config = FileCacheConfig()
           
           super().__init__(config)
           self._cache_dir = self._config.cache_dir
           
       def _get_file_path(self, key: str) -> str:
           """Get file path for a key."""
           safe_key = key.replace("/", "_").replace("\\\\", "_")
           return os.path.join(self._cache_dir, f"{safe_key}.json")
           
       def _do_connect(self) -> bool:
           """Create cache directory."""
           try:
               os.makedirs(self._cache_dir, exist_ok=True)
               return True
           except Exception as e:
               self._logger.error(f"Failed to create cache directory: {e}")
               return False
               
       def _do_disconnect(self) -> bool:
           """No cleanup needed for file cache."""
           return True
           
       def _do_health_check(self) -> bool:
           """Check if directory is writable."""
           try:
               test_file = os.path.join(self._cache_dir, ".health_check")
               with open(test_file, "w") as f:
                   f.write("test")
               os.remove(test_file)
               return True
           except Exception:
               return False
               
       def _set_internal(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
           """Store value in file."""
           try:
               file_path = self._get_file_path(key)
               expiration = (time.time() + ttl) if ttl else None
               
               data = {
                   "value": value,
                   "expiration": expiration,
                   "created": time.time()
               }
               
               with open(file_path, "w") as f:
                   json.dump(data, f)
                   
               self._update_cache_stats("set")
               return True
           except Exception as e:
               self._logger.error(f"Failed to set {key}: {e}")
               return False
               
       def _get_internal(self, key: str) -> Any:
           """Retrieve value from file."""
           try:
               file_path = self._get_file_path(key)
               
               if not os.path.exists(file_path):
                   self._update_cache_stats("get", success=False)
                   return None
                   
               with open(file_path, "r") as f:
                   data = json.load(f)
                   
               # Check expiration
               if data.get("expiration") and time.time() > data["expiration"]:
                   os.remove(file_path)
                   self._update_cache_stats("get", success=False)
                   return None
                   
               self._update_cache_stats("get", success=True)
               return data["value"]
           except Exception as e:
               self._logger.error(f"Failed to get {key}: {e}")
               self._update_cache_stats("get", success=False)
               return None
               
       def _delete_internal(self, key: str) -> bool:
           """Delete file."""
           try:
               file_path = self._get_file_path(key)
               if os.path.exists(file_path):
                   os.remove(file_path)
                   self._update_cache_stats("delete")
                   return True
               return False
           except Exception as e:
               self._logger.error(f"Failed to delete {key}: {e}")
               return False
               
       def _clear_internal(self) -> bool:
           """Remove all cache files."""
           try:
               if os.path.exists(self._cache_dir):
                   shutil.rmtree(self._cache_dir)
                   os.makedirs(self._cache_dir, exist_ok=True)
               self._update_cache_stats("clear")
               return True
           except Exception as e:
               self._logger.error(f"Failed to clear cache: {e}")
               return False

Factory for File Cache
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # src/omni_cache/adapters/file_cache/factory.py
   from typing import Any, Dict
   from omni_cache.core.interfaces import CacheBackend
   from omni_cache.core.factories.abstract_factory import AbstractFactory
   from omni_cache.core.factories.factory_metadata import FactoryMetadata
   from omni_cache.core.exceptions import FactoryCreationError
   from .file_cache import FileCacheAdapter, FileCacheConfig

   class FileCacheFactory(AbstractFactory):
       """Factory for creating FileCacheAdapter instances."""

       def _get_default_metadata(self) -> FactoryMetadata:
           return FactoryMetadata(
               backend=CacheBackend.YOUR_BACKEND.value,
               factory_class=self.__class__.__name__,
               adapter_types=[FileCacheAdapter.__name__],
               description="File-system based cache adapter",
               dependencies=[],
               config_schema={
                   "type": "object",
                   "properties": {
                       "name": {"type": "string", "default": "file_cache"},
                       "cache_dir": {"type": "string", "default": "omni_cache_files"},
                       "log_level": {"type": "string", "default": "INFO"},
                       "enable_stats": {"type": "boolean", "default": True},
                   },
                   "required": ["cache_dir"],
               },
               version="1.0.0"
           )

       def _create_adapter(self, config: Dict[str, Any]) -> FileCacheAdapter:
           """Create FileCacheAdapter instance."""
           try:
               return FileCacheAdapter(FileCacheConfig(**config))
           except Exception as e:
               raise FactoryCreationError(
                   self._metadata.backend, config, e
               ) from e

       def _setup_config_validators(self) -> None:
           """Setup custom validators."""
           def validate_cache_dir(value: str) -> bool:
               return isinstance(value, str) and len(value) > 0
               
           self.add_config_validator("cache_dir", validate_cache_dir)

Integration Steps
-----------------

1. Register Factory
~~~~~~~~~~~~~~~~~~~

Add your factory to the registry:

.. code-block:: python

   # File: src/omni_cache/core/factories/__init__.py
   from .file_cache.factory import FileCacheFactory

   # Add to __all__
   __all__ = [
       # ... existing items
       "FileCacheFactory",
   ]

2. Register in Built-in Factories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # File: src/omni_cache/core/factories/factory_registry.py
   from omni_cache.adapters.file_cache.factory import FileCacheFactory

   class FactoryRegistry:
       def _register_builtin_factories(self) -> None:
           """Register built-in factories."""
           try:
               self.register(MemoryAdapterFactory())
               self.register(FileCacheFactory())  # Add this line
               # ... other factories
           except Exception as e:
               self._logger.warning(f"Error registering built-in factories: {e}")

3. Expose Adapter
~~~~~~~~~~~~~~~~~

Make your adapter discoverable:

.. code-block:: python

   # File: src/omni_cache/adapters/__init__.py
   from .file_cache import FileCacheAdapter, FileCacheConfig

   # Add to __all__
   __all__ = [
       # ... existing items
       "FileCacheAdapter",
       "FileCacheConfig",
   ]

Testing Your Adapter
--------------------

Create comprehensive tests:

.. code-block:: python

   # tests/unit/adapters/file_cache/test_file_cache.py
   import pytest
   import tempfile
   import shutil
   from omni_cache.adapters.file_cache import FileCacheAdapter, FileCacheConfig

   class TestFileCacheAdapter:
       def test_basic_operations(self):
           """Test basic cache operations."""
           with tempfile.TemporaryDirectory() as temp_dir:
               config = FileCacheConfig(cache_dir=temp_dir)
               adapter = FileCacheAdapter(config)
               
               assert adapter.connect()
               
               # Test set/get
               assert adapter.set("key1", "value1")
               assert adapter.get("key1") == "value1"
               
               # Test delete
               assert adapter.delete("key1")
               assert adapter.get("key1") is None
               
               # Test clear
               adapter.set("key2", "value2")
               assert adapter.clear()
               assert adapter.get("key2") is None
               
               adapter.disconnect()

       def test_ttl_expiration(self):
           """Test TTL functionality."""
           with tempfile.TemporaryDirectory() as temp_dir:
               adapter = FileCacheAdapter(FileCacheConfig(cache_dir=temp_dir))
               adapter.connect()
               
               # Set with short TTL
               adapter.set("temp_key", "temp_value", ttl=1)
               assert adapter.get("temp_key") == "temp_value"
               
               # Wait for expiration
               import time
               time.sleep(1.1)
               assert adapter.get("temp_key") is None
               
               adapter.disconnect()

Usage Example
~~~~~~~~~~~~~

Once implemented, use your custom adapter:

.. code-block:: python

   from omni_cache import setup, create_adapter
   from omni_cache.core.interfaces import CacheBackend

   # Create and register your custom adapter
   manager = setup()
   
   file_adapter = create_adapter(
       CacheBackend.YOUR_BACKEND,
       {"cache_dir": "/tmp/my_cache"}
   )
   
   manager.register_adapter("custom_cache", file_adapter)

   # Use with decorators
   from omni_cache import cached

   @cached(ttl=300, adapter="custom_cache")
   def expensive_function(x):
       return complex_computation(x)

Best Practices
--------------

1. **Error Handling**
   - Always use ``_safe_operation()`` wrapper
   - Log errors appropriately
   - Return appropriate defaults

2. **Statistics Tracking**
   - Always call ``_update_cache_stats()`` or ``_update_pool_stats()``
   - Track both successful and failed operations

3. **Configuration Validation**
   - Validate configuration in ``__post_init__()``
   - Provide sensible defaults
   - Use type hints

4. **Thread Safety**
   - Ensure your implementation is thread-safe
   - Use appropriate locking if needed
   - Test concurrent access

5. **Resource Management**
   - Properly implement ``_do_connect()`` and ``_do_disconnect()``
   - Clean up resources in disconnect
   - Handle connection failures gracefully

6. **Testing**
   - Test all operations (set, get, delete, clear)
   - Test error conditions
   - Test concurrent access
   - Test configuration validation

Compliance Checklist
--------------------

- [ ] Inherits from ``BaseCacheAdapter`` or ``BasePoolAdapter``
- [ ] Implements all abstract methods
- [ ] Uses ``_safe_operation()`` wrapper for public methods
- [ ] Calls ``_update_cache_stats()`` or ``_update_pool_stats()``
- [ ] Provides ``FactoryMetadata`` with correct structure
- [ ] Handles configuration properly in ``__init__()``
- [ ] Registers in factory registry
- [ ] Includes comprehensive tests
- [ ] Validates configuration parameters
- [ ] Documents all configuration options
- [ ] Thread-safe implementation
- [ ] Proper error handling and logging