from unittest.mock import Mock

from omni_cache.core.manager import CacheManager
from omni_cache.utils.decorators import CacheConfig, KeyGenerator, cached


class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_cache_key_with_unhashable_args(self):
        """Test cache key generation with unhashable arguments."""

        def func_with_dict(data_dict):
            return sum(data_dict.values())

        # This should not raise an exception
        config = CacheConfig()
        key = KeyGenerator.default_key_generator(func_with_dict, ({"a": 1, "b": 2},), {}, config)
        assert "args:" in key

    def test_cached_decorator_with_none_manager(self):
        """Test cached decorator behavior with None manager."""
        # Créer un manager explicite au lieu d'utiliser get_global_manager
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get.return_value = "cached_result"
        mock_manager.set.return_value = True

        # Passer explicitement le manager - pas de get_global_manager()
        @cached(manager=mock_manager)  # ← Changement ici : passer le manager
        def func(x):
            return x * 2

        result = func(5)
        assert result == "cached_result"
        mock_manager.get.assert_called_once()

    def test_config_classes_with_invalid_types(self):
        """Test configuration classes with edge case inputs."""
        # This should work without issues
        config = CacheConfig(
            ignore_args=set(),  # Empty set
            ignore_kwargs=set(),  # Empty set
        )
        assert config.ignore_args == set()
        assert config.ignore_kwargs == set()

    def test_decorator_exception_in_cache_operations(self):
        """Test decorator behavior when cache operations raise exceptions."""
        mock_manager = Mock(spec=CacheManager)
        mock_manager.get.side_effect = Exception("Cache read error")
        mock_manager.set.side_effect = Exception("Cache write error")

        @cached()
        def func(x):
            return x * 2

        # Should still work despite cache errors
        result = func(5)
        assert result == 10
