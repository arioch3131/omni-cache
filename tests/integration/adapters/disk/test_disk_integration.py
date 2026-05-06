"""Integration tests for the disk adapter with real filesystem persistence."""

import multiprocessing
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from omni_cache.adapters.disk import DiskAdapter, DiskAdapterConfig


@pytest.fixture
def disk_integration_adapter(tmp_path):
    """Connected DiskAdapter isolated in a temporary directory."""
    config = DiskAdapterConfig(
        name="disk_integration",
        cache_dir=str(tmp_path / "disk_cache"),
        cleanup_interval_sec=0.2,
        batch_flush_interval_sec=0.05,
        batch_flush_max_pending=25,
        default_ttl=2.0,
    )
    adapter = DiskAdapter(config)
    assert adapter.connect() is True
    try:
        yield adapter
    finally:
        if adapter.is_connected():
            adapter.disconnect()


@pytest.mark.integration
def test_lifecycle_and_persistence_across_reconnect(tmp_path):
    """Values should survive adapter restart when the cache directory is reused."""
    config = DiskAdapterConfig(
        name="disk_lifecycle",
        cache_dir=str(tmp_path / "persistent_cache"),
        cleanup_interval_sec=0.2,
        batch_flush_interval_sec=0.05,
        batch_flush_max_pending=10,
    )

    first_adapter = DiskAdapter(config)
    assert first_adapter.connect() is True
    try:
        assert first_adapter.set("session:user:1", {"role": "admin"}) is True
        assert first_adapter.set("settings", {"theme": "dark", "lang": "fr"}) is True
        assert first_adapter.size() == 2
    finally:
        assert first_adapter.disconnect() is True

    second_adapter = DiskAdapter(config)
    assert second_adapter.connect() is True
    try:
        assert second_adapter.get("session:user:1") == {"role": "admin"}
        assert second_adapter.get("settings") == {"theme": "dark", "lang": "fr"}
        assert second_adapter.exists("session:user:1") is True
    finally:
        second_adapter.disconnect()


@pytest.mark.integration
def test_ttl_cleanup_and_non_expired_data_kept(disk_integration_adapter):
    """Expired entries should be cleaned while valid entries remain available."""
    adapter = disk_integration_adapter

    assert adapter.set("hot", "keep", ttl=2.0) is True
    assert adapter.set("short:1", "expire", ttl=0.12) is True
    assert adapter.set("short:2", "expire", ttl=0.12) is True

    time.sleep(0.18)
    removed = adapter.cleanup()

    assert removed >= 2
    assert adapter.get("short:1") is None
    assert adapter.get("short:2") is None
    assert adapter.get("hot") == "keep"
    assert adapter.size() == 1


@pytest.mark.integration
def test_batch_operations_end_to_end(disk_integration_adapter):
    """set_many/get_many/delete_many should be correct end-to-end."""
    adapter = disk_integration_adapter
    payload = {f"batch:{index}": {"index": index} for index in range(120)}
    keys = list(payload.keys())

    set_result = adapter.set_many(payload, ttl=5)
    get_result = adapter.get_many(keys)
    delete_result = adapter.delete_many(keys)

    assert all(set_result.values())
    assert get_result == payload
    assert all(delete_result.values())
    assert adapter.size() == 0


@pytest.mark.integration
def test_concurrent_mixed_workload_stability(disk_integration_adapter):
    """Concurrent set/get/delete operations should complete without corruption."""
    adapter = disk_integration_adapter
    worker_count = 6
    operations_per_worker = 120

    def worker(worker_id: int) -> int:
        local_operations = 0
        for index in range(operations_per_worker):
            key = f"worker:{worker_id}:key:{index}"
            value = {"worker": worker_id, "index": index}

            assert adapter.set(key, value, ttl=5.0) is True
            local_operations += 1

            assert adapter.get(key) == value
            local_operations += 1

            if index % 5 == 0:
                adapter.delete(key)
                local_operations += 1

        return local_operations

    total_operations = 0
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(worker, worker_id) for worker_id in range(worker_count)]
        for future in as_completed(futures):
            total_operations += future.result()

    assert total_operations > (worker_count * operations_per_worker)
    assert adapter.health_check() is True

    for worker_id in range(worker_count):
        for index in range(operations_per_worker):
            key = f"worker:{worker_id}:key:{index}"
            if index % 5 == 0:
                assert adapter.get(key) is None
            else:
                assert adapter.get(key) == {"worker": worker_id, "index": index}


def _disk_mp_writer_worker(cache_dir: str, worker_id: int, start: int, count: int) -> int:
    """Write a deterministic key range from a dedicated process."""
    config = DiskAdapterConfig(
        name=f"disk_mp_writer_{worker_id}",
        cache_dir=cache_dir,
        cleanup_interval_sec=60.0,
        batch_flush_interval_sec=0.05,
        batch_flush_max_pending=64,
        default_ttl=30.0,
    )
    adapter = DiskAdapter(config)
    assert adapter.connect() is True
    written = 0
    try:
        for offset in range(count):
            key_index = start + offset
            key = f"mp:key:{key_index}"
            value = {"worker": worker_id, "index": key_index}
            assert adapter.set(key, value) is True
            written += 1
        return written
    finally:
        adapter.disconnect()


@pytest.mark.integration
def test_multi_process_shared_cache_high_volume(tmp_path):
    """Multiple processes should safely share one disk cache directory."""
    cache_dir = str(tmp_path / "disk_mp_shared")
    process_count = 4
    per_process_writes = 400
    total_keys = process_count * per_process_writes

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=process_count) as pool:
        jobs = [
            pool.apply_async(
                _disk_mp_writer_worker,
                (cache_dir, worker_id, worker_id * per_process_writes, per_process_writes),
            )
            for worker_id in range(process_count)
        ]
        written_counts = [job.get(timeout=120) for job in jobs]

    assert sum(written_counts) == total_keys

    verifier = DiskAdapter(
        DiskAdapterConfig(
            name="disk_mp_verifier",
            cache_dir=cache_dir,
            cleanup_interval_sec=60.0,
            batch_flush_interval_sec=0.05,
            batch_flush_max_pending=64,
            default_ttl=30.0,
        )
    )
    assert verifier.connect() is True
    try:
        assert verifier.health_check() is True
        observed_size = verifier.size()
        assert observed_size >= int(total_keys * 0.99)

        found = 0
        for key_index in range(total_keys):
            key = f"mp:key:{key_index}"
            value = verifier.get(key)
            if value is None:
                continue
            assert value == {
                "worker": key_index // per_process_writes,
                "index": key_index,
            }
            found += 1
        assert found >= int(total_keys * 0.99)
    finally:
        verifier.disconnect()
