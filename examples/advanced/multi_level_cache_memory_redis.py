"""
Two-level cache pattern (L1 memory + L2 Redis).

This example shows:
- Fast local cache (L1) for hot reads
- Shared cache (L2) when available
- Read-through backfill from L2 to L1
"""

import time
from typing import Any

from omni_cache import CacheBackend, create_adapter, setup

manager = setup(log_level="INFO")

memory_adapter = create_adapter(CacheBackend.MEMORY, {"name": "l1_memory", "max_size": 1000})
manager.register_adapter("l1_memory", memory_adapter)

redis_available = False
try:
    redis_adapter = create_adapter(
        CacheBackend.REDIS,
        {"name": "l2_redis", "host": "localhost", "port": 6379, "db": 4},
    )
    redis_available = manager.register_adapter("l2_redis", redis_adapter)
except Exception:
    redis_available = False


def fetch_from_source(product_id: str) -> dict[str, Any]:
    """Simulate an expensive upstream call."""
    print(f"Source fetch for {product_id}")
    time.sleep(0.25)
    return {"id": product_id, "name": "Sample Product", "fetched_at": time.time()}


def get_product(product_id: str) -> dict[str, Any]:
    """Read with L1 -> L2 -> source strategy."""
    key = f"product:{product_id}"

    l1_value = manager.get(key, adapter="l1_memory")
    if l1_value is not None:
        print("L1 hit")
        return l1_value

    if redis_available:
        l2_value = manager.get(key, adapter="l2_redis")
        if l2_value is not None:
            print("L2 hit, backfilling L1")
            manager.set(key, l2_value, ttl=10, adapter="l1_memory")
            return l2_value

    print("Cache miss on L1/L2")
    source_value = fetch_from_source(product_id)
    manager.set(key, source_value, ttl=10, adapter="l1_memory")
    if redis_available:
        manager.set(key, source_value, ttl=60, adapter="l2_redis")
    return source_value


def main() -> None:
    print("=== Multi-level cache (memory + redis) ===")
    print(f"Redis enabled: {redis_available}")

    first = get_product("p-42")
    second = get_product("p-42")
    print(f"First fetched_at:  {first['fetched_at']}")
    print(f"Second fetched_at: {second['fetched_at']}")


if __name__ == "__main__":
    main()
