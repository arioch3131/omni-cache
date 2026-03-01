"""Basic example: using the SmartPool adapter directly."""

import time
from typing import Any

from omni_cache import CacheBackend, create_adapter, setup


def create_pooled_object(key: str | None = None) -> dict[str, Any]:
    """Create a pooled object instance."""
    return {
        "key": key,
        "created_at": time.time(),
        "uses": 0,
        "payload": bytearray(256),
    }


def main() -> None:
    print("SmartPool adapter basic example")
    print("=" * 40)

    manager = setup(log_level="INFO")

    try:
        smartpool_adapter = create_adapter(
            CacheBackend.SMARTPOOL,
            {
                "name": "smartpool_basic",
                "factory_function": create_pooled_object,
                "initial_size": 2,
                "min_size": 2,
                "max_size": 20,
                "enable_auto_tuning": False,
                "enable_performance_metrics": True,
            },
        )
        manager.register_adapter("smartpool_basic", smartpool_adapter)

        if not smartpool_adapter.connect():
            print("SmartPool adapter failed to connect")
            return

        with smartpool_adapter.borrow(key="worker-a") as obj:
            actual_obj = obj._obj if hasattr(obj, "_obj") else obj
            actual_obj["uses"] += 1
            actual_obj["payload"][:5] = b"hello"
            print("borrowed:", {"key": actual_obj.get("key"), "uses": actual_obj.get("uses")})

        print("health:", smartpool_adapter.health_check())
        print("backend_info:", smartpool_adapter.get_backend_info())

        smartpool_adapter.disconnect()
        print("Done")

    except Exception as error:  # pylint: disable=broad-exception-caught
        print(f"SmartPool example skipped: {error}")


if __name__ == "__main__":
    main()
