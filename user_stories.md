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

## Backlog (not yet written as full stories)

- Auditor-side workflow (reviewing/annotating an SSP) — no known persona yet.
- Multi-system / multi-SSP management for an organisation with several systems.
