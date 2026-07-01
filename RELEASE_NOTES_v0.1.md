# OSCAL User Toolkit — v0.1 (Pre-Production Release)

> ⚠️ **Pre-production**: this is an early, actively-developed release. Interfaces, file formats, and internal data structures may still change between versions. Not yet recommended for production authorisation packages without independent review of generated OSCAL output.

## What this is

A desktop application (Python/Tkinter) for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) 1.2.2 documents, purpose-built for organisations running multiple separate networks that each need their own System Security Plan. Component and capability libraries are defined once and reused across every SSP, turning SSP production into composition rather than repeated writing.

Full feature documentation is in [README.md](README.md).

## Highlights in this release

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

## Requirements

- Python 3.9+
- `jsonschema` (schema validation) and `python-docx` (Word export) — see [README.md#requirements](README.md#requirements) for installation

## Known limitations

- Single catalog/profile pair per session (multi-catalog support is tracked in `todo.md`)
- No Profile Editor or Component Definition bulk editor yet
- Generated OSCAL output should be independently reviewed before use in a real authorisation package

## Feedback

Please open an issue for bugs or feature requests.
