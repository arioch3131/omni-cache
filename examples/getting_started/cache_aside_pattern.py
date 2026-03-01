"""
Cache-aside pattern with explicit read/write flow.

This example shows:
- Cache lookup first
- Fallback to data source on miss
- Cache population with TTL
- Explicit invalidation after updates
"""

import time

from omni_cache import setup

manager = setup(log_level="INFO")

# Simulated source of truth (database/service)
PRODUCTS_DB: dict[str, dict[str, object]] = {
    "p-100": {"name": "Keyboard", "price": 49.0, "stock": 12},
    "p-200": {"name": "Mouse", "price": 29.0, "stock": 40},
}


def _fetch_product_from_source(product_id: str) -> dict[str, object]:
    """Simulate an expensive source read."""
    print(f"Source read for {product_id}")
    time.sleep(0.25)
    return PRODUCTS_DB[product_id].copy()


def get_product(product_id: str) -> dict[str, object]:
    """Read path using cache-aside."""
    cache_key = f"product:{product_id}"

    cached_value = manager.get(cache_key)
    if cached_value is not None:
        print(f"Cache hit for {cache_key}")
        return cached_value

    print(f"Cache miss for {cache_key}")
    value = _fetch_product_from_source(product_id)
    manager.set(cache_key, value, ttl=30)
    return value


def update_product_price(product_id: str, new_price: float) -> None:
    """Write path updates source and invalidates cache."""
    PRODUCTS_DB[product_id]["price"] = new_price
    cache_key = f"product:{product_id}"
    manager.delete(cache_key)
    print(f"Invalidated cache key {cache_key}")


def main() -> None:
    print("=== Cache-Aside Example ===")

    start = time.time()
    first = get_product("p-100")
    cold_duration = time.time() - start
    print(f"First read (cold): {first} in {cold_duration:.3f}s")

    start = time.time()
    second = get_product("p-100")
    warm_duration = time.time() - start
    print(f"Second read (warm): {second} in {warm_duration:.3f}s")

    print("\nUpdating price in source...")
    update_product_price("p-100", 59.0)

    refreshed = get_product("p-100")
    print(f"Read after invalidation: {refreshed}")


if __name__ == "__main__":
    main()
