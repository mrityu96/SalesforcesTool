# Security Policy

## Supported versions

Security fixes are provided for the latest released minor line only. During the
`2.x` series, upgrade to the newest `2.x` release before requesting a fix; the
`1.x` series is no longer supported. Pre-release builds and modified distributions are not supported.

## Reporting a vulnerability

Do not open a public issue containing exploit details, Salesforce identifiers,
tokens, CML, backups, or deployment reports. Use GitHub private vulnerability
reporting for this repository. If that facility is unavailable, open a minimal
issue asking the maintainer for a private reporting channel.

Include the affected version, operating system, reproduction steps, impact, and
a proposed mitigation if known. Redact org aliases, usernames, record IDs,
access tokens, and recovery artifacts. Expect acknowledgement within seven
calendar days; resolution timing depends on severity and reproducibility.

## Operating boundary

The application binds to loopback and is not designed as a shared or remote
service. It uses the current operating-system user's Salesforce CLI
credentials. Operators remain responsible for least-privilege org access,
reviewing exact targets, protecting `CML_RUNTIME_ROOT`, and validating changes
in an approved sandbox. Never publish runtime artifacts or browser diagnostics
without review.

The Chrome extension can run in two ways. The browser-session UI (current
unpackaged path) reads the `sid` cookie of Salesforce tabs already open in
Chrome and calls Salesforce REST as that user. The session stays in the
service worker; the page only receives alias, username, and org Id. It
requests Salesforce `host_permissions` plus `cookies`/`tabs` for that
purpose. Guarded CML and Constraint Data writes from that UI keep backups,
deletion archives, and reports in IndexedDB for this Chrome profile only.
The Salesforce session is never sent to a hosted backend.

The desktop Python tool remains a loopback API. POST requests from
`chrome-extension://` to that server are accepted only for the pinned
extension ID in `main/app/cml_http.py` (and optional `CML_EXTENSION_IDS`).
Arbitrary extension IDs, websites, and non-loopback Host headers remain
rejected there.
