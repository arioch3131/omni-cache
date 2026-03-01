"""
Integration tests for SmartPoolAdapter - Full system testing with real components.

This module contains comprehensive integration tests for the SmartPoolAdapter class,
using real SmartPool instances and testing complete workflows, concurrency,
object lifecycle management, and system behavior under various conditions.
"""

import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.smartpool import SmartPoolAdapter
from omni_cache.core.exceptions import AdapterNotConnectedError


# Test objects for integration testing
class IntegrationTestObject:
    """Real test object with lifecycle management capabilities."""

    _instance_counter = 0
    _lock = threading.Lock()

    def __init__(self, name="default", data=None):
        with IntegrationTestObject._lock:
            IntegrationTestObject._instance_counter += 1
            self.instance_id = IntegrationTestObject._instance_counter

        self.name = name
        self.data = data or {}
        self.is_reset = False
        self.is_destroyed = False
        self.is_valid = True
        self.reset_count = 0
        self.use_count = 0
        self.creation_time = time.time()
        self.last_reset_time = None
        self.last_use_time = None

        # Thread safety
        self._lock = threading.Lock()

    def reset(self):
        """Reset object state for reuse."""
        with self._lock:
            self.is_reset = True
            self.reset_count += 1
            self.last_reset_time = time.time()
            self.data.clear()

    def validate(self):
        """Validate object integrity."""
        with self._lock:
            return self.is_valid and not self.is_destroyed

    def destroy(self):
        """Clean up object resources."""
        with self._lock:
            self.is_destroyed = True
            self.is_valid = False
            self.data.clear()

    def use(self, operation="work"):
        """Simulate object usage."""
        with self._lock:
            if not self.is_valid or self.is_destroyed:
                raise RuntimeError("Cannot use invalid or destroyed object")
            self.use_count += 1
            self.last_use_time = time.time()
            self.data[f"operation_{self.use_count}"] = operation
            return f"Used {self.name} for {operation} (use #{self.use_count})"

    def __str__(self):
        return f"TestObject(id={self.instance_id}, name={self.name}, uses={self.use_count})"

    @classmethod
    def get_instance_count(cls):
        """Get total number of instances created."""
        with cls._lock:
            return cls._instance_counter

    @classmethod
    def reset_instance_counter(cls):
        """Reset instance counter for testing."""
        with cls._lock:
            cls._instance_counter = 0


class DatabaseConnectionMock:
    """Mock database connection for testing database pool scenarios."""

    def __init__(self, host="localhost", port=5432, database="test"):
        self.host = host
        self.port = port
        self.database = database
        self.is_connected = True
        self.is_valid = True
        self.transaction_count = 0
        self.query_count = 0
        self.connection_id = f"conn_{random.randint(1000, 9999)}"
        self._lock = threading.Lock()

    def execute_query(self, query):
        """Execute a database query."""
        with self._lock:
            if not self.is_connected or not self.is_valid:
                raise RuntimeError("Connection is not available")
            self.query_count += 1
            time.sleep(0.001)  # Simulate query time
            return f"Query result for: {query}"

    def begin_transaction(self):
        """Begin database transaction."""
        with self._lock:
            if not self.is_connected:
                raise RuntimeError("Cannot begin transaction on closed connection")
            self.transaction_count += 1

    def commit(self):
        """Commit transaction."""
        pass

    def rollback(self):
        """Rollback transaction."""
        pass

    def reset(self):
        """Reset connection state."""
        with self._lock:
            self.transaction_count = 0
            self.query_count = 0

    def validate(self):
        """Validate connection health."""
        return self.is_connected and self.is_valid

    def destroy(self):
        """Close connection."""
        with self._lock:
            self.is_connected = False
            self.is_valid = False


# Fixtures
@pytest.fixture(autouse=True)
def reset_test_object_counter():
    """Reset the test object counter before each test."""
    IntegrationTestObject.reset_instance_counter()
    yield
    IntegrationTestObject.reset_instance_counter()


@pytest.fixture
def test_object_factory():
    """Factory function for IntegrationTestObject."""

    def factory(name="test_obj", data=None):
        return IntegrationTestObject(name=name, data=data or {})

    return factory


@pytest.fixture
def database_connection_factory():
    """Factory function for DatabaseConnectionMock."""

    def factory(host="localhost", port=5432, database="test"):
        return DatabaseConnectionMock(host=host, port=port, database=database)

    return factory


@pytest.fixture
def basic_integration_config(test_object_factory):
    """Basic configuration for integration tests."""
    return SmartPoolAdapterConfig(
        name="integration_test_pool",
        factory_function=test_object_factory,
        initial_size=10,  # Increased for stress test
        max_size=20,  # Increased for stress test
        min_size=1,
        enable_stats=True,
        enable_performance_metrics=True,
        auto_wrap_objects=True,
        extra_config={
            "reset_func": lambda obj: obj.reset(),
            "validate_func": lambda obj: obj.validate(),
            "destroy_func": lambda obj: obj.destroy(),
        },
    )


@pytest.fixture
def database_integration_config(database_connection_factory):
    """Configuration for database connection pool integration tests."""
    return SmartPoolAdapterConfig(
        name="db_integration_pool",
        factory_function=database_connection_factory,
        initial_size=1,
        max_size=5,
        min_size=1,
        enable_stats=True,
        enable_performance_metrics=True,
        auto_wrap_objects=True,
        extra_config={
            "reset_func": lambda conn: conn.reset(),
            "validate_func": lambda conn: conn.validate(),
            "destroy_func": lambda conn: conn.destroy(),
        },
    )


@pytest.fixture
def connected_adapter(basic_integration_config):
    """Connected SmartPoolAdapter for integration tests."""
    adapter = SmartPoolAdapter(basic_integration_config)
    adapter.connect()

    # Wait for pool to stabilize
    time.sleep(0.1)

    yield adapter

    # Cleanup
    adapter.disconnect()


class TestSmartPoolIntegrationBasic:
    """Basic integration tests with real SmartPool backend."""

    def test_full_lifecycle_connection_operations_disconnection(self, basic_integration_config):
        """Test complete adapter lifecycle from connection to disconnection."""
        adapter = SmartPoolAdapter(basic_integration_config)

        # Initial state
        assert not adapter.is_connected()
        assert adapter._pool is None

        # Connect
        result = adapter.connect()
        assert result is True
        assert adapter.is_connected()
        assert adapter._pool is not None

        # Verify health
        assert adapter.health_check() is True

        # Perform operations
        obj = adapter.get()
        assert obj is not None
        assert hasattr(obj, "_obj")  # Wrapped object
        assert isinstance(obj._obj, IntegrationTestObject)

        # Use the object
        result = obj._obj.use("test_operation")
        assert "test_operation" in result
        assert obj._obj.use_count == 1

        # Return object
        put_result = adapter.put(obj)
        assert put_result is True

        # Disconnect
        disconnect_result = adapter.disconnect()
        assert disconnect_result is True
        assert not adapter.is_connected()
        assert adapter._pool is None

    def test_pool_sizing_and_prepopulation(self, basic_integration_config):
        """Test that pool respects sizing configuration and pre-populates correctly."""
        initial_instance_count = IntegrationTestObject.get_instance_count()

        adapter = SmartPoolAdapter(basic_integration_config)
        adapter.connect()

        # Check that initial_size objects were created
        current_instance_count = IntegrationTestObject.get_instance_count()
        created_objects = current_instance_count - initial_instance_count

        # Should have created at least initial_size objects
        assert created_objects >= basic_integration_config.initial_size

        # Verify pool size
        pool_size = adapter.size()
        assert pool_size >= basic_integration_config.initial_size

        adapter.disconnect()

    def test_object_lifecycle_reset_validation_destroy(self, connected_adapter):
        """Test complete object lifecycle including reset, validation, and destruction."""
        # Get an object
        obj = connected_adapter.get()
        original_obj = obj._obj

        # Use the object
        original_obj.use("first_operation")
        assert original_obj.use_count == 1

        # Return to pool (should trigger reset)
        connected_adapter.put(obj)
        assert original_obj.is_reset is True
        assert original_obj.reset_count >= 1

        # Get object again (might be the same reset object)
        obj2 = connected_adapter.get()

        # Verify object was reset if it's the same instance
        if obj2._obj is original_obj:
            assert original_obj.data == {}  # Should be cleared by reset

        connected_adapter.put(obj2)

    def test_clear_pool_functionality(self, connected_adapter):
        """Test pool clearing functionality."""
        # Get some objects first to populate active list
        objects = []
        for _ in range(3):
            obj = connected_adapter.get()
            objects.append(obj)

        # Put them back
        for obj in objects:
            connected_adapter.put(obj)

        # Verify pool has objects
        initial_size = connected_adapter.size()
        assert initial_size > 0

        # Clear the pool
        clear_result = connected_adapter.clear()
        assert clear_result is True

        # Pool should be functional but reset
        assert connected_adapter.is_connected()

        # Should be able to get new objects
        new_obj = connected_adapter.get()
        assert new_obj is not None
        connected_adapter.put(new_obj)


class TestSmartPoolIntegrationConcurrency:
    """Concurrency and thread-safety integration tests."""

    def test_concurrent_get_put_operations(self, connected_adapter):
        """Test concurrent get/put operations across multiple threads."""
        num_threads = 8
        operations_per_thread = 10
        results = queue.Queue()
        errors = queue.Queue()

        def worker(thread_id):
            try:
                for op_id in range(operations_per_thread):
                    # Get object
                    obj = connected_adapter.get()
                    if obj is None:
                        errors.put(f"Thread {thread_id}: Got None object")
                        continue

                    # Use object
                    usage_result = obj._obj.use(f"thread_{thread_id}_op_{op_id}")

                    # Small random delay to simulate work
                    time.sleep(random.uniform(0.001, 0.005))

                    # Return object
                    put_result = connected_adapter.put(obj)
                    if not put_result:
                        errors.put(f"Thread {thread_id}: Failed to put object")

                    results.put((thread_id, op_id, usage_result))

            except Exception as e:
                errors.put(f"Thread {thread_id}: Exception {e}")

        # Start threads
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify results
        assert errors.qsize() == 0, f"Errors occurred: {list(errors.queue)}"
        assert results.qsize() == num_threads * operations_per_thread

        # Verify pool is in good state
        assert connected_adapter.health_check() is True

    def test_concurrent_borrow_context_manager(self, connected_adapter):
        """Test concurrent usage of borrow context manager."""
        num_threads = 6
        duration_seconds = 2
        results = queue.Queue()
        errors = queue.Queue()

        def worker(thread_id):
            try:
                start_time = time.time()
                operation_count = 0

                while time.time() - start_time < duration_seconds:
                    with connected_adapter.borrow() as obj:
                        # Simulate work with object
                        result = obj._obj.use(f"concurrent_op_{operation_count}")
                        time.sleep(0.01)  # Simulate processing time
                        operation_count += 1
                        results.put((thread_id, operation_count, result))

            except Exception as e:
                errors.put(f"Thread {thread_id}: {e}")

        # Start concurrent workers
        threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Verify no errors
        assert errors.qsize() == 0, f"Errors: {list(errors.queue)}"

        # Verify all operations completed
        total_operations = results.qsize()
        assert total_operations > 0

        # Verify pool state
        assert connected_adapter.health_check() is True

    def test_high_contention_stress_test(self, connected_adapter):
        """Test behavior under high contention with many threads."""
        num_threads = 20
        operations_per_thread = 20

        # Create atomic integer helper
        class AtomicInteger:
            def __init__(self, value=0):
                self._value = value
                self._lock = threading.Lock()

            def increment(self):
                with self._lock:
                    self._value += 1

            def get(self):
                with self._lock:
                    return self._value

        success_count = AtomicInteger(0)  # Use the local class
        error_count = AtomicInteger(0)  # Use the local class

        def high_contention_worker(thread_id):
            try:
                for _ in range(operations_per_thread):
                    # Rapid get/put cycles
                    obj = connected_adapter.get()
                    if obj is not None:  # Changed from 'if obj:'
                        obj._obj.use("stress_test")
                        connected_adapter.put(obj)
                        success_count.increment()
                    else:
                        error_count.increment()

            except Exception:
                error_count.increment()

        # Create atomic integer helper
        class AtomicInteger:
            def __init__(self, value=0):
                self._value = value
                self._lock = threading.Lock()

            def increment(self):
                with self._lock:
                    self._value += 1

            def get(self):
                with self._lock:
                    return self._value

        success_count = AtomicInteger(0)
        error_count = AtomicInteger(0)

        # Start high contention test
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(high_contention_worker, i) for i in range(num_threads)]

            # Wait for completion
            for future in as_completed(futures):
                future.result()

        # Verify reasonable success rate
        total_attempts = num_threads * operations_per_thread
        actual_success = success_count.get()
        success_rate = actual_success / total_attempts

        # Should have at least 90% success rate
        assert success_rate >= 0.9, f"Success rate too low: {success_rate}"

        # Pool should still be healthy
        assert connected_adapter.health_check() is True


class TestSmartPoolIntegrationValidation:
    """Object validation and corruption handling integration tests."""

    def test_object_validation_and_replacement(self, connected_adapter):
        """Test that invalid objects are detected and replaced."""
        # Get an object and invalidate it
        obj = connected_adapter.get()
        original_obj = obj._obj

        # Invalidate the object
        original_obj.is_valid = False

        # Return to pool
        connected_adapter.put(obj)

        # Get next object - should be different if validation works
        new_obj = connected_adapter.get()

        # The pool should have detected invalid object and created/provided a new one
        assert new_obj._obj.is_valid is True

        connected_adapter.put(new_obj)

    def test_corrupted_object_destruction(self, connected_adapter):
        """Test that corrupted objects are properly destroyed."""
        initial_instance_count = IntegrationTestObject.get_instance_count()

        # Get object and corrupt it
        obj = connected_adapter.get()
        obj._obj.is_valid = False

        # Put back corrupted object
        connected_adapter.put(obj)

        # Get fresh object - should trigger creation of new object
        fresh_obj = connected_adapter.get()
        assert fresh_obj._obj.is_valid is True

        connected_adapter.put(fresh_obj)

        # New objects should have been created to replace corrupted ones
        final_instance_count = IntegrationTestObject.get_instance_count()
        assert final_instance_count > initial_instance_count

    def test_validation_during_health_check(self, connected_adapter):
        """Test that health check properly validates objects."""
        # Perform initial health check
        assert connected_adapter.health_check() is True

        # Health check should continue to work even after object operations
        for _ in range(5):
            obj = connected_adapter.get()
            obj._obj.use("health_check_test")
            connected_adapter.put(obj)
            assert connected_adapter.health_check() is True


class TestSmartPoolIntegrationPoolBehavior:
    """Pool behavior and configuration integration tests."""

    def test_pool_stats_and_metrics_accuracy(self, connected_adapter):
        """Test that pool statistics accurately reflect operations."""
        # Perform series of operations
        operations = []

        # Get multiple objects
        for _i in range(3):
            obj = connected_adapter.get()
            operations.append(obj)

        # Use objects
        for obj in operations:
            obj._obj.use("stats_test")

        # Return objects
        for obj in operations:
            connected_adapter.put(obj)

        # Check backend info reflects operations
        info = connected_adapter.get_backend_info()
        assert "smartpool_stats" in info
        stats = info["smartpool_stats"]

        # Should have recorded hits/acquisitions
        assert stats.get("hits", 0) > 0 or stats.get("borrows", 0) > 0
        assert stats.get("releases", 0) >= 0

    def test_performance_metrics_collection(self, basic_integration_config):
        """Test performance metrics collection during operations."""
        # Enable performance metrics
        basic_integration_config.enable_performance_metrics = True

        adapter = SmartPoolAdapter(basic_integration_config)
        adapter.connect()

        # Perform operations to generate metrics
        for _ in range(10):
            obj = adapter.get()
            if obj is not None:
                obj._obj.use("metrics_test")
                adapter.put(obj)

        # Get performance metrics
        metrics = adapter.get_performance_metrics()

        # Should have metrics data
        assert "current_snapshot" in metrics
        snapshot = metrics["current_snapshot"]
        assert "total_acquisitions" in snapshot

        adapter.disconnect()

    def test_health_reporting_integration(self, connected_adapter):
        """Test comprehensive health reporting."""
        # Perform some operations first
        for _ in range(5):
            with connected_adapter.borrow() as obj:
                obj._obj.use("health_test")

        # Get health report
        health_report = connected_adapter.get_health_report()

        assert "status" in health_report
        assert health_report["status"] in ["healthy", "warning", "critical", "error"]
        assert "timestamp" in health_report
        assert "issues" in health_report
        assert "warnings" in health_report
        assert "recommendations" in health_report

    def test_dashboard_summary_integration(self, connected_adapter):
        """Test dashboard summary provides useful information."""
        # Perform operations to populate metrics
        for _ in range(3):
            obj = connected_adapter.get()
            if obj is not None:
                connected_adapter.put(obj)

        # Get dashboard summary
        summary = connected_adapter.get_dashboard_summary()

        assert "status" in summary
        assert "metrics" in summary
        assert "performance" in summary
        assert "config" in summary

        # Metrics should have expected keys
        metrics = summary["metrics"]
        assert "pooled_objects" in metrics
        assert "active_objects" in metrics


class TestSmartPoolIntegrationDatabaseScenario:
    """Integration tests simulating database connection pool scenarios."""

    def test_database_connection_pool_simulation(self, database_integration_config):
        """Test SmartPoolAdapter with database connection objects."""
        adapter = SmartPoolAdapter(database_integration_config)
        adapter.connect()

        try:
            # Simulate database operations
            with adapter.borrow() as conn:
                # Execute queries
                result1 = conn._obj.execute_query("SELECT * FROM users")
                assert "Query result" in result1

                # Begin transaction
                conn._obj.begin_transaction()

                # More queries in transaction
                result2 = conn._obj.execute_query("INSERT INTO logs VALUES (...)")
                assert "Query result" in result2

                # Commit
                conn._obj.commit()

            # Connection should be reset and returned to pool
            assert adapter.health_check() is True

            # Get another connection and verify it's reset
            with adapter.borrow() as conn2:
                assert conn2._obj.transaction_count == 0  # Should be reset
                assert conn2._obj.is_connected is True

        finally:
            adapter.disconnect()

    def test_concurrent_database_connections(self, database_integration_config):
        """Test concurrent database connections simulation."""
        adapter = SmartPoolAdapter(database_integration_config)
        adapter.connect()

        try:

            def db_worker(worker_id, operations):
                for op_id in range(operations):
                    with adapter.borrow() as conn:
                        # Simulate database work
                        conn._obj.execute_query(f"SELECT * FROM table_{worker_id}")  # noqa: S608
                        conn._obj.begin_transaction()
                        conn._obj.execute_query(f"UPDATE table SET value={op_id}")  # noqa: S608
                        conn._obj.commit()

            # Run concurrent database workers
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(db_worker, i, 5) for i in range(3)]

                for future in as_completed(futures):
                    future.result()

            # Pool should be healthy after concurrent usage
            assert adapter.health_check() is True

        finally:
            adapter.disconnect()


class TestSmartPoolIntegrationErrorScenarios:
    """Integration tests for error scenarios and recovery."""

    def test_adapter_recovery_after_errors(self, basic_integration_config):
        """Test adapter recovery after various error conditions."""
        adapter = SmartPoolAdapter(basic_integration_config)
        adapter.connect()

        try:
            # Simulate error condition - corrupt some objects
            corrupted_objects = []
            for _ in range(2):
                obj = adapter.get()
                obj._obj.is_valid = False
                corrupted_objects.append(obj)

            # Return corrupted objects
            for obj in corrupted_objects:
                adapter.put(obj)

            # Adapter should recover and provide valid objects
            healthy_obj = adapter.get()
            assert healthy_obj is not None  # Ensure an object is acquired
            assert healthy_obj._obj.is_valid is True
            adapter.put(healthy_obj)

            # After recovery, the pool should be healthy.
            # Give SmartPool a moment to update its internal state if needed.
            time.sleep(0.01)  # Small delay

            # Acquire another object to ensure pool is functional after recovery
            another_obj = adapter.get()
            assert another_obj is not None
            assert another_obj._obj.is_valid is True
            adapter.put(another_obj)

            # Reset stats to clear any corruption/validation failure counts
            adapter.reset_stats()

        finally:
            adapter.disconnect()

    def test_graceful_shutdown_during_operations(self, basic_integration_config):
        """Test graceful shutdown while operations are in progress."""
        adapter = SmartPoolAdapter(basic_integration_config)
        adapter.connect()

        # Get some objects
        active_objects = []
        for _ in range(3):
            obj = adapter.get()
            if obj is not None:
                active_objects.append(obj)

        # Disconnect while objects are still borrowed
        disconnect_result = adapter.disconnect()
        assert disconnect_result is True

        # Should not be able to perform operations after disconnect
        with pytest.raises(AdapterNotConnectedError):
            adapter.get()

    def test_reconnection_capability(self, basic_integration_config):
        """Test adapter reconnection after disconnect."""
        adapter = SmartPoolAdapter(basic_integration_config)

        # Connect, use, disconnect
        adapter.connect()
        obj = adapter.get()
        adapter.put(obj)
        adapter.disconnect()

        # Reconnect
        reconnect_result = adapter.connect()
        assert reconnect_result is True
        assert adapter.is_connected()

        # Should work normally after reconnection
        new_obj = adapter.get()
        assert new_obj is not None
        adapter.put(new_obj)

        adapter.disconnect()
