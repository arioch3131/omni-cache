"""Unit tests for disk adapter."""

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

from omni_cache.adapters.disk import DiskAdapter, DiskAdapterConfig


def _build_adapter(tmp_path, **kwargs):
    config = DiskAdapterConfig(cache_dir=str(tmp_path / "disk_cache"), **kwargs)
    adapter = DiskAdapter(config)
    assert adapter.connect() is True
    return adapter


def test_set_get_delete_cycle(tmp_path):
    adapter = _build_adapter(tmp_path)
    try:
        assert adapter.set("alpha", {"a": 1}) is True
        assert adapter.get("alpha") == {"a": 1}
        assert adapter.exists("alpha") is True
        assert adapter.delete("alpha") is True
        assert adapter.get("alpha") is None
        assert adapter.exists("alpha") is False
    finally:
        adapter.disconnect()


def test_ttl_expiration(tmp_path):
    adapter = _build_adapter(tmp_path)
    try:
        assert adapter.set("k", "v", ttl=0.15) is True
        assert adapter.get("k") == "v"
        time.sleep(0.2)
        assert adapter.get("k") is None
    finally:
        adapter.disconnect()


def test_clear_keys_size(tmp_path):
    adapter = _build_adapter(tmp_path)
    try:
        adapter.set("k1", "v1")
        adapter.set("k2", "v2")
        assert adapter.size() == 2
        assert set(adapter.keys()) == {"k1", "k2"}
        assert adapter.clear() is True
        assert adapter.size() == 0
        assert list(adapter.keys()) == []
    finally:
        adapter.disconnect()


def test_renew_on_hit(tmp_path):
    adapter = _build_adapter(
        tmp_path,
        renew_on_hit=True,
        renew_threshold=0.5,
        default_ttl=0.3,
        batch_flush_interval_sec=0.05,
    )
    try:
        assert adapter.set("renew", "ok") is True
        time.sleep(0.2)
        assert adapter.get("renew") == "ok"
        time.sleep(0.2)
        assert adapter.get("renew") == "ok"
    finally:
        adapter.disconnect()


def test_no_renewal_outside_window(tmp_path):
    adapter = _build_adapter(
        tmp_path,
        renew_on_hit=True,
        renew_threshold=0.2,
        default_ttl=0.4,
        batch_flush_interval_sec=100.0,
    )
    try:
        assert adapter.set("renew-late", "ok") is True
        time.sleep(0.1)  # Still outside the renewal threshold window.
        assert adapter.get("renew-late") == "ok"
        time.sleep(0.33)
        assert adapter.get("renew-late") is None
    finally:
        adapter.disconnect()


def test_expired_entry_deletes_physical_file(tmp_path):
    adapter = _build_adapter(tmp_path, batch_flush_interval_sec=100.0)
    try:
        key = "expire-delete-file"
        assert adapter.set(key, {"x": 1}, ttl=0.1) is True
        payload_path = Path(adapter._cache_dir) / adapter._path_for_key(key)
        assert payload_path.exists()

        time.sleep(0.14)
        assert adapter.get(key) is None
        assert not payload_path.exists()
    finally:
        adapter.disconnect()


def test_batch_flush_updates_hit_count(tmp_path):
    adapter = _build_adapter(
        tmp_path,
        batch_flush_max_pending=2,
        batch_flush_interval_sec=100.0,
    )
    try:
        assert adapter.set("a", 1) is True
        assert adapter.set("b", 2) is True

        assert adapter.get("a") == 1
        assert adapter.get("b") == 2

        with sqlite3.connect(str(adapter._sqlite_path)) as conn:
            a_hits = conn.execute(
                "SELECT hit_count FROM cache_entries WHERE key = ?",
                ("a",),
            ).fetchone()[0]
            b_hits = conn.execute(
                "SELECT hit_count FROM cache_entries WHERE key = ?",
                ("b",),
            ).fetchone()[0]

        assert a_hits == 1
        assert b_hits == 1
    finally:
        adapter.disconnect()


def test_disconnect_flushes_pending_hits(tmp_path):
    adapter = _build_adapter(
        tmp_path,
        batch_flush_max_pending=1000,
        batch_flush_interval_sec=100.0,
    )
    key = "flush-on-disconnect"
    assert adapter.set(key, "v") is True
    assert adapter.get(key) == "v"
    assert adapter.disconnect() is True

    with sqlite3.connect(str(tmp_path / "disk_cache" / "index.sqlite3")) as conn:
        hits = conn.execute(
            "SELECT hit_count FROM cache_entries WHERE key = ?",
            (key,),
        ).fetchone()[0]
    assert hits == 1


def test_file_missing_index_row_cleaned_on_get(tmp_path):
    adapter = _build_adapter(tmp_path)
    try:
        key = "broken-file"
        assert adapter.set(key, "value") is True
        payload_path = Path(adapter._cache_dir) / adapter._path_for_key(key)
        payload_path.unlink(missing_ok=True)

        assert adapter.get(key) is None
        assert adapter.exists(key) is False
        assert key not in list(adapter.keys())
    finally:
        adapter.disconnect()


def test_cleanup_removes_orphan_file_without_index_row(tmp_path):
    adapter = _build_adapter(tmp_path, cleanup_interval_sec=3600.0)
    try:
        key = "orphan"
        orphan_path = Path(adapter._cache_dir) / adapter._path_for_key(key)
        orphan_path.parent.mkdir(parents=True, exist_ok=True)
        orphan_path.write_bytes(b"orphan-bytes")

        assert orphan_path.exists()
        cleaned_rows = adapter.cleanup()
        assert cleaned_rows == 0
        assert not orphan_path.exists()
    finally:
        adapter.disconnect()


def test_cleanup_is_idempotent(tmp_path):
    adapter = _build_adapter(tmp_path, cleanup_interval_sec=3600.0)
    try:
        assert adapter.set("ttl-k", "v", ttl=0.1) is True
        time.sleep(0.14)
        first = adapter.cleanup()
        second = adapter.cleanup()

        assert first >= 1
        assert second == 0
    finally:
        adapter.disconnect()


def test_flush_failure_does_not_break_hot_path(tmp_path):
    adapter = _build_adapter(
        tmp_path,
        batch_flush_max_pending=1,
        batch_flush_interval_sec=1.0,
    )
    try:
        assert adapter.set("k", "v") is True
        adapter._register_hit("k", time.time())
        with patch.object(adapter, "_require_conn", side_effect=RuntimeError("db down")):
            # Should not raise, and pending hit should be preserved.
            adapter._flush_pending_hits()

        info = adapter.get_backend_info()
        assert info["pending_flush_count"] >= 1
        assert info["disk_metrics"]["flush_error_count"] >= 1
    finally:
        adapter.disconnect()


def test_disk_backend_info_exposes_extended_metrics(tmp_path):
    adapter = _build_adapter(tmp_path, batch_flush_interval_sec=100.0)
    try:
        assert adapter.set("expire-me", "v", ttl=0.1) is True
        time.sleep(0.14)
        assert adapter.get("expire-me") is None

        info = adapter.get_backend_info()
        assert info["backend"] == "disk"
        assert info["storage_type"] == "sqlite_index+binary_files"
        assert "disk_metrics" in info
        assert info["disk_metrics"]["expired"] >= 1
        assert "reclaimed_bytes" in info["disk_metrics"]
        assert "pending_flush_count" in info["disk_metrics"]
    finally:
        adapter.disconnect()


def test_max_size_bytes_evicts_oldest_entry(tmp_path):
    adapter = _build_adapter(tmp_path, max_size_bytes=300)
    try:
        assert adapter.set("k1", b"x" * 100) is True
        time.sleep(0.01)
        assert adapter.set("k2", b"y" * 100) is True
        time.sleep(0.01)
        assert adapter.set("k3", b"z" * 100) is True

        assert adapter.size() == 2
        assert adapter.get("k1") is None
        assert adapter.get("k2") == b"y" * 100
        assert adapter.get("k3") == b"z" * 100
    finally:
        adapter.disconnect()
