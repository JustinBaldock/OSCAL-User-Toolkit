# OSCAL User Toolkit

> **Designed by Justin Baldock · Built with Claude AI**

A desktop application for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) (Open Security Controls Assessment Language) documents — purpose-built for organisations that operate multiple separate networks and need to reduce the effort of producing System Security Plans and supporting audit evidence.

---

## Why this tool exists

Large organisations — defence agencies, government departments, critical infrastructure operators — typically run many separate networks, each requiring its own System Security Plan (SSP). Without tooling, teams repeat the same work for every network: documenting the same firewall, the same identity platform, the same patching process, over and over.

OSCAL solves this at the standard level by separating **what a component does** from **which system it appears in**. The OSCAL User Toolkit makes that practical:

- Define a component once (e.g. "Managed Network Switch") and describe how it satisfies each relevant security control
- Group components into reusable **capabilities** (e.g. "Perimeter Defence" or "Identity and Access Management")
- Reference those components and capabilities in each SSP rather than rewriting implementation narratives from scratch
- Assess the system against those components using the Assessment Plan and Assessment Results editors
- Track remediation work in the POAM editor and import findings directly from Assessment Results

The result is a library of audited, reusable building blocks that grows over time, shifting SSP production from weeks of writing to days of composition.

---

## Features

The tab bar is grouped: **Workspace** and **Dashboard** stay top-level, while **Data** (Data Sources, Catalog Viewer), **Organisation** (Library Components, Library Capabilities, All Systems), **System Overview** (Component, Capability, and SSP Editors), and **Audit** (Assessment Plan, Assessment Results, POA&M Editor) are each a group of sub-tabs.

### Systems Folder & All Systems (new)
- **Systems folder**: one subfolder per system — each holding its own workspace manifest, SSP, AP, AR, and POA&M — separate from the shared Library. Configure it via the **🗂 Systems Folder** toolbar button (persisted between launches; defaults to this repo's own `systems/` folder, which is where the bundled examples now live)
- **🌐 All Systems tab** (lives in the **Organisation** tab group): scans every subfolder in the Systems folder and shows an organisation-wide rollup — one row per system (compliance %, open risks, overdue POA&M items) plus aggregate totals — without needing to open each system individually. Distinct from the Dashboard tab, which only ever shows the one system currently open in the live editor tabs

### Data Sources & Library (new in v0.2)
- **Library folder**: a shared, organisation-level `catalogs/`/`profiles/`/`components/`/`capabilities/` folder, separate from any one system's own workspace — configure it once via the **📚 Library Folder** toolbar button (persisted between launches; defaults to this repo's own `library/` folder)
- **Data Sources tab**: browse and load the Library's catalogs/profiles, or browse elsewhere for anything outside it — this is the only way to open or clear the active catalog/profile
- **Import from Library** (Component/Capability Editor): copy a Library component/capability into the current system's own folder as an independent, editable copy — never touches the Library source, never overwrites a copy you've already edited
- **Sync from System Folder** (SSP Editor, Section 8): pull everything that's been imported for the current system straight into the SSP, with control responses auto-populated
- Assessment Plan and POA&M both show read-only visibility into whatever components/capabilities the referenced SSP has, without needing write access
- **95 example components** ship in `library/components/`, covering every OSCAL component type — hardware, software, services, operating systems, policies, and (less commonly represented in most toolkits) `physical`, `process-procedure`, `plan`, `guidance`, and `standard` — plus **11 example capabilities** in `library/capabilities/`. See [oscal_user_toolkit_design_document.md §11](oscal_user_toolkit_design_document.md) for the full breakdown

### Organisation Tab — Library Component & Capability Editors (new)
- **⚙ Library Components** and **🔗 Library Capabilities**: dedicated editors locked to `library/components/`/`library/capabilities/` — no Open File/Open Folder dialogs, no location prompt on save; they auto-load every file in the Library and save straight back to it, so there's no ambiguity about whether you're editing the Library's shared master or a system's local copy
- **🔄 Refresh from Library** / **📥 Add File to Library** replace the removed Open/Import buttons — the only way files enter or update in this view
- Use this tab to maintain the organisation's shared component/capability masters; use the regular Component/Capability Editor tabs (under **System Overview**) to import and adapt a copy for one specific system
- **🌐 All Systems** also lives in this tab group, alongside the Library editors

### Workspace
- **Landing tab** with per-tab guidance and **Open/Save Workspace** buttons that load or save an entire system's file set (SSP, components, capabilities, AP, AR, POA&M) in one action via a portable JSON manifest
- Catalog/profile references in a workspace resolve against the Library automatically, so a workspace manifest stays valid even if the Library folder is configured differently on another machine
- **Dark/light theme toggle**, applied live across every tab without losing in-progress edits; the chosen theme persists between launches

### Authorization Dashboard
- Provides a live overview of the entire assessment lifecycle for the one system currently open in the editor tabs, at a glance (see "All Systems" above for the organisation-wide equivalent)
- **System Identity** card: system name, version, and classification from the open SSP
- **Assessment Currency** card: days since the last assessment completed, colour-coded by age
- **Compliance Posture** card: count of satisfied vs not-satisfied findings with a breakdown list
- **Risk Status** card: risks grouped by lifecycle state (open, investigating, remediating, closed)
- **POA&M Health** card: POA&M items split into on-track, overdue, and no scheduled date
- **Observations** card: observations grouped by method (EXAMINE, INTERVIEW, TEST) and type
- Reads live data from all currently open documents — no need to save first

### Catalog Viewer
- Load any OSCAL catalog (tested with the Australian ISM — 1,150+ controls, and NIST SP 800-53 Rev 5 — 1,189 controls and enhancements)
- Filter controls by **class**, **guideline group**, or **keyword search**
- Browse the full control hierarchy — top-level guideline group, sub-category, and topic shown for every control
- Select a control to see its full statement, applicability, revision history, and Essential Eight mapping in a detail panel
- Apply a **profile** to restrict the view to a specific baseline (e.g. ISM Non-Classified, NIST Moderate)

### Component Editor
- Create OSCAL Component Definition files describing how a system component implements security controls
- Supports all OSCAL 1.2.2 component types: `defined-system`, `system`, `interconnection`, `software`, `hardware`, `service`, `policy`, `process`, `procedure`, `plan`, `guidance`, `standard`, `validation`, `physical` (the schema's own single `process-procedure` value works too — it's just not yet one of the dropdown's preset options)
- **Version & Revision History** (Section 1): each component carries its own stable UUID, editable version number, and revision history using OSCAL's native `metadata.revisions[]` — a **📌 Save New Version** action archives the current version with optional remarks before bumping, distinct from a plain in-place save. Tracked per component (not per file), so this stays correct even in the Library Component Editor where many components share one tab instance
- **Live search and type filter** in the component list — find components instantly by name, description, or type even when hundreds are loaded
- **Section 6 — Protocols**: document the TCP/UDP ports and protocols the component uses or exposes
- **Section 7 — Links**: attach external references (vendor documentation, CVE advisories, configuration baselines, policy documents) with structured relationship types
- Write implementation narratives for individual controls with live dot indicators (● written / ○ not yet)
- "All Controls" and "Applied Controls" tabs for quick navigation
- Add structured metadata: operational status, responsible roles, custom properties
- Open multiple component files at once, or load an entire folder

### Capability Editor
- Group components into named security capabilities (e.g. "Privileged Access Management", "Email Security")
- **Automatic inheritance** — when a component is added as a member, its control responses flow into the capability automatically, attributed to the source component via `source-component-uuid` props
- Write additional capability-level responses for controls that span multiple components
- Save capabilities as self-contained OSCAL files that bundle their member components
- Load individual capability files or an entire folder of capabilities

### SSP Editor
- Create and edit OSCAL System Security Plan documents
- Capture system characteristics, authorisation boundary, network architecture, and data flow descriptions
- **VLANs** (Section 4): record VLAN ID (validated 1–4094), name, and description
- **Data Flow Links** (Section 4): record how data moves between the SSP's own components — source, target, protocol, port, transport, direction; the Data Flow description is auto-drafted from these links if left blank
- Manage roles, parties, and information types with full CIA impact levels
- **Security Impact Level** (OSCAL 1.2.x): set Confidentiality, Integrity, and Availability objectives independently
- Define system components and document how each implements individual security controls
- Reference a loaded profile so the SSP declares exactly which baseline it is assessed against
- **Capabilities Used** (Section 8): pick a capability from the Capability Editor's loaded list and it is recorded on the SSP (as an OSCAL metadata prop, since OSCAL 1.2.2 has no native "capabilities" field on an SSP) — its member components and their control responses are pulled straight into Section 8/9 automatically, provided the component files are already loaded in the Component Editor
- **🔄 Sync from System Folder** (Section 8): pulls every component/capability file that's been imported into the current system's folder (via Component/Capability Editor's "📚 Import from Library") straight into the SSP, with control responses auto-populated — safe to re-run any time, never duplicates
- **System Users → Import CSV** (Section 11): bulk-import system user entries from a CSV exported by another tool. Expected columns: `title, short_name, role_ids, description, remarks` (`role_ids` may list multiple roles separated by commas within the cell) — see `systems/example-data-ism/ssp_system_users.csv` for a template
- **Inventory Items → Import CSV** (Section 12): bulk-import inventory items from a CSV — typically an export from an external asset management system. Expected columns: `description, asset_tag, serial_number, hostname, ip_address, mac_address, physical_location, components, remarks`. Only `description` is required; the metadata columns become OSCAL props, and `components` (semicolon-separated for multiple) is matched case-insensitively against Section 8's current component titles — an asset management export won't usually know the OSCAL mapping, so most rows are expected to have this column blank and only link where the title matches exactly. See `systems/example-data-ism/inventory_items.csv` for a template
- **Export to Word** — generate a formatted `.docx` report, including a Capabilities Used table (capability name alongside its member components) and control implementations grouped under catalog guideline headings (requires `python-docx`)
- **Export Capability and Component Map** (Section 8): generate a System → Capability → Component hierarchy diagram:
  - Loads capabilities currently open in the Capability Editor
  - Capabilities and their member components are laid out in columns
  - SSP components not covered by any capability appear in an "Uncategorised" column
  - Component boxes are colour-coded by type (policy = amber, software = blue, hardware = green, service = purple)
  - Output is a `.drawio` file that opens directly in the draw.io desktop app or [app.diagrams.net](https://app.diagrams.net)
  - *Tip: load your capability files in the Capability Editor tab before exporting*

### Assessment Plan (AP) Editor
- Create and edit OSCAL Assessment Plan documents
- Document assessment objectives, methodology, and scope
- **Tasks**: define assessment tasks with type (milestone or action), timing (on-date, within-date, or repeating at-frequency with unit), associated activities, and responsible roles
- **Reviewed Controls**: specify which controls are in scope for the assessment
- **Assessment Subjects**: declare what system components, users, or locations are subject to assessment
- Link the AP to the SSP it assesses via the system reference field
- Save AP documents conformant with OSCAL 1.2.2

### Assessment Results (AR) Editor
- Create and edit OSCAL Assessment Results documents
- Record findings, observations, and risks discovered during assessment
- **Findings**: capture target control ID, target type, status (satisfied / not-satisfied), status reason, and remarks
- **Observations**: record evidence with method (EXAMINE, INTERVIEW, TEST), type, and description; UUID displayed for cross-referencing
- **Risks**: document open risks with title, description, status, lifecycle, and remediation responses; CIA impact characterizations (Confidentiality, Integrity, Availability) stored as OSCAL facets
- **Assessment Log**: record timestamped log entries of assessment activities
- **Import to POA&M**: export not-satisfied findings, their related observations, and risks directly into the POA&M editor — UUIDs are preserved for referential integrity

### POA&M Editor
- Create and edit OSCAL Plan of Action and Milestones documents
- **Import from Assessment Results**: load findings, observations, and risks from an AR file in a single action; deduplicates by UUID so re-importing does not create duplicate entries
- **POA&M Items**: track remediation work with scheduled completion dates, related findings, and related observations
- **Findings**: display UUID from the source AR so users can cross-reference back to the assessment evidence
- **Observations**: record observations with method, type, and assessed-by attribution
- **Risks**: document risks with CIA impact (Confidentiality, Integrity, Availability), remediation lifecycle, and open/closed status; amber warning banner shown for risks imported from AR to indicate they originated from an assessment
- Link the POA&M to its source SSP via the system reference field

### Schema Validation
- Bundled OSCAL release zips (1.1.2, 1.2.0, 1.2.2) — select the target version from the toolbar
- Catalog files are validated against the OSCAL JSON schema when opened
- Capability files are validated before saving
- Informative message shown when the optional `jsonschema` package is not installed
- Validation warnings allow the user to proceed — real-world files sometimes have minor deviations

---

## Example Data

### ISM Example Data (`systems/example-data-ism/`)

A complete example environment built around the Australian Information Security Manual (ISM), including a sample SSP, AP, AR, and POA&M.

**Components** — 38 ready-to-use component files. Load them all at once using **📁 Open Folder** in the Component Editor:

| Category | Examples |
|---|---|
| **Hardware** (6) | Cabling Infrastructure, Central Firewall, Network Encryptor, Managed Network Switch, Enterprise Wireless AP, UPS |
| **Interconnection** (3) | No Internet Connection, Filtered Internet Connection, Site-to-Site WAN Link |
| **Operating Systems** (4) | Windows 11 Workstation, Windows Server 2022, RHEL Linux Server, VMware ESXi Hypervisor |
| **Policies** (8) | System Usage, AD GPO Client Hardening, Patch Management, Backup and Recovery, Remote Access, Incident Response, Access Control, Data Classification |
| **Services** (11) | Active Directory, ManageEngine ServiceDesk Plus, Microsoft SQL Server 2022, Windows Fileshare, DHCP Server, Certificate Authority/PKI, VPN Remote Access, Exchange Online, Veeam Backup, Web Proxy, NTP Server |
| **Software** (6) | Microsoft 365 Apps, Microsoft Defender for Endpoint, Microsoft Edge, Adobe Acrobat, Tenable Nessus, Microsoft Sentinel |

**Capabilities** — 8 capability files showing how components combine to satisfy control families:

| Capability | Components |
|---|---|
| Account Management | Active Directory + System Usage Policy |
| Remote Office | Cabling Infrastructure + Network Encryptor |
| Patch Management | Patch Management Policy + Windows 11 + Tenable Nessus |
| Privileged Access Management | PAM Policy + Active Directory + Entra ID MFA |
| Endpoint Protection | Endpoint Protection Policy + Defender for Endpoint + Windows Firewall |
| Email Security | Email Security Policy + Defender for Office 365 + Outlook |
| Backup and Recovery | Backup Policy + Veeam + AWS S3 offsite storage |
| Security Monitoring and Logging | Logging Policy + Microsoft Sentinel + Windows Audit Policy/WEF |

**Assessment documents:**
- `ssp_ERN.json` — example System Security Plan
- `ap_ERN.json` — example Assessment Plan with 12 tasks across 4 phases
- `ar_ERN.json` — example Assessment Results with 5 risks, 12 observations, 14 findings, and 9 log entries
- `poam_ERN_POAM.json` — example POA&M with items imported from the AR

### NIST Example Data (`systems/example-data-nist/`)

A parallel example environment for US federal and contractor use cases, referencing NIST SP 800-53 Rev 5 controls (`ac-2`, `si-2`, `ra-5`, etc.).

**Catalogs and profiles** — downloaded directly from NIST OSCAL:

| File | Description |
|---|---|
| `NIST_SP-800-53_rev5_catalog.json` | Full SP 800-53 Rev 5 catalog (324 controls + 872 enhancements) |
| `NIST_SP-800-53_rev5_LOW-baseline_profile.json` | Low baseline (149 controls) |
| `NIST_SP-800-53_rev5_MODERATE-baseline_profile.json` | Moderate baseline (287 controls) |
| `NIST_SP-800-53_rev5_HIGH-baseline_profile.json` | High baseline (370 controls) |
| `NIST_SP-800-53_rev5_PRIVACY-baseline_profile.json` | Privacy baseline (96 controls) |
| `NIST_SP800-171_rev3_catalog.json` | SP 800-171 Rev 3 — CUI requirements (130 controls) |

**Components** — 20 component files referencing SP 800-53 Rev 5 Moderate baseline controls:

| Category | Examples |
|---|---|
| **Policies** (7) | Access Control, Patch Management, Incident Response, Backup & Recovery, Configuration Management, Remote Access, Security Awareness Training |
| **Operating Systems** (2) | Windows 11 Workstation, Windows Server 2022 |
| **Services** (5) | Active Directory, Exchange Online, VPN Remote Access, Veeam Backup, Microsoft Sentinel SIEM |
| **Software** (3) | Microsoft Defender for Endpoint, Microsoft 365 Apps, Tenable Nessus |
| **Hardware** (3) | Perimeter/Internal Firewalls, Network Switches, UPS |

---

## Getting Started

### Requirements

- Python 3.10 or later
- `tkinter` — included with standard Python on Windows and macOS; on Linux install `python3-tk`
- `jsonschema` *(optional)* — enables schema validation on open/save
- `python-docx` *(optional)* — enables the **Export to Word** button in the SSP Editor

```bash
pip install jsonschema python-docx
```

### Installation

```bash
git clone https://github.com/<your-org>/OSCAL-User-Toolkit.git
cd OSCAL-User-Toolkit
python main.py
```

No build steps required. All core functionality uses Python's standard library. If an optional package is not installed, the feature that depends on it is gracefully disabled with an informative message.

### OSCAL Schema Zips

The `oscal/` folder should contain one or more OSCAL release zip files:

```
oscal/
    oscal-1.2.2.zip
    oscal-1.2.0.zip
    oscal-1.1.2.zip
```

Download releases from the [OSCAL GitHub releases page](https://github.com/usnistgov/OSCAL/releases). The application scans this folder at startup and populates the version selector automatically.

---

## Recommended Workflow

### 0. Set up your Library and per-system workspace

- Catalogs, profiles, components, and capabilities that are shared across every system live in one **Library** folder — set it once via the **📚 Library Folder** button in the toolbar (defaults to this repo's own `library/` folder if you don't change it).
- Each individual system gets its own **workspace folder**, holding that system's own workspace manifest, SSP, AP, AR, POA&M, and any components/capabilities imported from the Library for that system specifically.
- Open/load a catalog or profile from the **📚 Data Sources** tab, which browses the Library's `catalogs/`/`profiles/` subfolders directly (or browse elsewhere for anything outside the Library).

### 1. Build a component library

1. In the **Data Sources** tab, load the catalog (and optionally a profile) you'll be writing components against
2. Switch to the **Component Editor** tab
3. Load the ISM example components from `systems/example-data-ism/components/` using **📁 Open Folder** as a starting point
4. For each component unique to your environment: set its type, add protocols and links, write implementation narratives per control, save as an individual JSON file into your Library's `components/` folder
5. Once a component is saved to the Library, any system can pull a copy of it in via **📚 Import from Library**

### 2. Build a capability library

1. Open your component files using **Open Folder** in the Capability Editor
2. Create a new capability (e.g. "Perimeter Defence")
3. Add the relevant components as members — their control responses inherit automatically
4. Add capability-level narratives for controls that span multiple components
5. Save the capability into your Library's `capabilities/` folder — it bundles its member components so it is self-contained

### 3. Produce an SSP

1. In the **Data Sources** tab, load the catalog and profile for the target network
2. In the Component/Capability Editor, use **📚 Import from Library** to pull in whichever components/capabilities this system needs, then edit them to match this system's specifics
3. In the SSP Editor, fill in system characteristics, boundary, network architecture (including VLANs), data flow (including Data Flow Links), information types, and security impact levels
4. Use **🔄 Sync from System Folder** (Section 8) to pull every component/capability that's been imported for this system straight into the SSP, with control responses auto-populated
5. Save the SSP
6. Use **Export Capability and Component Map** (with capabilities loaded in the Capability Editor) to produce a System → Capability → Component architecture diagram

### 4. Conduct an assessment

1. In the **Assessment Plan** editor, create an AP linked to the SSP; define tasks, reviewed controls, and assessment scope; save as an AP JSON file
2. In the **Assessment Results** editor, create an AR linked to the AP; record findings, observations, risks, and assessment log entries as the assessment progresses
3. When the assessment is complete, use **Import to POA&M** in the AR editor to push not-satisfied findings, observations, and risks into a new or existing POA&M

### 5. Track remediation

1. In the **POA&M Editor**, open or create a POA&M; use **Import from AR** to pull in findings from Assessment Results
2. For each POA&M item, set a scheduled completion date and link related findings and observations
3. Update risk status as remediation progresses (open → investigating → remediating → closed)
4. The **Authorization Dashboard** shows the current compliance posture, risk status, and POA&M health at a glance

---

## OSCAL Document Types Supported

| Document Type | Read | Write | Notes |
|---|:---:|:---:|---|
| Catalog | ✅ | — | Any OSCAL catalog; tested with ISM and NIST SP 800-53 Rev 5 |
| Profile | ✅ | — | Filters the control list to a selected baseline |
| Component Definition | ✅ | ✅ | All 14 OSCAL 1.2.2 component types; includes protocols, links, and control implementations |
| Capability Definition | ✅ | ✅ | Bundles member components; automatic control inheritance with source attribution |
| System Security Plan | ✅ | ✅ | Full metadata, characteristics, information types, security impact levels, control implementations |
| Assessment Plan | ✅ | ✅ | Tasks with timing and frequency, reviewed controls, assessment subjects |
| Assessment Results | ✅ | ✅ | Findings, observations, risks with CIA characterizations, assessment log |
| Plan of Action & Milestones | ✅ | ✅ | Items, findings, observations, risks; AR import with UUID deduplication |

---

## Project Structure

```
OSCAL-User-Toolkit/
├── main.py                          # Entry point — run this to start the app
├── oscal_user_toolkit/
│   ├── __init__.py
│   ├── models.py                    # All data logic — parsing, building, validating OSCAL JSON; no GUI code
│   ├── app.py                       # Main window, toolbar, tab wiring, and shared state
│   ├── settings.py                  # Persisted app settings — Library/Systems folder paths, default theme
│   ├── tab_utils.py                 # Shared helper for the grouped-tab mousewheel guard
│   ├── workspace_tab.py             # Workspace tab (landing tab; Open/Save Workspace)
│   ├── data_sources_tab.py          # Data Sources tab — browses the Library's catalogs/profiles
│   ├── dashboard_tab.py             # Authorization Dashboard tab (the one currently-open system)
│   ├── all_systems_tab.py           # All Systems tab — organisation-wide rollup across the Systems folder
│   ├── catalog_tab.py               # Catalog Viewer tab
│   ├── component_tab.py             # Component Editor tab (includes Import from Library)
│   ├── capability_tab.py            # Capability Editor tab (includes Import from Library)
│   ├── ssp_tab.py                   # SSP Editor tab (includes Capability/Component map, DOCX export, CSV import, Sync from System Folder)
│   ├── ap_tab.py                    # Assessment Plan Editor tab
│   ├── ar_tab.py                    # Assessment Results Editor tab
│   └── poam_tab.py                  # POA&M Editor tab (includes AR import)
├── oscal/                           # OSCAL schema release zips
│   ├── oscal-1.2.2.zip
│   ├── oscal-1.2.0.zip
│   └── oscal-1.1.2.zip
├── library/                          # Library folder (default location) — shared across every system
│   ├── catalogs/                    # e.g. ISM_catalog_2026_06.json
│   ├── profiles/                    # e.g. ISM_NON_CLASSIFIED-baseline_profile_2026-06.json
│   ├── components/                  # Reusable component-definition files
│   └── capabilities/                # Reusable capability-definition files
├── systems/                          # Systems folder (default location) — one subfolder per system
│   ├── example-data-ism/            # Example environment — Australian ISM
│   │   ├── ssp_ERN.json
│   │   ├── ap_ERN.json
│   │   ├── ar_ERN.json
│   │   ├── poam_ERN_POAM.json
│   │   ├── workspace_ERN.json       # Loads everything above via Open Workspace
│   │   ├── components/              # Copies of the example's own component files
│   │   └── capability/              # Copies of the example's own capability files
│   ├── example-data-nist/           # Example environment — NIST SP 800-53 Rev 5
│   │   └── components/              # NIST SP 800-53 component files
│   └── example-02/                  # Work-in-progress example (catalog/profile/components only, no SSP yet)
├── user_stories.md                  # Role-based user stories driving design decisions
├── todo.md                          # Planned features: Profile Editor, Component Definition Editor, multi-catalog support
├── oscal_user_toolkit_design_document.md  # Technical design document and changelog
├── SECURE_CODING.md                 # Project rules derived from the OpenSSF Secure Coding Guide for Python
└── README.md
```

The codebase follows a strict two-layer separation: `models.py` contains all data parsing, serialisation, and validation logic with no GUI code; the tab files contain all GUI code with no direct JSON manipulation.

Contributors (human or AI) should read [SECURE_CODING.md](SECURE_CODING.md) before touching file-loading or exception-handling code — this app constantly parses OSCAL JSON files a user picked from disk, which the OpenSSF guide treats as untrusted input regardless of it being "just a local file."

---

## Design and Authorship

**Designed by:** Justin Baldock  
**Built with:** [Claude AI](https://claude.ai) (Anthropic) — application code, architecture, and documentation written by Claude AI working interactively with the designer

This project demonstrates human-AI collaboration in software development: the domain expertise, product vision, and design decisions came from the designer; the implementation, architecture, and documentation were produced by Claude AI through an iterative conversation.

---

## OSCAL Standard

OSCAL is an open standard developed by [NIST](https://www.nist.gov/). It provides machine-readable formats for security control catalogues, baselines, component definitions, system security plans, and assessment artefacts.

- [OSCAL documentation](https://pages.nist.gov/OSCAL/)
- [OSCAL GitHub repository](https://github.com/usnistgov/OSCAL)
- [Australian ISM (Information Security Manual)](https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/ism)
- [NIST SP 800-53 Rev 5](https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final)
- [NIST SP 800-171 Rev 3](https://csrc.nist.gov/publications/detail/sp/800-171/rev-3/final)

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome. Please open an issue or pull request on GitHub.

---

## Licence

This project is released under the [GNU General Public License v3.0](LICENSE) (GPLv3).

You are free to use, study, modify, and distribute this software, provided that any distributed modifications or derivative works are also released under the GPLv3.
