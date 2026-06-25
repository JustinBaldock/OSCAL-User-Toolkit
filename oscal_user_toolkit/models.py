"""
models.py
=========
This file contains all the "data" logic for the OSCAL User Toolkit.
It has NO graphical user interface (GUI) code at all — it only deals
with reading, writing, and converting data.

Keeping data logic separate from GUI code is good practice because:
  - It is easier to test (you can run these functions without opening a window)
  - It is easier to read (each file has one clear job)
  - If you ever change the GUI library, this file stays the same

OSCAL is an open standard for describing security controls and plans.
Files are stored as JSON (JavaScript Object Notation), a plain-text
format that looks like Python dictionaries and lists.
"""

# ── Standard library imports ──────────────────────────────────────────────────
# These modules are built into Python — no installation needed.

import json        # Reads and writes JSON files
import uuid        # Generates universally unique identifiers (UUIDs)
from datetime import datetime, timezone   # Used to get the current date/time
from pathlib import Path                  # Cross-platform file path handling


# =============================================================================
# OSCAL CATALOG PARSING HELPERS
# These small functions extract specific pieces of data from the raw JSON
# dictionaries that come out of an OSCAL catalog file.
# =============================================================================

def get_prop(props, name, default="—"):
    """
    Search a list of OSCAL 'props' (properties) for one with a matching name,
    and return its value.

    In OSCAL, many objects carry extra metadata as a list of
    {"name": "...", "value": "..."} dictionaries called 'props'.
    This function makes it easy to look one up by name.

    Parameters:
        props   - A list of property dictionaries, e.g.
                  [{"name": "label", "value": "GOV-01"}, ...]
        name    - The property name to search for, e.g. "label"
        default - What to return if the property is not found (defaults to "—")

    Returns:
        The value string if found, otherwise the default.

    Example:
        props = [{"name": "label", "value": "GOV-01"}]
        get_prop(props, "label")   # returns "GOV-01"
        get_prop(props, "colour")  # returns "—"
    """
    for p in props:
        # Check whether this property's name matches what we are looking for
        if p.get("name") == name:
            return p.get("value", default)
    # If we went through every property and found nothing, return the default
    return default


def get_all_props(props, name):
    """
    Like get_prop, but returns ALL values whose name matches, as a list.

    This is needed for properties that can appear more than once —
    for example, 'applicability' (NC, OS, P, S, TS) appears as
    several separate props on one control.

    Parameters:
        props - A list of property dictionaries
        name  - The property name to search for

    Returns:
        A list of matching value strings (may be empty).

    Example:
        props = [
            {"name": "applicability", "value": "NC"},
            {"name": "applicability", "value": "OS"},
        ]
        get_all_props(props, "applicability")  # returns ["NC", "OS"]
    """
    # This is a "list comprehension" — a compact way to build a list
    # by looping and filtering in one line.
    return [p.get("value", "") for p in props if p.get("name") == name]


def get_statement(parts):
    """
    Extract the plain-English description (called the 'statement') from
    an OSCAL control's 'parts' list.

    Each control can have multiple 'parts' (e.g. statement, guidance,
    references). We only want the one named 'statement'.

    Parameters:
        parts - A list of part dictionaries from a control

    Returns:
        The prose text of the statement, or an empty string if not found.

    Example:
        parts = [{"name": "statement", "prose": "Cables are run in ..."}]
        get_statement(parts)  # returns "Cables are run in ..."
    """
    for part in parts:
        if part.get("name") == "statement":
            # .strip() removes any leading/trailing whitespace
            return part.get("prose", "").strip()
    return ""


def collect_controls(obj, parent_titles=None):
    """
    Recursively walk an OSCAL catalog (or group within a catalog) and
    collect every control into a flat list.

    OSCAL catalogs are nested: a catalog contains groups, groups can
    contain sub-groups, and groups/sub-groups contain controls.
    This function uses recursion (calling itself) to walk all levels.

    Each collected control becomes a plain Python dictionary with
    all the fields the GUI needs to display it.

    Parameters:
        obj           - A catalog, group, or sub-group dictionary
        parent_titles - A list of ancestor group titles, used to build
                        the breadcrumb path shown in the detail panel.
                        Starts as None (empty) at the top level.

    Returns:
        A flat list of control dictionaries.
    """
    # On the very first call, parent_titles is None — start with an empty list.
    # We avoid using [] as a default argument because Python reuses the same
    # list object across calls, which causes bugs. None is the safe pattern.
    if parent_titles is None:
        parent_titles = []

    result = []

    # Build the breadcrumb path for this level by adding the current title
    title = obj.get("title", "")
    path = parent_titles + ([title] if title else [])

    # Process every control directly inside this object
    for ctrl in obj.get("controls", []):
        props   = ctrl.get("props", [])
        ctrl_id = ctrl.get("id", "")

        # Use the 'label' prop (e.g. "GOV-01") as the display label.
        # If there is no label prop, fall back to the raw id (e.g. "ism-1130").
        # The 'or' operator returns ctrl_id if get_prop returns None.
        label = get_prop(props, "label", default=None) or ctrl_id

        # Build a clean dictionary with just the fields we need
        result.append({
            "id":              ctrl_id,
            "label":           label,
            "class":           ctrl.get("class", ""),    # e.g. "ISM-control"
            "title":           ctrl.get("title", ""),
            "statement":       get_statement(ctrl.get("parts", [])),
            "applicability":   get_all_props(props, "applicability"),
            "revision":        get_prop(props, "revision"),
            "updated":         get_prop(props, "updated"),
            "essential_eight": get_prop(props, "essential-eight-applicability"),
            # " › ".join([...]) builds "Group › Sub-group › ..." breadcrumb text
            "path":            " › ".join(path),
        })

    # Recurse into any sub-groups, passing the current path down
    for grp in obj.get("groups", []):
        result.extend(collect_controls(grp, path))

    return result


# =============================================================================
# FILE LOADERS
# These functions open a JSON file from disk, validate it, and return
# a clean Python dictionary the rest of the app can use.
# =============================================================================

def load_catalog(filepath):
    """
    Open an OSCAL catalog JSON file and return its contents as a
    structured Python dictionary.

    Parameters:
        filepath - The full path to the .json catalog file (string or Path)

    Returns:
        A dictionary containing:
            title, published, last_modified, version, oscal_version,
            controls (flat list), filepath

    Raises:
        ValueError - if the file does not look like an OSCAL catalog
        json.JSONDecodeError - if the file is not valid JSON
    """
    # Open the file and parse its JSON content into a Python dictionary.
    # 'encoding="utf-8"' ensures special characters are read correctly.
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # Every OSCAL catalog file must have a top-level "catalog" key.
    # If it is missing, this is not a valid catalog file.
    if "catalog" not in data:
        raise ValueError("Missing 'catalog' key — not an OSCAL catalog.")

    catalog = data["catalog"]
    # 'metadata' holds the document title, version, dates, etc.
    meta = catalog.get("metadata", {})

    # Return a clean, flat dictionary — the GUI only needs these fields.
    # .get("key", "—") returns "—" if the key does not exist,
    # so labels always show something rather than crashing.
    return {
        "title":         meta.get("title", "Untitled catalog"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        # collect_controls walks the whole catalog and returns a flat list
        "controls":      collect_controls(catalog),
        # Store the file path so we can reference it later when building the SSP
        "filepath":      filepath,
    }


def load_profile(filepath):
    """
    Open an OSCAL profile JSON file and return its contents as a
    structured Python dictionary.

    A profile is a document that selects a subset of controls from a
    catalog — for example, only the controls relevant to a non-classified
    system. It lists the selected control IDs under 'imports'.

    Parameters:
        filepath - The full path to the .json profile file

    Returns:
        A dictionary containing:
            title, published, last_modified, version, oscal_version,
            ids (a Python set of selected control ID strings), filepath

    Raises:
        ValueError - if the file does not look like an OSCAL profile
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if "profile" not in data:
        raise ValueError("Missing 'profile' key — not an OSCAL profile.")

    profile = data["profile"]
    meta    = profile.get("metadata", {})

    # Collect every selected control ID into a Python 'set'.
    # A set is like a list but automatically removes duplicates and
    # makes lookups (the 'in' operator) very fast — important when
    # filtering thousands of controls.
    included_ids = set()

    # The profile may import from multiple sources, each with multiple
    # include-controls selectors, each with multiple with-ids entries.
    # Three nested loops handle all combinations.
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


# =============================================================================
# SSP DATA MODEL
# The System Security Plan (SSP) is built up from user input in the GUI.
# Internally we store everything as a plain Python dictionary (self._ssp).
# These functions create, validate, convert, and parse that dictionary.
# =============================================================================

def empty_ssp():
    """
    Return a brand-new, blank SSP dictionary with sensible default values.

    This is called when the user clicks 'New SSP' or when the app starts.
    Every key here corresponds to a field in the SSP Editor form.

    Returns:
        A dictionary with all SSP fields set to empty strings or defaults.
    """
    return {
        # A UUID is a random unique identifier — required by the OSCAL schema.
        # We generate one now so it stays stable for the life of this SSP.
        "uuid": new_uuid(),

        # ── Section 1: Metadata ───────────────────────────────────────────
        "title":            "",     # SSP document title
        "version":          "1.0",  # Document version
        "date_authorized":  "",     # Date the system was authorised (YYYY-MM-DD)

        # ── Section 2: System characteristics ────────────────────────────
        "system_name":                "",
        "system_name_short":          "",
        "system_description":         "",
        # FIPS 199 defines three impact levels: low, moderate, high
        "security_sensitivity_level": "fips-199-moderate",
        "status":                     "under-development",
        "status_remarks":             "",

        # ── Section 3: Authorization boundary ────────────────────────────
        "auth_boundary_description":  "",

        # ── Section 4: Network architecture & data flow (optional) ───────
        "network_architecture": "",
        "data_flow":            "",

        # ── Sections 5-7: Lists — start empty, user adds entries ─────────
        # Each role is: {"role_id": str, "title": str}
        "roles":            [],
        # Each party is:  {"uuid": str, "type": str, "name": str, "email": str}
        "parties":          [],
        # Each info type: {"uuid", "title", "description", "c_impact", "i_impact", "a_impact"}
        "information_types": [],
    }


def build_oscal_ssp(ssp, profile, catalog):
    """
    Convert our internal SSP dictionary into a fully valid OSCAL SSP
    JSON document (as a Python dictionary ready to be written to a file).

    The OSCAL SSP schema defines a specific structure. This function
    maps our simple internal fields to that structure.

    Parameters:
        ssp     - The internal SSP dictionary (from the form)
        profile - The loaded profile dictionary, or None
        catalog - The loaded catalog dictionary, or None

    Returns:
        A nested dictionary matching the OSCAL system-security-plan schema.
    """
    # Record the exact moment of saving — required by the schema
    now = now_iso()

    # ── Convert roles to OSCAL format ────────────────────────────────────────
    # Our internal format:  {"role_id": "isso", "title": "ISSO"}
    # OSCAL format:         {"id": "isso", "title": "ISSO"}
    roles = [
        {"id": r["role_id"], "title": r["title"]}
        for r in ssp.get("roles", [])
    ]

    # ── Convert parties to OSCAL format ──────────────────────────────────────
    parties = []
    for p in ssp.get("parties", []):
        # Build the required fields first
        entry = {
            "uuid": p["uuid"],
            "type": p["type"],   # "person" or "organization"
            "name": p["name"],
        }
        # Email is optional — only add it if the user filled it in
        if p.get("email"):
            entry["email-addresses"] = [p["email"]]
        parties.append(entry)

    # ── Convert information types to OSCAL format ─────────────────────────────
    # CIA = Confidentiality, Integrity, Availability — the three security pillars
    info_types = []
    for it in ssp.get("information_types", []):
        info_types.append({
            "uuid":        it["uuid"],
            "title":       it["title"],
            "description": it.get("description", ""),
            # Each impact level is wrapped in a {"base": "fips-199-..."} dict
            "confidentiality-impact": {"base": it.get("c_impact", "fips-199-moderate")},
            "integrity-impact":       {"base": it.get("i_impact", "fips-199-moderate")},
            "availability-impact":    {"base": it.get("a_impact", "fips-199-moderate")},
        })

    # ── Build the import-profile reference and back-matter resource ───────────
    #
    # The OSCAL SSP must declare which profile (or catalog) it is based on.
    # The recommended way is:
    #   1. Give the profile a UUID and store its details in "back-matter"
    #   2. Set import-profile.href to "#<that-uuid>" (the # means "look in this file")
    #
    # This keeps the SSP self-documenting: anyone reading the file can see
    # exactly which profile version was used, without needing the profile file.

    # Re-use the existing resource UUID if this SSP was previously saved,
    # so the internal reference stays stable across edits.
    profile_resource_uuid = ssp.get("profile_resource_uuid") or new_uuid()

    if profile:
        # A profile is loaded — reference it (preferred by the OSCAL schema)
        fp    = profile.get("filepath", "")
        fname = Path(fp).name if fp else "profile.json"  # just the filename, not full path
        import_href = f"#{profile_resource_uuid}"         # e.g. "#abc-123"
        back_matter_resource = {
            "uuid":  profile_resource_uuid,
            "title": profile.get("title", "OSCAL Profile"),
            # Store key metadata so the SSP is self-documenting
            "props": [
                {"name": "type",          "value": "profile"},
                {"name": "version",       "value": profile.get("version", "—")},
                {"name": "oscal-version", "value": profile.get("oscal_version", "—")},
                {"name": "last-modified", "value": profile.get("last_modified", "—")},
            ],
            # rlinks = relative links — points to the actual profile file
            "rlinks": [{"href": fname}],
        }
    elif catalog:
        # No profile loaded — fall back to referencing the catalog directly.
        # The OSCAL schema discourages this but it keeps the file valid.
        fp    = catalog.get("filepath", "")
        fname = Path(fp).name if fp else "catalog.json"
        import_href = f"#{profile_resource_uuid}"
        back_matter_resource = {
            "uuid":  profile_resource_uuid,
            "title": catalog.get("title", "OSCAL Catalog"),
            "props": [
                {"name": "type",          "value": "catalog"},
                {"name": "version",       "value": catalog.get("version", "—")},
                {"name": "oscal-version", "value": catalog.get("oscal_version", "—")},
                {"name": "last-modified", "value": catalog.get("last_modified", "—")},
            ],
            "rlinks": [{"href": fname}],
        }
    else:
        # Neither loaded — use a placeholder string (file will be invalid)
        import_href          = "PROFILE_OR_CATALOG_HREF"
        back_matter_resource = None

    # ── Auto-generate the required "this-system" component ───────────────────
    # The OSCAL schema requires at least one component in system-implementation.
    # For a basic SSP, one component of type "this-system" is sufficient.
    component_uuid = new_uuid()

    # ── Assemble the final OSCAL document ────────────────────────────────────
    # The ** (double-star) operator unpacks a dictionary into keyword arguments.
    # Here we use it to conditionally include optional keys only when they
    # have a value — e.g. **({"key": val} if val else {}) adds "key" only
    # when val is not empty.
    doc = {
        "system-security-plan": {
            "uuid": ssp["uuid"],

            # Metadata section — document-level information
            "metadata": {
                "title":         ssp["title"],
                "last-modified": now,
                "version":       ssp.get("version", "1.0"),
                "oscal-version": "1.1.2",           # OSCAL schema version we target
                **({"roles":   roles}   if roles   else {}),
                **({"parties": parties} if parties else {}),
            },

            # Declare which profile this SSP is based on
            "import-profile": {"href": import_href},

            # System characteristics — details about the system being described
            "system-characteristics": {
                # system-ids: a unique identifier for the system itself
                "system-ids": [{
                    "id":              ssp["uuid"],
                    "identifier-type": "https://ietf.org/rfc/rfc4122",  # UUID standard
                }],
                "system-name": ssp.get("system_name", ""),
                # Only include short name if the user provided one
                **({"system-name-short": ssp["system_name_short"]}
                   if ssp.get("system_name_short") else {}),
                "description": ssp.get("system_description", ""),
                **({"date-authorized": ssp["date_authorized"]}
                   if ssp.get("date_authorized") else {}),
                **({"security-sensitivity-level": ssp["security_sensitivity_level"]}
                   if ssp.get("security_sensitivity_level") else {}),
                "system-information": {
                    "information-types": info_types,
                },
                "status": {
                    "state": ssp.get("status", "under-development"),
                    **({"remarks": ssp["status_remarks"]}
                       if ssp.get("status_remarks") else {}),
                },
                "authorization-boundary": {
                    "description": ssp.get("auth_boundary_description", ""),
                },
                # Network architecture and data flow are optional
                **({"network-architecture": {"description": ssp["network_architecture"]}}
                   if ssp.get("network_architecture") else {}),
                **({"data-flow": {"description": ssp["data_flow"]}}
                   if ssp.get("data_flow") else {}),
            },

            # System implementation — the components that make up the system
            "system-implementation": {
                "components": [{
                    "uuid":        component_uuid,
                    "type":        "this-system",
                    "title":       ssp.get("system_name", "This System"),
                    "description": ssp.get("system_description", ""),
                    "status":      {"state": ssp.get("status", "under-development")},
                }]
            },

            # Control implementation — to be populated in Stage 2
            "control-implementation": {
                "description": "Control implementation statements will be added in Stage 2.",
                "implemented-requirements": [],
            },

            # Back-matter — reference documents (our profile/catalog entry goes here)
            **({"back-matter": {"resources": [back_matter_resource]}}
               if back_matter_resource else {}),
        }
    }
    return doc


def parse_ssp_file(data):
    """
    Read a previously saved OSCAL SSP JSON document (already loaded into
    a Python dictionary) and convert it back into our internal SSP format.

    This is the reverse of build_oscal_ssp — it lets the user re-open
    a saved SSP to continue editing.

    Parameters:
        data - A dictionary from json.load() containing a saved OSCAL SSP

    Returns:
        A tuple of (ssp_dict, back_matter_info):
            ssp_dict        - Our internal SSP dictionary, ready to populate the form
            back_matter_info - Details about the referenced profile/catalog,
                               extracted from the SSP's back-matter section
    """
    # Navigate into the nested OSCAL structure
    # .get("key", {}) returns an empty dict if the key is missing,
    # which lets us safely call .get() on the result without crashing.
    root   = data.get("system-security-plan", {})
    meta   = root.get("metadata", {})
    sc     = root.get("system-characteristics", {})
    status = sc.get("status", {})
    ab     = sc.get("authorization-boundary", {})
    na     = sc.get("network-architecture", {})
    df     = sc.get("data-flow", {})

    # ── Roles: convert from OSCAL format back to our internal format ──────────
    # OSCAL uses "id", we use "role_id"
    roles = [
        {"role_id": r.get("id", ""), "title": r.get("title", "")}
        for r in meta.get("roles", [])
    ]

    # ── Parties ───────────────────────────────────────────────────────────────
    parties = []
    for p in meta.get("parties", []):
        emails = p.get("email-addresses", [])
        parties.append({
            "uuid":  p.get("uuid", new_uuid()),
            "type":  p.get("type", "person"),
            "name":  p.get("name", ""),
            # Take only the first email address if there are multiple
            "email": emails[0] if emails else "",
        })

    # ── Information types ─────────────────────────────────────────────────────
    info_types = []
    for it in sc.get("system-information", {}).get("information-types", []):
        info_types.append({
            "uuid":        it.get("uuid", new_uuid()),
            "title":       it.get("title", ""),
            "description": it.get("description", ""),
            # Unpack the nested {"base": "fips-199-..."} structure
            "c_impact": it.get("confidentiality-impact", {}).get("base", "fips-199-moderate"),
            "i_impact": it.get("integrity-impact",       {}).get("base", "fips-199-moderate"),
            "a_impact": it.get("availability-impact",    {}).get("base", "fips-199-moderate"),
        })

    # ── Resolve import-profile reference ──────────────────────────────────────
    import_href = root.get("import-profile", {}).get("href", "")

    # If the href starts with "#", it is an internal reference to a back-matter
    # resource. We look up that resource to get the profile title and filename.
    back_matter_info = {}
    if import_href.startswith("#"):
        # Strip the "#" to get the UUID we are looking for
        ref_uuid  = import_href.lstrip("#")
        resources = root.get("back-matter", {}).get("resources", [])

        # Search the resources list for the one with a matching UUID.
        # next(..., None) returns None if nothing matches (instead of crashing).
        resource = next(
            (r for r in resources if r.get("uuid") == ref_uuid),
            None
        )
        if resource:
            rlinks = resource.get("rlinks", [])
            back_matter_info = {
                "title":   resource.get("title", ""),
                "file":    rlinks[0].get("href", "") if rlinks else "",
                # Find the "version" prop using a generator expression
                "version": next(
                    (p["value"] for p in resource.get("props", [])
                     if p.get("name") == "version"),
                    ""  # default if not found
                ),
            }
    else:
        # Bare filename — treat the href itself as the file reference
        back_matter_info = {"title": "", "file": import_href, "version": ""}

    # ── Assemble and return the internal SSP dictionary ───────────────────────
    ssp = {
        "uuid":            root.get("uuid", new_uuid()),
        "title":           meta.get("title", ""),
        "version":         meta.get("version", "1.0"),
        "date_authorized": sc.get("date-authorized", ""),
        "system_name":     sc.get("system-name", ""),
        "system_name_short": sc.get("system-name-short", ""),
        "system_description": sc.get("description", ""),
        "security_sensitivity_level": sc.get("security-sensitivity-level", "fips-199-moderate"),
        "status":          status.get("state", "under-development"),
        "status_remarks":  status.get("remarks", ""),
        "auth_boundary_description": ab.get("description", ""),
        "network_architecture": na.get("description", ""),
        "data_flow":       df.get("description", ""),
        "roles":           roles,
        "parties":         parties,
        "information_types": info_types,
        # Preserve the import href so it round-trips correctly on re-save
        "import_href":           import_href,
        # Preserve the back-matter UUID so it stays stable across edits
        "profile_resource_uuid": import_href.lstrip("#") if import_href.startswith("#") else "",
    }
    return ssp, back_matter_info


def validate_ssp(ssp, profile, catalog):
    """
    Check that the SSP has all the required fields before saving.

    Returns two separate lists:
      - errors:   Problems that MUST be fixed — saving is blocked.
      - warnings: Advisory issues — the user is warned but can still save.

    Parameters:
        ssp     - The internal SSP dictionary
        profile - The loaded profile dict, or None
        catalog - The loaded catalog dict, or None

    Returns:
        A tuple of (errors_list, warnings_list)
    """
    errors   = []
    warnings = []

    # ── Hard errors — required by the OSCAL schema ────────────────────────────
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

    # ── Soft warnings — valid but not recommended ─────────────────────────────
    if not profile:
        # Saving without a profile means we reference the catalog directly,
        # which the OSCAL spec discourages (profile is preferred).
        warnings.append(
            "No profile loaded. It is strongly recommended to load an OSCAL profile "
            "before saving — the SSP will fall back to referencing the catalog directly."
        )

    return errors, warnings


# =============================================================================
# GENERAL UTILITIES
# Small helper functions used throughout the app.
# =============================================================================

def now_iso():
    """
    Return the current date and time as an ISO 8601 string in UTC.

    Example return value: "2026-06-25T10:30:00Z"
    The OSCAL schema requires this format for 'last-modified' fields.
    """
    # timezone.utc ensures we use UTC (Coordinated Universal Time),
    # not the local time zone of the computer running the app.
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_uuid():
    """
    Generate and return a new random UUID (Universally Unique Identifier)
    as a string.

    Example return value: "550e8400-e29b-41d4-a716-446655440000"
    UUIDs are used throughout OSCAL to uniquely identify documents,
    components, parties, and information types.
    """
    # uuid.uuid4() generates a random UUID object; str() converts it to a string
    return str(uuid.uuid4())


def refresh_ctrl_list(ctrl_responses, all_controls, search_term,
                      ctrl_tree, applied_tree, notebook, progress_lbl):
    """
    Rebuild the All Controls and Applied Controls Treeview tabs.

    Shared by ComponentTab and CapabilityTab so the control-list rendering
    logic only exists in one place.

    Parameters:
        ctrl_responses - dict {control_id: response_text}
        all_controls   - list of control dicts (id, label, title, statement)
        search_term    - text filter applied to the All Controls tab only
        ctrl_tree      - Treeview widget for the All Controls tab
        applied_tree   - Treeview widget for the Applied Controls tab
        notebook       - ttk.Notebook holding both tabs (for label updates)
        progress_lbl   - Label widget showing "N of M controls have responses"
    """
    DOT_DONE  = "●"
    DOT_EMPTY = "○"

    term = search_term.lower().strip()
    filtered = (
        [c for c in all_controls
         if term in c["label"].lower()
         or term in c["statement"].lower()
         or term in c["id"].lower()]
        if term else all_controls
    )

    total      = len(all_controls)
    done_count = sum(
        1 for c in all_controls
        if ctrl_responses.get(c["id"], "").strip()
    )

    def insert_row(tree, ctrl):
        has_resp = bool(ctrl_responses.get(ctrl["id"], "").strip())
        dot = DOT_DONE  if has_resp else DOT_EMPTY
        tag = "done"    if has_resp else "empty"
        tree.insert(
            "", "end", iid=ctrl["id"],
            values=(dot, ctrl["label"], ctrl["statement"] or ctrl["title"]),
            tags=(tag,),
        )

    ctrl_tree.delete(*ctrl_tree.get_children())
    for ctrl in filtered:
        insert_row(ctrl_tree, ctrl)

    applied_tree.delete(*applied_tree.get_children())
    applied_count = 0
    for ctrl in all_controls:
        if ctrl_responses.get(ctrl["id"], "").strip():
            insert_row(applied_tree, ctrl)
            applied_count += 1

    try:
        notebook.tab(0, text=f"All Controls ({len(filtered)})")
        notebook.tab(1, text=f"Applied Controls ({applied_count})")
    except Exception:
        pass

    if total > 0:
        progress_lbl.config(text=f"{done_count} of {total} controls have responses")
    else:
        progress_lbl.config(text="")


def build_component_oscal_entry(comp, source_href):
    """
    Convert one internal component dict into an OSCAL defined-component dict.

    Used by both ComponentTab (when saving a single component file) and
    CapabilityTab (when exporting a capability document that embeds its
    member components).  Keeping the conversion in one place ensures the
    two outputs always stay in sync.

    Parameters:
        comp        - Internal component dict (uuid, type, title, description,
                      purpose, status, status_remarks, props, roles,
                      ctrl_responses, remarks).
        source_href - URI for the control source (catalog or profile href),
                      written into each control-implementations block.

    Returns:
        A dict that conforms to the OSCAL defined-component assembly.
    """
    c = {
        "uuid":        comp["uuid"],
        "type":        comp.get("type", "software"),
        "title":       comp.get("title", ""),
        "description": comp.get("description", ""),
    }

    if comp.get("purpose"):
        c["purpose"] = comp["purpose"]

    # Props — operational-status first, then any user-defined props
    props = []
    if comp.get("status"):
        p = {"name": "operational-status", "value": comp["status"]}
        if comp.get("status_remarks"):
            p["remarks"] = comp["status_remarks"]
        props.append(p)
    for prop in comp.get("props", []):
        entry = {"name": prop["name"], "value": prop["value"]}
        if prop.get("remarks"):
            entry["remarks"] = prop["remarks"]
        props.append(entry)
    if props:
        c["props"] = props

    # Responsible roles — OSCAL uses "role-id" (hyphenated)
    roles = [
        {"role-id": r["role_id"],
         **({"remarks": r["remarks"]} if r.get("remarks") else {})}
        for r in comp.get("roles", [])
    ]
    if roles:
        c["responsible-roles"] = roles

    # Control implementations — only include controls with a non-empty response
    implemented = [
        {
            "uuid":        new_uuid(),
            "control-id":  ctrl_id,
            "description": desc.strip(),
        }
        for ctrl_id, desc in comp.get("ctrl_responses", {}).items()
        if desc.strip()
    ]
    if implemented:
        c["control-implementations"] = [{
            "uuid":        new_uuid(),
            "source":      source_href,
            "description": (
                f"Control implementations for "
                f"{comp.get('title', 'this component')}."
            ),
            "implemented-requirements": implemented,
        }]

    if comp.get("remarks"):
        c["remarks"] = comp["remarks"]

    return c
