# OSCAL User Toolkit

> **Designed by Justin Baldock · Built with Claude AI**

A desktop application for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) (Open Security Controls Assessment Language) documents — purpose-built for organisations that operate multiple separate networks and need to reduce the effort of producing System Security Plans and supporting audit evidence.

---

## Why this tool exists

Large organisations — defence agencies, government departments, critical infrastructure operators — typically run many separate networks, each requiring its own System Security Plan (SSP). Without tooling, teams repeat the same work for every network: documenting the same firewall, the same identity platform, the same patching process, over and over, with slight variations.

OSCAL solves this at the standard level by separating **what a component does** from **which system it appears in**. The OSCAL User Toolkit makes that practical:

- Define a component once (e.g. "Managed Network Switch") and describe how it satisfies each relevant security control
- Group components into reusable **capabilities** (e.g. "Perimeter Defence" or "Identity and Access Management")
- Reference those components and capabilities in each SSP rather than rewriting the implementation narrative from scratch
- When a component is patched or reconfigured, update it in one place — every SSP that references it benefits immediately

The result is a library of audited, reusable building blocks. As the library grows, producing a new SSP shifts from weeks of writing to days of composition.

---

## Features

### Catalog Viewer
- Load any OSCAL catalog (tested with the Australian ISM — 1,150+ controls)
- Filter controls by **class**, **guideline group**, or **keyword search**
- Browse the full control hierarchy — top-level guideline group, sub-category, and topic shown for every control
- Select a control to see its full statement, applicability, revision history, and Essential Eight mapping in a detail panel
- Apply a **profile** to restrict the view to a specific baseline (e.g. non-classified, SECRET)

### Component Editor
- Create OSCAL Component Definition files describing how a system component implements security controls
- Supports all OSCAL component types: `software`, `hardware`, `service`, `policy`, `process`, `procedure`, `plan`, `guidance`, `standard`, `validation`, `interconnection`
- **Live search and type filter** in the component list — find components instantly by name, description, or type even when hundreds are loaded
- **Section 7 — Links**: attach external references to each component (vendor documentation, CVE advisories, configuration baselines, policy documents) with structured relationship types
- **Section 6 — Protocols**: document the TCP/UDP ports and protocols the component uses or exposes
- Write implementation narratives for individual controls with live dot indicators (● written / ○ not yet)
- "All Controls" and "Applied Controls" tabs in the control list for quick navigation
- Add structured metadata: operational status, responsible roles, custom properties
- Open multiple component files at once, or load an entire folder
- Catalog required; profile optional (falls back to full control list if no profile is loaded)

### Capability Editor
- Group components into named security capabilities (e.g. "Privileged Access Management", "Network Segmentation")
- **Automatic inheritance** — when a component is added as a member, its control responses flow into the capability automatically, attributed to the source component
- Write additional capability-level responses for controls that no single component can satisfy alone
- Save capabilities as self-contained OSCAL files that bundle their member components — ready to reference from any SSP
- Load individual capability files or an entire folder of capabilities

### SSP Editor
- Create OSCAL System Security Plan documents
- Capture system characteristics, authorisation boundary, network architecture, and data flow descriptions
- Manage roles, parties, and information types with CIA impact levels
- Define system components and document how each one implements individual security controls
- Reference a loaded profile so the SSP declares exactly which baseline it is assessed against
- Saves a self-documenting SSP that records the profile title, version, and filename in the back-matter section
- **Export to Word** — generate a formatted `.docx` report from the SSP, with control implementations grouped and sorted under catalog guideline headings (requires `python-docx`)

### POAM Editor
- Create and edit OSCAL Plan of Action and Milestones (POAM) documents
- Track security findings, risks, and remediation activities
- Link findings to specific controls from the loaded catalog

### Schema Validation
- Bundled OSCAL release zips (1.1.2, 1.2.0, 1.2.2) — select the target version from the toolbar
- Catalog files are validated against the OSCAL schema when opened
- Capability files are validated before saving
- Validation warnings allow the user to proceed — real-world files sometimes have minor deviations

---

## Example Component Library

The `example-data/components/` folder contains **41 ready-to-use component files** covering a well-rounded example environment. Load them all at once using **📁 Open Folder** in the Component Editor.

| Category | Examples |
|---|---|
| **Hardware** (7) | Cabling Infrastructure, Central Firewall, Network Encryptor, Managed Network Switch, Enterprise Wireless AP, UPS, NAS Storage |
| **Interconnection** (3) | No Internet Connection, Filtered Internet Connection, Site-to-Site WAN Link |
| **Operating Systems** (4) | Windows 11 Workstation, Windows Server 2022, RHEL Linux Server, VMware ESXi Hypervisor |
| **Policies** (8) | System Usage, AD GPO Client Hardening, Patch Management, Backup and Recovery, Remote Access, Incident Response, Access Control, Data Classification |
| **Services** (12) | Active Directory, ManageEngine ServiceDesk Plus, Microsoft SQL Server 2022, Windows Fileshare, MongoDB, DHCP Server, Certificate Authority/PKI, VPN Remote Access, Exchange Online, Veeam Backup, Web Proxy, NTP Server |
| **Software** (7) | Airlock Digital, Microsoft 365 Apps, Microsoft Defender for Endpoint, Microsoft Edge, Adobe Acrobat, Tenable Nessus, Microsoft Sentinel |

All components include:
- ISM control implementations with detailed implementation narratives
- TCP/UDP protocol data (ports and transport) where applicable
- Relevant links to vendor documentation and configuration baselines

---

## Screenshots

| Catalog Viewer | Component Editor |
|---|---|
| Browse and filter 1,150+ ISM controls by guideline group, class, or keyword | Search and filter components by name or type; write control implementation narratives |

| Capability Editor | SSP Editor |
|---|---|
| Inherit control responses from member components automatically | Document system characteristics and reference a profile baseline |

---

## Getting Started

### Requirements

- Python 3.10 or later
- tkinter (included with standard Python on Windows and macOS; on Linux install `python3-tk`)
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

No installation steps beyond the optional packages above are required. All core functionality uses Python's standard library. If an optional package is not installed, the feature that depends on it is gracefully disabled with an informative message rather than crashing.

### OSCAL Schema Zips

The `oscal/` folder should contain one or more OSCAL release zip files named `oscal-<version>.zip`, for example:

```
oscal/
    oscal-1.2.2.zip
    oscal-1.2.0.zip
    oscal-1.1.2.zip
```

Download releases from the [OSCAL GitHub releases page](https://github.com/usnistgov/OSCAL/releases). The application scans this folder at startup and populates the version selector in the toolbar automatically.

---

## Recommended Workflow

### Building a component library

1. Open your OSCAL catalog (e.g. the ISM catalog) using **Open Catalog** in the toolbar
2. Optionally open a profile to filter controls to your baseline
3. Switch to the **Component Editor** tab
4. Load the example components from `example-data/components/` using **📁 Open Folder** as a starting point
5. For each system component unique to your environment:
   - Add a component, set its type and description
   - Add links to vendor documentation, CVE advisories, and configuration baselines
   - Document TCP/UDP protocols the component uses
   - Work through the control list in Section 9, writing implementation narratives
   - Save as an individual component file (e.g. `hardware_Palo_Alto_Firewall.json`)
6. Over time, build a library of component files in a dedicated folder

### Building a capability library

1. Open your component files using **Open Folder** in the Capability Editor
2. Create a new capability (e.g. "Perimeter Defence")
3. Add the relevant components as members — their control responses are inherited automatically
4. Review the inherited responses; add capability-level narratives for controls that span multiple components
5. Save the capability (e.g. `capability_Perimeter_Defence.json`) — it bundles its member components so it is self-contained

### Producing an SSP

1. Open the catalog and profile for the target network's classification
2. In the SSP Editor, fill in the system characteristics, boundary, and information types
3. Reference components and capabilities from your library in the system-implementation section
4. Save — the SSP records the profile provenance in its back-matter so auditors can verify the baseline used

---

## OSCAL Document Types Supported

| Document Type | Read | Write | Notes |
|---|:---:|:---:|---|
| Catalog | ✅ | — | Any OSCAL catalog; tested with ISM |
| Profile | ✅ | — | Filters the control list to a baseline |
| Component Definition | ✅ | ✅ | One component per file; includes links, protocols, and control implementations |
| Capability Definition | ✅ | ✅ | Bundles member components; automatic control inheritance |
| System Security Plan | ✅ | ✅ | Metadata, characteristics, information types; control responses in progress |
| Plan of Action & Milestones | ✅ | ✅ | Track findings, risks, and remediation milestones |

---

## Project Structure

```
OSCAL-User-Toolkit/
├── main.py                                  # Entry point — run this to start the app
├── oscal_user_toolkit/
│   ├── __init__.py                          # Package marker (empty)
│   ├── models.py                            # All data logic — no GUI code
│   ├── app.py                               # Main window, toolbar, and shared state
│   ├── catalog_tab.py                       # Catalog Viewer tab
│   ├── component_tab.py                     # Component Editor tab
│   ├── capability_tab.py                    # Capability Editor tab
│   ├── ssp_tab.py                           # SSP Editor tab
│   └── poam_tab.py                          # POAM Editor tab
├── oscal/                                   # OSCAL schema release zips
│   ├── oscal-1.2.2.zip
│   ├── oscal-1.2.0.zip
│   └── oscal-1.1.2.zip
├── example-data/
│   ├── ISM_catalog.json                     # Australian ISM catalog
│   ├── ISM_NON_CLASSIFIED-baseline_profile.json
│   ├── ISM_NON_CLASSIFIED-baseline-resolved-profile_catalog.json
│   ├── ssp_ERN.json                         # Example SSP
│   ├── poam_ERN_POAM.json                   # Example POAM
│   ├── microsoft_office_component.json      # Comprehensive example components
│   ├── windows_server_2022_component.json
│   ├── windows_11_component.json
│   ├── servicedesk_plus_component.json
│   ├── mssql_server_component.json
│   └── components/                          # 41 ready-to-use component files
│       ├── hardware_*.json
│       ├── interconnection_*.json
│       ├── operating-system_*.json
│       ├── policy_*.json
│       ├── service_*.json
│       └── software_*.json
├── oscal_user_toolkit_design_document.md    # Full technical design document
└── README.md
```

The codebase follows a strict two-layer separation: `models.py` contains all data parsing, conversion, and validation logic with no GUI code; the tab files contain all GUI code with no direct JSON manipulation. See the [design document](oscal_user_toolkit_design_document.md) for a full architecture description.

---

## Design and Authorship

**Designed by:** Justin Baldock  
**Built with:** [Claude AI](https://claude.ai) (Anthropic) — the application code, architecture, and documentation were written by Claude AI working interactively with the designer

This project is an example of human-AI collaboration in software development: the domain expertise, product vision, and design decisions came from the designer; the implementation, architecture, code structure, and documentation were produced by Claude AI through an iterative conversation.

---

## OSCAL Standard

OSCAL is an open standard developed by [NIST](https://www.nist.gov/) (National Institute of Standards and Technology). It provides machine-readable formats for security control catalogues, baselines (profiles), component definitions, system security plans, and assessment artefacts.

- [OSCAL documentation](https://pages.nist.gov/OSCAL/)
- [OSCAL GitHub repository](https://github.com/usnistgov/OSCAL)
- [Australian ISM (Information Security Manual)](https://www.cyber.gov.au/resources-business-and-government/essential-cyber-security/ism)

---

## Contributing

Contributions, bug reports, and feature suggestions are welcome. Please open an issue or pull request on GitHub.

---

## Licence

This project is released under the [GNU General Public License v3.0](LICENSE) (GPLv3).

You are free to use, study, modify, and distribute this software, provided that any distributed modifications or derivative works are also released under the GPLv3. See the [LICENSE](LICENSE) file for the full licence text.
