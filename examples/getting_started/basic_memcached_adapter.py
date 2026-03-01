"""Basic example: using the Memcached adapter directly."""

from omni_cache import CacheBackend, create_adapter, setup


def main() -> None:
    print("Memcached adapter basic example")
    print("=" * 40)

    manager = setup(log_level="INFO")

    try:
        memcached_adapter = create_adapter(
            CacheBackend.MEMCACHED,
            {
                "name": "memcached_basic",
                "host": "localhost",
                "port": 11211,
                "connect_timeout": 2.0,
                "timeout": 2.0,
                "enable_stats": True,
            },
        )
        manager.register_adapter("memcached_basic", memcached_adapter)

        if not memcached_adapter.connect():
            print("Memcached is not reachable on localhost:11211")
            return

        key = "profile:99"
        value = {"name": "Bob", "country": "FR"}

        print("set:", memcached_adapter.set(key, value, ttl=60))
        print("get:", memcached_adapter.get(key))
        print("exists:", memcached_adapter.exists(key))
        print("delete:", memcached_adapter.delete(key))
        print("exists_after_delete:", memcached_adapter.exists(key))

        stats = memcached_adapter.get_stats()
        print(f"stats: hits={stats.hits} misses={stats.misses} sets={stats.sets}")

        memcached_adapter.clear()
        memcached_adapter.disconnect()
        print("Done")

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Memcached example skipped: {error}")


if __name__ == "__main__":
    main()
