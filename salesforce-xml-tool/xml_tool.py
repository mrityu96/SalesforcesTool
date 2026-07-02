#!/usr/bin/env python3
"""
xml_tool.py — A tiny local web UI for Salesforce metadata XML comparison & merge.

The user picks an operation, pastes XML, and clicks a button:
    • Compare      — paste two XMLs, see a side-by-side diff + structural report
    • Merge        — paste a Base XML and a Modified XML, choose which is the
                     base, and get a single merged XML (with a one-click Copy)
    • Deduplicate  — paste a Permission Set XML and remove duplicate entries

Run it (or just double-click "Open XML Tool.command" on macOS):
    python3 xml_tool.py

It starts a local server on a stable port (127.0.0.1 only) and opens your
browser. Only the Python standard library is used — nothing to install.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
import sys
import threading
import webbrowser
from collections import Counter, OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.etree.ElementTree import Element, tostring
import xml.etree.ElementTree as ET

# ───────────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────────

NS = "http://soap.sforce.com/2006/04/metadata"
NS_PREFIX = f"{{{NS}}}"
ET.register_namespace("", NS)

# Child element(s) whose text values uniquely identify a repeating sibling.
# Covers both Permission Sets / Profiles and Context Definitions so the merge
# engine auto-adapts to whatever root it is given.
IDENTITY_KEYS: dict[str, list[str]] = {
    # ── Permission Set / Profile ──
    "applicationVisibilities": ["application"],
    "categoryGroupVisibilities": ["dataCategoryGroup"],
    "classAccesses": ["apexClass"],
    "customMetadataTypeAccesses": ["name"],
    "customPermissions": ["name"],
    "customSettingAccesses": ["name"],
    "externalCredentialPrincipalAccesses": ["externalCredentialPrincipal"],
    "externalDataSourceAccesses": ["externalDataSource"],
    "fieldPermissions": ["field"],
    "flowAccesses": ["flow"],
    "objectPermissions": ["object"],
    "pageAccesses": ["apexPage"],
    "profileActionOverrides": ["actionName"],
    "recordTypeVisibilities": ["recordType"],
    "tabSettings": ["tab"],
    "tabVisibilities": ["tab"],
    "userPermissions": ["name"],
    # ── Context Definition ──
    "contextMappings": ["title"],
    "contextNodes": ["title"],
    "contextAttributes": ["title"],
    "contextAttributeMappings": ["contextAttribute"],
    "contextNodeMappings": ["contextNode", "object"],
    "contextMappingIntents": ["mappingIntent"],
    "contextTags": ["title"],
    "contextDefinitionReferences": ["referenceContextDefinition"],
    "ctxAttrHydrationCtxs": ["contextQueryAttribute"],
    "contextAttrHydrationDetails": ["objectName", "queryAttribute"],
}

# Singleton containers that are deep-merged (recursed into) when both sides
# share the same identity. Everything else with an identity is merged by key.
DEEP_MERGE_TAGS: set[str] = {
    "ContextDefinition",
    "contextDefinitionVersions",
    "contextMappings",
    "contextNodeMappings",
    "contextNodes",
}

# Scalars inside <contextDefinitionVersions> that ALWAYS come from the BASE.
VERSION_METADATA_TAGS: set[str] = {"versionNumber", "startDate", "isActive"}

# Canonical ordering for Permission Set / Profile sections (matches the
# behaviour of dedup_permset.py for clean, stable output).
PERMSET_SECTION_ORDER = [
    "loginIpRanges", "description", "hasActivationRequired", "label", "license",
    "applicationVisibilities", "classAccesses", "customMetadataTypeAccesses",
    "customPermissions", "customSettingAccesses",
    "externalCredentialPrincipalAccesses", "externalDataSourceAccesses",
    "fieldPermissions", "flowAccesses", "objectPermissions", "pageAccesses",
    "profileActionOverrides", "recordTypeVisibilities", "tabSettings",
    "tabVisibilities", "userPermissions",
]

# Permission-set section key fields (used by the Deduplicate operation).
PERMSET_SECTION_KEYS = {
    "applicationVisibilities": "application",
    "classAccesses": "apexClass",
    "customMetadataTypeAccesses": "name",
    "customPermissions": "name",
    "customSettingAccesses": "name",
    "externalCredentialPrincipalAccesses": "externalCredentialPrincipal",
    "externalDataSourceAccesses": "externalDataSource",
    "fieldPermissions": "field",
    "flowAccesses": "flow",
    "objectPermissions": "object",
    "pageAccesses": "apexPage",
    "profileActionOverrides": "actionName",
    "recordTypeVisibilities": "recordType",
    "tabSettings": "tab",
    "tabVisibilities": "tab",
    "userPermissions": "name",
}

# ───────────────────────────────────────────────────────────────────────
# Namespace / identity helpers
# ───────────────────────────────────────────────────────────────────────

def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _ns(local_name: str) -> str:
    return f"{NS_PREFIX}{local_name}"


def _child_text(elem: Element, local_name: str) -> str:
    child = elem.find(_ns(local_name))
    if child is None:
        child = elem.find(local_name)
    return (child.text or "").strip() if child is not None else ""


def get_identity(elem: Element) -> str | None:
    fields = IDENTITY_KEYS.get(_local(elem.tag))
    if not fields:
        return None
    parts = [_child_text(elem, f) for f in fields]
    if all(p == "" for p in parts):
        return None
    return "\x1f".join(parts)


def _should_deep_merge(elem: Element) -> bool:
    return _local(elem.tag) in DEEP_MERGE_TAGS

# ───────────────────────────────────────────────────────────────────────
# Fingerprinting (structural identity, order-independent)
# ───────────────────────────────────────────────────────────────────────

def _normalize(elem: Element) -> str:
    parts = [_local(elem.tag)]
    if elem.attrib:
        for k in sorted(elem.attrib):
            parts.append(f'{k}="{elem.attrib[k]}"')
    text = (elem.text or "").strip()
    if text:
        parts.append(f"TEXT:{text}")
    parts.extend(sorted(_normalize(ch) for ch in elem))
    tail = (elem.tail or "").strip()
    if tail:
        parts.append(f"TAIL:{tail}")
    return "|".join(parts)


def _fingerprint(elem: Element) -> str:
    return hashlib.sha256(_normalize(elem).encode()).hexdigest()[:16]

# ───────────────────────────────────────────────────────────────────────
# Core merge engine (adapted from cd_merge.py, generalised to any root)
# ───────────────────────────────────────────────────────────────────────

def _group_by_tag(elem: Element) -> "OrderedDict[str, list[Element]]":
    groups: OrderedDict[str, list[Element]] = OrderedDict()
    for child in elem:
        groups.setdefault(_local(child.tag), []).append(child)
    return groups


def _id_index(elems: list[Element]) -> "OrderedDict[str, Element]":
    idx: OrderedDict[str, Element] = OrderedDict()
    for e in elems:
        key = get_identity(e)
        if key is not None:
            idx[key] = e
    return idx


def deep_merge(base: Element, override: Element, *, _is_version_level: bool = False,
               report: list | None = None, path: str = "") -> Element:
    """Recursively merge *override* onto *base*; returns a new element."""
    merged = Element(base.tag, base.attrib)
    merged.attrib.update(override.attrib)
    merged.text = base.text
    merged.tail = base.tail

    b_groups = _group_by_tag(base)
    o_groups = _group_by_tag(override)

    tag_order = list(b_groups)
    for t in o_groups:
        if t not in tag_order:
            tag_order.append(t)

    for tag in tag_order:
        b_list = b_groups.get(tag, [])
        o_list = o_groups.get(tag, [])

        if _is_version_level and tag in VERSION_METADATA_TAGS:
            for elem in (b_list or o_list):
                merged.append(copy.deepcopy(elem))
            continue

        sample = (b_list + o_list)[0] if (b_list or o_list) else None
        has_id = sample is not None and get_identity(sample) is not None

        if has_id:
            for e in _merge_by_id(b_list, o_list, report=report, path=f"{path}/{tag}"):
                merged.append(e)
        elif (len(b_list) == 1 and len(o_list) == 1 and _should_deep_merge(b_list[0])):
            is_ver = _local(b_list[0].tag) == "contextDefinitionVersions"
            merged.append(deep_merge(b_list[0], o_list[0], _is_version_level=is_ver,
                                     report=report, path=f"{path}/{tag}"))
        elif len(b_list) <= 1 and len(o_list) <= 1:
            src = o_list[0] if o_list else (b_list[0] if b_list else None)
            if src is not None:
                merged.append(copy.deepcopy(src))
                if (report is not None and b_list and o_list
                        and _fingerprint(b_list[0]) != _fingerprint(o_list[0])):
                    report.append(("OVERRIDE", f"{path}/{tag}", ""))
        else:
            b_fps = {_fingerprint(c) for c in b_list}
            for c in b_list:
                merged.append(copy.deepcopy(c))
            for c in o_list:
                if _fingerprint(c) not in b_fps:
                    merged.append(copy.deepcopy(c))
                    if report is not None:
                        report.append(("ADD", f"{path}/{tag}", "(no-id fallback)"))

    return merged


def _merge_by_id(b_list: list[Element], o_list: list[Element], *,
                 report: list | None = None, path: str = "") -> list[Element]:
    b_idx = _id_index(b_list)
    o_idx = _id_index(o_list)
    result: list[Element] = []
    seen: set[str] = set()

    for key, b_elem in b_idx.items():
        seen.add(key)
        if key in o_idx:
            o_elem = o_idx[key]
            same = _fingerprint(b_elem) == _fingerprint(o_elem)
            if _should_deep_merge(b_elem):
                is_ver = _local(b_elem.tag) == "contextDefinitionVersions"
                result.append(deep_merge(b_elem, o_elem, _is_version_level=is_ver,
                                         report=report, path=f"{path}[{key}]"))
                if report is not None and not same:
                    report.append(("DEEP-MERGE", f"{path}[{key}]", ""))
            else:
                result.append(copy.deepcopy(o_elem))
                if report is not None and not same:
                    report.append(("OVERRIDE", f"{path}[{key}]", ""))
        else:
            result.append(copy.deepcopy(b_elem))

    for key, o_elem in o_idx.items():
        if key not in seen:
            result.append(copy.deepcopy(o_elem))
            if report is not None:
                report.append(("ADD", f"{path}[{key}]", "new from modified"))

    return result

# ───────────────────────────────────────────────────────────────────────
# Pretty-print + serialization
# ───────────────────────────────────────────────────────────────────────

def _indent_tree(root: Element, indent_str: str = "    ") -> None:
    def _walk(elem: Element, level: int) -> None:
        child_prefix = "\n" + indent_str * (level + 1)
        closing_prefix = "\n" + indent_str * level
        children = list(elem)
        if children:
            if not (elem.text and elem.text.strip()):
                elem.text = child_prefix
            last = len(children) - 1
            for i, child in enumerate(children):
                _walk(child, level + 1)
                if not (child.tail and child.tail.strip()):
                    child.tail = child_prefix if i < last else closing_prefix
        if level and not (elem.tail and elem.tail.strip()):
            elem.tail = "\n" + indent_str * (level - 1)

    _walk(root, 0)
    root.tail = None


def serialize_tree(root: Element) -> str:
    _indent_tree(root)
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + raw + "\n"

# ───────────────────────────────────────────────────────────────────────
# Permission-set normalisation
# ───────────────────────────────────────────────────────────────────────

def _reorder_permset(root: Element) -> None:
    """Sort top-level Permission Set / Profile children into a stable order."""
    def keyfn(el: Element):
        tag = _local(el.tag)
        try:
            si = PERMSET_SECTION_ORDER.index(tag)
        except ValueError:
            si = len(PERMSET_SECTION_ORDER)
        ident = get_identity(el) or _child_text(el, "name") or ""
        return (si, tag, ident)

    children = sorted(list(root), key=keyfn)
    for c in list(root):
        root.remove(c)
    for c in children:
        root.append(c)

# ───────────────────────────────────────────────────────────────────────
# Validation
# ───────────────────────────────────────────────────────────────────────

def _collect_ids(root: Element, tag_local: str) -> set[str]:
    ids: set[str] = set()
    for elem in root.iter():
        if _local(elem.tag) == tag_local:
            eid = get_identity(elem)
            if eid:
                ids.add(eid)
    return ids


def validate_merge(base_root: Element, override_root: Element,
                   merged_root: Element) -> list[str]:
    """Every unique identity present in either input must survive into the merge."""
    errors: list[str] = []
    tags = set()
    for r in (base_root, override_root):
        for elem in r.iter():
            t = _local(elem.tag)
            if t in IDENTITY_KEYS:
                tags.add(t)
    for tag_local in sorted(tags):
        base_ids = _collect_ids(base_root, tag_local)
        override_ids = _collect_ids(override_root, tag_local)
        merged_ids = _collect_ids(merged_root, tag_local)
        missing = (base_ids | override_ids) - merged_ids
        for m in sorted(missing):
            src = "BASE" if m in base_ids else "MODIFIED"
            errors.append(f"MISSING <{tag_local}> '{m.replace(chr(0x1f), ' / ')}' (from {src})")
    return errors


def _find_duplicates(root: Element, label: str) -> list[str]:
    """Return warnings for every duplicate identity key found in root."""
    from collections import Counter
    warnings: list[str] = []
    counts: Counter = Counter()
    for child in root:
        tag = _local(child.tag)
        if tag not in IDENTITY_KEYS:
            continue
        key = get_identity(child)
        if key is not None:
            counts[(tag, key)] += 1
    for (tag, key), count in sorted(counts.items()):
        if count > 1:
            display_key = key.replace("\x1f", " / ")
            warnings.append(
                f"  [{label}] <{tag}> '{display_key}' appears {count}x — "
                f"only the last occurrence will be kept in the merged output."
            )
    return warnings

# ───────────────────────────────────────────────────────────────────────
# Operation: MERGE
# ───────────────────────────────────────────────────────────────────────

def _parse(text: str, label: str) -> Element:
    if not text or not text.strip():
        raise ValueError(f"The {label} XML is empty.")
    return ET.fromstring(text)


def merge_xml(base_text: str, override_text: str) -> dict:
    """Merge two pasted XML strings. Returns {ok, merged, report, warnings, duplicates}."""
    try:
        base_root = _parse(base_text, "Base")
        override_root = _parse(override_text, "Modified")
    except ValueError as e:
        return {"ok": False, "log": str(e)}
    except ET.ParseError as e:
        return {"ok": False, "log": f"XML parse error: {e}"}

    if _local(base_root.tag) != _local(override_root.tag):
        return {"ok": False, "log": (
            f"Root elements differ: Base is <{_local(base_root.tag)}> but "
            f"Modified is <{_local(override_root.tag)}>. They must be the same "
            "metadata type to merge.")}

    dup_warnings: list[str] = (
        _find_duplicates(base_root, "Base") +
        _find_duplicates(override_root, "Modified")
    )

    actions: list[tuple] = []
    root_local = _local(base_root.tag)
    merged_root = deep_merge(base_root, override_root, report=actions, path=root_local)

    if root_local in ("PermissionSet", "Profile"):
        _reorder_permset(merged_root)

    errors = validate_merge(base_root, override_root, merged_root)
    merged_xml = serialize_tree(merged_root)
    report = _format_merge_report(
        actions, base_root, override_root, merged_root, errors, dup_warnings)

    return {"ok": True, "merged": merged_xml, "report": report,
            "warnings": errors, "duplicates": dup_warnings, "rootType": root_local}


def _format_merge_report(actions: list[tuple], base_root: Element,
                         override_root: Element, merged_root: Element,
                         errors: list[str],
                         dup_warnings: list[str] | None = None) -> str:
    lines: list[str] = []

    if dup_warnings:
        lines.append("!" * 60)
        lines.append(f"  DUPLICATE ENTRIES DETECTED IN INPUT FILES  ({len(dup_warnings)} total)")
        lines.append("!" * 60)
        lines.append("")
        lines.append("  Your input XML files contain elements with duplicate identity")
        lines.append("  keys (same apexClass, field, object, etc. listed more than once).")
        lines.append("  The merge engine keeps only the LAST occurrence of each duplicate.")
        lines.append("  The merged output has FEWER entries than your inputs as a result.")
        lines.append("")
        lines.append("  To fix: run the DEDUPLICATE operation on each input file first,")
        lines.append("  then re-merge the cleaned files.")
        lines.append("")
        for w in dup_warnings:
            lines.append(w)
        lines.append("")
        lines.append("!" * 60)
        lines.append("")

    tags = set()
    for r in (base_root, override_root, merged_root):
        for elem in r.iter():
            t = _local(elem.tag)
            if t in IDENTITY_KEYS:
                tags.add(t)

    if tags:
        lines.append(f"{'Element Type':<34}{'Base':>7}{'Modified':>10}{'Merged':>8}")
        lines.append("-" * 59)
        for tag_local in sorted(tags):
            b = len(_collect_ids(base_root, tag_local))
            o = len(_collect_ids(override_root, tag_local))
            m = len(_collect_ids(merged_root, tag_local))
            flag = " !" if m < b else ""
            lines.append(f"{tag_local:<34}{b:>7}{o:>10}{m:>8}{flag}")
        lines.append("")

    adds = [a for a in actions if a[0] == "ADD"]
    overrides = [a for a in actions if a[0] == "OVERRIDE"]
    merges = [a for a in actions if a[0] == "DEEP-MERGE"]
    lines.append(f"Summary:  {len(adds)} added  |  {len(overrides)} overridden  "
                 f"|  {len(merges)} deep-merged")
    lines.append("")

    if adds:
        lines.append("NEW (added from Modified, not in Base):")
        for _, p, note in adds:
            lines.append(f"  + {p}  {note}".rstrip())
        lines.append("")
    if overrides:
        lines.append("OVERRIDDEN (Modified replaced Base):")
        for _, p, _n in overrides:
            lines.append(f"  ~ {p}")
        lines.append("")
    if merges:
        lines.append("DEEP-MERGED containers:")
        for _, p, _n in merges:
            lines.append(f"  * {p}")
        lines.append("")
    if not actions:
        lines.append("(no differences — Base and Modified are structurally identical)")
        lines.append("")

    if errors:
        lines.append("!! WARNING — some elements could not be accounted for:")
        for e in errors:
            lines.append(f"  x {e}")
    else:
        lines.append("Validation passed — every element from both sides is present.")
    return "\n".join(lines)

# ───────────────────────────────────────────────────────────────────────
# Operation: COMPARE
# ───────────────────────────────────────────────────────────────────────

def _collect_compare_elements(root: Element, tag_filter: str | None) -> list[Element]:
    if tag_filter:
        return [e for e in root.iter() if _local(e.tag) == tag_filter]
    children = list(root)
    if len(children) == 1 and len(list(children[0])) > 0:
        return list(children[0])
    return children


def _pretty_snippet(elem: Element, max_lines: int = 12) -> str:
    raw = tostring(elem, encoding="unicode", short_empty_elements=True)
    out = []
    for ln in raw.splitlines():
        out.append(ln.replace(NS_PREFIX, "").replace(f' xmlns="{NS}"', ""))
    if len(out) > max_lines:
        half = max_lines // 2
        out = out[:half] + [f"      ... ({len(out) - max_lines} more lines) ..."] + out[-half:]
    return "\n".join(out)


def compare_xml(a_text: str, b_text: str, tag_filter: str | None = None) -> dict:
    """Structural comparison of two XML strings. Returns {ok, report, xml}."""
    if not a_text.strip() or not b_text.strip():
        return {"ok": False, "log": "Please paste XML in both panes before comparing."}
    try:
        root_a = ET.fromstring(a_text)
        root_b = ET.fromstring(b_text)
    except ET.ParseError as e:
        # Not valid XML (e.g. Apex). The UI still renders a line-level diff.
        return {"ok": True, "xml": False,
                "report": f"Content is not valid XML ({e}).\n"
                          "Showing line-by-line differences only."}

    tf = tag_filter.strip() if tag_filter else None
    elements_a = _collect_compare_elements(root_a, tf)
    elements_b = _collect_compare_elements(root_b, tf)

    fps_a = Counter(_fingerprint(e) for e in elements_a)
    fps_b = Counter(_fingerprint(e) for e in elements_b)
    index_a, index_b = {}, {}
    for e in elements_a:
        index_a.setdefault(_fingerprint(e), e)
    for e in elements_b:
        index_b.setdefault(_fingerprint(e), e)

    only_a = fps_a - fps_b
    only_b = fps_b - fps_a
    common = fps_a & fps_b

    lines = []
    lines.append("STRUCTURAL COMPARISON (order-independent)")
    if tf:
        lines.append(f"Filter: <{tf}> elements only")
    lines.append(f"  Left elements:   {len(elements_a)}")
    lines.append(f"  Right elements:  {len(elements_b)}")
    lines.append(f"  Matched:         {sum(common.values())}")
    lines.append(f"  Only in Left:    {sum(only_a.values())}")
    lines.append(f"  Only in Right:   {sum(only_b.values())}")
    lines.append("")

    if only_a:
        lines.append("-" * 60)
        lines.append(f"IN LEFT BUT MISSING FROM RIGHT  [{sum(only_a.values())}]")
        lines.append("-" * 60)
        for fp, count in sorted(only_a.items(), key=lambda x: x[1], reverse=True):
            elem = index_a[fp]
            lines.append(f"\n  <{_local(elem.tag)}>  (x{count})")
            lines.append("  " + _pretty_snippet(elem).replace("\n", "\n  "))
    if only_b:
        lines.append("")
        lines.append("-" * 60)
        lines.append(f"IN RIGHT BUT MISSING FROM LEFT  [{sum(only_b.values())}]")
        lines.append("-" * 60)
        for fp, count in sorted(only_b.items(), key=lambda x: x[1], reverse=True):
            elem = index_b[fp]
            lines.append(f"\n  <{_local(elem.tag)}>  (x{count})")
            lines.append("  " + _pretty_snippet(elem).replace("\n", "\n  "))
    if not only_a and not only_b:
        lines.append("FILES ARE STRUCTURALLY IDENTICAL (no missing elements).")

    return {"ok": True, "xml": True, "report": "\n".join(lines),
            "onlyLeft": sum(only_a.values()), "onlyRight": sum(only_b.values()),
            "matched": sum(common.values())}

# ───────────────────────────────────────────────────────────────────────
# Operation: DEDUPLICATE (permission sets)
# ───────────────────────────────────────────────────────────────────────

def dedup_permset_text(text: str) -> dict:
    """Remove duplicate entries from a Permission Set / Profile XML string."""
    if not text or not text.strip():
        return {"ok": False, "log": "Please paste a Permission Set XML first."}
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        return {"ok": False, "log": f"XML parse error: {e}"}

    singles: "OrderedDict[str, Element]" = OrderedDict()
    sections: "OrderedDict[str, OrderedDict[str, Element]]" = OrderedDict()
    stats: dict[str, dict] = {}

    for child in root:
        tag = _local(child.tag)
        if tag in PERMSET_SECTION_KEYS:
            if tag not in sections:
                sections[tag] = OrderedDict()
                stats[tag] = {"total": 0, "dupes": 0}
            stats[tag]["total"] += 1
            key_val = _child_text(child, PERMSET_SECTION_KEYS[tag])
            if key_val and key_val in sections[tag]:
                stats[tag]["dupes"] += 1
            else:
                sections[tag][key_val or f"__unknown_{stats[tag]['total']}"] = child
        else:
            singles[tag] = child

    new_root = Element(root.tag, root.attrib)
    items: list[tuple] = []
    for tag, elem in singles.items():
        items.append((tag, "", elem))
    for tag, entries in sections.items():
        for key_val, elem in entries.items():
            items.append((tag, key_val, elem))

    def sort_key(it):
        try:
            si = PERMSET_SECTION_ORDER.index(it[0])
        except ValueError:
            si = len(PERMSET_SECTION_ORDER)
        return (si, it[0], it[1])

    items.sort(key=sort_key)
    for _tag, _k, elem in items:
        new_root.append(copy.deepcopy(elem))

    total_dupes = sum(s["dupes"] for s in stats.values())
    report_lines = ["DEDUPLICATION REPORT", "-" * 40]
    for tag in PERMSET_SECTION_ORDER:
        if tag in stats:
            s = stats[tag]
            unique = s["total"] - s["dupes"]
            report_lines.append(
                f"  {tag}: {s['total']} -> {unique} unique "
                f"({s['dupes']} duplicates removed)")
    report_lines.append("")
    report_lines.append(f"TOTAL duplicates removed: {total_dupes}")

    return {"ok": True, "result": serialize_tree(new_root),
            "report": "\n".join(report_lines), "removed": total_dupes}

# ───────────────────────────────────────────────────────────────────────
# Operation: CONTEXT DEFINITION FIX
# ───────────────────────────────────────────────────────────────────────

def _cd_get_versions(root: Element) -> Element | None:
    return root.find(_ns("contextDefinitionVersions"))


def _cd_get_mapping(versions: Element, title: str) -> Element | None:
    for cm in versions.findall(_ns("contextMappings")):
        if _child_text(cm, "title") == title:
            return cm
    return None


def _cd_get_node_mapping(mapping: Element, ctx_node: str, obj: str) -> Element | None:
    for nm in mapping.findall(_ns("contextNodeMappings")):
        if _child_text(nm, "contextNode") == ctx_node and _child_text(nm, "object") == obj:
            return nm
    return None


def _cd_get_context_node(versions: Element, title: str) -> Element | None:
    for cn in versions.findall(_ns("contextNodes")):
        if _child_text(cn, "title") == title:
            return cn
    return None


def _cd_has_attr_mapping(node_mapping: Element, attr_name: str) -> bool:
    return any(_child_text(cam, "contextAttribute") == attr_name
               for cam in node_mapping.findall(_ns("contextAttributeMappings")))


def _cd_has_context_attr(context_node: Element, title: str) -> bool:
    return any(_child_text(ca, "title") == title
               for ca in context_node.findall(_ns("contextAttributes")))


def _cd_field_info(cam: Element) -> str:
    """Human-readable field description from a contextAttributeMappings element."""
    hd = cam.find(_ns("contextAttrHydrationDetails"))
    if hd is not None:
        obj = _child_text(hd, "objectName")
        field = _child_text(hd, "queryAttribute")
        if obj and field:
            return f"{obj}.{field}"
    ctxs = cam.find(_ns("ctxAttrHydrationCtxs"))
    if ctxs is not None:
        cqa = _child_text(ctxs, "contextQueryAttribute")
        if cqa:
            return f"hydration ref: {cqa}"
    return ""


def _cd_group_key(name: str) -> str:
    """Strip known object-role prefixes for visual grouping."""
    for prefix in ("AAS", "ASP", "ASS", "STI", "OLI", "Asset_"):
        if name.startswith(prefix) and len(name) > len(prefix):
            return name[len(prefix):]
    return name


def cd_fix_analyze(base_text: str, modified_text: str) -> dict:
    """
    Scan Modified for contextAttributeMappings and contextAttributes that
    do not exist in Base.  Returns the full list so the UI can let the user
    pick which ones to apply.
    """
    if not base_text.strip() or not modified_text.strip():
        return {"ok": False, "log": "Paste both Base and Modified XMLs first."}
    try:
        base_root = _parse(base_text, "Base")
        mod_root  = _parse(modified_text, "Modified")
    except (ValueError, ET.ParseError) as exc:
        return {"ok": False, "log": str(exc)}

    if _local(base_root.tag) != "ContextDefinition" or _local(mod_root.tag) != "ContextDefinition":
        return {"ok": False,
                "log": "Both XMLs must be ContextDefinition metadata "
                       f"(got <{_local(base_root.tag)}> and <{_local(mod_root.tag)}>)."}

    base_ver = _cd_get_versions(base_root)
    mod_ver  = _cd_get_versions(mod_root)
    if base_ver is None or mod_ver is None:
        return {"ok": False, "log": "Could not find <contextDefinitionVersions> in both files."}

    items: list[dict] = []

    # ── contextMappings → contextNodeMappings → contextAttributeMappings ──────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        if not m_title:
            continue
        base_m = _cd_get_mapping(base_ver, m_title)

        for mod_nm in mod_m.findall(_ns("contextNodeMappings")):
            ctx_node = _child_text(mod_nm, "contextNode")
            obj      = _child_text(mod_nm, "object")
            if not ctx_node or not obj:
                continue
            base_nm = (_cd_get_node_mapping(base_m, ctx_node, obj)
                       if base_m is not None else None)

            for cam in mod_nm.findall(_ns("contextAttributeMappings")):
                attr = _child_text(cam, "contextAttribute")
                if not attr:
                    continue
                if base_nm is not None and _cd_has_attr_mapping(base_nm, attr):
                    continue   # already in base
                field_info = _cd_field_info(cam)
                items.append({
                    "id":           f"cam\x1f{m_title}\x1f{ctx_node}\x1f{obj}\x1f{attr}",
                    "type":         "mapping",
                    "mappingTitle": m_title,
                    "contextNode":  ctx_node,
                    "object":       obj,
                    "attrName":     attr,
                    "fieldInfo":    field_info,
                    "group":        _cd_group_key(attr),
                    "path":         f"{m_title} → {ctx_node} / {obj}",
                    "missingParent": base_m is None or base_nm is None,
                })

    # ── contextNodes → contextAttributes ─────────────────────────────────────
    for mod_cn in mod_ver.findall(_ns("contextNodes")):
        cn_title = _child_text(mod_cn, "title")
        if not cn_title:
            continue
        base_cn = _cd_get_context_node(base_ver, cn_title)

        for ca in mod_cn.findall(_ns("contextAttributes")):
            ca_title = _child_text(ca, "title")
            if not ca_title:
                continue
            if base_cn is not None and _cd_has_context_attr(base_cn, ca_title):
                continue   # already in base
            items.append({
                "id":        f"ca\x1f{cn_title}\x1f{ca_title}",
                "type":      "nodeAttr",
                "nodeName":  cn_title,
                "attrTitle": ca_title,
                "fieldInfo": "",
                "group":     _cd_group_key(ca_title),
                "path":      f"contextNodes[{cn_title}]",
                "missingParent": base_cn is None,
            })

    if not items:
        return {"ok": True, "items": [],
                "summary": "No additions found — Modified has nothing new beyond Base."}

    return {"ok": True, "items": items,
            "summary": f"Found {len(items)} addition(s) in Modified that are absent from Base."}


def cd_fix_build(base_text: str, modified_text: str, selected_ids: list) -> dict:
    """
    Apply the user-selected additions from Modified into Base.
    Returns the merged XML and a human-readable apply-report.
    """
    if not base_text.strip() or not modified_text.strip():
        return {"ok": False, "log": "Base and Modified XMLs are required."}
    if not selected_ids:
        return {"ok": False, "log": "No items selected — tick at least one field to include."}
    try:
        base_root = _parse(base_text, "Base")
        mod_root  = _parse(modified_text, "Modified")
    except (ValueError, ET.ParseError) as exc:
        return {"ok": False, "log": str(exc)}

    base_ver = _cd_get_versions(base_root)
    mod_ver  = _cd_get_versions(mod_root)
    if base_ver is None or mod_ver is None:
        return {"ok": False, "log": "Could not find <contextDefinitionVersions>."}

    selected = set(selected_ids)
    report_lines = ["CONTEXT DEFINITION FIX — APPLY REPORT", "=" * 60, ""]
    applied = skipped = 0
    errs: list[str] = []

    # ── contextAttributeMappings ──────────────────────────────────────────────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        for mod_nm in mod_m.findall(_ns("contextNodeMappings")):
            ctx_node = _child_text(mod_nm, "contextNode")
            obj      = _child_text(mod_nm, "object")
            for cam in mod_nm.findall(_ns("contextAttributeMappings")):
                attr    = _child_text(cam, "contextAttribute")
                item_id = f"cam\x1f{m_title}\x1f{ctx_node}\x1f{obj}\x1f{attr}"
                if item_id not in selected:
                    continue
                base_m = _cd_get_mapping(base_ver, m_title)
                if base_m is None:
                    errs.append(f"  ✗ contextMappings[{m_title}] not found in Base — skipped {attr}")
                    skipped += 1
                    continue
                base_nm = _cd_get_node_mapping(base_m, ctx_node, obj)
                if base_nm is None:
                    errs.append(f"  ✗ contextNodeMappings[{ctx_node}/{obj}] not in {m_title} — skipped {attr}")
                    skipped += 1
                    continue
                if _cd_has_attr_mapping(base_nm, attr):
                    report_lines.append(f"  ✓ already present: {attr}  [{m_title}/{ctx_node}/{obj}]")
                    skipped += 1
                    continue
                new_cam = copy.deepcopy(cam)
                children = list(base_nm)
                idx = next((i for i, ch in enumerate(children)
                            if _local(ch.tag) == "contextNode"), len(children))
                base_nm.insert(idx, new_cam)
                report_lines.append(f"  + added: {attr}  [{m_title}/{ctx_node}/{obj}]")
                applied += 1

    # ── contextAttributes in contextNodes ─────────────────────────────────────
    for mod_cn in mod_ver.findall(_ns("contextNodes")):
        cn_title = _child_text(mod_cn, "title")
        for ca in mod_cn.findall(_ns("contextAttributes")):
            ca_title = _child_text(ca, "title")
            item_id  = f"ca\x1f{cn_title}\x1f{ca_title}"
            if item_id not in selected:
                continue
            base_cn = _cd_get_context_node(base_ver, cn_title)
            if base_cn is None:
                errs.append(f"  ✗ contextNodes[{cn_title}] not found in Base — skipped {ca_title}")
                skipped += 1
                continue
            if _cd_has_context_attr(base_cn, ca_title):
                report_lines.append(f"  ✓ already present: {ca_title}  [contextNodes/{cn_title}]")
                skipped += 1
                continue
            new_ca = copy.deepcopy(ca)
            children = list(base_cn)
            last_ca = max((i for i, ch in enumerate(children)
                           if _local(ch.tag) == "contextAttributes"), default=-1)
            base_cn.insert(last_ca + 1, new_ca)
            report_lines.append(f"  + added: {ca_title}  [contextNodes/{cn_title}]")
            applied += 1

    report_lines += ["",
                     f"Summary: {applied} added · {skipped} skipped · {len(errs)} error(s)"]
    if errs:
        report_lines += ["", "Errors:"] + errs

    return {
        "ok":      True,
        "result":  serialize_tree(base_root),
        "report":  "\n".join(report_lines),
        "applied": applied,
        "skipped": skipped,
        "errors":  len(errs),
    }


# ───────────────────────────────────────────────────────────────────────
# HTTP server
# ───────────────────────────────────────────────────────────────────────

APP_ID = "xml-tool"
DEFAULT_PORT = int(os.environ.get("XML_UI_PORT", "8799"))


def _build_id() -> str:
    try:
        with open(os.path.abspath(__file__), "rb") as f:
            return hashlib.sha1(f.read()).hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return "dev"


BUILD = _build_id()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default logging
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

            if self.path == "/api/merge":
                self._send(200, merge_xml(body.get("base", ""), body.get("override", "")))
            elif self.path == "/api/compare":
                self._send(200, compare_xml(body.get("a", ""), body.get("b", ""),
                                            body.get("tag", "")))
            elif self.path == "/api/dedup":
                self._send(200, dedup_permset_text(body.get("content", "")))
            elif self.path == "/api/cdfix/analyze":
                self._send(200, cd_fix_analyze(body.get("base", ""), body.get("modified", "")))
            elif self.path == "/api/cdfix/build":
                self._send(200, cd_fix_build(
                    body.get("base", ""), body.get("modified", ""),
                    body.get("selectedIds", [])))
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(200, {"ok": False, "log": f"Unexpected server error: {exc}"})


def port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def is_our_server(port):
    try:
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=2) as resp:
            return json.loads(resp.read().decode("utf-8")).get("app") == APP_ID
    except Exception:  # noqa: BLE001
        return False


# PAGE is defined in the companion module section below.
from xml_tool_page import PAGE  # noqa: E402  (kept separate for readability)


def main():
    if "--print-build" in sys.argv:
        print(BUILD)
        return

    open_browser = "--no-browser" not in sys.argv
    port = DEFAULT_PORT
    url = f"http://127.0.0.1:{port}/"

    if is_our_server(port):
        print(f"XML Tool is already running at {url}")
        if open_browser:
            webbrowser.open(url)
        return

    if port_in_use(port):
        print(f"ERROR: Port {port} is in use by another program.")
        print("Stop it, or set a different port: XML_UI_PORT=8900 python3 xml_tool.py")
        sys.exit(1)

    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        print(f"ERROR: Could not start server on port {port}: {exc}")
        sys.exit(1)

    print("=" * 60)
    print("  Salesforce Metadata XML Tool — local UI")
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
