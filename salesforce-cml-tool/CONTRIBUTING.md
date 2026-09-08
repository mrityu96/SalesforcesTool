# Contributing

## Development setup

Runtime code has no third-party Python dependency. Development requires Python
3.9+, Node.js 22+, and npm:

```bash
cd development
npm ci
npx playwright install chromium
```

Keep source and configuration under `development/` tracked. Never add
`runtime/`, `node_modules/`, browser binaries, reports, caches, `.env` files,
credentials, CML exports, backups, or org data.

## Required checks

Run from `development/`:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
npm run check:editor
npm run test:browser
```

Also compile Python and check JavaScript syntax as CI does. Tests must not call
a live Salesforce org. Use synthetic adapters or intercepted browser API
responses. The contract harness defaults to read-only and must never be pointed
at production for routine development.

## Design and safety rules

- Keep responsibilities in their focused `main/app/cml_*.py` modules.
- Preserve exact-version ownership checks, explicit target confirmation,
  active-version blocks, backups, read-after-write verification, and recovery.
- Keep all POST routes behind Host, Origin, and CSRF validation.
- Use the existing Salesforce transport and ESCO write allowlist; do not add an
  independent write path.
- Treat Context Definition readiness and local validation as evidence, not
  compilation, activation, or runtime proof.
- Update tests, user guidance, changelog, and compatibility notes with behavior
  changes.

## Releases

Update `VERSION` and `CHANGELOG.md` in the same pull request. Tags must be
exactly `v<contents-of-VERSION>`. The release workflow reruns quality checks,
builds deterministic `.tar.gz` and `.zip` operator archives, verifies their
contents, and publishes SHA-256 checksums.
