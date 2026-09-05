# Salesforce CML Tool — Complete Functional and Technical Guide

## Table of contents

1. [Document control](#1-document-control)
2. [Executive summary](#2-executive-summary)
3. [Problem statement](#3-problem-statement)
4. [Solution overview](#4-solution-overview)
5. [CML technical primer](#5-cml-technical-primer)
6. [Architecture and request flow](#6-architecture-and-request-flow)
7. [Features in depth](#7-features-in-depth)
8. [Matching and decision semantics](#8-matching-and-decision-semantics)
9. [Deployment workflows](#9-deployment-workflows)
10. [Production safety controls](#10-production-safety-controls)
11. [Security and permissions](#11-security-and-permissions)
12. [Error and status reference](#12-error-and-status-reference)
13. [User responsibilities and manual intervention](#13-user-responsibilities-and-manual-intervention)
14. [Known limitations and non-goals](#14-known-limitations-and-non-goals)
15. [Production readiness and recovery](#15-production-readiness-and-recovery)
16. [Testing and validation](#16-testing-and-validation)
17. [Troubleshooting](#17-troubleshooting)
18. [Operations](#18-operations)
19. [Maintainer guide](#19-maintainer-guide)
20. [Glossary and appendices](#20-glossary-and-appendices)

## 1. Document control

### 1.1 Purpose

This document is the complete operating and maintenance guide for the Salesforce CML Tool. It explains what the tool implements, how it makes cross-org decisions, what it can safely write, and where a human or another deployment process must take over.

This is not a replacement README. The project README provides onboarding and a UI walkthrough; this guide records functional semantics, production controls, operational procedures, API contracts, and maintainer responsibilities.

### 1.2 Intended audience

- Functional users who fetch, review, compare, or deploy Constraint Model Language (CML).
- Product catalog and Revenue Cloud administrators who own prerequisite catalog data and activation.
- Release managers and change approvers supervising controlled deployments.
- Developers and maintainers changing the Python server, embedded browser application, matching rules, or recovery controls.
- Testers validating sandbox, UAT, recovery, and production-readiness scenarios.

### 1.3 Scope

The guide covers:

- CML discovery, fetch, editing, exact comparison, semantic comparison, deployment, backup, verification, and rollback.
- Local tolerant parsing and structural semantic comparison of CML entities and
  source ranges.
- `ExpressionSetConstraintObj` (ESCO) export, comparison, selected insertion and deletion, dependency preflight, audit, archive, and restore.
- The local HTTP server, embedded vanilla JavaScript UI, Salesforce CLI authentication, Salesforce REST calls, local artifacts, and process lifecycle.

It does not define Salesforce product-catalog deployment procedures, claim complete knowledge of Salesforce activation validation, or authorize unattended production changes.

### 1.4 Implementation locations

- Composition root and compatibility surface: `salesforce-cml-tool/main/app/cml_tool.py`
  (approximately 846 lines)
- Exact-version CML lifecycle: `salesforce-cml-tool/main/app/cml_lifecycle.py`
- Constraint-data workflows: `salesforce-cml-tool/main/app/cml_constraints.py`
- Salesforce authentication and REST transport:
  `salesforce-cml-tool/main/app/cml_salesforce.py`
- Local HTTP security and route dispatch: `salesforce-cml-tool/main/app/cml_http.py`
- Recovery and audit artifacts: `salesforce-cml-tool/main/app/cml_artifacts.py`
- Tokenizer, tolerant parser, semantic comparison, and the static tool guide:
  `salesforce-cml-tool/main/app/cml_analysis.py`
- Browser page: `salesforce-cml-tool/main/app/cml_tool_page.py`
- Guarded optional command-line adapter:
  `salesforce-cml-tool/main/app/utilities/cml_cli.py`
- Automated tests: `salesforce-cml-tool/development/tests/test_*.py` and
  `salesforce-cml-tool/development/tests/browser/cml_tool.spec.js`
- User-oriented summary: `salesforce-cml-tool/README.md`

The project root contains `README.md`, `.gitignore`,
`Start Here - CML Tool/`, `main/`, and `development/`. Platform-specific
launcher files live under `Start Here - CML Tool/`; production code and
packaged assets live under `main/`;
`development/` contains tests, npm metadata and dependencies, browser binaries
and results, caches, and local runtime/recovery artifacts. The entire
`development/` directory is excluded from Git and can contain sensitive
deployment data.

There is one application implementation under `main/app/`, split into sibling
Python modules. Application paths in this guide are relative to
`salesforce-cml-tool/main/`; test and development paths are relative to
`salesforce-cml-tool/development/`; runtime paths are relative to
`salesforce-cml-tool/development/runtime/` unless `CML_RUNTIME_ROOT` overrides
that root. `app/cml_tool.py` loads the application modules directly by file
path, composes their services, retains compatibility wrapper names used by
tests and guarded adapters, loads the page from `app/cml_tool_page.py`, and
starts the local server. There is no frontend build step and no second file to
synchronize. The optional shell/Python utility launchers delegate to
`app/utilities/cml_cli.py`; they must not implement an independent Salesforce
write path.

### 1.5 Terminology

- **CML:** Constraint Model Language text held in an `ExpressionSetDefinitionVersion` record's `ConstraintModel` field.
- **Constraint Model / model:** The model selected by `ExpressionSetDefinition.DeveloperName`.
- **Version:** One exact, explicitly selected `ExpressionSetDefinitionVersion`.
- **Expression Set:** The single parent `ExpressionSet` mapped from the exact
  definition version through `ExpressionSetVersion`.
- **ESCO:** An `ExpressionSetConstraintObj` association between an Expression Set CML tag and a reference object.
- **Reference object:** One of the exact supported ESCO polymorphic targets:
  `Product2`, `ProductClassification`, or `ProductRelatedComponent`.
- **Portable key:** A user-selected field whose value is expected to identify corresponding records across orgs. The default is the customer-defined `Global_Key__c`; it is not asserted to be a Salesforce standard.
- **PRC:** `ProductRelatedComponent`.
- **Source / target:** The org supplying intended state and the org being evaluated or changed.
- **Fresh comparison:** A server-side comparison performed at deployment time, not merely the state still displayed in the browser.
- **Guide Me on Tool:** The fifth application view, a static local safe-workflow reference requiring no API.

### 1.6 Document metadata and maintenance

| Field | Value |
|---|---|
| Document ID | CML-TOOL-GUIDE |
| Version | 1.1 |
| Last reviewed | 2026-09-05 |
| Status | Current implementation guide |
| Owner | CML Tool maintainers |
| Review cycle | Review after any change to matching, deployment, recovery, security, supported Salesforce objects, or UI action eligibility |

Update this guide in the same change that modifies user-visible behavior, API
contracts, deployment semantics, safety controls, artifact formats, or known
limitations. A passing automated test suite is required but does not replace
reviewing this document against the current implementation.

## 2. Executive summary

The Salesforce CML Tool is a zero-third-party-dependency, local Python web application for supervised movement of CML and its ESCO associations between authorized Salesforce orgs. It also provides local static exploration of CML logic. It binds to `127.0.0.1`, uses the Salesforce CLI to discover authorized orgs and obtain credentials, and performs Salesforce reads and writes over REST API version `v66.0` (Spring '26). `ExpressionSetConstraintObj` was introduced in API v63.0 and remains unavailable through v62.0.

The tool addresses two separate portability layers:

1. CML is text and can be fetched, edited, compared, backed up, patched, re-read, and byte-verified.
2. ESCO data contains org-specific Salesforce IDs and therefore must be matched and re-resolved by portable business identity before insert or restore.

The tool deliberately has a narrow write boundary. It writes only:

- `ExpressionSetDefinitionVersion.ConstraintModel`; and
- `ExpressionSetConstraintObj` inserts and deletes.

It does not create or repair products, classifications, attributes, component groups, product relationships, or other catalog prerequisites. It does not activate or compile a model. Active definition-version and parent-Expression-Set writes are blocked. Those remain explicit operational responsibilities.

Production use is appropriate only as a controlled, supervised operation after representative sandbox and UAT validation. Typed target confirmation, local backups, verification, rollback attempts, deletion archives, server-side revalidation, per-model locks, partial-result reporting, and audit artifacts reduce risk; they do not replace change approval, catalog ownership, live activation testing, or operator judgment.

## 3. Problem statement

### 3.1 CML portability is more than moving text

CML text can be copied between orgs, but its usable behavior also depends on Salesforce records associated with its Type and Port tags. Moving text alone does not reconstruct those associations.

**Tool response:** The UI separates CML operations from Constraint Data operations and exposes both as explicit workflows.

**User responsibility:** Treat CML and ESCO data as related but separately reviewed deployment units.

### 3.2 Salesforce IDs are org-specific

An ESCO row contains `ExpressionSetId` and `ReferenceObjectId`. IDs from one org must not be reused in another org.

**Tool response:** Comparison uses a portable composite identity. Deployment re-resolves the current target Expression Set and target reference record immediately before DML. Restore also resolves current records rather than blindly replaying archived IDs.

**User responsibility:** Select a stable and sufficiently unique portable key and resolve duplicate or missing values in the catalog.

### 3.3 CML text and ESCO data can disagree

An ESCO row may refer to a Type or Port tag that is absent from the exact selected version's CML. Conversely, exact source and target versions may legitimately define different tags.

**Tool response:** The tool reads Type and Port tags from each org's exact selected CML version, separates stale rows from comparison rows, and marks cross-org tag disagreement as `cml-difference`.

**User responsibility:** Review the CML difference first. Do not infer that a target-only association is wrong merely because it is absent from the source.

### 3.4 Activation depends on platform and catalog state

The selected model must have a resolvable Expression Set for associations to be attached. Salesforce may also validate catalog relationships and ESCO state during CML save or activation.

**Tool response:** The tool checks implemented catalog dependencies, maps the exact selected definition version through `ExpressionSetVersion`, blocks unresolved Expression Set ambiguity, and performs a tool-specific unchanged-CML save plus exact verification after successful association changes.

**User responsibility:** Activation is manual. The save/verification refresh is not documented activation, compilation, or runtime proof. If it fails after ESCO DML, records may already be committed and the response is partial/recovery-required. Validate the required activation sequence and dependency scope in a representative sandbox.

### 3.5 Raw line diffs are noisy

Formatting, comments, and reordered blocks can dominate a text diff even when model structure is equivalent.

**Tool response:** Exact mode provides a synchronized line diff; Semantic mode parses named blocks and type members and compares them by identity.

**User responsibility:** Use exact mode for byte/text review and Semantic mode as structural guidance. Semantic comparison is tolerant analysis, not a Salesforce compiler.

### 3.6 Authentication output can redact access tokens

Newer Salesforce CLI behavior may return a redaction placeholder from `sf org display`.

**Tool response:** The tool recognizes that a usable token contains `!` and is not marked `REDACTED`; it falls back to `sf org auth show-access-token`. Credentials are cached only in process memory and refreshed once after an authentication error.

**User responsibility:** Authenticate each org under the operating-system user running the tool, protect that user's CLI credentials, and reauthenticate expired or revoked sessions.

### 3.7 Production deployment has destructive and partial-failure risks

CML deployment overwrites the exact selected version's Constraint Model. ESCO deletion is destructive. Salesforce collection operations can succeed for some rows and fail for others.

**Tool response:** The server requires exact typed target alias confirmation, creates recovery artifacts before writes, revalidates browser selections, chunks operations, uses `allOrNone=false`, reports every result, and records audits.

**User responsibility:** Review the target, model, selected rows, saved artifacts, partial outcomes, and rollback readiness before and after every production operation.

## 4. Solution overview

### 4.1 Problem-to-control map

| Problem | Implemented tool response | Remaining responsibility |
|---|---|---|
| CML text must move between orgs | List every version; fetch and PATCH the exact selected version's `ConstraintModel`; create backup; verify exact saved bytes | Select and review exact source/target versions |
| Org-specific IDs | Match by portable identity; resolve target IDs at deployment and restore time | Maintain unique, stable key values |
| CML and ESCO drift | Parse current Type/Port tags; classify stale and CML-difference rows | Decide intended CML and catalog state |
| Missing catalog prerequisites | Read-only dependency preflight and blocking statuses | Deploy or repair catalog data externally |
| Noisy text changes | Bounded Myers line diff with safe coarse fallback, plus structural semantic overlay | Interpret semantic significance |
| Token redaction or expiry | Dedicated access-token command, in-memory cache, one refresh retry | Authenticate and protect local CLI state |
| Accidental production write | Explicit `None` defaults, confirmation dialog, exact alias prompt, backend confirmation | Follow change-control approval |
| Failed or partial write | CML backup, verification, automatic rollback attempt, ESCO archive, per-row results, refresh failure marked recovery-required, and reports | Review, recover, reconcile, and retain evidence |

### 4.2 Operating boundary

The browser UI is an operator console, not an independent source of authority. For data deployment, the browser submits selected IDs only. The Python backend reloads authoritative source and target data, repeats comparison and dependency checks, and rejects stale or forged selections.

## 5. CML technical primer

### 5.1 Constraint Models and definitions

The tool discovers models by querying `ExpressionSetDefinitionVersion` and
reading the related `ExpressionSetDefinition.DeveloperName` and `MasterLabel`.
The query requires a related `ExpressionSet` whose `UsageType` is
`Constraint`, so pricing procedures, qualification procedures, discovery
procedures, rating procedures, and other non-CML Expression Sets are excluded.
It returns **every matching Constraint CML version** to the picker. The displayed
effective status comes from `ExpressionSetVersion.IsActive` when a runtime
version is observed; otherwise the label explicitly falls back to
`ExpressionSetDefinitionVersion.Status`.

Within this tool:

- `ExpressionSetDefinition.DeveloperName` is the stable model selector.
- `ExpressionSetDefinitionVersion` is the versioned record containing status and CML content.
- Source and target version selection is explicit and mandatory.
- Every fetch, compare, deploy, rollback, ESCO view, comparison, deployment, and restore payload carries an exact version ID.
- The server requeries that ID and verifies
  `ExpressionSetDefinition.DeveloperName` equals the submitted model before use.
- A missing, stale, forged, or cross-model version ID is rejected.

There is no latest-version fallback. Version number ordering is presentation
only; ownership-verified IDs control every operation.

### 5.2 Expression Sets and ESCO associations

`ExpressionSetConstraintObj` rows link an `ExpressionSet` to a CML tag and a polymorphic reference record. The implemented fields are:

- `ExpressionSetId`
- `ReferenceObjectId`
- `ConstraintModelTag`
- `ConstraintModelTagType`

For inserts, the tool writes only these fields plus the REST `attributes.type` envelope.

An `ExpressionSetDefinitionVersion` is not itself the ESCO owner. The tool
queries `ExpressionSetVersion` where
`ExpressionSetDefinitionVerId = <exact selected version ID>` and requires those
rows to identify exactly one `ExpressionSetId`. Zero parents or multiple parent
IDs block the operation. ESCO associations belong to that parent
`ExpressionSet` and are therefore shared at the Expression Set level, not
version-specific. Selecting a version establishes exact ownership context; it
does not create a private association set for that version.

### 5.3 CML Type and Port tags

The backend extracts tags from the comment-stripped exact selected CML version as follows:

- A Type tag is the identifier following `type`.
- A Port tag is the identifier following `relation`.

Only recognized `Type` and `Port` ESCO tag types are filtered by this check. Unknown tag kinds remain included rather than being silently discarded.

This extraction is designed for the syntax used by the tool; it is not a complete Salesforce CML parser.

### 5.4 Supported reference object types

Using the tool's REST API v66.0 integration, the ESCO export and portable
matching implementation accepts exactly the allowed `ReferenceObjectId`
targets (the object itself requires API v63.0 or later):

- `Product2`
- `ProductClassification`
- `ProductRelatedComponent`

`ProductComponentGroup` can be inspected as a dependency of a
`ProductRelatedComponent`; it is **not** an ESCO polymorphic target. The
selected key field is probed independently on each supported target. A row can
still be exported when an object lacks the field, but it is not portable
through that field.

### 5.5 Portable matching

For Product and Classification references, the portable ESCO identity is:

`tag type + tag + reference object type + selected key value`

The default selected field is `Global_Key__c`, but the tool accepts a plain Salesforce field API name of up to 80 characters. `Name`, `ProductCode`, or another external/custom identifier can be used only where the target object exposes it and the deployment process has established that it is populated, stable, and unique.

No Salesforce-mandated universal cross-org key is assumed. `Name` does not
“always work”: it can be absent from the API surface, inaccessible, empty,
edited, or duplicated.

### 5.6 PRC canonical identity

A `ProductRelatedComponent` may not expose the selected key directly. PRC
identity v2 therefore uses typed scalar values for:

- parent product key;
- child kind (`Product2` or `ProductClassification`) and child key;
- relationship type name;
- component-group key;
- parent and child selling-model keys; and
- the discriminators `Quantity`, `Sequence`,
  `DoesBundlePriceIncludeChild`, `QuantityScaleMethod`, `MaxQuantity`,
  `MinQuantity`, `IsComponentRequired`, `IsQuantityEditable`,
  `IsDefaultComponent`, and `QuoteVisibility`.

Every discriminator participates in exact identity. If an ID-backed endpoint,
group, or selling model lacks its portable key, or if the full v2 identity
resolves to zero or multiple target PRCs, the tool blocks rather than choosing.

This identity is a defensive application convention, not a claimed Salesforce
uniqueness constraint. Legacy deletion archives that lack the detailed v2
relationship evidence cannot be restored safely: restore fails closed and asks
the user to recreate the archive with the current tool. The old weaker identity
is never replayed.

### 5.7 Catalog dependencies and activation

For Classification-backed rows, preflight reads source and target products and classification attributes and checks:

- that a portable child key can be selected;
- that corresponding target records exist uniquely;
- that a product is assigned to the expected target classification; and
- that an attribute belongs to the expected target classification.

For PRC-backed rows, it checks that the canonical parent/child/relationship identity resolves uniquely in the target.

The tool does not write these catalog objects. It also does not claim these checks exhaust Salesforce activation validation. Repository evidence explicitly identifies activation scope as requiring empirical sandbox verification.

## 6. Architecture and request flow

### 6.1 Components

1. **Composition root:** `app/cml_tool.py` loads sibling modules, exposes the
   compatibility wrapper surface, owns operation registration and build/process
   lifecycle, and starts a standard-library `ThreadingHTTPServer` bound to
   `127.0.0.1`.
2. **Browser UI:** HTML, CSS, and vanilla JavaScript are stored in
   `app/cml_tool_page.py` and loaded by the composition root. There is no
   separate frontend build.
3. **Salesforce CLI:** Used for locating authorized orgs and retrieving instance URL and access token.
4. **Salesforce transport:** `app/cml_salesforce.py` owns CLI discovery,
   credential retrieval, REST calls, paginated SOQL, cancellation checks, and
   the ESCO-only low-level DML allowlist.
5. **Guarded services:** `app/cml_lifecycle.py` owns exact-version CML
   lifecycle; `app/cml_constraints.py` owns ESCO comparison, deployment, and
   restore.
6. **HTTP boundary:** `app/cml_http.py` owns local Host/Origin, CSRF,
   request-size, security-header, and route-dispatch controls.
7. **Local artifacts:** `app/cml_artifacts.py` owns private, atomic backups,
   archives, reports, and audit files.
8. **Local analysis:** `app/cml_analysis.py` owns the tokenizer, tolerant AST
   parser, parser schema, and structural semantic comparison. It does
   not call Salesforce or any external analysis service.
9. **Optional CLI:** `app/utilities/cml_cli.py` delegates exact-version fetch
   and confirmed deploy to the same guarded composition root. The compatibility
   launchers do not bypass backup, locking, rollback, reporting, or
   verification.

### 6.2 High-level request flow

1. A platform-specific launcher under `Start Here - CML Tool/`, or
   `python3 main/app/cml_tool.py` from the project root, starts the local
   process. Each launcher resolves the production application under
   `main/app/` and keeps runtime output out of `main/`.
2. The process checks whether the configured port already hosts this application and compares build hashes.
3. The browser loads `/`; the server injects a per-process CSRF token into the page.
4. The UI calls `/api/orgs`, then `/api/models?org=...` after a source org is selected.
5. GET routes perform discovery and diagnostics. POST routes perform fetch, compare, local logic analysis, data operations, recovery, and protected shutdown.
6. The backend obtains credentials from `sf`, then sends HTTPS requests to the selected Salesforce instance.
7. Write operations create local recovery artifacts, perform Salesforce DML or PATCH, verify or requery state, and return structured results.
8. The UI presents row-level status and recovery locations. It does not silently refresh the comparison after association deployment; the operator must compare again.
9. A long-running Constraint Data comparison carries a browser-generated
   operation ID. **Stop Comparison** posts that ID to
   `/api/operation/cancel`, aborts the browser request, and causes the server to
   check cancellation between stages and paginated Salesforce reads. A
   short-lived pending-cancellation marker closes the race where cancellation
   arrives just before registration.

### 6.3 Salesforce CLI usage

The code searches normal `PATH` plus common nvm, fnm, Volta, Homebrew, npm-global, and Salesforce CLI locations. Windows `.cmd` and `.bat` launchers are invoked through `cmd.exe`.

Implemented CLI commands include:

- `sf org list --json`
- `sf org display --target-org <alias> --json`
- `sf org auth show-access-token --target-org <alias> --json --no-prompt`
- `sf --version` for diagnostics

All SOQL and Salesforce writes are performed over REST, not through shell-composed data commands.

### 6.4 Artifact roots

`APP_DIR` is `salesforce-cml-tool/main/app/`, `REPO_ROOT` is
`salesforce-cml-tool/main/`, and `PROJECT_ROOT` is `salesforce-cml-tool/`.
`RUNTIME_ROOT` defaults to `salesforce-cml-tool/development/runtime/`; setting
`CML_RUNTIME_ROOT` overrides it. Runtime directories (`cml-files/`,
`cml-backups/`, `deployment-reports/`, `association-archives/`, and `logs/`)
are created beneath the effective runtime root regardless of whether the UI or
guarded utility adapter initiated the operation.

## 7. Features in depth

### 7.1 Org and model selection

All org controls initialize with explicit `None` options:

- `None — select a source org`
- `None — select a target org`
- `None — select a deployment target`

No source, comparison target, deployment target, or version is inferred
automatically. The model picker waits for source selection and lists every
Constraint CML definition version with its number and explicitly qualified
runtime or definition status. Effective runtime-active versions are ordered
first, followed by Inactive and then other statuses; version ordering remains
descending within a model/status group. Source, compare-target, and
deployment-target labels are distinct because activity can differ by org. All
native picklists size themselves
from their current option labels within responsive viewport limits. Their
containers and nearby actions wrap rather than truncating the selected label.
Compare and deploy controls load every matching target version and require an
exact choice. The selected IDs are
ownership-verified again by the server.

### 7.2 Fetch, edit, and deploy CML

**Fetch**

- Requires the exact selected source version ID.
- Verifies that version belongs to the selected model.
- Reads the raw `ConstraintModel` blob.
- Saves a sanitized filename under `cml-files/`.
- Loads the text into the browser editor.
- Treats a 404/`NOT_FOUND` blob as empty and reports it explicitly.

**Edit**

- The editor accepts fetched or pasted CML.
- Copy uses the Clipboard API with a browser fallback.
- No autosave of editor changes is implemented.

**Deploy**

- Requires a selected deployment org, model, exact target version, and non-empty content.
- Shows an overwrite warning and cross-org warning.
- Requires the operator to type the target alias exactly.
- Verifies exact target-version ownership and requeries status.
- Blocks if the exact definition version is Active or status is unknown.
- Saves the current target CML before PATCH.
- Patches only the exact selected version.
- Re-reads and compares exact content.
- Attempts automatic restoration of the previous content if verification fails.

Activation and compilation are not performed. The user must deactivate an
Active version in Salesforce, refresh the tool's selections, and explicitly
select it again before a write.

### 7.3 Exact and semantic CML comparison

Exact comparison fetches the model from both orgs and runs a client-side Myers
shortest-edit line diff. The implementation bounds trace memory to 4,000,000
cells and considers at most 100,000 combined lines. If those bounds or the
derived edit-distance budget would be exceeded, it preserves the identical
leading and trailing lines and treats the unrelated middle as one coarse
delete/insert replacement. This safe fallback favors responsiveness and
complete text preservation over a potentially expensive minimal edit script.
The comparison shows:

- changed line pairs;
- source-only lines;
- target-only lines;
- line numbers on both sides;
- synchronized vertical scrolling;
- source-to-target draft merge arrows; and
- a target-pane copy action for the complete current target text or draft.

The source pane remains on the left and the target pane remains on the right.
Enabling **Semantic summary** overlays structural badges and highlighting on
those same stable panes; it does not replace the source or target with a
separate summary view. Semantic comparison:

- removes comments while preserving line structure;
- parses top-level `property`, `extern`, `define`, and `type` units;
- parses relations, fields, and supported call-like members inside types;
- keys named units and members by structural identity;
- ignores whitespace, comment, and order-only changes where the tolerant parser can prove equality; and
- reports `Moved`, `Added`, `Removed`, `Modified`, `Unchanged`, and
  `Ambiguous` entities with exact source/target ranges.

In semantic mode, arrows apply complete entities to the target working draft:

- `Modified` replaces the complete target entity with the source entity.
- Source-only (`Removed` from the target) inserts the complete source entity.
- Target-only (`Added` in the target) removes the complete target entity.
- `Moved` relocates the complete target entity to its source-relative position.

If a parent type is itself actionable, child actions are suppressed so the
same block is not applied twice. Duplicate or otherwise ambiguous semantic
identities receive badges but no merge arrow; the user must resolve the
ambiguity before merging. After every draft merge, the UI calls the protected
local `/api/semantic/compare` route again and rerenders the line diff, badges,
summary, and remaining actions against the new target draft. **Copy target
CML** always copies that complete current target state. A merged draft changes
no Salesforce data until it is loaded into the editor and sent through the
normal guarded deploy workflow.

The parser is intentionally tolerant and incomplete. Use it to focus review, not to certify CML validity.

### 7.4 Best-practice scoring and remediation

The client-side linter checks the current editor text. Implemented rules cover:

- `AP-1`: `double` declarations.
- `AP-3`: five or more empty stub types.
- `AP-4`: repeated enum literal sets used at least three times.
- `AP-5`: inheritance depth of four or more.
- `AP-6`: always-true constraints/preferences.
- `AP-8`: six or more `&&`/`||` operators in one rule.
- `AP-9`: unbounded or unspecified relation cardinality.
- `BP-2`: selected vague field names.
- `REC`: implication style guidance.

The score starts at 100. Severity weights are error 15, warning 6, and information 2, with a maximum 12-point penalty per rule. `REC` findings do not reduce the score.

Findings include line navigation, explanation, and generated before/after guidance where available. The linter runs in the browser and does not send editor text to an analysis service. Generated remediation still requires semantic review and Salesforce validation.

### 7.5 Guide Me on Tool

The fifth application view is a static, responsive operating guide. Opening it
makes no API request. Its eight numbered steps cover exact source version
selection, fetch, exact comparison with optional semantic overlays and merge
draft, best-practice checks, exact deployment-target selection and status
review, backup/confirmation before CML deployment, dependency-preflighted
Constraint Data Deploy, and restore/recovery.

Each step is labeled **Read-only** or **Writes Salesforce**. The guide also states
that target status may differ by org, that the tool does not compile or activate
CML or prove runtime behavior, and that catalog prerequisites are read-only in
this tool and must be corrected externally.

The tokenizer and tolerant parser remain implementation details of semantic
comparison. They recover declarations, types, variables, relations, expressions,
and logic entities so structural diffs can ignore formatting and line movement.
They are not exposed as a standalone analyzer or API.

### 7.6 Constraint data export and comparison

`View data` calls `/api/data` with the exact selected version ID, maps it through
`ExpressionSetVersion` to one parent `ExpressionSet`, and returns ESCO rows for
that parent as JSON. The UI displays reference type, tag type, tag, reference
label/code, selected key, and duplicate badges.

`Compare data` calls `/api/data/compare` with mandatory exact source and target
version IDs, exports each parent Expression Set, reads both exact CML versions,
groups rows by portable identity without collapsing duplicates, and assigns
statuses.

The UI's `Copy for Excel` action copies the currently visible/filter-matched rows as tab-separated text. It includes the readable status plus the full `blockNote` where present and normalizes embedded tabs and newlines. It does not create an Excel file.

### 7.7 Configurable key and ambiguity preflight

The configured key:

- defaults to `Global_Key__c`;
- must be a plain, SOQL-safe API name;
- is probed per reference object;
- is queried in batches of at most 200 values; and
- is re-resolved during deployment.

Comparison retains every target candidate ID. More than one target match yields `ambiguous-key`; no arbitrary winner is selected.

### 7.8 Duplicate statuses

Rows can carry one or more data-quality flags:

- **Exact duplicate:** same portable ESCO key occurs more than once in the scoped export.
- **Duplicate tag:** the same tag type and tag occur on multiple associations
  for a tag used by the exact CML selected by the user, inside that version's
  resolved parent Expression Set.
- **Duplicate reference:** the same reference type and key occur on multiple rows.
- **Ambiguous name:** the same reference name maps to multiple selected-key values.

Duplicate detection runs independently against the exact selected source CML
and exact selected target CML. Only associations whose Type/Port tags appear in
that CML participate; the rows must also belong to the selected version's
resolved parent Expression Set. It does not combine unrelated models, other
parents, tags used only by another CML version, or all ESCO rows in an org.

Reference `Name` is current display data read from each org, never portable
identity. A Salesforce auto-number format change such as `PRC-...` to
`ECO-...` therefore does not break matching. Matched comparison rows retain
both source and target names and display both when they differ; canonical PRC
identity remains based on endpoints, relationship context, and stable
discriminators.

Duplicate badges describe data shape; deployment status controls action eligibility. A surplus source exact duplicate is blocked as `exact-duplicate`. A surplus target duplicate remains visible and may be an explicit deletion candidate if it is a fresh target-only, non-CML-difference row.

### 7.9 CML difference versus stale

These statuses are intentionally different:

- **`cml-difference`:** A comparison row is valid against its own org's exact selected CML version, but the other exact selected version does not define the same Type or Port. It is protected from add or delete.
- **`stale`:** An association's own exact selected CML version does not define its Type or Port. Stale rows are removed from normal matching and listed separately. They are excluded from automated add and delete.

Stale is not a deletion queue. It is a review signal.

### 7.10 Dependency preflight

The tool distinguishes:

- confirmed missing, ambiguous, or unlinked catalog state, which yields `blocked`; and
- missing keys or query capability that prevent proof, which yields `dependency-unverified`.

Both are non-deployable. “Unverified” does not mean “missing,” and “matched ESCO” does not guarantee all deeper catalog dependencies are valid.

### 7.11 Matched evidence

Every paired row includes `matchedEvidence`:

- whether the portable keys are equal;
- source constraint, Expression Set, and reference IDs; and
- target constraint, Expression Set, and reference IDs.

This preserves evidence that different Salesforce IDs were paired through the same portable identity.

### 7.12 Association deployment and restore

Source-only `ready` rows are selected by default. Target-only eligible rows are not selected by default.

Deployment:

- sends source constraint IDs for additions and target ESCO IDs for deletions;
- re-runs comparison on the server;
- resolves current target references and Expression Set;
- repeats dependency checks for each insert chunk;
- archives authoritative deletion rows;
- performs collection DML with row-level outcomes;
- refreshes CML validation after successful association changes; and
- saves reports and audit history.

The “refresh” is specifically an unchanged-CML save and exact verification
owned by this tool. It is not documented proof that Salesforce activated,
compiled, or executed the model. If ESCO DML succeeds and this step fails, the
response is `partial`, `ok: false`, and `recoveryRequired: true`; the operator
must assume records changed and follow recovery.

Restore:

- requires exact target confirmation;
- checks archive ownership;
- resolves the current Expression Set;
- skips an association already present;
- resolves current references by portable key or PRC identity; and
- blocks zero or multiple matches.

## 8. Matching and decision semantics

### 8.1 Portable row key

For ordinary reference types:

`ConstraintModelTagType ␟ ConstraintModelTag ␟ reference type ␟ selected key`

For PRC:

`ConstraintModelTagType ␟ ConstraintModelTag ␟ ProductRelatedComponent ␟ canonical PRC identity`

The visible separator is represented internally by Unicode unit separator symbol `␟`.

### 8.2 Pairing behavior

Rows are grouped into lists by portable key. The comparison pairs source and target rows up to the smaller group size. This preserves exact duplicates rather than silently collapsing them.

Paired rows are `matched` unless dependency analysis changes the display status to `blocked` or `dependency-unverified`.

### 8.3 Status and action matrix

| Status | Meaning | Add | Delete |
|---|---|---:|---:|
| `matched` | Portable association exists in both orgs | No | No |
| `ready` / UI `add` | Source-only, target CML recognizes tag, reference resolves uniquely, preflight passes | Yes, selected by default | No |
| UI `extra` | Fresh target-only row not marked `cml-difference` | No | Yes, explicit opt-in |
| `cml-difference` | Other org's CML does not define the tag | No | No |
| `stale` | Own org's exact selected CML version does not define the tag | No | No |
| `exact-duplicate` | Surplus source exact duplicate | No | Not as a source row |
| `ambiguous-key` | Multiple target records share the selected key | No | No |
| `blocked` | Catalog dependency missing, ambiguous, unlinked, or unresolved | No | No |
| `dependency-unverified` | Dependency comparison lacks sufficient key/query evidence | No | No |
| `unmappable` | Reference lacks a portable identity for the selected key | No | No |

### 8.4 Exact deletion eligibility

A deletion candidate is not a stale row. It must be:

1. present in the fresh server-side `targetOnly` result;
2. not `cml-difference`;
3. explicitly selected by the user;
4. submitted with an ESCO-like ID;
5. found again under the selected target model; and
6. revalidated for ownership immediately before its DML chunk.

If any condition fails, deletion is blocked. The server does not trust a browser-provided tag, label, or status.

### 8.5 Exact duplicates

If two source rows and one target row share the same portable key, one pair is matched and the surplus source row is marked `exact-duplicate`. A forged request to add it is rejected server-side.

If the target contains a surplus exact duplicate, that row can appear as a target-only `extra`. The tool permits deliberate cleanup after fresh comparison and ownership validation; it does not automatically decide which target duplicate represents the intended row.

### 8.6 Multiple Expression Sets

Identical tag/reference values on different Expression Sets cannot be treated
casually as duplicates. The implementation maps the exact selected definition
version through `ExpressionSetVersion`; zero parents or multiple distinct
`ExpressionSetId` values block. Within one parent, ESCO data is shared by the
Expression Set rather than duplicated per definition version.

The tool does not encode a “keep oldest,” “keep newest,” or “keep active” cleanup rule. A human must establish the intended Expression Set before deployment.

## 9. Deployment workflows

### 9.1 Prerequisites

- Python 3 and Salesforce CLI are available to the launching user.
- The launching user has authorized source and target orgs.
- The user has Salesforce read permissions for queried model, ESCO, and catalog objects.
- The deployment user has update permission for `ExpressionSetDefinitionVersion.ConstraintModel` when deploying CML.
- The deployment user has create/delete access to `ExpressionSetConstraintObj` for association changes.
- The exact source and target definition versions have been selected and independently confirmed.
- The exact version-to-parent-Expression-Set mapping is unique.
- Any definition version or Expression Set that will be written is non-Active.
- The selected portable key exists, is populated, and is unique where required.
- Catalog prerequisites are deployed through their owning process.
- A writable, protected local artifact location is available.
- The exact activation sequence has been tested in a representative environment.

### 9.2 Recommended supervised sequence

Because activation behavior is not fully established by the repository's live evidence, use the following conservative sequence and adapt it to the validated org runbook:

1. Obtain change approval and preserve an independent target-state snapshot.
2. Authenticate and verify source and target aliases.
3. Deploy required Product, Classification, Attribute, Component Group, and Product Relationship data through approved catalog tooling.
4. Compare source and target CML in exact and semantic modes.
5. Select the intended exact source and target versions, then fetch and deploy.
6. Confirm the CML deployment report and SHA verification.
7. If a required write target is Active, deactivate it in Salesforce, refresh
   the version list, and reselect the exact version. Do not rely on the stale
   browser selection.
8. Compare Constraint Data using the approved key.
9. Resolve all `cml-difference`, ambiguous, blocked, unverified, and unmappable rows.
10. Deploy selected additions first unless the approved change specifically requires deletion.
11. Review per-row outcomes and the separate tool-specific CML
    save/verification refresh. If DML succeeded but refresh failed, stop:
    recovery is required.
12. Recompare data before considering deletions.
13. Select only approved fresh target-only extras, deploy, and retain the deletion archive.
14. Recompare until the intended outcome is explained.
15. Manually activate or re-activate as required by the tested target-org
    process; deploy never performs this.
16. Execute functional smoke tests and archive evidence.

The tool never activates a model automatically.

### 9.3 CML-only deployment

1. Select source org and model.
2. Select and fetch the exact source version.
3. Select an explicit deployment target and exact target version.
4. Compare the exact versions when moving cross-org.
5. If the target version is Active, deactivate it in Salesforce, refresh, and
   reselect it.
6. Click **Deploy CML**.
7. Confirm overwrite and type the target alias exactly.
8. Verify success, backup location, report location, and SHA.
9. Complete manual activation and smoke testing.

### 9.4 Association-only recovery

1. Use the result panel from the deployment that created the deletion archive.
2. Click **Restore deleted associations**.
3. Type the target alias exactly.
4. Review restored, already-present, blocked, and failed rows.
5. Review the restore report.
6. Recompare and manually validate/activate as required.

## 10. Production safety controls

### 10.1 Target confirmation

CML deploy, CML rollback, ESCO deploy, and ESCO restore require the exact target alias. The backend repeats this check; changing browser JavaScript is not enough to bypass it.

### 10.2 CML backup and integrity

Before CML deployment and before association deployment, the current target CML is saved locally with:

- org and model;
- exact version ID, number, and status;
- reason;
- SHA-256; and
- full CML content.

Rollback verifies that the stored content matches its saved SHA-256 and that
the selected exact version ID is the same version backed up.

### 10.3 Post-deploy verification and automatic rollback

After CML PATCH, the tool re-fetches the exact version up to four times with increasing short delays. Verification requires exact text equality.

If verification fails:

1. The tool patches the previous CML.
2. It verifies the restoration.
3. It records both outcomes.
4. If automatic restoration also fails, the saved backup remains the recovery source.

### 10.4 ESCO deletion archives and restore

Before deletion, complete authoritative target comparison rows are saved under `association-archives/`. If the archive cannot be created, deletion does not proceed.

Restore does not reuse archived Expression Set or reference IDs blindly. It resolves current IDs and requires exactly one portable match.

### 10.5 Fresh ownership and decision revalidation

- Every source/target version ID is requeried and must still belong to the named
  model.
- The exact target authoring status is requeried from
  `ExpressionSetDefinitionVersion.Status`.
- Runtime activity is requeried from `ExpressionSetVersion.IsActive`;
  `ExpressionSet` itself has no `Status` field. Because ESCO rows are shared by
  the parent Expression Set, any active runtime version under that parent
  blocks the applicable association write.
- The parent Expression Set is resolved again through `ExpressionSetVersion`.
- Additions must still be present in fresh `sourceOnly` results and have `deployStatus == ready`.
- Deletions must still be present in fresh `targetOnly` results and not be `cml-difference`.
- Deletion IDs must use the expected ESCO prefix.
- Selected deletion IDs are queried again under the target model.
- Ownership is queried again for each deletion chunk.

### 10.6 Chunking and partial outcomes

- Key and parent queries use bounded chunks, generally no more than 200 values.
- ESCO insert and delete collection operations use chunks of at most 200.
- The target Expression Set, target references, and dependencies are re-resolved for every insert chunk.
- Collections use `allOrNone=false`.
- A successful row is not rolled back merely because another row failed.
- The UI reports `success`, `partial`, `failed`, or `skipped` outcomes and shows each row result.
- A failed post-DML save/verification refresh makes the operation `partial` and
  `recoveryRequired`, even if every requested row DML result succeeded.

Partial success requires reconciliation; retry only failed rows after a fresh comparison.

### 10.7 In-process deployment locks

Write and recovery operations are serialized by `(target org, model)` within one Python process. A second concurrent operation for the same pair is rejected immediately.

This is not a distributed lock. Two separate processes on different ports or hosts do not share it.

### 10.8 Audit and deployment reports

- Timestamped JSON reports record CML deploy, rollback, association deploy, and association restore details.
- Every association deployment call attempts exactly one append to `logs/data-deploy-history.jsonl`, including pre-DML rejection and partial outcomes.
- Reports identify the operating-system user and target context.
- Audit or report write failure is surfaced; it is not silently ignored.

### 10.9 Filename and artifact safety

Artifact names allow only letters, digits, hyphen, underscore, and period; traversal characters are replaced, leading/trailing periods are stripped, reserved Windows names are prefixed, long/changed names receive a hash suffix, and artifact IDs are restricted to basenames ending in `.json`.

JSON artifacts are written through a temporary file, flushed, `fsync`ed, and atomically replaced. Directory mode `0700` and file mode `0600` are requested where the operating system supports them.

### 10.10 Transient cache behavior

- Access tokens and instance URLs are held in process memory and discarded when the process exits.
- A REST authentication error triggers one credential refresh.
- Field-existence results have a five-minute TTL.
- Definitive invalid-field/type responses are cached as false.
- Transient query failures are not cached, allowing a later probe to recover.

### 10.11 Local API protections

- Server binding: `127.0.0.1` only.
- Trusted Host values: `127.0.0.1`, `localhost`, and `::1`.
- POST Origin, when supplied, must resolve to a local hostname.
- Every POST requires a per-process `X-CML-CSRF` token.
- Shutdown is POST-only and CSRF-protected.
- Request bodies over 10 MiB are rejected.
- Invalid or negative `Content-Length` is rejected.
- Responses disable caching and include CSP, anti-framing, MIME-sniffing, and referrer protections.

The CSP permits inline scripts and styles because the entire UI is embedded in one response; it otherwise limits content and connections to the local origin.

### 10.12 Write allowlist

At the lowest shared collection-insert boundary, every inserted record must declare `ExpressionSetConstraintObj`. Delete accepts only IDs with the expected ESCO prefix. Catalog-object writes are blocked by design.

## 11. Security and permissions

### 11.1 Localhost-only design

The application is designed for a single operator on the same computer. It has no user accounts, TLS listener, remote access mode, or multi-user authorization layer. Do not proxy, port-forward, container-publish, or expose it to a network.

### 11.2 Credential and token handling

- Credentials come from the launching user's Salesforce CLI state.
- Tokens are sent only in Salesforce HTTPS `Authorization: Bearer` headers.
- The tool does not intentionally write access tokens into downloads, backups, reports, or deployment audit entries.
- A token redaction placeholder is not accepted as a token.
- The `/api/debug` response includes environment diagnostics such as paths, operating-system user, and login counts; share only after review.
- `/api/ping` returns the local request token so a newer launcher can ask an older local process to stop. Host restrictions and loopback binding are therefore part of the trust boundary.

### 11.3 Salesforce permissions

The exact permission-set design is org-specific. At minimum, operations require
access to the objects and fields they query. CML deployment requires permission
to update the exact selected version's `ConstraintModel`; ESCO deployment
requires insert/delete access for ESCO. Exact ownership requires read access to
`ExpressionSetDefinitionVersion`, `ExpressionSetVersion`, and `ExpressionSet`.
Dependency preflight requires read access to referenced catalog objects and
relationship fields.

Lack of read access can appear as an unavailable field, query error, or unverifiable dependency. Do not weaken controls to work around permission errors; use an approved deployment identity with least privilege.

### 11.4 Local artifact sensitivity

Backups and archives can contain CML, record IDs, portable keys, product labels, and relationship information. Deployment reports and audit logs can identify org aliases and operating-system users. Treat these as controlled deployment evidence, not disposable application cache.

## 12. Error and status reference

### 12.1 Selection and connectivity

| Message/status | Likely cause | Tool action | User action |
|---|---|---|---|
| No org selected / explicit `None` | Required picker is unset | Stops before request | Select the intended org |
| No orgs found | No CLI login for this OS user | Shows login guidance and debug URL | Authenticate under the same OS account |
| Salesforce CLI not found | `sf` absent or not on searched paths | Stops Salesforce operation | Install CLI or launch with a usable PATH/`SF_PATH` |
| Lost connection | Local process stopped or restarted | UI retries `/api/orgs` every 1.5 seconds | Restart server and reload if it does not reconnect |
| Port in use | Another non-CML process owns the configured port | Exits rather than selecting a random port | Stop conflict or set `CML_UI_PORT` |

### 12.2 Authentication

| Message/status | Likely cause | Tool action | User action |
|---|---|---|---|
| No usable access token | CLI output redacted and dedicated token command failed | Rejects Salesforce request | Reauthenticate and verify CLI |
| Saved login rejected | Expired/revoked session after one refresh | Returns explicit login/logout commands | Re-login, reload orgs, retry |
| Invalid auth header | Missing, malformed, or rejected Salesforce token | Refreshes once, then stops | Reauthenticate; never paste tokens into the UI |

### 12.3 CML

| Message/status | Likely cause | Tool action | User action |
|---|---|---|---|
| Model/version not found or ownership mismatch | Missing/stale/forged ID or version belongs to another definition | No write | Refresh and select the exact intended version |
| Empty Constraint Model | Exact selected version has no populated blob; status alone does not explain this | Saves/reports empty fetch but marks operation unsuccessful | Confirm exact version ID and lifecycle; select the intended populated version |
| Active definition version | CML PATCH/rollback/refresh target is Active | Blocks before write | Deactivate in Salesforce, refresh versions, and reselect |
| Backup could not be saved | Disk, permission, or path failure | Stops before write | Fix local storage and retry |
| PATCH accepted, verification failed | Saved content differs or cannot be re-read | Attempts automatic restoration | Review report; if needed use saved backup |
| Backup integrity mismatch | Artifact content was changed or corrupted | Blocks rollback | Preserve artifact; recover from trusted independent backup |
| Version/backup mismatch | Backup belongs to a different exact version | Blocks rollback | Select the matching version/backup or use approved manual recovery |

### 12.4 Constraint Data

| Status | Cause | Tool action | User action |
|---|---|---|---|
| Matched | Portable identities paired | No DML option | Review evidence if needed |
| Add to target | Source-only row passed preflight | Selected by default | Confirm intended addition |
| Only in target | Fresh target-only, non-CML-difference row | Delete checkbox, default off | Review and explicitly select only approved deletion |
| CML definitions differ | Other org lacks the same Type/Port | Blocks action | Compare/deploy intended CML first |
| Unused association in this org | Own exact selected CML version lacks Type/Port | Excludes from deploy | Investigate manually; do not treat as automatic cleanup |
| No selected key | Reference lacks portable identity | Blocks action | Populate/select a safe key |
| Blocked — ambiguous key | More than one target record matches | Retains candidate IDs and blocks | Make target key unique, then recompare |
| Needs review — dependency key missing | Dependency cannot be proven | Blocks action | Add a usable key or inspect manually |
| Blocked — catalog dependency | Required record/assignment/relationship absent or ambiguous | No catalog write | Fix through catalog deployment process |
| Active parent Expression Set | ESCO insert/delete/restore target is Active | Blocks before DML | Deactivate in Salesforce, refresh exact selection, and retry under approval |
| Skipped — exact duplicate | Surplus source duplicate | Rejects add, including forged request | Clean source intentionally |
| Partial deployment | Some collection rows succeeded and others failed | Preserves all row results and recovery artifacts | Recompare, reconcile successes, fix failures, retry selectively |
| Partial — recovery required | ESCO DML changed records but the tool-specific unchanged-CML save/verification failed | Returns `ok: false`, `outcome: partial`, and recovery artifacts | Stop, preserve evidence, recompare, and follow recovery; do not treat this as activation/runtime validation |

### 12.5 Local API security

| Message | Cause | Tool action | User action |
|---|---|---|---|
| Untrusted Host | Non-local Host header | HTTP 403 | Use the loopback URL |
| Untrusted Origin | Browser POST came from non-local origin | HTTP 403 | Close untrusted page; reload tool locally |
| Request rejected by local security protection | Missing/stale CSRF token | HTTP 403 | Reload the current tool page |
| Request is too large | Body exceeds 10 MiB | HTTP 413 | Reduce request; investigate unexpectedly large CML |
| Invalid request body | Malformed JSON | No operation | Use the built-in UI or correct local client |

## 13. User responsibilities and manual intervention

The user or release owner remains responsible for:

1. Installing and authenticating the Salesforce CLI.
2. Confirming source, target, model, exact source/target versions, and portable key.
3. Ensuring portable keys are populated, stable, and unique.
4. Deploying or repairing catalog objects outside this tool.
5. Reviewing exact and semantic CML differences.
6. Reviewing every blocked, unverified, unmappable, duplicate, CML-difference, stale, add, and delete row.
7. Performing activation manually and recording activation errors.
8. Resolving zero/multiple exact version-to-Expression-Set mappings rather than asking the tool to guess.
9. Reconciling partial success before retry.
10. Retaining, protecting, and eventually disposing of local artifacts under organizational policy.
11. Maintaining independent backups and approved rollback plans.
12. Following separation-of-duties, peer-review, change-window, and production-approval requirements.
13. Confirming that the target Salesforce user has appropriate least-privilege access.
14. Performing post-deployment functional and catalog smoke tests.

## 14. Known limitations and non-goals

### 14.1 No catalog writes

The tool does not create or update Product, Classification, Classification Attribute, Component Group, Product Relationship, Selling Model, or other prerequisite records.

### 14.2 No automatic activation

It does not activate or compile Expression Set versions or models. A CML
validation refresh is only this tool's unchanged-content save and exact
verification step; it is not documented activation/runtime proof.

### 14.3 No unattended production deployment

The UI and backend require interactive target confirmation. There is no scheduler, service account workflow, approval engine, or headless production mode.

### 14.4 No distributed locking

Locks exist only in one Python process. The application is not a multi-instance or multi-user deployment service.

### 14.5 Local artifacts only

Recovery artifacts are stored on the launching computer. There is no remote durable store, retention engine, encryption layer beyond operating-system controls, or central audit collector.

### 14.6 Semantic and lint analysis are guidance

Semantic parsing runs locally in `app/cml_analysis.py`; the best-practice
linter runs locally in the browser. Both are tolerant guidance and neither
replaces Salesforce parsing, compilation, save validation, activation, or
functional testing.

### 14.7 Static guide and analysis boundary

Guide Me on Tool is documentation only and performs no analysis or network
request. Semantic comparison remains conservative: it compares parsed structure
but does not compile, solve, activate, or predict Salesforce runtime behavior.

### 14.8 Exact version selection

The tool lists every version and requires explicit exact source and target
version selection. It does not infer “latest.” Ownership verification protects
against stale or forged IDs but does not decide which version the change owner
intended.

### 14.9 Supported tag and reference scope

Stale detection recognizes Type and Port declarations through implemented
patterns. ESCO reference handling is limited to the three allowed targets:
`Product2`, `ProductClassification`, and `ProductRelatedComponent`.
`ProductComponentGroup` is PRC dependency data, not an ESCO target. Other
syntax or polymorphic targets are unsupported.

### 14.10 Incomplete live evidence matrix

The repository's redacted live comparison evidence covers matched rows, source/target CML differences, dependency-unverified cases, and a matched Product2/PRC scenario. It does not yet provide real examples for all safe-add, safe-delete, duplicate, confirmed-missing, ambiguous-key, recreated-reference, or PRC-child variants.

Automated tests exercise many of these policies with mocks, but mocked policy coverage is not live platform evidence.

### 14.11 Activation-validation scope remains empirical

The exact dependencies Salesforce validates during activation are not established by the repository. This must be tested by changing one dependency at a time in a sandbox and recording actual platform results.

## 15. Production readiness and recovery

### 15.1 Readiness position

Use the tool in production only for controlled, supervised changes after representative sandbox and UAT scenarios have passed. The implemented controls support production discipline but do not establish production readiness by themselves.

### 15.2 Go/no-go checklist

**Change control**

- [ ] Approved change ticket identifies source, target, model, exact source and target versions, and operator.
- [ ] Peer reviewer has inspected exact and semantic CML differences.
- [ ] Planned ESCO adds/deletes are attached to the change evidence.
- [ ] Deployment and rollback owners are available during the window.

**Environment**

- [ ] Source and target aliases were selected explicitly and independently verified.
- [ ] Salesforce CLI login is valid for the launching OS user.
- [ ] Required read/write permissions have been tested.
- [ ] Artifact directories are writable, private, and have sufficient capacity.
- [ ] No other CML Tool process or conflicting deployment is operating on the same model.

**Data and dependencies**

- [ ] Portable key is approved, populated, and uniquely constrained by process or verified data.
- [ ] No unresolved ambiguous, blocked, unverified, or unmappable addition remains.
- [ ] Every CML difference is understood.
- [ ] Stale rows are excluded from automated cleanup.
- [ ] Catalog prerequisites were deployed and validated externally.
- [ ] Multiple Expression Set ambiguity is absent.
- [ ] Version-to-parent mapping and non-Active write status were refreshed immediately before the operation.

**Validation**

- [ ] CML and association deployment sequence passed in sandbox/UAT.
- [ ] Activation was tested manually with representative catalog states.
- [ ] Safe add, safe delete, partial failure, CML rollback, and archive restore were exercised.
- [ ] Production smoke tests and expected results are written down.

**Decision**

- [ ] **GO** only if all required checks pass.
- [ ] **NO-GO** if the target, model, key, Expression Set, dependency, backup location, or recovery owner is uncertain.

### 15.3 Rollback and recovery runbook

#### A. CML verification fails immediately

1. Stop further changes.
2. Read the deployment result to determine whether automatic rollback was attempted and verified.
3. Preserve the deployment report and backup.
4. If automatic rollback verified, re-fetch and compare the target before resuming.
5. If it did not verify, use **Restore backup** for the same org, model, and current version.
6. If the version changed, do not force the artifact through the UI; escalate to the model owner with the backup and report.
7. Manually validate/activate and execute smoke tests after restoration.

#### B. CML deployment succeeded but functional validation fails

1. Freeze association deployment.
2. Use **Restore backup** for the target/model.
3. Confirm the safety backup created before rollback.
4. Verify restored SHA and re-fetch exact content.
5. Complete manual activation and functional validation.

#### C. Association deployment is partial

1. Do not resubmit the original selection.
2. Preserve the report, audit line, CML backup, and deletion archive.
3. Recompare to establish current state.
4. Verify which inserts and deletes actually succeeded.
5. Fix the specific permission, dependency, ambiguity, or lock error.
6. Select only remaining valid rows and repeat under approval.
7. Review the CML validation refresh separately from DML success.

#### D. Approved deletion must be reversed

1. Use **Restore deleted associations** from the original result panel.
2. Confirm the exact target alias.
3. Review rows already present, restored, and blocked.
4. Resolve zero/multiple portable reference matches before another restore attempt.
5. Recompare and manually validate/activate.

#### E. Local recovery artifact is unavailable

1. Stop changes.
2. Do not reconstruct IDs from memory or source-org artifacts.
3. Use the independent change backup or retrieve current target state through approved means.
4. Escalate according to incident and change-management procedures.

## 16. Testing and validation

### 16.1 Current automated test categories

The test module covers:

- filename sanitization and traversal resistance;
- REST API v66.0 for tool requests, the ESCO v63.0 minimum, and the exact
  three ESCO target types;
- definitive versus transient field-probe caching;
- exact target confirmation;
- same-process per-org/model deployment locking;
- CML backup, exact verification, and backup-failure stop;
- automatic restoration after failed CML verification;
- exact-version listing, mandatory source/target IDs, ownership rejection,
  version-scoped backup listing, rollback ownership, safety backup,
  verification, active-version blocking, and tamper rejection;
- exact `ExpressionSetVersion` parent mapping, duplicate-parent collapse, and
  zero/multiple-parent blocking;
- duplicate preservation and source-surplus blocking;
- ambiguous portable-key candidate retention and comparison blocking;
- ordinary and PRC identity-v2 archive restore using current portable identity,
  every v2 discriminator, and weak legacy-archive rejection;
- deletion rejection outside a fresh target-only comparison;
- 200-row chunking and repeated revalidation for a large addition set;
- server-side rejection of forged exact-duplicate additions;
- authoritative deletion archive creation;
- partial deletion outcomes and post-DML refresh-failure recovery-required state;
- exactly one association audit entry for a rejected call;
- explicit `None` selection defaults;
- model selection waiting for source org;
- Parser token coordinates and quoted comment-like text;
- official declarations/types, annotations, type inheritance, variable domains,
  fixed/range relation cardinality, relation order, aggregate metadata, and
  relation-body recovery;
- parser expression forms and expression-completeness checks used by semantic
  comparison;
- malformed-construct recovery to later declarations;
- Guide Me on Tool navigation, eight numbered steps, safety badges, responsive layout, and zero-request behavior;
- bounded Myers diff fallback, stable semantic overlays, complete-entity draft
  merges, ambiguous-identity blocking, target copy, and semantic reanalysis
  after each merge;
- operation-ID registration, pre-registration cancellation, cancellation
  checks before and during paginated reads, and operation cleanup;
- guarded CLI delegation for exact-version fetch and confirmed deployment;
- CSRF, Host, Origin, shutdown-route, and security-header behavior; and
- the rollback UI's use of the implemented API helper.

### 16.2 Verified test command

From `salesforce-cml-tool/`, enter the Git-ignored development workspace before
running tests:

```bash
cd development
python3 -m unittest discover -s tests -v
```

This discovers the tests split across `test_cml_tool.py`,
`test_cml_salesforce.py`, `test_cml_artifacts.py`, and `test_cml_cli.py`.
The verified current suite contains **108 Python tests**.

The optional browser regression suite is development-only. From
`salesforce-cml-tool/`, enter `development/` first:

```bash
cd development
npm install
npx playwright install chromium
npm run test:browser
```

It contains **8 browser tests**. Playwright starts the real local HTTP server
on its dedicated test port, while each test intercepts the relevant local API
requests and supplies synthetic responses. The suite does not authenticate to
or contact Salesforce. It covers editor line-number/comment behavior, stable
semantic overlays, complete-entity merge behavior and ambiguity blocking,
target copy, Fetch-button placement, source/target runtime-status labeling,
large-input fallback behavior, and operation-ID cancellation.

### 16.3 Unit/mock boundary

Python Salesforce behavior is tested by replacing CLI, query, REST, backup,
and DML functions with mocks. Browser tests also mock local API responses.
These tests are valuable for decision policy, safety sequencing, request
validation, rendering, and result handling. They do not prove:

- object/field availability in a particular Salesforce release or org;
- target permission configuration;
- live Salesforce locking and validation behavior;
- actual activation dependency scope;
- exact duplicate constraints enforced by the platform; or
- every PRC and catalog topology.
- Salesforce CML compilation, scope creation, action execution, solver output,
  catalog binding, performance, or activation behavior.

### 16.4 Required live validation

Before production approval, run controlled sandbox/UAT scenarios from Appendix C. Capture redacted comparisons, Salesforce errors, deployment reports, activation results, and recovery evidence.

## 17. Troubleshooting

### 17.1 Salesforce CLI unavailable

1. Run `sf --version` in a terminal under the same OS user.
2. If installed through nvm/fnm/Volta, confirm the launcher can see that path.
3. From the project root, start with
   `SF_PATH=/approved/path/to/sf python3 main/app/cml_tool.py` if needed.
4. Use `/api/debug` locally to inspect discovery information.

### 17.2 No orgs appear

Salesforce CLI authorizations are per operating-system user. Run:

```bash
sf org list
sf org login web --alias <approved-alias>
```

Then click **Reload list**. Do not copy another user's credential files.

### 17.3 Auth header or token redaction errors

The tool already falls back from redacted `org display` output to the dedicated access-token command. If Salesforce still rejects the session:

```bash
sf org login web --target-org <approved-alias>
```

If necessary, log out and reauthorize. Never paste an access token into CML, logs, reports, screenshots, or support messages.

### 17.4 Model missing or CML empty

- Confirm the model developer name exists in the selected org.
- Refresh the picker and confirm the exact selected version ID.
- Check whether that exact version has a populated `ConstraintModel`.
- Do not infer content from status: empty does not mean Inactive, and Active
  does not guarantee populated CML.
- Confirm the intended version lifecycle with the model owner.

### 17.5 CML difference

Compare exact text and Semantic mode. A CML-difference association is protected
because one org's exact selected CML version does not recognize the same Type or
Port. Deploy or intentionally reconcile CML before reconsidering ESCO data.

### 17.6 Missing or unverifiable dependency

- **Missing/ambiguous/unlinked:** repair catalog data through its normal process.
- **Unverified:** provide a usable portable key or inspect the dependency manually.

Do not treat “could not verify” as proof that the target record is absent.

### 17.7 Ambiguous key

Use the reported conflicting IDs to locate duplicate target records. Establish one intended record or choose a truly unique portable key, then recompare. The tool will not choose by age, name, or first query result.

### 17.8 Activation failure

1. Record the exact Salesforce error and version state.
2. Check CML Type/Port consistency and ESCO comparison.
3. Check catalog dependencies outside the tool.
4. Do not assume the built-in preflight is complete.
5. Recover CML or associations if the approved rollback condition was reached.
6. Add the redacted scenario to the live evidence matrix.

The tool-specific save/verification refresh is not evidence that activation or
runtime execution succeeded.

### 17.9 Partial association deployment

Preserve reports and archives, recompare, and reconcile actual current state.
Correct only failed rows and retry a fresh selection. A partial response means
some writes are already committed. If `recoveryRequired` is true, the DML
changed records but the unchanged-CML save/verification refresh failed; stop and
use the recovery artifacts rather than interpreting the result as validation.

### 17.10 Active version or Expression Set blocks a write

The tool intentionally fails closed for Active or unknown write status. In
Salesforce, deactivate the exact definition version and/or parent Expression
Set named by the message. Then reload versions and select the exact version
again. Do not retry from a stale browser selection.

### 17.11 Stale server or build

The process computes a 12-character SHA-1 build ID from
`app/cml_tool.py` and every loaded sibling application module:
`cml_analysis.py`, `cml_salesforce.py`, `cml_http.py`,
`cml_artifacts.py`, `cml_lifecycle.py`, `cml_constraints.py`, and
`cml_tool_page.py`. Starting the same build reuses the running server; starting
a different build asks the old local server to shut down and takes over the
fixed port.

If the browser still shows old content:

1. Check the UI build stamp.
2. Restart the tool.
3. Reload or hard-refresh the browser.
4. If another process owns the port, stop it or choose a different `CML_UI_PORT`.

### 17.12 Guide Me on Tool does not open

Reload the local application and verify the current build identifier. Because the
guide is static, Salesforce authentication and API availability are not required.

### 17.13 Test discovery fails

Run discovery from `salesforce-cml-tool/development/`:

```bash
cd /path/to/salesforce-cml-tool/development
python3 -m unittest discover -s tests -v
```

Do not substitute a single test module: the suite is intentionally split
across application, transport, artifact, and guarded-CLI tests.

## 18. Operations

### 18.1 Runtime directories and files

Runtime paths default to `salesforce-cml-tool/development/runtime/`:

- `cml-files/`: fetched CML and two-org comparison copies.
- `cml-backups/`: CML recovery artifacts.
- `association-archives/`: rows captured before deletion.
- `deployment-reports/`: timestamped JSON operation reports.
- `logs/data-deploy-history.jsonl`: append-only association-deploy audit.
- `logs/cml-ui.log`: background macOS launcher output.

Set `CML_RUNTIME_ROOT` to an approved alternate directory to relocate this
runtime tree. The entire default `development/` directory is excluded from Git.
Never force-add it: tests, dependencies, browser binaries/results/caches, and
potentially sensitive CML and recovery evidence are intentionally kept outside
production commits.

### 18.2 Retention

The tool has no automatic retention or pruning. Define policy for:

- minimum retention through the change and rollback window;
- production-data classification;
- approved backup location;
- encryption at rest supplied by the operating system or storage platform;
- secure transfer when artifacts must be attached to a ticket;
- deletion after retention expires; and
- preservation during an incident.

Do not commit runtime artifacts to source control. Treat the default
`development/runtime/` tree, or an overridden `CML_RUNTIME_ROOT`, as potentially
sensitive.

### 18.3 Audit review

After each write:

1. Confirm target org, model, action, timestamp, and OS user.
2. Compare requested IDs with created/deleted results.
3. Review failed and skipped rows.
4. Review verification or validation-refresh state.
5. Confirm backup/archive/report files exist.
6. Attach redacted evidence to the approved change record.

### 18.4 Startup

**macOS background**

From the project root, open `Start Here - CML Tool/` and double-click
`Open CML Tool for macOS.command`. The launcher resolves
`main/app/cml_tool.py`, starts it with `--no-browser` and `nohup`, writes
`development/runtime/logs/cml-ui.log` by default, waits for `/api/ping`, and
opens the browser.

**Linux foreground**

```bash
./Start\ Here\ -\ CML\ Tool/Open\ CML\ Tool\ for\ Linux.sh
# or
python3 main/app/cml_tool.py
```

**Windows foreground**

Open `Start Here - CML Tool/` and double-click
`Open CML Tool for Windows.bat` or, from the project root, run
`python main\app\cml_tool.py`. The launcher resolves the same production
application path. Close its window to stop the tool.

**Alternate port**

```bash
CML_UI_PORT=8900 python3 main/app/cml_tool.py
```

### 18.5 Safe shutdown and restart

- Foreground: press `Ctrl+C`.
- macOS background: double-click
  `Start Here - CML Tool/Stop CML Tool for macOS.command`.
- Protected local API: `POST /api/quit` with the current CSRF token.
- Relaunching a changed build on the same port requests shutdown of the older CML Tool process.

Before restart, wait for any deployment or recovery operation to finish. Process shutdown discards credential and field-probe caches but does not remove artifacts.

## 19. Maintainer guide

### 19.1 Composition and compatibility rule

There is one modular application. Keep behavior in its owning sibling module;
do not add a second monolithic implementation.

- `app/cml_tool.py` is the approximately 846-line composition root. It loads
  sibling files without depending on `sys.path`, wires dynamic dependencies,
  retains compatibility wrappers and patch points, owns deployment locks and
  operation-ID cancellation state, computes the build, and starts the server.
- `app/cml_lifecycle.py` owns exact-version model discovery, fetch, compare,
  deploy, verification, rollback, and unchanged-content refresh.
- `app/cml_constraints.py` owns Expression Set resolution, ESCO export and
  matching, dependency preflight, archives, guarded deployment, and restore.
- `app/cml_salesforce.py` owns `sf` discovery/authentication, JSON/raw REST,
  paginated SOQL with cancellation checks, capability probes, and the
  lowest-level ESCO write allowlist.
- `app/cml_http.py` owns localhost request security and API route dispatch.
- `app/cml_artifacts.py` owns filename normalization, private atomic files,
  integrity hashes, and durable audit appends.
- `app/cml_analysis.py` owns tokenization, tolerant parsing, source ranges, and
  semantic comparison.
- `app/cml_tool_page.py` owns the HTML/CSS/JavaScript page, bounded Myers line
  diff, semantic overlays and draft merges, target copy, and browser
  cancellation behavior.
- `app/utilities/cml_cli.py` is an optional guarded wrapper. It loads
  `app/cml_tool.py` and delegates exact-version fetch or typed-confirmation
  deploy; `fetch-cml.sh` and `deploy-cml.py` are compatibility launchers over
  it. Never put direct Salesforce writes in a utility wrapper.

Dependencies in lifecycle and constraint services deliberately resolve
through the composition root at call time. Preserve that behavior so existing
routes, CLI calls, caches, compatibility names, and `mock.patch.object` tests
continue to intercept the guarded path.

### 19.2 Module and responsibility map

| Module | Primary public/maintenance surface |
|---|---|
| `app/cml_tool.py` | wrapper names, deployment locks, operation registration/cancellation, build and server lifecycle |
| `app/cml_lifecycle.py` | `list_models`, `resolve_exact_version`, `fetch_cml`, `compare_cml`, `deploy_cml`, `rollback_cml`, `_refresh_cml_validation` |
| `app/cml_constraints.py` | `export_constraints`, `compare_constraints`, `deploy_constraints`, `restore_association_archive`, PRC/dependency/duplicate helpers |
| `app/cml_salesforce.py` | CLI discovery, credentials, `rest`, `query_json`, ESCO collection insert/delete |
| `app/cml_http.py` | handler factory, GET/POST routing, Host/Origin/CSRF/body/security-header controls |
| `app/cml_artifacts.py` | safe names, SHA-256, atomic JSON, traversal-safe reads, audit append |
| `app/cml_tool_page.py` | `PAGE`, editor/UI contracts, bounded Myers/coarse diff, semantic merge UI, operation-ID cancellation |
| `app/utilities/cml_cli.py` | guarded `fetch` and `deploy` command adapter |

### 19.3 UI contracts

- All POSTs must use `postJSON`, which adds `X-CML-CSRF`.
- GETs should use `apiGet` and no-store caching.
- Org selectors must retain explicit empty defaults.
- Additions default selected; deletions default unselected.
- Only `isAdd` and `isDel` rows receive action checkboxes.
- `dataRows` adds UI-only `_status`, `_i`, and `_selected` fields.
- Backend status remains authoritative; server-side deploy must never rely on `_status`.
- Status details used for Excel export should remain plain-text-safe.
- Result rendering must keep row-level errors and recovery artifact links visible.
- Guide Me on Tool must remain static: opening it must not call an API or contact
  Salesforce.
- Its eight numbered steps, Read-only/Writes Salesforce labels, recovery
  guidance, and compile/activation/runtime boundary must remain visible.
- New parser nodes used by semantic comparison must preserve half-open source
  coordinates and tolerant recovery of later declarations.

### 19.4 Adding or changing a status safely

1. Define exact backend decision conditions.
2. Decide whether it belongs in `matched`, `sourceOnly`, `targetOnly`, or `stale`.
3. Define add and delete eligibility explicitly; default to neither.
4. Add a `blockNote` that states evidence and user action.
5. Update stats without double-counting.
6. Map backend status to UI status in `compareDataBtn`.
7. Add badge, readable text, filter behavior, chips, and Excel export behavior.
8. Confirm `isAdd`/`isDel` cannot accidentally make it actionable.
9. Repeat the same validation during server-side deployment.
10. Add tests for normal, forged, stale-browser, and partial-result cases.
11. Update this guide and the user README where user behavior changes.

### 19.5 Validation commands

```bash
# From salesforce-cml-tool/
cd development

# Syntax for all application modules and the guarded CLI
python3 -m py_compile ../main/app/*.py ../main/app/utilities/cml_cli.py

# Complete Python suite (108 tests)
python3 -m unittest discover -s tests -v

# Optional browser suite (8 tests, mocked API responses, no Salesforce contact)
npm install
npx playwright install chromium
npm run test:browser

# Print the current 12-character multi-module build hash
python3 ../main/app/cml_tool.py --print-build
```

The build hash covers the composition root and all seven sibling application
modules listed in section 17.11; changing any of them causes a changed-build
relaunch on the fixed port. Run a local smoke test with `--no-browser` if
browser launch is undesirable. Do not point automated tests at any Salesforce
org; the browser suite is specifically designed to avoid Salesforce contact.

### 19.6 Change-review priorities

Review especially carefully any change affecting:

- target alias confirmation;
- exact-version ownership or `ExpressionSetVersion` parent resolution;
- portable identity composition;
- stale or CML-difference classification;
- action eligibility;
- dependency error handling;
- query/DML chunk boundaries;
- `allOrNone`;
- write allowlist;
- ownership revalidation;
- backup/archive ordering;
- exact verification and rollback;
- artifact path or permissions;
- CSRF, Host, Origin, CSP, or request size; or
- audit completeness.
- Parser grammar expansion, recovery boundaries, dependency resolution, source ranges, outcome wording, or local-only behavior.

## 20. Glossary and appendices

### 20.1 Glossary

**Activation:** A manual Salesforce lifecycle action outside this tool. Saving or validation-refreshing CML is not activation.

**Ambiguous key:** A portable key that resolves to more than one candidate target record.

**CML difference:** An association valid against its own exact selected CML
version whose tag is absent from the other exact selected version.

**Dependency preflight:** Read-only checks of implemented catalog prerequisites before an ESCO row is considered deployable.

**Exact duplicate:** Multiple rows with the same portable ESCO comparison key within the exported model scope.

**Fresh target-only:** A row returned in the target-only set by the backend comparison performed during the deployment request.

**Matched evidence:** Source and target IDs retained with proof of portable-key equality.

**Portable key:** A selected business identifier used to locate corresponding reference records across orgs.

**PRC identity v2:** The typed canonical identity containing parent, child,
relationship, component-group, selling-model, and stable relationship
discriminators. Weak legacy PRC archives are not automatically compatible.

**Stale:** An ESCO association whose Type or Port is absent from the same org's
exact selected CML version.

**Validation refresh:** This tool's temporary newline PATCH followed by
restoration and exact verification of unchanged CML after association changes.
It is a save/verification step, not documented activation, compilation, or
runtime proof. Failure after successful DML is partial and recovery-required.

### 20.2 Appendix A — API route summary

All routes are local. POST routes require trusted Host/Origin and `X-CML-CSRF`.

| Method | Route | Purpose | Writes Salesforce |
|---|---|---|---:|
| GET | `/` | Embedded UI | No |
| GET | `/api/ping` | App/build identity and local request token | No |
| GET | `/api/orgs` | Authorized org list | No |
| GET | `/api/debug` | CLI/path/login diagnostics | No |
| GET | `/api/models?org=...` | Every exact model version for selected org | No |
| GET | `/api/backups?org=...&model=...&versionId=...` | Up to 50 newest backups for the exact version | No |
| POST | `/api/fetch` | Fetch exact `versionId` and locally save CML | No |
| POST | `/api/compare` | Fetch exact `sourceVersionId` and `targetVersionId` | No |
| POST | `/api/semantic/compare` | Reanalyze source text and the current target draft locally after a merge/reset | No |
| POST | `/api/operation/cancel` | Cancel the registered long-running comparison identified by `operationId` | No |
| POST | `/api/deploy` | Ownership/status check exact `targetVersionId`, backup, PATCH, verify CML | Yes |
| POST | `/api/rollback` | Ownership/status check exact `targetVersionId`, verify and restore matching backup | Yes |
| POST | `/api/data` | Map exact `versionId` to parent Expression Set and export ESCO | No |
| POST | `/api/data/compare` | Compare exact source/target versions, ESCO, and dependencies | No |
| POST | `/api/data/deploy` | Exact-version ownership/status checks and selected ESCO insert/delete | Yes |
| POST | `/api/data/restore` | Restore absent archived ESCO rows for exact target version/parent | Yes |
| POST | `/api/quit` | Stop local server | No |

The local API is an implementation detail for the embedded UI, not a supported remote integration API.

#### Exact-version payload contract

The browser must send version IDs; the server never substitutes the highest
version number. Representative payload fields are:

```json
{
  "fetch": {
    "org": "sourceAlias",
    "model": "ModelDeveloperName",
    "versionId": "exactSourceVersionId"
  },
  "compare": {
    "sourceOrg": "sourceAlias",
    "targetOrg": "targetAlias",
    "model": "ModelDeveloperName",
    "sourceVersionId": "exactSourceVersionId",
    "targetVersionId": "exactTargetVersionId"
  },
  "deploy": {
    "org": "targetAlias",
    "model": "ModelDeveloperName",
    "targetVersionId": "exactTargetVersionId",
    "content": "CML text",
    "confirmTarget": "targetAlias"
  }
}
```

Constraint-data calls use the same ownership contract:

```json
{
  "compareOrDeploy": {
    "sourceOrg": "sourceAlias",
    "targetOrg": "targetAlias",
    "model": "ModelDeveloperName",
    "sourceVersionId": "exactSourceVersionId",
    "targetVersionId": "exactTargetVersionId",
    "keyField": "Global_Key__c"
  },
  "restore": {
    "targetOrg": "targetAlias",
    "model": "ModelDeveloperName",
    "targetVersionId": "exactTargetVersionId",
    "archiveId": "tool-created-archive.json",
    "confirmTarget": "targetAlias"
  }
}
```

`/api/data/deploy` additionally carries `adds` (source ESCO IDs), `deletes`
(target ESCO IDs), and exact target confirmation. The server ignores
browser-supplied descriptive ownership and rebuilds it from Salesforce.
Association deployment responses include `sourceVersionId`,
`targetVersionId`, `targetExpressionSetId`, target statuses,
`prcIdentityVersion`, row results, backup/archive/report references,
`outcome`, and `recoveryRequired`. The scope note explicitly states that ESCO
data is shared at `ExpressionSet` level, not version-specific.

### 20.3 Appendix B — Artifact schema summary

### 20.3 Appendix B — Artifact schema summary

#### CML backup

Key fields:

- `kind: "cml-backup"`
- `reason`
- `org`, `model`
- `versionId`, `versionNumber`, `versionStatus`
- `sha256`
- `content`
- `createdAt`, `operatingSystemUser`

#### Association deletion archive

Key fields:

- `kind: "association-delete-archive"`
- `targetOrg`, `model`, exact `versionId`, parent `expressionSetId`, `keyField`
- `expressionSetStatus`, `prcIdentityVersion: 2`
- `rows` containing authoritative comparison data and complete portable identity
- `createdAt`, `operatingSystemUser`

#### Deployment report

Common fields:

- `kind: "deployment-report"`
- `action`
- `targetOrg`, `model`
- operation-specific exact source/target version IDs, parent Expression Set
  ID/status, PRC identity version, requested IDs, results, hashes,
  backup/archive references, errors, verification, validation refresh,
  `recoveryRequired`, or rollback details
- `createdAt`, `operatingSystemUser`

#### Association deployment audit line

Key fields include:

- timestamp and OS user;
- source/target org, model, and key field;
- add/delete attempted and succeeded counts;
- outcome and `ok`;
- blocked row labels/reasons;
- backup, archive, and report paths; and
- top-level message.

The JSONL audit is append-only by implementation, not cryptographically chained or centrally immutable.

### 20.4 Appendix C — Recommended sandbox test matrix

Run each scenario with synthetic or approved redacted data and capture comparison, DML, activation, and recovery evidence.

1. **Exact CML match:** exact and semantic modes report no substantive difference.
2. **Formatting/reorder only:** exact diff changes; semantic diff reports equivalence.
3. **Real member change:** semantic diff identifies changed field/relation/constraint.
4. **CML verification failure:** forced mismatch triggers automatic restoration and report.
5. **Tampered backup:** rollback blocks before PATCH.
6. **Exact versions:** every version is listed; missing, stale, and cross-model
   IDs are rejected; an old backup cannot restore another exact version.
7. **Matched ESCO with different IDs:** `matchedEvidence` shows portable equality and different org IDs.
8. **Safe addition:** one unique target reference; row is `ready`; insert succeeds.
9. **Safe deletion:** fresh target-only non-CML-difference row; explicit delete succeeds; archive restores it.
10. **Source exact duplicate:** surplus row is visible and blocked; forged add is rejected.
11. **Target exact duplicate:** surplus target row can be selected deliberately; intended row remains.
12. **Missing portable key:** row is unmappable.
13. **Ambiguous target key:** all candidate IDs are retained and DML is blocked.
14. **Recreated reference:** archive restore resolves the new target ID by the same portable key.
15. **Classification product missing:** dependency is blocked.
16. **Product assigned to another classification:** dependency is unlinked and blocked.
17. **Classification attribute missing/wrong parent:** dependency is blocked.
18. **Dependency key unavailable:** status is unverified, not falsely missing.
19. **PRC identity v2 with Product child:** every group, selling-model, quantity,
    sequence, Boolean, scale, and visibility discriminator changes identity;
    zero/one/multiple candidate handling remains fail-closed.
20. **PRC identity v2 with Classification child:** same discriminator and
    zero/one/multiple coverage; weak legacy archives are rejected.
21. **Expression Set ownership:** no parent and multiple distinct parents block;
    duplicate `ExpressionSetVersion` rows for one parent resolve to that parent;
    associations are demonstrated as parent-shared, not version-specific.
22. **CML-difference source-only:** addition is protected.
23. **CML-difference target-only:** deletion is protected.
24. **Stale source and target rows:** both are excluded from add/delete.
25. **Large deployment:** more than 400 rows produces expected 200-row chunks and repeated preflight.
26. **Partial collection result:** successes persist, failures are reported, retry begins with recompare.
27. **Refresh failure after DML:** response is partial and recovery-required;
    records, backup, archive, and report support reconciliation.
28. **Active write blocking:** Active definition versions and parent Expression
    Sets block before their respective writes; unknown status also fails closed.
29. **Permission failure:** read and write errors are clear and do not broaden access.
30. **Concurrent same-model operation:** second operation is rejected in one process.
31. **Local API abuse:** missing CSRF, remote Origin, untrusted Host, oversized body, and GET shutdown fail.
32. **Activation dependency matrix:** remove or alter one prerequisite at a time, activate manually, and record exact Salesforce behavior separately from save/verification refresh.
33. **Semantic parser syntax:** exercise declarations/types, fixed/range
    cardinality, relation order/aggregates, `^`, `?:`, table rows,
    `SalesforceTable`, `cardinality`, and configured targets.
34. **Semantic parser recovery:** damage an early construct and verify later
    balanced declarations remain available to semantic comparison.
35. **Guide Me on Tool static behavior:** verify all eight steps and safety
    labels render and opening the tab makes no API request.

### 20.5 Attribution

Made with 💙 by Mritunjaya Pancholi. [LinkedIn](https://www.linkedin.com/in/mrpancholi/).

The April 2026 Salesforce CML guide and linked official Salesforce topics are
the language authority. Local examples are illustrative;
`AllPatterns_recommended` is malformed recovery corpus rather than a grammar
oracle. NotebookLM-generated prose may contain unverified runtime claims and is
not an authority for tool behavior.

---

This is a community tool, not an official Salesforce product. Operators are responsible for review, approval, testing, recovery readiness, and the effects of changes in their orgs.
