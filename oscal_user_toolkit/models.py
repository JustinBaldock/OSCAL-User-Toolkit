"""
models.py — Pure data helpers, no GUI dependencies.
Handles loading/parsing OSCAL catalog, profile, and SSP files,
plus utility functions used across the app.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def get_prop(props, name, default="—"):
    for p in props:
        if p.get("name") == name:
            return p.get("value", default)
    return default

def get_all_props(props, name):
    return [p.get("value", "") for p in props if p.get("name") == name]

def get_statement(parts):
    for part in parts:
        if part.get("name") == "statement":
            return part.get("prose", "").strip()
    return ""

def collect_controls(obj, parent_titles=None):
    if parent_titles is None:
        parent_titles = []
    result = []
    title = obj.get("title", "")
    path = parent_titles + ([title] if title else [])
    for ctrl in obj.get("controls", []):
        props = ctrl.get("props", [])
        ctrl_id = ctrl.get("id", "")
        label = get_prop(props, "label", default=None) or ctrl_id
        result.append({
            "id":              ctrl_id,
            "label":           label,
            "class":           ctrl.get("class", ""),
            "title":           ctrl.get("title", ""),
            "statement":       get_statement(ctrl.get("parts", [])),
            "applicability":   get_all_props(props, "applicability"),
            "revision":        get_prop(props, "revision"),
            "updated":         get_prop(props, "updated"),
            "essential_eight": get_prop(props, "essential-eight-applicability"),
            "path":            " › ".join(path),
        })
    for grp in obj.get("groups", []):
        result.extend(collect_controls(grp, path))
    return result

def load_catalog(filepath):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "catalog" not in data:
        raise ValueError("Missing 'catalog' key — not an OSCAL catalog.")
    catalog = data["catalog"]
    meta = catalog.get("metadata", {})
    return {
        "title":         meta.get("title", "Untitled catalog"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        "controls":      collect_controls(catalog),
        "filepath":      filepath,
    }

def load_profile(filepath):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "profile" not in data:
        raise ValueError("Missing 'profile' key — not an OSCAL profile.")
    profile = data["profile"]
    meta = profile.get("metadata", {})
    included_ids = set()
    for imp in profile.get("imports", []):
        for selector in imp.get("include-controls", []):
            for ctrl_id in selector.get("with-ids", []):
                included_ids.add(ctrl_id)
    return {
        "title":         meta.get("title", "Untitled profile"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        "ids":           included_ids,
        "filepath":      filepath,
    }

def empty_ssp():
    return {
        "uuid": new_uuid(), "title": "", "version": "1.0",
        "date_authorized": "", "system_name": "", "system_name_short": "",
        "system_description": "", "security_sensitivity_level": "fips-199-moderate",
        "status": "under-development", "status_remarks": "",
        "auth_boundary_description": "", "network_architecture": "",
        "data_flow": "", "roles": [], "parties": [], "information_types": [],
    }

def build_oscal_ssp(ssp, profile, catalog):
    now = now_iso()
    roles = [{"id": r["role_id"], "title": r["title"]} for r in ssp.get("roles", [])]
    parties = []
    for p in ssp.get("parties", []):
        entry = {"uuid": p["uuid"], "type": p["type"], "name": p["name"]}
        if p.get("email"):
            entry["email-addresses"] = [p["email"]]
        parties.append(entry)
    info_types = []
    for it in ssp.get("information_types", []):
        info_types.append({
            "uuid": it["uuid"], "title": it["title"],
            "description": it.get("description", ""),
            "confidentiality-impact": {"base": it.get("c_impact", "fips-199-moderate")},
            "integrity-impact":       {"base": it.get("i_impact", "fips-199-moderate")},
            "availability-impact":    {"base": it.get("a_impact", "fips-199-moderate")},
        })
    profile_resource_uuid = ssp.get("profile_resource_uuid") or new_uuid()
    if profile:
        fp = profile.get("filepath", "")
        fname = Path(fp).name if fp else "profile.json"
        import_href = f"#{profile_resource_uuid}"
        bm = {
            "uuid": profile_resource_uuid, "title": profile.get("title", "OSCAL Profile"),
            "props": [
                {"name": "type", "value": "profile"},
                {"name": "version", "value": profile.get("version", "—")},
                {"name": "oscal-version", "value": profile.get("oscal_version", "—")},
                {"name": "last-modified", "value": profile.get("last_modified", "—")},
            ],
            "rlinks": [{"href": fname}],
        }
    elif catalog:
        fp = catalog.get("filepath", "")
        fname = Path(fp).name if fp else "catalog.json"
        import_href = f"#{profile_resource_uuid}"
        bm = {
            "uuid": profile_resource_uuid, "title": catalog.get("title", "OSCAL Catalog"),
            "props": [
                {"name": "type", "value": "catalog"},
                {"name": "version", "value": catalog.get("version", "—")},
                {"name": "oscal-version", "value": catalog.get("oscal_version", "—")},
                {"name": "last-modified", "value": catalog.get("last_modified", "—")},
            ],
            "rlinks": [{"href": fname}],
        }
    else:
        import_href = "PROFILE_OR_CATALOG_HREF"
        bm = None
    component_uuid = new_uuid()
    doc = {
        "system-security-plan": {
            "uuid": ssp["uuid"],
            "metadata": {
                "title": ssp["title"], "last-modified": now,
                "version": ssp.get("version", "1.0"), "oscal-version": "1.1.2",
                **({"roles": roles} if roles else {}),
                **({"parties": parties} if parties else {}),
            },
            "import-profile": {"href": import_href},
            "system-characteristics": {
                "system-ids": [{"id": ssp["uuid"], "identifier-type": "https://ietf.org/rfc/rfc4122"}],
                "system-name": ssp.get("system_name", ""),
                **({"system-name-short": ssp["system_name_short"]} if ssp.get("system_name_short") else {}),
                "description": ssp.get("system_description", ""),
                **({"date-authorized": ssp["date_authorized"]} if ssp.get("date_authorized") else {}),
                **({"security-sensitivity-level": ssp["security_sensitivity_level"]} if ssp.get("security_sensitivity_level") else {}),
                "system-information": {"information-types": info_types},
                "status": {"state": ssp.get("status", "under-development"),
                           **({"remarks": ssp["status_remarks"]} if ssp.get("status_remarks") else {})},
                "authorization-boundary": {"description": ssp.get("auth_boundary_description", "")},
                **({"network-architecture": {"description": ssp["network_architecture"]}} if ssp.get("network_architecture") else {}),
                **({"data-flow": {"description": ssp["data_flow"]}} if ssp.get("data_flow") else {}),
            },
            "system-implementation": {"components": [{
                "uuid": component_uuid, "type": "this-system",
                "title": ssp.get("system_name", "This System"),
                "description": ssp.get("system_description", ""),
                "status": {"state": ssp.get("status", "under-development")},
            }]},
            "control-implementation": {
                "description": "Control implementation statements will be added in Stage 2.",
                "implemented-requirements": [],
            },
            **({"back-matter": {"resources": [bm]}} if bm else {}),
        }
    }
    return doc

def parse_ssp_file(data):
    root   = data.get("system-security-plan", {})
    meta   = root.get("metadata", {})
    sc     = root.get("system-characteristics", {})
    status = sc.get("status", {})
    ab     = sc.get("authorization-boundary", {})
    na     = sc.get("network-architecture", {})
    df     = sc.get("data-flow", {})
    roles  = [{"role_id": r.get("id", ""), "title": r.get("title", "")} for r in meta.get("roles", [])]
    parties = []
    for p in meta.get("parties", []):
        emails = p.get("email-addresses", [])
        parties.append({"uuid": p.get("uuid", new_uuid()), "type": p.get("type", "person"),
                        "name": p.get("name", ""), "email": emails[0] if emails else ""})
    info_types = []
    for it in sc.get("system-information", {}).get("information-types", []):
        info_types.append({
            "uuid": it.get("uuid", new_uuid()), "title": it.get("title", ""),
            "description": it.get("description", ""),
            "c_impact": it.get("confidentiality-impact", {}).get("base", "fips-199-moderate"),
            "i_impact": it.get("integrity-impact",       {}).get("base", "fips-199-moderate"),
            "a_impact": it.get("availability-impact",    {}).get("base", "fips-199-moderate"),
        })
    import_href = root.get("import-profile", {}).get("href", "")
    bm_info = {}
    if import_href.startswith("#"):
        ref_uuid  = import_href.lstrip("#")
        resources = root.get("back-matter", {}).get("resources", [])
        resource  = next((r for r in resources if r.get("uuid") == ref_uuid), None)
        if resource:
            rlinks = resource.get("rlinks", [])
            bm_info = {
                "title":   resource.get("title", ""),
                "file":    rlinks[0].get("href", "") if rlinks else "",
                "version": next((p["value"] for p in resource.get("props", []) if p.get("name") == "version"), ""),
            }
    else:
        bm_info = {"title": "", "file": import_href, "version": ""}
    ssp = {
        "uuid": root.get("uuid", new_uuid()), "title": meta.get("title", ""),
        "version": meta.get("version", "1.0"), "date_authorized": sc.get("date-authorized", ""),
        "system_name": sc.get("system-name", ""), "system_name_short": sc.get("system-name-short", ""),
        "system_description": sc.get("description", ""),
        "security_sensitivity_level": sc.get("security-sensitivity-level", "fips-199-moderate"),
        "status": status.get("state", "under-development"), "status_remarks": status.get("remarks", ""),
        "auth_boundary_description": ab.get("description", ""),
        "network_architecture": na.get("description", ""),
        "data_flow": df.get("description", ""),
        "roles": roles, "parties": parties, "information_types": info_types,
        "import_href": import_href,
        "profile_resource_uuid": import_href.lstrip("#") if import_href.startswith("#") else "",
    }
    return ssp, bm_info

def validate_ssp(ssp, profile, catalog):
    errors, warnings = [], []
    if not ssp.get("title"):
        errors.append("SSP Title is required (Section 1).")
    if not ssp.get("system_name"):
        errors.append("System Name (Full) is required (Section 2).")
    if not ssp.get("system_description"):
        errors.append("System Description is required (Section 2).")
    if not ssp.get("auth_boundary_description"):
        errors.append("Authorization Boundary Description is required (Section 3).")
    if not ssp.get("information_types"):
        errors.append("At least one Information Type is required (Section 5).")
    if not profile and not catalog:
        errors.append("No catalog or profile loaded — import-profile cannot be set.")
    if not profile:
        warnings.append("No profile loaded. Recommended to load an OSCAL profile before saving.")
    return errors, warnings

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def new_uuid():
    return str(uuid.uuid4())
