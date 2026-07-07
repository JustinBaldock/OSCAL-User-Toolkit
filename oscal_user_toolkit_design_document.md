# OSCAL User Toolkit — Design Document

**Version:** 3.6  
**Date:** July 2026  
**Language:** Python 3.10+ (standard library only, plus optional `jsonschema` and `python-docx`)  
**GUI Framework:** tkinter (built into Python)

---

## 1. Purpose and Scope

The OSCAL User Toolkit is a desktop application for working with files that follow the **Open Security Controls Assessment Language (OSCAL)** standard. OSCAL is a machine-readable format published by NIST for describing security controls, system security plans, and component definitions as structured JSON files.

The toolkit allows a security practitioner to:

- Browse and search an OSCAL **catalog** of security controls, with filtering by class, guideline group, and keyword
- Apply an OSCAL **profile** to filter the catalog to a relevant baseline
- Create and save OSCAL **Component Definition** files describing how system components implement controls, including network protocol data and external reference links
- Create and save OSCAL **Capability Definition** files grouping components into named security functions, with automatic inheritance of component-level control responses
- Create and save an OSCAL **System Security Plan (SSP)** for a system
- Create and edit an OSCAL **Plan of Action and Milestones (POAM)** to track remediation of security findings
- Validate catalog and capability files against the bundled OSCAL JSON schema on open/save

---

## 2. File and Folder Structure

```
OSCAL-User-Toolkit/
├── main.py                                  ← Entry point — run this to start the app
├── oscal_user_toolkit/                      ← Python package folder
│   ├── __init__.py                          ← Empty file that marks this as a package
│   ├── models.py                            ← All data logic (no GUI code)
│   ├── app.py                               ← Main window, toolbar, info panel
│   ├── catalog_tab.py                       ← Catalog Viewer tab
│   ├── component_tab.py                     ← Component Editor tab
│   ├── capability_tab.py                    ← Capability Editor tab
│   ├── ssp_tab.py                           ← SSP Editor tab
│   └── poam_tab.py                          ← POAM Editor tab
│
├── oscal/                                   ← OSCAL schema release zips
│   ├── oscal-1.1.2.zip
│   ├── oscal-1.2.0.zip
│   └── oscal-1.2.2.zip
│
├── example-data/
│   ├── ISM_catalog.json                     ← Australian ISM catalog (1,150+ controls)
│   ├── ISM_NON_CLASSIFIED-baseline_profile.json
│   ├── ISM_NON_CLASSIFIED-baseline-resolved-profile_catalog.json
│   ├── ssp_ERN.json                         ← Example System Security Plan
│   ├── poam_ERN_POAM.json                   ← Example POAM
│   ├── microsoft_office_component.json      ← Comprehensive example components
│   ├── windows_server_2022_component.json
│   ├── windows_11_component.json
│   ├── servicedesk_plus_component.json
│   ├── mssql_server_component.json
│   └── components/                          ← 41 ready-to-use component files
│       ├── hardware_*.json                  ← 7 hardware components
│       ├── interconnection_*.json           ← 3 interconnection components
│       ├── operating-system_*.json          ← 4 OS components
│       ├── policy_*.json                    ← 8 policy components
│       ├── service_*.json                   ← 12 service components
│       └── software_*.json                  ← 7 software components
│
├── oscal_user_toolkit_design_document.md    ← This file
└── README.md
```

The application requires no external libraries for core operation.
- `jsonschema` is optional — if installed, catalog and capability files are validated against the bundled OSCAL schema on open/save. If not installed, validation is silently skipped.
- `python-docx` is optional — if installed, the SSP Editor's **Export to Word** button generates a formatted `.docx` report.

---

## 3. Architecture Overview

The application is structured in two layers:

```
┌──────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER  (GUI)                                   │
│                                                              │
│  app.py            OSCALApp (main window)                    │
│  catalog_tab.py    CatalogTab (tk.Frame subclass)            │
│  component_tab.py  ComponentTab (tk.Frame subclass)          │
│  capability_tab.py CapabilityTab (tk.Frame subclass)         │
│  ssp_tab.py        SSPTab (tk.Frame subclass)                │
│  poam_tab.py       POAMTab (tk.Frame subclass)               │
└─────────────────────────┬────────────────────────────────────┘
                          │ calls functions from
┌─────────────────────────▼────────────────────────────────────┐
│  DATA LAYER  (no GUI)                                        │
│                                                              │
│  models.py       load_catalog(), load_profile(),             │
│                  get_source_href(), get_profile_controls(),  │
│                  build_oscal_ssp(), parse_ssp_file(),        │
│                  validate_ssp(), validate_oscal_file(),      │
│                  refresh_ctrl_list(),                        │
│                  build_component_oscal_entry(),              │
│                  build_ssp_docx(),                           │
│                  new_uuid(), now_iso()                       │
└──────────────────────────────────────────────────────────────┘
```

### Why this separation matters

`models.py` contains zero GUI code. It can be imported, tested, and run independently of tkinter. This means:

- If the GUI framework were ever replaced, `models.py` stays unchanged
- Unit tests can call `load_catalog()` without opening a window
- The logic for building and parsing OSCAL JSON is in one place

---

## 4. The Data Layer — models.py

### 4.1 What models.py contains

| Function | Purpose |
|---|---|
| `get_prop(props, name)` | Extract a single named property value from an OSCAL props list |
| `get_all_props(props, name)` | Extract all values for a property that may appear multiple times |
| `get_statement(parts)` | Extract the prose text from an OSCAL control's parts list |
| `collect_controls(obj)` | Recursively walk a catalog and return a flat list of control dicts |
| `load_catalog(filepath)` | Open an OSCAL catalog JSON file and return a clean Python dict |
| `load_profile(filepath)` | Open an OSCAL profile JSON file and return a clean Python dict |
| `get_source_href(profile, catalog)` | Return the filename for control-implementations `source` (profile preferred, catalog fallback) |
| `get_profile_controls(catalog, profile)` | Return the filtered or full control list used by ComponentTab and CapabilityTab |
| `refresh_ctrl_list(...)` | Rebuild both control list Treeview tabs (shared by ComponentTab and CapabilityTab) |
| `build_component_oscal_entry(comp, source_href)` | Convert one internal component dict to an OSCAL defined-component dict (includes links and protocols) |
| `validate_oscal_file(data, schema_name, zip_path)` | Validate a parsed JSON dict against the OSCAL schema zip |
| `empty_ssp()` | Return a blank SSP dictionary with default values |
| `build_oscal_ssp(ssp, profile, catalog)` | Convert the internal SSP dict to a valid OSCAL JSON document |
| `parse_ssp_file(data)` | Convert a saved OSCAL SSP JSON dict back into the internal format |
| `validate_ssp(ssp, profile, catalog)` | Check for missing required fields; return (errors, warnings) |
| `build_ssp_docx(ssp, catalog)` | Generate a formatted Microsoft Word document from the SSP (requires `python-docx`) |
| `now_iso()` | Return the current UTC time as an ISO 8601 string |
| `new_uuid()` | Generate a new random UUID string |

### 4.2 The catalog internal format

When `load_catalog()` reads a file it returns this dictionary:

```python
{
    "title":         str,   # e.g. "Information security manual"
    "published":     str,   # e.g. "2026-06-18"
    "last_modified": str,
    "version":       str,   # e.g. "2026.06.18"
    "oscal_version": str,   # e.g. "1.1.2"
    "controls":      list,  # flat list — see below
    "filepath":      str,   # full path on disk
}
```

Each item in `controls` is:

```python
{
    "id":              str,   # e.g. "ism-1130" or "ism-principle-gov-01"
    "label":           str,   # e.g. "ism-1130" or "GOV-01" (from label prop, else id)
    "class":           str,   # e.g. "ISM-control" or "ISM-principle"
    "title":           str,   # e.g. "Executive cyber security accountability"
    "statement":       str,   # the plain-English requirement text
    "applicability":   list,  # e.g. ["NC", "OS", "P", "S", "TS"]
    "revision":        str,
    "updated":         str,
    "essential_eight": str,
    "path":            str,   # full breadcrumb e.g. "Cyber security principles › Govern › ..."
    "guideline":       str,   # top-level group title e.g. "Guidelines for cyber security roles"
}
```

The `guideline` field is the first element of the `path` breadcrumb. It is used by the Catalog Viewer's Guideline column and filter dropdown.

The OSCAL catalog is a nested structure (catalog → groups → sub-groups → controls). `collect_controls()` walks the entire tree recursively and returns a **flat** list, which is much easier for the GUI to work with.

### 4.3 The profile internal format

```python
{
    "title":         str,
    "published":     str,
    "last_modified": str,
    "version":       str,
    "oscal_version": str,
    "ids":           set,   # Python set of control ID strings
    "filepath":      str,
}
```

`ids` is a Python `set` (not a list). Sets make the `in` operator very fast — checking whether a control ID is in the profile takes the same time whether the profile has 10 or 10,000 controls (O(1) lookup vs O(n) for a list).

### 4.4 The component internal format

Components are stored as plain Python dicts in the `ComponentTab._components` list. They are only converted to OSCAL JSON at save time.

```python
{
    "uuid":           str,   # stable, auto-generated; preserved across edits
    "title":          str,
    "type":           str,   # e.g. "software", "hardware", "service"
    "description":    str,
    "purpose":        str,   # optional purpose statement
    "status":         str,   # e.g. "operational", "under-development"
    "status_remarks": str,
    "remarks":        str,
    "props":          list,  # [{"name": str, "value": str, "remarks": str}]
    "roles":          list,  # [{"role_id": str, "remarks": str}]
    "protocols":      list,  # [{"name": str, "title": str, "port_ranges": [...]}]
    "links":          list,  # [{"href": str, "rel": str, "text": str}]
    "ctrl_responses": dict,  # {control_id: description_string}
}
```

Each `port_ranges` entry is:
```python
{"start": int, "end": int, "transport": "TCP" | "UDP", "remarks": str}
```

Each `links` entry maps to an OSCAL `link` with a `rel` relationship type such as `vendor-documentation`, `security-advisory`, `configuration-baseline`, or `reference`.

### 4.5 Shared helper functions

**`get_source_href(profile, catalog)`**  
Both ComponentTab and CapabilityTab need to write a `source` URI into control-implementations blocks. This function centralises the logic: prefer the profile filename, fall back to the catalog filename, fall back to a placeholder string if neither is loaded.

**`get_profile_controls(catalog, profile)`**  
Both tabs show the same control list (profile-filtered if a profile is loaded, full catalog otherwise). This function is the single source of truth for that logic.

**`refresh_ctrl_list(...)`**  
Rebuilds both the "All Controls" and "Applied Controls" Treeview tabs. Shared by ComponentTab and CapabilityTab so the rendering logic exists in one place only.

**`build_component_oscal_entry(comp, source_href)`**  
Converts one internal component dict to an OSCAL defined-component dict. Serialises props, responsible-roles, protocols (with port-ranges), links, and control-implementations. Used by both ComponentTab (single-component save) and CapabilityTab (bundling member components into the capability file).

### 4.6 The SSP internal format

The SSP is stored as a plain Python dictionary throughout editing. It is only converted to OSCAL JSON at save time by `build_oscal_ssp()`.

```python
{
    "uuid":                       str,   # auto-generated, stays stable
    "title":                      str,
    "version":                    str,
    "date_authorized":            str,
    "system_name":                str,
    "system_name_short":          str,
    "system_description":         str,
    "security_sensitivity_level": str,   # "fips-199-low/moderate/high"
    "status":                     str,   # "operational", "under-development", etc.
    "status_remarks":             str,
    "auth_boundary_description":  str,
    "network_architecture":       str,
    "vlans":             list,  # [{"uuid", "vlan_id", "name", "description"}]
    "data_flow":                  str,
    "data_flow_links":  list,  # [{"uuid","source_component_uuid","source_component_title",
                                #   "target_component_uuid","target_component_title",
                                #   "protocol","port","transport","direction","description"}]
    "roles":     list,   # [{"role_id": str, "title": str}]
    "parties":   list,   # [{"uuid", "type", "name", "email"}]
    "information_types": list,  # [{"uuid","title","description","c_impact","i_impact","a_impact"}]
}
```

`data_flow_links` (Section 4) records how data moves between the SSP's own components — source, target, protocol, port, transport, and direction — so that a Data Flow diagram can eventually be generated from it. `vlans` (also Section 4) records the network's VLANs — ID, name, and description. Both are serialised into OSCAL using the same grouped-props approach; see §10.12.

---

## 5. The Presentation Layer

### 5.1 OSCALApp (app.py)

`OSCALApp` inherits from `tk.Tk`, making it the root window. It is responsible for:

- The **main toolbar** (OSCAL version selector, Open Catalog, Open Profile, Clear Profile buttons)
- The **info panel** (two cards showing catalog and profile metadata)
- The **notebook** (tabbed container holding all five tabs)
- The **status bar** (one-line message at the bottom)
- Loading catalog and profile files, validating them against the schema, and distributing the data to tabs

`OSCALApp` holds two pieces of shared state:

```python
self._catalog = None   # loaded catalog dict, or None
self._profile = None   # loaded profile dict, or None
```

These are the single source of truth for which files are loaded. Tabs do not store their own copies — they receive the data through callbacks.

The OSCAL version selector in the toolbar scans the `oscal/` folder for zip files at startup and presents them newest-first. The selected version is used for schema validation (catalog on open, capability on save) and written into the `oscal-version` field of saved capability files.

### 5.2 CatalogTab (catalog_tab.py)

Displays the catalog control list and a scrollable detail pane.

**Owns:**
- `_all_controls` — the complete flat list from the catalog
- `_filtered_controls` — the currently visible subset
- `_profile_ids` — the profile filter (set by app via `apply_profile()`)
- `_selected_class` — the class dropdown value
- `_selected_guideline` — the guideline dropdown value
- `_search_var` — the search box text
- `_wrap_labels` — list of detail-pane labels whose `wraplength` is updated dynamically when the pane is resized

**Filter toolbar contains:** Class dropdown, Guideline dropdown, Search box, control count label.

**Guideline column:** The Treeview has four columns — ID/Label, Title/Statement, Class, and Guideline. The Guideline column shows the top-level catalog group (e.g. "Guidelines for cyber security roles"). A Guideline filter dropdown lets the user restrict the list to one group at a time.

**Dynamic text wrapping:** All text labels in the detail pane have their `wraplength` updated whenever the right pane is resized (`_on_canvas_configure`). This replaces hardcoded pixel values that caused text to overflow when the window was resized.

**Public methods the app calls:**
- `load_controls(controls)` — replaces the full list after a catalog is loaded
- `apply_profile(profile_ids)` — applies or removes the profile filter

**Internal filtering:** all four filters (profile, class, guideline, search) are applied together inside `_apply_filters()` which runs whenever any one of them changes.

### 5.3 ComponentTab (component_tab.py)

Creates and edits OSCAL Component Definition files. Each component is saved as its own individual JSON file.

**Owns:**
- `_components` — list of component dicts (the in-memory list)
- `_filtered_indices` — list of indices into `_components` currently shown in the listbox after search/type filtering
- `_file_uuid`, `_file_title`, `_file_version` — file-level metadata
- `_selected_index` — index into `_components` (not the listbox position) for the component currently open in the form
- `_ctrl_responses` — `{control_id: description}` for the current component
- `_selected_ctrl_id` — which control is selected in Section 9
- `_dirty` — whether there are unsaved changes

**Guard condition:** requires a catalog. Profile is optional — if loaded, Section 9 shows only profile controls; without one the full catalog is shown.

**Component list search/filter:** the left pane has a live text search box and a type dropdown above the component listbox. Typing filters by title, type, or description; selecting a type shows only that category. The count in the panel header updates to show `showing / total`. Filters reset automatically when loading new files or adding a component. The `_filtered_indices` list maps listbox display positions to actual `_components` list indices, decoupling the two so filtering does not corrupt the index used for editing.

**Form sections:**
1. Basic Information (title, type, purpose)
2. Description
3. Operational Status
4. Properties (name/value metadata)
5. Responsible Roles
6. Protocols (TCP/UDP port ranges)
7. Links (external references: vendor docs, CVE advisories, configuration baselines)
8. Remarks
9. Control Implementations (All Controls / Applied Controls tabs with dot indicators)

**File operations:**
- `📂 Open File(s)` — loads one or more component JSON files (components appended, duplicates by UUID skipped)
- `📁 Open Folder` — loads every `.json` file in a chosen directory
- `💾 Save Component` — validates and saves the selected component to its own file

**Public methods the app calls:**
- `on_catalog_or_profile_changed()` — re-evaluates the guard condition
- `set_on_components_changed(callback)` — registers the CapabilityTab's `on_state_changed` to be called whenever the component list changes
- `add_component(comp)` — adds a component dict if its UUID is not already present; called by CapabilityTab when loading a capability file that bundles member components

**Dialog helper:** `_make_dialog(title, width)` creates a styled modal Toplevel with `transient` + `grab_set` behaviour. Used by `_property_dialog`, `_role_dialog`, `_protocol_dialog`, and `_link_dialog`.

### 5.4 CapabilityTab (capability_tab.py)

Creates and edits OSCAL Capability Definition files. A capability is a named security function composed of one or more components, with control implementations that may be inherited from members or defined at the capability level.

**Owns:**
- `_capabilities` — list of capability dicts (in-memory state)
- `_sel_index` — which capability is selected
- `_ctrl_responses` — `{control_id: description}` for the selected capability's capability-level responses
- `_sel_ctrl_id` — which control is selected in Section 3

**In-memory capability dict format:**
```python
{
    "uuid":                     str,
    "name":                     str,
    "description":              str,
    "remarks":                  str,
    "member_uuids":             [str, ...],   # component UUIDs
    "member_descriptions":      {uuid: str},  # each member's role in this capability
    "ctrl_responses":           {ctrl_id: str},  # capability-level responses
    "inherited_ctrl_responses": [             # synced from member components
        {
            "ctrl_id":                str,
            "description":            str,
            "source_component_uuid":  str,
            "source_component_title": str,
        }, ...
    ]
}
```

**Control inheritance:** When a component is added as a member, `_resync_inherited_for_cap()` reads that component's `ctrl_responses` and adds them to the capability's `inherited_ctrl_responses` list with the source component's UUID and title. This is re-run on every `on_state_changed()` call. The Section 3 UI shows inherited responses (read-only, attributed to their source component) separately from capability-level responses (editable).

**File operations:**
- `📂 Open File(s)` — loads one or more capability JSON files; bundled member components are imported into ComponentTab's live list via `add_component`
- `📁 Open Folder` — loads every `.json` file in a chosen directory
- `💾 Save Capability` — validates, optionally schema-checks, and saves the selected capability with its member components bundled

**OSCAL output format:** The saved file is an OSCAL `component-definition` document with:
- `components[]` — the bundled member components (serialised via `build_component_oscal_entry`)
- `capabilities[0]` — the capability definition with `incorporates-components` and `control-implementations`
- Inherited responses saved as `implemented-requirement` entries with a `props[{name: "source-component-uuid", value: "..."}]` entry for attribution
- Capability-level responses saved as `implemented-requirement` entries without that prop

**Public methods the app calls:**
- `on_state_changed()` — re-evaluates guard, resyncs inherited controls, refreshes the form

### 5.5 SSPTab (ssp_tab.py)

Creates and edits OSCAL System Security Plan files.

**Owns:**
- `_ssp` — the in-memory SSP dict (see Section 4.6)
- All form widgets (StringVars, Text widgets, Treeview tables)
- `_file_path` — path to the last saved/opened SSP file (for re-save without dialog)

**Key operations:**
- `💾 Save SSP` — collects form values, validates, and saves as OSCAL JSON
- `📂 Open SSP` — parses an existing OSCAL SSP JSON file back into the form
- `📄 Export to Word` — calls `models.build_ssp_docx()` to generate a formatted `.docx` report (disabled if `python-docx` is not installed)

**Public methods the app calls:**
- `refresh_profile_box()` — updates the profile info label in the SSP toolbar

### 5.6 POAMTab (poam_tab.py)

Creates and edits OSCAL Plan of Action and Milestones (POAM) files.

**Owns:**
- `_poam` — the in-memory POAM dict
- Form widgets for local definitions, findings, risks, and milestones

**Key operations:**
- `💾 Save POAM` — saves as OSCAL JSON
- `📂 Open POAM` — parses an existing OSCAL POAM file

---

## 6. How Data Flows Through the Application

### 6.1 Loading a catalog

```
User clicks "📂 Open Catalog"
    │
    ▼
app._open_catalog()
    │ json.load() → models.validate_oscal_file() → warns if invalid
    │ models.load_catalog(filepath)
    │   → collect_controls() walks the nested catalog tree
    │   → returns flat catalog dict (with "guideline" field per control)
    │
    ├─► stores in self._catalog
    ├─► updates catalog info card labels
    ├─► resets profile state (self._profile = None)
    │
    ├─► catalog_tab.load_controls(catalog["controls"])
    │       populates class and guideline dropdowns
    │       resets search, count label, populates the Treeview
    │
    ├─► ssp_tab.refresh_profile_box()
    ├─► component_tab.on_catalog_or_profile_changed()
    └─► capability_tab.on_state_changed()
```

### 6.2 Loading a profile

```
User clicks "🔖 Open Profile"
    │
    ▼
app._open_profile()
    │ models.load_profile(filepath)
    │   → collects control IDs into a Python set
    │
    ├─► stores in self._profile
    ├─► catalog_tab.apply_profile(profile["ids"])
    ├─► ssp_tab.refresh_profile_box()
    ├─► component_tab.on_catalog_or_profile_changed()
    └─► capability_tab.on_state_changed()
```

### 6.3 Filtering the catalog (CatalogTab internal)

```
_apply_filters()
    │
    ├─► Step 1 — Profile filter
    │   if _profile_ids is not None: keep controls in the profile set
    │
    ├─► Step 2 — Class filter
    │   if _selected_class != "All": keep controls with matching class
    │
    ├─► Step 3 — Guideline filter
    │   if _selected_guideline != "All": keep controls in that top-level group
    │
    ├─► Step 4 — Text search
    │   if search term not empty: match against label, title, statement, id, guideline
    │
    └─► _populate_tree(result) → _update_count()
```

### 6.4 Filtering the component list (ComponentTab internal)

```
_on_comp_filter_changed()   ← fires on every keystroke or type dropdown change
    │
    ▼
_refresh_list()
    │
    ├─► _build_filtered_indices()
    │       for each component in self._components:
    │           apply type filter
    │           apply text search (title, type, description)
    │           → returns list of matching indices into self._components
    │
    ├─► clears and repopulates the Listbox from _filtered_indices
    ├─► updates the count label (showing / total)
    └─► re-selects the current component if it is still in the filtered view
```

The key design decision: the Listbox display positions (0, 1, 2…) are NOT the same as `self._components` indices when a filter is active. `_filtered_indices[list_pos]` converts from display position to component index. `_selected_index` always stores the component index, not the display position.

### 6.5 Saving a Component Definition

```
User fills form → "✔ Apply Component Changes" → "💾 Save Component"
    │
    ├─► _collect_into(index)    reads all form widgets into component dict
    ├─► _validate_selected()    checks required fields (title, description)
    ├─► filedialog.asksaveasfilename()
    ├─► models.get_source_href(profile, catalog)
    ├─► models.build_component_oscal_entry(comp, source_href)
    │       serialises props, roles, protocols, links, control-implementations
    └─► json.dump(doc, file, indent=2)
```

### 6.6 Saving a Capability

```
User builds capability → "💾 Save Capability"
    │
    ├─► _collect_into(index)    reads form into capability dict
    ├─► _validate_selected()    checks name, description, members, UUID resolution
    ├─► filedialog.asksaveasfilename()
    ├─► _build_oscal_document(cap)
    │     models.get_source_href(profile, catalog)
    │     models.build_component_oscal_entry() for each member component
    │     inherited responses → implemented-requirements with source-component-uuid prop
    │     capability-level responses → implemented-requirements without the prop
    ├─► models.validate_oscal_file() → warns if schema violations found
    └─► json.dump(doc, file, indent=2)
```

### 6.7 Loading a Capability file

```
User clicks "📂 Open File(s)" in Capability Editor
    │
    ├─► _load_capability_from_path(path)
    │     json.load() → check "component-definition.capabilities" exists
    │     rebuild in-memory capability dict from OSCAL structure
    │     for each bundled component:
    │         component_tab.add_component(comp_dict)  ← imports if not already open
    │     _resync_inherited_for_cap(cap)              ← resolve source titles
    │
    └─► _after_open(added, skipped)
          _refresh_list() → auto-select first loaded capability
```

### 6.8 Saving an SSP

```
User clicks "💾 Save SSP"
    │
    ├─► _collect()              reads all form widgets into self._ssp
    ├─► models.validate_ssp()   returns (errors, warnings)
    ├─► filedialog.asksaveasfilename()
    ├─► models.build_oscal_ssp(ssp, profile, catalog)
    └─► json.dump(doc, file, indent=2)
```

---

## 7. Inter-Tab Communication

Tabs never talk directly to each other. All communication goes through `OSCALApp` using the **callback (dependency injection) pattern**:

```
┌──────────────┐     callbacks      ┌──────────────────┐
│   OSCALApp   │ ─────────────────► │   CatalogTab     │
│              │                    │                  │
│ _catalog     │ get_catalog=       │ _all_controls    │
│ _profile     │   lambda: self._catalog               │
│              │                    │                  │
│              │ ─────────────────► │  ComponentTab    │
│              │                    │                  │
│              │ get_profile=       │ _components      │
│              │   lambda: self._profile               │
│              │                    │                  │
│              │ ─────────────────► │  CapabilityTab   │
│              │                    │                  │
│              │ get_components=    │ _capabilities    │
│              │   lambda: comp_tab │                  │
│              │   ._components     │                  │
│              │                    │                  │
│              │ add_component=     │ (imports bundled │
│              │   comp_tab         │  components on   │
│              │   .add_component   │  capability load)│
└──────────────┘                    └──────────────────┘
```

The **component-change notification** is wired separately:

```python
component_tab.set_on_components_changed(
    capability_tab.on_state_changed
)
```

This ensures the Capability Editor re-evaluates its guard (at least one component must be open) whenever the Component Editor's list changes.

**Why lambdas?** A lambda like `lambda: self._catalog` gives a tab a way to ask "what catalog is loaded right now?" without holding a reference to the app. The tab calls `self._get_catalog()` and gets the current value at that moment — not a copy taken at construction time. This is the **dependency injection** pattern: the tab declares what it needs; the app decides what to provide.

---

## 8. The Guard Pattern

Both ComponentTab and CapabilityTab enforce prerequisites before editing is permitted. This is implemented as a **gate panel** that covers the editing area.

**ComponentTab guard:** requires a catalog. Profile is optional.

**CapabilityTab guard:** requires both a catalog AND at least one component open in the Component Editor.

```
on_catalog_or_profile_changed() / on_state_changed()
    │
    ├─► _ready()   True only if prerequisites are met
    │
    ├── if NOT ready:
    │       body_pane.pack_forget()     hide editing area
    │       gate_frame.pack(...)        show lock panel with ✅/❌ checklist
    │
    └── if ready:
            gate_frame.pack_forget()   hide lock panel
            body_pane.pack(...)        show editing area
```

---

## 9. The OSCAL JSON Structures

### 9.1 Catalog (read-only input)

```json
{
  "catalog": {
    "uuid": "...",
    "metadata": { "title": "...", "version": "...", "oscal-version": "1.1.2" },
    "groups": [
      {
        "title": "Guidelines for cyber security roles",
        "groups": [
          {
            "title": "Board of directors and executive committee",
            "controls": [
              {
                "id": "ism-0016",
                "class": "ISM-control",
                "props": [{"name": "label", "value": "0016"}],
                "parts": [{"name": "statement", "prose": "..."}]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The ISM catalog has 3 levels of group nesting. The top-level group title ("Guidelines for cyber security roles") becomes the `guideline` field on each control collected from that branch.

### 9.2 Component Definition (created by ComponentTab)

```json
{
  "component-definition": {
    "uuid": "auto-generated",
    "metadata": {
      "title": "hardware - My Firewall",
      "last-modified": "2026-06-25T10:00:00Z",
      "version": "1.0",
      "oscal-version": "1.1.2"
    },
    "components": [
      {
        "uuid": "auto-generated",
        "type": "hardware",
        "title": "My Firewall",
        "description": "A perimeter firewall...",
        "props": [{"name": "operational-status", "value": "operational"}],
        "responsible-roles": [{"role-id": "asset-administrator"}],
        "protocols": [
          {
            "uuid": "auto-generated",
            "name": "https",
            "title": "HTTPS management console",
            "port-ranges": [{"start": 443, "end": 443, "transport": "TCP"}]
          }
        ],
        "links": [
          {
            "href": "https://vendor.com/hardening-guide",
            "rel": "vendor-documentation",
            "text": "Vendor Hardening Guide"
          },
          {
            "href": "https://nvd.nist.gov/vuln/detail/CVE-2024-1234",
            "rel": "security-advisory",
            "text": "CVE-2024-1234"
          }
        ],
        "control-implementations": [
          {
            "uuid": "auto-generated",
            "source": "ISM_profile.json",
            "description": "Control implementations for My Firewall.",
            "implemented-requirements": [
              {"uuid": "...", "control-id": "ism-1130", "description": "..."}
            ]
          }
        ]
      }
    ]
  }
}
```

### 9.3 Capability Definition (created by CapabilityTab)

```json
{
  "component-definition": {
    "uuid": "auto-generated",
    "metadata": { "title": "Capability: Account Management", "oscal-version": "1.1.2" },
    "components": [
      { "uuid": "comp-uuid-1", "type": "software", "title": "LDAP Directory", ... },
      { "uuid": "comp-uuid-2", "type": "software", "title": "IAM Service", ... }
    ],
    "capabilities": [
      {
        "uuid": "cap-uuid",
        "name": "Account Management",
        "description": "Manages user accounts across the system.",
        "incorporates-components": [
          {"component-uuid": "comp-uuid-1", "description": "Provides directory store."},
          {"component-uuid": "comp-uuid-2", "description": "Provides provisioning."}
        ],
        "control-implementations": [
          {
            "uuid": "...",
            "source": "ISM_profile.json",
            "description": "...",
            "implemented-requirements": [
              {
                "uuid": "...", "control-id": "ism-0415", "description": "LDAP enforces...",
                "props": [{"name": "source-component-uuid", "value": "comp-uuid-1"}]
              },
              {
                "uuid": "...", "control-id": "ism-0415", "description": "IAM provides...",
                "props": [{"name": "source-component-uuid", "value": "comp-uuid-2"}]
              },
              {
                "uuid": "...", "control-id": "ism-0415", "description": "Combined: ..."
              }
            ]
          }
        ]
      }
    ]
  }
}
```

The `source-component-uuid` prop is the OSCAL extension mechanism for component attribution in component-definition files. The `by-component` field (which provides this natively) is only available in SSP, not in component-definition.

### 9.4 System Security Plan (created by SSPTab)

```json
{
  "system-security-plan": {
    "uuid": "...",
    "metadata": { "title": "My System SSP", "oscal-version": "1.1.2", ... },
    "import-profile": { "href": "#back-matter-resource-uuid" },
    "system-characteristics": { ... },
    "system-implementation": {
      "components": [{"uuid": "...", "type": "this-system", ...}]
    },
    "control-implementation": { "implemented-requirements": [] },
    "back-matter": {
      "resources": [{"uuid": "back-matter-resource-uuid", "title": "Profile name", ...}]
    }
  }
}
```

---

## 10. Key Design Decisions

### 10.1 Internal format vs OSCAL format

The application maintains two representations of each document:

| Representation | Where used | Example |
|---|---|---|
| **Internal dict** | In memory during editing | `ssp["system_name"]` |
| **OSCAL JSON** | On disk / for interoperability | `"system-characteristics": {"system-name": ...}` |

Conversion between them happens only at load time and save time. This makes the form code much simpler — it works with flat Python dicts rather than deeply nested OSCAL structures.

### 10.2 UUIDs

OSCAL requires a UUID on every significant object. The toolkit auto-generates UUIDs using `uuid.uuid4()` so the user never has to manage them. Once generated, a UUID is preserved across edits so that the same document remains consistently identifiable.

### 10.3 Back-matter for profile provenance

When saving an SSP, the toolkit records the loaded profile's title, version, and filename inside the SSP's `back-matter` section. The `import-profile.href` is then set to `#<uuid>` pointing at that back-matter entry. This means the SSP is self-documenting — anyone reading the file can see exactly which profile version was used.

### 10.4 The `set` type for profile IDs

Profile IDs are stored as a Python `set` rather than a list. The `in` operator on a set is O(1) regardless of set size. Since the catalog filter checks every control against the profile IDs, this matters when there are 1,000+ controls.

### 10.5 Flat control list

The OSCAL catalog is a deeply nested tree. `collect_controls()` flattens it into a single list at load time. The `path` (breadcrumb) and `guideline` (top-level group name) fields preserve hierarchy context for display and filtering without requiring the GUI to traverse the tree.

### 10.6 Schema validation — warn, don't block

Both catalog loading and capability saving validate against the OSCAL schema zip if `jsonschema` is installed. Validation failures show a warning dialog (ask yes/no) rather than hard-blocking the operation. This is intentional: real-world OSCAL files sometimes have minor schema deviations, and blocking would make the tool unusable with those files.

### 10.7 Capability control inheritance

The OSCAL `component-definition` schema has no `by-component` field (that is SSP-only). To attribute control responses to specific components within a capability, the toolkit uses the OSCAL `props` extension mechanism: each inherited `implemented-requirement` carries a prop named `source-component-uuid`. This is OSCAL-conformant and round-trips correctly when the file is loaded back in.

### 10.8 Tab reorder-safe mousewheel

Both ComponentTab and CapabilityTab use `bind_all("<MouseWheel>", ...)`, which fires on all tabs. To scroll only the active tab's canvas, each handler compares `self.master.select()` against `str(self)` — the widget path string that uniquely identifies this tab's frame. This is resilient to tab reordering, unlike hardcoding a tab index integer.

### 10.9 Dialog boilerplate via `_make_dialog`

Both ComponentTab and CapabilityTab need multiple modal dialogs. Each tab has a `_make_dialog(title, width)` method that creates a styled, modal `Toplevel` with `transient` + `grab_set` behaviour. Individual dialog methods call this instead of repeating the same setup code.

### 10.10 Component list filtering via `_filtered_indices`

When a search term or type filter is active in the Component Editor, only a subset of components is visible in the listbox. A naive approach would store the selected component's listbox position — but that position changes whenever the filter changes. Instead, `_selected_index` always stores the real position in `self._components`. The `_filtered_indices` list maps listbox display positions to `_components` indices: `_filtered_indices[list_pos]` gives the component index for any listbox row. This means filtering never corrupts the selection.

### 10.11 OSCAL links on components

Components support an OSCAL `links` array for attaching external references. Nine `rel` relationship types are predefined in the editor (`reference`, `vendor-documentation`, `security-advisory`, `configuration-baseline`, `policy`, `homepage`, `related`, `dependency`, `required-by`). These are serialised directly to the OSCAL `links` array on save and parsed back on load, making them a clean roundtrip.

### 10.12 Data flow links stored as grouped props, not on Information Types

An earlier iteration attached structured "which component sends this information type where" data to each Information Type (SSP Section 5), encoded as `props` with `class: "data-flow"` in fixed-order triplets. This was removed after checking `oscal_ssp_schema.json` directly: the `information-type` object (`additionalProperties: false`) has no field for component-to-component flow data at all — it was the wrong OSCAL object, and the fixed-order triplet encoding had no correlation key, so it silently broke if props were ever reordered.

The dedicated `system-characteristics.data-flow` object is the correct home for this concept, but its schema is equally sparse: only `description` (free text), `props`, `links`, `diagrams[]`, and `remarks` — no structured field for an edge list either. OSCAL's `property` object does have a `group` field, though, documented as "an identifier for relating distinct sets of properties" — the sanctioned mechanism for exactly this problem.

**Decision:** each data flow link (Section 4) is stored as a set of `data-flow.props[]` entries — one prop per field (`data-flow-source`, `data-flow-target`, `data-flow-protocol`, `data-flow-port`, `data-flow-transport`, `data-flow-direction`, `data-flow-description`, plus cached `-name` props for the two component titles) — all sharing the flow's UUID as their `group` value, and all tagged with a fixed `ns` (`https://oscal-user-toolkit/ns/data-flow-link`) so they can't collide with another tool's props and so `parse_ssp_file()` knows which grouped props to reassemble (`_build_data_flow_link_props` / `_parse_data_flow_link_props` in `models.py`). This is order-independent (unlike the removed triplet encoding) and keeps the data inspectable as ordinary name/value props to any OSCAL-conformant tool that doesn't recognise the vocabulary, rather than hiding it in an opaque base64 blob.

Because `data-flow.description` is the field any plain OSCAL consumer will actually read, `build_oscal_ssp()` auto-drafts a narrative summary from the flow links (`_data_flow_links_narrative()`) whenever the user hasn't written their own Data Flow description text, so the document stays meaningful outside this toolkit even when the structured detail lives in custom props. Component titles cached on each flow link are also re-resolved against the current components list on load (`_refresh_flow_link_titles()`), in case a component was renamed since the flow was recorded — the same cached-title-refresh pattern used for responsible-parties party names (§10.11-adjacent, `parse_ssp_file`).

**VLANs (Section 4) reuse the same pattern on `network-architecture`**, which has the identical sparse schema shape (`description`/`props`/`links`/`diagrams`/`remarks`, `additionalProperties: false`). Each VLAN is a set of `network-architecture.props[]` entries (`vlan-id`, `vlan-name`, `vlan-description`) sharing the VLAN's UUID as `group`, tagged with `ns: https://oscal-user-toolkit/ns/vlan` (`_build_vlan_props` / `_parse_vlan_props` in `models.py`). No narrative auto-draft is generated for VLANs — unlike data flow, a list of VLAN IDs/names doesn't reduce to a natural sentence the way a source→target edge does, so `network-architecture.description` is left to the user as free text.

### 10.13 Library folder — a shared source, copied into each system's own folder

Large organisations maintain a shared library of reusable components/capabilities (and eventually catalogs/profiles) at an org level, separate from any one system's SSP. Rather than have every editor tab reach into that shared library directly (which risks two systems silently sharing and mutating the same file), the design copies a library item into the current system's own folder at import time, and every SSP-side tool only ever reads/writes that copy — never the library source. This mirrors, and is a direct generalisation of, the "independent editable copy" behaviour `ssp_tab.py`'s older `_import_component_file` already had for one-off component-definition imports.

**Where the library path lives:** a small module, `settings.py`, persists the configured library folder in `settings.json` inside the `oscal_user_toolkit/` package folder itself (`.gitignore`d, since it's machine-specific) — a per-installation preference rather than OSCAL content. `set_library_path()` also creates the standard `catalogs/`, `profiles/`, `components/`, `capabilities/` subfolders if missing. If nothing has been configured yet, `get_library_path()` falls back to `DEFAULT_LIBRARY_PATH` — the repo's own `library/` folder — so the app and Import from Library work out of the box without a manual setup step. `OSCALApp` loads this once at startup (`self._library_path = settings.get_library_path()`) and exposes it to other tabs via a `get_library_path()` callback, plus a "📚 Library Folder" toolbar button (`_set_library_folder()`) to change it. `settings.py` also persists the default light/dark theme (`get_theme()`/`set_theme()`), applied on startup before any widget is built.

**Where "the current system's folder" comes from:** rather than invent a second concept to track, the design reuses the existing workspace manifest path (`self._workspace_path`, already tracked for Save/Open Workspace) — `OSCALApp.get_system_folder()` simply returns that path's parent directory, or `None` if no workspace is active yet. A system's folder is therefore just wherever its workspace JSON lives, which is also the natural place for that workspace's `components/`/`capabilities/` subfolders to sit alongside it.

**The import action itself** (`_import_from_library()` in `component_tab.py` and `capability_tab.py`) requires both a configured library path and an active system folder — it refuses with a clear message if either is missing, rather than silently picking an arbitrary destination. It copies the chosen library file(s) into `<system folder>/components/` (or `.../capabilities/`), skipping any file whose name already exists at the destination so that re-importing never clobbers a copy the user has since edited for this system, then loads the copies into the tab's in-memory list via the existing `load_from_paths()` — the same function already used by "Open Folder", so import behaves identically to opening a folder of files, just with an extra copy step first.

**Scope note:** this stage makes Component Editor and Capability Editor library-aware and gives them a working import-into-system-folder action. It does **not** yet change how the SSP Editor, Assessment Plan, or POA&M editors source their own component/capability lists — those still use their pre-existing mechanisms (`ssp_tab.py`'s own `_import_components_from_files`/`_import_capability_into_ssp`, independent of the system folder). Making those tabs read from the system folder is a separate, not-yet-built stage — see `user_stories.md` US-12 and `todo.md`.

### 10.14 Data Sources tab replaces the toolbar's Open Catalog/Profile buttons

Extending the Library concept (§10.13) to catalogs/profiles meant deciding where "browse the library's catalogs/profiles" should live. Rather than add a second way to open a catalog/profile alongside the existing toolbar buttons, the toolbar's "📂 Open Catalog", "🔖 Open Profile", and "✕ Clear Profile" buttons were removed from `app.py._build_toolbar()` entirely, and `data_sources_tab.py` — previously a "feature coming soon" placeholder — became the single place to open, browse, or clear a catalog/profile.

The tab lists every `.json` file directly under the configured library's `catalogs/` and `profiles/` subfolders (re-scanned on `refresh()`, not cached), alongside a "…  Browse Elsewhere" button per list that falls through to `app.py`'s own file dialog (`_open_catalog()`/`_open_profile()` called with `path=None`) — so a catalog or profile that isn't in the library can still be opened; the library list is a shortcut for the common case, not the only path in. Selecting a library entry and clicking "📂 Load Selected" (or double-clicking) calls the same `_open_catalog(path)`/`_open_profile(path)` methods with the file's path directly.

`app._catalog`/`app._profile` remain the single source of truth, exactly as before — `DataSourcesTab` holds no catalog/profile state of its own. It reflects the current selection via `get_catalog()`/`get_profile()` callbacks, and `OSCALApp` now calls `self._data_sources_tab.refresh()` at the end of `_open_catalog()`, `_open_profile()`, and `_clear_profile()` (alongside the existing `on_catalog_or_profile_changed()`/`on_state_changed()` calls to the Component/Capability tabs), so the tab's "currently loaded" labels and Clear Profile button's enabled state stay correct regardless of which tab triggered the change (including Open Workspace, which calls `_open_catalog`/`_open_profile` with an explicit path).

### 10.15 Closing the loop: SSP reads the system folder; AP/POA&M get read-only visibility

§10.13 gave Component/Capability Editor a way to import a library item into the current system's folder. On its own, that import didn't do anything for the SSP itself — the SSP Editor's Section 8/9 still only knew about components/capabilities added through its own older, separate `_import_components_from_files`/`_import_capability_into_ssp` mechanism. This stage connects the two.

**SSP Editor — "🔄 Sync from System Folder" (Section 8):** a new `_sync_from_system_folder()` reads every file in `<system folder>/components/` and `.../capabilities/` and imports them. It deliberately reuses, rather than duplicates, the existing single-file import logic:
- Component files go through the existing `_import_component_file()` unchanged — it already knows the "one `component-definition` document, N components" shape and already dedups by UUID and auto-populates Section 9 by-component entries.
- Capability files (saved by `capability_tab.py`'s "💾 Save Capability", which bundles a capability's member components in the *same* document) are handled by a new `_import_capability_file()`. Since a capability file is a `component-definition` document with an extra `capabilities` array, its bundled components are imported via the *same* `_import_component_file()` call — `_import_capability_file()` only has to handle that extra array: recording each capability in Capabilities Used (Section 7a), and walking its `control-implementations` to either add a by-component response (when an `implemented-requirement` carries a `source-component-uuid` prop) or fold a capability-level-only response into that control's Section 9 remarks (when it doesn't) — the same two cases `_import_capability_into_ssp()` already handles for a *live* capability from the Capability Editor tab, just driven from a parsed file instead of an in-memory dict.
- Both paths dedup by UUID (`_add_by_component_response()`'s existing "already has an entry for this component" check), so re-running Sync after adding more files to the system folder is always safe — nothing is duplicated.

This intentionally does **not** replace the older `_import_components_from_files`/`_import_capability_into_ssp` paths — a user can still hand-pick an arbitrary file, or pull a capability that's only ever been opened live in the Capability Editor. Sync from System Folder is an additional, system-folder-scoped path alongside them.

**Assessment Plan / POA&M — read-only SSP awareness:** `ap_tab.py` already had a components tree fed by `_refresh_ssp_components()`, which parses the referenced SSP file directly from disk (not via the SSP Editor tab, so it works even if that tab never opened this particular file) — it just had no equivalent for capabilities. Both `ap_tab.py` and `poam_tab.py` (which previously had no SSP-derived visibility at all beyond the bare `import_ssp` reference field) now show a read-only Capabilities pane alongside Components, populated from the same parsed SSP's `capabilities_used` list. This is deliberately name-only: OSCAL's SSP schema has no native capabilities structure (`capabilities_used` is a toolkit-side tag list — `{uuid, name}`, see §4.6), so a capability's member components aren't recoverable from the SSP file alone once you're outside the toolkit's own live Capability Editor state. Both tabs are strictly read-only here — no write path was added, matching the design decision that editing a system's components/capabilities stays the System Owner's job in Component/Capability Editor, not the auditor's.

### 10.16 Workspace manifest resolves catalog/profile against the Library, not just the workspace folder

`build_workspace_manifest()`/`load_workspace_manifest()` (§6.8) originally stored every referenced file — catalog, profile, SSP, components, etc. — as a path relative to the workspace manifest's own folder, so the whole folder stayed portable if moved or shared. That assumption broke once catalogs/profiles became Library resources (§10.13/§10.14): a catalog opened via the Data Sources tab now normally lives in the Library folder, which is a separate, independently-configured location, not inside any one system's workspace folder. A workspace-relative path to it (`../../library/catalogs/x.json`) is fragile — it silently breaks if the workspace folder is ever shared or moved on its own, and it broke outright for the bundled `example-data-ism/workspace_ERN.json`, whose catalog/profile were plain filenames relative to `example-data-ism/` from before the Library existed, pointing at files that have since moved to `library/catalogs/`/`library/profiles/`.

**Fix, save side:** `build_workspace_manifest()` now checks whether the given catalog/profile path sits directly inside the *configured* Library's `catalogs/`/`profiles/` subfolder. If it does, only the bare filename is stored (resolved against whatever Library is configured on the machine that opens it later — see load side). Otherwise it falls back to the original workspace-relative path, unchanged, which still covers a catalog/profile opened from outside the Library via Data Sources' "…  Browse Elsewhere".

**Fix, load side:** `load_workspace_manifest()` tries the workspace-relative interpretation *first* (matching every other field, and covering the non-Library case above), and only falls back to resolving the same filename against the configured Library's `catalogs/`/`profiles/` subfolder if that file doesn't exist. This fallback is what fixes *already-saved* workspace files like `workspace_ERN.json` without needing to edit them — no schema change or version marker was needed, since the fallback only ever triggers when the primary (workspace-relative) resolution fails to find a file, which is exactly the situation those older files are now in.

### 10.17 CatalogResolver — foundation for multi-catalog profiles (todo.md §3, stage 1 of 3)

The app has always treated catalog and profile as strictly 1:1 — one `self._catalog` dict, loaded once via Open Catalog. OSCAL's own profile schema doesn't have that limitation: a profile's `imports[]` is an array, each entry independently referencing its own catalog (or another profile) via `href`, with its own `include-controls`/`include-all`/`exclude-controls` selection (confirmed directly against `oscal_profile_schema.json`'s `import` definition) — the documented pattern for a baseline spanning two frameworks (e.g. SP 800-53 + SP 800-171). `load_profile()` already walked every import to build a flat, merged `ids` set, but discarded which import each ID came from, so there was no way to know which catalog a given control actually belongs to once more than one is involved.

**`CatalogResolver`** (`models.py`) is a small class an `OSCALApp` instance owns one of (`self._resolver`), holding every loaded catalog keyed by **resolved absolute file path** — not by the href as written in a profile or component file. An href is only meaningful relative to whichever file declared it (two profiles could use different relative hrefs for the same catalog, or the same href could resolve to different files from different directories), so resolving to an absolute path first is what makes the resolver's cache key collision-free regardless of which file referenced a given catalog.

**Auto-load, not manual "Add Catalog"** (Option A from the brainstorm that preceded this): `CatalogResolver.load_from_profile(profile, profile_path)` is called from `app.py`'s `_open_profile()` after the profile loads successfully. It re-reads `profile_path` itself directly (rather than trusting `load_profile()`'s already-flattened return value, whose new `imports` list — added alongside the unchanged `ids` set for backward compatibility — doesn't retain back-matter), because **an import's `href` is frequently a `"#uuid"` reference to one of the profile's own back-matter resources**, not a direct file path — confirmed on the actual bundled NIST example profiles, which use exactly this indirection to point at their source catalog. This is the *same* indirection `parse_ssp_file()` already resolves for `import-profile.href`; `load_from_profile()` mirrors that logic (look up the back-matter resource by UUID, take its first `rlink`) rather than inventing a second resolution scheme. Each resolved href is then treated as relative to the profile file's own directory, exactly like every other relative-href resolution elsewhere in this app. An href that doesn't resolve to a real local file — e.g. many published OSCAL profiles' `rlinks` point at the *upstream content repository's* own directory layout (confirmed on the bundled NIST profiles, whose rlinks assume a `nist.gov/SP800-53/rev5/json/...` structure that doesn't exist locally) — is silently skipped, matching how this app has never fetched remote URLs.

**What this stage does and doesn't do:** `self._catalog` remains "the" catalog for every tab not yet updated to consult the resolver — Catalog Viewer, Component Editor, SSP Editor, Capability Editor all still work exactly as before, reading only the one manually-opened catalog. The resolver exists, is populated automatically by `_open_profile()`, and is exposed via a `get_resolver()` callback (mirroring `get_library_path()`/`get_system_folder()`) — but nothing consumes `resolve_control()`/`all_controls()` yet except a small "(+N more via profile imports)" note on the Data Sources tab's catalog label, added mainly to make this stage independently verifiable. Loading a brand-new catalog via Open Catalog clears the resolver first (a fresh catalog starts a fresh multi-catalog session) and re-adds itself, so the resolver and `self._catalog` never disagree about which catalogs are "current."

**Still to come (stages 2–3, not built yet):** Component Editor's "All Controls"/"Applied Controls" trees gaining a Source column and Source filter, sourced from `resolver.all_controls()` instead of the single active catalog (the UI design settled on merging every loaded catalog into one filterable list rather than a catalog switcher or per-catalog tabs); and `build_component_oscal_entry()` in `models.py` grouping a component's control responses by distinct `source_href` into multiple `control-implementations` blocks, since it currently always emits exactly one block with one global `source`.

---

## 11. Example Component Library

The `example-data/components/` folder ships with 41 pre-built component files that demonstrate the full range of component types and OSCAL features. They are designed to be loaded wholesale using **Open Folder** and used as a starting point for customisation.

All example components include:
- ISM control implementations with detailed implementation narratives
- TCP/UDP protocol data (`protocols` array with `port-ranges`) where applicable
- External links to vendor documentation, ASD guidance, and relevant standards

The components span a realistic medium-to-large Australian government environment:

| Type | Count | Examples |
|---|---|---|
| hardware | 7 | Firewall, Network Switch, Wireless AP, NAS, UPS, Cabling, Network Encryptor |
| interconnection | 3 | Internet (filtered), WAN Link (IPsec), No Internet |
| operating-system | 4 | Windows 11, Windows Server 2022, RHEL 9, VMware ESXi 8 |
| policy | 8 | Patch Management, Backup, Remote Access, Incident Response, Access Control, Data Classification, System Usage, AD GPO Hardening |
| service | 12 | Active Directory, SQL Server, ManageEngine ServiceDesk Plus, Exchange Online, Veeam, VPN, DHCP, PKI/CA, Web Proxy, NTP, MongoDB, Windows Fileshare |
| software | 7 | Microsoft 365, Airlock Digital, Defender for Endpoint, Edge, Acrobat, Nessus, Sentinel |

---

## 12. Potential Future Enhancements

| Feature | Where it would go |
|---|---|
| SSP Stage 2 — full control responses (per-component, per-control narratives) | `ssp_tab.py` — Section 7 matching ComponentTab's Section 9 pattern |
| SSP ↔ Component linking (inherit responses via `by-component`) | `ssp_tab.py` + `models.py` — reference component UUIDs |
| Fix `status` field — use OSCAL `status.state` assembly rather than a prop | `models.py` (`build_component_oscal_entry`) + `component_tab.py` (`_parse_single_component`) |
| Stable protocol/CI UUIDs — store UUIDs in internal dict to prevent regeneration on save | `models.py` + `component_tab.py` |
| `ns` (namespace) on well-known OSCAL props | `models.py` (`build_component_oscal_entry`) |
| `set-parameters` editing in component control implementations | `component_tab.py` — new sub-section in Section 9 |
| Export to PDF / HTML report | New `report_tab.py` or standalone export function in `models.py` |
| Multiple catalogs / profiles open at once | `app.py` — change `self._catalog` to a list |
| Dark/light theme toggle | `app.py` — add a second COLORS dict and rebuild styles |

---

## 13. Changelog

### Version 3.6 (July 2026)

**New features (foundation only — see §10.17):**
- **`CatalogResolver`** (`models.py`): holds every loaded catalog keyed by resolved absolute path; `load_from_profile()` auto-loads any additional catalogs a profile's `imports[]` references, resolving `"#uuid"` back-matter indirection the same way `parse_ssp_file()` already does for `import-profile.href`.
- `app.py`: new `self._resolver`, populated on Open Catalog (reset + re-add) and Open Profile (auto-load additional imports); new `get_resolver()` callback (not yet consumed by any tab).
- `load_profile()` gained a new `imports` key (raw per-import href/include/exclude data) alongside the existing, unchanged `ids` set.
- Data Sources tab shows "(+N more via profile imports)" on the catalog label when a profile has auto-loaded additional catalogs.

**Not yet implemented (stages 2–3 of `todo.md` §3):** Component Editor's Source column/filter, and grouping a component's control-implementations by distinct source in `build_component_oscal_entry()`. `self._catalog` remains the single source every other tab reads from until those land.

### Version 3.5 (July 2026)

**Fixes:**
- **Workspace manifest catalog/profile resolution** (`models.py`, §10.16): `load_workspace_manifest()` now falls back to resolving a catalog/profile filename against the configured Library folder when the workspace-relative path doesn't exist — fixes opening `example-data-ism/workspace_ERN.json` (and any other pre-Library workspace file) without editing it, since its catalog/profile now live in `library/catalogs/`/`library/profiles/` instead of next to the workspace. `build_workspace_manifest()` also now stores just the filename (instead of a workspace-relative path) for a catalog/profile that lives directly inside the Library, so future saves resolve correctly even if the workspace and Library folders are shared/moved independently of each other.

### Version 3.4 (July 2026)

**New features:**
- **SSP Editor — "🔄 Sync from System Folder" (Section 8)**: imports every component/capability file in the current system's folder directly into the SSP, closing the loop on the Library → system folder pipeline from v3.2 (see §10.15). Reuses the existing `_import_component_file()` for components; new `_import_capability_file()` handles capability files' extra `capabilities` array (Capabilities Used entry + control-implementation folding), reusing `_import_component_file()` for their bundled member components.
- **Assessment Plan / POA&M — read-only Capabilities visibility**: both tabs now show a Capabilities pane (name only, read from the referenced SSP's `capabilities_used`) alongside their existing/new read-only Components pane. `poam_tab.py` previously had no SSP-derived visibility at all beyond the bare SSP reference field; it now mirrors `ap_tab.py`'s existing components-from-SSP pattern for both.

**Data model additions:**
- `ssp_tab.py`: `_import_capability_file()`, `_sync_from_system_folder()`, new `get_system_folder` constructor parameter (wired from `app.py`).
- `poam_tab.py`: `_refresh_ssp_components()` (new — mirrors `ap_tab.py`'s existing method), `parse_ssp_file` import.

### Version 3.3 (July 2026)

**New features:**
- **Data Sources tab is now the catalog/profile Library browser** (`data_sources_tab.py`, previously a placeholder): lists the configured library's `catalogs/`/`profiles/` subfolders, loads a selected file, browses elsewhere when needed, and shows/clears the currently loaded catalog/profile.
- Removed the toolbar's "📂 Open Catalog", "🔖 Open Profile", and "✕ Clear Profile" buttons (`app.py._build_toolbar()`) — the Data Sources tab is now the only way to open or clear a catalog/profile.
- "📂 Open Catalog"/"🔖 Open Profile" (still used internally, and by the Data Sources tab's "Browse Elsewhere") now default their file dialogs to the library's `catalogs/`/`profiles/` subfolders when those exist.

**Fixes:**
- `settings.py`'s library path now falls back to the repo's own `library/` folder (`DEFAULT_LIBRARY_PATH`) when nothing has been configured, instead of returning `None` and requiring a manual "Library Folder" click first.

### Version 3.2 (July 2026)

**New features:**
- **Library folder mechanism** (`settings.py`, new): a persisted, configurable folder holding shared `catalogs/`, `profiles/`, `components/`, `capabilities/` — set via a new "📚 Library Folder" toolbar button in `app.py`, persisted in `~/.oscal_user_toolkit/settings.json` across launches.
- **"📚 Import from Library" button** in Component Editor and Capability Editor: copies a file from the library into the current system's folder (derived from the active workspace's own folder — see §10.13) as an independent, editable copy, then loads it for editing. Refuses with a clear message if no library is configured or no workspace is active.

**Not yet implemented (see `user_stories.md` US-12, `todo.md`):**
- SSP Editor, Assessment Plan, and POA&M editors do not yet read a system's folder for its components/capabilities — this stage only covers importing them into that folder, not consuming them from it.
- Catalogs/profiles are not yet library-aware; only components/capabilities are, via Component/Capability Editor.

### Version 3.1 (July 2026)

**New features:**
- **SSP Editor — Section 4: Data Flow Links**: new table under the Data Flow description textbox for recording how data moves between the SSP's own components (Section 8) — source, target, protocol, port, transport, and direction; Add/Edit/Remove dialog with component dropdowns and a shared protocol name list (`COMMON_PROTOCOLS`, imported from `component_tab.py`)
- **SSP Editor — Section 4: VLANs**: new table under the Network Architecture description textbox (above the Network Architecture Diagrams table) for recording VLAN ID, name, and description; Add/Edit/Remove dialog

**Removed:**
- **Information Types — component data flows**: removed the `component_flows` concept and its "Export Data Flow Diagram" button from SSP Section 5. Checking `oscal_ssp_schema.json` directly confirmed Information Types has no native field for this and the encoding (fixed-order `props` triplets) was fragile. See §10.12 for the replacement design.

**Data model additions:**
- `"data_flow_links"` and `"vlans"` keys added to the internal SSP dict format (§4.6)
- `models._build_data_flow_link_props()` / `_parse_data_flow_link_props()` — serialise/deserialise flow links as grouped `data-flow.props[]` entries (§10.12)
- `models._build_vlan_props()` / `_parse_vlan_props()` — same grouped-props approach applied to `network-architecture.props[]` for VLANs (§10.12)
- `models._data_flow_links_narrative()` — auto-drafts `data-flow.description` from flow links when the user hasn't written their own
- `models._refresh_flow_link_titles()` — re-resolves cached component titles on load

**Not yet implemented (see `todo.md` §4 for further ideas):**
- Auto-generating a data-flow `.drawio` diagram from the new flow links table (the removed feature did this from the old, wrong-location data; a replacement built on the new storage is future work)

### Version 3.0 (June 2026)

**New features:**
- **Component Editor — live search and type filter**: text search box and type dropdown above the component listbox; filters by title, type, or description in real time; count label shows `showing / total`; filters reset on folder open or add component
- **Component Editor — Section 7: Links**: new form section for attaching external references (vendor documentation, CVE advisories, configuration baselines, policy documents); nine predefined `rel` relationship types with context hints; full OSCAL roundtrip (serialised to `links[]` on save, parsed back on load)
- **Component Editor — section renumbering**: Remarks moved to Section 8, Control Implementations to Section 9 to accommodate new Links section at Section 7
- **41 example components**: pre-built `example-data/components/` library covering hardware, interconnections, operating systems, policies, services, and software for a medium-large Australian government environment; all include ISM control implementations, TCP/UDP protocol data, and external links
- **TCP/UDP protocol data**: all appropriate components in the example library have been populated with `protocols` arrays (network services, port ranges, and transport) using confirmed OSCAL structure
- **POAM Editor tab** (`poam_tab.py`): create and edit Plan of Action and Milestones documents

**Data model additions:**
- `"links"` key added to internal component dict format
- `build_component_oscal_entry()` serialises `links` to OSCAL `links[]` array
- `_parse_single_component()` parses `links[]` from OSCAL JSON back to internal format

**OSCAL compliance notes (known gaps for future work):**
- `status` is stored as an `operational-status` prop rather than the OSCAL `status.state` assembly — scheduled for a future fix
- Protocol and control-implementation UUIDs are regenerated on every save — scheduled for a future fix

### Version 2.0 (June 2026)

**New features:**
- **Capability Editor** (`capability_tab.py`) — create, edit, load, and save OSCAL capability definitions; automatic inheritance of control responses from member components
- **Open File(s) / Open Folder** in both Component Editor and Capability Editor
- **OSCAL version selector** in the toolbar — scans `oscal/` zip files; drives schema validation and `oscal-version` in saved files
- **Schema validation** — catalog files validated on open; capability files validated before save; both warn-and-allow rather than hard-block
- **Catalog Viewer: Guideline column** — new fourth column showing the top-level catalog group
- **Catalog Viewer: Guideline filter dropdown** — filter the control list by top-level group
- **Catalog Viewer: dynamic text wrapping** — detail pane labels rewrap when the panel is resized
- **Component Editor: profile optional** — profile no longer required; control list falls back to full catalog

**Refactoring:**
- `models.get_source_href(profile, catalog)` — extracted from both tabs, single source of truth
- `models.get_profile_controls(catalog, profile)` — extracted from both tabs, single source of truth
- `ComponentTab.add_component(comp)` — public method replacing direct list mutation from CapabilityTab
- `_make_dialog(title, width)` — dialog boilerplate extracted in both ComponentTab and CapabilityTab
- Mousewheel guard changed from hardcoded tab index to `nb.select() == str(self)`
- `collect_controls()` now adds `"guideline"` field to each control dict
