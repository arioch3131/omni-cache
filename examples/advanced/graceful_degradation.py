"""
Graceful degradation when primary cache is unavailable.

This example shows:
- Primary Redis cache when reachable
- Automatic fallback to memory cache
- Resilient reads/writes in degraded mode
"""

from typing import Any

from omni_cache import CacheBackend, create_adapter, setup

manager = setup(log_level="INFO")

fallback_adapter = create_adapter(CacheBackend.MEMORY, {"name": "fallback_memory", "max_size": 200})
manager.register_adapter("fallback_memory", fallback_adapter)

primary_name: str | None = None
try:
    primary_adapter = create_adapter(
        CacheBackend.REDIS,
        {"name": "primary_redis", "host": "localhost", "port": 6379, "db": 5},
    )
    if manager.register_adapter("primary_redis", primary_adapter):
        primary_name = "primary_redis"
except Exception:
    primary_name = None


def resilient_set(key: str, value: Any, ttl: int = 30) -> bool:
    if primary_name:
        success = manager.set(key, value, ttl=ttl, adapter=primary_name)
        if success:
            return True
    return manager.set(key, value, ttl=ttl, adapter="fallback_memory")


def resilient_get(key: str) -> Any:
    if primary_name:
        value = manager.get(key, adapter=primary_name)
        if value is not None:
            return value
    return manager.get(key, adapter="fallback_memory")


def main() -> None:
    print("=== Graceful degradation example ===")
    print(f"Primary Redis available: {primary_name is not None}")

    resilient_set("session:user-1", {"user_id": 1, "role": "admin"})
    session = resilient_get("session:user-1")
    print(f"Session read: {session}")

    missing = resilient_get("session:missing")
    print(f"Missing read (expected None): {missing}")


if __name__ == "__main__":
    main()
