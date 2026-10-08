<!-- cover -->
# Salesforce CML Tool
Security & Operations Summary — quick-check edition for review and approval
Product version: 2.0.2 (desktop tool and companion Chrome extension)
Document version: 1.2 · Date: 8 October 2026
Owner and maintainer: Mritunjaya Pancholi
Classification: Internal — for security review
Status: Submitted for approval
<!-- /cover -->

# Document control

| Field | Value |
|---|---|
| Document | Salesforce CML Tool — Security & Operations Summary, v1.2, 8 October 2026 |
| Product reviewed | 2.0.2 desktop tool (`main/VERSION`) and Chrome extension 2.0.2 (`manifest.json`) |
| Review type | Design and code review with a self-assessed control mapping; not a third-party penetration test |
| Owner | Mritunjaya Pancholi |
| Approvers | Information Security, Salesforce Platform Owner, Change Advisory Board (CAB) |
| Source of truth | The 2.0.2 source code. Where other documents disagree, the code wins (section 8.2) |

| Version | Date | Change |
|---|---|---|
| 1.0 | 4 October 2026 | First quick-check edition |
| 1.1 | 4 October 2026 | Standalone edition; factual review against the 2.0.1 code |
| 1.2 | 8 October 2026 | Aligned with product 2.0.2 (no Activate/Deactivate UI; read-only target status; PRC identity mismatch messages) |

**How to use this document.** Approvers can decide from sections 1, 7, 8 and 15. Operators should read sections 11 to 13 before their first deployment.

> **Google Docs tip:** after importing, place the cursor under **Contents** and choose **Insert → Table of contents**, so the list links to every heading.

# Contents

1. At a glance — decision summary
2. What the tool is and why it exists
3. Architecture and trust boundaries
4. Features and the Salesforce write boundary
5. Data, identity and credentials
6. Security controls
7. Threats and risk register
8. Conditions of approval and documentation corrections
9. Control mapping (OWASP Top 10 and ASVS)
10. Secure development and supply chain
11. Installation, hardening and operation
12. Getting unstuck during a deployment
13. Incident response and recovery
14. Known limitations
15. Approval record

<!-- pagebreak -->

# 1. At a glance — decision summary

The Salesforce CML Tool is a **locally run, single-operator utility**. It moves Revenue Cloud **CML models** and their **ESCO associations** between Salesforce orgs that the operator is already authorised to use. It also provides:
- read-only comparison of two orgs;
- a best-practice checker;
- a Context Definition helper;
- XML utilities.

| Question | Answer |
|---|---|
| What can it change in Salesforce? | Only the CML text of one exact **non-Active** version (including a same-content validation refresh), deactivation of one version, and ESCO insert and delete. Nothing else |
| Can it do more than the user? | No. It runs with the operator's own Salesforce rights and only adds restrictions on top |
| Is it exposed on the network? | No. The desktop tool listens on `127.0.0.1` only; the extension has no server at all |
| Does it store credentials? | No. Tokens and sessions live in memory only and are never written, logged or shown |
| Third-party code at runtime? | One MIT-licensed editor bundle (CodeMirror 6), stored locally. Python standard library only |
| Findings | **No critical or high.** 5 medium, 15 low, 2 informational (section 7) |

**Recommendation: approve for supervised use by named operators,** subject to the eight conditions in section 8. The most important are:
- a managed single-user workstation;
- the go/no-go checklist for every production write;
- the five medium items R-01 to R-05 either fixed or accepted in writing. R-05 must be fixed before the next push, R-01 to R-03 in release 2.0.2, and R-04 partly through the way the extension is distributed.

# 2. What the tool is and why it exists

A working CML model is two things that must agree:
- the **CML text** on `ExpressionSetDefinitionVersion`;
- the **ESCO rows** that bind each CML tag to catalog records.

Record IDs differ in every org, and the two parts can drift apart. Salesforce also offers no undo for an overwrite. Copying by hand, with change sets or with Data Loader misses these traps.

| Problem done by hand | What the tool does |
|---|---|
| IDs differ between orgs | Matches records by a **portable business key** and re-resolves target IDs at deploy time |
| CML and ESCO drift | Reads each org's CML tags; marks stale and mismatched rows as not deployable |
| Missing catalog data | Read-only dependency check that blocks rows before any write |
| Noisy line diffs | Line diff plus a structural (semantic) comparison |
| No undo, partial failures | Backup first, byte-exact verify, automatic rollback, deletion archives, per-row results |

**Two forms, one user interface:**

| Form | How it runs | How it reaches Salesforce |
|---|---|---|
| Desktop tool | Python 3.9–3.13 process on `127.0.0.1`, opened in a local browser | Operator's existing Salesforce CLI (`sf`) login. Uses REST API v66.0, plus read-only Metadata SOAP retrieves and Tooling queries, over HTTPS |
| Chrome extension | Manifest V3 extension, no server | The operator's open Salesforce browser session (`sid` cookie) |

**Users:** a few named Revenue Cloud developers and release engineers who already have access to both orgs. It is not a self-service or multi-user tool.

# 3. Architecture and trust boundaries

![Figure 1 — Components and data flows. Everything except Salesforce runs on the operator's workstation.](summary-charts/fig1-architecture.png)

| Boundary | What crosses it | Main controls |
|---|---|---|
| TB-1 Web pages and other processes → local server | HTTP to `127.0.0.1` | Loopback bind, Host and Origin allowlists, CSRF token, 10 MiB cap, generic errors |
| TB-2 Browser UI → backend | Selections, CML, XML | Server treats all UI input as untrusted and re-checks it |
| TB-3 Backend → Salesforce CLI | Fixed commands, argument list | No shell on macOS/Linux; 120 s timeout |
| TB-4 Tool → Salesforce | HTTPS with bearer token or session | TLS verified; write allowlist; typed confirmation; Active blocking |
| TB-5 Tool → local storage | Backups, archives, reports | Private folders and files, atomic writes, safe filenames |
| TB-6 Pages / extensions → extension worker | Chrome messages | No external messaging; other extension IDs rejected |
| TB-7 Tool → Trust status API | Instance name only | Read-only, no token, 6 s timeout |

**Deployment model:** one operator, one workstation, one process or Chrome profile. There is no server installation, service account, scheduler or shared database. In 2.0.1 the extension does not talk to the desktop server.

# 4. Features and the Salesforce write boundary

| View | Purpose | Writes Salesforce? |
|---|---|---|
| Fetch & Deploy CML | Fetch, edit, check, deploy, restore. Target status is read-only | **Yes**: CML text |
| Constraint Data | Compare and deploy ESCO associations by portable key; restore | **Yes**: ESCO insert/delete |
| Compare CML | Exact and semantic comparison between two orgs | No |
| Context Definition Fix | Analyse and build corrected XML; check fields; *show* deploy commands | No; commands are never run |
| XML Tools | Compare, merge, de-duplicate XML | No; local only |
| Help Me | Static step-by-step guides | No; makes no API call |

**The complete write surface:**

| Write | What exactly | Preconditions |
|---|---|---|
| CML deploy | PATCH `ConstraintModel` on one exact version | Status known and not Active; version belongs to the model; typed alias; backup saved; lock held |
| CML rollback / restore | Same PATCH with the backed-up text | As above, plus the backup's SHA-256 matches, it belongs to the same version, and a fresh safety backup is taken first |
| Validation refresh | Same PATCH: unchanged CML plus a newline, then the original | Only after successful ESCO changes; verified byte for byte; a failure gives partial and recoveryRequired |
| Deactivation | Not exposed in Fetch & Deploy. Deactivate in Constraint Builder. Server still refuses `IsActive=true` | Activation is **always refused** |
| ESCO insert | Composite insert, at most 200 per chunk, allOrNone=false | No Active version under the parent Expression Set; fresh server-side status "ready"; references and dependencies re-resolved per chunk; records built on the server with four fields only |
| ESCO delete | Delete by ID, at most 200 per chunk | No Active version under the parent; IDs start with `1JE`; fresh "only in target" rows (not CML differences) found again under the target model; archive saved first |

The tool never writes:
- products, classifications or attributes;
- component groups, relationships or selling models;
- Context Definition metadata.

It never runs a Metadata API deploy. **Activation is done in Salesforce Constraint Builder**, so the platform compiler validates the model.

# 5. Data, identity and credentials

| Data | Where it is held | How long | Class |
|---|---|---|---|
| Salesforce token (desktop) or session (extension) | Process / service-worker memory only | Until exit | **Secret** |
| CML text, ESCO rows, catalog identifiers | Editor, backups, archives, reports | 90 days by default | Confidential |
| Context Definition XML, XML Tools files | Memory; operator downloads | Not stored | Confidential |
| Org alias, usernames, OS user | Deployment reports; audit log | Reports 90 days by default; the audit log is append-only and never pruned automatically | Internal |

**Data handled**
- **What the tool never handles:** customer records, payment data, passwords, MFA codes, OAuth client secrets, refresh tokens and private keys.
- **Personal data:** if a catalog key field holds personal data, it will appear in comparisons and archives.
- **What leaves the workstation:** data goes only to the selected Salesforce org. The public Salesforce Trust status API receives the instance name, nothing more. There is no telemetry, analytics, CDN or update check.

**Identity and access**
- **Identity:** the tool has no accounts of its own. On the desktop it inherits the OS user and the CLI login; in the extension, the Chrome profile and browser login. Every report records the OS user.
- **Least privilege:** use a named user with a dedicated permission set containing only the following. **Never grant Modify All Data.** Exact permission names depend on the licence; read-only reviewers need only the Read rights.

  | Permission | Objects or fields |
  |---|---|
  | Read | ExpressionSetDefinition, ExpressionSetDefinitionVersion, ExpressionSet, ExpressionSetVersion, ExpressionSetConstraintObj, and the catalog objects (Product2, ProductClassification, ProductClassificationAttr, ProductRelatedComponent, ProductComponentGroup, ProductRelationshipType, ProductSellingModel) with the chosen key fields |
  | Edit | ConstraintModel and IsActive |
  | Create and Delete | ExpressionSetConstraintObj |
  | API Enabled | — |
  | View Setup or Modify Metadata | Only for the Context Definition helper |

- **Separation of duties** comes from the change process:
  - a peer reviews the differences;
  - a change record names the exact versions;
  - where possible, a second person does the activation.

**Token handling (desktop)**
- The token is read from `sf`, with a fallback when the CLI output is redacted. A value counts as a token only if it contains `!` and not `REDACTED`.
- It is held in memory, never returned to the browser, refreshed once on expiry and discarded at exit.
- It is sent with TLS verification to the instance URL the CLI provides. That URL is not yet checked to be https on a Salesforce domain (R-09).
- Token-shaped text is redacted from error messages.

# 6. Security controls

## 6.1 Local API (desktop)

The server binds to `127.0.0.1`, and there is no option to bind elsewhere.
- **Host header:** must be a loopback name, which blocks DNS rebinding.
- **Origin header** (on POST and OPTIONS): any Origin present must be a loopback host or an allowlisted extension (the pinned ID, plus any in `CML_EXTENSION_IDS`). Requests with no Origin (non-browser local clients) are accepted.
- **CSRF:** every POST must carry the per-process CSRF token.
- **Size:** bodies are capped at 10 MiB.
- **Response headers:** a strict Content Security Policy, plus no-framing, no-sniff and no-referrer headers.

As a result, a malicious web page cannot read the token, post to the API or frame the UI.

## 6.2 Input validation

- SOQL values are escaped, and IDs, key fields and object names must match fixed patterns.
- The CLI is called with an argument list and no shell.
- File reads use the base name only.
- **XML:** the parser never resolves external entities, so XXE is not possible. Entity expansion is still possible on expat older than 2.4.1, such as the macOS system Python 3.9.6, which ships expat 2.2.8 (R-01).
- **HTML:** escaping in the UI is inconsistent; the CSP compensates (R-15).

## 6.3 Change safety

Twelve layers protect the write paths. Layer 6 applies to data deploys, and automatic rollback to CML writes:

![Figure 2 — Defence in depth: checks before, during and after the Salesforce writes.](summary-charts/fig2-defence-layers.png)

## 6.4 Chrome extension

**Permissions and isolation**
- **Permissions:** `cookies`, `tabs`, `alarms` and `storage` (`storage` is unused and should be removed), plus Salesforce host permissions.
- **Isolation:** no content scripts and no external messaging.

**When it accepts a session cookie.** Only if all of these hold:
- the cookie is `secure`;
- its org-ID prefix matches the org;
- its domain is an API-usable host (Lightning, Visualforce and setup hosts are rejected);
- the tab is https and is not a login, test or help host.

It then confirms the identity through the identity URL or `/services/oauth2/userinfo` before use.

**Differences from the desktop tool.** It has the same write guards, with two exceptions:
- its lock is per service worker only;
- it keeps no JSONL audit log; reports and backups are held in IndexedDB, with at most 50 items per target.

**Key concern:** it acts with the operator's full browser session and is loaded unpacked, so the integrity of its code is critical (R-04).

## 6.5 Logging and storage

**What is recorded**
- Every write produces a JSON deployment report. On the desktop, every data-deploy call adds exactly one audit line, rejected calls included.
- Tokens are never logged.

**How files are stored**
- **Permissions:** folders are `0700` and files `0600`.
- **Windows:** POSIX modes are not enforced; files inherit the parent folder's ACL, so keep the runtime folder inside the operator's profile.
- **Retention:** JSON artifacts are pruned after 90 days by default. The JSONL audit log is never pruned automatically.
- **Encryption:** the application does not encrypt files, and the audit log is not tamper-evident. Use full-disk encryption.
- **Authoritative record:** Salesforce Setup Audit Trail and Event Monitoring.

# 7. Threats and risk register

**Threat actors considered:**
- a malicious website;
- another local user;
- malware running as the operator;
- a rushed operator;
- a hostile input file;
- a supply-chain attacker;
- a network attacker.

| STRIDE | Main threats | Residual |
|---|---|---|
| Spoofing | Forged local requests; fake extension; wrong org targeted; cookie from another org | Low |
| Tampering | Forged statuses; altered backup; modified extension folder; replaced release; man-in-the-middle | Low; **Medium** for extension backups (R-03) and unpacked extension (R-04) |
| Repudiation | Operator denies a change; local audit edited | Low; Salesforce server logs are authoritative |
| Information disclosure | Token in logs; artifacts read by others; diagnostics output; UI exfiltration; real IDs in test files | Low; **Medium** until R-05 is fixed |
| Denial of service | XML entity expansion; deep nesting or zip bomb; huge diffs; launcher kills another process | Low; **Medium** for R-01 |
| Elevation of privilege | Alias injection on Windows; SOQL or HTML injection; writes outside the surface; local process drives the API | Low; **Medium** for R-02 on Windows; local process accepted under C-1 |

![Figure 3 — Findings by severity, and where each one sits on the likelihood × impact grid.](summary-charts/fig3-risk-overview.png)

**The five medium findings:**

| ID | Finding | Fix |
|---|---|---|
| R-01 | XML parsing does not reject `DOCTYPE`/`ENTITY`; old expat on macOS system Python allows entity expansion | Reject them before parsing; require a current Python |
| R-02 | Org alias not validated before the CLI; on Windows `cmd.exe` re-parses it | Validate every alias against a strict pattern |
| R-03 | Extension computes a SHA-256 for imported backups that have none, so any imported file passes the integrity check and can drive a rollback | Mark imports, require the hash, extra confirmation |
| R-04 | Extension has broad permissions and is distributed unpacked | Remove `storage`, narrow hosts, deploy by Chrome policy |
| R-05 | A real UAT username and org ID are in a test harness file | Move to local config; synthetic test values |

**The 15 low findings:**

| Finding | Finding | Finding |
|---|---|---|
| R-06 Zip size limit (zip bomb) | R-07 Constant-time token comparison | R-08 Nonce reuse |
| R-09 Instance-URL validation | R-10 URL encoding | R-11 Temp-file permissions |
| R-12 Error detail | R-13 Debug-route output | R-14 Deploy-plan alias |
| R-15 HTML escaping | R-16 Artifact encryption | R-17 Cross-machine locks |
| R-18 Launcher behaviour | R-19 CI pinning; no SBOM, signing or provenance | R-20 Release packaging |

**The two informational findings:**
- **R-21:** extension test gaps.
- **R-22:** the message handler checks `sender.id` only.

![Figure 4 — When each finding is fixed. All five medium items are due before or in 2.0.2, or are accepted in writing.](summary-charts/fig4-remediation.png)

# 8. Conditions of approval and documentation corrections

## 8.1 Conditions

| # | Condition | Owner |
|---|---|---|
| C-1 | Managed, single-user, full-disk-encrypted workstation; named operators only | Operator's manager |
| C-2 | Every production write under an approved change record and the go/no-go checklist (section 11) | Change owner |
| C-3 | R-01 to R-05 fixed in 2.0.2 (R-05 before the next push; R-04 partly by distribution), or accepted in writing by Information Security (section 15) | Tool owner |
| C-4 | The sandbox validation matrix (39 test cases covering save, restore, deactivation, adds, deletes, partial failure and Active blocking) run on 2.0.2 before first production use, with a signed test record | Tool + platform owner |
| C-5 | Dedicated least-privilege permission set; no Modify All Data | Platform owner |
| C-6 | Runtime folder kept in the operator's profile; never committed or shared unredacted | Operator |
| C-7 | Extension installed by managed Chrome policy or from the checksummed zip | Desktop engineering |
| C-8 | Documentation corrections D-01 to D-08 made in the next release | Tool owner |

## 8.2 Documentation corrections

The project's README, guides and in-app Help differ from the 2.0.1 code in eight places:

| ID | Correction |
|---|---|
| D-01 | The extension calls Salesforce directly with the browser session; it is not a client of the local API |
| D-02 | The real test counts are 225 Python tests and 38 Playwright tests |
| D-03 | There is no `SF_PATH` setting |
| D-04 | The module sizes and counts are out of date |
| D-05 | The extension Help text wrongly mentions 127.0.0.1 and a CLI login |
| D-06 | `storage` is unused |
| D-07 | The CLI timeout is 120 s, not 30 s |
| D-08 | The in-app Help Me guide puts *Activate* (step 10) before *Deploy Product associations* (step 11), so users following it get stuck. Association deploy, delete and restore are all blocked while any runtime version under the parent Expression Set is Active. The correct order is in section 11 |

# 9. Control mapping (OWASP Top 10 and ASVS)

The mapping is self-assessed and was checked against the code.

| OWASP Top 10 (2021) | Position | Open gaps |
|---|---|---|
| A01 Broken access control | Server-side re-validation; two-layer write allowlist; typed confirmation | — |
| A02 Cryptographic failures | TLS verified; strong random CSRF token; SHA-256 integrity | Artifacts rely on disk encryption (R-16) |
| A03 Injection | SOQL escaping; patterns; argv without shell; strict CSP | R-02, R-15 |
| A04 Insecure design | Narrow write boundary; fail-closed; backup first; no activation | — |
| A05 Security misconfiguration | Secure headers by default; debug off; no bind option | — |
| A06 Vulnerable components | Standard library only; bundle checked byte for byte | R-01, R-19 |
| A07 Authentication failures | Delegated to Salesforce login with the org's SSO/MFA | — |
| A08 Integrity failures | Reproducible releases with SHA256SUMS; backup hash checks | R-03, R-04, R-19 |
| A09 Logging and monitoring | Reports and audit line; Salesforce logs authoritative | R-16 |
| A10 SSRF | Only the CLI-given instance URL and a fixed Trust URL | R-09 |

**ASVS 4.0.3 results**

| Result | Areas | Open gaps |
|---|---|---|
| Met | Access control, anti-CSRF, no tokens in logs, TLS, CSP, framing, CORS, file paths | — |
| Partly met | Input allowlists, sanitisation and output escaping, OS-command protection, the XML parser, component currency | R-01, R-02, R-15, R-19 |
| Mostly met | Generic error messages | R-12 |
| Not applicable | Authentication (V2), because it is delegated to Salesforce; cookie attributes (V3.4), because the tool sets no cookies | — |

# 10. Secure development and supply chain

| Area | Position |
|---|---|
| Ownership | Single maintainer; MIT licence; semantic versioning; changelog per release |
| CI on every change | Version consistency; compile; 225 Python tests (3.9 and 3.13); secret and runtime-file hygiene; `npm audit`; byte-for-byte editor bundle check; offline-asset check; 38 Playwright tests; reproducible-release dry run |
| Release | Tag-only; tag must equal the code version; fixed build timestamp; archives plus SHA256SUMS; least-privilege tokens |
| Runtime dependencies | Python standard library; CodeMirror 6 / Lezer (MIT, vendored); the operator's `sf` CLI |
| Dev-only (never shipped) | esbuild, Playwright; pinned by lockfile |
| Not yet in place | Signing, SBOM, build provenance, SHA-pinned actions, Dependabot, CodeQL, CODEOWNERS (R-19 and recommendations) |

# 11. Installation, hardening and operation

## 11.1 Install

1. Download the release and its `SHA256SUMS`, and verify the checksum.
2. Extract it into the operator's profile.
3. Start it with the launcher in `Start Tool Here/`. Use a current Python (3.11+ from python.org or Homebrew) rather than the macOS system Python (R-01).
4. As the same OS user, log in with `sf org login web --alias <alias>`.

## 11.2 Harden

- **Runtime folder:** keep `CML_RUNTIME_ROOT` private, and set retention long enough to cover the rollback window.
- **Debug:** leave `CML_DEBUG` off.
- **Extension:** install it by Chrome Enterprise policy or from the checksummed zip, in a dedicated admin profile.
- **Salesforce side:** use a dedicated permission set and a short session timeout, and keep Setup Audit Trail and Event Monitoring on.

## 11.3 Supervised deployment sequence

![Figure 5 — The approved order. Associations go before activation, because the tool blocks association writes while any version under the parent Expression Set is Active.](summary-charts/fig5-deploy-sequence.png)

**Within the sequence**
- Confirm the CML report and SHA-256 verification after step 5.
- Before step 7, resolve every row that is not ready: CML difference, ambiguous, blocked, unverified or unmappable.
- In step 7, deploy additions first, compare again, then delete. If the model is live in production, it stays inactive during this window, so plan the change window for it.

## 11.4 Go/no-go checklist

**GO only if every check passes.**

| Area | Checks |
|---|---|
| Change control | The approved ticket names source, target, model, exact versions and operator. A peer reviewed the exact and semantic differences. Planned ESCO additions and deletions are attached. Deployment and rollback owners are available |
| Environment | Aliases selected explicitly and checked independently. Login or session valid. Read and write permissions tested. Storage private, writable and with space. No other process or deployment on the same model. Approved tool version with verified checksum |
| Data and dependencies | Portable key approved, populated and unique. No ambiguous, blocked, unverified or unmappable addition. Every CML difference understood. Stale rows excluded. Catalog prerequisites deployed separately. No multiple-Expression-Set ambiguity. Version mapping and non-Active status refreshed just before the operation |
| Validation | Sequence passed in sandbox/UAT. Activation tested manually. Safe add, safe delete, partial failure, CML rollback and archive restore exercised. Smoke tests and expected results written down |

**NO-GO** if any of these is uncertain: the target, model, key, Expression Set, dependency, backup location or recovery owner.

# 12. Getting unstuck during a deployment

![Figure 6 — The four most common stuck points and the fix for each.](summary-charts/fig6-unstuck.png)

**Three rules that unblock most cases.**
- **Refresh, then reselect** the exact version after any change in Salesforce.
- **Compare again** after every write. The tool never refreshes a comparison silently.
- **Do catalog data and activation in Salesforce.** The tool does neither.

| Step | Message (as shown by the tool) | Fix |
|---|---|---|
| Install / start | "The Salesforce CLI ('sf') was not found…" or "Could not start server on port 8787" | Start the tool from a terminal where `sf --version` works; set `CML_UI_PORT` to another port |
| Choose org | "Salesforce rejected the saved login…" | `sf org login web --target-org <alias>`, then **Refresh org list** |
| Check target | "…this exact runtime CML version is Active" | Pick an Inactive version, or deactivate it in Salesforce Constraint Builder, then **Check target status** again |
| Check target | "…has no runtime ExpressionSetVersion. Activate it once…" | Agree with the model owner first, because this briefly makes the version live. Then activate once in Constraint Builder, deactivate, refresh and reselect |
| Deploy CML | Button stays grey; "Production safety check failed" | Type the target alias exactly, including case |
| Deploy CML | "Deploy failed…" followed by a Salesforce error | Read the code: expired session, missing permission, record lock or API limit |
| Associations | "No target … has <key> matching…" or "Blocked — catalog dependency" | Deploy the catalog record through its own process, then **Compare data** again |
| Associations | "Partial deployment: Salesforce applied some rows and rejected others…" | Do not resubmit. Compare again, fix the causes, and select only the remaining rows |
| Associations | "RECOVERY REQUIRED — association records changed, but the tool-specific CML save/verification refresh failed…" | Stop. Keep the report, backup and archive, and follow runbook C |
| Extension | "That org is not in an open Salesforce tab…" | Open and log in to the org in the same Chrome profile, then **Refresh org list** |

**Stop and escalate if any of these happens:**
- the Org ID, model or version does not match the change record;
- a version maps to several runtime records or several Expression Sets;
- automatic rollback fails, or a result says recovery required;
- a backup fails its integrity check;
- a "safety policy" message appears;
- you are about to deactivate a live production model that the change record does not mention.

# 13. Incident response and recovery

| Runbook | Situation | First actions |
|---|---|---|
| A | CML verification fails | Stop. Check whether automatic rollback was verified; if not, restore the backup for the same version |
| B | CML deployed, but behaviour is wrong | Freeze associations; restore the backup; re-check the SHA-256; re-activate and test |
| C | Association deploy is partial | Never resubmit. Compare again, fix the cause, and deploy only the remaining rows |
| D | An approved deletion must be undone | Restore from the deletion archive, which re-resolves records by portable key |
| E | Local recovery file unavailable | Use the independent snapshot taken before the change |
| F | Token or session exposed | See the steps below the table |
| G | Tool or extension tampering suspected | Stop and disable the extension. Compare checksums with a fresh release. Treat every org open in that profile or logged in through the CLI as exposed, and run F for each. Reinstall only after the workstation is cleared |
| H | Unexpected or unauthorised write | Identify it from the report and audit line, and confirm it in Setup Audit Trail. Restore with A, B or D. If it was not approved, run F and report it |
| I | Hostile input file suspected | Stop the tool if it is unresponsive. Keep the file and do not reopen it. Restart; XML Tools and Context Definition analysis cannot write to Salesforce |

**Runbook F steps**
1. Stop the tool and close the extension page.
2. End the operator's sessions in Setup → Session Management.
3. Run `sf org logout`, and revoke the CLI's OAuth token if needed.
4. Review Setup Audit Trail and Event Monitoring.
5. Preserve the evidence.
6. Report to Information Security.

During any incident, **preserve** the runtime folder (or the extension's IndexedDB) and its logs as evidence. Do not delete them.

# 14. Known limitations

- No catalog writes and no activation, by design.
- No unattended or scheduled mode.
- No locking across machines (and only per service worker in the extension). Use one operator per model per change window.
- Artifacts are stored locally only. There is no application encryption and no central audit collector.
- Semantic comparison and the linter are guidance. They do not replace Salesforce compilation and testing.
- The operator must always pick the exact version; the tool never assumes "latest".
- ESCO targets are limited to Product2, ProductClassification and ProductRelatedComponent.
- Not every add, delete, duplicate, ambiguous or ProductRelatedComponent variant has live sandbox evidence yet. Condition C-4 closes this gap.
- Which dependencies Salesforce checks at activation must be learned by sandbox testing.
- The extension uses the full browser session.
- Shared workstations are not supported.

# 15. Approval record

| Item | Entry |
|---|---|
| Tool and version reviewed | Salesforce CML Tool 2.0.2 (desktop and Chrome extension) |
| Version approved for use | |
| Decision | ☐ Approved  ☐ Approved with conditions (C-1 to C-8)  ☐ Rejected |
| Approved users and orgs | |
| Review date / next review | / 12 months, or on any major release |

**Risk acceptance (if C-3 is met by acceptance rather than a fix):**

| Risk ID | Accepted by | Reason and compensating control | Expiry |
|---|---|---|---|
| | | | |
| | | | |

| Role | Name | Signature | Date |
|---|---|---|---|
| Tool owner | Mritunjaya Pancholi | | |
| Information Security reviewer | | | |
| Salesforce platform owner | | | |
| Change / release manager | | | |
