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

### Update — largely superseded by the Library system (see section 5)

Most of what this feature wanted — a reusable, shareable component library separate from any one SSP, with an import path into the SSP — now exists via the Library folder (`settings.py`), Component/Capability Editor's "📚 Import from Library", and the SSP Editor's "🔄 Sync from System Folder" (see section 5 and design document §10.13/§10.15). What's still missing relative to this original proposal:
- No dedicated "standalone Component Definition" document type/tab distinct from what Component Editor already edits — the Library *is* just Component Editor pointed at `library/components/`, not a separate document format with its own metadata (title/version/remarks at the library level, `import-component-definitions` support, etc.).
- No "Load all controls from profile" skeleton-generation button.
- Capabilities-within-a-component-definition-file is already how `capability_tab.py` saves today (bundles member components in the same file) — Section 4 of this proposal is effectively done, just not as a separate optional section.

### ISM-Specific Considerations
- ISM assessment methods map to component implementation: EXAMINE (policy/documentation components), TEST (software/hardware components), INTERVIEW (process/people components)
- Australian Cyber Security Centre (ACSC) publishes hardening guides for common platforms — a pre-populated component library for Windows, Microsoft 365, and network devices aligned to ISM would be high value
- Component definitions can be versioned and shared between agencies as a common baseline

---

## 3. Multi-Catalog Support

### Background

OSCAL 1.2.2 fully supports multiple catalogs through the Profile's `imports[]` array — each entry can reference a different catalog (or another profile). This is the intended OSCAL pattern for overlay scenarios, for example:

- A US federal contractor that must satisfy both **SP 800-53** (FISMA/FedRAMP) and **SP 800-171** (CUI/CMMC)
- A DoD organisation applying an **SP 800-53 Moderate** baseline plus a **CMMC Level 2** overlay
- An organisation layering a sector-specific overlay (e.g., healthcare HIPAA controls) on top of a standard baseline

A profile with two catalog imports looks like:

```json
{
  "profile": {
    "imports": [
      {
        "href": "NIST_SP-800-53_rev5_catalog.json",
        "include-controls": [{ "with-ids": ["ac-2", "si-2", "ra-5"] }]
      },
      {
        "href": "NIST_SP800-171_rev3_catalog.json",
        "include-controls": [{ "with-ids": ["03.01.01", "03.14.02"] }]
      }
    ],
    "merge": { "combine": { "method": "merge" }, "as-is": true }
  }
}
```

### Current Limitation

The app currently treats catalog and profile as a 1:1 relationship — one catalog file loaded at a time via "Open Catalog". `load_profile()` in `models.py` already walks the full `imports[]` array and collects all control IDs correctly, but:

- The UI has a single catalog slot; only one catalog file can be loaded at a time
- Control title lookups in the SSP, Component, and Catalog Viewer tabs only resolve against the single loaded catalog
- If a profile imported from two catalogs, control IDs from the second catalog would appear in the profile's ID set but have no title to display

### What Needs to Change

#### 1 — Catalog Resolver in `models.py`

- Replace the single `load_catalog()` call with a `CatalogResolver` that holds a list of loaded catalogs
- `resolve_control(control_id)` searches all loaded catalogs and returns the matching control (title, description, parameters)
- When a profile is loaded, auto-discover referenced catalog files relative to the profile's file path — if a `href` points to a local file that exists, load it automatically without requiring the user to open it manually

#### 2 — UI: Multiple Catalog Slots or Auto-Load

Two approaches (pick one):

**Option A — Auto-load from profile** (preferred): When the user opens a profile, the app resolves all `imports[].href` values relative to the profile file. Any that point to local JSON files are loaded automatically into the resolver. The info panel shows a list of all loaded catalogs (not just one). No extra UI controls needed.

**Option B — Manual multi-catalog**: Add an "Add Catalog…" button that appends to a catalog list. The info panel shows a scrollable list of loaded catalogs with individual remove buttons.

#### 2b — "Data Sources" tab — ✅ Done (single catalog/profile, Library-backed)

`data_sources_tab.py` is no longer a placeholder: it browses the configured Library's `catalogs/`/`profiles/` subfolders, loads a selected file, falls through to a normal file dialog via "Browse Elsewhere" for anything outside the library, and shows/clears the currently active catalog/profile. The toolbar's "Open Catalog"/"Open Profile"/"Clear Profile" buttons were removed from `app.py._build_toolbar()` — this tab is now the only way to do those things. See design document §10.14.

**What this did NOT do — still open:** the app still only holds **one** active catalog and **one** active profile at a time (`self._catalog`/`self._profile` in `app.py`), same as before. This tab makes picking *which* single catalog/profile to load easier and more discoverable, but doesn't implement true multi-catalog support (Option B below). The open questions below about multiple simultaneously-loaded catalogs are still unresolved:
- If multiple catalogs are loaded with no profile, how does the Catalog Viewer disambiguate controls that happen to share an ID across catalogs? (See namespace note in #4 below.)
- Does every other tab (Component Editor, SSP Editor, etc.) need to let the user pick *which* loaded catalog a component's controls come from, or is the profile still the sole source of truth for control resolution?
- Should removing a catalog warn the user if components/SSPs currently reference controls from it?

#### 3 — Profile Editor Integration

The Profile Editor (Feature 1) should support adding multiple `imports` entries — each with its own catalog href and control selection. The merge strategy (`as-is` vs `combine`) should be configurable when more than one import is present.

#### 4 — Control ID Namespace Awareness

SP 800-53 uses IDs like `ac-2`, `si-2`; SP 800-171 uses `03.01.01`; ISM uses `ism-1490`. The app should handle these without collision. Since each import in a profile references a specific catalog, the resolver can use `(catalog_href, control_id)` as the lookup key to avoid ambiguity if two catalogs ever share an ID.

### Example Data to Create

Once multi-catalog support is implemented, create an example overlay profile in `example-data-nist/`:

- `profile_SP800-53-Moderate-plus-SP800-171-overlay.json` — imports from both NIST catalogs, selects Moderate baseline from SP 800-53 plus the full SP 800-171 control set, demonstrating a dual-framework SSP baseline

---

## 4. Data Flow Mapping & Diagram Feature

### Background

The SSP schema's `system-characteristics.data-flow` object only carries a free-text `description` plus a `diagrams[]` array of externally-linked diagram files (`uuid`, `caption`, `link`, `description`) — see `oscal_ssp_schema.json`. OSCAL has no schema object anywhere that models a structured graph of "component A sends information type X to component B." An earlier iteration of the SSP Editor bolted a `component_flows` concept onto each Information Type (Section 5) — encoded as generic `props` triplets tagged `class="data-flow"` — and used it to auto-generate a draw.io export. This was removed (see commit removing `_export_data_flow_drawio` and `component_flows` from `models.py`/`ssp_tab.py`) because Information Types is not the OSCAL-correct home for flow/topology data, and smuggling structured data through generic `props` made the encoding fragile and non-obvious to round-trip.

### Purpose

Reintroduce data-flow mapping as its own dedicated feature — not attached to Information Types — that helps users author the narrative `data-flow.description` field and produce a real network/data-flow diagram, without inventing non-standard OSCAL fields.

### Status: Input UX done, diagram export still to do

**Done (see design doc §10.12 for the storage decision):** SSP Section 4 now has a "Data Flow Links" table directly under the Data Flow description textbox — Add/Edit/Remove a link between two of the SSP's own components (Section 8), each with a protocol (shared `COMMON_PROTOCOLS` list from `component_tab.py`), port, transport (TCP/UDP), and direction (outbound/inbound/bidirectional). Stored as OSCAL `data-flow.props[]`, grouped by a shared `group` UUID per flow and namespaced (`ns: https://oscal-user-toolkit/ns/data-flow-link`) — a schema-valid, order-independent encoding using the `property` object's documented `group` field, unlike the removed Information-Types encoding. `data-flow.description` is auto-drafted from the flow links when the user leaves it blank, so the document stays meaningful to any plain OSCAL consumer.

**Still to do — the diagram export:**
- A "📊 Export Data Flow Diagram" action (draw.io `.drawio`) generated from the new `data_flow_links` table — reuse the bipartite/graph-building helpers from the removed `_export_data_flow_drawio` (component boxes, `TYPE_STYLES` colours, arrow direction per flow direction), but sourced from `ssp["data_flow_links"]` instead of Information Types' `component_flows`.
- Link the generated `.drawio` file into `data-flow.diagrams[]` automatically (the same way manually-added diagrams already work via `_build_diagram_section`), so the exported diagram shows up in the existing Data Flow Diagrams list rather than being a one-off file the user has to separately attach.
- Consider extending the same flow-link concept to Network Architecture (Section 4), which has the identical "no structured schema, diagrams + description only" shape — could reuse the same table/dialog pattern with a topology-flavoured field set (e.g. adding a "link type" instead of protocol/port).

---

## 5. Component & Capability Library — ✅ Done

### What was built

A large organisation's shared, reusable components/capabilities now live in a **Library** folder (`library/{catalogs,profiles,components,capabilities}/`), separate from any one system's own workspace folder — see design document §10.13–§10.16 for the full design history, and `user_stories.md` US-12/US-13 for the driving use case.

- **Library path**: configured once via the "📚 Library Folder" toolbar button, persisted in `settings.json` (inside the `oscal_user_toolkit/` package folder, `.gitignore`d), defaulting to the repo's own `library/` folder if never changed.
- **Data Sources tab**: browses the Library's `catalogs/`/`profiles/` subfolders and is now the only way to open/clear the active catalog/profile (replaced the old toolbar buttons).
- **Component/Capability Editor — "📚 Import from Library"**: copies a chosen library file into the current system's folder (the folder containing the active workspace manifest) as an independent, editable copy — never mutates the library source, and never overwrites an already-imported local copy.
- **SSP Editor — "🔄 Sync from System Folder" (Section 8)**: reads every file in the current system's `components/`/`capabilities/` folders and imports it into the SSP, including auto-populated Section 9 control responses and Capabilities Used entries.
- **AP/POA&M — read-only Components/Capabilities panes**: sourced from the referenced SSP file, so an auditor can see what's in the system without needing write access to it.

### Known remaining gaps

- Still only one active catalog/profile at a time (see section 3's still-open multi-catalog questions above — the Library made *picking* a catalog/profile easier, it didn't add multi-catalog support).
- No dedicated standalone Component/Capability Definition document type — see the note at the end of section 2.
- No UI-level indicator in Component/Capability Editor showing whether the currently-loaded file came from the Library vs. a system folder vs. neither — a user could plausibly edit and re-save a Library master file directly (via plain "Open File(s)"/"Save") without realising it's shared, since nothing currently warns them.

---

## Implementation Priority

| Feature | Priority | Effort | Notes |
|---|---|---|---|
| Authorization Dashboard | ✅ Done | Low | Implemented — reads from open document tabs |
| Component & Capability Library | ✅ Done | — | Library folder, Import from Library, Sync from System Folder, Data Sources tab; see section 5 |
| Profile Editor | High | High | Most impactful missing editor; every SSP needs a profile |
| Component Definition Editor | Medium | Medium | Largely superseded by the Library system; remaining gap is a standalone document type — see section 2's update note |
| Multi-Catalog Support | Medium | Medium | OSCAL schema already supports it; app needs CatalogResolver + UI update |
| Data Flow Mapping & Diagram Feature | Medium | Medium | Input UX (Data Flow Links table) done; diagram export still to do — see section 4 |
