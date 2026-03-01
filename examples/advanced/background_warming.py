"""
Background cache warming for frequently requested keys.

This example shows:
- Periodic refresh of hot keys
- Avoiding cold-start penalties
- Safe shutdown of warmer thread
"""

import threading
import time

from omni_cache import setup

manager = setup(log_level="INFO")

HOT_KEYS = ["dashboard:summary", "dashboard:alerts", "dashboard:stats"]


def fetch_data(key: str) -> dict[str, object]:
    """Simulate expensive source query."""
    time.sleep(0.15)
    return {"key": key, "generated_at": time.time()}


def warm_once() -> None:
    for key in HOT_KEYS:
        value = fetch_data(key)
        manager.set(key, value, ttl=20)
    print("Warm cycle completed")


def warmer_loop(stop_event: threading.Event, interval_seconds: int = 5) -> None:
    while not stop_event.is_set():
        warm_once()
        stop_event.wait(interval_seconds)


def main() -> None:
    print("=== Background warming example ===")
    stop_event = threading.Event()
    warmer = threading.Thread(target=warmer_loop, args=(stop_event, 3), daemon=True)
    warmer.start()

    time.sleep(1)
    for key in HOT_KEYS:
        value = manager.get(key)
        print(f"Read {key}: hit={value is not None}")

    time.sleep(4)
    for key in HOT_KEYS:
        value = manager.get(key)
        if value:
            print(f"{key} generated_at={value['generated_at']}")

    stop_event.set()
    warmer.join(timeout=1)
    print("Warmer stopped")


if __name__ == "__main__":
    main()
