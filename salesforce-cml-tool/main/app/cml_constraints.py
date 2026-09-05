"""Constraint-data export, comparison, archive, and guarded deployment.

All application dependencies are resolved from ``cml_tool`` at call time.
This deliberately preserves its public patch surface for tests, HTTP routes,
and CLI callers while keeping Salesforce transport and artifact primitives in
their dedicated sibling modules.
"""

import json
import re
import time

DEFAULT_KEY_FIELD = "Global_Key__c"
_resolve = None


def _get(name):
    if _resolve is None:
        raise RuntimeError("Constraint services have not been initialized.")
    return _resolve(name)


def _dynamic(name):
    """Return a call-through that honors cml_tool patches at invocation time."""
    def call(*args, **kwargs):
        return _get(name)(*args, **kwargs)
    return call


resolve_exact_version = _dynamic("resolve_exact_version")
_query_json = _dynamic("_query_json")
_soql_str = _dynamic("_soql_str")
_cml_text = _dynamic("_cml_text")
find_sf = _dynamic("find_sf")
_org_creds = _dynamic("_org_creds")
_rest = _dynamic("_rest")
_is_auth_error = _dynamic("_is_auth_error")
_auth_help = _dynamic("_auth_help")
_check_operation_cancelled = _dynamic("_check_operation_cancelled")
_freeze_json_value = _dynamic("_freeze_json_value")
_read_json_artifact = _dynamic("_read_json_artifact")
_collections_insert = _dynamic("_collections_insert")
_collections_delete = _dynamic("_collections_delete")
_try_deployment_report = _dynamic("_try_deployment_report")
_run_with_deployment_lock = _dynamic("_run_with_deployment_lock")
_version_write_status = _dynamic("_version_write_status")
_version_cml_text = _dynamic("_version_cml_text")
_create_cml_backup = _dynamic("_create_cml_backup")
_refresh_cml_validation = _dynamic("_refresh_cml_validation")
_append_data_deploy_audit = _dynamic("_append_data_deploy_audit")
_write_json_artifact = _dynamic("_write_json_artifact")


def _exact_expression_set(*args, **kwargs):
    return _get('_exact_expression_set')(*args, **kwargs)

def _expression_set_write_status(*args, **kwargs):
    return _get('_expression_set_write_status')(*args, **kwargs)

def _strip_cml_comments(*args, **kwargs):
    return _get('_strip_cml_comments')(*args, **kwargs)

def _cml_used_tags(*args, **kwargs):
    return _get('_cml_used_tags')(*args, **kwargs)

def _row_used_by_cml(*args, **kwargs):
    return _get('_row_used_by_cml')(*args, **kwargs)

def _valid_field(*args, **kwargs):
    return _get('_valid_field')(*args, **kwargs)

def _field_exists(*args, **kwargs):
    return _get('_field_exists')(*args, **kwargs)

def _esco_capability_preflight(*args, **kwargs):
    return _get('_esco_capability_preflight')(*args, **kwargs)

def _constraint_key(*args, **kwargs):
    return _get('_constraint_key')(*args, **kwargs)

def _build_typeof(*args, **kwargs):
    return _get('_build_typeof')(*args, **kwargs)

def export_constraints(*args, **kwargs):
    return _get('export_constraints')(*args, **kwargs)

def _flag_duplicates(*args, **kwargs):
    return _get('_flag_duplicates')(*args, **kwargs)

def _flag_duplicates_for_selected_cml(*args, **kwargs):
    return _get('_flag_duplicates_for_selected_cml')(*args, **kwargs)

def _target_key_candidates(*args, **kwargs):
    return _get('_target_key_candidates')(*args, **kwargs)

def _portable_child_field(*args, **kwargs):
    return _get('_portable_child_field')(*args, **kwargs)

def _records_by_parent(*args, **kwargs):
    return _get('_records_by_parent')(*args, **kwargs)

def _records_by_keys(*args, **kwargs):
    return _get('_records_by_keys')(*args, **kwargs)

def _classification_dependency_audit(*args, **kwargs):
    return _get('_classification_dependency_audit')(*args, **kwargs)

def _canonical_identity_scalar(*args, **kwargs):
    return _get('_canonical_identity_scalar')(*args, **kwargs)

def _prc_identity_from_detail(*args, **kwargs):
    return _get('_prc_identity_from_detail')(*args, **kwargs)

def _prc_identity(*args, **kwargs):
    return _get('_prc_identity')(*args, **kwargs)

def _prc_select_fields(*args, **kwargs):
    return _get('_prc_select_fields')(*args, **kwargs)

def _prc_detail_from_record(*args, **kwargs):
    return _get('_prc_detail_from_record')(*args, **kwargs)

def _prc_details(*args, **kwargs):
    return _get('_prc_details')(*args, **kwargs)

def _target_prc_by_identity(*args, **kwargs):
    return _get('_target_prc_by_identity')(*args, **kwargs)

def compare_constraints(*args, **kwargs):
    return _get('compare_constraints')(*args, **kwargs)

def _constraint_ids_in_expression_set(*args, **kwargs):
    return _get('_constraint_ids_in_expression_set')(*args, **kwargs)

def _archive_associations(*args, **kwargs):
    return _get('_archive_associations')(*args, **kwargs)

def _archived_prc_detail(*args, **kwargs):
    return _get('_archived_prc_detail')(*args, **kwargs)

def _restore_association_archive_unlocked(*args, **kwargs):
    return _get('_restore_association_archive_unlocked')(*args, **kwargs)

def restore_association_archive(*args, **kwargs):
    return _get('restore_association_archive')(*args, **kwargs)

def _deploy_constraints_unlocked(*args, **kwargs):
    return _get('_deploy_constraints_unlocked')(*args, **kwargs)

def deploy_constraints(*args, **kwargs):
    return _get('deploy_constraints')(*args, **kwargs)


def _impl__exact_expression_set(org, model, version_id):
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

def _impl__expression_set_write_status(
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

def _impl__strip_cml_comments(text):
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

def _impl__cml_used_tags(org, model, version_id):
    """Return the Type and Port tags referenced by one exact CML version."""
    text, err = _cml_text(org, model, version_id)
    if err:
        return None, err
    clean = _strip_cml_comments(text or "")
    return {
        "Type": set(re.findall(r"\btype\s+([A-Za-z_][A-Za-z0-9_]*)", clean)),
        "Port": set(re.findall(r"\brelation\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", clean)),
    }, None

def _impl__row_used_by_cml(row, used_tags):
    """Unknown tag kinds remain included; only recognized Type/Port rows filter."""
    if not used_tags:
        return True
    tag_type = row.get("tagType")
    return tag_type not in used_tags or row.get("tag") in used_tags[tag_type]

def _impl__valid_field(name):
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

def _impl__field_exists(org, sobject, field):
    """Cheap, cached probe: does `sobject` expose `field`? (SELECT ... LIMIT 1).

    Lets us include the chosen key only on the reference objects that actually
    have it, instead of failing the whole TYPEOF query when one object lacks it.
    """
    ck = (org, sobject, field)
    cached = _get("_FIELD_PROBE").get(ck)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    _, err = _query_json(org, f"SELECT {field} FROM {sobject} LIMIT 1")
    if err:
        invalid = any(marker in err for marker in (
            "INVALID_FIELD", "No such column", "INVALID_TYPE",
            "INVALID_FIELD_FOR_INSERT"))
        if invalid:
            _get("_FIELD_PROBE")[ck] = (False, time.monotonic() + _get("FIELD_PROBE_TTL"))
        return False
    _get("_FIELD_PROBE")[ck] = (True, time.monotonic() + _get("FIELD_PROBE_TTL"))
    return True

def _impl__esco_capability_preflight(org, _retried=False):
    return _get("_SALESFORCE").esco_capability_preflight(
        org, _retried, _get("_ESCO_CAPABILITY"), _get("ESCO_CAPABILITY_TTL"), _get("API_VERSION"),
        _org_creds, _rest, _is_auth_error, _auth_help)

def _impl__constraint_key(tag_type, tag, ref_type, gkey):
    """Org-portable identity for one constraint row."""
    return "\u241f".join([tag_type or "", tag or "", ref_type or "",
                          gkey or ""])

def _impl__build_typeof(org, key_field):
    """Build the TYPEOF clause, including `key_field` only on the reference
    objects that actually have it. Returns (clause, {refType: has_field})."""
    field_on = {}
    whens = []
    for t in _get("REF_TYPES"):
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

def _impl_export_constraints(org, model, version_id,
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
            row["prcIdentityVersion"] = _get("PRC_IDENTITY_VERSION")
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

def _impl__flag_duplicates(rows, expression_set_id=None):
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

def _impl__flag_duplicates_for_selected_cml(
        rows, expression_set_id, used_tags):
    """Flag only associations used by the exact CML selected by the user."""
    for row in rows:
        row["dups"] = []
    selected_rows = [
        row for row in rows
        if _row_used_by_cml(row, used_tags)
    ]
    return _flag_duplicates(selected_rows, expression_set_id)

def _impl__target_key_candidates(target_org, needed, key_field):
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

def _impl__portable_child_field(source_org, target_org, sobject, preferred):
    """Choose a readable cross-org key for catalog dependency auditing."""
    for field in (preferred, DEFAULT_KEY_FIELD, "ProductCode", "Name"):
        if (field and _valid_field(field)
                and _field_exists(source_org, sobject, field)
                and _field_exists(target_org, sobject, field)):
            return field
    return None

def _impl__records_by_parent(org, sobject, parent_field, parent_ids, fields):
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

def _impl__records_by_keys(org, sobject, key_field, keys, fields):
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

def _impl__classification_dependency_audit(source_org, target_org, source_rows,
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

def _impl__canonical_identity_scalar(value):
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

def _impl__prc_identity_from_detail(detail):
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
        "version": _get("PRC_IDENTITY_VERSION"),
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
            for field in _get("_PRC_STABLE_FIELDS")
        },
    }
    return json.dumps(
        canonical, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False), None

def _impl__prc_identity(parent_key, child_kind, child_key, relationship_type,
                  **discriminators):
    """Compatibility wrapper for callers/tests constructing a detailed PRC."""
    detail = {
        "parentKey": parent_key, "childKind": child_kind,
        "childKey": child_key, "relationshipTypeName": relationship_type,
        **discriminators,
    }
    return _prc_identity_from_detail(detail)[0]

def _impl__prc_select_fields(org, kf):
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
    for field in _get("_PRC_STABLE_FIELDS"):
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

def _impl__prc_detail_from_record(record, kf):
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
    for field in _get("_PRC_STABLE_FIELDS"):
        detail[field] = record.get(field)
    detail["identity"], detail["identityError"] = (
        _prc_identity_from_detail(detail))
    detail["prcIdentityVersion"] = _get("PRC_IDENTITY_VERSION")
    return detail

def _impl__prc_details(org, prc_ref_ids, kf):
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

def _impl__target_prc_by_identity(target_org, source_details, kf):
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

def _impl_compare_constraints(source_org, target_org, model, source_version_id,
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
    _check_operation_cancelled()
    for capability_org in (source_org, target_org):
        capability_err = _esco_capability_preflight(capability_org)
        _check_operation_cancelled()
        if capability_err:
            return {"ok": False, "log": capability_err}

    kf = _valid_field(key_field)
    if not kf:
        return {"ok": False, "log": (
            f"\u201c{key_field}\u201d is not a valid field API name. Use a plain "
            "field name like Global_Key__c, ProductCode, External_Id__c, or Name.")}

    src = export_constraints(source_org, model, source_version_id, kf)
    _check_operation_cancelled()
    if not src.get("ok"):
        return src
    tgt = export_constraints(target_org, model, target_version_id, kf)
    _check_operation_cancelled()
    if not tgt.get("ok"):
        return tgt

    source_tags, tags_err = _cml_used_tags(
        source_org, model, source_version_id)
    _check_operation_cancelled()
    if tags_err:
        return {"ok": False, "log": (
            f"Could not read the source CML in {source_org}, so association "
            f"deployment was stopped safely:\n{tags_err}")}
    target_tags, tags_err = _cml_used_tags(
        target_org, model, target_version_id)
    _check_operation_cancelled()
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
    _check_operation_cancelled()

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
    _check_operation_cancelled()

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
    _check_operation_cancelled()
    target_prcs = _target_prc_by_identity(
        target_org, list(src_prc_details.values()), kf)
    _check_operation_cancelled()

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

def _impl__constraint_ids_in_expression_set(org, expression_set_id, ids):
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

def _impl__archive_associations(org, model, version_id, expression_set_id,
                          key_field, rows, expression_set_status=None):
    return _write_json_artifact(
        _get("ARCHIVE_DIR"), f"{org}__{model}__deleted-associations", {
            "kind": "association-delete-archive",
            "targetOrg": org, "model": model, "versionId": version_id,
            "expressionSetId": expression_set_id, "keyField": key_field,
            "expressionSetStatus": expression_set_status,
            "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
            "rows": rows,
        })

def _impl__archived_prc_detail(row):
    """Rebuild v2 PRC identity evidence; reject weak legacy archives."""
    detail = row.get("prcDetail")
    if not isinstance(detail, dict):
        required = {
            "parentId", "parentKey", "childKind", "childId", "childKey",
            "relationshipTypeId", "relationshipTypeName",
            "groupId", "groupKey", "parentSellingModelId",
            "parentSellingModelKey", "parentSellingModelName",
            "childSellingModelId", "childSellingModelKey",
            "childSellingModelName", *_get("_PRC_STABLE_FIELDS"),
        }
        if not required.issubset(row):
            return None, (
                "Archive is incompatible with PRC identity v2: this legacy "
                "row lacks the detailed relationship discriminators required "
                "for an exact restore. Recreate the archive with this tool "
                "version; the old weak identity will not be used.")
        detail = {field: row.get(field) for field in required}
    missing_fields = [
        field for field in _get("_PRC_STABLE_FIELDS") if field not in detail
    ]
    if missing_fields:
        return None, (
            "Archive is incompatible with PRC identity v2: detailed PRC "
            "evidence is missing " + ", ".join(missing_fields) + ".")
    identity, identity_err = _prc_identity_from_detail(detail)
    if identity_err:
        return None, "Archived PRC is unmappable: " + identity_err
    return {**detail, "identity": identity,
            "prcIdentityVersion": _get("PRC_IDENTITY_VERSION")}, None

def _impl__restore_association_archive_unlocked(
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
    archive, err = _read_json_artifact(_get("ARCHIVE_DIR"), archive_id)
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
        row["prcIdentityVersion"] = _get("PRC_IDENTITY_VERSION")
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
                    "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
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
            "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
            "results": restored,
        })
    return {
        "ok": fail_count == 0, "target": org, "model": model,
        "versionId": version["Id"],
        "expressionSetId": current_expression_set_id,
        "expressionSetStatus": expression_set_status,
        "versionStatus": version.get("Status"),
        "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
        "restored": restored, "report": report, "reportError": report_err,
        "stats": {"restoreOk": success_count, "restoreFail": fail_count},
        "log": (
            f"Association recovery finished: {success_count} restored/already "
            f"present, {fail_count} failed."),
    }

def _impl_restore_association_archive(org, model, version_id, archive_id,
                                confirm_target=None):
    return _run_with_deployment_lock(
        org, model, lambda: _restore_association_archive_unlocked(
            org, model, version_id, archive_id, confirm_target))

def _impl__deploy_constraints_unlocked(
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
            "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
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
        "prcIdentityVersion": _get("PRC_IDENTITY_VERSION"),
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

def _impl_deploy_constraints(source_org, target_org, model, source_version_id,
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


class Constraints:
    """Facade over dynamically linked constraint-data implementations."""

    def __init__(self, resolve):
        global _resolve
        _resolve = resolve

    def __getattr__(self, name):
        implementation = globals().get("_impl_" + name)
        if implementation is None:
            raise AttributeError(name)
        return implementation


def make_constraints(resolve):
    """Build constraint services around a dynamic dependency resolver."""
    return Constraints(resolve)
