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
import hashlib
import json
import os
import re
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
    return _download_cml(org, model, os.path.join(DOWNLOAD_DIR, f"{model}.cml"))


def _safe(name):
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in (name or ""))


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
_FIELD_PROBE = {}  # cache: (org, sobject, field) -> bool (field exists & queryable)


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
    if ck in _FIELD_PROBE:
        return _FIELD_PROBE[ck]
    _, err = _query_json(org, f"SELECT {field} FROM {sobject} LIMIT 1")
    ok = not (err and ("INVALID_FIELD" in err or "No such column" in err
                       or "INVALID_TYPE" in err or "INVALID_FIELD_FOR_INSERT" in err))
    _FIELD_PROBE[ck] = ok
    return ok


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
    unmapped = 0
    for rec in records:
        ro = rec.get("ReferenceObject") or {}
        ref_type = (ro.get("attributes") or {}).get("type") or ""
        gkey = ro.get(kf)
        tag = rec.get("ConstraintModelTag")
        tag_type = rec.get("ConstraintModelTagType")
        mappable = bool(gkey)
        if not mappable:
            unmapped += 1
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
            "mappable": mappable,
            "key": _constraint_key(tag_type, tag, ref_type, gkey),
        })

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

    src_by = {r["key"]: r for r in src["rows"]}
    tgt_by = {r["key"]: r for r in tgt["rows"]}

    # Reference records needed in target for the rows that are only in source.
    needed = {}
    for key, r in src_by.items():
        if key not in tgt_by and r["mappable"]:
            needed.setdefault(r["refType"], set()).add(r["gkey"])
    present = _target_present_keys(target_org, needed, kf)

    matched, source_only, target_only = [], [], []
    for key, r in src_by.items():
        if key in tgt_by:
            matched.append(r)
        else:
            row = dict(r)
            if not r["mappable"]:
                row["deployStatus"] = "unmappable"
            elif (r["refType"], r["gkey"]) in present:
                row["deployStatus"] = "ready"
            else:
                row["deployStatus"] = "blocked"
            source_only.append(row)
    for key, r in tgt_by.items():
        if key not in src_by:
            target_only.append(r)

    return {
        "ok": True, "model": model, "keyField": kf,
        "source": {"org": source_org, "total": len(src["rows"]),
                   "duplicates": src["stats"]["duplicates"]},
        "target": {"org": target_org, "total": len(tgt["rows"]),
                   "duplicates": tgt["stats"]["duplicates"]},
        "matched": matched,
        "sourceOnly": source_only,
        "targetOnly": target_only,
        "stats": {
            "matched": len(matched),
            "sourceOnly": len(source_only),
            "targetOnly": len(target_only),
            "ready": sum(1 for r in source_only if r.get("deployStatus") == "ready"),
            "blocked": sum(1 for r in source_only if r.get("deployStatus") == "blocked"),
            "unmappable": sum(1 for r in source_only if r.get("deployStatus") == "unmappable"),
        },
    }


_CREDS_CACHE = {}  # org -> (token, instanceUrl) for the life of this process


def _org_creds(org, refresh=False):
    """Return (accessToken, instanceUrl, error). Cached per org; pass
    refresh=True to force a new `sf org display` (e.g. after a 401)."""
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
    if not token or not url:
        return None, None, ("No access token for this org. Re-authenticate with: "
                            f"sf org login web --alias {org}")
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
    """Insert records via sObject Collections (allOrNone=false). Returns list
    aligned with input: [{success, id, error}]."""
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
    """Delete records via sObject Collections (allOrNone=false). Returns list
    aligned with input ids: [{success, id, error}]."""
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
        from collections import Counter
        common = Counter(r["ExpressionSetId"] for r in recs).most_common(1)
        if common:
            return common[0][0], None
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


def deploy_constraints(source_org, target_org, model, adds, deletes,
                       key_field=DEFAULT_KEY_FIELD):
    """Insert selected source-only constraints and delete selected target-only
    ones. Each item is handled individually so per-row results can be shown.

    adds:    [{tag, tagType, refType, gkey, refName}]  (from the source org)
    deletes: [{id, refName, tag, tagType}]             (target record Ids)
    """
    if not target_org:
        return {"ok": False, "log": "No target org."}
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

    # ---- Inserts ----
    if adds:
        es_id, es_err = _resolve_target_expression_set(target_org, model)
        if es_err:
            return {"ok": False, "log": f"Cannot insert constraints: {es_err}"}

        # Resolve each reference record's target Id by type + chosen key field.
        needed = {}
        for a in adds:
            if a.get("gkey"):
                needed.setdefault(a["refType"], set()).add(a["gkey"])
        ref_map = {}  # (type, key) -> target Id
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
                    continue
                for r in recs:
                    ref_map[(ref_type, r.get(kf))] = r["Id"]

        records, meta = [], []
        for a in adds:
            label = f'{a.get("tagType")} · {a.get("tag")} → {a.get("refName") or a.get("gkey")}'
            ref_id = ref_map.get((a.get("refType"), a.get("gkey")))
            if not a.get("gkey"):
                created.append({"success": False, "label": label,
                                "error": f"Reference record has no {kf} — cannot map."})
                continue
            if not ref_id:
                created.append({"success": False, "label": label,
                                "error": f"Reference {a.get('refType')} with {kf} "
                                         f"'{a.get('gkey')}' not found in target."})
                continue
            records.append({
                "attributes": {"type": "ExpressionSetConstraintObj"},
                "ExpressionSetId": es_id,
                "ReferenceObjectId": ref_id,
                "ConstraintModelTag": a.get("tag"),
                "ConstraintModelTagType": a.get("tagType"),
            })
            meta.append(label)

        if records:
            res = _collections_insert(token, instance, records)
            for label, r in zip(meta, res):
                created.append({"success": r["success"], "label": label,
                                "id": r.get("id"), "error": r.get("error")})

    # ---- Deletes ----
    if deletes:
        ids, labels = [], {}
        for d in deletes:
            rid = d.get("id")
            if not rid or not str(rid).startswith("1JE"):  # ESCO key prefix guard
                delete_results.append({"success": False,
                                       "label": d.get("refName") or rid,
                                       "error": "Not a valid ExpressionSetConstraintObj Id; skipped."})
                continue
            ids.append(rid)
            labels[rid] = f'{d.get("tagType")} · {d.get("tag")} → {d.get("refName") or rid}'
        if ids:
            res = _collections_delete(token, instance, ids)
            for r in res:
                delete_results.append({"success": r["success"],
                                       "label": labels.get(r.get("id"), r.get("id")),
                                       "id": r.get("id"), "error": r.get("error")})

    ins_ok = sum(1 for r in created if r["success"])
    del_ok = sum(1 for r in delete_results if r["success"])
    return {
        "ok": True, "model": model, "target": target_org,
        "created": created, "deleted": delete_results,
        "stats": {
            "insertOk": ins_ok, "insertFail": len(created) - ins_ok,
            "deleteOk": del_ok, "deleteFail": len(delete_results) - del_ok,
        },
    }


def deploy_cml(org, model, content):
    """Deploy CML by PATCHing the ConstraintModel of the model's latest version
    over REST (cross-platform; no helper script or shell needed)."""
    if not org or not model:
        return {"ok": False, "log": "Please choose an org and enter the CML API name."}
    if not content or not content.strip():
        return {"ok": False, "log": "There is no CML content to deploy."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    rec, err = _latest_version(org, model)
    if err:
        return {"ok": False, "log": err}
    version_id = rec["Id"]
    token, instance, cerr = _org_creds(org)
    if cerr:
        return {"ok": False, "log": cerr}

    b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
    url = (f"{instance}/services/data/{API_VERSION}/sobjects/"
           f"ExpressionSetDefinitionVersion/{version_id}")
    _, perr = _rest("PATCH", url, token, {"ConstraintModel": b64})
    if perr:
        if _is_auth_error(perr):
            token, instance, cerr = _org_creds(org, refresh=True)
            if cerr:
                return {"ok": False, "log": cerr}
            _, perr = _rest("PATCH", url, token, {"ConstraintModel": b64})
            if perr and _is_auth_error(perr):
                return {"ok": False, "log": _auth_help(org, perr)}
        if perr:
            return {"ok": False, "log": (
                f"Deploy failed for '{model}' ({version_id}, status "
                f"{rec.get('Status')}) in '{org}':\n{perr}")}
    lines = content.count("\n") + 1
    return {"ok": True, "log": (
        f"SUCCESS — deployed CML to '{model}' ({version_id}) in '{org}'.\n"
        f"Version status: {rec.get('Status')} · {lines} lines.")}


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
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            if self.path == "/" or self.path.startswith("/?"):
                self._send(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/api/ping":
                self._send(200, {"app": APP_ID, "build": BUILD})
            elif self.path == "/api/quit":
                # Lets a newly-launched (updated) instance ask this one to exit so
                # the new build can take over the port. Shut down from a separate
                # thread so this response finishes first.
                self._send(200, {"ok": True, "bye": True})
                threading.Thread(target=lambda: (time.sleep(0.3), self.server.shutdown()), daemon=True).start()
            elif self.path == "/api/orgs":
                self._send(200, list_orgs())
            elif self.path == "/api/debug":
                self._send(200, sf_debug_info())
            elif self.path.startswith("/api/models"):
                qs = urllib.parse.urlparse(self.path).query
                org = urllib.parse.parse_qs(qs).get("org", [""])[0]
                self._send(200, list_models(org))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(200, {"ok": False, "log": f"Unexpected server error: {exc}"})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(200, {"ok": False, "log": "Invalid request body."})
                return

            if self.path == "/api/fetch":
                self._send(200, fetch_cml(body.get("org"), body.get("model")))
            elif self.path == "/api/deploy":
                self._send(200, deploy_cml(
                    body.get("org"), body.get("model"), body.get("content")
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
                    body.get("keyField") or DEFAULT_KEY_FIELD
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
        urllib.request.urlopen(f"http://127.0.0.1:{port}/api/quit", timeout=3).read()
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
<title>CML Fetch, Deploy &amp; Compare</title>
<script>(function(){try{var t=localStorage.getItem('cml-theme')||'light';document.documentElement.setAttribute('data-theme',t);}catch(e){}})();</script>
<style>
  :root {
    --bg: #f4f6f9; --panel: #ffffff; --line: #e3e7ee; --text: #1b2330;
    --muted: #616b7b; --accent: #2f6fed; --green: #1f9d57; --red: #d23b34;
    --radius: 10px; --input-bg: #ffffff;
    --ok-bg:#e7f6ec; --ok-text:#0f6b39; --err-bg:#fdeae8; --err-text:#a3241d;
    --info-bg:#e8f0fe; --info-text:#1b4fb5;
    --chg-bg:#f3e1ec; --del-bg:#fbe3d2; --ins-bg:#d6e9f7;
    --chg-line:#b3589a; --del-line:#d55e00; --ins-line:#0072b2;
    --gutter:#f1f3f7; --gutter-text:#97a1b0;
  }
  html[data-theme="dark"] {
    --bg:#0f1115; --panel:#171a21; --line:#262b35; --text:#e6e9ef; --muted:#9aa3b2;
    --accent:#4c8bf5; --green:#2ea66b; --red:#e5534b; --input-bg:#0f131a;
    --ok-bg:rgba(46,166,107,.12); --ok-text:#8be0b3; --err-bg:rgba(229,83,75,.12); --err-text:#f3a9a4;
    --info-bg:rgba(76,139,245,.10); --info-text:#b9d2ff;
    --chg-bg:rgba(204,121,167,.26); --del-bg:rgba(213,94,0,.26); --ins-bg:rgba(0,114,178,.28);
    --chg-line:#cc79a7; --del-line:#e08a3c; --ins-line:#4ea3df;
    --gutter:#10141b; --gutter-text:#6b7480;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }
  .wrap { width: 100%; max-width: none; margin: 0; padding: 24px clamp(16px, 3vw, 40px) 60px; }
  .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .byline { font-size: 13px; margin: 0 0 6px; color: var(--muted); }
  .byline strong { color: var(--accent); font-weight: 600; }
  .byline a { color: var(--accent); text-decoration: none; }
  .byline a:hover { text-decoration: underline; }
  .byline .heart { color: var(--accent); }
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 22px; }
  .appver { color: var(--muted); font-size: 11px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; opacity: .8; white-space: nowrap; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; }
  .row { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; }
  .field { flex: 1; min-width: 220px; }
  label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .04em; }
  select, input, textarea {
    width: 100%; background: var(--input-bg); color: var(--text); border: 1px solid var(--line);
    border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none;
  }
  select:focus, input:focus, textarea:focus { border-color: var(--accent); }
  .btns { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; align-items: center; }
  .deploy-group { display: inline-flex; align-items: center; gap: 8px; padding: 4px 4px 4px 12px;
    border: 1px solid var(--line); border-radius: 8px; background: var(--gutter); }
  .deploy-group label { margin: 0; text-transform: none; letter-spacing: 0; font-size: 12px; color: var(--muted); white-space: nowrap; }
  .deploy-group select { width: auto; min-width: 150px; padding: 8px 10px; }
  button {
    border: none; border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: 600;
    cursor: pointer; color: #fff;
  }
  button:disabled { opacity: .5; cursor: not-allowed; }
  .fetch { background: var(--accent); }
  .deploy { background: var(--green); }
  .compare { background: #7a4fd0; }
  .ghost { background: transparent; border: 1px solid var(--line); color: var(--text); font-weight: 500; }
  .editor { margin-top: 22px; }
  .editor-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .editor-head label { margin: 0; }
  textarea {
    min-height: 300px; font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px;
    resize: vertical; white-space: pre; tab-size: 2;
  }
  .status { margin-top: 16px; font-size: 13px; padding: 12px 14px; border-radius: 8px; display: none; white-space: pre-wrap; font-family: "SF Mono", Menlo, monospace; }
  .status.show { display: block; }
  .status.ok { background: var(--ok-bg); border: 1px solid var(--green); color: var(--ok-text); }
  .status.err { background: var(--err-bg); border: 1px solid var(--red); color: var(--err-text); }
  .status.info { background: var(--info-bg); border: 1px solid var(--accent); color: var(--info-text); }
  .meta { color: var(--muted); font-size: 12px; text-transform: none; letter-spacing: 0; }
  .combo { display: flex; flex-direction: column; gap: 8px; }
  select[size] { padding: 0; height: auto; }
  select[size] option { padding: 8px 12px; border-bottom: 1px solid var(--line); }
  select[size] option:checked { background: var(--accent); color: #fff; }
  .combo-selected { display: flex; align-items: center; gap: 10px; }
  .selchip { flex: 1; display: inline-flex; align-items: center; gap: 8px; padding: 10px 12px;
    border-radius: 8px; background: var(--accent); color: #fff; font-weight: 600; font-size: 14px;
    border: 1px solid var(--accent); min-width: 0; }
  .selchip .name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .selchip::before { content: "✓"; font-weight: 700; flex: none; }
  [hidden] { display: none !important; }
  .spinner { display: inline-block; width: 13px; height: 13px; border: 2px solid rgba(128,128,128,.35); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; vertical-align: -2px; margin-right: 6px; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .conn { display: none; margin: 0 0 16px; padding: 11px 14px; border-radius: 8px; font-size: 13px;
    background: var(--err-bg); border: 1px solid var(--red); color: var(--err-text); }
  .conn.show { display: flex; align-items: center; }

  /* Diff view — two synced panes */
  .diff { margin-top: 22px; display: none; }
  .diff.show { display: block; }
  .diff-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .summary { font-size: 13px; font-weight: 600; }
  .legend { font-size: 12px; color: var(--muted); display: flex; gap: 14px; flex-wrap: wrap; align-items: center; }
  .legend span { display: inline-flex; align-items: center; }
  .legend i { width: 14px; height: 14px; border-radius: 3px; margin-right: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #1b2330; }
  .lg-chg { background: var(--chg-bg); border: 1px solid var(--chg-line); }
  .lg-del { background: var(--del-bg); border: 1px solid var(--del-line); }
  .lg-ins { background: var(--ins-bg); border: 1px solid var(--ins-line); }
  .diff-panes { display: flex; gap: 12px; align-items: stretch; }
  .pane { flex: 1; min-width: 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; }
  .pane-title { padding: 8px 12px; font-size: 12px; font-weight: 600; color: var(--muted); border-bottom: 1px solid var(--line); background: var(--gutter); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .pane-scroll { overflow: auto; max-height: 600px; }
  table.pane-table { border-collapse: collapse; width: 100%; font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; }
  .pane-table td { padding: 0 8px; vertical-align: top; white-space: pre; }
  .gutter { text-align: right; color: var(--gutter-text); background: var(--gutter); user-select: none; width: 1%; white-space: nowrap; border-right: 1px solid var(--line); position: sticky; left: 0; }
  .code { width: 100%; border-left: 3px solid transparent; }
  .mk { user-select: none; display: inline-block; width: 1ch; margin-right: 7px; color: var(--muted); font-weight: 700; }
  .row-chg .code { background: var(--chg-bg); border-left-color: var(--chg-line); }
  .row-del .code { background: var(--del-bg); border-left-color: var(--del-line); }
  .row-ins .code { background: var(--ins-bg); border-left-color: var(--ins-line); }
  .row-filler td { background: repeating-linear-gradient(45deg, transparent, transparent 6px, rgba(128,128,128,.06) 6px, rgba(128,128,128,.06) 12px); }
  .moved { color: var(--accent); font-style: italic; }
  .diff-panes.hide-eq tr.eqrow { display: none; }
  .diff-opts { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
  .diff-opts input { width: auto; }

  /* Constraint data (ExpressionSetConstraintObj) */
  .section-head { margin: 30px 0 4px; font-size: 16px; font-weight: 700; display: flex; align-items: center; gap: 10px; }
  .section-head .meta { font-weight: 400; }
  .data { margin-top: 14px; display: none; }
  .data.show { display: block; }
  .data-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }
  .chip.ok { background: var(--ok-bg); color: var(--ok-text); border-color: var(--green); }
  .chip.add { background: var(--ins-bg); color: var(--ins-line); border-color: var(--ins-line); }
  .chip.extra { background: var(--del-bg); color: var(--del-line); border-color: var(--del-line); }
  .chip.warn { background: var(--err-bg); color: var(--err-text); border-color: var(--red); }
  .table-scroll { overflow: auto; max-height: 560px; border: 1px solid var(--line); border-radius: 8px; }
  table.data-table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
  .data-table th, .data-table td { padding: 7px 10px; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; vertical-align: top; }
  .data-table th { position: sticky; top: 0; background: var(--gutter); color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; z-index: 1; }
  .data-table tbody tr:hover { background: var(--gutter); }
  .data-table .gkey { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 11px; color: var(--muted); }
  .badge { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px; }
  .b-match { background: var(--ok-bg); color: var(--ok-text); }
  .b-add { background: var(--ins-bg); color: var(--ins-line); }
  .b-extra { background: var(--del-bg); color: var(--del-line); }
  .b-blocked, .b-unmappable { background: var(--err-bg); color: var(--err-text); }
  .b-type { background: var(--info-bg); color: var(--info-text); }
  .data-filter { font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 6px; }
  .data-filter select { width: auto; padding: 6px 8px; }
  .data-table td.sel, .data-table th.sel { width: 1%; text-align: center; }
  .data-table input[type=checkbox] { width: auto; cursor: pointer; }
  .b-dup { background: #fff2cc; color: #7a5c00; border: 1px solid #e0b400; margin-left: 6px; }
  html[data-theme="dark"] .b-dup { background: rgba(224,180,0,.18); color: #f2d680; border-color: #9a7c00; }
  .deploy-bar { display: none; margin-top: 14px; padding: 12px 14px; border-radius: 8px; background: var(--info-bg); border: 1px solid var(--accent);
    align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
  .deploy-bar.show { display: flex; }
  .deploy-bar .sel-summary { font-size: 13px; color: var(--text); }
  .deploy-bar .sel-actions { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .linklike { background: none; border: none; color: var(--accent); font-weight: 600; cursor: pointer; padding: 4px 6px; font-size: 12px; }
  .warn-note { color: var(--err-text); font-size: 12px; }
  .results { display: none; margin-top: 16px; }
  .results.show { display: block; }
  .results h4 { margin: 0 0 8px; font-size: 14px; }
  .result-row { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; display: flex; gap: 8px; }
  .result-row.good { background: var(--ok-bg); color: var(--ok-text); }
  .result-row.bad { background: var(--err-bg); color: var(--err-text); }
  .result-row .ico { font-weight: 700; }
  /* ---- Best-practices lint report ---- */
  .lint { display: none; margin-top: 16px; }
  .lint.show { display: block; }
  .lint-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .lint-head h4 { margin: 0; font-size: 14px; }
  .lint-score { font-size: 13px; font-weight: 700; padding: 4px 10px; border-radius: 999px; }
  .lint-score.good { background: var(--ok-bg); color: var(--ok-text); }
  .lint-score.mid { background: var(--del-bg); color: var(--del-line); }
  .lint-score.bad { background: var(--err-bg); color: var(--err-text); }
  .lint-counts { font-size: 12px; color: var(--muted); display: flex; gap: 10px; flex-wrap: wrap; }
  .lint-caption { font-size: 12px; color: var(--muted); margin: 8px 0 12px; line-height: 1.5; }
  .lint-item { border: 1px solid var(--line); border-left-width: 4px; border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; font-size: 13px; }
  .lint-item .rmeta { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-bottom: 2px; }
  .lint-item .msg { color: var(--text); }
  .lint-item .fix { color: var(--muted); font-size: 12px; margin-top: 3px; }
  .lint-item.error { border-left-color: var(--red); }
  .lint-item.warn { border-left-color: var(--del-line); }
  .lint-item.info { border-left-color: var(--accent); }
  .lint-line { font-family: "SF Mono", Menlo, Consolas, monospace; color: var(--accent); cursor: pointer; font-weight: 700; }
  .lint-empty { padding: 12px; border-radius: 8px; background: var(--ok-bg); color: var(--ok-text); font-size: 13px; }
  .lint-fix { margin-top: 8px; }
  .lint-fix .fixhead { font-size: 11px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin: 8px 0 3px; display: flex; align-items: center; gap: 8px; }
  .lint-code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--line); }
  .lint-code.before { background: var(--del-bg); color: var(--del-line); }
  .lint-code.after { background: var(--ins-bg); color: var(--ins-line); }
  .lint-copy { font-size: 11px; padding: 1px 8px; }
  /* ---- Semantic diff ---- */
  .sem-diff { display: none; margin-top: 12px; }
  .sem-diff.show { display: block; }
  .sem-sec { margin-bottom: 14px; }
  .sem-sec h4 { margin: 0 0 6px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
  .sem-block { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; margin-bottom: 6px; font-size: 13px; }
  .sem-block .nm { font-weight: 700; }
  .sem-block .knd { font-size: 11px; color: var(--muted); }
  .sem-mem { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px; padding: 3px 8px; border-radius: 5px; margin: 3px 0; white-space: pre-wrap; }
  .sem-mem.add { background: var(--ins-bg); color: var(--ins-line); }
  .sem-mem.del { background: var(--del-bg); color: var(--del-line); }
  .sem-mem.chg { background: var(--chg-bg); color: var(--chg-line); }
  .sem-mem .lab { font-weight: 700; margin-right: 6px; }
  .sem-ok { padding: 12px; border-radius: 8px; background: var(--ok-bg); color: var(--ok-text); font-size: 13px; }
  .sem-moved { font-size: 12px; color: var(--muted); margin-top: 6px; }
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>CML Fetch, Deploy &amp; Compare</h1>
        <p class="byline">Made with <span class="heart">&#128153;</span> by <a href="https://www.linkedin.com/in/mrpancholi/" target="_blank" rel="noopener noreferrer"><strong>Mritunjaya Pancholi</strong></a></p>
        <p class="sub">Pick a source org — its CMLs load automatically. Fetch, Deploy, or Compare against a target org. No terminal needed.</p>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="appver" id="appver" title="Running build — confirms you're on the latest version"></span>
        <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
      </div>
    </div>

    <div class="conn" id="conn"></div>

    <div class="panel">
      <div class="row">
        <div class="field">
          <label for="org">Source org (fetch / deploy / compare-from)</label>
          <select id="org"><option>Loading orgs…</option></select>
        </div>
        <div class="field">
          <label for="targetOrg">Target org (compare-with)</label>
          <select id="targetOrg"><option>Loading orgs…</option></select>
        </div>
      </div>

      <div class="row" style="margin-top:14px;">
        <div class="field">
          <label for="model">CML <span id="cmlCount" class="meta"></span></label>
          <div class="combo" id="combo">
            <input id="cmlFilter" placeholder="Type to filter CMLs…" autocomplete="off" spellcheck="false" />
            <select id="model" size="6"><option value="">Choose an org first…</option></select>
          </div>
          <div class="combo-selected" id="comboSelected" hidden>
            <span class="selchip"><span class="name" id="selectedName"></span></span>
            <button type="button" class="ghost" id="changeModelBtn">Change CML</button>
          </div>
        </div>
      </div>

      <div class="btns">
        <button class="ghost" id="reloadBtn">Reload list</button>
        <button class="fetch" id="fetchBtn">Fetch CML</button>
        <span class="deploy-group">
          <label for="deployOrg">Deploy to</label>
          <select id="deployOrg"><option>Loading orgs…</option></select>
          <button class="deploy" id="deployBtn">Deploy CML</button>
        </span>
        <button class="compare" id="compareBtn">Compare source ↔ target</button>
      </div>

      <div class="editor">
        <div class="editor-head">
          <label>CML Content</label>
          <span style="display:flex;gap:8px;">
            <button class="ghost" id="lintBtn" title="Scan the CML above against built-in best-practice rules">Check best practices</button>
            <button class="ghost" id="copyBtn">Copy</button>
          </span>
        </div>
        <textarea id="content" placeholder="Fetched CML appears here. You can also paste CML here and Deploy it." spellcheck="false"></textarea>
      </div>

      <div class="lint" id="lint"></div>

      <div class="status" id="status"></div>

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

      <div class="section-head">
        Constraint Data <span class="meta">— Product associations (ExpressionSetConstraintObj)</span>
      </div>
      <p class="sub" style="margin:4px 0 12px;">Deploying CML code alone doesn't recreate the Product associations. These rows are matched across orgs by a <strong>foreign key</strong> you choose below — a field whose value is the same for a record in every org — instead of by record Id.</p>
      <div class="row" style="margin-bottom:4px;">
        <div class="field" style="max-width:340px;">
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
          <p class="meta" style="margin:6px 0 0;">Must exist on the reference objects. <code>Name</code> always works; pick a stable custom/external Id if you have one.</p>
        </div>
      </div>
      <div class="btns" style="margin-top:6px;">
        <button class="ghost" id="loadDataBtn">View data (source org)</button>
        <button class="compare" id="compareDataBtn">Compare data (source ↔ target)</button>
      </div>

      <div class="data" id="data">
        <div class="data-head">
          <div class="chips" id="dataChips"></div>
          <label class="data-filter">Show
            <select id="dataFilter">
              <option value="all">All rows</option>
              <option value="match">Matched only</option>
              <option value="add">Only in source (to add)</option>
              <option value="extra">Only in target (extra)</option>
              <option value="blocked">Blocked / unmappable</option>
              <option value="dups">Duplicates only</option>
            </select>
          </label>
        </div>

        <div class="deploy-bar" id="deployBar">
          <div class="sel-summary" id="selSummary"></div>
          <div class="sel-actions">
            <button class="linklike" id="selAllAdds">Select all adds</button>
            <button class="linklike" id="selNoAdds">Clear adds</button>
            <button class="linklike" id="selAllDels">Select all deletes</button>
            <button class="linklike" id="selNoDels">Clear deletes</button>
            <button class="deploy" id="deployDataBtn">Deploy selected to target</button>
          </div>
        </div>

        <div class="table-scroll">
          <table class="data-table" id="dataTable"></table>
        </div>

        <div class="results" id="results"></div>
      </div>
    </div>
  </div>

<script>
  const $ = (id) => document.getElementById(id);
  const orgSel = $("org"), targetSel = $("targetOrg"), model = $("model"), content = $("content"), status = $("status");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const cmlFilter = $("cmlFilter"), reloadBtn = $("reloadBtn"), cmlCount = $("cmlCount");
  const combo = $("combo"), comboSelected = $("comboSelected"), selectedName = $("selectedName"), changeModelBtn = $("changeModelBtn");
  const deployOrgSel = $("deployOrg");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll");
  const lintBtn = $("lintBtn"), lintBox = $("lint");
  const semanticChk = $("semanticDiff"), semDiff = $("semDiff"), lineLegend = $("lineLegend"), onlyDiffsWrap = $("onlyDiffsWrap");
  let lastCompare = null;
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn"), keyField = $("keyField");
  const keyName = () => (keyField.value || "Global_Key__c").trim();
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  const deployBar = $("deployBar"), selSummary = $("selSummary"), deployDataBtn = $("deployDataBtn");
  const selAllAdds = $("selAllAdds"), selNoAdds = $("selNoAdds"), selAllDels = $("selAllDels"), selNoDels = $("selNoDels");
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

  function setStatus(kind, msg) {
    status.className = "status show " + kind;
    status.textContent = msg;
    status.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
        method: "POST", headers: { "Content-Type": "application/json" },
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
  const actionBtns = [fetchBtn, deployBtn, compareBtn, loadDataBtn, compareDataBtn, deployDataBtn];
  function busy(btn, label) {
    btn.innerHTML = '<span class="spinner"></span>' + label;
    actionBtns.forEach(b => b.disabled = true);
  }
  function idle() {
    fetchBtn.textContent = "Fetch CML";
    deployBtn.textContent = "Deploy CML";
    compareBtn.textContent = "Compare source ↔ target";
    loadDataBtn.textContent = "View data (source org)";
    compareDataBtn.textContent = "Compare data (source ↔ target)";
    deployDataBtn.textContent = "Deploy selected to target";
    actionBtns.forEach(b => b.disabled = false);
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
    busy(deployBtn, "Deploying…");
    setStatus("info", "Deploying " + model.value.trim() + " to " + dest + "…");
    try {
      const data = await postJSON("/api/deploy", { org: dest, model: model.value.trim(), content: content.value });
      setStatus(data.ok ? "ok" : "err", data.log || (data.ok ? "Deployed." : "Deploy failed."));
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e); }
    }
    idle();
  };

  copyBtn.onclick = async () => {
    if (!content.value) return;
    try { await navigator.clipboard.writeText(content.value); copyBtn.textContent = "Copied!"; setTimeout(() => copyBtn.textContent = "Copy", 1200); }
    catch (e) { content.select(); document.execCommand("copy"); }
  };

  // ---- Compare (source org vs target org) ----
  compareBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org."); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org."); return; }
    if (orgSel.value === targetSel.value) { setStatus("err", "Source and target orgs are the same. Pick two different orgs."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    busy(compareBtn, "Comparing…");
    diffBox.classList.remove("show");
    setStatus("info", `Comparing "${model.value}" between ${orgSel.value} (source) and ${targetSel.value} (target)…\nThis fetches the CML from both orgs and can take up to a minute — please wait.`);
    try {
      const data = await postJSON("/api/compare", { sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim() });
      if (data.ok) {
        lastCompare = { src: data.source, tgt: data.target };
        renderCompare();
        setStatus("ok", `Compared "${data.model}".\nSource: ${data.source.file}\nTarget: ${data.target.file}`);
      } else {
        setStatus("err", data.log || "Compare failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Compare error: " + e); }
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

  lintBtn.onclick = () => {
    if (!content.value.trim()) { setStatus("err", "Paste or fetch some CML first, then check best practices."); return; }
    renderLint(content.value);
    setStatus("ok", "Best-practice check complete — see the report below the editor.");
  };

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
    if (s === "blocked")    return '<span class="badge b-blocked">Blocked — ref missing in target</span>';
    if (s === "unmappable") return '<span class="badge b-unmappable">No ' + esc(currentKeyField) + '</span>';
    return "";
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
    let sel = "";
    if (withStatus) {
      if (isAdd(r) || isDel(r)) {
        sel = `<td class="sel"><input type="checkbox" data-i="${r._i}" ${r._selected ? "checked" : ""}></td>`;
      } else {
        sel = `<td class="sel"></td>`;
      }
    }
    return "<tr>"
      + sel
      + (withStatus ? `<td>${statusBadge(r._status)}</td>` : "")
      + `<td><span class="badge b-type">${esc(shortType(r.refType))}</span></td>`
      + `<td>${esc(r.tagType)}</td>`
      + `<td>${esc(r.tag)}</td>`
      + `<td>${esc(r.refName)}${code}${dupBadges(r)}</td>`
      + `<td>${gk}</td>`
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
      if (f === "blocked") return r._status === "blocked" || r._status === "unmappable";
      if (f === "dups")    return r.dups && r.dups.length;
      return true;
    });
    const cols = (withStatus ? 7 : 5);
    const head = "<thead><tr>"
      + (withStatus ? '<th class="sel"></th><th>Status</th>' : "")
      + "<th>Ref type</th><th>Tag type</th><th>Tag</th><th>Reference record</th><th>" + esc(currentKeyField) + "</th>"
      + "</tr></thead>";
    const body = visible.length
      ? visible.map(r => dataRowHtml(r, withStatus)).join("")
      : `<tr><td colspan="${cols}" style="text-align:center;color:var(--muted);padding:18px;">No rows for this filter.</td></tr>`;
    dataTable.innerHTML = head + "<tbody>" + body + "</tbody>";
    dataTable.querySelectorAll("input[type=checkbox]").forEach(cb => {
      cb.onchange = () => { dataRows[+cb.dataset.i]._selected = cb.checked; updateDeployBar(); };
    });
    updateDeployBar();
  }
  dataFilter.onchange = renderDataTable;

  function updateDeployBar() {
    if (dataMode !== "compare") { deployBar.classList.remove("show"); return; }
    const adds = dataRows.filter(r => isAdd(r) && r._selected).length;
    const dels = dataRows.filter(r => isDel(r) && r._selected).length;
    const totalAdds = dataRows.filter(isAdd).length;
    const totalDels = dataRows.filter(isDel).length;
    deployBar.classList.toggle("show", (totalAdds + totalDels) > 0);
    selSummary.innerHTML =
      `Selected: <strong>${adds}</strong> to add`
      + (dels ? ` · <strong class="warn-note">${dels}</strong> <span class="warn-note">to delete</span>` : ` · <strong>0</strong> to delete`);
    deployDataBtn.disabled = (adds + dels) === 0;
  }

  function setSel(pred, val) { dataRows.forEach(r => { if (pred(r)) r._selected = val; }); renderDataTable(); }
  selAllAdds.onclick = () => setSel(isAdd, true);
  selNoAdds.onclick  = () => setSel(isAdd, false);
  selAllDels.onclick = () => setSel(isDel, true);
  selNoDels.onclick  = () => setSel(isDel, false);

  loadDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org first."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    busy(loadDataBtn, "Loading…");
    setStatus("info", `Loading constraint data for "${model.value}" from ${orgSel.value}…`);
    try {
      const data = await postJSON("/api/data", { org: orgSel.value, model: model.value.trim(), keyField: keyName() });
      if (data.ok) {
        dataMode = "single";
        currentKeyField = data.keyField || keyName();
        dataRows = data.rows.map((r, i) => ({ ...r, _status: "", _i: i, _selected: false }));
        deployBar.classList.remove("show");
        results.classList.remove("show");
        renderDataChips({ single: true, total: data.stats.total, unmappable: data.stats.unmappable, dups: data.stats.duplicates, org: orgSel.value });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const warn = data.stats.unmappable ? ` (${data.stats.unmappable} without ${currentKeyField})` : "";
        setStatus("ok", `Loaded ${data.stats.total} constraint rows from ${orgSel.value}${warn}.`);
      } else {
        setStatus("err", data.log || "Could not load data.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Data error: " + e); }
    }
    idle();
  };

  compareDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org."); return; }
    if (!targetSel.value) { setStatus("err", "Please choose a target org."); return; }
    if (orgSel.value === targetSel.value) { setStatus("err", "Source and target orgs are the same. Pick two different orgs."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    busy(compareDataBtn, "Comparing…");
    setStatus("info", `Comparing constraint data for "${model.value}" between ${orgSel.value} and ${targetSel.value}…\nThis reads both orgs and can take up to a minute — please wait.`);
    try {
      const data = await postJSON("/api/data/compare", { sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim(), keyField: keyName() });
      if (data.ok) {
        dataMode = "compare";
        currentKeyField = data.keyField || keyName();
        const rows = [];
        data.matched.forEach(r => rows.push({ ...r, _status: "match" }));
        data.sourceOnly.forEach(r => rows.push({ ...r, _status: r.deployStatus === "ready" ? "add" : r.deployStatus }));
        data.targetOnly.forEach(r => rows.push({ ...r, _status: "extra" }));
        // Adds default ON; deletes default OFF (deletion is riskier — opt in).
        rows.forEach((r, i) => { r._i = i; r._selected = (r._status === "add"); });
        dataRows = rows;
        results.classList.remove("show");
        renderDataChips({ single: false, s: data.stats, src: data.source, tgt: data.target });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        setStatus("ok", `Compared constraint data for "${data.model}".\n`
          + `${data.stats.matched} matched · ${data.stats.sourceOnly} only in source · ${data.stats.targetOnly} only in target.`);
      } else {
        setStatus("err", data.log || "Compare failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Data compare error: " + e); }
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
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked (ref missing in target)</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "")
      + ((sd + td) ? `<span class="chip warn">${sd + td} duplicate rows (src ${sd} / tgt ${td})</span>` : "");
  }

  // ---- Deploy selected constraint data to the target ----
  function renderResults(data) {
    const s = data.stats;
    let html = `<h4>Deployment results — target ${esc(data.target)}</h4>`;
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
    results.innerHTML = html;
    results.classList.add("show");
    results.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  deployDataBtn.onclick = async () => {
    const adds = dataRows.filter(r => isAdd(r) && r._selected)
      .map(r => ({ tag: r.tag, tagType: r.tagType, refType: r.refType, gkey: r.gkey, refName: r.refName }));
    const deletes = dataRows.filter(r => isDel(r) && r._selected)
      .map(r => ({ id: r.id, tag: r.tag, tagType: r.tagType, refName: r.refName }));
    if (!adds.length && !deletes.length) { setStatus("err", "Select at least one row to deploy."); return; }
    let msg = `Deploy to "${targetSel.value}"?\n\n• ${adds.length} association(s) will be ADDED.`;
    if (deletes.length) msg += `\n• ${deletes.length} association(s) will be DELETED (permanent).`;
    msg += `\n\nProceed?`;
    if (!confirm(msg)) return;
    busy(deployDataBtn, "Deploying…");
    setStatus("info", `Deploying constraint data to ${targetSel.value}: +${adds.length} / −${deletes.length}…`);
    try {
      const data = await postJSON("/api/data/deploy", {
        sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim(),
        adds, deletes, keyField: keyName()
      });
      if (data.ok) {
        renderResults(data);
        const s = data.stats;
        setStatus(s.insertFail + s.deleteFail ? "info" : "ok",
          `Done. Added ${s.insertOk}/${adds.length}, deleted ${s.deleteOk}/${deletes.length}.`
          + (s.insertFail + s.deleteFail ? ` ${s.insertFail + s.deleteFail} failed — see details below.` : "")
          + `\nRe-comparing to refresh…`);
        compareDataBtn.click();  // refresh the comparison to reflect new state
      } else {
        setStatus("err", data.log || "Deploy failed.");
      }
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); } else { setStatus("err", "Deploy error: " + e); }
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
