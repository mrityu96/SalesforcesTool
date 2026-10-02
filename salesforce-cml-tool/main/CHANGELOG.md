# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/) and
this project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [2.0.0] - 2026-10-02

### Added

- Stale-server banner. The page checks `/api/build-status` on load, every
  minute and when the tab regains focus. It asks you to restart the tool when
  Python or template files changed after the server started, or to reload the
  page when only JS/CSS changed.
- Context Definition Fix: the build report now starts with a **Sources**
  section. It shows where Base and Modified came from (org alias, org Id,
  retrieve time, whether the XML was edited afterwards, or "pasted") and which
  standard definition version each one inherits.
- Context Definition Fix: a **Not applied** list after Analyze, also included
  in the build report. It covers schema changes Salesforce refuses on existing
  attributes (`dataType`, `fieldType`, `key`, `transient`), Base content that
  Modified no longer has (the tool never deletes it), and refused node tags.
- Context Definition Fix, Step 4 **Check and deploy commands**:
  - An optional read-only field check. It verifies that every field the result
    hydrates from exists in the chosen org with a compatible type, using the
    Tooling API `FieldDefinition` (not limited by field-level security). Each
    problem is marked "added by this build" or "already in Base".
  - The deployable file name, a `package.xml`, and the exact check-only
    (`--dry-run`) and real `sf project deploy start` commands. They are shown
    only; the tool never runs them.
  - A warning when Base was pasted, was edited, or came from a different org
    than the deploy target.
- Anonymised real release-pair fixtures (Base on 67.11, Modified on 68.26) in
  `development/tests/fixtures/context-definitions/`, so the real-file tests
  always run.
- Compare CML: **Merge all →** in the source pane header applies every
  source change to the target draft in one step.
- Compare CML: a **←** revert arrow in the merge rail beside each change
  between the target draft and the target fetched from Salesforce. Clicking
  it restores the original lines for that change only. This covers merged
  hunks, Merge all, and direct target edits. Changed draft lines get a marker
  in the target gutter and stay visible when "Show only differences" is on.
  Nothing is written to Salesforce.
- Browser-session Chrome/Edge extension under `chrome-extension/` that lists
  orgs from open Salesforce tabs, reads the classic/`my.salesforce.com` `sid`,
  fetches Constraint CML over REST, compares exact versions, and performs
  guarded deploy/rollback/deactivation plus Constraint Data (ESCO) view,
  compare, deploy, cancel, and restore. Backups, deletion archives, and
  reports live in IndexedDB in this Chrome profile. Fetch can download a
  `.cml` file; recovery backups, association archives, and deployment
  reports can be downloaded and imported as JSON. Lightning-only tabs
  surface as unusable orgs with an API-session warning. A sideload zip is
  built with `chrome-extension/scripts/pack.py`. No Python or CLI in this
  path. Chrome Web Store publish is still out of scope.
- Local HTTP CORS/Origin allowlist for the pinned extension ID, plus an
  `OPTIONS` preflight, still used by the desktop Python tool. Extra IDs can
  be added with `CML_EXTENSION_IDS`.
- **Context Definition Fix** view (merged from the standalone XML Tool). It
  retrieves `ContextDefinition` metadata read-only from the selected target
  org (Base) and source org (Modified) through the Metadata API
  (`listMetadata`, `retrieve`, `checkRetrieveStatus`) using the existing CLI
  login. Paste still works. The view analyzes additions and value changes,
  lets you pick changes, and builds a patched Base to copy or download.
  Nothing is deployed back to the org. New routes:
  `GET /api/context-definitions`, `POST /api/context-definitions/retrieve`,
  `POST /api/cdfix/analyze`, and `POST /api/cdfix/build`.
- README screenshots refreshed for the current UI, with three new ones:
  Context Definition Fix analysis, its check-and-deploy-commands step, and
  XML Tools. `npm run screenshots` in `development/` regenerates all nine with
  synthetic data (`screenshots.config.js`,
  `scripts/screenshots/capture.spec.js`); every Salesforce-facing API is
  intercepted. The README walkthrough and view list now describe all six views.
- **XML Tools** view with a Compare | Merge | Dedup sub-navigation (merged
  from the standalone XML Tool; routes `POST /api/xml/compare|merge|dedup`).
  The engine lives in `main/app/cml_xml.py`, and retrieval lives in
  `main/app/cml_context_definition.py`.
- The Chrome extension shows a "requires the local CML Tool" notice on both
  new views. Their routes are local-server only for now.

### Changed

- **Guide Me is now Help Me**, a built-in handbook with two sub-tabs: the
  **CML Deployment Guide** (13 steps, from installation and login through
  fetch, compare, deploy, activation, Product associations, recovery, and
  troubleshooting) and the **Context Definition Deployment Guide** (11 steps,
  from retrieve and analyze through build, field check, the generated `sf`
  commands, and verification). Each step has a sample-data screenshot, a
  read-only or Salesforce-write badge, and a "check before moving on" note.
  Screenshots are regenerated by `npm run screenshots` into
  `main/assets/help/`. Opening Help Me still makes no API request.

### Fixed

- The Salesforce Release value in the org cards is no longer cut off on
  narrower screens.
- Source and Target org cards are equal height and about 10% more compact,
  with the org and its exact CML version side by side (50:50). The
  "runtime status can differ" note moved to the target version label's
  tooltip, and the Active/Inactive pill no longer truncates.
- Fetch CML, Compare source ↔ target, and Compare data are double width at
  normal height, with the header pill's blue-to-cyan gradient. Analyze
  differences moved into Context Definition Fix step 1, centered at half the
  page width with the same gradient; input errors appear under it and results
  scroll into view.
- Org ID and Salesforce Release sit in a tinted box on each org card (green
  for source, purple for target) with icons and a copy button for the Org ID.
- Org cards show the Salesforce release under the Org ID (for example
  "Release · 262.14.26 · Summer '26 Patch 14.26"). The patch number comes from
  the public Salesforce Trust status API for the org's instance, with the
  org's own release name as a fallback; read-only and cached per org.
- Constraint Data layout: the match-key field and its help sit beside
  **View Source Org Data** and **Compare data**; source pills on the left,
  target pills on the right, comparison pills below; repeated counts removed
  (overlapping dependency-finding and exact-duplicate pills, the count line in
  the compare status, the count in the deploy button, and the second deploy
  button beside search). Page side gutters are halved.
- Constraint Data deployment results and blocked table rows now list each
  catalog dependency problem (for example, every missing classification
  attribute with its key) as its own bullet under one headline, instead of one
  run-on paragraph. The saved report and audit log keep the full text.
- Constraint Data workspace readability: compact foreign-key banner with
  **Learn more**, status chips grouped into Matching, CML definition,
  Dependencies, and Data quality with consistent colors, **Compare data** as
  the primary action, a deploy button that shows the selected count, a sticky
  filter row with search and a deploy shortcut, larger table text and rows
  with a highlighted selected row, Active/Inactive pills on the selected CML
  versions, and click-to-copy Org IDs.
- Context Definition Fix no longer freezes or paints partially with large
  Context Definitions. The Base, Modified, and Output panes (and the XML Tools
  panes) are now CodeMirror editors that render only the visible lines, with
  XML highlighting, built-in line numbers, and Cmd/Ctrl+F search. Measured in
  Chrome with two ~32,000-line Context Definitions: switching back to the view
  went from an 836 ms freeze to no long task, retrieve and build from
  200–330 ms layout stalls to none, and rendered DOM from ~6.9 MB of textarea
  text to about 50 lines per pane.
- Context Definition field check no longer reports false "Missing field"
  problems. Parts of compound fields (for example `ShippingStreet` from
  `ShippingAddress`, or `Site__Latitude__s` from a custom geolocation) count
  as present. The check now queries at the org's newest API version instead
  of the tool's pinned one, so fields added in newer releases are found. The
  status line shows which API version was used.

- Context Definition Fix build correctness:
  - A context attribute is no longer blocked because another node already
    uses the same title. Real org exports share attribute titles across
    nodes; only **tag** titles are unique across a definition. The old block
    also left the attribute's mapping pointing at nothing.
  - Tag uniqueness now covers node-level tags, tags added earlier in the same
    build, tags inside newly copied node blocks, and tags merged in by
    attribute updates. A clashing tag is dropped from the incoming element,
    and Base's existing tags are never removed.
  - Selecting a mapping, node-mapping block, or mapping block whose context
    attribute or node is missing from Base now adds that attribute or node
    from Modified. A mapping whose attribute exists in neither file is
    skipped with an error instead of written.
  - A Base mapping is replaced by destination only when Modified drops the
    old attribute name. This stops two attributes that share a destination
    from replacing each other.
  - New selectable **Mapping Settings** changes (missing
    `contextMappingIntents`, becoming the default mapping (the previous
    default is turned off), and description) and **Node Tag** additions.
    Node tags that duplicate another tag are listed in the analysis summary
    instead of offered.
  - Hydration references (`ctxAttrHydrationCtxs/contextQueryAttribute`)
    that are raw `ContextAttribute` Ids are now renamed to
    `<object node>_QA_DE_<attribute on that node>`. The attribute is matched
    exactly first, then by title without its node prefix (for example
    `ConstraintEngineNodeStatus__c` matches
    `AssetConstraintEngineNodeStatus__c`). Previously the same Id could be
    renamed to a missing attribute or to the wrong node. Existing names that
    point at a missing attribute are repaired when a match exists. Each
    rewrite is listed in the build report. Attributes that a hydration
    reference queries are pulled in as dependencies.
  - When Base and Modified inherit different versions of the same standard
    definition (`inheritedFromVersion`), items whose Modified element is
    inherited from that standard definition are marked as **Salesforce
    release** content. They are grouped last and start unselected, and the
    analysis summary explains why. Building with any of them selected,
    including ones pulled in as dependencies, adds a warning to the report and
    the build status. These elements reach Base when its org is upgraded;
    copying them earlier can fail because the fields they read may not exist
    there yet.
  - Every build result is validated. Duplicate node, attribute, tag,
    mapping, or node-mapping identities, dangling node or attribute
    references, and more than one default mapping are build errors. Problems
    already present in Base are reported as warnings.
- Service worker registration: `session.js`, `artifacts.js`, and `esco.js`
  no longer share a top-level `const CORE` (Chrome `importScripts` is one
  global scope). Unpacked loads no longer include a `.pem` under
  `chrome-extension/`.

### Changed

- The Chrome/Edge extension is no longer part of this repository. It moved,
  with its scripts, tests, and signing key, to a separate
  `salesforce-cml-tool-chrome-extension/` folder next to this one. The server
  still accepts the pinned extension ID.
- The standalone XML Tool (`salesforce-xml-tool/`) is retired. Its "Open XML
  Tool" launchers now open the CML Tool, and its server prints a notice.
- Browser API client can talk to the extension service worker
  (`CmlRuntime.transport = "extension"`) or to the local Python server.
- Center navigation order is now Fetch & Deploy CML, Constraint Data,
  Compare CML, Context Definition Fix, XML Tools, Guide Me. The header stays
  on one row and never shrinks its type. When space runs out, the
  lowest-priority items move into a `More ▾` menu, which labels the active
  view when that view is hidden in the menu. Fetch & Deploy CML and Compare
  CML always stay visible. The supported minimum width is 1024px; the old
  second-row nav wrap and phone header layouts are removed. Below 1760px,
  Donate/About and "Runs locally" collapse to icons. Below 1860px, the
  version/build text moves into the "Runs locally" tooltip.
- The "Night mode" text button is now a sliding day/night switch
  (`role="switch"`) that honors reduced motion.
- `/api/orgs` now answers from an in-memory stale-while-revalidate cache
  instead of waiting 4–5s for `sf org list`. The server starts one background
  refresh at launch. The cache revalidates in the background only when older
  than 60s, and a guard stops overlapping refreshes. Until the first list
  arrives, the endpoint returns a `loading` state, which the page polls.
  Background refreshes keep existing org selections. The Source and Target
  org menus gain a **Refresh org list** action (`POST /api/orgs/refresh`,
  CSRF-protected) so a newly authenticated org appears right away.

### Security

- Org discovery no longer asks the CLI for access tokens
  (`SF_TEMP_SHOW_SECRETS`) and no longer pre-fills the credential cache.
  Tokens are fetched lazily per org by the operation that needs them.
- The browser-session extension keeps the Salesforce session in the service
  worker. Org pickers receive alias, username, and org Id only.
- `chrome-extension://` origins remain denied on the Python server unless the
  ID is the pinned packaged extension or an explicit `CML_EXTENSION_IDS`
  entry. Host checks, CSRF, request-size limits, and loopback binding are
  unchanged for that server.

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
- Explicit exact-version CML deactivation through
  `ExpressionSetVersion.IsActive=false`, with typed target confirmation, shared
  process-safe locking, lifecycle reports, and read-after-write verification.
  Direct activation fails closed because `IsActive=true` bypasses Salesforce
  Constraint Builder compilation and can mark invalid CML active.
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

[Unreleased]: https://github.com/mrityu96/SalesforcesTool/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/mrityu96/SalesforcesTool/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/mrityu96/SalesforcesTool/releases/tag/v1.0.0
