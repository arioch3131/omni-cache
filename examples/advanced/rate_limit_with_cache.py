"""
Simple rate limiting using cache as a counter store.

This example uses a fixed window algorithm:
- key: rl:{user}:{route}:{window_start}
- value: request count in the current window
"""

import time

from omni_cache import setup

manager = setup(log_level="INFO")


def allow_request(
    user_id: str, route: str, limit: int = 5, window_seconds: int = 10
) -> tuple[bool, int]:
    now = int(time.time())
    window_start = now - (now % window_seconds)
    key = f"rl:{user_id}:{route}:{window_start}"

    count = manager.get(key, default=0)
    if count is None:
        count = 0

    if count >= limit:
        return False, 0

    new_count = count + 1
    manager.set(key, new_count, ttl=window_seconds + 1)
    remaining = limit - new_count
    return True, remaining


def main() -> None:
    print("=== Rate limit with cache example ===")
    user_id = "user-123"
    route = "/search"

    for i in range(1, 8):
        allowed, remaining = allow_request(user_id, route, limit=5, window_seconds=8)
        print(f"Request {i}: allowed={allowed}, remaining={remaining}")
        time.sleep(0.7)

    print("Waiting for window reset...")
    time.sleep(8)
    allowed, remaining = allow_request(user_id, route, limit=5, window_seconds=8)
    print(f"After reset: allowed={allowed}, remaining={remaining}")


if __name__ == "__main__":
    main()
