# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
this project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-09-08

### Added

- Modular Python services for HTTP, Salesforce transport, lifecycle,
  constraint data, semantic analysis, and private recovery artifacts.
- Exact-version guarded CML fetch, compare, deploy, backup, restore, and
  post-write verification.
- Local CodeMirror editor bundle, structured diagnostics, semantic comparison,
  virtualized large comparisons, selectable backups, retention controls, and
  cross-process deployment locking.
- Reusable primary/target editors, inline best-practice diagnostics, accessible
  typed confirmations, session-only draft recovery, shortcut help, and
  cross-engine 200% zoom acceptance coverage.
- Read-only contract harness, tracked Python and browser tests, CI, and
  reproducible release archives with SHA-256 checksums.

### Changed

- Simplified primary navigation from five views to four by keeping
  best-practice checking only in Fetch & Deploy.
- Added an obvious **Hide best practices** action that removes the inline
  report and clears editor diagnostics; rerunning the check shows fresh results.
- Reduced deployment readiness to a read-only exact-target
  Active/Inactive/write-blocked status check. Removed runtime Context Definition
  reference/path discovery, evidence payloads, and related describe/query work;
  deployment still rechecks exact target status server-side.

### Security

- Localhost Host/Origin checks, per-process CSRF protection, request-size
  limits, restrictive response headers, path-safe assets, write allowlists,
  private atomic artifacts, and fail-closed ownership/status checks.

[1.0.0]: https://github.com/mrityu96/SalesforcesTool/releases/tag/v1.0.0
