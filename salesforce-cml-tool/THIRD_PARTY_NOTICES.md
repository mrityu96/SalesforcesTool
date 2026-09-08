# Third-Party Notices

The operator archive contains one third-party runtime artifact:
`main/assets/vendor/codemirror.bundle.js`. It is generated from the exact
dependency graph in `development/package-lock.json`, is served only by the
local application, and does not download code from a CDN.

## CodeMirror 6 and Lezer

CodeMirror packages (`@codemirror/*`), Lezer packages (`@lezer/*`), `crelt`,
`style-mod`, and `w3c-keyname` are distributed under the MIT License.

Copyright (C) 2018-2026 by Marijn Haverbeke and others

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Project sources: <https://codemirror.net/> and <https://github.com/lezer-parser>

The bundle includes the MIT-licensed runtime dependencies recorded in the lock
file: `@codemirror/*`, `@lezer/*`, `@marijn/find-cluster-break`, `crelt`,
`style-mod`, and `w3c-keyname`. The copyright and MIT terms above apply.

## Development-only tools

The following packages are not shipped as executable dependencies in operator
archives:

- `esbuild` and its platform packages — MIT License; used only to produce the
  committed CodeMirror bundle.
- Playwright and `@playwright/test` — Apache License 2.0; used only by browser
  regression tests. Browser binaries are downloaded locally and excluded from
  source control and releases.

Full package names, versions, integrity hashes, and declared licenses are in
`development/package-lock.json`. The release archive includes this notice but
intentionally excludes the development dependency tree.
