"""Performance tests for DiskAdapter under realistic local workloads."""

import os
import statistics
import time

import pytest

from omni_cache.adapters.disk import DiskAdapter, DiskAdapterConfig

pytestmark = pytest.mark.slow


@pytest.fixture
def performance_adapter(tmp_path):
    """Connected DiskAdapter tuned for stable benchmark-like tests."""
    config = DiskAdapterConfig(
        name="disk_performance",
        cache_dir=str(tmp_path / "disk_perf_cache"),
        cleanup_interval_sec=30.0,
        batch_flush_interval_sec=0.02,
        batch_flush_max_pending=100,
        default_ttl=60.0,
    )

    adapter = DiskAdapter(config)
    assert adapter.connect() is True
    try:
        yield adapter
    finally:
        if adapter.is_connected():
            adapter.clear()
            adapter.disconnect()


@pytest.mark.integration
def test_bulk_set_get_throughput(performance_adapter):
    """Measure bulk set/get throughput with conservative non-flaky thresholds."""
    adapter = performance_adapter
    operation_count = 1200

    start_set = time.perf_counter()
    for index in range(operation_count):
        assert adapter.set(f"perf:set:{index}", {"v": index}) is True
    set_duration = time.perf_counter() - start_set

    start_get = time.perf_counter()
    for index in range(operation_count):
        assert adapter.get(f"perf:set:{index}") == {"v": index}
    get_duration = time.perf_counter() - start_get

    set_rate = operation_count / set_duration
    get_rate = operation_count / get_duration

    min_set_rate = 70 if os.getenv("CI", "").lower() == "true" else 120
    min_get_rate = 100 if os.getenv("CI", "").lower() == "true" else 180

    assert set_rate > min_set_rate
    assert get_rate > min_get_rate


@pytest.mark.integration
def test_batch_operations_throughput(performance_adapter):
    """Measure throughput of set_many/get_many/delete_many operations."""
    adapter = performance_adapter
    batch_size = 600
    payload = {f"perf:batch:{index}": {"idx": index} for index in range(batch_size)}
    keys = list(payload.keys())

    start_set_many = time.perf_counter()
    set_result = adapter.set_many(payload, ttl=30)
    set_many_duration = time.perf_counter() - start_set_many

    start_get_many = time.perf_counter()
    get_result = adapter.get_many(keys)
    get_many_duration = time.perf_counter() - start_get_many

    start_delete_many = time.perf_counter()
    delete_result = adapter.delete_many(keys)
    delete_many_duration = time.perf_counter() - start_delete_many

    assert all(set_result.values())
    assert get_result == payload
    assert all(delete_result.values())

    assert (batch_size / set_many_duration) > 80
    assert (batch_size / get_many_duration) > 90
    assert (batch_size / delete_many_duration) > 80


@pytest.mark.integration
def test_hot_read_latency_distribution(performance_adapter):
    """Validate average and p95 read latency on a warm working set."""
    adapter = performance_adapter
    key_count = 400
    sample_count = 2000

    for index in range(key_count):
        assert adapter.set(f"perf:latency:{index}", {"index": index}) is True

    latencies = []
    for sample in range(sample_count):
        key = f"perf:latency:{sample % key_count}"
        start_time = time.perf_counter()
        value = adapter.get(key)
        latencies.append(time.perf_counter() - start_time)
        assert value is not None

    average_latency = statistics.mean(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    assert average_latency < 0.01
    assert p95_latency < 0.03


@pytest.mark.integration
def test_high_volume_dataset_retrieval_stability(performance_adapter):
    """High key volume should remain retrievable with stable hit quality."""
    adapter = performance_adapter
    key_count = 5000

    start_set = time.perf_counter()
    for index in range(key_count):
        assert adapter.set(f"perf:volume:{index}", {"payload": "x" * 128, "index": index}) is True
    set_duration = time.perf_counter() - start_set

    # Read only a large sample to keep runtime predictable while still stressing index lookups.
    sample_count = 2000
    start_get = time.perf_counter()
    for index in range(sample_count):
        key_index = (index * 7) % key_count
        assert adapter.get(f"perf:volume:{key_index}") == {
            "payload": "x" * 128,
            "index": key_index,
        }
    get_duration = time.perf_counter() - start_get

    assert adapter.size() == key_count
    assert (key_count / set_duration) > 70
    assert (sample_count / get_duration) > 130


@pytest.mark.integration
def test_cleanup_reconcile_cost_under_volume(performance_adapter):
    """Cleanup on a large expired set should finish in bounded time."""
    adapter = performance_adapter
    entry_count = 2500

    for index in range(entry_count):
        assert adapter.set(f"perf:expire:{index}", {"idx": index}, ttl=0.15) is True

    time.sleep(0.22)
    start_cleanup = time.perf_counter()
    removed_rows = adapter.cleanup()
    cleanup_duration = time.perf_counter() - start_cleanup

    # A small margin is accepted for rows already opportunistically cleaned.
    assert removed_rows >= (entry_count - 128)
    assert cleanup_duration < 8.0
    assert adapter.size() == 0
