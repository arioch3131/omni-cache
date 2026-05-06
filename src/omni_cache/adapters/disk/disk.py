"""Disk-backed cache adapter (SQLite index + binary files)."""

import hashlib
import os
import pickle
import sqlite3
import tempfile
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from omni_cache.adapters.base import BaseCacheAdapter
from omni_cache.adapters.disk.config import DiskAdapterConfig
from omni_cache.core.interfaces import KeyValueInterface


class DiskAdapter(BaseCacheAdapter, KeyValueInterface[str, Any]):
    """Cache adapter storing payloads on disk with an SQLite metadata index."""

    def __init__(self, config: dict[str, Any] | DiskAdapterConfig | None = None):
        """Initialize the adapter state and resolve storage/index paths."""
        if isinstance(config, dict):
            parsed_config = DiskAdapterConfig(**config)
        elif isinstance(config, DiskAdapterConfig):
            parsed_config = config
        else:
            parsed_config = DiskAdapterConfig()

        super().__init__(parsed_config)
        self._config: DiskAdapterConfig = parsed_config

        self._cache_dir = Path(self._config.cache_dir).resolve()
        self._sqlite_path = (
            Path(self._config.sqlite_path).resolve()
            if self._config.sqlite_path
            else self._cache_dir / "index.sqlite3"
        )

        self._conn: sqlite3.Connection | None = None
        self._db_lock = threading.RLock()

        self._pending_hits: dict[str, tuple[float, int]] = {}
        self._pending_hits_lock = threading.RLock()
        self._last_flush_at = time.time()
        self._last_opportunistic_cleanup_at = 0.0
        self._last_reconcile_at = 0.0
        self._reconcile_interval_sec = max(60.0, self._config.cleanup_interval_sec * 5.0)

        self._metrics_lock = threading.RLock()
        self._expired_count = 0
        self._reclaimed_bytes = 0
        self._flush_error_count = 0

        self._maintenance_thread: threading.Thread | None = None
        self._stop_maintenance = threading.Event()

    def _do_connect(self) -> bool:
        """Open SQLite, initialize schema, and start background maintenance."""
        try:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._sqlite_path.parent.mkdir(parents=True, exist_ok=True)

            self._conn = sqlite3.connect(
                str(self._sqlite_path),
                timeout=30,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self._conn.execute("PRAGMA synchronous=NORMAL;")
            self._conn.execute("PRAGMA foreign_keys=ON;")
            self._ensure_schema()
            self._last_opportunistic_cleanup_at = time.time()
            self._last_reconcile_at = self._last_opportunistic_cleanup_at

            # Best-effort startup reconciliation after unclean shutdowns.
            try:
                self._reconcile_disk_index(limit=512)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.warning("Startup reconciliation failed: %s", exc)

            self._stop_maintenance.clear()
            self._maintenance_thread = threading.Thread(
                target=self._maintenance_loop,
                name=f"DiskAdapter-{self._config.name}-Maintenance",
                daemon=True,
            )
            self._maintenance_thread.start()
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to connect disk adapter: %s", exc)
            return False

    def _do_disconnect(self) -> bool:
        """Stop maintenance, flush pending hits, and close SQLite cleanly."""
        try:
            self._stop_maintenance.set()
            if self._maintenance_thread and self._maintenance_thread.is_alive():
                self._maintenance_thread.join(timeout=1.5)

            self._flush_pending_hits()

            with self._db_lock:
                if self._conn is not None:
                    self._conn.close()
                    self._conn = None
            return True
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to disconnect disk adapter: %s", exc)
            return False

    def _do_health_check(self) -> bool:
        """Validate that the SQLite connection is alive."""
        try:
            with self._db_lock:
                if self._conn is None:
                    return False
                self._conn.execute("SELECT 1")
            return True
        except Exception:
            return False

    def set(self, key: str, value: Any, ttl: int | float | None = None) -> bool:
        """Store a value under ``key`` with an optional time-to-live."""
        return self._safe_operation(lambda: self._set_impl(key, value, ttl), "set", False)

    def get(self, key: str, default: Any = None) -> Any:
        """Fetch a value by ``key`` or return ``default`` on miss/failure."""
        return self._safe_operation(lambda: self._get_impl(key, default), "get", default)

    def delete(self, key: str) -> bool:
        """Delete an entry from both index and disk payload storage."""
        return self._safe_operation(lambda: self._delete_impl(key), "delete", False)

    def exists(self, key: str) -> bool:
        """Check whether a key exists and is still valid."""
        return self._safe_operation(lambda: self._exists_impl(key), "exists", False)

    def clear(self) -> bool:
        """Remove every cache entry and associated payload files."""
        return self._safe_operation(self._clear_impl, "clear", False)

    def keys(self) -> Iterator[str]:
        """Return an iterator over non-expired keys."""
        return self._safe_operation(lambda: iter(self._keys_impl()), "keys", iter([]))

    def size(self) -> int:
        """Return the number of non-expired cached entries."""
        return self._safe_operation(self._size_impl, "size", 0)

    def cleanup(self) -> int:
        """Run full maintenance and return removed index row count."""
        return self._safe_operation(self._cleanup_impl, "cleanup", 0)

    def _set_impl(self, key: str, value: Any, ttl: int | float | None) -> bool:
        """Serialize and persist a payload, then upsert metadata in SQLite."""
        now = time.time()
        ttl_seconds = float(ttl) if ttl is not None else self._config.default_ttl
        expires_at = now + ttl_seconds if ttl_seconds is not None else None

        payload = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        relative_path = self._path_for_key(key)
        absolute_path = self._cache_dir / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        self._atomic_write(absolute_path, payload)

        with self._db_lock:
            conn = self._require_conn()
            conn.execute(
                """
                INSERT INTO cache_entries (
                    key, path, size_bytes, created_at, updated_at,
                    expires_at, ttl_seconds, last_hit_at, hit_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, 0)
                ON CONFLICT(key) DO UPDATE SET
                    path=excluded.path,
                    size_bytes=excluded.size_bytes,
                    updated_at=excluded.updated_at,
                    expires_at=excluded.expires_at,
                    ttl_seconds=excluded.ttl_seconds
                """,
                (
                    key,
                    str(relative_path),
                    len(payload),
                    now,
                    now,
                    expires_at,
                    ttl_seconds,
                ),
            )
            conn.commit()
            evicted = self._enforce_max_size_bytes(conn, now)

        self._update_cache_stats("set", success=True, size=self._size_impl())
        for _ in range(evicted):
            self._update_cache_stats("eviction")
        self._maybe_opportunistic_cleanup(now)
        return True

    def _get_impl(self, key: str, default: Any) -> Any:
        """Load and deserialize a payload while enforcing TTL and consistency."""
        now = time.time()
        with self._db_lock:
            conn = self._require_conn()
            row = conn.execute(
                "SELECT path, expires_at, ttl_seconds, size_bytes FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            self._update_cache_stats("get", success=False, size=self._size_impl())
            return default

        path, expires_at, ttl_seconds, size_bytes = row
        if expires_at is not None and now >= float(expires_at):
            self._delete_expired_entry(key, path, int(size_bytes) if size_bytes is not None else 0)
            self._update_cache_stats("get", success=False, size=self._size_impl())
            return default

        payload_path = self._cache_dir / path
        if not payload_path.exists():
            with self._db_lock:
                conn = self._require_conn()
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
            self._update_cache_stats("get", success=False, size=self._size_impl())
            return default

        try:
            payload = payload_path.read_bytes()
            # Payloads are produced by this adapter itself and read from local storage.
            value = pickle.loads(payload)  # noqa: S301
        except Exception:  # pylint: disable=broad-exception-caught
            self._delete_impl(key)
            self._update_cache_stats("get", success=False, size=self._size_impl())
            return default

        self._register_hit(key, now)
        if self._should_renew(now, expires_at, ttl_seconds):
            with self._db_lock:
                conn = self._require_conn()
                conn.execute(
                    "UPDATE cache_entries SET expires_at = ?, updated_at = ? WHERE key = ?",
                    (now + float(ttl_seconds), now, key),
                )
                conn.commit()

        self._maybe_flush_hits(now)
        self._maybe_opportunistic_cleanup(now)
        self._update_cache_stats("get", success=True, size=self._size_impl())
        return value

    def _delete_impl(self, key: str) -> bool:
        """Delete a key from index and remove its corresponding payload file."""
        with self._db_lock:
            conn = self._require_conn()
            row = conn.execute("SELECT path FROM cache_entries WHERE key = ?", (key,)).fetchone()
            if row is None:
                return False

            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()

        path = self._cache_dir / row[0]
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return False

        self._update_cache_stats("delete", success=True, size=self._size_impl())
        return True

    def _exists_impl(self, key: str) -> bool:
        """Check key presence and repair stale index/file states when needed."""
        now = time.time()
        with self._db_lock:
            conn = self._require_conn()
            row = conn.execute(
                "SELECT path, expires_at, size_bytes FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()

        if row is None:
            return False

        path, expires_at, size_bytes = row
        if expires_at is not None and now >= float(expires_at):
            self._delete_expired_entry(key, path, int(size_bytes) if size_bytes is not None else 0)
            return False

        if not (self._cache_dir / path).exists():
            with self._db_lock:
                conn = self._require_conn()
                conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                conn.commit()
            return False

        return True

    def _clear_impl(self) -> bool:
        """Clear all metadata rows and best-effort delete all payload files."""
        with self._db_lock:
            conn = self._require_conn()
            rows = conn.execute("SELECT path FROM cache_entries").fetchall()
            conn.execute("DELETE FROM cache_entries")
            conn.commit()

        for (relative_path,) in rows:
            try:
                (self._cache_dir / relative_path).unlink(missing_ok=True)
            except OSError:
                pass

        with self._pending_hits_lock:
            self._pending_hits.clear()
        self._update_cache_stats("delete", success=True, size=0)
        return True

    def _keys_impl(self) -> list[str]:
        """Return a snapshot list of non-expired keys."""
        now = time.time()
        with self._db_lock:
            conn = self._require_conn()
            rows = conn.execute(
                "SELECT key FROM cache_entries WHERE expires_at IS NULL OR expires_at > ?",
                (now,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _size_impl(self) -> int:
        """Return current non-expired row count from SQLite."""
        now = time.time()
        with self._db_lock:
            conn = self._require_conn()
            row = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at IS NULL OR expires_at > ?",
                (now,),
            ).fetchone()
        return int(row[0] if row else 0)

    def _maintenance_loop(self) -> None:
        """Run periodic cleanup, hit flush, and reconciliation in background."""
        while not self._stop_maintenance.wait(self._config.cleanup_interval_sec):
            try:
                self._cleanup_expired()
                self._flush_pending_hits()
                self._maybe_reconcile_disk_index(time.time())
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._logger.debug("Disk maintenance iteration failed: %s", exc)

    def _cleanup_expired(self, limit: int | None = None) -> int:
        """Remove expired rows/files and update expiration/reclamation counters."""
        now = time.time()
        with self._db_lock:
            conn = self._require_conn()
            query = """
                SELECT key, path, size_bytes
                FROM cache_entries
                WHERE expires_at IS NOT NULL AND expires_at <= ?
            """
            params: tuple[Any, ...] = (now,)
            if limit is not None:
                query += " LIMIT ?"
                params = (now, limit)

            rows = conn.execute(query, params).fetchall()
            if not rows:
                return 0

            conn.executemany("DELETE FROM cache_entries WHERE key = ?", [(row[0],) for row in rows])
            conn.commit()

        reclaimed = 0
        for _, relative_path, size_bytes in rows:
            try:
                (self._cache_dir / relative_path).unlink(missing_ok=True)
                reclaimed += int(size_bytes) if size_bytes is not None else 0
            except OSError:
                pass

        with self._metrics_lock:
            self._expired_count += len(rows)
            self._reclaimed_bytes += reclaimed

        return len(rows)

    def _ensure_schema(self) -> None:
        """Create the SQLite schema and indexes when they do not exist."""
        with self._db_lock:
            conn = self._require_conn()
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    expires_at REAL,
                    ttl_seconds REAL,
                    last_hit_at REAL,
                    hit_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_cache_entries_expires_at
                ON cache_entries(expires_at)
                """
            )
            conn.commit()

    def _should_renew(
        self, now: float, expires_at: float | None, ttl_seconds: float | None
    ) -> bool:
        """Return whether sliding TTL renewal should be applied on access."""
        if not self._config.renew_on_hit or expires_at is None or ttl_seconds is None:
            return False

        remaining = float(expires_at) - now
        return remaining <= (float(ttl_seconds) * self._config.renew_threshold)

    def _register_hit(self, key: str, now: float) -> None:
        """Buffer hit updates in memory for batched persistence."""
        with self._pending_hits_lock:
            _, existing_count = self._pending_hits.get(key, (now, 0))
            self._pending_hits[key] = (now, existing_count + 1)

    def _maybe_flush_hits(self, now: float) -> None:
        """Trigger hit flush based on interval or pending-key threshold."""
        with self._pending_hits_lock:
            pending_size = len(self._pending_hits)
            should_flush_count = pending_size >= self._config.batch_flush_max_pending
            should_flush_interval = (
                now - self._last_flush_at
            ) >= self._config.batch_flush_interval_sec

        if should_flush_count or should_flush_interval:
            self._flush_pending_hits()

    def _flush_pending_hits(self) -> None:
        """Flush buffered hit counters with safe requeue on DB failure."""
        with self._pending_hits_lock:
            if not self._pending_hits:
                self._last_flush_at = time.time()
                return
            pending = self._pending_hits
            self._pending_hits = {}

        try:
            with self._db_lock:
                conn = self._require_conn()
                conn.executemany(
                    """
                    UPDATE cache_entries
                    SET last_hit_at = ?, hit_count = hit_count + ?
                    WHERE key = ?
                    """,
                    [(last_hit_at, count, key) for key, (last_hit_at, count) in pending.items()],
                )
                conn.commit()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.warning("Failed to flush pending hits: %s", exc)
            with self._metrics_lock:
                self._flush_error_count += 1

            with self._pending_hits_lock:
                for key, (last_hit_at, count) in pending.items():
                    existing_hit_at, existing_count = self._pending_hits.get(key, (last_hit_at, 0))
                    self._pending_hits[key] = (
                        max(existing_hit_at, last_hit_at),
                        existing_count + count,
                    )
        finally:
            self._last_flush_at = time.time()

    def _cleanup_impl(self) -> int:
        """Run full maintenance cycle and return removed index row count."""
        removed_expired = self._cleanup_expired()
        reconciliation = self._reconcile_disk_index()
        return removed_expired + reconciliation["stale_rows_removed"]

    def _enforce_max_size_bytes(self, conn: sqlite3.Connection, now: float) -> int:
        """Evict oldest non-expired entries when max_size_bytes is configured and exceeded."""
        if self._config.max_size_bytes is None:
            return 0

        row = conn.execute(
            """
            SELECT COALESCE(SUM(size_bytes), 0)
            FROM cache_entries
            WHERE expires_at IS NULL OR expires_at > ?
            """,
            (now,),
        ).fetchone()
        current_size_bytes = int(row[0] if row else 0)
        overflow = current_size_bytes - self._config.max_size_bytes
        if overflow <= 0:
            return 0

        rows = conn.execute(
            """
            SELECT key, path, size_bytes
            FROM cache_entries
            WHERE expires_at IS NULL OR expires_at > ?
            ORDER BY updated_at ASC
            """,
            (now,),
        ).fetchall()
        if not rows:
            return 0

        bytes_to_free = overflow
        rows_to_evict: list[tuple[str, str]] = []
        for key, path, size_bytes in rows:
            rows_to_evict.append((str(key), str(path)))
            bytes_to_free -= int(size_bytes) if size_bytes is not None else 0
            if bytes_to_free <= 0:
                break

        if not rows_to_evict:
            return 0

        conn.executemany("DELETE FROM cache_entries WHERE key = ?", [(row[0],) for row in rows_to_evict])
        conn.commit()

        for _, relative_path in rows_to_evict:
            try:
                (self._cache_dir / relative_path).unlink(missing_ok=True)
            except OSError:
                continue

        return len(rows_to_evict)

    def _delete_expired_entry(self, key: str, path: str, size_bytes: int) -> None:
        """Delete a known expired key and account reclaimed bytes."""
        with self._db_lock:
            conn = self._require_conn()
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()

        try:
            (self._cache_dir / path).unlink(missing_ok=True)
            reclaimed = size_bytes
        except OSError:
            reclaimed = 0

        with self._metrics_lock:
            self._expired_count += 1
            self._reclaimed_bytes += reclaimed

    def _maybe_opportunistic_cleanup(self, now: float) -> None:
        """Run lightweight maintenance opportunistically from hot paths."""
        if (now - self._last_opportunistic_cleanup_at) < self._config.cleanup_interval_sec:
            return

        self._last_opportunistic_cleanup_at = now
        try:
            self._cleanup_expired(limit=32)
            self._maybe_reconcile_disk_index(now)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._logger.debug("Opportunistic cleanup skipped due to error: %s", exc)

    def _maybe_reconcile_disk_index(self, now: float) -> None:
        """Run reconciliation only when its interval has elapsed."""
        if (now - self._last_reconcile_at) < self._reconcile_interval_sec:
            return
        self._last_reconcile_at = now
        self._reconcile_disk_index(limit=512)

    def _reconcile_disk_index(self, limit: int | None = None) -> dict[str, int]:
        """Reconcile disk/index state by pruning stale rows and orphan files."""
        with self._db_lock:
            conn = self._require_conn()
            query = "SELECT key, path, size_bytes FROM cache_entries"
            params: tuple[Any, ...] = ()
            if limit is not None:
                query += " LIMIT ?"
                params = (limit,)
            rows = conn.execute(query, params).fetchall()

            stale_keys: list[tuple[str]] = []
            indexed_paths: set[str] = set()
            for key, relative_path, _ in rows:
                indexed_paths.add(str(relative_path))
                if not (self._cache_dir / str(relative_path)).exists():
                    stale_keys.append((str(key),))

            if stale_keys:
                conn.executemany("DELETE FROM cache_entries WHERE key = ?", stale_keys)
                conn.commit()

        # When reconciliation runs on a limited row window (startup/opportunistic mode),
        # indexed_paths is incomplete. In that mode, skip orphan-file sweeping to avoid
        # deleting valid payload files that are simply outside the selected window.
        if limit is not None:
            return {
                "stale_rows_removed": len(stale_keys),
                "orphan_files_removed": 0,
                "orphan_bytes_reclaimed": 0,
            }

        orphan_files_removed = 0
        orphan_bytes_reclaimed = 0
        for payload_path in self._cache_dir.rglob("*.bin"):
            try:
                relative_path = payload_path.relative_to(self._cache_dir).as_posix()
            except ValueError:
                continue

            if relative_path in indexed_paths:
                continue

            try:
                orphan_bytes_reclaimed += payload_path.stat().st_size
                payload_path.unlink(missing_ok=True)
                orphan_files_removed += 1
            except OSError:
                continue

        if orphan_bytes_reclaimed:
            with self._metrics_lock:
                self._reclaimed_bytes += orphan_bytes_reclaimed

        return {
            "stale_rows_removed": len(stale_keys),
            "orphan_files_removed": orphan_files_removed,
            "orphan_bytes_reclaimed": orphan_bytes_reclaimed,
        }

    def get_backend_info(self) -> dict[str, Any]:
        """Get detailed information about the disk backend."""
        info = super().get_backend_info()
        with self._pending_hits_lock:
            pending_flush_count = len(self._pending_hits)
        with self._metrics_lock:
            expired = self._expired_count
            reclaimed_bytes = self._reclaimed_bytes
            flush_errors = self._flush_error_count

        info.update(
            {
                "storage_type": "sqlite_index+binary_files",
                "cache_dir": str(self._cache_dir),
                "sqlite_path": str(self._sqlite_path),
                "max_size_bytes": self._config.max_size_bytes,
                "renew_on_hit": self._config.renew_on_hit,
                "cleanup_interval_sec": self._config.cleanup_interval_sec,
                "pending_flush_count": pending_flush_count,
                "disk_metrics": {
                    "expired": expired,
                    "reclaimed_bytes": reclaimed_bytes,
                    "pending_flush_count": pending_flush_count,
                    "flush_error_count": flush_errors,
                },
            }
        )
        return info

    def _path_for_key(self, key: str) -> Path:
        """Return deterministic sharded payload path derived from key hash."""
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return Path(digest[0:2]) / digest[2:4] / f"{digest}.bin"

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        """Write to a temp file and atomically replace the target payload."""
        fd, tmp_path = tempfile.mkstemp(prefix="omni_cache_", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _require_conn(self) -> sqlite3.Connection:
        """Return the active SQLite connection or raise if uninitialized."""
        if self._conn is None:
            raise RuntimeError("Disk adapter SQLite connection is not initialized")
        return self._conn
