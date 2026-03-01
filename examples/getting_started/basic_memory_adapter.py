"""Basic example: using the Memory adapter directly."""

from omni_cache import CacheBackend, create_adapter, setup


def main() -> None:
    print("Memory adapter basic example")
    print("=" * 40)

    manager = setup(log_level="INFO")
    memory_adapter = create_adapter(
        CacheBackend.MEMORY,
        {
            "name": "memory_basic",
            "max_size": 1000,
            "eviction_policy": "lru",
            "enable_stats": True,
        },
    )
    manager.register_adapter("memory_basic", memory_adapter)

    if not memory_adapter.connect():
        print("Failed to connect memory adapter")
        return

    key = "user:42"
    value = {"name": "Alice", "role": "admin"}

    print("set:", memory_adapter.set(key, value, ttl=60))
    print("get:", memory_adapter.get(key))
    print("exists:", memory_adapter.exists(key))
    print("delete:", memory_adapter.delete(key))
    print("exists_after_delete:", memory_adapter.exists(key))

    stats = memory_adapter.get_stats()
    print(f"stats: hits={stats.hits} misses={stats.misses} sets={stats.sets}")

    memory_adapter.clear()
    memory_adapter.disconnect()
    print("Done")


if __name__ == "__main__":
    main()
