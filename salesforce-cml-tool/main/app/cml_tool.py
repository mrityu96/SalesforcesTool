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

import hashlib
import importlib.util
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer

# App code and packaged assets live in main/. Local-only artifacts stay under
# the sibling development/runtime/ folder so production commits remain clean.
APP_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(APP_DIR)
PROJECT_ROOT = os.path.dirname(REPO_ROOT)
RUNTIME_ROOT = os.environ.get(
    "CML_RUNTIME_ROOT",
    os.path.join(PROJECT_ROOT, "development", "runtime"))
ANALYSIS_MODULE_PATH = os.path.join(APP_DIR, "cml_analysis.py")
PAGE_MODULE_PATH = os.path.join(APP_DIR, "cml_tool_page.py")
SALESFORCE_MODULE_PATH = os.path.join(APP_DIR, "cml_salesforce.py")
HTTP_MODULE_PATH = os.path.join(APP_DIR, "cml_http.py")
ARTIFACT_MODULE_PATH = os.path.join(APP_DIR, "cml_artifacts.py")
LIFECYCLE_MODULE_PATH = os.path.join(APP_DIR, "cml_lifecycle.py")
CONSTRAINTS_MODULE_PATH = os.path.join(APP_DIR, "cml_constraints.py")
SCRIPTS_DIR = os.path.join(APP_DIR, "utilities")
DOWNLOAD_DIR = os.path.join(RUNTIME_ROOT, "cml-files")
BACKUP_DIR = os.path.join(RUNTIME_ROOT, "cml-backups")
REPORT_DIR = os.path.join(RUNTIME_ROOT, "deployment-reports")
ARCHIVE_DIR = os.path.join(RUNTIME_ROOT, "association-archives")
LOG_DIR = os.path.join(RUNTIME_ROOT, "logs")
DATA_DEPLOY_AUDIT_FILE = os.path.join(
    LOG_DIR, "data-deploy-history.jsonl")
CSRF_TOKEN = secrets.token_urlsafe(32)
FIELD_PROBE_TTL = 300
ESCO_CAPABILITY_TTL = 300
_DEPLOY_LOCKS = {}
_DEPLOY_LOCKS_GUARD = threading.Lock()
_AUDIT_LOG_LOCK = threading.Lock()
_ACTIVE_OPERATIONS = {}
_PENDING_CANCELLATIONS = {}
_ACTIVE_OPERATIONS_LOCK = threading.Lock()
_OPERATION_CONTEXT = threading.local()


class OperationCancelled(Exception):
    """Raised when the user cancels a registered long-running read operation."""


def _valid_operation_id(operation_id):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{8,128}", operation_id or ""))


def _begin_operation(operation_id):
    if not _valid_operation_id(operation_id):
        return None, "A valid operation ID is required."
    with _ACTIVE_OPERATIONS_LOCK:
        now = time.monotonic()
        for stale_id, expiry in list(_PENDING_CANCELLATIONS.items()):
            if expiry <= now:
                _PENDING_CANCELLATIONS.pop(stale_id, None)
        if operation_id in _ACTIVE_OPERATIONS:
            return None, "That operation is already running."
        cancel_event = threading.Event()
        if _PENDING_CANCELLATIONS.pop(operation_id, None):
            cancel_event.set()
        _ACTIVE_OPERATIONS[operation_id] = cancel_event
    return cancel_event, None


def _cancel_operation(operation_id):
    if not _valid_operation_id(operation_id):
        return {"ok": False, "cancelled": False,
                "log": "A valid operation ID is required."}
    with _ACTIVE_OPERATIONS_LOCK:
        cancel_event = _ACTIVE_OPERATIONS.get(operation_id)
        if cancel_event:
            cancel_event.set()
        else:
            # A very fast click can reach the cancellation route just before
            # the comparison route registers. Keep a short-lived tombstone so
            # that operation starts in the cancelled state instead of running.
            _PENDING_CANCELLATIONS[operation_id] = time.monotonic() + 60
    return {
        "ok": True,
        "cancelled": True,
        "log": "Cancellation requested.",
    }


def _finish_operation(operation_id):
    with _ACTIVE_OPERATIONS_LOCK:
        _ACTIVE_OPERATIONS.pop(operation_id, None)
        _PENDING_CANCELLATIONS.pop(operation_id, None)


def _check_operation_cancelled():
    cancel_event = getattr(_OPERATION_CONTEXT, "cancel_event", None)
    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled("Comparison stopped by the user.")


def _load_sibling_module(module_name, path):
    """Load a module beside this file without relying on sys.path."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load sibling module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

_SALESFORCE = _load_sibling_module(
    "_cml_salesforce", SALESFORCE_MODULE_PATH)
_ARTIFACTS = _load_sibling_module(
    "_cml_artifacts", ARTIFACT_MODULE_PATH)
_LIFECYCLE_MODULE = _load_sibling_module(
    "_cml_lifecycle", LIFECYCLE_MODULE_PATH)
_CONSTRAINTS_MODULE = _load_sibling_module(
    "_cml_constraints", CONSTRAINTS_MODULE_PATH)


def _resolve_lifecycle_dependency(name):
    return globals()[name]


def _resolve_constraints_dependency(name):
    return globals()[name]


_LIFECYCLE = _LIFECYCLE_MODULE.make_lifecycle(
    _resolve_lifecycle_dependency)
_CONSTRAINTS = _CONSTRAINTS_MODULE.make_constraints(
    _resolve_constraints_dependency)

def _nvm_bin_dirs() -> list:
    return _SALESFORCE._nvm_bin_dirs()


def _fnm_bin_dirs() -> list:
    return _SALESFORCE._fnm_bin_dirs()


def _volta_bin_dir() -> list:
    return _SALESFORCE._volta_bin_dir()


def _extra_paths() -> list:
    return _SALESFORCE.extra_paths()


CMD_TIMEOUT = _SALESFORCE.CMD_TIMEOUT
API_VERSION = _SALESFORCE.API_VERSION
PRC_IDENTITY_VERSION = 2
_CREDS_CACHE = {}


def _env():
    return _SALESFORCE.environment()


def find_sf():
    return _SALESFORCE.find_sf()


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
    return _SALESFORCE.run_process(args, REPO_ROOT, **kwargs)


def _sf_run(args, **kwargs):
    return _SALESFORCE.sf_run(
        args, REPO_ROOT, locate=find_sf, **kwargs)


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
    return _LIFECYCLE.list_models(org)


def resolve_exact_version(org, model, version_id):
    return _LIFECYCLE.resolve_exact_version(org, model, version_id)


def _exact_expression_set(org, model, version_id):
    return _CONSTRAINTS._exact_expression_set(org, model, version_id)

def _expression_set_write_status(org, expression_set_id, operation, definition_version_id=None):
    return _CONSTRAINTS._expression_set_write_status(org, expression_set_id, operation, definition_version_id)

def _version_write_status(org, version_id, operation):
    return _LIFECYCLE.version_write_status(org, version_id, operation)


def _download_cml(org, model, version_id, out_file):
    return _LIFECYCLE.download_cml(org, model, version_id, out_file)


def fetch_cml(org, model, version_id):
    return _LIFECYCLE.fetch_cml(org, model, version_id)


def _cml_text(org, model, version_id):
    return _LIFECYCLE.cml_text(org, model, version_id)


def _version_cml_text(org, version_id):
    return _LIFECYCLE.version_cml_text(org, version_id)


def _strip_cml_comments(text):
    return _CONSTRAINTS._strip_cml_comments(text)

def _cml_used_tags(org, model, version_id):
    return _CONSTRAINTS._cml_used_tags(org, model, version_id)

def _row_used_by_cml(row, used_tags):
    return _CONSTRAINTS._row_used_by_cml(row, used_tags)

def _safe(name):
    return _ARTIFACTS.safe_filename(name)


def _utc_now():
    return _ARTIFACTS.utc_now()


def _artifact_stamp():
    return _ARTIFACTS.artifact_stamp()


def _sha256_text(content):
    return _ARTIFACTS.sha256_text(content)


def _freeze_json_value(value):
    return _ARTIFACTS.freeze_json_value(value)


def _write_json_artifact(directory, prefix, payload):
    return _ARTIFACTS.write_json_artifact(directory, prefix, payload)


def _read_json_artifact(directory, artifact_id):
    return _ARTIFACTS.read_json_artifact(directory, artifact_id)


def _deployment_report(action, org, model, details):
    return _write_json_artifact(
        REPORT_DIR, f"{action}__{org}__{model}", {
            "kind": "deployment-report", "action": action,
            "targetOrg": org, "model": model, **details,
        })


def _append_data_deploy_audit(entry):
    return _ARTIFACTS.append_jsonl_audit(
        LOG_DIR, DATA_DEPLOY_AUDIT_FILE, entry, _AUDIT_LOG_LOCK)


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
    return _LIFECYCLE.list_cml_backups(org, model, version_id)


def compare_cml(source_org, target_org, model, source_version_id,
                target_version_id):
    return _LIFECYCLE.compare_cml(
        source_org, target_org, model, source_version_id, target_version_id)


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
    return _CONSTRAINTS._valid_field(name)

def _field_exists(org, sobject, field):
    return _CONSTRAINTS._field_exists(org, sobject, field)

def _is_auth_error(msg):
    return _SALESFORCE.is_auth_error(msg)


def _auth_help(org, raw):
    return _SALESFORCE.auth_help(org, raw)


def _esco_capability_preflight(org, _retried=False):
    return _CONSTRAINTS._esco_capability_preflight(org, _retried)

def _query_json(org, soql, _retried=False):
    return _SALESFORCE.query_json(
        org, soql, _retried, API_VERSION, _org_creds, _rest,
        _check_operation_cancelled, _is_auth_error, _auth_help)


def _constraint_key(tag_type, tag, ref_type, gkey):
    return _CONSTRAINTS._constraint_key(tag_type, tag, ref_type, gkey)

def _build_typeof(org, key_field):
    return _CONSTRAINTS._build_typeof(org, key_field)

def export_constraints(org, model, version_id, key_field=DEFAULT_KEY_FIELD):
    return _CONSTRAINTS.export_constraints(org, model, version_id, key_field)

def _flag_duplicates(rows, expression_set_id=None):
    return _CONSTRAINTS._flag_duplicates(rows, expression_set_id)

def _flag_duplicates_for_selected_cml(rows, expression_set_id, used_tags):
    return _CONSTRAINTS._flag_duplicates_for_selected_cml(rows, expression_set_id, used_tags)

def _target_key_candidates(target_org, needed, key_field):
    return _CONSTRAINTS._target_key_candidates(target_org, needed, key_field)

def _portable_child_field(source_org, target_org, sobject, preferred):
    return _CONSTRAINTS._portable_child_field(source_org, target_org, sobject, preferred)

def _records_by_parent(org, sobject, parent_field, parent_ids, fields):
    return _CONSTRAINTS._records_by_parent(org, sobject, parent_field, parent_ids, fields)

def _records_by_keys(org, sobject, key_field, keys, fields):
    return _CONSTRAINTS._records_by_keys(org, sobject, key_field, keys, fields)

def _classification_dependency_audit(source_org, target_org, source_rows, target_rows, key_field):
    return _CONSTRAINTS._classification_dependency_audit(source_org, target_org, source_rows, target_rows, key_field)

_PRC_STABLE_FIELDS = (
    "Quantity", "Sequence", "DoesBundlePriceIncludeChild",
    "QuantityScaleMethod", "MaxQuantity", "MinQuantity",
    "IsComponentRequired", "IsQuantityEditable", "IsDefaultComponent",
    "QuoteVisibility",
)


def _canonical_identity_scalar(value):
    return _CONSTRAINTS._canonical_identity_scalar(value)

def _prc_identity_from_detail(detail):
    return _CONSTRAINTS._prc_identity_from_detail(detail)

def _prc_identity(parent_key, child_kind, child_key, relationship_type, **discriminators):
    return _CONSTRAINTS._prc_identity(parent_key, child_kind, child_key, relationship_type, **discriminators)

def _prc_select_fields(org, kf):
    return _CONSTRAINTS._prc_select_fields(org, kf)

def _prc_detail_from_record(record, kf):
    return _CONSTRAINTS._prc_detail_from_record(record, kf)

def _prc_details(org, prc_ref_ids, kf):
    return _CONSTRAINTS._prc_details(org, prc_ref_ids, kf)

def _target_prc_by_identity(target_org, source_details, kf):
    return _CONSTRAINTS._target_prc_by_identity(target_org, source_details, kf)

def compare_constraints(source_org, target_org, model, source_version_id, target_version_id, key_field=DEFAULT_KEY_FIELD):
    return _CONSTRAINTS.compare_constraints(source_org, target_org, model, source_version_id, target_version_id, key_field)

def _looks_like_token(token):
    return _SALESFORCE.looks_like_token(token)


def _fetch_access_token(org):
    return _SALESFORCE.fetch_access_token(org, _sf_run)


def _org_creds(org, refresh=False):
    return _SALESFORCE.org_credentials(
        org, refresh, _CREDS_CACHE, _sf_run, _fetch_access_token, _auth_help)


def _fmt_rest_error(code, parsed, body):
    return _SALESFORCE.format_rest_error(code, parsed, body)


def _rest(method, url, token, payload=None):
    return _SALESFORCE.rest(method, url, token, payload)


def _http_get_text(url, token):
    return _SALESFORCE.http_get_text(url, token)


def _collections_insert(token, instance, records):
    return _SALESFORCE.collections_insert(
        token, instance, records, API_VERSION, _rest)


def _collections_delete(token, instance, ids):
    return _SALESFORCE.collections_delete(
        token, instance, ids, API_VERSION, _rest)


def _constraint_ids_in_expression_set(org, expression_set_id, ids):
    return _CONSTRAINTS._constraint_ids_in_expression_set(org, expression_set_id, ids)

def _archive_associations(org, model, version_id, expression_set_id, key_field, rows, expression_set_status=None):
    return _CONSTRAINTS._archive_associations(org, model, version_id, expression_set_id, key_field, rows, expression_set_status)

def _archived_prc_detail(row):
    return _CONSTRAINTS._archived_prc_detail(row)

def _restore_association_archive_unlocked(org, model, version_id, archive_id, confirm_target=None):
    return _CONSTRAINTS._restore_association_archive_unlocked(org, model, version_id, archive_id, confirm_target)

def restore_association_archive(org, model, version_id, archive_id, confirm_target=None):
    return _CONSTRAINTS.restore_association_archive(org, model, version_id, archive_id, confirm_target)

def _deploy_constraints_unlocked(source_org, target_org, model, source_version_id, target_version_id, adds, deletes, key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    return _CONSTRAINTS._deploy_constraints_unlocked(source_org, target_org, model, source_version_id, target_version_id, adds, deletes, key_field, confirm_target)

def deploy_constraints(source_org, target_org, model, source_version_id, target_version_id, adds, deletes, key_field=DEFAULT_KEY_FIELD, confirm_target=None):
    return _CONSTRAINTS.deploy_constraints(source_org, target_org, model, source_version_id, target_version_id, adds, deletes, key_field, confirm_target)

def _patch_cml_version(org, version_id, content):
    return _LIFECYCLE.patch_cml_version(org, version_id, content)


def _verify_cml_version(org, version_id, expected, attempts=4):
    return _LIFECYCLE.verify_cml_version(
        org, version_id, expected, attempts)


def _try_deployment_report(action, org, model, details):
    try:
        return _deployment_report(action, org, model, details), None
    except OSError as exc:
        return None, f"Could not save deployment report: {exc}"


def _deploy_cml_unlocked(org, model, version_id, content,
                         confirm_target=None):
    return _LIFECYCLE.deploy_cml_unlocked(
        org, model, version_id, content, confirm_target)


def deploy_cml(org, model, version_id, content, confirm_target=None):
    return _LIFECYCLE.deploy_cml(
        org, model, version_id, content, confirm_target)


def _rollback_cml_unlocked(org, model, version_id, backup_id,
                           confirm_target=None):
    return _LIFECYCLE.rollback_cml_unlocked(
        org, model, version_id, backup_id, confirm_target)


def rollback_cml(org, model, version_id, backup_id,
                 confirm_target=None):
    return _LIFECYCLE.rollback_cml(
        org, model, version_id, backup_id, confirm_target)


def _refresh_cml_validation(org, model, content, version_id=None):
    return _LIFECYCLE.refresh_cml_validation(
        org, model, content, version_id)


_ANALYSIS = _load_sibling_module(
    "_cml_analysis", ANALYSIS_MODULE_PATH)
_CmlToken = _ANALYSIS._CmlToken
_CmlParser = _ANALYSIS._CmlParser
_tokenize_cml = _ANALYSIS._tokenize_cml
compare_cml_semantics = _ANALYSIS.compare_cml_semantics


def _run_cancellable_constraint_compare(body):
    operation_id = body.get("operationId") or (
        "server_" + secrets.token_urlsafe(18))
    cancel_event, error = _begin_operation(operation_id)
    if error:
        return {"ok": False, "log": error}
    _OPERATION_CONTEXT.cancel_event = cancel_event
    try:
        return compare_constraints(
            body.get("sourceOrg"), body.get("targetOrg"), body.get("model"),
            body.get("sourceVersionId"), body.get("targetVersionId"),
            body.get("keyField") or DEFAULT_KEY_FIELD)
    except OperationCancelled as exc:
        return {
            "ok": False,
            "cancelled": True,
            "operationId": operation_id,
            "log": str(exc),
        }
    finally:
        _OPERATION_CONTEXT.cancel_event = None
        _finish_operation(operation_id)


_HTTP = _load_sibling_module("_cml_http", HTTP_MODULE_PATH)


def _resolve_http_dependency(name):
    return globals()[name]


Handler = _HTTP.make_handler(_resolve_http_dependency)


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
    """Short hash of server, analysis, and page code for automatic restarts."""
    try:
        digest = hashlib.sha1()
        for path in (
                os.path.abspath(__file__),
                ANALYSIS_MODULE_PATH,
                SALESFORCE_MODULE_PATH,
                HTTP_MODULE_PATH,
                ARTIFACT_MODULE_PATH,
                LIFECYCLE_MODULE_PATH,
                CONSTRAINTS_MODULE_PATH,
                PAGE_MODULE_PATH):
            with open(path, "rb") as source:
                digest.update(source.read())
        return digest.hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return "dev"


BUILD = _build_id()


def _load_page():
    """Load PAGE from the sibling module without relying on sys.path."""
    return _load_sibling_module("_cml_tool_page", PAGE_MODULE_PATH).PAGE


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




PAGE = _load_page()


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
