# OSCAL User Toolkit — Feature Todo List

---

## 1. Profile Editor

### Purpose
Allow users to create and edit OSCAL 1.2.2 `profile` documents within the application. Currently the app can load a profile as a filter over the catalog, but profiles can only be created or modified by hand-editing JSON. Every SSP depends on a profile to define the applicable control baseline, so this is the most significant missing editor.

### OSCAL 1.2.2 Structure
A profile document has the following top-level structure:

```json
{
  "profile": {
    "uuid": "...",
    "metadata": { "title", "last-modified", "version", "oscal-version" },
    "imports": [
      {
        "href": "path/to/catalog.json",
        "include-controls": [{ "with-ids": ["ism-1490", "ism-1486", ...] }]
      }
    ],
    "merge": { "combine": { "method": "merge" }, "as-is": true },
    "modify": {
      "set-parameters": [...],
      "alters": [...]
    }
  }
}
```

Key fields:
- **`imports[]`** — One or more source catalogs (or other profiles) to draw controls from. Each import can use `include-all`, `include-controls` (with-ids list), or `exclude-controls`.
- **`merge`** — Controls how controls from multiple imports are combined. `as-is: true` preserves the source catalog structure.
- **`modify.set-parameters`** — Overrides parameter values from the source catalog.
- **`modify.alters`** — Adds, removes, or modifies control parts (guidance, statements) from the source.

### Sections to Implement

#### Section 1 — Metadata
- Profile Title (required)
- Version
- SSP Reference (what system this profile is for — optional, informational)
- Remarks

#### Section 2 — Source Catalog
- Browse button to select source catalog JSON file
- Displays catalog title, version, and control count once loaded
- Stores href (relative path, same pattern as SSP/AP/AR)

#### Section 3 — Control Selection
- Radio: "Include all controls" / "Select specific controls"
- If specific: searchable tree/list of controls from the loaded catalog
  - Show control ID + title per row
  - Multi-select checkboxes (or Ctrl+click Treeview)
  - "Select all in family" shortcut buttons for ISM control families
  - Display count of selected controls
- If all: show total count from catalog

#### Section 4 — Parameter Overrides (optional)
- Table: Parameter ID | Value | Remarks
- Add/Edit/Remove CRUD
- Parameters sourced from selected controls in the catalog

#### Section 5 — Control Alterations (optional/advanced)
- Table: Control ID | Alteration Type (add/remove/replace) | Target Part | Content
- Allows organisations to add implementation guidance or remove inapplicable control parts
- Lower priority — can be phase 2

### Serialisation Notes
- `build_oscal_profile(profile, oscal_version, save_path)` — mirrors the pattern of `build_oscal_poam` etc.
- `parse_profile_file(data)` — reads back into internal dict
- `empty_profile()` — blank working dict
- Relative href computation for source catalog — same `Path.relative_to()` pattern used by other builders

### Integration
- Profile Editor tab added to notebook between Catalog Viewer and Component Editor
- When a profile is saved, offer to reload it as the active profile in the toolbar (replacing the current "Open Profile" workflow)
- The SSP tab's "Change Profile…" button should also be able to open/create a profile via the Profile Editor tab

### ISM-Specific Considerations
- ISM control IDs follow the pattern `ism-NNNN` (4-digit numeric suffix)
- The ISM catalog has control families defined via `group` elements — the Profile Editor should group controls by family in the selection tree
- Common ISM baselines: Essential Eight, Protected baseline, Official baseline — could offer preset templates that pre-select common control sets

---

## 2. Component Definition Editor (Standalone)

### Purpose
Create and edit standalone OSCAL 1.2.2 `component-definition` documents. These differ from the Component Editor within the SSP tab: a component-definition document is a reusable, shareable library of pre-approved component configurations that can be imported into multiple SSPs across an organisation or across organisations.

Examples:
- "Windows 11 Hardened Workstation — ISM baseline"
- "Microsoft 365 Tenant — Exchange Online and SharePoint"
- "Cisco Catalyst Switch — Network device hardening"
- "VMware vSphere 8 — Hypervisor platform"

### OSCAL 1.2.2 Structure

```json
{
  "component-definition": {
    "uuid": "...",
    "metadata": { "title", "last-modified", "version", "oscal-version" },
    "import-component-definitions": [{ "href": "..." }],
    "components": [
      {
        "uuid": "...",
        "type": "software|hardware|service|policy|process|plan|guidance|standard|validation",
        "title": "...",
        "description": "...",
        "purpose": "...",
        "responsible-roles": [...],
        "protocols": [...],
        "control-implementations": [
          {
            "uuid": "...",
            "source": "profile-href",
            "description": "...",
            "implemented-requirements": [
              {
                "uuid": "...",
                "control-id": "ism-1490",
                "description": "...",
                "set-parameters": [...],
                "responsible-roles": [...],
                "statements": [...]
              }
            ]
          }
        ]
      }
    ],
    "capabilities": [...],
    "back-matter": { "resources": [...] }
  }
}
```

### Key Differences from SSP Component Tab
| SSP Component Tab | Standalone Component Definition |
|---|---|
| Components are scoped to one system | Components are reusable across systems |
| Control implementations reference the SSP's profile | Control implementations reference any profile/catalog |
| Cannot be exported independently | Saved as a standalone portable document |
| No import-component-definitions support | Can import and extend other component libraries |

### Sections to Implement

#### Section 1 — Document Metadata
- Title, Version, Remarks
- Source Profile reference (href to the profile that control implementations are drawn from)

#### Section 2 — Components List
- Treeview: Type | Title | Control Coverage (count)
- Add/Edit/Remove
- Component dialog:
  - Type (combo: software/hardware/service/policy/process/plan/guidance/standard/validation)
  - Title, Description, Purpose
  - Version, Vendor (as props)
  - Responsible Roles (table: role-id + party description)

#### Section 3 — Control Implementations (per component)
- For each selected component: table of implemented requirements
- Implemented Requirement dialog:
  - Control ID (with lookup from loaded profile/catalog)
  - Description of how this component implements the control
  - Implementation Status (implemented/partial/planned/alternative/not-applicable)
  - Remarks
- "Load all controls from profile" button — creates a skeleton implementation entry for each control in the active profile

#### Section 4 — Capabilities (optional/advanced)
- Capabilities group components into higher-level functional units
- Table: Capability Name | Description | Incorporated Components
- Lower priority — phase 2

### Serialisation Notes
- `build_oscal_component_definition(doc, oscal_version, save_path)`
- `parse_component_definition_file(data)`
- `empty_component_definition()`
- On open: offer to merge components into the current SSP Component tab (import workflow)

### Integration
- New tab: "📦  Component Library" added after Component Editor
- SSP Component tab gains an "Import from Component Definition…" button that opens a component-definition file and lets the user select components to pull into the SSP
- When saving an SSP, offer to also export its components as a component-definition document

### ISM-Specific Considerations
- ISM assessment methods map to component implementation: EXAMINE (policy/documentation components), TEST (software/hardware components), INTERVIEW (process/people components)
- Australian Cyber Security Centre (ACSC) publishes hardening guides for common platforms — a pre-populated component library for Windows, Microsoft 365, and network devices aligned to ISM would be high value
- Component definitions can be versioned and shared between agencies as a common baseline

---

## Implementation Priority

| Feature | Priority | Effort | Notes |
|---|---|---|---|
| Authorization Dashboard | ✅ Done | Low | Implemented — reads from open document tabs |
| Profile Editor | High | High | Most impactful missing editor; every SSP needs a profile |
| Component Definition Editor | Medium | Medium | High value for multi-system organisations |
