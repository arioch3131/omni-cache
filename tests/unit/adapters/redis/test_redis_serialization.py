"""
Tests for Redis adapter serialization and key operations.

This module tests the serialization/deserialization functionality
and key management operations of the RedisAdapter.
"""

import pytest

# Test Redis availability
try:
    from omni_cache.adapters.redis import RedisAdapter, RedisAdapterConfig

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisAdapter = None
    RedisAdapterConfig = None

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name


# Au niveau du module, pas dans la fonction
class SerializableTestClass:
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __eq__(self, other):
        return (
            isinstance(other, SerializableTestClass)
            and self.name == other.name
            and self.value == other.value
        )


class TestRedisAdapterSerialization:
    """Tests for Redis adapter serialization methods."""

    @pytest.fixture
    def adapter(self):
        """Create RedisAdapter instance for testing."""
        if not HAS_REDIS:
            pytest.skip("Redis not available")
        return RedisAdapter(RedisAdapterConfig())

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_json_serialization_simple_types(self, adapter):
        """Test JSON serialization with simple data types."""
        # String
        result = adapter._serialize_json("hello")
        assert result == '"hello"'
        assert adapter._deserialize_json(result) == "hello"

        # Integer
        result = adapter._serialize_json(42)
        assert result == "42"
        assert adapter._deserialize_json(result) == 42

        # Float
        result = adapter._serialize_json(3.14)
        assert result == "3.14"
        assert adapter._deserialize_json(result) == 3.14

        # Boolean
        result = adapter._serialize_json(True)
        assert result == "true"
        assert adapter._deserialize_json(result) is True

        # None
        result = adapter._serialize_json(None)
        assert result == "null"
        assert adapter._deserialize_json(result) is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_json_serialization_complex_types(self, adapter):
        """Test JSON serialization with complex data types."""
        # List
        data = [1, 2, "three", True, None]
        result = adapter._serialize_json(data)
        assert adapter._deserialize_json(result) == data

        # Dictionary
        data = {"key": "value", "number": 42, "nested": {"inner": "data"}}
        result = adapter._serialize_json(data)
        assert adapter._deserialize_json(result) == data

        # Nested structures
        data = {
            "users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}],
            "metadata": {"version": "1.0", "active": True},
        }
        result = adapter._serialize_json(data)
        assert adapter._deserialize_json(result) == data

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_json_serialization_with_default_str(self, adapter):
        """Test JSON serialization with default=str for non-serializable objects."""
        from datetime import datetime

        dt = datetime(2023, 1, 1, 12, 0, 0)

        result = adapter._serialize_json(dt)
        # Should convert datetime to string
        assert isinstance(result, str)
        deserialized = adapter._deserialize_json(result)
        assert isinstance(deserialized, str)

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_unknown_serialization_method(self):
        """Test that an unknown serialization method raises ValueError."""
        config = RedisAdapterConfig(serialization_method="unknown")
        adapter = RedisAdapter(config)
        with pytest.raises(ValueError, match="Unknown serialization method: unknown"):
            adapter._serialize_value("test")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_unknown_deserialization_method(self):
        """Test that an unknown deserialization method raises ValueError."""
        config = RedisAdapterConfig(serialization_method="unknown")
        adapter = RedisAdapter(config)
        with pytest.raises(ValueError, match="Unknown serialization method: unknown"):
            adapter._deserialize_value("test")

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_deserialize_json_from_bytes(self, adapter):
        """Test JSON deserialization from bytes."""
        raw_value = b'"test_value"'
        result = adapter._deserialize_json(raw_value)
        assert result == "test_value"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_serialize_string(self, adapter):
        """Test string serialization."""
        value = "hello world"
        result = adapter._serialize_string(value)
        assert result == "hello world"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_deserialize_string_from_bytes(self, adapter):
        """Test string deserialization from bytes."""
        raw_value = b"hello world"
        result = adapter._deserialize_string(raw_value)
        assert result == "hello world"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_deserialize_string_from_string(self, adapter):
        """Test string deserialization from string."""
        raw_value = "hello world"
        result = adapter._deserialize_string(raw_value)
        assert result == "hello world"
