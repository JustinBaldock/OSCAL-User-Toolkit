# OSCAL User Toolkit — v0.2 (Pre-Production Release)

> ⚠️ **Pre-production**: this is an early, actively-developed release. Interfaces, file formats, and internal data structures may still change between versions. Not yet recommended for production authorisation packages without independent review of generated OSCAL output.

## What this is

A desktop application (Python/Tkinter) for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) 1.2.2 documents, purpose-built for organisations running multiple separate networks that each need their own System Security Plan. v0.2's headline addition is a proper **Library** system: components, capabilities, catalogs, and profiles now live in one shared, organisation-level folder, separate from any individual system's own workspace — turning "copy this firewall's control responses into every new SSP" into a two-click import instead of hand-editing JSON.

Full feature documentation is in [README.md](README.md). See [oscal_user_toolkit_design_document.md](oscal_user_toolkit_design_document.md) for the technical design history (§10.13–§10.16 cover the Library system specifically), and [user_stories.md](user_stories.md) for the workflows this release targets.

## Highlights since v0.1

### Library system (new)

The biggest change in this release — a shared **Library** folder (`library/catalogs/`, `.../profiles/`, `.../components/`, `.../capabilities/`) that's separate from any one system's workspace:

- **📚 Library Folder** (toolbar): configure which folder is the Library once; persisted between launches, defaulting to the repo's own `library/` folder if never changed.
- **📚 Data Sources tab**: browse and load catalogs/profiles from the Library, or browse elsewhere for anything outside it. This is now the *only* way to open or clear the active catalog/profile — the old toolbar "Open Catalog"/"Open Profile"/"Clear Profile" buttons are gone.
- **📚 Import from Library** (Component/Capability Editor): copy a component or capability from the Library into the current system's own folder as an independent, editable copy — never mutates the Library source, never overwrites a local copy you've already edited.
- **🔄 Sync from System Folder** (SSP Editor, Section 8): pulls every component/capability file sitting in the current system's folder straight into the SSP, including auto-populated control responses and Capabilities Used entries. Safe to re-run any time — never duplicates.
- **Read-only Components/Capabilities visibility** (Assessment Plan, POA&M): both editors now show what the referenced SSP's system is built from, without needing write access to it.

### SSP Editor — Network Architecture & Data Flow

- **VLANs** (Section 4): record VLAN ID (validated 1–4094), name, and description, positioned under the Network Architecture description text.
- **Data Flow Links** (Section 4): record how data moves between the SSP's own components — source, target, protocol, port, transport, direction — positioned under the Data Flow description text. Both VLANs and Data Flow Links are stored as schema-valid, order-independent grouped OSCAL `props` (not a home-grown encoding), and `data-flow.description` auto-drafts a narrative summary from the links when left blank.
- Removed an earlier, OSCAL-incorrect approach that had attached "which component sends this information type" data directly to Information Types — checking the schema directly confirmed that object has no field for it.
- **Export to Word**: table cell font reduced to 9pt for readability in wide tables; page-break-before-table and per-table landscape orientation were both tried and reverted (didn't read well in practice).
- VLANs also appear in the Word export, at the bottom of the Network Architecture section.

### Application preferences

- **Dark/light theme** choice now persists between launches (`settings.py`).
- Assorted UX fixes: Save/Open Workspace button colours matched; app-wide sweep of unreadable button text in both themes; scrollbars and live counts added to the Capability Editor's Member Components and Component Editor's Protocols sections; Edit buttons added to Parties, Roles, and Diagram lists in the SSP Editor; Section 7b Responsible Parties remarks were found to be silently dropped on save and fixed.

### Diagrams

- Authorization Boundary and Network Architecture gained their own `diagrams[]` support (previously only Data Flow had it), each with its own reference list in the Word export.
- A "🔄 Refresh from Components" button in SSP Section 9 re-syncs applied controls from whatever's currently in Section 8, without overwriting existing responses.
- Dashboard tab moved to the far right of the notebook; a new Data Sources tab placeholder was added (later became the Library's catalog/profile browser above).

### Documentation

- New `user_stories.md` — role-based user stories (System Owner, Application User, System Auditor, Organisation User) with acceptance criteria and honest implementation-status notes, used throughout this release to ground design decisions.
- `todo.md` and the design document were kept current alongside every change in this release, rather than drifting — both fully reflect v0.2's actual state.

## Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

## Known limitations

- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md` §3) — the Library made *picking* one easier, it did not add multi-catalog support.
- No Profile Editor or standalone Component/Capability Definition document type yet (`todo.md` §1–2).
- No visual indicator in Component/Capability Editor showing whether an open file is the Library's master copy or a system's local copy — nothing currently stops editing a Library master directly by mistake (`todo.md` §5).
- Data Flow Links have no diagram export yet (drawing the links is done; auto-generating a `.drawio` from them is not — `todo.md` §4).
- Dashboard is still single-document (one SSP/AP/AR/POA&M at a time); the multi-network rollup described in `user_stories.md` US-13 is not built.
- Generated OSCAL output should be independently reviewed before use in a real authorisation package.

## Upgrading from v0.1

- If you have an existing workspace whose catalog/profile files now live in your Library folder, no action is needed — `load_workspace_manifest()` automatically falls back to the Library when the old workspace-relative path no longer resolves. Re-saving the workspace will record the new Library-relative reference going forward.
- If you haven't set up a Library folder yet, the app defaults to the repo's own `library/` folder — use the "📚 Library Folder" toolbar button to point it elsewhere.

## Feedback

Please open an issue for bugs or feature requests.
