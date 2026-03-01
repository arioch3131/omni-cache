# Custom Adapter Development Guide

## Overview

This guide defines the exact requirements and specifications for developing custom adapters within the Omni-Cache framework, based on the actual codebase.

## Prerequisites

- Python 3.8+
- Understanding of abstract base classes and interfaces
- Familiarity with Omni-Cache core concepts

## Architecture Overview

### Component Hierarchy

```
┌─────────────────────────────────────┐
│            Client Code              │
├─────────────────────────────────────┤
│         Omni-Cache Manager          │
├─────────────────────────────────────┤
│       Factory Registry              │
├─────────────────────────────────────┤
│       Adapter Interface             │
├─────────────────────────────────────┤
│       Custom Adapter                │
├─────────────────────────────────────┤
│       Backend Storage               │
└─────────────────────────────────────┘
```

### Core Interfaces

- **`AdapterInterface`**: Defines the contract for all adapters
- **`AbstractFactory`**: Responsible for adapter instantiation and metadata
- **`AdapterConfig`**: Encapsulates adapter-specific configuration
- **`FactoryRegistry`**: Manages adapter factories and enables discovery

## Architecture Requirements

### 1. Backend Type Registration

Register your adapter in the backend enumeration:

```python
# File: src/omni_cache/core/interfaces/enum_dataclasses.py
class CacheBackend(Enum):
    YOUR_BACKEND = "your_backend_name"
```

### 2. Configuration Class

Define a configuration class inheriting from `AdapterConfig`:

```python
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
```

### 3. Adapter Implementation

#### Required Base Classes

- **For Cache**: Inherit from `BaseCacheAdapter`
- **For Pool**: Inherit from `BasePoolAdapter` 
- **Both inherit from**: `BaseAdapter` → `AdapterInterface` + `StatisticsInterface` + `Configurable`

#### Mandatory Abstract Methods

All adapters MUST implement these methods:

```python
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
```

#### Cache Adapter Specific Methods

For `BaseCacheAdapter`, you must also implement:

```python
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
```

#### Pool Adapter Specific Methods

For `BasePoolAdapter`, implement pool-specific operations (check actual interface for exact signatures).

### 4. Factory Implementation

Create a factory class:

```python
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
```

## Integration Steps

### 1. Factory Registration

Add to factory registry:

```python
# File: src/omni_cache/core/factories/__init__.py
# Add your import
from your_package.factory import YourAdapterFactory

# Add to __all__
__all__ = [
    # ... existing items
    "YourAdapterFactory",
]
```

And register in the built-in factories:

```python
# File: src/omni_cache/core/factories/factory_registry.py
# Import and register in _register_builtin_factories()
```

### 2. Adapter Exposure

Add to adapter module:

```python
# File: src/omni_cache/adapters/__init__.py
from .your_adapter import YourAdapter, YourAdapterConfig

# Add to discovery functions
def list_available_adapters():
    adapters = {
        # ... existing
        "your_backend": YourAdapter,
    }
    return adapters
```

## Implementation Guidelines

### Required Patterns

1. **Always use `_safe_operation()`** for all public methods
2. **Always call `_update_cache_stats()`** or `_update_pool_stats()`
3. **Implement internal `_*_internal()` methods** for actual logic
4. **Handle configuration in `__init__()`** with proper type conversion

### Error Handling

Use framework exceptions:
```python
from omni_cache.core.exceptions import (
    AdapterNotConnectedError,
    FactoryCreationError,
    InvalidConfigurationError
)
```

### Thread Safety

- Use `self._logger` for logging
- Implement proper locking if needed
- Test concurrent operations

### Statistics

- Cache adapters: Use `_update_cache_stats(operation, success=True)`
- Pool adapters: Use `_update_pool_stats(operation, **kwargs)`

## Testing Requirements

Test these aspects:
- Connection lifecycle (`connect`/`disconnect`)
- All operations (`set`/`get`/`delete`/`clear`)
- Error conditions and exceptions
- Configuration validation
- Thread safety if claimed
- Factory creation and metadata

## Usage Example

```python
from omni_cache import setup, create_adapter
from omni_cache.core.interfaces import CacheBackend

manager = setup()
adapter = create_adapter(
    CacheBackend.YOUR_BACKEND,
    {"parameter1": "value", "parameter2": 200}
)
manager.register_adapter("my_adapter", adapter)
```

## Compliance Checklist

- [ ] Inherits from `BaseCacheAdapter` or `BasePoolAdapter`
- [ ] Implements all abstract methods (`_do_connect`, `_do_disconnect`, `_do_health_check`)
- [ ] Uses `_safe_operation()` wrapper for public methods
- [ ] Calls `_update_cache_stats()` or `_update_pool_stats()`
- [ ] Provides `FactoryMetadata` with correct structure
- [ ] Handles configuration properly in `__init__()`
- [ ] Registers in factory registry
- [ ] Includes comprehensive tests
- [ ] Validates configuration parameters
- [ ] Documents all configuration options