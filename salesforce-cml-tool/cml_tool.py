#!/usr/bin/env python3
"""
cml_tool.py — A tiny local web UI for fetching, deploying, and comparing
Salesforce Revenue Cloud CML (Constraint Model Language).

It wraps two small helper scripts that live next to it:
    - fetch-cml.sh    (fetch a CML from an org)
    - deploy-cml.py   (deploy a CML to an org)

You never type in the terminal: pick an org from the dropdown, choose a CML,
and click Fetch / Deploy / Compare.

Run it (or just double-click "Open CML Tool.command"):
    python3 cml_tool.py

It starts a local server on 127.0.0.1 and opens your browser.
Only the Python 3 standard library is used — nothing to install.
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = APP_DIR
SCRIPTS_DIR = APP_DIR
FETCH_SCRIPT = os.path.join(APP_DIR, "fetch-cml.sh")
DEPLOY_SCRIPT = os.path.join(APP_DIR, "deploy-cml.py")
DOWNLOAD_DIR = os.path.join(APP_DIR, "cml-files")

# When launched from Finder (double-click), the process may not inherit the
# shell PATH, so CLIs like `sf` can't be found. Augment PATH with every known
# install location so the tool works regardless of how it was started.
#
# The most common cause of "orgs not loading" is that `sf` was installed via
# nvm/fnm (Node version managers). These put sf under a versioned path like
#   ~/.nvm/versions/node/v20.x.x/bin/sf
# but they only add it to PATH inside an interactive shell (via .zshrc /
# .bashrc). A double-clicked .command file starts a login shell that does NOT
# source .zshrc, so that path is never set.
#
# Fix: scan ALL installed node versions under nvm/fnm/volta at startup.

def _nvm_bin_dirs() -> list:
    """Return every bin/ directory across all nvm-installed Node versions."""
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
    """Return every bin/ directory across all fnm-installed Node versions."""
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
    """Return Volta's shim bin directory if present."""
    p = os.path.expanduser("~/.volta/bin")
    return [p] if os.path.isdir(p) else []


def _extra_paths() -> list:
    """Build the full list of extra PATH entries to search for sf."""
    static = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        os.path.expanduser("~/.npm-global/bin"),
        os.path.expanduser("~/.nvm/current/bin"),  # kept for backward compat
        "/usr/local/sfdx/bin",
        # Homebrew-managed Node on Apple Silicon
        "/opt/homebrew/lib/node_modules/@salesforce/cli/bin",
    ]
    return static + _nvm_bin_dirs() + _fnm_bin_dirs() + _volta_bin_dir()


CMD_TIMEOUT = 120  # seconds


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
    # Direct file check across every candidate dir (catches cases where the
    # directory exists but isn't in the which search path)
    for p in _extra_paths():
        candidate = os.path.join(p, "sf")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def sf_debug_info() -> dict:
    """Return diagnostic info about the sf CLI and authorized orgs.

    Called by /api/debug so users can diagnose 'orgs not loading' without
    opening a terminal.
    """
    sf_path = find_sf()
    sf_version = None
    if sf_path:
        try:
            res = subprocess.run([sf_path, "--version"], capture_output=True,
                                 text=True, timeout=10, env=_env())
            sf_version = (res.stdout or res.stderr or "").strip().splitlines()[0]
        except Exception:  # noqa: BLE001
            sf_version = "(could not run --version)"

    searched = [p for p in _extra_paths() if p]
    found_dirs = [p for p in searched if os.path.isdir(p)]

    info = {
        "sf_found": sf_path is not None,
        "sf_path": sf_path or "not found",
        "sf_version": sf_version,
        "path_searched": searched,
        "path_found": found_dirs,
        "system_path": os.environ.get("PATH", "").split(os.pathsep),
    }

    if sf_path:
        try:
            proc = subprocess.run([sf_path, "org", "list", "--json"],
                                  capture_output=True, text=True, timeout=30,
                                  env=_env())
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
    """subprocess.run with augmented PATH, timeout, and captured text output."""
    return subprocess.run(
        args, capture_output=True, text=True, cwd=REPO_ROOT,
        env=_env(), timeout=CMD_TIMEOUT, **kwargs,
    )


def list_orgs():
    """Return a sorted list of {alias, username} from `sf org list`."""
    if not find_sf():
        return {"error": "The Salesforce CLI ('sf') was not found on this machine. "
                         "Install it or run: npm install -g @salesforce/cli"}
    try:
        proc = run(["sf", "org", "list", "--json"])
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
    try:
        proc = run(["sf", "data", "query", "--query", query,
                    "--target-org", org, "--json"])
    except subprocess.TimeoutExpired:
        return {"error": f"Loading CMLs timed out after {CMD_TIMEOUT}s."}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Could not load CMLs: {exc}"}

    if not proc.stdout.strip():
        return {"error": (proc.stderr or "No response from the org.").strip()}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": (proc.stderr or proc.stdout)[:500].strip()}
    if data.get("status") != 0:
        msg = data.get("message") or "Query failed."
        return {"error": msg}

    latest = {}
    for rec in data.get("result", {}).get("records", []):
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


def _download_cml(org, model, out_file):
    """Fetch one CML via fetch-cml.sh into out_file. Returns a result dict."""
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    try:
        proc = run(["bash", FETCH_SCRIPT, org, model, out_file])
    except subprocess.TimeoutExpired:
        return {"ok": False, "log": f"Fetch timed out after {CMD_TIMEOUT}s. "
                                    "Check your org connection (sf org login) and try again."}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "log": f"Could not run fetch: {exc}"}
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return {"ok": False, "log": (log.strip() or
                f"Fetch failed (exit {proc.returncode}). "
                "Verify the org alias and CML API name are correct.")}
    try:
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as exc:
        return {"ok": False, "log": f"{log}\nCould not read file: {exc}"}
    if not content.strip():
        return {
            "ok": False, "content": "", "file": out_file, "empty": True,
            "log": (
                f"{log}\n\nThe latest version of '{model}' in '{org}' has an EMPTY "
                "Constraint Model (this usually means the version is Inactive or was "
                "never populated). Try an org where an Active version exists."
            ).strip(),
        }
    return {"ok": True, "log": log.strip(), "content": content, "file": out_file}


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


def _query_json(org, soql):
    """Run a SOQL query and return (records, error). error is None on success."""
    try:
        proc = run(["sf", "data", "query", "--query", soql,
                    "--target-org", org, "--json"])
    except subprocess.TimeoutExpired:
        return None, f"Query timed out after {CMD_TIMEOUT}s."
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not run query: {exc}"
    if not proc.stdout.strip():
        return None, (proc.stderr or "No response from the org.").strip()
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, (proc.stderr or proc.stdout)[:500].strip()
    if data.get("status") != 0:
        return None, data.get("message") or "Query failed."
    return data.get("result", {}).get("records", []), None


def _constraint_key(tag_type, tag, ref_type, gkey):
    """Org-portable identity for one constraint row."""
    return "\u241f".join([tag_type or "", tag or "", ref_type or "",
                          gkey or ""])


def export_constraints(org, model):
    """Return enriched ExpressionSetConstraintObj rows for one CML model.

    Each row is resolved to its reference object's type + Global_Key__c so it
    can be matched across orgs regardless of record Ids.
    """
    if not org or not model:
        return {"ok": False, "log": "Choose an org and a CML first."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    soql = (
        "SELECT Id, ExpressionSet.Name, ConstraintModelTag, "
        "ConstraintModelTagType, ReferenceObjectId, "
        "TYPEOF ReferenceObject "
        "WHEN Product2 THEN Global_Key__c, Name, ProductCode "
        "WHEN ProductClassification THEN Global_Key__c, Name "
        "WHEN ProductComponentGroup THEN Global_Key__c, Name "
        "WHEN ProductRelatedComponent THEN Global_Key__c, Name "
        "ELSE Name END "
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
        gkey = ro.get("Global_Key__c")
        tag = rec.get("ConstraintModelTag")
        tag_type = rec.get("ConstraintModelTagType")
        mappable = bool(gkey)
        if not mappable:
            unmapped += 1
        rows.append({
            "id": rec.get("Id"),
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
    return {"ok": True, "org": org, "model": model, "rows": rows,
            "stats": {"total": len(rows), "unmappable": unmapped}}


def _target_present_keys(target_org, needed):
    """Given {refType: set(gkeys)} needed in the target, return the set of
    (refType, gkey) that actually exist there. Used to flag whether a
    source-only constraint can be deployed (its reference record exists)."""
    present = set()
    for ref_type, gkeys in needed.items():
        gkeys = [g for g in gkeys if g]
        if not gkeys:
            continue
        for i in range(0, len(gkeys), 200):  # keep IN-lists well under limits
            chunk = gkeys[i:i + 200]
            in_list = ",".join("'" + _soql_str(g) + "'" for g in chunk)
            soql = (f"SELECT Global_Key__c FROM {ref_type} "
                    f"WHERE Global_Key__c IN ({in_list})")
            recs, err = _query_json(target_org, soql)
            if err:  # treat as unknown rather than blocking the whole compare
                continue
            for r in recs:
                present.add((ref_type, r.get("Global_Key__c")))
    return present


def compare_constraints(source_org, target_org, model):
    """Compare constraint data of one CML between two orgs, keyed on the
    portable composite key. Returns matched / source-only / target-only rows
    plus, for source-only rows, whether the reference record exists in target.
    """
    if not source_org or not target_org or not model:
        return {"ok": False, "log": "Choose a source org, a target org, and a CML."}
    if source_org == target_org:
        return {"ok": False, "log": "Source and target orgs are the same. Pick two different orgs."}

    src = export_constraints(source_org, model)
    if not src.get("ok"):
        return src
    tgt = export_constraints(target_org, model)
    if not tgt.get("ok"):
        return tgt

    src_by = {r["key"]: r for r in src["rows"]}
    tgt_by = {r["key"]: r for r in tgt["rows"]}

    # Reference records needed in target for the rows that are only in source.
    needed = {}
    for key, r in src_by.items():
        if key not in tgt_by and r["mappable"]:
            needed.setdefault(r["refType"], set()).add(r["gkey"])
    present = _target_present_keys(target_org, needed)

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
        "ok": True, "model": model,
        "source": {"org": source_org, "total": len(src["rows"])},
        "target": {"org": target_org, "total": len(tgt["rows"])},
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


def deploy_cml(org, model, content):
    """Write content to a temp file and run deploy-cml.py against the model."""
    if not org or not model:
        return {"ok": False, "log": "Please choose an org and enter the CML API name."}
    if not content or not content.strip():
        return {"ok": False, "log": "There is no CML content to deploy."}
    if not find_sf():
        return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                    "Install it with: npm install -g @salesforce/cli"}
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".cml", delete=False, encoding="utf-8"
    )
    try:
        tmp.write(content)
        tmp.close()
        try:
            proc = run([sys.executable or "python3", DEPLOY_SCRIPT,
                        org, "--model", model, tmp.name])
        except subprocess.TimeoutExpired:
            return {"ok": False, "log": f"Deploy timed out after {CMD_TIMEOUT}s. "
                                        "Check your org connection and try again."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "log": f"Could not run deploy: {exc}"}
        log = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            return {"ok": False, "log": (log.strip() or
                    f"Deploy failed (exit {proc.returncode}).")}
        return {"ok": True, "log": log.strip()}
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


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
                    body.get("org"), body.get("model")
                ))
            elif self.path == "/api/data/compare":
                self._send(200, compare_constraints(
                    body.get("sourceOrg"), body.get("targetOrg"), body.get("model")
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
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/ping", timeout=2
        ) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == APP_ID
    except Exception:  # noqa: BLE001
        return False




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
  .sub { color: var(--muted); font-size: 13px; margin: 0 0 22px; }
  .panel { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 18px; }
  .row { display: flex; gap: 14px; flex-wrap: wrap; align-items: flex-end; }
  .field { flex: 1; min-width: 220px; }
  label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: .04em; }
  select, input, textarea {
    width: 100%; background: var(--input-bg); color: var(--text); border: 1px solid var(--line);
    border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none;
  }
  select:focus, input:focus, textarea:focus { border-color: var(--accent); }
  .btns { display: flex; gap: 10px; margin-top: 16px; flex-wrap: wrap; }
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
</style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div>
        <h1>CML Fetch, Deploy &amp; Compare</h1>
        <p class="sub">Pick a source org — its CMLs load automatically. Fetch, Deploy, or Compare against a target org. No terminal needed.</p>
      </div>
      <button class="ghost" id="themeBtn" title="Toggle day/night">Night mode</button>
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
          <div class="combo">
            <input id="cmlFilter" placeholder="Type to filter CMLs…" autocomplete="off" spellcheck="false" />
            <select id="model" size="6"><option value="">Choose an org first…</option></select>
          </div>
        </div>
      </div>

      <div class="btns">
        <button class="ghost" id="reloadBtn">Reload list</button>
        <button class="fetch" id="fetchBtn">Fetch CML</button>
        <button class="deploy" id="deployBtn">Deploy CML</button>
        <button class="compare" id="compareBtn">Compare source ↔ target</button>
      </div>

      <div class="editor">
        <div class="editor-head">
          <label>CML Content</label>
          <button class="ghost" id="copyBtn">Copy</button>
        </div>
        <textarea id="content" placeholder="Fetched CML appears here. You can also paste CML here and Deploy it." spellcheck="false"></textarea>
      </div>

      <div class="status" id="status"></div>

      <div class="diff" id="diff">
        <div class="diff-head">
          <div class="summary" id="diffSummary"></div>
          <div class="legend">
            <span><i class="lg-chg">~</i>Changed</span>
            <span><i class="lg-del">&minus;</i>Only in source</span>
            <span><i class="lg-ins">+</i>Only in target</span>
            <label class="diff-opts"><input type="checkbox" id="onlyDiffs" /> Show only differences</label>
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
      </div>

      <div class="section-head">
        Constraint Data <span class="meta">— Product associations (ExpressionSetConstraintObj)</span>
      </div>
      <p class="sub" style="margin:4px 0 12px;">Deploying CML code alone doesn't recreate the Product associations. These rows are matched across orgs by each reference record's <code>Global_Key__c</code>, not by record Id.</p>
      <div class="btns" style="margin-top:0;">
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
            </select>
          </label>
        </div>
        <div class="table-scroll">
          <table class="data-table" id="dataTable"></table>
        </div>
      </div>
    </div>
  </div>

<script>
  const $ = (id) => document.getElementById(id);
  const orgSel = $("org"), targetSel = $("targetOrg"), model = $("model"), content = $("content"), status = $("status");
  const fetchBtn = $("fetchBtn"), deployBtn = $("deployBtn"), compareBtn = $("compareBtn"), copyBtn = $("copyBtn");
  const cmlFilter = $("cmlFilter"), reloadBtn = $("reloadBtn"), cmlCount = $("cmlCount");
  const themeBtn = $("themeBtn"), conn = $("conn");
  const diffBox = $("diff"), diffSummary = $("diffSummary"), onlyDiffs = $("onlyDiffs");
  const diffPanes = $("diffPanes"), srcTable = $("srcTable"), tgtTable = $("tgtTable");
  const srcTitle = $("srcTitle"), tgtTitle = $("tgtTitle"), srcScroll = $("srcScroll"), tgtScroll = $("tgtScroll");
  const loadDataBtn = $("loadDataBtn"), compareDataBtn = $("compareDataBtn");
  const dataBox = $("data"), dataChips = $("dataChips"), dataTable = $("dataTable"), dataFilter = $("dataFilter");
  let allModels = [];
  let reconnecting = false;
  let dataRows = [];        // current rows shown in the data table
  let dataMode = "single";  // "single" (one org) or "compare"

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
  const actionBtns = [fetchBtn, deployBtn, compareBtn, loadDataBtn, compareDataBtn];
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
        setStatus("err", "No Salesforce orgs are authorized. Run: sf org login web");
        return;
      }
      const opts = orgs.map(o => `<option value="${o.alias}">${o.alias}${o.username ? "  —  " + o.username : ""}</option>`).join("");
      orgSel.innerHTML = opts;
      targetSel.innerHTML = opts;
      if (orgs.length > 1) targetSel.selectedIndex = 1;  // default target != source
      loadModels();
    } catch (e) {
      if (e && e.conn) { handleDisconnect(); return; }
      orgSel.innerHTML = '<option value="">(could not load orgs)</option>';
      setStatus("err", "Could not load orgs: " + e);
    }
  }

  function renderModels() {
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
    if (!orgSel.value) { setStatus("err", "Please choose an org first."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    if (!content.value.trim()) { setStatus("err", "There is no CML content to deploy."); return; }
    if (!confirm(`Deploy "${model.value.trim()}" to org "${orgSel.value}"?\n\nThis overwrites the latest version's Constraint Model.`)) return;
    busy(deployBtn, "Deploying…");
    setStatus("info", "Deploying " + model.value.trim() + " to " + orgSel.value + "…");
    try {
      const data = await postJSON("/api/deploy", { org: orgSel.value, model: model.value.trim(), content: content.value });
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
        renderDiff(data.source, data.target);
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
    if (s === "unmappable") return '<span class="badge b-unmappable">No Global_Key__c</span>';
    return "";
  }

  function dataRowHtml(r, withStatus) {
    const code = r.refCode ? ` <span class="gkey">(${esc(r.refCode)})</span>` : "";
    const gk = r.mappable ? `<span class="gkey">${esc(r.gkey)}</span>`
                          : '<span class="badge b-unmappable">missing</span>';
    return "<tr>"
      + (withStatus ? `<td>${statusBadge(r._status)}</td>` : "")
      + `<td><span class="badge b-type">${esc(shortType(r.refType))}</span></td>`
      + `<td>${esc(r.tagType)}</td>`
      + `<td>${esc(r.tag)}</td>`
      + `<td>${esc(r.refName)}${code}</td>`
      + `<td>${gk}</td>`
      + "</tr>";
  }

  function renderDataTable() {
    const withStatus = dataMode === "compare";
    const f = dataFilter.value;
    const visible = dataRows.filter(r => {
      if (f === "all") return true;
      if (f === "match")   return r._status === "match";
      if (f === "add")     return r._status === "add" || r._status === "ready";
      if (f === "extra")   return r._status === "extra";
      if (f === "blocked") return r._status === "blocked" || r._status === "unmappable";
      return true;
    });
    const head = "<thead><tr>"
      + (withStatus ? "<th>Status</th>" : "")
      + "<th>Ref type</th><th>Tag type</th><th>Tag</th><th>Reference record</th><th>Global_Key__c</th>"
      + "</tr></thead>";
    const body = visible.length
      ? visible.map(r => dataRowHtml(r, withStatus)).join("")
      : `<tr><td colspan="${withStatus ? 6 : 5}" style="text-align:center;color:var(--muted);padding:18px;">No rows for this filter.</td></tr>`;
    dataTable.innerHTML = head + "<tbody>" + body + "</tbody>";
  }
  dataFilter.onchange = renderDataTable;

  loadDataBtn.onclick = async () => {
    if (!orgSel.value) { setStatus("err", "Please choose a source org first."); return; }
    if (!model.value.trim()) { setStatus("err", "Please choose a CML from the list."); model.focus(); return; }
    busy(loadDataBtn, "Loading…");
    setStatus("info", `Loading constraint data for "${model.value}" from ${orgSel.value}…`);
    try {
      const data = await postJSON("/api/data", { org: orgSel.value, model: model.value.trim() });
      if (data.ok) {
        dataMode = "single";
        dataRows = data.rows.map(r => ({ ...r, _status: "" }));
        renderDataChips({ single: true, total: data.stats.total, unmappable: data.stats.unmappable, org: orgSel.value });
        renderDataTable();
        dataBox.classList.add("show");
        dataBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const warn = data.stats.unmappable ? ` (${data.stats.unmappable} without Global_Key__c)` : "";
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
      const data = await postJSON("/api/data/compare", { sourceOrg: orgSel.value, targetOrg: targetSel.value, model: model.value.trim() });
      if (data.ok) {
        dataMode = "compare";
        const rows = [];
        data.matched.forEach(r => rows.push({ ...r, _status: "match" }));
        data.sourceOnly.forEach(r => rows.push({ ...r, _status: r.deployStatus === "ready" ? "add" : r.deployStatus }));
        data.targetOnly.forEach(r => rows.push({ ...r, _status: "extra" }));
        dataRows = rows;
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

  function renderDataChips(o) {
    if (o.single) {
      dataChips.innerHTML =
        `<span class="chip ok">${o.total} rows · ${o.org}</span>`
        + (o.unmappable ? `<span class="chip warn">${o.unmappable} without Global_Key__c</span>` : "");
      return;
    }
    const s = o.s;
    dataChips.innerHTML =
      `<span class="chip">Source ${o.src.org}: ${o.src.total}</span>`
      + `<span class="chip">Target ${o.tgt.org}: ${o.tgt.total}</span>`
      + `<span class="chip ok">${s.matched} matched</span>`
      + `<span class="chip add">${s.sourceOnly} only in source</span>`
      + `<span class="chip extra">${s.targetOnly} only in target</span>`
      + (s.blocked ? `<span class="chip warn">${s.blocked} blocked (ref missing in target)</span>` : "")
      + (s.unmappable ? `<span class="chip warn">${s.unmappable} unmappable</span>` : "");
  }

  loadOrgs();
</script>
</body>
</html>"""


def main():
    if "--print-build" in sys.argv:
        print(BUILD)
        return

    if not os.path.exists(FETCH_SCRIPT) or not os.path.exists(DEPLOY_SCRIPT):
        print("ERROR: Could not find fetch/deploy scripts next to this file.", file=sys.stderr)
        sys.exit(1)

    open_browser = "--no-browser" not in sys.argv
    port = DEFAULT_PORT
    url = f"http://127.0.0.1:{port}/"

    # If a CML Tool is already running here, don't start a second one.
    if is_our_server(port):
        print(f"CML Tool is already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return

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
