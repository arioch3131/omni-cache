"""
Database query cache with explicit invalidation after writes.

This example shows:
- Cached read queries with @cached
- Write operations that invalidate stale cache entries
- Separation between source of truth and cached reads
"""

import time

from omni_cache import cached, setup

setup(log_level="INFO")

# Simulated database table
USERS_TABLE: dict[int, dict[str, object]] = {
    1: {"id": 1, "name": "Alice", "plan": "pro"},
    2: {"id": 2, "name": "Bob", "plan": "free"},
}


@cached(ttl=60, namespace="db", key_prefix="users")
def get_user_by_id(user_id: int) -> dict[str, object] | None:
    """Simulate expensive SQL query."""
    print(f"DB query for user_id={user_id}")
    time.sleep(0.2)

    row = USERS_TABLE.get(user_id)
    return row.copy() if row else None


def update_user_plan(user_id: int, new_plan: str) -> None:
    """Update source and invalidate cache for that user."""
    if user_id not in USERS_TABLE:
        raise ValueError(f"user_id={user_id} does not exist")

    USERS_TABLE[user_id]["plan"] = new_plan
    invalidated = get_user_by_id.invalidate(user_id)
    print(f"Updated user {user_id} to plan={new_plan}, invalidated={invalidated}")


def main() -> None:
    print("=== DB Query Cache + Invalidation Example ===")

    u1 = get_user_by_id(1)
    u2 = get_user_by_id(1)  # Cached
    print(f"First read:  {u1}")
    print(f"Second read: {u2} (from cache)")

    print("\nApplying write operation...")
    update_user_plan(1, "enterprise")

    u3 = get_user_by_id(1)  # Re-query after invalidation
    print(f"Read after write: {u3}")


if __name__ == "__main__":
    main()
