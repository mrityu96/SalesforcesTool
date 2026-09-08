"""Local-only HTTP handler and route dispatch for CML Tool."""

import json
import logging
import mimetypes
import os
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler


def make_handler(resolve):
    """Build a handler whose application dependencies resolve at request time.

    Dynamic lookup preserves the main module's stable monkey-patch surface for
    tests and guarded CLI integrations while keeping HTTP concerns isolated.
    """

    class CmlHttpHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _send(self, code, body, content_type="application/json"):
            if isinstance(body, (dict, list)):
                body = json.dumps(body)
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; "
                f"style-src 'self' 'nonce-{resolve('CSRF_TOKEN')}'; "
                "img-src 'self'; font-src 'self'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                "form-action 'none'; object-src 'none'")
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
                    self._send(
                        403, {"ok": False, "log": "Untrusted Host header."})
                    return
                request_path = urllib.parse.urlparse(self.path).path
                if request_path == "/":
                    page = resolve("PAGE").replace(
                        "__CML_CSRF_TOKEN__", resolve("CSRF_TOKEN"))
                    self._send(200, page, "text/html; charset=utf-8")
                elif request_path.startswith("/assets/"):
                    relative = urllib.parse.unquote(
                        request_path[len("/assets/"):])
                    asset_root = os.path.realpath(resolve("ASSETS_DIR"))
                    asset_path = os.path.realpath(
                        os.path.join(asset_root, relative))
                    try:
                        inside_root = (
                            os.path.commonpath((asset_root, asset_path))
                            == asset_root)
                    except (ValueError, OSError):
                        inside_root = False
                    if (not relative or "\x00" in relative or
                            not inside_root or not os.path.isfile(asset_path)):
                        self._send(404, {"error": "not found"})
                        return
                    content_type = (
                        mimetypes.guess_type(asset_path)[0]
                        or "application/octet-stream")
                    if asset_path.endswith(".js"):
                        content_type = "text/javascript"
                    with open(asset_path, "rb") as asset:
                        self._send(
                            200, asset.read(),
                            content_type + (
                                "; charset=utf-8"
                                if content_type.startswith(("text/", "application/json"))
                                else ""))
                elif request_path in resolve("STATIC_ASSETS"):
                    filename, content_type = resolve("STATIC_ASSETS")[
                        request_path]
                    with open(
                            resolve("_static_asset_path")(filename),
                            "rb") as asset:
                        self._send(200, asset.read(), content_type)
                elif request_path == "/api/ping":
                    self._send(200, {
                        "app": resolve("APP_ID"),
                        "version": resolve("APP_VERSION"),
                        "build": resolve("BUILD"),
                        "localRequestToken": resolve("CSRF_TOKEN"),
                    })
                elif request_path == "/api/orgs":
                    self._send(200, resolve("list_orgs")())
                elif self.path.startswith("/api/models"):
                    query = urllib.parse.urlparse(self.path).query
                    org = urllib.parse.parse_qs(query).get("org", [""])[0]
                    self._send(200, resolve("list_models")(org))
                elif self.path.startswith("/api/key-fields"):
                    query = urllib.parse.parse_qs(
                        urllib.parse.urlparse(self.path).query)
                    self._send(200, resolve("list_key_fields")(
                        query.get("sourceOrg", [""])[0],
                        query.get("targetOrg", [""])[0]))
                elif self.path.startswith("/api/backups"):
                    query = urllib.parse.parse_qs(
                        urllib.parse.urlparse(self.path).query)
                    self._send(200, resolve("list_cml_backups")(
                        query.get("org", [""])[0],
                        query.get("model", [""])[0],
                        query.get("versionId", [""])[0]))
                else:
                    self._send(404, {"error": "not found"})
            except Exception as exc:  # noqa: BLE001
                logging.exception("Unexpected CML Tool GET failure: %s", exc)
                self._send(500, {
                    "ok": False, "log": "Unexpected server error."})

        def do_POST(self):
            try:
                if not self._trusted_host():
                    self._send(
                        403, {"ok": False, "log": "Untrusted Host header."})
                    return
                if not self._trusted_origin():
                    self._send(
                        403, {"ok": False, "log": "Untrusted Origin header."})
                    return
                if self.headers.get("X-CML-CSRF") != resolve("CSRF_TOKEN"):
                    self._send(403, {"ok": False, "log": (
                        "Request rejected by local security protection. "
                        "Reload the tool.")})
                    return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                except (TypeError, ValueError):
                    self._send(
                        400, {"ok": False, "log": "Invalid Content-Length."})
                    return
                if length < 0:
                    self._send(
                        400, {"ok": False, "log": "Invalid Content-Length."})
                    return
                if length > 10 * 1024 * 1024:
                    self._send(
                        413, {"ok": False, "log": "Request is too large."})
                    return
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    self._send(
                        200, {"ok": False, "log": "Invalid request body."})
                    return
                self._dispatch_post(body)
            except Exception as exc:  # noqa: BLE001
                logging.exception("Unexpected CML Tool POST failure: %s", exc)
                self._send(500, {
                    "ok": False, "log": "Unexpected server error."})

        def _dispatch_post(self, body):
            resolve("_clear_rest_diagnostic")()
            if self.path == "/api/debug":
                if os.environ.get("CML_DEBUG") != "1":
                    self._send(404, {"error": "not found"})
                    return
                result = resolve("sf_debug_info")()
            elif self.path == "/api/fetch":
                result = resolve("fetch_cml")(
                    body.get("org"), body.get("model"), body.get("versionId"))
            elif self.path == "/api/quit":
                self._send(200, {"ok": True, "bye": True})
                threading.Thread(
                    target=lambda: (
                        time.sleep(0.3), self.server.shutdown()),
                    daemon=True).start()
                return
            elif self.path == "/api/deploy":
                result = resolve("deploy_cml")(
                    body.get("org"), body.get("model"),
                    body.get("targetVersionId"), body.get("content"),
                    body.get("confirmTarget"))
            elif self.path == "/api/rollback":
                result = resolve("rollback_cml")(
                    body.get("org"), body.get("model"),
                    body.get("targetVersionId"), body.get("backupId"),
                    body.get("confirmTarget"))
            elif self.path == "/api/readiness":
                result = resolve("target_version_readiness")(
                    body.get("org"), body.get("model"),
                    body.get("targetVersionId"))
            elif self.path == "/api/compare":
                result = resolve("compare_cml")(
                    body.get("sourceOrg"), body.get("targetOrg"),
                    body.get("model"), body.get("sourceVersionId"),
                    body.get("targetVersionId"))
            elif self.path == "/api/semantic/compare":
                result = resolve("compare_cml_semantics")(
                    body.get("sourceContent") or "",
                    body.get("targetContent") or "")
            elif self.path == "/api/data":
                result = resolve("export_constraints")(
                    body.get("org"), body.get("model"), body.get("versionId"),
                    body.get("keyField") or "")
            elif self.path == "/api/data/compare":
                result = resolve("_run_cancellable_constraint_compare")(body)
            elif self.path == "/api/operation/cancel":
                result = resolve("_cancel_operation")(body.get("operationId"))
            elif self.path == "/api/data/deploy":
                result = resolve("deploy_constraints")(
                    body.get("sourceOrg"), body.get("targetOrg"),
                    body.get("model"), body.get("sourceVersionId"),
                    body.get("targetVersionId"), body.get("adds") or [],
                    body.get("deletes") or [],
                    body.get("keyField") or "",
                    body.get("confirmTarget"))
            elif self.path == "/api/data/restore":
                result = resolve("restore_association_archive")(
                    body.get("targetOrg"), body.get("model"),
                    body.get("targetVersionId"), body.get("archiveId"),
                    body.get("confirmTarget"))
            else:
                self._send(404, {"error": "not found"})
                return
            failed = (
                isinstance(result, dict)
                and (result.get("ok") is False
                     or result.get("outcome") in ("failed", "partial")
                     or any(
                         not row.get("success")
                         for key in ("created", "deleted", "restored")
                         for row in (result.get(key) or [])
                         if isinstance(row, dict))))
            diagnostic = resolve("_consume_rest_diagnostic")()
            if failed and diagnostic and "diagnostic" not in result:
                result["diagnostic"] = diagnostic
            self._send(200, result)

    return CmlHttpHandler
