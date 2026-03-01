"""
Tests for Redis adapter configuration and initialization.

This module tests the RedisAdapterConfig class and RedisAdapter initialization
with various configuration scenarios, validation, and error handling.
"""

import sys

import pytest

# Test Redis availability
try:
    from omni_cache.adapters.redis import RedisAdapter, RedisAdapterConfig
    from omni_cache.core.interfaces import CacheBackend

    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    RedisAdapter = None
    RedisAdapterConfig = None
    CacheBackend = None

# pylint: disable=import-outside-toplevel,too-many-locals
# pylint: disable=protected-access,redefined-outer-name


class TestRedisImport:
    def test_has_yaml_false_when_import_error(self):
        # Save original state
        redis_module = sys.modules.get("redis")
        adapter_module = sys.modules.get("omni_cache.adapters.redis.redis")

        try:
            # Force yaml import to fail by setting it to None
            sys.modules["redis"] = None

            # Remove config from sys.modules to force reload
            if "omni_cache.adapters.redis" in sys.modules:
                del sys.modules["omni_cache.adapters.redis.redis"]

            # Import config which will try to import yaml and set HAS_YAML
            import omni_cache.adapters.redis.redis

            # Assert that HAS_YAML is False due to ImportError
            assert omni_cache.adapters.redis.redis.HAS_REDIS is False

        finally:
            # Restore original state
            if redis_module is not None:
                sys.modules["redis"] = redis_module
            elif "redis" in sys.modules:
                del sys.modules["redis"]

            if adapter_module is not None:
                sys.modules["omni_cache.adapters.redis.redis"] = adapter_module
            elif "omni_cache.adapters.redis.redis" in sys.modules:
                del sys.modules["omni_cache.adapters.redis.redis"]


class TestRedisInitImport:
    def test_has_redis_false_in_init_when_import_error(self):
        # Save original state
        original_redis_module = sys.modules.get("redis")
        original_omni_cache_redis_module = sys.modules.get("omni_cache.adapters.redis")

        try:
            # Force redis import to fail
            sys.modules["redis"] = None

            # Remove omni_cache.adapters.redis from sys.modules to force reload of __init__.py
            if "omni_cache.adapters.redis" in sys.modules:
                del sys.modules["omni_cache.adapters.redis"]

            # Import the package, which will trigger __init__.py
            import omni_cache.adapters.redis

            # Assert that HAS_REDIS is False due to ImportError
            assert omni_cache.adapters.redis.HAS_REDIS is False

        finally:
            # Restore original state
            if original_redis_module is not None:
                sys.modules["redis"] = original_redis_module
            elif "redis" in sys.modules:
                del sys.modules["redis"]

            if original_omni_cache_redis_module is not None:
                sys.modules["omni_cache.adapters.redis"] = original_omni_cache_redis_module
            elif "omni_cache.adapters.redis" in sys.modules:
                del sys.modules["omni_cache.adapters.redis"]


class TestRedisAdapterConfig:
    """Tests for RedisAdapterConfig class."""

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_default_config_values(self):
        """Test RedisAdapterConfig with default values."""
        config = RedisAdapterConfig()

        assert config.backend == CacheBackend.REDIS
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db == 0
        assert config.password is None
        assert config.username is None
        assert config.serialization_method == "json"
        assert config.connection_pool_max_connections == 10
        assert config.key_prefix == ""
        assert config.key_separator == ":"
        assert config.health_check_key == "_omni_cache_health_check"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_custom_config_values(self):
        """Test RedisAdapterConfig with custom values."""
        redis_credential = "redis-auth-for-tests"
        config = RedisAdapterConfig(
            host="redis.example.com",
            port=6380,
            db=1,
            password=redis_credential,
            username="redis_user",
            serialization_method="json",
            connection_pool_max_connections=20,
            key_prefix="app",
            key_separator="|",
            health_check_key="custom_health",
            connection_timeout=10.0,
            socket_timeout=5.0,
            retry_on_error=True,
            max_retries=5,
            retry_delay=0.5,
        )

        assert config.host == "redis.example.com"
        assert config.port == 6380
        assert config.db == 1
        assert config.password == redis_credential
        assert config.username == "redis_user"
        assert config.serialization_method == "json"
        assert config.connection_pool_max_connections == 20
        assert config.key_prefix == "app"
        assert config.key_separator == "|"
        assert config.health_check_key == "custom_health"
        assert config.connection_timeout == 10.0
        assert config.socket_timeout == 5.0
        assert config.retry_on_error is True
        assert config.max_retries == 5
        assert config.retry_delay == 0.5

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_redis_kwargs_generation(self):
        """Test Redis connection kwargs generation."""
        redis_credential = "redis-auth-for-tests"
        config = RedisAdapterConfig(
            host="localhost",
            port=6379,
            db=2,
            password=redis_credential,
            username="user",
            connection_timeout=8.0,
            socket_timeout=3.0,
        )

        kwargs = config.get_redis_kwargs()

        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 6379
        assert kwargs["db"] == 2
        assert kwargs["password"] == redis_credential
        assert kwargs["username"] == "user"
        assert "socket_timeout" in kwargs
        assert "socket_connect_timeout" in kwargs

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_redis_kwargs_with_minimal_config(self):
        """Test Redis kwargs with minimal configuration."""
        config = RedisAdapterConfig()

        kwargs = config.get_redis_kwargs()

        assert kwargs["host"] == "localhost"
        assert kwargs["port"] == 6379
        assert kwargs["db"] == 0
        assert kwargs.get("password") is None
        assert kwargs.get("username") is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_serialization_method_validation(self):
        """Test serialization method validation."""
        # Valid serialization methods
        valid_methods = ["json", "string"]

        for method in valid_methods:
            config = RedisAdapterConfig(serialization_method=method)
            assert config.serialization_method == method

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_port_validation(self):
        """Test port number validation."""
        # Valid port
        config = RedisAdapterConfig(port=6380)
        assert config.port == 6380

        # Edge case ports
        config_min = RedisAdapterConfig(port=1)
        assert config_min.port == 1

        config_max = RedisAdapterConfig(port=65535)
        assert config_max.port == 65535

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_db_validation(self):
        """Test database number validation."""
        # Valid database numbers
        for db in [0, 1, 5, 15]:
            config = RedisAdapterConfig(db=db)
            assert config.db == db

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_connection_pool_validation(self):
        """Test connection pool size validation."""
        config = RedisAdapterConfig(connection_pool_max_connections=25)
        assert config.connection_pool_max_connections == 25

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_timeout_validation(self):
        """Test timeout values validation."""
        config = RedisAdapterConfig(connection_timeout=15.0, socket_timeout=10.0)

        assert config.connection_timeout == 15.0
        assert config.socket_timeout == 10.0

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_key_prefix_and_separator(self):
        """Test key prefix and separator configuration."""
        config = RedisAdapterConfig(key_prefix="myapp", key_separator="_")

        assert config.key_prefix == "myapp"
        assert config.key_separator == "_"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_config_repr(self):
        """Test configuration string representation."""
        config = RedisAdapterConfig(host="localhost", port=6379)
        repr_str = repr(config)

        assert "RedisAdapterConfig" in repr_str
        assert "localhost" in repr_str
        assert "6379" in repr_str


class TestRedisAdapterInitialization:
    """Tests for RedisAdapter initialization."""

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_initialization_with_no_config(self):
        """Test RedisAdapter initialization with no configuration."""
        adapter = RedisAdapter()

        assert adapter._config is not None
        assert isinstance(adapter._config, RedisAdapterConfig)
        assert adapter._config.host == "localhost"
        assert adapter._config.port == 6379
        assert adapter._redis is None
        assert adapter._connection_pool is None

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_initialization_with_dict_config(self):
        """Test RedisAdapter initialization with dictionary configuration."""
        redis_credential = "redis-auth-for-tests"
        config_dict = {
            "host": "redis.test.com",
            "port": 6380,
            "db": 1,
            "password": redis_credential,
            "serialization_method": "json",
        }

        adapter = RedisAdapter(config_dict)

        assert adapter._config.host == "redis.test.com"
        assert adapter._config.port == 6380
        assert adapter._config.db == 1
        assert adapter._config.password == redis_credential
        assert adapter._config.serialization_method == "json"

    @pytest.mark.skipif(not HAS_REDIS, reason="Redis not available")
    def test_initialization_with_config_object(self):
        """Test RedisAdapter initialization with RedisAdapterConfig object."""
        config = RedisAdapterConfig(host="config.redis.com", port=6381, serialization_method="json")

        adapter = RedisAdapter(config)

        assert adapter._config is config
        assert adapter._config.host == "config.redis.com"
        assert adapter._config.port == 6381
        assert adapter._config.serialization_method == "json"

    def test_initialization_without_redis_library(self):
        """Test RedisAdapter initialization when Redis library is not available."""
        # This test should be skipped when Redis is available
        # The actual implementation should check HAS_REDIS flag
        if not HAS_REDIS:
            with pytest.raises(ImportError, match="Redis is not available"):
                RedisAdapter()
        else:
            pytest.skip("Redis library is available")
