# OSCAL User Toolkit — Design Document

**Version:** 1.0  
**Date:** June 2026  
**Language:** Python 3.10+ (standard library only — no third-party packages required)  
**GUI Framework:** tkinter (built into Python)

---

## 1. Purpose and Scope

The OSCAL User Toolkit is a desktop application for working with files that follow the **Open Security Controls Assessment Language (OSCAL)** standard. OSCAL is a machine-readable format published by NIST for describing security controls, system security plans, and component definitions as structured JSON files.

The toolkit allows a security practitioner to:

- Browse and search an OSCAL **catalog** of security controls
- Apply an OSCAL **profile** to filter the catalog to a relevant baseline
- Create and save OSCAL **Component Definition** files describing how system components implement controls
- Create and save an OSCAL **System Security Plan (SSP)** for a system

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
    ssp_tab.py               ← SSP Editor tab
```

The application uses no external libraries. Every import comes from
Python's standard library (`json`, `tkinter`, `uuid`, `datetime`, `pathlib`).

---

## 3. Architecture Overview

The application is structured in two layers:

```
┌─────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER  (GUI)                              │
│                                                         │
│  app.py          OSCALApp (main window)                 │
│  catalog_tab.py  CatalogTab (tk.Frame subclass)         │
│  component_tab.py ComponentTab (tk.Frame subclass)      │
│  ssp_tab.py      SSPTab (tk.Frame subclass)             │
└────────────────────────┬────────────────────────────────┘
                         │ calls functions from
┌────────────────────────▼────────────────────────────────┐
│  DATA LAYER  (no GUI)                                   │
│                                                         │
│  models.py       load_catalog(), load_profile(),        │
│                  build_oscal_ssp(), parse_ssp_file(),   │
│                  validate_ssp(), new_uuid(), now_iso()  │
└─────────────────────────────────────────────────────────┘
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
    "path":            str,   # breadcrumb e.g. "Cyber security principles › Govern"
}
```

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

### 4.4 The SSP internal format

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

- The **main toolbar** (Open Catalog, Open Profile, Clear Profile buttons)
- The **info panel** (two cards showing catalog and profile metadata)
- The **notebook** (tabbed container holding all three tabs)
- The **status bar** (one-line message at the bottom)
- Loading catalog and profile files and distributing the data to tabs

`OSCALApp` holds two pieces of shared state:

```python
self._catalog = None   # loaded catalog dict, or None
self._profile = None   # loaded profile dict, or None
```

These are the single source of truth for which files are loaded. Tabs
do not store their own copies — they receive the data through callbacks.

### 5.2 CatalogTab (catalog_tab.py)

Displays the catalog control list and a scrollable detail pane.

**Owns:**
- `_all_controls` — the complete flat list from the catalog
- `_filtered_controls` — the currently visible subset
- `_profile_ids` — the profile filter (set by app via `apply_profile()`)
- `_selected_class` — the class dropdown value
- `_search_var` — the search box text
- The filter toolbar (class dropdown, search box, count label)

**Public methods the app calls:**
- `load_controls(controls)` — replaces the full list after a catalog is loaded
- `apply_profile(profile_ids)` — applies or removes the profile filter

**Internal filtering:** all three filters (profile, class, search) are
applied together inside `_apply_filters()` which runs whenever any one
of them changes.

### 5.3 ComponentTab (component_tab.py)

Creates and edits OSCAL Component Definition files.

**Owns:**
- `_components` — list of component dicts (the in-memory file state)
- `_file_uuid`, `_file_title`, `_file_version` — file-level metadata
- `_selected_index` — which component is currently open in the form
- `_ctrl_responses` — `{control_id: description}` for the current component
- `_selected_ctrl_id` — which control is selected in Section 7
- `_dirty` — whether there are unsaved changes

**Guard condition:** the tab checks `_get_catalog()` and `_get_profile()`
on startup and whenever the app calls `on_catalog_or_profile_changed()`.
If either is `None`, the editing pane is hidden and a gate panel is shown
in its place. This enforces that the control implementations section
(Section 7) always has a valid source of controls.

**Public methods the app calls:**
- `on_catalog_or_profile_changed()` — re-evaluates the guard condition

### 5.4 SSPTab (ssp_tab.py)

Creates and edits OSCAL System Security Plan files.

**Owns:**
- `_ssp` — the in-memory SSP dict (see Section 4.4)
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
    │ calls json.load() → models.load_catalog(filepath)
    │   → collect_controls() walks the nested catalog
    │   → returns flat catalog dict
    │
    ├─► stores in self._catalog
    ├─► updates catalog info card labels
    ├─► resets profile state (self._profile = None)
    │
    ├─► catalog_tab.load_controls(catalog["controls"])
    │       stores in _all_controls
    │       resets class dropdown, search, count label
    │       populates the Treeview
    │
    ├─► ssp_tab.refresh_profile_box()
    │       shows "⚠ No profile loaded" warning
    │
    └─► component_tab.on_catalog_or_profile_changed()
            re-evaluates guard → shows gate panel
            (profile was also cleared)
```

### 6.2 Loading a profile

```
User clicks "🔖 Open Profile"
    │
    ▼
app._open_profile()
    │ calls models.load_profile(filepath)
    │   → collects control IDs into a Python set
    │   → returns profile dict
    │
    ├─► stores in self._profile
    ├─► updates profile info card labels
    ├─► enables "✕ Clear Profile" button
    │
    ├─► catalog_tab.apply_profile(profile["ids"])
    │       stores profile_ids in _profile_ids
    │       calls _apply_filters() → rebuilds the Treeview
    │       updates the count label
    │
    ├─► ssp_tab.refresh_profile_box()
    │       shows profile title, version, control count
    │
    └─► component_tab.on_catalog_or_profile_changed()
            both catalog and profile now loaded
            hides gate panel, shows editing pane
            refreshes Section 7 control list
```

### 6.3 Filtering the catalog (CatalogTab internal)

The CatalogTab applies three filters in sequence every time any one changes:

```
_apply_filters()
    │
    ├─► Step 1 — Profile filter
    │   if _profile_ids is not None:
    │       keep only controls whose id is in _profile_ids (set lookup)
    │
    ├─► Step 2 — Class filter
    │   if _selected_class != "All":
    │       keep only controls with matching class
    │
    ├─► Step 3 — Text search
    │   if search term is not empty:
    │       keep only controls where term appears in
    │       label, title, statement, or id
    │
    └─► _populate_tree(result)
        _update_count()
```

### 6.4 Selecting a control in the Catalog Viewer

```
User clicks a row in the Treeview
    │
    ▼
_tree_selected()
    │ reads the row iid (integer index)
    │ looks up _filtered_controls[index]
    │
    └─► _show_detail(ctrl)
            destroys old detail widgets
            builds new label/badge/statement widgets
            updates the canvas scroll region
```

### 6.5 Saving an SSP

```
User clicks "💾 Save SSP"
    │
    ▼
ssp_tab._save()
    │
    ├─► _collect()         reads all form widgets into self._ssp dict
    │
    ├─► models.validate_ssp(self._ssp, profile, catalog)
    │       returns (hard_errors, warnings)
    │       hard errors → show error dialog, abort
    │       warnings → ask user to confirm
    │
    ├─► filedialog.asksaveasfilename()   asks where to save
    │
    ├─► models.build_oscal_ssp(self._ssp, profile, catalog)
    │       converts internal dict to OSCAL JSON structure
    │       adds import-profile with back-matter resource
    │       auto-generates "this-system" component
    │       returns nested Python dict
    │
    └─► json.dump(doc, file, indent=2)
            writes formatted JSON to disk
```

### 6.6 Re-opening a saved SSP

```
User clicks "📂 Open SSP"
    │
    ▼
ssp_tab._open()
    │ json.load(file) → raw data dict
    │
    ├─► models.parse_ssp_file(data)
    │       navigates the OSCAL structure
    │       extracts metadata, roles, parties, info types
    │       extracts back-matter profile reference
    │       returns (ssp_dict, back_matter_info)
    │
    ├─► self._ssp = ssp_dict
    │
    ├─► _populate()
    │       pushes values into StringVar fields
    │       inserts text into Text widgets
    │       rebuilds Treeview tables (info types, roles, parties)
    │
    └─► _update_profile_box_from_bm(back_matter_info)
            shows profile title from saved back-matter
            (even if the profile file is not currently loaded)
```

### 6.7 Saving a Component Definition

```
User fills in form, clicks "✔ Apply Component Changes"
    │
    ▼
component_tab._apply_component()
    │ _collect_into(index)   reads form widgets into component dict
    │ _refresh_list()        renames the list entry if title changed
    │ _refresh_control_list() updates dot indicators in Section 7
    │
    ▼ (later) User clicks "💾 Save File"
    │
    ├─► _collect_into(index)   final collection
    ├─► _validate()            check required fields
    ├─► filedialog.asksaveasfilename()
    │
    ├─► _build_oscal_document()
    │       for each component:
    │         builds props list (includes status as "operational-status" prop)
    │         builds responsible-roles list
    │         builds control-implementations from _ctrl_responses dict:
    │             one implemented-requirement per control with a response
    │             grouped under one control-implementation entry
    │             source href = profile filename (or catalog as fallback)
    │
    └─► json.dump(doc, file, indent=2)
```

---

## 7. Inter-Tab Communication

Tabs never talk directly to each other. All communication goes through
`OSCALApp` using the **callback (dependency injection) pattern**:

```
┌──────────────┐     callbacks     ┌─────────────────┐
│   OSCALApp   │ ────────────────► │   CatalogTab    │
│              │                   │                 │
│ _catalog     │ get_catalog=      │ _all_controls   │
│ _profile     │   lambda: self._catalog             │
│              │                   │                 │
│              │ ────────────────► │  ComponentTab   │
│              │                   │                 │
│              │ get_profile=      │ _components     │
│              │   lambda: self._profile             │
│              │                   │                 │
│              │ ────────────────► │    SSPTab       │
│              │                   │                 │
│              │ set_status=       │ _ssp            │
│              │   lambda msg:     │                 │
│              │   self._status_lbl│                 │
│              │   .config(text=m) │                 │
└──────────────┘                   └─────────────────┘
```

A **lambda** is a small anonymous function. For example:

```python
get_catalog = lambda: self._catalog
```

This gives the tab a way to ask "what catalog is loaded right now?"
without needing a direct reference to the app object. The tab calls
`self._get_catalog()` and gets back the current value of `self._catalog`
at that moment — not a copy taken at construction time.

This pattern means:
- Tabs are fully self-contained and can be tested independently
- The app controls what data tabs can see
- Adding a new tab never requires modifying existing tabs

---

## 8. The Guard Pattern (ComponentTab)

The ComponentTab enforces a prerequisite: both a catalog and a profile
must be loaded before editing is permitted. This is implemented as a
**gate panel** that covers the editing area.

```
on_catalog_or_profile_changed()   ← called by app after any load/clear
    │
    ├─► _ready()   returns True only if both catalog AND profile are loaded
    │
    ├── if NOT ready:
    │       body_pane.pack_forget()     hide editing area
    │       gate_frame.pack(...)        show lock panel
    │       _update_gate_label()        show ✅/❌ status
    │
    └── if ready:
            gate_frame.pack_forget()   hide lock panel
            body_pane.pack(...)        show editing area
            _refresh_control_list()    populate Section 7 controls
```

The gate label is updated dynamically to show exactly what is missing,
e.g. `✅ Catalog loaded  ❌ No profile loaded`.

---

## 9. The OSCAL JSON Structures

### 9.1 Catalog (read-only input)

The toolkit reads but never writes catalog files.

```json
{
  "catalog": {
    "uuid": "...",
    "metadata": { "title": "...", "version": "...", ... },
    "groups": [
      {
        "title": "Governance",
        "groups": [
          {
            "title": "Principles",
            "controls": [
              {
                "id": "ism-principle-gov-01",
                "class": "ISM-principle",
                "title": "Executive cyber security accountability",
                "props": [{"name": "label", "value": "GOV-01"}, ...],
                "parts": [{"name": "statement", "prose": "The board of directors..."}]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### 9.2 Profile (read-only input)

The toolkit reads but never writes profile files.

```json
{
  "profile": {
    "uuid": "...",
    "metadata": { "title": "...", "version": "...", ... },
    "imports": [
      {
        "href": "#catalog-uuid",
        "include-controls": [
          { "with-ids": ["ism-1130", "ism-0169", "ism-principle-gov-01", ...] }
        ]
      }
    ]
  }
}
```

### 9.3 Component Definition (created by ComponentTab)

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
        "purpose": "Filters network traffic.",
        "props": [
          {"name": "operational-status", "value": "operational"},
          {"name": "virtual",            "value": "no"}
        ],
        "responsible-roles": [
          {"role-id": "asset-administrator", "remarks": "Network team"}
        ],
        "control-implementations": [
          {
            "uuid": "auto-generated",
            "source": "ISM_NON_CLASSIFIED-baseline_profile.json",
            "description": "Controls implemented by this component.",
            "implemented-requirements": [
              {
                "uuid": "auto-generated",
                "control-id": "ism-1130",
                "description": "The firewall enforces cable reticulation by..."
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### 9.4 System Security Plan (created by SSPTab)

```json
{
  "system-security-plan": {
    "uuid": "auto-generated",
    "metadata": {
      "title": "My System SSP",
      "last-modified": "2026-06-25T10:00:00Z",
      "version": "1.0",
      "oscal-version": "1.1.2",
      "roles":   [{"id": "isso", "title": "ISSO"}],
      "parties": [{"uuid": "...", "type": "person", "name": "Alice"}]
    },
    "import-profile": { "href": "#back-matter-resource-uuid" },
    "system-characteristics": {
      "system-ids": [{"id": "...", "identifier-type": "https://ietf.org/rfc/rfc4122"}],
      "system-name": "My System",
      "description": "This system...",
      "security-sensitivity-level": "fips-199-moderate",
      "system-information": {
        "information-types": [
          {
            "uuid": "...", "title": "Personnel Data",
            "confidentiality-impact": {"base": "fips-199-moderate"},
            "integrity-impact":       {"base": "fips-199-moderate"},
            "availability-impact":    {"base": "fips-199-low"}
          }
        ]
      },
      "status": {"state": "operational"},
      "authorization-boundary": {"description": "The whole network."}
    },
    "system-implementation": {
      "components": [
        {
          "uuid": "auto-generated",
          "type": "this-system",
          "title": "My System",
          "description": "This system...",
          "status": {"state": "operational"}
        }
      ]
    },
    "control-implementation": {
      "description": "Stage 2.",
      "implemented-requirements": []
    },
    "back-matter": {
      "resources": [
        {
          "uuid": "back-matter-resource-uuid",
          "title": "Information security manual non-classified Baseline",
          "props": [
            {"name": "type",          "value": "profile"},
            {"name": "version",       "value": "2026.06.18"},
            {"name": "oscal-version", "value": "1.1.2"},
            {"name": "last-modified", "value": "2026-06-18"}
          ],
          "rlinks": [{"href": "ISM_NON_CLASSIFIED-baseline_profile.json"}]
        }
      ]
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

Conversion between them happens only at load time (`parse_ssp_file`) and
save time (`build_oscal_ssp`). This makes the form code much simpler —
it works with flat Python dicts rather than deeply nested OSCAL structures.

### 10.2 UUIDs

OSCAL requires a UUID on every significant object (the whole file, each
component, each information type, each implemented requirement, etc.).
The toolkit auto-generates UUIDs using `uuid.uuid4()` so the user never
has to manage them. Once generated, a UUID is preserved across edits so
that the same document remains consistently identifiable.

### 10.3 Back-matter for profile provenance

When saving an SSP, the toolkit records the loaded profile's title,
version, and filename inside the SSP's `back-matter` section. The
`import-profile.href` is then set to `#<uuid>` pointing at that
back-matter entry. This means the SSP is self-documenting — anyone
reading the file can see exactly which profile version was used, without
needing the profile file to be present.

### 10.4 The `set` type for profile IDs

Profile IDs are stored as a Python `set` rather than a list:

```python
profile_ids = set()   # not []
```

The `in` operator on a set is O(1) — it takes the same time to check
membership regardless of the set's size. On a list it is O(n) — slower
as the list grows. Since the catalog filter checks every control against
the profile IDs, this optimisation matters when there are 1,000+ controls.

### 10.5 Flat control list

The OSCAL catalog is a deeply nested tree. `collect_controls()` flattens
it into a single list at load time. This makes filtering, searching, and
displaying controls much simpler — the GUI never needs to walk a tree.
The breadcrumb path (`ctrl["path"]`) preserves the original hierarchy
context for display purposes.

---

## 11. Potential Future Enhancements

| Feature | Where it would go |
|---|---|
| Stage 2 SSP control responses (click a control, write a response) | `ssp_tab.py` — add Section 7 matching ComponentTab's Section 7 |
| Export to PDF / HTML report | New `report_tab.py` or standalone export function in `models.py` |
| SSP ↔ Component linking (inherit responses) | `ssp_tab.py` + `models.py` — reference component file UUIDs |
| OSCAL schema validation on save | `models.py` — add `validate_oscal_document()` using jsonschema |
| Multiple catalogs / profiles open at once | `app.py` — change `self._catalog` to a list |
| Dark/light theme toggle | `app.py` — add a second COLORS dict and rebuild styles |

