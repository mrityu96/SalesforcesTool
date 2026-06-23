# Salesforce CML Tool

A tiny, **zero-dependency** local web app for working with Salesforce **Revenue
Cloud CML** (Constraint Model Language). Pick an org, choose a Constraint Model,
and **fetch**, **deploy**, or **compare** it — no terminal commands to type, no
installs, and nothing ever leaves your machine.

It does three things:

| Operation | What it does |
|---|---|
| **Fetch** | Download the latest CML of any Expression Set / Constraint Model from an org into an editable text box (and save a copy locally). |
| **Deploy** | Push CML (fetched or pasted) back to the latest version of that model in an org — with a confirmation prompt so nothing happens by accident. |
| **Compare** | Fetch the **same** CML from a **source** and **target** org and show a synced, line-numbered, side-by-side diff that highlights every difference. |

You select everything from dropdowns and lists, so there are **no typos** in org
names or model API names.

![Main screen](docs/screenshots/main.png)

---

## Why it's safe

- Runs a local server bound to **`127.0.0.1` only** — not reachable by anyone
  else on your network.
- **No external Python dependencies** — uses only the Python 3 standard library.
- **No telemetry, no cloud** — it talks only to your Salesforce orgs through the
  Salesforce CLI you already use.

---

## Requirements

- **Python 3.8+** (preinstalled on most macOS/Linux machines).
  - macOS: comes preinstalled, or run `xcode-select --install`.
  - Windows: install from [python.org](https://www.python.org/downloads/) and tick
    **"Add Python to PATH"**.
- **Salesforce CLI (`sf`)**, logged in to the orgs you want to use:
  ```bash
  npm install -g @salesforce/cli      # install (one time)
  sf org login web --alias myOrg      # authorize each org
  ```
  The tool reads your authorized orgs automatically via `sf org list`.

---

## Quick start

### macOS (easiest)

1. Clone or download this folder.
2. Double-click **`Open CML Tool.command`**.
3. Your browser opens at `http://127.0.0.1:8787`. Done.

The server runs in the **background**, so you can close the Terminal window and
the tool stays available. To stop it, double-click **`Stop CML Tool.command`**.

> **First launch shows a security warning?** That's normal — see
> [macOS security warning](#macos-security-warning-apple-could-not-verify) below.
> The quickest fix is to **`git clone`** the repo instead of receiving the files
> via AirDrop/Slack/email/zip.

### Windows

Double-click **`run.bat`** (or run it from a terminal). Your browser opens
automatically. Close the window to stop the tool.

### Linux / any terminal

```bash
./run.sh
# or:
python3 cml_tool.py
```

Then open `http://127.0.0.1:8787` if it doesn't open automatically. Press
`Ctrl+C` to stop.

### Change the port

```bash
CML_UI_PORT=8900 python3 cml_tool.py        # macOS / Linux
set CML_UI_PORT=8900 && python cml_tool.py  # Windows
```

---

## How to use

### Fetch
1. Pick a **Source org** — the tool automatically loads every CML in that org
   into the list (with version number and status, e.g. `[V1 · Active]`).
2. Type in the filter box to narrow the list, then click a CML to select it.
3. Click **Fetch CML**. The content appears in the box and is saved to
   `cml-files/<model>.cml`. Use **Copy** to copy it.

### Deploy
1. Select the org and CML, and make sure the desired CML text is in the box
   (fetched or pasted).
2. Click **Deploy CML**, confirm the prompt, and the tool deploys it to the
   latest version of that model.

### Compare (source org ↔ target org)
1. Pick a **Source org** and a **Target org** (must be different).
2. Choose the **CML** to compare.
3. Click **Compare source ↔ target**. The tool fetches the CML from both orgs
   and shows a two-pane diff: **source on the left, target on the right.**

![Compare view](docs/screenshots/compare.png)

The diff is built to be **colorblind-friendly** — it uses an orange / blue /
purple palette plus text markers (`−`, `+`, `~`) so differences are clear
without relying on color:

| Highlight | Marker | Meaning |
|---|---|---|
| Purple | `~` | Line **changed** between the two orgs |
| Orange | `−` | Line exists **only in source** |
| Blue | `+` | Line exists **only in target** |

- Line numbers are shown for **both** orgs, and the panes scroll together so
  matching lines stay aligned.
- If a line isn't in the same place but exists **elsewhere** in the other org,
  the diff tells you where (e.g. `↦ also in target at L420`).
- Tick **Show only differences** to hide the matching lines.

Toggle **Night / Day mode** any time with the button in the top-right.

![Dark mode](docs/screenshots/dark.png)

---

## Project structure

```
salesforce-cml-tool/
├── cml_tool.py            # Local server + UI (HTML/CSS/JS) — the whole app
├── fetch-cml.sh           # Helper: download a CML from an org (uses sf + REST)
├── deploy-cml.py          # Helper: upload a CML to an org (uses sf + REST)
├── Open CML Tool.command  # macOS: double-click to start (runs in background)
├── Stop CML Tool.command  # macOS: double-click to stop
├── run.sh                 # macOS / Linux launcher
├── run.bat                # Windows launcher
├── README.md
├── LICENSE
├── .gitignore
└── docs/
    └── screenshots/       # Images used in this README
```

The endpoints (`/api/orgs`, `/api/models`, `/api/fetch`, `/api/deploy`,
`/api/compare`) are simple JSON requests, so you can also script against the
server if you want.

---

## How it works (in short)

- **Orgs** come from `sf org list`, so the dropdowns always match your authorized
  orgs.
- **CMLs** are discovered by querying `ExpressionSetDefinitionVersion`, keeping the
  latest version per model.
- **Fetch/Deploy** read and write the `ConstraintModel` field of the latest
  `ExpressionSetDefinitionVersion` via the Salesforce REST API, using the access
  token from your `sf` session.
- **Compare** fetches from both orgs (sequentially — the `sf` CLI serializes on
  its own config) and diffs them in your browser with a longest-common-subsequence
  algorithm.

---

## Troubleshooting

### "The Salesforce CLI ('sf') was not found"
Install it and authorize at least one org:
```bash
npm install -g @salesforce/cli
sf org login web --alias myOrg
```

### A fetched CML is empty
The selected version has no Constraint Model — usually because that version is
**Inactive** or was never populated in that org. Pick an org where the model has
an **Active** version. The tool tells you when this happens.

### macOS security warning: *"Apple could not verify…"*

When you double-click `Open CML Tool.command` you may see:

> *"Apple could not verify 'Open CML Tool.command' is free of malware…"*

**Why:** macOS adds a hidden *quarantine* flag to files that arrive from "the
outside" — downloads, AirDrop, Slack/Teams, email, or an unzipped archive.
Gatekeeper then blocks unsigned scripts. The person who *created* the files
locally never sees this. It's not a sign the tool is unsafe — the source is
plain, readable Python you can inspect.

**Fix — pick whichever is easiest:**

1. **Best: clone instead of copying.** Files obtained with `git clone` are **not**
   quarantined, so there's no warning at all:
   ```bash
   git clone https://github.com/mrityu96/SalesforcesTool.git
   cd SalesforcesTool/salesforce-cml-tool
   open "Open CML Tool.command"
   ```

2. **Allow it in System Settings** (recent macOS, incl. Sequoia): double-click
   once (it gets blocked) → **System Settings → Privacy & Security** → scroll to
   the blocked-file message → **"Open Anyway"** → confirm. One-time per machine.

3. **Right-click → Open** (macOS 14 and earlier): right-click (or Control-click)
   the file → **Open** → **Open**.

4. **Remove the quarantine flag from Terminal:**
   ```bash
   xattr -dr com.apple.quarantine "/path/to/salesforce-cml-tool"
   ```

> None of this requires admin rights. If you'd rather skip the `.command`
> launcher, just run `python3 cml_tool.py` in Terminal — that never triggers
> Gatekeeper.

### "Port 8787 is in use"
Another copy is running, or something else holds the port. Stop it with
`Stop CML Tool.command`, or start on a different port:
`CML_UI_PORT=8900 python3 cml_tool.py`.

### I changed the code but don't see the update
The launcher detects a code change and restarts automatically. If you started it
manually, stop it (`Stop CML Tool.command` or `Ctrl+C`) and run it again, then
reload the browser tab.

---

## Contributing

Issues and pull requests are welcome. It's plain Python + vanilla JS with no
build step: edit `cml_tool.py` and relaunch.

## License

[MIT](./LICENSE) — free to use, modify, and share.
