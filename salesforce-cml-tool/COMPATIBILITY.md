# Compatibility and Support

## Supported operator environments

- Python 3.9 through 3.13 using only the standard library at runtime.
- Current stable macOS, Windows 10/11, and common Linux distributions.
- Current Chrome, Edge, Firefox, or Safari releases.
- Salesforce CLI (`sf`) available to the launching user and an authenticated
  Salesforce org that exposes the required Revenue Cloud metadata and APIs.

CI verifies Python 3.9 and 3.13 on Ubuntu and the browser suite on the current
Playwright Chromium version. The packaged CodeMirror bundle is generated from
the exact `development/package-lock.json` dependency graph and runs offline.

## Salesforce compatibility boundary

The tool targets the API version declared in `main/app/cml_salesforce.py` and
detects selected API capabilities at runtime. Salesforce permissions, licenses,
Revenue Cloud schema, metadata lifecycle, and org configuration vary. A
successful local read/write verification does not prove compilation,
activation, solver behavior, Context Definition resolution, or production
scenario reliability.

## Support policy

The latest release receives best-effort community support. Reports should
include the tool version, operating system, Python and `sf` versions, and
redacted diagnostics. Live Salesforce reliability is not certified until the
read-only contract harness and approved scenario validation have been run
against a named non-production org.
