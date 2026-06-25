"""
component_tab.py
================
This file defines the ComponentTab class — the middle tab of the
OSCAL User Toolkit where users create and save OSCAL Component Definition
files.

WHAT IS AN OSCAL COMPONENT?
-----------------------------
A component describes a piece of a system that helps implement security
controls. Components can be:
  - Software  (e.g. an operating system, a web application)
  - Hardware  (e.g. a firewall, a server)
  - Service   (e.g. an authentication service, a logging service)
  - Policy    (e.g. an access control policy document)
  - Process   (e.g. a patch management process)
  - Procedure (e.g. a backup procedure)
  - Plan      (e.g. an incident response plan)
  - Guidance  (e.g. a configuration guide)
  - Standard  (e.g. a security standard)
  - Validation (e.g. a compliance validation activity)

Each component definition file can contain one or more components.
The file is saved as JSON and follows the OSCAL Component Definition
schema (oscal_component_metaschema.xml).

DESIGN PATTERN
--------------
ComponentTab inherits from tk.Frame, making it a proper GUI widget.
It manages all its own state and only talks to the rest of the app
through injected callback functions (get_catalog, get_profile,
set_status) — the same pattern used by CatalogTab and SSPTab.

The tab has two panes side by side:
  LEFT   — A list of components added to the current file
  RIGHT  — A form to edit the selected component's details
"""

import json       # Reading and writing JSON files
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path   # Cross-platform file path handling

# Import utility functions from our data models module
from .models import new_uuid, now_iso

# =============================================================================
# CONSTANTS — Allowed values defined by the OSCAL Component schema
# These lists populate dropdown menus so users pick valid values.
# =============================================================================

# Component types defined in the OSCAL component metaschema.
# Each type describes the nature of the component.
COMPONENT_TYPES = [
    "software",     # Implemented in code (applications, operating systems)
    "hardware",     # Physical or virtual hardware devices
    "service",      # An external or internal service (APIs, cloud services)
    "policy",       # A documented policy (e.g. access control policy)
    "process",      # A repeatable business or technical process
    "procedure",    # A step-by-step procedure document
    "plan",         # A formal plan document (e.g. incident response plan)
    "guidance",     # Guidance document (e.g. configuration guide)
    "standard",     # A technical or security standard
    "validation",   # A validation or audit activity
    "interconnection",  # A system interconnection
]

# Operational status values — describes the lifecycle state of the component
COMPONENT_STATUS = [
    "under-development",          # Being built or planned
    "operational",                # In active use
    "disposition",                # Being retired
    "other",                      # None of the above
]

# Role IDs that can be assigned to people responsible for the component.
# These come from the OSCAL allowed-values constraints in the schema.
RESPONSIBLE_ROLES = [
    "asset-owner",                # Person/org that owns the asset
    "asset-administrator",        # Person/org that administers the asset
    "security-operations",        # Security operations team
    "network-operations",         # Network operations team
    "incident-response",          # Incident response team
    "help-desk",                  # Help desk / support team
    "configuration-management",   # Configuration management team
    "maintainer",                 # Person/org maintaining the component
    "provider",                   # Person/org providing the component
    "system-owner",               # Overall system owner
    "isso",                       # Information System Security Officer
    "authorizing-official",       # Person who authorises the system
]

# Common property names allowed on components by the OSCAL schema.
# Properties add structured metadata to a component.
PROP_NAMES = [
    "asset-type",              # Type of asset (e.g. "os", "database")
    "asset-id",                # Asset identifier / tag number
    "asset-tag",               # Physical asset tag
    "public",                  # Is the component publicly accessible? (yes/no)
    "virtual",                 # Is the component virtualised? (yes/no)
    "implementation-point",    # internal or external to the system boundary
    "allows-authenticated-scan", # Does it allow authenticated scans? (yes/no)
    "baseline-configuration-name", # Name of the baseline configuration
    "release-date",            # Date the component was released
    "version",                 # Component version number
    "patch-level",             # Current patch level
    "model",                   # Hardware/software model identifier
    "fqdn",                    # Fully qualified domain name
    "uri",                     # URI identifying the component
    "scan-type",               # Type of security scan used
]

# Yes/No values used for boolean-style properties
YES_NO_VALUES = ["yes", "no"]

# Implementation point values
IMPL_POINT_VALUES = ["internal", "external"]

# Asset type values
ASSET_TYPE_VALUES = [
    "os",             # Operating system
    "database",       # Database system
    "web-server",     # Web server
    "dns-server",     # DNS server
    "email-server",   # Email server
    "directory-server", # Directory / LDAP server
    "pbx",            # Private Branch Exchange (telephony)
    "firewall",       # Firewall appliance or software
    "router",         # Network router
    "switch",         # Network switch
    "storage-array",  # Storage array / NAS / SAN
    "appliance",      # Dedicated hardware appliance
]


class ComponentTab(tk.Frame):
    """
    A self-contained OSCAL Component Definition editor panel.

    The tab is split into two panes:
      LEFT  — Component list showing all components in the current file,
              with New / Delete / Save File / Open File buttons.
      RIGHT — Component detail form for editing the selected component.

    Each component has:
      - Basic info:       title, type, description, purpose, remarks
      - Status:           operational status
      - Properties:       flexible key-value metadata table
      - Responsible Roles: who is accountable for this component
    """

    def __init__(self, parent, colors, get_catalog, get_profile, set_status):
        """
        Set up the ComponentTab panel.

        Parameters:
            parent      - The parent widget (the ttk.Notebook)
            colors      - Shared colour dictionary from app.py
            get_catalog - Callback: returns the loaded catalog dict or None
            get_profile - Callback: returns the loaded profile dict or None
            set_status  - Callback: updates the main window status bar
        """
        # Initialise the underlying tk.Frame
        super().__init__(parent, bg=colors["BG"])

        # Store references to things we were given
        self._colors      = colors
        self._get_catalog = get_catalog
        self._get_profile = get_profile
        self._set_status  = set_status

        # ── Component file state ──────────────────────────────────────────────
        # A component definition file contains metadata and a list of components.
        # We store everything here and only convert to OSCAL JSON on save.

        # File-level metadata
        self._file_uuid  = new_uuid()   # Unique ID for the whole file
        self._file_title = tk.StringVar(value="")
        self._file_version = tk.StringVar(value="1.0")

        # List of component dicts — each represents one OSCAL component.
        # When the user clicks a component in the left list, we load its
        # data into the right-hand form for editing.
        self._components = []

        # Index of the currently selected component in self._components,
        # or None if nothing is selected.
        self._selected_index = None

        # Track whether the file has unsaved changes
        self._dirty = False

        # Build all the GUI widgets
        self._build()

    # =========================================================================
    # PUBLIC API — called by app.py
    # =========================================================================

    def on_catalog_loaded(self):
        """
        Called by the app when a new catalog is loaded.
        Currently a no-op but available for future Stage 2 integration
        (e.g. populating control-id dropdowns from the catalog).
        """
        pass   # Nothing to do yet — placeholder for Stage 2

    # =========================================================================
    # PRIVATE BUILD METHODS
    # =========================================================================

    def _update_file_title(self, *_args):
        """
        Auto-generate the file title from the component type and title,
        then update both the toolbar display label and self._file_title.

        This method is also responsible for keeping the component list on
        the left in sync — whenever the type or title changes, the matching
        list entry is renamed immediately so it always reflects the current
        values without the user needing to click 'Apply'.

        This method is called automatically whenever the Component Title
        or Component Type fields change (via StringVar traces).

        The generated title format is:  "<type> - <title>"
        For example: "hardware - My Firewall"

        The generated filename format is: "<type>_<title_with_underscores>.json"
        For example: "hardware_My_Firewall.json"

        If either field is empty, a placeholder prompt is shown instead.
        """
        # Read the current values from both fields.
        # .strip() removes any leading/trailing whitespace the user may have typed.
        comp_type  = self._v_type.get().strip()
        comp_title = self._v_title.get().strip()

        if comp_type and comp_title:
            # Both fields have content — build the auto title
            # e.g. "hardware - My Firewall"
            auto_title = f"{comp_type} - {comp_title}"

            # Build a filesystem-safe filename:
            #   1. Replace spaces with underscores  ("My Firewall" → "My_Firewall")
            #   2. Combine type and sanitised title ("hardware_My_Firewall")
            safe_title = comp_title.replace(" ", "_")
            auto_filename = f"{comp_type}_{safe_title}.json"

            # Update the toolbar label — show both the human title and the filename
            self._file_title_lbl.config(
                text=f"{auto_title}  →  {auto_filename}",
                fg=self._colors["TEXT"],
                font=("Helvetica", 10),
            )

            # Store the generated title in _file_title so _build_oscal_document
            # can use it as the metadata title when saving.
            self._file_title.set(auto_title)

        elif comp_type or comp_title:
            # Only one field has content — show a partial prompt
            self._file_title_lbl.config(
                text="(enter both component type and title to generate filename)",
                fg=self._colors["SUBTEXT"],
                font=("Helvetica", 10, "italic"),
            )
            # Set a partial title so saving still has something to show
            self._file_title.set(comp_type or comp_title)

        else:
            # Neither field has content — show the initial placeholder
            self._file_title_lbl.config(
                text="(enter component type and title below)",
                fg=self._colors["SUBTEXT"],
                font=("Helvetica", 10, "italic"),
            )
            self._file_title.set("")

        # ── Keep the left-hand component list entry in sync ───────────────────
        # If a component is currently selected, update just that one row in the
        # Listbox so the user sees the new name immediately as they type.
        # We do this instead of rebuilding the whole list to avoid flicker and
        # losing the current selection.
        if self._selected_index is not None:
            # Build the display string the same way _refresh_list does
            title   = comp_title or "(untitled)"
            display = f"{title}  [{comp_type}]" if comp_type else title

            # Listbox.delete + insert is the standard way to update one entry.
            # We delete the old entry at the selected index and insert the new
            # text at the same position.
            self._comp_listbox.delete(self._selected_index)
            self._comp_listbox.insert(self._selected_index, display)

            # Restore the selection highlight (delete + insert clears it)
            self._comp_listbox.selection_set(self._selected_index)
            self._comp_listbox.see(self._selected_index)

    def _build(self):
        """
        Create the overall layout:
          - Top toolbar (New Component, Save File, Open File buttons)
          - Below: a horizontal split pane with list on left, form on right
        """
        self._build_toolbar()
        self._build_body()

    def _build_toolbar(self):
        """
        Create the tab toolbar with file-level controls and metadata fields.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)   # Fix the toolbar height at 52 pixels

        # ── File action buttons ───────────────────────────────────────────────
        tk.Button(
            tb, text="💾  Save File", command=self._save_file,
            bg=C["GREEN"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#8cd39a", activeforeground=C["BG"],
        ).pack(side="left", padx=12, pady=8)

        tk.Button(
            tb, text="📂  Open File", command=self._open_file,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(
            tb, text="🆕  New File", command=self._new_file,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(0, 12), pady=8)

        # ── Vertical separator ────────────────────────────────────────────────
        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=4, pady=6
        )

        # ── Auto-generated file title display ─────────────────────────────────
        # The file title is NOT typed manually — it is generated automatically
        # from the component type and title entered in the form below.
        # We show it here so the user can always see what the file will be named.
        tk.Label(
            tb, text="File:",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
        ).pack(side="left", padx=(8, 4))

        # This label is updated by _update_file_title() whenever the
        # component type or title fields change.
        self._file_title_lbl = tk.Label(
            tb, text="(enter component type and title below)",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._file_title_lbl.pack(side="left", padx=(0, 8))

        tk.Label(
            tb, text="  Version:",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
        ).pack(side="left", padx=(8, 4))

        tk.Entry(
            tb, textvariable=self._file_version, width=8,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", ipady=3, pady=10)

        # ── Status label (right side) ─────────────────────────────────────────
        self._status_lbl = tk.Label(
            tb, text="No file loaded",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=12)

    def _build_body(self):
        """
        Create the main body: a horizontal PanedWindow (split view) with
        the component list on the left and the detail form on the right.
        """
        C    = self._colors
        pane = tk.PanedWindow(
            self, orient="horizontal",
            bg=C["BG"], sashwidth=5, sashrelief="flat",
        )
        pane.pack(fill="both", expand=True)

        self._build_component_list(pane)
        self._build_detail_form(pane)

    def _build_component_list(self, pane):
        """
        Build the LEFT pane: a list of components with Add/Delete buttons.
        """
        C    = self._colors
        left = tk.Frame(pane, bg=C["SIDEBAR_BG"])
        pane.add(left, minsize=240, width=280)

        # ── Heading ───────────────────────────────────────────────────────────
        hdr = tk.Frame(left, bg=C["HEADER_BG"])
        hdr.pack(fill="x")
        tk.Label(
            hdr, text="⚙  Components",
            bg=C["HEADER_BG"], fg=C["ACCENT"],
            font=("Helvetica", 11, "bold"), anchor="w",
        ).pack(side="left", padx=10, pady=8)

        # ── Add / Delete buttons ──────────────────────────────────────────────
        btn_row = tk.Frame(left, bg=C["SIDEBAR_BG"])
        btn_row.pack(fill="x", padx=8, pady=6)

        tk.Button(
            btn_row, text="＋  Add Component",
            command=self._add_component,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BG"],
        ).pack(side="left")

        tk.Button(
            btn_row, text="✕ Delete",
            command=self._delete_component,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="right")

        # ── Component listbox ─────────────────────────────────────────────────
        # We use a Listbox here (simpler than Treeview for a single-column list)
        list_frame = tk.Frame(left, bg=C["SIDEBAR_BG"])
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._comp_listbox = tk.Listbox(
            list_frame,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"],
            selectbackground=C["ACCENT"], selectforeground=C["BG"],
            font=("Helvetica", 11), relief="flat",
            activestyle="none",   # Removes the dotted border on hover
            highlightthickness=0,
        )
        vsb = ttk.Scrollbar(
            list_frame, orient="vertical", command=self._comp_listbox.yview
        )
        self._comp_listbox.configure(yscrollcommand=vsb.set)
        self._comp_listbox.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # When the user clicks a component in the list, load it into the form
        self._comp_listbox.bind("<<ListboxSelect>>", self._on_list_select)

    def _build_detail_form(self, pane):
        """
        Build the RIGHT pane: a scrollable form for editing a component.
        The form is initially blank and populated when the user selects
        a component from the left list or adds a new one.
        """
        C     = self._colors
        right = tk.Frame(pane, bg=C["BG"])
        pane.add(right, minsize=500)

        # ── Canvas for scrolling ──────────────────────────────────────────────
        # The form can be longer than the visible area, so we wrap it in a
        # Canvas + Scrollbar (same pattern as the SSP Editor form).
        canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        # Inner frame that holds all the form widgets
        self._form_frame = tk.Frame(canvas, bg=C["BG"])
        self._form_win   = canvas.create_window(
            (0, 0), window=self._form_frame, anchor="nw"
        )

        # Update scroll region whenever the form grows or shrinks
        self._form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Keep the form as wide as the canvas panel
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._form_win, width=e.width)
        )
        self._detail_canvas = canvas

        # Mouse-wheel scrolling for the detail form
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Build the form widgets inside the inner frame
        self._build_form_widgets(self._form_frame)

        # Show a placeholder until the user selects a component
        self._show_form_placeholder()

    def _on_mousewheel(self, event):
        """
        Scroll the detail form when the user rolls the mouse wheel,
        but only when tab index 1 (this tab) is active.
        """
        try:
            nb = self.master
            if hasattr(nb, "index") and nb.index("current") == 1:
                self._detail_canvas.yview_scroll(
                    int(-1 * (event.delta / 120)), "units"
                )
        except Exception:
            pass

    def _build_form_widgets(self, parent):
        """
        Create all the form fields inside the scrollable detail pane.
        These widgets are always present; we show/hide the placeholder
        label to indicate whether a component is loaded for editing.
        """
        C = self._colors
        P = dict(padx=20)   # Standard horizontal padding for all sections

        # ── Helper: coloured section heading ──────────────────────────────────
        def section(title):
            """Add a dark header bar with a section title."""
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(16, 4))
            tk.Label(
                hdr, text=title,
                bg=C["HEADER_BG"], fg=C["ACCENT"],
                font=("Helvetica", 11, "bold"), anchor="w",
            ).pack(side="left", padx=10, pady=5)

        # ── Helper: single-line text entry ────────────────────────────────────
        def field(label, var, width=50):
            """
            Add a label + Entry widget row.
            'var' is a tk.StringVar — changes to the Entry update it automatically.
            """
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(
                row, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11), width=20, anchor="w",
            ).pack(side="left")
            tk.Entry(
                row, textvariable=var, width=width,
                bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                relief="flat", font=("Helvetica", 11),
                highlightthickness=1, highlightbackground=C["HEADER_BG"],
            ).pack(side="left", ipady=3, fill="x", expand=True)

        # ── Helper: dropdown (combobox) ────────────────────────────────────────
        def combo(label, var, values, width=30):
            """
            Add a label + read-only dropdown.
            'var' is a tk.StringVar linked to the combobox selection.
            """
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(
                row, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11), width=20, anchor="w",
            ).pack(side="left")
            ttk.Combobox(
                row, textvariable=var, values=values,
                state="readonly", width=width,
            ).pack(side="left")

        # ── Helper: multi-line text area ───────────────────────────────────────
        def textbox(label, height=4):
            """
            Add a label above a multi-line Text widget.
            Returns the Text widget so callers can read/write content.
            """
            tk.Label(
                parent, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11),
            ).pack(anchor="w", **P, pady=(6, 2))
            border = tk.Frame(
                parent, bg=C["HEADER_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            border.pack(fill="x", **P, pady=2)
            t = tk.Text(
                border,
                bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                relief="flat", font=("Helvetica", 11), height=height,
                wrap="word", padx=8, pady=6,
            )
            t.pack(fill="both")
            return t

        # ── Placeholder label (shown when no component is selected) ───────────
        self._placeholder_lbl = tk.Label(
            parent,
            text="Add a component using the '＋ Add Component' button,\n"
                 "or open an existing file with '📂 Open File'.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 12, "italic"),
            justify="center",
        )
        self._placeholder_lbl.pack(pady=60, padx=40)

        # ── Wrapper frame — hidden until a component is selected ──────────────
        # We put all real form content inside this frame so we can
        # show/hide it as a unit by packing/unpacking it.
        self._form_content = tk.Frame(parent, bg=C["BG"])
        # (Not packed yet — shown by _show_component_form)

        # Work inside _form_content from now on
        parent = self._form_content

        # =============================================================
        # SECTION 1: BASIC INFORMATION
        # =============================================================
        section("1 ·  Basic Information")

        # StringVars for the simple text fields
        # We store them as instance variables so _collect() and _populate()
        # can read/write them without needing to find the widgets again.
        self._v_title   = tk.StringVar()
        self._v_purpose = tk.StringVar()

        field("Component Title *", self._v_title, width=50)

        # Component type dropdown — required by the OSCAL schema
        self._v_type = tk.StringVar(value=COMPONENT_TYPES[0])
        combo("Component Type *", self._v_type, COMPONENT_TYPES, width=28)

        # ── Auto-filename traces ───────────────────────────────────────────────
        # trace_add("write", callback) means: call callback whenever this
        # StringVar's value changes (i.e. the user types or picks from dropdown).
        # We attach the same callback to BOTH variables so updating either one
        # refreshes the generated filename in the toolbar.
        #
        # The *_args in _update_file_title absorbs the three arguments that
        # tkinter passes to every trace callback (variable name, index, mode).
        self._v_title.trace_add("write", self._update_file_title)
        self._v_type.trace_add("write",  self._update_file_title)

        field("Purpose", self._v_purpose, width=50)

        tk.Label(
            parent,
            text="  * Required fields",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        # =============================================================
        # SECTION 2: DESCRIPTION
        # =============================================================
        section("2 ·  Description")
        tk.Label(
            parent,
            text="  A description of the component, including information about its function.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)
        self._v_description = textbox("Component Description *", height=4)

        # =============================================================
        # SECTION 3: OPERATIONAL STATUS
        # =============================================================
        section("3 ·  Operational Status")
        tk.Label(
            parent,
            text="  The lifecycle state of this component.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        self._v_status  = tk.StringVar(value=COMPONENT_STATUS[0])
        self._v_remarks = tk.StringVar()

        combo("Status *", self._v_status, COMPONENT_STATUS, width=28)
        field("Status Remarks", self._v_remarks, width=50)

        # =============================================================
        # SECTION 4: PROPERTIES
        # =============================================================
        section("4 ·  Properties")
        tk.Label(
            parent,
            text="  Properties add structured metadata to the component.\n"
                 "  Each property has a name, a value, and an optional remark.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        # Frame containing the Add/Remove buttons + table
        prop_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        prop_frame.pack(fill="x", padx=20, pady=6)

        prop_btn_row = tk.Frame(prop_frame, bg=C["CARD_BG"])
        prop_btn_row.pack(fill="x", padx=8, pady=6)

        tk.Button(
            prop_btn_row, text="＋  Add Property",
            command=self._add_property,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="left")

        tk.Button(
            prop_btn_row, text="✕  Remove Selected",
            command=self._remove_property,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)

        # Treeview table showing existing properties
        prop_cols = ("name", "value", "remarks")
        self._prop_tree = ttk.Treeview(
            prop_frame, columns=prop_cols,
            show="headings", height=4, selectmode="browse",
        )
        self._prop_tree.heading("name",    text="Property Name", anchor="w")
        self._prop_tree.heading("value",   text="Value",         anchor="w")
        self._prop_tree.heading("remarks", text="Remarks",       anchor="w")
        self._prop_tree.column("name",    width=200, anchor="w")
        self._prop_tree.column("value",   width=180, anchor="w")
        self._prop_tree.column("remarks", width=200, anchor="w", stretch=True)
        self._prop_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =============================================================
        # SECTION 5: RESPONSIBLE ROLES
        # =============================================================
        section("5 ·  Responsible Roles")
        tk.Label(
            parent,
            text="  Define who is responsible for this component.\n"
                 "  Each role can optionally list party UUIDs (people/orgs).",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        role_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        role_frame.pack(fill="x", padx=20, pady=6)

        role_btn_row = tk.Frame(role_frame, bg=C["CARD_BG"])
        role_btn_row.pack(fill="x", padx=8, pady=6)

        tk.Button(
            role_btn_row, text="＋  Add Role",
            command=self._add_role,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="left")

        tk.Button(
            role_btn_row, text="✕  Remove Selected",
            command=self._remove_role,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)

        role_cols = ("role_id", "remarks")
        self._role_tree = ttk.Treeview(
            role_frame, columns=role_cols,
            show="headings", height=4, selectmode="browse",
        )
        self._role_tree.heading("role_id",  text="Role ID",  anchor="w")
        self._role_tree.heading("remarks",  text="Remarks",  anchor="w")
        self._role_tree.column("role_id",  width=240, anchor="w")
        self._role_tree.column("remarks",  width=340, anchor="w", stretch=True)
        self._role_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =============================================================
        # SECTION 6: REMARKS
        # =============================================================
        section("6 ·  Remarks  (optional)")
        tk.Label(
            parent,
            text="  Additional notes about this component.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)
        self._v_remarks_text = textbox("", height=3)

        # ── Save Component button (bottom of form) ────────────────────────────
        # This saves the form values back into the component dict in memory.
        # It does NOT write to disk — use 'Save File' for that.
        save_btn_row = tk.Frame(parent, bg=C["BG"])
        save_btn_row.pack(fill="x", padx=20, pady=(16, 8))
        tk.Button(
            save_btn_row,
            text="✔  Apply Component Changes",
            command=self._apply_component,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BG"],
        ).pack(side="left")
        tk.Label(
            save_btn_row,
            text="  (Saves to memory — use 'Save File' to write to disk)",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=8)

        # Bottom padding
        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # SHOW / HIDE PLACEHOLDER vs FORM
    # =========================================================================

    def _show_form_placeholder(self):
        """
        Hide the component editing form and show the placeholder message.
        Called when no component is selected.
        """
        # Unpack (hide) the form content frame
        self._form_content.pack_forget()
        # Show the placeholder label
        self._placeholder_lbl.pack(pady=60, padx=40)

    def _show_component_form(self):
        """
        Hide the placeholder and show the component editing form.
        Called when a component is selected or a new one is added.
        """
        # Hide the placeholder label
        self._placeholder_lbl.pack_forget()
        # Show the form content
        self._form_content.pack(fill="both", expand=True)

    # =========================================================================
    # COMPONENT LIST MANAGEMENT
    # =========================================================================

    def _refresh_list(self):
        """
        Rebuild the left-hand Listbox from self._components.
        Called after any change to the components list.
        """
        self._comp_listbox.delete(0, "end")   # Clear all existing entries

        for comp in self._components:
            # Display the component title (or a placeholder if blank)
            title   = comp.get("title", "").strip() or "(untitled)"
            c_type  = comp.get("type", "")
            # Show title + type in brackets, e.g. "My Firewall  [hardware]"
            display = f"{title}  [{c_type}]" if c_type else title
            self._comp_listbox.insert("end", display)

    def _on_list_select(self, _event=None):
        """
        Called when the user clicks a component in the left list.
        Saves any pending changes to the previously selected component,
        then loads the newly selected one into the form.
        """
        # selection() returns a tuple of selected indices (we allow only one)
        sel = self._comp_listbox.curselection()
        if not sel:
            return

        new_index = int(sel[0])

        # If there was a previous selection, save its current form state first
        # so we don't lose unsaved typing when switching between components.
        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        # Load the newly selected component's data into the form
        self._selected_index = new_index
        self._populate_from(new_index)
        self._show_component_form()

    def _add_component(self):
        """
        Create a new blank component, add it to the list, and select it.
        """
        # Build a minimal component dict with required defaults
        new_comp = {
            "uuid":        new_uuid(),
            "title":       "",
            "type":        COMPONENT_TYPES[0],   # Default to "software"
            "description": "",
            "purpose":     "",
            "status":      COMPONENT_STATUS[0],  # Default to "under-development"
            "status_remarks": "",
            "remarks":     "",
            "props":       [],   # List of property dicts
            "roles":       [],   # List of responsible-role dicts
        }
        self._components.append(new_comp)
        self._dirty = True

        # Rebuild the list widget to show the new entry
        self._refresh_list()

        # Automatically select the new component (last in the list)
        new_index = len(self._components) - 1
        self._comp_listbox.selection_clear(0, "end")
        self._comp_listbox.selection_set(new_index)
        self._comp_listbox.see(new_index)   # Scroll to make it visible

        # Save any pending changes from the previously selected component
        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        # Load the new blank component into the form
        self._selected_index = new_index
        self._populate_from(new_index)
        self._show_component_form()

        self._status_lbl.config(text="New component added", fg=self._colors["ACCENT"])

    def _delete_component(self):
        """
        Delete the currently selected component after asking for confirmation.
        """
        if self._selected_index is None:
            messagebox.showinfo("No selection", "Please select a component to delete.")
            return

        title = self._components[self._selected_index].get("title", "(untitled)")
        if not messagebox.askyesno(
            "Delete component?",
            f"Delete the component '{title}'? This cannot be undone."
        ):
            return

        # Remove from the list
        self._components.pop(self._selected_index)
        self._selected_index = None
        self._dirty = True

        # Rebuild the list and hide the form
        self._refresh_list()
        self._show_form_placeholder()
        self._status_lbl.config(
            text="Component deleted", fg=self._colors["SUBTEXT"]
        )

    # =========================================================================
    # FORM POPULATION AND DATA COLLECTION
    # =========================================================================

    def _populate_from(self, index):
        """
        Load the component at self._components[index] into the form widgets.

        Parameters:
            index - The integer index into self._components
        """
        comp = self._components[index]

        # ── Simple text fields (StringVar) ────────────────────────────────────
        self._v_title.set(comp.get("title", ""))
        self._v_type.set(comp.get("type", COMPONENT_TYPES[0]))
        self._v_purpose.set(comp.get("purpose", ""))
        self._v_status.set(comp.get("status", COMPONENT_STATUS[0]))
        self._v_remarks.set(comp.get("status_remarks", ""))

        # ── Multi-line Text widgets ────────────────────────────────────────────
        # Clear then insert — .get("1.0", "end-1c") would read content
        self._v_description.delete("1.0", "end")
        desc = comp.get("description", "")
        if desc:
            self._v_description.insert("1.0", desc)

        self._v_remarks_text.delete("1.0", "end")
        remarks = comp.get("remarks", "")
        if remarks:
            self._v_remarks_text.insert("1.0", remarks)

        # ── Properties table ──────────────────────────────────────────────────
        self._prop_tree.delete(*self._prop_tree.get_children())
        for prop in comp.get("props", []):
            self._prop_tree.insert("", "end", values=(
                prop.get("name", ""),
                prop.get("value", ""),
                prop.get("remarks", ""),
            ))

        # ── Responsible roles table ───────────────────────────────────────────
        self._role_tree.delete(*self._role_tree.get_children())
        for role in comp.get("roles", []):
            self._role_tree.insert("", "end", values=(
                role.get("role_id", ""),
                role.get("remarks", ""),
            ))

    def _collect_into(self, index):
        """
        Read all form widget values and store them in self._components[index].

        This is called before switching between components and before saving,
        to make sure the in-memory data matches what is shown on screen.

        Parameters:
            index - The integer index into self._components
        """
        comp = self._components[index]

        # Read StringVar fields (these update automatically, but we read
        # them explicitly for clarity)
        comp["title"]          = self._v_title.get().strip()
        comp["type"]           = self._v_type.get()
        comp["purpose"]        = self._v_purpose.get().strip()
        comp["status"]         = self._v_status.get()
        comp["status_remarks"] = self._v_remarks.get().strip()

        # Read multi-line Text widgets
        # "1.0" = start, "end-1c" = end minus the trailing newline character
        comp["description"] = self._v_description.get("1.0", "end-1c").strip()
        comp["remarks"]     = self._v_remarks_text.get("1.0", "end-1c").strip()

        # Properties are already stored in self._components[index]["props"]
        # by _add_property/_remove_property, so no need to re-read the tree.
        # Same for roles.

        self._dirty = True

    def _apply_component(self):
        """
        Save the current form values into the selected component's dict,
        then refresh the list (in case the title changed).

        This keeps everything in memory — it does NOT write to disk.
        Use 'Save File' to write the JSON file.
        """
        if self._selected_index is None:
            return

        self._collect_into(self._selected_index)
        self._refresh_list()   # Title may have changed

        # Restore the listbox selection (refresh clears it)
        self._comp_listbox.selection_set(self._selected_index)

        self._status_lbl.config(
            text="Component changes applied  (not yet saved to disk)",
            fg=self._colors["YELLOW"],
        )

    # =========================================================================
    # PROPERTY MANAGEMENT
    # =========================================================================

    def _add_property(self):
        """
        Show a dialog to collect property details and add a new row
        to the properties table.

        Properties are name/value pairs with an optional remark.
        The schema defines a specific set of allowed property names,
        but also allows others ("allow-other=yes" in the schema).
        """
        if self._selected_index is None:
            messagebox.showinfo("No component", "Please select or add a component first.")
            return

        result = self._property_dialog()
        if not result:
            return   # User cancelled

        # Add to the in-memory component dict
        self._components[self._selected_index]["props"].append(result)

        # Add a row to the table widget
        self._prop_tree.insert("", "end", values=(
            result["name"],
            result["value"],
            result.get("remarks", ""),
        ))
        self._dirty = True

    def _remove_property(self):
        """Remove the selected row from the properties table."""
        sel = self._prop_tree.selection()
        if not sel:
            return
        idx = self._prop_tree.index(sel[0])
        # Remove from in-memory list
        if self._selected_index is not None:
            self._components[self._selected_index]["props"].pop(idx)
        # Remove from the table widget
        self._prop_tree.delete(sel[0])
        self._dirty = True

    def _property_dialog(self, existing=None):
        """
        Show a modal dialog for adding or editing a property.

        The dialog shows:
          - A dropdown for the property name (from OSCAL schema)
          - A value field (with contextual options based on the name chosen)
          - An optional remarks field

        Parameters:
            existing - A dict of existing values to pre-fill (for editing),
                       or None for a new property.

        Returns:
            A dict {"name": ..., "value": ..., "remarks": ...}
            or None if the user cancelled.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Add Property")
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.grab_set()   # Make the dialog modal

        # ── Property Name dropdown ─────────────────────────────────────────────
        name_row = tk.Frame(dlg, bg=C["BG"])
        name_row.pack(fill="x", padx=20, pady=8)
        tk.Label(
            name_row, text="Property Name *",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), width=18, anchor="w",
        ).pack(side="left")
        v_name = tk.StringVar(value=(existing or {}).get("name", PROP_NAMES[0]))
        name_combo = ttk.Combobox(
            name_row, textvariable=v_name,
            values=PROP_NAMES,
            state="normal",   # Allow typing a custom name not in the list
            width=28,
        )
        name_combo.pack(side="left")

        # ── Value field — changes based on selected property name ─────────────
        # Some property names have a fixed set of allowed values (dropdowns);
        # others accept any text (free entry).
        value_row = tk.Frame(dlg, bg=C["BG"])
        value_row.pack(fill="x", padx=20, pady=4)
        tk.Label(
            value_row, text="Value *",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), width=18, anchor="w",
        ).pack(side="left")

        v_value    = tk.StringVar(value=(existing or {}).get("value", ""))
        # We'll swap between a Combobox and an Entry depending on the name chosen.
        # value_widget_frame holds whichever widget is currently shown.
        value_widget_frame = tk.Frame(value_row, bg=C["BG"])
        value_widget_frame.pack(side="left", fill="x", expand=True)

        # Create both widget types upfront; show/hide them as needed
        value_combo = ttk.Combobox(
            value_widget_frame, textvariable=v_value, state="readonly", width=28
        )
        value_entry = tk.Entry(
            value_widget_frame, textvariable=v_value, width=32,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )

        # Map property names to their allowed values (from the schema)
        # Keys not listed here use a free-text Entry instead.
        VALUE_OPTIONS = {
            "public":                   YES_NO_VALUES,
            "virtual":                  YES_NO_VALUES,
            "allows-authenticated-scan": YES_NO_VALUES,
            "implementation-point":     IMPL_POINT_VALUES,
            "asset-type":               ASSET_TYPE_VALUES,
        }

        def refresh_value_widget(*_):
            """
            Called when the user changes the property name dropdown.
            Swaps between a value dropdown and a free-text entry.
            """
            name = v_name.get()
            options = VALUE_OPTIONS.get(name)
            if options:
                # Show the combobox with the appropriate options
                value_entry.pack_forget()
                value_combo.configure(values=options)
                v_value.set(options[0])   # Pre-select the first option
                value_combo.pack(side="left")
            else:
                # Show the free-text entry
                value_combo.pack_forget()
                v_value.set("")
                value_entry.pack(side="left", ipady=3)

        # Wire up the name dropdown to refresh the value widget
        v_name.trace_add("write", refresh_value_widget)
        # Call once to set the initial state
        refresh_value_widget()

        # ── Remarks field (optional) ───────────────────────────────────────────
        rem_row = tk.Frame(dlg, bg=C["BG"])
        rem_row.pack(fill="x", padx=20, pady=4)
        tk.Label(
            rem_row, text="Remarks",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), width=18, anchor="w",
        ).pack(side="left")
        v_remarks = tk.StringVar(value=(existing or {}).get("remarks", ""))
        tk.Entry(
            rem_row, textvariable=v_remarks, width=32,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", ipady=3)

        # ── OK / Cancel buttons ────────────────────────────────────────────────
        result = {}

        def _ok():
            """Validate and close the dialog."""
            if not v_name.get().strip():
                messagebox.showwarning("Required", "Property Name is required.")
                return
            if not v_value.get().strip():
                messagebox.showwarning("Required", "Value is required.")
                return
            result["name"]    = v_name.get().strip()
            result["value"]   = v_value.get().strip()
            result["remarks"] = v_remarks.get().strip()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=C["BG"])
        btn_row.pack(pady=12)
        tk.Button(
            btn_row, text="  OK  ", command=_ok,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=10,
        ).pack(side="left", padx=8)
        tk.Button(
            btn_row, text="Cancel", command=dlg.destroy,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=10,
        ).pack(side="left")

        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # RESPONSIBLE ROLE MANAGEMENT
    # =========================================================================

    def _add_role(self):
        """
        Show a dialog to add a responsible role to the current component.
        """
        if self._selected_index is None:
            messagebox.showinfo("No component", "Please select or add a component first.")
            return

        result = self._role_dialog()
        if not result:
            return

        self._components[self._selected_index]["roles"].append(result)
        self._role_tree.insert("", "end", values=(
            result["role_id"],
            result.get("remarks", ""),
        ))
        self._dirty = True

    def _remove_role(self):
        """Remove the selected row from the responsible roles table."""
        sel = self._role_tree.selection()
        if not sel:
            return
        idx = self._role_tree.index(sel[0])
        if self._selected_index is not None:
            self._components[self._selected_index]["roles"].pop(idx)
        self._role_tree.delete(sel[0])
        self._dirty = True

    def _role_dialog(self):
        """
        Show a modal dialog to collect a responsible role entry.

        Returns:
            A dict {"role_id": ..., "remarks": ...} or None if cancelled.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Add Responsible Role")
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.grab_set()

        # Role ID dropdown with all allowed values from the OSCAL schema
        row1 = tk.Frame(dlg, bg=C["BG"])
        row1.pack(fill="x", padx=20, pady=8)
        tk.Label(
            row1, text="Role ID *",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), width=16, anchor="w",
        ).pack(side="left")
        v_role = tk.StringVar(value=RESPONSIBLE_ROLES[0])
        ttk.Combobox(
            row1, textvariable=v_role,
            values=RESPONSIBLE_ROLES,
            state="normal",   # Allow typing a custom role not in the list
            width=28,
        ).pack(side="left")

        # Optional remarks
        row2 = tk.Frame(dlg, bg=C["BG"])
        row2.pack(fill="x", padx=20, pady=4)
        tk.Label(
            row2, text="Remarks",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), width=16, anchor="w",
        ).pack(side="left")
        v_remarks = tk.StringVar()
        tk.Entry(
            row2, textvariable=v_remarks, width=32,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", ipady=3)

        result = {}

        def _ok():
            if not v_role.get().strip():
                messagebox.showwarning("Required", "Role ID is required.")
                return
            result["role_id"]  = v_role.get().strip()
            result["remarks"]  = v_remarks.get().strip()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=C["BG"])
        btn_row.pack(pady=12)
        tk.Button(
            btn_row, text="  OK  ", command=_ok,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=10,
        ).pack(side="left", padx=8)
        tk.Button(
            btn_row, text="Cancel", command=dlg.destroy,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=10,
        ).pack(side="left")

        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # OSCAL JSON CONVERSION
    # =========================================================================

    def _build_oscal_document(self):
        """
        Convert the in-memory component list into a valid OSCAL
        Component Definition JSON document (as a Python dictionary).

        The structure follows the oscal_component_metaschema.xml schema:
          component-definition
            metadata
            components[]
              uuid, type, title, description, purpose
              status (as a prop)
              props[]
              responsible-roles[]
              remarks
        """
        now = now_iso()

        # ── Build the components list ─────────────────────────────────────────
        oscal_components = []
        for comp in self._components:
            # Start with the mandatory fields
            c = {
                "uuid":        comp["uuid"],
                "type":        comp.get("type", "software"),
                "title":       comp.get("title", ""),
                "description": comp.get("description", ""),
            }

            # Optional fields — only include if the user provided a value
            if comp.get("purpose"):
                c["purpose"] = comp["purpose"]

            # ── Props — from user-added properties ─────────────────────────
            # We also add the operational status as a prop, which is the
            # standard OSCAL way to convey component status.
            props = []

            # Add status as a prop if provided
            if comp.get("status"):
                props.append({
                    "name":  "operational-status",
                    "value": comp["status"],
                    # Include remarks on the status prop if provided
                    **({"remarks": comp["status_remarks"]}
                       if comp.get("status_remarks") else {}),
                })

            # Add user-defined properties
            for prop in comp.get("props", []):
                entry = {
                    "name":  prop["name"],
                    "value": prop["value"],
                }
                if prop.get("remarks"):
                    entry["remarks"] = prop["remarks"]
                props.append(entry)

            if props:
                c["props"] = props

            # ── Responsible roles ──────────────────────────────────────────
            roles_list = []
            for role in comp.get("roles", []):
                r = {"role-id": role["role_id"]}
                if role.get("remarks"):
                    r["remarks"] = role["remarks"]
                roles_list.append(r)

            if roles_list:
                c["responsible-roles"] = roles_list

            # ── Remarks ───────────────────────────────────────────────────
            if comp.get("remarks"):
                c["remarks"] = comp["remarks"]

            oscal_components.append(c)

        # ── Assemble the full OSCAL document ──────────────────────────────────
        doc = {
            "component-definition": {
                "uuid": self._file_uuid,
                "metadata": {
                    "title":         self._file_title.get().strip() or "Component Definition",
                    "last-modified": now,
                    "version":       self._file_version.get().strip() or "1.0",
                    "oscal-version": "1.1.2",   # OSCAL schema version we target
                },
                # Only include the components key if there are components to add
                **({"components": oscal_components} if oscal_components else {}),
            }
        }
        return doc

    def _parse_oscal_document(self, data):
        """
        Parse a saved OSCAL Component Definition JSON document back into
        our internal component list format.

        This is the reverse of _build_oscal_document — it lets users
        re-open a saved file to continue editing.

        Parameters:
            data - A Python dictionary from json.load() of a saved file.
        """
        root = data.get("component-definition", {})
        meta = root.get("metadata", {})

        # Restore file-level metadata
        self._file_uuid = root.get("uuid", new_uuid())
        self._file_title.set(meta.get("title", ""))
        self._file_version.set(meta.get("version", "1.0"))

        # Update the toolbar display label to show the loaded file's title.
        # When the user selects a component from the list, _update_file_title
        # will fire and overwrite this — that is the correct behaviour.
        loaded_title = meta.get("title", "")
        if loaded_title:
            self._file_title_lbl.config(
                text=loaded_title,
                fg=self._colors["TEXT"],
                font=("Helvetica", 10),
            )
        else:
            self._file_title_lbl.config(
                text="(enter component type and title below)",
                fg=self._colors["SUBTEXT"],
                font=("Helvetica", 10, "italic"),
            )

        # ── Parse each component ──────────────────────────────────────────────
        self._components = []
        for c in root.get("components", []):
            # Read props back, separating the status prop from user-defined ones
            all_props = c.get("props", [])
            status_prop = next(
                (p for p in all_props if p.get("name") == "operational-status"),
                None
            )
            # Everything except the status prop goes into user properties
            user_props = [
                {"name": p["name"], "value": p["value"],
                 "remarks": p.get("remarks", "")}
                for p in all_props
                if p.get("name") != "operational-status"
            ]

            # Read responsible roles
            roles = [
                {"role_id": r.get("role-id", ""), "remarks": r.get("remarks", "")}
                for r in c.get("responsible-roles", [])
            ]

            comp = {
                "uuid":           c.get("uuid", new_uuid()),
                "title":          c.get("title", ""),
                "type":           c.get("type", COMPONENT_TYPES[0]),
                "description":    c.get("description", ""),
                "purpose":        c.get("purpose", ""),
                "status":         status_prop["value"] if status_prop else COMPONENT_STATUS[0],
                "status_remarks": status_prop.get("remarks", "") if status_prop else "",
                "remarks":        c.get("remarks", ""),
                "props":          user_props,
                "roles":          roles,
            }
            self._components.append(comp)

    # =========================================================================
    # FILE ACTIONS (Save, Open, New)
    # =========================================================================

    def _validate(self):
        """
        Check that the file is ready to save.

        Returns a list of error strings.
        An empty list means everything is valid.
        """
        errors = []

        # The file must have a title
        if not self._file_title.get().strip():
            errors.append("File Title is required (in the toolbar above).")

        # There must be at least one component
        if not self._components:
            errors.append("At least one component must be added.")

        # Each component must have a title and description
        for i, comp in enumerate(self._components, start=1):
            if not comp.get("title", "").strip():
                errors.append(f"Component {i}: Title is required.")
            if not comp.get("description", "").strip():
                errors.append(f"Component {i}: Description is required.")

        return errors

    def _save_file(self):
        """
        Validate and save all components to an OSCAL Component Definition
        JSON file chosen by the user.

        The file is named after the file title by default.
        """
        # First, save the currently displayed form into its component dict
        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        # Validate
        errors = self._validate()
        if errors:
            messagebox.showerror(
                "Cannot save",
                "Please fix the following before saving:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        # Suggest a filename based on the auto-generated name in the toolbar.
        # _update_file_title() keeps self._file_title in sync with the type
        # and title fields, so we derive the filename the same way.
        comp_type  = self._v_type.get().strip()  if self._v_type  else ""
        comp_title = self._v_title.get().strip() if self._v_title else ""

        if comp_type and comp_title:
            # Build the same safe filename as _update_file_title does
            safe_title    = comp_title.replace(" ", "_")
            initial_file  = f"{comp_type}_{safe_title}.json"
        else:
            # Fall back to a generic name if fields are somehow empty
            initial_file  = "component_definition.json"

        path = filedialog.asksaveasfilename(
            title="Save OSCAL Component Definition",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=initial_file,
        )
        if not path:
            return   # User cancelled

        # Build the OSCAL document structure and write it to disk
        doc = self._build_oscal_document()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        self._dirty = False
        fname = Path(path).name
        self._status_lbl.config(
            text=f"Saved: {fname}", fg=self._colors["GREEN"]
        )
        self._set_status(f"Component file saved: {fname}")
        messagebox.showinfo("Saved", f"Component definition saved:\n{path}")

    def _open_file(self):
        """
        Ask the user to select a saved OSCAL Component Definition JSON file
        and load it for editing.
        """
        # Warn if there are unsaved changes
        if self._dirty and self._components:
            if not messagebox.askyesno(
                "Unsaved changes",
                "You have unsaved changes. Open a new file and discard them?"
            ):
                return

        path = filedialog.askopenfilename(
            title="Open OSCAL Component Definition",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showerror("Failed to open file", str(exc))
            return

        # Validate that this is actually a component definition file
        if "component-definition" not in data:
            messagebox.showerror(
                "Invalid file",
                "Missing 'component-definition' key — not an OSCAL Component Definition."
            )
            return

        # Parse the file into our internal format
        self._parse_oscal_document(data)

        # Reset selection and rebuild the list
        self._selected_index = None
        self._refresh_list()
        self._show_form_placeholder()

        self._dirty = False
        fname = Path(path).name
        self._status_lbl.config(text=f"Opened: {fname}", fg=self._colors["BLUE"])
        self._set_status(f"Component file opened: {fname}")

    def _new_file(self):
        """
        Clear everything and start a fresh component definition file.
        """
        if self._dirty and self._components:
            if not messagebox.askyesno(
                "Unsaved changes",
                "You have unsaved changes. Start a new file and discard them?"
            ):
                return

        # Reset all state to defaults
        self._file_uuid  = new_uuid()
        self._file_title.set("")
        self._file_version.set("1.0")
        self._components      = []
        self._selected_index  = None
        self._dirty           = False

        # Reset the toolbar filename display to its placeholder text
        self._file_title_lbl.config(
            text="(enter component type and title below)",
            fg=self._colors["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )

        # Clear the list and hide the form
        self._refresh_list()
        self._show_form_placeholder()

        self._status_lbl.config(
            text="New file  (unsaved)", fg=self._colors["SUBTEXT"]
        )
        self._set_status("New component definition file started.")
