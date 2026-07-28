# OSCAL User Toolkit — Release Notes

> ⚠️ **Pre-production**: this is an early, actively-developed project. Interfaces, file formats, and internal data structures may still change between versions. Not yet recommended for production authorisation packages without independent review of generated OSCAL output.

---

## v0.5 (Pre-Production Release)

### What this is

A quality-and-correctness-focused release: v0.5 adds no new document type or major workflow, but it's the first release with automated CI (lint, unit tests, a compliance-grade SBOM with drift detection, and CodeQL security scanning), fixes a real duplicate-title bug that led to a batch of Library components being extracted from capability bundles into their own files, fixes a genuine app-wide memory leak, and closes two real bugs the new test coverage surfaced (an AR field that silently failed to save, and a documented-but-missing CIA characterization feature for AR risks). It also adds multi-catalog support to the Library editors, several SSP Editor usability/coverage improvements, and a batch of diagram-workflow fixes.

Full feature documentation is in [README.md](README.md). See [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) §10.24–§10.36 for the technical design history.

### Highlights since v0.4

#### Automated CI — lint, tests, SBOM drift check, CodeQL, Dependabot (new)

The project had no automated verification before this release — every fix was checked by hand. A GitHub Actions workflow (`.github/workflows/ci.yml`) now runs on every push/PR to `main`:

- **Lint** (Ruff) and **test** (pytest) jobs — 42 tests total, covering `models.py`'s data helpers, `CatalogResolver`, multi-catalog `control-implementations` grouping, VLAN/data-flow-link prop round-trips, full save/load round-trips for SSP/AP/AR/POA&M, `settings.scan_oscal_versions()`, and the mousewheel-leak fix below.
- **SBOM drift check** — `sbom.json`, a CycloneDX 1.6 Software Bill of Materials for `requirements.txt`'s runtime dependencies (direct and transitive, exact resolved versions), regenerated fresh on every push and failing the build if it doesn't match what's committed. Both `requirements.txt`'s two direct dependencies and the SBOM generation venv's own `pip` version are now pinned exactly, closing a real source of false-positive drift (an unpinned dependency or an unpinned ambient `pip` version resolving differently across machines/CI runners with no actual code change).
- **CodeQL** security scanning and **Dependabot** (dependency graph, alerts, security updates) both enabled via GitHub's repo settings.

#### Library — duplicate-title bug fixed, components extracted from capability bundles (fix)

Reported directly by the designer using the app: the Library Component Editor showed a duplicate "Backup and Recovery Policy" row. Root cause: the Library Capability Editor was importing its *own* bundled copy of each member component into the shared Library Component list on top of the real file already loaded from `library/components/` — normally harmless, except two of those bundled copies had drifted from the real file (different UUID, different content) and showed up as visually-identical duplicate rows. Fixed by no longer wiring bundle-importing for the Library Capability Editor specifically (System Overview's editors are unaffected — they still need it).

Verifying the fix surfaced a much bigger latent gap: **18 components across 6 capabilities existed only as bundled copies inside a capability file, never as their own standalone `library/components/` file** — every member of Email Security, Endpoint Protection, Privileged Access Management, and Security Monitoring and Logging, among others. All 18 were extracted into real, independently-reusable library files, taking the Library from 102 to 121 components. 3 more new `process-procedure` components (Data Breach Notification, Disaster Recovery Testing, Vulnerability Scan Response) were added separately, for **124 components total** (capabilities unchanged at 11).

#### Multi-catalog components — Library editors only (new)

The Library Component and Capability Editors' control lists now combine every catalog a loaded profile imports (e.g. ISM + NIST), tagging each control with its source catalog. A new per-response source record means a single component can hold correctly-sourced responses against controls from more than one catalog at once — `build_component_oscal_entry()` groups them into one `control-implementations` block per catalog, confirmed schema-valid. Deliberately scoped to the Library editors only, not System Overview's per-system editors, which stay tied to one catalog/profile as before. 6 example components (SSH, Privacy Policy, LMS, Drupal, Django, AWS) were converted to carry real ISM + NIST SP 800-53 rev5 coverage as a demonstration.

#### Two real bugs found by new test coverage, both fixed (fix)

Building round-trip tests for SSP/AP/AR/POA&M surfaced two genuine, previously-undiscovered bugs, fixed immediately after:

- **AR observations silently dropped their `assessed_by` value on save** — the POA&M side wrote this field correctly, the AR side never did, even though both read it back the same way. Low real-world impact (the AR UI never actually collected this field), but a hand-crafted or another-tool's AR file with it set would have lost it silently. Fixed.
- **AR risks never got the CIA (Confidentiality/Integrity/Availability) impact characterization that README/design docs claimed they had** — that feature only ever existed for POA&M risks. Rather than just correcting the documentation, added the real feature: AR's risk dialog gained the same three CIA impact dropdowns POA&M already has, matching its exact encoding — so "Generate POA&M from Findings" now carries a risk's CIA rating through automatically instead of silently losing it.

#### Real memory leak fixed, plus two missing scroll guards (fix)

An external code review flagged four findings; investigating them directly (rather than trusting the description) found the real bug was substantially worse than described: every theme toggle (dark/light) leaked one entire previous tab instance — including every loaded SSP, component, and capability it held — for the life of the process, because rebuilding a tab's scrollable canvas re-registered a mouse-wheel binding that tkinter never releases. Fixed with a new shared dispatcher (`tab_utils.bind_mousewheel()`) that registers the underlying binding exactly once per process; confirmed fixed with a `weakref`-based test (20 theme toggles, 1 survivor instead of 20). Also fixed two tabs (Dashboard, Workspace) missing the same "don't scroll when not the active tab" guard every other tab already had.

#### SSP Editor — AusGov-aligned dropdown options (new)

OSCAL's Security Sensitivity Level and CIA impact fields are free text in the schema, not a fixed enum, so these add options rather than replacing existing ones:

- **Security Sensitivity Level** (Section 2) gained the ISM classifications (NC, OS, PROTECTED, SECRET, TOP SECRET) alongside the existing FIPS-199 options.
- **Confidentiality/Integrity/Availability impact** dropdowns (Section 2's top-level fields and each Information Type's per-item fields) gained the 7-point AusGov Business Impact Level scale alongside FIPS-199, via one shared option list so both places stay in sync.

#### All Systems tab — Controls Required / Controls Applied columns (new)

Two new columns: **Controls Required** (the system's profile selection size, or the full catalog if no profile narrows it) and **Controls Applied** (how many controls actually have a recorded response in the SSP), positioned right after System.

#### Diagram workflow fixes (fix/new)

- **Export to PNG**, alongside the existing draw.io export — shells out to the draw.io desktop app's own export CLI; shows a clear message (not a raw error) if draw.io isn't installed.
- **Browse button** added to the diagram dialog's Link/Path field (all four diagram tables) — previously plain-text-only, so attaching an existing file meant typing the exact path by hand.
- **Fixed a real bug**: the Capability and Component Map's "Add Diagram" always jumped straight into generating a brand-new export, with no way to attach an existing PNG or `.drawio` file. Now asks first — generate new, or attach existing.
- **Capability and Component Map diagrams** are now tracked in their own table (Section 8), matching the existing Auth Boundary/Network Architecture/Data Flow diagram tables, rather than the export button producing a file with no record of it in the SSP.

#### UI polish — resizable hint boxes (fix)

Every hint/description label across the SSP Editor's main form (Sections 1–12) now reflows to the window's actual current width via a shared `_hint()` helper, replacing hand-wrapped line breaks that either clipped or overflowed when the window was resized. Matches the technique already proven on Section 10's protocol hint.

#### Housekeeping

- Renamed the bundled example system folders to a consistent numbered scheme (`example-data-ism` → `example-01-ism`, `example-data-nist` → `example-03-nist`).
- Fixed the `process-procedure` component-type gap (`todo.md`): the schema's real single value had been incorrectly split into two non-schema `process`/`procedure` options in two separate dropdowns; both fixed, plus a dead unused duplicate constant removed.
- Extracted the OSCAL-version-scanner and ttk-styling logic out of `app.py` into `settings.py`/`tab_utils.py` (now independently unit-testable), trimming `app.py` from 1,857 to 1,766 lines.
- Merged `usability_review.md` and `usability_review_2.md` into one file, organized by the original 10-heuristic structure.
- Refreshed the bundled example ISM system's data (`ssp_ERN.json`, its Word export, and its system diagram).

### Requirements

- Python 3.9+
- `jsonschema==4.26.0` (schema validation) and `python-docx==1.2.0` (Word export), now pinned exactly — see [README.md#requirements](README.md#requirements) for installation
- Optional: the draw.io desktop app, only if you want the new **Export to PNG** diagram button — every other feature works without it

### Known limitations

- Capability version/revision history is still not implemented (components only — `todo.md` §1).
- No undo/redo, no batch operations/multi-select, no in-app tutorial (`todo.md` §2) — unchanged from v0.4.
- Multi-catalog support is scoped to the Library Component/Capability Editors only — the Catalog Viewer, SSP Editor, and System Overview's per-system editors still work against one catalog/profile at a time (`todo.md` §5).
- Control ID collisions across two loaded catalogs are resolved by keeping whichever was seen first — not expected to matter in practice (ISM's and NIST's ID formats don't overlap), but not solved generally.
- No auto-generated Data Flow diagram from the Section 4 Data Flow Links table yet — diagrams for Data Flow/Network Architecture are still manually attached (`todo.md` §6).
- Single catalog/profile pair per session; no Profile Editor or standalone Component/Capability Definition document type yet.
- Generated OSCAL output should be independently reviewed before use in a real authorisation package.

### Upgrading from v0.4

- No breaking changes to file formats, the workspace manifest, or the Library folder layout. Existing single-catalog components/capabilities save and load byte-for-byte the same as before — the new multi-catalog source tracking only activates when more than one catalog is actually loaded.
- If you have a local copy of the renamed example folders (`example-data-ism`/`example-data-nist`) referenced in an old workspace manifest, re-point it at the new `example-01-ism`/`example-03-nist` paths (or just re-save the workspace once opened, which records the new path).
- Re-run `pip install -r requirements.txt` to pick up the newly-pinned `jsonschema`/`python-docx` versions.

---

## v0.4 (Pre-Production Release)

### What this is

A usability and polish-focused release: v0.4 doesn't add a new document type or major workflow, it rounds out the Document Metadata work v0.3 started (Creator/Organisation, Document Links, and a schema-version upgrade tool), closes gaps found by a second Nielsen heuristics pass, and fixes a batch of visual inconsistencies across the app's buttons.

Full feature documentation is in [README.md](README.md). See [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) §10.23 for the technical design history, and [usability_review_2.md](usability_review_2.md) for the full second heuristics pass and its priority-ordered fixes.

### Highlights since v0.3

#### Document Metadata — Creator/Organisation, Document Links, and OSCAL version upgrade (new)

- Both the Component and Capability Editors' Document Metadata card gained a **Creator/Organisation** field and a **Document Links** table (rel/href/text describing the file itself — e.g. a vendor's "latest version" URL — separate from the component's own Links section). The card is now collapsible.
- **🔼 Upgrade OSCAL Version**: re-validates the current component/capability against any bundled OSCAL schema version — independent of whichever version the toolbar currently has selected — and re-stamps `metadata.oscal-version` once you confirm. This is explicitly a re-validate-and-relabel action, not a content migration; the app has no schema-migration logic for any version, and the dialog says so.
- If the target version's schema can't be found on disk, the dialog now warns and asks for explicit confirmation before proceeding unchecked, instead of silently skipping validation (a genuine gap found by the second usability pass, below).

#### Workspace — Create New Workspace (new)

- **🆕 Create New Workspace** clears every open document plus the loaded catalog/profile to start fresh — warns first only if something currently open has unsaved changes, never unconditionally. Files already saved to disk are never affected.
- Found and fixed a real bug while building this: the SSP, Assessment Plan, Assessment Results, and POA&M editors' internal reset never cleared their own "unsaved changes" flag, so a blank-slate reset could still show a stale `*` on the tab afterward.

#### Second usability pass — `usability_review_2.md` (new)

A fresh, code-verified Nielsen heuristics pass specifically hunting for gaps in everything built since the first review, fixed in priority order:

- **Dialog keyboard support**: every dialog in the app now closes on **Escape**; the Component and Capability Editors' own dialogs also confirm on **Return**.
- **Tooltips** added to the Workspace tab's Open/Save/Create New Workspace buttons, which previously had none.
- System Overview's Capability Editor now auto-loads every capability file already in the current system's folder, matching how the Component Editor already behaved.

#### Button consistency (new)

Two rounds of fixes, prompted by direct visual inspection of the running app:

- **Text colour**: every secondary button (Cancel, Delete, Remove Selected, Create New Workspace, Browse Elsewhere, Clear Profile, and others — around 85 in total) previously used the theme's own text colour, while primary/coloured buttons used a fixed near-black colour — in dark mode this put two different text colours on adjacent buttons in the same row. Every button now uses the same fixed text colour.
- **Font weight**: all ~94 buttons using bold text switched to normal weight, for a consistent look with no unintended emphasis.

#### Library content

- 7 new example components — `aws`, `django`, `drupal`, `ilias`, `privacy`, `ssh`, and EDR (CrowdStrike Falcon) — all `software` type, taking the Library from 95 to **102 components**. Capabilities unchanged at 11.

### Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

### Known limitations

- Capability version/revision history is not yet implemented (components only — see `todo.md` §5). Capabilities now have the Document Metadata card and OSCAL version upgrade, but not the per-capability version/UUID/revision-history tracking components have.
- `component_tab.py`'s type dropdown splits the schema's single `process-procedure` value into two separate options (`process`, `procedure`); the exact schema term isn't currently selectable from the dropdown for a *new* component, though it loads and displays correctly if already saved with that value (`todo.md` §6).
- `<Return>`-to-confirm is only wired up in the Component and Capability Editors' own dialogs — the Assessment Plan, Assessment Results, and POA&M editors' dialogs close on Escape but don't yet confirm on Return.
- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md` §3).
- No Profile Editor or standalone Component/Capability Definition document type yet (`todo.md` §1–2).

---

## v0.3 (Pre-Production Release)

### What this is

A desktop application (Python/Tkinter) for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) 1.2.2 documents, purpose-built for organisations running multiple separate networks that each need their own System Security Plan. v0.3's focus is the Library itself: a dedicated Organisation tab for maintaining shared master components/capabilities without ambiguity, per-component version history, and a large expansion of the bundled example content to cover every OSCAL component type.

Full feature documentation is in [README.md](README.md). See [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) §10.20–§11 for the technical design history, and [user_stories.md](user_stories.md) US-14 for the workflow this release targets.

### Highlights since v0.2

#### Organisation tab — Library Component & Capability Editors (new)

- **⚙ Library Components** and **🔗 Library Capabilities**: dedicated editor instances locked to `library/components/`/`library/capabilities/` by construction — no Open File/Open Folder/Import dialogs, no save-location prompt. They auto-load every file in the Library on open and via **🔄 Refresh from Library**, and save straight back to it.
- **📥 Add File to Library** is the one controlled way an external file enters the Library.
- Resolves the previous "no way to tell if I'm editing the Library's master or a system's local copy" gap — since these are now separate tab instances entirely, the tab itself answers that question.
- **🌐 All Systems** now lives alongside these two editors in the Organisation tab group (moved from top-level).

#### Component version, revision, and UUID metadata (new)

- Each component now carries its own stable UUID, editable version, and revision history, using OSCAL's native `metadata.revisions[]` — not an invented field.
- A new **Version & Revision History** card (Section 1) shows the component and document UUIDs, an editable Version field, and a read-only revision history table, with hint text explaining the two available workflows.
- **📌 Save New Version** archives the current version and optional remarks into history before bumping to a new version number — distinct from a plain in-place save, which just relabels the current version.
- This replaces a previous bug: version/UUID state used to be shared across an entire editor tab rather than tracked per component, meaning every component saved from the same tab got the *same* document UUID and version — most visibly broken in the Library Component Editor, where dozens of components share one tab instance. Fixed; components only for now — capabilities don't yet have their own version history.

#### Library content — full component-type coverage (new)

The bundled example Library grew from 64 to **95 components** and from 9 to **11 capabilities**, with every OSCAL `defined-component.type` schema value now represented at least once — including `physical`, `process-procedure`, `plan`, `guidance`, and `standard`, which previously had no examples at all:

- **Physical** (new type coverage): Main Office Server Room, Remote Office Comms Room, Air Conditioning, Power Generator.
- **Hardware**: SAN Storage Array, Fibre Channel Switch, Load Balancer, Web Application Firewall.
- **Operating systems**: Windows 10/11 Workstation, Ubuntu Workstation, RHEL Workstation, Microsoft Hyper-V, Proxmox VE, Nutanix AHV.
- **Services**: DNS Server, Kubernetes, Identity Provider (Microsoft Entra ID), Privileged Access Management, Email Security Gateway, Two-Factor Authentication (Duo).
- **Software**: GitLab and Subversion (source code management), Oracle VirtualBox.
- **Policies**: Password and Credential Management, Cryptographic Key Management, Physical Security.
- **New type coverage** (one example each): `process-procedure` (Cyber Security Incident Response Procedure), `plan` (Business Continuity and Disaster Recovery Plan), `guidance` (ASD Secure Configuration and Hardening Guidance Register), `standard` (OWASP ASVS/MASVS).
- **New capabilities**: Virtualisation (VMware) and Virtualisation (Hyper-V), each bundling a hypervisor with the shared SAN Storage Array and NAS components — generated by driving the real Component/Capability Editor code paths rather than hand-written, so they're exactly what the UI itself would produce.
- Every new component's ISM control implementations use real control IDs verified directly against the bundled catalog — none invented.

#### Fixes

- Fixed a schema violation present in 29 pre-existing library component files — an invalid `remarks` field on a protocol `port-ranges` entry (the schema only allows `start`/`end`/`transport` there) — plus an empty `protocols: []` array in 6 policy components (the schema requires it be non-empty if present at all). All 95 library components now validate cleanly against `oscal_component_schema.json`.
- Fixed the Library Component/Capability Editors getting stuck showing "Catalog Required" even after a catalog was loaded elsewhere in the app — they weren't being notified of catalog/profile changes.

### Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

### Known limitations

- Capability version/revision history is not yet implemented (components only — see `todo.md` §6).
- `component_tab.py`'s type dropdown splits the schema's single `process-procedure` value into two separate options (`process`, `procedure`); the exact schema term isn't currently selectable from the dropdown for a *new* component, though it loads and displays correctly if already saved with that value (`todo.md` §7).
- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md` §3).
- No Profile Editor or standalone Component/Capability Definition document type yet (`todo.md` §1–2).
- Data Flow Links have no diagram export yet (`todo.md` §4).
- Generated OSCAL output should be independently reviewed before use in a real authorisation package.

### Upgrading from v0.2

- No breaking changes to the workspace manifest or Library folder layout — existing Library folders and workspaces continue to work unchanged.
- Existing components saved before this release have no `version`/`revisions[]` data; they'll default to version "1.0" with empty history the first time they're opened, and gain real history from that point forward.

---

## v0.2 (Pre-Production Release)

### What this is

A desktop application (Python/Tkinter) for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) 1.2.2 documents, purpose-built for organisations running multiple separate networks that each need their own System Security Plan. v0.2's headline addition is a proper **Library** system: components, capabilities, catalogs, and profiles now live in one shared, organisation-level folder, separate from any individual system's own workspace — turning "copy this firewall's control responses into every new SSP" into a two-click import instead of hand-editing JSON.

Full feature documentation is in [README.md](README.md). See [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) for the technical design history (§10.13–§10.16 cover the Library system specifically), and [user_stories.md](user_stories.md) for the workflows this release targets.

### Highlights since v0.1

#### Library system (new)

The biggest change in this release — a shared **Library** folder (`library/catalogs/`, `.../profiles/`, `.../components/`, `.../capabilities/`) that's separate from any one system's workspace:

- **📚 Library Folder** (toolbar): configure which folder is the Library once; persisted between launches, defaulting to the repo's own `library/` folder if never changed.
- **📚 Data Sources tab**: browse and load catalogs/profiles from the Library, or browse elsewhere for anything outside it. This is now the *only* way to open or clear the active catalog/profile — the old toolbar "Open Catalog"/"Open Profile"/"Clear Profile" buttons are gone.
- **📚 Import from Library** (Component/Capability Editor): copy a component or capability from the Library into the current system's own folder as an independent, editable copy — never mutates the Library source, never overwrites a local copy you've already edited.
- **🔄 Sync from System Folder** (SSP Editor, Section 8): pulls every component/capability file sitting in the current system's folder straight into the SSP, including auto-populated control responses and Capabilities Used entries. Safe to re-run any time — never duplicates.
- **Read-only Components/Capabilities visibility** (Assessment Plan, POA&M): both editors now show what the referenced SSP's system is built from, without needing write access to it.

#### SSP Editor — Network Architecture & Data Flow

- **VLANs** (Section 4): record VLAN ID (validated 1–4094), name, and description, positioned under the Network Architecture description text.
- **Data Flow Links** (Section 4): record how data moves between the SSP's own components — source, target, protocol, port, transport, direction — positioned under the Data Flow description text. Both VLANs and Data Flow Links are stored as schema-valid, order-independent grouped OSCAL `props` (not a home-grown encoding), and `data-flow.description` auto-drafts a narrative summary from the links when left blank.
- Removed an earlier, OSCAL-incorrect approach that had attached "which component sends this information type" data directly to Information Types — checking the schema directly confirmed that object has no field for it.
- **Export to Word**: table cell font reduced to 9pt for readability in wide tables; page-break-before-table and per-table landscape orientation were both tried and reverted (didn't read well in practice).
- VLANs also appear in the Word export, at the bottom of the Network Architecture section.

#### Application preferences

- **Dark/light theme** choice now persists between launches (`settings.py`).
- Assorted UX fixes: Save/Open Workspace button colours matched; app-wide sweep of unreadable button text in both themes; scrollbars and live counts added to the Capability Editor's Member Components and Component Editor's Protocols sections; Edit buttons added to Parties, Roles, and Diagram lists in the SSP Editor; Section 7b Responsible Parties remarks were found to be silently dropped on save and fixed.

#### Diagrams

- Authorization Boundary and Network Architecture gained their own `diagrams[]` support (previously only Data Flow had it), each with its own reference list in the Word export.
- A "🔄 Refresh from Components" button in SSP Section 9 re-syncs applied controls from whatever's currently in Section 8, without overwriting existing responses.
- Dashboard tab moved to the far right of the notebook; a new Data Sources tab placeholder was added (later became the Library's catalog/profile browser above).

#### Documentation

- New `user_stories.md` — role-based user stories (System Owner, Application User, System Auditor, Organisation User) with acceptance criteria and honest implementation-status notes, used throughout this release to ground design decisions.
- `todo.md` and the design document were kept current alongside every change in this release, rather than drifting — both fully reflect v0.2's actual state.

### Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

### Known limitations

- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md` §3) — the Library made *picking* one easier, it did not add multi-catalog support.
- No Profile Editor or standalone Component/Capability Definition document type yet (`todo.md` §1–2).
- No visual indicator in Component/Capability Editor showing whether an open file is the Library's master copy or a system's local copy — nothing currently stops editing a Library master directly by mistake (`todo.md` §5).
- Data Flow Links have no diagram export yet (drawing the links is done; auto-generating a `.drawio` from them is not — `todo.md` §4).
- Dashboard is still single-document (one SSP/AP/AR/POA&M at a time); the multi-network rollup described in `user_stories.md` US-13 is not built.
- Generated OSCAL output should be independently reviewed before use in a real authorisation package.

### Upgrading from v0.1

- If you have an existing workspace whose catalog/profile files now live in your Library folder, no action is needed — `load_workspace_manifest()` automatically falls back to the Library when the old workspace-relative path no longer resolves. Re-saving the workspace will record the new Library-relative reference going forward.
- If you haven't set up a Library folder yet, the app defaults to the repo's own `library/` folder — use the "📚 Library Folder" toolbar button to point it elsewhere.

---

## v0.1 (Pre-Production Release)

### What this is

A desktop application (Python/Tkinter) for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) 1.2.2 documents, purpose-built for organisations running multiple separate networks that each need their own System Security Plan. Component and capability libraries are defined once and reused across every SSP, turning SSP production into composition rather than repeated writing.

Full feature documentation is in [README.md](README.md).

### Highlights in this release

**Nine editor tabs**, covering the full assessment lifecycle:
- 🗂 **Workspace** — landing tab with per-tab guidance, plus Open/Save Workspace buttons that load or save an entire system's file set (catalog, profile, SSP, components, capabilities, AP, AR, POA&M) in one action via a portable JSON manifest
- 📊 **Authorization Dashboard** — live rollup of system identity, assessment currency, compliance posture, risk status, and POA&M health
- 📋 **Catalog Viewer** — browse any OSCAL catalog with class/guideline/search filtering and profile-aware highlighting
- ⚙ **Component Editor** — define reusable components (policy, hardware, software, service, etc.) and their control implementations
- 🔗 **Capability Editor** — bundle components into named capabilities with automatic control-response inheritance
- 🛡 **SSP Editor** — full System Security Plan authoring: system characteristics, boundary, network architecture, data flow, information types, roles/parties, capabilities used, components, control implementations, system users, and inventory items. Exports to OSCAL JSON, Word (.docx), and a System→Capability→Component draw.io diagram
- 📝 **Assessment Plan Editor** and 🔍 **Assessment Results Editor** — scope and record formal assessments, with one-click push of not-satisfied findings into the POA&M
- 📋 **POA&M Editor** — track remediation items through to closure

**Bulk data workflows:**
- CSV import for System Users (Section 11) and Inventory Items (Section 12), matching what an export from an external HR/asset-management system would realistically contain
- Workspace manifest import/export for loading an entire system's documents in one step

**Usability:**
- Dark/light theme toggle (Workspace tab), applied live across every tab without losing in-progress edits
- OSCAL 1.2.2 schema validation on load and save, with bundled schema zips for offline use

**Example data:**
- `example-data-ism/` — a complete fictional example ("Example Research Network") built against the Australian ISM catalog: catalog, profile, ~30 components, 8 capabilities, SSP, AP, AR, POA&M, and CSV templates
- `example-data-nist/` — component library aligned to NIST SP 800-53 Rev 5 and SP 800-171 Rev 3

### Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

### Known limitations

- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md`)
- No Profile Editor or Component Definition bulk editor yet
- Generated OSCAL output should be independently reviewed before use in a real authorisation package

---

## Feedback

Please open an issue for bugs or feature requests.
