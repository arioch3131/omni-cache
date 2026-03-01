"""
Observability-focused cache example.

This example shows:
- How cache hits/misses evolve
- How to read global manager stats
- How to inspect adapter stats
"""

from omni_cache import create_adapter, setup
from omni_cache.core.interfaces import CacheBackend

manager = setup(log_level="INFO")

memory_adapter = create_adapter(CacheBackend.MEMORY, {"name": "obs_memory", "max_size": 50})
manager.register_adapter("obs_memory", memory_adapter)


def main() -> None:
    print("=== Observability metrics example ===")

    # Write phase
    for i in range(5):
        manager.set(f"item:{i}", {"value": i}, ttl=30, adapter="obs_memory")

    # Read phase: 5 hits + 2 misses
    for i in range(5):
        manager.get(f"item:{i}", adapter="obs_memory")
    manager.get("item:missing-a", adapter="obs_memory")
    manager.get("item:missing-b", adapter="obs_memory")

    global_stats = manager.get_global_stats()["cache"]
    adapter_stats = manager.get_adapter_stats("obs_memory")

    print(f"Global hits: {global_stats.hits}")
    print(f"Global misses: {global_stats.misses}")
    print(f"Global sets: {global_stats.sets}")
    print(f"Global hit_rate: {global_stats.hit_rate:.2%}")
    print(f"Adapter stats: {adapter_stats}")


if __name__ == "__main__":
    main()
