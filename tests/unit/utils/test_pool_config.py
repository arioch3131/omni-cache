from omni_cache.utils.decorators import PoolConfig


class TestPoolConfig:
    """Test PoolConfig dataclass."""

    def test_pool_config_default_values(self):
        """Test default values of PoolConfig."""
        config = PoolConfig()

        assert config.adapter is None
        assert config.timeout is None
        assert config.max_retries == 3
        assert config.retry_delay == 0.1
        assert config.on_borrow is None
        assert config.on_return is None
        assert config.on_error is None
        assert config.auto_create is False
        assert config.factory_function is None

    def test_pool_config_custom_values(self):
        """Test PoolConfig with custom values."""

        def on_borrow(obj):
            return None

        def factory_func():
            return "new_object"

        config = PoolConfig(
            adapter="memory",
            timeout=30.0,
            max_retries=5,
            retry_delay=0.5,
            on_borrow=on_borrow,
            auto_create=True,
            factory_function=factory_func,
        )

        assert config.adapter == "memory"
        assert config.timeout == 30.0
        assert config.max_retries == 5
        assert config.retry_delay == 0.5
        assert config.on_borrow == on_borrow
        assert config.auto_create is True
        assert config.factory_function == factory_func
