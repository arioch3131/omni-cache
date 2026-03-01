import time

from omni_cache.utils.decorators import CacheConfig, KeyGenerator


class TestKeyGenerator:
    """Test KeyGenerator utility class."""

    def test_default_key_generator(self):
        """Test default key generation."""

        def sample_func(a, b, c=None):
            return a + b

        config = CacheConfig()
        args = (1, 2)
        kwargs = {"c": 3}

        key = KeyGenerator.default_key_generator(sample_func, args, kwargs, config)

        # Key should contain function name and serialized args/kwargs
        assert isinstance(key, str)
        assert len(key) > 0
        # Key should be deterministic
        key2 = KeyGenerator.default_key_generator(sample_func, args, kwargs, config)
        assert key == key2

    def test_key_generator_with_ignore_args(self):
        """Test key generation with ignored arguments."""

        def sample_func(a, b, timestamp):
            return a + b

        config = CacheConfig(ignore_args={2})  # Ignore third argument
        args1 = (1, 2, time.time())
        args2 = (1, 2, time.time() + 100)  # Different timestamp
        kwargs = {}

        key1 = KeyGenerator.default_key_generator(sample_func, args1, kwargs, config)
        key2 = KeyGenerator.default_key_generator(sample_func, args2, kwargs, config)

        # Keys should be the same since timestamp is ignored
        assert key1 == key2

    def test_key_generator_with_ignore_kwargs(self):
        """Test key generation with ignored keyword arguments."""

        def sample_func(a, b, debug=False):
            return a + b

        config = CacheConfig(ignore_kwargs={"debug"})
        args = (1, 2)
        kwargs1 = {"debug": True}
        kwargs2 = {"debug": False}

        key1 = KeyGenerator.default_key_generator(sample_func, args, kwargs1, config)
        key2 = KeyGenerator.default_key_generator(sample_func, args, kwargs2, config)

        # Keys should be the same since debug is ignored
        assert key1 == key2

    def test_key_generator_with_prefix(self):
        """Test key generation with prefix."""

        def sample_func():
            return "result"

        config = CacheConfig(key_prefix="test_prefix_")
        args = ()
        kwargs = {}

        key = KeyGenerator.default_key_generator(sample_func, args, kwargs, config)

        assert key.startswith("test_prefix_")
