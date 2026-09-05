# CML Tool Modernization — Change Summary

**Snapshot:** September 5, 2026  
**Validation status:** 108 Python tests passing; 8 Playwright browser tests
present (the sandbox Chromium process crashed before test execution)

This document summarizes the completed CML Tool modernization: what existed
before, what exists now, what was added or changed, and what was cleaned up or
retired.

## Important Git note

The entire `salesforce-cml-tool/` directory is currently untracked in the
parent Git repository, so Git cannot provide an authoritative historical
file-by-file diff for the modernization. When the project is added, production
commits should include `README.md`, `.gitignore`,
`Start Here - CML Tool/`, and `main/`.

The root `.gitignore` excludes the entire `development/` directory; do not
force-add it. That workspace contains tests, npm metadata and dependencies,
browser binaries/results/caches, and potentially sensitive runtime/recovery
artifacts. The classifications below are based on implementation history and
the current project structure.

## Executive summary

Earlier, most backend, UI, Salesforce transport, CML analysis, HTTP routing,
artifact handling, lifecycle operations, and constraint-data behavior lived in
one Python file of more than 9,000 lines. Supporting fetch/deploy utilities also
contained or implied separate behavior.

Now, `app/cml_tool.py` is a compact composition root and
compatibility layer. The implementation is split into focused modules with
preserved public contracts, guarded writes, exact-version handling, recovery
artifacts, semantic entity comparison and merging, server-side cancellation,
and automated unit/browser coverage.

The reorganized project root contains `README.md`, `.gitignore`,
`Start Here - CML Tool/`, `main/`, and `development/`. `main/` contains the
production `app/`, `docs/`, `favicon/`, `donate/`, and `LICENSE`. The
platform-specific files under `Start Here - CML Tool/` point to
`main/app/cml_tool.py`.

Tests, npm files and dependencies, browser binaries/results/caches, and runtime
artifacts now live under the Git-ignored `development/` workspace. Runtime and
recovery output defaults to `development/runtime/`; `CML_RUNTIME_ROOT` can
override that root.

## What was added

### Modular application services

- `app/cml_tool_page.py`
  - Owns the embedded HTML, CSS, and JavaScript UI.
  - Provides synchronized source/target editors, line numbers, semantic
    overlays, merge rail, target draft copy, comments, and cancellation UI.
- `app/cml_analysis.py`
  - Owns tokenization, tolerant parsing, AST creation, and semantic comparison.
- `app/cml_salesforce.py`
  - Owns Salesforce CLI discovery, credentials, token caching, REST calls,
    paginated SOQL, ESCO capability checks, and restricted collection DML.
- `app/cml_http.py`
  - Owns local HTTP routing, JSON APIs, CSRF validation, trusted host/origin
    checks, security headers, and runtime service resolution.
- `app/cml_artifacts.py`
  - Owns private atomic JSON writes, safe artifact reads, filename
    sanitization, path-traversal protection, and durable audit JSONL writes.
- `app/cml_lifecycle.py`
  - Owns exact-version model lookup, fetch, comparison, guarded deploy,
    verification, backup, rollback, and unchanged-CML refresh behavior.
- `app/cml_constraints.py`
  - Owns constraint association export, portable identity, duplicate and
    dependency checks, comparison, guarded deployment, archive, and restore.
- `app/utilities/cml_cli.py`
  - Provides one guarded cross-platform CLI adapter using the same lifecycle
    core as the web UI.

### Tests

- `development/tests/test_cml_salesforce.py`
  - Salesforce transport, pagination, caching, cancellation, and DML allowlist.
- `development/tests/test_cml_artifacts.py`
  - Atomic/private artifacts, safe names, audit appends, and traversal blocking.
- `development/tests/test_cml_cli.py`
  - Exact-version guarded fetch/deploy utility behavior.
- `development/tests/browser/cml_tool.spec.js`
  - Local Chromium workflows with mocked API responses, including the static guide.
  - Covers Fetch-button placement, scoped runtime-status labels, comments and
    synchronized line numbers, stable semantic overlays, target copying,
    complete-entity merge, ambiguous merge blocking, bounded large-file
    comparison, and server-aware cancellation.

### Documentation and visual guidance

- `salesforce-cml-tool/main/docs/CML_TOOL_COMPLETE_GUIDE.md`
  - Documents the modular architecture, exact-version safety contract, API
    routes, semantic merge workflow, cancellation, artifacts, testing, and
    maintenance.
- `salesforce-cml-tool/main/docs/screenshots/*.svg`
  - Annotated synthetic walkthroughs for fetch/deploy, semantic comparison,
    best practices, dependency preflight, association deployment results, and
    the static Guide Me on Tool workflow.
- The roadmap canvas was updated to record ten completed workstreams and the
  remaining optional enhancements.

## What was modified

### `app/cml_tool.py`

Earlier:

- Contained nearly every application responsibility.
- Mixed UI assets, parsing, Salesforce access, routing, storage, CML lifecycle,
  and constraint-data rules.
- Was difficult to review safely because unrelated changes touched one large
  file.

Now:

- Starts and composes the application.
- Re-exports compatibility names used by tests and existing callers.
- Provides thin wrappers that delegate to focused sibling services.
- Maintains deployment locks and operation registration/cancellation.
- Includes sibling module bytes in the build hash.

### Comparison engine and UI

Earlier:

- Used a quadratic longest-common-subsequence line diff.
- Large inputs could consume excessive time or memory.
- Semantic results were presented separately from the stable comparison panes.
- Merge behavior was less aware of complete CML entity identity.

Now:

- Uses a bounded Myers line diff.
- Falls back safely to a coarse result when configured work limits are reached.
- Keeps source and target panes stable while semantic findings are overlaid.
- Classifies entities as `ADDED`, `REMOVED`, `MODIFIED`, `MOVED`, `UNCHANGED`,
  or `AMBIGUOUS`.
- Applies merge arrows to complete entities and reanalyzes the working target
  draft after each merge.
- Does not offer a merge arrow when identity is ambiguous.
- Supports both entity-aware semantic merge and raw line-hunk merge.

### Cancellation

Earlier:

- Client-side cancellation could stop browser work without reliably signaling
  every server-side stage.

Now:

- Long-running operations receive operation IDs.
- The browser aborts its request and posts the ID to
  `/api/operation/cancel`.
- Server cancellation events are checked before Salesforce access and while
  processing paginated work.
- Early cancellation is preserved even if it arrives immediately before normal
  operation registration.

### Salesforce access

Earlier:

- CLI discovery, token handling, REST behavior, query pagination, and direct
  collection operations were mixed with domain logic.

Now:

- Transport is isolated in `cml_salesforce.py`.
- Credentials are cached in memory and refreshed once after authorization
  failure.
- SOQL pagination and cancellation checks are centralized.
- Low-level inserts/deletes reject objects outside the ESCO allowlist.
- Capability checks distinguish definitive API unavailability from transient
  or authentication failures.

### CML lifecycle safety

Earlier:

- Some standalone utility behavior could imply or select a latest version.
- Lifecycle logic was embedded in the monolith.

Now:

- Every write requires an exact model/version identity.
- Version ownership and runtime status are rechecked before writing.
- Active runtime versions are blocked.
- Deployment requires explicit confirmation and exact target alias entry.
- Existing CML is backed up before modification.
- Written content is read back and byte-verified.
- Failed post-write verification attempts automatic rollback.
- Rollback validates backup identity and integrity, backs up current content,
  restores, and verifies.
- The tool does **not** claim compilation, activation, solver correctness, or
  runtime validation.

### Constraint-data safety

Earlier:

- Export, portable matching, dependency checks, DML, archives, and restore logic
  were intertwined with the server and other domains.

Now:

- All domain behavior is isolated in `cml_constraints.py`.
- ESCO ownership is scoped to the exact Expression Set.
- Cross-org matching uses portable keys instead of Salesforce record IDs.
- Duplicate and ambiguous identities fail closed.
- Catalog prerequisites are read-only checked before selection and immediately
  before writes.
- Deletes are archived from authoritative current records before DML.
- Writes are safely chunked and partial results are reported explicitly.
- Restore re-resolves current target references rather than trusting stale IDs.

### Local artifacts

Earlier:

- Artifact creation and reading were distributed across application logic.

Now:

- Writes use temporary files followed by atomic replacement.
- Sensitive files receive private permissions where supported.
- User-influenced names are sanitized with stable collision-resistant suffixes.
- Reads are restricted to expected artifact roots.
- Audit records are appended durably as one JSON object per line.

### Utility scripts

- `app/utilities/fetch-cml.sh` is now a small compatibility launcher.
- `app/utilities/deploy-cml.py` is now a small compatibility launcher.
- Both delegate to `cml_cli.py` and no longer implement independent Salesforce
  write behavior.
- Exact version IDs are mandatory.

### Platform launcher folder and runtime locations

- `salesforce-cml-tool/Start Here - CML Tool/Open CML Tool for macOS.command`
  starts `main/app/cml_tool.py --no-browser` in the background and writes
  `development/runtime/logs/cml-ui.log` by default.
- `salesforce-cml-tool/Start Here - CML Tool/Stop CML Tool for macOS.command`
  stops the macOS background server.
- `salesforce-cml-tool/Start Here - CML Tool/Open CML Tool for Windows.bat`
  and
  `salesforce-cml-tool/Start Here - CML Tool/Open CML Tool for Linux.sh`
  run `main/app/cml_tool.py` in the foreground.
- Runtime artifacts default to `development/runtime/`: `cml-files/`,
  `cml-backups/`, `association-archives/`, `deployment-reports/`, and `logs/`.
  `CML_RUNTIME_ROOT` can relocate this tree.

## What was cleaned up

- Removed large duplicated responsibility blocks from `cml_tool.py` after
  extracting them into sibling modules.
- Centralized Salesforce credentials, REST, pagination, and DML restrictions.
- Centralized private artifact writes and safe reads.
- Centralized lifecycle backup, verification, rollback, and reporting.
- Centralized ESCO identity, dependency, archive, deployment, and restore rules.
- Replaced direct utility deployment logic with guarded delegation.
- Preserved test patching compatibility through dynamic dependency resolution
  and compatibility re-exports.
- Removed obsolete two-file-mirror maintenance instructions from the complete
  guide.
- Removed stale documentation references to quadratic LCS, old test counts, and
  latest-version deployment.
- Updated annotated screenshots to describe exact selected versions, semantic
  overlays/entity merges, and the boundary between byte verification and
  Salesforce runtime validation.

## What was deleted or retired

### Code deleted from the monolith

The extracted implementations were removed from `app/cml_tool.py`; they were
not discarded. Their maintained equivalents now live in the modules listed
above. This includes:

- Embedded page asset implementation
- Parser and semantic-analysis implementation
- Salesforce transport implementation
- HTTP request routing implementation
- Artifact persistence implementation
- CML lifecycle implementation
- Constraint-data implementation

### Retired behavior

- Quadratic LCS line comparison
- Standalone logic-analysis UI, local analysis route, presentation helpers, and
  plain-English outcome/detail rendering
- Latest-version selection by standalone deployment utilities
- Independent direct Salesforce writes from compatibility utility launchers
- Documentation requiring synchronized edits to two maintained application
  mirrors
- Merge actions for semantically ambiguous entities

### Files actually deleted

No file deletion can be confirmed from Git because the project directory is
untracked. The Git-ignored `development/` workspace is not production deletion
evidence. In the current workspace:

- `scripts/cml-ui.py` still exists, but it is no longer documented or treated as
  the maintained packaged implementation.
- `app/utilities/fetch-cml.sh` and `app/utilities/deploy-cml.py` still exist as
  compatibility wrappers.

Therefore, the accurate statement is: implementation blocks and unsafe/obsolete
behaviors were removed or replaced, but these legacy filenames were not deleted
from the current workspace.

## Behavior intentionally preserved

- Localhost-only server binding
- CSRF and trusted host/origin protection
- Explicit org and exact-version selection
- Confirmation prompts for writes
- Active-version blocking
- Backup before write
- Read-after-write verification
- Rollback and recovery artifacts
- Scoped ownership validation
- Read-only catalog dependency checks
- Backward-compatible public function names for callers and tests

## Current verification

Run from `salesforce-cml-tool/` by entering `development/` first:

```bash
cd development
python3 -m unittest discover -s tests -v
npm run test:browser
```

Verified result:

- **108 of 108 Python tests passed**
- **8 Playwright browser tests are present. In this sandbox run, Chromium crashed at launch with `SIGSEGV` before test code executed; rerun outside the sandbox to verify them.**

The browser suite starts the real local application server but mocks the API
responses used by each workflow. It does not contact Salesforce.

## Remaining optional roadmap items

The completed modernization is usable without these items. Future enhancements
remain:

- Deployment and rollback history UI using existing private reports
- Controlled sandbox smoke scenarios
- Artifact retention and redaction controls
- Configurable Salesforce API version with capability detection
- Exportable dependency manifests for blocked prerequisites

