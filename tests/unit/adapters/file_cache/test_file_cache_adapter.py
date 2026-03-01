"""
Tests for the FileCacheAdapter.
"""

import os
import time
from unittest.mock import patch

import pytest

from omni_cache.adapters.file_cache.file_cache import (
    FileCacheAdapter,
    FileCacheConfig,
    create_file_cache_adapter,
)

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture
def file_cache_adapter(tmp_path):
    """Returns a FileCacheAdapter instance with a temporary cache directory."""
    cache_dir = str(tmp_path / "test_cache")
    adapter = FileCacheAdapter(FileCacheConfig(cache_dir=cache_dir))
    adapter.connect()
    yield adapter
    adapter.disconnect()


class TestFileCacheAdapterInitialization:
    """Tests for FileCacheAdapter initialization and configuration."""

    def test_initialization_with_dict_config(self, tmp_path):
        """Test adapter initialization with a dictionary config."""
        cache_dir = str(tmp_path / "test_cache")
        config = {"cache_dir": cache_dir}
        adapter = FileCacheAdapter(config)
        assert adapter._config.cache_dir == cache_dir

    def test_initialization_without_config(self):
        """Test adapter initialization without config."""
        adapter = FileCacheAdapter()
        assert adapter._config is not None


class TestFileCacheAdapterConnection:
    """Tests for FileCacheAdapter connection and health check."""

    def test_connect_creates_directory(self, tmp_path):
        """Test that connect creates the cache directory."""
        cache_dir = str(tmp_path / "test_cache")
        adapter = FileCacheAdapter(FileCacheConfig(cache_dir=cache_dir))
        assert not os.path.exists(cache_dir)
        adapter.connect()
        assert os.path.exists(cache_dir)

    def test_connect_creates_directory_failed(self, tmp_path):
        """Test that connect creates the cache directory."""
        with patch("os.makedirs", side_effect=OSError("Directory Not Found")):
            cache_dir = str(tmp_path / "test_cache")
            adapter = FileCacheAdapter(FileCacheConfig(cache_dir=cache_dir))
            assert adapter.connect() is False

    def test_health_check(self, file_cache_adapter):
        """Test the health check."""
        assert file_cache_adapter.health_check() is True

    def test_health_check_failed(self, file_cache_adapter):
        """Test the health check failed."""
        with patch("builtins.open", side_effect=OSError("Open Error")):
            assert file_cache_adapter.health_check() is False


class TestFileCacheAdapterBasicOperations:
    """Tests for basic CRUD operations (set, get, delete)."""

    def test_set_and_get(self, file_cache_adapter):
        """Test setting and getting a value."""
        assert file_cache_adapter.set("key1", "value1") is True
        assert file_cache_adapter.get("key1") == "value1"

    def test_get_nonexistent_key(self, file_cache_adapter):
        """Test getting a nonexistent key."""
        assert file_cache_adapter.get("nonexistent") is None

    def test_delete(self, file_cache_adapter):
        """Test deleting a key."""
        file_cache_adapter.set("key1", "value1")
        assert file_cache_adapter.delete("key1") is True
        assert file_cache_adapter.get("key1") is None

    def test_delete_nonexistent_key(self, file_cache_adapter):
        """Test deleting a nonexistent key."""
        assert file_cache_adapter.delete("nonexistent") is False


class TestFileCacheAdapterAdvancedOperations:
    """Tests for advanced operations (clear, TTL)."""

    def test_clear(self, file_cache_adapter):
        """Test clearing the cache."""
        file_cache_adapter.set("key1", "value1")
        file_cache_adapter.set("key2", "value2")
        assert file_cache_adapter.clear() is True
        assert file_cache_adapter.get("key1") is None
        assert file_cache_adapter.get("key2") is None

    def test_clear_dir_not_found(self, file_cache_adapter):
        """Test clear with cache dir not found"""
        with patch("os.path.exists", return_value=False):
            file_cache_adapter.set("key1", "value1")
            file_cache_adapter.set("key2", "value2")
            assert file_cache_adapter.clear() is True

    def test_clear_impossible_to_remove_dir(self, file_cache_adapter):
        """Test clear with remove dir failed"""
        with patch("shutil.rmtree", side_effect=OSError("Impossible to remove tree")):
            file_cache_adapter.set("key1", "value1")
            file_cache_adapter.set("key2", "value2")
            assert file_cache_adapter.clear() is False

    def test_ttl(self, file_cache_adapter):
        """Test TTL functionality."""
        assert file_cache_adapter.set("key1", "value1", ttl=1) is True
        assert file_cache_adapter.get("key1") == "value1"
        time.sleep(1.1)
        assert file_cache_adapter.get("key1") is None


class TestFileCacheAdapterErrorHandling:
    """Tests for error handling scenarios."""

    def test_delete_removing_file_fails(self, file_cache_adapter):
        """Test deleting a key."""
        file_cache_adapter.set("key1", "value1")
        with patch("os.remove", side_effect=OSError("File not found")):
            assert file_cache_adapter.delete("key1") is False

    def test_set_with_invalid_serialization(self, file_cache_adapter):
        """Test that set handles values that cannot be serialized to JSON."""

        class Unserializable:
            """Definition of a class Unserializable."""

        assert file_cache_adapter.set("key1", Unserializable()) is False

    def test_set_with_path_error(self, file_cache_adapter):
        """Test with a open file error."""
        with patch("builtins.open", side_effect=OSError("Open Error")):
            assert file_cache_adapter.set("key1", "value") is False

    def test_get_with_corrupted_file(self, file_cache_adapter):
        """Test that get handles corrupted (invalid JSON) files."""
        file_path = file_cache_adapter._get_file_path("key1")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("this is not json")
        assert file_cache_adapter.get("key1") is None


class TestFileCacheAdapterFactory:
    """Tests for the factory function."""

    def test_create_file_cache_adapter(self, tmp_path):
        """Test the function to create a file cache adapter"""
        cache_dir = str(tmp_path / "test_cache")
        file_cache_adapter = create_file_cache_adapter({"cache_dir": cache_dir})
        assert file_cache_adapter is not None
        assert isinstance(file_cache_adapter, FileCacheAdapter)
