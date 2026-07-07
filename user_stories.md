# OSCAL User Toolkit — User Stories

Lightweight backlog of who uses this tool, what they need to do, and why.
Referenced when designing or changing features so decisions are grounded in
an actual workflow rather than the schema alone.

**Format:** `As a [role], I want to [action], so that [benefit].`
Each story lists a few concrete acceptance criteria — enough to check a
feature against, not a full spec.

---

## Roles

Roles referenced by stories below. Add to this list as new personas come up.

- **System Owner** — accountable for a system's security posture; assembles
  and maintains its SSP; the primary user of this toolkit today.
- **Application User** — anyone running the toolkit day to day, regardless
  of which editor tab they work in; cares about the app itself being
  convenient across sessions (workspace continuity, display preferences),
  as distinct from the OSCAL content they're producing.
- **System Auditor** — reviews a system's SSP and plans/conducts its
  assessment; needs the SSP's documentation and full coverage of its
  components, capabilities, and selected controls before assessing.

---

## Catalog & Profile Selection

### US-1: Select a catalog and profile for the system to meet

**As a** System Owner,
**I want to** load a control catalog and a profile (control baseline) for my system,
**so that** the rest of my work (components, capabilities, SSP) is scoped to the right set of controls.

**Acceptance criteria:**
- Can open a catalog file and see its controls in the Catalog Viewer.
- Can open a profile file and see it filter the catalog down to the applicable control baseline.
- The loaded catalog/profile drives which controls are selectable elsewhere (Component Editor, Capability Editor, SSP Editor Section 8/9).

---

## Components & Capabilities

### US-2: Create or update components and capabilities

**As a** System Owner,
**I want to** create and edit components (and group them into capabilities) with their control implementations,
**so that** I have a reusable record of how each part of my system meets its controls.

**Acceptance criteria:**
- Can create a new component, or edit an existing one, with type, description, purpose, protocols, and control implementations.
- Can group components into a capability and have it inherit member components' control responses.
- Components and capabilities can be saved/loaded independently of any one SSP.

---

## System Security Plan

### US-3: Produce an SSP for system auditors

**As a** System Owner,
**I want to** assemble a System Security Plan and export it as both a Word document and OSCAL JSON,
**so that** I can give it to system auditors in a form they can read (docx) and a form other tools can validate/ingest (JSON).

**Acceptance criteria:**
- Can build up all SSP sections (system characteristics, boundary, network architecture, data flow, information types, roles, parties, components, control implementations, etc.) referencing the catalog/profile from US-1 and the components/capabilities from US-2.
- Can export the SSP as a `.docx` file that reads cleanly for a human auditor.
- Can save the SSP as OSCAL-conformant JSON that validates against the bundled OSCAL 1.2.2 schema.

---

## Assessment Results & Plan of Action and Milestones (POA&M)

### US-6: Open and read assessment results

**As a** System Owner,
**I want to** open an Assessment Results file and read its findings and observations,
**so that** I know what problems an assessor identified and need to be addressed.

**Acceptance criteria:**
- Can open an existing Assessment Results (`.json`) file.
- Findings, observations, and risks are readable in the Assessment Results tab, not just raw JSON.
- **Status: implemented.** `ar_tab.py` already supports opening and displaying Assessment Results files.

### US-7: Create a POA&M in response to an assessment result

**As a** System Owner,
**I want to** create a Plan of Action and Milestones (POA&M) that responds to findings from an Assessment Result,
**so that** I have a documented remediation plan for each identified problem, tied back to the finding it addresses.

**Acceptance criteria:**
- Can create POA&M items (weaknesses/risks, remediation milestones, target dates) in the POA&M Editor.
- Each POA&M item can reference the assessment finding/observation it responds to.
- **Status: partially implemented.** `poam_tab.py` supports creating and editing POA&M items and saving/opening POA&M JSON, but there is no current linkage step that lets a user open an Assessment Result and generate or cross-reference POA&M items directly from its findings — POA&M items are created independently today.

### US-8: Provide a POA&M to a system auditor to show remediation progress

**As a** System Owner,
**I want to** export my POA&M as both a Word document and OSCAL JSON,
**so that** I can give a system auditor evidence of progress fixing identified problems, in a form they can read (docx) and a form other tools can validate/ingest (JSON).

**Acceptance criteria:**
- Can save the POA&M as OSCAL-conformant JSON that validates against the bundled OSCAL 1.2.2 schema.
- Can export the POA&M as a `.docx` file that reads cleanly for a human auditor.
- **Status: partially implemented.** POA&M JSON save/open exists (`poam_tab.py`), but there is no `build_poam_docx()` equivalent to `build_ssp_docx()` yet — POA&M docx export does not exist.

---

## Assessment Planning (System Auditor)

### US-9: Load an SSP to view system documentation

**As a** System Auditor,
**I want to** load a System Security Plan and read its documentation,
**so that** I understand the system I'm assessing — its boundary, network architecture, components, capabilities, and control implementations — before planning the assessment.

**Acceptance criteria:**
- Can open an existing SSP (`.json`) file and browse its sections in the SSP Editor.
- All SSP sections (system characteristics, boundary, network architecture, VLANs, data flow, information types, roles, parties, components, control implementations, etc.) are readable, not just raw JSON.
- **Status: implemented.** `ssp_tab.py` already supports opening and displaying a saved SSP.

### US-10: Create an assessment plan covering all components, capabilities, and selected controls

**As a** System Auditor,
**I want to** create an Assessment Plan that references the system's SSP and covers every one of its components and capabilities, addressing every control selected for the system,
**so that** the assessment plan has complete coverage — nothing in the system's boundary or control baseline is left unassessed.

**Acceptance criteria:**
- Can reference an SSP by href in the Assessment Plan (Section 2 — SSP Reference).
- The Assessment Plan can be populated with every component from the referenced SSP.
- The Assessment Plan can be populated with every capability from the referenced SSP.
- The Assessment Plan can be populated with every control ID selected for the system, and clearly shows/tracks which of those controls are still outstanding.
- **Status: partially implemented.** `ap_tab.py` already has "🔄 Refresh from SSP" to pull components from the referenced SSP's file, and "📋 Load IDs from profile" to populate control IDs from the toolbar's loaded profile. There is currently no equivalent capability-coverage step (capabilities aren't referenced anywhere in `ap_tab.py` yet), and "Load IDs from profile" draws from whichever profile happens to be loaded in the toolbar rather than specifically the control set recorded against the referenced SSP itself — worth checking these two sources always agree before treating control coverage as complete.

---

## Application Preferences & Session Continuity

### US-4: Save and reopen a workspace, including its theme

**As an** Application User,
**I want to** save a workspace file that records all my currently open files and my light/dark theme choice at the time of saving,
**so that** opening that workspace file later reopens every file into the correct tabs *and* switches the app to whichever theme I was using when I saved it — without manually reopening each file or reselecting the theme.

**Acceptance criteria:**
- Saving a workspace captures every file currently open across all tabs, plus the active theme (light/dark).
- Opening a saved workspace file reopens every one of those files into the correct tabs.
- Opening a saved workspace file also switches the app's theme to whatever was active when that workspace was saved.
- The theme is workspace-scoped, not a standalone global app preference — a different workspace file can carry a different saved theme.
- **Status: partially implemented.** Save/Open Workspace already exists (`app.py` `_save_workspace()` / `_open_workspace()`, `WorkspaceTab`, `build_workspace_manifest()` / `load_workspace_manifest()` in `models.py`) and correctly reopens files. The theme is not yet part of the saved manifest, and opening a workspace does not currently change the active theme — `set_theme()` only mutates the in-memory `COLORS` dict for the running session.

---

## Backlog (not yet written as full stories)

- System Auditor conducting/recording the assessment itself (Assessment Results authoring) — US-9/US-10 cover planning; actually running the assessment and recording findings isn't written up yet.
- Multi-system / multi-SSP management for an organisation with several systems.
