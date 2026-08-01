#!/usr/bin/env python3
"""
cml_tool.py — A tiny, self-contained local web UI for fetching, comparing and
deploying CML (and its ExpressionSetConstraintObj data) across Salesforce orgs.

Cross-platform (macOS / Windows / Linux). It talks to Salesforce over the REST
API directly and only uses the `sf` CLI for authentication (`sf org list` /
`sf org display`), so there are no bash/curl dependencies.

The user never types in the terminal: pick an org from the dropdown, paste the
CML API name, and click Fetch, Compare or Deploy.

Run it (or just double-click the launcher for your OS):
    python3 cml_tool.py

It picks a free port, starts a local server, and opens your browser.
Only the Python standard library is used — nothing to install.
"""

import base64
import datetime
import getpass
import hashlib
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Self-contained package: everything lives next to this file.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = APP_DIR
SCRIPTS_DIR = APP_DIR
DOWNLOAD_DIR = os.path.join(APP_DIR, "cml-files")
BACKUP_DIR = os.path.join(APP_DIR, "cml-backups")
REPORT_DIR = os.path.join(APP_DIR, "deployment-reports")
ARCHIVE_DIR = os.path.join(APP_DIR, "association-archives")
CSRF_TOKEN = secrets.token_urlsafe(32)
FIELD_PROBE_TTL = 300
_DEPLOY_LOCKS = {}
_DEPLOY_LOCKS_GUARD = threading.Lock()


def _deployment_lock(org, model):
    key = (org or "", model or "")
    with _DEPLOY_LOCKS_GUARD:
        return _DEPLOY_LOCKS.setdefault(key, threading.Lock())


def _run_with_deployment_lock(org, model, operation):
    lock = _deployment_lock(org, model)
    if not lock.acquire(blocking=False):
        return {"ok": False, "log": (
            f"Another deployment or recovery operation is already running for "
            f"'{model}' in '{org}'. Wait for it to finish and try again.")}
    try:
        return operation()
    finally:
        lock.release()

# When launched from Finder (double-click), the process may not inherit the
# shell PATH, so CLIs like `sf` can't be found. Augment PATH with every known
# install location so the tool works regardless of how it was started.
# Most common cause of "orgs not loading": sf was installed via nvm/fnm which
# only adds its bin to PATH inside an interactive shell session, not when the
# tool is launched from Finder. Fix: scan ALL installed node versions.

def _nvm_bin_dirs() -> list:
    dirs = []
    nvm_root = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(nvm_root):
        try:
            for entry in sorted(os.listdir(nvm_root), reverse=True):
                p = os.path.join(nvm_root, entry, "bin")
                if os.path.isdir(p):
                    dirs.append(p)
        except OSError:
            pass
    return dirs


def _fnm_bin_dirs() -> list:
    dirs = []
    for fnm_root in [
        os.path.expanduser("~/.local/share/fnm/node-versions"),
        os.path.expanduser("~/.fnm/node-versions"),
    ]:
        if os.path.isdir(fnm_root):
            try:
                for entry in sorted(os.listdir(fnm_root), reverse=True):
                    p = os.path.join(fnm_root, entry, "installation", "bin")
                    if os.path.isdir(p):
                        dirs.append(p)
            except OSError:
                pass
    return dirs


def _volta_bin_dir() -> list:
    p = os.path.expanduser("~/.volta/bin")
    return [p] if os.path.isdir(p) else []


def _extra_paths() -> list:
    static = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        os.path.expanduser("~/.npm-global/bin"),
        os.path.expanduser("~/.nvm/current/bin"),
        "/usr/local/sfdx/bin",
        "/opt/homebrew/lib/node_modules/@salesforce/cli/bin",
    ]
    return static + _nvm_bin_dirs() + _fnm_bin_dirs() + _volta_bin_dir()


CMD_TIMEOUT = 120  # seconds
API_VERSION = "v62.0"  # Salesforce REST API version for data writes


def _env():
    """Return an environment with a robust PATH for finding CLIs."""
    env = os.environ.copy()
    parts = env.get("PATH", "").split(os.pathsep)
    for p in _extra_paths():
        if p and os.path.isdir(p) and p not in parts:
            parts.append(p)
    env["PATH"] = os.pathsep.join(parts)
    return env


def find_sf():
    """Locate the `sf` executable, or return None if it cannot be found."""
    found = shutil.which("sf", path=_env()["PATH"])
    if found:
        return found
    for p in _extra_paths():
        candidate = os.path.join(p, "sf")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def sf_debug_info() -> dict:
    """Return diagnostic info about sf CLI and authorized orgs for /api/debug."""
    sf_path = find_sf()
    sf_version = None
    if sf_path:
        try:
            res = _sf_run(["--version"])
            sf_version = (res.stdout or res.stderr or "").strip().splitlines()[0]
        except Exception:  # noqa: BLE001
            sf_version = "(could not run --version)"

    searched = [p for p in _extra_paths() if p]
    found_dirs = [p for p in searched if os.path.isdir(p)]

    # The Salesforce CLI stores authorized orgs PER OS USER, under the user's
    # home (~/.sfdx/*.json and/or ~/.sf). Surfacing this makes "no orgs" easy to
    # diagnose: a different system owner simply hasn't logged in on their account.
    home = os.path.expanduser("~")
    sfdx_dir = os.path.join(home, ".sfdx")
    sf_dir = os.path.join(home, ".sf")
    auth_files = []
    if os.path.isdir(sfdx_dir):
        try:
            auth_files = [f for f in os.listdir(sfdx_dir)
                          if f.endswith(".json") and f != "alias.json"]
        except OSError:
            pass

    info = {
        "sf_found": sf_path is not None,
        "sf_path": sf_path or "not found",
        "sf_version": sf_version,
        "path_searched": searched,
        "path_found": found_dirs,
        "system_path": os.environ.get("PATH", "").split(os.pathsep),
        "os_user": os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
        "home": home,
        "sfdx_dir_exists": os.path.isdir(sfdx_dir),
        "sf_dir_exists": os.path.isdir(sf_dir),
        "authorized_org_files": len(auth_files),
    }
    if sf_path and len(auth_files) == 0:
        info["auth_hint"] = (
            "The Salesforce CLI on this computer/user has no saved org logins "
            "(~/.sfdx is empty). Orgs are per OS user — log in on THIS account: "
            "sf org login web --alias <name>"
        )

    if sf_path:
        try:
            proc = _sf_run(["org", "list", "--json"])
            info["org_list_exit"] = proc.returncode
            info["org_list_stderr"] = (proc.stderr or "").strip()[:500]
            if proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout)
                    result = data.get("result", {})
                    count = sum(
                        len(result.get(b, []) or [])
                        for b in ("sandboxes", "nonScratchOrgs", "scratchOrgs",
                                  "other", "devHubs")
                    )
                    info["orgs_found"] = count
                    if count == 0:
                        info["org_hint"] = (
                            "sf org list returned 0 orgs. "
                            "Run: sf org login web --alias <name>"
                        )
                except json.JSONDecodeError:
                    info["org_list_parse_error"] = proc.stdout[:300]
        except subprocess.TimeoutExpired:
            info["org_list_error"] = "sf org list timed out after 30s"
        except Exception as e:  # noqa: BLE001
            info["org_list_error"] = str(e)

    return info


def run(args, **kwargs):
    """subprocess.run with augmented PATH, timeout, and captured text output.

    Force UTF-8 decoding: the `sf` CLI emits UTF-8, but on Windows Python would
    otherwise decode with the locale codepage (cp1252), which corrupts non-ASCII
    text (e.g. an em-dash shows up as "â€") and can even raise UnicodeDecodeError
    on bytes that are undefined in cp1252.
    """
    return subprocess.run(
        args, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=REPO_ROOT, env=_env(), timeout=CMD_TIMEOUT, **kwargs,
    )


def _sf_run(args, **kwargs):
    """Run the `sf` CLI in a cross-platform way.

    On Windows the CLI is installed as `sf.cmd`, which Windows' CreateProcess
    can't launch from a bare name or even a full path (you get
    'WinError 2' / 'not a valid Win32 application'); route those through
    cmd.exe. On macOS/Linux just call the resolved executable. All of our sf
    calls end in `--json`, so cmd.exe never strips the surrounding quotes of a
    path that contains spaces (e.g. "C:\\Program Files\\sf\\bin\\sf.cmd").
    """
    exe = find_sf() or "sf"
    argv = [exe] + list(args)
    if os.name == "nt" and exe.lower().endswith((".cmd", ".bat")):
        argv = [os.environ.get("COMSPEC", "cmd.exe"), "/c"] + argv
    return subprocess.run(
        argv, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
        cwd=REPO_ROOT, env=_env(), timeout=CMD_TIMEOUT, **kwargs,
    )


def list_orgs():
    """Return a sorted list of {alias, username} from `sf org list`."""
    if not find_sf():
        return {"error": "The Salesforce CLI ('sf') was not found on this machine. "
                         "Install it or run: npm install -g @salesforce/cli"}
    try:
        proc = _sf_run(["org", "list", "--json"])
        if not proc.stdout.strip():
            return {"error": (proc.stderr or "sf org list returned no output.").strip()}
        data = json.loads(proc.stdout)
        result = data.get("result", {})
        orgs = []
        seen = set()
        for bucket in ("sandboxes", "nonScratchOrgs", "scratchOrgs", "other", "devHubs"):
            for o in result.get(bucket, []) or []:
                alias = o.get("alias") or o.get("username")
                username = o.get("username", "")
                if not alias or alias in seen:
                    continue
                seen.add(alias)
                orgs.append({"alias": alias, "username": username})
        orgs.sort(key=lambda x: x["alias"].lower())
        return orgs
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def list_models(org):
    """Return all CMLs (Expression Set constraint models) available in an org.

    Each item: {name, label, version, status}. The list is built from
    ExpressionSetDefinitionVersion so it only includes models the tool can
    actually fetch/deploy, keeping the latest version per model.
    """
    if not org:
        return {"error": "No org selected."}
    if not find_sf():
        return {"error": "The Salesforce CLI ('sf') was not found. "
                         "Install it with: npm install -g @salesforce/cli"}
    query = (
        "SELECT ExpressionSetDefinition.DeveloperName, "
        "ExpressionSetDefinition.MasterLabel, VersionNumber, Status "
        "FROM ExpressionSetDefinitionVersion "
        "ORDER BY ExpressionSetDefinition.DeveloperName, VersionNumber DESC"
    )
    records, err = _query_json(org, query)
    if err:
        return {"error": err}

    latest = {}
    for rec in records:
        defn = rec.get("ExpressionSetDefinition") or {}
        name = defn.get("DeveloperName")
        if not name or name in latest:  # records are ordered newest-first
            continue
        latest[name] = {
            "name": name,
            "label": defn.get("MasterLabel") or name,
            "version": rec.get("VersionNumber"),
            "status": rec.get("Status"),
        }
    models = sorted(latest.values(), key=lambda m: m["name"].lower())
    return {"models": models}


def _latest_version(org, model):
    """Return (record, error) for the newest ExpressionSetDefinitionVersion of a
    model. record has Id, DeveloperName, VersionNumber, Status."""
    recs, err = _query_json(
        org,
        "SELECT Id, DeveloperName, VersionNumber, Status "
        "FROM ExpressionSetDefinitionVersion "
        "WHERE ExpressionSetDefinition.DeveloperName = '" + _soql_str(model) + "' "
        "ORDER BY VersionNumber DESC LIMIT 1")
    if err:
        return None, err
    if not recs:
        return None, (f"No Expression Set Version found for '{model}' in '{org}'. "
                      "Check the CML API name and that it exists in this org.")
    return recs[0], None


def _download_cml(org, model, out_file):
    """Fetch one CML's ConstraintModel over REST into out_file (cross-platform).
    Returns a result dict."""
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    rec, err = _latest_version(org, model)
    if err:
        return {"ok": False, "log": err}
    version_id = rec["Id"]
    log = f"==> {rec.get('DeveloperName')} ({version_id}) — Status: {rec.get('Status')}"

    token, instance, cerr = _org_creds(org)
    if cerr:
        return {"ok": False, "log": cerr}

    url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
           f"ExpressionSetDefinitionVersion/{version_id}/ConstraintModel")
    content, gerr = _http_get_text(url, token)
    if gerr:
        # An empty/unpopulated ConstraintModel blob returns 404 — treat as empty.
        if "404" in gerr or "NOT_FOUND" in gerr:
            content = ""
        else:
            return {"ok": False, "log": f"{log}\nCould not download CML:\n{gerr}"}

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content or "")
    except OSError as exc:
        return {"ok": False, "log": f"{log}\nCould not write file: {exc}"}

    if not (content or "").strip():
        return {
            "ok": False, "content": "", "file": out_file, "empty": True,
            "log": (
                f"{log}\n\nThe latest version of '{model}' in '{org}' has an EMPTY "
                "Constraint Model (this usually means the version is Inactive or was "
                "never populated). Try an org where an Active version exists."
            ).strip(),
        }
    return {"ok": True, "log": log, "content": content, "file": out_file}


def fetch_cml(org, model):
    """Fetch a CML and return its content + logs."""
    if not org or not model:
        return {"ok": False, "log": "Please choose an org and enter the CML API name."}
    return _download_cml(
        org, model, os.path.join(DOWNLOAD_DIR, f"{_safe(model)}.cml"))


def _cml_text(org, model):
    """Read the current CML without writing a download file."""
    rec, err = _latest_version(org, model)
    if err:
        return None, err
    return _version_cml_text(org, rec["Id"])


def _version_cml_text(org, version_id):
    """Read the CML blob from one exact version, avoiding latest-version races."""
    token, instance, err = _org_creds(org)
    if err:
        return None, err
    url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
           f"ExpressionSetDefinitionVersion/{version_id}/ConstraintModel")
    content, err = _http_get_text(url, token)
    if err and ("404" in err or "NOT_FOUND" in err):
        return "", None
    return content, err


def _strip_cml_comments(text):
    """Remove // and /* */ comments while preserving quoted strings."""
    out, i, state, quote = [], 0, "code", ""
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if state == "code":
            if ch in ("'", '"'):
                state, quote = "string", ch
                out.append(ch)
            elif ch == "/" and nxt == "/":
                state = "line"
                out.extend("  ")
                i += 1
            elif ch == "/" and nxt == "*":
                state = "block"
                out.extend("  ")
                i += 1
            else:
                out.append(ch)
        elif state == "string":
            out.append(ch)
            if ch == "\\" and nxt:
                out.append(nxt)
                i += 1
            elif ch == quote:
                state = "code"
        elif state == "line":
            if ch == "\n":
                state = "code"
                out.append(ch)
            else:
                out.append(" ")
        else:  # block comment
            if ch == "*" and nxt == "/":
                state = "code"
                out.extend("  ")
                i += 1
            else:
                out.append("\n" if ch == "\n" else " ")
        i += 1
    return "".join(out)


def _cml_used_tags(org, model):
    """Return the Type and Port tags referenced by the current CML text."""
    text, err = _cml_text(org, model)
    if err:
        return None, err
    clean = _strip_cml_comments(text or "")
    return {
        "Type": set(re.findall(r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)", clean)),
        "Port": set(re.findall(r"\brelation\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", clean)),
    }, None


def _row_used_by_cml(row, used_tags):
    """Unknown tag kinds remain included; only recognized Type/Port rows filter."""
    if not used_tags:
        return True
    tag_type = row.get("tagType")
    return tag_type not in used_tags or row.get("tag") in used_tags[tag_type]


def _safe(name):
    raw = str(name or "")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    value = "".join(c if c in allowed else "_" for c in raw)
    value = value.strip("._")
    reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if (value.split(".", 1)[0] or "").upper() in reserved:
        value = "_" + value
    changed = value != raw or len(value) > 120
    value = value[:109] or "item"
    if changed:
        value += "__" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return value


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)


def _artifact_stamp():
    return _utc_now().strftime("%Y%m%dT%H%M%S.%fZ")


def _sha256_text(content):
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _write_json_artifact(directory, prefix, payload):
    """Write a private JSON artifact atomically and return its public metadata."""
    os.makedirs(directory, mode=0o700, exist_ok=True)
    artifact_id = f"{_artifact_stamp()}__{_safe(prefix)}.json"
    path = os.path.join(directory, artifact_id)
    temp_path = path + ".tmp"
    data = dict(payload)
    data.setdefault("createdAt", _utc_now().isoformat())
    data.setdefault("operatingSystemUser", getpass.getuser())
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    os.replace(temp_path, path)
    return {"id": artifact_id, "file": path, "createdAt": data["createdAt"]}


def _read_json_artifact(directory, artifact_id):
    safe_id = os.path.basename(artifact_id or "")
    if safe_id != artifact_id or not safe_id.endswith(".json"):
        return None, "Invalid artifact identifier."
    path = os.path.join(directory, safe_id)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except FileNotFoundError:
        return None, "The requested recovery artifact no longer exists."
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"Could not read recovery artifact: {exc}"


def _deployment_report(action, org, model, details):
    return _write_json_artifact(
        REPORT_DIR, f"{action}__{org}__{model}", {
            "kind": "deployment-report", "action": action,
            "targetOrg": org, "model": model, **details,
        })


def _create_cml_backup(org, model, version, content, reason):
    return _write_json_artifact(
        BACKUP_DIR, f"{org}__{model}__v{version.get('VersionNumber')}", {
            "kind": "cml-backup", "reason": reason,
            "org": org, "model": model,
            "versionId": version.get("Id"),
            "versionNumber": version.get("VersionNumber"),
            "versionStatus": version.get("Status"),
            "sha256": _sha256_text(content),
            "content": content or "",
        })


def list_cml_backups(org, model):
    if not org or not model:
        return {"ok": False, "log": "Choose a target org and CML model."}
    if not os.path.isdir(BACKUP_DIR):
        return {"ok": True, "backups": []}
    backups = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        data, err = _read_json_artifact(BACKUP_DIR, name)
        if err or data.get("kind") != "cml-backup":
            continue
        if data.get("org") == org and data.get("model") == model:
            backups.append({
                "id": name, "createdAt": data.get("createdAt"),
                "versionNumber": data.get("versionNumber"),
                "versionStatus": data.get("versionStatus"),
                "sha256": data.get("sha256"),
                "reason": data.get("reason"),
            })
        if len(backups) >= 50:
            break
    return {"ok": True, "backups": backups}


def compare_cml(source_org, target_org, model):
    """Fetch the same CML from two orgs so the UI can diff them."""
    if not source_org or not target_org or not model:
        return {"ok": False, "log": "Choose a source org, a target org, and a CML."}
    if source_org == target_org:
        return {"ok": False, "log": "Source and target orgs are the same. Pick two different orgs."}

    # Fetch sequentially: the `sf` CLI serializes on its own config/lock files,
    # so running two at once can hang. One after the other is reliable.
    src = _download_cml(source_org, model,
                        os.path.join(DOWNLOAD_DIR, f"{_safe(model)}__{_safe(source_org)}.cml"))
    tgt = _download_cml(target_org, model,
                        os.path.join(DOWNLOAD_DIR, f"{_safe(model)}__{_safe(target_org)}.cml"))

    # A truly empty version is informative for a comparison (e.g. Inactive),
    # so treat empty as a non-fatal result and still return its content ("").
    def norm(res, org):
        if res.get("ok") or res.get("empty"):
            return {"org": org, "content": res.get("content", ""),
                    "file": res.get("file"), "log": res.get("log", "")}
        return None

    s = norm(src, source_org)
    t = norm(tgt, target_org)
    if s is None:
        return {"ok": False, "log": f"Could not fetch from source '{source_org}':\n{src.get('log')}"}
    if t is None:
        return {"ok": False, "log": f"Could not fetch from target '{target_org}':\n{tgt.get('log')}"}
    return {"ok": True, "model": model, "source": s, "target": t}


# ---------------------------------------------------------------------------
# Constraint data (ExpressionSetConstraintObj) — visualize & compare
#
# Each row links a CML (ExpressionSet) to a Product / ProductClassification /
# ProductComponentGroup / ProductRelatedComponent via a polymorphic lookup
# (ReferenceObjectId). Record Ids differ per org, so rows are made portable by
# keying on the reference object's Global_Key__c (stable across orgs) plus the
# tag + tag type. See README for the mapping rationale.
# ---------------------------------------------------------------------------

# Object types ReferenceObjectId can point to (all carry Global_Key__c).
REF_TYPES = ("Product2", "ProductClassification",
             "ProductComponentGroup", "ProductRelatedComponent")


def _soql_str(value):
    """Escape a value for safe inclusion in a single-quoted SOQL literal."""
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


# The field used to match reference records across orgs. Defaults to the custom
# Global_Key__c, but any field can be chosen so orgs without that field can use
# their own foreign key (e.g. an external Id, a code, or even Name).
DEFAULT_KEY_FIELD = "Global_Key__c"
_FIELD_PROBE = {}  # (org, sobject, field) -> (bool, expiry monotonic time)


def _valid_field(name):
    """Return a SOQL-safe field API name, or None if it isn't a plain identifier.

    The key field is interpolated directly into SOQL (TYPEOF / SELECT / WHERE),
    so it must be validated to prevent injection. Blank means "use the default".
    """
    name = (name or "").strip()
    if not name:
        return DEFAULT_KEY_FIELD
    if len(name) <= 80 and re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name):
        return name
    return None


def _field_exists(org, sobject, field):
    """Cheap, cached probe: does `sobject` expose `field`? (SELECT ... LIMIT 1).

    Lets us include the chosen key only on the reference objects that actually
    have it, instead of failing the whole TYPEOF query when one object lacks it.
    """
    ck = (org, sobject, field)
    cached = _FIELD_PROBE.get(ck)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    _, err = _query_json(org, f"SELECT {field} FROM {sobject} LIMIT 1")
    if err:
        invalid = any(marker in err for marker in (
            "INVALID_FIELD", "No such column", "INVALID_TYPE",
            "INVALID_FIELD_FOR_INSERT"))
        if invalid:
            _FIELD_PROBE[ck] = (False, time.monotonic() + FIELD_PROBE_TTL)
        return False
    _FIELD_PROBE[ck] = (True, time.monotonic() + FIELD_PROBE_TTL)
    return True


def _is_auth_error(msg):
    msg = (msg or "")
    return (
        "INVALID_SESSION_ID" in msg
        or "INVALID_AUTH_HEADER" in msg
        or "INVALID_LOGIN" in msg
        or "MISSING_OAUTH_TOKEN" in msg
        or "401" in msg
        or "Session expired" in msg
    )


def _auth_help(org, raw):
    """Actionable message for auth failures a token re-read can't fix — the saved
    session for this org is expired/invalid and needs a real re-login."""
    return (
        f"Salesforce rejected the saved login for '{org}'.\n"
        f"Details: {raw}\n\n"
        "This almost always means the org's saved session has expired or was "
        "revoked. Re-authenticate in a terminal, then click \u201cReload list\u201d:\n"
        f"    sf org login web --target-org {org}\n\n"
        "If it still fails, log out and back in, then reload:\n"
        f"    sf org logout --no-prompt --target-org {org}\n"
        f"    sf org login web --alias {org}"
    )


def _query_json(org, soql, _retried=False):
    """Run a SOQL query over the REST API and return (records, error).

    Using REST (instead of `sf data query`) avoids shell-quoting the SOQL on
    Windows and is much faster, since we reuse the cached access token.
    """
    token, instance, err = _org_creds(org)
    if err:
        return None, err
    records = []
    url = f"{instance}/services/data/{API_VERSION}/query?q=" + urllib.parse.quote(soql)
    guard = 0
    while url and guard < 2000:
        guard += 1
        data, e = _rest("GET", url, token)
        if e:
            if _is_auth_error(e) and not _retried:
                _org_creds(org, refresh=True)  # token likely expired; refresh once
                return _query_json(org, soql, _retried=True)
            if _is_auth_error(e):  # refresh didn't help — needs a real re-login
                return None, _auth_help(org, e)
            return None, e
        records.extend(data.get("records", []) or [])
        nxt = data.get("nextRecordsUrl")
        url = (instance + nxt) if nxt else None
    return records, None


def _constraint_key(tag_type, tag, ref_type, gkey):
    """Org-portable identity for one constraint row."""
    return "\u241f".join([tag_type or "", tag or "", ref_type or "",
                          gkey or ""])


def _build_typeof(org, key_field):
    """Build the TYPEOF clause, including `key_field` only on the reference
    objects that actually have it. Returns (clause, {refType: has_field})."""
    field_on = {}
    whens = []
    for t in REF_TYPES:
        has = _field_exists(org, t, key_field)
        field_on[t] = has
        cols = []
        if has:
            cols.append(key_field)
        for c in (["Name", "ProductCode"] if t == "Product2" else ["Name"]):
            if c not in cols:
                cols.append(c)
        whens.append(f"WHEN {t} THEN " + ", ".join(cols))
    clause = "TYPEOF ReferenceObject " + " ".join(whens) + " ELSE Name END "
    return clause, field_on


def export_constraints(org, model, key_field=DEFAULT_KEY_FIELD):
    """Return enriched ExpressionSetConstraintObj rows for one CML model.

    Each row is resolved to its reference object's type + the chosen `key_field`
    (default Global_Key__c) so it can be matched across orgs regardless of Ids.
    """
    if not org or not model:
        return {"ok": False, "log": "Choose an org and a CML first."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name. Use a plain "
            "field name like Global_Key__c, ProductCode, External_Id__c, or Name.")}

    typeof, field_on = _build_typeof(org, kf)
    if not any(field_on.values()):
        return {"ok": False, "log": (
            f"None of the reference objects (Product2, ProductClassification, "
            f"ProductComponentGroup, ProductRelatedComponent) have a field named "
            f"\u201c{kf}\u201d in {org}. Pick a field that exists on them "
            f"(\u201cName\u201d always works), then try again.")}

    soql = (
        "SELECT Id, ExpressionSetId, ExpressionSet.Name, ConstraintModelTag, "
        "ConstraintModelTagType, ReferenceObjectId, " + typeof +
        "FROM ExpressionSetConstraintObj "
        "WHERE ExpressionSet.ExpressionSetDefinition.DeveloperName = '"
        + _soql_str(model) + "' "
        "ORDER BY ConstraintModelTagType, ConstraintModelTag"
    )
    records, err = _query_json(org, soql)
    if err:
        return {"ok": False, "log": f"Could not load constraint data from {org}:\n{err}"}

    rows = []
    for rec in records:
        ro = rec.get("ReferenceObject") or {}
        ref_type = (ro.get("attributes") or {}).get("type") or ""
        gkey = ro.get(kf)
        tag = rec.get("ConstraintModelTag")
        tag_type = rec.get("ConstraintModelTagType")
        rows.append({
            "id": rec.get("Id"),
            "expressionSetId": rec.get("ExpressionSetId"),
            "tag": tag,
            "tagType": tag_type,
            "refType": ref_type,
            "refName": ro.get("Name"),
            "refCode": ro.get("ProductCode"),
            "gkey": gkey,
            "refId": rec.get("ReferenceObjectId"),
        })

    # A PRC can legitimately have no chosen key field in one org while still
    # representing the same relationship as another org. Give PRC rows a
    # canonical, org-portable identity based on the parent/child endpoints and
    # relationship type. This also prevents a successful fallback deployment
    # from continuing to appear as source-only on the next comparison.
    prc_ids = [r["refId"] for r in rows
               if r["refType"] == "ProductRelatedComponent" and r.get("refId")]
    prc_details = _prc_details(org, prc_ids, kf)
    unmapped = 0
    for row in rows:
        detail = prc_details.get(row.get("refId")) or {}
        prc_identity = detail.get("identity")
        if detail:
            row["prcIdentity"] = prc_identity
            row["prcParentName"] = detail.get("parentName")
            row["prcChildName"] = detail.get("childName")
            row["prcRelationshipType"] = detail.get("relationshipTypeName")
        portable_ref = prc_identity if row["refType"] == "ProductRelatedComponent" else row.get("gkey")
        row["mappable"] = bool(portable_ref)
        row["key"] = _constraint_key(
            row.get("tagType"), row.get("tag"), row.get("refType"), portable_ref)
        if not row["mappable"]:
            unmapped += 1

    dup_stats = _flag_duplicates(rows)
    return {"ok": True, "org": org, "model": model, "rows": rows,
            "keyField": kf,
            "stats": {"total": len(rows), "unmappable": unmapped,
                      "duplicates": dup_stats}}


def _flag_duplicates(rows):
    """Annotate each row with a `dups` list and return duplicate counts.

    Flags:
      exact - the same constraint (tag type + tag + ref type + Global_Key)
              appears more than once (truly redundant rows).
      tag   - the same tag type + tag is used by more than one row.
      ref   - the same reference record (type + Global_Key) is used by
              more than one row.
      name  - the same reference *name* maps to more than one Global_Key
              (ambiguous name — a cross-org mapping hazard).
    """
    from collections import defaultdict
    by_exact, by_tag, by_ref, by_name = (defaultdict(list) for _ in range(4))
    for i, r in enumerate(rows):
        by_exact[r["key"]].append(i)
        by_tag[(r["tagType"], r["tag"])].append(i)
        if r["gkey"]:
            by_ref[(r["refType"], r["gkey"])].append(i)
        if r["refName"]:
            by_name[(r["refType"], r["refName"])].append(i)

    for r in rows:
        r["dups"] = []
    counts = {"exact": 0, "tag": 0, "ref": 0, "name": 0}

    for idxs in by_exact.values():
        if len(idxs) > 1:
            for i in idxs:
                rows[i]["dups"].append("exact")
            counts["exact"] += len(idxs)
    for idxs in by_tag.values():
        if len(idxs) > 1:
            for i in idxs:
                if "exact" not in rows[i]["dups"]:
                    rows[i]["dups"].append("tag")
            counts["tag"] += len(idxs)
    for idxs in by_ref.values():
        if len(idxs) > 1:
            for i in idxs:
                rows[i]["dups"].append("ref")
            counts["ref"] += len(idxs)
    for idxs in by_name.values():
        gkeys = {rows[i]["gkey"] for i in idxs}
        if len(gkeys) > 1:  # same name, different keys -> ambiguous
            for i in idxs:
                rows[i]["dups"].append("name")
            counts["name"] += len(idxs)
    return counts


def _target_present_keys(target_org, needed, key_field):
    """Given {refType: set(keys)} needed in the target, return the set of
    (refType, key) that actually exist there. Used to flag whether a
    source-only constraint can be deployed (its reference record exists)."""
    present = set()
    for ref_type, keys in needed.items():
        keys = [g for g in keys if g]
        if not keys:
            continue
        for i in range(0, len(keys), 200):  # keep IN-lists well under limits
            chunk = keys[i:i + 200]
            in_list = ",".join("'" + _soql_str(g) + "'" for g in chunk)
            soql = (f"SELECT {key_field} FROM {ref_type} "
                    f"WHERE {key_field} IN ({in_list})")
            recs, err = _query_json(target_org, soql)
            if err:  # treat as unknown rather than blocking the whole compare
                continue
            for r in recs:
                present.add((ref_type, r.get(key_field)))
    return present


def _portable_child_field(source_org, target_org, sobject, preferred):
    """Choose a readable cross-org key for catalog dependency auditing."""
    for field in (preferred, DEFAULT_KEY_FIELD, "ProductCode", "Name"):
        if (field and _valid_field(field)
                and _field_exists(source_org, sobject, field)
                and _field_exists(target_org, sobject, field)):
            return field
    return None


def _records_by_parent(org, sobject, parent_field, parent_ids, fields):
    """Read bounded catalog children for a known set of parent record IDs."""
    result = []
    ids = sorted({str(x) for x in parent_ids if x})
    for i in range(0, len(ids), 200):
        values = ",".join("'" + _soql_str(x) + "'" for x in ids[i:i + 200])
        recs, err = _query_json(
            org,
            f"SELECT {', '.join(fields)} FROM {sobject} "
            f"WHERE {parent_field} IN ({values})")
        if err:
            return [], err
        result.extend(recs)
    return result, None


def _records_by_keys(org, sobject, key_field, keys, fields):
    """Read target catalog records matching a bounded set of portable keys."""
    result = []
    values = sorted({str(x) for x in keys if x is not None and str(x)})
    for i in range(0, len(values), 200):
        in_list = ",".join(
            "'" + _soql_str(x) + "'" for x in values[i:i + 200])
        recs, err = _query_json(
            org,
            f"SELECT {', '.join(fields)} FROM {sobject} "
            f"WHERE {key_field} IN ({in_list})")
        if err:
            return [], err
        result.extend(recs)
    return result, None


def _classification_dependency_audit(source_org, target_org, source_rows,
                                     target_rows, key_field):
    """Read-only preflight for ProductClassification-backed CML types.

    A matching ExpressionSetConstraintObj is not enough: the target
    classification must also own the products and classification attributes
    represented by the source. This function only reads catalog objects and
    returns issues keyed by (reference type, portable classification key).
    """
    source_classes = {
        r.get("gkey"): r for r in source_rows
        if r.get("refType") == "ProductClassification" and r.get("gkey")
    }
    target_classes = {
        r.get("gkey"): r for r in target_rows
        if r.get("refType") == "ProductClassification" and r.get("gkey")
    }
    issues = {}
    if not source_classes:
        return issues

    product_key = _portable_child_field(
        source_org, target_org, "Product2", key_field)
    attr_key = _portable_child_field(
        source_org, target_org, "ProductClassificationAttr", key_field)

    source_ids = [r.get("refId") for r in source_classes.values()]
    source_products, product_err = ([], None)
    target_products, target_product_err = ([], None)
    source_attrs, attr_err = ([], None)
    target_attrs, target_attr_err = ([], None)

    if product_key:
        fields = ["Id", "Name", product_key, "BasedOnId"]
        source_products, product_err = _records_by_parent(
            source_org, "Product2", "BasedOnId", source_ids, fields)
        target_products, target_product_err = _records_by_keys(
            target_org, "Product2", product_key,
            [r.get(product_key) for r in source_products], fields)
    if attr_key:
        fields = ["Id", "Name", attr_key, "ProductClassificationId"]
        source_attrs, attr_err = _records_by_parent(
            source_org, "ProductClassificationAttr",
            "ProductClassificationId", source_ids, fields)
        target_attrs, target_attr_err = _records_by_keys(
            target_org, "ProductClassificationAttr", attr_key,
            [r.get(attr_key) for r in source_attrs], fields)

    products_by_source = {}
    for record in source_products:
        products_by_source.setdefault(record.get("BasedOnId"), []).append(record)
    attrs_by_source = {}
    for record in source_attrs:
        attrs_by_source.setdefault(
            record.get("ProductClassificationId"), []).append(record)
    target_products_by_key = {}
    for record in target_products:
        target_products_by_key.setdefault(record.get(product_key), []).append(record)
    target_attrs_by_key = {}
    for record in target_attrs:
        target_attrs_by_key.setdefault(record.get(attr_key), []).append(record)

    for class_key, source_row in source_classes.items():
        target_row = target_classes.get(class_key)
        if not target_row:
            continue  # the main comparison reports the missing classification
        row_issues = []
        if product_err or target_product_err or not product_key:
            row_issues.append({
                "kind": "Product2", "state": "unknown",
                "name": source_row.get("refName"),
                "message": "Could not verify products assigned to this "
                           "classification in both orgs.",
            })
        else:
            for source_product in products_by_source.get(
                    source_row.get("refId"), []):
                value = source_product.get(product_key)
                label = source_product.get("Name") or value
                if value is None or not str(value).strip():
                    message = (
                        f"Source catalog product '{label}' has no {product_key}. "
                        "The tool cannot match it to a target product; this does "
                        "not prove that the product is missing.")
                    state = "unmappable"
                else:
                    matches = target_products_by_key.get(value, [])
                    if not matches:
                        message = (
                            f"Missing catalog product '{label}' "
                            f"({product_key}: {value}).")
                        state = "missing"
                    elif len(matches) > 1:
                        message = (
                            f"{len(matches)} target products match '{label}' "
                            f"({product_key}: {value}); mapping is ambiguous.")
                        state = "ambiguous"
                    elif matches[0].get("BasedOnId") != target_row.get("refId"):
                        message = (
                            f"Product '{label}' exists but is not assigned to target "
                            f"classification '{target_row.get('refName')}'.")
                        state = "unlinked"
                    else:
                        continue
                row_issues.append({
                    "kind": "Product2", "state": state, "name": label,
                    "key": value, "message": message,
                })
        if attr_err or target_attr_err or not attr_key:
            row_issues.append({
                "kind": "ProductClassificationAttr", "state": "unknown",
                "name": source_row.get("refName"),
                "message": "Could not verify classification attributes in both orgs.",
            })
        else:
            for source_attr in attrs_by_source.get(source_row.get("refId"), []):
                value = source_attr.get(attr_key)
                label = source_attr.get("Name") or value
                if value is None or not str(value).strip():
                    message = (
                        f"Source classification attribute '{label}' has no "
                        f"{attr_key}. The tool cannot match it to the target; "
                        "this does not prove that the attribute is missing.")
                    state = "unmappable"
                else:
                    matches = target_attrs_by_key.get(value, [])
                    if not matches:
                        message = (
                            f"Missing classification attribute '{label}' "
                            f"({attr_key}: {value}).")
                        state = "missing"
                    elif len(matches) > 1:
                        message = (
                            f"{len(matches)} target classification attributes match "
                            f"'{label}' ({attr_key}: {value}); mapping is ambiguous.")
                        state = "ambiguous"
                    elif matches[0].get("ProductClassificationId") != target_row.get("refId"):
                        message = (
                            f"Classification attribute '{label}' exists but belongs "
                            "to a different target classification.")
                        state = "unlinked"
                    else:
                        continue
                row_issues.append({
                    "kind": "ProductClassificationAttr", "state": state,
                    "name": label, "key": value, "message": message,
                })
        if row_issues:
            issues[("ProductClassification", class_key)] = row_issues
    return issues


def _prc_identity(parent_key, child_kind, child_key, relationship_type):
    """Stable cross-org identity for one ProductRelatedComponent.

    ProductRelatedComponent.Global_Key__c isn't available in every org. Parent
    and child portable keys plus the relationship type describe the business
    relationship without relying on source IDs. Component group and sequence
    are deliberately excluded: migrated orgs can have a stale/missing group
    lookup or a different sequence while still representing the same relation.
    Duplicate identities are treated as ambiguous instead of picking one.
    """
    if not parent_key or not child_key or not relationship_type:
        return None
    return "\u241f".join([
        str(parent_key), child_kind or "", str(child_key), str(relationship_type)
    ])


def _prc_select_fields(org, kf):
    """Return safe PRC fields and endpoint capability flags for this org."""
    product_key = _field_exists(org, "Product2", kf)
    classification_key = _field_exists(org, "ProductClassification", kf)
    group_key = _field_exists(org, "ProductComponentGroup", kf)
    fields = ["Id"]
    lookups = (
        ("ParentProductId", "ParentProduct.Name"),
        ("ChildProductId", "ChildProduct.Name"),
        ("ChildProductClassificationId", "ChildProductClassification.Name"),
        ("ProductRelationshipTypeId", "ProductRelationshipType.Name"),
        ("ProductComponentGroupId", "ProductComponentGroup.Name"),
        ("ParentSellingModelId", "ParentSellingModel.Name"),
        ("ChildSellingModelId", "ChildSellingModel.Name"),
    )
    for id_field, relationship_field in lookups:
        if _field_exists(org, "ProductRelatedComponent", id_field):
            fields.extend([id_field, relationship_field])
    for field in (
        "Quantity", "Sequence", "DoesBundlePriceIncludeChild",
        "QuantityScaleMethod", "MaxQuantity", "MinQuantity",
        "IsComponentRequired", "IsQuantityEditable", "IsDefaultComponent",
        "QuoteVisibility",
    ):
        # The package API version can lag behind the installed CLI's describe
        # version, so include only fields queryable through this tool's REST API.
        if _field_exists(org, "ProductRelatedComponent", field):
            fields.append(field)
    if product_key:
        fields.extend([f"ParentProduct.{kf}", f"ChildProduct.{kf}"])
    if classification_key:
        fields.append(f"ChildProductClassification.{kf}")
    if group_key:
        fields.append(f"ProductComponentGroup.{kf}")
    return fields, {
        "product": product_key,
        "classification": classification_key,
        "group": group_key,
    }


def _prc_detail_from_record(record, kf):
    parent = record.get("ParentProduct") or {}
    child_product = record.get("ChildProduct") or {}
    child_classification = record.get("ChildProductClassification") or {}
    relationship_type = record.get("ProductRelationshipType") or {}
    group = record.get("ProductComponentGroup") or {}
    parent_selling = record.get("ParentSellingModel") or {}
    child_selling = record.get("ChildSellingModel") or {}

    if record.get("ChildProductId"):
        child_kind = "Product2"
        child = child_product
    elif record.get("ChildProductClassificationId"):
        child_kind = "ProductClassification"
        child = child_classification
    else:
        child_kind = ""
        child = {}

    detail = {
        "id": record.get("Id"),
        "parentId": record.get("ParentProductId"),
        "parentKey": parent.get(kf),
        "parentName": parent.get("Name"),
        "childKind": child_kind,
        "childId": (record.get("ChildProductId")
                    or record.get("ChildProductClassificationId")),
        "childKey": child.get(kf),
        "childName": child.get("Name"),
        "relationshipTypeId": record.get("ProductRelationshipTypeId"),
        "relationshipTypeName": relationship_type.get("Name"),
        "groupId": record.get("ProductComponentGroupId"),
        "groupKey": group.get(kf),
        "groupName": group.get("Name"),
        "parentSellingModelId": record.get("ParentSellingModelId"),
        "parentSellingModelName": parent_selling.get("Name"),
        "childSellingModelId": record.get("ChildSellingModelId"),
        "childSellingModelName": child_selling.get("Name"),
    }
    for field in (
        "Quantity", "Sequence", "DoesBundlePriceIncludeChild",
        "QuantityScaleMethod", "MaxQuantity", "MinQuantity",
        "IsComponentRequired", "IsQuantityEditable", "IsDefaultComponent",
        "QuoteVisibility",
    ):
        detail[field] = record.get(field)
    detail["identity"] = _prc_identity(
        detail["parentKey"], detail["childKind"], detail["childKey"],
        detail["relationshipTypeName"])
    return detail


def _prc_details(org, prc_ref_ids, kf):
    """Return authoritative PRC endpoint/details keyed by PRC Id."""
    ids = sorted({x for x in prc_ref_ids if x and str(x).startswith("0dS")})
    if not ids:
        return {}
    fields, _ = _prc_select_fields(org, kf)
    result = {}
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        in_list = ",".join("'" + _soql_str(x) + "'" for x in chunk)
        recs, err = _query_json(
            org,
            f"SELECT {', '.join(fields)} FROM ProductRelatedComponent "
            f"WHERE Id IN ({in_list})")
        if err:
            continue
        for record in recs:
            detail = _prc_detail_from_record(record, kf)
            detail["sourceOrg"] = org
            result[record["Id"]] = detail
    return result


def _target_prc_by_identity(target_org, source_details, kf):
    """Return canonical identity -> candidate target PRC Ids.

    Candidate records are filtered by parent keys, then canonicalized using
    target endpoint keys. This handles target orgs that don't have the selected
    key field on ProductRelatedComponent itself.
    """
    details = [d for d in source_details if d.get("identity")]
    parent_keys = sorted({d["parentKey"] for d in details if d.get("parentKey")})
    if not parent_keys or not _field_exists(target_org, "Product2", kf):
        return {}
    fields, _ = _prc_select_fields(target_org, kf)
    result = {}
    for i in range(0, len(parent_keys), 100):
        chunk = parent_keys[i:i + 100]
        in_list = ",".join("'" + _soql_str(k) + "'" for k in chunk)
        recs, err = _query_json(
            target_org,
            f"SELECT {', '.join(fields)} FROM ProductRelatedComponent "
            f"WHERE ParentProduct.{kf} IN ({in_list})")
        if err:
            continue
        for record in recs:
            detail = _prc_detail_from_record(record, kf)
            identity = detail.get("identity")
            if identity:
                result.setdefault(identity, []).append(record["Id"])
    return result


def compare_constraints(source_org, target_org, model, key_field=DEFAULT_KEY_FIELD):
    """Compare constraint data of one CML between two orgs, keyed on the
    portable composite key. Returns matched / source-only / target-only rows
    plus, for source-only rows, whether the reference record exists in target.
    """
    if not source_org or not target_org or not model:
        return {"ok": False, "log": "Choose a source org, a target org, and a CML."}
    if source_org == target_org:
        return {"ok": False, "log": "Source and target orgs are the same. Pick two different orgs."}

    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name. Use a plain "
            "field name like Global_Key__c, ProductCode, External_Id__c, or Name.")}

    src = export_constraints(source_org, model, kf)
    if not src.get("ok"):
        return src
    tgt = export_constraints(target_org, model, kf)
    if not tgt.get("ok"):
        return tgt

    source_tags, tags_err = _cml_used_tags(source_org, model)
    if tags_err:
        return {"ok": False, "log": (
            f"Could not read the source CML in {source_org}, so association "
            f"deployment was stopped safely:\n{tags_err}")}
    target_tags, tags_err = _cml_used_tags(target_org, model)
    if tags_err:
        return {"ok": False, "log": (
            f"Could not read the target CML in {target_org}, so association "
            f"deployment was stopped safely:\n{tags_err}")}
    active_source = [
        r for r in src["rows"] if _row_used_by_cml(r, source_tags)]
    active_target = [
        r for r in tgt["rows"] if _row_used_by_cml(r, target_tags)]
    stale = []
    for origin, own_tags, rows in (
        ("source", source_tags, src["rows"]),
        ("target", target_tags, tgt["rows"]),
    ):
        for raw in (r for r in rows if not _row_used_by_cml(r, own_tags)):
            row = dict(raw)
            row["staleOrigin"] = origin
            row["deployStatus"] = "stale"
            row["blockNote"] = (
                f"This association exists in the {origin} org, but that same "
                f"org's current CML does not define {row.get('tagType')} "
                f"'{row.get('tag')}'. It may be a leftover from an older CML "
                "version. The tool will not add or delete it automatically.")
            stale.append(row)

    src_by = {r["key"]: r for r in active_source}
    tgt_by = {r["key"]: r for r in active_target}
    dependency_issues = _classification_dependency_audit(
        source_org, target_org, active_source, active_target, kf)

    def apply_dependency_preflight(raw):
        row = dict(raw)
        found = dependency_issues.get((row.get("refType"), row.get("gkey")), [])
        if found and row.get("deployStatus") != "cml-difference":
            row["dependencyIssues"] = found
            uncertain = all(
                issue.get("state") in ("unmappable", "unknown")
                for issue in found)
            row["deployStatus"] = (
                "dependency-unverified" if uncertain else "blocked")
            prefix = (
                "Catalog dependency check is incomplete: " if uncertain
                else "Catalog dependency check failed: ")
            row["blockNote"] = prefix + " ".join(
                issue["message"] for issue in found)
        return row

    # Reference records needed in target for the rows that are only in source.
    needed = {}
    for key, r in src_by.items():
        if (key not in tgt_by and r["mappable"]
                and r["refType"] != "ProductRelatedComponent"):
            needed.setdefault(r["refType"], set()).add(r["gkey"])
    present = _target_present_keys(target_org, needed, kf)

    # Canonical PRC identities are used for the main comparison key. For PRCs
    # that are genuinely source-only, locate any existing target relationship
    # again so the UI can distinguish "ready" from "must create prerequisite".
    source_only_prc_rows = [
        r for key, r in src_by.items()
        if key not in tgt_by
        and r["refType"] == "ProductRelatedComponent"
        and r.get("prcIdentity")
    ]
    src_prc_details = _prc_details(
        source_org,
        [r.get("refId") for r in source_only_prc_rows],
        kf)
    target_prcs = _target_prc_by_identity(
        target_org, list(src_prc_details.values()), kf)

    matched, source_only, target_only = [], [], []
    for key, r in src_by.items():
        if key in tgt_by:
            matched.append(apply_dependency_preflight(r))
        else:
            row = dict(r)
            if not r["mappable"]:
                row["deployStatus"] = "unmappable"
            elif not _row_used_by_cml(r, target_tags):
                row["deployStatus"] = "cml-difference"
                row["blockNote"] = (
                    f"The source CML defines {r.get('tagType')} "
                    f"'{r.get('tag')}', but the target CML does not. Compare "
                    "and deploy the intended CML code first; this association "
                    "is not safe to add yet.")
            elif (r["refType"], r["gkey"]) in present:
                row["deployStatus"] = "ready"
            elif r["refType"] == "ProductRelatedComponent":
                detail = src_prc_details.get(r.get("refId")) or {}
                identity = detail.get("identity")
                if identity:
                    candidates = target_prcs.get(identity, [])
                    relation = (
                        f"{detail.get('parentName') or detail.get('parentKey')} \u2192 "
                        f"{detail.get('childName') or detail.get('childKey')} "
                        f"({detail.get('relationshipTypeName')})"
                    )
                    if len(candidates) == 1:
                        row["deployStatus"] = "ready"
                        row["prcResolution"] = "existing"
                        row["blockNote"] = (
                            f"Resolved to existing target relationship: {relation}"
                        )
                    elif len(candidates) > 1:
                        row["deployStatus"] = "blocked"
                        row["blockNote"] = (
                            f"Ambiguous: {len(candidates)} target PRC records match "
                            f"{relation}. Resolve duplicates before deployment."
                        )
                    else:
                        row["deployStatus"] = "blocked"
                        row["blockNote"] = (
                            f"Missing catalog relationship: {relation}. This tool "
                            "is read-only for ProductRelatedComponent; deploy the "
                            "catalog relationship separately, then compare again."
                        )
                else:
                    row["deployStatus"] = "blocked"
                    row["blockNote"] = (
                        f"Cannot resolve portable endpoint keys for this "
                        f"ProductRelatedComponent using {kf}."
                    )
                source_only.append(row)
                continue
            else:
                row["deployStatus"] = "blocked"
                row["blockNote"] = (
                    f"Missing catalog {r['refType']}: "
                    f"{r.get('refName') or r.get('gkey')}. This tool will not "
                    "create or update catalog records; deploy it separately, "
                    "then compare again."
                )
            row = apply_dependency_preflight(row)
            source_only.append(row)
    for key, r in tgt_by.items():
        if key not in src_by:
            row = dict(r)
            if not _row_used_by_cml(r, source_tags):
                row["deployStatus"] = "cml-difference"
                row["blockNote"] = (
                    f"This association is valid for the target CML, which "
                    f"defines {r.get('tagType')} '{r.get('tag')}', but the "
                    "source CML does not define that tag. Both models can be "
                    "Active and still have this difference. Compare the CML "
                    "code before deciding whether anything should be removed.")
            target_only.append(row)

    return {
        "ok": True, "model": model, "keyField": kf,
        "source": {"org": source_org, "total": len(src["rows"]),
                   "duplicates": src["stats"]["duplicates"]},
        "target": {"org": target_org, "total": len(tgt["rows"]),
                   "duplicates": tgt["stats"]["duplicates"]},
        "matched": matched,
        "sourceOnly": source_only,
        "targetOnly": target_only,
        "stale": stale,
        "dependencyIssues": [
            {"refType": ref_type, "gkey": gkey, "issues": found}
            for (ref_type, gkey), found in dependency_issues.items()
        ],
        "stats": {
            "matched": len(matched),
            "sourceOnly": len(source_only),
            "targetOnly": len(target_only),
            "cmlDifferences": sum(
                1 for r in source_only + target_only
                if r.get("deployStatus") == "cml-difference"),
            "ready": sum(1 for r in source_only if r.get("deployStatus") == "ready"),
            "blocked": sum(
                1 for r in matched + source_only
                if r.get("deployStatus") == "blocked"),
            "dependencyUnverified": sum(
                1 for r in matched + source_only
                if r.get("deployStatus") == "dependency-unverified"),
            "dependencyBlocked": sum(
                1 for r in matched + source_only
                if r.get("deployStatus") == "blocked"
                and r.get("dependencyIssues")),
            "dependencyIssues": sum(
                len(found) for found in dependency_issues.values()),
            "unmappable": sum(1 for r in source_only if r.get("deployStatus") == "unmappable"),
            "stale": len(stale),
        },
    }


_CREDS_CACHE = {}  # org -> (token, instanceUrl) for the life of this process


def _looks_like_token(token):
    """A real Salesforce access token looks like `00D...!...`. Newer CLIs
    (May 2026 security update) redact it in `sf org display`, returning a
    placeholder like `[REDACTED] Use 'sf org auth show-access-token' to view`.
    Every genuine token contains a `!`, so that's a reliable tell."""
    return bool(token) and "!" in token and "REDACTED" not in token


def _fetch_access_token(org):
    """Get a live access token via the dedicated command that newer CLIs require
    (`sf org display` no longer returns it). Returns (token, error)."""
    try:
        proc = _sf_run(["org", "auth", "show-access-token",
                        "--target-org", org, "--json", "--no-prompt"])
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not read the access token for '{org}': {exc}"
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, (proc.stderr or "Could not read the access token.").strip()
    if data.get("status") != 0:
        return None, data.get("message") or "Could not read the access token."
    tok = (data.get("result") or {}).get("accessToken")
    if not _looks_like_token(tok):
        return None, None  # command exists but gave nothing usable
    return tok, None


def _org_creds(org, refresh=False):
    """Return (accessToken, instanceUrl, error). Cached per org; pass
    refresh=True to force a new lookup (e.g. after a 401)."""
    if not refresh and org in _CREDS_CACHE:
        token, url = _CREDS_CACHE[org]
        return token, url, None
    try:
        proc = _sf_run(["org", "display", "--target-org", org, "--json"])
    except Exception as exc:  # noqa: BLE001
        return None, None, f"Could not read org credentials: {exc}"
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return None, None, (proc.stderr or "Could not read org credentials.").strip()
    if data.get("status") != 0:
        return None, None, data.get("message") or "Could not read org credentials."
    res = data.get("result", {})
    token, url = res.get("accessToken"), res.get("instanceUrl")
    # Newer Salesforce CLIs redact the token in `org display` output. When that
    # happens, fetch it with the dedicated `org auth show-access-token` command.
    if not _looks_like_token(token):
        token, terr = _fetch_access_token(org)
        if terr:
            return None, None, terr
    if not token or not url:
        return None, None, _auth_help(org, "No usable access token was returned.")
    _CREDS_CACHE[org] = (token, url)
    return token, url, None


def _fmt_rest_error(code, parsed, body):
    """Turn a Salesforce REST error body into a readable one-line message."""
    if isinstance(parsed, list) and parsed:
        parts = []
        for x in parsed:
            if isinstance(x, dict):
                ec, msg = x.get("errorCode", ""), x.get("message", "")
                parts.append(f"{ec}: {msg}".strip(": ").strip())
        if parts:
            return "; ".join(parts)
    if isinstance(parsed, dict) and parsed.get("message"):
        return f"{parsed.get('errorCode', '')}: {parsed['message']}".strip(": ").strip()
    return f"HTTP {code}: {(body or '')[:300]}"


def _rest(method, url, token, payload=None):
    """Make a JSON REST call. Returns (parsed_json_or_None, error). `error` is
    set for any HTTP >= 400 (with the Salesforce error message). Per-record
    failures in a 200 sObject-Collections response are NOT errors here — the
    caller inspects each record."""
    import ssl
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=CMD_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return (json.loads(body) if body.strip() else {}), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        return parsed, _fmt_rest_error(e.code, parsed, body)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _http_get_text(url, token):
    """GET a raw (non-JSON) resource such as the ConstraintModel blob.
    Returns (text, error)."""
    import ssl
    req = urllib.request.Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {token}")
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=CMD_TIMEOUT) as resp:
            return resp.read().decode("utf-8"), None
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        return None, _fmt_rest_error(e.code, parsed, body)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def _collections_insert(token, instance, records):
    """Insert CML association rows via sObject Collections.

    Catalog objects are intentionally read-only in this tool. Keep the write
    allowlist here, at the lowest shared DML boundary, so future callers cannot
    accidentally create Product2, ProductClassification, component groups, or
    product relationships.
    """
    disallowed = [
        r for r in records
        if (r.get("attributes") or {}).get("type") != "ExpressionSetConstraintObj"
    ]
    if disallowed:
        return [{
            "success": False, "id": None,
            "error": "Write blocked by safety policy: only "
                     "ExpressionSetConstraintObj can be inserted.",
        } for _ in records]
    url = f"{instance}/services/data/{API_VERSION}/composite/sobjects"
    out = []
    for i in range(0, len(records), 200):
        chunk = records[i:i + 200]
        payload = {"allOrNone": False, "records": chunk}
        res, err = _rest("POST", url, token, payload)
        if err:
            out.extend({"success": False, "id": None, "error": err} for _ in chunk)
            continue
        for r in res:
            errs = r.get("errors") or []
            msg = "; ".join(e.get("message", "") for e in errs) if errs else None
            out.append({"success": bool(r.get("success")), "id": r.get("id"), "error": msg})
    return out


def _collections_delete(token, instance, ids):
    """Delete only ExpressionSetConstraintObj records."""
    if any(not str(record_id).startswith("1JE") for record_id in ids):
        return [{
            "success": False, "id": record_id,
            "error": "Delete blocked by safety policy: only "
                     "ExpressionSetConstraintObj can be deleted.",
        } for record_id in ids]
    out = []
    for i in range(0, len(ids), 200):
        chunk = ids[i:i + 200]
        url = (f"{instance}/services/data/{API_VERSION}/composite/sobjects"
               f"?ids={','.join(chunk)}&allOrNone=false")
        res, err = _rest("DELETE", url, token, None)
        if err:
            out.extend({"success": False, "id": cid, "error": err} for cid in chunk)
            continue
        for r in res:
            errs = r.get("errors") or []
            msg = "; ".join(e.get("message", "") for e in errs) if errs else None
            out.append({"success": bool(r.get("success")), "id": r.get("id"), "error": msg})
    return out


def _constraint_ids_in_model(org, model, ids):
    """Reconfirm ESCO ownership immediately before destructive deletion."""
    present = set()
    for start in range(0, len(ids), 200):
        values = ",".join(
            "'" + _soql_str(record_id) + "'"
            for record_id in ids[start:start + 200])
        records, err = _query_json(
            org,
            "SELECT Id FROM ExpressionSetConstraintObj "
            f"WHERE Id IN ({values}) AND "
            "ExpressionSet.ExpressionSetDefinition.DeveloperName = '"
            + _soql_str(model) + "'")
        if err:
            return None, err
        present.update(record.get("Id") for record in records)
    return present, None


def _archive_associations(org, model, key_field, rows):
    return _write_json_artifact(
        ARCHIVE_DIR, f"{org}__{model}__deleted-associations", {
            "kind": "association-delete-archive",
            "targetOrg": org, "model": model, "keyField": key_field,
            "rows": rows,
        })


def _restore_association_archive_unlocked(
        org, model, archive_id, confirm_target=None):
    """Restore absent ESCO rows from a tool-created deletion archive."""
    if confirm_target != org:
        return {"ok": False, "log": (
            f"Production safety check failed. Type the target org alias exactly: {org}")}
    archive, err = _read_json_artifact(ARCHIVE_DIR, archive_id)
    if err:
        return {"ok": False, "log": err}
    if (archive.get("kind") != "association-delete-archive"
            or archive.get("targetOrg") != org
            or archive.get("model") != model):
        return {"ok": False, "log": (
            "Association archive does not belong to the selected target org and model.")}
    key_field = archive.get("keyField") or DEFAULT_KEY_FIELD
    current = export_constraints(org, model, key_field)
    if not current.get("ok"):
        return current
    current_expression_set_id, err = _resolve_target_expression_set(org, model)
    if err:
        return {"ok": False, "log": (
            "Association restore stopped because the current target Expression "
            f"Set could not be resolved:\n{err}")}
    current_keys = {row.get("key") for row in current["rows"]}
    records, labels, skipped = [], [], []
    for row in archive.get("rows") or []:
        label = f"{row.get('tagType')} · {row.get('tag')} → {row.get('refName') or row.get('refId')}"
        if row.get("key") in current_keys:
            skipped.append({"success": True, "label": label,
                            "skipped": True, "error": None})
            continue
        if not row.get("refId"):
            skipped.append({"success": False, "label": label,
                            "error": "Archive row lacks its target reference Id."})
            continue
        records.append({
            "attributes": {"type": "ExpressionSetConstraintObj"},
            "ExpressionSetId": current_expression_set_id,
            "ReferenceObjectId": row["refId"],
            "ConstraintModelTag": row.get("tag"),
            "ConstraintModelTagType": row.get("tagType"),
        })
        labels.append(label)
    token, instance, err = _org_creds(org)
    if err:
        return {"ok": False, "log": err}
    restored = list(skipped)
    if records:
        for label, result in zip(labels, _collections_insert(token, instance, records)):
            restored.append({
                "success": result["success"], "label": label,
                "id": result.get("id"), "error": result.get("error"),
            })
    success_count = sum(1 for row in restored if row.get("success"))
    fail_count = len(restored) - success_count
    report, report_err = _try_deployment_report(
        "association-restore", org, model, {
            "success": fail_count == 0, "archiveId": archive_id,
            "results": restored,
        })
    return {
        "ok": fail_count == 0, "target": org, "model": model,
        "restored": restored, "report": report, "reportError": report_err,
        "stats": {"restoreOk": success_count, "restoreFail": fail_count},
        "log": (
            f"Association recovery finished: {success_count} restored/already "
            f"present, {fail_count} failed."),
    }


def restore_association_archive(org, model, archive_id, confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _restore_association_archive_unlocked(
            org, model, archive_id, confirm_target))


def _resolve_target_expression_set(target_org, model):
    """Find the target ExpressionSetId for a model. Prefer the one already used
    by existing constraint rows; fall back to the ExpressionSet for the model.
    Returns (expressionSetId, error)."""
    # 1) Reuse the ExpressionSet that existing target constraints point to.
    recs, err = _query_json(
        target_org,
        "SELECT ExpressionSetId FROM ExpressionSetConstraintObj "
        "WHERE ExpressionSet.ExpressionSetDefinition.DeveloperName = '"
        + _soql_str(model) + "'")
    if not err and recs:
        expression_set_ids = {
            r.get("ExpressionSetId") for r in recs if r.get("ExpressionSetId")}
        if len(expression_set_ids) == 1:
            return next(iter(expression_set_ids)), None
        if len(expression_set_ids) > 1:
            return None, (
                f"Existing associations for '{model}' point to "
                f"{len(expression_set_ids)} different Expression Sets. "
                "Resolve that ambiguity before deploying.")
    # 2) No existing rows — resolve the model's ExpressionSet directly.
    recs, err = _query_json(
        target_org,
        "SELECT Id FROM ExpressionSet WHERE ExpressionSetDefinition.DeveloperName = '"
        + _soql_str(model) + "'")
    if err:
        return None, err
    if not recs:
        return None, (f"No Expression Set named '{model}' exists in the target org. "
                      "Deploy and activate the CML there first.")
    if len(recs) > 1:
        return None, (f"The target org has {len(recs)} Expression Sets named '{model}'. "
                      "Cannot decide which to attach constraints to.")
    return recs[0]["Id"], None


def _deploy_constraints_unlocked(
        source_org, target_org, model, adds, deletes,
        key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    """Insert selected source-only constraints and delete selected target-only
    ones. Each item is handled individually so per-row results can be shown.

    adds:    [{sourceConstraintId}] (all other source data is reloaded server-side)
    deletes: [{id, refName, tag, tagType}]             (target record Ids)
    """
    if not target_org:
        return {"ok": False, "log": "No target org."}
    if confirm_target != target_org:
        return {"ok": False, "log": (
            "Production safety check failed. Type the target org alias exactly: "
            + target_org)}
    if not adds and not deletes:
        return {"ok": False, "log": "Nothing selected to deploy."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found."}
    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name.")}

    token, instance, err = _org_creds(target_org)
    if err:
        return {"ok": False, "log": err}

    created, delete_results = [], []
    comparison = compare_constraints(source_org, target_org, model, kf)
    if not comparison.get("ok"):
        return comparison
    cml_version, cml_err = _latest_version(target_org, model)
    if cml_err:
        return {"ok": False, "log": (
            "Deployment stopped because the target CML version could not be "
            f"resolved for backup:\n{cml_err}")}
    target_cml_before, cml_err = _version_cml_text(
        target_org, cml_version["Id"])
    if cml_err:
        return {"ok": False, "log": (
            "Deployment stopped because the target CML could not be backed up:\n"
            + cml_err)}
    try:
        cml_backup = _create_cml_backup(
            target_org, model, cml_version, target_cml_before,
            "before-association-deploy")
    except OSError as exc:
        return {"ok": False, "log": (
            "Deployment stopped because the target CML backup could not be saved:\n"
            + str(exc))}

    # ---- Inserts ----
    if adds:
        es_id, es_err = _resolve_target_expression_set(target_org, model)
        if es_err:
            return {"ok": False, "log": f"Cannot insert constraints: {es_err}"}

        # Re-run the authoritative read-only preflight. Browser payloads are
        # forgeable, and catalog state can change after the UI comparison.
        source_by_id = {
            r["id"]: r for r in comparison["sourceOnly"] if r.get("id")
        }
        selected = []
        seen_source_ids = set()
        for requested in adds:
            source_id = requested.get("sourceConstraintId")
            row = source_by_id.get(source_id)
            if not row:
                created.append({
                    "success": False,
                    "label": requested.get("refName") or source_id or "Unknown row",
                    "error": "The selected source association is no longer valid; recompare and retry.",
                })
                continue
            if source_id in seen_source_ids:
                continue
            seen_source_ids.add(source_id)
            label = (
                f'{row.get("tagType")} · {row.get("tag")} → '
                f'{row.get("refName") or row.get("gkey") or row.get("refId")}'
            )
            if row.get("deployStatus") != "ready":
                created.append({
                    "success": False, "label": label,
                    "error": row.get("blockNote") or (
                        "Catalog dependency preflight did not mark this "
                        "association as safe to deploy."),
                })
                continue
            selected.append(row)

        # Resolve non-PRC reference records in bulk by type + portable key.
        needed = {}
        for row in selected:
            if row["refType"] != "ProductRelatedComponent" and row.get("gkey"):
                needed.setdefault(row["refType"], set()).add(row["gkey"])
        ref_map = {}  # (type, key) -> [target Ids]
        for ref_type, keys in needed.items():
            keys = list(keys)
            for i in range(0, len(keys), 200):
                chunk = keys[i:i + 200]
                in_list = ",".join("'" + _soql_str(g) + "'" for g in chunk)
                recs, qerr = _query_json(
                    target_org,
                    f"SELECT Id, {kf} FROM {ref_type} "
                    f"WHERE {kf} IN ({in_list})")
                if qerr:
                    return {"ok": False, "backup": cml_backup, "log": (
                        f"Deployment stopped because target {ref_type} "
                        f"references could not be verified:\n{qerr}")}
                for r in recs:
                    ref_map.setdefault((ref_type, r.get(kf)), []).append(r["Id"])

        # Product relationships are catalog data. Resolve an existing canonical
        # target relationship, but never create or modify one.
        prc_details = _prc_details(
            source_org,
            [r.get("refId") for r in selected
             if r["refType"] == "ProductRelatedComponent"],
            kf)
        target_prcs = _target_prc_by_identity(
            target_org, list(prc_details.values()), kf)
        records, meta = [], []
        for row in selected:
            label = (
                f'{row.get("tagType")} · {row.get("tag")} → '
                f'{row.get("refName") or row.get("gkey") or row.get("refId")}'
            )
            if row["refType"] == "ProductRelatedComponent":
                detail = prc_details.get(row.get("refId")) or {}
                candidates = target_prcs.get(detail.get("identity"), [])
                if len(candidates) != 1:
                    created.append({
                        "success": False, "label": label,
                        "error": (
                            "Catalog relationship preflight changed; expected "
                            "exactly one existing target ProductRelatedComponent "
                            f"but found {len(candidates)}. No catalog data was changed."),
                    })
                    continue
                ref_id = candidates[0]
            else:
                candidates = ref_map.get((row["refType"], row.get("gkey")), [])
                if len(candidates) != 1:
                    created.append({
                        "success": False, "label": label,
                        "error": (
                            "Catalog reference preflight changed; expected exactly "
                            f"one target {row['refType']} with {kf} "
                            f"'{row.get('gkey')}' but found {len(candidates)}. "
                            "No catalog data was changed."),
                    })
                    continue
                ref_id = candidates[0]

            if not row.get("mappable"):
                created.append({"success": False, "label": label,
                                "error": f"Reference record has no portable {kf} mapping."})
                continue
            if not ref_id:
                created.append({"success": False, "label": label,
                                "error": f"Reference {row.get('refType')} with {kf} "
                                         f"'{row.get('gkey')}' not found in target."})
                continue
            records.append({
                "attributes": {"type": "ExpressionSetConstraintObj"},
                "ExpressionSetId": es_id,
                "ReferenceObjectId": ref_id,
                "ConstraintModelTag": row.get("tag"),
                "ConstraintModelTagType": row.get("tagType"),
            })
            meta.append(label)

        if records:
            res = _collections_insert(token, instance, records)
            for index, label in enumerate(meta):
                if index >= len(res):
                    created.append({
                        "success": False, "label": label, "id": None,
                        "error": "Salesforce returned no result for this row.",
                    })
                    continue
                result = res[index]
                created.append({
                    "success": result["success"], "label": label,
                    "id": result.get("id"), "error": result.get("error")})

    # ---- Deletes ----
    archive = None
    if deletes:
        # Deletion requests are untrusted browser input. Only rows that are
        # still target-only in a fresh authoritative comparison may be deleted.
        target_by_id = {
            row["id"]: row for row in comparison["targetOnly"]
            if row.get("id") and row.get("deployStatus") != "cml-difference"
        }
        ids, labels = [], {}
        archive_rows = []
        seen_delete_ids = set()
        for d in deletes:
            rid = d.get("id")
            row = target_by_id.get(rid)
            if (not rid or not str(rid).startswith("1JE") or not row
                    or rid in seen_delete_ids):
                delete_results.append({"success": False,
                                       "label": d.get("refName") or rid,
                                       "error": (
                                           "Deletion blocked: this Id is not a current, "
                                           "safe target-only association for the selected "
                                           "target org and model. Recompare and retry.")})
                continue
            seen_delete_ids.add(rid)
            ids.append(rid)
            archive_rows.append(row)
            labels[rid] = (
                f'{row.get("tagType")} · {row.get("tag")} → '
                f'{row.get("refName") or rid}')
        if ids:
            verified_ids, verify_err = _constraint_ids_in_model(
                target_org, model, ids)
            if verify_err:
                for rid in ids:
                    delete_results.append({
                        "success": False, "label": labels.get(rid, rid),
                        "id": rid, "error": (
                            "Deletion stopped because record ownership could not "
                            f"be reverified immediately before DML: {verify_err}"),
                    })
                ids = []
            elif verified_ids != set(ids):
                missing = set(ids) - verified_ids
                for rid in missing:
                    delete_results.append({
                        "success": False, "label": labels.get(rid, rid),
                        "id": rid, "error": (
                            "Deletion blocked because this association no longer "
                            "belongs to the selected target model."),
                    })
                ids = [rid for rid in ids if rid in verified_ids]
                archive_rows = [
                    row for row in archive_rows if row.get("id") in verified_ids]
        if ids:
            try:
                archive = _archive_associations(
                    target_org, model, kf, archive_rows)
            except OSError as exc:
                for rid in ids:
                    delete_results.append({
                        "success": False, "label": labels.get(rid, rid),
                        "id": rid, "error": (
                            "Deletion stopped because its recovery archive could "
                            f"not be saved: {exc}"),
                    })
            else:
                res = _collections_delete(token, instance, ids)
                for r in res:
                    delete_results.append({"success": r["success"],
                                           "label": labels.get(r.get("id"), r.get("id")),
                                           "id": r.get("id"), "error": r.get("error")})

    ins_ok = sum(1 for r in created if r["success"])
    del_ok = sum(1 for r in delete_results if r["success"])
    refresh = None
    changed = any(r.get("success") and r.get("id") for r in created)
    changed = changed or any(r.get("success") for r in delete_results)
    if changed:
        # Salesforce compiles/validates the ConstraintModel when its blob is
        # saved. Constraint associations are deployed after the CML, so the
        # version can otherwise retain a stale "has no type association" result
        # even though ExpressionSetConstraintObj now contains the row. Re-save
        # the exact target blob; do not use the catalog Sync action, which can
        # regenerate and shorten custom CML.
        if not (target_cml_before or "").strip():
            refresh = {
                "ok": False,
                "log": "Associations changed, but the target CML is empty; "
                       "validation was not refreshed.",
            }
        else:
            refresh = _refresh_cml_validation(
                target_org, model, target_cml_before, cml_version["Id"])
    insert_fail = len(created) - ins_ok
    delete_fail = len(delete_results) - del_ok
    succeeded = ins_ok + del_ok
    failed = insert_fail + delete_fail
    outcome = "partial" if succeeded and failed else (
        "failed" if failed and not succeeded else "success")
    report, report_err = _try_deployment_report(
        "association-deploy", target_org, model, {
            "success": failed == 0, "outcome": outcome,
            "sourceOrg": source_org, "keyField": kf,
            "requested": {
                "addSourceConstraintIds": [
                    row.get("sourceConstraintId") for row in adds],
                "deleteTargetConstraintIds": [row.get("id") for row in deletes],
            },
            "created": created, "deleted": delete_results,
            "cmlBackup": cml_backup, "deletionArchive": archive,
            "validationRefresh": refresh,
        })
    return {
        "ok": outcome != "failed", "processed": True,
        "model": model, "target": target_org,
        "created": created, "deleted": delete_results,
        "refresh": refresh, "archive": archive, "backup": cml_backup,
        "report": report, "reportError": report_err, "outcome": outcome,
        "stats": {
            "insertOk": ins_ok, "insertFail": insert_fail,
            "deleteOk": del_ok, "deleteFail": delete_fail,
        },
    }


def deploy_constraints(source_org, target_org, model, adds, deletes,
                       key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    return _run_with_deployment_lock(
        target_org, model, lambda: _deploy_constraints_unlocked(
            source_org, target_org, model, adds, deletes,
            key_field, confirm_target))


def _patch_cml_version(org, version_id, content):
    """PATCH one exact CML version. Backup/report policy belongs to callers."""
    token, instance, err = _org_creds(org)
    if err:
        return err
    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
           f"ExpressionSetDefinitionVersion/{version_id}")
    _, err = _rest("PATCH", url, token, {"ConstraintModel": b64})
    if err and _is_auth_error(err):
        token, instance, refresh_err = _org_creds(org, refresh=True)
        if refresh_err:
            return refresh_err
        url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
               f"ExpressionSetDefinitionVersion/{version_id}")
        _, err = _rest("PATCH", url, token, {"ConstraintModel": b64})
        if err and _is_auth_error(err):
            return _auth_help(org, err)
    return err


def _verify_cml_version(org, version_id, expected, attempts=4):
    """Re-fetch after PATCH, allowing briefly eventual Salesforce blob reads."""
    saved, err = None, None
    for attempt in range(attempts):
        saved, err = _version_cml_text(org, version_id)
        if not err and saved == expected:
            return True, saved, None
        if attempt + 1 < attempts:
            time.sleep(0.4 * (attempt + 1))
    return False, saved, err


def _try_deployment_report(action, org, model, details):
    try:
        return _deployment_report(action, org, model, details), None
    except OSError as exc:
        return None, f"Could not save deployment report: {exc}"


def _deploy_cml_unlocked(org, model, content, confirm_target=None):
    """Back up, deploy and byte-verify the latest CML version."""
    if not org or not model:
        return {"ok": False, "log": "Please choose an org and enter the CML API name."}
    if confirm_target != org:
        return {"ok": False, "log": (
            f"Production safety check failed. Type the target org alias exactly: {org}")}
    if not content or not content.strip():
        return {"ok": False, "log": "There is no CML content to deploy."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    rec, err = _latest_version(org, model)
    if err:
        return {"ok": False, "log": err}
    version_id = rec["Id"]
    current, read_err = _version_cml_text(org, version_id)
    if read_err:
        return {"ok": False, "log": (
            "Deployment stopped because the target CML could not be backed up:\n"
            + read_err)}
    try:
        backup = _create_cml_backup(
            org, model, rec, current, "before-cml-deploy")
    except OSError as exc:
        return {"ok": False, "log": (
            "Deployment stopped because the target backup could not be saved:\n"
            + str(exc))}

    perr = _patch_cml_version(org, version_id, content)
    if perr:
        report, report_err = _try_deployment_report(
            "cml-deploy", org, model, {
                "success": False, "versionId": version_id,
                "backup": backup, "requestedSha256": _sha256_text(content),
                "error": perr,
            })
        return {"ok": False, "backup": backup, "report": report,
                "reportError": report_err, "log": (
                    f"Deploy failed for '{model}' ({version_id}, status "
                    f"{rec.get('Status')}) in '{org}':\n{perr}")}

    verified, saved, verify_err = _verify_cml_version(
        org, version_id, content)
    automatic_rollback = None
    if not verified:
        rollback_err = _patch_cml_version(org, version_id, current)
        rollback_verified, rollback_saved, rollback_verify_err = (
            (False, None, rollback_err) if rollback_err
            else _verify_cml_version(org, version_id, current))
        automatic_rollback = {
            "attempted": True, "verified": rollback_verified,
            "error": rollback_verify_err,
            "restoredSha256": (
                _sha256_text(rollback_saved)
                if rollback_saved is not None else None),
        }
    report, report_err = _try_deployment_report(
        "cml-deploy", org, model, {
            "success": verified, "versionId": version_id,
            "versionNumber": rec.get("VersionNumber"),
            "versionStatus": rec.get("Status"),
            "backup": backup, "requestedSha256": _sha256_text(content),
            "savedSha256": _sha256_text(saved) if not verify_err else None,
            "verificationError": verify_err,
            "automaticRollback": automatic_rollback,
        })
    if not verified:
        reason = verify_err or "The saved CML does not exactly match the requested content."
        rollback_note = (
            "The previous CML was restored and verified automatically."
            if automatic_rollback.get("verified")
            else "Automatic rollback also failed; use the saved backup for recovery.")
        return {"ok": False, "backup": backup, "report": report,
                "automaticRollback": automatic_rollback,
                "reportError": report_err, "log": (
                    "Salesforce accepted the PATCH, but post-deploy verification "
                    f"failed.\n{reason}\n{rollback_note}")}
    lines = content.count("\n") + 1
    return {"ok": True, "backup": backup, "report": report,
            "reportError": report_err, "verified": True, "log": (
        f"SUCCESS — deployed CML to '{model}' ({version_id}) in '{org}'.\n"
        f"Version status: {rec.get('Status')} · {lines} lines.\n"
        f"Verified SHA-256: {_sha256_text(content)}")}


def deploy_cml(org, model, content, confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _deploy_cml_unlocked(
            org, model, content, confirm_target))


def _rollback_cml_unlocked(org, model, backup_id, confirm_target=None):
    if confirm_target != org:
        return {"ok": False, "log": (
            f"Production safety check failed. Type the target org alias exactly: {org}")}
    backup_data, err = _read_json_artifact(BACKUP_DIR, backup_id)
    if err:
        return {"ok": False, "log": err}
    if (backup_data.get("kind") != "cml-backup"
            or backup_data.get("org") != org
            or backup_data.get("model") != model):
        return {"ok": False, "log": (
            "Backup does not belong to the selected target org and model.")}
    content = backup_data.get("content", "")
    if _sha256_text(content) != backup_data.get("sha256"):
        return {"ok": False, "log": (
            "Rollback stopped because the backup integrity hash does not match "
            "its saved CML content.")}
    rec, err = _latest_version(org, model)
    if err:
        return {"ok": False, "log": err}
    if rec.get("Id") != backup_data.get("versionId"):
        return {"ok": False, "log": (
            "Rollback stopped because the latest model version has changed since "
            "this backup was created. Select a backup for the current version.")}
    current, err = _version_cml_text(org, rec["Id"])
    if err:
        return {"ok": False, "log": (
            "Rollback stopped because the current CML could not be backed up:\n" + err)}
    try:
        safety_backup = _create_cml_backup(
            org, model, rec, current, "before-cml-rollback")
    except OSError as exc:
        return {"ok": False, "log": (
            "Rollback stopped because its safety backup could not be saved:\n"
            + str(exc))}
    patch_err = _patch_cml_version(org, rec["Id"], content)
    if patch_err:
        verified, saved, verify_err = False, None, patch_err
    else:
        verified, saved, verify_err = _verify_cml_version(
            org, rec["Id"], content)
    report, report_err = _try_deployment_report(
        "cml-rollback", org, model, {
            "success": verified, "versionId": rec["Id"],
            "restoredBackupId": backup_id, "safetyBackup": safety_backup,
            "restoredSha256": _sha256_text(content),
            "savedSha256": _sha256_text(saved) if not verify_err else None,
            "error": verify_err,
        })
    if not verified:
        return {"ok": False, "backup": safety_backup, "report": report,
                "reportError": report_err,
                "log": "Rollback failed verification:\n" + (verify_err or "Content mismatch.")}
    return {"ok": True, "verified": True, "backup": safety_backup,
            "report": report, "reportError": report_err,
            "content": content, "log": (
                f"Rollback complete and verified for '{model}' in '{org}'.\n"
                f"Restored SHA-256: {_sha256_text(content)}")}


def rollback_cml(org, model, backup_id, confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _rollback_cml_unlocked(
            org, model, backup_id, confirm_target))


def _refresh_cml_validation(org, model, content, version_id=None):
    """Force Salesforce to recompile unchanged CML after associations change.

    Salesforce can optimize an identical ConstraintModel PATCH as a no-op. Save
    one temporary trailing blank line, then restore the byte-exact original so
    validation runs while the final CML remains unchanged.
    """
    if not version_id:
        rec, err = _latest_version(org, model)
        if err:
            return {"ok": False, "log": err}
        version_id = rec["Id"]
    staged_err = _patch_cml_version(org, version_id, content + "\n")
    if staged_err:
        return {
            "ok": False,
            "log": "Could not stage the CML validation refresh:\n"
                   + staged_err,
        }
    restore_err = _patch_cml_version(org, version_id, content)
    if restore_err:
        return {
            "ok": False,
            "log": "Salesforce recompiled the CML, but the original byte-exact "
                   "content could not be restored:\n"
                   + restore_err,
        }
    verified, _, verify_err = _verify_cml_version(
        org, version_id, content)
    if not verified:
        return {"ok": False, "log": (
            "CML validation refresh finished, but byte-exact verification failed:\n"
            + (verify_err or "Restored content does not match."))}
    return {
        "ok": True,
        "log": "Target CML was force-refreshed and restored unchanged so "
               "Salesforce can validate the new associations.",
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default request logging
        pass

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(data)

    def _trusted_host(self):
        host = (self.headers.get("Host") or "").lower()
        hostname = host.rsplit(":", 1)[0].strip("[]")
        return hostname in ("127.0.0.1", "localhost", "::1")

    def _trusted_origin(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            hostname = urllib.parse.urlparse(origin).hostname
        except ValueError:
            return False
        return hostname in ("127.0.0.1", "localhost", "::1")

    def do_GET(self):
        try:
            if not self._trusted_host():
                self._send(403, {"ok": False, "log": "Untrusted Host header."})
                return
            if self.path == "/" or self.path.startswith("/?"):
                self._send(
                    200, PAGE.replace("__CML_CSRF_TOKEN__", CSRF_TOKEN),
                    "text/html; charset=utf-8")
            elif self.path == "/api/ping":
                self._send(200, {
                    "app": APP_ID, "build": BUILD,
                    "localRequestToken": CSRF_TOKEN})
            elif self.path == "/api/orgs":
                self._send(200, list_orgs())
            elif self.path == "/api/debug":
                self._send(200, sf_debug_info())
            elif self.path.startswith("/api/models"):
                qs = urllib.parse.urlparse(self.path).query
                org = urllib.parse.parse_qs(qs).get("org", [""])[0]
                self._send(200, list_models(org))
            elif self.path.startswith("/api/backups"):
                qs = urllib.parse.parse_qs(
                    urllib.parse.urlparse(self.path).query)
                self._send(200, list_cml_backups(
                    qs.get("org", [""])[0], qs.get("model", [""])[0]))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(200, {"ok": False, "log": f"Unexpected server error: {exc}"})

    def do_POST(self):
        try:
            if not self._trusted_host():
                self._send(403, {"ok": False, "log": "Untrusted Host header."})
                return
            if not self._trusted_origin():
                self._send(403, {"ok": False, "log": "Untrusted Origin header."})
                return
            if self.headers.get("X-CML-CSRF") != CSRF_TOKEN:
                self._send(403, {"ok": False, "log": (
                    "Request rejected by local security protection. Reload the tool.")})
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
            except (TypeError, ValueError):
                self._send(400, {"ok": False, "log": "Invalid Content-Length."})
                return
            if length < 0:
                self._send(400, {"ok": False, "log": "Invalid Content-Length."})
                return
            if length > 10 * 1024 * 1024:
                self._send(413, {"ok": False, "log": "Request is too large."})
                return
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(200, {"ok": False, "log": "Invalid request body."})
                return

            if self.path == "/api/fetch":
                self._send(200, fetch_cml(body.get("org"), body.get("model")))
            elif self.path == "/api/quit":
                self._send(200, {"ok": True, "bye": True})
                threading.Thread(
                    target=lambda: (time.sleep(0.3), self.server.shutdown()),
                    daemon=True).start()
            elif self.path == "/api/deploy":
                self._send(200, deploy_cml(
                    body.get("org"), body.get("model"), body.get("content"),
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/rollback":
                self._send(200, rollback_cml(
                    body.get("org"), body.get("model"), body.get("backupId"),
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/compare":
                self._send(200, compare_cml(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model")
                ))
            elif self.path == "/api/data":
                self._send(200, export_constraints(
                    body.get("org"), body.get("model"),
                    body.get("keyField") or DEFAULT_KEY_FIELD
                ))
            elif self.path == "/api/data/compare":
                self._send(200, compare_constraints(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model"),
                    body.get("keyField") or DEFAULT_KEY_FIELD
                ))
            elif self.path == "/api/data/deploy":
                self._send(200, deploy_constraints(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model"),
                    body.get("adds") or [], body.get("deletes") or [],
                    body.get("keyField") or DEFAULT_KEY_FIELD,
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/data/restore":
                self._send(200, restore_association_archive(
                    body.get("targetOrg"), body.get("model"),
                    body.get("archiveId"), body.get("confirmTarget")
                ))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(200, {"ok": False, "log": f"Unexpected server error: {exc}"})


# A stable, preferred port so the URL stays consistent between launches. This
# avoids "Failed to fetch" errors caused by old browser tabs pointing at a dead
# random port. Override with the CML_UI_PORT environment variable.
DEFAULT_PORT = int(os.environ.get("CML_UI_PORT", "8787"))
APP_ID = "cml-tool"  # marker so we can tell our own server apart from others


def _build_id():
    """Short hash of this file so the launcher can detect code changes."""
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return "dev"


BUILD = _build_id()


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_our_server(port):
    """Return True only if a *current* CML Tool is already serving this port."""
    return _server_build(port) is not None


def _server_build(port):
    """Build hash of a CML Tool already on this port, or None if it isn't ours."""
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/ping", timeout=2
        ) as resp:
            info = json.loads(resp.read().decode("utf-8"))
            return info.get("build") if info.get("app") == APP_ID else None
    except Exception:  # noqa: BLE001
        return None


def _quit_running(port):
    """Ask a running CML Tool to exit, then wait for the port to free up."""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ping", timeout=3) as response:
            token = json.loads(response.read().decode("utf-8")).get(
                "localRequestToken")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/quit",
            data=b"{}", method="POST",
            headers={
                "Content-Type": "application/json",
                "X-CML-CSRF": token or "",
            })
        urllib.request.urlopen(request, timeout=3).read()
    except Exception:  # noqa: BLE001
        pass
    for _ in range(40):  # up to ~10s
        if not port_in_use(port):
            return True
        time.sleep(0.25)
    return not port_in_use(port)




PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CML Tool — Fetch, Deploy &amp; Compare</title>
<script>(function(){try{var t=localStorage.getItem('cml-theme')||'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>
  :root {
    color-scheme: light;
    --bg:#f7f8fc; --panel:#ffffff; --gutter:#f0f3fa; --input-bg:#fbfcff;
    --line:#dce2ef; --text:#172033; --muted:#667085; --gutter-text:#8490a6;
    --accent:#3b82f6; --accent-strong:#06b6d4; --green:#22c55e; --red:#ef4444;
    --purple:#8b5cf6; --amber:#f59e0b; --teal:#06b6d4; --on-accent:#ffffff;
    --radius:18px;
    --ok-bg:color-mix(in srgb,var(--green) 11%,var(--panel)); --ok-text:#08734f;
    --err-bg:color-mix(in srgb,var(--red) 10%,var(--panel)); --err-text:#b4233f;
    --info-bg:color-mix(in srgb,var(--accent) 9%,var(--panel)); --info-text:#3f40bd;
    --teal-bg:color-mix(in srgb,var(--teal) 10%,var(--panel)); --teal-text:#07657c;
    --chg-bg:color-mix(in srgb,var(--purple) 14%,var(--panel));
    --del-bg:color-mix(in srgb,var(--red) 12%,var(--panel));
    --ins-bg:color-mix(in srgb,var(--teal) 13%,var(--panel));
    --chg-line:var(--purple); --del-line:var(--red); --ins-line:var(--teal);
    --shadow:0 16px 44px rgba(29,39,70,.08);
  }
  html[data-theme="dark"] {
    color-scheme: dark;
    --bg:#090e1a; --panel:#11182a; --gutter:#171f34; --input-bg:#0c1323;
    --line:#303b57; --text:#f4f7ff; --muted:#b5bfd3; --gutter-text:#7f8ba5;
    --accent:#60a5fa; --accent-strong:#22d3ee; --green:#4ade80; --red:#f87171;
    --purple:#a78bfa; --amber:#fbbf24; --teal:#22d3ee;
    --ok-bg:color-mix(in srgb,var(--green) 13%,var(--panel)); --ok-text:#a7f3d0;
    --err-bg:color-mix(in srgb,var(--red) 13%,var(--panel)); --err-text:#fecdd3;
    --info-bg:color-mix(in srgb,var(--accent) 13%,var(--panel)); --info-text:#d9dcff;
    --teal-bg:color-mix(in srgb,var(--teal) 12%,var(--panel)); --teal-text:#a5f3fc;
    --shadow:0 20px 60px rgba(0,0,0,.30);
  }
  * { box-sizing: border-box; }
  html,body { max-width:100%; overflow-x:hidden; }
  body {
    margin:0; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    min-height:100vh;
    background:
      radial-gradient(circle at 8% 0%,color-mix(in srgb,var(--accent) 8%,transparent),transparent 28rem),
      radial-gradient(circle at 92% 5%,color-mix(in srgb,var(--teal) 7%,transparent),transparent 30rem),
      var(--bg);
    color:var(--text); line-height:1.5;
    transition:background-color .2s ease,color .2s ease;
  }
  button,input,select,textarea { font:inherit; }
  [hidden] { display:none !important; }

  /* ── App shell ────────────────────────────────────────────────── */
  .app-shell { min-height:100vh; display:grid; grid-template-columns:244px minmax(0,1fr); }
  .sidebar { position:sticky; top:0; height:100vh; display:flex; flex-direction:column;
    padding:22px 14px 16px; background:color-mix(in srgb,var(--panel) 92%,var(--bg));
    border-right:1px solid var(--line); z-index:20; overflow-y:auto; }
  .brand { display:flex; align-items:center; gap:11px; padding:0 8px 26px; color:var(--text); text-decoration:none; }
  .brand-mark { width:36px; height:36px; flex:0 0 36px; display:grid; place-items:center; border-radius:12px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    box-shadow:0 8px 22px color-mix(in srgb,var(--accent) 24%,transparent); }
  .brand-mark svg { width:22px; fill:var(--on-accent); }
  .brand strong,.brand small { display:block; line-height:1.2; }
  .brand strong { font-size:13px; }
  .brand small { margin-top:3px; color:var(--muted); font-size:11px; font-weight:600; }
  .side-label { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em;
    text-transform:uppercase; padding:0 12px 8px; }
  .side-menu { display:grid; min-width:0; gap:5px; }
  .side-nav { width:100%; border:0; display:flex; align-items:center; gap:10px; padding:10px 12px;
    border-radius:12px; background:transparent; color:var(--muted); font-size:13px; font-weight:650;
    text-align:left; cursor:pointer; transition:background .2s,color .2s,transform .2s; }
  .side-nav:hover { color:var(--text); background:var(--gutter); transform:translateX(2px); }
  .side-nav.active { color:var(--accent); background:color-mix(in srgb,var(--accent) 11%,var(--panel));
    box-shadow:inset 3px 0 0 var(--accent); }
  .nav-icon { width:21px; height:21px; display:grid; place-items:center; flex:0 0 21px; }
  .nav-icon svg { width:17px; height:17px; fill:none; stroke:currentColor; stroke-width:1.8;
    stroke-linecap:round; stroke-linejoin:round; }
  .sidebar-footer { margin-top:auto; border-top:1px solid var(--line); padding-top:12px; }
  .about-link { width:100%; border:0; display:flex; align-items:center; gap:10px; padding:10px 12px;
    border-radius:12px; background:transparent; color:var(--muted); text-decoration:none; font-size:13px;
    font-weight:650; cursor:pointer; transition:background .2s,color .2s,transform .2s; }
  .about-link:hover { color:var(--text); background:var(--gutter); transform:translateX(2px); }
  .sidebar .credit { padding:10px 12px 0; margin:0; font-size:10px; line-height:1.5; color:var(--muted); }

  /* ── Main area ────────────────────────────────────────────────── */
  .app-main { min-width:0; display:flex; flex-direction:column; }
  .topbar { display:flex; align-items:center; justify-content:space-between; gap:20px;
    padding:22px clamp(14px,2.2vw,36px) 18px; position:relative; overflow:hidden; min-height:100px; }
  .topbar::after { content:""; position:absolute; right:-80px; top:-130px; width:420px; height:260px;
    pointer-events:none; background:radial-gradient(circle,color-mix(in srgb,var(--teal) 18%,transparent),transparent 68%); }
  .topbar > * { position:relative; z-index:1; }
  .eyebrow { color:var(--muted); font-size:10px; font-weight:800; letter-spacing:.12em; text-transform:uppercase; margin-bottom:4px; }
  h1 { font-size:clamp(22px,2vw,30px); letter-spacing:-.03em; margin:0 0 3px; }
  .sub { color:var(--muted); font-size:13px; margin:0; }
  .top-actions { display:flex; align-items:center; gap:10px; flex-shrink:0; }
  .local-badge { display:inline-flex; align-items:center; gap:7px; padding:8px 11px;
    border:1px solid var(--line); border-radius:12px;
    background:color-mix(in srgb,var(--panel) 88%,transparent); color:var(--muted); font-size:11px; font-weight:700; }
  .live-dot { width:7px; height:7px; border-radius:50%; background:var(--green);
    box-shadow:0 0 0 4px color-mix(in srgb,var(--green) 14%,transparent); }
  .wrap { padding:0 clamp(14px,2.2vw,36px) 64px; }

  /* ── Tabs ─────────────────────────────────────────────────────── */
  .tabs { display:inline-flex; max-width:100%; gap:5px; background:var(--gutter); border:1px solid var(--line);
    border-radius:14px; padding:5px; margin-bottom:18px; flex-wrap:wrap; }
  .tab { border:none; background:transparent; color:var(--muted); font-weight:600; font-size:13px;
    padding:8px 16px; border-radius:10px; cursor:pointer; transition:background .2s,color .2s; }
  .tab:hover { background:color-mix(in srgb,var(--accent) 10%,transparent); color:var(--text); }
  .tab.active { background:var(--accent); color:var(--on-accent);
    box-shadow:0 6px 18px color-mix(in srgb,var(--accent) 28%,transparent); }

  /* ── Panels ───────────────────────────────────────────────────── */
  .view-panel { display:none; }
  .view-panel.active { display:block; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:var(--radius);
    padding:clamp(14px,1.5vw,24px); box-shadow:var(--shadow); margin-bottom:18px; }
  .card-head { display:flex; align-items:flex-start; justify-content:space-between; gap:14px;
    padding-bottom:16px; margin-bottom:18px; border-bottom:1px solid var(--line); }
  .card-title { display:flex; align-items:flex-start; gap:11px; min-width:0; }
  .step-dot { width:27px; height:27px; flex:0 0 27px; display:grid; place-items:center; border-radius:9px;
    background:linear-gradient(135deg,var(--accent),var(--accent-strong)); color:var(--on-accent);
    font-size:12px; font-weight:800; box-shadow:0 7px 16px color-mix(in srgb,var(--accent) 22%,transparent); }
  .card-title h2 { margin:0; font-size:15px; letter-spacing:-.01em; }
  .card-title p { margin:3px 0 0; color:var(--muted); font-size:12px; }

  /* ── Connection strip ─────────────────────────────────────────── */
  .conn-strip { display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:14px; align-items:end; }
  .field { min-width:0; }
  label { display:block; font-size:11px; color:var(--muted); margin-bottom:5px;
    text-transform:uppercase; letter-spacing:.05em; font-weight:700; }
  select,input { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:12px; padding:9px 13px; font-size:13px; outline:none;
    transition:border-color .16s,box-shadow .16s; }
  select:focus,input:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }
  textarea { width:100%; background:var(--input-bg); color:var(--text); border:1px solid var(--line);
    border-radius:14px; padding:10px 13px; font-size:12.5px; outline:none;
    font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,Consolas,monospace;
    min-height:320px; resize:vertical; white-space:pre; tab-size:2;
    transition:border-color .16s,box-shadow .16s; }
  textarea:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 16%,transparent); }

  /* combo / model picker */
  .combo { display:flex; flex-direction:column; gap:6px; }
  select[size] { padding:0; height:auto; border-radius:12px; }
  select[size] option { padding:7px 12px; border-bottom:1px solid var(--line); }
  select[size] option:checked { background:var(--accent); color:#fff; }
  .combo-selected { display:flex; align-items:center; gap:10px; }
  .selchip { flex:1; display:inline-flex; align-items:center; gap:8px; padding:9px 13px;
    border-radius:12px; background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    color:#fff; font-weight:700; font-size:13px; min-width:0; }
  .selchip .name { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .selchip::before { content:"✓"; font-weight:700; flex:none; }
  .meta { color:var(--muted); font-size:11px; }

  /* ── Buttons ──────────────────────────────────────────────────── */
  button { font-family:inherit; }
  .btn-row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; margin-top:14px; }
  .btn { border:none; border-radius:12px; padding:9px 20px; font-size:13px; font-weight:700;
    cursor:pointer; transition:transform .14s,filter .14s,box-shadow .14s;
    width:auto; white-space:nowrap; }
  .btn:disabled { opacity:.5; cursor:not-allowed; }
  .btn:hover:not(:disabled) { transform:translateY(-1px); filter:brightness(1.08); }
  .btn:active:not(:disabled) { transform:translateY(1px) scale(.97); filter:brightness(.92); }
  .btn-primary { background:linear-gradient(135deg,var(--accent),var(--accent-strong)); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--accent) 28%,transparent); }
  .btn-green { background:linear-gradient(135deg,var(--green),color-mix(in srgb,var(--green) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--green) 22%,transparent); }
  .btn-purple { background:linear-gradient(135deg,var(--purple),color-mix(in srgb,var(--purple) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--purple) 22%,transparent); }
  .ghost { background:var(--panel); border:1px solid var(--line); color:var(--text);
    font-weight:650; border-radius:10px; padding:8px 14px; font-size:12px; cursor:pointer;
    transition:transform .14s,background .14s,border-color .14s,color .14s;
    width:auto; white-space:nowrap; }
  .ghost:hover { background:color-mix(in srgb,var(--accent) 9%,var(--panel)); border-color:var(--accent); color:var(--accent); }
  .ghost:active { transform:scale(.96); }
  button:focus-visible { outline:3px solid color-mix(in srgb,var(--accent) 35%,transparent); outline-offset:3px; }
  .linklike { background:none; border:none; color:var(--accent); font-weight:600; cursor:pointer;
    padding:4px 6px; font-size:12px; border-radius:6px; }
  .linklike:hover { background:color-mix(in srgb,var(--accent) 10%,transparent); }
  .linklike:disabled { opacity:.45; cursor:not-allowed; background:none; }

  /* deploy group inline widget */
  .deploy-group { display:inline-flex; align-items:center; gap:8px; padding:4px 4px 4px 12px;
    border:1px solid var(--line); border-radius:12px; background:var(--gutter); }
  .deploy-group label { margin:0; text-transform:none; letter-spacing:0; font-size:12px; white-space:nowrap; }
  .deploy-group select { width:auto; min-width:140px; padding:7px 10px; border-radius:9px; }

  /* ── Status / conn ────────────────────────────────────────────── */
  .conn { display:none; margin:0 0 16px; padding:11px 16px; border-radius:12px; font-size:13px;
    background:var(--err-bg); border:1px solid var(--red); color:var(--err-text); }
  .conn.show { display:flex; align-items:center; gap:8px; }
  .status { margin-top:16px; font-size:13px; padding:13px 16px; border-radius:14px; display:none;
    white-space:pre-wrap; font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,monospace; }
  .status.show { display:block; }
  .status.ok { background:var(--ok-bg); border:1px solid var(--green); color:var(--ok-text); }
  .status.err { background:var(--err-bg); border:1px solid var(--red); color:var(--err-text); }
  .status.info { background:var(--info-bg); border:1px solid var(--accent); color:var(--info-text); }
  .spinner { display:inline-block; width:13px; height:13px; border:2px solid rgba(128,128,128,.35);
    border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite; vertical-align:-2px; margin-right:6px; }
  @keyframes spin { to { transform:rotate(360deg); } }

  /* ── Editor toolbar ───────────────────────────────────────────── */
  .editor-wrap { border:1px solid var(--line); border-radius:16px; overflow:hidden;
    transition:border-color .16s,box-shadow .16s; }
  .editor-wrap:focus-within { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 12%,transparent); }
  .editor-head { display:flex; align-items:center; justify-content:space-between; gap:8px;
    padding:9px 13px; border-bottom:1px solid var(--line); background:var(--gutter); }
  .editor-head .ttl { font-size:11px; font-weight:700; letter-spacing:.05em; text-transform:uppercase; color:var(--muted); }
  .editor-head .mini { display:flex; gap:6px; }
  .editor-wrap textarea { border:none; border-radius:0; min-height:320px; }
  .editor-wrap textarea:focus { border:none; box-shadow:none; }

  /* ── Diff view ────────────────────────────────────────────────── */
  .diff { margin-top:22px; display:none; }
  .diff.show { display:block; }
  .diff-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .summary { font-size:13px; font-weight:600; }
  .legend { font-size:12px; color:var(--muted); display:flex; gap:14px; flex-wrap:wrap; align-items:center; }
  .legend span { display:inline-flex; align-items:center; }
  .legend i { width:14px; height:14px; border-radius:4px; margin-right:6px; display:inline-flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; color:var(--text); }
  .lg-chg { background:var(--chg-bg); border:1px solid var(--chg-line); }
  .lg-del { background:var(--del-bg); border:1px solid var(--del-line); }
  .lg-ins { background:var(--ins-bg); border:1px solid var(--ins-line); }
  .diff-panes { display:flex; gap:12px; align-items:stretch; }
  .pane { flex:1; min-width:0; border:1px solid var(--line); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; }
  .pane-title { padding:8px 12px; font-size:12px; font-weight:600; color:var(--muted); border-bottom:1px solid var(--line); background:var(--gutter); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .pane-scroll { overflow:auto; max-height:600px; }
  table.pane-table { border-collapse:collapse; width:100%; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12.5px; }
  .pane-table td { padding:0 8px; vertical-align:top; white-space:pre; }
  .gutter { text-align:right; color:var(--gutter-text); background:var(--gutter); user-select:none; width:1%; white-space:nowrap; border-right:1px solid var(--line); position:sticky; left:0; }
  .code { width:100%; border-left:3px solid transparent; }
  .mk { user-select:none; display:inline-block; width:1ch; margin-right:7px; color:var(--muted); font-weight:700; }
  .row-chg .code { background:var(--chg-bg); border-left-color:var(--chg-line); }
  .row-del .code { background:var(--del-bg); border-left-color:var(--del-line); }
  .row-ins .code { background:var(--ins-bg); border-left-color:var(--ins-line); }
  .row-filler td { background:repeating-linear-gradient(45deg,transparent,transparent 6px,rgba(128,128,128,.06) 6px,rgba(128,128,128,.06) 12px); }
  .moved { color:var(--accent); font-style:italic; }
  .diff-panes.hide-eq tr.eqrow { display:none; }
  .diff-opts { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .diff-opts input { width:auto; }

  /* ── Semantic diff ────────────────────────────────────────────── */
  .sem-diff { display:none; margin-top:12px; }
  .sem-diff.show { display:block; }
  .sem-sec { margin-bottom:14px; }
  .sem-sec h4 { margin:0 0 6px; font-size:13px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
  .sem-block { border:1px solid var(--line); border-radius:12px; padding:8px 12px; margin-bottom:6px; font-size:13px; }
  .sem-block .nm { font-weight:700; }
  .sem-block .knd { font-size:11px; color:var(--muted); }
  .sem-mem { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12px; padding:3px 8px; border-radius:5px; margin:3px 0; white-space:pre-wrap; }
  .sem-mem.add { background:var(--ins-bg); color:var(--ins-line); }
  .sem-mem.del { background:var(--del-bg); color:var(--del-line); }
  .sem-mem.chg { background:var(--chg-bg); color:var(--chg-line); }
  .sem-mem .lab { font-weight:700; margin-right:6px; }
  .sem-ok { padding:13px 16px; border-radius:12px; background:var(--ok-bg); color:var(--ok-text); font-size:13px; }
  .sem-moved { font-size:12px; color:var(--muted); margin-top:6px; }

  /* ── Lint / best-practices ────────────────────────────────────── */
  .lint { display:none; margin-top:16px; }
  .lint.show { display:block; }
  .lint-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .lint-head h4 { margin:0; font-size:15px; font-weight:700; }
  .lint-score { font-size:13px; font-weight:700; padding:5px 14px; border-radius:999px; }
  .lint-score.good { background:var(--ok-bg); color:var(--ok-text); }
  .lint-score.mid { background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--amber); }
  .lint-score.bad { background:var(--err-bg); color:var(--err-text); }
  .lint-counts { font-size:12px; color:var(--muted); display:flex; gap:10px; flex-wrap:wrap; }
  .lint-caption { font-size:12px; color:var(--muted); margin:8px 0 12px; line-height:1.5; }
  .lint-item { border:1px solid var(--line); border-left-width:4px; border-radius:12px; padding:10px 14px; margin-bottom:8px; font-size:13px; }
  .lint-item .rmeta { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin-bottom:3px; }
  .lint-item .msg { color:var(--text); }
  .lint-item .fix { color:var(--muted); font-size:12px; margin-top:4px; }
  .lint-item.error { border-left-color:var(--red); }
  .lint-item.warn { border-left-color:var(--amber); }
  .lint-item.info { border-left-color:var(--accent); }
  .lint-line { font-family:"JetBrains Mono","SF Mono",Menlo,monospace; color:var(--accent); cursor:pointer; font-weight:700; }
  .lint-empty { padding:14px 16px; border-radius:12px; background:var(--ok-bg); color:var(--ok-text); font-size:13px; }
  .lint-fix { margin-top:8px; }
  .lint-fix .fixhead { font-size:11px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; margin:8px 0 3px; display:flex; align-items:center; gap:8px; }
  .lint-code { font-family:"JetBrains Mono","SF Mono",Menlo,monospace; font-size:12px; white-space:pre-wrap; word-break:break-word; padding:8px 12px; border-radius:8px; border:1px solid var(--line); }
  .lint-code.before { background:var(--del-bg); color:var(--del-line); }
  .lint-code.after { background:var(--ins-bg); color:var(--ins-line); }
  .lint-copy { font-size:11px; padding:2px 8px; }

  /* ── Constraint data ──────────────────────────────────────────── */
  .chips { display:flex; gap:8px; flex-wrap:wrap; }
  .chip { font-size:12px; font-weight:600; padding:4px 12px; border-radius:999px; border:1px solid var(--line); color:var(--muted); }
  .chip.ok { background:var(--ok-bg); color:var(--ok-text); border-color:var(--green); }
  .chip.add { background:var(--ins-bg); color:var(--ins-line); border-color:var(--ins-line); }
  .chip.extra { background:var(--del-bg); color:var(--del-line); border-color:var(--del-line); }
  .chip.warn { background:var(--err-bg); color:var(--err-text); border-color:var(--red); }
  .data { margin-top:14px; display:none; }
  .data.show { display:block; }
  .data-head { display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
  .data-filter { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .data-filter select { width:auto; padding:6px 10px; border-radius:9px; }
  .table-scroll { overflow:auto; max-height:560px; border:1px solid var(--line); border-radius:14px; }
  table.data-table { border-collapse:collapse; width:100%; font-size:12.5px; table-layout:auto; }
  .data-table th,.data-table td { padding:8px 12px; text-align:left; border-bottom:1px solid var(--line); vertical-align:top; word-break:break-word; }
  .data-table th { position:sticky; top:0; background:var(--gutter); color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; z-index:1; white-space:nowrap; }
  .data-table tbody tr:hover { background:var(--gutter); }
  /* narrow columns — short content, no wrap needed */
  .data-table td.col-sel,.data-table th.col-sel { width:32px; text-align:center; white-space:nowrap; }
  .data-table td.col-reftype,.data-table th.col-reftype { width:110px; white-space:nowrap; }
  .data-table td.col-tagtype,.data-table th.col-tagtype { width:80px; white-space:nowrap; }
  /* wide columns — allow wrap so full value is always visible */
  .data-table td.col-status,.data-table th.col-status { min-width:160px; }
  .data-table td.col-tag,.data-table th.col-tag { min-width:120px; }
  .data-table td.col-ref,.data-table th.col-ref { min-width:180px; }
  .data-table td.col-key,.data-table th.col-key { min-width:140px; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table .gkey { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:11px; color:var(--muted); word-break:break-all; }
  .data-table td.col-sel input[type=checkbox] { width:auto; cursor:pointer; accent-color:var(--accent); }
  .badge { display:inline-block; font-size:11px; font-weight:700; padding:2px 8px; border-radius:6px; }
  .b-match { background:var(--ok-bg); color:var(--ok-text); }
  .b-add { background:var(--ins-bg); color:var(--ins-line); }
  .b-extra { background:var(--del-bg); color:var(--del-line); }
  .b-blocked,.b-unmappable { background:var(--err-bg); color:var(--err-text); }
  .b-type { background:var(--info-bg); color:var(--info-text); }
  .b-dup { background:color-mix(in srgb,var(--amber) 18%,var(--panel)); color:var(--amber); border:1px solid var(--amber); margin-left:6px; }
  .block-note { display:block; margin-top:4px; font-size:11px; color:var(--muted); font-style:italic; white-space:normal; }
  .deploy-bar { display:none; margin-top:14px; padding:13px 16px; border-radius:14px;
    background:var(--info-bg); border:1px solid var(--accent); align-items:center;
    justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .deploy-bar.show { display:flex; }
  .deploy-bar .sel-summary { font-size:13px; color:var(--text); }
  .deploy-bar .sel-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
  .warn-note { color:var(--err-text); font-size:12px; }
  .results { display:none; margin-top:16px; }
  .results.show { display:block; }
  .results h4 { margin:0 0 8px; font-size:14px; }
  .result-row { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; font-size:12px;
    padding:7px 12px; border-radius:8px; margin-bottom:5px; display:flex; gap:8px; }
  .result-row.good { background:var(--ok-bg); color:var(--ok-text); }
  .result-row.bad { background:var(--err-bg); color:var(--err-text); }
  .result-row .ico { font-weight:700; }

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width:1050px) {
    .app-shell { display:block; }
    .sidebar { position:sticky; top:0; height:auto; padding:9px 12px; flex-direction:row;
      align-items:center; gap:12px; border-right:0; border-bottom:1px solid var(--line); }
    .brand { padding:0; min-width:max-content; }
    .brand-mark { width:30px; height:30px; }
    .brand small,.side-label,.sidebar-footer { display:none; }
    .side-menu { display:flex; flex:1; gap:4px; overflow-x:auto; scrollbar-width:none; }
    .side-menu::-webkit-scrollbar { display:none; }
    .side-nav { width:auto; min-width:max-content; padding:7px 10px; }
    .side-nav:hover { transform:none; }
    .side-nav.active { box-shadow:inset 0 -2px 0 var(--accent); }
    .topbar { min-height:80px; }
    .conn-strip { grid-template-columns:1fr 1fr; }
  }
  @media (max-width:700px) {
    .topbar { flex-direction:column; align-items:flex-start; gap:8px; }
    .top-actions { width:100%; justify-content:space-between; }
    .conn-strip { grid-template-columns:1fr; }
    .diff-panes { flex-direction:column; }
    .tabs { width:100%; }
    .tab { flex:1; }
    .deploy-group { flex-wrap:wrap; }
  }
</style>
</head>
<body>
<div class="app-shell">

  <!-- ═══════════ SIDEBAR ═══════════ -->
  <aside class="sidebar" aria-label="Primary navigation">
    <a class="brand" href="#" onclick="return false;">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z"/></svg>
      </span>
      <span><strong>Salesforce</strong><small>CML Tool</small></span>
    </a>
    <div class="side-label">Tools</div>
    <nav class="side-menu" id="sideNav">
      <button class="side-nav active" data-view="fetch">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></span>
        <span>Fetch &amp; Deploy</span>
      </button>
      <button class="side-nav" data-view="compare">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg></span>
        <span>Compare</span>
      </button>
      <button class="side-nav" data-view="lint">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M9 11l3 3L22 4M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg></span>
        <span>Best Practices</span>
      </button>
      <button class="side-nav" data-view="data">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg></span>
        <span>Constraint Data</span>
      </button>
    </nav>
    <div class="sidebar-footer">
      <a class="about-link" href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/></svg></span>
        <span>About</span>
      </a>
      <p class="credit">Made with 💙 by <strong>Mritunjaya Pancholi</strong></p>
    </div>
  </aside>

  <!-- ═══════════ MAIN ═══════════ -->
  <main class="app-main">
    <header class="topbar">
      <div>
        <div class="eyebrow">Developer tools</div>
        <h1 id="pageTitle">Fetch &amp; Deploy</h1>
        <p class="sub" id="pageSubtitle">Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org.</p>
      </div>
      <div class="top-actions">
        <span class="local-badge"><span class="live-dot"></span>Runs locally</span>
        <span id="appver" style="font-size:11px;color:var(--muted);font-family:'JetBrains Mono',ui-monospace,monospace;opacity:.8;white-space:nowrap;" title="Running build"></span>
        <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
      </div>
    </header>

    <div class="wrap">
      <!-- connection error banner -->
      <div class="conn" id="conn"></div>

      <!-- ── Tabs (synced with sidebar) ── -->
      <div class="tabs" id="tabRow" role="tablist">
        <button class="tab active" data-view="fetch">Fetch &amp; Deploy</button>
        <button class="tab" data-view="compare">Compare</button>
        <button class="tab" data-view="lint">Best Practices</button>
        <button class="tab" data-view="data">Constraint Data</button>
      </div>

      <!-- ═══ CONNECTION STRIP (shared across all views, always visible) ═══ -->
      <div class="card">
        <div class="conn-strip">
          <div class="field">
            <label for="org">Source org</label>
            <select id="org"><option>Loading orgs…</option></select>
          </div>
          <div class="field">
            <label for="targetOrg">Target org (compare-with)</label>
            <select id="targetOrg"><option>Loading orgs…</option></select>
          </div>
          <div class="field">
            <label for="model">CML <span id="cmlCount" class="meta"></span></label>
            <div class="combo" id="combo">
              <input id="cmlFilter" placeholder="Type to filter CMLs…" autocomplete="off" spellcheck="false" />
              <select id="model" size="5"><option value="">Choose an org first…</option></select>
            </div>
            <div class="combo-selected" id="comboSelected" hidden>
              <span class="selchip"><span class="name" id="selectedName"></span></span>
              <button type="button" class="ghost" id="changeModelBtn">Change CML</button>
            </div>
          </div>
          <div class="field" style="align-self:end;">
            <button class="ghost" id="reloadBtn">Reload list</button>
          </div>
        </div>
      </div>

      <!-- ══════════════ VIEW: FETCH & DEPLOY ══════════════ -->
      <div class="view-panel active" id="view-fetch">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot">1</span>
              <div>
                <h2>CML Editor</h2>
                <p>Fetch the CML from a source org, edit it, then deploy to any target org.</p>
              </div>
            </div>
          </div>

          <div class="editor-wrap">
            <div class="editor-head">
              <span class="ttl">CML Content</span>
              <div class="mini">
                <button class="ghost" id="lintBtn" title="Scan against built-in best-practice rules">Check best practices</button>
                <button class="ghost" id="copyBtn">Copy</button>
              </div>
            </div>
            <textarea id="content" placeholder="Fetched CML appears here. You can also paste CML and Deploy it." spellcheck="false"></textarea>
          </div>

          <div class="btn-row">
            <button class="btn btn-primary" id="fetchBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>Fetch CML
            </button>
            <span class="deploy-group">
              <label for="deployOrg">Deploy to</label>
              <select id="deployOrg"><option>Loading orgs…</option></select>
              <button class="btn btn-green" id="deployBtn">Deploy CML</button>
              <button class="ghost" id="rollbackBtn" title="Restore the newest saved backup for this target and model">Restore backup</button>
            </span>
          </div>

          <div class="lint" id="lint"></div>
          <div class="status" id="status"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: COMPARE ══════════════ -->
      <div class="view-panel" id="view-compare">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot">2</span>
              <div>
                <h2>Compare CML</h2>
                <p>Fetch the selected CML from both orgs and show a synchronized line diff plus a structural semantic diff.</p>
              </div>
            </div>
            <button class="btn btn-purple" id="compareBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target
            </button>
          </div>

          <div class="diff" id="diff">
            <div class="diff-head">
              <div class="summary" id="diffSummary"></div>
              <div class="legend">
                <span id="lineLegend">
                  <span><i class="lg-chg">~</i>Changed</span>
                  <span><i class="lg-del">&minus;</i>Only in source</span>
                  <span><i class="lg-ins">+</i>Only in target</span>
                </span>
                <label class="diff-opts" id="onlyDiffsWrap"><input type="checkbox" id="onlyDiffs" /> Show only differences</label>
                <label class="diff-opts" title="Compare by structure (types, attributes, relations, constraints) ignoring order and formatting"><input type="checkbox" id="semanticDiff" /> Semantic</label>
              </div>
            </div>
            <div class="diff-panes" id="diffPanes">
              <div class="pane">
                <div class="pane-title" id="srcTitle">Source</div>
                <div class="pane-scroll" id="srcScroll"><table class="pane-table" id="srcTable"></table></div>
              </div>
              <div class="pane">
                <div class="pane-title" id="tgtTitle">Target</div>
                <div class="pane-scroll" id="tgtScroll"><table class="pane-table" id="tgtTable"></table></div>
              </div>
            </div>
            <div class="sem-diff" id="semDiff"></div>
          </div>

          <div id="compareStatus" class="status" style="margin-top:14px;display:none;"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: BEST PRACTICES ══════════════ -->
      <div class="view-panel" id="view-lint">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--green),var(--teal));">3</span>
              <div>
                <h2>Best Practices</h2>
                <p>Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes.</p>
              </div>
            </div>
            <button class="btn btn-green" id="lintPanelBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>Check best practices
            </button>
          </div>
          <p class="sub" style="margin-bottom:14px;">Paste or fetch a CML first using the <strong>Fetch &amp; Deploy</strong> tab, then run the check here.</p>
          <div class="lint" id="lintPanel"></div>
          <div class="status" id="lintStatus"></div>
        </div>
      </div>

      <!-- ══════════════ VIEW: CONSTRAINT DATA ══════════════ -->
      <div class="view-panel" id="view-data">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--teal),var(--accent-strong));">4</span>
              <div>
                <h2>Constraint Data</h2>
                <p>View, compare, and deploy ExpressionSetConstraintObj rows (Product associations).</p>
              </div>
            </div>
          </div>

          <p class="sub" style="margin:0 0 14px;">Deploying CML code alone doesn't recreate Product associations. These rows are matched across orgs by a <strong>foreign key</strong> — a field whose value is stable across orgs — instead of by record Id.</p>
          <p class="meta" style="margin:0 0 14px;"><strong>Safe deployment boundary:</strong> catalog records are read-only. The tool reports missing products, classifications, attributes, component groups, and relationships, but it only writes CML content and ExpressionSetConstraintObj associations.</p>

          <div class="conn-strip" style="grid-template-columns:minmax(200px,340px) auto;gap:14px;align-items:end;margin-bottom:16px;">
            <div class="field">
              <label for="keyField">Match records by (foreign key field)</label>
              <input id="keyField" list="keyFieldOpts" value="Global_Key__c" spellcheck="false" autocomplete="off"
                     placeholder="Global_Key__c" title="API name of a field that identifies the same record across orgs" />
              <datalist id="keyFieldOpts">
                <option value="Global_Key__c"></option>
                <option value="Name"></option>
                <option value="ProductCode"></option>
                <option value="ExternalId"></option>
                <option value="External_Id__c"></option>
                <option value="StockKeepingUnit"></option>
              </datalist>
              <p class="meta" style="margin:5px 0 0;"><code>Name</code> always works; pick a stable custom/external Id if you have one.</p>
            </div>
            <div class="btn-row" style="margin-top:0;gap:8px;">
              <button class="btn btn-primary" id="loadDataBtn">View data</button>
              <button class="btn btn-purple" id="compareDataBtn">Compare data</button>
            </div>
          </div>

          <div class="deploy-bar show" id="deployBar">
            <div class="sel-summary" id="selSummary">Compare source and target data to select rows for deployment.</div>
            <div class="sel-actions">
              <button class="linklike" id="selAllAdds" disabled>Select all adds</button>
              <button class="linklike" id="selNoAdds" disabled>Clear adds</button>
              <button class="linklike" id="selAllDels" disabled>Select all deletes</button>
              <button class="linklike" id="selNoDels" disabled>Clear deletes</button>
              <button class="btn btn-green" id="deployDataBtn" disabled>Deploy selected to target</button>
            </div>
          </div>

          <div class="data" id="data">
            <div class="data-head">
              <div class="chips" id="dataChips"></div>
              <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
                <label class="data-filter">Show
                  <select id="dataFilter">
                    <option value="all">All rows</option>
                    <option value="match">Matched only</option>
                    <option value="add">Only in source (to add)</option>
                    <option value="extra">Only in target (extra)</option>
                    <option value="cml-difference">CML definition differences</option>
                    <option value="blocked">Blocked / unmappable</option>
                    <option value="stale">Unused association — absent from same org's CML</option>
                    <option value="dups">Duplicates only</option>
                  </select>
                </label>
                <button class="ghost" id="copyExcelBtn" disabled title="Copy visible rows as tab-separated values for Excel">Copy for Excel</button>
              </div>
            </div>

            <div class="table-scroll">
              <table class="data-table" id="dataTable"></table>
            </div>

            <div class="results" id="results"></div>
          </div>

          <div class="status" id="dataStatus"></div>
        </div>
      </div>

    </div><!-- .wrap -->
  </main>
</div><!-- .app-shell -->

<script>
  const $ = (id) => document.getElementById(id);
  const CSRF_TOKEN = "__CML_CSRF_TOKEN__";

  // ── Navigation ──────────────────────────────────────────────────
  const PAGE_META = {
    fetch:   { title:"Fetch &amp; Deploy",  sub:"Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org." },
    compare: { title:"Compare",             sub:"Fetch the selected CML from both orgs and show a line diff plus semantic diff." },
    lint:    { title:"Best Practices",      sub:"Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes." },
    data:    { title:"Constraint Data",     sub:"View, compare, and deploy ExpressionSetConstraintObj rows (Product associations)." },
  };
  function switchView(view) {
    document.querySelectorAll(".view-panel").forEach(p => p.classList.remove("active"));
    const panel = $("view-" + view);
    if (panel) panel.classList.add("active");
    document.querySelectorAll(".side-nav").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.view === view));
    const m = PAGE_META[view] || {};
    if ($("pageTitle")) $("pageTitle").innerHTML = m.title || view;
    if ($("pageSubtitle")) $("pageSubtitle").textContent = (m.sub || "").replace(/&amp;/g,"&");
  }
  document.querySelectorAll(".side-nav,.tab").forEach(b => {
    b.addEventListener("click", () => switchView(b.dataset.view));
  });

  const orgSel = $("org"), targetSel = $("targetOrg"), model = $("model"), content = $("content"), status = $("status");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), rollbackBtn = $("rollbackBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const cmlFilter = $("cmlFilter"), reloadBtn = $("reloadBtn"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName"), changeModelBtn = $("changeModelBtn");
  const deployOrgSel = $("deployOrg");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const lintPanelBtn = $("lintPanelBtn"), lintPanel = $("lintPanel"), lintStatus = $("lintStatus");
  const semanticChk = $("semanticDiff"), semDiff = $("semDiff"), lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  let lastCompare = null;
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), keyField = $("keyField");
  const keyName = () => (keyField.value || "Global_Key__c").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
  const copyExcelBtn = $("copyExcelBtn");
  const results = $("results");
  let allModels = [];
  let reconnecting = false;
  let dataRows = [];        // current rows shown in the data table
  let dataMode = "single";  // "single" (one org) or "compare"
  let currentKeyField = "Global_Key__c";  // foreign key the shown data was matched on

  // ---- Theme (day/night) ----
  function applyThemeLabel() {
    const t = document.documentElement.getAttribute("data-theme") || "light";
    themeBtn.textContent = t === "light" ? "Night mode" : "Day mode";
  }
  themeBtn.onclick = () => {
    const cur = document.documentElement.getAttribute("data-theme") || "light";
    const next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("cml-theme", next); } catch (e) {}
    applyThemeLabel();
  };
  applyThemeLabel();

  function setStatus(kind, msg, targetEl) {
    const el = targetEl || status;
    el.className = "status show " + kind;
    el.textContent = msg;
    el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // A network-level failure means the local server isn't reachable (window
  // closed, restarted, etc). Mark it as a connection error so callers can
  // trigger auto-reconnect instead of showing a confusing message.
  async function apiGet(path) {
    let res;
    try { res = await fetch(path, { cache: "no-store" }); }
    catch (e) { throw { conn: true }; }
    const text = await res.text();
    try { return JSON.parse(text); }
    catch (e) { return { error: "Unexpected server response (HTTP " + res.status + "):\n" + text.slice(0, 500) }; }
  }

  async function postJSON(url, payload) {
    let res;
    try {
      res = await fetch(url, {
        method: "POST", headers: {
          "Content-Type": "application/json", "X-CML-CSRF": CSRF_TOKEN
        },
        body: JSON.stringify(payload)
      });
    } catch (e) { throw { conn: true }; }
    const text = await res.text();
    try { return JSON.parse(text); }
    catch (e) { return { ok: false, log: "Server returned an unexpected response (HTTP " + res.status + "):\n" + text.slice(0, 500) }; }
  }

  function showConn() {
    conn.className = "conn show";
    conn.innerHTML = '<span class="spinner"></span>Lost connection to the CML Tool. Make sure its window is still open — reconnecting automatically…';
  }
  function hideConn() { conn.className = "conn"; }

  function handleDisconnect() {
    if (reconnecting) return;
    reconnecting = true;
    showConn();
    const timer = setInterval(async () => {
      try {
        const r = await fetch("/api/orgs", { cache: "no-store" });
        if (r.ok) {
          clearInterval(timer);
          reconnecting = false;
          hideConn();
          setStatus("ok", "Reconnected to the CML Tool.");
          loadOrgs();
        }
      } catch (e) { /* still down; keep trying */ }
    }, 1500);
  }
  const actionBtns = [fetchBtn, deployBtn, rollbackBtn, compareBtn, loadDataBtn, compareDataBtn, deployDataBtn];
  function busy(btn, label) {
    btn.innerHTML = '<span class="spinner"></span>' + label;
    actionBtns.forEach(b => b.disabled = true);
  }
  function idle() {
    fetchBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>Fetch CML';
    deployBtn.textContent = "Deploy CML";
    rollbackBtn.textContent = "Restore backup";
    compareBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target';
    loadDataBtn.textContent = "View data";
    compareDataBtn.textContent = "Compare data";
    deployDataBtn.textContent = "Deploy selected to target";
    actionBtns.forEach(b => b.disabled = false);
    updateDeployBar();
  }

  async function loadOrgs() {
    try {
      const orgs = await apiGet("/api/orgs");
      if (orgs.error) {
        orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
        setStatus("err", orgs.error);
        return;
      }
      if (!orgs.length) {
        orgSel.innerHTML = '<option value="">(no orgs found)</option>';
        setStatus("err",
          "No Salesforce orgs are authorized for THIS user on THIS computer.\n"
          + "Org logins are stored per operating-system user, so each person must log in on their own account:\n\n"
          + "    sf org login web --alias <name>\n\n"
          + "Then click \u201cReload list\u201d. Open http://127.0.0.1:" + location.port + "/api/debug to see details (sf path, OS user, saved logins).");
        return;
      }
      const opts = orgs.map(o => `<option value="${o.alias}">${o.alias}${o.username ? "  —  " + o.username : ""}</option>`).join("");
      orgSel.innerHTML = opts;
      targetSel.innerHTML = opts;
      deployOrgSel.innerHTML = opts;
      if (orgs.length > 1) targetSel.selectedIndex = 1;  // default target != source
      deployOrgSel.value = orgSel.value;  // default deploy target = source org
      loadModels();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
      setStatus("err", "Could not load orgs: " + e);
    }
  }

  // Collapse the picklist down to just the chosen CML once one is picked, and
  // let the user re-open the full list with "Change CML".
  function collapseModelView() {
    if (!model.value) return;
    const opt = model.options[model.selectedIndex];
    selectedName.textContent = opt ? opt.textContent : model.value;
    combo.hidden = true;
    comboSelected.hidden = false;
  }
  function expandModelView() {
    comboSelected.hidden = true;
    combo.hidden = false;
    try { cmlFilter.focus(); } catch (e) {}
  }
  model.addEventListener("click", () => { if (model.value) collapseModelView(); });
  model.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && model.value) { e.preventDefault(); collapseModelView(); }
  });
  changeModelBtn.onclick = expandModelView;

  function renderModels() {
    expandModelView();
    const f = cmlFilter.value.trim().toLowerCase();
    const list = allModels.filter(m =>
      !f || m.name.toLowerCase().includes(f) || (m.label || "").toLowerCase().includes(f));
    if (!list.length) {
      model.innerHTML = `<option value="">${allModels.length ? "No CMLs match your filter" : "No CMLs found in this org"}</option>`;
    } else {
      model.innerHTML = list.map(m => {
        const tag = m.status ? `  [V${m.version} · ${m.status}]` : "";
        return `<option value="${m.name}">${m.name}${tag}</option>`;
      }).join("");
      model.selectedIndex = 0;
    }
    cmlCount.textContent = allModels.length ? `(${list.length} of ${allModels.length})` : "";
  }

  async function loadModels() {
    const org = orgSel.value;
    if (!org) return;
    expandModelView();
    allModels = [];
    cmlCount.textContent = "";
    model.innerHTML = '<option value="">Loading CMLs…</option>';
    try {
      const data = await apiGet("/api/models?org=" + encodeURIComponent(org));
      if (data.error) {
        model.innerHTML = '<option value="">(could not load CMLs)</option>';
        setStatus("err", "Could not load CMLs from " + org + ":\n" + data.error);
        return;
      }
      allModels = data.models || [];
      renderModels();
      if (!allModels.length) setStatus("info", "No CMLs (Expression Set versions) were found in " + org + ".");
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      model.innerHTML = '<option value="">(could not load CMLs)</option>';
      setStatus("err", "Could not load CMLs: " + e);
    }
  }

  orgSel.onchange = loadModels;
  reloadBtn.onclick = loadModels;
  cmlFilter.oninput = renderModels;

  fetchBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose an org first."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    busy(fetchBtn, "Fetching…");
    setStatus("info", "Fetching " + model.value.trim() + " from " + orgSel.value + "…");
    try {
      const data = await postJSON("/api/fetch", { org: orgSel.value, model: model.value.trim() });
      if (data.ok) {
        content.value = data.content;
        setStatus("ok", data.log + "\n\nSaved to: " + data.file);
      } else {
        setStatus("err", data.log || "Fetch failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Fetch error: " + e); }
    }
    idle();
  };

  deployBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    if (!dest) { setStatus("err", "Please choose an org to deploy to."); deployOrgSel.focus(); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    if (!content.value.trim()) { setStatus("err", "There is no CML content to deploy."); return; }
    const crossOrg = dest !== orgSel.value;
    let msg = `Deploy "${model.value.trim()}" to org "${dest}"?\n\nThis overwrites the latest version's Constraint Model.`;
    if (crossOrg) msg += `\n\nNote: you are deploying to "${dest}", which is NOT the source org "${orgSel.value}".`;
    if (!confirm(msg)) return;
    const typed = prompt(`Production safety check:\nType the target org alias exactly to deploy:\n\n${dest}`);
    if (typed !== dest) { setStatus("err", "Deployment cancelled: target org alias did not match."); return; }
    busy(deployBtn, "Deploying…");
    setStatus("info", "Deploying " + model.value.trim() + " to " + dest + "…");
    try {
      const data = await postJSON("/api/deploy", {
        org: dest, model: model.value.trim(), content: content.value,
        confirmTarget: typed
      });
      let details = data.log || (data.ok ? "Deployed." : "Deploy failed.");
      if (data.backup && data.backup.file) details += `\n\nRecovery backup: ${data.backup.file}`;
      if (data.report && data.report.file) details += `\nDeployment report: ${data.report.file}`;
      if (data.reportError) details += `\nWARNING: ${data.reportError}`;
      setStatus(data.ok ? "ok" : "err", details);
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e); }
    }
    idle();
  };

  rollbackBtn.onclick = async () => {
    const dest = deployOrgSel.value;
    const selectedModel = model.value.trim();
    if (!dest || !selectedModel) { setStatus("err", "Choose a target org and CML model first."); return; }
    try {
      const list = await apiGet(`/api/backups?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}`);
      const backup = list.backups && list.backups[0];
      if (!backup) { setStatus("err", "No saved backup exists for this target org and model."); return; }
      const typed = prompt(`Restore the newest backup from ${backup.createdAt || "unknown time"}?\n\nType the target org alias exactly:\n${dest}`);
      if (typed !== dest) { setStatus("err", "Rollback cancelled: target org alias did not match."); return; }
      busy(rollbackBtn, "Restoring…");
      const data = await postJSON("/api/rollback", {
        org: dest, model: selectedModel, backupId: backup.id,
        confirmTarget: typed
      });
      if (data.ok && typeof data.content === "string") content.value = data.content;
      let details = data.log || (data.ok ? "Rollback complete." : "Rollback failed.");
      if (data.report && data.report.file) details += `\nDeployment report: ${data.report.file}`;
      setStatus(data.ok ? "ok" : "err", details);
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Rollback error: " + e); }
    }
    idle();
  };

  copyBtn.onclick = async () => {
    if (!content.value) return;
    try { await navigator.clipboard.writeText(content.value); copyBtn.textContent = "Copied!"; setTimeout(() => copyBtn.textContent = "Copy", 1200); }
    catch (e) { content.select(); document.execCommand("copy"); }
  };

  // ---- Compare (source org vs target org) ----
  const cmpStatus = $("compareStatus") || status;
  compareBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org.", cmpStatus); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org.", cmpStatus); return; }
    if (orgSel.value === targetSel.value) { setStatus("err", "Source and target orgs are the same. Pick two different orgs.", cmpStatus); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list.", cmpStatus); model.focus(); return; }
    busy(compareBtn, "Comparing…");
    diffBox.classList.remove("show");
    setStatus("info", `Comparing "${model.value}" between ${orgSel.value} (source) and ${targetSel.value} (target)…\nThis fetches the CML from both orgs and can take up to a minute — please wait.`, cmpStatus);
    try {
      const d = await postJSON("/api/compare", { sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim() });
      if (d.ok) {
        lastCompare = { src: d.source, tgt: d.target };
        renderCompare();
        setStatus("ok", `Compared "${d.model}".\nSource: ${d.source.file}\nTarget: ${d.target.file}`, cmpStatus);
      } else {
        setStatus("err", d.log || "Compare failed.", cmpStatus);
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Compare error: " + e, cmpStatus); }
    }
    idle();
  };

  function esc(s) { return (s == null ? "" : String(s)).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  // Longest-common-subsequence line diff -> ordered ops (eq / del / ins).
  function diffOps(a, b) {
    const n = a.length, m = b.length;
    const dp = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
    for (let i = n - 1; i >= 0; i--)
      for (let j = m - 1; j >= 0; j--)
        dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    const ops = []; let i = 0, j = 0;
    while (i < n && j < m) {
      if (a[i] === b[j]) { ops.push({ t: "eq", a: i, b: j }); i++; j++; }
      else if (dp[i + 1][j] >= dp[i][j + 1]) { ops.push({ t: "del", a: i }); i++; }
      else { ops.push({ t: "ins", b: j }); j++; }
    }
    while (i < n) { ops.push({ t: "del", a: i++ }); }
    while (j < m) { ops.push({ t: "ins", b: j++ }); }
    return ops;
  }

  function mapLines(arr) {
    const map = new Map();
    arr.forEach((line, idx) => {
      const key = line.trim();
      if (!key) return;
      if (!map.has(line)) map.set(line, []);
      map.get(line).push(idx + 1);
    });
    return map;
  }

  // A row rendered into a pane table. `marker` is a glyph cue (+ - ~) so the
  // diff is readable without relying on color (colorblind-friendly).
  function paneRow(rowType, num, codeHtml, marker) {
    const cls = rowType === "eq" ? "eqrow"
      : rowType === "chg" ? "row-chg"
      : rowType === "del" ? "row-del"
      : rowType === "ins" ? "row-ins" : "row-filler";
    if (rowType === "filler") {
      return `<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>`;
    }
    const mk = `<span class="mk">${marker}</span>`;
    return `<tr class="${cls}"><td class="gutter">${num}</td><td class="code">${mk}${codeHtml}</td></tr>`;
  }

  function renderDiff(src, tgt) {
    const a = (src.content || "").replace(/\r\n/g, "\n").split("\n");
    const b = (tgt.content || "").replace(/\r\n/g, "\n").split("\n");
    const ops = diffOps(a, b);
    const srcMap = mapLines(a), tgtMap = mapLines(b);

    // Pair runs of del/ins into aligned "changed" rows.
    const rows = []; let pendDel = [], pendIns = [];
    const flush = () => {
      const k = Math.max(pendDel.length, pendIns.length);
      for (let x = 0; x < k; x++) {
        const d = pendDel[x], ins = pendIns[x];
        if (d != null && ins != null) rows.push({ type: "chg", a: d, b: ins });
        else if (d != null) rows.push({ type: "del", a: d });
        else rows.push({ type: "ins", b: ins });
      }
      pendDel = []; pendIns = [];
    };
    for (const op of ops) {
      if (op.t === "eq") { flush(); rows.push({ type: "eq", a: op.a, b: op.b }); }
      else if (op.t === "del") pendDel.push(op.a);
      else pendIns.push(op.b);
    }
    flush();

    let chg = 0, del = 0, ins = 0, left = "", right = "";
    for (const r of rows) {
      if (r.type === "eq") {
        left += paneRow("eq", r.a + 1, esc(a[r.a]), " ");
        right += paneRow("eq", r.b + 1, esc(b[r.b]), " ");
      } else if (r.type === "chg") {
        chg++;
        left += paneRow("chg", r.a + 1, esc(a[r.a]), "~");
        right += paneRow("chg", r.b + 1, esc(b[r.b]), "~");
      } else if (r.type === "del") {
        del++;
        const where = tgtMap.get(a[r.a]);
        const note = where ? `  <span class="moved">↦ also in target at L${where.join(", ")}</span>` : "";
        left += paneRow("del", r.a + 1, esc(a[r.a]) + note, "−");
        right += paneRow("filler");
      } else {
        ins++;
        const where = srcMap.get(b[r.b]);
        const note = where ? `  <span class="moved">↤ also in source at L${where.join(", ")}</span>` : "";
        left += paneRow("filler");
        right += paneRow("ins", r.b + 1, esc(b[r.b]) + note, "+");
      }
    }
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    srcTitle.textContent = "Source — " + src.org;
    tgtTitle.textContent = "Target — " + tgt.org;
    diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);

    if (chg + del + ins === 0) {
      diffSummary.textContent = `Identical — "${model.value}" matches exactly (${a.length} lines).`;
    } else {
      diffSummary.textContent = `${chg} changed · ${del} only in source · ${ins} only in target   (source ${a.length} lines, target ${b.length} lines)`;
    }
    diffBox.classList.add("show");
    diffBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Keep the two panes vertically aligned while allowing independent
  // horizontal scrolling of long lines.
  let syncing = false;
  function syncScroll(from, to) {
    from.addEventListener("scroll", () => {
      if (syncing) { syncing = false; return; }
      syncing = true;
      to.scrollTop = from.scrollTop;
    });
  }
  syncScroll(srcScroll, tgtScroll);
  syncScroll(tgtScroll, srcScroll);

  onlyDiffs.onchange = () => diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);

  // ========================================================================
  //  CML analysis — semantic diff + best-practices linter (all client-side)
  // ========================================================================

  // Replace comments with blanks but keep newlines so line numbers stay exact.
  function stripComments(text) {
    let out = "", i = 0; const n = text.length; let s = false;
    while (i < n) {
      const c = text[i], d = text[i + 1];
      if (s) { out += c; if (c === '"') s = false; i++; continue; }
      if (c === '"') { s = true; out += c; i++; continue; }
      if (c === '/' && d === '/') { while (i < n && text[i] !== "\n") { out += " "; i++; } continue; }
      if (c === '/' && d === '*') {
        out += "  "; i += 2;
        while (i < n && !(text[i] === '*' && text[i + 1] === '/')) { out += (text[i] === "\n" ? "\n" : " "); i++; }
        if (i < n) { out += "  "; i += 2; }
        continue;
      }
      out += c; i++;
    }
    return out;
  }

  // Index of the matching close bracket for the open bracket at openIdx (string-aware).
  function matchPair(text, openIdx, open, close) {
    let depth = 0, s = false;
    for (let i = openIdx; i < text.length; i++) {
      const c = text[i];
      if (s) { if (c === '"') s = false; continue; }
      if (c === '"') { s = true; continue; }
      if (c === open) depth++;
      else if (c === close) { depth--; if (depth === 0) return i; }
    }
    return -1;
  }

  const norm = (s) => (s || "").replace(/\s+/g, " ").trim();
  const lineOf = (text, idx) => text.slice(0, idx).split("\n").length;

  // ---- Tolerant top-level parser: returns blocks keyed by declared name ----
  function parseCml(rawText) {
    const text = stripComments(rawText);
    const n = text.length; let i = 0; const units = [];
    const ws = () => { while (i < n && /\s/.test(text[i])) i++; };
    const findTop = (ch, from) => {
      let s = false, d = 0;
      for (let k = from; k < n; k++) {
        const c = text[k];
        if (s) { if (c === '"') s = false; continue; }
        if (c === '"') { s = true; continue; }
        if (c === ch && d === 0) return k;
        if (c === '(' || c === '[' || c === '{') d++;
        else if (c === ')' || c === ']' || c === '}') { if (d > 0) d--; }
      }
      return -1;
    };
    while (true) {
      ws(); if (i >= n) break;
      const start = i;
      while (text[i] === '@' && text[i + 1] === '(') { const e = matchPair(text, i + 1, '(', ')'); if (e < 0) { i = n; break; } i = e + 1; ws(); }
      const rest = text.slice(i);
      let kind = "other", name = null, end;
      let km;
      if ((km = rest.match(/^property\s+([A-Za-z_]\w*)/))) {
        kind = "property"; name = km[1]; const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else if ((km = rest.match(/^extern\s+[\w()\[\]]+\s+([A-Za-z_]\w*)/))) {
        kind = "extern"; name = km[1]; const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else if ((km = rest.match(/^define\s+([A-Za-z_]\w*)/))) {
        kind = "define"; name = km[1];
        const br = text.indexOf('[', i); const be = br >= 0 ? matchPair(text, br, '[', ']') : -1;
        if (be >= 0) end = be + 1; else { const semi = findTop(';', i); end = semi < 0 ? n : semi + 1; }
      } else if ((km = rest.match(/^type\s+([A-Za-z_]\w*)/))) {
        kind = "type"; name = km[1];
        const brace = findTop('{', i), semi = findTop(';', i);
        if (brace >= 0 && (semi < 0 || brace < semi)) { const be = matchPair(text, brace, '{', '}'); end = be < 0 ? n : be + 1; }
        else end = semi < 0 ? n : semi + 1;
      } else {
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      }
      const raw = text.slice(start, end);
      units.push({ kind, name, raw, norm: norm(raw), line: lineOf(text, start) });
      i = end > start ? end : start + 1;
    }
    return units;
  }

  // ---- Member parser for a type body (between the outer braces) ----
  function parseMembers(typeRaw) {
    const o = typeRaw.indexOf('{'); const cl = typeRaw.lastIndexOf('}');
    if (o < 0 || cl < 0 || cl < o) return [];
    const body = typeRaw.slice(o + 1, cl);
    const n = body.length; let i = 0; const out = [];
    const ws = () => { while (i < n && /\s/.test(body[i])) i++; };
    const findTop = (ch, from) => {
      let s = false, d = 0;
      for (let k = from; k < n; k++) {
        const c = body[k];
        if (s) { if (c === '"') s = false; continue; }
        if (c === '"') { s = true; continue; }
        if (c === ch && d === 0) return k;
        if (c === '(' || c === '[' || c === '{') d++;
        else if (c === ')' || c === ']' || c === '}') { if (d > 0) d--; }
      }
      return -1;
    };
    const CALLS = ["constraint", "require", "exclude", "preference", "message", "rule"];
    while (true) {
      ws(); if (i >= n) break;
      const start = i;
      while (body[i] === '@' && body[i + 1] === '(') { const e = matchPair(body, i + 1, '(', ')'); if (e < 0) { i = n; break; } i = e + 1; ws(); }
      const rest = body.slice(i);
      let sig = null, end;
      let m;
      if ((m = rest.match(/^relation\s+([A-Za-z_]\w*)/))) {
        sig = "relation:" + m[1];
        const brace = findTop('{', i), semi = findTop(';', i);
        if (brace >= 0 && (semi < 0 || brace < semi)) { const be = matchPair(body, brace, '{', '}'); end = be < 0 ? n : be + 1; }
        else end = semi < 0 ? n : semi + 1;
      } else if ((m = rest.match(new RegExp("^(" + CALLS.join("|") + ")\\s*\\(")))) {
        const p = body.indexOf('(', i); const pe = matchPair(body, p, '(', ')');
        let j = pe + 1; while (j < n && /\s/.test(body[j])) j++;
        if (body[j] === '{') { const be = matchPair(body, j, '{', '}'); end = be < 0 ? n : be + 1; }
        else { const semi = findTop(';', pe); end = semi < 0 ? (pe + 1) : semi + 1; }
        sig = m[1] + ":" + norm(body.slice(i, end));
      } else if ((m = rest.match(/^(string\[\]|string|boolean|int|double|decimal\s*\(\s*\d+\s*\))\s+([A-Za-z_]\w*)/))) {
        sig = "field:" + m[2];
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
      } else {
        const semi = findTop(';', i); end = semi < 0 ? n : semi + 1;
        sig = "stmt:" + norm(body.slice(i, end));
      }
      const raw = body.slice(start, end);
      out.push({ sig, raw: raw.trim(), norm: norm(raw) });
      i = end > start ? end : start + 1;
    }
    return out;
  }

  // ---- Semantic diff between two CML texts ----
  function semanticDiff(srcText, tgtText) {
    const su = parseCml(srcText), tu = parseCml(tgtText);
    const keyOf = (u) => (u.name ? u.kind + ":" + u.name : u.kind + "#" + u.norm);
    const sMap = new Map(), tMap = new Map();
    su.forEach((u, idx) => { u._i = idx; sMap.set(keyOf(u), u); });
    tu.forEach((u, idx) => { u._i = idx; tMap.set(keyOf(u), u); });

    const added = [], removed = [], changed = []; let same = 0;
    const commonEqualKeys = [];
    const header = (raw) => { const o = raw.indexOf('{'); return norm(o < 0 ? raw : raw.slice(0, o)); };
    for (const [k, u] of sMap) {
      if (!tMap.has(k)) { removed.push(u); continue; }
      const v = tMap.get(k);
      if (u.norm === v.norm) { same++; commonEqualKeys.push(k); continue; }
      if (u.kind === "type") {
        const md = memberDiff(u.raw, v.raw);
        // Members and header match -> only order/formatting differs -> not a change.
        if (!md.added.length && !md.removed.length && !md.changed.length && header(u.raw) === header(v.raw)) {
          same++; commonEqualKeys.push(k); continue;
        }
        changed.push({ kind: u.kind, name: u.name, members: md });
      } else {
        changed.push({ kind: u.kind, name: u.name || "(anon)", whole: { src: u.norm, tgt: v.norm } });
      }
    }
    for (const [k, v] of tMap) { if (!sMap.has(k)) added.push(v); }

    // "Reordered only": blocks identical in content but whose relative order differs.
    const sOrder = su.filter(u => commonEqualKeys.includes(keyOf(u))).map(keyOf);
    const tOrder = tu.filter(u => commonEqualKeys.includes(keyOf(u))).map(keyOf);
    const reordered = JSON.stringify(sOrder) !== JSON.stringify(tOrder);

    return { added, removed, changed, same, reordered, srcTotal: su.length, tgtTotal: tu.length };
  }

  function memberDiff(srcType, tgtType) {
    const sm = parseMembers(srcType), tm = parseMembers(tgtType);
    const sMap = new Map(), tMap = new Map();
    sm.forEach(x => sMap.set(x.sig, x));
    tm.forEach(x => tMap.set(x.sig, x));
    const added = [], removed = [], changed = [];
    for (const x of sm) {
      if (tMap.has(x.sig)) { const y = tMap.get(x.sig); if (x.norm !== y.norm) changed.push({ src: x.raw, tgt: y.raw }); }
      else removed.push(x.raw);
    }
    for (const y of tm) { if (!sMap.has(y.sig)) added.push(y.raw); }
    return { added, removed, changed };
  }

  function renderSemantic(src, tgt) {
    const d = semanticDiff(src.content || "", tgt.content || "");
    const total = d.added.length + d.removed.length + d.changed.length;
    srcTitle.textContent = "Source — " + src.org;
    tgtTitle.textContent = "Target — " + tgt.org;
    if (total === 0) {
      diffSummary.textContent = `Semantically identical${d.reordered ? " (only ordering/formatting differs)" : ""}.`;
    } else {
      diffSummary.textContent = `${d.changed.length} changed · ${d.removed.length} only in source · ${d.added.length} only in target · ${d.same} unchanged`;
    }
    let html = "";
    if (total === 0) {
      html += `<div class="sem-ok">No structural differences. The two models define the same types, attributes, relations and constraints` + (d.reordered ? `, just in a different order or formatting.` : `.`) + `</div>`;
    }
    const blockLine = (u) => `<div class="sem-block"><span class="nm">${esc(u.name || "(anonymous)")}</span> <span class="knd">${esc(u.kind)}</span></div>`;
    if (d.removed.length) html += `<div class="sem-sec"><h4>Only in source (${src.org})</h4>` + d.removed.map(blockLine).join("") + `</div>`;
    if (d.added.length) html += `<div class="sem-sec"><h4>Only in target (${tgt.org})</h4>` + d.added.map(blockLine).join("") + `</div>`;
    if (d.changed.length) {
      html += `<div class="sem-sec"><h4>Changed</h4>`;
      for (const c of d.changed) {
        html += `<div class="sem-block"><div><span class="nm">${esc(c.name)}</span> <span class="knd">${esc(c.kind)}</span></div>`;
        if (c.whole) {
          html += `<div class="sem-mem del"><span class="lab">src</span>${esc(c.whole.src)}</div>`;
          html += `<div class="sem-mem add"><span class="lab">tgt</span>${esc(c.whole.tgt)}</div>`;
        } else if (c.members) {
          const m = c.members;
          m.changed.forEach(x => {
            html += `<div class="sem-mem chg"><span class="lab">−</span>${esc(x.src)}</div>`;
            html += `<div class="sem-mem chg"><span class="lab">+</span>${esc(x.tgt)}</div>`;
          });
          m.removed.forEach(x => { html += `<div class="sem-mem del"><span class="lab">−</span>${esc(x)}</div>`; });
          m.added.forEach(x => { html += `<div class="sem-mem add"><span class="lab">+</span>${esc(x)}</div>`; });
          if (!m.changed.length && !m.removed.length && !m.added.length) html += `<div class="knd">Members match; difference is in the type header or formatting.</div>`;
        }
        html += `</div>`;
      }
      html += `</div>`;
    }
    if (d.reordered && total > 0) html += `<div class="sem-moved">Note: some identical blocks appear in a different order between the two orgs (no semantic change).</div>`;
    semDiff.innerHTML = html;
  }

  // Toggle between line diff and semantic diff and (re)render the last comparison.
  function renderCompare() {
    const sem = semanticChk.checked;
    diffPanes.style.display = sem ? "none" : "";
    semDiff.classList.toggle("show", sem);
    lineLegend.style.display = sem ? "none" : "";
    onlyDiffsWrap.style.display = sem ? "none" : "";
    if (!lastCompare) return;
    if (sem) renderSemantic(lastCompare.src, lastCompare.tgt);
    else renderDiff(lastCompare.src, lastCompare.tgt);
    diffBox.classList.add("show");
  }
  semanticChk.onchange = renderCompare;

  // Turn an implication constraint (pre -> post) into the recommended
  // "guard constraint + require() auto-add" pattern (valid CML you can paste).
  function splitImplication(blockText) {
    const t = norm(blockText);
    let label = "Rule";
    const lm = t.match(/^(?:constraint|preference)\s*\(\s*([A-Za-z_]\w*)\s*\)\s*\{/);
    if (lm) label = lm[1].replace(/_guard$/i, "");
    let region;
    const brace = t.indexOf("{");
    if (brace >= 0) { const be = t.lastIndexOf("}"); region = t.slice(brace + 1, be > brace ? be : t.length); }
    else { const p = t.indexOf("("); const pe = t.lastIndexOf(")"); region = t.slice(p + 1, pe > p ? pe : t.length); }
    const ai = region.indexOf("->");
    if (ai < 0) return null;
    // Skip biconditionals (<->) — they mean something different.
    if (region.slice(Math.max(0, ai - 2), ai).indexOf("<") >= 0) return null;
    let pre = region.slice(0, ai).trim();
    let post = region.slice(ai + 2).trim();
    post = post.replace(/,\s*"[^"]*"\s*$/, "").trim();   // drop trailing , "message"
    if (!pre || !post || pre.endsWith("<")) return null;
    const after =
      `constraint(${label}_guard) {\n  ${pre} -> ${post}\n}\n` +
      `require(${label}_auto) {\n  // When ${pre} is selected, auto-add ${post}\n}`;
    return { before: t, after };
  }

  // ---- Best-practices linter ----
  // Each finding carries: a short note, the offending snippet (before), and a
  // concrete, CML-valid correction (after) the user can copy and paste.
  function lintCml(rawText) {
    const findings = [];
    const text = stripComments(rawText);
    const lines = text.split(/\r?\n/);
    const add = (rule, sev, line, msg, note, before, after) =>
      findings.push({ rule, sev, line, msg, note, before: before || null, after: after || null });

    // Inheritance map for depth (AP-5) and stub detection (AP-3).
    const parent = {}; const typeDefs = [];
    const typeRe = /\btype\s+([A-Za-z_]\w*)\s*(?::\s*([A-Za-z_]\w*))?\s*([;{])/g;
    let mt;
    while ((mt = typeRe.exec(text))) {
      parent[mt[1]] = mt[2] || null;
      typeDefs.push({ name: mt[1], parent: mt[2] || null, line: lineOf(text, mt.index), isStub: mt[3] === ';', decl: norm(mt[0]) });
    }
    const depth = (name, seen) => {
      seen = seen || new Set();
      if (!name || seen.has(name)) return 0; seen.add(name);
      return parent[name] ? 1 + depth(parent[name], seen) : 0;
    };
    typeDefs.forEach(t => {
      const dp = depth(t.name);
      if (dp < 4) return;
      const chain = []; let cur = t.name, guard = 0;
      while (cur && guard++ < 25) { chain.push(cur); cur = parent[cur]; }
      const base = chain[chain.length - 1];
      add("AP-5", "warn", t.line,
        `Type "${t.name}" sits ${dp} levels down a chain of parent types.`,
        `This type inherits through ${dp} parents (the chain is shown below). Long chains are hard to follow and slower for the engine to resolve. Where you can, have "${t.name}" inherit directly from one shared base type and keep its own fields on it, instead of adding more in-between levels. The After sketch shows the flatter shape.`,
        chain.slice().reverse().join("  ->  "),
        `// Inherit directly from the shared base and keep this type's own fields here,\n// instead of stacking intermediate levels:\ntype ${t.name} : ${base} {\n    // attributes / relations that were spread across the chain\n}`);
    });
    const stubs = typeDefs.filter(t => t.isStub);
    if (stubs.length >= 5) {
      const ex = stubs.find(s => s.parent) || stubs[0];
      const exParent = ex.parent || "LineItem";
      add("AP-3", "info", stubs[0].line,
        `${stubs.length} types are declared with no body (e.g. "type X;").`,
        "These types are empty placeholders. That's fine if something references them, but extra unused ones add clutter. Delete the placeholders nothing points to, or give the ones you keep some real content (attributes / relations). The After example shows a stub turned into a real type.",
        stubs.slice(0, 4).map(s => s.decl).join("\n"),
        `// Either delete unused stubs, or give them meaningful content:\ntype ${ex.name} : ${exParent} {\n    @(defaultValue = "Standard")\n    string Variant = ["Standard", "Premium"];\n}`);
    }

    // Per-line rules.
    lines.forEach((ln, idx) => {
      const num = idx + 1; const t = ln.trim(); let m;
      if ((m = ln.match(/^\s*double\s+([A-Za-z_]\w*)/))) {
        add("AP-1", "warn", num,
          `"${m[1]}" uses double — not safe for money or other exact numbers.`,
          "double stores approximate values, so prices and totals can drift by a fraction of a cent. Change the type to decimal(2) — the 2 is how many digits to keep after the decimal point (use decimal(4) if you need more). The After line is the exact replacement.",
          t, t.replace(/^double\b/, "decimal(2)"));
      }
      if (/\brelation\s+\w+\s*:\s*\w+\s*\[\s*\.\.\s*\]/.test(ln)) {
        add("AP-9", "warn", num,
          "This relation is unbounded ([..]) — it allows unlimited child items.",
          "[..] lets someone add an unlimited number of these, which can slow the configurator and usually isn't intended. Put a maximum inside the brackets, like [0..50] (zero to fifty). Change 50 to the largest count you actually want to allow.",
          t, t.replace(/\[\s*\.\.\s*\]/, "[0..50]"));
      }
      if (/\brelation\s+\w+\s*:\s*\w+\s*;/.test(ln) && !/\[/.test(ln)) {
        add("AP-9", "info", num,
          "This relation doesn't say how many child items are allowed.",
          "With no range, the relation falls back to a hidden default. Make it explicit by adding a range in square brackets right after the type. Common choices: [0..1] = optional, at most one; [1..1] = required, exactly one; [0..5] = up to five. The After line uses [0..1] — change the numbers to match your rule.",
          t, t.replace(/\s*;\s*$/, "[0..1];"));
      }
      if ((m = ln.match(/\b(?:string\[\]|string|boolean|int|double|decimal\s*\(\s*\d+\s*\))\s+(x|y|z|tmp|temp|var|foo|bar|val|data)\b/))) {
        add("BP-2", "info", num,
          `The name "${m[1]}" doesn't say what it holds.`,
          "Short names like this make the model hard to read later. Rename it to a noun that describes the value — for example seatCount, monthlyTotal, or contractTerm. The After line shows where the new name goes.",
          t, t.replace(new RegExp("\\b" + m[1] + "\\b"), "descriptiveName"));
      }
    });

    // Constraint / preference scans (multi-line aware).
    const kwRe = /\b(constraint|preference)\s*\(/g; let m;
    while ((m = kwRe.exec(text))) {
      const kw = m[1]; const p = m.index + m[0].length - 1;
      const pe = matchPair(text, p, '(', ')'); if (pe < 0) continue;
      const inner = text.slice(p + 1, pe);
      let j = pe + 1; while (j < text.length && /\s/.test(text[j])) j++;
      let blockEnd = pe;
      if (text[j] === '{') { const be = matchPair(text, j, '{', '}'); if (be > 0) blockEnd = be; }
      const blockText = text.slice(m.index, blockEnd + 1);
      const oneLine = norm(blockText);
      const line = lineOf(text, m.index);
      if (/^\s*true\s*[,)]/.test(inner)) {
        add("AP-6", "warn", line,
          `This ${kw} is always true, so it never does anything.`,
          "A condition that is always true can't block or change anything — it just adds noise. If it's a leftover, delete it. If you meant to enforce something, replace true with the real condition. The After shows the shape to use.",
          oneLine,
          `// Remove this no-op, or replace true with the real condition:\n${kw}(/* your real condition */, "Message shown to the user");`);
      }
      const ops = (blockText.match(/&&|\|\|/g) || []).length;
      if (ops >= 6) {
        add("AP-8", "warn", line,
          `This ${kw} combines ${ops} conditions with && / || — too much in one rule.`,
          "Testing many things at once in a single rule is hard to read and debug. Split it into a few smaller constraints that each check one idea — they all still apply together. The After shows how to break it up.",
          oneLine,
          `// Split the combined condition into separate constraints:\n${kw}(/* first part of the condition */, "Message A");\n${kw}(/* second part of the condition */, "Message B");`);
      }
      const split = splitImplication(blockText);
      if (split) {
        add("REC", "info", line,
          `Tip: this ${kw} uses an implication (A -> B).`,
          "This works as-is. The recommended pattern is to keep A -> B as a 'guard' and add a matching require() that spells out what gets auto-added when A is chosen — so the auto-add behaviour is obvious to the next person. The After block is ready to paste; rename the _guard / _auto labels to suit.",
          split.before, split.after);
      } else if (/->/.test(blockText)) {
        add("REC", "info", line,
          `Tip: this ${kw} uses an implication (A -> B).`,
          "This works as-is. As a style improvement you can split it into a guard constraint plus a require() auto-add, which makes the auto-add behaviour explicit.",
          oneLine, null);
      }
      kwRe.lastIndex = pe + 1;
    }

    // Repeated enum literal sets (AP-4).
    const enumRe = /=\s*\[([^\]]*)\]/g; let em; const sets = {};
    while ((em = enumRe.exec(text))) {
      const items = em[1].split(",").map(s => s.trim().replace(/^"|"$/g, "")).filter(Boolean);
      if (items.length < 2) continue;
      const key = items.slice().sort().join("|");
      const rec = sets[key] || (sets[key] = { lines: [], items });
      rec.lines.push(lineOf(text, em.index));
    }
    Object.values(sets).forEach((rec) => {
      if (rec.lines.length < 3) return;
      const domain = "SharedValues";
      const listed = rec.items.map(v => `    "${v}"`).join(",\n");
      add("AP-4", "info", rec.lines[0],
        `The same list of values is typed out ${rec.lines.length} times: ["${rec.items.join('", "')}"].`,
        "Because the list is copied in many places, changing it later means editing every copy and it's easy to miss one. List the values once in a named define block (usually near the top of the file), then point to that name wherever you need the list. The After block shows the define to add — rename SharedValues to something that describes the list (e.g. ContractTerms).",
        rec.items.map(v => `"${v}"`).join(", ") + `   (used in ${rec.lines.length} places)`,
        `// 1) Declare the list once (near the top of the file):\ndefine ${domain} [\n${listed}\n]\n\n// 2) Then reference ${domain} instead of re-typing the values.`);
    });

    findings.sort((a, b) => (a.line || 0) - (b.line || 0));
    return findings;
  }

  function renderLint(rawText) {
    const findings = lintCml(rawText);
    const sevRank = { error: 0, warn: 1, info: 2 };
    const errors = findings.filter(f => f.sev === "error").length;
    const warns = findings.filter(f => f.sev === "warn").length;
    const infos = findings.filter(f => f.sev === "info").length;
    // Scoring: weight by severity, but cap how much any single rule can cost so
    // one repetitive finding (e.g. many relations missing cardinality) can't sink
    // the whole score. Recommendations (REC) are optional and don't reduce it.
    const W = { error: 15, warn: 6, info: 2 };
    const NO_SCORE = new Set(["REC"]);
    const RULE_CAP = 12;
    const perRule = {};
    findings.forEach(f => { if (NO_SCORE.has(f.rule)) return; perRule[f.rule] = (perRule[f.rule] || 0) + (W[f.sev] || 0); });
    let penalty = 0; Object.values(perRule).forEach(p => penalty += Math.min(p, RULE_CAP));
    const score = Math.max(0, 100 - penalty);
    const scoreCls = score >= 85 ? "good" : score >= 60 ? "mid" : "bad";
    let html = `<div class="lint-head"><h4>Best practices</h4>`
      + `<span class="lint-score ${scoreCls}">Quality score ${score}/100</span></div>`
      + `<div class="lint-counts"><span>${errors} error${errors === 1 ? "" : "s"}</span><span>${warns} warning${warns === 1 ? "" : "s"}</span><span>${infos} suggestion${infos === 1 ? "" : "s"}</span></div>`
      + `<div class="lint-caption">The score reflects <strong>errors</strong> and <strong>warnings</strong> (each rule is capped so one repeated issue can't dominate). Blue <strong>suggestions</strong> are optional polish and don't lower the score. Every item below has a plain-English explanation and a paste-ready fix.</div>`;
    if (!findings.length) {
      html += `<div class="lint-empty">No issues found — this CML follows the built-in best-practice rules. 🎉</div>`;
    } else {
      findings.sort((a, b) => sevRank[a.sev] - sevRank[b.sev] || (a.line || 0) - (b.line || 0));
      findings.forEach((f, i) => {
        const where = f.line ? `<span class="lint-line" data-line="${f.line}">Line ${f.line}</span> · ` : "";
        let fix = "";
        if (f.before || f.after) {
          fix += `<div class="lint-fix">`;
          if (f.before) fix += `<div class="fixhead">Before (in your CML)</div><div class="lint-code before">${esc(f.before)}</div>`;
          if (f.after) fix += `<div class="fixhead">After — paste-ready CML <button class="linklike lint-copy" data-idx="${i}">Copy</button></div><div class="lint-code after">${esc(f.after)}</div>`;
          fix += `</div>`;
        }
        html += `<div class="lint-item ${f.sev}"><div class="rmeta">${where}${esc(f.rule)} · ${esc(f.sev)}</div>`
          + `<div class="msg">${esc(f.msg)}</div>`
          + (f.note ? `<div class="fix">→ ${esc(f.note)}</div>` : "")
          + fix
          + `</div>`;
      });
    }
    lintBox.innerHTML = html;
    lintBox.classList.add("show");
    lintBox.querySelectorAll(".lint-line").forEach(el => {
      el.onclick = () => {
        const ln = parseInt(el.getAttribute("data-line"), 10) || 1;
        const before = content.value.split("\n").slice(0, ln).join("\n").length;
        content.focus();
        content.setSelectionRange(Math.max(0, before - 1), before);
        const approxTop = (ln - 1) * 16;
        content.scrollTop = Math.max(0, approxTop - content.clientHeight / 2);
      };
    });
    lintBox.querySelectorAll(".lint-copy").forEach(el => {
      el.onclick = async (ev) => {
        ev.stopPropagation();
        const idx = parseInt(el.getAttribute("data-idx"), 10);
        const txt = (findings[idx] && findings[idx].after) || "";
        try { await navigator.clipboard.writeText(txt); el.textContent = "Copied!"; setTimeout(() => el.textContent = "Copy", 1200); }
        catch (e) { el.textContent = "Copy failed"; }
      };
    });
    lintBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function doLint() {
    if (!content.value.trim()) {
      setStatus("err", "Paste or fetch some CML first (Fetch & Deploy tab), then check best practices.");
      if (lintStatus) { lintStatus.className = "status show err"; lintStatus.textContent = "No CML to check. Go to Fetch & Deploy, fetch or paste a CML, then return here."; }
      return;
    }
    renderLint(content.value);
    // also populate the dedicated panel
    if (lintPanel) { lintPanel.innerHTML = lintBox.innerHTML; lintPanel.className = "lint show"; }
    if (lintStatus) lintStatus.className = "status";
  }
  lintBtn.onclick = () => { doLint(); };
  if (lintPanelBtn) lintPanelBtn.onclick = () => { doLint(); switchView("lint"); };

  // ---- Constraint data (ExpressionSetConstraintObj) ----
  const TYPE_SHORT = {
    Product2: "Product", ProductClassification: "Classification",
    ProductComponentGroup: "Comp. Group", ProductRelatedComponent: "Related Comp."
  };
  function shortType(t) { return TYPE_SHORT[t] || t || "—"; }

  function statusBadge(s) {
    if (s === "match")      return '<span class="badge b-match">Matched</span>';
    if (s === "add")        return '<span class="badge b-add">Add to target</span>';
    if (s === "ready")      return '<span class="badge b-add">Add to target</span>';
    if (s === "extra")      return '<span class="badge b-extra">Only in target</span>';
    if (s === "cml-difference") return '<span class="badge b-extra">CML definitions differ</span>';
    if (s === "blocked")    return '<span class="badge b-blocked">Blocked — catalog dependency</span>';
    if (s === "dependency-unverified") return '<span class="badge b-unmappable">Needs review — dependency key missing</span>';
    if (s === "unmappable") return '<span class="badge b-unmappable">No ' + esc(currentKeyField) + '</span>';
    if (s === "stale")      return '<span class="badge b-unmappable">Unused association in this org</span>';
    return "";
  }

  function statusText(r) {
    const s = r._status;
    if (s === "match")      return "Matched";
    if (s === "add" || s === "ready") return "Add to target";
    if (s === "extra")      return "Only in target";
    if (s === "cml-difference") return "CML definitions differ — valid in one org";
    if (s === "blocked")    return "Blocked — catalog dependency";
    if (s === "dependency-unverified") return "Needs review — dependency could not be compared";
    if (s === "unmappable") return "No " + currentKeyField;
    if (s === "stale")      return "Unused association — absent from the same org's CML";
    return s || "";
  }

  const DUP_LABEL = { exact: "Exact duplicate", tag: "Duplicate tag", ref: "Duplicate reference", name: "Ambiguous name" };
  function dupBadges(r) {
    if (!r.dups || !r.dups.length) return "";
    return r.dups.map(d => `<span class="badge b-dup" title="${esc(DUP_LABEL[d] || d)}">${esc(DUP_LABEL[d] || d)}</span>`).join("");
  }

  // Which rows can be acted on in a compare deploy.
  function isAdd(r) { return r._status === "add"; }     // ready to insert in target
  function isDel(r) { return r._status === "extra"; }   // exists only in target

  function dataRowHtml(r, withStatus) {
    const code = r.refCode ? ` <span class="gkey">(${esc(r.refCode)})</span>` : "";
    const gk = r.mappable ? `<span class="gkey">${esc(r.gkey)}</span>`
                          : '<span class="badge b-unmappable">missing</span>';
    const blockNote = r.blockNote ? `<span class="block-note">${esc(r.blockNote)}</span>` : "";
    let sel = "";
    if (withStatus) {
      if (isAdd(r) || isDel(r)) {
        sel = `<td class="col-sel"><input type="checkbox" data-i="${r._i}" ${r._selected ? "checked" : ""}></td>`;
      } else {
        sel = `<td class="col-sel"></td>`;
      }
    }
    return "<tr>"
      + sel
      + (withStatus ? `<td class="col-status">${statusBadge(r._status)}${blockNote}</td>` : "")
      + `<td class="col-reftype"><span class="badge b-type">${esc(shortType(r.refType))}</span></td>`
      + `<td class="col-tagtype">${esc(r.tagType)}</td>`
      + `<td class="col-tag">${esc(r.tag)}</td>`
      + `<td class="col-ref">${esc(r.refName)}${code}${dupBadges(r)}</td>`
      + `<td class="col-key">${gk}</td>`
      + "</tr>";
  }

  function renderDataTable() {
    const withStatus = dataMode === "compare";
    const f = dataFilter.value;
    const visible = dataRows.filter(r => {
      if (f === "all") return true;
      if (f === "match")   return r._status === "match";
      if (f === "add")     return r._status === "add";
      if (f === "extra")   return r._status === "extra";
      if (f === "cml-difference") return r._status === "cml-difference";
      if (f === "blocked") return r._status === "blocked" || r._status === "unmappable" || r._status === "dependency-unverified";
      if (f === "stale")   return r._status === "stale";
      if (f === "dups")    return r.dups && r.dups.length;
      return true;
    });
    const cols = (withStatus ? 7 : 5);
    const head = "<thead><tr>"
      + (withStatus ? '<th class="col-sel"></th><th class="col-status">Status</th>' : "")
      + '<th class="col-reftype">Ref type</th><th class="col-tagtype">Tag type</th><th class="col-tag">Tag</th><th class="col-ref">Reference record</th><th class="col-key">' + esc(currentKeyField) + "</th>"
      + "</tr></thead>";
    const body = visible.length
      ? visible.map(r => dataRowHtml(r, withStatus)).join("")
      : `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:18px;">No rows for this filter.</td></tr>`;
    dataTable.innerHTML = head + "<tbody>" + body + "</tbody>";
    dataTable.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.onchange = () => { dataRows[+cb.dataset.i]._selected = cb.checked; updateDeployBar(); };
    });
    copyExcelBtn.disabled = visible.length === 0;
    updateDeployBar();
  }
  dataFilter.onchange = renderDataTable;

  function updateDeployBar() {
    deployBar.classList.add("show");
    if (dataMode !== "compare") {
      selSummary.textContent = "Compare source and target data to select rows for deployment.";
      [selAllAdds, selNoAdds, selAllDels, selNoDels, deployDataBtn].forEach(b => { b.disabled = true; });
      return;
    }
    const adds = dataRows.filter(r => isAdd(r) && r._selected).length;
    const dels = dataRows.filter(r => isDel(r) && r._selected).length;
    const totalAdds = dataRows.filter(isAdd).length;
    const totalDels = dataRows.filter(isDel).length;
    selAllAdds.disabled = selNoAdds.disabled = totalAdds === 0;
    selAllDels.disabled = selNoDels.disabled = totalDels === 0;
    if ((totalAdds + totalDels) === 0) {
      selSummary.textContent = "No deployable differences were found.";
    } else {
      selSummary.innerHTML =
        `Selected: <strong>${adds}</strong> to add`
        + (dels ? ` · <strong class="warn-note">${dels}</strong> <span class="warn-note">to delete</span>` : ` · <strong>0</strong> to delete`);
    }
    deployDataBtn.disabled = (adds + dels) === 0;
  }

  function setSel(pred, val) { dataRows.forEach(r => { if (pred(r)) r._selected = val; }); renderDataTable(); }
  selAllAdds.onclick = () => setSel(isAdd, true);
  selNoAdds.onclick  = () => setSel(isAdd, false);
  selAllDels.onclick = () => setSel(isDel, true);
  selNoDels.onclick  = () => setSel(isDel, false);

  copyExcelBtn.onclick = async () => {
    const withStatus = dataMode === "compare";
    const f = dataFilter.value;
    const visible = dataRows.filter(r => {
      if (f === "all") return true;
      if (f === "match")   return r._status === "match";
      if (f === "add")     return r._status === "add";
      if (f === "extra")   return r._status === "extra";
      if (f === "cml-difference") return r._status === "cml-difference";
      if (f === "blocked") return r._status === "blocked" || r._status === "unmappable" || r._status === "dependency-unverified";
      if (f === "stale")   return r._status === "stale";
      if (f === "dups")    return r.dups && r.dups.length;
      return true;
    });
    if (!visible.length) return;
    const cols = withStatus
      ? ["Status", "Ref type", "Tag type", "Tag", "Reference record", currentKeyField]
      : ["Ref type", "Tag type", "Tag", "Reference record", currentKeyField];
    const rows = visible.map(r => {
      const base = [
        shortType(r.refType),
        r.tagType || "",
        r.tag || "",
        (r.refName || "") + (r.refCode ? " (" + r.refCode + ")" : ""),
        r.mappable ? (r.gkey || "") : "missing",
      ];
      if (withStatus) {
        const detail = r.blockNote ? " — " + r.blockNote : "";
        base.unshift(statusText(r) + detail);
      }
      return base.map(v => String(v ?? "").replace(/[\t\r\n]+/g, " ")).join("\t");
    });
    const tsv = cols.join("\t") + "\r\n" + rows.join("\r\n");
    try {
      await navigator.clipboard.writeText(tsv);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = tsv; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    const orig = copyExcelBtn.textContent;
    copyExcelBtn.textContent = `Copied ${visible.length} row${visible.length === 1 ? "" : "s"} for Excel!`;
    setTimeout(() => { copyExcelBtn.textContent = orig; }, 1600);
  };

  const dSt = () => $("dataStatus") || status;
  loadDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org first.", dSt()); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list.", dSt()); model.focus(); return; }
    busy(loadDataBtn, "Loading…");
    setStatus("info", `Loading constraint data for "${model.value}" from ${orgSel.value}…`, dSt());
    try {
      const data = await postJSON("/api/data", { org: orgSel.value, model: model.value.trim(), keyField: keyName() });
      if (data.ok) {
        dataMode = "single";
        currentKeyField = data.keyField || keyName();
        dataRows = data.rows.map((r, i) => ({ ...r, _status: "", _i: i, _selected: false }));
        deployBar.classList.add("show");
        results.classList.remove("show");
        renderDataChips({ single: true, total: data.stats.total, unmappable: data.stats.unmappable, dups: data.stats.duplicates, org: orgSel.value });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const warn = data.stats.unmappable ? ` (${data.stats.unmappable} without ${currentKeyField})` : "";
        setStatus("ok", `Loaded ${data.stats.total} constraint rows from ${orgSel.value}${warn}.`, dSt());
      } else {
        setStatus("err", data.log || "Could not load data.", dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Data error: " + e, dSt()); }
    }
    idle();
  };

  compareDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org.", dSt()); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org.", dSt()); return; }
    if (orgSel.value === targetSel.value) { setStatus("err", "Source and target orgs are the same. Pick two different orgs.", dSt()); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list.", dSt()); model.focus(); return; }
    busy(compareDataBtn, "Comparing…");
    setStatus("info", `Comparing constraint data for "${model.value}" between ${orgSel.value} and ${targetSel.value}…\nThis reads both orgs and can take up to a minute — please wait.`, dSt());
    try {
      const data = await postJSON("/api/data/compare", { sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim(), keyField: keyName() });
      if (data.ok) {
        dataMode = "compare";
        currentKeyField = data.keyField || keyName();
        const rows = [];
        data.matched.forEach(r => rows.push({
          ...r, _status: ["blocked", "dependency-unverified"].includes(r.deployStatus)
            ? r.deployStatus : "match"
        }));
        data.sourceOnly.forEach(r => rows.push({ ...r, _status: r.deployStatus === "ready" ? "add" : r.deployStatus }));
        data.targetOnly.forEach(r => rows.push({
          ...r, _status: r.deployStatus === "cml-difference" ? "cml-difference" : "extra"
        }));
        (data.stale || []).forEach(r => rows.push({ ...r, _status: "stale" }));
        // Adds default ON; deletes default OFF (deletion is riskier — opt in).
        rows.forEach((r, i) => { r._i = i; r._selected = (r._status === "add"); });
        dataRows = rows;
        results.classList.remove("show");
        renderDataChips({ single: false, s: data.stats, src: data.source, tgt: data.target });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setStatus("ok", `Compared constraint data for "${data.model}".\n`
          + `${data.stats.matched} matched · ${data.stats.sourceOnly} only in source · ${data.stats.targetOnly} only in target`
          + (data.stats.cmlDifferences ? ` · ${data.stats.cmlDifferences} explained by different CML definitions` : "")
          + (data.stats.dependencyIssues ? ` · ${data.stats.dependencyIssues} catalog dependency finding(s)` : "")
          + (data.stats.dependencyUnverified ? ` · ${data.stats.dependencyUnverified} dependency check(s) need a key` : "")
          + (data.stats.stale ? ` · ${data.stats.stale} stale (excluded)` : "") + `.`, dSt());
      } else {
        setStatus("err", data.log || "Compare failed.", dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Data compare error: " + e, dSt()); }
    }
    idle();
  };

  function dupSum(d) { return d ? (d.exact + d.tag + d.ref + d.name) : 0; }

  function renderDataChips(o) {
    if (o.single) {
      const dn = dupSum(o.dups);
      dataChips.innerHTML =
        `<span class="chip ok">${o.total} rows · ${o.org}</span>`
        + (o.unmappable ? `<span class="chip warn">${o.unmappable} without ${currentKeyField}</span>` : "")
        + (dn ? `<span class="chip warn">${dn} duplicate rows</span>` : "");
      return;
    }
    const s = o.s;
    const sd = dupSum(o.src.duplicates), td = dupSum(o.tgt.duplicates);
    dataChips.innerHTML =
      `<span class="chip">Source ${o.src.org}: ${o.src.total}</span>`
      + `<span class="chip">Target ${o.tgt.org}: ${o.tgt.total}</span>`
      + `<span class="chip ok">${s.matched} matched</span>`
      + `<span class="chip add">${s.sourceOnly} only in source</span>`
      + `<span class="chip extra">${s.targetOnly} only in target</span>`
      + (s.cmlDifferences ? `<span class="chip warn">${s.cmlDifferences} CML definition differences (not errors)</span>` : "")
      + (s.dependencyIssues ? `<span class="chip warn">${s.dependencyIssues} catalog dependency findings</span>` : "")
      + (s.dependencyUnverified ? `<span class="chip warn">${s.dependencyUnverified} dependency checks need review</span>` : "")
      + (s.stale ? `<span class="chip warn">${s.stale} stale (excluded from deploy)</span>` : "")
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked by catalog dependencies</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "")
      + ((sd + td) ? `<span class="chip warn">${sd + td} duplicate rows (src ${sd} / tgt ${td})</span>` : "");
  }

  // ---- Deploy selected constraint data to the target ----
  function renderResults(data) {
    const s = data.stats;
    let html = `<h4>Deployment results — target ${esc(data.target)}</h4>`;
    if (data.outcome === "partial") {
      html += `<div class="status show warn" style="margin-bottom:10px;">Partial deployment: Salesforce applied some rows and rejected others because allOrNone=false. Review every failed row before retrying.</div>`;
    }
    html += `<div class="chips" style="margin-bottom:10px;">`
      + `<span class="chip ok">${s.insertOk} added</span>`
      + (s.insertFail ? `<span class="chip warn">${s.insertFail} add failed</span>` : "")
      + `<span class="chip extra">${s.deleteOk} deleted</span>`
      + (s.deleteFail ? `<span class="chip warn">${s.deleteFail} delete failed</span>` : "")
      + `</div>`;
    const line = (r, verb) => `<div class="result-row ${r.success ? "good" : "bad"}">`
      + `<span class="ico">${r.success ? "✓" : "✗"}</span>`
      + `<span>${verb} ${esc(r.label)}${r.success ? "" : " — " + esc(r.error || "failed")}</span></div>`;
    if (data.created.length) html += `<h4>Inserts</h4>` + data.created.map(r => line(r, "Add")).join("");
    if (data.deleted.length) html += `<h4>Deletes</h4>` + data.deleted.map(r => line(r, "Delete")).join("");
    if (data.refresh) {
      html += `<h4>CML validation refresh</h4>`
        + `<div class="result-row ${data.refresh.ok ? "good" : "bad"}">`
        + `<span class="ico">${data.refresh.ok ? "✓" : "✗"}</span>`
        + `<span>${esc(data.refresh.ok
          ? "Target CML was re-saved unchanged so Salesforce can validate the new associations."
          : data.refresh.log || "Target CML validation refresh failed.")}</span></div>`;
    }
    if (data.archive && data.archive.id) {
      html += `<div style="margin-top:10px;"><button class="ghost" id="restoreArchiveBtn">Restore deleted associations</button></div>`;
    }
    if (data.backup && data.backup.file) {
      html += `<div class="result-row good"><span>CML backup</span><span>${esc(data.backup.file)}</span></div>`;
    }
    if (data.report && data.report.file) {
      html += `<div class="result-row good"><span>Report</span><span>${esc(data.report.file)}</span></div>`;
    }
    if (data.reportError) {
      html += `<div class="result-row bad"><span>!</span><span>${esc(data.reportError)}</span></div>`;
    }
    results.innerHTML = html;
    results.classList.add("show");
    const restoreBtn = $("restoreArchiveBtn");
    if (restoreBtn) restoreBtn.onclick = async () => {
      const dest = data.target;
      const typed = prompt(`Restore deleted associations?\n\nType the target org alias exactly:\n${dest}`);
      if (typed !== dest) { setStatus("err", "Restore cancelled: target org alias did not match.", dSt()); return; }
      busy(restoreBtn, "Restoring…");
      try {
        const restored = await postJSON("/api/data/restore", {
          targetOrg: dest, model: model.value.trim(),
          archiveId: data.archive.id, confirmTarget: typed
        });
        setStatus(restored.ok ? "ok" : "err", restored.log || "Association restore finished.", dSt());
      } catch (e) {
        if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Restore error: " + e, dSt()); }
      }
      restoreBtn.textContent = "Restore deleted associations";
      idle();
    };
    results.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  deployDataBtn.onclick = async () => {
    const adds = dataRows.filter(r => isAdd(r) && r._selected)
      .map(r => ({ sourceConstraintId: r.id, refName: r.refName }));
    const deletes = dataRows.filter(r => isDel(r) && r._selected)
      .map(r => ({ id: r.id, tag: r.tag, tagType: r.tagType, refName: r.refName }));
    if (!adds.length && !deletes.length) { setStatus("err", "Select at least one row to deploy.", dSt()); return; }
    let msg = `Deploy to "${targetSel.value}"?\n\n• ${adds.length} association(s) will be ADDED.`;
    if (deletes.length) msg += `\n• ${deletes.length} association(s) will be DELETED (permanent).`;
    msg += `\n\nProceed?`;
    if (!confirm(msg)) return;
    const typed = prompt(`Production safety check:\nType the target org alias exactly to deploy:\n\n${targetSel.value}`);
    if (typed !== targetSel.value) { setStatus("err", "Deployment cancelled: target org alias did not match.", dSt()); return; }
    busy(deployDataBtn, "Deploying…");
    setStatus("info", `Deploying constraint data to ${targetSel.value}: +${adds.length} / −${deletes.length}…`, dSt());
    try {
      const data = await postJSON("/api/data/deploy", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim(),
        adds, deletes, keyField: keyName(), confirmTarget: typed
      });
      if (data.stats) {
        renderResults(data);
        const s = data.stats;
        const refreshFailed = data.refresh && !data.refresh.ok;
        const severity = data.outcome === "failed" ? "err"
          : (s.insertFail + s.deleteFail || refreshFailed ? "info" : "ok");
        setStatus(severity,
          `Done. Added ${s.insertOk}/${adds.length}, deleted ${s.deleteOk}/${deletes.length}.`
          + (s.insertFail + s.deleteFail ? ` ${s.insertFail + s.deleteFail} failed — see details below.` : "")
          + (refreshFailed ? ` Associations were deployed, but CML validation refresh failed — see details below.` : "")
          + `\nReview the saved report and recovery options below, then click Compare data to refresh.`, dSt());
      } else {
        setStatus("err", data.log || "Deploy failed.", dSt());
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e, dSt()); }
    }
    idle();
  };

  fetch("/api/ping", { cache: "no-store" })
    .then(r => r.json())
    .then(d => { const e = $("appver"); if (e) e.textContent = "build " + (d.build || "?").slice(0, 8); })
    .catch(() => {});

  loadOrgs();
</script>
</body>
</html>"""


def main():
    if "--print-build" in sys.argv:
        print(BUILD)
        return

    open_browser = "--no-browser" not in sys.argv
    port = DEFAULT_PORT
    url = f"http://127.0.0.1:{port}/"

    # If a CML Tool is already running here, decide what to do based on its build.
    running_build = _server_build(port)
    if running_build == BUILD:
        # Same code already serving — just reuse it.
        print(f"CML Tool is already running (latest build) at {url}")
        if open_browser:
            webbrowser.open(url)
        return
    if running_build is not None:
        # An older build is running — stop it so this new build takes over.
        print("A previous version of the CML Tool is running — restarting with the new build…")
        if not _quit_running(port):
            print(f"ERROR: Could not stop the previous version on port {port}.")
            print("Close it manually (or reboot) and try again.")
            sys.exit(1)

    # Port held by something that isn't us — fail clearly instead of drifting.
    if port_in_use(port):
        print(f"ERROR: Port {port} is in use by another program.")
        print(f"Stop it, or set a different port: CML_UI_PORT=8900 python3 cml_tool.py")
        sys.exit(1)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(f"ERROR: Could not start server on port {port}: {exc}")
        sys.exit(1)

    print("=" * 60)
    print("  CML Fetch & Deploy — local UI")
    print("=" * 60)
    print(f"  Running at:  {url}")
    print("=" * 60)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
