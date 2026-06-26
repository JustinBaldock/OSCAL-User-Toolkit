# OSCAL User Toolkit — Design Document

**Version:** 2.0  
**Date:** June 2026  
**Language:** Python 3.10+ (standard library only, plus optional `jsonschema`)  
**GUI Framework:** tkinter (built into Python)

---

## 1. Purpose and Scope

The OSCAL User Toolkit is a desktop application for working with files that follow the **Open Security Controls Assessment Language (OSCAL)** standard. OSCAL is a machine-readable format published by NIST for describing security controls, system security plans, and component definitions as structured JSON files.

The toolkit allows a security practitioner to:

- Browse and search an OSCAL **catalog** of security controls, with filtering by class, guideline group, and keyword
- Apply an OSCAL **profile** to filter the catalog to a relevant baseline
- Create and save OSCAL **Component Definition** files describing how system components implement controls
- Create and save OSCAL **Capability Definition** files grouping components into named security functions, with automatic inheritance of component-level control responses
- Create and save an OSCAL **System Security Plan (SSP)** for a system
- Validate catalog and capability files against the bundled OSCAL JSON schema on open/save

---

## 2. File and Folder Structure

```
oscal_user_toolkit/          ← Python package folder
    __init__.py              ← Empty file that marks this as a package
    main.py                  ← Entry point — run this to start the app
    models.py                ← All data logic (no GUI code)
    app.py                   ← Main window, toolbar, info panel
    catalog_tab.py           ← Catalog Viewer tab
    component_tab.py         ← Component Editor tab
    capability_tab.py        ← Capability Editor tab
    ssp_tab.py               ← SSP Editor tab

oscal/                       ← OSCAL schema release zips
    oscal-1.1.2.zip
    oscal-1.2.0.zip
    oscal-1.2.2.zip

example-data/                ← Sample files for testing
    ISM_catalog.json
    ...
```

The application requires no external libraries for core operation.
`jsonschema` is an optional dependency — if installed, catalog and capability
files are validated against the bundled OSCAL schema on open/save. If not
installed, validation is silently skipped.

---

## 3. Architecture Overview

The application is structured in two layers:

```
┌──────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER  (GUI)                                   │
│                                                              │
│  app.py           OSCALApp (main window)                     │
│  catalog_tab.py   CatalogTab (tk.Frame subclass)             │
│  component_tab.py ComponentTab (tk.Frame subclass)           │
│  capability_tab.py CapabilityTab (tk.Frame subclass)         │
│  ssp_tab.py       SSPTab (tk.Frame subclass)                 │
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
│                  new_uuid(), now_iso()                       │
└──────────────────────────────────────────────────────────────┘
```

### Why this separation matters

`models.py` contains zero GUI code. It can be imported, tested, and
run independently of tkinter. This means:

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
| `get_source_href(profile, catalog)` | Return the filename for control-implementations 'source' (profile preferred, catalog fallback) |
| `get_profile_controls(catalog, profile)` | Return the filtered or full control list used by ComponentTab and CapabilityTab |
| `refresh_ctrl_list(...)` | Rebuild both control list Treeview tabs (shared by ComponentTab and CapabilityTab) |
| `build_component_oscal_entry(comp, source_href)` | Convert one internal component dict to an OSCAL defined-component dict |
| `validate_oscal_file(data, schema_name, zip_path)` | Validate a parsed JSON dict against the OSCAL schema zip |
| `empty_ssp()` | Return a blank SSP dictionary with default values |
| `build_oscal_ssp(ssp, profile, catalog)` | Convert the internal SSP dict to a valid OSCAL JSON document |
| `parse_ssp_file(data)` | Convert a saved OSCAL SSP JSON dict back into the internal format |
| `validate_ssp(ssp, profile, catalog)` | Check for missing required fields; return (errors, warnings) |
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

The `guideline` field is the first element of the `path` breadcrumb. It
is used by the Catalog Viewer's Guideline column and filter dropdown.

The OSCAL catalog is a nested structure (catalog → groups → sub-groups
→ controls). `collect_controls()` walks the entire tree recursively and
returns a **flat** list, which is much easier for the GUI to work with.

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

`ids` is a Python `set` (not a list). Sets make the `in` operator very
fast — checking whether a control ID is in the profile takes the same
time whether the profile has 10 or 10,000 controls.

### 4.4 Shared helper functions

**`get_source_href(profile, catalog)`**  
Both ComponentTab and CapabilityTab need to write a `source` URI into
control-implementations blocks. This function centralises the logic:
prefer the profile filename, fall back to the catalog filename, fall back
to a placeholder string if neither is loaded.

**`get_profile_controls(catalog, profile)`**  
Both tabs show the same control list (profile-filtered if a profile is
loaded, full catalog otherwise). This function is the single source of
truth for that logic.

**`refresh_ctrl_list(...)`**  
Rebuilds both the "All Controls" and "Applied Controls" Treeview tabs.
Shared by ComponentTab and CapabilityTab so the rendering logic exists
in one place only.

**`build_component_oscal_entry(comp, source_href)`**  
Converts one internal component dict to an OSCAL defined-component dict.
Used by both ComponentTab (single-component save) and CapabilityTab
(bundling member components into the capability file).

### 4.5 The SSP internal format

The SSP is stored as a plain Python dictionary throughout editing. It is
only converted to OSCAL JSON at save time by `build_oscal_ssp()`.

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
    "data_flow":                  str,
    "roles":     list,   # [{"role_id": str, "title": str}]
    "parties":   list,   # [{"uuid", "type", "name", "email"}]
    "information_types": list,  # [{"uuid","title","description","c_impact","i_impact","a_impact"}]
}
```

---

## 5. The Presentation Layer

### 5.1 OSCALApp (app.py)

`OSCALApp` inherits from `tk.Tk`, making it the root window. It is
responsible for:

- The **main toolbar** (OSCAL version selector, Open Catalog, Open Profile, Clear Profile buttons)
- The **info panel** (two cards showing catalog and profile metadata)
- The **notebook** (tabbed container holding all four tabs)
- The **status bar** (one-line message at the bottom)
- Loading catalog and profile files, validating them against the schema, and distributing the data to tabs

`OSCALApp` holds two pieces of shared state:

```python
self._catalog = None   # loaded catalog dict, or None
self._profile = None   # loaded profile dict, or None
```

These are the single source of truth for which files are loaded. Tabs
do not store their own copies — they receive the data through callbacks.

The OSCAL version selector in the toolbar scans the `oscal/` folder for
zip files at startup and presents them newest-first. The selected version
is used for schema validation (catalog on open, capability on save) and
written into the `oscal-version` field of saved capability files.

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

**Dynamic text wrapping:** All text labels in the detail pane (statement, category, header title, row values) have their `wraplength` updated whenever the right pane is resized (`_on_canvas_configure`). This replaces the previous hardcoded pixel values that caused text to overflow when the window was made narrower.

**Public methods the app calls:**
- `load_controls(controls)` — replaces the full list after a catalog is loaded
- `apply_profile(profile_ids)` — applies or removes the profile filter

**Internal filtering:** all four filters (profile, class, guideline, search) are
applied together inside `_apply_filters()` which runs whenever any one of them changes.

### 5.3 ComponentTab (component_tab.py)

Creates and edits OSCAL Component Definition files.

**Owns:**
- `_components` — list of component dicts (the in-memory file state)
- `_file_uuid`, `_file_title`, `_file_version` — file-level metadata
- `_selected_index` — which component is currently open in the form
- `_ctrl_responses` — `{control_id: description}` for the current component
- `_selected_ctrl_id` — which control is selected in Section 7
- `_dirty` — whether there are unsaved changes

**Guard condition:** the tab checks `_get_catalog()` on startup and whenever the app calls `on_catalog_or_profile_changed()`. If no catalog is loaded, the editing pane is hidden and a gate panel is shown. A profile is optional — if loaded, Section 7 shows only profile controls; without one the full catalog is shown.

**File operations:**
- `📂 Open File(s)` — loads one or more component JSON files (components appended, duplicates by UUID skipped)
- `📁 Open Folder` — loads every `.json` file in a chosen directory
- `💾 Save Component` — validates and saves the selected component to its own file

**Public methods the app calls:**
- `on_catalog_or_profile_changed()` — re-evaluates the guard condition
- `set_on_components_changed(callback)` — registers the CapabilityTab's `on_state_changed` to be called whenever the component list changes
- `add_component(comp)` — adds a component dict if its UUID is not already present; called by CapabilityTab when loading a capability file that bundles member components

**Dialog helper:** `_make_dialog(title, width)` creates a styled modal Toplevel with `transient` + `grab_set` behaviour. Used by `_property_dialog` and `_role_dialog` to avoid duplicating window-creation boilerplate.

### 5.4 CapabilityTab (capability_tab.py)

Creates and edits OSCAL Capability Definition files. A capability is a
named security function composed of one or more components, with
control implementations that may be inherited from members or defined
at the capability level.

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
    "member_descriptions":      {uuid: str},  # each member's role
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
- `📂 Open File(s)` — loads one or more capability JSON files; bundled member components are imported into ComponentTab's live list via `_add_component`
- `📁 Open Folder` — loads every `.json` file in a chosen directory
- `💾 Save Capability` — validates, optionally schema-checks, and saves the selected capability with its member components bundled

**OSCAL output format:** The saved file is an OSCAL `component-definition` document with:
- `components[]` — the bundled member components
- `capabilities[0]` — the capability definition with `incorporates-components` and `control-implementations`
- Inherited responses are saved as `implemented-requirement` entries with a `props[{name: "source-component-uuid", value: "..."}]` entry for attribution
- Capability-level responses are saved as `implemented-requirement` entries without that prop

**Dialog helper:** `_make_dialog(title, width)` — same pattern as ComponentTab, used by `_member_dialog`.

**Public methods the app calls:**
- `on_state_changed()` — re-evaluates guard, resyncs inherited controls, refreshes the form

### 5.5 SSPTab (ssp_tab.py)

Creates and edits OSCAL System Security Plan files.

**Owns:**
- `_ssp` — the in-memory SSP dict (see Section 4.5)
- All form widgets (StringVars, Text widgets, Treeview tables)

**Public methods the app calls:**
- `refresh_profile_box()` — updates the profile info label in the SSP toolbar

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
    │       resets search, count label
    │       populates the Treeview
    │
    ├─► ssp_tab.refresh_profile_box()
    │
    ├─► component_tab.on_catalog_or_profile_changed()
    │
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

### 6.4 Saving a Component Definition

```
User fills form → "✔ Apply Component Changes" → "💾 Save Component"
    │
    ├─► _collect_into(index)   reads form into component dict
    ├─► _validate_selected()   checks required fields
    ├─► filedialog.asksaveasfilename()
    ├─► models.get_source_href(profile, catalog)   resolves source URI
    ├─► models.build_component_oscal_entry(comp, source_href)
    └─► json.dump(doc, file, indent=2)
```

### 6.5 Saving a Capability

```
User builds capability → "💾 Save Capability"
    │
    ├─► _collect_into(index)   reads form into capability dict
    ├─► _validate_selected()   checks name, description, members, UUID resolution
    ├─► filedialog.asksaveasfilename()
    ├─► _build_oscal_document(cap)
    │     models.get_source_href(profile, catalog)
    │     models.build_component_oscal_entry() for each member component
    │     inherited responses → implemented-requirements with source-component-uuid prop
    │     capability-level responses → implemented-requirements without the prop
    ├─► models.validate_oscal_file() → warns if schema violations found
    └─► json.dump(doc, file, indent=2)
```

### 6.6 Loading a Capability file

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

### 6.7 Saving an SSP

```
User clicks "💾 Save SSP"
    │
    ├─► _collect()             reads all form widgets into self._ssp
    ├─► models.validate_ssp()  returns (errors, warnings)
    ├─► filedialog.asksaveasfilename()
    ├─► models.build_oscal_ssp(ssp, profile, catalog)
    └─► json.dump(doc, file, indent=2)
```

---

## 7. Inter-Tab Communication

Tabs never talk directly to each other. All communication goes through
`OSCALApp` using the **callback (dependency injection) pattern**:

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

This ensures the Capability Editor re-evaluates its guard (at least one
component must be open) whenever the Component Editor's list changes.

**Why lambdas?** A lambda like `lambda: self._catalog` gives a tab a way
to ask "what catalog is loaded right now?" without holding a reference to
the app. The tab calls `self._get_catalog()` and gets the current value
at that moment — not a copy taken at construction time. This is the
**dependency injection** pattern: the tab declares what it needs; the
app decides what to provide.

---

## 8. The Guard Pattern

Both ComponentTab and CapabilityTab enforce prerequisites before editing
is permitted. This is implemented as a **gate panel** that covers the
editing area.

**ComponentTab guard:** requires a catalog. Profile is optional.

**CapabilityTab guard:** requires both a catalog AND at least one component open in the Component Editor.

```
on_catalog_or_profile_changed() / on_state_changed()
    │
    ├─► _ready()   True only if prerequisites are met
    │
    ├── if NOT ready:
    │       body_pane.pack_forget()     hide editing area
    │       gate_frame.pack(...)        show lock panel
    │       _update_gate_label()        show ✅/❌ status per prerequisite
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
    "metadata": { "title": "...", "version": "...", "oscal-version": "1.2.2" },
    "groups": [
      {
        "title": "Guidelines for cyber security roles",
        "groups": [
          {
            "title": "Board of directors and executive committee",
            "groups": [
              {
                "title": "Embedding cyber security",
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
    ]
  }
}
```

The ISM catalog has 3 levels of group nesting. The top-level group title
("Guidelines for cyber security roles") becomes the `guideline` field on
each control collected from that branch.

### 9.2 Component Definition (created by ComponentTab)

```json
{
  "component-definition": {
    "uuid": "auto-generated",
    "metadata": {
      "title": "hardware - My Firewall",
      "last-modified": "2026-06-25T10:00:00Z",
      "version": "1.0",
      "oscal-version": "1.2.2"
    },
    "components": [
      {
        "uuid": "auto-generated",
        "type": "hardware",
        "title": "My Firewall",
        "description": "A perimeter firewall...",
        "props": [{"name": "operational-status", "value": "operational"}],
        "responsible-roles": [{"role-id": "asset-administrator"}],
        "control-implementations": [
          {
            "uuid": "auto-generated",
            "source": "ISM_profile.json",
            "description": "...",
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
    "metadata": { "title": "Capability: Account Management", "oscal-version": "1.2.2" },
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

The `source-component-uuid` prop is the OSCAL extension mechanism for
component attribution in component-definition files. The `by-component`
field (which provides this natively) is only available in SSP, not in
component-definition.

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

Conversion between them happens only at load time and save time. This
makes the form code much simpler — it works with flat Python dicts rather
than deeply nested OSCAL structures.

### 10.2 UUIDs

OSCAL requires a UUID on every significant object. The toolkit
auto-generates UUIDs using `uuid.uuid4()` so the user never has to manage
them. Once generated, a UUID is preserved across edits so that the same
document remains consistently identifiable.

### 10.3 Back-matter for profile provenance

When saving an SSP, the toolkit records the loaded profile's title,
version, and filename inside the SSP's `back-matter` section. The
`import-profile.href` is then set to `#<uuid>` pointing at that
back-matter entry. This means the SSP is self-documenting — anyone
reading the file can see exactly which profile version was used.

### 10.4 The `set` type for profile IDs

Profile IDs are stored as a Python `set` rather than a list. The `in`
operator on a set is O(1) regardless of set size. Since the catalog
filter checks every control against the profile IDs, this matters when
there are 1,000+ controls.

### 10.5 Flat control list

The OSCAL catalog is a deeply nested tree. `collect_controls()` flattens
it into a single list at load time. The `path` (breadcrumb) and
`guideline` (top-level group name) fields preserve hierarchy context
for display and filtering without requiring the GUI to traverse the tree.

### 10.6 Schema validation — warn, don't block

Both catalog loading and capability saving validate against the OSCAL
schema zip if `jsonschema` is installed. Validation failures show a
warning dialog (ask yes/no) rather than hard-blocking the operation.
This is intentional: real-world OSCAL files sometimes have minor schema
deviations, and blocking would make the tool unusable with those files.

### 10.7 Capability control inheritance

The OSCAL `component-definition` schema has no `by-component` field (that
is SSP-only). To attribute control responses to specific components within
a capability, the toolkit uses the OSCAL `props` extension mechanism:
each inherited `implemented-requirement` carries a prop named
`source-component-uuid`. This is OSCAL-conformant and round-trips
correctly when the file is loaded back in.

### 10.8 Tab reorder-safe mousewheel

Both ComponentTab and CapabilityTab use `bind_all("<MouseWheel>", ...)`,
which fires on all tabs. To scroll only the active tab's canvas, each
handler compares `self.master.select()` against `str(self)` — the widget
path string that uniquely identifies this tab's frame. This is resilient
to tab reordering, unlike the previous approach of hardcoding a tab index
integer.

### 10.9 Dialog boilerplate via `_make_dialog`

Both ComponentTab and CapabilityTab need multiple modal dialogs. Each tab
has a `_make_dialog(title, width)` method that creates a styled, modal
`Toplevel` with `transient` + `grab_set` behaviour. Individual dialog
methods call this instead of repeating the same six lines of setup code.

---

## 11. Potential Future Enhancements

| Feature | Where it would go |
|---|---|
| Stage 2 SSP control responses (click a control, write a response) | `ssp_tab.py` — add Section 7 matching ComponentTab's Section 7 |
| SSP ↔ Component linking (inherit responses via `by-component`) | `ssp_tab.py` + `models.py` — reference component file UUIDs |
| Export to PDF / HTML report | New `report_tab.py` or standalone export function in `models.py` |
| Multiple catalogs / profiles open at once | `app.py` — change `self._catalog` to a list |
| Dark/light theme toggle | `app.py` — add a second COLORS dict and rebuild styles |
| Component Editor list refresh after capability file load | `ComponentTab._refresh_list()` called via a new callback after `add_component` |

---

## 12. Changelog

### Version 2.0 (June 2026)

**New features:**
- **Capability Editor** (`capability_tab.py`) — create, edit, load, and save OSCAL capability definitions; automatic inheritance of control responses from member components
- **Open File(s) / Open Folder** in both Component Editor and Capability Editor
- **OSCAL version selector** in the toolbar — scans `oscal/` zip files; drives schema validation and `oscal-version` in saved files
- **Schema validation** — catalog files validated on open; capability files validated before save; both warn-and-allow rather than hard-block
- **Catalog Viewer: Guideline column** — new fourth column showing the top-level catalog group (e.g. "Guidelines for cyber security roles")
- **Catalog Viewer: Guideline filter dropdown** — filter the control list by top-level group
- **Catalog Viewer: dynamic text wrapping** — detail pane labels rewrap when the panel is resized
- **Component Editor: profile optional** — profile no longer required; control list falls back to full catalog

**Refactoring:**
- `models.get_source_href(profile, catalog)` — extracted from both tabs, single source of truth for the control-implementations source URI
- `models.get_profile_controls(catalog, profile)` — extracted from both tabs, single source of truth for profile-filtered control list
- `ComponentTab.add_component(comp)` — public method replacing direct list mutation from CapabilityTab
- `_make_dialog(title, width)` — dialog boilerplate extracted in both ComponentTab and CapabilityTab
- Mousewheel guard changed from hardcoded tab index to `nb.select() == str(self)` — resilient to tab reordering
- `DOT_PARTIAL` constant removed (was defined but never used)
- `collect_controls()` now adds `"guideline"` field to each control dict

**Comment improvements:**
- Canvas/scrollable-frame pattern explained in `catalog_tab.py`
- `trace_add` explained in `component_tab.py`
- Inherited control resync rationale explained in `capability_tab.py`
- `add_component` cross-tab coupling explained in `capability_tab.py`
- `_make_dialog` `transient` and `grab_set` explained in both tabs
