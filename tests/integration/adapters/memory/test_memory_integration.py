"""
IntTests for MemoryAdapter integration scenarios including memory pressure handling,
cleanup resilience, large item handling, realistic usage patterns,
and cross-functional behavior.
"""

import random
import threading
import time

import pytest

from omni_cache.adapters.memory import MemoryAdapter, MemoryAdapterConfig

# pylint: disable=too-many-locals,too-many-statements


class TestMemoryAdapterRealWorldScenarios:
    """Test memory adapter in realistic usage scenarios."""

    def test_web_application_cache_simulation(self, configured_memory_adapter):
        """Simulate a web application cache usage pattern."""
        adapter = configured_memory_adapter

        # Simulate user sessions
        sessions = {}
        for i in range(20):
            session_id = f"session_{i}"
            session_data = {
                "user_id": i,
                "username": f"user_{i}",
                "preferences": {"theme": "dark", "lang": "en"},
                "cart_items": [f"item_{j}" for j in range(random.randint(0, 5))],
            }
            sessions[session_id] = session_data
            adapter.set(session_id, session_data, ttl=3600)  # 1 hour TTL

        # Simulate database query caching
        for i in range(50):
            query_key = f"query_result_{i % 10}"  # Some overlap for cache hits
            query_result = {
                "data": [f"row_{j}" for j in range(random.randint(1, 10))],
                "timestamp": time.time(),
                "query_id": i,
            }
            adapter.set(query_key, query_result, ttl=300)  # 5 minutes TTL

        # Simulate API response caching
        api_responses = {}
        for endpoint in ["users", "products", "orders", "analytics"]:
            for page in range(1, 6):
                cache_key = f"api_{endpoint}_page_{page}"
                response_data = {
                    "endpoint": endpoint,
                    "page": page,
                    "data": [f"{endpoint}_item_{i}" for i in range(20)],
                    "total": 100,
                    "cached_at": time.time(),
                }
                api_responses[cache_key] = response_data
                adapter.set(cache_key, response_data, ttl=600)  # 10 minutes TTL

        # Verify data retrieval
        for session_id, expected_data in sessions.items():
            cached_data = adapter.get(session_id)
            assert cached_data == expected_data

        for cache_key, expected_data in api_responses.items():
            cached_data = adapter.get(cache_key)
            assert cached_data == expected_data

        # Check cache statistics
        stats = adapter.get_stats()
        assert stats.hits > 0
        assert stats.sets > 0
        assert adapter.size() == 50

    def test_microservice_cache_pattern(self):
        """Test cache usage pattern typical of microservices."""
        # Create specialized caches for different services
        user_cache_config = MemoryAdapterConfig(
            name="user_service",
            max_size=1000,
            default_ttl=1800,  # 30 minutes
            eviction_policy="lru",
        )

        product_cache_config = MemoryAdapterConfig(
            name="product_service",
            max_size=5000,
            default_ttl=3600,  # 1 hour
            eviction_policy="fifo",
        )

        order_cache_config = MemoryAdapterConfig(
            name="order_service",
            max_size=500,
            default_ttl=300,
            eviction_policy="lru",  # 5 minutes
        )

        adapters = {
            "user": MemoryAdapter(user_cache_config),
            "product": MemoryAdapter(product_cache_config),
            "order": MemoryAdapter(order_cache_config),
        }

        # Connect all adapters
        for adapter in adapters.values():
            adapter.connect()

        try:
            # Simulate user service operations
            user_adapter = adapters["user"]
            for i in range(100):
                user_data = {
                    "id": i,
                    "email": f"user{i}@example.com",
                    "profile": {"name": f"User {i}", "created": time.time()},
                }
                user_adapter.set(f"user:{i}", user_data)

                # Simulate access patterns - some users accessed more frequently
                if i < 20:  # Hot users
                    for _ in range(random.randint(3, 10)):
                        retrieved = user_adapter.get(f"user:{i}")
                        assert retrieved == user_data

            # Simulate product service operations
            product_adapter = adapters["product"]
            categories = ["electronics", "clothing", "books", "home"]
            for i in range(200):
                category = random.choice(categories)
                product_data = {
                    "id": i,
                    "name": f"Product {i}",
                    "category": category,
                    "price": round(random.uniform(10, 1000), 2),
                    "stock": random.randint(0, 100),
                }
                product_adapter.set(f"product:{i}", product_data)
                product_adapter.set(f"category:{category}:product:{i}", product_data)

            # Simulate order service operations
            order_adapter = adapters["order"]
            for i in range(50):
                order_data = {
                    "id": i,
                    "user_id": random.randint(0, 99),
                    "products": [random.randint(0, 199) for _ in range(random.randint(1, 5))],
                    "total": round(random.uniform(20, 500), 2),
                    "status": random.choice(["pending", "processing", "shipped", "delivered"]),
                }
                order_adapter.set(f"order:{i}", order_data)

                # Cache user's orders
                user_orders_key = f"user:{order_data['user_id']}:orders"
                existing_orders = order_adapter.get(user_orders_key, [])
                existing_orders.append(i)
                order_adapter.set(user_orders_key, existing_orders)

            # Verify cross-service data access patterns
            for _, adapter in adapters.items():
                assert adapter.size() > 0
                stats = adapter.get_stats()
                assert stats.sets > 0
                assert stats.hits >= 0  # May be 0 if no repeated access

                # Test that each adapter maintains its own data
                keys = list(adapter.keys())
                assert len(keys) > 0

                # Verify data integrity
                for key in random.sample(keys, min(10, len(keys))):
                    data = adapter.get(key)
                    assert data is not None

        finally:
            # Cleanup
            for adapter in adapters.values():
                adapter.disconnect()

    @pytest.mark.slow
    def test_high_throughput_scenario(self, large_adapter):
        """Test adapter under high throughput conditions."""
        adapter = large_adapter
        num_operations = 10000

        # Phase 1: Bulk write operations
        start_time = time.time()
        for i in range(num_operations):
            key = f"bulk_key_{i}"
            value = {
                "id": i,
                "data": "x" * 100,  # 100 bytes of data
                "timestamp": time.time(),
                "metadata": {"category": i % 10, "priority": i % 5},
            }
            success = adapter.set(key, value)
            assert success

        write_time = time.time() - start_time

        # Phase 2: Mixed read/write operations
        start_time = time.time()
        hits = 0
        for i in range(num_operations):
            if i % 3 == 0:  # 33% writes
                key = f"mixed_key_{i}"
                value = f"mixed_value_{i}"
                adapter.set(key, value)
            else:  # 67% reads
                key = f"bulk_key_{random.randint(0, num_operations - 1)}"
                result = adapter.get(key)
                if result is not None:
                    hits += 1

        mixed_time = time.time() - start_time

        # Verify performance characteristics
        assert write_time < 10.0, f"Bulk writes took too long: {write_time:.2f}s"
        assert mixed_time < 10.0, f"Mixed operations took too long: {mixed_time:.2f}s"
        assert hits > num_operations * 0.3, f"Hit rate too low: {hits}/{num_operations * 2 / 3}"

        # Verify data integrity
        stats = adapter.get_stats()
        assert stats.sets >= num_operations
        assert stats.hits >= hits

    def test_cache_warming_and_preloading(self, configured_memory_adapter):
        """Test cache warming and preloading scenarios."""
        adapter = configured_memory_adapter

        # Simulate cache warming phase
        def warm_user_data():
            """Warm up user-related data."""
            for i in range(100):
                user_key = f"user:{i}"
                user_data = {
                    "id": i,
                    "profile": f"User Profile {i}",
                    "settings": {"theme": "light", "notifications": True},
                }
                adapter.set(user_key, user_data, ttl=3600)

        def warm_reference_data():
            """Warm up reference/configuration data."""
            reference_data = {
                "countries": ["US", "CA", "UK", "DE", "FR", "JP"],
                "currencies": ["USD", "CAD", "GBP", "EUR", "JPY"],
                "timezones": ["UTC", "EST", "PST", "CET", "JST"],
                "feature_flags": {"new_ui": True, "beta_feature": False, "maintenance_mode": False},
            }

            for key, value in reference_data.items():
                adapter.set(f"config:{key}", value, ttl=86400)  # 24 hours

        def warm_lookup_tables():
            """Warm up lookup tables."""
            for category in ["electronics", "books", "clothing"]:
                category_data = {
                    "id": category,
                    "subcategories": [f"{category}_sub_{i}" for i in range(5)],
                    "popular_items": [f"{category}_item_{i}" for i in range(10)],
                }
                adapter.set(f"category:{category}", category_data, ttl=7200)  # 2 hours

        # Execute cache warming
        start_time = time.time()
        warm_user_data()
        warm_reference_data()
        warm_lookup_tables()
        warming_time = time.time() - start_time

        # Verify cache warming was effective
        assert adapter.size() == 100
        assert warming_time < 5.0, f"Cache warming took too long: {warming_time:.2f}s"

        # Test that warmed data is accessible
        user_data = adapter.get("user:50")
        assert user_data is not None
        assert user_data["id"] == 50

        config_data = adapter.get("config:countries")
        assert config_data is not None
        assert "US" in config_data

        category_data = adapter.get("category:electronics")
        assert category_data is not None
        assert category_data["id"] == "electronics"

        # Simulate application startup performance test
        # (accessing pre-warmed data should be fast)
        lookup_start = time.time()
        for _ in range(1000):
            adapter.get(f"user:{random.randint(0, 99)}")
            adapter.get(f"config:{random.choice(['countries', 'currencies', 'timezones'])}")
            adapter.get(f"category:{random.choice(['electronics', 'books', 'clothing'])}")
        lookup_time = time.time() - lookup_start

        assert lookup_time < 1.0, f"Lookups too slow: {lookup_time:.2f}s"

        # Verify cache hit rate is high for warmed data
        stats = adapter.get_stats()
        assert stats.hit_rate > 0.8, f"Hit rate too low: {stats.hit_rate:.2%}"


class TestMemoryAdapterConcurrentWorkloads:
    """Test memory adapter under concurrent access patterns."""

    @pytest.mark.concurrent
    def test_concurrent_cache_pattern_simulation(self):
        """Simulate realistic concurrent cache usage patterns."""
        config = MemoryAdapterConfig(
            name="concurrent_test", max_size=1000, cleanup_interval=0.5, enable_stats=True
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            results = {"errors": 0, "operations": 0}
            results_lock = threading.Lock()

            def worker_read_heavy(worker_id: int, iterations: int):
                """Worker that performs mostly read operations."""
                local_errors = 0
                local_operations = 0

                for i in range(iterations):
                    try:
                        # 80% reads, 20% writes
                        if random.random() < 0.8:
                            key = f"shared_key_{random.randint(0, 100)}"
                            _ = adapter.get(key)
                            local_operations += 1
                        else:
                            key = f"worker_{worker_id}_key_{i}"
                            value = f"worker_{worker_id}_value_{i}"
                            adapter.set(key, value, ttl=random.uniform(1.0, 5.0))
                            local_operations += 1
                    except Exception:  # pylint: disable=broad-exception-caught
                        local_errors += 1

                with results_lock:
                    results["errors"] += local_errors
                    results["operations"] += local_operations

            def worker_write_heavy(worker_id: int, iterations: int):
                """Worker that performs mostly write operations."""
                local_errors = 0
                local_operations = 0

                for i in range(iterations):
                    try:
                        # 20% reads, 80% writes
                        if random.random() < 0.2:
                            key = f"shared_key_{random.randint(0, 100)}"
                            _ = adapter.get(key)
                            local_operations += 1
                        else:
                            key = f"shared_key_{random.randint(0, 100)}"
                            value = {
                                "worker_id": worker_id,
                                "iteration": i,
                                "timestamp": time.time(),
                                "data": "x" * random.randint(10, 100),
                            }
                            adapter.set(key, value, ttl=random.uniform(0.5, 3.0))
                            local_operations += 1
                    except Exception:  # pylint: disable=broad-exception-caught
                        local_errors += 1

                with results_lock:
                    results["errors"] += local_errors
                    results["operations"] += local_operations

            def worker_mixed_operations(worker_id: int, iterations: int):
                """Worker that performs mixed operations."""
                local_errors = 0
                local_operations = 0

                for i in range(iterations):
                    try:
                        operation = random.choice(["get", "set", "delete", "exists"])
                        key = f"mixed_key_{random.randint(0, 50)}"

                        if operation == "get":
                            _ = adapter.get(key)
                        elif operation == "set":
                            value = f"mixed_value_{worker_id}_{i}"
                            adapter.set(key, value, ttl=random.uniform(0.2, 2.0))
                        elif operation == "delete":
                            adapter.delete(key)
                        elif operation == "exists":
                            adapter.exists(key)

                        local_operations += 1
                    except Exception:  # pylint: disable=broad-exception-caught
                        local_errors += 1

                with results_lock:
                    results["errors"] += local_errors
                    results["operations"] += local_operations

            # Start concurrent workers
            threads = []

            # 5 read-heavy workers
            for i in range(5):
                thread = threading.Thread(
                    target=worker_read_heavy, args=(i, 200), name=f"ReadWorker-{i}"
                )
                threads.append(thread)

            # 3 write-heavy workers
            for i in range(3):
                thread = threading.Thread(
                    target=worker_write_heavy, args=(i + 10, 150), name=f"WriteWorker-{i}"
                )
                threads.append(thread)

            # 2 mixed workers
            for i in range(2):
                thread = threading.Thread(
                    target=worker_mixed_operations, args=(i + 20, 100), name=f"MixedWorker-{i}"
                )
                threads.append(thread)

            # Start all threads
            start_time = time.time()
            for thread in threads:
                thread.start()

            # Wait for completion
            for thread in threads:
                thread.join(timeout=30)  # 30 second timeout
                if thread.is_alive():
                    pytest.fail(f"Thread {thread.name} did not complete in time")

            execution_time = time.time() - start_time

            # Verify results
            assert results["errors"] == 0, f"Errors occurred: {results['errors']}"
            assert results["operations"] > 0, "No operations were performed"
            assert execution_time < 20.0, f"Execution took too long: {execution_time:.2f}s"

            # Verify adapter is still functional
            adapter.set("final_test", "final_value")
            assert adapter.get("final_test") == "final_value"

            # Check statistics
            stats = adapter.get_stats()
            assert stats.sets > 0
            assert stats.hits + stats.misses > 0

        finally:
            adapter.disconnect()

    @pytest.mark.concurrent
    def test_producer_consumer_pattern(self):
        """Test producer-consumer pattern with the memory adapter."""
        config = MemoryAdapterConfig(name="producer_consumer", max_size=100, cleanup_interval=0.2)
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            produced_items = []
            consumed_items = []
            lock = threading.Lock()

            def producer(producer_id: int, num_items: int):
                """Produce items and put them in the cache."""
                for i in range(num_items):
                    item = {
                        "producer_id": producer_id,
                        "item_id": i,
                        "timestamp": time.time(),
                        "data": f"Producer {producer_id} Item {i}",
                    }
                    key = f"item_{producer_id}_{i}"

                    success = adapter.set(key, item, ttl=5.0)
                    if success:
                        with lock:
                            produced_items.append(key)

                    # Small delay to simulate processing
                    time.sleep(0.001)

            # pylint: disable=unused-argument
            def consumer(consumer_id: int):
                """Consume items from the cache."""
                processed_count = 0
                start_time = time.time()

                while time.time() - start_time < 5.0:  # Run for 5 seconds
                    with lock:
                        if produced_items:
                            # Get a random item
                            key = random.choice(produced_items)
                        else:
                            time.sleep(0.01)
                            continue

                    item = adapter.get(key)
                    if item is not None:
                        with lock:
                            consumed_items.append(key)
                            if key in produced_items:
                                produced_items.remove(key)

                        # Simulate processing
                        processed_count += 1
                        adapter.delete(key)  # Remove processed item

                    time.sleep(0.005)  # Small delay

                return processed_count

            # Start producers and consumers
            producer_threads = []
            consumer_threads = []

            # Start 3 producers
            for i in range(3):
                thread = threading.Thread(target=producer, args=(i, 50), name=f"Producer-{i}")
                producer_threads.append(thread)
                thread.start()

            # Start 2 consumers
            for i in range(2):
                thread = threading.Thread(target=consumer, args=(i,), name=f"Consumer-{i}")
                consumer_threads.append(thread)
                thread.start()

            # Wait for producers to finish
            for thread in producer_threads:
                thread.join()

            # Wait for consumers to finish
            for thread in consumer_threads:
                thread.join()

            # Verify results
            assert len(produced_items) + len(consumed_items) > 0, "No items were processed"

            # Some items should have been consumed
            assert len(consumed_items) > 0, "No items were consumed"

            # Verify adapter state
            stats = adapter.get_stats()
            assert stats.sets > 0
            assert stats.deletes > 0

        finally:
            adapter.disconnect()


class TestMemoryAdapterFailureRecovery:
    """Test memory adapter's behavior under failure conditions."""

    def test_memory_pressure_handling(self):
        """Test adapter behavior under memory pressure."""
        config = MemoryAdapterConfig(
            name="pressure_test",
            max_size=50,  # Small size to trigger evictions
            eviction_policy="lru",
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Fill the cache beyond capacity
            for i in range(100):  # More than max_size
                key = f"pressure_key_{i}"
                value = {"id": i, "data": "x" * 1000, "timestamp": time.time()}  # 1KB of data
                success = adapter.set(key, value)
                assert success  # Set should always succeed due to eviction

            # Verify cache size is within limits
            assert adapter.size() <= config.max_size

            # Verify eviction statistics
            stats = adapter.get_stats()
            assert stats.evictions > 0

            # Verify newer items are still present (LRU behavior)
            newer_items_found = 0
            for i in range(90, 100):  # Check last 10 items
                key = f"pressure_key_{i}"
                if adapter.exists(key):
                    newer_items_found += 1

            assert newer_items_found > 0, "Newer items should still be in cache"

        finally:
            adapter.disconnect()

    def test_cleanup_thread_resilience(self):
        """Test that cleanup thread continues working despite errors."""
        config = MemoryAdapterConfig(
            name="cleanup_test",
            cleanup_interval=0.1,
            default_ttl=0.2,  # Fast cleanup
        )
        adapter = MemoryAdapter(config)
        adapter.connect()

        try:
            # Add items that will expire
            for i in range(10):
                adapter.set(f"expiring_{i}", f"value_{i}")

            initial_size = adapter.size()
            assert initial_size == 10

            # Wait for items to expire and be cleaned up
            time.sleep(0.4)  # Wait longer than TTL + cleanup interval

            # Most items should be cleaned up
            final_size = adapter.size()
            assert final_size < initial_size

            # Adapter should still be functional
            adapter.set("new_item", "new_value")
            assert adapter.get("new_item") == "new_value"

        finally:
            adapter.disconnect()

    def test_large_item_handling(self):
        """Test adapter's handling of large data items."""
        adapter = MemoryAdapter()
        adapter.connect()

        try:
            # Test with increasingly large items
            sizes = [1024, 10240, 102400, 1024000]  # 1KB to 1MB

            for size in sizes:
                large_data = {
                    "size": size,
                    "data": "x" * size,
                    "metadata": {"test": True, "size_bytes": size},
                }

                key = f"large_item_{size}"
                success = adapter.set(key, large_data)
                assert success, f"Failed to store item of size {size}"

                # Verify retrieval
                retrieved = adapter.get(key)
                assert retrieved is not None
                assert retrieved["size"] == size
                assert len(retrieved["data"]) == size

                # Clean up
                adapter.delete(key)

            # Verify adapter is still functional
            adapter.set("normal_item", "normal_value")
            assert adapter.get("normal_item") == "normal_value"

        finally:
            adapter.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
