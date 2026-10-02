"""Salesforce metadata XML engine: compare, merge, deduplicate, and Context
Definition fix (analyze + build).

Ported from the standalone XML Tool so the CML Tool can serve these operations.
Pure functions over XML text; no HTTP, filesystem, or org access.
"""

from __future__ import annotations

import copy
import hashlib
from collections import Counter, OrderedDict
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


def _compare_diff_items(counter: Counter, index: dict[str, Element]) -> list[dict]:
    """Create one display item per unique structural difference."""
    items = []
    for fingerprint, count in counter.items():
        elem = index[fingerprint]
        identity = get_identity(elem) or ""
        items.append({
            "tag": _local(elem.tag),
            "identity": identity.replace("\x1f", " / "),
            "count": count,
            "snippet": _pretty_snippet(elem, max_lines=80),
        })
    return sorted(items, key=lambda item: (
        item["tag"].lower(), item["identity"].lower(), item["snippet"]
    ))


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

    return {
        "ok": True,
        "xml": True,
        "report": "\n".join(lines),
        "onlyLeft": sum(only_a.values()),
        "onlyRight": sum(only_b.values()),
        "matched": sum(common.values()),
        "uniqueLeft": _compare_diff_items(only_a, index_a),
        "uniqueRight": _compare_diff_items(only_b, index_b),
    }

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
    singleton_stats: "OrderedDict[str, dict]" = OrderedDict()
    warnings: list[str] = []

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
            if tag not in singleton_stats:
                singleton_stats[tag] = {"total": 0, "dupes": 0, "conflicts": 0}
            singleton_stats[tag]["total"] += 1
            if tag in singles:
                singleton_stats[tag]["dupes"] += 1
                if _normalize(singles[tag]) != _normalize(child):
                    singleton_stats[tag]["conflicts"] += 1
            else:
                # Singleton metadata is authoritative at its first occurrence.
                # Later copies are removed, with conflicting values reported.
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

    section_dupes = sum(s["dupes"] for s in stats.values())
    singleton_dupes = sum(s["dupes"] for s in singleton_stats.values())
    total_dupes = section_dupes + singleton_dupes
    report_lines = ["DEDUPLICATION REPORT", "-" * 40]
    for tag in PERMSET_SECTION_ORDER:
        if tag in stats:
            s = stats[tag]
            unique = s["total"] - s["dupes"]
            report_lines.append(
                f"  {tag}: {s['total']} -> {unique} unique "
                f"({s['dupes']} duplicates removed)")
    duplicated_singletons = [
        (tag, values) for tag, values in singleton_stats.items() if values["dupes"]
    ]
    if duplicated_singletons:
        report_lines += ["", "SINGLETON ELEMENTS:"]
        for tag, values in duplicated_singletons:
            report_lines.append(
                f"  {tag}: {values['total']} -> 1 "
                f"({values['dupes']} duplicate{'s' if values['dupes'] != 1 else ''} removed)"
            )
            if values["conflicts"]:
                warning = (
                    f"<{tag}> had {values['conflicts']} conflicting duplicate value(s); "
                    "the first occurrence was kept."
                )
                warnings.append(warning)
                report_lines.append(f"    ! {warning}")
    report_lines.append("")
    report_lines.append(f"TOTAL duplicates removed: {total_dupes}")

    return {"ok": True, "result": serialize_tree(new_root),
            "report": "\n".join(report_lines), "removed": total_dupes,
            "singletonDuplicates": singleton_dupes, "warnings": warnings}

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


def _cd_get_attr_mapping(node_mapping: Element, attr_name: str) -> Element | None:
    for cam in node_mapping.findall(_ns("contextAttributeMappings")):
        if _child_text(cam, "contextAttribute") == attr_name:
            return cam
    return None


def _cd_mapping_destination(cam: Element) -> tuple[tuple[str, str], ...] | None:
    """Return the object/field hydration path written by an attribute mapping."""
    current = cam.find(_ns("contextAttrHydrationDetails"))
    if current is None:
        return None
    path: list[tuple[str, str]] = []
    while current is not None:
        path.append((
            _child_text(current, "objectName") or "",
            _child_text(current, "queryAttribute") or "",
        ))
        current = current.find(_ns("contextAttrHydrationDetails"))
    return tuple(path) if any(obj or field for obj, field in path) else None


def _cd_get_attr_mapping_by_destination(
        node_mapping: Element, target: Element,
        modified_node_mapping: Element | None = None) -> Element | None:
    """
    Find a differently named context attribute mapped to target's destination.
    A Base mapping that Modified also keeps is not a rename, so it is never
    returned for replacement.
    """
    destination = _cd_mapping_destination(target)
    if destination is None:
        return None
    target_attr = _child_text(target, "contextAttribute")
    for cam in node_mapping.findall(_ns("contextAttributeMappings")):
        attr = _child_text(cam, "contextAttribute")
        if (attr != target_attr
                and _cd_mapping_destination(cam) == destination
                and (modified_node_mapping is None
                     or _cd_get_attr_mapping(modified_node_mapping, attr) is None)):
            return cam
    return None


def _cd_has_attr_mapping(node_mapping: Element, attr_name: str) -> bool:
    return _cd_get_attr_mapping(node_mapping, attr_name) is not None


def _cd_get_context_attr(context_node: Element, title: str) -> Element | None:
    for ca in context_node.findall(_ns("contextAttributes")):
        if _child_text(ca, "title") == title:
            return ca
    return None


def _cd_has_context_attr(context_node: Element, title: str) -> bool:
    return _cd_get_context_attr(context_node, title) is not None


def _cd_context_attr_tags(context_attr: Element) -> set[str]:
    return {
        _child_text(tag, "title")
        for tag in context_attr.findall(_ns("contextTags"))
        if _child_text(tag, "title")
    }


def _cd_tag_index(versions: Element) -> dict[str, list[tuple[Element, Element | None]]]:
    """Tag title -> owners, for repeated conflict lookups on an unchanging tree."""
    index: dict[str, list[tuple[Element, Element | None]]] = {}
    for node in versions.findall(_ns("contextNodes")):
        for tag in _cd_context_attr_tags(node):
            index.setdefault(tag, []).append((node, None))
        for context_attr in node.findall(_ns("contextAttributes")):
            for tag in _cd_context_attr_tags(context_attr):
                index.setdefault(tag, []).append((node, context_attr))
    return index


def _cd_context_tag_conflicts(
        versions: Element, target: Element,
        ignore: Element | None = None,
        index: dict | None = None) -> list[tuple[str, Element, Element | None]]:
    """
    Return target's tags already owned elsewhere in the definition. Tag titles
    are unique across the whole ContextDefinition (attribute- and node-level);
    attribute titles are only unique within their node.
    """
    target_tags = _cd_context_attr_tags(target)
    if not target_tags:
        return []
    conflicts: list[tuple[str, Element, Element | None]] = []
    if index is not None:
        for tag in sorted(target_tags):
            for node, owner in index.get(tag, []):
                holder = node if owner is None else owner
                if holder is not target and holder is not ignore:
                    conflicts.append((tag, node, owner))
        return conflicts
    for node in versions.findall(_ns("contextNodes")):
        if node is not target and node is not ignore:
            for shared_tag in target_tags & _cd_context_attr_tags(node):
                conflicts.append((shared_tag, node, None))
        for context_attr in node.findall(_ns("contextAttributes")):
            if context_attr is target or context_attr is ignore:
                continue
            for shared_tag in target_tags & _cd_context_attr_tags(context_attr):
                conflicts.append((shared_tag, node, context_attr))
    return conflicts


def _cd_tag_owner_label(node: Element, context_attr: Element | None) -> str:
    node_title = _child_text(node, "title")
    if context_attr is None:
        return f"{node_title} (node tag)"
    return f"{node_title}/{_child_text(context_attr, 'title')}"


def _cd_strip_conflicting_tags(
        versions: Element, target: Element,
        ignore: Element | None = None,
        index: dict | None = None) -> list[str]:
    """
    Drop target's tags that another owner already holds; return descriptions.
    When target overlays `ignore` (an existing Base element), tags Base already
    had on it are left alone — only tags Modified adds can be refused.
    """
    existing = _cd_context_attr_tags(ignore) if ignore is not None else set()
    conflicts = [
        conflict for conflict in _cd_context_tag_conflicts(versions, target, ignore, index)
        if conflict[0] not in existing
    ]
    if not conflicts:
        return []
    conflicting = {tag for tag, _, _ in conflicts}
    for context_tag in list(target.findall(_ns("contextTags"))):
        if _child_text(context_tag, "title") in conflicting:
            target.remove(context_tag)
    return [
        f"{tag} on {_cd_tag_owner_label(node, owner)}"
        for tag, node, owner in conflicts
    ]


def _cd_release_info(base_root: Element, mod_root: Element) -> dict | None:
    """
    Standard-definition versions when Base and Modified inherit different
    releases of the same parent; None when they match or are unknown.
    """
    parent = _child_text(mod_root, "inheritedFrom")
    base_version = _child_text(base_root, "inheritedFromVersion")
    mod_version = _child_text(mod_root, "inheritedFromVersion")
    if (not parent or not base_version or not mod_version or base_version == mod_version
            or _child_text(base_root, "inheritedFrom") != parent):
        return None
    return {"parent": parent, "base": base_version, "modified": mod_version,
            "group": f"Salesforce release content (Modified {mod_version} · Base {base_version})"}


def _cd_clean_provenance(provenance) -> dict:
    """Keep only the known string fields of each side's origin record."""
    clean = {}
    for side in ("base", "modified"):
        raw = (provenance or {}).get(side) if isinstance(provenance, dict) else None
        if not isinstance(raw, dict):
            clean[side] = {}
            continue
        clean[side] = {
            key: str(raw[key])[:200] for key in ("org", "orgId", "name", "retrievedAt")
            if raw.get(key)}
        if raw.get("edited"):
            clean[side]["edited"] = True
    return clean


def _cd_provenance_lines(provenance: dict, base_root: Element, mod_root: Element) -> list[str]:
    lines = ["Sources:"]
    for side, label, root in (("base", "Base", base_root), ("modified", "Modified", mod_root)):
        origin = provenance.get(side) or {}
        if origin.get("org"):
            where = f"'{origin.get('name') or '?'}' retrieved from {origin['org']}"
            if origin.get("orgId"):
                where += f" (org {origin['orgId']})"
            if origin.get("retrievedAt"):
                where += f" at {origin['retrievedAt']}"
            if origin.get("edited"):
                where += ", then edited by hand"
        else:
            where = "pasted XML (org unknown)"
        parent = _child_text(root, "inheritedFrom")
        version = _child_text(root, "inheritedFromVersion")
        inherits = f"; inherits {parent} {version}" if parent and version else ""
        lines.append(f"  {label + ':':<10}{where}{inherits}")
    return lines + [""]


def _cd_release_element(mod_ver: Element, item_id: str) -> Element | None:
    """The Modified element an analyze item copies, for release-content checks."""
    parts = item_id.split("\x1f")
    kind = parts[0]
    if kind in ("cm", "cam", "nm") and len(parts) >= 2:
        mapping = _cd_get_mapping(mod_ver, parts[1])
        if mapping is None or kind == "cm":
            return mapping
        node_mapping = _cd_get_node_mapping(mapping, parts[2], parts[3]) if len(parts) >= 4 else None
        if node_mapping is None or kind == "nm":
            return node_mapping
        return _cd_get_attr_mapping(node_mapping, parts[4]) if len(parts) == 5 else None
    if kind in ("cn", "ca") and len(parts) >= 2:
        node = _cd_get_context_node(mod_ver, parts[1])
        if node is None or kind == "cn":
            return node
        return _cd_get_context_attr(node, parts[2]) if len(parts) == 3 else None
    return None


def _cd_is_release_content(mod_ver: Element, item_id: str, release: dict | None) -> bool:
    """True when the item's Modified element is inherited from the standard parent."""
    if release is None:
        return False
    element = _cd_release_element(mod_ver, item_id)
    return element is not None and (
        _child_text(element, "inheritedFrom") or "").startswith(release["parent"] + "/")


def _cd_hydration_references(cam: Element) -> list[tuple[str, str]]:
    """(contextNode, contextAttribute) pairs named by a mapping's hydration contexts."""
    refs: list[tuple[str, str]] = []
    for ctx in cam.findall(_ns("ctxAttrHydrationCtxs")):
        node, infix, attr = (
            _child_text(ctx, "contextQueryAttribute") or "").partition(_CD_QUERY_ATTRIBUTE_INFIX)
        if infix and node and attr:
            refs.append((node, attr))
    return refs


def _cd_mapping_references(block: Element) -> list[tuple[str, str]]:
    """
    (contextNode, contextAttribute) pairs referenced by a mapping-side element,
    including the attributes its hydration contexts query.
    """
    local = _local(block.tag)
    if local == "contextAttributeMappings":
        return _cd_hydration_references(block)
    node_mappings = (
        [block] if local == "contextNodeMappings"
        else block.findall(_ns("contextNodeMappings"))
    )
    refs: list[tuple[str, str]] = []
    for node_mapping in node_mappings:
        ctx_node = _child_text(node_mapping, "contextNode")
        for cam in node_mapping.findall(_ns("contextAttributeMappings")):
            attr = _child_text(cam, "contextAttribute")
            if ctx_node and attr:
                refs.append((ctx_node, attr))
            refs.extend(_cd_hydration_references(cam))
    return refs


def _cd_mapping_intents(mapping: Element) -> list[str]:
    return [
        _child_text(intent, "mappingIntent")
        for intent in mapping.findall(_ns("contextMappingIntents"))
        if _child_text(intent, "mappingIntent")
    ]


def _cd_mapping_settings_changes(base_m: Element, mod_m: Element) -> list[tuple[str, str, str]]:
    """
    Mapping-level (field, before, after) changes Modified supplies: missing
    intents, becoming the default mapping, and a changed description. Omitted
    fields are never treated as deletions.
    """
    changes: list[tuple[str, str, str]] = []
    base_intents = set(_cd_mapping_intents(base_m))
    for intent in _cd_mapping_intents(mod_m):
        if intent not in base_intents:
            changes.append(("intent", "", intent))
    if ((_child_text(mod_m, "default") or "").lower() == "true"
            and (_child_text(base_m, "default") or "").lower() != "true"):
        changes.append(("default", _child_text(base_m, "default") or "false", "true"))
    mod_description = _child_text(mod_m, "description")
    if mod_description and mod_description != (_child_text(base_m, "description") or ""):
        changes.append(("description", _child_text(base_m, "description") or "", mod_description))
    return changes


def _cd_insert_in_order(parent: Element, child: Element, order: list[str]) -> None:
    """Insert child after its same-named siblings, else before the first later field."""
    local = _local(child.tag)
    children = list(parent)
    same = [i for i, c in enumerate(children) if _local(c.tag) == local]
    if same:
        parent.insert(same[-1] + 1, child)
        return
    later = set(order[order.index(local) + 1:]) if local in order else set()
    insert_at = next(
        (i for i, c in enumerate(children) if _local(c.tag) in later), len(children))
    parent.insert(insert_at, child)


_CD_MAPPING_FIELD_ORDER = [
    "contextMappingIntents", "contextNodeMappings", "default", "description",
    "inheritedFrom", "title",
]
_CD_NODE_FIELD_ORDER = [
    "contextAttributes", "contextTags", "customMappingAllowed", "displayName",
    "inheritedFrom", "title", "transposable",
]


def _cd_set_scalar(parent: Element, field: str, value: str, order: list[str]) -> None:
    existing = parent.find(_ns(field))
    if existing is None:
        existing = ET.Element(_ns(field))
        _cd_insert_in_order(parent, existing, order)
    existing.text = value


def _cd_node_tag_candidates(
        base_ver: Element, mod_ver: Element,
        base_cn: Element, mod_cn: Element) -> tuple[list[Element], list[str]]:
    """
    Node-level tags Modified adds to an existing node. Returns (safe tags,
    descriptions of tags refused because another owner already holds the title).
    """
    base_tags = _cd_context_attr_tags(base_cn)
    safe: list[Element] = []
    refused: list[str] = []
    for context_tag in mod_cn.findall(_ns("contextTags")):
        title = _child_text(context_tag, "title")
        if not title or title in base_tags:
            continue
        probe = ET.Element(_ns("contextNodes"))
        probe.append(copy.deepcopy(context_tag))
        owners = _cd_context_tag_conflicts(base_ver, probe, ignore=base_cn)
        owners += _cd_context_tag_conflicts(mod_ver, probe, ignore=mod_cn)
        if owners:
            refused.append(
                f"{_child_text(mod_cn, 'title')} node tag {title} (already used by "
                + ", ".join(sorted({_cd_tag_owner_label(n, a) for _, n, a in owners})) + ")"
            )
        else:
            safe.append(context_tag)
    return safe, refused


def _cd_dependency_ids(
        base_ver: Element, mod_ver: Element,
        refs: list[tuple[str, str]]) -> list[str]:
    """Analyze item ids that must also be applied for refs to resolve in Base."""
    required: list[str] = []
    for ctx_node, attr in refs:
        base_cn = _cd_get_context_node(base_ver, ctx_node)
        if base_cn is not None and _cd_get_context_attr(base_cn, attr) is not None:
            continue
        mod_cn = _cd_get_context_node(mod_ver, ctx_node)
        if mod_cn is None or _cd_get_context_attr(mod_cn, attr) is None:
            continue
        item_id = (
            f"cn\x1f{ctx_node}" if base_cn is None
            else f"ca\x1f{ctx_node}\x1f{attr}"
        )
        if item_id not in required:
            required.append(item_id)
    return required


def cd_validate_structure(root: Element) -> list[str]:
    """
    Structural rules a ContextDefinition must satisfy to deploy: unique node
    titles, attribute titles unique per node, tag titles unique across the
    definition, unique mapping / node-mapping / attribute-mapping identities,
    no mapping that points at a missing node or attribute, at most one default
    mapping.
    """
    issues: list[str] = []
    versions = root.findall(_ns("contextDefinitionVersions"))
    if len(versions) != 1:
        return [f"expected exactly one contextDefinitionVersions, found {len(versions)}"]
    version = versions[0]

    nodes: dict[str, set[str]] = {}
    tag_owners: dict[str, list[str]] = {}
    for node in version.findall(_ns("contextNodes")):
        node_title = _child_text(node, "title")
        if node_title in nodes:
            issues.append(f"duplicate contextNodes title: {node_title}")
        attrs = nodes.setdefault(node_title, set())
        for tag in _cd_context_attr_tags(node):
            tag_owners.setdefault(tag, []).append(f"{node_title} (node tag)")
        for context_attr in node.findall(_ns("contextAttributes")):
            attr_title = _child_text(context_attr, "title")
            if attr_title in attrs:
                issues.append(f"duplicate contextAttributes title on {node_title}: {attr_title}")
            attrs.add(attr_title)
            for tag in _cd_context_attr_tags(context_attr):
                tag_owners.setdefault(tag, []).append(f"{node_title}/{attr_title}")
    for tag, owners in tag_owners.items():
        if len(owners) > 1:
            issues.append(f"duplicate contextTags title {tag}: {', '.join(owners)}")

    mapping_titles: set[str] = set()
    defaults = 0
    for mapping in version.findall(_ns("contextMappings")):
        m_title = _child_text(mapping, "title")
        if m_title in mapping_titles:
            issues.append(f"duplicate contextMappings title: {m_title}")
        mapping_titles.add(m_title)
        if (_child_text(mapping, "default") or "").lower() == "true":
            defaults += 1
        node_mapping_keys: set[tuple[str, str]] = set()
        for node_mapping in mapping.findall(_ns("contextNodeMappings")):
            ctx_node = _child_text(node_mapping, "contextNode")
            obj = _child_text(node_mapping, "object")
            if (ctx_node, obj) in node_mapping_keys:
                issues.append(f"duplicate contextNodeMappings: {m_title}/{ctx_node}/{obj}")
            node_mapping_keys.add((ctx_node, obj))
            if ctx_node not in nodes:
                issues.append(
                    f"contextNodeMappings points to missing contextNode: {m_title}/{ctx_node}/{obj}")
                continue
            mapped_attrs: set[str] = set()
            for cam in node_mapping.findall(_ns("contextAttributeMappings")):
                attr = _child_text(cam, "contextAttribute")
                if attr in mapped_attrs:
                    issues.append(
                        f"duplicate contextAttributeMappings: {m_title}/{ctx_node}/{obj}/{attr}")
                mapped_attrs.add(attr)
                if attr not in nodes[ctx_node]:
                    issues.append(
                        "contextAttributeMappings points to missing contextAttribute: "
                        f"{m_title}/{ctx_node}/{obj}/{attr}")
                for hydration_ctx in cam.findall(_ns("ctxAttrHydrationCtxs")):
                    query = _child_text(hydration_ctx, "contextQueryAttribute")
                    if _cd_is_salesforce_id(query):
                        issues.append(
                            "ctxAttrHydrationCtxs uses an org-specific record Id: "
                            f"{m_title}/{ctx_node}/{obj}/{attr} → {query}")
                    elif _CD_QUERY_ATTRIBUTE_INFIX in query:
                        target_node, _, target_attr = query.partition(_CD_QUERY_ATTRIBUTE_INFIX)
                        if target_attr not in nodes.get(target_node, set()):
                            issues.append(
                                "ctxAttrHydrationCtxs points to missing context attribute: "
                                f"{m_title}/{ctx_node}/{obj}/{attr} → {query}")
    if defaults > 1:
        issues.append(f"{defaults} contextMappings are marked default=true (at most one allowed)")
    return issues


def _cd_field_info(cam: Element) -> str:
    """Human-readable field description from a contextAttributeMappings element."""
    hd = cam.find(_ns("contextAttrHydrationDetails"))
    if hd is not None:
        parts = []
        current = hd
        first_object = _child_text(current, "objectName")
        if first_object:
            parts.append(first_object)
        while current is not None:
            query = _child_text(current, "queryAttribute")
            if query:
                parts.append(query)
            current = current.find(_ns("contextAttrHydrationDetails"))
        if parts:
            return ".".join(parts)
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


def _cd_normalize_serializer_fields(root: Element) -> dict:
    """Omit serializer-only fields that the UAT API 66 schema rejects."""
    localization_defaults = 0
    for parent in root.iter():
        for child in list(parent):
            if (_local(child.tag) == "localizationDisabled"
                    and (child.text or "").strip().lower() == "false"):
                parent.remove(child)
                localization_defaults += 1

    root_fields = []
    for child in list(root):
        tag = _local(child.tag)
        if tag in {"isTransformationEnabled", "releaseVersion"}:
            root.remove(child)
            root_fields.append(tag)

    return {
        "localizationDefaults": localization_defaults,
        "rootFields": root_fields,
    }


def _cd_is_salesforce_id(value: str) -> bool:
    """True for a 15/18-char Salesforce record Id (not a developer name)."""
    return (
        len(value) in {15, 18}
        and value.isalnum()
        and any(char.isalpha() for char in value)
        and any(char.isdigit() for char in value)
    )


def _cd_set_child_text(elem: Element, local_name: str, value: str) -> bool:
    child = elem.find(_ns(local_name))
    if child is None:
        child = elem.find(local_name)
    if child is None:
        return False
    child.text = value
    return True


def _cd_strip_attribute_role_prefix(name: str) -> str:
    """AASBillingCode__c → BillingCode__c; AssetConstraintEngineNodeStatus__c → ConstraintEngineNodeStatus__c."""
    for prefix in ("AAS", "ASP", "ASS", "STI", "OLI", "Asset"):
        rest = name[len(prefix):]
        if name.startswith(prefix) and rest and rest[0].isupper():
            return rest
    return name


def _cd_iter_node_mappings(root: Element):
    versions = _cd_get_versions(root)
    if versions is None:
        return
    for mapping in versions.findall(_ns("contextMappings")):
        for node_mapping in mapping.findall(_ns("contextNodeMappings")):
            yield mapping, node_mapping


def _cd_node_mapping_key(mapping: Element, node_mapping: Element) -> tuple[str, str, str]:
    return (
        _child_text(mapping, "title"),
        _child_text(node_mapping, "contextNode"),
        _child_text(node_mapping, "object"),
    )


def _cd_node_mapping_keys(root: Element) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for mapping, node_mapping in _cd_iter_node_mappings(root):
        key = _cd_node_mapping_key(mapping, node_mapping)
        if all(key):
            keys.add(key)
    return keys


def _cd_context_definition_developer_name(root: Element) -> str:
    """Prefer <developerName>, else the most common non-Id mappedContextDefinition."""
    named = _child_text(root, "developerName")
    if named and not _cd_is_salesforce_id(named):
        return named
    counts: Counter[str] = Counter()
    for element in root.iter():
        if _local(element.tag) != "mappedContextDefinition":
            continue
        value = (element.text or "").strip()
        if value and not _cd_is_salesforce_id(value):
            counts[value] += 1
    return counts.most_common(1)[0][0] if counts else ""


_CD_QUERY_ATTRIBUTE_INFIX = "_QA_DE_"


def _cd_query_attribute_target(versions: Element | None, name: str) -> tuple[str, str] | None:
    """(node, attribute) a Node_QA_DE_Attribute name refers to, if it exists."""
    if versions is None or _CD_QUERY_ATTRIBUTE_INFIX not in name:
        return None
    node_title, attr_title = name.split(_CD_QUERY_ATTRIBUTE_INFIX, 1)
    node = _cd_get_context_node(versions, node_title)
    if node is None or _cd_get_context_attr(node, attr_title) is None:
        return None
    return node_title, attr_title


def _cd_is_dangling_query_attribute(versions: Element | None, value: str) -> bool:
    return (
        _CD_QUERY_ATTRIBUTE_INFIX in value
        and _cd_query_attribute_target(versions, value) is None
    )


def _cd_portable_hydration_name(
        versions: Element | None, node_mapping: Element, attr_mapping: Element) -> str:
    """
    Name the query attribute a raw ContextAttribute Id refers to. The reference
    is <Node>_QA_DE_<attribute on that node>, where the node is the node
    mapping's <object> (this holds for every named reference in real exports).
    The attribute is the same-named one, else the single one whose name matches
    once role prefixes (AAS, STI, Asset, …) are ignored. Returns "" when no
    existing attribute can be identified, so the caller never invents a name.
    """
    obj = _child_text(node_mapping, "object")
    attr = _child_text(attr_mapping, "contextAttribute")
    if versions is None or not obj or not attr:
        return ""
    target_node = _cd_get_context_node(versions, obj)
    if target_node is None:
        return ""
    if _cd_get_context_attr(target_node, attr) is not None:
        return f"{obj}{_CD_QUERY_ATTRIBUTE_INFIX}{attr}"
    wanted = _cd_strip_attribute_role_prefix(attr)
    matches = [
        _child_text(candidate, "title")
        for candidate in target_node.findall(_ns("contextAttributes"))
        if _cd_strip_attribute_role_prefix(_child_text(candidate, "title")) == wanted
    ]
    if len(matches) == 1:
        return f"{obj}{_CD_QUERY_ATTRIBUTE_INFIX}{matches[0]}"
    return ""


def _cd_rewrite_hydration_ids(root: Element) -> list[dict]:
    """Replace ContextQueryAttribute record Ids with portable developer names.

    Raw Ids fail deploy with: Invalid Id … provided for
    CtxAttrHydrationCtx.ContextQueryAttribute. This must run on Base as well
    as Modified — target-org retrieves often already contain the stale Id.
    """
    rewritten: list[dict] = []
    versions = _cd_get_versions(root)
    mappings = (
        versions.findall(_ns("contextMappings")) if versions is not None else []
    )
    for mapping in mappings:
        mapping_title = _child_text(mapping, "title")
        for node_mapping in mapping.findall(_ns("contextNodeMappings")):
            context_node = _child_text(node_mapping, "contextNode")
            obj = _child_text(node_mapping, "object")
            for attr_mapping in node_mapping.findall(_ns("contextAttributeMappings")):
                attr = _child_text(attr_mapping, "contextAttribute")
                for hydration_ctx in list(attr_mapping.findall(_ns("ctxAttrHydrationCtxs"))):
                    value = _child_text(hydration_ctx, "contextQueryAttribute")
                    is_id = _cd_is_salesforce_id(value)
                    if not is_id and not _cd_is_dangling_query_attribute(versions, value):
                        continue
                    portable = _cd_portable_hydration_name(
                        versions, node_mapping, attr_mapping)
                    path = f"{mapping_title}/{context_node}/{obj}/{attr}"
                    if not is_id:
                        if portable and portable != value:
                            _cd_set_child_text(
                                hydration_ctx, "contextQueryAttribute", portable)
                            rewritten.append({
                                "kind": "contextQueryAttribute",
                                "action": "repair",
                                "path": path,
                                "fromValue": value,
                                "toValue": portable,
                                "detail": (
                                    f"Repaired hydration reference {value} (no such context "
                                    f"attribute) to {portable}."
                                ),
                            })
                        continue
                    if portable:
                        _cd_set_child_text(
                            hydration_ctx, "contextQueryAttribute", portable)
                        rewritten.append({
                            "kind": "contextQueryAttribute",
                            "action": "rewrite",
                            "path": path,
                            "fromValue": value,
                            "toValue": portable,
                            "detail": (
                                f"Rewrote hydration Id {value} to portable "
                                f"name {portable}."
                            ),
                        })
                    else:
                        attr_mapping.remove(hydration_ctx)
                        rewritten.append({
                            "kind": "contextQueryAttribute",
                            "action": "omit",
                            "path": path,
                            "fromValue": value,
                            "toValue": "",
                            "detail": (
                                f"Omitted hydration Id {value}; no portable "
                                "query-attribute name could be derived."
                            ),
                        })
    return rewritten


def _cd_rewrite_mapped_context_definition_ids(
        root: Element, preserve_keys: set[tuple[str, str, str]],
        developer_name: str) -> list[dict]:
    """Keep Base mappedContextDefinition Ids; rewrite Ids on newly copied nodes.

    Salesforce rejects changing an existing mappedContextDefinition from a
    record Id to a developer name even when they refer to the same definition
    ('mappedContextDefinition changed for 11O… new value: Name').
    """
    rewritten: list[dict] = []
    for mapping, node_mapping in _cd_iter_node_mappings(root):
        key = _cd_node_mapping_key(mapping, node_mapping)
        value = _child_text(node_mapping, "mappedContextDefinition")
        if not _cd_is_salesforce_id(value):
            continue
        path = "/".join(part for part in key if part)
        if key in preserve_keys:
            rewritten.append({
                "kind": "mappedContextDefinition",
                "action": "preserve",
                "path": path,
                "fromValue": value,
                "toValue": value,
                "detail": (
                    f"Kept mappedContextDefinition Id {value} on existing "
                    "node mapping; Salesforce rejects renaming it to a "
                    "developer name."
                ),
            })
            continue
        if not developer_name:
            continue
        _cd_set_child_text(node_mapping, "mappedContextDefinition", developer_name)
        rewritten.append({
            "kind": "mappedContextDefinition",
            "action": "rewrite",
            "path": path,
            "fromValue": value,
            "toValue": developer_name,
            "detail": (
                f"Rewrote mappedContextDefinition Id {value} to "
                f"{developer_name} on a newly added node mapping."
            ),
        })
    return rewritten


def _cd_collect_org_id_findings(base_root: Element, mod_root: Element) -> list[dict]:
    """Describe Id issues that Step 3 will auto-fix or preserve."""
    findings: list[dict] = []
    base_keys = _cd_node_mapping_keys(base_root)
    developer_name = (
        _cd_context_definition_developer_name(base_root)
        or _cd_context_definition_developer_name(mod_root)
    )

    seen_hydration: set[str] = set()
    for origin, tree in (("Base", base_root), ("Modified", mod_root)):
        versions = _cd_get_versions(tree)
        if versions is None:
            continue
        for mapping in versions.findall(_ns("contextMappings")):
            mapping_title = _child_text(mapping, "title")
            for node_mapping in mapping.findall(_ns("contextNodeMappings")):
                context_node = _child_text(node_mapping, "contextNode")
                obj = _child_text(node_mapping, "object")
                key = (mapping_title, context_node, obj)
                mapped = _child_text(node_mapping, "mappedContextDefinition")
                if _cd_is_salesforce_id(mapped):
                    preserve = origin == "Base" or key in base_keys
                    findings.append({
                        "origin": origin,
                        "kind": "mappedContextDefinition",
                        "action": "preserve" if preserve else "rewrite",
                        "path": f"{mapping_title}/{context_node}/{obj}",
                        "fromValue": mapped,
                        "toValue": mapped if preserve else developer_name,
                        "detail": (
                            f"Keeping mappedContextDefinition Id {mapped} — "
                            "Salesforce rejects changing this to a developer "
                            "name on an existing mapping."
                            if preserve else
                            f"Will rewrite mappedContextDefinition Id {mapped} "
                            f"to {developer_name or 'the Context Definition developer name'} "
                            "when this new node mapping is copied."
                        ),
                    })
                for attr_mapping in node_mapping.findall(_ns("contextAttributeMappings")):
                    attr = _child_text(attr_mapping, "contextAttribute")
                    ctxs = attr_mapping.find(_ns("ctxAttrHydrationCtxs"))
                    if ctxs is None:
                        continue
                    value = _child_text(ctxs, "contextQueryAttribute")
                    is_id = _cd_is_salesforce_id(value)
                    if not is_id and not _cd_is_dangling_query_attribute(versions, value):
                        continue
                    path = f"{mapping_title}/{context_node}/{obj}/{attr}"
                    if path in seen_hydration:
                        continue
                    seen_hydration.add(path)
                    portable = _cd_portable_hydration_name(
                        versions, node_mapping, attr_mapping)
                    if not is_id and not portable:
                        continue
                    findings.append({
                        "origin": origin,
                        "kind": "contextQueryAttribute",
                        "action": "rewrite" if portable else "omit",
                        "path": path,
                        "fromValue": value,
                        "toValue": portable,
                        "detail": (
                            (f"Will rewrite hydration Id {value} to {portable}." if is_id else
                             f"Will repair hydration reference {value} (no such context "
                             f"attribute) to {portable}.")
                            if portable else
                            f"Will omit hydration Id {value}."
                        ),
                    })
    return findings


def _cd_annotate_id_findings(diagnostics: dict, findings: list[dict]) -> None:
    if not findings or not diagnostics:
        return
    for finding in findings:
        preserved = finding["action"] == "preserve"
        diagnostics.setdefault("changed", []).append({
            "type": (
                "Org-specific ID (preserved)" if preserved
                else "Org-specific ID (auto-fix)"
            ),
            "name": finding["kind"],
            "path": finding["path"],
            "detail": finding["detail"],
            "before": finding["fromValue"],
            "after": finding.get("toValue") or "",
            "count": 1,
        })
    diagnostics["changedCount"] = len(diagnostics.get("changed") or [])
    diagnostics["idFixes"] = findings


def _cd_id_findings_summary_clause(findings: list[dict]) -> str:
    if not findings:
        return ""
    rewrites = sum(1 for item in findings if item["action"] == "rewrite")
    preserved = sum(1 for item in findings if item["action"] == "preserve")
    parts = []
    if rewrites:
        parts.append(
            f"Step 3 will auto-rewrite {rewrites} org-specific Salesforce "
            "Id(s) so the result can deploy."
        )
    if preserved:
        parts.append(
            f"{preserved} existing mappedContextDefinition Id(s) will be "
            "kept; changing them to a developer name is rejected by Salesforce."
        )
    return " " + " ".join(parts)


def _cd_strip_org_specific_hydration_ids(root: Element) -> list[str]:
    """Rewrite source-org hydration record Ids; return the original Id values."""
    return [item["fromValue"] for item in _cd_rewrite_hydration_ids(root)]


def _cd_semantic_signature(elem: Element, skip_children: set[str] | None = None) -> str:
    """Order-independent signature that ignores serializer-only default false fields."""
    skip_children = skip_children or set()

    def walk(node: Element) -> str:
        local = _local(node.tag)
        text = (node.text or "").strip()
        if local == "localizationDisabled" and text.lower() == "false":
            return ""
        parts = [local]
        if text:
            parts.append(f"TEXT:{text}")
        children = []
        for child in node:
            if _local(child.tag) in skip_children:
                continue
            value = walk(child)
            if value:
                children.append(value)
        parts.extend(sorted(children))
        return "|".join(parts)

    return hashlib.sha256(walk(elem).encode()).hexdigest()[:16]


def _cd_overlay_update(base_elem: Element, modified_elem: Element) -> tuple[Element, list[str]]:
    """
    Overlay fields supplied by Modified without treating omissions as deletions.
    Repeating contextTags are unioned; other supplied child groups replace the
    same field in Base so selected value/path changes still take effect.
    """
    result = copy.deepcopy(base_elem)
    result.attrib.update(modified_elem.attrib)
    if (modified_elem.text or "").strip():
        result.text = modified_elem.text

    base_groups: OrderedDict[str, list[Element]] = OrderedDict()
    mod_groups: OrderedDict[str, list[Element]] = OrderedDict()
    for child in base_elem:
        base_groups.setdefault(_local(child.tag), []).append(child)
    for child in modified_elem:
        mod_groups.setdefault(_local(child.tag), []).append(child)

    preserved: list[str] = []
    for tag, base_children in base_groups.items():
        mod_children = mod_groups.get(tag, [])
        if tag == "localizationDisabled" and all(
                (child.text or "").strip().lower() == "false" for child in base_children):
            continue
        if tag == "contextTags":
            mod_signatures = {_cd_semantic_signature(child) for child in mod_children}
            if any(_cd_semantic_signature(child) not in mod_signatures for child in base_children):
                preserved.append(tag)
        elif not mod_children:
            preserved.append(tag)

    def insert_at_modified_position(tag: str, new_children: list[Element]) -> None:
        result_children = list(result)
        same_indexes = [
            index for index, child in enumerate(result_children) if _local(child.tag) == tag
        ]
        if same_indexes:
            insert_at = same_indexes[-1] + 1
        else:
            mod_tags = [_local(child.tag) for child in modified_elem]
            target = mod_tags.index(tag)
            insert_at = len(result_children)
            for following_tag in mod_tags[target + 1:]:
                following = [
                    index for index, child in enumerate(result_children)
                    if _local(child.tag) == following_tag
                ]
                if following:
                    insert_at = following[0]
                    break
            else:
                for prior_tag in reversed(mod_tags[:target]):
                    prior = [
                        index for index, child in enumerate(result_children)
                        if _local(child.tag) == prior_tag
                    ]
                    if prior:
                        insert_at = prior[-1] + 1
                        break
        for offset, child in enumerate(new_children):
            result.insert(insert_at + offset, copy.deepcopy(child))

    for tag, mod_children in mod_groups.items():
        if tag == "contextTags":
            existing = {
                _cd_semantic_signature(child)
                for child in result
                if _local(child.tag) == "contextTags"
            }
            additions = [
                child for child in mod_children
                if _cd_semantic_signature(child) not in existing
            ]
            if additions:
                insert_at_modified_position(tag, additions)
            continue

        result_children = list(result)
        same_indexes = [
            index for index, child in enumerate(result_children) if _local(child.tag) == tag
        ]
        if same_indexes:
            insert_at = same_indexes[0]
            for index in reversed(same_indexes):
                result.remove(result_children[index])
            for offset, child in enumerate(mod_children):
                result.insert(insert_at + offset, copy.deepcopy(child))
        else:
            insert_at_modified_position(tag, mod_children)

    return result, sorted(set(preserved))


def _cd_overlay_context_attr_update(
        base_elem: Element, modified_elem: Element) -> tuple[Element, list[str]]:
    """Overlay a context attribute without changing its immutable schema."""
    safe_modified = copy.deepcopy(modified_elem)
    immutable_fields = {"dataType", "fieldType", "key", "transient"}
    for child in list(safe_modified):
        if _local(child.tag) in immutable_fields:
            safe_modified.remove(child)
    return _cd_overlay_update(base_elem, safe_modified)


def _cd_diag_indexes(versions: Element) -> dict[str, dict[tuple, Element]]:
    """Build natural-identity indexes used by the bidirectional diagnostics UI."""
    indexes: dict[str, dict[tuple, Element]] = {
        "mapping": {}, "nodeMapping": {}, "attributeMapping": {},
        "contextNode": {}, "contextAttribute": {},
    }
    for mapping in versions.findall(_ns("contextMappings")):
        mapping_title = _child_text(mapping, "title")
        if not mapping_title:
            continue
        indexes["mapping"][(mapping_title,)] = mapping
        for node_mapping in mapping.findall(_ns("contextNodeMappings")):
            context_node = _child_text(node_mapping, "contextNode")
            obj = _child_text(node_mapping, "object")
            if not context_node or not obj:
                continue
            parent_key = (mapping_title, context_node, obj)
            indexes["nodeMapping"][parent_key] = node_mapping
            for attr_mapping in node_mapping.findall(_ns("contextAttributeMappings")):
                attr = _child_text(attr_mapping, "contextAttribute")
                if attr:
                    indexes["attributeMapping"][parent_key + (attr,)] = attr_mapping
    for context_node in versions.findall(_ns("contextNodes")):
        node_title = _child_text(context_node, "title")
        if not node_title:
            continue
        indexes["contextNode"][(node_title,)] = context_node
        for context_attr in context_node.findall(_ns("contextAttributes")):
            attr_title = _child_text(context_attr, "title")
            if attr_title:
                indexes["contextAttribute"][(node_title, attr_title)] = context_attr
    return indexes


def _cd_hydration_paths(detail: Element) -> list[list[tuple[str, str]]]:
    """Each root-to-leaf (objectName, queryAttribute) chain of a hydration detail."""
    step = (_child_text(detail, "objectName"), _child_text(detail, "queryAttribute"))
    nested = detail.findall(_ns("contextAttrHydrationDetails"))
    if not nested:
        return [[step]]
    return [[step] + tail for child in nested for tail in _cd_hydration_paths(child)]


def cd_hydration_sources(text: str) -> list[dict]:
    """
    The sObject fields a ContextDefinition hydrates from: one entry per
    root-to-leaf chain, with the destination attribute's declared dataType.
    """
    versions = _cd_get_versions(_parse(text, "Context Definition"))
    if versions is None:
        return []
    data_types = {
        (_child_text(node, "title"), _child_text(attr, "title")): _child_text(attr, "dataType")
        for node in versions.findall(_ns("contextNodes"))
        for attr in node.findall(_ns("contextAttributes"))
    }
    sources = []
    for mapping in versions.findall(_ns("contextMappings")):
        mapping_title = _child_text(mapping, "title")
        for node_mapping in mapping.findall(_ns("contextNodeMappings")):
            context_node = _child_text(node_mapping, "contextNode")
            for cam in node_mapping.findall(_ns("contextAttributeMappings")):
                attr = _child_text(cam, "contextAttribute")
                for detail in cam.findall(_ns("contextAttrHydrationDetails")):
                    for chain in _cd_hydration_paths(detail):
                        if not all(obj and field for obj, field in chain):
                            continue
                        sources.append({
                            "mapping": mapping_title,
                            "contextNode": context_node,
                            "attribute": attr,
                            "dataType": data_types.get((context_node, attr), ""),
                            "chain": chain,
                            "path": " → ".join(f"{obj}.{field}" for obj, field in chain),
                        })
    return sources


_CD_IMMUTABLE_DEFAULTS = {"dataType": "", "fieldType": "", "key": "false", "transient": "false"}


def _cd_not_applied(base_ver: Element, mod_ver: Element) -> list[dict]:
    """
    Differences the build deliberately leaves out: schema changes Salesforce
    refuses on an existing attribute, and Base content Modified no longer has
    (the tool never deletes from Base).
    """
    base_idx = _cd_diag_indexes(base_ver)
    mod_idx = _cd_diag_indexes(mod_ver)
    rows: list[dict] = []

    for key, base_ca in base_idx["contextAttribute"].items():
        mod_ca = mod_idx["contextAttribute"].get(key)
        if mod_ca is None:
            continue
        changes = []
        for field, default in _CD_IMMUTABLE_DEFAULTS.items():
            before = (_child_text(base_ca, field) or default).lower()
            after = (_child_text(mod_ca, field) or default).lower()
            if before != after:
                changes.append(f"{field} {before or '—'} → {after or '—'}")
        if changes:
            rows.append({
                "kind": "schema", "path": f"contextNodes › {key[0]} › {key[1]}",
                "detail": "; ".join(changes) + ". Salesforce does not allow changing this on an "
                          "existing attribute; Base keeps its current value."})

    def renamed_in_modified(key: tuple) -> bool:
        destination = _cd_mapping_destination(base_idx["attributeMapping"][key])
        mod_nm = mod_idx["nodeMapping"].get(key[:3])
        return destination is not None and mod_nm is not None and any(
            _cd_mapping_destination(cam) == destination
            for cam in mod_nm.findall(_ns("contextAttributeMappings")))

    def removed(kind: str, label: str, parent_kind: str | None = None, parent_len: int = 0) -> None:
        # Only the topmost missing element is listed, not each of its children.
        for key in base_idx[kind]:
            if key in mod_idx[kind]:
                continue
            if parent_kind and key[:parent_len] not in mod_idx[parent_kind]:
                continue
            if kind == "attributeMapping" and renamed_in_modified(key):
                continue
            prefix = ("contextNodes",) if kind.startswith("context") else ()
            rows.append({
                "kind": "deletion", "path": " › ".join(prefix + key),
                "detail": f"{label} is in Base but not in Modified. The tool never deletes, "
                          "so Base keeps it."})

    removed("mapping", "Context mapping")
    removed("nodeMapping", "Node mapping", "mapping", 1)
    removed("attributeMapping", "Attribute mapping", "nodeMapping", 3)
    removed("contextNode", "Context node")
    removed("contextAttribute", "Context attribute", "contextNode", 1)

    for key, base_ca in base_idx["contextAttribute"].items():
        mod_ca = mod_idx["contextAttribute"].get(key)
        if mod_ca is None:
            continue
        for tag in sorted(_cd_context_attr_tags(base_ca) - _cd_context_attr_tags(mod_ca)):
            rows.append({
                "kind": "deletion", "path": f"contextNodes › {key[0]} › {key[1]} › tag {tag}",
                "detail": "Context tag is in Base but not in Modified; Base keeps it."})
    for key, base_cam in base_idx["attributeMapping"].items():
        mod_cam = mod_idx["attributeMapping"].get(key)
        if mod_cam is None:
            continue
        for group in ("ctxAttrHydrationCtxs", "contextAttrHydrationDetails"):
            if base_cam.findall(_ns(group)) and not mod_cam.findall(_ns(group)):
                rows.append({
                    "kind": "deletion", "path": " › ".join(key) + f" › {group}",
                    "detail": "Modified removed this mapping's hydration source; Base keeps it."})
    return rows


def _cd_diag_entry(kind: str, key: tuple, elem: Element) -> dict:
    labels = {
        "mapping": "Context mapping",
        "nodeMapping": "Node mapping parent",
        "attributeMapping": "Attribute mapping",
        "contextNode": "Context node parent",
        "contextAttribute": "Context attribute",
    }
    if kind == "mapping":
        path, name = f"contextMappings[{key[0]}]", key[0]
    elif kind == "nodeMapping":
        path = f"{key[0]} / {key[1]} / {key[2]}"
        name = f"{key[1]} → {key[2]}"
    elif kind == "attributeMapping":
        path = f"{key[0]} / {key[1]} / {key[2]}"
        name = key[3]
    elif kind == "contextNode":
        path, name = f"contextNodes[{key[0]}]", key[0]
    else:
        path, name = f"contextNodes[{key[0]}]", key[1]
    detail = _cd_field_info(elem) if kind == "attributeMapping" else ""
    return {"type": labels[kind], "name": name, "path": path, "detail": detail, "count": 1}


def _cd_compare_diagnostics(base_text: str, modified_text: str,
                            base_root: Element, mod_root: Element,
                            base_ver: Element, mod_ver: Element) -> dict:
    """Explain line-count and semantic differences in both directions."""
    base_idx = _cd_diag_indexes(base_ver)
    mod_idx = _cd_diag_indexes(mod_ver)
    removed: list[dict] = []
    added: list[dict] = []
    changed: list[dict] = []

    kind_order = ("mapping", "nodeMapping", "attributeMapping",
                  "contextNode", "contextAttribute")
    for kind in kind_order:
        b_keys, m_keys = set(base_idx[kind]), set(mod_idx[kind])
        for key in sorted(b_keys - m_keys):
            removed.append(_cd_diag_entry(kind, key, base_idx[kind][key]))
        for key in sorted(m_keys - b_keys):
            added.append(_cd_diag_entry(kind, key, mod_idx[kind][key]))

    # Material changes inside identities that exist on both sides. Ignore the
    # localizationDisabled=false noise that Salesforce may omit on retrieval.
    for kind in ("attributeMapping", "contextAttribute"):
        common = set(base_idx[kind]) & set(mod_idx[kind])
        for key in sorted(common):
            before, after = base_idx[kind][key], mod_idx[kind][key]
            if _cd_semantic_signature(before) == _cd_semantic_signature(after):
                continue
            entry = _cd_diag_entry(kind, key, after)
            entry["before"] = _cd_field_info(before) if kind == "attributeMapping" else ""
            entry["after"] = _cd_field_info(after) if kind == "attributeMapping" else ""
            overlaid, preserved_fields = _cd_overlay_update(before, after)
            if _cd_semantic_signature(before) == _cd_semantic_signature(overlaid):
                entry["type"] = "Base-protected omission"
                entry["detail"] = (
                    "Modified omits "
                    + (", ".join(preserved_fields) or "Base-only metadata")
                    + "; Base value will be preserved and no update will be offered."
                )
            elif preserved_fields:
                existing_detail = entry.get("detail", "")
                protection = "Base-only " + ", ".join(preserved_fields) + " will be preserved."
                entry["detail"] = (
                    f"{existing_detail} · {protection}" if existing_detail else protection
                )
            changed.append(entry)

    def direct_leaf_values(root: Element) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}
        for child in root:
            if len(child) == 0:
                values.setdefault(_local(child.tag), []).append((child.text or "").strip())
        return values

    base_leaf, mod_leaf = direct_leaf_values(base_root), direct_leaf_values(mod_root)
    for tag in sorted(set(base_leaf) | set(mod_leaf)):
        b_values, m_values = base_leaf.get(tag, []), mod_leaf.get(tag, [])
        if b_values == m_values:
            continue
        if b_values and not m_values:
            serializer_field = tag in {"isTransformationEnabled", "releaseVersion"}
            removed.append({
                "type": "Serializer/root omission" if serializer_field else "Root field",
                "name": tag,
                "path": "ContextDefinition",
                "detail": (
                    f"{', '.join(b_values)}. This field may be normalized or omitted by "
                    "Salesforce retrieval."
                    if serializer_field else ", ".join(b_values)
                ),
                "count": len(b_values),
            })
        elif m_values and not b_values:
            added.append({"type": "Root field", "name": tag, "path": "ContextDefinition",
                          "detail": ", ".join(m_values), "count": len(m_values)})
        else:
            changed.append({"type": "Root field", "name": tag, "path": "ContextDefinition",
                            "detail": f"{', '.join(b_values)} → {', '.join(m_values)}",
                            "before": ", ".join(b_values), "after": ", ".join(m_values),
                            "count": 1})

    tracked_tags = (
        "contextMappings", "contextNodeMappings", "contextAttributeMappings",
        "contextNodes", "contextAttributes", "ctxAttrHydrationCtxs",
        "contextAttrHydrationDetails", "contextTags", "localizationDisabled",
    )
    counts = []
    for tag in tracked_tags:
        base_count = sum(1 for el in base_root.iter() if _local(el.tag) == tag)
        mod_count = sum(1 for el in mod_root.iter() if _local(el.tag) == tag)
        counts.append({"tag": tag, "base": base_count, "modified": mod_count,
                       "delta": mod_count - base_count})

    base_loc_false = sum(
        1 for el in base_root.iter()
        if _local(el.tag) == "localizationDisabled"
        and (el.text or "").strip().lower() == "false"
    )
    mod_loc_false = sum(
        1 for el in mod_root.iter()
        if _local(el.tag) == "localizationDisabled"
        and (el.text or "").strip().lower() == "false"
    )
    default_delta = base_loc_false - mod_loc_false
    if default_delta > 0:
        removed.insert(0, {
            "type": "Serializer/default omission",
            "name": "localizationDisabled=false",
            "path": "Repeated metadata entries",
            "detail": (
                f"Modified contains {default_delta} fewer explicit default-false values. "
                "Salesforce retrieval commonly omits these defaults; this is not by itself "
                "a business-metadata deletion."
            ),
            "count": default_delta,
        })
    elif default_delta < 0:
        added.insert(0, {
            "type": "Serializer/default expansion",
            "name": "localizationDisabled=false",
            "path": "Repeated metadata entries",
            "detail": f"Modified contains {-default_delta} more explicit default-false values.",
            "count": -default_delta,
        })

    base_lines = len(base_text.splitlines())
    mod_lines = len(modified_text.splitlines())
    line_delta = mod_lines - base_lines
    if line_delta < 0:
        line_summary = f"Modified has {-line_delta:,} fewer lines than Base."
    elif line_delta > 0:
        line_summary = f"Modified has {line_delta:,} more lines than Base."
    else:
        line_summary = "Base and Modified have the same number of lines."
    if default_delta > 0:
        line_summary += (
            f" It also has {default_delta:,} fewer explicit "
            "localizationDisabled=false defaults; added metadata may offset part of that reduction."
        )
    line_summary += " Use the lists below to separate serializer omissions from real metadata changes."

    return {
        "baseLines": base_lines,
        "modifiedLines": mod_lines,
        "lineDelta": line_delta,
        "baseVersion": _child_text(base_ver, "versionNumber"),
        "modifiedVersion": _child_text(mod_ver, "versionNumber"),
        "summary": line_summary,
        "removed": removed,
        "added": added,
        "changed": changed,
        "counts": counts,
        "removedCount": sum(item.get("count", 1) for item in removed),
        "addedCount": sum(item.get("count", 1) for item in added),
        "changedCount": len(changed),
        "businessRemovedCount": sum(
            item.get("count", 1) for item in removed
            if not item["type"].startswith("Serializer/")
        ),
    }


def cd_fix_analyze(base_text: str, modified_text: str) -> dict:
    """
    Scan Modified for additions and material updates relative to Base. Missing
    structural parents are returned as one selectable full-block addition.
    """
    if not base_text.strip() or not modified_text.strip():
        return {"ok": False, "log": "Paste both Base and Modified XMLs first."}
    try:
        base_root = _parse(base_text, "Base")
        mod_root  = _parse(modified_text, "Modified")
    except (ValueError, ET.ParseError) as exc:
        return {"ok": False, "log": str(exc)}
    id_findings = _cd_collect_org_id_findings(base_root, mod_root)
    _cd_rewrite_hydration_ids(base_root)
    _cd_rewrite_hydration_ids(mod_root)

    if _local(base_root.tag) != "ContextDefinition" or _local(mod_root.tag) != "ContextDefinition":
        return {"ok": False,
                "log": "Both XMLs must be ContextDefinition metadata "
                       f"(got <{_local(base_root.tag)}> and <{_local(mod_root.tag)}>)."}

    base_ver = _cd_get_versions(base_root)
    mod_ver  = _cd_get_versions(mod_root)
    if base_ver is None or mod_ver is None:
        return {"ok": False, "log": "Could not find <contextDefinitionVersions> in both files."}

    diagnostics = _cd_compare_diagnostics(
        base_text, modified_text, base_root, mod_root, base_ver, mod_ver)
    items: list[dict] = []
    refused_node_tags: list[str] = []
    base_tag_index = _cd_tag_index(base_ver)

    # ── contextMappings → contextNodeMappings → contextAttributeMappings ──────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        if not m_title:
            continue
        base_m = _cd_get_mapping(base_ver, m_title)
        if base_m is None:
            node_count = len(mod_m.findall(_ns("contextNodeMappings")))
            attr_count = sum(
                len(node.findall(_ns("contextAttributeMappings")))
                for node in mod_m.findall(_ns("contextNodeMappings"))
            )
            items.append({
                "id": f"cm\x1f{m_title}",
                "type": "mappingBlock",
                "mappingTitle": m_title,
                "attrName": m_title,
                "fieldInfo": f"{node_count} node mapping(s) · {attr_count} attribute mapping(s)",
                "includedCount": attr_count,
                "requires": _cd_dependency_ids(
                    base_ver, mod_ver, _cd_mapping_references(mod_m)),
                "group": "Required parent blocks",
                "path": f"contextMappings[{m_title}]",
                "parentPatch": True,
                "missingParent": False,
                "parentPatchMessage": (
                    f"Base does not contain mapping '{m_title}'. Step 3 will copy the complete "
                    "<contextMappings> block from Modified, including all of its node and "
                    "attribute mappings."
                ),
            })
            continue

        settings = _cd_mapping_settings_changes(base_m, mod_m)
        if settings:
            items.append({
                "id": f"ms\x1f{m_title}",
                "type": "mappingSettings",
                "mappingTitle": m_title,
                "attrName": f"{m_title} settings",
                "fieldInfo": ", ".join(field for field, _, _ in settings),
                "beforeField": "; ".join(
                    f"{field}: {before or '—'}" for field, before, _ in settings),
                "afterField": "; ".join(f"{field}: {after}" for field, _, after in settings),
                "changeKind": "update",
                "preservedBaseFields": [],
                "group": "Mapping settings",
                "path": f"contextMappings[{m_title}]",
                "parentPatch": False,
                "missingParent": False,
            })

        for mod_nm in mod_m.findall(_ns("contextNodeMappings")):
            ctx_node = _child_text(mod_nm, "contextNode")
            obj      = _child_text(mod_nm, "object")
            if not ctx_node or not obj:
                continue
            base_nm = _cd_get_node_mapping(base_m, ctx_node, obj)
            if base_nm is None:
                attr_count = len(mod_nm.findall(_ns("contextAttributeMappings")))
                items.append({
                    "id": f"nm\x1f{m_title}\x1f{ctx_node}\x1f{obj}",
                    "type": "nodeMappingBlock",
                    "mappingTitle": m_title,
                    "contextNode": ctx_node,
                    "object": obj,
                    "attrName": f"{ctx_node} / {obj}",
                    "fieldInfo": f"{attr_count} attribute mapping(s)",
                    "includedCount": attr_count,
                    "requires": _cd_dependency_ids(
                        base_ver, mod_ver, _cd_mapping_references(mod_nm)),
                    "group": "Required parent blocks",
                    "path": f"{m_title} → {ctx_node} / {obj}",
                    "parentPatch": True,
                    "missingParent": False,
                    "parentPatchMessage": (
                        f"Base mapping '{m_title}' does not contain the {ctx_node} / {obj} "
                        "node mapping. Step 3 will copy the complete <contextNodeMappings> "
                        "block from Modified, including all of its attribute mappings."
                    ),
                })
                continue

            for cam in mod_nm.findall(_ns("contextAttributeMappings")):
                attr = _child_text(cam, "contextAttribute")
                if not attr:
                    continue
                base_cam = _cd_get_attr_mapping(base_nm, attr)
                replaced_attr = ""
                if base_cam is None:
                    base_cam = _cd_get_attr_mapping_by_destination(base_nm, cam, mod_nm)
                    if base_cam is not None:
                        replaced_attr = _child_text(base_cam, "contextAttribute") or ""
                change_kind = "add"
                before_field = ""
                preserved_base_fields: list[str] = []
                if base_cam is not None:
                    overlaid_cam, preserved_base_fields = _cd_overlay_update(base_cam, cam)
                    if _cd_semantic_signature(base_cam) == _cd_semantic_signature(overlaid_cam):
                        continue
                    change_kind = "update"
                    before_field = _cd_field_info(base_cam)
                    field_info = _cd_field_info(overlaid_cam)
                    if replaced_attr:
                        before_field = f"{replaced_attr} → {before_field or 'existing XML definition'}"
                        field_info = f"{attr} → {field_info or 'modified XML definition'}"
                else:
                    field_info = _cd_field_info(cam)
                items.append({
                    "id":           f"cam\x1f{m_title}\x1f{ctx_node}\x1f{obj}\x1f{attr}",
                    "type":         "mapping",
                    "mappingTitle": m_title,
                    "contextNode":  ctx_node,
                    "object":       obj,
                    "attrName":     attr,
                    "fieldInfo":    field_info,
                    "beforeField":  before_field,
                    "afterField":   field_info,
                    "changeKind":   change_kind,
                    "replacesAttr": replaced_attr,
                    "preservedBaseFields": preserved_base_fields,
                    "requires":     _cd_dependency_ids(
                        base_ver, mod_ver, [(ctx_node, attr)] + _cd_mapping_references(cam)),
                    "group":        _cd_group_key(attr),
                    "path":         f"{m_title} → {ctx_node} / {obj}",
                    "parentPatch":  False,
                    "missingParent": False,
                })

    # ── contextNodes → contextAttributes ─────────────────────────────────────
    for mod_cn in mod_ver.findall(_ns("contextNodes")):
        cn_title = _child_text(mod_cn, "title")
        if not cn_title:
            continue
        base_cn = _cd_get_context_node(base_ver, cn_title)
        if base_cn is None:
            attr_count = len(mod_cn.findall(_ns("contextAttributes")))
            items.append({
                "id": f"cn\x1f{cn_title}",
                "type": "contextNodeBlock",
                "nodeName": cn_title,
                "attrTitle": cn_title,
                "fieldInfo": f"{attr_count} context attribute(s)",
                "includedCount": attr_count,
                "group": "Required parent blocks",
                "path": f"contextNodes[{cn_title}]",
                "parentPatch": True,
                "missingParent": False,
                "parentPatchMessage": (
                    f"Base does not contain context node '{cn_title}'. Step 3 will copy the "
                    "complete <contextNodes> block from Modified, including all of its "
                    "context attributes."
                ),
            })
            continue

        safe_tags, refused = _cd_node_tag_candidates(base_ver, mod_ver, base_cn, mod_cn)
        refused_node_tags += refused
        for context_tag in safe_tags:
            tag_title = _child_text(context_tag, "title")
            items.append({
                "id": f"nt\x1f{cn_title}\x1f{tag_title}",
                "type": "nodeTag",
                "nodeName": cn_title,
                "attrTitle": tag_title,
                "fieldInfo": "node-level context tag",
                "changeKind": "add",
                "preservedBaseFields": [],
                "group": "Node tags",
                "path": f"contextNodes[{cn_title}]",
                "parentPatch": False,
                "missingParent": False,
            })

        for ca in mod_cn.findall(_ns("contextAttributes")):
            ca_title = _child_text(ca, "title")
            if not ca_title:
                continue
            base_ca = _cd_get_context_attr(base_cn, ca_title)
            change_kind = "add"
            preserved_base_fields: list[str] = []
            if base_ca is None:
                tag_conflicts = _cd_context_tag_conflicts(base_ver, ca, index=base_tag_index)
            else:
                overlaid_ca, preserved_base_fields = _cd_overlay_context_attr_update(base_ca, ca)
                existing_tags = _cd_context_attr_tags(base_ca)
                tag_conflicts = [
                    conflict for conflict in _cd_context_tag_conflicts(
                        base_ver, overlaid_ca, ignore=base_ca, index=base_tag_index)
                    if conflict[0] not in existing_tags
                ]
                _cd_strip_conflicting_tags(
                    base_ver, overlaid_ca, ignore=base_ca, index=base_tag_index)
                if _cd_semantic_signature(base_ca) == _cd_semantic_signature(overlaid_ca):
                    continue
                change_kind = "update"

            conflict_description = ", ".join(
                f"{tag} owned by {_cd_tag_owner_label(owner_node, owner_attr)}"
                for tag, owner_node, owner_attr in tag_conflicts
            )
            items.append({
                "id":        f"ca\x1f{cn_title}\x1f{ca_title}",
                "type":      "nodeAttr",
                "nodeName":  cn_title,
                "attrTitle": ca_title,
                "fieldInfo": "",
                "beforeField": conflict_description,
                "afterField": (
                    f"{cn_title}/{ca_title} without duplicate context tag"
                    if tag_conflicts else ""
                ),
                "changeKind": change_kind,
                "conflictingTags": [tag for tag, _, _ in tag_conflicts],
                "preservedBaseFields": preserved_base_fields,
                "group":     _cd_group_key(ca_title),
                "path":      f"contextNodes[{cn_title}]",
                "parentPatch": False,
                "missingParent": False,
            })

    _cd_annotate_id_findings(diagnostics, id_findings)
    id_clause = _cd_id_findings_summary_clause(id_findings)
    if refused_node_tags:
        id_clause += (
            f" {len(refused_node_tags)} node-level tag(s) in Modified were not offered because "
            "their title is already used by another tag (Salesforce rejects duplicate tag "
            "names): " + "; ".join(refused_node_tags) + "."
        )
    not_applied = _cd_not_applied(base_ver, mod_ver) + [
        {"kind": "tag", "path": tag, "detail": "Node-level tag not offered: another tag already "
                                               "uses this title, and Salesforce rejects duplicates."}
        for tag in refused_node_tags]
    schema_count = sum(1 for row in not_applied if row["kind"] == "schema")
    deletion_count = sum(1 for row in not_applied if row["kind"] == "deletion")
    if schema_count or deletion_count:
        id_clause += (
            f" Not applied: {schema_count} attribute schema change(s) Salesforce does not "
            f"allow on existing attributes, and {deletion_count} Base item(s) Modified no "
            "longer has (the tool never deletes). See \"Not applied\" for the list."
        )

    if not items:
        return {"ok": True, "items": [],
                "summary": "No selectable additions or value changes found." + id_clause,
                "diagnostics": diagnostics,
                "refusedNodeTags": refused_node_tags,
                "notApplied": not_applied}

    release = _cd_release_info(base_root, mod_root)
    for item in items:
        if _cd_is_release_content(mod_ver, item["id"], release):
            item["releaseContent"] = True
            item["group"] = release["group"]
    items.sort(key=lambda item: bool(item.get("releaseContent")))
    release_count = sum(1 for item in items if item.get("releaseContent"))

    parent_blocks = sum(1 for item in items if item.get("parentPatch"))
    updates = sum(1 for item in items if item.get("changeKind") == "update")
    additions = len(items) - updates
    summary = (
        f"Found {additions} selectable addition(s) and {updates} value change(s) "
        "in Modified."
    )
    if parent_blocks:
        summary += f" {parent_blocks} will add a complete required parent block."
    if release_count:
        summary += (
            f" {release_count} item(s) are standard elements of {release['parent']} "
            f"version {release['modified']}, but Base inherits version {release['base']}. "
            "They are not selected: Base gets them when its org is upgraded, and copying "
            "them earlier can fail because the fields they read may not exist there yet."
        )
    return {"ok": True, "items": items,
            "summary": summary + id_clause,
            "diagnostics": diagnostics,
            "refusedNodeTags": refused_node_tags,
            "notApplied": not_applied,
            "release": release}


def _cd_expand_selection(base_ver: Element, mod_ver: Element, selected: set[str]) -> set[str]:
    """
    Add the context node / attribute items that selected mappings reference but
    Base lacks, so no attribute mapping is written without its attribute.
    Returns the ids that were added.
    """
    added: set[str] = set()
    for item_id in list(selected):
        parts = item_id.split("\x1f")
        kind = parts[0]
        refs: list[tuple[str, str]] = []
        if kind == "cm" and len(parts) == 2:
            mod_m = _cd_get_mapping(mod_ver, parts[1])
            if mod_m is not None:
                refs = _cd_mapping_references(mod_m)
        elif kind == "nm" and len(parts) == 4:
            mod_m = _cd_get_mapping(mod_ver, parts[1])
            mod_nm = _cd_get_node_mapping(mod_m, parts[2], parts[3]) if mod_m is not None else None
            if mod_nm is not None:
                refs = _cd_mapping_references(mod_nm)
        elif kind == "cam" and len(parts) == 5:
            refs = [(parts[2], parts[4])]
            mod_m = _cd_get_mapping(mod_ver, parts[1])
            mod_nm = _cd_get_node_mapping(mod_m, parts[2], parts[3]) if mod_m is not None else None
            mod_cam = _cd_get_attr_mapping(mod_nm, parts[4]) if mod_nm is not None else None
            if mod_cam is not None:
                refs += _cd_mapping_references(mod_cam)
        for dep in _cd_dependency_ids(base_ver, mod_ver, refs):
            if dep not in selected:
                selected.add(dep)
                added.add(dep)
    return added


def cd_fix_build(base_text: str, modified_text: str, selected_ids: list,
                 provenance: dict | None = None) -> dict:
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
    preserve_mapped_keys = _cd_node_mapping_keys(base_root)
    developer_name = (
        _cd_context_definition_developer_name(base_root)
        or _cd_context_definition_developer_name(mod_root)
    )
    rewritten_hydration = [
        {**item, "origin": "Modified"} for item in _cd_rewrite_hydration_ids(mod_root)]

    base_ver = _cd_get_versions(base_root)
    mod_ver  = _cd_get_versions(mod_root)
    if base_ver is None or mod_ver is None:
        return {"ok": False, "log": "Could not find <contextDefinitionVersions>."}

    base_issues = cd_validate_structure(base_root)
    not_applied = _cd_not_applied(base_ver, mod_ver)
    selected = set(selected_ids)
    dependency_ids = _cd_expand_selection(base_ver, mod_ver, selected)
    release = _cd_release_info(base_root, mod_root)
    release_ids = [
        item_id for item_id in list(dict.fromkeys(selected_ids)) + sorted(dependency_ids)
        if _cd_is_release_content(mod_ver, item_id, release)
    ]
    provenance = _cd_clean_provenance(provenance)
    report_lines = ["CONTEXT DEFINITION FIX — APPLY REPORT", "=" * 60, ""]
    report_lines += _cd_provenance_lines(provenance, base_root, mod_root)
    applied = skipped = parent_blocks = updated = 0
    errs: list[str] = []

    def attr_available(ctx_node: str, attr: str) -> bool:
        base_cn = _cd_get_context_node(base_ver, ctx_node)
        if base_cn is not None and _cd_get_context_attr(base_cn, attr) is not None:
            return True
        mod_cn = _cd_get_context_node(mod_ver, ctx_node)
        if mod_cn is None or _cd_get_context_attr(mod_cn, attr) is None:
            return False
        return (f"cn\x1f{ctx_node}" in selected and base_cn is None) or (
            f"ca\x1f{ctx_node}\x1f{attr}" in selected and base_cn is not None)

    # ── complete contextMappings blocks ───────────────────────────────────────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        item_id = f"cm\x1f{m_title}"
        if item_id not in selected:
            continue
        if _cd_get_mapping(base_ver, m_title) is not None:
            report_lines.append(f"  ✓ parent block already present: contextMappings[{m_title}]")
            skipped += 1
            continue
        children = list(base_ver)
        last_mapping = max(
            (i for i, child in enumerate(children) if _local(child.tag) == "contextMappings"),
            default=-1,
        )
        base_ver.insert(last_mapping + 1, copy.deepcopy(mod_m))
        node_count = len(mod_m.findall(_ns("contextNodeMappings")))
        attr_count = sum(
            len(node.findall(_ns("contextAttributeMappings")))
            for node in mod_m.findall(_ns("contextNodeMappings"))
        )
        report_lines.append(
            f"  + added parent block: contextMappings[{m_title}] "
            f"({node_count} node mapping(s), {attr_count} attribute mapping(s))"
        )
        applied += 1
        parent_blocks += 1

    # ── complete contextNodeMappings blocks ──────────────────────────────────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        for mod_nm in mod_m.findall(_ns("contextNodeMappings")):
            ctx_node = _child_text(mod_nm, "contextNode")
            obj = _child_text(mod_nm, "object")
            item_id = f"nm\x1f{m_title}\x1f{ctx_node}\x1f{obj}"
            if item_id not in selected:
                continue
            base_m = _cd_get_mapping(base_ver, m_title)
            if base_m is None:
                errs.append(
                    f"  ✗ parent mapping unavailable: contextMappings[{m_title}] "
                    f"for {ctx_node}/{obj}"
                )
                skipped += 1
                continue
            if _cd_get_node_mapping(base_m, ctx_node, obj) is not None:
                report_lines.append(
                    f"  ✓ parent block already present: {m_title}/{ctx_node}/{obj}"
                )
                skipped += 1
                continue
            children = list(base_m)
            insert_at = next(
                (i for i, child in enumerate(children)
                 if _local(child.tag) in {"default", "description", "inheritedFrom", "title"}),
                len(children),
            )
            base_m.insert(insert_at, copy.deepcopy(mod_nm))
            attr_count = len(mod_nm.findall(_ns("contextAttributeMappings")))
            report_lines.append(
                f"  + added parent block: {m_title}/{ctx_node}/{obj} "
                f"({attr_count} attribute mapping(s))"
            )
            applied += 1
            parent_blocks += 1

    # ── complete contextNodes blocks ─────────────────────────────────────────
    for mod_cn in mod_ver.findall(_ns("contextNodes")):
        cn_title = _child_text(mod_cn, "title")
        item_id = f"cn\x1f{cn_title}"
        if item_id not in selected:
            continue
        if _cd_get_context_node(base_ver, cn_title) is not None:
            report_lines.append(f"  ✓ parent block already present: contextNodes[{cn_title}]")
            skipped += 1
            continue
        new_cn = copy.deepcopy(mod_cn)
        dropped_tags: list[str] = []
        kept_tags: set[str] = set()
        for tag_owner in new_cn.findall(_ns("contextAttributes")) + [new_cn]:
            dropped_tags += _cd_strip_conflicting_tags(base_ver, tag_owner)
            for context_tag in list(tag_owner.findall(_ns("contextTags"))):
                tag_title = _child_text(context_tag, "title")
                if tag_title in kept_tags:
                    tag_owner.remove(context_tag)
                    dropped_tags.append(f"{tag_title} (repeated inside Modified {cn_title})")
                else:
                    kept_tags.add(tag_title)
        children = list(base_ver)
        last_node = max(
            (i for i, child in enumerate(children) if _local(child.tag) == "contextNodes"),
            default=-1,
        )
        base_ver.insert(last_node + 1, new_cn)
        attr_count = len(mod_cn.findall(_ns("contextAttributes")))
        report_lines.append(
            f"  + added parent block: contextNodes[{cn_title}] "
            f"({attr_count} context attribute(s))"
            + (f"; dropped duplicate tag(s): {', '.join(dropped_tags)}" if dropped_tags else "")
            + ("  (required by a selected mapping)" if item_id in dependency_ids else "")
        )
        applied += 1
        parent_blocks += 1

    # ── mapping settings (intents, default, description) ─────────────────────
    for mod_m in mod_ver.findall(_ns("contextMappings")):
        m_title = _child_text(mod_m, "title")
        if f"ms\x1f{m_title}" not in selected:
            continue
        base_m = _cd_get_mapping(base_ver, m_title)
        if base_m is None:
            errs.append(f"  ✗ contextMappings[{m_title}] not found in Base — skipped its settings")
            skipped += 1
            continue
        changes = _cd_mapping_settings_changes(base_m, mod_m)
        if not changes:
            report_lines.append(f"  ✓ mapping settings already match: {m_title}")
            skipped += 1
            continue
        notes: list[str] = []
        for field, _, after in changes:
            if field == "intent":
                intent = ET.Element(_ns("contextMappingIntents"))
                ET.SubElement(intent, _ns("mappingIntent")).text = after
                _cd_insert_in_order(base_m, intent, _CD_MAPPING_FIELD_ORDER)
                notes.append(f"intent {after}")
            elif field == "default":
                for other in base_ver.findall(_ns("contextMappings")):
                    if other is not base_m and (_child_text(other, "default") or "").lower() == "true":
                        _cd_set_scalar(other, "default", "false", _CD_MAPPING_FIELD_ORDER)
                        notes.append(f"default moved from {_child_text(other, 'title')}")
                _cd_set_scalar(base_m, "default", "true", _CD_MAPPING_FIELD_ORDER)
                if not any(note.startswith("default moved") for note in notes):
                    notes.append("default=true")
            else:
                _cd_set_scalar(base_m, field, after, _CD_MAPPING_FIELD_ORDER)
                notes.append(field)
        report_lines.append(f"  ~ updated mapping settings: {m_title}  ({', '.join(notes)})")
        applied += 1
        updated += 1

    # ── node-level contextTags ───────────────────────────────────────────────
    for mod_cn in mod_ver.findall(_ns("contextNodes")):
        cn_title = _child_text(mod_cn, "title")
        for context_tag in mod_cn.findall(_ns("contextTags")):
            tag_title = _child_text(context_tag, "title")
            if f"nt\x1f{cn_title}\x1f{tag_title}" not in selected:
                continue
            base_cn = _cd_get_context_node(base_ver, cn_title)
            if base_cn is None:
                errs.append(f"  ✗ contextNodes[{cn_title}] not found in Base — skipped tag {tag_title}")
                skipped += 1
                continue
            if tag_title in _cd_context_attr_tags(base_cn):
                report_lines.append(f"  ✓ node tag already present: {tag_title}  [contextNodes/{cn_title}]")
                skipped += 1
                continue
            new_tag = copy.deepcopy(context_tag)
            probe = ET.Element(_ns("contextNodes"))
            probe.append(new_tag)
            owners = _cd_context_tag_conflicts(base_ver, probe)
            if owners:
                errs.append(
                    f"  ✗ blocked node tag {tag_title}  [contextNodes/{cn_title}]  — already "
                    "used by " + ", ".join(sorted({_cd_tag_owner_label(n, a) for _, n, a in owners}))
                    + "; Salesforce rejects duplicate tag names"
                )
                skipped += 1
                continue
            probe.remove(new_tag)
            _cd_insert_in_order(base_cn, new_tag, _CD_NODE_FIELD_ORDER)
            report_lines.append(f"  + added node tag: {tag_title}  [contextNodes/{cn_title}]")
            applied += 1

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
                if not attr_available(ctx_node, attr):
                    errs.append(
                        f"  ✗ skipped mapping {attr}  [{m_title}/{ctx_node}/{obj}]  — context "
                        f"attribute {ctx_node}/{attr} exists in neither Base nor Modified, "
                        "so the mapping would point at nothing"
                    )
                    skipped += 1
                    continue
                base_cam = _cd_get_attr_mapping(base_nm, attr)
                replaced_attr = ""
                if base_cam is None:
                    base_cam = _cd_get_attr_mapping_by_destination(base_nm, cam, mod_nm)
                    if base_cam is not None:
                        replaced_attr = _child_text(base_cam, "contextAttribute") or ""
                if base_cam is not None:
                    overlaid_cam, preserved_fields = _cd_overlay_update(base_cam, cam)
                    if _cd_semantic_signature(base_cam) == _cd_semantic_signature(overlaid_cam):
                        report_lines.append(
                            f"  ✓ no non-destructive change: {attr}  "
                            f"[{m_title}/{ctx_node}/{obj}]"
                        )
                        skipped += 1
                        continue
                    before_field = _cd_field_info(base_cam) or "existing XML definition"
                    after_field = _cd_field_info(overlaid_cam) or "modified XML definition"
                    replace_at = list(base_nm).index(base_cam)
                    base_nm[replace_at] = overlaid_cam
                    preserved_note = (
                        f"; preserved Base-only: {', '.join(preserved_fields)}"
                        if preserved_fields else ""
                    )
                    if replaced_attr:
                        report_lines.append(
                            f"  ~ replaced mapping: {replaced_attr} -> {attr}  "
                            f"[{m_title}/{ctx_node}/{obj}]  "
                            f"destination: {after_field}{preserved_note}"
                        )
                    else:
                        report_lines.append(
                            f"  ~ updated: {attr}  [{m_title}/{ctx_node}/{obj}]  "
                            f"{before_field} -> {after_field}{preserved_note}"
                        )
                    applied += 1
                    updated += 1
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
            base_ca = _cd_get_context_attr(base_cn, ca_title)
            if base_ca is not None:
                overlaid_ca, preserved_fields = _cd_overlay_context_attr_update(base_ca, ca)
                dropped_tags = _cd_strip_conflicting_tags(base_ver, overlaid_ca, ignore=base_ca)
                if _cd_semantic_signature(base_ca) == _cd_semantic_signature(overlaid_ca):
                    report_lines.append(
                        f"  ✓ no non-destructive change: {ca_title}  "
                        f"[contextNodes/{cn_title}]"
                    )
                    skipped += 1
                    continue
                replace_at = list(base_cn).index(base_ca)
                base_cn[replace_at] = overlaid_ca
                preserved_note = (
                    f"; preserved Base-only: {', '.join(preserved_fields)}"
                    if preserved_fields else ""
                )
                if dropped_tags:
                    preserved_note += (
                        f"; kept existing tag owner(s): {', '.join(dropped_tags)}")
                report_lines.append(
                    f"  ~ updated: {ca_title}  [contextNodes/{cn_title}]"
                    f"{preserved_note}"
                )
                applied += 1
                updated += 1
                continue

            new_ca = copy.deepcopy(ca)
            dropped_tags = _cd_strip_conflicting_tags(base_ver, new_ca)
            children = list(base_cn)
            last_ca = max((i for i, ch in enumerate(children)
                           if _local(ch.tag) == "contextAttributes"), default=-1)
            base_cn.insert(last_ca + 1, new_ca)
            required_note = (
                "  (required by a selected mapping)" if item_id in dependency_ids else "")
            if dropped_tags:
                report_lines.append(
                    f"  + added without duplicate tag: {ca_title}  "
                    f"[contextNodes/{cn_title}]  preserved Base tag owner(s): "
                    f"{', '.join(dropped_tags)}{required_note}"
                )
            else:
                report_lines.append(
                    f"  + added: {ca_title}  [contextNodes/{cn_title}]{required_note}")
            applied += 1

    normalization = _cd_normalize_serializer_fields(base_root)
    normalized_defaults = normalization["localizationDefaults"]
    normalized_root_fields = normalization["rootFields"]
    if normalized_defaults:
        report_lines += [
            "",
            f"  ✓ normalized: omitted {normalized_defaults} explicit "
            "localizationDisabled=false serializer default(s)",
        ]
    if normalized_root_fields:
        report_lines.append(
            "  ✓ normalized: omitted API-incompatible root field(s): "
            + ", ".join(normalized_root_fields)
        )
    rewritten_hydration.extend(
        {**item, "origin": "result"} for item in _cd_rewrite_hydration_ids(base_root))
    mapped_id_fixes = _cd_rewrite_mapped_context_definition_ids(
        base_root, preserve_mapped_keys, developer_name)
    omitted_hydration_ids = [
        item["fromValue"] for item in rewritten_hydration
        if item["action"] in {"rewrite", "omit"}
    ]
    if rewritten_hydration:
        report_lines.append(
            f"  ✓ normalized: rewrote {len(rewritten_hydration)} "
            "hydration Id(s) to portable query-attribute name(s)"
        )
        for item in rewritten_hydration:
            report_lines.append(
                f"      [{item['origin']}] {item['path']}: {item['fromValue']} → "
                f"{item['toValue'] or '(omitted — no matching context attribute)'}"
            )
    preserved_mapped = [item for item in mapped_id_fixes if item["action"] == "preserve"]
    rewritten_mapped = [item for item in mapped_id_fixes if item["action"] == "rewrite"]
    if preserved_mapped:
        report_lines.append(
            f"  ✓ normalized: kept {len(preserved_mapped)} existing "
            "mappedContextDefinition Id(s) (Salesforce rejects renaming them)"
        )
    if rewritten_mapped:
        report_lines.append(
            f"  ✓ normalized: rewrote {len(rewritten_mapped)} "
            "mappedContextDefinition Id(s) on newly added node mapping(s)"
        )

    result_text = serialize_tree(base_root)
    result_issues = cd_validate_structure(ET.fromstring(result_text.encode("utf-8")))
    base_issue_set = set(base_issues)
    new_issues = [issue for issue in result_issues if issue not in base_issue_set]
    inherited_issues = [issue for issue in result_issues if issue in base_issue_set]
    errs += [f"  ✗ invalid result: {issue}" for issue in new_issues]
    if inherited_issues:
        report_lines += [
            "",
            f"Warnings — {len(inherited_issues)} issue(s) already present in Base "
            "(not introduced by this build; Salesforce will reject them on deploy):",
        ] + [f"  ⚠ {issue}" for issue in inherited_issues]
    if release_ids:
        report_lines += [
            "",
            f"Warnings — {len(release_ids)} applied item(s) are standard elements of "
            f"{release['parent']} version {release['modified']}; Base inherits version "
            f"{release['base']}. Base gets them when its org is upgraded. Deploying them "
            "earlier can fail if the fields they read do not exist in that org yet:",
        ] + [f"  ⚠ {item_id.replace(chr(31), ' / ')}" for item_id in release_ids]
    if not_applied:
        report_lines += [
            "",
            f"Not applied — {len(not_applied)} difference(s) in Modified the build leaves out "
            "on purpose:",
        ] + [f"  – {row['path']}: {row['detail']}" for row in not_applied]

    added = applied - updated
    report_lines += [
        "",
        f"Summary: {added} added · {updated} updated · "
        f"{skipped} skipped · {len(errs)} error(s)",
    ]
    if errs:
        report_lines += ["", "Errors:"] + errs

    return {
        "ok":      True,
        "result":  result_text,
        "validationIssues": new_issues,
        "baseIssues": inherited_issues,
        "report":  "\n".join(report_lines),
        "applied": applied,
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "errors":  len(errs),
        "parentBlocks": parent_blocks,
        "normalizedDefaults": normalized_defaults,
        "normalizedRootFields": normalized_root_fields,
        "omittedHydrationIds": len(omitted_hydration_ids),
        "rewrittenHydrationIds": len(rewritten_hydration),
        "preservedMappedContextDefinitionIds": len(preserved_mapped),
        "rewrittenMappedContextDefinitionIds": len(rewritten_mapped),
        "releaseContentIds": release_ids,
        "developerName": developer_name,
        "provenance": provenance,
        "notApplied": not_applied,
    }
