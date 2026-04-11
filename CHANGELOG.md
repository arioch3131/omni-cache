# Changelog

All notable changes to this project will be documented in this file.

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
