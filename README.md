<h1 align="center">Salesforce CML Tool</h1>

<p align="center">
  <strong>Fetch, compare, deploy, and fix Salesforce Revenue Cloud CML (Constraint Modeling Language) models and Context Definitions across orgs — safely, from your own laptop.</strong>
</p>

<p align="center">
  <a href="salesforce-cml-tool/main/CHANGELOG.md"><img alt="Version 2.1.0" src="https://img.shields.io/badge/version-2.1.0-2563eb"></a>
  <a href="salesforce-cml-tool/main/LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-16a34a"></a>
  <img alt="Python 3.9 to 3.13" src="https://img.shields.io/badge/python-3.9%E2%80%933.13-3776ab">
  <img alt="macOS, Windows, Linux" src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-6b7280">
  <img alt="Salesforce Revenue Cloud" src="https://img.shields.io/badge/Salesforce-Revenue%20Cloud%20CML-00a1e0">
  <img alt="No telemetry" src="https://img.shields.io/badge/telemetry-none-0f766e">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#what-you-can-do">Features</a> ·
  <a href="#screenshots">Screenshots</a> ·
  <a href="#why-teams-trust-it">Safety</a> ·
  <a href="#frequently-asked-questions">FAQ</a> ·
  <a href="salesforce-cml-tool/README.md">Full documentation</a>
</p>

<p align="center">
  <img src="salesforce-cml-tool/main/docs/screenshots/01-fetch-deploy-latest.png" alt="Salesforce CML Tool: fetch a Revenue Cloud Constraint Model from one org and deploy it to another" width="900">
</p>

---

## The problem

If you build **product configuration rules in Salesforce Revenue Cloud** (Revenue Lifecycle Management, RLM), your rules live in a **CML Constraint Model**. Promoting that model from a dev sandbox to QA, UAT, and production usually means:

- copying CML text by hand in **Constraint Builder** and hoping nothing was missed,
- writing SOQL to find which **Product associations** (`ExpressionSetConstraintObj`) are missing in the target org,
- comparing 30,000-line **Context Definition** XML files in a text editor to see which tags and mappings the target is missing,
- and finding out about a missing catalog record only when activation fails.

**Salesforce CML Tool turns that into one guided, verified workflow.** Pick a source org and a target org from your existing Salesforce CLI logins, and the tool shows you exactly what differs, what will be written, and what is blocked, before anything changes.

## What you can do

| | |
|---|---|
| **Fetch & deploy CML** | List every Constraint Model and every version in an org, fetch the exact version, edit it in a full code editor (search, replace, comments), and deploy it to an exact target version. **Check target status** is read-only. Activate or deactivate in Salesforce Constraint Builder. The tool backs up the target first, writes, reads it back, and verifies a SHA-256 fingerprint, restoring automatically if verification fails. |
| **Compare CML between orgs** | Side-by-side, colour-blind-friendly diff of two exact versions, plus a **semantic summary** that ignores formatting and moved blocks. Merge changes one at a time or all at once, undo any single change, and edit the target draft before deploying. |
| **Check CML best practices** | A built-in linter flags money stored as `double`, unbounded relations, deep inheritance, always-true constraints, and more, with a quality score and **paste-ready Before → After fixes**. |
| **Deploy Product associations** | Compare and deploy `ExpressionSetConstraintObj` rows between orgs, matched by a portable key such as `Global_Key__c` instead of record Ids. Missing products, classifications, attributes, and relationships are listed as clear bullets before anything is written. A blocked Product Related Component that is close but not identical lists the mismatched identity field with source vs target values. |
| **Fix Context Definitions** | Retrieve a Context Definition from two orgs, see exactly which tags, attributes, and mappings differ, and build a patched copy that **adds without deleting**. Then check every hydration field in the target org (read-only) and get the exact `sf project deploy` commands, check-only first. Handles 30,000+ line files smoothly. |
| **XML tools** | Compare, merge, and deduplicate any Salesforce metadata XML (Permission Sets, Profiles, and more) by content, not by line position. |
| **Help Me handbook** | Two built-in step-by-step guides with screenshots: the **CML Deployment Guide** (13 steps) and the **Context Definition Deployment Guide** (11 steps). |

Each org card shows the **Org ID** and the exact **Salesforce release** (for example `264.5.4 · Winter '27 Patch 5.4`), so you always know which org and which release you are working with.

## Who it is for

- **Salesforce Revenue Cloud / RLM developers and architects** who build CML product rules.
- **Release managers and DevOps engineers** promoting Constraint Models from sandbox to production.
- **Salesforce admins and consultants** who need to know why a configuration rule works in one org and not another.
- **Implementation partners** moving the same model across many client orgs.

## Quick start

You need **Python 3.9+** and the **Salesforce CLI** (`sf`), logged in to your orgs.

```bash
# 1. Install the Salesforce CLI once and log in to each org
npm install -g @salesforce/cli
sf org login web --alias Dev_Sandbox --instance-url https://test.salesforce.com

# 2. Get the tool
git clone https://github.com/mrityu96/SalesforcesTool.git
cd SalesforcesTool/salesforce-cml-tool
```

3. Start it by double-clicking the launcher for your computer in **`Start Tool Here/`**:
   - macOS: `Open CML Tool for macOS.command`
   - Windows: `Open CML Tool for Windows.bat`
   - Linux: `Open CML Tool for Linux.sh`, or run `python3 main/app/cml_tool.py`
4. Your browser opens at **http://127.0.0.1:8787**. Pick your orgs and go.

There's nothing to `pip install`: the tool uses only the Python standard library and a bundled, offline code editor. Open the **Help Me** tab inside the tool for the complete handbook.

Current release is **2.1.0**. See the [changelog](salesforce-cml-tool/main/CHANGELOG.md).

## Screenshots

All screenshots use sample data.

| Compare CML by meaning | Diagnose blocked Product associations |
|---|---|
| <img src="salesforce-cml-tool/main/docs/screenshots/02-semantic-compare-latest.png" alt="Semantic comparison of two Salesforce CML Constraint Model versions with merge arrows" width="440"> | <img src="salesforce-cml-tool/main/docs/screenshots/04-constraint-preflight-latest.png" alt="ExpressionSetConstraintObj comparison showing missing catalog dependencies as bullets" width="440"> |

| Fix a Context Definition across orgs | Check fields and get deploy commands |
|---|---|
| <img src="salesforce-cml-tool/main/docs/screenshots/07-context-definition-fix-latest.png" alt="Context Definition differences between a source and target Salesforce org" width="440"> | <img src="salesforce-cml-tool/main/docs/screenshots/08-context-definition-deploy-latest.png" alt="Read-only field check and generated sf project deploy commands" width="440"> |

| CML best-practice checks | Built-in Help Me handbook |
|---|---|
| <img src="salesforce-cml-tool/main/docs/screenshots/03-best-practices-latest.png" alt="CML linter with quality score and paste-ready fixes" width="440"> | <img src="salesforce-cml-tool/main/docs/screenshots/06-help-me-latest.png" alt="Step-by-step CML and Context Definition deployment handbook" width="440"> |

## Why teams trust it

- **Runs only on your computer.** The server listens on `127.0.0.1` and talks to Salesforce only through your own Salesforce CLI login. No cloud service, no telemetry, no account to create.
- **Every write is deliberate.** Each deployment, deletion, and restore asks you to type the target org alias before it runs.
- **Backups and verification on every CML deploy.** The tool saves the target first, reads back what it wrote, compares fingerprints, and restores automatically if they don't match.
- **Never touches live models.** Writes to an **Active** CML version are blocked. Fetch & Deploy does not activate or deactivate CML; that stays in Salesforce Constraint Builder so the platform compiler and validation always run.
- **Read-only where it should be.** Catalog data (products, classifications, attributes) is only ever read. Context Definitions are only retrieved; you run the generated deploy commands yourself.
- **Open source (MIT).** Plain, readable Python and JavaScript you can review before you run it.

## Frequently asked questions

**How do I deploy a CML Constraint Model from one Salesforce org to another?**
Pick the source org and exact CML version, click **Fetch CML**, pick the target org and exact target version, check its status, and click **Deploy CML**. The tool backs up the target, writes the CML, and verifies it. Then activate the version in Constraint Builder.

**How do I compare CML between two Salesforce sandboxes?**
Open **Compare CML**, choose the exact source and target versions, and click **Compare source ↔ target**. Turn on **Semantic summary** to compare by meaning instead of by line.

**How do I copy `ExpressionSetConstraintObj` Product associations between orgs?**
Use **Constraint Data**: choose a portable key field such as `Global_Key__c`, click **Compare data**, select the rows to add or delete, and deploy. Rows whose catalog dependencies are missing in the target are blocked, and each missing item is listed.

**Why does my CML work in one org but not in another?**
Usually the target org is missing a Context Definition tag or mapping, a Product association, or catalog data such as a classification attribute. The tool checks all three.

**How do I find which Context Definition tags and mappings are missing in my target org?**
Open **Context Definition Fix**, retrieve the same Context Definition from both orgs, and click **Analyze differences**. Build a patched copy, run the read-only field check, and use the generated `sf project deploy` commands.

**Does it work with production orgs?**
Yes, through your normal Salesforce CLI login. Every write requires typing the org alias, Active versions are never overwritten, and Context Definitions are never deployed by the tool itself.

**Is it an official Salesforce product?**
No. It's an independent, community-built open-source tool, not affiliated with or endorsed by Salesforce.

## Requirements

- Python 3.9–3.13 (macOS, Windows, or Linux)
- Salesforce CLI (`sf`), logged in to the orgs you use
- A Salesforce org with Revenue Cloud / Constraint Models (REST API v66.0, Spring '26, or later)

## Documentation

- [Full tool documentation](salesforce-cml-tool/README.md): every feature, the security model, and troubleshooting
- [Complete guide](salesforce-cml-tool/main/docs/CML_TOOL_COMPLETE_GUIDE.md)
- [Security handbook](salesforce-cml-tool/main/docs/CML_TOOL_SECURITY_HANDBOOK.md) · [Security summary](salesforce-cml-tool/main/docs/CML_TOOL_SECURITY_SUMMARY.md)
- [Changelog](salesforce-cml-tool/main/CHANGELOG.md) · [Security policy](salesforce-cml-tool/main/SECURITY.md) · [Compatibility](salesforce-cml-tool/main/COMPATIBILITY.md) · [Contributing](salesforce-cml-tool/main/CONTRIBUTING.md)

## Support the project

If this tool saves you time:

- ⭐ **Star this repository** so other Salesforce Revenue Cloud teams can find it.
- Share it with your team, your Trailblazer Community group, or on LinkedIn.
- Report bugs and ideas in [Issues](https://github.com/mrityu96/SalesforcesTool/issues).
- Optional contributions are possible from the **Donate** button inside the tool.

## License

[MIT](salesforce-cml-tool/main/LICENSE) © 2026 Mritunjaya Pancholi

---

<sub>Salesforce, Revenue Cloud, Constraint Builder, and related marks are trademarks of Salesforce, Inc. This project is independent and is not affiliated with, sponsored by, or endorsed by Salesforce. Provided as-is, without warranty: review every change and test in a sandbox before deploying to production.</sub>