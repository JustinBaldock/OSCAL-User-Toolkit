# OSCAL User Toolkit — Feature Todo List

> This file tracks work that is **not yet done**. Completed features are documented in [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) instead (see its §10 "Key Design Decisions" and §11 "Example Component Library") — once something ships, it moves out of this file and into that one, so this list doesn't accumulate stale "✅ Done" history.

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

## 2. Standalone Component Definition document type

The Library system (see design document §10.13–§10.20) already covers most of what a "reusable, shareable component library separate from any one SSP" originally needed — a shared folder, an import path into any SSP, dedicated Library-mode editors. What it still doesn't provide, relative to a true standalone `component-definition` document type:

- **No document-level metadata distinct from the Library itself** — no `import-component-definitions` support, no title/version/remarks that live at the "collection of components" level rather than per-component. The Library *is* just `ComponentTab` pointed at `library/components/`, one component per file — not a separate document format that can bundle many components with its own metadata.
- **No "Load all controls from profile" skeleton-generation button** — a button that creates a blank implemented-requirement entry for every control in the currently active profile, so a user fills in descriptions rather than adding requirements one at a time.

(Capabilities bundling multiple components into one file — originally proposed as a "Section 4" of this feature — is already how `capability_tab.py` saves today, so that part doesn't need separate work.)

### ISM-Specific Considerations
- ISM assessment methods map to component implementation: EXAMINE (policy/documentation components), TEST (software/hardware components), INTERVIEW (process/people components)

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

The app still only holds **one** active catalog and **one** active profile at a time (`self._catalog`/`self._profile` in `app.py`). A `CatalogResolver` already exists (design document §10.17) and auto-loads every catalog a profile's `imports[]` references.

**Stages 2–3 are done, but scoped to the Library Component/Capability Editors only** (see design document §10.24): when a loaded profile's `imports[]` pulls in more than one catalog, both editors' control lists combine every loaded catalog (tagged `[source_filename]` per control), and `build_component_oscal_entry()`/`CapabilityTab._build_oscal_document()` group responses by distinct source into one `control-implementations` block per catalog — confirmed schema-valid directly against `oscal_component_schema.json` (the array has no max, each entry has its own required `source`). **Not yet done**: the System Overview Component/Capability Editors still show a single catalog's controls (deliberately deferred — see §10.24 for why); the Catalog Viewer and SSP Editor are also untouched by this.

### What Still Needs to Change

#### Profile Editor Integration

The Profile Editor (§1 above) should support adding multiple `imports` entries — each with its own catalog href and control selection. The merge strategy (`as-is` vs `combine`) should be configurable when more than one import is present.

#### Control ID Namespace Awareness

SP 800-53 uses IDs like `ac-2`, `si-2`; SP 800-171 uses `03.01.01`; ISM uses `ism-1490`. The app should handle these without collision. Since each import in a profile references a specific catalog, the resolver can use `(catalog_href, control_id)` as the lookup key to avoid ambiguity if two catalogs ever share an ID.

### Open questions
- If multiple catalogs are loaded with no profile, how does the Catalog Viewer disambiguate controls that happen to share an ID across catalogs?
- Does every other tab (Component Editor, SSP Editor, etc.) need to let the user pick *which* loaded catalog a component's controls come from, or is the profile still the sole source of truth for control resolution?
- Should removing a catalog warn the user if components/SSPs currently reference controls from it?

### Example Data to Create

Once multi-catalog support is implemented, create an example overlay profile in `systems/example-data-nist/`:

- `profile_SP800-53-Moderate-plus-SP800-171-overlay.json` — imports from both NIST catalogs, selects Moderate baseline from SP 800-53 plus the full SP 800-171 control set, demonstrating a dual-framework SSP baseline

---

## 4. Data Flow Diagram Export

The SSP schema's `system-characteristics.data-flow` object only carries a free-text `description` plus a `diagrams[]` array of externally-linked diagram files — OSCAL has no schema object anywhere that models a structured graph of "component A sends information type X to component B." SSP Section 4 already has a "Data Flow Links" table (Add/Edit/Remove a link between two of the SSP's own components, with protocol/port/transport/direction — see design document §10.12 for the storage decision) that captures this structured data in a schema-valid way. What's still missing is turning it into a diagram:

- A "📊 Export Data Flow Diagram" action (draw.io `.drawio`) generated from the `data_flow_links` table — component boxes, direction-coded arrows, colour-coding by component type (the same visual language the existing System→Capability→Component export already uses).
- Link the generated `.drawio` file into `data-flow.diagrams[]` automatically (the same way manually-added diagrams already work), so the exported diagram shows up in the existing Data Flow Diagrams list rather than being a one-off file the user has to separately attach.
- Consider extending the same flow-link concept to Network Architecture (Section 4), which has the identical "no structured schema, diagrams + description only" shape — could reuse the same table/dialog pattern with a topology-flavoured field set (e.g. a "link type" field instead of protocol/port).

---

## 5. Capability version / revision history

Components already have their own `file_uuid`/`version`/`revisions[]` and a "Version & Revision History" UI (design document §10.21) — `CapabilityTab` still uses shared, tab-level `_file_version` state and has no revision history at all. Same design, applied to capabilities: per-capability `file_uuid`/`version`/`revisions[]`, a "Save New Version" action, and the version/UUID display card in the capability form.

---

## 6. `COMPONENT_TYPES` dropdown doesn't offer the exact `process-procedure` schema term

`component_tab.py`'s `COMPONENT_TYPES` list splits the schema's single `process-procedure` type into two separate dropdown options, `"process"` and `"procedure"` — neither is the exact schema term (though all three, being free-form-string-compatible, are schema-valid, so nothing currently saved is actually broken). A user picking a brand-new component's type from the dropdown just can't select the literal `process-procedure` term today. Fix: replace the two split options with the single correct term (or offer all three).

---

## 7. Remaining usability gaps

From the `usability_review.md` pass (see design document §10.22 for what was already done):

- **No undo/redo** — would need a real change-tracking layer across every tab's edit operations. A separate, larger project, not a quick addition.
- **No batch operations / multi-select** — every `Treeview` in the app uses `selectmode="browse"` (one row at a time); no bulk-delete or bulk-edit workflow exists anywhere.
- **No in-app tutorial/walkthrough for new users** — the Workspace tab's existing per-tab guidance cards cover some of this ground already, but there's no guided first-run flow.
- **`GREEN`/`TEAL` text colour is marginally under WCAG's normal-text contrast threshold in light mode only** (3.1–3.9:1, vs. the 4.5:1 normal-text target — still comfortably above the 3:1 large/bold-text threshold). Left alone deliberately: both are load-bearing brand/identity colours used consistently across many components, so changing a hue for a marginal contrast gain is a visual-identity decision, not a quick accessibility fix.

---

## 8. Enable GitHub code scanning (CodeQL)

Turn on GitHub's default CodeQL code scanning setup for this repo. Free for public repos, and complementary to the existing CI (`.github/workflows/ci.yml`) rather than redundant: Ruff catches style/correctness issues, CodeQL does deeper security-focused taint analysis (path traversal, unsafe deserialization, etc.) — relevant here since the app's whole job is parsing JSON files a user picked off disk, which `SECURE_CODING.md` already treats as untrusted input.

Use GitHub's **"Default" setup** (one click, auto-configured) rather than the "Advanced" custom-workflow option — this is a straightforward Python codebase with no unusual build steps. Expect some initial noise on the first scan (findings to triage — accept as safe, or fix — not all necessarily real bugs).

---

## 9. Two bugs found while writing SSP/AP/AR/POA&M round-trip tests (`tests/test_roundtrip.py`)

Found by building real fixtures and reading the actual output before writing assertions (see design document §10.28) — not yet fixed, deliberately, since fixing them wasn't the point of that task:

- **`build_oscal_ar()` drops an AR observation's `assessed_by` value on save.** `build_oscal_poam()` writes this to an `assessed-by` prop for the identical internal field name; `build_oscal_ar()` never does, even though `parse_ar_file()` reads it back via the same shared `_parse_oscal_observation()` helper both document types use. Low real-world impact today — `ar_tab.py`'s own UI never collects or displays `assessed_by` for AR observations — but a file from another OSCAL tool with that prop set would silently lose it on the first save through this app. Fix: add the same `if o.get("assessed_by"): entry["props"] = [...]` block `build_oscal_poam()` already has, to `build_oscal_ar()`'s observation loop.
- **README.md and the design document's own feature list overstate AR's risk fields.** Both claim AR risks carry "CIA impact characterizations... stored as OSCAL facets" — that's only true for POA&M risks. `build_oscal_ar()`/`parse_ar_file()` have no CIA handling for risks at all, and `ar_tab.py` never collects `cia_c`/`cia_i`/`cia_a` from the user. Either fix the docs to stop claiming this for AR, or (bigger) actually add CIA characterization support to AR risks to match POA&M's.

---

## Implementation Priority

| Feature | Priority | Effort | Notes |
|---|---|---|---|
| Profile Editor | High | High | Most impactful missing editor; every SSP needs a profile — see §1 |
| Multi-Catalog Support — extend to System Overview editors | Low | Medium | Done for the Library Component/Capability Editors; System Overview's own editors, the Catalog Viewer, and the SSP Editor still show a single catalog — see §3 |
| Data Flow Diagram Export | Medium | Medium | Input UX done; only the `.drawio` export itself remains — see §4 |
| Standalone Component Definition document type | Low | Medium | Largely superseded by the Library system; remaining gap is a distinct document type + "load all controls from profile" — see §2 |
| Capability version/revision history | Low | Low | Same design as components, just not yet applied to `CapabilityTab` — see §5 |
| `COMPONENT_TYPES` dropdown fix | Low | Low | Cosmetic — nothing currently saved is broken — see §6 |
| Batch operations / multi-select | Low | High | No existing Treeview supports multi-select — see §7 |
| Undo/redo | Low | High | Needs a real change-tracking layer — see §7 |
| Enable GitHub code scanning (CodeQL) | Low | Low | One-click "Default" setup, free for public repos — see §8 |
