# OSCAL User Toolkit — Design Document

**Version:** 4.2  
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

### 10.18 Grouped top-level tabs — nested Notebooks for Data / System Overview / Audit

The top-level tab bar had grown to ten flat tabs (Workspace, Data Sources, Catalog Viewer, Component Editor, Capability Editor, SSP Editor, Assessment Plan, Assessment Results, POA&M Editor, Dashboard) as features accumulated across this project's history — each addition made sense on its own, but the cumulative result was a crowded bar with no structure. `app.py._build_notebook()` now groups related tabs under three umbrella tabs, each itself a `ttk.Notebook` nested inside the outer one:

- **Data** — Data Sources, Catalog Viewer (browsing/loading shared reference material; nothing system-specific happens here)
- **System Overview** — Component Editor, Capability Editor, SSP Editor (defining one system)
- **Audit** — Assessment Plan, Assessment Results, POA&M Editor (the assessment-to-remediation lifecycle)

**Workspace and Dashboard stay top-level, not inside any group.** Workspace is the landing tab shown at startup. Dashboard was deliberately *not* filed under System Overview (where POA&M-adjacent Component/Capability/SSP editors live) despite reading from the SSP — it's a cross-cutting rollup that also reads AP, AR, and POA&M, so nesting it inside any one group would make it invisible while working in a different one.

**No individual tab class needed to change.** Every `ComponentTab`/`CapabilityTab`/`SSPTab`/etc. constructor call is identical to before — only the `parent=` argument (which Notebook the widget is built inside) and which Notebook's `.add()` receives it changed. This is possible because tabs never assumed anything about their parent beyond "a widget I can build into and register with" — the one place that *did* implicitly assume exactly one level of Notebook nesting was the mousewheel-scroll guard every tab uses (`bind_all("<MouseWheel>")` fires regardless of which tab is visible, so each tab checks whether it's the active one before scrolling its own canvas).

**Fix: `tab_utils.is_tab_active()`.** The old guard compared only the immediate parent Notebook's `.select()` against `str(self)` — correct for "is this tab selected within its own Notebook," but not "is this tab actually visible," since a tab nested inside an unselected group tab would still appear as its own inner Notebook's current selection. `is_tab_active()` walks up through `.master` however many levels deep, checking `.select()` at every ancestor that has one (skipping non-Notebook ancestors), stopping at the first mismatch. This generalizes correctly to any nesting depth — including the zero-nesting case (Dashboard, Workspace), where it behaves identically to the old check. Every tab whose mousewheel guard used the old pattern (`component_tab.py`, `capability_tab.py`, `ssp_tab.py`, `ap_tab.py`, `ar_tab.py`, `poam_tab.py`) now calls this shared helper instead of duplicating the comparison inline. `catalog_tab.py` uses an unrelated, position-based guard (checks mouse position against the canvas widget) and didn't need changing; `workspace_tab.py`/`dashboard_tab.py` stay top-level so their existing single-level check remains correct as-is, though they could adopt the shared helper too if ever nested later.

**`set_theme()`'s per-tab refresh loop needed no changes** — it already iterates leaf tab objects directly (`self._component_tab`, `self._ssp_tab`, etc.), never the Notebook structure itself, so grouping doesn't affect it. The group Notebooks themselves (`data_nb`/`system_nb`/`audit_nb`) are plain `ttk.Notebook` instances styled globally by `_style_ttk()`'s `ttk.Style` configuration, the same as the outer Notebook always was — no per-instance theme handling was needed for them either.

### 10.19 Systems folder + All Systems tab — the multi-network Dashboard, built as a separate read-from-disk tab

`user_stories.md` US-13 wanted a summary across every system an organisation runs, not just the one currently open. The existing `dashboard_tab.py` couldn't be extended to do this in place: it's built entirely around reading the *live* SSP/AP/AR/POA&M editor tabs (`get_ssp_tab()` etc. return the one singleton tab instance each), so "show N systems at once" would mean either opening N systems simultaneously across the same four editor tabs (impossible — each is a singleton) or bolting an entirely different data path onto the same tab. Rather than complicate `dashboard_tab.py` with two mutually-exclusive modes, the multi-system view is a **new, separate tab that reads straight from disk**, independent of whatever the editor tabs currently have open.

**Systems folder** (`settings.py`, `get_systems_path()`/`set_systems_path()`) is the third configured-path setting, alongside the Library (§10.13) and the theme — same pattern: persisted in `settings.json`, defaults to the repo's own `systems/` folder if never configured, changed via a "🗂 Systems Folder" toolbar button. Unlike the Library, there's no fixed subfolder structure to create — a "system" is just any subfolder, expected to contain its own workspace manifest plus whatever SSP/AP/AR/POA&M files that manifest references. The three bundled example environments (`example-data-ism/`, `example-data-nist/`, `example-02/`) moved from the repo root into `systems/` as a result — a plain file move; nothing inside any of them needed to change, since `workspace_ERN.json`'s catalog/profile resolution already has the Library fallback from §10.16, and every other reference inside a workspace manifest is relative to that manifest's own folder, which moved as a unit.

**`AllSystemsTab`** (`all_systems_tab.py`) scans every subfolder of the Systems folder on `refresh()`. For each one, `_find_workspace_manifest()` looks at every top-level `*.json` file and checks for a `"workspace"` key — deliberately not assuming a naming convention, since the bundled examples already disagree (`workspace_ERN.json` vs `workspace.json`). It then loads whatever `load_workspace_manifest()` finds (SSP, Assessment Results, POA&M — components/capabilities aren't needed for a summary) via the existing `parse_ssp_file()`/`parse_ar_file()`/`parse_poam_file()`, computing the same compliance-percentage, open-risk-count, and POA&M-overdue logic `dashboard_tab.py` already uses for its cards (re-derived here rather than shared, since the existing methods are tightly coupled to building that tab's own Tkinter widgets, not to returning plain numbers). A system missing any of these files degrades gracefully — a blank cell and a note ("no SSP", "not yet assessed", "no POA&M"), not an error; `example-02/` in this repo's own bundled data (catalog/profile/components only, no SSP yet) exercises exactly this path.

Every per-file read is wrapped narrowly (`OSError, json.JSONDecodeError, KeyError`) and never propagates — a malformed or half-finished system folder just contributes a mostly-blank row rather than breaking the whole tab, since the point of an organisation-wide rollup is to work even when not every system is equally far along.

### 10.20 Organisation tab — `library_mode` locks ComponentTab/CapabilityTab to the Library, by construction

`user_stories.md` US-14 identified a real gap: an Organisation User maintaining the Library's shared components/capabilities had no dedicated place to do it — the existing Component/Capability Editor tabs (System Overview) are generic file editors with no restriction on *where* a file lives, so editing a Library master was already technically possible via plain Open File(s)/Save, just with no discoverable entry point and no way to tell "am I editing the Library's master or a system's local copy" from the UI alone.

**Decision: reuse `ComponentTab`/`CapabilityTab`, don't build new editor classes.** Both already take their behaviour entirely from constructor callbacks, so a second instance of each, added to a new **Organisation** tab (a `ttk.Notebook` group like Data/System Overview/Audit — see §10.18 — placed between Data and System Overview), gets the full existing editing UI (protocols, control implementations, search, everything) for free. The alternative — a bespoke, cut-down editor just for the Library — would have meant re-implementing a large fraction of an already-mature editor for no real benefit.

**The lock is structural, not a convention.** A brainstorm beforehand considered "default the Open/Save dialog's starting folder to the Library" as a softer option, but tkinter's file dialogs have no way to *restrict* browsing to one folder — a defaulted starting directory is just a suggestion the user can navigate away from. The actual lock implemented instead: a new `library_mode=True` constructor flag removes the "📂 Open File(s)", "📁 Open Folder", and "📚 Import from Library" buttons entirely (there is no dialog to escape from, because there is no dialog), and:

- **Auto-load, not manual Open.** `_load_library_folder()` runs once from `__init__` (mirroring `_after_open()`'s cleanup) and again on demand via a "🔄 Refresh from Library" button — it's the *only* way either list is ever populated, scanning `library/components/*.json` or `library/capabilities/*.json` directly.
- **Save writes back with no location prompt.** A new `_component_paths`/`_capability_paths` dict (`{uuid: path}`) records where each item was loaded from — populated in `_load_component_from_path()`/`_load_capability_from_path()` alongside the existing `_loaded_paths` list. `_save_to_library_path()` returns that recorded path if known, or auto-generates one inside the Library using the same `{type}_{title}.json` naming convention the normal Save dialog already defaults to, disambiguated with a short UUID suffix if that generated name collides with a *different* component/capability already on disk (checked by reading the candidate file's own UUID first, rather than either silently overwriting an unrelated file or refusing outright).
- **One controlled way in from outside: "📥 Add File to Library".** Copies a chosen external file into `library/components/`(or `.../capabilities/`) and loads the copy — the same copy-then-load pattern `_import_from_library()` already uses in the opposite direction (Library → system folder), just reversed. This is the only code path that ever brings an outside file into scope, and it only ever copies *in*.
- **A visible reminder, not just a lock.** A teal (`TEAL_BG` — the colour already associated with Library actions elsewhere) banner under the toolbar states plainly that this edits shared masters and that systems which already imported a copy won't automatically receive changes — since the copy-not-link design (§10.13) means Library edits never propagate on their own.

**The Library Capability Editor's dependencies point at the Library Component Editor, not System Overview's.** `get_components`/`add_component` are wired to `self._library_component_tab` in `app.py`, so a Library capability's member components, and its guard condition (`_ready()` requires at least one component), are entirely about what's in the Library — never contaminated by, or dependent on, whatever happens to be loaded in System Overview for the current system.

**A construction-order bug this surfaced:** `library_mode`'s auto-load calls `set_status()` synchronously during `ComponentTab.__init__()`, which runs during `app.py._build_notebook()` — but `_build_statusbar()` (which creates `self._status_lbl`, the target of every tab's `set_status` callback) previously ran *after* `_build_notebook()` in `OSCALApp.__init__()`. Nothing had ever called `set_status()` synchronously during construction before, so this ordering bug was latent until now. Fixed by building the status bar before the notebook — `pack()`'s `side="top"`/`side="bottom"` layout is unaffected by which is constructed first, only by pack call order relative to each other, which didn't change.

**Component/capability versioning (`metadata.revisions[]`) is intentionally not part of this stage.** The brainstorm that led here also covered using OSCAL's native per-document revision history so a Library update is visible to whoever already imported an older copy — confirmed against `oscal_component_schema.json` that `metadata.revisions[]` exists (title/version/published/last-modified/remarks, documented reverse-chronological) but only at the document level, not per-component, and that a component's own `uuid` should stay stable across edits for this to work. That work is designed in §10.21 below.

### 10.21 Component version / revision / UUID metadata — implemented

**Status: done.** Version, revision history, and stable UUIDs are now surfaced in the Component Editor (both `library_mode` and System Overview instances, since they share the `ComponentTab` class). Groundwork for a later "compare version" function (still not in scope). Scoped to **components only** — capabilities are a separate follow-up and should not be started without an explicit request.

**Uses OSCAL's native `metadata.revisions[]`, no invented field.** Confirmed against `oscal_component_schema.json`:
- The `defined-component` object has **no version field** — only its own `uuid`. Its properties are `uuid, type, title, description, purpose, props, links, responsible-roles, protocols, control-implementations, remarks`.
- Versioning lives at the **document** level: `component-definition.metadata` has `version` (required) and `revisions[]`, where each revision is `{title, published, last-modified, version (required), oscal-version, props, links, remarks}`, documented as reverse-chronological (latest first).

So the model is: each single-component file carries a stable document `uuid`, a stable component `uuid`, a current `version`, and an ordered `revisions[]` history — all round-tripping natively through OSCAL with no home-grown encoding.

**Fixed the architectural blocker.** `ComponentTab` used to store `self._file_uuid` (set once via `new_uuid()`) and `self._file_version` (a single `tk.StringVar(value="1.0")`) as **shared, tab-level** state — reset only by `_new_file()`. `_build_single_component_oscal(comp)` used these shared values for *every* component's `metadata.uuid`/`metadata.version` regardless of which component was selected, which was badly broken in `library_mode` (dozens of components sharing one `ComponentTab` instance would all have been written with the same document UUID and version). Both fields were removed; this state now lives per-component:
- Each component dict carries its own `file_uuid`, `version` (default `"1.0"`), and `revisions` (list of `{version, date, remarks}`, latest-first — mirrors OSCAL's `revisions[]` shape).
- `_add_component()` seeds a fresh `file_uuid`/`version`/`revisions` for new components.
- `_parse_single_component()` reads `component-definition.uuid` and `metadata.version`/`metadata.revisions[]` back onto the component dict on load; a file with no `revisions[]` gets an empty list, and a missing/empty root uuid gets a freshly generated one rather than erroring.
- `_build_single_component_oscal(comp)` reads `comp["file_uuid"]` / `comp["version"]` / `comp["revisions"]` — never shared tab-level state — and only emits a `metadata.revisions` key at all when the list is non-empty (an empty array is needless noise in the OSCAL output).

**UI** — a bordered "🗂 Metadata — Version & Revision History" card sits inside Section 1 "Basic Information" (deliberately *not* its own numbered section, to avoid renumbering every section after it). It has its own header bar (visually distinct from the surrounding Basic Information fields) and an italic hint line explaining the two available workflows before any of the controls, since "editing Version and clicking Apply" vs. "Save New Version" look similar but do different things:
- Component UUID and document UUID, shown as small read-only labels (traceability only — never hand-edited).
- An editable Version field (`self._v_version`), replacing the old shared toolbar Version entry, which was removed entirely.
- A read-only `ttk.Treeview` revision history list (version / date / remarks), rebuilt from `comp["revisions"]` on every `_populate_from()`.
- A "📌 Save New Version" button opens a small modal (`_save_new_version()`): shows the current version, asks for a new version number (must differ) and optional free-text remarks on what changed, then on confirm prepends `{version: <old>, date: now_iso(), remarks}` to `revisions[]` and sets `comp["version"]` to the new value. This only updates the in-memory component (mirroring `_apply_component()`'s "not yet saved to disk" pattern) — Apply/Save still do the actual write.

**Verified functionally** (not just syntax-checked): instantiated `ComponentTab` directly, added two components, confirmed each gets an independent `file_uuid`; saved both to disk and confirmed the OSCAL output has distinct document UUIDs; ran a "Save New Version" bump on one and confirmed `metadata.revisions[]` round-trips correctly through save → reload; specifically exercised the `library_mode` many-components-one-tab case (`_load_library_folder()` loading two files into one instance) and confirmed selecting each component shows its own version/UUID/history in the form, and that saving one from the shared tab only touches that component's document UUID/version.

### 10.22 Usability heuristics + secure-coding pass — `usability_review.md` and `SECURE_CODING.md`

Two companion documents drove a full pass through Nielsen's 10 usability heuristics and the OpenSSF Secure Coding Guide for Python (per-item detail lives in those files, not duplicated here — this section is the "why" and the cross-reference):

**Usability (`usability_review.md`)** — every one of the 10 heuristics was checked directly against the codebase (not just re-stated from the original review) and either fixed, found already-addressed, or explicitly marked out of scope with a reason:
- **#1 Visibility of status**: an "unsaved changes" `*` marker on tab labels, propagating up through nested tab groups (`app.py`'s `_refresh_dirty_indicators()`, polling every 500ms since no tab fires a "dirty changed" event to hook into instead).
- **#2/#6/#10 Recognition over recall / help**: a new `attach_tooltip()` helper (`tab_utils.py`) attached to the highest-value spots (genuinely icon-only buttons, buttons whose label doesn't reveal a real consequence like discarding unsaved edits); a native Help menu (`app.py`'s `_build_menu_bar()`) — the app had zero `tk.Menu` usage before this.
- **#3/#7 User control, flexibility**: Ctrl+S (dispatches to whichever of 8 save-capable tabs is active, via a lookup table) and Ctrl+O (wired only where "open" is unambiguous). Found and worked around a real platform conflict: Tk's `Text` widget has its own default `<Control-o>` binding (an Emacs-style newline insert) that fires *before* `bind_all` can intercept it.
- **#4 Consistency**: normalized icon/text spacing and "Remove"/"Remove Selected" terminology across ~28 buttons in 7 files — verified each button's actual behaviour first (e.g. confirmed "Delete" vs "Remove" already tracked a real semantic distinction — whole-entity delete vs. sub-item removal — so that distinction was kept, not flattened).
- **#5 Error prevention**: port range fields in the protocol dialog only checked "is this an integer at all," not the valid 1–65535 range or that end ≥ start — both now checked. Confirmed UUID validation doesn't apply anywhere: every UUID in the app is auto-generated and shown read-only.
- **#8 Aesthetic/minimalist**: computed actual WCAG 2.1 contrast ratios (formula verified against the known white/black 21:1 reference) for every `fg`/`bg` colour pair used together anywhere in the app. Found a real, severe bug this way, not a subjective one: **74 buttons** across 7 files paired a fixed near-black `BUTTON_TEXT` (intended only for the light pastel `_BG` fills) with `HEADER_BG`, giving **1.38:1 contrast in dark mode** — every "secondary" button (Remove Selected, Edit Selected, Cancel) had near-invisible text. Fixed by switching to `fg=C["TEXT"]`, the pattern 2 buttons already used correctly (now 8.69:1 dark / 12.06:1 light). Deliberately left one marginal finding unfixed (`GREEN`/`TEAL` text colour, 3.1–3.9:1 in light mode only) since those are load-bearing brand colours and changing a hue for a marginal contrast gain is a visual-identity decision, not a surgical fix.
- **#9 Error recovery**: tkinter's default behaviour for an uncaught exception in any UI callback is to print a traceback to stderr and otherwise do *nothing visible* — worse than "basic error messages," since for this whole class of failure there was no message at all. `app.py`'s `_setup_error_logging()` (called first thing in `__init__`) installs `report_callback_exception`, logging a full traceback to `oscal_user_toolkit/error.log` (gitignored) via Python's `logging` module — this app's first real use of it — and shows the user a plain-language dialog naming the exception and log location instead of silent failure.

**Secure coding (`SECURE_CODING.md`)** — a short, project-specific companion to the OpenSSF guide, written directly from an audit of this codebase rather than generic advice: which of the guide's 9 sections actually apply here (§4 Neutralization and §5 Exception handling are high-relevance, since this app constantly `json.load()`s files a user picked; §7 Concurrency and §9 Cryptography don't apply at all), and 7 concrete rules with real examples from this repo. Two fixes came directly out of that audit:
- Narrowed 10 `except Exception: pass` blocks to `except tk.TclError:` — the only realistic failure in the Tkinter widget-race code they guarded (a stale tree-item id, a canvas destroyed mid-scroll). Left `models.py`'s one remaining broad catch as a documented, intentional exception: that file deliberately never imports `tkinter` to preserve the data/UI layer boundary, even though one function takes a live notebook widget.
- Added `OSError` to `app.py`'s catalog/profile load handlers, which caught malformed JSON but not a file becoming unreadable between the file dialog and the actual read. Testing this by actually deleting a file mid-flow (not just reading the code) surfaced a *second*, earlier instance of the same gap in `_open_catalog()` — a raw pre-validation JSON parse, before `load_catalog()` is even called — that a pure code-reading pass had missed.

Every fix across both documents was verified functionally (simulated the actual failure condition and confirmed the app's response), not just syntax-checked — several genuine findings in this pass (the dark-mode contrast bug, the second `OSError` gap) were only caught because of that.

### 10.23 Document metadata, OSCAL version upgrade, and a second usability pass

A follow-up round of work, driven partly by direct feature requests and partly by a second Nielsen heuristics pass (originally its own `usability_review_2.md`, later merged into `usability_review.md` — see §10.27) specifically hunting for gaps introduced by everything §10.20–§10.22 built.

**Document metadata — Creator/Organisation and Document Links, collapsible.** Both `ComponentTab` and `CapabilityTab` gained two new per-file metadata fields alongside the existing version/UUID card (§10.21): a Creator/Organisation text field and a `doc_links[]` table (same rel/href/text shape as the existing per-component `links[]`, but describing the *document itself* — e.g. a vendor's "latest version" URL — not the component). Prompted by inspecting real-world example components (CivicActions' published OSCAL components) that carry exactly this kind of file-level provenance. The whole "🗂 Document Metadata" card is now collapsible via a new `tab_utils.make_collapsible()` helper (parent, title, colors, start_expanded) — a generic disclosure-triangle wrapper, not specific to this card, so any future card can reuse it.

**"🔼 Upgrade OSCAL Version"** (both editors' Document Metadata card): lets the user pick any bundled OSCAL schema version (via `get_oscal_versions()`/`get_oscal_version_paths()` on `OSCALApp`, already existed for the toolbar's version selector — this dialog is the first *other* consumer of them) and re-validate the current component/capability against that version's schema specifically, independent of whatever the toolbar currently has selected. Deliberately framed as "re-validate and re-stamp," not "migrate" — the app has no schema-migration logic for any version, and the in-dialog copy says so. On confirmation, records the change as a new `revisions[]` entry (components) and updates `doc_oscal_version`; never writes to disk itself, same as the rest of the editors' "not yet saved" pattern.

**"🆕 Create New Workspace"** (Workspace tab): clears every open document plus the loaded catalog/profile, gated behind a dirty-check warning (`app.py._new_workspace()`) — only prompts if something would actually be lost, not unconditionally. Surfaced a real pre-existing bug while building this: `SSPTab`/`APTab`/`ARTab`/`POAMTab`'s `_reset()` never cleared `self._dirty`, so a blank-slate reset could still show a stale unsaved-changes `*` afterward; fixed alongside.

**System Overview Capability Editor auto-loads from the system's capability folder.** Mirroring how the Component Editor already behaved, `on_system_folder_changed()`/`_load_system_folder()` (`capability_tab.py`) now load every capability file in the current system's `capabilities/` folder automatically when the system folder changes, instead of requiring a manual Open Folder each time.

**Second-pass findings, fixed in priority order:**
- **Silent validation-skip in the Upgrade dialog** (🔴 highest priority): both `_upgrade_oscal_version()` methods guarded the whole validation step with `if zip_path:` — a missing/renamed schema zip meant `zip_path` was `None`, and the code fell straight through to committing the upgrade with **no indication validation had ever run**, directly contradicting the dialog's own "re-validates before re-labelling" copy. Fixed with an `else:` branch requiring explicit confirmation ("could not find the schema — upgrade anyway, without validation?") before proceeding.
- **No tooltip on "Create New Workspace"**: added, along with the Open/Save Workspace buttons, which also had none.
- **No dialog anywhere supports Enter-to-confirm/Escape-to-cancel**: `<Escape>` → cancel added to every `_make_dialog()` implementation across all 6 tab files with dialogs (cheap, one line each, benefits every dialog in the app at once) plus the handful of dialogs built as standalone `tk.Toplevel`s outside that helper. `<Return>` → primary action scoped to `component_tab.py`/`capability_tab.py`'s own dialogs (the ones actively developed this round) — deliberately *not* extended to `ar_tab.py`/`ap_tab.py`/`poam_tab.py`/`ssp_tab.py`'s dialogs in the same pass, left as a documented follow-up rather than an exhaustive ~20-dialog sweep. One deliberate exception: the Protocol dialog's port-range entry fields bind `<Return>` to "add this port range" instead of the dialog-wide primary action, since Return there should extend the list being built, not submit the whole dialog.
- Verified functionally (not just syntax-checked): simulated `<Return>`/`<Escape>` key events on live dialog instances and confirmed the right callback fired, for both the validation-skip fix and the Enter/Escape bindings.

**Button colour and weight consistency** (raised directly by the designer testing the running app, after the above): every secondary button (Cancel, Delete, Remove Selected, Create New Workspace, Browse Elsewhere, Clear Profile, etc.) used `bg=HEADER_BG, fg=TEXT` — the theme's *own* text colour — while every primary/coloured button (Save, Open, Add, Upgrade) used a fixed near-black `BUTTON_TEXT` regardless of theme (§10.22's contrast fix). Individually both pairings had fine contrast, but side by side in dark mode this put two visibly different text colours on adjacent buttons in the same row. Fixed by adding a new fixed `SECONDARY_BG` fill (`#c9ccdb`, same value in both palettes — same non-theme-swapped rationale as the existing `_BG` keys, §10.22) and switching all secondary buttons (~85, including two found later that built their colours inside a loop rather than a literal `tk.Button()` call, missed by the first sweep) to `bg=SECONDARY_BG, fg=BUTTON_TEXT`. Separately, all ~94 buttons using bold font were switched to normal weight, since the app had no deliberate rule for which buttons should be bold and the result was inconsistent rather than intentional emphasis.

**Library growth**: 7 new example components (`aws.json`, `django.json`, `drupal.json`, `ilias.json`, `privacy.json`, `ssh.json`, `software_EDR_crowdstrike.json` — all `software` type), taking the Library from 95 to **102 components**; capabilities unchanged at 11. See §11.

### 10.24 Multi-catalog components — Library Component/Capability Editors only (todo.md §3, Stages 2–3)

Confirmed directly against `oscal_component_schema.json` before building anything: `defined-component.control-implementations` is an array (`minItems: 1`, no maximum), and each `control-implementation` entry has its own required `source` — so a component genuinely can hold responses against controls from more than one catalog natively, no workaround needed. This closes out `todo.md` §3's Stages 2–3, which were blocked on nothing consuming the `CatalogResolver` (§10.17) that already existed.

**Deliberately scoped to the Library Component/Capability Editors, not System Overview's.** The Library is the shared, cross-system master most likely to need this — e.g. a single "AWS" component reused across an ISM-governed system and a NIST-governed system needs both an ISM response and a NIST response on the *same* component. System Overview's per-system editors stay tied to whatever one catalog/profile is loaded for that system, unchanged. `app.py`'s `get_resolver()` callback (previously defined but consumed by nothing) is now wired only into `self._library_component_tab`/`self._library_capability_tab`'s construction, not `self._component_tab`/`self._capability_tab`.

**Control list combines every loaded catalog when there's more than one.** `ComponentTab._get_profile_controls()`/`CapabilityTab._get_controls()` now check `get_resolver().catalogs()` first: with 0 or 1 catalog loaded, behaviour is byte-for-byte unchanged (delegates to the existing single-catalog `get_profile_controls()`). With more than one, they build a combined list from `resolver.all_controls()` (still respecting the profile's `ids` filter if one's loaded) and rebuild `self._ctrl_source_map` (`{control_id: source_catalog_filename}`). `models.refresh_ctrl_list()` gained an optional `source_labels` parameter — when given, tags a control's row label `"[source_filename]"` — but defaults to `None`, so `SSPTab`'s unrelated call site (which shares this function) is completely unaffected.

**Per-control source is recorded alongside the response, not computed at save time.** A new `ctrl_response_sources` dict (`{control_id: source_filename}`) sits next to the existing `ctrl_responses`/`ctrl_impl_status`, populated from `_ctrl_source_map` at the same points a response is captured (control switch, explicit Save, `_collect_into()`), and round-tripped through load/save exactly like the others. A control with no recorded source (every pre-existing single-catalog component/capability) falls back to the one computed `source_href`, so none of the 105 real library components/11 capabilities needed migrating — verified by reloading and rebuilding every one of them with zero failures.

**`build_component_oscal_entry()` (models.py) and `CapabilityTab._build_oscal_document()` group by source instead of emitting one hardcoded block.** Both now bucket a component/capability's responses by `ctrl_response_sources.get(ctrl_id) or source_href` and emit one `control-implementations` block per distinct bucket. For capabilities, inherited responses carry their *member component's own* recorded source through `_resync_inherited_for_cap()`'s new `catalog_source` field, so a capability inheriting an ISM response from one member and a NIST response from another produces two correctly-sourced blocks without the capability itself needing to track anything extra for inherited entries.

**Control ID collisions across catalogs** (flagged as an open question in `todo.md` §3) are handled by keeping whichever catalog's control was seen first and skipping the duplicate — avoids a Tkinter `TclError` from a duplicate Treeview row iid, at the cost of the second catalog's colliding control being invisible in the combined list. Not expected to matter in practice (ISM's `ism-NNNN` and NIST's `ac-2`/`03.01.01`-style IDs don't overlap), and left as a known, documented limitation rather than solved generally.

**Verified functionally, not just syntax-checked**: built a component with an ISM response and a NIST response from two fake loaded catalogs, confirmed `build_component_oscal_entry()` emits two correctly-sourced blocks and the output validates cleanly against the real bundled `oscal-1.2.2.zip` schema; round-tripped a capability with one inherited (member-catalog) response and one capability-level response through save → reload and confirmed both sources survive; reloaded and rebuilt every real file in `library/components/`/`library/capabilities/` with zero failures to confirm no regression on existing single-catalog content.

### 10.25 Fixed a real duplicate-title bug: Library Capability Editor no longer imports its own bundled component copies

Reported directly by the designer using the app: the Library Component Editor showed two "Backup and Recovery Policy [policy]" rows, but only one `policy_Backup_and_Recovery.json` file existed on disk.

**Root cause.** `CapabilityTab._load_capability_from_path()` has always called `self._add_component()` for every component a capability file bundles (needed so a standalone capability file's member references resolve without also separately loading every member — see §10.20). In the Library, this meant a capability's *own* bundled copy of a member got imported into the Library Component Editor's shared list on top of whatever ComponentTab already auto-loaded from `library/components/` directly. `ComponentTab.add_component()` dedupes by UUID only — so if a capability's bundled copy had a different UUID than the real library file for the same title (confirmed: `capability_Backup_and_Recovery.json` bundled a "Backup and Recovery Policy" with UUID `664b2cda-...`, completely different content — different description, disjoint ISM controls — from the real `policy_Backup_and_Recovery.json`'s `ea20768b-...`), both ended up in the list as two rows with an identical title.

**Fix, per direct instruction: the Library Component Editor should only ever show files actually in `library/components/`.** `app.py` no longer wires `add_component` for `self._library_capability_tab` at all (System Overview's pair is unchanged — it still needs bundle-importing, since a system's capability file has to resolve its members without necessarily having every one separately loaded). Member resolution in the Library now relies purely on `get_components()` already containing the real files, which is guaranteed by construction order (`self._library_component_tab` is built and auto-loads before `self._library_capability_tab`).

**This surfaced a much bigger latent gap while verifying the fix**: checking all 11 Library capabilities against `library/components/` found **18 bundled member components across 6 capabilities that had never been saved as their own standalone file** — some genuinely duplicate-but-different-content (the 2 above), most simply never extracted at all (e.g. every member of Email Security, Endpoint Protection, Privileged Access Management, and Security Monitoring and Logging existed *only* inside their capability's own bundle). Per direct instruction, extracted all of them into real `library/components/` files using `ComponentTab._save_to_library_path()`/`_build_single_component_oscal()` — the same code path a real Save would use — so every capability member is now a first-class, independently reusable library component, consistent with the rest of the Library. The two capabilities with a genuine UUID mismatch (`capability_Backup_and_Recovery.json`, `capability_Patch_Management.json`) had their `member_uuids` repointed at the correct library UUID and their inherited responses re-synced from it.

**One piece of content was deliberately not kept**: the stale "Backup and Recovery Policy" bundled copy covered three ISM controls (`ism-1111`, `ism-1118`, `ism-1960`) that the real library policy component doesn't. Rather than silently merging or discarding this, it was surfaced back to the designer as an open follow-up — Patch Management's equivalent stale copy needed no such call, since its controls were already a strict subset of the real library version's.

**Verified**: reloaded the full Library (121 components, 11 capabilities) and confirmed zero duplicate titles and every capability's `member_uuids` resolves against `get_components()`; rebuilt every component and capability with zero failures.

### 10.26 CI — GitHub Actions, Ruff, and the first unit tests (`tests/`)

The project had no automated verification at all before this — every fix in this document was checked by hand, either via manual UI testing or a throwaway script run once and discarded. A GitHub Actions workflow (`.github/workflows/ci.yml`) now runs on every push/PR to `main`: a **lint** job (Ruff) and a **test** job (pytest). Since this repo is public, both run on GitHub's free-minutes tier — no cost consideration.

**Ruff config deliberately narrower than the defaults.** `pyproject.toml` selects only `F` (pyflakes — unused imports/variables, undefined names) and `E7`/`E9` (statement- and syntax-level errors), not the full `E`/`W` pycodestyle style set. Tried the full default set first: it flagged 51 "line too long" findings alone, because this codebase's existing style consistently runs past pycodestyle's line-length default. Reformatting dozens of files to satisfy a width nobody had asked for wasn't worth the churn, so the config was narrowed to genuine correctness issues instead — matching the "start lenient, tighten later if wanted" framing this was proposed under.

**Fixed the 15 real findings that scope did surface**, so CI starts green rather than red on its first run: 5 unused imports (`ap_tab.py`'s `now_iso`, `ar_tab.py`'s `empty_poam`/`build_oscal_poam`, `models.py`'s `docx.shared.RGBColor`/`Inches`), 5 unused variables (three identical dead `C = COLORS` lines in `app.py`, one in `dashboard_tab.py`, one dead `it_parent` in `ssp_tab.py`), and 5 multi-statement-per-line issues (`if`/`elif` one-liners in `models.py`'s POA&M risk-facet parsing, a semicolon-joined triple-assignment in `component_tab.py`). All cosmetic — re-ran the full app-construction sanity check and every file's `ast.parse()` after, to confirm none of these were load-bearing.

**Why `tests/test_models.py` and only `models.py` for now.** `models.py` is the one file in this codebase with a documented, deliberate no-GUI-code rule (see its own module docstring, and §10.1) — every function takes plain dicts/lists and returns plain dicts/lists, with no tkinter widget to construct or fake. That makes it the only part of the app that's actually *easy* to unit test; the tab files are tkinter UI code, where a real test would need widget mocking or a headless Tk display in CI — a bigger, lower-value investment left out of this pass deliberately, per direct discussion with the designer.

**26 tests**, chosen to cover the pieces most likely to silently break on a careless refactor rather than attempting exhaustive coverage: the small pure helpers (`new_uuid`, `now_iso`, `safe_filename_component`, `get_prop`), `get_source_href`'s profile-over-catalog-over-placeholder preference order, `get_profile_controls`'s filtering, `CatalogResolver` (add/get/resolve/all_controls/clear), and — the newest and most change-prone logic in the file — `build_component_oscal_entry()`'s multi-catalog grouping from §10.24, including the "some controls have a recorded source, some don't" mixed case that a less careful implementation could merge into the wrong bucket. Also covers the VLAN and data-flow-link grouped-props round-trips (§10.12), which had no prior test coverage at all.

**Suggested next, in rough order of effort-to-value** (not yet built): `empty_ssp()`/`empty_poam()`/`empty_ap()`/`empty_ar()` shape assertions (trivial); `parse_*_file()` round-trips for SSP/AP/AR/POA&M (same pattern as the VLAN/data-flow tests, just bigger documents); `build_workspace_manifest()`/`load_workspace_manifest()` (needs `tmp_path` fixtures — real files on disk, not pure dicts); `validate_oscal_file()` against the real bundled `oscal-1.2.2.zip` schema (highest real-world value, since it's the app's actual conformance guarantee, but needs that fixture file); `CatalogResolver.load_from_profile()`'s back-matter indirection (hardest of the five).

### 10.27 `usability_review.md` and `usability_review_2.md` merged into one file

Two separate review documents had accumulated — the original 10-heuristic pass (§10.22) and a follow-up pass hunting for regressions introduced by everything built since (§10.23) — plus a set of button-colour/font-weight fixes that had been appended to the second file as ad hoc follow-ups rather than filed under any heuristic. Per direct instruction, merged both into a single `usability_review.md`, organized by the original 10-heuristic structure: each second-pass finding is now folded inline under whichever heuristic it actually belongs to (cross-referenced where a finding spans two, e.g. the Upgrade dialog's validation-skip bug under #1 with a #9 cross-reference), labelled **"Second pass"** so the two passes stay distinguishable without needing two files. The button-colour/weight follow-ups landed under #8 (Aesthetic and Minimalist Design), next to the WCAG contrast fix they're a direct continuation of. `usability_review_2.md` was deleted; every code comment across the tab files that referenced it by name (`# usability_review_2.md — Escape always means Cancel`, etc.) was updated to point at the merged file instead.

---

## 11. Example Component Library

The `library/components/` folder (see §10.13–§10.20 for the Library system itself) ships with **121 pre-built component files** spanning every component type listed in `oscal_component_schema.json`'s `defined-component.type` enum, plus the app's own `operating-system` convention. They're loaded automatically by the Organisation tab's Library Component Editor (`library_mode` — see §10.20), or can be picked individually via **📚 Import from Library** in the System Overview Component Editor.

All example components include:
- ISM control implementations with detailed implementation narratives, using real control IDs verified directly against the bundled ISM catalog (`library/catalogs/ISM_catalog_2026_06.json`) — never invented
- TCP/UDP protocol data (`protocols` array with `port-ranges`) where applicable
- Realistic `props` describing vendor, deployment model, and other identifying metadata

The components span a realistic medium-to-large Australian organisation's environment:

| Type | Count | Examples |
|---|---|---|
| hardware | 13 | Firewall, Network Switch, Wireless AP, NAS, SAN Storage Array, Fibre Channel Switch, UPS, Cabling, Network Encryptor, Load Balancer, Web Application Firewall |
| interconnection | 3 | Internet (filtered), WAN Link (IPsec), No Internet |
| operating-system | 10 | Windows 10/11 Workstation, Windows Server 2022, RHEL Server/Workstation, Ubuntu Workstation, VMware ESXi, Microsoft Hyper-V, Proxmox VE, Nutanix AHV |
| policy | 36 | Patch Management, Backup and Recovery, Remote Access, Incident Response, Access Control, Data Classification, System Usage, Password and Credential Management, Cryptographic Key Management, Physical Security, Email Security, Endpoint Protection, Privileged Access Management, Security Logging and Monitoring, and the six ISM Cyber Security Principles (Govern/Identify/Protect/Detect/Respond/Recover) |
| service | 24 | Active Directory, SQL Server, ManageEngine ServiceDesk Plus, Exchange Online, Veeam, VPN, DHCP, DNS, PKI/CA, Web Proxy, NTP, MongoDB, Windows Fileshare, Kubernetes, Identity Provider (Entra ID), Privileged Access Management, Email Security Gateway, Two-Factor Authentication (Duo), Offsite Backup Storage (AWS S3), Microsoft Defender for Office 365, Active Directory (Privileged Access), SIEM (Microsoft Sentinel) |
| software | 26 | Microsoft 365, Airlock Digital, Defender for Endpoint, Edge, Acrobat, Nessus, Sentinel, GitLab, Subversion, Oracle VirtualBox, AWS, Django, Drupal CMS, Ilias, Privacy, SSH, EDR (CrowdStrike Falcon), Veeam Backup and Replication, Windows 11 (Patch Management), Vulnerability Scanner (Tenable Nessus), Microsoft Outlook, Windows Defender Firewall, Multi-Factor Authentication (Entra ID), Windows Advanced Audit Policy |
| physical | 4 | Main Office Server Room, Remote Office Comms Room, Air Conditioning (server room precision cooling), Power Generator |
| process-procedure | 1 | Cyber Security Incident Response Procedure |
| plan | 1 | Business Continuity and Disaster Recovery Plan |
| guidance | 1 | ASD Secure Configuration and Hardening Guidance Register |
| standard | 1 | OWASP ASVS / MASVS |
| validation | 1 | Penetration Testing and Security Assessment Program |

`library/capabilities/` ships with **11 capability files** bundling these components into named capabilities (e.g. Account Management, Backup and Recovery, Endpoint Protection). Two of note — **Virtualisation (VMware)** and **Virtualisation (Hyper-V)** — were generated by driving the real `ComponentTab`/`CapabilityTab` code directly (library_mode) rather than hand-written, so their `incorporates-components`, bundled member component copies, and aggregated `control-implementations` (inherited responses tagged with `source-component-uuid`) are exactly what the UI itself would produce; each bundles a hypervisor component with the shared SAN Storage Array and NAS components.

**A note on the `type` field**: the app's own `COMPONENT_TYPES` list (`component_tab.py`) splits the schema's single `process-procedure` enum value into two separate dropdown options, `"process"` and `"procedure"` — neither is the literal schema term (though both, and `process-procedure`, are schema-valid since `type` also accepts any free-form string). The `process-procedure` example component above was created with the correct schema term directly; a `ttk.Combobox` in readonly mode still displays a preset value correctly even when it isn't one of the dropdown's own options (confirmed directly), so the file loads and displays correctly — a user manually creating a *new* process-procedure component from the dropdown just can't pick that exact combined term today. Not yet fixed; see `todo.md`.

**A note on schema validation**: while adding components in this batch, 29 of the library's pre-existing files were found to fail `oscal_component_schema.json` validation — most for an invalid `remarks` field on a `port-ranges` entry (only `start`/`end`/`transport` are allowed there), a handful for an empty `protocols: []` array (the schema requires it be non-empty if present at all). All were fixed library-wide; every file in `library/components/` now validates cleanly.

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

### Version 4.9 (July 2026)

**New:**
- **CI**: a GitHub Actions workflow (`.github/workflows/ci.yml`) now lints (Ruff) and unit-tests (pytest) every push/PR to `main`. New `tests/test_models.py` — 26 tests covering `models.py`'s data helpers, `CatalogResolver`, the multi-catalog `control-implementations` grouping (§10.24), and the VLAN/data-flow-link prop round-trips.
- New `pyproject.toml` (Ruff + pytest config) and `requirements-dev.txt` (dev/CI-only dependencies).

**Fixes:**
- 15 real Ruff findings across 6 files — unused imports/variables and multi-statement-per-line issues — fixed so CI starts green. See §10.26.

### Version 4.8 (July 2026)

**Fixes:**
- Fixed a real duplicate-title bug reported by the designer: the Library Capability Editor no longer imports its own bundled component copies into the Library Component Editor's shared list — `app.py` stops wiring `add_component` for that instance. Surfaced a much bigger latent gap while verifying: 18 components across 6 capabilities existed only as bundled copies, never as their own `library/components/` file — extracted all of them; Library grows from 102 to 121 components. Two genuine content mismatches (`capability_Backup_and_Recovery.json`, `capability_Patch_Management.json`) repointed at their correct library component. See §10.25.

### Version 4.7 (July 2026)

**New features:**
- **Multi-catalog components** (`todo.md` §3, Stages 2–3) — the Library Component/Capability Editors' control lists now combine every catalog `get_resolver()` holds when a loaded profile imports more than one (e.g. ISM + NIST), tagging each control with its source catalog. A new `ctrl_response_sources` dict records which catalog each response's control came from; `build_component_oscal_entry()` and `CapabilityTab._build_oscal_document()` group responses by source and emit one `control-implementations` block per catalog, confirmed schema-valid against `oscal_component_schema.json`. Deliberately scoped to the Library editors only, not System Overview's. See §10.24.
- 6 CivicActions-format library components converted to house style with real ISM + NIST SP 800-53 rev5 control coverage: `service_ssh.json`, `policy_privacy.json`, `service_learning_management_system.json` (was `ilias.json`), `software_drupal.json`, `software_django.json`, `service_aws.json`.

### Version 4.6 (July 2026)

**Fixes:**
- Removed bold font from all ~94 `tk.Button()` instances app-wide — normal weight everywhere, since bold had no deliberate rule behind it.
- Found and fixed two secondary buttons (`ap_tab.py`'s task Edit/Remove, `ar_tab.py`'s Add/Edit/Remove rows) missed by Version 4.5's sweep because their colours were chosen inside a loop rather than a literal `tk.Button()` call.

### Version 4.5 (July 2026)

**Fixes:**
- Unified secondary-button text colour app-wide: added a new fixed `SECONDARY_BG` fill and switched every secondary button (Cancel, Delete, Remove Selected, Create New Workspace, Browse Elsewhere, Clear Profile, etc. — ~83 buttons) from `bg=HEADER_BG, fg=TEXT` to `bg=SECONDARY_BG, fg=BUTTON_TEXT`, matching primary buttons' fixed text colour. See §10.23.

### Version 4.4 (July 2026)

**Usability (second pass, fixed in priority order):**
- Fixed the "Upgrade OSCAL Version" dialog silently skipping validation when the target schema zip couldn't be found — now warns and requires explicit confirmation before proceeding unchecked.
- Added tooltips to all three Workspace tab buttons (Open/Save/Create New Workspace).
- Added `<Escape>`-to-cancel to every dialog in the app (via `_make_dialog()` plus the standalone `tk.Toplevel` dialogs outside it) and `<Return>`-to-confirm to `component_tab.py`/`capability_tab.py`'s own dialogs.
- See §10.23.

### Version 4.3 (July 2026)

**New features:**
- **Document metadata** — Creator/Organisation field and a `doc_links[]` table added to both `ComponentTab`/`CapabilityTab`'s Document Metadata card, now collapsible via a new generic `tab_utils.make_collapsible()` helper.
- **"🔼 Upgrade OSCAL Version"** — re-validates a component/capability against any bundled schema version (independent of the toolbar's current selection) and re-stamps `metadata.oscal-version` on confirmation; explicitly not a content migration.
- **"🆕 Create New Workspace"** (Workspace tab) — clears every open document plus the catalog/profile, gated behind a dirty-check warning.
- System Overview's Capability Editor now auto-loads from the current system's `capabilities/` folder, matching the Component Editor's existing behaviour.
- 7 new Library components (`aws`, `django`, `drupal`, `ilias`, `privacy`, `ssh`, EDR/CrowdStrike) — Library grows from 95 to 102 components.

**Fixes:**
- `SSPTab`/`APTab`/`ARTab`/`POAMTab`'s `_reset()` never cleared `self._dirty` — found while building Create New Workspace's dirty-check gate.

See §10.23 for full detail on all of the above.

### Version 4.2 (July 2026)

**Usability (full pass against `usability_review.md`'s 10 Nielsen heuristics):**
- Unsaved-changes `*` indicator on tab labels, propagating through nested tab groups.
- Tooltips (`tab_utils.py`'s new `attach_tooltip()`) on the highest-value icon-only/consequence-hiding buttons.
- Ctrl+S (save active tab, any of 8 save-capable tabs) and Ctrl+O (open files, where unambiguous) — found and worked around a real Tk `Text` widget default-binding conflict on `<Control-o>`.
- A native Help menu — Keyboard Shortcuts, Workspace Guide, About — the app's first `tk.Menu` usage.
- Consistency pass: icon/text spacing and "Remove"/"Remove Selected" terminology normalized across ~28 buttons in 7 files.
- Port range fields now validate the actual 1–65535 range and end ≥ start, not just "is this a number."
- Found and fixed a real WCAG contrast bug (not a subjective one — computed actual ratios): 74 buttons across 7 files had 1.38:1 contrast in dark mode (near-invisible secondary-button text); fixed to 8.69:1 dark / 12.06:1 light.
- Uncaught UI-callback exceptions now get logged (`oscal_user_toolkit/error.log`, this app's first real use of the `logging` module) and shown to the user as a plain-language dialog, instead of tkinter's default silent-failure behaviour.
- Full detail and per-item verification evidence lives in `usability_review.md`, not duplicated here — see §10.22.

**Secure coding:**
- New `SECURE_CODING.md` — a short, project-specific summary of the OpenSSF Secure Coding Guide for Python, written from an actual audit of this codebase.
- Narrowed 10 overly-broad `except Exception: pass` blocks to `except tk.TclError:`; added missing `OSError` handling to catalog/profile loading (found a second instance of the same gap by testing the actual failure condition, not just reading the code).
- See §10.22.

### Version 4.1 (July 2026)

**Library content:**
- Grew the example Library from 64 to **95 components** and from a handful of ad hoc examples to full coverage of every OSCAL `defined-component.type` (plus the app's `operating-system` convention): hardware (SAN Storage Array, Fibre Channel Switch, Load Balancer, Web Application Firewall), operating systems (Windows 10 Workstation, Ubuntu, RHEL Workstation, Hyper-V, Proxmox VE, Nutanix AHV), services (DNS, Kubernetes, Identity Provider/Entra ID, Privileged Access Management, Email Security Gateway, Two-Factor Authentication/Duo), software (GitLab, Subversion, Oracle VirtualBox), policies (Password and Credential Management, Cryptographic Key Management, Physical Security), and — filling previously entirely-absent schema types — 4 `physical` components (Main Office Server Room, Remote Office Comms Room, Air Conditioning, Power Generator), 1 `process-procedure`, 1 `plan`, 1 `guidance`, and 1 `standard`. See the updated §11 table for the full breakdown.
- Added 2 new capabilities — **Virtualisation (VMware)** and **Virtualisation (Hyper-V)** — each bundling a hypervisor component with the shared SAN Storage Array and NAS components, generated by driving the real `ComponentTab`/`CapabilityTab` code paths rather than hand-written, so their aggregated control-implementations are exactly what the UI itself would produce.
- Every new component's control implementations use real ISM control IDs, verified directly against the bundled catalog before use — never invented.

**Fixes:**
- Fixed a schema violation present in 29 pre-existing library component files: an invalid `remarks` field on `port-ranges` entries (the schema only allows `start`/`end`/`transport` there), plus an empty `protocols: []` array in 6 policy components (the schema requires it be non-empty if present at all, so the key was removed instead). All 95 library components now validate cleanly against `oscal_component_schema.json`.

**Known follow-up (not yet fixed):** `component_tab.py`'s `COMPONENT_TYPES` list splits the schema's single `process-procedure` type into two separate dropdown options (`"process"`, `"procedure"`), neither of which is the exact schema term — see §11's note and `todo.md`.

### Version 4.0 (July 2026)

**New features:**
- **Component version / revision / UUID metadata** — surfaces OSCAL's native document-level `version`/`metadata.revisions[]` and stable UUIDs per component in the Component Editor (`ComponentTab`), replacing the shared tab-level `_file_uuid`/`_file_version` with per-component storage. New "Version & Revision History" card in Section 1 with an editable Version field, read-only UUID labels, revision history list, and a "📌 Save New Version" action. Groundwork for a future "compare version" function; components only — capabilities not yet covered. Full design in §10.21.

**Fixes:**
- Fixed the shared tab-level `_file_uuid`/`_file_version` state in `ComponentTab`, which wrote the *same* document UUID and version to every component's saved file — most visibly broken in `library_mode`, where many components share one tab instance.

### Version 3.9 (July 2026)

**New features:**
- **Organisation tab** (`app.py`, new group between Data and System Overview): "⚙ Library Components", "🔗 Library Capabilities" (second instances of `ComponentTab`/`CapabilityTab` with the new `library_mode=True`), and "🌐 All Systems" (moved from top-level).
- **`ComponentTab`/`CapabilityTab` `library_mode`**: locks an instance to `library/components/`/`library/capabilities/` — no Open File(s)/Open Folder/Import from Library, auto-loads on construction and via "🔄 Refresh from Library", saves back with no location prompt (new `_component_paths`/`_capability_paths` + `_save_to_library_path()`), and a new "📥 Add File to Library" for bringing in an external file. See §10.20.
- Resolves `user_stories.md` US-14.

**Fixes:**
- `OSCALApp.__init__()` now builds the status bar before the notebook — `library_mode`'s auto-load calls `set_status()` during construction, which previously ran before `self._status_lbl` existed.

### Version 3.8 (July 2026)

**New features:**
- **Systems folder** (`settings.py`): `get_systems_path()`/`set_systems_path()`, same persisted-setting pattern as the Library folder, defaulting to the repo's own `systems/` folder. New "🗂 Systems Folder" toolbar button.
- **🌐 All Systems tab** (`all_systems_tab.py`, new): scans every subfolder of the Systems folder and shows an organisation-wide rollup — one row per system (compliance %, open risks, POA&M overdue, last assessed) plus aggregate totals — resolving `user_stories.md` US-13 as a separate, disk-reading tab rather than by extending the existing (live-tab-reading) Dashboard. See §10.19.
- Bundled example environments moved: `example-data-ism/`, `example-data-nist/`, `example-02/` are now under `systems/` (a plain file move; nothing inside any of them changed).

### Version 3.7 (July 2026)

**New features:**
- **Grouped top-level tabs** (`app.py`, see §10.18): the ten flat top-level tabs are now five — Workspace, Data (Data Sources + Catalog Viewer), System Overview (Component + Capability + SSP Editor), Audit (Assessment Plan + Assessment Results + POA&M Editor), and Dashboard, which stays top-level as a cross-cutting rollup.
- New `tab_utils.py` module: `is_tab_active(widget)` replaces the mousewheel-scroll guard's old "compare immediate parent's `.select()`" check with one that walks up through any nesting depth — needed once tabs could be nested two Notebooks deep.

**Refactoring:**
- `component_tab.py`, `capability_tab.py`, `ssp_tab.py`, `ap_tab.py`, `ar_tab.py`, `poam_tab.py` all switched their `_on_mousewheel()` guard to the shared `is_tab_active()` helper instead of duplicating the (now nesting-unaware) inline check.

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
