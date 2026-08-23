#!/usr/bin/env python3
"""
patch_ref_product_category.py

Surgically patches the QA org context definition to add ONLY the
Reference_Product_Category__c field mappings from tigerDev.

Changes applied:
  1. contextMappings[OrderEntitiesMapping] → contextNodeMappings[SalesTransactionItem/OrderItem]
       add contextAttributeMappings for ReferenceProductCategory__c
  2. contextMappings[SalesTransactionToAssetMapping] → contextNodeMappings[SalesTransactionItem/AssetActionSource]
       add contextAttributeMappings for ReferenceProductCategory__c
  3. contextMappings[AssetToSalesTransactionMapping] → contextNodeMappings[AssetActionSource/SalesTransactionItem]
       add contextAttributeMappings for AASReferenceProductCategory__c
  4. contextNodes[SalesTransactionItem]
       add contextAttributes for ReferenceProductCategory__c
  5. contextNodes[AssetActionSource]
       add contextAttributes for AASReferenceProductCategory__c

Everything else from QA is kept as-is.
"""

from __future__ import annotations
import copy
import sys
from pathlib import Path
from xml.etree.ElementTree import Element
import xml.etree.ElementTree as ET

# ── namespace ──────────────────────────────────────────────────────────────────
NS  = "http://soap.sforce.com/2006/04/metadata"
NSP = f"{{{NS}}}"
ET.register_namespace("", NS)


def ns(name: str) -> str:
    return f"{NSP}{name}"


def child_text(elem: Element, name: str) -> str:
    c = elem.find(ns(name))
    if c is None:
        c = elem.find(name)
    return (c.text or "").strip() if c is not None else ""


# ── finders ───────────────────────────────────────────────────────────────────

def get_versions(root: Element) -> Element:
    v = root.find(ns("contextDefinitionVersions"))
    if v is None:
        raise ValueError("Could not find <contextDefinitionVersions>")
    return v


def get_mapping(versions: Element, title: str) -> Element:
    for cm in versions.findall(ns("contextMappings")):
        if child_text(cm, "title") == title:
            return cm
    raise ValueError(f"contextMappings with title '{title}' not found")


def get_node_mapping(mapping: Element, ctx_node: str, obj: str) -> Element:
    for nm in mapping.findall(ns("contextNodeMappings")):
        if child_text(nm, "contextNode") == ctx_node and child_text(nm, "object") == obj:
            return nm
    raise ValueError(
        f"contextNodeMappings contextNode='{ctx_node}' object='{obj}' not found"
    )


def get_attr_mapping(node_mapping: Element, attr_name: str) -> Element | None:
    for cam in node_mapping.findall(ns("contextAttributeMappings")):
        if child_text(cam, "contextAttribute") == attr_name:
            return cam
    return None


def get_context_node(versions: Element, title: str) -> Element:
    for cn in versions.findall(ns("contextNodes")):
        if child_text(cn, "title") == title:
            return cn
    raise ValueError(f"contextNodes with title '{title}' not found")


def get_context_attr(context_node: Element, title: str) -> Element | None:
    for ca in context_node.findall(ns("contextAttributes")):
        if child_text(ca, "title") == title:
            return ca
    return None


# ── inserter helpers ──────────────────────────────────────────────────────────

def insert_attr_mapping_before_contextnode(node_mapping: Element, new_cam: Element) -> None:
    """Insert new_cam just before the first <contextNode> child."""
    children = list(node_mapping)
    for i, ch in enumerate(children):
        if ch.tag in (ns("contextNode"), "contextNode"):
            node_mapping.insert(i, new_cam)
            return
    node_mapping.append(new_cam)


def insert_context_attr_after_last(context_node: Element, new_ca: Element) -> None:
    """Insert new_ca immediately after the last existing <contextAttributes> child."""
    children = list(context_node)
    last_idx = -1
    for i, ch in enumerate(children):
        if ch.tag in (ns("contextAttributes"), "contextAttributes"):
            last_idx = i
    if last_idx >= 0:
        context_node.insert(last_idx + 1, new_ca)
    else:
        # Fallback: insert before <contextTags>
        for i, ch in enumerate(children):
            if ch.tag in (ns("contextTags"), "contextTags"):
                context_node.insert(i, new_ca)
                return
        context_node.append(new_ca)


# ── new element builders ──────────────────────────────────────────────────────

def make_cam_order_item() -> Element:
    """
    <contextAttributeMappings>
        <contextAttrHydrationDetails>
            <objectName>OrderItem</objectName>
            <queryAttribute>Reference_Product_Category__c</queryAttribute>
        </contextAttrHydrationDetails>
        <contextAttribute>ReferenceProductCategory__c</contextAttribute>
        <contextInputAttributeName>ReferenceProductCategory__c</contextInputAttributeName>
    </contextAttributeMappings>
    """
    cam = Element(ns("contextAttributeMappings"))
    hd  = ET.SubElement(cam, ns("contextAttrHydrationDetails"))
    ET.SubElement(hd, ns("objectName")).text = "OrderItem"
    ET.SubElement(hd, ns("queryAttribute")).text = "Reference_Product_Category__c"
    ET.SubElement(cam, ns("contextAttribute")).text = "ReferenceProductCategory__c"
    ET.SubElement(cam, ns("contextInputAttributeName")).text = "ReferenceProductCategory__c"
    return cam


def make_cam_sti_to_aas() -> Element:
    """
    <contextAttributeMappings>
        <contextAttribute>ReferenceProductCategory__c</contextAttribute>
        <contextInputAttributeName>ReferenceProductCategory__c</contextInputAttributeName>
        <ctxAttrHydrationCtxs>
            <contextQueryAttribute>AssetActionSource_QA_DE_AASReferenceProductCategory__c</contextQueryAttribute>
        </ctxAttrHydrationCtxs>
    </contextAttributeMappings>
    """
    cam = Element(ns("contextAttributeMappings"))
    ET.SubElement(cam, ns("contextAttribute")).text = "ReferenceProductCategory__c"
    ET.SubElement(cam, ns("contextInputAttributeName")).text = "ReferenceProductCategory__c"
    ctxs = ET.SubElement(cam, ns("ctxAttrHydrationCtxs"))
    ET.SubElement(ctxs, ns("contextQueryAttribute")).text = (
        "AssetActionSource_QA_DE_AASReferenceProductCategory__c"
    )
    return cam


def make_cam_aas_to_sti() -> Element:
    """
    <contextAttributeMappings>
        <contextAttribute>AASReferenceProductCategory__c</contextAttribute>
        <contextInputAttributeName>AASReferenceProductCategory__c</contextInputAttributeName>
        <ctxAttrHydrationCtxs>
            <contextQueryAttribute>SalesTransactionItem_QA_DE_ReferenceProductCategory__c</contextQueryAttribute>
        </ctxAttrHydrationCtxs>
    </contextAttributeMappings>
    """
    cam = Element(ns("contextAttributeMappings"))
    ET.SubElement(cam, ns("contextAttribute")).text = "AASReferenceProductCategory__c"
    ET.SubElement(cam, ns("contextInputAttributeName")).text = "AASReferenceProductCategory__c"
    ctxs = ET.SubElement(cam, ns("ctxAttrHydrationCtxs"))
    ET.SubElement(ctxs, ns("contextQueryAttribute")).text = (
        "SalesTransactionItem_QA_DE_ReferenceProductCategory__c"
    )
    return cam


def make_context_attr(title: str) -> Element:
    """
    <contextAttributes>
        <contextTags>
            <title>{title}</title>
        </contextTags>
        <customMappingAllowed>false</customMappingAllowed>
        <dataType>string</dataType>
        <fieldType>inputoutput</fieldType>
        <key>false</key>
        <localizationDisabled>false</localizationDisabled>
        <title>{title}</title>
        <transient>false</transient>
        <value>false</value>
    </contextAttributes>
    """
    ca = Element(ns("contextAttributes"))
    ct = ET.SubElement(ca, ns("contextTags"))
    ET.SubElement(ct, ns("title")).text = title
    ET.SubElement(ca, ns("customMappingAllowed")).text = "false"
    ET.SubElement(ca, ns("dataType")).text = "string"
    ET.SubElement(ca, ns("fieldType")).text = "inputoutput"
    ET.SubElement(ca, ns("key")).text = "false"
    ET.SubElement(ca, ns("localizationDisabled")).text = "false"
    ET.SubElement(ca, ns("title")).text = title
    ET.SubElement(ca, ns("transient")).text = "false"
    ET.SubElement(ca, ns("value")).text = "false"
    return ca


# ── indent helper ─────────────────────────────────────────────────────────────

def _indent(elem: Element, indent: str = "    ", level: int = 0) -> None:
    """Recursively add whitespace indentation to an element tree."""
    pad  = "\n" + indent * level
    cpad = "\n" + indent * (level + 1)
    children = list(elem)
    if children:
        if not (elem.text and elem.text.strip()):
            elem.text = cpad
        for i, child in enumerate(children):
            _indent(child, indent, level + 1)
            if i < len(children) - 1:
                child.tail = cpad
            else:
                child.tail = pad
    else:
        if not (elem.text and elem.text.strip()):
            elem.text = None


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    base_dir = Path(__file__).parent.parent

    qa_path  = base_dir / "force-app/main/default/contextDefinitions/qaOrgSalesTrans_CD.xml"
    out_path = base_dir / "force-app/main/default/contextDefinitions/SalesTransactionContextExt.contextDefinition-meta.xml"

    print(f"Reading QA base: {qa_path}")
    tree = ET.parse(qa_path)
    root = tree.getroot()
    versions = get_versions(root)

    changes = 0

    # ── 1. OrderEntitiesMapping → SalesTransactionItem / OrderItem ────────────
    print("\n[1] OrderEntitiesMapping → SalesTransactionItem/OrderItem")
    try:
        om  = get_mapping(versions, "OrderEntitiesMapping")
        nm1 = get_node_mapping(om, "SalesTransactionItem", "OrderItem")
        if get_attr_mapping(nm1, "ReferenceProductCategory__c"):
            print("    ✓ Already present – skipping")
        else:
            insert_attr_mapping_before_contextnode(nm1, make_cam_order_item())
            print("    + Added ReferenceProductCategory__c mapping (OrderItem.Reference_Product_Category__c)")
            changes += 1
    except ValueError as e:
        print(f"    ✗ {e}")

    # ── 2. SalesTransactionToAssetMapping → SalesTransactionItem / AssetActionSource
    print("\n[2] SalesTransactionToAssetMapping → SalesTransactionItem/AssetActionSource")
    try:
        stam = get_mapping(versions, "SalesTransactionToAssetMapping")
        nm2  = get_node_mapping(stam, "SalesTransactionItem", "AssetActionSource")
        if get_attr_mapping(nm2, "ReferenceProductCategory__c"):
            print("    ✓ Already present – skipping")
        else:
            insert_attr_mapping_before_contextnode(nm2, make_cam_sti_to_aas())
            print("    + Added ReferenceProductCategory__c mapping (SalesTransactionItem → AssetActionSource)")
            changes += 1
    except ValueError as e:
        print(f"    ✗ {e}")

    # ── 3. AssetToSalesTransactionMapping → AssetActionSource / SalesTransactionItem
    print("\n[3] AssetToSalesTransactionMapping → AssetActionSource/SalesTransactionItem")
    try:
        atsm = get_mapping(versions, "AssetToSalesTransactionMapping")
        nm3  = get_node_mapping(atsm, "AssetActionSource", "SalesTransactionItem")
        if get_attr_mapping(nm3, "AASReferenceProductCategory__c"):
            print("    ✓ Already present – skipping")
        else:
            insert_attr_mapping_before_contextnode(nm3, make_cam_aas_to_sti())
            print("    + Added AASReferenceProductCategory__c mapping (AssetActionSource → SalesTransactionItem)")
            changes += 1
    except ValueError as e:
        print(f"    ✗ {e}")

    # ── 4. contextNodes[SalesTransactionItem] → contextAttributes ─────────────
    print("\n[4] contextNodes[SalesTransactionItem] → contextAttributes")
    try:
        sti_node = get_context_node(versions, "SalesTransactionItem")
        if get_context_attr(sti_node, "ReferenceProductCategory__c"):
            print("    ✓ Already present – skipping")
        else:
            insert_context_attr_after_last(sti_node, make_context_attr("ReferenceProductCategory__c"))
            print("    + Added contextAttributes ReferenceProductCategory__c to SalesTransactionItem node")
            changes += 1
    except ValueError as e:
        print(f"    ✗ {e}")

    # ── 5. contextNodes[AssetActionSource] → contextAttributes ────────────────
    print("\n[5] contextNodes[AssetActionSource] → contextAttributes")
    try:
        aas_node = get_context_node(versions, "AssetActionSource")
        if get_context_attr(aas_node, "AASReferenceProductCategory__c"):
            print("    ✓ Already present – skipping")
        else:
            insert_context_attr_after_last(aas_node, make_context_attr("AASReferenceProductCategory__c"))
            print("    + Added contextAttributes AASReferenceProductCategory__c to AssetActionSource node")
            changes += 1
    except ValueError as e:
        print(f"    ✗ {e}")

    # ── write output ──────────────────────────────────────────────────────────
    if changes == 0:
        print("\nNo changes needed – output file would be identical to QA base.")
        sys.exit(0)

    print(f"\nApplied {changes}/5 change(s). Writing output to:\n  {out_path}")

    # Indent the entire tree so the output is human-readable
    _indent(root, indent="    ", level=0)
    root.text = "\n    "   # first child starts on its own line

    tree.write(str(out_path), encoding="UTF-8", xml_declaration=True)
    print("Done.")


if __name__ == "__main__":
    main()
