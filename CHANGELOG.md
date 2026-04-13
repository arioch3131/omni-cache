# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-04-13

### Breaking Changes
- Removed the built-in `file_cache` adapter from source code, factory registry, scripts, examples, and unit tests.
- Removed `CacheBackend.FILE_CACHE`.
- Removed docs API entries tied to `omni_cache.adapters.file_cache`.

### Changed
- Version bumped to `2.0.0` across package metadata, adapter factory metadata, docs, and related tests.
- Release planning files renamed from `*_1.3.0.md` to `*_2.0.0.md`.

### Added
- New `disk` adapter (SQLite metadata index + binary payload files).
- TTL expiration with physical file deletion and optional `renew_on_hit`.
- Periodic and manual cleanup (`cleanup()`), including disk/index reconciliation.
- Batched hit flush on interval/threshold, with non-blocking flush error handling.
- Disk-specific backend info fields and metrics (`expired`, `reclaimed_bytes`, `pending_flush_count`).
- User docs for disk adapter configuration and migration from `file_cache`.

### Known Limitations
- `max_size_bytes` and adaptive eviction policies are not implemented yet.
- Multi-process stress behavior is based on SQLite defaults and remains lightly validated.

### Deferred to 2.1.0
- `max_size_bytes` support and deterministic eviction strategies.
- Expanded integration/performance suites for high-volume and multi-process disk workloads.

## [1.2.0] - 2026-04-11

### Changed
- Version bumped to `1.2.0` across package metadata, adapter factory metadata, docs, and related tests.
- SmartPool dependency baseline moved to `smartpool 2.0.0`.
- SmartPool adapter hot paths optimized:
  - `get`/`put` fast-path behavior refined.
  - `borrow()` now uses a lightweight context manager path (`borrow_fast`) to reduce overhead.
- SmartPool v2 metrics configuration adjusted for compatibility and observability.
- Cache routing and manager internals optimized with adapter caching and lower lock contention for global stats collection.
- SmartPool factory loading made optional when SmartPool dependencies are unavailable.

### Fixed
- Corrupted object replacement behavior in SmartPool flows (integration behavior preserved while keeping `put()` lean).
- Performance metrics under load now report expected acquisition volume in test scenarios.

## [1.1.0] - 2026-03-15

### Added
- SmartPool adapters now allow `initial_size = 0` (schema + validation update).

### Maintenance
- SmartPool adapter tests formatted with Ruff.

## [1.0.0] - 2026-03-01

### Added
- Initial snapshot release.
