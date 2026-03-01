"""Tests for import-time fallback behavior in Memcached modules."""

import builtins
import importlib
import sys
from unittest.mock import patch

_ORIGINAL_IMPORT = builtins.__import__


def _import_blocking_pymemcache(name, globals_=None, locals_=None, fromlist=(), level=0):
    if name.startswith("pymemcache"):
        raise ImportError("blocked for test")
    return _ORIGINAL_IMPORT(name, globals_, locals_, fromlist, level)


def test_package_init_fallback_when_pymemcache_missing():
    sys.modules.pop("omni_cache.adapters.memcached", None)

    with patch.object(builtins, "__import__", side_effect=_import_blocking_pymemcache):
        module = importlib.import_module("omni_cache.adapters.memcached")
        assert module.HAS_MEMCACHED is False
        assert module.Client.__name__ == "Client"

    importlib.reload(module)


def test_adapter_module_fallback_when_pymemcache_missing():
    import omni_cache.adapters.memcached.memcached as memcached_module

    with patch.object(builtins, "__import__", side_effect=_import_blocking_pymemcache):
        module = importlib.reload(memcached_module)
        assert module.HAS_MEMCACHED is False
        assert module.Client.__name__ == "Client"

    importlib.reload(module)
