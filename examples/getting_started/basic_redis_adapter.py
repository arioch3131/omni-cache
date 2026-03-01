"""Basic example: using the Redis adapter directly."""

from omni_cache import CacheBackend, create_adapter, setup


def main() -> None:
    print("Redis adapter basic example")
    print("=" * 40)

    manager = setup(log_level="INFO")

    try:
        redis_adapter = create_adapter(
            CacheBackend.REDIS,
            {
                "name": "redis_basic",
                "host": "localhost",
                "port": 6379,
                "db": 0,
                "socket_timeout": 3.0,
                "enable_stats": True,
            },
        )
        manager.register_adapter("redis_basic", redis_adapter)

        if not redis_adapter.connect():
            print("Redis is not reachable on localhost:6379")
            return

        key = "session:abc"
        value = {"user_id": 42, "scopes": ["read", "write"]}

        print("set:", redis_adapter.set(key, value, ttl=60))
        print("get:", redis_adapter.get(key))
        print("exists:", redis_adapter.exists(key))
        print("delete:", redis_adapter.delete(key))
        print("exists_after_delete:", redis_adapter.exists(key))

        stats = redis_adapter.get_stats()
        print(f"stats: hits={stats.hits} misses={stats.misses} sets={stats.sets}")

        redis_adapter.clear()
        redis_adapter.disconnect()
        print("Done")

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"Redis example skipped: {error}")


if __name__ == "__main__":
    main()
