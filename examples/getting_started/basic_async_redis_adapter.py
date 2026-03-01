"""Basic example: using the Async Redis adapter directly."""

import asyncio

from omni_cache.adapters.redis import AsyncRedisAdapter, RedisAdapterConfig


async def main() -> None:
    print("Async Redis adapter basic example")
    print("=" * 40)

    adapter = AsyncRedisAdapter(
        RedisAdapterConfig(
            name="redis_async_basic",
            host="localhost",
            port=6379,
            db=0,
            socket_timeout=3.0,
            enable_stats=True,
        )
    )

    if not await adapter.connect():
        print("Redis is not reachable on localhost:6379 or redis.asyncio is unavailable")
        return

    key = "async:user:42"
    value = {"name": "Alice", "roles": ["reader", "writer"]}

    print("set:", await adapter.set(key, value, ttl=60))
    print("get:", await adapter.get(key))
    print("exists:", await adapter.exists(key))

    print("set_many:", await adapter.set_many({"a": 1, "b": 2}, ttl=60))
    print("get_many:", await adapter.get_many(["a", "b", "missing"]))
    print("keys:", await adapter.keys())
    print("size:", await adapter.size())

    print("delete:", await adapter.delete(key))
    print("delete_many:", await adapter.delete_many(["a", "b"]))
    print("health_check:", await adapter.health_check())

    await adapter.clear()
    await adapter.disconnect()
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
