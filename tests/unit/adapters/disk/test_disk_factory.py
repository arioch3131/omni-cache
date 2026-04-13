"""Unit tests for disk adapter factory."""

from omni_cache.adapters.disk import DiskAdapter
from omni_cache.adapters.disk.factory import DiskAdapterFactory
from omni_cache.core.factories import create_adapter
from omni_cache.core.interfaces import CacheBackend


def test_disk_factory_metadata():
    factory = DiskAdapterFactory()
    metadata = factory.get_metadata()

    assert metadata.backend == CacheBackend.DISK.value
    assert metadata.factory_class == "DiskAdapterFactory"
    assert metadata.version == "2.0.0"


def test_disk_factory_create(tmp_path):
    factory = DiskAdapterFactory()
    adapter = factory.create({"cache_dir": str(tmp_path / "disk_cache")})

    assert isinstance(adapter, DiskAdapter)
    assert adapter.connect() is True
    assert adapter.set("a", 1) is True
    assert adapter.get("a") == 1
    adapter.disconnect()


def test_disk_creation_paths_enum_and_string(tmp_path):
    enum_adapter = create_adapter(
        CacheBackend.DISK,
        {"cache_dir": str(tmp_path / "enum_disk")},
    )
    string_adapter = create_adapter(
        "disk",
        {"cache_dir": str(tmp_path / "string_disk")},
    )

    assert isinstance(enum_adapter, DiskAdapter)
    assert isinstance(string_adapter, DiskAdapter)
