"""Low-level Salesforce CLI authentication and REST transport for CML Tool.

This module contains no HTTP routes or CML business rules. Callers inject small
dependencies where useful so the main application keeps its stable patch/test
surface while transport behavior can be tested independently.
"""

import json
import os
import shutil
import ssl
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


CMD_TIMEOUT = 120
API_VERSION = "v66.0"


def _nvm_bin_dirs():
    dirs = []
    root = os.path.expanduser("~/.nvm/versions/node")
    if os.path.isdir(root):
        try:
            for entry in sorted(os.listdir(root), reverse=True):
                path = os.path.join(root, entry, "bin")
                if os.path.isdir(path):
                    dirs.append(path)
        except OSError:
            pass
    return dirs


def _fnm_bin_dirs():
    dirs = []
    for root in (
            os.path.expanduser("~/.local/share/fnm/node-versions"),
            os.path.expanduser("~/.fnm/node-versions")):
        if os.path.isdir(root):
            try:
                for entry in sorted(os.listdir(root), reverse=True):
                    path = os.path.join(root, entry, "installation", "bin")
                    if os.path.isdir(path):
                        dirs.append(path)
            except OSError:
                pass
    return dirs


def _volta_bin_dir():
    path = os.path.expanduser("~/.volta/bin")
    return [path] if os.path.isdir(path) else []


def extra_paths():
    static = [
        "/usr/local/bin",
        "/opt/homebrew/bin",
        os.path.expanduser("~/.npm-global/bin"),
        os.path.expanduser("~/.nvm/current/bin"),
        "/usr/local/sfdx/bin",
        "/opt/homebrew/lib/node_modules/@salesforce/cli/bin",
    ]
    return static + _nvm_bin_dirs() + _fnm_bin_dirs() + _volta_bin_dir()


def environment():
    """Return an environment with Finder-safe Salesforce CLI discovery."""
    env = os.environ.copy()
    parts = env.get("PATH", "").split(os.pathsep)
    for path in extra_paths():
        if path and os.path.isdir(path) and path not in parts:
            parts.append(path)
    env["PATH"] = os.pathsep.join(parts)
    return env


def find_sf():
    """Locate the Salesforce CLI executable."""
    found = shutil.which("sf", path=environment()["PATH"])
    if found:
        return found
    for path in extra_paths():
        candidate = os.path.join(path, "sf")
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def run_process(args, repo_root, **kwargs):
    """Run a process with the same UTF-8 and timeout policy as the app."""
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=repo_root,
        env=environment(),
        timeout=CMD_TIMEOUT,
        **kwargs,
    )


def sf_run(args, repo_root, locate=find_sf, **kwargs):
    """Run Salesforce CLI cross-platform, including Windows .cmd launchers."""
    executable = locate() or "sf"
    argv = [executable] + list(args)
    if os.name == "nt" and executable.lower().endswith((".cmd", ".bat")):
        argv = [os.environ.get("COMSPEC", "cmd.exe"), "/c"] + argv
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=repo_root,
        env=environment(),
        timeout=CMD_TIMEOUT,
        **kwargs,
    )


def looks_like_token(token):
    """Return whether CLI output resembles a non-redacted Salesforce token."""
    return bool(token) and "!" in token and "REDACTED" not in token


def fetch_access_token(org, sf_runner):
    """Read a token through the dedicated non-redacted CLI command."""
    try:
        process = sf_runner([
            "org", "auth", "show-access-token",
            "--target-org", org, "--json", "--no-prompt",
        ])
    except Exception as exc:  # noqa: BLE001
        return None, f"Could not read the access token for '{org}': {exc}"
    try:
        data = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return None, (
            process.stderr or "Could not read the access token.").strip()
    if data.get("status") != 0:
        return None, (
            data.get("message") or "Could not read the access token.")
    token = (data.get("result") or {}).get("accessToken")
    if not looks_like_token(token):
        return None, None
    return token, None


def is_auth_error(message):
    message = message or ""
    return (
        "INVALID_SESSION_ID" in message
        or "INVALID_AUTH_HEADER" in message
        or "INVALID_LOGIN" in message
        or "MISSING_OAUTH_TOKEN" in message
        or "401" in message
        or "Session expired" in message
    )


def auth_help(org, raw):
    """Return actionable re-authentication guidance."""
    return (
        f"Salesforce rejected the saved login for '{org}'.\n"
        f"Details: {raw}\n\n"
        "This almost always means the org's saved session has expired or was "
        "revoked. Re-authenticate in a terminal, then click “Reload list”:\n"
        f"    sf org login web --target-org {org}\n\n"
        "If it still fails, log out and back in, then reload:\n"
        f"    sf org logout --no-prompt --target-org {org}\n"
        f"    sf org login web --alias {org}"
    )


def org_credentials(
        org, refresh, cache, sf_runner, token_fetcher, auth_helper=auth_help):
    """Return ``(token, instance_url, error)`` with process-local caching."""
    if not refresh and org in cache:
        token, url = cache[org]
        return token, url, None
    try:
        process = sf_runner([
            "org", "display", "--target-org", org, "--json",
        ])
    except Exception as exc:  # noqa: BLE001
        return None, None, f"Could not read org credentials: {exc}"
    try:
        data = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return None, None, (
            process.stderr or "Could not read org credentials.").strip()
    if data.get("status") != 0:
        return None, None, (
            data.get("message") or "Could not read org credentials.")
    result = data.get("result", {})
    token, url = result.get("accessToken"), result.get("instanceUrl")
    if not looks_like_token(token):
        token, token_error = token_fetcher(org)
        if token_error:
            return None, None, token_error
    if not token or not url:
        return None, None, auth_helper(
            org, "No usable access token was returned.")
    cache[org] = (token, url)
    return token, url, None


def format_rest_error(code, parsed, body):
    """Convert Salesforce REST error envelopes into readable text."""
    if isinstance(parsed, list) and parsed:
        parts = []
        for item in parsed:
            if isinstance(item, dict):
                error_code = item.get("errorCode", "")
                message = item.get("message", "")
                parts.append(f"{error_code}: {message}".strip(": ").strip())
        if parts:
            return "; ".join(parts)
    if isinstance(parsed, dict) and parsed.get("message"):
        return (
            f"{parsed.get('errorCode', '')}: {parsed['message']}"
            .strip(": ").strip())
    return f"HTTP {code}: {(body or '')[:300]}"


def rest(method, url, token, payload=None):
    """Make one JSON REST request and return ``(parsed, error)``."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(
                request, context=ssl.create_default_context(),
                timeout=CMD_TIMEOUT) as response:
            body = response.read().decode("utf-8")
            return (json.loads(body) if body.strip() else {}), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        return parsed, format_rest_error(exc.code, parsed, body)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def http_get_text(url, token):
    """GET a raw resource such as an exact ConstraintModel blob."""
    request = urllib.request.Request(url, method="GET")
    request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(
                request, context=ssl.create_default_context(),
                timeout=CMD_TIMEOUT) as response:
            return response.read().decode("utf-8"), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None
        return None, format_rest_error(exc.code, parsed, body)
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def esco_capability_preflight(
        org, retried, cache, ttl, api_version, credentials, rest_call,
        auth_error=is_auth_error, auth_helper=auth_help):
    """Verify ESCO query capability, caching only definitive outcomes."""
    token, instance, error = credentials(org)
    if error:
        return error
    cache_key = (org, instance)
    cached = cache.get(cache_key)
    if cached and cached[1] > time.monotonic():
        return cached[0]

    url = (
        f"{instance}/services/data/{api_version}/sobjects/"
        "ExpressionSetConstraintObj/describe")
    description, error = rest_call("GET", url, token)
    if error and auth_error(error) and not retried:
        credentials(org, refresh=True)
        return esco_capability_preflight(
            org, True, cache, ttl, api_version, credentials, rest_call,
            auth_error, auth_helper)
    if error and auth_error(error):
        return auth_helper(org, error)

    unavailable = error and any(marker in error for marker in (
        "INVALID_TYPE", "NOT_FOUND", "404",
        "sObject type 'ExpressionSetConstraintObj' is not supported",
    ))
    if unavailable or (
            not error and not (description or {}).get("queryable")):
        detail = (
            error
            or "The object describe response reports queryable=false.")
        message = (
            f"ExpressionSetConstraintObj is unavailable or not queryable in "
            f"'{org}' at API {api_version}. Revenue Cloud/Product Configurator "
            "must be enabled and the selected user must be able to query this "
            "object before association compare, export, deploy, or restore "
            f"operations can run.\nDetails: {detail}"
        )
        cache[cache_key] = (message, time.monotonic() + ttl)
        return message
    if error:
        return (
            f"Could not verify ExpressionSetConstraintObj capability in '{org}' "
            f"at API {api_version} because Salesforce returned an indeterminate "
            "or transient service error. This failure was not cached; "
            f"retry the operation.\nDetails: {error}"
        )
    cache[cache_key] = (None, time.monotonic() + ttl)
    return None


def query_json(
        org, soql, retried, api_version, credentials, rest_call,
        cancel_check, auth_error=is_auth_error, auth_helper=auth_help):
    """Run paginated SOQL with cancellation and one authentication refresh."""
    cancel_check()
    token, instance, error = credentials(org)
    if error:
        return None, error
    records = []
    url = (
        f"{instance}/services/data/{api_version}/query?q="
        + urllib.parse.quote(soql))
    guard = 0
    while url and guard < 2000:
        cancel_check()
        guard += 1
        data, error = rest_call("GET", url, token)
        cancel_check()
        if error:
            if auth_error(error) and not retried:
                credentials(org, refresh=True)
                return query_json(
                    org, soql, True, api_version, credentials, rest_call,
                    cancel_check, auth_error, auth_helper)
            if auth_error(error):
                return None, auth_helper(org, error)
            return None, error
        records.extend(data.get("records", []) or [])
        next_url = data.get("nextRecordsUrl")
        url = instance + next_url if next_url else None
    return records, None


def collections_insert(token, instance, records, api_version, rest_call):
    """Insert only ExpressionSetConstraintObj rows in chunks of 200."""
    disallowed = [
        record for record in records
        if (record.get("attributes") or {}).get("type")
        != "ExpressionSetConstraintObj"
    ]
    if disallowed:
        return [{
            "success": False,
            "id": None,
            "error": "Write blocked by safety policy: only "
                     "ExpressionSetConstraintObj can be inserted.",
        } for _ in records]
    url = f"{instance}/services/data/{api_version}/composite/sobjects"
    output = []
    for index in range(0, len(records), 200):
        chunk = records[index:index + 200]
        response, error = rest_call(
            "POST", url, token, {"allOrNone": False, "records": chunk})
        if error:
            output.extend({
                "success": False, "id": None, "error": error,
            } for _ in chunk)
            continue
        for result in response:
            errors = result.get("errors") or []
            message = "; ".join(
                item.get("message", "") for item in errors) if errors else None
            output.append({
                "success": bool(result.get("success")),
                "id": result.get("id"),
                "error": message,
            })
    return output


def collections_delete(token, instance, ids, api_version, rest_call):
    """Delete only ExpressionSetConstraintObj IDs in chunks of 200."""
    if any(not str(record_id).startswith("1JE") for record_id in ids):
        return [{
            "success": False,
            "id": record_id,
            "error": "Delete blocked by safety policy: only "
                     "ExpressionSetConstraintObj can be deleted.",
        } for record_id in ids]
    output = []
    for index in range(0, len(ids), 200):
        chunk = ids[index:index + 200]
        url = (
            f"{instance}/services/data/{api_version}/composite/sobjects"
            f"?ids={','.join(chunk)}&allOrNone=false")
        response, error = rest_call("DELETE", url, token, None)
        if error:
            output.extend({
                "success": False, "id": record_id, "error": error,
            } for record_id in chunk)
            continue
        for result in response:
            errors = result.get("errors") or []
            message = "; ".join(
                item.get("message", "") for item in errors) if errors else None
            output.append({
                "success": bool(result.get("success")),
                "id": result.get("id"),
                "error": message,
            })
    return output
