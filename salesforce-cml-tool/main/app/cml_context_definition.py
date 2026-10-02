"""Read-only Context Definition retrieval through the Salesforce Metadata API.

Uses the same CLI-sourced access token as the rest of the CML Tool and calls the
SOAP Metadata API directly (listMetadata, retrieve, checkRetrieveStatus). Nothing
here writes to an org.
"""

import base64
import io
import re
import shlex
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape


METADATA_TYPE = "ContextDefinition"
SOAP_TIMEOUT = 120
POLL_INTERVAL_SECONDS = 1.5
POLL_ATTEMPTS = 60
_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,254}$")
OBJECT_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,254}$")
_ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@+\-]{0,254}$")
_FILE_SUFFIXES = (".contextDefinition", ".contextDefinition-meta.xml")


class SoapFault(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}" if code else message)
        self.code = code or ""


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _children(elem, name):
    return [child for child in elem if _local(child.tag) == name]


def _child_text(elem, name):
    for child in elem:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def _find_all(root, name):
    return [elem for elem in root.iter() if _local(elem.tag) == name]


def _api_number(api_version):
    return str(api_version or "").lstrip("vV") or "66.0"


def _envelope(token, body):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:met="http://soap.sforce.com/2006/04/metadata">'
        "<env:Header><met:SessionHeader><met:sessionId>"
        f"{escape(token)}"
        "</met:sessionId></met:SessionHeader></env:Header>"
        f"<env:Body>{body}</env:Body></env:Envelope>"
    ).encode("utf-8")


def _parse_fault(root):
    for fault in _find_all(root, "Fault"):
        return SoapFault(
            _child_text(fault, "faultcode").split(":")[-1],
            _child_text(fault, "faultstring") or "Metadata API request failed.")
    return None


def soap_post(instance, api_version, token, body):
    """POST one Metadata API SOAP call and return the parsed ``<result>`` list."""
    url = f"{instance.rstrip('/')}/services/Soap/m/{_api_number(api_version)}"
    request = urllib.request.Request(
        url, data=_envelope(token, body), method="POST")
    request.add_header("Content-Type", "text/xml; charset=UTF-8")
    request.add_header("SOAPAction", '""')
    try:
        with urllib.request.urlopen(
                request, context=ssl.create_default_context(),
                timeout=SOAP_TIMEOUT) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            fault = _parse_fault(ET.fromstring(payload))
        except ET.ParseError:
            fault = None
        raise fault or SoapFault("", f"HTTP {exc.code} from the Metadata API.")
    root = ET.fromstring(payload)
    fault = _parse_fault(root)
    if fault:
        raise fault
    return _find_all(root, "result")


def _is_session_fault(exc, auth_error):
    return exc.code in ("INVALID_SESSION_ID", "INVALID_AUTH_HEADER") or auth_error(
        str(exc))


def _call(org, body, credentials, api_version, soap_call, auth_error,
          auth_helper):
    """Run one SOAP call, refreshing the cached login once on session errors."""
    for refresh in (False, True):
        token, instance, error = credentials(org, refresh=refresh)
        if error:
            return None, error
        try:
            return soap_call(instance, api_version, token, body), None
        except SoapFault as exc:
            if refresh or not _is_session_fault(exc, auth_error):
                if _is_session_fault(exc, auth_error):
                    return None, auth_helper(org, str(exc))
                return None, str(exc)
        except (urllib.error.URLError, OSError, ET.ParseError) as exc:
            return None, f"Could not reach the Metadata API for '{org}': {exc}"
    return None, auth_helper(org, "Session could not be refreshed.")


def list_context_definitions(
        org, credentials, api_version, soap_call=soap_post,
        auth_error=lambda message: False, auth_helper=lambda org, raw: raw):
    """List ContextDefinition metadata members in ``org`` (read-only)."""
    if not org:
        return {"ok": False, "log": "Select an org first."}
    api = _api_number(api_version)
    body = (
        "<met:listMetadata><met:queries>"
        f"<met:type>{METADATA_TYPE}</met:type>"
        f"</met:queries><met:asOfVersion>{api}</met:asOfVersion>"
        "</met:listMetadata>")
    results, error = _call(
        org, body, credentials, api_version, soap_call, auth_error, auth_helper)
    if error:
        return {"ok": False, "log": error}
    definitions = []
    for result in results:
        name = _child_text(result, "fullName")
        if not name:
            continue
        definitions.append({
            "name": name,
            "lastModifiedDate": _child_text(result, "lastModifiedDate"),
            "lastModifiedByName": _child_text(result, "lastModifiedByName"),
            "namespacePrefix": _child_text(result, "namespacePrefix"),
            "manageableState": _child_text(result, "manageableState"),
        })
    definitions.sort(key=lambda item: item["name"].lower())
    return {
        "ok": True,
        "org": org,
        "definitions": definitions,
        "log": (
            f"Found {len(definitions)} Context Definition(s) in '{org}'."
            if definitions else
            f"No retrievable Context Definitions were found in '{org}'."),
    }


def field_category(data_type):
    """Coarse kind of a FieldDefinition.DataType label such as 'Currency(16, 2)'."""
    label = (data_type or "").strip().lower()
    formula = re.match(r"formula\s*\((.+)\)$", label)
    if formula:
        label = formula.group(1).strip()
    for prefix, category in (
            ("checkbox", "boolean"), ("currency", "currency"), ("percent", "percent"),
            ("number", "number"), ("date/time", "datetime"), ("date", "date"),
            ("time", "time"), ("lookup", "reference"), ("master-detail", "reference"),
            ("hierarchy", "reference"), ("external lookup", "reference"),
            ("indirect lookup", "reference"), ("id", "reference"),
            ("picklist", "picklist"), ("multi-select picklist", "picklist"),
            ("text", "text"), ("long text", "text"), ("rich text", "text"),
            ("email", "text"), ("phone", "text"), ("url", "text"),
            ("auto number", "text")):
        if label.startswith(prefix):
            return category
    return ""


# Context attribute dataType -> field kinds Salesforce can hydrate it from.
# "string" and unknown kinds are not checked, to avoid false alarms.
_COMPATIBLE_CATEGORIES = {
    "boolean": {"boolean"},
    "currency": {"currency", "number", "percent"},
    "number": {"currency", "number", "percent"},
    "percent": {"currency", "number", "percent"},
    "date": {"date", "datetime"},
    "datetime": {"date", "datetime"},
    "lookup": {"reference", "text"},
    "reference": {"reference", "text"},
    "picklist": {"picklist", "text"},
}


# FieldDefinition lists a compound field (e.g. ShippingAddress, Location__c)
# but not its parts, which describe and hydration use (ShippingStreet, ...).
_ADDRESS_PARTS = (
    ("Street", "Text Area"), ("City", "Text"), ("State", "Text"), ("StateCode", "Picklist"),
    ("PostalCode", "Text"), ("Country", "Text"), ("CountryCode", "Picklist"),
    ("Latitude", "Number"), ("Longitude", "Number"), ("GeocodeAccuracy", "Picklist"))
_GEOLOCATION_PARTS = (("Latitude", "Number"), ("Longitude", "Number"))


def _compound_parts(row):
    name = row.get("QualifiedApiName") or ""
    label = (row.get("DataType") or "").strip().lower()
    if label.startswith("address") and name.lower().endswith("address"):
        prefix = name[:-len("Address")]
        return [(prefix + part, data_type) for part, data_type in _ADDRESS_PARTS]
    if label.startswith("geolocation") and name.lower().endswith("__c"):
        return [(f"{name[:-3]}__{part}__s", data_type)
                for part, data_type in _GEOLOCATION_PARTS]
    return []


def _field_index(rows):
    fields = {(row.get("QualifiedApiName") or "").lower(): row for row in rows}
    for row in rows:
        for part, data_type in _compound_parts(row):
            fields.setdefault(part.lower(), {"QualifiedApiName": part, "DataType": data_type})
    return fields


def evaluate_hydration_preflight(sources, fields_by_object, base_paths=()):
    """
    Check hydration chains against one org's FieldDefinition rows.
    fields_by_object maps object name -> list of {QualifiedApiName, DataType,
    RelationshipName}, or None when the object does not exist in the org.
    """
    base_paths = set(base_paths)
    problems, checked = [], 0
    lookup = {}
    for obj, rows in fields_by_object.items():
        if rows is None:
            lookup[obj.lower()] = None
            continue
        lookup[obj.lower()] = {
            "fields": _field_index(rows),
            "relationships": {
                (row.get("RelationshipName") or "").lower(): row
                for row in rows if row.get("RelationshipName")},
        }
    seen = set()
    for source in sources:
        key = (source["contextNode"], source["attribute"], source["path"])
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        chain = source["chain"]
        problem = None
        for index, (obj, field) in enumerate(chain):
            leaf = index == len(chain) - 1
            info = lookup.get(obj.lower(), "unchecked")
            if info == "unchecked":
                break
            if info is None:
                problem = ("missing-object", f"Object {obj} does not exist in this org.")
                break
            name = field.lower()
            row = info["fields"].get(name)
            if row is None and not leaf:
                row = info["relationships"].get(name) or (
                    info["fields"].get(name[:-3] + "__c") if name.endswith("__r") else None)
            if row is None:
                problem = ("missing-field", f"Field {obj}.{field} does not exist in this org.")
                break
            if leaf:
                attr_type = (source.get("dataType") or "").lower()
                allowed = _COMPATIBLE_CATEGORIES.get(attr_type)
                category = field_category(row.get("DataType"))
                if allowed and category and category not in allowed:
                    problem = ("type-mismatch", (
                        f"{obj}.{field} is {row.get('DataType')}, but the context attribute "
                        f"is declared as {attr_type}."))
        if problem:
            problems.append({
                "kind": problem[0],
                "detail": problem[1],
                "mapping": source["mapping"],
                "contextNode": source["contextNode"],
                "attribute": source["attribute"],
                "path": source["path"],
                "inBase": source["path"] in base_paths,
            })
    return {"checked": checked, "problems": problems}


def deploy_plan(name, target_org, api_version, base_origin=None,
                release_count=0, base_edited=False):
    """
    The files and sf CLI commands to deploy one built ContextDefinition.
    Only text is produced: the tool never runs these commands.
    """
    name = (name or "").strip()
    target_org = (target_org or "").strip()
    if not _NAME_PATTERN.match(name):
        return {"ok": False, "log": "The built Context Definition has no valid developerName."}
    if not _ALIAS_PATTERN.match(target_org):
        return {"ok": False, "log": "Choose the org you plan to deploy to."}
    api = _api_number(api_version)
    file_path = f"force-app/main/default/contextDefinitions/{name}.contextDefinition-meta.xml"
    manifest_path = "manifest/contextDefinition-package.xml"
    package_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Package xmlns="http://soap.sforce.com/2006/04/metadata">\n'
        "    <types>\n"
        f"        <members>{escape(name)}</members>\n"
        f"        <name>{METADATA_TYPE}</name>\n"
        "    </types>\n"
        f"    <version>{api}</version>\n"
        "</Package>\n")
    base = (
        f"sf project deploy start --manifest {manifest_path} "
        f"--target-org {shlex.quote(target_org)} --wait 30")
    warnings = []
    base_org = (base_origin or "").strip()
    if not base_org:
        warnings.append(
            "Base was pasted, so the tool cannot confirm it came from "
            f"{target_org}. Deploying replaces {target_org}'s definition with this file, "
            f"so anything only {target_org} has would be lost. Retrieve Base from "
            f"{target_org} and rebuild to be sure.")
    elif base_org != target_org:
        warnings.append(
            f"Base was retrieved from {base_org}, not {target_org}. This file is "
            f"{base_org}'s definition plus your selections; deploying it to {target_org} "
            f"replaces {target_org}'s definition and removes anything only {target_org} has. "
            f"Retrieve Base from {target_org} and rebuild instead.")
    if base_org and base_edited:
        warnings.append("Base was edited by hand after it was retrieved.")
    if release_count:
        warnings.append(
            f"{release_count} applied item(s) are Salesforce release content. Run the field "
            "check and the check-only deploy first; they fail if the org is on an older release.")
    return {
        "ok": True,
        "name": name,
        "targetOrg": target_org,
        "filePath": file_path,
        "manifestPath": manifest_path,
        "packageXml": package_xml,
        "commands": {"checkOnly": base + " --dry-run", "deploy": base},
        "warnings": warnings,
    }


def _extract_context_definition(zip_b64, name):
    archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(zip_b64)))
    members = [
        member for member in archive.namelist()
        if member.endswith(_FILE_SUFFIXES)]
    exact = [
        member for member in members
        if member.rsplit("/", 1)[-1].split(".", 1)[0] == name]
    chosen = (exact or members or [None])[0]
    if chosen is None:
        return None, None
    return chosen.rsplit("/", 1)[-1], archive.read(chosen).decode("utf-8")


def retrieve_context_definition(
        org, name, credentials, api_version, soap_call=soap_post,
        auth_error=lambda message: False, auth_helper=lambda org, raw: raw,
        sleep=time.sleep, attempts=POLL_ATTEMPTS):
    """Retrieve the exact ``.contextDefinition`` XML for ``name`` (read-only)."""
    if not org:
        return {"ok": False, "log": "Select an org first."}
    name = (name or "").strip()
    if not _NAME_PATTERN.match(name):
        return {"ok": False, "log": "Choose a valid Context Definition name."}
    api = _api_number(api_version)
    body = (
        "<met:retrieve><met:retrieveRequest>"
        f"<met:apiVersion>{api}</met:apiVersion>"
        "<met:singlePackage>true</met:singlePackage>"
        "<met:unpackaged><met:types>"
        f"<met:members>{escape(name)}</met:members>"
        f"<met:name>{METADATA_TYPE}</met:name>"
        f"</met:types><met:version>{api}</met:version></met:unpackaged>"
        "</met:retrieveRequest></met:retrieve>")
    results, error = _call(
        org, body, credentials, api_version, soap_call, auth_error, auth_helper)
    if error:
        return {"ok": False, "log": error}
    process_id = _child_text(results[0], "id") if results else ""
    if not process_id:
        return {"ok": False, "log": "The Metadata API did not start a retrieve."}

    status_body = (
        "<met:checkRetrieveStatus>"
        f"<met:asyncProcessId>{escape(process_id)}</met:asyncProcessId>"
        "<met:includeZip>true</met:includeZip>"
        "</met:checkRetrieveStatus>")
    result = None
    for _ in range(max(1, attempts)):
        results, error = _call(
            org, status_body, credentials, api_version, soap_call,
            auth_error, auth_helper)
        if error:
            return {"ok": False, "log": error}
        result = results[0] if results else None
        if result is not None and _child_text(result, "done") == "true":
            break
        sleep(POLL_INTERVAL_SECONDS)
    else:
        return {"ok": False, "log": (
            f"Retrieving '{name}' from '{org}' is still running after "
            f"{int(attempts * POLL_INTERVAL_SECONDS)}s. Try again shortly.")}

    status = _child_text(result, "status")
    problems = [
        _child_text(message, "problem")
        for message in _children(result, "messages")
        if _child_text(message, "problem")]
    if status == "Failed":
        detail = _child_text(result, "errorMessage") or "; ".join(problems)
        return {"ok": False, "log": (
            f"Retrieve of '{name}' from '{org}' failed: "
            f"{detail or 'no details returned.'}")}
    zip_b64 = _child_text(result, "zipFile")
    file_name, content = (
        _extract_context_definition(zip_b64, name) if zip_b64 else (None, None))
    if content is None:
        detail = "; ".join(problems) or "the package did not contain it."
        return {"ok": False, "log": (
            f"Context Definition '{name}' was not returned by '{org}': {detail}")}
    return {
        "ok": True,
        "org": org,
        "name": name,
        "fileName": file_name,
        "content": content,
        "warnings": problems,
        "retrievedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "log": f"Retrieved Context Definition '{name}' from '{org}' (read-only).",
    }
