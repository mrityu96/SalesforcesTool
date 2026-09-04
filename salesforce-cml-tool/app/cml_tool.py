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
    python3 app/cml_tool.py

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

# App code lives in app/; runtime artifacts stay at the package root.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(APP_DIR)
SCRIPTS_DIR = os.path.join(APP_DIR, "utilities")
DOWNLOAD_DIR = os.path.join(REPO_ROOT, "cml-files")
BACKUP_DIR = os.path.join(REPO_ROOT, "cml-backups")
REPORT_DIR = os.path.join(REPO_ROOT, "deployment-reports")
ARCHIVE_DIR = os.path.join(REPO_ROOT, "association-archives")
LOG_DIR = os.path.join(REPO_ROOT, "logs")
DATA_DEPLOY_AUDIT_FILE = os.path.join(
    LOG_DIR, "data-deploy-history.jsonl")
CSRF_TOKEN = secrets.token_urlsafe(32)
FIELD_PROBE_TTL = 300
ESCO_CAPABILITY_TTL = 300
_DEPLOY_LOCKS = {}
_DEPLOY_LOCKS_GUARD = threading.Lock()
_AUDIT_LOG_LOCK = threading.Lock()


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
API_VERSION = "v66.0"  # Spring '26; ESCO itself requires v63.0 or later
PRC_IDENTITY_VERSION = 2


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
    """Return every exact CML definition version available in an org."""
    if not org:
        return {"error": "No org selected."}
    if not find_sf():
        return {"error": "The Salesforce CLI ('sf') was not found. "
                         "Install it with: npm install -g @salesforce/cli"}
    query = (
        "SELECT Id, ExpressionSetDefinition.DeveloperName, "
        "ExpressionSetDefinition.MasterLabel, VersionNumber, Status "
        "FROM ExpressionSetDefinitionVersion "
        "WHERE ExpressionSetDefinitionId IN ("
        "SELECT ExpressionSetDefinitionId FROM ExpressionSet "
        "WHERE UsageType = 'Constraint') "
        "ORDER BY ExpressionSetDefinition.DeveloperName, VersionNumber DESC"
    )
    records, err = _query_json(org, query)
    if err:
        return {"error": err}

    models = []
    for rec in records:
        defn = rec.get("ExpressionSetDefinition") or {}
        name = defn.get("DeveloperName")
        if not name or not rec.get("Id"):
            continue
        models.append({
            "versionId": rec.get("Id"),
            "name": name,
            "label": defn.get("MasterLabel") or name,
            "version": rec.get("VersionNumber"),
            "status": rec.get("Status"),
        })
    status_rank = {"active": 0, "inactive": 1}
    models.sort(key=lambda item: (
        status_rank.get(str(item.get("status") or "").strip().lower(), 2),
        str(item.get("name") or "").lower(),
        -(float(item.get("version")) if str(
            item.get("version") or "").replace(".", "", 1).isdigit() else -1),
        str(item.get("versionId") or ""),
    ))
    return {"models": models}


def resolve_exact_version(org, model, version_id):
    """Verify an untrusted version Id belongs to the named model."""
    if not org or not model or not version_id:
        return None, (
            "Select an exact version for this operation; org, model name, and "
            "versionId are all required.")
    recs, err = _query_json(
        org,
        "SELECT Id, VersionNumber, Status, "
        "ExpressionSetDefinition.DeveloperName, "
        "ExpressionSetDefinition.MasterLabel "
        "FROM ExpressionSetDefinitionVersion "
        "WHERE Id = '" + _soql_str(version_id) + "' "
        "AND ExpressionSetDefinitionId IN ("
        "SELECT ExpressionSetDefinitionId FROM ExpressionSet "
        "WHERE UsageType = 'Constraint')")
    if err:
        return None, err
    if not recs:
        return None, (
            f"Exact Constraint CML version '{version_id}' was not found in "
            f"'{org}'. It may be unavailable or belong to a non-Constraint "
            "Expression Set such as a pricing procedure. Refresh the CML "
            "version list and select it again.")
    rec = recs[0]
    definition = rec.get("ExpressionSetDefinition") or {}
    observed_model = definition.get("DeveloperName")
    if observed_model != model:
        return None, (
            f"Version '{version_id}' belongs to model "
            f"'{observed_model or 'unknown'}', not '{model}'. Refresh the "
            "version list and select the intended exact version.")
    return {
        "Id": rec.get("Id"),
        "DeveloperName": observed_model,
        "MasterLabel": definition.get("MasterLabel") or observed_model,
        "VersionNumber": rec.get("VersionNumber"),
        "Status": rec.get("Status"),
    }, None


def _exact_expression_set(org, model, version_id):
    """Resolve the sole ExpressionSet parent for a verified definition version."""
    version, err = resolve_exact_version(org, model, version_id)
    if err:
        return None, None, err
    recs, err = _query_json(
        org,
        "SELECT ExpressionSetId FROM ExpressionSetVersion "
        "WHERE ExpressionSetDefinitionVerId = '"
        + _soql_str(version["Id"]) + "'")
    if err:
        return version, None, err
    parent_ids = sorted({
        rec.get("ExpressionSetId") for rec in recs
        if rec.get("ExpressionSetId")
    })
    if not parent_ids:
        return version, None, (
            f"Exact version '{version_id}' of '{model}' has no "
            "ExpressionSetVersion parent mapping. Verify "
            "ExpressionSetVersion.ExpressionSetDefinitionVerId in the org.")
    if len(parent_ids) != 1:
        return version, None, (
            f"Exact version '{version_id}' of '{model}' maps to "
            f"{len(parent_ids)} Expression Sets ({', '.join(parent_ids)}). "
            "Resolve the ambiguous ExpressionSetVersion ownership before "
            "continuing.")
    return version, parent_ids[0], None


def _expression_set_write_status(
        org, expression_set_id, operation, definition_version_id=None):
    """Fail closed unless the parent has no active runtime ExpressionSetVersion.

    ExpressionSet has no Status field in the REST schema. Runtime activation is
    represented by ExpressionSetVersion.IsActive, while the authoring version's
    lifecycle is checked separately through ExpressionSetDefinitionVersion.
    ESCO rows are parent-ExpressionSet scoped, so any active runtime version
    under that shared parent blocks association writes.
    """
    if not expression_set_id:
        return None, (
            f"{operation} blocked because the exact parent ExpressionSet was "
            "not supplied.")
    recs, err = _query_json(
        org,
        "SELECT Id, IsActive, ExpressionSetId, ExpressionSetDefinitionVerId "
        "FROM ExpressionSetVersion WHERE ExpressionSetId = '"
        + _soql_str(expression_set_id) + "'")
    if err:
        return None, (
            f"{operation} blocked because runtime ExpressionSetVersion "
            f"activity could not be reverified:\n{err}")
    if not recs:
        return None, (
            f"{operation} blocked because parent ExpressionSet "
            f"'{expression_set_id}' has no observable ExpressionSetVersion.")
    if definition_version_id and not any(
            rec.get("ExpressionSetDefinitionVerId") == definition_version_id
            for rec in recs):
        return None, (
            f"{operation} blocked because selected definition version "
            f"'{definition_version_id}' no longer maps to parent ExpressionSet "
            f"'{expression_set_id}'. Refresh versions and compare again.")
    active_ids = sorted(
        rec.get("Id") for rec in recs
        if rec.get("IsActive") is True and rec.get("Id"))
    if active_ids:
        return "Active", (
            f"{operation} blocked because parent ExpressionSet "
            f"'{expression_set_id}' has active runtime ExpressionSetVersion "
            f"record(s): {', '.join(active_ids)}. Deactivate the constraint "
            "model, then refresh versions before retrying.")
    return "No active runtime version", None


def _version_write_status(org, version_id, operation):
    """Fail closed unless the exact definition version is observed non-Active."""
    recs, err = _query_json(
        org,
        "SELECT Id, Status FROM ExpressionSetDefinitionVersion WHERE Id = '"
        + _soql_str(version_id) + "'")
    if err:
        return None, (
            f"{operation} blocked because the exact selected version status "
            f"could not be reverified:\n{err}")
    if len(recs) != 1:
        return None, (
            f"{operation} blocked because exact selected version '{version_id}' "
            "could not be uniquely reverified.")
    status = recs[0].get("Status")
    if status is None or not str(status).strip():
        return None, (
            f"{operation} blocked because exact selected version '{version_id}' "
            "returned no observable Status value.")
    if str(status).strip().lower() == "active":
        return status, (
            f"{operation} blocked: exact selected version '{version_id}' is "
            f"{status}. Deactivate it, then refresh versions before retrying.")
    return status, None


def _download_cml(org, model, version_id, out_file):
    """Fetch one CML's ConstraintModel over REST into out_file (cross-platform).
    Returns a result dict."""
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    rec, err = resolve_exact_version(org, model, version_id)
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
            "versionId": version_id,
            "versionNumber": rec.get("VersionNumber"),
            "versionStatus": rec.get("Status"),
            "log": (
                f"{log}\n\nThe selected version of '{model}' in '{org}' has an EMPTY "
                "Constraint Model. This reports only the observed empty content; "
                "no lifecycle state or cause is inferred."
            ).strip(),
        }
    return {
        "ok": True, "log": log, "content": content, "file": out_file,
        "versionId": version_id,
        "versionNumber": rec.get("VersionNumber"),
        "versionStatus": rec.get("Status"),
    }


def fetch_cml(org, model, version_id):
    """Fetch a CML and return its content + logs."""
    if not org or not model or not version_id:
        return {"ok": False, "log": (
            "Select an exact version before fetching CML.")}
    return _download_cml(
        org, model, version_id,
        os.path.join(
            DOWNLOAD_DIR, f"{_safe(model)}__{_safe(version_id)}.cml"))


def _cml_text(org, model, version_id):
    """Read one verified exact CML without writing a download file."""
    rec, err = resolve_exact_version(org, model, version_id)
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


def _cml_used_tags(org, model, version_id):
    """Return the Type and Port tags referenced by one exact CML version."""
    text, err = _cml_text(org, model, version_id)
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


def _freeze_json_value(value):
    """Convert JSON lists back into hashable tuple identities recursively."""
    if isinstance(value, list):
        return tuple(_freeze_json_value(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted(
            (key, _freeze_json_value(item)) for key, item in value.items()))
    return value


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


def _append_data_deploy_audit(entry):
    """Append exactly one durable JSON line for each association deploy call."""
    os.makedirs(LOG_DIR, mode=0o700, exist_ok=True)
    payload = {
        "timestamp": _utc_now().isoformat(),
        "operating_system_user": getpass.getuser(),
        **entry,
    }
    with _AUDIT_LOG_LOCK:
        with open(DATA_DEPLOY_AUDIT_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(DATA_DEPLOY_AUDIT_FILE, 0o600)
        except OSError:
            pass


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


def list_cml_backups(org, model, version_id):
    if not org or not model or not version_id:
        return {"ok": False, "log": (
            "Select an exact target version before listing backups.")}
    _, err = resolve_exact_version(org, model, version_id)
    if err:
        return {"ok": False, "log": err}
    if not os.path.isdir(BACKUP_DIR):
        return {"ok": True, "backups": []}
    backups = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        data, err = _read_json_artifact(BACKUP_DIR, name)
        if err or data.get("kind") != "cml-backup":
            continue
        if (data.get("org") == org and data.get("model") == model
                and data.get("versionId") == version_id):
            backups.append({
                "id": name, "createdAt": data.get("createdAt"),
                "versionId": data.get("versionId"),
                "versionNumber": data.get("versionNumber"),
                "versionStatus": data.get("versionStatus"),
                "sha256": data.get("sha256"),
                "reason": data.get("reason"),
            })
        if len(backups) >= 50:
            break
    return {"ok": True, "backups": backups}


def compare_cml(source_org, target_org, model, source_version_id,
                target_version_id):
    """Fetch the same CML from two orgs so the UI can diff them."""
    if (not source_org or not target_org or not model
            or not source_version_id or not target_version_id):
        return {"ok": False, "log": (
            "Select an exact source version and exact target version before "
            "comparing CML.")}
    # Fetch sequentially: the `sf` CLI serializes on its own config/lock files,
    # so running two at once can hang. One after the other is reliable.
    src = _download_cml(
        source_org, model, source_version_id,
        os.path.join(
            DOWNLOAD_DIR,
            f"{_safe(model)}__{_safe(source_org)}__{_safe(source_version_id)}.cml"))
    tgt = _download_cml(
        target_org, model, target_version_id,
        os.path.join(
            DOWNLOAD_DIR,
            f"{_safe(model)}__{_safe(target_org)}__{_safe(target_version_id)}.cml"))

    # A truly empty version is informative for a comparison,
    # so treat empty as a non-fatal result and still return its content ("").
    def norm(res, org, version_id):
        if res.get("ok") or res.get("empty"):
            return {"org": org, "content": res.get("content", ""),
                    "versionId": version_id, "file": res.get("file"),
                    "versionNumber": res.get("versionNumber"),
                    "versionStatus": res.get("versionStatus"),
                    "log": res.get("log", "")}
        return None

    s = norm(src, source_org, source_version_id)
    t = norm(tgt, target_org, target_version_id)
    if s is None:
        return {"ok": False, "log": f"Could not fetch from source '{source_org}':\n{src.get('log')}"}
    if t is None:
        return {"ok": False, "log": f"Could not fetch from target '{target_org}':\n{tgt.get('log')}"}
    try:
        semantic = compare_cml_semantics(
            s.get("content", ""), t.get("content", ""))
    except Exception as exc:  # noqa: BLE001
        # Semantic analysis is supplemental and must never block the raw diff.
        semantic = {
            "schemaVersion": "1.0",
            "entities": [],
            "stats": {
                "UNCHANGED": 0, "MOVED": 0, "ADDED": 0,
                "REMOVED": 0, "MODIFIED": 0, "AMBIGUOUS": 0,
            },
            "sourceParseIssues": [],
            "targetParseIssues": [],
            "analysisError": str(exc),
        }
    return {
        "ok": True,
        "model": model,
        "source": s,
        "target": t,
        "semantic": semantic,
    }


# ---------------------------------------------------------------------------
# Constraint data (ExpressionSetConstraintObj) — visualize & compare
#
# Each row links a CML (ExpressionSet) to a Product / ProductClassification /
# ProductRelatedComponent via a polymorphic lookup
# (ReferenceObjectId). Record Ids differ per org, so rows are made portable by
# keying on the reference object's Global_Key__c (stable across orgs) plus the
# tag + tag type. See README for the mapping rationale.
# ---------------------------------------------------------------------------

# Object types ReferenceObjectId can point to (all carry Global_Key__c).
REF_TYPES = ("Product2", "ProductClassification", "ProductRelatedComponent")


def _soql_str(value):
    """Escape a value for safe inclusion in a single-quoted SOQL literal."""
    return (value or "").replace("\\", "\\\\").replace("'", "\\'")


# The field used to match reference records across orgs. Defaults to the custom
# Global_Key__c, but any field can be chosen so orgs without that field can use
# their own foreign key (e.g. an external Id, a code, or even Name).
DEFAULT_KEY_FIELD = "Global_Key__c"
_FIELD_PROBE = {}  # (org, sobject, field) -> (bool, expiry monotonic time)
_ESCO_CAPABILITY = {}  # (org, instance) -> (error_or_none, expiry monotonic time)


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


def _esco_capability_preflight(org, _retried=False):
    """Verify ESCO is queryable in this org at the minimum supported API.

    Successful and definitively unavailable results are cached briefly.
    Authentication and indeterminate/transient failures are never cached.
    """
    token, instance, err = _org_creds(org)
    if err:
        return err
    cache_key = (org, instance)
    cached = _ESCO_CAPABILITY.get(cache_key)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
           "ExpressionSetConstraintObj/describe")
    description, err = _rest("GET", url, token)
    if err and _is_auth_error(err) and not _retried:
        _org_creds(org, refresh=True)
        return _esco_capability_preflight(org, _retried=True)
    if err and _is_auth_error(err):
        return _auth_help(org, err)

    unavailable = err and any(marker in err for marker in (
        "INVALID_TYPE", "NOT_FOUND", "404",
        "sObject type 'ExpressionSetConstraintObj' is not supported",
    ))
    if unavailable or (not err and not (description or {}).get("queryable")):
        detail = err or "The object describe response reports queryable=false."
        message = (
            f"ExpressionSetConstraintObj is unavailable or not queryable in "
            f"'{org}' at API {API_VERSION}. Revenue Cloud/Product Configurator "
            "must be enabled and the selected user must be able to query this "
            "object before association compare, export, deploy, or restore "
            f"operations can run.\nDetails: {detail}"
        )
        _ESCO_CAPABILITY[cache_key] = (
            message, time.monotonic() + ESCO_CAPABILITY_TTL)
        return message
    if err:
        return (
            f"Could not verify ExpressionSetConstraintObj capability in '{org}' "
            f"at API {API_VERSION} because Salesforce returned an indeterminate "
            "or transient service error. This failure was not cached; "
            f"retry the operation.\nDetails: {err}"
        )

    _ESCO_CAPABILITY[cache_key] = (
        None, time.monotonic() + ESCO_CAPABILITY_TTL)
    return None


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


def export_constraints(org, model, version_id,
                       key_field=DEFAULT_KEY_FIELD):
    """Return enriched ExpressionSetConstraintObj rows for one CML model.

    Each row is resolved to its reference object's type + the chosen `key_field`
    (default Global_Key__c) so it can be matched across orgs regardless of Ids.
    """
    if not org or not model or not version_id:
        return {"ok": False, "log": (
            "Select an exact version before loading constraint data.")}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    capability_err = _esco_capability_preflight(org)
    if capability_err:
        return {"ok": False, "log": capability_err}
    version, expression_set_id, ownership_err = _exact_expression_set(
        org, model, version_id)
    if ownership_err:
        return {"ok": False, "log": (
            "Constraint data could not be scoped to the selected exact "
            f"version:\n{ownership_err}")}
    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name. Use a plain "
            "field name like Global_Key__c, ProductCode, External_Id__c, or Name.")}

    typeof, field_on = _build_typeof(org, kf)
    if not any(field_on.values()):
        return {"ok": False, "log": (
            f"None of the reference objects (Product2, ProductClassification, "
            f"ProductRelatedComponent) have a field named "
            f"\u201c{kf}\u201d in {org}. Pick a field that exists on them "
            f"(Name may be selected only when it is present and uniquely "
            f"portable in both orgs), then try again.")}

    soql = (
        "SELECT Id, ExpressionSetId, ExpressionSet.Name, ExpressionSet.ApiName, "
        "ExpressionSet.ExpressionSetDefinition.DeveloperName, ConstraintModelTag, "
        "ConstraintModelTagType, ReferenceObjectId, " + typeof +
        "FROM ExpressionSetConstraintObj "
        "WHERE ExpressionSetId = '" + _soql_str(expression_set_id) + "' "
        "ORDER BY ConstraintModelTagType, ConstraintModelTag"
    )
    records, err = _query_json(org, soql)
    if err:
        return {"ok": False, "log": f"Could not load constraint data from {org}:\n{err}"}

    rows = []
    scope_api_name = None
    scope_definition_name = None
    for rec in records:
        expression_set = rec.get("ExpressionSet") or {}
        definition = expression_set.get("ExpressionSetDefinition") or {}
        observed_api_name = expression_set.get("ApiName")
        observed_definition_name = definition.get("DeveloperName")
        scope_api_name = scope_api_name or observed_api_name
        scope_definition_name = (
            scope_definition_name or observed_definition_name)
        if ((observed_api_name and observed_api_name != model)
                or (observed_definition_name
                    and observed_definition_name != model)):
            return {"ok": False, "log": (
                "Constraint-data scope changed while it was being queried. "
                f"Selected model '{model}' resolved to ExpressionSet "
                f"'{expression_set_id}', but Salesforce returned ApiName "
                f"'{observed_api_name}' and definition DeveloperName "
                f"'{observed_definition_name}'. Refresh versions and retry.")}
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
        if row["refType"] == "ProductRelatedComponent":
            row["prcIdentityVersion"] = PRC_IDENTITY_VERSION
        if detail:
            row["prcIdentity"] = prc_identity
            row["prcIdentityError"] = detail.get("identityError")
            row["prcDetail"] = {
                key: value for key, value in detail.items()
                if key not in ("id", "sourceOrg", "identity", "identityError")
            }
            row["prcParentName"] = detail.get("parentName")
            row["prcChildName"] = detail.get("childName")
            row["prcRelationshipType"] = detail.get("relationshipTypeName")
        elif row["refType"] == "ProductRelatedComponent":
            row["prcIdentityError"] = (
                "ProductRelatedComponent details could not be queried; exact "
                "portable identity is not established.")
        portable_ref = prc_identity if row["refType"] == "ProductRelatedComponent" else row.get("gkey")
        row["mappable"] = bool(portable_ref)
        row["key"] = _constraint_key(
            row.get("tagType"), row.get("tag"), row.get("refType"), portable_ref)
        if not row["mappable"]:
            unmapped += 1

    used_tags, duplicate_tags_error = _cml_used_tags(
        org, model, version["Id"])
    if duplicate_tags_error:
        for row in rows:
            row["dups"] = []
        dup_stats = {"exact": 0, "tag": 0, "ref": 0, "name": 0}
    else:
        dup_stats = _flag_duplicates_for_selected_cml(
            rows, expression_set_id, used_tags)
    return {"ok": True, "org": org, "model": model,
            "versionId": version["Id"],
            "versionNumber": version.get("VersionNumber"),
            "versionStatus": version.get("Status"),
            "expressionSetId": expression_set_id,
            "expressionSetApiName": scope_api_name or model,
            "expressionSetDefinitionDeveloperName": (
                scope_definition_name or model),
            "associationScope": "ExpressionSet",
            "associationScopeNote": (
                "Association data is shared at the ExpressionSet level; it is "
                "not version-specific."),
            "duplicateScope": {
                "model": model,
                "versionId": version["Id"],
                "expressionSetId": expression_set_id,
                "note": (
                    "Duplicate flags are calculated only for associations whose "
                    "tags are used by this exact selected CML version, within "
                    "its resolved parent ExpressionSet.")
            },
            "duplicateCheckError": duplicate_tags_error,
            "rows": rows,
            "keyField": kf,
            "stats": {"total": len(rows), "unmappable": unmapped,
                      "duplicates": dup_stats}}


def _flag_duplicates(rows, expression_set_id=None):
    """Annotate duplicates inside one selected parent Expression Set only.

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
    for r in rows:
        r["dups"] = []
    scoped = [
        (i, r) for i, r in enumerate(rows)
        if not expression_set_id
        or r.get("expressionSetId") == expression_set_id
    ]
    for i, r in scoped:
        by_exact[r["key"]].append(i)
        by_tag[(r["tagType"], r["tag"])].append(i)
        if r["gkey"]:
            by_ref[(r["refType"], r["gkey"])].append(i)
        if r["refName"]:
            by_name[(r["refType"], r["refName"])].append(i)

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


def _flag_duplicates_for_selected_cml(
        rows, expression_set_id, used_tags):
    """Flag only associations used by the exact CML selected by the user."""
    for row in rows:
        row["dups"] = []
    selected_rows = [
        row for row in rows
        if _row_used_by_cml(row, used_tags)
    ]
    return _flag_duplicates(selected_rows, expression_set_id)


def _target_key_candidates(target_org, needed, key_field):
    """Return every target Id found for each requested portable reference key.

    Keeping the complete candidate list lets comparison distinguish a unique
    deployable match from an ambiguous key before the user selects the row.
    Deployment still repeats this lookup immediately before DML.
    """
    candidates = {}
    for ref_type, keys in needed.items():
        keys = [g for g in keys if g]
        if not keys:
            continue
        for i in range(0, len(keys), 200):  # keep IN-lists well under limits
            chunk = keys[i:i + 200]
            in_list = ",".join("'" + _soql_str(g) + "'" for g in chunk)
            soql = (f"SELECT Id, {key_field} FROM {ref_type} "
                    f"WHERE {key_field} IN ({in_list})")
            recs, err = _query_json(target_org, soql)
            if err:  # treat as unknown rather than blocking the whole compare
                continue
            for r in recs:
                key = (ref_type, r.get(key_field))
                if key[1]:
                    candidates.setdefault(key, []).append(r.get("Id"))
    return candidates


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


_PRC_STABLE_FIELDS = (
    "Quantity", "Sequence", "DoesBundlePriceIncludeChild",
    "QuantityScaleMethod", "MaxQuantity", "MinQuantity",
    "IsComponentRequired", "IsQuantityEditable", "IsDefaultComponent",
    "QuoteVisibility",
)


def _canonical_identity_scalar(value):
    """Normalize REST scalars without relying on Python/JSON coercion quirks."""
    if value is None:
        return None
    if isinstance(value, bool):
        return {"type": "boolean", "value": value}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        text = format(value, ".15g") if isinstance(value, float) else str(value)
        return {"type": "number", "value": text}
    if isinstance(value, str):
        return {"type": "string", "value": value}
    return {
        "type": type(value).__name__,
        "value": json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), default=str),
    }


def _prc_identity_from_detail(detail):
    """Return the v2 exact portable identity, or a fail-closed mapping error."""
    required = (
        ("parentId", "parentKey", "parent product"),
        ("childId", "childKey", "child product/classification"),
        ("relationshipTypeId", "relationshipTypeName", "relationship type"),
        ("groupId", "groupKey", "component group"),
        ("parentSellingModelId", "parentSellingModelKey",
         "parent selling model"),
        ("childSellingModelId", "childSellingModelKey",
         "child selling model"),
    )
    missing = []
    for id_field, portable_field, label in required:
        if detail.get(id_field) and not detail.get(portable_field):
            missing.append(label)
    if not detail.get("parentKey"):
        missing.append("parent product")
    if not detail.get("childKind") or not detail.get("childKey"):
        missing.append("child endpoint")
    if not detail.get("relationshipTypeName"):
        missing.append("relationship type")
    if missing:
        labels = ", ".join(sorted(set(missing)))
        return None, (
            "Cannot establish the complete portable PRC identity; missing "
            f"portable identity for: {labels}.")

    canonical = {
        "version": PRC_IDENTITY_VERSION,
        "parentKey": _canonical_identity_scalar(detail.get("parentKey")),
        "child": {
            "kind": _canonical_identity_scalar(detail.get("childKind")),
            "key": _canonical_identity_scalar(detail.get("childKey")),
        },
        "relationshipType": _canonical_identity_scalar(
            detail.get("relationshipTypeName")),
        "componentGroup": _canonical_identity_scalar(detail.get("groupKey")),
        "sellingModelContext": {
            "parent": _canonical_identity_scalar(
                detail.get("parentSellingModelKey")),
            "child": _canonical_identity_scalar(
                detail.get("childSellingModelKey")),
        },
        "discriminators": {
            field: _canonical_identity_scalar(detail.get(field))
            for field in _PRC_STABLE_FIELDS
        },
    }
    return json.dumps(
        canonical, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False), None


def _prc_identity(parent_key, child_kind, child_key, relationship_type,
                  **discriminators):
    """Compatibility wrapper for callers/tests constructing a detailed PRC."""
    detail = {
        "parentKey": parent_key, "childKind": child_kind,
        "childKey": child_key, "relationshipTypeName": relationship_type,
        **discriminators,
    }
    return _prc_identity_from_detail(detail)[0]


def _prc_select_fields(org, kf):
    """Return safe PRC fields and endpoint capability flags for this org."""
    product_key = _field_exists(org, "Product2", kf)
    classification_key = _field_exists(org, "ProductClassification", kf)
    group_key = _field_exists(org, "ProductComponentGroup", kf)
    selling_model_key = _field_exists(org, "ProductSellingModel", kf)
    fields = ["Id", "Name"]
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
    for field in _PRC_STABLE_FIELDS:
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
    if selling_model_key:
        fields.extend([
            f"ParentSellingModel.{kf}", f"ChildSellingModel.{kf}"])
    return fields, {
        "product": product_key,
        "classification": classification_key,
        "group": group_key,
        "sellingModel": selling_model_key,
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
        "name": record.get("Name"),
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
        "parentSellingModelKey": parent_selling.get(kf),
        "parentSellingModelName": parent_selling.get("Name"),
        "childSellingModelId": record.get("ChildSellingModelId"),
        "childSellingModelKey": child_selling.get(kf),
        "childSellingModelName": child_selling.get("Name"),
    }
    for field in _PRC_STABLE_FIELDS:
        detail[field] = record.get(field)
    detail["identity"], detail["identityError"] = (
        _prc_identity_from_detail(detail))
    detail["prcIdentityVersion"] = PRC_IDENTITY_VERSION
    return detail


def _prc_details(org, prc_ref_ids, kf):
    """Return authoritative PRC endpoint/details keyed by PRC Id."""
    # Callers already selected rows whose polymorphic ReferenceObject type is
    # ProductRelatedComponent. Auto-number display prefixes such as PRC-/ECO-
    # are labels, not identity. Validate only the generic Salesforce Id shape.
    ids = sorted({
        str(x) for x in prc_ref_ids
        if x and re.fullmatch(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?", str(x))
    })
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


def compare_constraints(source_org, target_org, model, source_version_id,
                        target_version_id, key_field=DEFAULT_KEY_FIELD):
    """Compare constraint data of one CML between two orgs, keyed on the
    portable composite key. Returns matched / source-only / target-only rows
    plus, for source-only rows, whether the reference record exists in target.
    """
    if (not source_org or not target_org or not model
            or not source_version_id or not target_version_id):
        return {"ok": False, "log": (
            "Select an exact source version and exact target version before "
            "comparing constraint data.")}
    for capability_org in (source_org, target_org):
        capability_err = _esco_capability_preflight(capability_org)
        if capability_err:
            return {"ok": False, "log": capability_err}

    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name. Use a plain "
            "field name like Global_Key__c, ProductCode, External_Id__c, or Name.")}

    src = export_constraints(source_org, model, source_version_id, kf)
    if not src.get("ok"):
        return src
    tgt = export_constraints(target_org, model, target_version_id, kf)
    if not tgt.get("ok"):
        return tgt

    source_tags, tags_err = _cml_used_tags(
        source_org, model, source_version_id)
    if tags_err:
        return {"ok": False, "log": (
            f"Could not read the source CML in {source_org}, so association "
            f"deployment was stopped safely:\n{tags_err}")}
    target_tags, tags_err = _cml_used_tags(
        target_org, model, target_version_id)
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

    # Preserve every row. A dict comprehension would silently collapse exact
    # duplicates that share the same portable comparison key.
    from collections import defaultdict
    src_groups, tgt_groups = defaultdict(list), defaultdict(list)
    for row in active_source:
        src_groups[row["key"]].append(row)
    for row in active_target:
        tgt_groups[row["key"]].append(row)
    all_keys = list(dict.fromkeys(
        [row["key"] for row in active_source + active_target]))

    def source_surplus():
        for key in all_keys:
            source_rows = src_groups.get(key, [])
            paired = min(len(source_rows), len(tgt_groups.get(key, [])))
            yield from source_rows[paired:]

    dependency_issues = _classification_dependency_audit(
        source_org, target_org, active_source, active_target, kf)

    def apply_dependency_preflight(raw):
        row = dict(raw)
        found = dependency_issues.get((row.get("refType"), row.get("gkey")), [])
        if found and row.get("deployStatus") not in (
                "cml-difference", "exact-duplicate"):
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
    for r in source_surplus():
        if (r["mappable"] and "exact" not in (r.get("dups") or [])
                and r["refType"] != "ProductRelatedComponent"):
            needed.setdefault(r["refType"], set()).add(r["gkey"])
    target_key_candidates = _target_key_candidates(target_org, needed, kf)

    # Canonical PRC identities are used for the main comparison key. For PRCs
    # that are genuinely source-only, locate any existing target relationship
    # again so the UI can distinguish "ready" from "must create prerequisite".
    source_only_prc_rows = [
        r for r in source_surplus()
        if r["refType"] == "ProductRelatedComponent"
        and "exact" not in (r.get("dups") or [])
        and r.get("prcIdentity")
    ]
    src_prc_details = _prc_details(
        source_org,
        [r.get("refId") for r in source_only_prc_rows],
        kf)
    target_prcs = _target_prc_by_identity(
        target_org, list(src_prc_details.values()), kf)

    matched, source_only, target_only = [], [], []
    for key in all_keys:
        source_rows = src_groups.get(key, [])
        target_rows = tgt_groups.get(key, [])
        paired = min(len(source_rows), len(target_rows))
        for index, r in enumerate(source_rows[:paired]):
            target_row = target_rows[index]
            row = dict(r)
            # Display names are live labels, not portable identity. Preserve
            # both org values so a Salesforce auto-number/name-format change
            # (for example PRC-* to ECO-*) is shown accurately without
            # affecting matching.
            row["sourceRefName"] = r.get("refName")
            row["sourceRefCode"] = r.get("refCode")
            row["targetRefName"] = target_row.get("refName")
            row["targetRefCode"] = target_row.get("refCode")
            row["referenceNamesDiffer"] = (
                r.get("refName") != target_row.get("refName")
                or r.get("refCode") != target_row.get("refCode")
            )
            row["matchedEvidence"] = {
                "portableKeyEqual": r.get("key") == target_row.get("key"),
                "source": {
                    "constraintId": r.get("id"),
                    "expressionSetId": r.get("expressionSetId"),
                    "referenceId": r.get("refId"),
                    "referenceName": r.get("refName"),
                    "referenceCode": r.get("refCode"),
                },
                "target": {
                    "constraintId": target_row.get("id"),
                    "expressionSetId": target_row.get("expressionSetId"),
                    "referenceId": target_row.get("refId"),
                    "referenceName": target_row.get("refName"),
                    "referenceCode": target_row.get("refCode"),
                },
            }
            matched.append(apply_dependency_preflight(row))
        for r in source_rows[paired:]:
            row = dict(r)
            if "exact" in (r.get("dups") or []):
                row["deployStatus"] = "exact-duplicate"
                row["blockNote"] = (
                    "Skipped — exact duplicate. The source contains multiple "
                    "identical associations. Remove the duplicate in the source "
                    "before deploying this association.")
            elif not r["mappable"]:
                row["deployStatus"] = "unmappable"
            elif not _row_used_by_cml(r, target_tags):
                row["deployStatus"] = "cml-difference"
                row["blockNote"] = (
                    f"The source CML defines {r.get('tagType')} "
                    f"'{r.get('tag')}', but the target CML does not. Compare "
                    "and deploy the intended CML code first; this association "
                    "is not safe to add yet.")
            elif len(target_key_candidates.get(
                    (r["refType"], r["gkey"]), [])) == 1:
                row["deployStatus"] = "ready"
            elif len(target_key_candidates.get(
                    (r["refType"], r["gkey"]), [])) > 1:
                candidates = target_key_candidates[
                    (r["refType"], r["gkey"])]
                row["deployStatus"] = "ambiguous-key"
                row["targetCandidateIds"] = candidates
                row["blockNote"] = (
                    f"Blocked — ambiguous key. The configured {kf} value "
                    f"matches {len(candidates)} target {r['refType']} records. "
                    "Make the portable key unique in the target org, then "
                    "compare again.")
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
                            f"{relation}. Conflicting Ids: "
                            f"{', '.join(candidates)}. Resolve duplicates before "
                            "deployment."
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
        for r in target_rows[paired:]:
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
        "sourceVersionId": source_version_id,
        "targetVersionId": target_version_id,
        "associationsShared": (
            source_org == target_org
            and src.get("expressionSetId") == tgt.get("expressionSetId")),
        "associationScopeNote": (
            "Association data is shared at the ExpressionSet level; it is not "
            "version-specific."
        ),
        "source": {"org": source_org, "total": len(src["rows"]),
                   "versionId": source_version_id,
                   "expressionSetId": src.get("expressionSetId"),
                   "expressionSetApiName": src.get("expressionSetApiName"),
                   "expressionSetDefinitionDeveloperName": src.get(
                       "expressionSetDefinitionDeveloperName"),
                   "duplicateScope": src.get("duplicateScope"),
                   "duplicateCheckError": src.get("duplicateCheckError"),
                   "duplicates": src["stats"]["duplicates"]},
        "target": {"org": target_org, "total": len(tgt["rows"]),
                   "versionId": target_version_id,
                   "expressionSetId": tgt.get("expressionSetId"),
                   "expressionSetApiName": tgt.get("expressionSetApiName"),
                   "expressionSetDefinitionDeveloperName": tgt.get(
                       "expressionSetDefinitionDeveloperName"),
                   "duplicateScope": tgt.get("duplicateScope"),
                   "duplicateCheckError": tgt.get("duplicateCheckError"),
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
            "exactDuplicates": sum(
                1 for r in matched + source_only + target_only
                if "exact" in (r.get("dups") or [])),
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
            "ambiguousKeys": sum(
                1 for r in source_only
                if r.get("deployStatus") == "ambiguous-key"),
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


def _constraint_ids_in_expression_set(org, expression_set_id, ids):
    """Reconfirm ESCO ownership immediately before destructive deletion."""
    present = set()
    for start in range(0, len(ids), 200):
        values = ",".join(
            "'" + _soql_str(record_id) + "'"
            for record_id in ids[start:start + 200])
        records, err = _query_json(
            org,
            "SELECT Id FROM ExpressionSetConstraintObj "
            f"WHERE Id IN ({values}) AND ExpressionSetId = '"
            + _soql_str(expression_set_id) + "'")
        if err:
            return None, err
        present.update(record.get("Id") for record in records)
    return present, None


def _archive_associations(org, model, version_id, expression_set_id,
                          key_field, rows, expression_set_status=None):
    return _write_json_artifact(
        ARCHIVE_DIR, f"{org}__{model}__deleted-associations", {
            "kind": "association-delete-archive",
            "targetOrg": org, "model": model, "versionId": version_id,
            "expressionSetId": expression_set_id, "keyField": key_field,
            "expressionSetStatus": expression_set_status,
            "prcIdentityVersion": PRC_IDENTITY_VERSION,
            "rows": rows,
        })


def _archived_prc_detail(row):
    """Rebuild v2 PRC identity evidence; reject weak legacy archives."""
    detail = row.get("prcDetail")
    if not isinstance(detail, dict):
        required = {
            "parentId", "parentKey", "childKind", "childId", "childKey",
            "relationshipTypeId", "relationshipTypeName",
            "groupId", "groupKey", "parentSellingModelId",
            "parentSellingModelKey", "parentSellingModelName",
            "childSellingModelId", "childSellingModelKey",
            "childSellingModelName", *_PRC_STABLE_FIELDS,
        }
        if not required.issubset(row):
            return None, (
                "Archive is incompatible with PRC identity v2: this legacy "
                "row lacks the detailed relationship discriminators required "
                "for an exact restore. Recreate the archive with this tool "
                "version; the old weak identity will not be used.")
        detail = {field: row.get(field) for field in required}
    missing_fields = [
        field for field in _PRC_STABLE_FIELDS if field not in detail
    ]
    if missing_fields:
        return None, (
            "Archive is incompatible with PRC identity v2: detailed PRC "
            "evidence is missing " + ", ".join(missing_fields) + ".")
    identity, identity_err = _prc_identity_from_detail(detail)
    if identity_err:
        return None, "Archived PRC is unmappable: " + identity_err
    return {**detail, "identity": identity,
            "prcIdentityVersion": PRC_IDENTITY_VERSION}, None


def _restore_association_archive_unlocked(
        org, model, version_id, archive_id, confirm_target=None):
    """Restore absent ESCO rows from a tool-created deletion archive."""
    if not version_id:
        return {"ok": False, "log": (
            "Select an exact target version before restoring association data.")}
    if confirm_target != org:
        return {"ok": False, "log": (
            f"Production safety check failed. Type the target org alias exactly: {org}")}
    capability_err = _esco_capability_preflight(org)
    if capability_err:
        return {"ok": False, "log": capability_err}
    archive, err = _read_json_artifact(ARCHIVE_DIR, archive_id)
    if err:
        return {"ok": False, "log": err}
    version, current_expression_set_id, ownership_err = _exact_expression_set(
        org, model, version_id)
    if ownership_err:
        return {"ok": False, "log": ownership_err}
    expression_set_status, status_err = _expression_set_write_status(
        org, current_expression_set_id, "Association restore", version["Id"])
    if status_err:
        return {
            "ok": False, "expressionSetId": current_expression_set_id,
            "expressionSetStatus": expression_set_status, "log": status_err,
        }
    if (archive.get("kind") != "association-delete-archive"
            or archive.get("targetOrg") != org
            or archive.get("model") != model
            or archive.get("versionId") != version_id
            or archive.get("expressionSetId") != current_expression_set_id):
        return {"ok": False, "log": (
            "Association archive does not belong to the selected exact target "
            "version and its current ExpressionSet parent.")}
    key_field = archive.get("keyField") or DEFAULT_KEY_FIELD
    current = export_constraints(org, model, version_id, key_field)
    if not current.get("ok"):
        return current
    current_keys = {row.get("key") for row in current["rows"]}
    archived_rows = archive.get("rows") or []

    # Resolve references from portable identities at restore time. Never trust
    # an archived Salesforce Id: the catalog record may have been recreated.
    reference_candidates = {}
    needed = {}
    for row in archived_rows:
        if row.get("refType") != "ProductRelatedComponent" and row.get("gkey"):
            needed.setdefault(row.get("refType"), set()).add(row.get("gkey"))
    for ref_type, keys in needed.items():
        if not _field_exists(org, ref_type, key_field):
            continue
        key_list = sorted(keys)
        for start in range(0, len(key_list), 200):
            chunk = key_list[start:start + 200]
            values = ",".join(
                "'" + _soql_str(value) + "'" for value in chunk)
            records, query_err = _query_json(
                org,
                f"SELECT Id, {key_field} FROM {ref_type} "
                f"WHERE {key_field} IN ({values})")
            if query_err:
                return {"ok": False, "log": (
                    f"Association restore stopped because current {ref_type} "
                    f"references could not be resolved:\n{query_err}")}
            for record in records:
                reference_candidates.setdefault(
                    (ref_type, record.get(key_field)), []).append(record["Id"])

    archived_prc_details = []
    archive_identity_errors = {}
    for row in archived_rows:
        if row.get("refType") != "ProductRelatedComponent":
            continue
        detail, detail_err = _archived_prc_detail(row)
        if detail_err:
            archive_identity_errors[id(row)] = detail_err
            continue
        row["prcIdentity"] = detail["identity"]
        row["prcIdentityVersion"] = PRC_IDENTITY_VERSION
        row["key"] = _constraint_key(
            row.get("tagType"), row.get("tag"), row.get("refType"),
            detail["identity"])
        archived_prc_details.append(detail)
    prc_candidates = _target_prc_by_identity(
        org, archived_prc_details, key_field)

    records, labels, skipped = [], [], []
    for row in archived_rows:
        label = f"{row.get('tagType')} · {row.get('tag')} → {row.get('refName') or row.get('refId')}"
        if _freeze_json_value(row.get("key")) in current_keys:
            skipped.append({"success": True, "label": label,
                            "skipped": True, "error": None})
            continue
        if row.get("refType") == "ProductRelatedComponent":
            if id(row) in archive_identity_errors:
                skipped.append({
                    "success": False, "label": label,
                    "prcIdentityVersion": PRC_IDENTITY_VERSION,
                    "error": archive_identity_errors[id(row)],
                })
                continue
            identity = row.get("prcIdentity") or ""
            candidates = prc_candidates.get(identity, [])
        else:
            candidates = reference_candidates.get(
                (row.get("refType"), row.get("gkey")), [])
        if len(candidates) != 1:
            skipped.append({"success": False, "label": label,
                            "error": (
                                "Restore blocked — expected exactly one current "
                                f"{row.get('refType') or 'reference'} match but "
                                f"found {len(candidates)}. Conflicting Ids: "
                                f"{', '.join(candidates) if candidates else 'none'}.")})
            continue
        reference_id = candidates[0]
        records.append({
            "attributes": {"type": "ExpressionSetConstraintObj"},
            "ExpressionSetId": current_expression_set_id,
            "ReferenceObjectId": reference_id,
            "ConstraintModelTag": row.get("tag"),
            "ConstraintModelTagType": row.get("tagType"),
        })
        labels.append(label)
    token, instance, err = _org_creds(org)
    if err:
        return {"ok": False, "log": err}
    restored = list(skipped)
    if records:
        expression_set_status, status_err = _expression_set_write_status(
            org, current_expression_set_id, "Association restore", version["Id"])
        if status_err:
            restored.extend({
                "success": False, "label": label, "error": status_err,
            } for label in labels)
            records = []
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
            "versionId": version["Id"],
            "expressionSetId": current_expression_set_id,
            "expressionSetStatus": expression_set_status,
            "versionStatus": version.get("Status"),
            "prcIdentityVersion": PRC_IDENTITY_VERSION,
            "results": restored,
        })
    return {
        "ok": fail_count == 0, "target": org, "model": model,
        "versionId": version["Id"],
        "expressionSetId": current_expression_set_id,
        "expressionSetStatus": expression_set_status,
        "versionStatus": version.get("Status"),
        "prcIdentityVersion": PRC_IDENTITY_VERSION,
        "restored": restored, "report": report, "reportError": report_err,
        "stats": {"restoreOk": success_count, "restoreFail": fail_count},
        "log": (
            f"Association recovery finished: {success_count} restored/already "
            f"present, {fail_count} failed."),
    }


def restore_association_archive(org, model, version_id, archive_id,
                                confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _restore_association_archive_unlocked(
            org, model, version_id, archive_id, confirm_target))


def _deploy_constraints_unlocked(
        source_org, target_org, model, source_version_id, target_version_id,
        adds, deletes,
        key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    """Insert selected source-only constraints and delete selected target-only
    ones. Each item is handled individually so per-row results can be shown.

    adds:    [{sourceConstraintId}] (all other source data is reloaded server-side)
    deletes: [{id, refName, tag, tagType}]             (target record Ids)
    """
    if not target_org:
        return {"ok": False, "log": "No target org."}
    if not source_version_id or not target_version_id:
        return {"ok": False, "log": (
            "Select an exact source version and exact target version before "
            "deploying constraint data.")}
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
    comparison = compare_constraints(
        source_org, target_org, model, source_version_id,
        target_version_id, kf)
    if not comparison.get("ok"):
        return comparison
    cml_version, target_expression_set_id, cml_err = _exact_expression_set(
        target_org, model, target_version_id)
    if cml_err:
        return {"ok": False, "log": (
            "Deployment stopped because the target CML version could not be "
            f"resolved for backup:\n{cml_err}")}
    target_expression_set_status, status_err = _expression_set_write_status(
        target_org, target_expression_set_id, "Association deployment",
        cml_version["Id"])
    if status_err:
        return {
            "ok": False, "outcome": "rejected",
            "targetExpressionSetId": target_expression_set_id,
            "targetExpressionSetStatus": target_expression_set_status,
            "targetVersionStatus": cml_version.get("Status"),
            "log": status_err,
        }
    target_version_status, status_err = _version_write_status(
        target_org, cml_version["Id"],
        "Association deployment CML save/verification refresh")
    if status_err:
        return {
            "ok": False, "outcome": "rejected",
            "targetExpressionSetId": target_expression_set_id,
            "targetExpressionSetStatus": target_expression_set_status,
            "targetVersionStatus": target_version_status,
            "log": status_err,
        }
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
            if row.get("deployStatus") == "exact-duplicate":
                created.append({
                    "success": False, "skipped": True,
                    "status": "skipped-exact-duplicate", "label": label,
                    "error": row.get("blockNote") or (
                        "Skipped — exact duplicate."),
                })
                continue
            if row.get("deployStatus") != "ready":
                created.append({
                    "success": False, "label": label,
                    "error": row.get("blockNote") or (
                        "Catalog dependency preflight did not mark this "
                        "association as safe to deploy."),
                })
                continue
            selected.append(row)

        # Re-resolve the Expression Set, references, and classification
        # dependencies immediately before each <=200-row DML chunk. A catalog
        # change after one chunk therefore cannot silently affect later chunks.
        for chunk_start in range(0, len(selected), 200):
            selected_chunk = selected[chunk_start:chunk_start + 200]
            _, es_id, es_err = _exact_expression_set(
                target_org, model, target_version_id)
            if es_err:
                for row in selected_chunk:
                    created.append({
                        "success": False,
                        "label": (
                            f'{row.get("tagType")} · {row.get("tag")} → '
                            f'{row.get("refName") or row.get("gkey") or row.get("refId")}'),
                        "error": "Chunk blocked — current Expression Set could "
                                 f"not be resolved: {es_err}",
                    })
                continue
            chunk_es_status, chunk_status_err = _expression_set_write_status(
                target_org, es_id, "Association insert", cml_version["Id"])
            if chunk_status_err:
                for row in selected_chunk:
                    created.append({
                        "success": False,
                        "label": (
                            f'{row.get("tagType")} · {row.get("tag")} → '
                            f'{row.get("refName") or row.get("gkey") or row.get("refId")}'),
                        "prcIdentityVersion": row.get("prcIdentityVersion"),
                        "error": chunk_status_err,
                    })
                continue

            needed = {}
            for row in selected_chunk:
                if (row["refType"] != "ProductRelatedComponent"
                        and row.get("gkey")):
                    needed.setdefault(row["refType"], set()).add(row["gkey"])
            ref_map, resolution_errors = {}, {}
            for ref_type, keys in needed.items():
                key_list = list(keys)
                for start in range(0, len(key_list), 200):
                    key_chunk = key_list[start:start + 200]
                    in_list = ",".join(
                        "'" + _soql_str(value) + "'" for value in key_chunk)
                    recs, qerr = _query_json(
                        target_org,
                        f"SELECT Id, {kf} FROM {ref_type} "
                        f"WHERE {kf} IN ({in_list})")
                    if qerr:
                        resolution_errors[ref_type] = qerr
                        break
                    for record in recs:
                        ref_map.setdefault(
                            (ref_type, record.get(kf)), []).append(record["Id"])

            prc_details = _prc_details(
                source_org,
                [row.get("refId") for row in selected_chunk
                 if row["refType"] == "ProductRelatedComponent"],
                kf)
            target_prcs = _target_prc_by_identity(
                target_org, list(prc_details.values()), kf)

            resolved = []
            for row in selected_chunk:
                label = (
                    f'{row.get("tagType")} · {row.get("tag")} → '
                    f'{row.get("refName") or row.get("gkey") or row.get("refId")}'
                )
                if row.get("refType") in resolution_errors:
                    created.append({
                        "success": False, "label": label,
                        "error": "Blocked — catalog dependency changed. "
                                 + resolution_errors[row["refType"]],
                    })
                    continue
                if row["refType"] == "ProductRelatedComponent":
                    detail = prc_details.get(row.get("refId")) or {}
                    candidates = target_prcs.get(detail.get("identity"), [])
                else:
                    candidates = ref_map.get(
                        (row["refType"], row.get("gkey")), [])
                if len(candidates) != 1:
                    created.append({
                        "success": False, "label": label,
                        "error": (
                            "Blocked — ambiguous key. Expected exactly one "
                            f"current target {row['refType']} match but found "
                            f"{len(candidates)}. Conflicting Ids: "
                            f"{', '.join(candidates) if candidates else 'none'}."),
                    })
                    continue
                target_row = dict(row)
                target_row["refId"] = candidates[0]
                resolved.append((row, target_row, label, candidates[0]))

            chunk_dependency_issues = _classification_dependency_audit(
                source_org, target_org,
                [item[0] for item in resolved],
                [item[1] for item in resolved], kf)
            records, meta = [], []
            for row, _, label, ref_id in resolved:
                issues = chunk_dependency_issues.get(
                    (row.get("refType"), row.get("gkey")), [])
                if issues:
                    created.append({
                        "success": False, "label": label,
                        "error": (
                            "Blocked — catalog dependency changed. "
                            + " ".join(issue.get("message", "")
                                       for issue in issues)),
                    })
                    continue
                records.append({
                    "attributes": {"type": "ExpressionSetConstraintObj"},
                    "ExpressionSetId": es_id,
                    "ReferenceObjectId": ref_id,
                    "ConstraintModelTag": row.get("tag"),
                    "ConstraintModelTagType": row.get("tagType"),
                })
                meta.append((label, row))

            if records:
                results = _collections_insert(token, instance, records)
                for index, (label, source_row) in enumerate(meta):
                    if index >= len(results):
                        created.append({
                            "success": False, "label": label, "id": None,
                            "error": "Salesforce returned no result for this row.",
                        })
                        continue
                    result = results[index]
                    created.append({
                        "success": result["success"], "label": label,
                        "id": result.get("id"), "error": result.get("error"),
                        "prcIdentity": source_row.get("prcIdentity"),
                        "prcIdentityVersion": source_row.get(
                            "prcIdentityVersion"),
                    })

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
            target_expression_set_status, status_err = (
                _expression_set_write_status(
                    target_org, target_expression_set_id,
                    "Association deletion", cml_version["Id"]))
            if status_err:
                for rid in ids:
                    delete_results.append({
                        "success": False, "label": labels.get(rid, rid),
                        "id": rid, "error": status_err,
                    })
                ids = []
        if ids:
            verified_ids, verify_err = _constraint_ids_in_expression_set(
                target_org, target_expression_set_id, ids)
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
                    target_org, model, target_version_id,
                    target_expression_set_id, kf, archive_rows,
                    target_expression_set_status)
            except OSError as exc:
                for rid in ids:
                    delete_results.append({
                        "success": False, "label": labels.get(rid, rid),
                        "id": rid, "error": (
                            "Deletion stopped because its recovery archive could "
                            f"not be saved: {exc}"),
                    })
            else:
                for start in range(0, len(ids), 200):
                    delete_chunk = ids[start:start + 200]
                    target_expression_set_status, status_err = (
                        _expression_set_write_status(
                            target_org, target_expression_set_id,
                            "Association deletion", cml_version["Id"]))
                    if status_err:
                        for rid in delete_chunk:
                            delete_results.append({
                                "success": False,
                                "label": labels.get(rid, rid), "id": rid,
                                "error": status_err,
                            })
                        continue
                    current_ids, chunk_err = (
                        _constraint_ids_in_expression_set(
                            target_org, target_expression_set_id,
                            delete_chunk))
                    if chunk_err:
                        for rid in delete_chunk:
                            delete_results.append({
                                "success": False,
                                "label": labels.get(rid, rid), "id": rid,
                                "error": (
                                    "Deletion chunk blocked — ownership could "
                                    f"not be revalidated: {chunk_err}"),
                            })
                        continue
                    safe_chunk = []
                    for rid in delete_chunk:
                        if rid not in current_ids:
                            delete_results.append({
                                "success": False,
                                "label": labels.get(rid, rid), "id": rid,
                                "error": (
                                    "Deletion blocked — association ownership "
                                    "changed before this chunk was written."),
                            })
                        else:
                            safe_chunk.append(rid)
                    if not safe_chunk:
                        continue
                    for result in _collections_delete(
                            token, instance, safe_chunk):
                        delete_results.append({
                            "success": result["success"],
                            "label": labels.get(
                                result.get("id"), result.get("id")),
                            "id": result.get("id"),
                            "error": result.get("error"),
                        })

    ins_ok = sum(1 for r in created if r["success"])
    del_ok = sum(1 for r in delete_results if r["success"])
    refresh = None
    changed = any(r.get("success") and r.get("id") for r in created)
    changed = changed or any(r.get("success") for r in delete_results)
    if changed:
        # Perform the tool-specific unchanged-blob save/verification after ESCO
        # changes. This does not activate/compile the model or prove runtime
        # behavior. Do not use catalog Sync, which can regenerate custom CML.
        if not (target_cml_before or "").strip():
            refresh = {
                "ok": False,
                "log": "Associations changed, but the target CML is empty; "
                       "the tool-specific save/verification refresh was not run.",
            }
        else:
            refresh = _refresh_cml_validation(
                target_org, model, target_cml_before, cml_version["Id"])
    insert_skipped = sum(1 for r in created if r.get("skipped"))
    insert_fail = len(created) - ins_ok - insert_skipped
    delete_fail = len(delete_results) - del_ok
    succeeded = ins_ok + del_ok
    failed = insert_fail + delete_fail
    refresh_failed = bool(changed and refresh and not refresh.get("ok"))
    outcome = "partial" if succeeded and (
        failed or insert_skipped or refresh_failed) else (
        "failed" if failed else ("skipped" if insert_skipped else "success"))
    overall_success = failed == 0 and not refresh_failed
    recovery_message = None
    if refresh_failed:
        recovery_message = (
            "RECOVERY REQUIRED — association records changed, but the "
            "tool-specific CML save/verification refresh failed. Runtime "
            "validation is not established. Review the per-row results, CML "
            "backup, deletion archive, and deployment report before recovery.")
    report, report_err = _try_deployment_report(
        "association-deploy", target_org, model, {
            "success": overall_success, "outcome": outcome,
            "sourceOrg": source_org, "keyField": kf,
            "sourceVersionId": source_version_id,
            "targetVersionId": target_version_id,
            "targetExpressionSetId": target_expression_set_id,
            "targetExpressionSetStatus": target_expression_set_status,
            "targetVersionStatus": target_version_status,
            "prcIdentityVersion": PRC_IDENTITY_VERSION,
            "requested": {
                "addSourceConstraintIds": [
                    row.get("sourceConstraintId") for row in adds],
                "deleteTargetConstraintIds": [row.get("id") for row in deletes],
            },
            "created": created, "deleted": delete_results,
            "cmlBackup": cml_backup, "deletionArchive": archive,
            "validationRefresh": refresh,
            "recoveryRequired": refresh_failed,
            "recoveryMessage": recovery_message,
        })
    return {
        "ok": overall_success, "processed": True,
        "model": model, "target": target_org,
        "sourceVersionId": source_version_id,
        "targetVersionId": target_version_id,
        "targetExpressionSetId": target_expression_set_id,
        "targetExpressionSetStatus": target_expression_set_status,
        "targetVersionStatus": target_version_status,
        "prcIdentityVersion": PRC_IDENTITY_VERSION,
        "associationScopeNote": (
            "Association data is shared at the ExpressionSet level; it is not "
            "version-specific."),
        "created": created, "deleted": delete_results,
        "refresh": refresh, "archive": archive, "backup": cml_backup,
        "report": report, "reportError": report_err, "outcome": outcome,
        "recoveryRequired": refresh_failed,
        "log": recovery_message,
        "stats": {
            "insertOk": ins_ok, "insertFail": insert_fail,
            "insertSkipped": insert_skipped,
            "deleteOk": del_ok, "deleteFail": delete_fail,
        },
    }


def deploy_constraints(source_org, target_org, model, source_version_id,
                       target_version_id, adds, deletes,
                       key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    try:
        result = _run_with_deployment_lock(
            target_org, model, lambda: _deploy_constraints_unlocked(
                source_org, target_org, model, source_version_id,
                target_version_id, adds, deletes,
                key_field, confirm_target))
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "log": f"Unexpected deployment error: {exc}"}

    failures = [
        {
            "label": row.get("label"),
            "reason": row.get("error"),
            "status": row.get("status"),
        }
        for row in (result.get("created") or []) + (result.get("deleted") or [])
        if not row.get("success")
    ]
    audit_entry = {
        "source_org": source_org,
        "target_org": target_org,
        "model": model,
        "source_version_id": source_version_id,
        "target_version_id": target_version_id,
        "key_field": key_field,
        "adds_attempted": len(adds or []),
        "adds_succeeded": (result.get("stats") or {}).get("insertOk", 0),
        "deletes_attempted": len(deletes or []),
        "deletes_succeeded": (result.get("stats") or {}).get("deleteOk", 0),
        "outcome": result.get("outcome") or (
            "rejected" if not result.get("ok") else "success"),
        "ok": bool(result.get("ok")),
        "target_expression_set_status": result.get(
            "targetExpressionSetStatus"),
        "target_version_status": result.get("targetVersionStatus"),
        "prc_identity_version": result.get("prcIdentityVersion"),
        "recovery_required": bool(result.get("recoveryRequired")),
        "blocked_rows": failures,
        "backup_file": (result.get("backup") or {}).get("file"),
        "archive_file": (result.get("archive") or {}).get("file"),
        "report_file": (result.get("report") or {}).get("file"),
        "message": result.get("log"),
    }
    try:
        _append_data_deploy_audit(audit_entry)
    except OSError as exc:
        result["auditError"] = f"Could not write deployment audit log: {exc}"
    return result


def _patch_cml_version(org, version_id, content):
    """PATCH one exact CML version. Backup/report policy belongs to callers."""
    _, status_err = _version_write_status(
        org, version_id, "CML PATCH")
    if status_err:
        return status_err
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


def _deploy_cml_unlocked(org, model, version_id, content,
                         confirm_target=None):
    """Back up, deploy and byte-verify one exact CML version."""
    if not org or not model or not version_id:
        return {"ok": False, "log": (
            "Select an exact target version before deploying CML.")}
    if confirm_target != org:
        return {"ok": False, "log": (
            f"Production safety check failed. Type the target org alias exactly: {org}")}
    if not content or not content.strip():
        return {"ok": False, "log": "There is no CML content to deploy."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    rec, err = resolve_exact_version(org, model, version_id)
    if err:
        return {"ok": False, "log": err}
    version_id = rec["Id"]
    observed_status, status_err = _version_write_status(
        org, version_id, "CML deployment")
    if status_err:
        return {
            "ok": False, "outcome": "rejected",
            "versionId": version_id, "versionStatus": observed_status,
            "log": status_err,
        }
    rec["Status"] = observed_status
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
                "versionStatus": rec.get("Status"),
                "runtimeValidated": False,
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
            "runtimeValidated": False,
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
            "versionId": version_id,
            "versionNumber": rec.get("VersionNumber"),
            "versionStatus": rec.get("Status"),
            "reportError": report_err, "verified": True,
            "runtimeValidated": False, "log": (
        f"SUCCESS — saved CML to '{model}' ({version_id}) in '{org}'.\n"
        f"Version status: {rec.get('Status')} · {lines} lines.\n"
        f"Verified persisted SHA-256: {_sha256_text(content)}\n"
        "Save verification does not activate/compile the model or prove "
        "runtime behavior.")}


def deploy_cml(org, model, version_id, content, confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _deploy_cml_unlocked(
            org, model, version_id, content, confirm_target))


def _rollback_cml_unlocked(org, model, version_id, backup_id,
                           confirm_target=None):
    if not version_id:
        return {"ok": False, "log": (
            "Select an exact target version before restoring a CML backup.")}
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
    rec, err = resolve_exact_version(org, model, version_id)
    if err:
        return {"ok": False, "log": err}
    if rec.get("Id") != backup_data.get("versionId"):
        return {"ok": False, "log": (
            "Rollback stopped because the backup belongs to another exact "
            "version. Select a backup for the selected target version.")}
    observed_status, status_err = _version_write_status(
        org, rec["Id"], "CML rollback")
    if status_err:
        return {
            "ok": False, "outcome": "rejected",
            "versionId": rec["Id"], "versionStatus": observed_status,
            "log": status_err,
        }
    rec["Status"] = observed_status
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
            "versionStatus": rec.get("Status"),
            "runtimeValidated": False,
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
            "runtimeValidated": False,
            "versionId": rec["Id"],
            "versionNumber": rec.get("VersionNumber"),
            "versionStatus": rec.get("Status"),
            "content": content, "log": (
                f"Rollback complete and verified for '{model}' in '{org}'.\n"
                f"Restored SHA-256: {_sha256_text(content)}\n"
                "Persistence verification does not activate/compile the model "
                "or prove runtime behavior.")}


def rollback_cml(org, model, version_id, backup_id,
                 confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _rollback_cml_unlocked(
            org, model, version_id, backup_id, confirm_target))


def _refresh_cml_validation(org, model, content, version_id=None):
    """Perform a tool-specific unchanged-CML save/verification refresh.

    An identical ConstraintModel PATCH may be optimized as a no-op. Save one
    temporary trailing blank line, restore the byte-exact original, and verify
    persistence. This does not activate the model, compile it, or prove runtime
    behavior.
    """
    if not version_id:
        return {"ok": False, "log": (
            "Select an exact target version before refreshing CML validation.")}
    rec, err = resolve_exact_version(org, model, version_id)
    if err:
        return {"ok": False, "log": err}
    observed_status, status_err = _version_write_status(
        org, rec["Id"], "CML save/verification refresh")
    if status_err:
        return {
            "ok": False, "versionStatus": observed_status,
            "log": status_err,
        }
    staged_err = _patch_cml_version(org, version_id, content + "\n")
    if staged_err:
        return {
            "ok": False,
            "log": "Could not stage the CML save/verification refresh:\n"
                   + staged_err,
        }
    restore_err = _patch_cml_version(org, version_id, content)
    if restore_err:
        return {
            "ok": False,
            "versionStatus": observed_status,
            "log": "The tool-specific refresh staged a temporary save, but the original byte-exact "
                   "content could not be restored:\n"
                   + restore_err,
        }
    verified, _, verify_err = _verify_cml_version(
        org, version_id, content)
    if not verified:
        return {"ok": False, "log": (
            "CML save/verification refresh finished, but byte-exact verification failed:\n"
            + (verify_err or "Restored content does not match."))}
    return {
        "ok": True,
        "versionStatus": observed_status,
        "runtimeValidated": False,
        "log": "Target CML completed the tool-specific save/verification "
               "refresh and was restored unchanged. This does not activate or "
               "compile the model and does not prove runtime behavior.",
    }


_CML_LOGIC_CALLS = {
    "constraint", "require", "exclude", "preference", "recommend", "rule",
    "setdefault", "message",
}
_CML_TOP_LEVEL = {"property", "extern", "define", "type"}
_CML_PRIMITIVES = {
    "boolean", "date", "decimal", "double", "float", "int", "integer", "long",
    "number", "string",
}
_CML_BUILTINS = {
    "abs", "all", "any", "cardinality", "count", "false", "max", "min",
    "null", "parent", "root", "self", "size", "sum", "this", "total",
    "true",
}


class _CmlToken:
    """Small source-aware token used by the tolerant CML parser."""

    __slots__ = ("kind", "value", "start", "end", "line", "column",
                 "end_line", "end_column")

    def __init__(self, kind, value, start, end, line, column,
                 end_line, end_column):
        self.kind = kind
        self.value = value
        self.start = start
        self.end = end
        self.line = line
        self.column = column
        self.end_line = end_line
        self.end_column = end_column


def _cml_range(start_token, end_token=None):
    """Return a JSON-safe half-open source range for one or more tokens."""
    end_token = end_token or start_token
    return {
        "start": {
            "offset": start_token.start,
            "line": start_token.line,
            "column": start_token.column,
        },
        "end": {
            "offset": end_token.end,
            "line": end_token.end_line,
            "column": end_token.end_column,
        },
    }


def _cml_diag(code, message, token, severity="warning", end_token=None,
              confidence="high"):
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "line": token.line,
        "column": token.column,
        "confidence": confidence,
        "sourceRange": _cml_range(token, end_token),
    }


def _tokenize_cml(content):
    """Tokenize CML while preserving exact offsets and source coordinates."""
    tokens = []
    diagnostics = []
    i, line, column = 0, 1, 1
    size = len(content)
    multi_ops = (
        "<->", "===", "!==", "->", "=>", "==", "!=", "<=", ">=", "&&",
        "||", "..", "::", "+=", "-=", "*=", "/=",
    )

    def advance_one():
        nonlocal i, line, column
        char = content[i]
        i += 1
        if char == "\n":
            line += 1
            column = 1
        else:
            column += 1

    def emit(kind, value, start, start_line, start_column):
        tokens.append(_CmlToken(
            kind, value, start, i, start_line, start_column, line, column))

    while i < size:
        char = content[i]
        if char.isspace():
            advance_one()
            continue
        start, start_line, start_column = i, line, column

        if content.startswith("//", i):
            while i < size and content[i] != "\n":
                advance_one()
            continue
        if content.startswith("/*", i):
            advance_one()
            advance_one()
            closed = False
            while i < size:
                if content.startswith("*/", i):
                    advance_one()
                    advance_one()
                    closed = True
                    break
                advance_one()
            if not closed:
                token = _CmlToken(
                    "COMMENT", content[start:i], start, i, start_line,
                    start_column, line, column)
                diagnostics.append(_cml_diag(
                    "unterminated-comment", "Unterminated block comment.",
                    token, "error"))
            continue
        if char in ('"', "'"):
            quote = char
            advance_one()
            escaped = False
            closed = False
            while i < size:
                current = content[i]
                if escaped:
                    escaped = False
                    advance_one()
                elif current == "\\":
                    escaped = True
                    advance_one()
                elif current == quote:
                    advance_one()
                    closed = True
                    break
                else:
                    advance_one()
            emit("STRING", content[start:i], start, start_line, start_column)
            if not closed:
                diagnostics.append(_cml_diag(
                    "unterminated-string", "Unterminated quoted string.",
                    tokens[-1], "error"))
            continue
        if char.isalpha() or char in "_$":
            advance_one()
            while i < size and (
                    content[i].isalnum() or content[i] in "_$"):
                advance_one()
            emit("IDENT", content[start:i], start, start_line, start_column)
            continue
        if char.isdigit() or (
                char == "." and i + 1 < size and content[i + 1].isdigit()):
            if char == ".":
                advance_one()
            while i < size and (
                    content[i].isdigit() or content[i] == "_"):
                advance_one()
            # Do not absorb the first dot of CML's cardinality operator (`..`).
            if (i < size and content[i] == "."
                    and not content.startswith("..", i)):
                advance_one()
                while i < size and (
                        content[i].isdigit() or content[i] == "_"):
                    advance_one()
            if i < size and content[i] in "eE":
                advance_one()
                if i < size and content[i] in "+-":
                    advance_one()
                while i < size and content[i].isdigit():
                    advance_one()
            emit("NUMBER", content[start:i], start, start_line, start_column)
            continue
        operator = next(
            (candidate for candidate in multi_ops
             if content.startswith(candidate, i)), None)
        if operator:
            for _ in operator:
                advance_one()
            emit("OP", operator, start, start_line, start_column)
            continue
        if char in "{}()[];,:.@":
            advance_one()
            emit("SYMBOL", char, start, start_line, start_column)
            continue
        if char in "+-*/%!<>=?&|^":
            advance_one()
            emit("OP", char, start, start_line, start_column)
            continue

        advance_one()
        emit("UNKNOWN", char, start, start_line, start_column)
        diagnostics.append(_cml_diag(
            "unknown-character", f"Unsupported character {char!r}.",
            tokens[-1], "warning"))

    tokens.append(_CmlToken(
        "EOF", "", size, size, line, column, line, column))
    return tokens, diagnostics


class _CmlParser:
    """Tolerant recursive-descent parser for declarations and logic calls."""

    _PRECEDENCE = {
        # Revenue Cloud Developer Guide PDF pp. 1032-1034: implication is
        # lowest; conditional, biconditional, OR, XOR, AND then bind tighter.
        "=": 0, "..": 0, "->": 1, "<->": 3, "||": 4, "or": 4,
        "^": 5, "&&": 6, "and": 6,
        "==": 7, "===": 7, "!=": 7, "!==": 7, "in": 7,
        "<": 8, "<=": 8, ">": 8, ">=": 8,
        "+": 9, "-": 9, "*": 10, "/": 10, "%": 10,
    }
    _RIGHT_ASSOCIATIVE = {"=", "->"}

    def __init__(self, content, tokens, diagnostics):
        self.content = content
        self.tokens = tokens
        self.diagnostics = diagnostics
        self.pos = 0
        self.declarations = []
        self.types = []
        self.logic = []
        self.unknown = []

    @property
    def current(self):
        return self.tokens[self.pos]

    @property
    def previous(self):
        return self.tokens[max(0, self.pos - 1)]

    def _at(self, value=None, kind=None):
        token = self.current
        return ((value is None or token.value == value)
                and (kind is None or token.kind == kind))

    def _at_ci(self, *values):
        return (self.current.kind == "IDENT"
                and self.current.value.lower()
                in {value.lower() for value in values})

    def _take(self):
        token = self.current
        if token.kind != "EOF":
            self.pos += 1
        return token

    def _match(self, *values):
        if self.current.value in values:
            return self._take()
        return None

    def _error(self, code, message, token=None, severity="warning"):
        self.diagnostics.append(_cml_diag(
            code, message, token or self.current, severity))

    def _raw(self, start, end=None):
        end = end or self.previous
        return self.content[start.start:end.end]

    def _node(self, kind, start, end=None, **values):
        end = end or self.previous
        node = {
            "kind": kind,
            "raw": self.content[start.start:end.end],
            "sourceRange": _cml_range(start, end),
        }
        node.update(values)
        return node

    def parse(self):
        while not self._at(kind="EOF"):
            start_pos = self.pos
            annotations = self._parse_annotations()
            if self._at(kind="EOF"):
                if annotations:
                    self._error(
                        "orphan-annotation",
                        "Annotation is not attached to a declaration.",
                        self.previous)
                break
            keyword = self.current.value
            if keyword == "type":
                self._parse_type(annotations)
            elif keyword in ("property", "extern", "define"):
                self._parse_declaration(keyword, annotations)
            else:
                self._parse_unknown("top-level")
            if self.pos == start_pos:
                self._take()
        return self.declarations, self.types, self.logic, self.unknown

    def _parse_annotations(self):
        annotations = []
        while self._at("@"):
            start = self._take()
            if not self._match("("):
                self._error(
                    "malformed-annotation",
                    "Expected '(' after annotation marker.", start)
                annotations.append(self._node(
                    "annotation", start, start, arguments=[]))
                continue
            args = self._parse_expression_list(")")
            if not self._match(")"):
                self._error(
                    "malformed-annotation", "Unclosed annotation.", start)
            annotations.append(self._node(
                "annotation", start, self.previous, arguments=args))
        return annotations

    def _parse_type_spec(self):
        if not self._at(kind="IDENT"):
            return None
        start = self._take()
        name = start.value
        if name in ("decimal", "double") and self._match("("):
            scale = self._take() if self._at(kind="NUMBER") else None
            if not self._match(")"):
                self._error(
                    "malformed-type",
                    f"Expected ')' in {name} type.", start)
            if scale:
                name = f"{name}({scale.value})"
        if self._match("["):
            if not self._match("]"):
                self._error(
                    "malformed-type", "Expected ']' in array type.", start)
            name += "[]"
        return name, start, self.previous

    def _parse_declaration(self, kind, annotations):
        start = self._take()
        data_type = None
        name_token = None
        value = None
        if kind == "extern":
            parsed_type = self._parse_type_spec()
            if parsed_type:
                data_type = parsed_type[0]
            else:
                self._error(
                    "malformed-declaration",
                    "Expected a type after 'extern'.", start)
            if self._at(kind="IDENT"):
                name_token = self._take()
        else:
            if self._at(kind="IDENT"):
                name_token = self._take()

        if not name_token:
            self._error(
                "malformed-declaration",
                f"Expected a name in {kind} declaration.", start, "error")

        if self._match("="):
            value = self._parse_expression()
        elif kind == "define" and not self._at(";"):
            # Official syntax is `define NAME value` (PDF pp. 1009, 1059).
            # Accept `=` too for compatibility with existing local corpora.
            value = self._parse_expression()
        self._consume_terminator(start, top_level=True)
        end = self.previous
        declaration = {
            "kind": kind,
            "name": name_token.value if name_token else None,
            "dataType": data_type,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "value": value,
        }
        self.declarations.append(declaration)

    def _parse_type(self, annotations):
        start = self._take()
        name_token = self._take() if self._at(kind="IDENT") else None
        if not name_token:
            self._error(
                "malformed-type", "Expected a name after 'type'.",
                start, "error")
        parent = None
        parent_token = None
        if self._match(":"):
            if self._at(kind="IDENT"):
                parent_token = self._take()
                parent = parent_token.value
            else:
                self._error(
                    "malformed-inheritance",
                    "Expected a parent type after ':'.", self.current)

        members, closed, stub = [], True, False
        if self._match(";"):
            stub = True
        elif self._match("{"):
            closed = False
            while not self._at(kind="EOF") and not self._at("}"):
                # A declaration aligned with the type header is a useful
                # recovery point when a malformed type body lost its '}'.
                if (self.current.value in _CML_TOP_LEVEL
                        and self.current.column <= start.column):
                    break
                before = self.pos
                member_annotations = self._parse_annotations()
                if self._at("}"):
                    if member_annotations:
                        self._error(
                            "orphan-annotation",
                            "Annotation is not attached to a type member.",
                            self.previous)
                    break
                member = self._parse_member(
                    name_token.value if name_token else "<unknown>",
                    member_annotations)
                if member:
                    members.append(member)
                if self.pos == before:
                    self._take()
            if self._match("}"):
                closed = True
                self._match(";")
            else:
                self._error(
                    "unclosed-type",
                    f"Type '{name_token.value if name_token else '?'}' "
                    "is missing a closing '}'.", start, "error")
        else:
            self._error(
                "malformed-type",
                "Expected ';' or '{' after type declaration.", self.current,
                "error")
            self._consume_terminator(start, top_level=True)

        end = self.previous
        type_record = {
            "kind": "type",
            "name": name_token.value if name_token else None,
            "parent": parent,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "stub": stub,
            "closed": closed,
            "variables": [m for m in members if m["kind"] == "variable"],
            "relations": [m for m in members if m["kind"] == "relation"],
            "unknownMembers": [
                m for m in members if m["kind"] == "unknown"],
        }
        self.types.append(type_record)
        self.declarations.append({
            key: type_record[key] for key in (
                "kind", "name", "parent", "line", "raw", "sourceRange",
                "annotations", "stub")
        })

    def _parse_member(self, scope, annotations):
        if self.current.value == "relation":
            return self._parse_relation(scope, annotations)
        if (self.current.kind == "IDENT"
                and self.current.value.lower() in _CML_LOGIC_CALLS):
            return self._parse_logic(scope, annotations)
        if self._looks_like_variable():
            return self._parse_variable(scope, annotations)
        return self._parse_unknown(scope, annotations)

    def _looks_like_variable(self):
        if not self._at(kind="IDENT"):
            return False
        index = self.pos + 1
        if self.current.value in ("decimal", "double") and index < len(self.tokens):
            if self.tokens[index].value == "(":
                depth = 1
                index += 1
                while index < len(self.tokens) and depth:
                    depth += self.tokens[index].value == "("
                    depth -= self.tokens[index].value == ")"
                    index += 1
        if index + 1 < len(self.tokens) and self.tokens[index].value == "[":
            if self.tokens[index + 1].value == "]":
                index += 2
        return (index < len(self.tokens)
                and self.tokens[index].kind == "IDENT")

    def _parse_variable(self, scope, annotations):
        start = self.current
        parsed_type = self._parse_type_spec()
        name_token = self._take() if self._at(kind="IDENT") else None
        value = None
        if self._match("="):
            value = self._parse_expression()
        self._consume_terminator(start)
        end = self.previous
        if not name_token:
            self._error(
                "malformed-variable", "Expected a variable name.", start)
        return {
            "kind": "variable",
            "name": name_token.value if name_token else None,
            "dataType": parsed_type[0] if parsed_type else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "domain": value,
        }

    def _parse_relation(self, scope, annotations):
        start = self._take()
        name_token = self._take() if self._at(kind="IDENT") else None
        if not self._match(":"):
            self._error(
                "malformed-relation", "Expected ':' in relation.", start)
        target_token = self._take() if self._at(kind="IDENT") else None
        cardinality = None
        if self._match("["):
            card_start = self.previous
            lower = None if self._at("..") else self._parse_expression(1)
            fixed = not self._at("..")
            if fixed:
                upper = lower
            else:
                self._take()
                upper = None if self._at("]") else self._parse_expression(1)
            if not self._match("]"):
                self._error(
                    "malformed-cardinality",
                    "Expected ']' after relation cardinality.", card_start)
            cardinality = {
                "raw": self._raw(card_start, self.previous),
                "min": lower,
                "max": upper,
                "fixed": fixed,
                "sourceRange": _cml_range(card_start, self.previous),
            }
        order = None
        if self._at_ci("order"):
            order_start = self._take()
            ordered_types = []
            if self._match("("):
                ordered_types = self._parse_expression_list(")")
                if not self._match(")"):
                    self._error(
                        "malformed-relation-order",
                        "Expected ')' after relation order list.",
                        order_start, "error")
            else:
                self._error(
                    "malformed-relation-order",
                    "Expected '(' after relation order.", order_start,
                    "error")
            order = {
                "raw": self._raw(order_start, self.previous),
                "types": ordered_types,
                "sourceRange": _cml_range(order_start, self.previous),
            }
        body = None
        if self._match("{"):
            body_start = self.previous
            declarations = []
            aggregate_calls = []
            unknown_constructs = []
            while not self._at(kind="EOF") and not self._at("}"):
                declaration_start = self.current
                if (self._at(kind="IDENT")
                        and self.pos + 1 < len(self.tokens)
                        and self.tokens[self.pos + 1].value == "="):
                    derived_name_token = self._take()
                    self._take()
                    expression = self._parse_expression()
                    self._consume_terminator(declaration_start)
                    declaration = self._node(
                        "relationDerivedDeclaration", declaration_start,
                        self.previous, name=derived_name_token.value,
                        expression=expression)
                    declarations.append(declaration)
                    aggregate_calls.extend(
                        self._collect_aggregate_calls(expression))
                else:
                    unknown = self._parse_unknown(
                        f"relation {name_token.value if name_token else '?'}")
                    unknown_constructs.append(unknown)
            if not self._match("}"):
                self._error(
                    "malformed-relation",
                    "Relation body is missing a closing '}'.",
                    body_start, "error")
            body = {
                "raw": self._raw(body_start, self.previous),
                "sourceRange": _cml_range(body_start, self.previous),
                "declarations": declarations,
                "aggregateCalls": aggregate_calls,
                "unknownConstructs": unknown_constructs,
                "complete": self.previous.value == "}",
            }
            self._match(";")
        else:
            self._consume_terminator(start)
        end = self.previous
        if not name_token or not target_token:
            self._error(
                "malformed-relation",
                "Relation requires a name and target type.", start, "error")
        return {
            "kind": "relation",
            "name": name_token.value if name_token else None,
            "target": target_token.value if target_token else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "cardinality": cardinality,
            "order": order,
            "body": body,
        }

    def _collect_aggregate_calls(self, node):
        calls = []

        def visit(current):
            if not isinstance(current, dict):
                return
            if current.get("kind") == "call":
                callee = current.get("callee") or {}
                aggregate = None
                if callee.get("kind") == "name":
                    aggregate = callee.get("name", "").lower()
                elif callee.get("kind") == "member":
                    aggregate = callee.get("member", "").lower()
                if aggregate in {"count", "max", "min", "sum", "total"}:
                    calls.append({
                        "function": aggregate,
                        "raw": current.get("raw", ""),
                        "arguments": current.get("arguments", []),
                        "sourceRange": current.get("sourceRange"),
                        "quantityBehavior": (
                            "multiplies-by-product-quantity"
                            if aggregate == "sum" else
                            "ignores-product-quantity"
                            if aggregate == "total" else None),
                    })
            for value in current.values():
                if isinstance(value, dict):
                    visit(value)
                elif isinstance(value, list):
                    for child in value:
                        visit(child)

        visit(node)
        return calls

    def _parse_logic(self, scope, annotations):
        start = self._take()
        diagnostic_start = len(self.diagnostics)
        logic_kind = start.value.lower()
        name_token = None
        malformed = False
        args = []
        # Named forms are documented as `constraint name(expression)` (PDF
        # pp. 1038 and 1121); accepting the form for every rule keeps recovery
        # consistent without changing ordinary call syntax.
        if self._at(kind="IDENT"):
            name_token = self._take()
        if self._match("("):
            args = self._parse_expression_list(")")
            if not self._match(")"):
                malformed = True
                self._error(
                    "malformed-logic",
                    f"Unclosed argument list for {logic_kind}.", start,
                    "error")
        else:
            malformed = True
            self._error(
                "malformed-logic",
                f"Expected '(' after {logic_kind}.", start, "error")

        block_expression = None
        if self._match("{"):
            block_start = self.previous
            if not self._at("}"):
                block_expression = self._parse_expression()
            if not self._match("}"):
                malformed = True
                self._error(
                    "malformed-logic",
                    f"Unclosed body for {logic_kind}.", block_start, "error")
            self._match(";")
        else:
            self._consume_terminator(start)
        end = self.previous
        condition = block_expression or (args[0] if args else None)
        logic_diagnostics = self.diagnostics[diagnostic_start:]
        damaging_codes = {
            "malformed-logic", "malformed-expression",
            "malformed-conditional", "malformed-configured-target",
            "malformed-call", "malformed-index", "malformed-member",
        }
        syntax_complete = (
            not malformed and condition is not None
            and _cml_expression_complete(condition)
            and not any(
                diagnostic.get("code") in damaging_codes
                for diagnostic in logic_diagnostics))
        record = {
            "kind": logic_kind,
            "name": name_token.value if name_token else None,
            "scope": scope,
            "line": start.line,
            "raw": self._raw(start, end),
            "sourceRange": _cml_range(start, end),
            "annotations": annotations,
            "arguments": args,
            "conditionAst": condition,
            "syntaxComplete": syntax_complete,
            "parseDiagnosticCodes": [
                diagnostic.get("code") for diagnostic in logic_diagnostics],
            "malformed": not syntax_complete,
        }
        self.logic.append(record)
        return record

    def _parse_unknown(self, scope, annotations=None):
        start = self.current
        self._consume_terminator(start, top_level=(scope == "top-level"))
        end = self.previous
        if end.start < start.start:
            end = self._take()
        raw = self._raw(start, end)
        self._error(
            "unsupported-syntax",
            f"Unsupported or malformed construct in {scope}; analysis "
            "continued at the next balanced boundary.",
            start, "warning")
        node = {
            "kind": "unknown",
            "scope": scope,
            "line": start.line,
            "raw": raw,
            "sourceRange": _cml_range(start, end),
            "annotations": annotations or [],
        }
        self.unknown.append(node)
        return node

    def _consume_terminator(self, start, top_level=False):
        depths = {"(": 0, "[": 0, "{": 0}
        pairs = {")": "(", "]": "[", "}": "{"}
        while not self._at(kind="EOF"):
            token = self.current
            if all(value == 0 for value in depths.values()):
                if token.value == ";":
                    self._take()
                    return
                if token.value == "}":
                    return
                if (token is not start and token.value in _CML_TOP_LEVEL
                        and token.line > start.line):
                    return
                if (not top_level and token.value in _CML_LOGIC_CALLS
                        and token.line > start.line):
                    return
            if token.value in depths:
                depths[token.value] += 1
            elif token.value in pairs:
                opener = pairs[token.value]
                if depths[opener] == 0:
                    return
                depths[opener] -= 1
            self._take()
        self._error(
            "missing-terminator",
            "Construct reached end of input without a balanced terminator.",
            start)

    def _parse_expression_list(self, close):
        expressions = []
        while not self._at(kind="EOF") and not self._at(close):
            if self._at(";") or self._at("}"):
                break
            if (expressions and self.current.value in (
                    _CML_TOP_LEVEL | _CML_LOGIC_CALLS)
                    and self.current.line > self.previous.line):
                break
            before = self.pos
            expressions.append(self._parse_expression())
            if self._match(","):
                continue
            if self._at(close):
                break
            self._error(
                "malformed-expression",
                f"Expected ',' or '{close}' in expression list.",
                self.current)
            if self.pos == before:
                self._take()
            while (not self._at(kind="EOF") and not self._at(close)
                   and not self._at(",") and not self._at(";")
                   and not self._at("}")):
                self._take()
            self._match(",")
        return expressions

    def _parse_expression(self, minimum=0):
        start = self.current
        left = self._parse_prefix()
        while True:
            operator = self.current.value
            spaced_biconditional_tokens = 0
            if operator == "<" and self.pos + 1 < len(self.tokens):
                if self.tokens[self.pos + 1].value == "->":
                    spaced_biconditional_tokens = 1
                elif (self.pos + 2 < len(self.tokens)
                      and self.tokens[self.pos + 1].value == "-"
                      and self.tokens[self.pos + 2].value == ">"):
                    spaced_biconditional_tokens = 2
            spaced_biconditional = spaced_biconditional_tokens > 0
            if spaced_biconditional:
                operator = "<->"
            if operator == "?" and minimum <= 2:
                self._take()
                when_true = self._parse_expression()
                if not self._match(":"):
                    self._error(
                        "malformed-conditional",
                        "Expected ':' in conditional expression.",
                        self.current, "error")
                    when_false = self._node(
                        "unknownExpression", self.current, self.current,
                        reason="missing-conditional-branch")
                else:
                    # CML conditional is right-associative (PDF pp. 1032-1034).
                    when_false = self._parse_expression(2)
                left = self._node(
                    "conditional", start, self.previous, condition=left,
                    whenTrue=when_true, whenFalse=when_false)
                continue
            precedence = self._PRECEDENCE.get(operator)
            if precedence is None or precedence < minimum:
                break
            if spaced_biconditional:
                self._error(
                    "malformed-operator-spacing",
                    "The biconditional operator cannot contain spaces. "
                    "Write '<->' instead of '< ->'. Analysis recovered this "
                    "expression as a biconditional.",
                    self.current, "error")
            self._take()
            if spaced_biconditional:
                for _ in range(spaced_biconditional_tokens):
                    self._take()
            right = self._parse_expression(
                precedence if operator in self._RIGHT_ASSOCIATIVE
                else precedence + 1)
            left = self._node(
                "binary", start, self.previous, operator=operator,
                left=left, right=right)
        return left

    def _parse_prefix(self):
        start = self.current
        if start.value in ("!", "not", "-", "+"):
            operator = self._take()
            operand = self._parse_expression(11)
            return self._node(
                "unary", start, self.previous, operator=operator.value,
                operand=operand)
        if self._match("("):
            expression = self._parse_expression()
            if not self._match(")"):
                self._error(
                    "malformed-expression",
                    "Expected ')' after expression.", start)
            expression = self._node(
                "group", start, self.previous, expression=expression)
            return self._parse_postfix(expression, start)
        if self._match("["):
            values = self._parse_expression_list("]")
            if not self._match("]"):
                self._error(
                    "malformed-expression", "Expected ']' after list.", start)
            return self._parse_postfix(
                self._node("list", start, self.previous, values=values), start)
        if self._match("{"):
            values = self._parse_expression_list("}")
            if not self._match("}"):
                self._error(
                    "malformed-row-literal",
                    "Expected '}' after table row literal.", start, "error")
            return self._parse_postfix(
                self._node(
                    "rowLiteral", start, self.previous, values=values),
                start)
        if start.kind == "STRING":
            self._take()
            raw_value = start.value[1:-1] if len(start.value) >= 2 else ""
            node = self._node(
                "literal", start, start, value=raw_value,
                literalType="string")
            return self._parse_postfix(node, start)
        if start.kind == "NUMBER":
            self._take()
            compact = start.value.replace("_", "")
            try:
                value = float(compact) if any(
                    char in compact for char in ".eE") else int(compact)
            except ValueError:
                value = compact
            node = self._node(
                "literal", start, start, value=value,
                literalType="number")
            return self._parse_postfix(node, start)
        if start.kind == "IDENT":
            self._take()
            lowered = start.value.lower()
            if lowered in ("true", "false", "null"):
                value = (lowered == "true") if lowered != "null" else None
                node = self._node(
                    "literal", start, start, value=value,
                    literalType=lowered)
            else:
                node = self._node("name", start, start, name=start.value)
            return self._parse_postfix(node, start)

        self._error(
            "malformed-expression",
            f"Expected expression, found {start.value!r}.", start)
        if start.kind != "EOF":
            self._take()
        return self._node(
            "unknownExpression", start, self.previous,
            reason="unsupported-token")

    def _parse_postfix(self, node, start):
        while True:
            if self._match("."):
                if not self._at(kind="IDENT"):
                    self._error(
                        "malformed-member",
                        "Expected a member name after '.'.", self.current)
                    break
                member = self._take()
                node = self._node(
                    "member", start, member, object=node, member=member.value)
            elif self._match("["):
                index = None if self._at("]") else self._parse_expression()
                if not self._match("]"):
                    self._error(
                        "malformed-index",
                        "Expected ']' after index expression.", start)
                node = self._node(
                    "index", start, self.previous, object=node, index=index)
            elif self._match("("):
                args = self._parse_expression_list(")")
                if not self._match(")"):
                    self._error(
                        "malformed-call",
                        "Expected ')' after call arguments.", start)
                node = self._node(
                    "call", start, self.previous, callee=node, arguments=args)
            elif self._match("{"):
                assignments = []
                configuration_start = self.previous
                while not self._at(kind="EOF") and not self._at("}"):
                    assignment_start = self.current
                    key = self._take() if self._at(kind="IDENT") else None
                    if not key or not self._match("="):
                        self._error(
                            "malformed-configured-target",
                            "Expected attribute=value in configured target.",
                            assignment_start, "error")
                        while (not self._at(kind="EOF")
                               and not self._at(",") and not self._at("}")):
                            self._take()
                        value = self._node(
                            "unknownExpression", assignment_start,
                            self.previous, reason="malformed-assignment")
                    else:
                        value = self._parse_expression(1)
                    assignments.append({
                        "attribute": key.value if key else None,
                        "value": value,
                        "raw": self._raw(assignment_start, self.previous),
                        "sourceRange": _cml_range(
                            assignment_start, self.previous),
                    })
                    if not self._match(","):
                        break
                if not self._match("}"):
                    self._error(
                        "malformed-configured-target",
                        "Expected '}' after configured target attributes.",
                        configuration_start, "error")
                node = self._node(
                    "configuredTarget", start, self.previous, target=node,
                    assignments=assignments)
            else:
                break
        return node


def _cml_expression_complete(node):
    """True only when no recovery placeholder survives in an expression."""
    if not isinstance(node, dict):
        return False
    if node.get("kind") == "unknownExpression":
        return False
    for value in node.values():
        if isinstance(value, dict) and "kind" in value:
            if not _cml_expression_complete(value):
                return False
        elif isinstance(value, list):
            for child in value:
                if (isinstance(child, dict) and "kind" in child
                        and not _cml_expression_complete(child)):
                    return False
                if isinstance(child, dict):
                    nested = child.get("value")
                    if (isinstance(nested, dict)
                            and not _cml_expression_complete(nested)):
                        return False
    return True


_CML_NOT_CONSTANT = object()


def _cml_constant(node):
    """Evaluate only expressions whose complete tree is compile-time constant."""
    if not node:
        return _CML_NOT_CONSTANT
    kind = node.get("kind")
    if kind == "literal":
        return node.get("value")
    if kind == "group":
        return _cml_constant(node.get("expression"))
    if kind == "list":
        values = []
        for item in node.get("values", []):
            value = _cml_constant(item)
            if value is _CML_NOT_CONSTANT:
                return value
            values.append(value)
        return values
    if kind == "rowLiteral":
        return _CML_NOT_CONSTANT
    if kind == "conditional":
        condition = _cml_constant(node.get("condition"))
        if condition is _CML_NOT_CONSTANT:
            return condition
        return _cml_constant(
            node.get("whenTrue") if bool(condition)
            else node.get("whenFalse"))
    if kind == "unary":
        value = _cml_constant(node.get("operand"))
        if value is _CML_NOT_CONSTANT:
            return value
        try:
            return {
                "!": lambda: not value,
                "not": lambda: not value,
                "-": lambda: -value,
                "+": lambda: +value,
            }[node.get("operator")]()
        except (KeyError, TypeError, ValueError):
            return _CML_NOT_CONSTANT
    if kind != "binary":
        return _CML_NOT_CONSTANT
    left = _cml_constant(node.get("left"))
    right = _cml_constant(node.get("right"))
    if left is _CML_NOT_CONSTANT or right is _CML_NOT_CONSTANT:
        return _CML_NOT_CONSTANT
    operator = node.get("operator")
    try:
        operations = {
            "&&": lambda: bool(left) and bool(right),
            "and": lambda: bool(left) and bool(right),
            "||": lambda: bool(left) or bool(right),
            "or": lambda: bool(left) or bool(right),
            "^": lambda: bool(left) != bool(right),
            "==": lambda: left == right,
            "===": lambda: left == right,
            "!=": lambda: left != right,
            "!==": lambda: left != right,
            "<": lambda: left < right,
            "<=": lambda: left <= right,
            ">": lambda: left > right,
            ">=": lambda: left >= right,
            "in": lambda: left in right,
            "+": lambda: left + right,
            "-": lambda: left - right,
            "*": lambda: left * right,
            "/": lambda: left / right,
            "%": lambda: left % right,
            "->": lambda: (not bool(left)) or bool(right),
            "<->": lambda: bool(left) == bool(right),
        }
        return operations[operator]()
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return _CML_NOT_CONSTANT


def _cml_references(node):
    """Collect dependency names without treating member labels as variables."""
    references = []

    def visit(current, callee=False):
        if not isinstance(current, dict):
            return
        kind = current.get("kind")
        if kind == "name":
            name = current.get("name")
            if name and not (callee and name.lower() in _CML_BUILTINS):
                references.append({
                    "name": name,
                    "line": current["sourceRange"]["start"]["line"],
                    "sourceRange": current["sourceRange"],
                    "simple": True,
                })
        elif kind == "member":
            visit(current.get("object"))
        elif kind == "index":
            visit(current.get("object"))
            visit(current.get("index"))
        elif kind == "call":
            visit(current.get("callee"), True)
            for argument in current.get("arguments", []):
                visit(argument)
        elif kind == "configuredTarget":
            visit(current.get("target"))
            for assignment in current.get("assignments", []):
                visit(assignment.get("value"))
        else:
            for key in (
                    "left", "right", "operand", "expression", "condition",
                    "whenTrue", "whenFalse"):
                visit(current.get(key))
            for key in ("values", "arguments"):
                for child in current.get(key, []) or []:
                    visit(child)

    visit(node)
    seen = set()
    return [
        reference for reference in references
        if not (reference["name"] in seen or seen.add(reference["name"]))
    ]


def _cml_business_label(value):
    """Turn a CML identifier into a readable label without changing its value."""
    if not value:
        return "Unknown expression"
    text = str(value).replace("_", " ").strip()
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return " ".join(text.split())


def _cml_expression_view(node):
    """Return a JSON-safe, syntax-level description of an expression."""
    if not isinstance(node, dict):
        return {
            "kind": "unknown",
            "raw": "",
            "description": "Unknown expression",
        }
    kind = node.get("kind")
    raw = node.get("raw", "")
    if kind == "literal":
        literal_type = node.get("literalType")
        value = node.get("value")
        if literal_type == "null":
            description = "null"
        elif literal_type == "boolean" or isinstance(value, bool):
            description = "true" if value else "false"
        else:
            description = str(value)
        return {
            "kind": "literal",
            "raw": raw,
            "description": description,
            "value": value,
            "valueType": literal_type,
        }
    if kind == "name":
        return {
            "kind": "name",
            "raw": raw,
            "description": _cml_business_label(node.get("name")),
            "name": node.get("name"),
        }
    if kind == "member":
        object_view = _cml_expression_view(node.get("object"))
        member = node.get("member")
        return {
            "kind": "member",
            "raw": raw,
            "description": (
                f"{object_view['description']}.{_cml_business_label(member)}"),
            "object": object_view,
            "member": member,
        }
    if kind == "index":
        object_view = _cml_expression_view(node.get("object"))
        index_view = _cml_expression_view(node.get("index"))
        description = (
            f"{index_view['description']} items in "
            f"{object_view['description']}")
        return {
            "kind": "index",
            "raw": raw,
            "description": description,
            "object": object_view,
            "index": index_view,
            "interpretation": "Expected runtime relation count or value",
        }
    if kind == "list":
        values = [
            _cml_expression_view(value) for value in node.get("values", [])
        ]
        return {
            "kind": "list",
            "raw": raw,
            "description": (
                "[" + ", ".join(value["description"] for value in values)
                + "]"),
            "items": values,
        }
    if kind == "rowLiteral":
        values = [
            _cml_expression_view(value) for value in node.get("values", [])
        ]
        return {
            "kind": "tableRow",
            "raw": raw,
            "description": (
                "valid table row {"
                + ", ".join(value["description"] for value in values) + "}"),
            "items": values,
            "interpretation": (
                "Declared valid combination; no runtime row was observed"),
        }
    if kind == "configuredTarget":
        target = _cml_expression_view(node.get("target"))
        assignments = [{
            "attribute": assignment.get("attribute"),
            "value": _cml_expression_view(assignment.get("value")),
            "raw": assignment.get("raw", ""),
        } for assignment in node.get("assignments", [])]
        suffix = ", ".join(
            f"{item['attribute']}={item['value']['description']}"
            for item in assignments)
        return {
            "kind": "configuredTarget",
            "raw": raw,
            "description": (
                f"{target['description']} configured with {suffix}"
                if suffix else target["description"]),
            "target": target,
            "assignments": assignments,
            "interpretation": (
                "Configured product target; runtime presence and quantity "
                "remain unknown"),
        }
    if kind == "call":
        callee = _cml_expression_view(node.get("callee"))
        arguments = [
            _cml_expression_view(argument)
            for argument in node.get("arguments", [])
        ]
        result = {
            "kind": "call",
            "raw": raw,
            "description": (
                f"{callee['description']}("
                + ", ".join(item["description"] for item in arguments)
                + ")"),
            "callee": callee,
            "arguments": arguments,
            "interpretation": "Runtime call result; no value was observed",
        }
        callee_name = None
        if node.get("callee", {}).get("kind") == "name":
            callee_name = node["callee"].get("name", "").lower()
        elif node.get("callee", {}).get("kind") == "member":
            callee_name = node["callee"].get("member", "").lower()
        if callee_name == "table":
            result.update({
                "semanticKind": "valid-combination-table",
                "interpretation": (
                    "Constrains the listed variables to declared or imported "
                    "valid row combinations; no runtime match is inferred"),
            })
        elif callee_name == "salesforcetable":
            result.update({
                "semanticKind": "salesforce-table-source",
                "interpretation": (
                    "Declares a Salesforce object and field mapping as the "
                    "table source; rows are not fetched or inferred here"),
            })
        elif callee_name == "cardinality":
            result.update({
                "semanticKind": "relation-cardinality-proxy",
                "typeArgument": arguments[0] if arguments else None,
                "relationArgument": (
                    arguments[1] if len(arguments) > 1 else None),
                "interpretation": (
                    "Reads the runtime instance quantity for the type"
                    + (" in the specified relation"
                       if len(arguments) > 1 else " across relations")
                    + "; no quantity is inferred"),
            })
        elif callee_name in {"count", "max", "min", "sum", "total"}:
            quantity_behavior = (
                "multiplies each value by product quantity"
                if callee_name == "sum" else
                "does not multiply values by product quantity"
                if callee_name == "total" else None)
            result.update({
                "semanticKind": "relation-aggregate",
                "aggregateFunction": callee_name,
                "quantityBehavior": quantity_behavior,
                "interpretation": (
                    f"Runtime relation aggregate"
                    + (f"; {quantity_behavior}" if quantity_behavior else "")
                    + "; no aggregate value is inferred"),
            })
        return result
    if kind == "group":
        expression = _cml_expression_view(node.get("expression"))
        return {
            "kind": "group",
            "raw": raw,
            "description": expression["description"],
            "expression": expression,
        }
    if kind == "unary":
        operand = _cml_expression_view(node.get("operand"))
        operator = node.get("operator")
        return {
            "kind": "unary",
            "raw": raw,
            "description": f"{operator}{operand['description']}",
            "operator": operator,
            "operand": operand,
        }
    if kind == "binary":
        left = _cml_expression_view(node.get("left"))
        right = _cml_expression_view(node.get("right"))
        operator = node.get("operator")
        return {
            "kind": "binary",
            "raw": raw,
            "description": (
                f"{left['description']} {operator} {right['description']}"),
            "left": left,
            "operator": operator,
            "right": right,
        }
    if kind == "conditional":
        condition = _cml_expression_view(node.get("condition"))
        when_true = _cml_expression_view(node.get("whenTrue"))
        when_false = _cml_expression_view(node.get("whenFalse"))
        return {
            "kind": "conditional",
            "raw": raw,
            "description": (
                f"if {condition['description']}, then "
                f"{when_true['description']}, otherwise "
                f"{when_false['description']}"),
            "condition": condition,
            "whenTrue": when_true,
            "whenFalse": when_false,
            "interpretation": (
                "Conditional requirement; runtime branch is unknown"),
        }
    return {
        "kind": kind or "unknown",
        "raw": raw,
        "description": raw or "Unknown expression",
    }


def _cml_expected_value(node):
    """Keep literal expectations primitive and describe dynamic ones safely."""
    if isinstance(node, dict) and node.get("kind") == "literal":
        return node.get("value")
    return _cml_expression_view(node)


def _cml_comparison_english(left, operator, right):
    """Describe one comparison as a requirement, never as an observed result."""
    left_view = _cml_expression_view(left)
    right_view = _cml_expression_view(right)
    subject = left_view["description"]
    expected = right_view["description"]
    right_is_literal = isinstance(right, dict) and right.get("kind") == "literal"
    right_value = right.get("value") if right_is_literal else None

    if right_is_literal and right.get("literalType") == "null":
        if operator in ("!=", "!=="):
            return f"{subject} must have a value."
        if operator in ("==", "==="):
            return f"{subject} must not have a value."

    if left_view["kind"] == "index" and right_is_literal:
        # Preserve catalog/relation identifiers in count requirements. Splitting
        # ProductType into "Product Type" can make a real type look generic.
        item = (
            left_view["index"].get("name")
            or left_view["index"]["description"])
        relation = (
            left_view["object"].get("name")
            or left_view["object"]["description"])
        count_requirements = {
            ("==", 0): f"No {item} items may be present in {relation}.",
            ("===", 0): f"No {item} items may be present in {relation}.",
            ("!=", 0): (
                f"At least one {item} item must be present in {relation}."),
            ("!==", 0): (
                f"At least one {item} item must be present in {relation}."),
            (">", 0): (
                f"At least one {item} item must be present in {relation}."),
            (">=", 1): (
                f"At least one {item} item must be present in {relation}."),
            ("<", 1): f"No {item} items may be present in {relation}.",
            ("<=", 0): f"No {item} items may be present in {relation}.",
            ("==", 1): (
                f"Exactly one {item} item must be present in {relation}."),
            ("===", 1): (
                f"Exactly one {item} item must be present in {relation}."),
            ("<=", 1): (
                f"At most one {item} item may be present in {relation}."),
            (">", 1): (
                f"More than one {item} item must be present in {relation}."),
        }
        description = count_requirements.get((operator, right_value))
        if description:
            return description

    if right_is_literal and isinstance(right_value, bool):
        expected = "true" if right_value else "false"
    elif right_is_literal and right_value == 0:
        expected = "zero"
    elif right_is_literal and right_value == 1:
        expected = "one"

    phrases = {
        "==": "must equal",
        "===": "must equal",
        "!=": "must not equal",
        "!==": "must not equal",
        "<": "must be less than",
        "<=": "must be less than or equal to",
        ">": "must be greater than",
        ">=": "must be greater than or equal to",
        "in": "must be in",
    }
    phrase = phrases.get(operator, f"must satisfy {operator} against")
    return f"{subject} {phrase} {expected}."


def _cml_condition_clause(node):
    """Build the common schema used by terminal condition clauses."""
    raw = node.get("raw", "") if isinstance(node, dict) else ""
    line = (
        node.get("sourceRange", {}).get("start", {}).get("line")
        if isinstance(node, dict) else None)
    return {
        "nodeType": "clause",
        "raw": raw,
        "line": line,
        "left": raw,
        "subject": _cml_expression_view(node)["description"],
        "operator": "evaluates-to",
        "expectedValue": True,
        "plainEnglish": "The expression must evaluate to true.",
        "actualValue": None,
        "result": "Runtime value required",
    }


def _cml_condition_breakdown(node):
    """Recursively decompose a parsed condition for business/UI presentation."""
    if not isinstance(node, dict):
        clause = _cml_condition_clause({})
        clause.update({
            "subject": "Unknown condition",
            "plainEnglish": (
                "The condition could not be recovered from the source."),
        })
        return clause

    kind = node.get("kind")
    if kind == "group":
        child = _cml_condition_breakdown(node.get("expression"))
        return {
            "nodeType": "group",
            "operator": "group",
            "logicalJoin": "GROUP",
            "raw": node.get("raw", ""),
            "line": node["sourceRange"]["start"]["line"],
            "summary": "Evaluate the enclosed condition as one branch.",
            "failCondition": "The enclosed condition does not pass.",
            "plainEnglish": child.get("plainEnglish", child.get("summary")),
            "children": [child],
            "actualValue": None,
            "result": "Runtime value required",
        }

    if kind == "unary" and node.get("operator") in ("!", "not"):
        child = _cml_condition_breakdown(node.get("operand"))
        return {
            "nodeType": "logicalGroup",
            "operator": node.get("operator"),
            "logicalJoin": "NOT",
            "raw": node.get("raw", ""),
            "line": node["sourceRange"]["start"]["line"],
            "summary": "The enclosed condition must not be true.",
            "failCondition": "This condition fails when its child is true.",
            "plainEnglish": (
                "The opposite of the enclosed condition is required."),
            "children": [child],
            "actualValue": None,
            "result": "Runtime value required",
        }

    logical_operators = {
        "&&": (
            "ALL", "All conditions must be true.",
            "This condition fails when any child condition is false.",
            "The action is eligible only if every clause passes."),
        "and": (
            "ALL", "All conditions must be true.",
            "This condition fails when any child condition is false.",
            "The action is eligible only if every clause passes."),
        "||": (
            "ANY", "At least one condition must be true.",
            "This condition fails only when every branch is false.",
            "Any branch can pass to make the action eligible."),
        "or": (
            "ANY", "At least one condition must be true.",
            "This condition fails only when every branch is false.",
            "Any branch can pass to make the action eligible."),
        "^": (
            "EXACTLY_ONE",
            "Exactly one of the two conditions must be true.",
            "This condition fails when both branches have the same truth value.",
            "One branch must pass and the other must not."),
        "->": (
            "IMPLIES", "If the first condition is true, the second must be true.",
            "This condition fails only when the first condition is true and "
            "the second condition is false.",
            "The implication passes when its prerequisite is false or its "
            "required consequence is true."),
        "<->": (
            "EQUIVALENT",
            "Both conditions must have the same truth value.",
            "This condition fails when one condition is true and the other "
            "is false.",
            "The biconditional passes only when both branches agree."),
    }
    if kind == "binary" and node.get("operator") in logical_operators:
        join, summary, fail_condition, plain_english = logical_operators[
            node.get("operator")]
        return {
            "nodeType": "logicalGroup",
            "operator": node.get("operator"),
            "logicalJoin": join,
            "raw": node.get("raw", ""),
            "line": node["sourceRange"]["start"]["line"],
            "summary": summary,
            "failCondition": fail_condition,
            "plainEnglish": plain_english,
            "children": [
                _cml_condition_breakdown(node.get("left")),
                _cml_condition_breakdown(node.get("right")),
            ],
            "actualValue": None,
            "result": "Runtime value required",
        }

    if kind == "conditional":
        return {
            "nodeType": "conditional",
            "operator": "?:",
            "logicalJoin": "IF_THEN_ELSE",
            "raw": node.get("raw", ""),
            "line": node["sourceRange"]["start"]["line"],
            "summary": (
                "Use the second branch when the condition is true; otherwise "
                "use the third branch."),
            "failCondition": (
                "Runtime values are required to identify and evaluate the "
                "selected branch."),
            "plainEnglish": _cml_expression_view(node)["description"],
            "children": [
                _cml_condition_breakdown(node.get("condition")),
                _cml_condition_breakdown(node.get("whenTrue")),
                _cml_condition_breakdown(node.get("whenFalse")),
            ],
            "actualValue": None,
            "result": "Runtime value required",
        }

    comparisons = {
        "==", "===", "!=", "!==", "<", "<=", ">", ">=", "in",
    }
    if kind == "binary" and node.get("operator") in comparisons:
        left = node.get("left")
        right = node.get("right")
        left_view = _cml_expression_view(left)
        clause = _cml_condition_clause(node)
        clause.update({
            "left": left_view["raw"],
            "subject": left_view["description"],
            "operator": node.get("operator"),
            "expectedValue": _cml_expected_value(right),
            "plainEnglish": _cml_comparison_english(
                left, node.get("operator"), right),
            "interpretation": (
                "Expected runtime requirement; not an observed result"),
            "expression": {
                "left": left_view,
                "right": _cml_expression_view(right),
            },
        })
        return clause

    clause = _cml_condition_clause(node)
    expression = _cml_expression_view(node)
    clause.update({
        "left": expression["raw"],
        "subject": expression["description"],
        "expression": expression,
    })
    if kind == "literal":
        clause["expectedValue"] = bool(node.get("value"))
        clause["plainEnglish"] = (
            f"The constant condition is "
            f"{'true' if bool(node.get('value')) else 'false'}.")
    return clause


def _cml_literal_text(node):
    if isinstance(node, dict) and node.get("kind") == "literal":
        value = node.get("value")
        return value if isinstance(value, str) else None
    return None


def _cml_target_details(node):
    """Expose configured target/quantity syntax without resolving its value."""
    target = node
    quantity = None
    if (isinstance(node, dict) and node.get("kind") == "binary"
            and node.get("operator") in ("==", "===")):
        target = node.get("left")
        quantity = node.get("right")
    configured = (
        target if isinstance(target, dict)
        and target.get("kind") == "configuredTarget" else None)
    return {
        "targetExpression": _cml_expression_view(target),
        "configuredAttributes": (
            [{
                "attribute": assignment.get("attribute"),
                "value": _cml_expression_view(assignment.get("value")),
            } for assignment in configured.get("assignments", [])]
            if configured else []),
        "quantityExpression": (
            _cml_expression_view(quantity) if quantity else None),
    }


def _cml_effect(kind, arguments):
    """Describe syntax-level intent without predicting solver execution."""
    raw_args = [argument.get("raw", "") for argument in arguments]
    if kind == "message":
        severity = "Info"
        format_args = arguments[2:]
        if format_args:
            candidate = _cml_literal_text(format_args[-1])
            if candidate and candidate.lower() in {
                    "info", "warning", "error"}:
                severity = candidate.title()
                format_args = format_args[:-1]
        return {
            "action": "emit-message",
            "message": raw_args[1] if len(raw_args) > 1 else None,
            "formatArguments": [
                argument.get("raw", "") for argument in format_args],
            "severity": severity,
            "blocking": severity in ("Warning", "Error"),
        }
    if kind == "require":
        effect = {
            "action": "require",
            "target": raw_args[1] if len(raw_args) > 1 else None,
            "message": raw_args[2] if len(raw_args) > 2 else None,
            "physicalPresence": True,
            "canAutoAdd": True,
            "runtimeResult": None,
        }
        if len(arguments) > 1:
            effect.update(_cml_target_details(arguments[1]))
        return effect
    if kind == "exclude":
        effect = {
            "action": "exclude",
            "target": raw_args[1] if len(raw_args) > 1 else None,
            "message": raw_args[2] if len(raw_args) > 2 else None,
            "targetRequirement": "leaf-type",
            "overridesUserSelection": True,
            "runtimeResult": None,
        }
        if len(arguments) > 1:
            effect.update(_cml_target_details(arguments[1]))
        return effect
    if kind == "preference":
        return {
            "action": "preference",
            "explanation": raw_args[1] if len(raw_args) > 1 else None,
            "formatArguments": raw_args[2:] if len(raw_args) > 2 else [],
            "blocking": False,
            "messageSeverity": "Info",
        }
    if kind == "recommend":
        return {
            "action": "legacy-recommend",
            "arguments": raw_args[1:],
            "official": False,
            "verification": "legacy/unverified standalone syntax",
        }
    if kind == "setdefault":
        effect = {
            "action": "set-default",
            "target": raw_args[1] if len(raw_args) > 1 else None,
            "message": raw_args[2] if len(raw_args) > 2 else None,
            "attemptMode": "condition-changed-or-parent-new",
            "otherwise": "passive-evaluation",
            "runtimeResult": None,
        }
        if len(arguments) > 1:
            effect.update(_cml_target_details(arguments[1]))
        return effect
    if kind == "rule":
        action = (
            _cml_literal_text(arguments[1]).lower()
            if len(arguments) > 1 and _cml_literal_text(arguments[1])
            else None)
        scope_name = (
            _cml_literal_text(arguments[2]).lower()
            if len(arguments) > 2 and _cml_literal_text(arguments[2])
            else None)
        target = raw_args[3] if len(raw_args) > 3 else None
        if action in ("hide", "disable"):
            return {
                "action": action,
                "scope": scope_name,
                "target": target,
                "arguments": raw_args[4:],
                "runtimeResult": None,
            }
        if action == "recommend":
            return {
                "action": "recommend",
                "scope": scope_name,
                "target": target,
                "blocking": False,
                "runtimeResult": None,
            }
        return {
            "action": "rule-directive",
            "directive": action,
            "arguments": raw_args[2:],
            "runtimeResult": None,
        }
    return {
        "action": "enforce-condition",
        "purpose": "logical-consistency",
        "message": raw_args[1] if len(raw_args) > 1 else None,
        "formatArguments": raw_args[2:] if len(raw_args) > 2 else [],
        "runtimeResult": None,
    }


def analyze_cml_logic(content):
    """Parse and conservatively analyze CML without invoking a runtime solver.

    The result is deliberately JSON-serializable and remains useful when parts
    of the input are malformed: diagnostics and unknown nodes preserve those
    regions while balanced recovery continues with later declarations.
    """
    if not isinstance(content, str):
        return {
            "schemaVersion": "1.1",
            "ok": False,
            "summary": {
                "declarationCount": 0, "typeCount": 0, "logicItemCount": 0,
                "diagnosticCount": 1,
                "outcomes": {
                    "Static": 0, "Context-dependent": 0,
                    "Runtime-unknown": 0,
                },
            },
            "declarations": [],
            "types": [],
            "logicItems": [],
            "diagnostics": [{
                "code": "invalid-input",
                "severity": "error",
                "message": "CML content must be a string.",
                "line": 1,
                "column": 1,
                "confidence": "high",
                "sourceRange": {
                    "start": {"offset": 0, "line": 1, "column": 1},
                    "end": {"offset": 0, "line": 1, "column": 1},
                },
            }],
            "dependencyEdges": [],
        }

    tokens, diagnostics = _tokenize_cml(content)
    parser = _CmlParser(content, tokens, diagnostics)
    declarations, types, raw_logic, unknown = parser.parse()

    global_symbols = {}
    type_symbols = {}
    for declaration in declarations:
        name = declaration.get("name")
        if name:
            global_symbols.setdefault(name, declaration)
    for type_record in types:
        if type_record.get("name"):
            type_symbols[type_record["name"]] = type_record

    member_symbols = {}
    for type_record in types:
        scope = type_record.get("name")
        if not scope:
            continue
        member_symbols[scope] = {
            member.get("name"): member
            for member in (
                type_record.get("variables", [])
                + type_record.get("relations", []))
            if member.get("name")
        }

    def visible_members(scope):
        visible, seen = {}, set()
        current = scope
        complete = True
        while current and current not in seen:
            seen.add(current)
            visible.update(member_symbols.get(current, {}))
            type_record = type_symbols.get(current)
            if not type_record:
                complete = False
                break
            current = type_record.get("parent")
        if current in seen:
            complete = False
        return visible, complete

    dependency_edges = []
    edge_keys = set()

    def add_edge(source, target, kind, line, resolved=True):
        key = (source, target, kind)
        if key in edge_keys:
            return
        edge_keys.add(key)
        dependency_edges.append({
            "from": source,
            "to": target,
            "kind": kind,
            "line": line,
            "resolved": bool(resolved),
        })

    for type_record in types:
        type_name = type_record.get("name") or "<unknown>"
        parent = type_record.get("parent")
        if parent:
            add_edge(
                f"type:{type_name}", f"type:{parent}", "inherits",
                type_record["line"], parent in type_symbols)
            if parent not in type_symbols:
                diagnostics.append(_cml_diag(
                    "unresolved-parent",
                    f"Parent type '{parent}' is not declared in this model.",
                    tokens[next(
                        (index for index, token in enumerate(tokens)
                         if token.line == type_record["line"]
                         and token.value == type_name), 0)],
                    "warning", confidence="high"))
        for relation in type_record.get("relations", []):
            target = relation.get("target")
            relation_id = f"{type_name}.{relation.get('name') or '?'}"
            if target:
                add_edge(
                    relation_id, f"type:{target}", "relation-target",
                    relation["line"], target in type_symbols)
            if relation.get("cardinality") is None:
                start_offset = relation["sourceRange"]["start"]["offset"]
                token = next(
                    (candidate for candidate in tokens
                     if candidate.start == start_offset), tokens[-1])
                diagnostics.append(_cml_diag(
                    "missing-relation-cardinality",
                    f"Relation '{relation_id}' has no explicit cardinality; "
                    "runtime/default cardinality is not inferred.",
                    token, "info", confidence="high"))

    logic_items = []
    outcomes = {"Static": 0, "Context-dependent": 0, "Runtime-unknown": 0}
    incomplete_logic_count = 0
    for number, record in enumerate(raw_logic, 1):
        item_id = f"logic-{number}"
        condition_ast = record.get("conditionAst")
        references = _cml_references(condition_ast)
        malformed = record.get("malformed") or (
            condition_ast and condition_ast.get("kind") == "unknownExpression")
        if malformed:
            incomplete_logic_count += 1
            outcome = "Runtime-unknown"
            confidence = "low"
            applies = "Unknown; syntax could not be fully analyzed."
            does_not_apply = "Unknown; syntax could not be fully analyzed."
            runtime_needed = True
        elif references:
            outcome = "Context-dependent"
            confidence = "high"
            names = ", ".join(reference["name"] for reference in references)
            applies = f"When the condition over {names} evaluates true."
            does_not_apply = f"When the condition over {names} evaluates false."
            runtime_needed = True
        else:
            outcome = "Runtime-unknown"
            confidence = "medium"
            applies = "Requires CML runtime semantics."
            does_not_apply = "Requires CML runtime semantics."
            runtime_needed = True
        outcomes[outcome] += 1

        condition = {
            "raw": condition_ast.get("raw", "") if condition_ast else "",
            "sourceRange": (
                condition_ast.get("sourceRange") if condition_ast else None),
            # Phase 1 never evaluates even literal-looking conditions. Runtime
            # scope, bindings, and solver behavior remain authoritative.
            "constant": False,
        }
        item = {
            "id": item_id,
            "kind": record["kind"],
            "name": record.get("name"),
            "scope": record["scope"],
            "line": record["line"],
            "raw": record["raw"],
            "condition": condition,
            "conditionExpression": _cml_expression_view(condition_ast),
            "conditionBreakdown": _cml_condition_breakdown(condition_ast),
            "effect": _cml_effect(record["kind"], record["arguments"]),
            "references": references,
            "confidence": confidence,
            "outcome": outcome,
            "appliesWhen": applies,
            "doesNotApplyWhen": does_not_apply,
            "runtimeNeeded": runtime_needed,
            "complete": not malformed,
            "runtimeUnknownReason": (
                "Condition syntax is incomplete or materially damaged."
                if malformed else None),
            "parseDiagnosticCodes": record.get(
                "parseDiagnosticCodes", []),
        }
        logic_items.append(item)

        visible, hierarchy_complete = visible_members(record["scope"])
        for reference in references:
            name = reference["name"]
            resolved_target = None
            if name in visible:
                resolved_target = f"{record['scope']}.{name}"
            elif name in global_symbols:
                resolved_target = (
                    f"{global_symbols[name]['kind']}:{name}")
            elif name in type_symbols:
                resolved_target = f"type:{name}"
            elif name.lower() in _CML_BUILTINS or name.startswith("$"):
                continue
            add_edge(
                item_id, resolved_target or f"unresolved:{name}",
                "references", reference["line"],
                resolved_target is not None)
            if resolved_target is None:
                start_offset = reference["sourceRange"]["start"]["offset"]
                token = next(
                    (candidate for candidate in tokens
                     if candidate.start == start_offset), tokens[-1])
                if hierarchy_complete and reference.get("simple"):
                    diagnostics.append(_cml_diag(
                        "undefined-reference",
                        f"Simple reference '{name}' is not declared in scope "
                        f"'{record['scope']}', its inheritance chain, or at "
                        "top level.",
                        token, "warning", confidence="high"))
                else:
                    diagnostics.append(_cml_diag(
                        "unresolved-context-reference",
                        f"Reference '{name}' could not be resolved statically; "
                        "it may be supplied by an incomplete parent or runtime "
                        "context.",
                        token, "info", confidence="medium"))

    inbound_types = {
        edge["to"][5:] for edge in dependency_edges
        if edge["resolved"] and edge["to"].startswith("type:")
    }
    for type_record in types:
        name = type_record.get("name")
        if (not name or name in inbound_types
                or name.lower() in ("order", "lineitem")):
            continue
        start_offset = type_record["sourceRange"]["start"]["offset"]
        token = next(
            (candidate for candidate in tokens
             if candidate.start == start_offset), tokens[-1])
        diagnostics.append(_cml_diag(
            "candidate-unreachable-type",
            f"Type '{name}' has no detected inheritance, relation, or logic "
            "reference into it; it may be unreachable, externally selected, "
            "or catalog-bound.",
            token, "info", confidence="low"))

    error_count = sum(
        diagnostic["severity"] == "error" for diagnostic in diagnostics)
    summary = {
        "declarationCount": len(declarations),
        "typeCount": len(types),
        "logicItemCount": len(logic_items),
        "diagnosticCount": len(diagnostics),
        "errorCount": error_count,
        "unknownNodeCount": len(unknown),
        "incompleteLogicItemCount": incomplete_logic_count,
        "dependencyEdgeCount": len(dependency_edges),
        "outcomes": outcomes,
    }
    return {
        "schemaVersion": "1.1",
        "ok": error_count == 0 and incomplete_logic_count == 0,
        "summary": summary,
        "declarations": declarations,
        "types": types,
        "logicItems": logic_items,
        "diagnostics": diagnostics,
        "dependencyEdges": dependency_edges,
    }


_SEMANTIC_POSITION_FIELDS = {
    "raw", "sourceRange", "line", "column", "start", "end",
    "startLine", "endLine", "startColumn", "endColumn",
    "parseDiagnosticCodes", "syntaxComplete", "malformed",
}


def _semantic_value(value):
    """Canonical AST value without formatting or source-position metadata."""
    if isinstance(value, dict):
        return {
            key: _semantic_value(item)
            for key, item in sorted(value.items())
            if key not in _SEMANTIC_POSITION_FIELDS
        }
    if isinstance(value, list):
        return [_semantic_value(item) for item in value]
    return value


def _semantic_line_range(source_range):
    if not isinstance(source_range, dict):
        return None
    start = source_range.get("start") or {}
    end = source_range.get("end") or {}
    start_line = max(1, int(start.get("line") or 1))
    end_line = max(start_line, int(end.get("line") or start_line))
    return {"startLine": start_line, "endLine": end_line}


def _semantic_entity(identity, kind, name, scope, source_range, raw,
                     properties):
    return {
        "identity": identity,
        "kind": kind,
        "name": name,
        "scope": scope,
        "range": _semantic_line_range(source_range),
        "raw": raw or "",
        "properties": _semantic_value(properties),
    }


def _semantic_index(content):
    """Parse CML once and index named entities independently of line order."""
    tokens, diagnostics = _tokenize_cml(content)
    parser = _CmlParser(content, tokens, diagnostics)
    declarations, types, logic, unknown = parser.parse()
    entities = []

    for declaration in declarations:
        kind = declaration.get("kind")
        name = declaration.get("name")
        if kind == "type" or not name:
            continue
        entities.append(_semantic_entity(
            f"{kind}:{name}", kind, name, "top-level",
            declaration.get("sourceRange"), declaration.get("raw"), {
                "dataType": declaration.get("dataType"),
                "annotations": declaration.get("annotations") or [],
                "value": declaration.get("value"),
            }))

    for type_record in types:
        type_name = type_record.get("name")
        if not type_name:
            continue
        entities.append(_semantic_entity(
            f"type:{type_name}", "type", type_name, "top-level",
            type_record.get("sourceRange"), type_record.get("raw"), {
                "parent": type_record.get("parent"),
                "annotations": type_record.get("annotations") or [],
                "stub": bool(type_record.get("stub")),
            }))
        for variable in type_record.get("variables") or []:
            name = variable.get("name")
            if not name:
                continue
            entities.append(_semantic_entity(
                f"variable:{type_name}:{name}", "variable", name, type_name,
                variable.get("sourceRange"), variable.get("raw"), {
                    "dataType": variable.get("dataType"),
                    "annotations": variable.get("annotations") or [],
                    "domain": variable.get("domain"),
                }))
        for relation in type_record.get("relations") or []:
            name = relation.get("name")
            if not name:
                continue
            entities.append(_semantic_entity(
                f"relation:{type_name}:{name}", "relation", name, type_name,
                relation.get("sourceRange"), relation.get("raw"), {
                    "target": relation.get("target"),
                    "cardinality": relation.get("cardinality"),
                    "order": relation.get("order"),
                    "body": relation.get("body"),
                    "annotations": relation.get("annotations") or [],
                }))

    for record in logic:
        kind = record.get("kind") or "logic"
        scope = record.get("scope") or "top-level"
        name = record.get("name")
        properties = {
            "annotations": record.get("annotations") or [],
            "arguments": record.get("arguments") or [],
            "condition": record.get("conditionAst"),
        }
        if name:
            identity = f"logic:{scope}:{kind}:{name}"
        else:
            # Anonymous rules have no platform identity. An exact structural
            # fingerprint safely recognizes moved/unchanged rules without
            # guessing that two different rules are modifications.
            fingerprint = hashlib.sha256(json.dumps(
                _semantic_value(properties), sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest()[:16]
            identity = f"logic:{scope}:{kind}:anonymous:{fingerprint}"
        entities.append(_semantic_entity(
            identity, kind, name, scope, record.get("sourceRange"),
            record.get("raw"), properties))

    issues = [{
        "code": item.get("code"),
        "severity": item.get("severity"),
        "message": item.get("message"),
        "line": item.get("line"),
    } for item in diagnostics if item.get("severity") in ("error", "warning")]
    return entities, issues, len(unknown)


def _semantic_property_changes(source, target):
    source_props = source.get("properties") or {}
    target_props = target.get("properties") or {}
    changes = []
    for prop in sorted(set(source_props) | set(target_props)):
        if source_props.get(prop) != target_props.get(prop):
            changes.append({
                "property": prop,
                "source": source_props.get(prop),
                "target": target_props.get(prop),
            })
    return changes


def _semantic_result(status, source=None, target=None, changes=None,
                     reason=None):
    entity = source or target or {}
    result = {
        "kind": entity.get("kind"),
        "identity": entity.get("identity"),
        "name": entity.get("name"),
        "scope": entity.get("scope"),
        "status": status,
        "sourceRange": source.get("range") if source else None,
        "targetRange": target.get("range") if target else None,
        "propertyChanges": changes or [],
    }
    if reason:
        result["reason"] = reason
    return result


def compare_cml_semantics(source_content, target_content):
    """Compare parsed CML entities by stable structural identity in O(n)."""
    source_entities, source_issues, source_unknown = _semantic_index(
        source_content or "")
    target_entities, target_issues, target_unknown = _semantic_index(
        target_content or "")
    source_map, target_map = {}, {}
    for entity in source_entities:
        source_map.setdefault(entity["identity"], []).append(entity)
    for entity in target_entities:
        target_map.setdefault(entity["identity"], []).append(entity)

    results = []
    for identity in sorted(set(source_map) | set(target_map)):
        source_group = source_map.get(identity, [])
        target_group = target_map.get(identity, [])
        if len(source_group) > 1 or len(target_group) > 1:
            remaining_target = list(target_group)
            unmatched_source = []
            for source in source_group:
                exact_index = next((
                    index for index, target in enumerate(remaining_target)
                    if source["properties"] == target["properties"]), None)
                if exact_index is None:
                    unmatched_source.append(source)
                    continue
                target = remaining_target.pop(exact_index)
                moved = (
                    (source.get("range") or {}).get("startLine")
                    != (target.get("range") or {}).get("startLine"))
                results.append(_semantic_result(
                    "MOVED" if moved else "UNCHANGED", source, target))
            if len(unmatched_source) == 1 and len(remaining_target) == 1:
                source, target = unmatched_source[0], remaining_target[0]
                results.append(_semantic_result(
                    "MODIFIED", source, target,
                    _semantic_property_changes(source, target)))
            else:
                for source in unmatched_source:
                    results.append(_semantic_result(
                        "AMBIGUOUS", source=source,
                        reason="Duplicate semantic identity in source or target."))
                for target in remaining_target:
                    results.append(_semantic_result(
                        "AMBIGUOUS", target=target,
                        reason="Duplicate semantic identity in source or target."))
            continue

        source = source_group[0] if source_group else None
        target = target_group[0] if target_group else None
        if source is None:
            results.append(_semantic_result("ADDED", target=target))
        elif target is None:
            results.append(_semantic_result("REMOVED", source=source))
        else:
            changes = _semantic_property_changes(source, target)
            if changes:
                results.append(_semantic_result(
                    "MODIFIED", source, target, changes))
            else:
                moved = (
                    (source.get("range") or {}).get("startLine")
                    != (target.get("range") or {}).get("startLine"))
                results.append(_semantic_result(
                    "MOVED" if moved else "UNCHANGED", source, target))

    counts = {
        status: sum(item["status"] == status for item in results)
        for status in (
            "UNCHANGED", "MOVED", "ADDED", "REMOVED", "MODIFIED", "AMBIGUOUS")
    }
    return {
        "schemaVersion": "1.0",
        "entities": results,
        "stats": counts,
        "sourceParseIssues": source_issues,
        "targetParseIssues": target_issues,
        "sourceUnknownCount": source_unknown,
        "targetUnknownCount": target_unknown,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default request logging
        pass

    def _send(self, code, body, content_type="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body)
        data = body if isinstance(body, bytes) else body.encode("utf-8")
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
            elif self.path in STATIC_ASSETS:
                filename, content_type = STATIC_ASSETS[self.path]
                with open(_static_asset_path(filename), "rb") as asset:
                    self._send(200, asset.read(), content_type)
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
                    qs.get("org", [""])[0], qs.get("model", [""])[0],
                    qs.get("versionId", [""])[0]))
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
                self._send(200, fetch_cml(
                    body.get("org"), body.get("model"),
                    body.get("versionId")))
            elif self.path == "/api/quit":
                self._send(200, {"ok": True, "bye": True})
                threading.Thread(
                    target=lambda: (time.sleep(0.3), self.server.shutdown()),
                    daemon=True).start()
            elif self.path == "/api/deploy":
                self._send(200, deploy_cml(
                    body.get("org"), body.get("model"),
                    body.get("targetVersionId"), body.get("content"),
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/rollback":
                self._send(200, rollback_cml(
                    body.get("org"), body.get("model"),
                    body.get("targetVersionId"), body.get("backupId"),
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/compare":
                self._send(200, compare_cml(
                    body.get("sourceOrg"), body.get("targetOrg"),
                    body.get("model"), body.get("sourceVersionId"),
                    body.get("targetVersionId")
                ))
            elif self.path == "/api/semantic/compare":
                self._send(200, compare_cml_semantics(
                    body.get("sourceContent") or "",
                    body.get("targetContent") or ""
                ))
            elif self.path == "/api/logic/analyze":
                self._send(200, analyze_cml_logic(body.get("content")))
            elif self.path == "/api/data":
                self._send(200, export_constraints(
                    body.get("org"), body.get("model"),
                    body.get("versionId"),
                    body.get("keyField") or DEFAULT_KEY_FIELD
                ))
            elif self.path == "/api/data/compare":
                self._send(200, compare_constraints(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model"),
                    body.get("sourceVersionId"), body.get("targetVersionId"),
                    body.get("keyField") or DEFAULT_KEY_FIELD
                ))
            elif self.path == "/api/data/deploy":
                self._send(200, deploy_constraints(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model"),
                    body.get("sourceVersionId"), body.get("targetVersionId"),
                    body.get("adds") or [], body.get("deletes") or [],
                    body.get("keyField") or DEFAULT_KEY_FIELD,
                    body.get("confirmTarget")
                ))
            elif self.path == "/api/data/restore":
                self._send(200, restore_association_archive(
                    body.get("targetOrg"), body.get("model"),
                    body.get("targetVersionId"),
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
STATIC_ASSETS = {
    "/favicon/favicon-96x96.png": ("favicon/favicon-96x96.png", "image/png"),
    "/favicon/favicon.svg": ("favicon/favicon.svg", "image/svg+xml"),
    "/favicon/favicon.ico": ("favicon/favicon.ico", "image/x-icon"),
    "/favicon/apple-touch-icon.png": ("favicon/apple-touch-icon.png", "image/png"),
    "/favicon/site.webmanifest": ("favicon/site.webmanifest", "application/manifest+json"),
    "/favicon/web-app-manifest-192x192.png": (
        "favicon/web-app-manifest-192x192.png", "image/png"),
    "/favicon/web-app-manifest-512x512.png": (
        "favicon/web-app-manifest-512x512.png", "image/png"),
    "/donate/upi-qr.png": ("donate/upi-qr.png", "image/png"),
    # Conventional browser fallback when no explicit <link> has been processed.
    "/favicon.ico": ("favicon/favicon.ico", "image/x-icon"),
}


def _static_asset_path(filename: str) -> str:
    """Resolve packaged browser assets for both supported launch locations."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = (
        os.path.join(script_dir, filename),
        os.path.join(script_dir, "..", filename),
        os.path.join(script_dir, "..", "salesforce-cml-tool", filename),
    )
    for candidate in candidates:
        resolved = os.path.abspath(candidate)
        if os.path.isfile(resolved):
            return resolved
    return os.path.abspath(candidates[1])


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
<link rel="icon" type="image/png" href="/favicon/favicon-96x96.png" sizes="96x96" />
<link rel="icon" type="image/svg+xml" href="/favicon/favicon.svg" />
<link rel="shortcut icon" href="/favicon/favicon.ico" />
<link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon.png" />
<meta name="apple-mobile-web-app-title" content="CML Tool" />
<meta name="theme-color" content="#3B82F6" />
<link rel="manifest" href="/favicon/site.webmanifest" />
<title>CML Tool — Fetch, Deploy &amp; Compare</title>
<script>(function(){try{var t=localStorage.getItem('cml-theme')||'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>
  :root {
    color-scheme: light;
    --bg:#f7f8fc; --panel:#ffffff; --gutter:#f0f3fa; --input-bg:#fbfcff;
    --line:#dce2ef; --text:#172033; --muted:#667085; --gutter-text:#8490a6; --comment:#9aa4b5;
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
    --line:#303b57; --text:#f4f7ff; --muted:#b5bfd3; --gutter-text:#7f8ba5; --comment:#929db2;
    --accent:#60a5fa; --accent-strong:#22d3ee; --green:#4ade80; --red:#f87171;
    --purple:#a78bfa; --amber:#fbbf24; --teal:#22d3ee;
    --ok-bg:color-mix(in srgb,var(--green) 13%,var(--panel)); --ok-text:#a7f3d0;
    --err-bg:color-mix(in srgb,var(--red) 13%,var(--panel)); --err-text:#fecdd3;
    --info-bg:color-mix(in srgb,var(--accent) 13%,var(--panel)); --info-text:#d9dcff;
    --teal-bg:color-mix(in srgb,var(--teal) 12%,var(--panel)); --teal-text:#a5f3fc;
    --shadow:0 20px 60px rgba(0,0,0,.30);
  }
  * { box-sizing: border-box; }
  html,body { width:100%; height:100%; max-width:100%; overflow:hidden; }
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
  .app-shell { height:100vh; min-height:0; display:grid; grid-template-columns:244px minmax(0,1fr); overflow:hidden; }
  .sidebar { position:relative; height:100vh; min-height:0; display:flex; flex-direction:column;
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
  .donate-link { color:var(--accent); }
  .donate-wrap { width:100%; position:relative; }
  .donate-options { display:grid; gap:5px; margin:3px 6px 8px 12px; padding-left:9px;
    border-left:1px solid var(--line); }
  .donate-options[hidden] { display:none; }
  .donate-option { width:100%; display:flex; align-items:center; gap:9px; padding:8px 10px;
    border:1px solid transparent; border-radius:9px; background:transparent; color:var(--text);
    font-size:12px; font-weight:700; text-align:left; text-decoration:none; cursor:pointer; }
  .donate-option:hover:not(:disabled) { border-color:var(--accent); background:var(--gutter); }
  .donate-option:disabled { color:var(--muted); cursor:not-allowed; opacity:.58; }
  .payment-icon { width:27px; height:22px; flex:0 0 27px; display:grid; place-items:center;
    border:1px solid currentColor; border-radius:6px; font-size:8px; font-weight:900;
    letter-spacing:-.03em; }
  .razorpay-icon { font-size:14px; font-style:italic; }
  .sidebar .credit { padding:10px 12px 0; margin:0; font-size:10px; line-height:1.5; color:var(--muted); }
  .donate-dialog { width:min(520px,calc(100vw - 28px)); max-width:100%; padding:0;
    border:1px solid var(--line); border-radius:18px; background:var(--panel);
    color:var(--text); }
  .donate-dialog::backdrop { background:rgba(9,14,26,.68); }
  .donate-dialog-body { padding:22px; }
  .donate-dialog-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
  .donate-dialog h2 { margin:0; font-size:20px; }
  .donate-dialog p { color:var(--muted); font-size:13px; }
  .donate-dialog .disclaimer { padding:10px 12px; border-radius:10px; background:var(--gutter);
    font-size:11px; line-height:1.55; }
  .donate-qr { display:block; width:min(330px,100%); max-height:54vh; object-fit:contain;
    margin:17px auto 0; border:1px solid var(--line); border-radius:12px; background:#fff; }
  .donate-actions { display:flex; align-items:center; gap:9px; flex-wrap:wrap; margin-top:18px; }
  .upi-note { margin:10px 0 0; font-size:11px !important; }

  /* ── Main area ────────────────────────────────────────────────── */
  .app-main { min-width:0; min-height:0; height:100vh; display:flex; flex-direction:column;
    overflow-y:auto; overflow-x:hidden; scrollbar-gutter:stable; }
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
  .conn-strip { display:flex; flex-wrap:wrap; gap:14px; align-items:flex-end; }
  .conn-strip > .field { flex:1 1 220px; max-width:100%; }
  .conn-strip > .field.model-field { flex:1 0 100%; width:100%; }
  .field { min-width:0; max-width:100%; }
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
  .combo-selected { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .selchip { flex:1; display:inline-flex; align-items:center; gap:8px; padding:9px 13px;
    border-radius:12px; background:linear-gradient(135deg,var(--accent),var(--accent-strong));
    color:#fff; font-weight:700; font-size:13px; min-width:0; }
  .selchip .name { overflow:visible; text-overflow:clip; white-space:normal; overflow-wrap:anywhere; }
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
  .btn-danger { background:linear-gradient(135deg,var(--red),color-mix(in srgb,var(--red) 75%,var(--text))); color:var(--on-accent);
    box-shadow:0 8px 20px color-mix(in srgb,var(--red) 22%,transparent); }
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

  /* Desktop CML actions */
  .cml-actions { display:grid; grid-template-columns:max-content minmax(0,1fr); gap:18px;
    align-items:stretch; margin-top:18px; }
  .fetch-action-panel { display:flex; align-items:flex-start; }
  .deploy-panel { display:grid; grid-template-columns:minmax(210px,.8fr) minmax(300px,1.35fr) max-content;
    gap:14px; align-items:end; padding:14px; border:1px solid var(--line);
    border-radius:16px; background:var(--gutter); min-width:0; }
  .deploy-panel .field select { width:100% !important; min-height:44px; }
  .deploy-action-stack { display:flex; flex-direction:column; align-items:stretch; gap:9px; }
  .cml-main-action { min-width:176px; min-height:56px; padding:14px 26px; font-size:15px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .cml-main-action svg { width:19px; height:19px; flex:none; }
  .restore-action { min-width:176px; min-height:52px; padding:12px 20px; font-size:14px;
    display:inline-flex; align-items:center; justify-content:center; gap:9px; }
  .restore-action svg { width:18px; height:18px; flex:none; }

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
  .editor-head .mini { display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end; }
  .editor-body { display:flex; align-items:stretch; min-width:0; background:var(--input-bg); }
  .editor-line-numbers { flex:0 0 auto; min-width:3.5em; height:640px;
    margin:0; padding:10px 10px; overflow:hidden; border-right:1px solid var(--line);
    background:var(--gutter); color:var(--gutter-text); text-align:right; user-select:none;
    pointer-events:none; white-space:pre; font-family:"JetBrains Mono","Fira Code",ui-monospace,
    "SF Mono",Menlo,Consolas,monospace; font-size:12.5px; line-height:1.5; }
  .editor-code-pane { position:relative; flex:1 1 auto; min-width:0; height:640px;
    background:var(--input-bg); }
  .editor-highlight,.editor-wrap textarea { position:absolute; inset:0; width:100%; height:100%;
    margin:0; padding:10px 13px; border:none; border-radius:0; font-size:12.5px;
    line-height:1.5; tab-size:2; white-space:pre; overflow-wrap:normal;
    font-family:"JetBrains Mono","Fira Code",ui-monospace,"SF Mono",Menlo,Consolas,monospace; }
  .editor-highlight { z-index:0; overflow:hidden; pointer-events:none; color:var(--text);
    background:var(--input-bg); }
  .editor-highlight .cml-comment { color:var(--comment); }
  .editor-wrap textarea { z-index:1; min-width:0; min-height:0; resize:none; overflow:auto;
    background:transparent; color:transparent; -webkit-text-fill-color:transparent;
    caret-color:var(--text); }
  .editor-wrap textarea::placeholder { color:var(--muted); -webkit-text-fill-color:var(--muted); }
  .editor-wrap textarea::selection { background:color-mix(in srgb,var(--accent) 28%,transparent); }
  .editor-wrap textarea:focus { border:none; box-shadow:none; }
  .key-field-compact { flex:0 1 170px !important; width:170px; max-width:170px !important; }

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
  .diff-panes { display:grid; grid-template-columns:minmax(0,1fr) 48px minmax(0,1fr);
    gap:8px; align-items:stretch; }
  .pane { flex:1; min-width:0; border:1px solid var(--line); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; }
  .pane-title { min-height:40px; padding:6px 10px; font-size:12px; font-weight:600; color:var(--muted);
    border-bottom:1px solid var(--line); background:var(--gutter); white-space:nowrap;
    overflow:hidden; display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .pane-title-text { overflow:hidden; text-overflow:ellipsis; }
  .pane-copy { display:inline-flex; align-items:center; gap:5px; flex:none; padding:4px 8px;
    border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--text);
    font-size:11px; font-weight:700; cursor:pointer; }
  .pane-copy:hover { border-color:var(--accent); color:var(--accent); background:var(--info-bg); }
  .pane-copy svg { width:13px; height:13px; }
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
  .diff-panes.hide-eq tr.eqrow { display:none; }
  .diff-opts { font-size:12px; color:var(--muted); display:inline-flex; align-items:center; gap:6px; }
  .diff-opts input { width:auto; }
  .merge-rail { min-width:0; border:1px solid var(--line); border-radius:12px; overflow:hidden;
    background:var(--gutter); display:flex; flex-direction:column; }
  .merge-rail .pane-title { padding-left:4px; padding-right:4px; text-align:center; }
  .merge-scroll { overflow:hidden; max-height:600px; flex:1; }
  table.merge-table { border-collapse:collapse; width:100%; font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
    font-size:12.5px; }
  .merge-table td { height:18.75px; padding:0; text-align:center; vertical-align:top; white-space:nowrap; }
  .merge-table tr:not(.eqrow) td { background:color-mix(in srgb,var(--accent) 5%,var(--gutter)); }
  .merge-arrow { width:34px; height:18px; padding:0; border:1px solid var(--accent);
    border-radius:6px; background:var(--panel); color:var(--accent); font-size:14px;
    font-weight:850; line-height:16px; cursor:pointer; }
  .merge-arrow:hover { background:var(--accent); color:var(--on-accent); transform:none; }
  .merge-workflow { margin:0 0 12px; padding:10px 12px; border:1px solid var(--accent);
    border-radius:12px; background:var(--info-bg); display:flex; align-items:center;
    justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .merge-workflow-copy { color:var(--text); font-size:12px; }
  .merge-workflow-actions { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }

  /* ── Semantic overlay (never replaces the two code panes) ───── */
  .summary-stack { display:flex; flex-direction:column; gap:3px; min-width:0; }
  .semantic-inline-summary { color:var(--muted); font-size:12px; }
  .semantic-inline-summary strong { color:var(--text); }
  .semantic-badge { display:inline-flex; align-items:center; margin:0 7px 0 1px;
    padding:1px 6px; border-radius:999px; font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
    font-size:9px; font-weight:850; line-height:14px; letter-spacing:.035em; text-transform:uppercase;
    vertical-align:1px; }
  .semantic-badge.moved { background:var(--info-bg); color:var(--accent); border:1px solid var(--accent); }
  .semantic-badge.modified { background:color-mix(in srgb,var(--amber) 13%,var(--panel)); color:var(--amber); border:1px solid var(--amber); }
  .semantic-badge.added { background:var(--ins-bg); color:var(--ins-line); border:1px solid var(--ins-line); }
  .semantic-badge.removed { background:var(--del-bg); color:var(--del-line); border:1px solid var(--del-line); }
  .semantic-badge.ambiguous { background:var(--chg-bg); color:var(--purple); border:1px solid var(--purple); }
  .pane-table tr.sem-moved .code { background:var(--info-bg); box-shadow:inset 4px 0 0 var(--accent); }
  .pane-table tr.sem-modified .code { background:color-mix(in srgb,var(--amber) 11%,var(--panel)); box-shadow:inset 4px 0 0 var(--amber); }
  .pane-table tr.sem-added .code { box-shadow:inset 4px 0 0 var(--ins-line); }
  .pane-table tr.sem-removed .code { box-shadow:inset 4px 0 0 var(--del-line); }
  .pane-table tr.sem-ambiguous .code { background:var(--chg-bg); box-shadow:inset 4px 0 0 var(--purple); }

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

  /* ── Logic explorer ───────────────────────────────────────────── */
  .logic-disclaimer { margin:0 0 16px; padding:13px 16px; border:2px solid var(--amber);
    border-radius:14px; background:color-mix(in srgb,var(--amber) 12%,var(--panel));
    color:var(--text); font-size:13px; font-weight:650; }
  .logic-controls { display:grid; grid-template-columns:minmax(220px,2fr) minmax(160px,1fr);
    gap:10px; margin:14px 0; }
  .logic-results { display:none; margin-top:16px; }
  .logic-results.show { display:block; }
  .logic-layout { display:grid; grid-template-columns:minmax(280px,.9fr) minmax(360px,1.4fr);
    gap:14px; align-items:start; margin-top:14px; }
  .logic-pane { min-width:0; border:1px solid var(--line); border-radius:14px;
    background:var(--input-bg); overflow:hidden; }
  .logic-pane-head { padding:10px 13px; border-bottom:1px solid var(--line);
    background:var(--gutter); color:var(--muted); font-size:11px; font-weight:800;
    letter-spacing:.05em; text-transform:uppercase; }
  .logic-list { max-height:580px; overflow:auto; padding:8px; }
  .logic-row { width:100%; display:block; text-align:left; padding:10px 11px; margin:0 0 7px;
    border:1px solid var(--line); border-left:4px solid var(--accent); border-radius:10px;
    background:var(--panel); color:var(--text); cursor:pointer; white-space:normal; }
  .logic-row:hover,.logic-row.active { border-color:var(--accent);
    background:color-mix(in srgb,var(--accent) 9%,var(--panel)); transform:none; }
  .logic-row .logic-row-title { display:flex; justify-content:space-between; gap:10px;
    font-size:13px; font-weight:750; }
  .logic-row .logic-row-meta { margin-top:4px; color:var(--muted); font-size:11px; }
  .logic-detail { min-height:260px; padding:16px; }
  .logic-detail-grid { display:grid; grid-template-columns:150px minmax(0,1fr); gap:9px 13px;
    font-size:13px; }
  .logic-detail-grid dt { color:var(--muted); font-weight:750; }
  .logic-detail-grid dd { margin:0; min-width:0; white-space:pre-wrap; word-break:break-word; }
  .logic-code { font-family:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace; }
  .condition-evaluation { margin-bottom:18px; border:1px solid color-mix(in srgb,var(--purple) 45%,var(--line));
    border-radius:14px; overflow:hidden; background:var(--panel); }
  .condition-evaluation-head { padding:14px 16px; color:var(--text);
    background:linear-gradient(135deg,color-mix(in srgb,var(--purple) 15%,var(--panel)),
      color-mix(in srgb,var(--accent) 11%,var(--panel))); border-bottom:1px solid var(--line); }
  .condition-evaluation-title { display:flex; align-items:center; gap:9px; flex-wrap:wrap;
    margin:0 0 5px; font-size:15px; font-weight:800; }
  .condition-join { display:inline-flex; align-items:center; padding:3px 9px; border-radius:999px;
    background:var(--purple); color:var(--on-accent); font-size:10px; font-weight:850;
    letter-spacing:.06em; }
  .condition-summary,.condition-fail { margin:4px 0 0; font-size:12.5px; line-height:1.5; }
  .condition-fail { color:var(--err-text); }
  .condition-explanation { margin:10px 16px 0; padding:10px 12px; border-radius:10px;
    background:var(--info-bg); color:var(--info-text); font-size:12px; }
  .condition-tree { padding:14px 16px 16px; }
  .condition-group { margin-top:10px; padding:11px; border:1px solid var(--line);
    border-radius:11px; background:var(--input-bg); }
  .condition-group:first-child { margin-top:0; }
  .condition-group-head { display:flex; align-items:flex-start; gap:8px; flex-wrap:wrap;
    margin-bottom:8px; font-size:12px; }
  .condition-group-head strong { color:var(--text); }
  .condition-group-summary { color:var(--muted); flex:1 1 220px; }
  .condition-children { display:grid; gap:9px; }
  .condition-clause { border:1px solid var(--line); border-left:4px solid var(--accent);
    border-radius:10px; padding:11px 12px; background:var(--panel); min-width:0; }
  .condition-clause-head { display:flex; align-items:flex-start; justify-content:space-between;
    gap:10px; margin-bottom:6px; }
  .condition-clause-title { font-size:12px; font-weight:800; color:var(--text); }
  .condition-line { border:0; background:none; color:var(--accent); padding:0; width:auto;
    font:inherit; font-size:11px; font-weight:800; cursor:pointer; white-space:nowrap; }
  .condition-line:hover { text-decoration:underline; }
  .condition-plain { margin:0 0 8px; font-size:13px; font-weight:700; line-height:1.5; }
  .condition-fields { display:grid; grid-template-columns:minmax(105px,.35fr) minmax(0,1fr);
    gap:5px 10px; margin:0; font-size:11.5px; }
  .condition-fields dt { color:var(--muted); font-weight:750; }
  .condition-fields dd { margin:0; min-width:0; overflow-wrap:anywhere; }
  .condition-runtime { color:var(--amber); font-weight:700; }
  .condition-raw-detail { margin:0 16px 16px; padding-top:11px; border-top:1px solid var(--line);
    font-size:11.5px; color:var(--muted); }
  .condition-raw-detail summary { cursor:pointer; font-weight:750; }
  .condition-raw-detail code { display:block; margin-top:7px; padding:9px 10px;
    border-radius:8px; background:var(--gutter); color:var(--text); white-space:pre-wrap;
    overflow-wrap:anywhere; }
  .logic-empty { padding:18px; color:var(--muted); font-size:13px; text-align:center; }

  /* ── Responsive ───────────────────────────────────────────────── */
  @media (max-width:1050px) {
    .app-shell { display:flex; flex-direction:column; height:100vh; }
    .sidebar { position:relative; height:auto; min-height:auto; flex:0 0 auto;
      padding:9px 12px; flex-direction:row;
      align-items:center; gap:12px; border-right:0; border-bottom:1px solid var(--line); }
    .app-main { height:auto; min-height:0; flex:1 1 auto; overflow-y:auto; }
    .brand { padding:0; min-width:max-content; }
    .brand-mark { width:30px; height:30px; }
    .brand small,.side-label { display:none; }
    .side-menu { display:flex; flex:1; gap:4px; overflow-x:auto; scrollbar-width:none; }
    .side-menu::-webkit-scrollbar { display:none; }
    .side-nav { width:auto; min-width:max-content; padding:7px 10px; }
    .side-nav:hover { transform:none; }
    .side-nav.active { box-shadow:inset 0 -2px 0 var(--accent); }
    .sidebar-footer { display:flex; flex:0 0 auto; align-items:center; gap:4px;
      margin:0 0 0 auto; padding:0; border:0; }
    .sidebar-footer .about-link { width:auto; min-width:max-content; padding:7px 9px; }
    .sidebar-footer .credit { display:none; }
    .donate-wrap { width:auto; }
    .donate-options { position:absolute; z-index:40; top:calc(100% + 6px); right:0;
      width:190px; margin:0; padding:7px; border:1px solid var(--line); border-radius:11px;
      background:var(--panel); }
    .topbar { min-height:80px; }
    .conn-strip { grid-template-columns:1fr 1fr; }
    .logic-controls { grid-template-columns:1fr 1fr; }
  }
  @media (max-width:700px) {
    .topbar { flex-direction:column; align-items:flex-start; gap:8px; }
    .top-actions { width:100%; justify-content:space-between; }
    .conn-strip { grid-template-columns:1fr; }
    .diff-panes { grid-template-columns:1fr; }
    .merge-rail { display:none; }
    .tabs { width:100%; }
    .tab { flex:1; }
    .deploy-group { flex-wrap:wrap; }
    .logic-controls,.logic-layout { grid-template-columns:1fr; }
    .logic-detail-grid { grid-template-columns:1fr; gap:3px; }
    .logic-detail-grid dd { margin-bottom:8px; }
    .condition-fields { grid-template-columns:1fr; gap:2px; }
    .condition-fields dd { margin-bottom:6px; }
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
        <span>Constraint Data Deploy</span>
      </button>
      <button class="side-nav" data-view="logic">
        <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M8 4h8M8 20h8M12 4v5M12 15v5M5 9h14v6H5z"/></svg></span>
        <span>Logic Explorer</span>
      </button>
    </nav>
    <div class="sidebar-footer">
      <div class="donate-wrap">
        <button type="button" class="about-link donate-link" id="donateBtn"
          aria-expanded="false" aria-controls="donateOptions">
          <span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M12 21s-7-4.35-9.33-8.28C.8 9.56 2.14 5.5 5.8 4.55 8 3.98 10.12 5 12 7c1.88-2 4-3.02 6.2-2.45 3.66.95 5 5.01 3.13 8.17C19 16.65 12 21 12 21z"/></svg></span>
          <span>Donate</span>
        </button>
        <div class="donate-options" id="donateOptions" hidden>
          <button type="button" class="donate-option" id="donateUpiBtn">
            <span class="payment-icon upi-icon" aria-hidden="true">UPI</span>
            <span>UPI</span>
          </button>
          <a class="donate-option" id="donateRazorpayBtn"
            href="https://razorpay.me/@mpancholi" target="_blank"
            rel="noopener noreferrer" title="Open secure Razorpay payment page">
            <span class="payment-icon razorpay-icon" aria-hidden="true">R</span>
            <span>Razorpay</span>
          </a>
        </div>
      </div>
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
        <button class="tab" data-view="data">Constraint Data Deploy</button>
        <button class="tab" data-view="logic">Logic Explorer</button>
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
            <label for="targetVersion">Target exact version (compare-with)</label>
            <select id="targetVersion"><option value="">None — select target org and source version</option></select>
          </div>
          <div class="field model-field">
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
                <button class="ghost" id="lineCommentBtn" title="Toggle // on the selected line or lines (Cmd+/)">// Line comment</button>
                <button class="ghost" id="blockCommentBtn" title="Wrap or unwrap the selection with /* and */">/* */ Block comment</button>
                <button class="ghost" id="lintBtn" title="Scan against built-in best-practice rules">Check best practices</button>
                <button class="ghost" id="copyBtn">Copy</button>
              </div>
            </div>
            <div class="editor-body">
              <pre class="editor-line-numbers" id="contentLineNumbers" aria-hidden="true">1</pre>
              <div class="editor-code-pane">
                <pre class="editor-highlight" id="contentHighlight" aria-hidden="true"></pre>
                <textarea id="content" placeholder="Fetched CML appears here. You can also paste CML and Deploy it." spellcheck="false" wrap="off"></textarea>
              </div>
            </div>
          </div>

          <div class="cml-actions">
            <div class="fetch-action-panel">
              <button class="btn btn-primary cml-main-action" id="fetchBtn">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
                Fetch CML
              </button>
            </div>
            <div class="deploy-panel">
              <div class="field">
                <label for="deployOrg">Deploy to org</label>
                <select id="deployOrg"><option>Loading orgs…</option></select>
              </div>
              <div class="field">
                <label for="deployVersion">Target exact CML version</label>
                <select id="deployVersion"><option value="">None — select deployment target</option></select>
              </div>
              <div class="deploy-action-stack">
                <button class="btn btn-green cml-main-action" id="deployBtn">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V3M7 8l5-5 5 5"/><path d="M5 21h14a2 2 0 0 0 2-2v-4M3 15v4a2 2 0 0 0 2 2"/></svg>
                  Deploy CML
                </button>
                <button class="ghost restore-action" id="rollbackBtn" title="Restore the newest saved backup for this target and model">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>
                  Restore Backup CML
                </button>
              </div>
            </div>
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
                <p>Review a VS Code-style side-by-side diff and apply selected source changes to a target draft.</p>
              </div>
            </div>
            <button class="btn btn-purple" id="compareBtn">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target
            </button>
          </div>

          <div class="diff" id="diff">
            <div class="diff-head">
              <div class="summary-stack">
                <div class="summary" id="diffSummary"></div>
                <div class="semantic-inline-summary" id="semanticInlineSummary" hidden></div>
              </div>
              <div class="legend">
                <span id="lineLegend">
                  <span><i class="lg-chg">~</i>Changed</span>
                  <span><i class="lg-del">&minus;</i>Only in source</span>
                  <span><i class="lg-ins">+</i>Only in target</span>
                </span>
                <label class="diff-opts" id="onlyDiffsWrap"><input type="checkbox" id="onlyDiffs" /> Show only differences</label>
                <label class="diff-opts" title="Show a separate structural summary without hiding either code pane"><input type="checkbox" id="semanticDiff" /> Semantic summary</label>
              </div>
            </div>
            <div class="merge-workflow" id="mergeWorkflow" hidden>
              <div class="merge-workflow-copy" id="mergeWorkflowCopy"></div>
              <div class="merge-workflow-actions">
                <button class="ghost" id="resetMergeBtn">Reset target draft</button>
                <button class="btn btn-green" id="reviewMergeBtn">Review &amp; Deploy merged target</button>
              </div>
            </div>
            <div class="diff-panes" id="diffPanes">
              <div class="pane">
                <div class="pane-title"><span class="pane-title-text" id="srcTitle">Source</span></div>
                <div class="pane-scroll" id="srcScroll"><table class="pane-table" id="srcTable"></table></div>
              </div>
              <div class="merge-rail" aria-label="Merge source changes into target draft">
                <div class="pane-title" title="Apply a source change to the target draft">→</div>
                <div class="merge-scroll" id="mergeScroll"><table class="merge-table" id="mergeTable"></table></div>
              </div>
              <div class="pane">
                <div class="pane-title">
                  <span class="pane-title-text" id="tgtTitle">Target</span>
                  <button type="button" class="pane-copy" id="copyTargetCmlBtn" title="Copy the complete target CML or current target draft">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3"/></svg>
                    <span>Copy</span>
                  </button>
                </div>
                <div class="pane-scroll" id="tgtScroll"><table class="pane-table" id="tgtTable"></table></div>
              </div>
            </div>
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
                <h2>Constraint Data Deploy</h2>
                <p>View, compare, and deploy ExpressionSetConstraintObj rows (Product associations).</p>
              </div>
            </div>
          </div>

          <p class="sub" style="margin:0 0 14px;">Deploying CML code alone doesn't recreate Product associations. These rows are matched across orgs by a <strong>foreign key</strong> — a field whose value is stable across orgs — instead of by record Id.</p>
          <p class="meta" style="margin:0 0 14px;"><strong>Safe deployment boundary:</strong> catalog records are read-only. The tool reports missing products, classifications, attributes, component groups, and relationships, but it only writes CML content and ExpressionSetConstraintObj associations.</p>

          <div class="conn-strip" style="gap:14px;align-items:end;margin-bottom:16px;">
            <div class="field key-field-compact">
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
              <p class="meta" style="margin:5px 0 0;"><code>Name</code> may be selected only when it is present and uniquely portable in both orgs; prefer a stable custom/external Id.</p>
            </div>
            <div class="btn-row" style="margin-top:0;gap:8px;">
              <button class="btn btn-primary" id="loadDataBtn">View data</button>
              <button class="btn btn-purple" id="compareDataBtn">Compare data</button>
              <button class="btn btn-danger" id="stopCompareDataBtn" hidden>Stop Comparison</button>
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
                    <option value="ambiguous-key">Ambiguous portable keys</option>
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

      <!-- ══════════════ VIEW: LOGIC EXPLORER ══════════════ -->
      <div class="view-panel" id="view-logic">
        <div class="card">
          <div class="card-head">
            <div class="card-title">
              <span class="step-dot" style="background:linear-gradient(135deg,var(--purple),var(--accent));">5</span>
              <div>
                <h2>Logic Explorer</h2>
                <p>Translate the CML currently in the editor into a plain-English local logic explanation.</p>
              </div>
            </div>
            <div class="btn-row" style="margin-top:0;">
              <button class="ghost" id="logicEditorBtn">Open fetch/editor</button>
              <button class="btn btn-purple" id="logicAnalyzeBtn">Analyze logic</button>
            </div>
          </div>

          <div class="logic-disclaimer">
            Local explanations are guidance only, not Salesforce compile validation or proof of runtime behavior.
          </div>
          <p class="sub" style="margin:0;">Fetch or paste CML in the Fetch &amp; Deploy editor, then analyze it here.</p>
          <div class="status" id="logicStatus"></div>

          <div class="logic-results" id="logicResults">
            <div class="logic-controls">
              <div class="field">
                <label for="logicSearch">Search logic</label>
                <input id="logicSearch" placeholder="Search scope, condition, effect, or dependency…" autocomplete="off" />
              </div>
              <div class="field">
                <label for="logicKindFilter">Logic kind</label>
                <select id="logicKindFilter"><option value="">All kinds</option></select>
              </div>
            </div>

            <div class="logic-layout">
              <section class="logic-pane" aria-label="Logic items">
                <div class="logic-pane-head">Logic items <span id="logicVisibleCount"></span></div>
                <div class="logic-list" id="logicList"></div>
              </section>
              <section class="logic-pane" aria-label="Logic detail">
                <div class="logic-pane-head">Plain-English detail</div>
                <div class="logic-detail" id="logicDetail"></div>
              </section>
            </div>
          </div>
        </div>
      </div>

    </div><!-- .wrap -->
  </main>
</div><!-- .app-shell -->

<dialog class="donate-dialog" id="donateDialog" aria-labelledby="donateTitle">
  <div class="donate-dialog-body">
    <div class="donate-dialog-head">
      <div>
        <div class="eyebrow">Optional contribution</div>
        <h2 id="donateTitle">UPI</h2>
      </div>
      <button type="button" class="ghost" id="donateCloseBtn" aria-label="Close donation dialog">Close</button>
    </div>
    <img class="donate-qr" src="/donate/upi-qr.png" alt="UPI payment QR code" />
    <p class="disclaimer">Contributions do not purchase support, features, priority
      service, or warranty. This project is not affiliated with or endorsed by Salesforce.</p>
    <div class="donate-actions">
      <a class="btn btn-primary" id="upiDonateLink"
        href="upi://pay?pa=mpancholi17%40ybl&amp;pn=Mritunjaya%20Pancholi&amp;tn=Support%20CML%20Tool&amp;cu=INR">
        Open UPI
      </a>
      <button type="button" class="ghost" id="copyUpiBtn" data-upi="mpancholi17@ybl">Copy UPI ID</button>
    </div>
    <p class="upi-note">Scan the QR code or open UPI. On desktop, copy the UPI ID.</p>
  </div>
</dialog>

<script>
  const $ = (id) => document.getElementById(id);
  const CSRF_TOKEN = "__CML_CSRF_TOKEN__";

  // ── Navigation ──────────────────────────────────────────────────
  const PAGE_META = {
    fetch:   { title:"Fetch &amp; Deploy",  sub:"Pick a source org — CMLs load automatically. Fetch, edit, and deploy to any org." },
    compare: { title:"Compare",             sub:"Use a VS Code-style diff to review and merge source changes into a guarded target draft." },
    lint:    { title:"Best Practices",      sub:"Client-side CML linter — checks rules, scores quality, and provides paste-ready fixes." },
    data:    { title:"Constraint Data Deploy", sub:"View, compare, and deploy ExpressionSetConstraintObj rows (Product associations)." },
    logic:   { title:"Logic Explorer",      sub:"Plain-English local logic explanation for the CML currently in the editor." },
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

  const orgSel = $("org"), targetSel = $("targetOrg"), targetVersionSel = $("targetVersion"), model = $("model"), content = $("content"), status = $("status");
  const contentLineNumbers = $("contentLineNumbers"), contentHighlight = $("contentHighlight");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), rollbackBtn = $("rollbackBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const lineCommentBtn = $("lineCommentBtn"), blockCommentBtn = $("blockCommentBtn");
  const cmlFilter = $("cmlFilter"), reloadBtn = $("reloadBtn"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName"), changeModelBtn = $("changeModelBtn");
  const deployOrgSel = $("deployOrg"), deployVersionSel = $("deployVersion");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable"), mergeTable = $("mergeTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll"), mergeScroll = $("mergeScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const lintPanelBtn = $("lintPanelBtn"), lintPanel = $("lintPanel"), lintStatus = $("lintStatus");
  const semanticChk = $("semanticDiff"), semanticInlineSummary = $("semanticInlineSummary");
  const lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  const mergeWorkflow = $("mergeWorkflow"), mergeWorkflowCopy = $("mergeWorkflowCopy");
  const resetMergeBtn = $("resetMergeBtn"), reviewMergeBtn = $("reviewMergeBtn");
  const copyTargetCmlBtn = $("copyTargetCmlBtn");
  let lastCompare = null;
  let activeMergeHunks = [];
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), stopCompareDataBtn = $("stopCompareDataBtn"), keyField = $("keyField");
  const keyName = () => (keyField.value || "Global_Key__c").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
  const copyExcelBtn = $("copyExcelBtn");
  const results = $("results");
  const logicAnalyzeBtn = $("logicAnalyzeBtn"), logicEditorBtn = $("logicEditorBtn");
  const logicStatus = $("logicStatus"), logicResults = $("logicResults");
  const logicSearch = $("logicSearch"), logicKindFilter = $("logicKindFilter");
  const logicList = $("logicList"), logicDetail = $("logicDetail");
  const logicVisibleCount = $("logicVisibleCount");
  const donateBtn = $("donateBtn"), donateOptions = $("donateOptions");
  const donateUpiBtn = $("donateUpiBtn"), donateDialog = $("donateDialog");
  const donateCloseBtn = $("donateCloseBtn"), copyUpiBtn = $("copyUpiBtn");
  let allModels = [];
  let reconnecting = false;
  let dataRows = [];        // current rows shown in the data table
  let dataMode = "single";  // "single" (one org) or "compare"
  let currentKeyField = "Global_Key__c";  // foreign key the shown data was matched on
  let logicAnalysis = null;
  let selectedLogicId = null;
  let dataCompareController = null;
  const selectedSourceVersion = () => allModels.find(m => m.versionId === model.value) || null;
  const selectedModelName = () => (selectedSourceVersion() || {}).name || "";
  const selectedVersionLabel = (m) => m
    ? `${m.name} · V${m.version} · ${m.status || "Unknown"} · ${m.versionId}`
    : "";

  // Size native picklists from their current option text. Containers wrap, so
  // a long exact-version label gets room instead of forcing button truncation.
  function fitPicklist(select) {
    if (!select) return;
    const texts = Array.from(select.options || []).map(option =>
      (option.textContent || "").trim());
    const selectedText = select.selectedOptions?.[0]?.textContent?.trim() || "";
    select.title = selectedText;
    if (select.hasAttribute("size")) {
      select.style.width = "100%";
      select.style.maxWidth = "100%";
      return;
    }
    const longest = Math.max(10, selectedText.length, ...texts.map(text => text.length));
    const desiredCh = Math.max(16, Math.min(96, longest + 5));
    select.style.width = `min(100%, ${desiredCh}ch)`;
    select.style.maxWidth = "100%";
    const field = select.closest(".field");
    if (field && field.parentElement?.classList.contains("conn-strip")) {
      const labelLength = (field.querySelector("label")?.textContent || "").trim().length;
      const fieldCh = Math.max(desiredCh, Math.min(96, labelLength + 4));
      field.style.flexBasis = `min(100%, ${fieldCh}ch)`;
    }
  }
  function fitAllPicklists() {
    document.querySelectorAll("select").forEach(fitPicklist);
  }
  document.querySelectorAll("select").forEach(select => {
    new MutationObserver(() => fitPicklist(select)).observe(
      select, { childList:true, subtree:true });
    select.addEventListener("change", () => fitPicklist(select));
  });
  window.addEventListener("resize", fitAllPicklists);
  fitAllPicklists();

  // ---- Optional project support ----
  donateBtn.onclick = () => {
    const willOpen = donateOptions.hidden;
    donateOptions.hidden = !willOpen;
    donateBtn.setAttribute("aria-expanded", String(willOpen));
  };
  donateUpiBtn.onclick = () => {
    donateOptions.hidden = true;
    donateBtn.setAttribute("aria-expanded", "false");
    if (typeof donateDialog.showModal === "function") donateDialog.showModal();
    else donateDialog.setAttribute("open", "");
  };
  donateCloseBtn.onclick = () => donateDialog.close();
  donateDialog.addEventListener("click", event => {
    if (event.target === donateDialog) donateDialog.close();
  });
  document.addEventListener("click", event => {
    if (!event.target.closest(".donate-wrap")) {
      donateOptions.hidden = true;
      donateBtn.setAttribute("aria-expanded", "false");
    }
  });
  copyUpiBtn.onclick = async () => {
    const upi = copyUpiBtn.dataset.upi || "";
    try {
      await navigator.clipboard.writeText(upi);
    } catch (_) {
      const helper = document.createElement("textarea");
      helper.value = upi;
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    copyUpiBtn.textContent = "UPI ID copied";
    setTimeout(() => { copyUpiBtn.textContent = "Copy UPI ID"; }, 1400);
  };

  // ---- CML editor line-number gutter ----
  function editorEsc(value) {
    return String(value).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function renderEditorHighlight() {
    const source = content.value || "";
    let rendered = "", index = 0;
    while (index < source.length) {
      const quote = source[index];
      if (quote === '"' || quote === "'") {
        let end = index + 1;
        while (end < source.length) {
          if (source[end] === "\\\\") { end += 2; continue; }
          if (source[end] === quote) { end += 1; break; }
          end += 1;
        }
        rendered += editorEsc(source.slice(index, end));
        index = end;
        continue;
      }
      if (source.startsWith("//", index)) {
        let end = source.indexOf("\n", index);
        if (end < 0) end = source.length;
        rendered += `<span class="cml-comment">${editorEsc(source.slice(index, end))}</span>`;
        index = end;
        continue;
      }
      if (source.startsWith("/*", index)) {
        const close = source.indexOf("*/", index + 2);
        const end = close < 0 ? source.length : close + 2;
        rendered += `<span class="cml-comment">${editorEsc(source.slice(index, end))}</span>`;
        index = end;
        continue;
      }
      rendered += editorEsc(source[index]);
      index += 1;
    }
    contentHighlight.innerHTML = rendered + (source.endsWith("\n") ? " " : "\n");
    contentHighlight.scrollTop = content.scrollTop;
    contentHighlight.scrollLeft = content.scrollLeft;
  }
  function updateEditorLineNumbers() {
    const lineCount = Math.max(1, content.value.replace(/\r\n?/g, "\n").split("\n").length);
    contentLineNumbers.textContent = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");
    contentLineNumbers.scrollTop = content.scrollTop;
    renderEditorHighlight();
  }
  function setEditorContent(value) {
    content.value = value == null ? "" : String(value);
    updateEditorLineNumbers();
  }
  function syncEditorGutter() {
    contentLineNumbers.scrollTop = content.scrollTop;
    contentHighlight.scrollTop = content.scrollTop;
    contentHighlight.scrollLeft = content.scrollLeft;
  }
  function syncEditorGutterSize() {
    contentLineNumbers.style.height = content.offsetHeight + "px";
    syncEditorGutter();
  }
  function scrollEditorLineIntoView(line) {
    const styles = getComputedStyle(content);
    const lineHeight = parseFloat(styles.lineHeight) || (parseFloat(styles.fontSize) || 12.5) * 1.5;
    const topPadding = parseFloat(styles.paddingTop) || 0;
    const targetTop = topPadding + (Math.max(1, Number(line) || 1) - 1) * lineHeight;
    content.scrollTop = Math.max(0, targetTop - content.clientHeight / 2 + lineHeight / 2);
    syncEditorGutter();
  }
  content.addEventListener("input", updateEditorLineNumbers);
  content.addEventListener("scroll", syncEditorGutter, { passive: true });
  function replaceEditorRange(start, end, replacement, selectionStart, selectionEnd) {
    content.setRangeText(replacement, start, end, "select");
    content.setSelectionRange(selectionStart, selectionEnd);
    content.dispatchEvent(new Event("input", { bubbles:true }));
    content.focus();
  }
  function toggleLineComment() {
    const value = content.value;
    const selectionStart = content.selectionStart;
    const selectionEnd = content.selectionEnd;
    const lineStart = value.lastIndexOf("\n", Math.max(0, selectionStart - 1)) + 1;
    const effectiveEnd = selectionEnd > selectionStart && value[selectionEnd - 1] === "\n"
      ? selectionEnd - 1 : selectionEnd;
    const nextBreak = value.indexOf("\n", effectiveEnd);
    const lineEnd = nextBreak < 0 ? value.length : nextBreak;
    const original = value.slice(lineStart, lineEnd);
    const lines = original.split("\n");
    const nonBlank = lines.filter(line => line.trim().length);
    const uncomment = nonBlank.length > 0 && nonBlank.every(line => /^\s*\/\//.test(line));
    const changed = lines.map(line => {
      if (uncomment) return line.replace(/^(\s*)\/\/ ?/, "$1");
      const indent = (line.match(/^\s*/) || [""])[0];
      return indent + "// " + line.slice(indent.length);
    }).join("\n");
    replaceEditorRange(lineStart, lineEnd, changed, lineStart, lineStart + changed.length);
  }
  function toggleBlockComment() {
    let start = content.selectionStart, end = content.selectionEnd;
    if (start === end) {
      start = content.value.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
      const nextBreak = content.value.indexOf("\n", end);
      end = nextBreak < 0 ? content.value.length : nextBreak;
    }
    const selected = content.value.slice(start, end);
    const leading = selected.match(/^\s*/)?.[0] || "";
    const trailing = selected.match(/\s*$/)?.[0] || "";
    const core = selected.slice(leading.length, selected.length - trailing.length);
    const isCommented = core.startsWith("/*") && core.endsWith("*/");
    const replacement = isCommented
      ? leading + core.slice(2, -2).replace(/^ /, "").replace(/ $/, "") + trailing
      : leading + "/* " + core + " */" + trailing;
    replaceEditorRange(start, end, replacement, start, start + replacement.length);
  }
  lineCommentBtn.onclick = toggleLineComment;
  blockCommentBtn.onclick = toggleBlockComment;
  content.addEventListener("keydown", event => {
    if ((event.metaKey || event.ctrlKey) && event.key === "/") {
      event.preventDefault();
      toggleLineComment();
    }
  });
  updateEditorLineNumbers();
  syncEditorGutterSize();
  if (typeof ResizeObserver === "function") {
    new ResizeObserver(syncEditorGutterSize).observe(content);
  } else {
    window.addEventListener("resize", syncEditorGutterSize);
  }

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

  async function postJSON(url, payload, options = {}) {
    let res;
    try {
      res = await fetch(url, {
        method: "POST", headers: {
          "Content-Type": "application/json", "X-CML-CSRF": CSRF_TOKEN
        },
        body: JSON.stringify(payload),
        signal: options.signal
      });
    } catch (e) {
      if (e && e.name === "AbortError") throw { aborted: true };
      throw { conn: true };
    }
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
  const actionBtns = [fetchBtn, deployBtn, rollbackBtn, compareBtn, loadDataBtn, compareDataBtn, deployDataBtn, logicAnalyzeBtn];
  function busy(btn, label) {
    btn.innerHTML = '<span class="spinner"></span>' + label;
    actionBtns.forEach(b => b.disabled = true);
  }
  function idle() {
    fetchBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>Fetch CML';
    deployBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V3M7 8l5-5 5 5"/><path d="M5 21h14a2 2 0 0 0 2-2v-4M3 15v4a2 2 0 0 0 2 2"/></svg>Deploy CML';
    rollbackBtn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Restore Backup CML';
    compareBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:5px"><path d="M8 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3M16 3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-3M10 8l-3 4 3 4M14 8l3 4-3 4"/></svg>Compare source ↔ target';
    loadDataBtn.textContent = "View data";
    compareDataBtn.textContent = "Compare data";
    deployDataBtn.textContent = "Deploy selected to target";
    logicAnalyzeBtn.textContent = "Analyze logic";
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
      orgSel.innerHTML = '<option value="">None — select a source org</option>' + opts;
      targetSel.innerHTML = '<option value="">None — select a target org</option>' + opts;
      deployOrgSel.innerHTML = '<option value="">None — select a deployment target</option>' + opts;
      orgSel.value = "";
      targetSel.value = "";
      deployOrgSel.value = "";
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
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
    selectedName.textContent = selectedVersionLabel(selectedSourceVersion());
    combo.hidden = true;
    comboSelected.hidden = false;
  }
  function expandModelView() {
    comboSelected.hidden = true;
    combo.hidden = false;
    try { cmlFilter.focus(); } catch (e) {}
  }
  model.addEventListener("change", () => {
    if (model.value) collapseModelView();
    loadTargetVersions(targetSel, targetVersionSel, "compare");
    loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
  });
  model.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && model.value) { e.preventDefault(); collapseModelView(); }
  });
  changeModelBtn.onclick = expandModelView;

  function renderModels() {
    expandModelView();
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    const f = cmlFilter.value.trim().toLowerCase();
    const list = allModels.filter(m =>
      !f || m.name.toLowerCase().includes(f)
      || (m.label || "").toLowerCase().includes(f)
      || String(m.version || "").includes(f)
      || (m.status || "").toLowerCase().includes(f)
      || (m.versionId || "").toLowerCase().includes(f));
    if (!list.length) {
      model.innerHTML = `<option value="">${allModels.length ? "No CMLs match your filter" : "No CMLs found in this org"}</option>`;
      model.size = 2;
    } else {
      const optionHtml = m => {
        const tag = `  [V${m.version} · ${m.status || "Unknown"}]`;
        return `<option value="${m.versionId}">${m.name}${tag} · ${m.versionId}</option>`;
      };
      const active = list.filter(m =>
        String(m.status || "").trim().toLowerCase() === "active");
      const inactive = list.filter(m =>
        String(m.status || "").trim().toLowerCase() !== "active");
      model.innerHTML = '<option value="">None — select an exact version</option>'
        + (active.length
          ? `<optgroup label="Active CML versions">${active.map(optionHtml).join("")}</optgroup>`
          : "")
        + (inactive.length
          ? `<optgroup label="Inactive / other CML versions">${inactive.map(optionHtml).join("")}</optgroup>`
          : "");
      model.size = Math.min(10, Math.max(3, list.length + 1));
      model.value = "";
    }
    cmlCount.textContent = allModels.length ? `(${list.length} of ${allModels.length})` : "";
    fitPicklist(model);
  }

  async function loadModels() {
    const org = orgSel.value;
    if (!org) {
      expandModelView();
      allModels = [];
      cmlCount.textContent = "";
      cmlFilter.value = "";
      model.innerHTML = '<option value="">Choose a source org first…</option>';
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      return;
    }
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
      targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
      deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
      if (!allModels.length) setStatus("info", "No CMLs (Expression Set versions) were found in " + org + ".");
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      model.innerHTML = '<option value="">(could not load CMLs)</option>';
      setStatus("err", "Could not load CMLs: " + e);
    }
  }

  async function loadTargetVersions(orgControl, versionControl, purpose) {
    versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`;
    const org = orgControl.value;
    const modelName = selectedModelName();
    if (!org || !modelName) return;
    versionControl.innerHTML = '<option value="">Loading exact versions…</option>';
    try {
      const data = await apiGet("/api/models?org=" + encodeURIComponent(org));
      if (data.error) {
        versionControl.innerHTML = '<option value="">(could not load exact versions)</option>';
        setStatus("err", `Could not load ${purpose} versions from ${org}:\n${data.error}`);
        return;
      }
      const versions = (data.models || []).filter(m => m.name === modelName);
      versionControl.innerHTML = `<option value="">None — select exact ${purpose} version</option>`
        + versions.map(m => `<option value="${m.versionId}">${m.name} · V${m.version} · ${m.status || "Unknown"} · ${m.versionId}</option>`).join("");
      versionControl.value = "";
    } catch (e) {
      if (e && e.conn) handleDisconnect();
      else setStatus("err", `Could not load ${purpose} versions: ${e}`);
    }
  }

  orgSel.onchange = () => {
    targetVersionSel.innerHTML = '<option value="">None — select target org and source version</option>';
    deployVersionSel.innerHTML = '<option value="">None — select deployment target and source version</option>';
    loadModels();
  };
  targetSel.onchange = () => loadTargetVersions(targetSel, targetVersionSel, "compare");
  deployOrgSel.onchange = () => loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
  reloadBtn.onclick = loadModels;
  cmlFilter.oninput = renderModels;

  fetchBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose an org first."); return; }
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact CML version."); model.focus(); return; }
    busy(fetchBtn, "Fetching…");
    setStatus("info", "Fetching " + selectedVersionLabel(source) + " from " + orgSel.value + "…");
    try {
      const data = await postJSON("/api/fetch", {
        org: orgSel.value, model: source.name, versionId: source.versionId
      });
      if (data.ok) {
        setEditorContent(data.content);
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version."); model.focus(); return; }
    if (!deployVersionSel.value) { setStatus("err", "Please select an exact deployment target version."); deployVersionSel.focus(); return; }
    if (!content.value.trim()) { setStatus("err", "There is no CML content to deploy."); return; }
    const crossOrg = dest !== orgSel.value;
    let msg = `Deploy "${source.name}" to org "${dest}" exact version "${deployVersionSel.value}"?\n\nThis overwrites only that selected version's Constraint Model.`;
    if (crossOrg) msg += `\n\nNote: you are deploying to "${dest}", which is NOT the source org "${orgSel.value}".`;
    if (!confirm(msg)) return;
    const typed = prompt(`Production safety check:\nType the target org alias exactly to deploy:\n\n${dest}`);
    if (typed !== dest) { setStatus("err", "Deployment cancelled: target org alias did not match."); return; }
    busy(deployBtn, "Deploying…");
    setStatus("info", "Deploying " + source.name + " to " + dest + " version " + deployVersionSel.value + "…");
    try {
      const data = await postJSON("/api/deploy", {
        org: dest, model: source.name,
        targetVersionId: deployVersionSel.value, content: content.value,
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
    const source = selectedSourceVersion();
    const selectedModel = source && source.name;
    const targetVersionId = deployVersionSel.value;
    if (!dest || !selectedModel || !targetVersionId) { setStatus("err", "Choose a target org, model, and exact target version first."); return; }
    try {
      const list = await apiGet(`/api/backups?org=${encodeURIComponent(dest)}&model=${encodeURIComponent(selectedModel)}&versionId=${encodeURIComponent(targetVersionId)}`);
      const backup = list.backups && list.backups[0];
      if (!backup) { setStatus("err", "No saved backup exists for this exact target version."); return; }
      const typed = prompt(`Restore the newest backup from ${backup.createdAt || "unknown time"}?\n\nType the target org alias exactly:\n${dest}`);
      if (typed !== dest) { setStatus("err", "Rollback cancelled: target org alias did not match."); return; }
      busy(rollbackBtn, "Restoring…");
      const data = await postJSON("/api/rollback", {
        org: dest, model: selectedModel, backupId: backup.id,
        targetVersionId,
        confirmTarget: typed
      });
      if (data.ok && typeof data.content === "string") setEditorContent(data.content);
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", cmpStatus); model.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", cmpStatus); targetVersionSel.focus(); return; }
    busy(compareBtn, "Comparing…");
    diffBox.classList.remove("show");
    setStatus("info", `Comparing "${source.name}" ${source.versionId} between ${orgSel.value} (source) and ${targetSel.value} target version ${targetVersionSel.value}…\nThis fetches the CML from both orgs and can take up to a minute — please wait.`, cmpStatus);
    try {
      const d = await postJSON("/api/compare", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value
      });
      if (d.ok) {
        lastCompare = {
          src: d.source,
          tgt: { ...d.target },
          originalTargetContent: d.target.content || "",
          mergeCount: 0,
          semantic: d.semantic || null
        };
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

  // ---- Logic Explorer (server-side tolerant parser, local UI only) ----
  function jumpToEditorLine(line) {
    const requested = Math.max(1, Number(line) || 1);
    const lines = content.value.replace(/\r\n/g, "\n").split("\n");
    const safeLine = Math.min(requested, Math.max(1, lines.length));
    let offset = 0;
    for (let i = 1; i < safeLine; i++) offset += lines[i - 1].length + 1;
    switchView("fetch");
    setTimeout(() => {
      content.focus();
      content.setSelectionRange(offset, Math.min(offset + (lines[safeLine - 1] || "").length, content.value.length));
      scrollEditorLineIntoView(safeLine);
    }, 0);
  }

  function logicEffectText(effect) {
    if (!effect || typeof effect !== "object") return "No effect could be described statically.";
    const action = effect.action || "unknown action";
    const target = effect.target != null ? effect.target : "the declared target";
    if (action === "enforce-condition") return "Validate logical consistency of the declared expression; no runtime result is inferred.";
    if (action === "require") return `Force ${target} to be physically present at the declared quantity when the condition is true; Salesforce may auto-add it, but the runtime result is unknown.`;
    if (action === "exclude") return `Remove the leaf-type target ${target} when the condition is true; exclude is the documented user-selection override exception.`;
    if (action === "set-default") return `Attempt to satisfy ${target} only when the condition changes or the parent is new; otherwise evaluate it passively.`;
    if (action === "emit-message") {
      return `Show ${effect.message != null ? effect.message : "the declared message"}`
        + ` with severity ${effect.severity || "Info"} when the condition is true.`;
    }
    if (action === "preference") return "Ask the solver to satisfy this nonblocking preference; its optional explanation is an Info message, not a target outcome.";
    if (action === "recommend") return `Recommend the declared ${effect.scope || "type or relation"} ${target} without auto-adding it.`;
    if (action === "legacy-recommend") return "Standalone recommend syntax was parsed only for recovery; it is legacy/unverified, not the documented recommendation form.";
    if (action === "hide") return `Hide ${target} in the declared ${effect.scope || "scope"} when the condition is true.`;
    if (action === "disable") return `Keep ${target} visible but unselectable in the declared ${effect.scope || "scope"} when the condition is true.`;
    if (action === "rule-directive") {
      const args = Array.isArray(effect.arguments) ? effect.arguments.join(", ") : (effect.arguments || "the declared action");
      return `Emit the action directive ${args}; the configurator or calling code must interpret it.`;
    }
    return `Declared action: ${action}.`;
  }

  function logicDependencies(item) {
    if (!logicAnalysis) return [];
    return (logicAnalysis.dependencyEdges || []).filter(edge => edge.from === item.id);
  }

  function conditionValue(value) {
    if (value === null || value === undefined || value === "") return "Not specified";
    if (typeof value === "string") return value;
    if (typeof value === "object") {
      try { return JSON.stringify(value); } catch (e) { return String(value); }
    }
    return String(value);
  }

  function conditionJoinExplanation() {
    return "<strong>How groups work:</strong> ALL means every clause must pass. "
      + "ANY means one branch can pass.";
  }

  function meaningfulConditionRoot(node) {
    let current = node;
    while (current && current.logicalJoin === "GROUP"
      && Array.isArray(current.children) && current.children.length === 1) {
      current = current.children[0];
    }
    return current || node;
  }

  function renderConditionNode(node, state) {
    if (!node || typeof node !== "object") return "";
    const children = Array.isArray(node.children) ? node.children : [];
    if (node.nodeType === "logicalGroup" || node.nodeType === "group" || children.length) {
      const join = node.logicalJoin || "GROUP";
      return `<div class="condition-group">`
        + `<div class="condition-group-head"><span class="condition-join">${esc(join)}</span>`
        + `<strong>${esc(node.plainEnglish || "Evaluate this group.")}</strong>`
        + `<span class="condition-group-summary">${esc(node.summary || "")}`
        + `${node.failCondition ? ` Failure: ${esc(node.failCondition)}` : ""}</span></div>`
        + `<div class="condition-children">${children.map(child => renderConditionNode(child, state)).join("")}</div>`
        + `</div>`;
    }
    state.number += 1;
    const line = Math.max(1, Number(node.line) || 1);
    const operatorExpected = `${conditionValue(node.operator)} / ${conditionValue(node.expectedValue)}`;
    return `<article class="condition-clause">`
      + `<div class="condition-clause-head"><span class="condition-clause-title">Clause ${state.number}</span>`
      + `<button type="button" class="condition-line" data-condition-line="${line}">Source line ${line}</button></div>`
      + `<p class="condition-plain">${esc(node.plainEnglish || "This clause must be evaluated.")}</p>`
      + `<dl class="condition-fields">`
      + `<dt>Raw expression</dt><dd class="logic-code">${esc(node.raw || "Unavailable")}</dd>`
      + `<dt>Operator / expected</dt><dd>${esc(operatorExpected)}</dd>`
      + `<dt>Actual value</dt><dd class="condition-runtime">available in Phase 2 runtime validation</dd>`
      + `<dt>Result</dt><dd class="condition-runtime">Runtime value required</dd>`
      + `</dl></article>`;
  }

  function renderConditionEvaluation(item) {
    const root = meaningfulConditionRoot(item.conditionBreakdown);
    if (!root || typeof root !== "object") return "";
    const join = root.logicalJoin || (root.nodeType === "clause" ? "CLAUSE" : "GROUP");
    const state = { number: 0 };
    const children = Array.isArray(root.children) && root.children.length
      ? root.children.map(child => renderConditionNode(child, state)).join("")
      : renderConditionNode(root, state);
    const raw = (item.condition && item.condition.raw) || root.raw || "No raw condition recovered.";
    return `<section class="condition-evaluation" aria-label="Business-readable condition evaluation">`
      + `<div class="condition-evaluation-head">`
      + `<h3 class="condition-evaluation-title">Condition evaluation <span class="condition-join">${esc(join)}</span></h3>`
      + `<p class="condition-summary">${esc(root.summary || root.plainEnglish || "Evaluate the condition clauses below.")}</p>`
      + `<p class="condition-fail"><strong>Fail condition:</strong> ${esc(root.failCondition || "The required condition does not pass.")}</p>`
      + `</div>`
      + `<div class="condition-explanation">${conditionJoinExplanation()}</div>`
      + `<div class="condition-tree">${children}</div>`
      + `<details class="condition-raw-detail"><summary>Supporting technical detail: raw condition</summary>`
      + `<code>${esc(raw)}</code></details></section>`;
  }

  function renderLogicDetail(item) {
    if (!item) {
      logicDetail.innerHTML = '<div class="logic-empty">Choose a logic item to see its plain-English interpretation.</div>';
      return;
    }
    selectedLogicId = item.id;
    const deps = logicDependencies(item);
    const dependencyText = deps.length
      ? deps.map(edge => `${edge.to} (${edge.kind}${edge.resolved ? ", resolved" : ", unresolved"})`).join("\n")
      : "No local dependencies detected.";
    const refs = (item.references || []).map(ref => ref.name).filter(Boolean);
    const runtimeText = item.runtimeNeeded
      ? `Salesforce runtime values and solver behavior are still needed${refs.length ? ` for: ${refs.join(", ")}` : ""}.`
      : "No runtime information is needed for this constant condition; Salesforce compilation is still not verified.";
    const hasBreakdown = item.conditionBreakdown && typeof item.conditionBreakdown === "object";
    const rows = [
      ["Scope", item.scope || "Unknown"],
      ["Line", item.line || 1],
      ["Logic kind", item.kind || "Unknown"],
      ...(!hasBreakdown ? [["Condition", item.condition && item.condition.raw ? item.condition.raw : "No condition recovered."]] : []),
      ["Effect", logicEffectText(item.effect)],
      ["Applies when", item.appliesWhen || "Unknown"],
      ["Does not apply when", item.doesNotApplyWhen || "Unknown"],
      ["Dependencies", dependencyText],
      ["Runtime information still needed", runtimeText],
    ];
    logicDetail.innerHTML = (hasBreakdown ? renderConditionEvaluation(item) : "")
      + '<dl class="logic-detail-grid">' + rows.map(row =>
      `<dt>${esc(row[0])}</dt><dd${row[0] === "Condition" ? ' class="logic-code"' : ""}>${esc(row[1])}</dd>`
    ).join("") + "</dl>";
    logicDetail.querySelectorAll("[data-condition-line]").forEach(link => {
      link.addEventListener("click", () => jumpToEditorLine(Number(link.dataset.conditionLine) || 1));
    });
  }

  function logicSearchText(item) {
    const deps = logicDependencies(item).map(edge => `${edge.to} ${edge.kind}`).join(" ");
    return [
      item.kind, item.scope,
      item.condition && item.condition.raw, logicEffectText(item.effect),
      item.appliesWhen, item.doesNotApplyWhen, deps,
      item.conditionBreakdown ? JSON.stringify(item.conditionBreakdown) : ""
    ].filter(Boolean).join(" ").toLowerCase();
  }

  function renderLogicList() {
    if (!logicAnalysis) return;
    const query = logicSearch.value.trim().toLowerCase();
    const rows = (logicAnalysis.logicItems || []).filter(item =>
      (!logicKindFilter.value || item.kind === logicKindFilter.value)
      && (!query || logicSearchText(item).includes(query))
    );
    logicVisibleCount.textContent = `(${rows.length} shown)`;
    if (!rows.length) {
      logicList.innerHTML = '<div class="logic-empty">No logic items match these filters.</div>';
      renderLogicDetail(null);
      return;
    }
    if (!rows.some(item => item.id === selectedLogicId)) selectedLogicId = rows[0].id;
    logicList.innerHTML = rows.map(item => {
      const condition = item.condition && item.condition.raw ? item.condition.raw : "Condition unavailable";
      return `<button type="button" class="logic-row${item.id === selectedLogicId ? " active" : ""}" data-logic-id="${esc(item.id)}">`
        + `<span class="logic-row-title"><span>${esc(item.kind || "logic")}</span><span>L${esc(item.line || 1)}</span></span>`
        + `<span class="logic-row-meta">${esc(item.scope || "Unknown scope")}</span>`
        + `<span class="logic-row-meta logic-code">${esc(condition)}</span></button>`;
    }).join("");
    const selected = rows.find(item => item.id === selectedLogicId) || rows[0];
    renderLogicDetail(selected);
    logicList.querySelectorAll("[data-logic-id]").forEach(row => {
      row.addEventListener("click", () => {
        const item = (logicAnalysis.logicItems || []).find(candidate => candidate.id === row.dataset.logicId);
        if (!item) return;
        renderLogicDetail(item);
        jumpToEditorLine(item.line);
      });
    });
  }

  function renderLogicAnalysis(data) {
    logicAnalysis = data;
    selectedLogicId = (data.logicItems && data.logicItems[0] && data.logicItems[0].id) || null;
    const kinds = [...new Set((data.logicItems || []).map(item => item.kind).filter(Boolean))].sort();
    logicKindFilter.innerHTML = '<option value="">All kinds</option>'
      + kinds.map(kind => `<option value="${esc(kind)}">${esc(kind)}</option>`).join("");
    logicResults.classList.add("show");
    renderLogicList();
  }

  [logicSearch, logicKindFilter].forEach(control => {
    control.addEventListener(control === logicSearch ? "input" : "change", renderLogicList);
  });
  logicEditorBtn.onclick = () => { switchView("fetch"); content.focus(); };
  logicAnalyzeBtn.onclick = async () => {
    if (!content.value.trim()) {
      logicResults.classList.remove("show");
      setStatus("info", "The editor is empty. Open Fetch & Deploy, then fetch a CML or paste CML content before analyzing.", logicStatus);
      return;
    }
    busy(logicAnalyzeBtn, "Analyzing…");
    setStatus("info", "Analyzing the editor content locally…", logicStatus);
    try {
      const data = await postJSON("/api/logic/analyze", { content: content.value });
      if (data && data.summary && Array.isArray(data.logicItems)) {
        renderLogicAnalysis(data);
        if (data.ok) {
          setStatus("ok", "Local logic explanation complete. This is guidance only, not Salesforce compile/runtime proof.", logicStatus);
        } else {
          setStatus("err", "Some source could not be interpreted; only recovered logic is shown.", logicStatus);
        }
      } else {
        logicResults.classList.remove("show");
        setStatus("err", data.log || "Logic analysis returned no usable result.", logicStatus);
      }
    } catch (e) {
      if (e && e.conn) handleDisconnect();
      else setStatus("err", "Logic analysis error: " + e, logicStatus);
    }
    idle();
  };

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

  // A row rendered into a pane table. `marker` is a glyph cue (+ - ~) so the
  // diff is readable without relying on color (colorblind-friendly).
  function semanticLineMaps() {
    const source = new Map(), target = new Map();
    if (!semanticChk.checked || !lastCompare || !lastCompare.semantic) return { source, target };
    const priority = { AMBIGUOUS:5, MODIFIED:4, MOVED:3, REMOVED:2, ADDED:2 };
    const add = (map, range, entity) => {
      if (!range || entity.status === "UNCHANGED") return;
      for (let line = range.startLine; line <= range.endLine; line++) {
        const mark = map.get(line) || { statuses:[], badges:[] };
        if (!mark.statuses.includes(entity.status)) mark.statuses.push(entity.status);
        if (line === range.startLine) mark.badges.push(entity);
        mark.statuses.sort((a, b) => (priority[b] || 0) - (priority[a] || 0));
        map.set(line, mark);
      }
    };
    (lastCompare.semantic.entities || []).forEach(entity => {
      add(source, entity.sourceRange, entity);
      add(target, entity.targetRange, entity);
    });
    return { source, target };
  }

  function semanticTooltip(entity) {
    const changes = (entity.propertyChanges || []).map(change => change.property);
    return `${entity.identity || entity.name || entity.kind}: ${entity.status}`
      + (changes.length ? ` · changed ${changes.join(", ")}` : "")
      + (entity.reason ? ` · ${entity.reason}` : "");
  }

  function semanticDecoration(mark) {
    if (!mark) return { className:"", badges:"" };
    const status = (mark.statuses[0] || "").toLowerCase();
    const badges = mark.badges.map(entity =>
      `<span class="semantic-badge ${entity.status.toLowerCase()}" title="${esc(semanticTooltip(entity)).replace(/"/g, "&quot;")}">${esc(entity.status)}</span>`
    ).join("");
    return { className: status ? ` sem-${status}` : "", badges };
  }

  function paneRow(rowType, num, codeHtml, marker, semanticMark) {
    const baseClass = rowType === "eq" ? "eqrow"
      : rowType === "chg" ? "row-chg"
      : rowType === "del" ? "row-del"
      : rowType === "ins" ? "row-ins" : "row-filler";
    if (rowType === "filler") {
      return `<tr class="row-filler"><td class="gutter">&nbsp;</td><td class="code">&nbsp;</td></tr>`;
    }
    const semantic = semanticDecoration(semanticMark);
    const mk = `<span class="mk">${marker}</span>`;
    return `<tr class="${baseClass}${semantic.className}"><td class="gutter">${num}</td><td class="code">${mk}${semantic.badges}${codeHtml}</td></tr>`;
  }

  function mergeRailRow(row) {
    if (row.type === "eq") return '<tr class="eqrow"><td>&nbsp;</td></tr>';
    const button = row.mergeLead
      ? `<button type="button" class="merge-arrow" data-merge-hunk="${row.mergeId}" title="Apply this source change to the target draft" aria-label="Apply source change to target draft">→</button>`
      : "&nbsp;";
    return `<tr><td>${button}</td></tr>`;
  }

  function updateMergeWorkflow() {
    const count = lastCompare ? lastCompare.mergeCount || 0 : 0;
    mergeWorkflow.hidden = count === 0;
    if (!count) return;
    mergeWorkflowCopy.textContent = `${count} source change${count === 1 ? "" : "s"} applied to the target working draft. Salesforce has not been changed yet.`;
  }

  function renderDiff(src, tgt) {
    const a = (src.content || "").replace(/\r\n/g, "\n").split("\n");
    const b = (tgt.content || "").replace(/\r\n/g, "\n").split("\n");
    const ops = diffOps(a, b);
    const semanticMaps = semanticLineMaps();
    activeMergeHunks = [];

    // Pair runs of del/ins into aligned "changed" rows.
    const rows = []; let pendDel = [], pendIns = [];
    const flush = (nextTargetLine) => {
      if (!pendDel.length && !pendIns.length) return;
      const mergeId = activeMergeHunks.length;
      activeMergeHunks.push({
        targetStart: pendIns.length ? pendIns[0] : nextTargetLine,
        targetDeleteCount: pendIns.length,
        sourceLines: pendDel.map(index => a[index])
      });
      const k = Math.max(pendDel.length, pendIns.length);
      for (let x = 0; x < k; x++) {
        const d = pendDel[x], ins = pendIns[x];
        const merge = { mergeId, mergeLead: x === 0 };
        if (d != null && ins != null) rows.push({ type: "chg", a: d, b: ins, ...merge });
        else if (d != null) rows.push({ type: "del", a: d, ...merge });
        else rows.push({ type: "ins", b: ins, ...merge });
      }
      pendDel = []; pendIns = [];
    };
    for (const op of ops) {
      if (op.t === "eq") { flush(op.b); rows.push({ type: "eq", a: op.a, b: op.b }); }
      else if (op.t === "del") pendDel.push(op.a);
      else pendIns.push(op.b);
    }
    flush(b.length);

    let chg = 0, del = 0, ins = 0, left = "", middle = "", right = "";
    for (const r of rows) {
      middle += mergeRailRow(r);
      if (r.type === "eq") {
        left += paneRow("eq", r.a + 1, esc(a[r.a]), " ", semanticMaps.source.get(r.a + 1));
        right += paneRow("eq", r.b + 1, esc(b[r.b]), " ", semanticMaps.target.get(r.b + 1));
      } else if (r.type === "chg") {
        chg++;
        left += paneRow("chg", r.a + 1, esc(a[r.a]), "~", semanticMaps.source.get(r.a + 1));
        right += paneRow("chg", r.b + 1, esc(b[r.b]), "~", semanticMaps.target.get(r.b + 1));
      } else if (r.type === "del") {
        del++;
        left += paneRow("del", r.a + 1, esc(a[r.a]), "−", semanticMaps.source.get(r.a + 1));
        right += paneRow("filler");
      } else {
        ins++;
        left += paneRow("filler");
        right += paneRow("ins", r.b + 1, esc(b[r.b]), "+", semanticMaps.target.get(r.b + 1));
      }
    }
    srcTable.innerHTML = "<tbody>" + left + "</tbody>";
    mergeTable.innerHTML = "<tbody>" + middle + "</tbody>";
    tgtTable.innerHTML = "<tbody>" + right + "</tbody>";
    srcTitle.textContent = "Source — " + src.org;
    tgtTitle.textContent = (lastCompare && lastCompare.mergeCount ? "Target draft — " : "Target — ") + tgt.org;
    diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
    updateMergeWorkflow();

    if (chg + del + ins === 0) {
      diffSummary.textContent = `Identical — "${selectedModelName()}" matches exactly (${a.length} lines).`;
    } else {
      diffSummary.textContent = `${chg} changed · ${del} only in source · ${ins} only in target   (source ${a.length} lines, target ${b.length} lines)`;
    }
    diffBox.classList.add("show");
    diffBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // Keep the two panes vertically aligned while allowing independent
  // horizontal scrolling of long lines.
  let syncing = false;
  function syncScroll(from) {
    from.addEventListener("scroll", () => {
      if (syncing) return;
      syncing = true;
      [srcScroll, mergeScroll, tgtScroll].forEach(pane => {
        if (pane !== from) pane.scrollTop = from.scrollTop;
      });
      requestAnimationFrame(() => { syncing = false; });
    });
  }
  syncScroll(srcScroll);
  syncScroll(mergeScroll);
  syncScroll(tgtScroll);

  onlyDiffs.onchange = () => diffPanes.classList.toggle("hide-eq", onlyDiffs.checked);
  mergeTable.onclick = async event => {
    const button = event.target.closest("[data-merge-hunk]");
    if (!button || !lastCompare) return;
    const hunk = activeMergeHunks[Number(button.dataset.mergeHunk)];
    if (!hunk) return;
    const targetLines = (lastCompare.tgt.content || "").replace(/\r\n/g, "\n").split("\n");
    targetLines.splice(hunk.targetStart, hunk.targetDeleteCount, ...hunk.sourceLines);
    lastCompare.tgt.content = targetLines.join("\n");
    lastCompare.mergeCount = (lastCompare.mergeCount || 0) + 1;
    lastCompare.semantic = null;
    renderCompare();
    try {
      lastCompare.semantic = await postJSON("/api/semantic/compare", {
        sourceContent: lastCompare.src.content || "",
        targetContent: lastCompare.tgt.content || ""
      });
      renderCompare();
    } catch (e) {
      if (e && e.conn) handleDisconnect();
    }
  };
  resetMergeBtn.onclick = () => {
    if (!lastCompare) return;
    lastCompare.tgt.content = lastCompare.originalTargetContent;
    lastCompare.mergeCount = 0;
    lastCompare.semantic = null;
    renderCompare();
    postJSON("/api/semantic/compare", {
      sourceContent: lastCompare.src.content || "",
      targetContent: lastCompare.tgt.content || ""
    }).then(data => {
      if (!lastCompare) return;
      lastCompare.semantic = data;
      renderCompare();
    }).catch(e => { if (e && e.conn) handleDisconnect(); });
    setStatus("info", "Target draft reset to the version fetched from Salesforce. No org data was changed.", cmpStatus);
  };
  reviewMergeBtn.onclick = async () => {
    if (!lastCompare || !lastCompare.mergeCount) return;
    setEditorContent(lastCompare.tgt.content);
    deployOrgSel.value = targetSel.value;
    await loadTargetVersions(deployOrgSel, deployVersionSel, "deployment");
    deployVersionSel.value = targetVersionSel.value;
    fitPicklist(deployOrgSel);
    fitPicklist(deployVersionSel);
    switchView("fetch");
    setStatus("info", `Merged target draft loaded for review.\nDeployment target: ${targetSel.value} · exact version ${targetVersionSel.value}.\nReview the CML, then use Deploy CML. The normal backup, confirmation, and verification safeguards still apply.`);
  };
  copyTargetCmlBtn.onclick = async () => {
    if (!lastCompare) return;
    const value = lastCompare.tgt.content || "";
    try {
      await navigator.clipboard.writeText(value);
    } catch (e) {
      const helper = document.createElement("textarea");
      helper.value = value;
      helper.style.position = "fixed";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.select();
      document.execCommand("copy");
      helper.remove();
    }
    const label = copyTargetCmlBtn.querySelector("span");
    if (label) label.textContent = "Copied";
    setTimeout(() => { if (label) label.textContent = "Copy"; }, 1300);
  };

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

  function renderSemanticSummary() {
    const semantic = lastCompare && lastCompare.semantic;
    semanticInlineSummary.hidden = !semanticChk.checked;
    if (!semanticChk.checked) return;
    if (!semantic) {
      semanticInlineSummary.textContent = "Semantic: refreshing the target draft analysis…";
      return;
    }
    if (semantic.analysisError) {
      semanticInlineSummary.innerHTML = `<strong>Semantic:</strong> unavailable — ${esc(semantic.analysisError)}`;
      return;
    }
    const s = semantic.stats || {};
    const parseIssues = (semantic.sourceParseIssues || []).length
      + (semantic.targetParseIssues || []).length;
    semanticInlineSummary.innerHTML = "<strong>Semantic:</strong> "
      + `${s.ADDED || 0} added · ${s.REMOVED || 0} removed · ${s.MODIFIED || 0} modified · `
      + `${s.MOVED || 0} moved · ${s.UNCHANGED || 0} unchanged`
      + (s.AMBIGUOUS ? ` · ${s.AMBIGUOUS} ambiguous` : "")
      + (parseIssues ? ` · ${parseIssues} parser warning${parseIssues === 1 ? "" : "s"}` : "");
  }

  // Semantic analysis is an overlay: it never replaces or hides the code panes.
  function renderCompare() {
    if (!lastCompare) return;
    renderDiff(lastCompare.src, lastCompare.tgt);
    renderSemanticSummary();
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
        scrollEditorLineIntoView(ln);
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
    if (s === "ambiguous-key") return '<span class="badge b-blocked">Blocked — ambiguous key</span>';
    if (s === "dependency-unverified") return '<span class="badge b-unmappable">Needs review — dependency key missing</span>';
    if (s === "exact-duplicate") return '<span class="badge b-dup">Skipped — exact duplicate</span>';
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
    if (s === "ambiguous-key") return "Blocked — portable key matches multiple target records";
    if (s === "dependency-unverified") return "Needs review — dependency could not be compared";
    if (s === "exact-duplicate") return "Skipped — exact duplicate";
    if (s === "unmappable") return "No " + currentKeyField;
    if (s === "stale")      return "Unused association — absent from the same org's CML";
    return s || "";
  }

  const DUP_LABEL = { exact: "Exact duplicate", tag: "Duplicate tag", ref: "Duplicate reference", name: "Ambiguous name" };
  const DUP_HELP = {
    exact: "Same complete association identity repeats within this selected parent Expression Set.",
    tag: "Same tag type and tag repeats within this selected parent Expression Set; references may still differ.",
    ref: "Same reference identity is used more than once within this selected parent Expression Set.",
    name: "Same display name maps to different portable keys within this selected parent Expression Set."
  };
  function dupBadges(r) {
    if (!r.dups || !r.dups.length) return "";
    return r.dups.map(d => `<span class="badge b-dup" title="${esc(DUP_HELP[d] || DUP_LABEL[d] || d)}">${esc(DUP_LABEL[d] || d)}</span>`).join("");
  }

  // Which rows can be acted on in a compare deploy.
  function isAdd(r) { return r._status === "add"; }     // ready to insert in target
  function isDel(r) { return r._status === "extra"; }   // exists only in target

  function referenceLabel(name, code, fallback) {
    const base = name || fallback || "(unnamed record)";
    return base + (code ? ` (${code})` : "");
  }

  function referenceRecordText(r) {
    const source = referenceLabel(r.sourceRefName, r.sourceRefCode, r.refId);
    const target = referenceLabel(r.targetRefName, r.targetRefCode, r.matchedEvidence?.target?.referenceId);
    if (r._status === "match" && (r.sourceRefName || r.targetRefName)) {
      if (source === target) return source;
      return `${r._sourceOrg || "Source"}: ${source} | ${r._targetOrg || "Target"}: ${target}`;
    }
    return referenceLabel(r.refName, r.refCode, r.refId);
  }

  function referenceRecordHtml(r) {
    const source = referenceLabel(r.sourceRefName, r.sourceRefCode, r.refId);
    const target = referenceLabel(r.targetRefName, r.targetRefCode, r.matchedEvidence?.target?.referenceId);
    if (r._status === "match" && (r.sourceRefName || r.targetRefName) && source !== target) {
      return `<span><strong>${esc(r._sourceOrg || "Source")}:</strong> ${esc(source)}</span>`
        + `<span class="block-note"><strong>${esc(r._targetOrg || "Target")}:</strong> ${esc(target)}</span>`;
    }
    return esc(referenceRecordText(r));
  }

  function dataRowHtml(r, withStatus) {
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
      + `<td class="col-ref">${referenceRecordHtml(r)}${dupBadges(r)}</td>`
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
      if (f === "ambiguous-key") return r._status === "ambiguous-key";
      if (f === "blocked") return r._status === "blocked" || r._status === "ambiguous-key" || r._status === "unmappable" || r._status === "dependency-unverified";
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
        referenceRecordText(r),
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); model.focus(); return; }
    busy(loadDataBtn, "Loading…");
    setStatus("info", `Loading ExpressionSet-scoped constraint data for "${source.name}" ${source.versionId} from ${orgSel.value}…`, dSt());
    try {
      const data = await postJSON("/api/data", {
        org: orgSel.value, model: source.name,
        versionId: source.versionId, keyField: keyName()
      });
      if (data.ok) {
        dataMode = "single";
        currentKeyField = data.keyField || keyName();
        dataRows = data.rows.map((r, i) => ({ ...r, _status: "", _i: i, _selected: false }));
        deployBar.classList.add("show");
        results.classList.remove("show");
        renderDataChips({
          single: true, total: data.stats.total,
          unmappable: data.stats.unmappable, dups: data.stats.duplicates,
          duplicateScope: data.duplicateScope,
          duplicateCheckError: data.duplicateCheckError,
          apiName: data.expressionSetApiName,
          definitionName: data.expressionSetDefinitionDeveloperName,
          org: orgSel.value
        });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const warn = data.stats.unmappable ? ` (${data.stats.unmappable} without ${currentKeyField})` : "";
        const duplicateNote = data.duplicateCheckError
          ? `\nDuplicate check was unavailable because the selected CML could not be read: ${data.duplicateCheckError}`
          : "\nDuplicate flags were checked only against tags used by the exact selected CML.";
        setStatus("ok", `Loaded ${data.stats.total} constraint rows from ${orgSel.value}${warn}.`
          + `\nScope verified: ExpressionSet.ApiName ${data.expressionSetApiName}`
          + ` · Definition ${data.expressionSetDefinitionDeveloperName}.`
          + `\n${data.associationScopeNote}${duplicateNote}`, dSt());
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
    const source = selectedSourceVersion();
    if (!source) { setStatus("err", "Please select an exact source CML version.", dSt()); model.focus(); return; }
    if (!targetVersionSel.value) { setStatus("err", "Please select an exact compare target version.", dSt()); targetVersionSel.focus(); return; }
    dataCompareController = new AbortController();
    busy(compareDataBtn, "Comparing…");
    stopCompareDataBtn.hidden = false;
    stopCompareDataBtn.disabled = false;
    setStatus("info", `Comparing ExpressionSet-scoped constraint data for "${source.name}" between exact versions ${source.versionId} and ${targetVersionSel.value}…\nThis reads both orgs and can take up to a minute — please wait.`, dSt());
    try {
      const data = await postJSON("/api/data/compare", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value, keyField: keyName()
      }, { signal: dataCompareController.signal });
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
        rows.forEach((r, i) => {
          r._i = i;
          r._selected = (r._status === "add");
          r._sourceOrg = data.source.org;
          r._targetOrg = data.target.org;
        });
        dataRows = rows;
        results.classList.remove("show");
        renderDataChips({ single: false, s: data.stats, src: data.source, tgt: data.target });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setStatus("ok", `Compared constraint data for "${data.model}".\n`
          + `${data.stats.matched} matched · ${data.stats.sourceOnly} only in source · ${data.stats.targetOnly} only in target`
          + (data.stats.cmlDifferences ? ` · ${data.stats.cmlDifferences} explained by different CML definitions` : "")
          + (data.stats.ambiguousKeys ? ` · ${data.stats.ambiguousKeys} ambiguous portable key(s)` : "")
          + (data.stats.dependencyIssues ? ` · ${data.stats.dependencyIssues} catalog dependency finding(s)` : "")
          + (data.stats.dependencyUnverified ? ` · ${data.stats.dependencyUnverified} dependency check(s) need a key` : "")
          + (data.stats.stale ? ` · ${data.stats.stale} stale (excluded)` : "")
          + `.\n${data.associationScopeNote}`
          + (data.associationsShared ? "\nBoth selected versions map to the same ExpressionSet, so these associations are shared." : ""), dSt());
      } else {
        setStatus("err", data.log || "Compare failed.", dSt());
      }
    } catch (e) {
      if (e && e.aborted) {
        setStatus("info", "Constraint data comparison stopped. No comparison results were changed.", dSt());
      } else if (e && e.conn) {
        handleDisconnect();
      } else {
        setStatus("err", "Data compare error: " + e, dSt());
      }
    }
    dataCompareController = null;
    stopCompareDataBtn.hidden = true;
    idle();
  };
  stopCompareDataBtn.onclick = () => {
    if (!dataCompareController) return;
    stopCompareDataBtn.disabled = true;
    dataCompareController.abort();
  };

  function dupSum(d) { return d ? (d.exact + d.tag + d.ref + d.name) : 0; }

  function renderDataChips(o) {
    if (o.single) {
      const dn = dupSum(o.dups);
      const scope = o.duplicateScope?.expressionSetId || "selected parent";
      dataChips.innerHTML =
        `<span class="chip ok">${o.total} rows · ${o.org}</span>`
        + `<span class="chip" title="ExpressionSet.ApiName and definition DeveloperName">${esc(o.apiName || "")}</span>`
        + (o.unmappable ? `<span class="chip warn">${o.unmappable} without ${currentKeyField}</span>` : "")
        + (o.duplicateCheckError ? `<span class="chip warn">Duplicate check unavailable</span>` : "")
        + (dn ? `<span class="chip warn" title="Checked only within Expression Set ${esc(scope)}">${dn} duplicate flags · selected model only</span>` : "");
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
      + (s.ambiguousKeys ? `<span class="chip warn">${s.ambiguousKeys} ambiguous portable keys</span>` : "")
      + (s.dependencyIssues ? `<span class="chip warn">${s.dependencyIssues} catalog dependency findings</span>` : "")
      + (s.dependencyUnverified ? `<span class="chip warn">${s.dependencyUnverified} dependency checks need review</span>` : "")
      + (s.exactDuplicates ? `<span class="chip warn">${s.exactDuplicates} exact duplicate rows</span>` : "")
      + (s.stale ? `<span class="chip warn">${s.stale} stale (excluded from deploy)</span>` : "")
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked by catalog dependencies</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "")
      + ((o.src.duplicateCheckError || o.tgt.duplicateCheckError)
        ? `<span class="chip warn">Duplicate check unavailable for one selected CML</span>` : "")
      + ((sd + td) ? `<span class="chip warn" title="Each org is checked independently inside the exact selected version's resolved parent Expression Set">${sd + td} duplicate flags (selected source ${sd} / selected target ${td})</span>` : "");
  }

  // ---- Deploy selected constraint data to the target ----
  function renderResults(data) {
    const s = data.stats;
    let html = `<h4>Deployment results — target ${esc(data.target)}</h4>`;
    if (data.outcome === "partial") {
      const partialText = data.recoveryRequired
        ? (data.log || "RECOVERY REQUIRED — associations changed but runtime validation is not established.")
        : "Partial deployment: Salesforce applied some rows and rejected others because allOrNone=false. Review every failed row before retrying.";
      html += `<div class="status show err" style="margin-bottom:10px;"><strong>${esc(partialText)}</strong></div>`;
    }
    html += `<div class="chips" style="margin-bottom:10px;">`
      + `<span class="chip ok">${s.insertOk} added</span>`
      + (s.insertSkipped ? `<span class="chip warn">${s.insertSkipped} duplicate add skipped</span>` : "")
      + (s.insertFail ? `<span class="chip warn">${s.insertFail} add failed</span>` : "")
      + `<span class="chip extra">${s.deleteOk} deleted</span>`
      + (s.deleteFail ? `<span class="chip warn">${s.deleteFail} delete failed</span>` : "")
      + `</div>`;
    const line = (r, verb) => `<div class="result-row ${r.success ? "good" : "bad"}">`
      + `<span class="ico">${r.success ? "✓" : (r.skipped ? "○" : "✗")}</span>`
      + `<span>${r.skipped ? "Skip" : verb} ${esc(r.label)}${r.success ? "" : " — " + esc(r.error || "failed")}</span></div>`;
    if (data.created.length) html += `<h4>Inserts</h4>` + data.created.map(r => line(r, "Add")).join("");
    if (data.deleted.length) html += `<h4>Deletes</h4>` + data.deleted.map(r => line(r, "Delete")).join("");
    if (data.refresh) {
      html += `<h4>CML save/verification refresh</h4>`
        + `<div class="result-row ${data.refresh.ok ? "good" : "bad"}">`
        + `<span class="ico">${data.refresh.ok ? "✓" : "✗"}</span>`
        + `<span>${esc(data.refresh.ok
          ? "Target CML completed the tool-specific unchanged save/verification. This does not prove runtime behavior."
          : data.refresh.log || "Target CML save/verification refresh failed.")}</span></div>`;
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
    if (data.auditError) {
      html += `<div class="result-row bad"><span>!</span><span>${esc(data.auditError)}</span></div>`;
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
          targetOrg: dest, model: data.model,
          targetVersionId: data.targetVersionId,
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
    const source = selectedSourceVersion();
    if (!source || !targetVersionSel.value) {
      setStatus("err", "Select exact source and target versions before deployment.", dSt());
      return;
    }
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
        sourceOrg: orgSel.value, targetOrg: targetSel.value,
        model: source.name, sourceVersionId: source.versionId,
        targetVersionId: targetVersionSel.value,
        adds, deletes, keyField: keyName(), confirmTarget: typed
      });
      if (data.stats) {
        renderResults(data);
        const s = data.stats;
        const refreshFailed = data.refresh && !data.refresh.ok;
        const nonSuccess = s.insertFail + s.deleteFail + (s.insertSkipped || 0);
        const severity = (data.outcome === "failed" || data.outcome === "partial"
          || refreshFailed) ? "err" : (nonSuccess ? "info" : "ok");
        setStatus(severity,
          `Done. Added ${s.insertOk}/${adds.length}, deleted ${s.deleteOk}/${deletes.length}.`
          + (s.insertFail + s.deleteFail ? ` ${s.insertFail + s.deleteFail} failed — see details below.` : "")
          + (s.insertSkipped ? ` ${s.insertSkipped} exact duplicate add skipped.` : "")
          + (refreshFailed ? ` RECOVERY REQUIRED — associations changed, but the tool-specific CML save/verification refresh failed; runtime validation is not established.` : "")
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
        print(f"Stop it, or set a different port: CML_UI_PORT=8900 python3 app/cml_tool.py")
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
