"""
Cache stampede protection using a per-key single-flight lock.

This example shows:
- Many concurrent requests for same key
- Only one request computes the expensive value
- Others wait and reuse cached result
"""

import threading
import time
from collections import defaultdict

from omni_cache import setup

manager = setup(log_level="INFO")

_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
_source_calls = 0
_source_calls_lock = threading.Lock()


def _expensive_compute(key: str) -> str:
    global _source_calls
    with _source_calls_lock:
        _source_calls += 1
    print(f"Computing source value for {key}")
    time.sleep(0.4)
    return f"value-for-{key}"


def get_or_compute(key: str) -> str:
    cache_key = f"stampede:{key}"
    cached = manager.get(cache_key)
    if cached is not None:
        return cached

    lock = _locks[cache_key]
    with lock:
        cached_after_lock = manager.get(cache_key)
        if cached_after_lock is not None:
            return cached_after_lock

        value = _expensive_compute(key)
        manager.set(cache_key, value, ttl=30)
        return value


def worker(thread_id: int) -> None:
    value = get_or_compute("daily-report")
    print(f"Thread {thread_id} got {value}")


def main() -> None:
    print("=== Stampede protection example ===")
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - start
    print(f"Source calls: {_source_calls} (expected close to 1)")
    print(f"Elapsed: {elapsed:.3f}s")


if __name__ == "__main__":
    main()
