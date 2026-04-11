"""
Factory implementation for creating objects within a SmartPool.

This module provides `SimpleSmartPoolFactory`, an enhanced implementation of
SmartPool's `ObjectFactory`. It is responsible for the lifecycle of objects
managed by the pool, including creation, validation, reset, and destruction.
It also supports automatic object wrapping.
"""

import logging
import sys
from collections.abc import Callable
from typing import Any, TypeVar, cast

from smartpool import ObjectFactory

from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper

_T = TypeVar("_T", bound=object)


class SimpleSmartPoolFactory(ObjectFactory):
    """
    Enhanced factory for SmartPool that automatically handles object wrapping
    and provides reset/validation/destroy capabilities.
    """

    # pylint: disable=too-many-positional-arguments
    def __init__(
        self,
        factory_func: Callable[..., _T],
        factory_args: tuple = (),
        factory_kwargs: dict | None = None,
        auto_wrap: bool = True,
        reset_func: Callable[[_T], None] | None = None,
        validate_func: Callable[[_T], bool] | None = None,
        destroy_func: Callable[[_T], None] | None = None,
    ):
        self.factory_func = factory_func
        self.factory_args = factory_args or ()
        self.factory_kwargs = factory_kwargs or {}
        self.auto_wrap = auto_wrap
        self.reset_func = reset_func
        self.validate_func = validate_func
        self.destroy_func = destroy_func
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def create_object(self, *args: Any, **kwargs: Any) -> Any:
        """Create a new object using the factory function."""
        try:
            # Use class args/kwargs by default, but allow override
            final_args = args or self.factory_args
            if kwargs:
                final_kwargs = {**self.factory_kwargs, **kwargs}
            else:
                final_kwargs = self.factory_kwargs
            obj = self.factory_func(*final_args, **final_kwargs)

            # Auto-wrap if requested
            if self.auto_wrap and not isinstance(obj, AutoWeakRefWrapper):
                obj = cast(Any, AutoWeakRefWrapper(obj))

            return obj

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Object creation failed: %s", e)
            raise

    # SmartPool ObjectFactory interface methods
    def create(self, *args: Any, **kwargs: Any) -> Any:
        """ObjectFactory interface: create an object."""
        return self.create_object(*args, **kwargs)

    # pylint: disable=protected-access
    def reset(self, obj: Any) -> bool:
        """ObjectFactory interface: reset an object."""
        if self.reset_func:
            try:
                # Unwrap if needed
                real_obj = obj._obj if hasattr(obj, "_obj") else obj
                self.reset_func(real_obj)
                return True
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.warning("Object reset failed: %s", e)
                return False
        return True

    def validate(self, obj: Any) -> bool:
        """ObjectFactory interface: validate an object."""
        if self.validate_func:
            try:
                # Unwrap if needed
                real_obj = obj._obj if hasattr(obj, "_obj") else obj
                return self.validate_func(real_obj)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.warning("Object validation failed: %s", e)
                return False
        return True

    # pylint: disable=protected-access
    def destroy(self, obj: Any) -> None:
        """ObjectFactory interface: destroy an object."""
        if self.destroy_func:
            try:
                # Unwrap if needed
                real_obj = obj._obj if hasattr(obj, "_obj") else obj
                self.destroy_func(real_obj)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.warning("Object destruction failed: %s", e)

    def get_key(self, *args: Any, **kwargs: Any) -> str:
        """
        Generates a unique key based on the arguments used to create an object.
        """
        effective_args = args or self.factory_args
        if kwargs:
            effective_kwargs = {**self.factory_kwargs, **kwargs} if self.factory_kwargs else kwargs
        else:
            effective_kwargs = self.factory_kwargs

        if not effective_args and not effective_kwargs:
            return "default_pool_key"

        # Fast path: dominant borrow case with a single key argument and no kwargs.
        if len(effective_args) == 1 and not effective_kwargs:
            return str(effective_args[0])

        key_parts = [str(arg) for arg in effective_args]
        if effective_kwargs:
            key_parts.extend(f"{key}={value}" for key, value in sorted(effective_kwargs.items()))

        return "_".join(key_parts)

    # pylint: disable=protected-access
    def estimate_size(self, obj: Any) -> int:
        """
        ObjectFactory interface: estimate object size.

        Returns an estimate of the object's memory footprint.
        """
        try:
            real_obj = obj._obj if hasattr(obj, "_obj") else obj
            return sys.getsizeof(real_obj)
        except Exception:  # pylint: disable=broad-exception-caught
            return 1024  # Default estimate: 1KB
