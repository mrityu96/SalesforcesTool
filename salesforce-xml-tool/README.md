# Salesforce Metadata XML Tool

A tiny, **zero-dependency** local web app for working with Salesforce metadata XML.
Paste your XML, pick an operation, and go — no terminal commands, no installs, and
nothing ever leaves your machine.

It does four things:

| Operation | What it does |
|---|---|
| **Compare** | Side-by-side view of only the unique XML differences (changed / only-left / only-right), using an order-independent structural comparison. Matching XML is ignored even when it appears on different lines. Plain text/Apex still uses a line diff. |
| **Merge** | Merge a **Base** XML and a **Modified** XML into one. You choose which side is the base; the tool keeps the base intact and layers the other side's changes on top — matching identity keys (e.g. `apexClass`, `field`, `object`, `contextMapping title`) so nothing is duplicated or lost. |
| **Deduplicate** | Remove duplicate entries from a Permission Set / Profile and output a clean, consistently sorted file. |
| **Context Definition Fix** | Compare a **Base** Context Definition and a **Modified** one, find missing entries and changed field mappings, then cherry-pick additions or updates into the base and download the patched file. |

Built for Salesforce metadata such as **Permission Sets, Profiles, and Context
Definitions**, but the compare works on any XML (or text).

![Latest merge workspace in dark mode](docs/screenshots/merge-dark.png)

---

## Why it's safe

- Runs a local server bound to **`127.0.0.1` only** — it is not reachable by anyone
  else on your network.
- **No external dependencies** — uses only the Python 3 standard library.
- **No telemetry, no cloud** — your XML is processed in memory on your own computer.

---

## Requirements

- **Python 3.8+** (already installed on most macOS/Linux machines).
  - macOS: comes preinstalled, or run `xcode-select --install`.
  - Windows: install from [python.org](https://www.python.org/downloads/) and tick
    **"Add Python to PATH"**.

---

## Quick start

### macOS (easiest)

1. Download/clone this folder.
2. Open `launchers/` and double-click **`Open XML Tool.command`**.
3. Your browser opens at `http://127.0.0.1:8799`. Done.

To stop it later, double-click **`launchers/Stop XML Tool.command`**.

> **First launch shows a security warning?** That's normal — see
> [macOS security warning](#macos-security-warning-apple-could-not-verify) below.
> The quickest fix is to **`git clone`** the repo instead of receiving the files
> via AirDrop/Slack/email/zip.
>
> **Says you do not have appropriate access privileges?** The executable bit was
> lost during download or copying. Follow the
> [macOS launcher permission fix](#macos-says-you-do-not-have-appropriate-access-privileges).

### Windows

Double-click **`launchers/run.bat`** (or run it from a terminal). Your browser opens
automatically. Close the window to stop the tool.

### Linux / any terminal

```bash
./launchers/run.sh
# or:
python3 app/xml_tool.py
```

Then open `http://127.0.0.1:8799` if it doesn't open automatically. Press
`Ctrl+C` to stop.

### Change the port

```bash
XML_UI_PORT=8900 python3 app/xml_tool.py      # macOS / Linux
set XML_UI_PORT=8900 && python app\xml_tool.py  # Windows
```

---

## How to use

### Compare
1. Open the **Compare** tab.
2. Paste XML into the **Left** and **Right** panes.
3. (Optional) Type an element name in *"Limit to element"* (e.g. `fieldPermissions`)
   to focus the structural summary.
4. Click **Compare**. The two-pane result shows only unique structural differences;
   unchanged elements moved to another line or reordered within XML are not reported.

![Unique structural comparison results](docs/screenshots/compare-unique.png)

### Merge
1. Open the **Merge** tab.
2. Paste the **Base XML** (Pane 1) and the **Modified XML** (Pane 2).
3. Pick **which pane is the base** (or use **Swap panes**).
4. Click **Merge**. The merged XML appears in Pane 3 — use **Copy** or **Download**.
5. A merge report shows what was added, overridden, and deep-merged, plus a
   validation check that every element from both sides survived.

### Deduplicate
1. Open the **Deduplicate** tab.
2. Paste a Permission Set / Profile XML.
3. Click **Remove duplicates** → copy/download the cleaned result.

The operation handles both keyed repeating sections (such as
`fieldPermissions`) and singleton metadata (such as `description`, `label`, and
`license`). Identical singleton copies are reduced to one. If duplicate
singleton values conflict, the first occurrence is kept and the report shows a
warning instead of resolving the conflict silently.

![Permission Set deduplication result](docs/screenshots/deduplicate.png)

### Context Definition Fix

Use this tab to bring selected mappings, node attributes, or complete required
parent blocks from a **Modified** Context Definition into a **Base** definition.
When the result is intended for deployment, use the current target-org XML as
Base so its version and existing metadata remain authoritative.

**Step 1 — Analyze Differences**

1. Open the **Context Definition Fix** tab.
2. Paste your **Base** Context Definition XML (Pane 1) and the **Modified** XML (Pane 2).
3. Click **Analyze Differences**.

The tool first explains line-count differences, separating serializer omissions
from actual metadata additions, removals, and material changes. It then lists
every selectable addition that is **present in Modified but missing from Base**
and every existing mapping whose nested field path or XML value changed.
Patching is non-destructive: an element omitted from Modified is preserved from
Base rather than interpreted as a deletion. For example, existing `contextTags`
remain intact unless new tags are added.

![Context Definition diagnostics and selectable additions](docs/screenshots/context-analysis.png)

Each card shows:

- Whether it's a **Mapping** (a `contextAttributeMappings` entry) or a **Node Attr**
  (a `contextAttributes` entry on a `contextNodes` node).
- The **full attribute name** so you can immediately see what it is.
- The **location** — which mapping title, context node, and object the entry lives under.
- The **SF Field** (or hydration reference, or node role).
- For value changes, the current Base value and the replacement Modified value.
- Any Base-only child metadata that Step 3 will protect and preserve.
- Whether Step 3 must copy a complete required parent block. Parent blocks are
  selectable and are no longer skipped as errors.

**Step 2 — Select additions and updates**

4. All differences are selected by default. Deselect any you want to skip.
   - Use **Select all** / **Deselect all** to bulk-toggle.
   - Each group header has its own checkbox to toggle the whole group at once.
5. Review any **Full block patch** cards. Selecting one copies that complete
   required mapping or context-node block, including its child attributes.

**Step 3 — Build and review**

6. Click **Build Context Definition**. The result and compact apply report show
   every selected field and complete parent block that was added.
7. Review the output, then use **Copy** or **Download**.

![Patched Context Definition and apply report](docs/screenshots/context-patched.png)

> **Business metadata is preserved.** Step 3 adds only selected business entries.
> It can omit explicit serializer defaults such as
> `localizationDisabled=false` and API-incompatible root fields that Salesforce
> itself omits on retrieval; these normalizations are listed in the apply report.

Toggle **Night / Day mode** any time with the button in the top-right (the Merge
screenshot above shows dark mode).

### Optional project support

The navigation includes **Donate** above **About**. Clicking it reveals hidden
**UPI** and **Razorpay** choices. UPI displays the packaged payment QR, opens a
generic UPI link, and provides a copyable UPI ID. Razorpay opens the verified
hosted payment page in a separate tab. Contributions are voluntary and do not
purchase support, features, priority service, or warranty. Bank account and
IFSC details are not published by the tool.

---

## Project structure

```
salesforce-xml-tool/
├── app/
│   ├── xml_tool.py        # Local server + merge/compare/dedup/cdfix engine
│   ├── xml_tool_page.py   # Web UI (HTML + CSS + JavaScript)
│   └── utilities/
│       └── patch_ref_product_category.py
├── launchers/
│   ├── Open XML Tool.command  # macOS: double-click to start in background
│   ├── Stop XML Tool.command  # macOS: double-click to stop
│   ├── run.sh                 # Linux / macOS terminal launcher
│   └── run.bat                # Windows launcher
├── README.md
├── LICENSE
├── .gitignore
├── favicon/               # Browser, Apple touch, and web-app icon assets
│   ├── favicon.svg
│   ├── favicon.ico
│   ├── favicon-96x96.png
│   ├── apple-touch-icon.png
│   ├── web-app-manifest-192x192.png
│   ├── web-app-manifest-512x512.png
│   └── site.webmanifest
└── docs/
    └── screenshots/       # Images used in this README
```

The endpoints (`/api/compare`, `/api/merge`, `/api/dedup`, `/api/cdfix/analyze`,
`/api/cdfix/build`) are simple JSON POSTs, so you can also script against the
server if you want.

---

## How the merge works (in short)

Repeating elements are matched by an **identity key** rather than by position, so
order in the file never matters. Examples:

| Element | Identity |
|---|---|
| `classAccesses` | `apexClass` |
| `fieldPermissions` | `field` |
| `objectPermissions` | `object` |
| `recordTypeVisibilities` | `recordType` |
| `contextMappings` / `contextNodes` | `title` |
| `contextAttributeMappings` | `contextAttribute` |

- An element only in the base → **kept**.
- An element in both → the **modified** version wins (or is deep-merged for nested
  containers).
- An element only in the modified → **added**.

Permission Sets / Profiles are additionally re-sorted into a stable section order
for clean diffs.

---

## Troubleshooting

### macOS security warning: *"Apple could not verify…"*

When you double-click `Open XML Tool.command` you may see:

> *"Apple could not verify 'Open XML Tool.command' is free of malware that may
> harm your Mac or compromise your privacy."*

**Why this happens (and why the author didn't see it):** macOS adds a hidden
*quarantine* flag to files that arrive from "the outside" — downloads, AirDrop,
Slack/Teams, email, or an unzipped archive. Gatekeeper then blocks them because
these scripts aren't signed by a paid Apple Developer account. The person who
*created* the files locally has no quarantine flag, so they never see the prompt.
It has nothing to do with the tool being unsafe — the source is plain, readable
Python you can inspect.

**Fix — pick whichever is easiest:**

1. **Best: clone instead of copying.** Files obtained with `git clone` are **not**
   quarantined, so there's no warning at all:
   ```bash
   git clone https://github.com/<your-username>/salesforce-xml-tool.git
   cd salesforce-xml-tool
   open "launchers/Open XML Tool.command"
   ```

2. **Allow it in System Settings** (works on all recent macOS, including Sequoia):
   double-click once (it gets blocked) → open **System Settings → Privacy &
   Security** → scroll to the message about the blocked file → click
   **"Open Anyway"** → confirm. One-time per machine.

3. **Right-click → Open** (older macOS 14 and earlier): right-click (or
   Control-click) the file → **Open** → **Open**. *(Apple removed this shortcut on
   macOS 15 Sequoia — use option 1 or 2 there.)*

4. **Remove the quarantine flag from Terminal** (clears it for the whole folder):
   ```bash
   xattr -dr com.apple.quarantine "/path/to/salesforce-xml-tool"
   ```
   Then double-click normally.

> None of this requires admin rights or installing anything. If you'd rather skip
> the `.command` launcher entirely, teammates can just run `python3 app/xml_tool.py`
> in Terminal — that never triggers Gatekeeper.

### "Port 8799 is in use"

Another copy is already running, or something else holds the port. Stop it with
`launchers/Stop XML Tool.command`, or start on a different port:
`XML_UI_PORT=8900 python3 app/xml_tool.py`.

### macOS says you do not have appropriate access privileges

This message is different from the Gatekeeper warning: the executable permission
was removed while the files were copied, uploaded, or downloaded. Run this once
in Terminal:

```bash
cd "/path/to/salesforce-xml-tool"
chmod 755 "launchers/Open XML Tool.command" "launchers/Stop XML Tool.command" "launchers/run.sh"
```

Then double-click **`launchers/Open XML Tool.command`** again.

If macOS next shows **“Apple could not verify…”**, and you trust the repository,
remove the downloaded-folder quarantine flag once:

```bash
xattr -dr com.apple.quarantine "/path/to/salesforce-xml-tool"
```

For GitHub distributions, do not upload these scripts only through the GitHub
web page, which can lose Unix file modes. Commit all three with executable mode
`100755`:

```bash
git add --chmod=+x "launchers/Open XML Tool.command" "launchers/Stop XML Tool.command" "launchers/run.sh"
git commit -m "Preserve executable permissions for launch scripts"
```

After pushing, verify the Git index shows `100755` for each launcher:

```bash
git ls-files --stage -- "launchers/Open XML Tool.command" "launchers/Stop XML Tool.command" "launchers/run.sh"
```

---

## Contributing

Issues and pull requests are welcome. The whole thing is plain Python + vanilla
JS with no build step, so editing is easy: change `app/xml_tool.py` (logic) or
`app/xml_tool_page.py` (UI) and relaunch.

## License

[MIT](./LICENSE) — free to use, modify, and share.
