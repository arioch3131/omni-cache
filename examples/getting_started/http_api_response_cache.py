"""
HTTP API response caching with stable cache keys.

This example shows:
- Caching endpoint responses with @cached
- Stable key generation for query parameters
- Ignoring request-specific noise (`request_id`)
"""

import time
from typing import Any

from omni_cache import cached, setup

setup(log_level="INFO")


def stable_query_key(func: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """
    Create a deterministic key from endpoint + normalized params.

    `request_id` is intentionally excluded to avoid cache fragmentation.
    """
    endpoint = args[0]
    params = args[1] if len(args) > 1 else kwargs.get("params", {})

    normalized = tuple(sorted((k, str(v)) for k, v in params.items()))
    return f"http:{endpoint}:{normalized}"


@cached(ttl=20, namespace="api", key_generator=stable_query_key)
def fetch_search_results(endpoint: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    """Simulate an expensive HTTP call."""
    print(f"Calling upstream API for {endpoint} with params={params}")
    time.sleep(0.3)
    return {
        "endpoint": endpoint,
        "params": params,
        "results": [f"item-{i}" for i in range(1, 4)],
        "fetched_at": time.time(),
    }


def main() -> None:
    print("=== HTTP API Response Cache Example ===")

    params_a = {"q": "keyboard", "page": 1, "sort": "price"}
    params_b = {"sort": "price", "page": 1, "q": "keyboard"}  # Same semantics, different order

    first = fetch_search_results("/search", params_a, request_id="req-1")
    second = fetch_search_results("/search", params_b, request_id="req-2")
    third = fetch_search_results("/search", {"q": "mouse", "page": 1}, request_id="req-3")

    print(f"First timestamp:  {first['fetched_at']}")
    print(f"Second timestamp: {second['fetched_at']} (should be same as first)")
    print(f"Third timestamp:  {third['fetched_at']} (different query, new fetch)")


if __name__ == "__main__":
    main()
