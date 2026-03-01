"""
Wrapper classes for objects managed by the SmartPool adapter.

This module contains utility classes used to wrap and manage objects within
the SmartPool. `OmniCachePooledObject` is a dataclass for holding metadata
about a pooled object. `AutoWeakRefWrapper` provides a flexible wrapper
that adds support for weak references and transparently delegates operations
to the underlying object.
"""

import weakref
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")


@dataclass
class OmniCachePooledObject:
    """Wrapper for SmartPool objects with metadata."""

    id: Any
    key: Any
    obj: Any


class AutoWeakRefWrapper(Generic[T]):  # Make it generic
    """
    Enhanced automatic wrapper that handles weak references AND dictionary operations.
    """

    def __init__(self, obj: Any):  # Type obj as T
        self._obj: Any = obj  # Type _obj as T
        self._supports_weakref = self._test_weakref_support(obj)

    @staticmethod
    def _test_weakref_support(obj: Any) -> bool:
        """Test if the object supports weak references."""
        try:
            weakref.ref(obj)
            return True
        except TypeError:
            return False

    def __getattr__(self, name: str) -> Any:
        return getattr(self._obj, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_obj", "_supports_weakref"):
            super().__setattr__(name, value)
        else:
            setattr(self._obj, name, value)

    def __delattr__(self, name: str) -> None:
        delattr(self._obj, name)

    def __str__(self) -> str:
        return str(self._obj)

    def __repr__(self) -> str:
        return repr(self._obj)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._obj(*args, **kwargs)

    def __getitem__(self, key: Any) -> Any:
        """Support for obj[key] if the underlying object supports it."""
        return self._obj[key]

    def __setitem__(self, key: Any, value: Any) -> None:
        """Support for obj[key] = value if the underlying object supports it."""
        self._obj[key] = value

    def __contains__(self, key: Any) -> bool:
        """Support for 'key in obj' if the underlying object supports it."""
        return key in self._obj

    def __len__(self) -> int:
        """Support for len(obj) if the underlying object supports it."""
        return len(self._obj)

    def __enter__(self) -> Any:
        if hasattr(self._obj, "__enter__"):
            return self._obj.__enter__()
        return self._obj

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool | None:
        if hasattr(self._obj, "__exit__"):
            return cast(bool | None, self._obj.__exit__(exc_type, exc_val, exc_tb))
        return None
