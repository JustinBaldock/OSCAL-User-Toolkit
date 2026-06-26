# OSCAL User Toolkit

> **Designed by Justin Baldock · Built with Claude AI**

A desktop application for creating, editing, and managing [OSCAL](https://pages.nist.gov/OSCAL/) (Open Security Controls Assessment Language) documents — purpose-built for large organisations that operate multiple separate networks and need to reduce the effort of producing System Security Plans and supporting audit evidence.

---

## Why this tool exists

Large organisations — defence agencies, government departments, critical infrastructure operators — typically run many separate networks, each requiring its own System Security Plan (SSP). Without tooling, teams repeat the same work for every network: documenting the same firewall, the same identity platform, the same patching process, over and over, with slight variations.

OSCAL solves this at the standard level by separating **what a component does** from **which system it appears in**. The OSCAL User Toolkit makes that practical:

- Define a component once (e.g. "Palo Alto Firewall — stateful packet inspection") and describe how it satisfies each relevant security control
- Group components into reusable **capabilities** (e.g. "Perimeter Defence" or "Identity and Access Management")
- Reference those components and capabilities in each SSP rather than rewriting the implementation narrative from scratch
- When a component is patched or reconfigured, update it in one place — every SSP that references it benefits immediately

The result is a library of audited, reusable building blocks. As the library grows, producing a new SSP shifts from weeks of writing to days of composition.

---

## Features

### Catalog Viewer
- Load any OSCAL catalog (tested with the Australian ISM)
- Filter controls by **class**, **guideline group**, or **keyword search**
- Browse the full control hierarchy — top-level guideline group, sub-category, and topic shown for every control
- Select a control to see its full statement, applicability, revision history, and Essential Eight mapping in a detail panel
- Apply a **profile** to restrict the view to a specific baseline (e.g. non-classified, SECRET)

### Component Editor
- Create OSCAL Component Definition files describing how a system component implements security controls
- Supports all OSCAL component types: software, hardware, service, policy, process, procedure, plan, guidance, standard, validation, interconnection
- Write implementation narratives for individual controls with live dot indicators (● written / ○ not yet)
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
- Capture system characteristics, authorization boundary, network architecture, and data flow descriptions
- Manage roles, parties, and information types with CIA impact levels
- Reference a loaded profile so the SSP declares exactly which baseline it is assessed against
- Saves a self-documenting SSP that records the profile title, version, and filename in the back-matter section

### Schema Validation
- Bundled OSCAL release zips (1.1.2, 1.2.0, 1.2.2) — select the target version from the toolbar
- Catalog files are validated against the OSCAL schema when opened
- Capability files are validated before saving
- Validation warnings allow the user to proceed — real-world files sometimes have minor deviations

---

## Screenshots

| Catalog Viewer | Component Editor |
|---|---|
| Browse and filter 1,150+ ISM controls by guideline group, class, or keyword | Write control implementation narratives with live progress tracking |

| Capability Editor | SSP Editor |
|---|---|
| Inherit control responses from member components automatically | Document system characteristics and reference a profile baseline |

---

## Getting Started

### Requirements

- Python 3.10 or later
- tkinter (included with standard Python on Windows and macOS; on Linux install `python3-tk`)
- `jsonschema` *(optional)* — enables schema validation on open/save

```bash
pip install jsonschema
```

### Installation

```bash
git clone https://github.com/<your-org>/OSCAL-Processor.git
cd OSCAL-Processor
python main.py
```

No other installation steps are required. All core functionality uses Python's standard library.

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
4. For each system component (firewall, identity platform, SIEM, etc.):
   - Add a component, set its type and description
   - Work through the control list in Section 7, writing implementation narratives
   - Save as an individual component file (e.g. `hardware_Palo_Alto_Firewall.json`)
5. Over time, build a library of component files in a dedicated folder

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
| Component Definition | ✅ | ✅ | One component per file |
| Capability Definition | ✅ | ✅ | Bundles member components in the same file |
| System Security Plan | — | ✅ | Stage 1 (metadata + characteristics); Stage 2 (control responses) planned |

---

## Project Structure

```
OSCAL-Processor/
├── main.py                              # Entry point
├── oscal_user_toolkit/
│   ├── models.py                        # All data logic — no GUI code
│   ├── app.py                           # Main window and toolbar
│   ├── catalog_tab.py                   # Catalog Viewer tab
│   ├── component_tab.py                 # Component Editor tab
│   ├── capability_tab.py                # Capability Editor tab
│   └── ssp_tab.py                       # SSP Editor tab
├── oscal/                               # OSCAL schema release zips
│   ├── oscal-1.2.2.zip
│   └── ...
├── example-data/                        # Sample catalog and profile files
├── oscal_user_toolkit_design_document.md  # Full technical design document
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
