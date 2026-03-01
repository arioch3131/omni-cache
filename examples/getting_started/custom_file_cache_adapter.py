import os
import shutil
import time

from omni_cache import CacheBackend, create_adapter, setup

# Define a custom cache directory for this example
CUSTOM_CACHE_DIR = "my_file_cache_data"


def clean_up_cache_dir():
    """Removes the custom cache directory if it exists."""
    if os.path.exists(CUSTOM_CACHE_DIR):
        shutil.rmtree(CUSTOM_CACHE_DIR)
        print(f"Cleaned up directory: {CUSTOM_CACHE_DIR}")


def main():
    print("🚀 Demonstrating Custom FileCache Adapter")
    print("=" * 50)

    # Ensure a clean state before starting
    clean_up_cache_dir()

    # 1. Setup omni-cache manager
    # The setup function will now automatically discover and register FileCacheFactory
    manager = setup(log_level="INFO")

    # 2. Create an instance of our custom FileCache adapter
    print(f"\n1. Creating FileCache adapter in directory: {CUSTOM_CACHE_DIR}")
    file_cache_adapter = create_adapter(
        CacheBackend.FILE_CACHE, {"name": "my_file_cache", "cache_dir": CUSTOM_CACHE_DIR}
    )
    manager.register_adapter("my_file_cache", file_cache_adapter)

    # 3. Connect to the adapter
    print("\n2. Connecting to FileCache adapter...")
    if file_cache_adapter.connect():
        print("✅ FileCache adapter connected successfully.")
    else:
        print("❌ Failed to connect to FileCache adapter. Exiting.")
        return

    # 4. Perform basic cache operations
    print("\n3. Performing cache operations:")

    # Set a value
    key1 = "user_profile_123"
    value1 = {"name": "Alice", "email": "alice@example.com", "age": 30}
    if file_cache_adapter.set(key1, value1):
        print(f"   Set '{key1}': {value1}")
    else:
        print(f"   Failed to set '{key1}'.")

    # Get the value
    retrieved_value1 = file_cache_adapter.get(key1)
    if retrieved_value1:
        print(f"   Get '{key1}': {retrieved_value1}")
        assert retrieved_value1 == value1
        print("   ✅ Retrieved value matches original.")
    else:
        print(f"   Failed to get '{key1}'.")

    # Set a value with TTL
    key2 = "temp_data_456"
    value2 = {"session_id": "abc", "token": "xyz"}
    ttl_seconds = 5
    if file_cache_adapter.set(key2, value2, ttl=ttl_seconds):
        print(f"   Set '{key2}' with TTL {ttl_seconds}s: {value2}")
    else:
        print(f"   Failed to set '{key2}' with TTL.")

    # Try to get immediately (should be present)
    retrieved_value2_1 = file_cache_adapter.get(key2)
    if retrieved_value2_1:
        print(f"   Get '{key2}' immediately: {retrieved_value2_1}")
        assert retrieved_value2_1 == value2
        print("   ✅ Retrieved value matches original (before expiration).")
    else:
        print(f"   Failed to get '{key2}' immediately.")

    # Wait for TTL to expire
    print(f"   Waiting for {ttl_seconds + 1} seconds for '{key2}' to expire...")
    time.sleep(ttl_seconds + 1)

    # Try to get after TTL (should be None)
    retrieved_value2_2 = file_cache_adapter.get(key2)
    if retrieved_value2_2 is None:
        print(f"   Get '{key2}' after TTL: None (as expected).")
        print("   ✅ Value expired and was not retrieved.")
    else:
        print(f"   Error: '{key2}' was still retrieved after TTL: {retrieved_value2_2}")

    # Delete a key
    if file_cache_adapter.delete(key1):
        print(f"   Deleted '{key1}'.")
    else:
        print(f"   Failed to delete '{key1}'.")

    # Try to get deleted key (should be None)
    retrieved_value1_after_delete = file_cache_adapter.get(key1)
    if retrieved_value1_after_delete is None:
        print(f"   Get '{key1}' after delete: None (as expected).")
        print("   ✅ Deleted key is no longer retrievable.")
    else:
        print(
            f"   Error: '{key1}' was still retrieved after delete: {retrieved_value1_after_delete}"
        )

    # 5. Check health and stats
    print("\n4. Checking adapter health and statistics:")
    if file_cache_adapter.health_check():
        print("   ✅ FileCache adapter is healthy.")
    else:
        print("   ❌ FileCache adapter is unhealthy.")

    stats = file_cache_adapter.get_stats()
    if stats:
        print(
            f"   Cache Stats: Hits={stats.hits}, Misses={stats.misses}, "
            f"Sets={stats.sets}, Deletes={stats.deletes}"
        )
        print(f"   Hit Rate: {stats.hit_rate:.2f}")
    else:
        print("   Statistics not available.")

    # 6. Clear the cache
    print("\n5. Clearing the cache...")
    if file_cache_adapter.clear():
        print("   ✅ FileCache cleared successfully.")
    else:
        print("   ❌ Failed to clear FileCache.")

    # Verify clear
    if not os.path.exists(CUSTOM_CACHE_DIR) or not os.listdir(CUSTOM_CACHE_DIR):
        print(f"   ✅ Cache directory '{CUSTOM_CACHE_DIR}' is empty or removed.")
    else:
        print(f"   ❌ Cache directory '{CUSTOM_CACHE_DIR}' is not empty after clear.")

    # 7. Disconnect
    print("\n6. Disconnecting from FileCache adapter...")
    if file_cache_adapter.disconnect():
        print("✅ FileCache adapter disconnected.")
    else:
        print("❌ Failed to disconnect from FileCache adapter.")

    print("\n✅ Custom FileCache Adapter Demo Completed!")
    print(f"You can inspect the '{CUSTOM_CACHE_DIR}' directory to see the created files.")

    # Clean up at the end
    clean_up_cache_dir()


if __name__ == "__main__":
    main()
