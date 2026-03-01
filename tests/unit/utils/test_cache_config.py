from omni_cache.utils.decorators import CacheConfig


class TestCacheConfig:
    """Test CacheConfig dataclass."""

    def test_cache_config_default_values(self):
        """Test default values of CacheConfig."""
        config = CacheConfig()

        assert config.ttl is None
        assert config.namespace is None
        assert config.key_prefix == ""
        assert config.adapter is None
        assert config.ignore_args == set()
        assert config.ignore_kwargs == set()
        assert config.key_generator is None
        assert config.serializer is None
        assert config.deserializer is None
        assert config.on_hit is None
        assert config.on_miss is None
        assert config.on_error is None
        assert config.enable_stats is True

    def test_cache_config_custom_values(self):
        """Test CacheConfig with custom values."""
        ignore_args = {0, 1}
        ignore_kwargs = {"param1", "param2"}

        def key_gen(*args):
            return "test_key"

        config = CacheConfig(
            ttl=300,
            namespace="test",
            key_prefix="prefix_",
            adapter="redis",
            ignore_args=ignore_args,
            ignore_kwargs=ignore_kwargs,
            key_generator=key_gen,
            enable_stats=False,
        )

        assert config.ttl == 300
        assert config.namespace == "test"
        assert config.key_prefix == "prefix_"
        assert config.adapter == "redis"
        assert config.ignore_args == ignore_args
        assert config.ignore_kwargs == ignore_kwargs
        assert config.key_generator == key_gen
        assert config.enable_stats is False
