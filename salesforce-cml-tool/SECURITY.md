# Security Policy

## Supported versions

Security fixes are provided for the latest released minor line only. During the
initial `1.x` series, upgrade to the newest `1.x` release before requesting a
fix. Pre-release builds and modified distributions are not supported.

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
