"""Guarded exact-version CML lifecycle workflows.

The application core supplies a dynamic name resolver so every dependency is
looked up in ``cml_tool`` at call time. This preserves its public patch surface
for tests, HTTP routes, and the guarded CLI adapter.
"""

import base64
import os
import time


class Lifecycle:
    def __init__(self, resolve):
        self._resolve = resolve

    def _get(self, name):
        return self._resolve(name)

    def _runtime_activity_by_definition_version(self, org, version_ids):
        """Return observed ExpressionSetVersion activity for definition versions."""
        active_by_version = {}
        observed_versions = set()
        for start in range(0, len(version_ids), 200):
            chunk = version_ids[start:start + 200]
            quoted = ",".join(
                "'" + self._get("_soql_str")(version_id) + "'"
                for version_id in chunk)
            records, err = self._get("_query_json")(
                org,
                "SELECT ExpressionSetDefinitionVerId, IsActive "
                "FROM ExpressionSetVersion "
                f"WHERE ExpressionSetDefinitionVerId IN ({quoted})")
            if err:
                return {}, set(), err
            for record in records:
                version_id = record.get("ExpressionSetDefinitionVerId")
                if version_id not in chunk:
                    continue
                observed_versions.add(version_id)
                active_by_version[version_id] = (
                    active_by_version.get(version_id, False)
                    or record.get("IsActive") is True)
        return active_by_version, observed_versions, None

    def list_models(self, org):
        """Return exact versions with effective runtime-aware CML status."""
        if not org:
            return {"error": "No org selected."}
        if not self._get("find_sf")():
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
        records, err = self._get("_query_json")(org, query)
        if err:
            return {"error": err}

        version_ids = [
            record.get("Id") for record in records if record.get("Id")]
        runtime_active, runtime_observed, runtime_err = (
            self._runtime_activity_by_definition_version(org, version_ids)
            if version_ids else ({}, set(), None))
        models = []
        for rec in records:
            defn = rec.get("ExpressionSetDefinition") or {}
            name = defn.get("DeveloperName")
            if not name or not rec.get("Id"):
                continue
            version_id = rec.get("Id")
            definition_status = rec.get("Status")
            if version_id in runtime_observed:
                status = (
                    "Active" if runtime_active.get(version_id) else "Inactive")
                status_basis = "runtime"
                runtime_status = status
            else:
                status = definition_status
                status_basis = "definition"
                runtime_status = (
                    "Unknown" if runtime_err else "Not instantiated")
            models.append({
                "versionId": version_id,
                "name": name,
                "label": defn.get("MasterLabel") or name,
                "version": rec.get("VersionNumber"),
                "status": status,
                "statusBasis": status_basis,
                "definitionStatus": definition_status,
                "runtimeStatus": runtime_status,
            })
        status_rank = {"active": 0, "inactive": 1}
        models.sort(key=lambda item: (
            status_rank.get(str(item.get("status") or "").strip().lower(), 2),
            str(item.get("name") or "").lower(),
            -(float(item.get("version")) if str(
                item.get("version") or "").replace(".", "", 1).isdigit() else -1),
            str(item.get("versionId") or ""),
        ))
        result = {"models": models}
        if runtime_err:
            result["runtimeStatusWarning"] = runtime_err
        return result

    def resolve_exact_version(self, org, model, version_id):
        """Verify an untrusted version Id belongs to the named model."""
        if not org or not model or not version_id:
            return None, (
                "Select an exact version for this operation; org, model name, and "
                "versionId are all required.")
        recs, err = self._get("_query_json")(
            org,
            "SELECT Id, VersionNumber, Status, "
            "ExpressionSetDefinition.DeveloperName, "
            "ExpressionSetDefinition.MasterLabel "
            "FROM ExpressionSetDefinitionVersion "
            "WHERE Id = '" + self._get("_soql_str")(version_id) + "' "
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

    def version_write_status(self, org, version_id, operation):
        """Fail closed unless the exact definition version is observed non-Active."""
        recs, err = self._get("_query_json")(
            org,
            "SELECT Id, Status FROM ExpressionSetDefinitionVersion WHERE Id = '"
            + self._get("_soql_str")(version_id) + "'")
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

    def download_cml(self, org, model, version_id, out_file):
        """Fetch one exact CML version over REST into ``out_file``."""
        if not self._get("find_sf")():
            return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                        "Install it with: npm install -g @salesforce/cli"}
        rec, err = self._get("resolve_exact_version")(org, model, version_id)
        if err:
            return {"ok": False, "log": err}
        version_id = rec["Id"]
        log = f"==> {rec.get('DeveloperName')} ({version_id}) — Status: {rec.get('Status')}"

        token, instance, cerr = self._get("_org_creds")(org)
        if cerr:
            return {"ok": False, "log": cerr}

        url = (f"{instance}/services/data/{self._get('API_VERSION')}/sobjects/"
               f"ExpressionSetDefinitionVersion/{version_id}/ConstraintModel")
        content, gerr = self._get("_http_get_text")(url, token)
        if gerr:
            if "404" in gerr or "NOT_FOUND" in gerr:
                content = ""
            else:
                return {"ok": False, "log": f"{log}\nCould not download CML:\n{gerr}"}

        os.makedirs(self._get("DOWNLOAD_DIR"), exist_ok=True)
        try:
            with open(out_file, "w", encoding="utf-8") as handle:
                handle.write(content or "")
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

    def fetch_cml(self, org, model, version_id):
        """Fetch a CML and return its content and logs."""
        if not org or not model or not version_id:
            return {"ok": False, "log": (
                "Select an exact version before fetching CML.")}
        safe = self._get("_safe")
        return self._get("_download_cml")(
            org, model, version_id,
            os.path.join(
                self._get("DOWNLOAD_DIR"),
                f"{safe(model)}__{safe(version_id)}.cml"))

    def cml_text(self, org, model, version_id):
        """Read one verified exact CML without writing a download file."""
        rec, err = self._get("resolve_exact_version")(org, model, version_id)
        if err:
            return None, err
        return self._get("_version_cml_text")(org, rec["Id"])

    def version_cml_text(self, org, version_id):
        """Read one exact version's blob, avoiding latest-version races."""
        token, instance, err = self._get("_org_creds")(org)
        if err:
            return None, err
        url = (f"{instance}/services/data/{self._get('API_VERSION')}/sobjects/"
               f"ExpressionSetDefinitionVersion/{version_id}/ConstraintModel")
        content, err = self._get("_http_get_text")(url, token)
        if err and ("404" in err or "NOT_FOUND" in err):
            return "", None
        return content, err

    def list_cml_backups(self, org, model, version_id):
        if not org or not model or not version_id:
            return {"ok": False, "log": (
                "Select an exact target version before listing backups.")}
        _, err = self._get("resolve_exact_version")(org, model, version_id)
        if err:
            return {"ok": False, "log": err}
        backup_dir = self._get("BACKUP_DIR")
        if not os.path.isdir(backup_dir):
            return {"ok": True, "backups": []}
        backups = []
        for name in sorted(os.listdir(backup_dir), reverse=True):
            if not name.endswith(".json"):
                continue
            data, err = self._get("_read_json_artifact")(backup_dir, name)
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

    def compare_cml(self, source_org, target_org, model, source_version_id,
                    target_version_id):
        """Fetch the same CML from two orgs so the UI can diff them."""
        if (not source_org or not target_org or not model
                or not source_version_id or not target_version_id):
            return {"ok": False, "log": (
                "Select an exact source version and exact target version before "
                "comparing CML.")}
        safe = self._get("_safe")
        download_dir = self._get("DOWNLOAD_DIR")
        download = self._get("_download_cml")
        src = download(
            source_org, model, source_version_id,
            os.path.join(
                download_dir,
                f"{safe(model)}__{safe(source_org)}__{safe(source_version_id)}.cml"))
        tgt = download(
            target_org, model, target_version_id,
            os.path.join(
                download_dir,
                f"{safe(model)}__{safe(target_org)}__{safe(target_version_id)}.cml"))

        def norm(res, org, version_id):
            if res.get("ok") or res.get("empty"):
                return {"org": org, "content": res.get("content", ""),
                        "versionId": version_id, "file": res.get("file"),
                        "versionNumber": res.get("versionNumber"),
                        "versionStatus": res.get("versionStatus"),
                        "log": res.get("log", "")}
            return None

        source = norm(src, source_org, source_version_id)
        target = norm(tgt, target_org, target_version_id)
        if source is None:
            return {"ok": False, "log": f"Could not fetch from source '{source_org}':\n{src.get('log')}"}
        if target is None:
            return {"ok": False, "log": f"Could not fetch from target '{target_org}':\n{tgt.get('log')}"}
        try:
            semantic = self._get("compare_cml_semantics")(
                source.get("content", ""), target.get("content", ""))
        except Exception as exc:  # noqa: BLE001
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
            "ok": True, "model": model,
            "source": source, "target": target,
            "semantic": semantic,
        }

    def patch_cml_version(self, org, version_id, content):
        """PATCH one exact CML version. Backup/report policy belongs to callers."""
        _, status_err = self._get("_version_write_status")(
            org, version_id, "CML PATCH")
        if status_err:
            return status_err
        token, instance, err = self._get("_org_creds")(org)
        if err:
            return err
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        url = (f"{instance}/services/data/{self._get('API_VERSION')}/sobjects/"
               f"ExpressionSetDefinitionVersion/{version_id}")
        _, err = self._get("_rest")(
            "PATCH", url, token, {"ConstraintModel": encoded})
        if err and self._get("_is_auth_error")(err):
            token, instance, refresh_err = self._get("_org_creds")(
                org, refresh=True)
            if refresh_err:
                return refresh_err
            url = (f"{instance}/services/data/{self._get('API_VERSION')}/sobjects/"
                   f"ExpressionSetDefinitionVersion/{version_id}")
            _, err = self._get("_rest")(
                "PATCH", url, token, {"ConstraintModel": encoded})
            if err and self._get("_is_auth_error")(err):
                return self._get("_auth_help")(org, err)
        return err

    def verify_cml_version(self, org, version_id, expected, attempts=4):
        """Re-fetch after PATCH, allowing briefly eventual Salesforce blob reads."""
        saved, err = None, None
        for attempt in range(attempts):
            saved, err = self._get("_version_cml_text")(org, version_id)
            if not err and saved == expected:
                return True, saved, None
            if attempt + 1 < attempts:
                time.sleep(0.4 * (attempt + 1))
        return False, saved, err

    def deploy_cml_unlocked(self, org, model, version_id, content,
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
        if not self._get("find_sf")():
            return {"ok": False, "log": "The Salesforce CLI ('sf') was not found. "
                                        "Install it with: npm install -g @salesforce/cli"}
        rec, err = self._get("resolve_exact_version")(org, model, version_id)
        if err:
            return {"ok": False, "log": err}
        version_id = rec["Id"]
        observed_status, status_err = self._get("_version_write_status")(
            org, version_id, "CML deployment")
        if status_err:
            return {
                "ok": False, "outcome": "rejected",
                "versionId": version_id, "versionStatus": observed_status,
                "log": status_err,
            }
        rec["Status"] = observed_status
        current, read_err = self._get("_version_cml_text")(org, version_id)
        if read_err:
            return {"ok": False, "log": (
                "Deployment stopped because the target CML could not be backed up:\n"
                + read_err)}
        try:
            backup = self._get("_create_cml_backup")(
                org, model, rec, current, "before-cml-deploy")
        except OSError as exc:
            return {"ok": False, "log": (
                "Deployment stopped because the target backup could not be saved:\n"
                + str(exc))}

        perr = self._get("_patch_cml_version")(org, version_id, content)
        if perr:
            report, report_err = self._get("_try_deployment_report")(
                "cml-deploy", org, model, {
                    "success": False, "versionId": version_id,
                    "versionStatus": rec.get("Status"),
                    "runtimeValidated": False,
                    "backup": backup,
                    "requestedSha256": self._get("_sha256_text")(content),
                    "error": perr,
                })
            return {"ok": False, "backup": backup, "report": report,
                    "reportError": report_err, "log": (
                        f"Deploy failed for '{model}' ({version_id}, status "
                        f"{rec.get('Status')}) in '{org}':\n{perr}")}

        verified, saved, verify_err = self._get("_verify_cml_version")(
            org, version_id, content)
        automatic_rollback = None
        if not verified:
            rollback_err = self._get("_patch_cml_version")(
                org, version_id, current)
            rollback_verified, rollback_saved, rollback_verify_err = (
                (False, None, rollback_err) if rollback_err
                else self._get("_verify_cml_version")(
                    org, version_id, current))
            automatic_rollback = {
                "attempted": True, "verified": rollback_verified,
                "error": rollback_verify_err,
                "restoredSha256": (
                    self._get("_sha256_text")(rollback_saved)
                    if rollback_saved is not None else None),
            }
        report, report_err = self._get("_try_deployment_report")(
            "cml-deploy", org, model, {
                "success": verified, "versionId": version_id,
                "versionNumber": rec.get("VersionNumber"),
                "versionStatus": rec.get("Status"),
                "runtimeValidated": False,
                "backup": backup,
                "requestedSha256": self._get("_sha256_text")(content),
                "savedSha256": (
                    self._get("_sha256_text")(saved) if not verify_err else None),
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
            f"Verified persisted SHA-256: {self._get('_sha256_text')(content)}\n"
            "Save verification does not activate/compile the model or prove "
            "runtime behavior.")}

    def deploy_cml(self, org, model, version_id, content,
                   confirm_target=None):
        return self._get("_run_with_deployment_lock")(
            org, model, lambda: self._get("_deploy_cml_unlocked")(
                org, model, version_id, content, confirm_target))

    def rollback_cml_unlocked(self, org, model, version_id, backup_id,
                              confirm_target=None):
        if not version_id:
            return {"ok": False, "log": (
                "Select an exact target version before restoring a CML backup.")}
        if confirm_target != org:
            return {"ok": False, "log": (
                f"Production safety check failed. Type the target org alias exactly: {org}")}
        backup_dir = self._get("BACKUP_DIR")
        backup_data, err = self._get("_read_json_artifact")(
            backup_dir, backup_id)
        if err:
            return {"ok": False, "log": err}
        if (backup_data.get("kind") != "cml-backup"
                or backup_data.get("org") != org
                or backup_data.get("model") != model):
            return {"ok": False, "log": (
                "Backup does not belong to the selected target org and model.")}
        content = backup_data.get("content", "")
        if self._get("_sha256_text")(content) != backup_data.get("sha256"):
            return {"ok": False, "log": (
                "Rollback stopped because the backup integrity hash does not match "
                "its saved CML content.")}
        rec, err = self._get("resolve_exact_version")(
            org, model, version_id)
        if err:
            return {"ok": False, "log": err}
        if rec.get("Id") != backup_data.get("versionId"):
            return {"ok": False, "log": (
                "Rollback stopped because the backup belongs to another exact "
                "version. Select a backup for the selected target version.")}
        observed_status, status_err = self._get("_version_write_status")(
            org, rec["Id"], "CML rollback")
        if status_err:
            return {
                "ok": False, "outcome": "rejected",
                "versionId": rec["Id"], "versionStatus": observed_status,
                "log": status_err,
            }
        rec["Status"] = observed_status
        current, err = self._get("_version_cml_text")(org, rec["Id"])
        if err:
            return {"ok": False, "log": (
                "Rollback stopped because the current CML could not be backed up:\n" + err)}
        try:
            safety_backup = self._get("_create_cml_backup")(
                org, model, rec, current, "before-cml-rollback")
        except OSError as exc:
            return {"ok": False, "log": (
                "Rollback stopped because its safety backup could not be saved:\n"
                + str(exc))}
        patch_err = self._get("_patch_cml_version")(
            org, rec["Id"], content)
        if patch_err:
            verified, saved, verify_err = False, None, patch_err
        else:
            verified, saved, verify_err = self._get("_verify_cml_version")(
                org, rec["Id"], content)
        report, report_err = self._get("_try_deployment_report")(
            "cml-rollback", org, model, {
                "success": verified, "versionId": rec["Id"],
                "versionStatus": rec.get("Status"),
                "runtimeValidated": False,
                "restoredBackupId": backup_id,
                "safetyBackup": safety_backup,
                "restoredSha256": self._get("_sha256_text")(content),
                "savedSha256": (
                    self._get("_sha256_text")(saved) if not verify_err else None),
                "error": verify_err,
            })
        if not verified:
            return {"ok": False, "backup": safety_backup, "report": report,
                    "reportError": report_err,
                    "log": "Rollback failed verification:\n" + (
                        verify_err or "Content mismatch.")}
        return {"ok": True, "verified": True, "backup": safety_backup,
                "report": report, "reportError": report_err,
                "runtimeValidated": False,
                "versionId": rec["Id"],
                "versionNumber": rec.get("VersionNumber"),
                "versionStatus": rec.get("Status"),
                "content": content, "log": (
                    f"Rollback complete and verified for '{model}' in '{org}'.\n"
                    f"Restored SHA-256: {self._get('_sha256_text')(content)}\n"
                    "Persistence verification does not activate/compile the model "
                    "or prove runtime behavior.")}

    def rollback_cml(self, org, model, version_id, backup_id,
                     confirm_target=None):
        return self._get("_run_with_deployment_lock")(
            org, model, lambda: self._get("_rollback_cml_unlocked")(
                org, model, version_id, backup_id, confirm_target))

    def refresh_cml_validation(self, org, model, content, version_id=None):
        """Perform a tool-specific unchanged-CML save/verification refresh."""
        if not version_id:
            return {"ok": False, "log": (
                "Select an exact target version before refreshing CML validation.")}
        rec, err = self._get("resolve_exact_version")(
            org, model, version_id)
        if err:
            return {"ok": False, "log": err}
        observed_status, status_err = self._get("_version_write_status")(
            org, rec["Id"], "CML save/verification refresh")
        if status_err:
            return {
                "ok": False, "versionStatus": observed_status,
                "log": status_err,
            }
        staged_err = self._get("_patch_cml_version")(
            org, version_id, content + "\n")
        if staged_err:
            return {
                "ok": False,
                "log": "Could not stage the CML save/verification refresh:\n"
                       + staged_err,
            }
        restore_err = self._get("_patch_cml_version")(
            org, version_id, content)
        if restore_err:
            return {
                "ok": False,
                "versionStatus": observed_status,
                "log": "The tool-specific refresh staged a temporary save, but the original byte-exact "
                       "content could not be restored:\n"
                       + restore_err,
            }
        verified, _, verify_err = self._get("_verify_cml_version")(
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


def make_lifecycle(resolve):
    """Build lifecycle services around a dynamic application dependency resolver."""
    return Lifecycle(resolve)
