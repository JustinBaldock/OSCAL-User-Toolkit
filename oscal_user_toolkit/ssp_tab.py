"""
ssp_tab.py
==========
This file defines the SSPTab class — the right-hand tab of the
OSCAL User Toolkit where users create and edit System Security Plans (SSPs).

An SSP is a formal document that describes a system's security controls,
who is responsible for them, and how they are implemented. The OSCAL
standard defines a JSON schema for SSPs so they can be machine-readable.

DESIGN PATTERN
--------------
SSPTab inherits from tk.Frame, so it IS a GUI widget. It owns all of
its own form fields, tables, and buttons. It does NOT directly access
the catalog or profile — instead it calls callback functions that the
main app provides. This keeps the tab loosely coupled to the rest of
the app (changes in one place do not break the other).

Injected callbacks:
    get_profile()   Returns the loaded profile dict, or None
    get_catalog()   Returns the loaded catalog dict, or None
    set_status(msg) Updates the main window's status bar
"""

import json        # Reading and writing JSON files
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path   # Cross-platform file path handling

# Import our data functions from the models module.
# The dot before 'models' means "look in the same package folder".
from .models import (
    empty_ssp,         # Creates a blank SSP dictionary
    build_oscal_ssp,   # Converts our dict to OSCAL JSON format
    build_ssp_docx,    # Converts our dict to a Word (.docx) document
    parse_ssp_file,    # Reads a saved SSP back into our dict format
    validate_ssp,      # Checks required fields before saving
    new_uuid,          # Generates a unique ID string
    refresh_ctrl_list, # Shared All/Applied control-list renderer (Section 9)
)


# =============================================================================
# CONSTANTS — allowed values from the OSCAL SSP schema
# =============================================================================

# Component type enum for SSP system-implementation components (Section 8).
# Note this differs from the component-definition enum: an SSP may NOT use
# "this-system" here (that one is auto-generated), so it is omitted.
SSP_COMPONENT_TYPES = [
    "software", "hardware", "service", "policy", "physical",
    "process-procedure", "plan", "guidance", "standard",
    "validation", "network", "system", "interconnection",
]

# implementation-status state enum for a by-component entry (Section 9).
IMPL_STATUS_VALUES = [
    "implemented", "partial", "planned", "alternative", "not-applicable",
]

# Operational status enum for an SSP component's status.state (Section 8).
SSP_COMPONENT_STATUS = [
    "under-development", "operational", "disposition", "other",
]


class SSPTab(tk.Frame):
    """
    A self-contained SSP editor panel.

    The panel contains a scrollable form divided into nine sections:
        1. SSP Metadata
        2. System Characteristics
        3. Authorization Boundary
        4. Network Architecture & Data Flow (optional)
        5. Information Types (table)
        6. Roles (table)
        7. Parties / People & Organisations (table)
        8. System Components (table + import)
        9. Control Implementations (control list + by-component entries)
    """

    def __init__(self, parent, colors, get_profile, get_catalog, set_status,
                 get_components=None):
        """
        Set up the SSPTab panel.

        Parameters:
            parent         - The parent widget (the ttk.Notebook)
            colors         - Shared colour dictionary from app.py
            get_profile    - Callback: returns the loaded profile dict or None
            get_catalog    - Callback: returns the loaded catalog dict or None
            set_status     - Callback: set_status("message") updates the status bar
            get_components - Optional callback returning ComponentTab's live list
                             of component dicts, used to import components into
                             Section 8. Defaults to a no-op returning an empty
                             list so the tab works even if the hook is not wired.
        """
        super().__init__(parent, bg=colors["BG"])

        # Store the injected dependencies
        self._colors      = colors
        self._get_profile = get_profile
        self._get_catalog = get_catalog
        self._set_status  = set_status
        self._get_components = get_components or (lambda: [])

        # The SSP data is stored as a plain Python dictionary.
        # All form widgets read from and write to this dictionary.
        self._ssp = empty_ssp()

        # ── Section 8 & 9 working state ───────────────────────────────────────
        # These mirror the lists inside self._ssp while the form is open, so the
        # tables and dialogs can mutate them directly without touching the
        # canonical dict until _collect() runs.
        self._ssp_components = []   # mirrors ssp["components"]
        self._ssp_ctrl_impls = []   # mirrors ssp["ctrl_implementations"]
        self._sel_comp_index = None # selected component row in Section 8
        self._sel_ctrl_id    = None # selected control id in Section 9

        # _ssp_vars holds tkinter StringVar objects, one per form text field.
        # A StringVar is a special variable that automatically updates the
        # widget it is linked to whenever its value changes.
        self._ssp_vars = {}

        # Build the GUI
        self._build()

        # Show the correct profile status in the toolbar right away
        self.refresh_profile_box()

    # =========================================================================
    # PUBLIC API
    # Called by the main app when something outside this tab changes.
    # =========================================================================

    def refresh_profile_box(self):
        """
        Update the profile info box in the SSP toolbar to reflect the
        currently loaded profile.

        Called by app.py after the user loads or clears a profile,
        so the SSP tab always shows current information.
        """
        C = self._colors
        p = self._get_profile()   # Ask the app what profile is loaded

        if p:
            # Build a summary string with all available profile details
            label = p.get("title", "Unknown profile")
            if p.get("version") and p["version"] != "—":
                label += f"  (v{p['version']})"
            if p.get("oscal_version") and p["oscal_version"] != "—":
                label += f"  |  OSCAL {p['oscal_version']}"
            if p.get("ids"):
                label += f"  |  {len(p['ids'])} controls"
            if p.get("filepath"):
                # Path().name gives just the filename without the directory
                label += f"  |  {Path(p['filepath']).name}"
            self._profile_lbl.config(text=label, fg=C["YELLOW"])
        else:
            # No profile loaded — show a warning in red
            self._profile_lbl.config(
                text="⚠  No profile loaded — open a profile before saving the SSP",
                fg=C["RED"],
            )

    # =========================================================================
    # PRIVATE BUILD METHODS
    # These create all the GUI widgets. They are called once in __init__.
    # =========================================================================

    def _build(self):
        """Top-level build: create the toolbar then the scrollable form."""
        self._build_toolbar()
        self._build_form_canvas()

    def _build_toolbar(self):
        """
        Create the SSP tab's own toolbar with Save, Open, New buttons
        and a profile info box.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)   # Prevent child widgets resizing the toolbar

        # ── Action buttons ────────────────────────────────────────────────────
        tk.Button(
            tb, text="💾  Save SSP", command=self._save,
            bg=C["GREEN"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#8cd39a", activeforeground=C["BG"],
        ).pack(side="left", padx=12, pady=8)

        tk.Button(
            tb, text="📂  Open SSP", command=self._open,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(
            tb, text="🆕  New SSP", command=self._new,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(
            tb, text="📄  Export DOCX", command=self._export_docx,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(0, 8), pady=8)

        # ── Visual separator line ─────────────────────────────────────────────
        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=8, pady=6
        )

        # ── Profile info box ──────────────────────────────────────────────────
        # This box always shows which profile is linked to the SSP.
        prof_box = tk.Frame(
            tb, bg=C["SIDEBAR_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"]
        )
        prof_box.pack(side="left", fill="y", pady=6, padx=(0, 8))

        tk.Label(
            prof_box, text="🔖 Profile:",
            bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "bold"),
        ).pack(side="left", padx=(10, 4))

        # _profile_lbl is updated by refresh_profile_box()
        self._profile_lbl = tk.Label(
            prof_box, text="",
            bg=C["SIDEBAR_BG"], font=("Helvetica", 9),
        )
        self._profile_lbl.pack(side="left", padx=(0, 10))

        # ── Save status label ─────────────────────────────────────────────────
        # Shows "Saved: filename.json" or "SSP not saved"
        self._status_lbl = tk.Label(
            tb, text="SSP not saved",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="left", padx=16)

    def _build_form_canvas(self):
        """
        Create a scrollable canvas that holds all the SSP form sections.

        We need a canvas (rather than a plain Frame) because the form is
        longer than the screen and needs to scroll vertically.
        The actual form widgets live inside a Frame placed inside the canvas.
        """
        C      = self._colors
        canvas = tk.Canvas(self, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        # Create the inner frame and place it at the top-left of the canvas
        form = tk.Frame(canvas, bg=C["BG"])
        win  = canvas.create_window((0, 0), window=form, anchor="nw")

        # Update scroll region when form height changes (fields added/removed)
        form.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Stretch the form to match the canvas width (so it fills the tab)
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(win, width=e.width)
        )

        # Keep a reference to the canvas so _on_mousewheel can scroll it
        self._canvas = canvas

        # Mouse wheel scrolling — only scroll when this tab is active
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Now build all the form sections inside the inner frame
        self._build_form(form)

    def _on_mousewheel(self, event):
        """
        Scroll the form canvas when the user rolls the mouse wheel, but only
        when the SSP tab is the currently selected one.

        bind_all means this fires regardless of which tab is visible, so we
        compare nb.select() against str(self) to confirm THIS tab is active.
        That is resilient to tab reordering — unlike hardcoding a tab index,
        which silently breaks if tabs are added, removed, or reordered.
        """
        try:
            nb = self.master
            if hasattr(nb, "select") and nb.select() == str(self):
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass   # Silently ignore any errors (e.g. during startup)

    # =========================================================================
    # FORM BUILDING
    # _build_form() lays out all the sections using small helper functions
    # (section, field, textbox, combo) to avoid repetitive code.
    # =========================================================================

    def _build_form(self, parent):
        """
        Build all seven SSP form sections inside the scrollable form frame.

        Parameters:
            parent - The tk.Frame inside the scroll canvas
        """
        C = self._colors
        P = dict(padx=28)   # Standard left/right padding for all sections

        # ── Local helper: section header ──────────────────────────────────────
        def section(title):
            """Add a coloured section heading bar."""
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(20, 4))
            tk.Label(
                hdr, text=title,
                bg=C["HEADER_BG"], fg=C["ACCENT"],
                font=("Helvetica", 12, "bold"), anchor="w",
            ).pack(side="left", padx=12, pady=6)

        # ── Local helper: single-line text entry field ────────────────────────
        def field(label, key, width=50, default=""):
            """
            Add a label + text entry row to the form.

            Parameters:
                label   - The field label shown to the left
                key     - The key in self._ssp_vars and self._ssp dicts
                width   - Width of the entry box in characters
                default - Pre-filled value (used for version number etc.)
            """
            # StringVar links the Entry widget to a Python variable.
            # When the user types, the var updates automatically.
            v = tk.StringVar(value=default)
            self._ssp_vars[key] = v
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(
                row, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11), width=22, anchor="w",
            ).pack(side="left")
            tk.Entry(
                row, textvariable=v,
                bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                relief="flat", font=("Helvetica", 11), width=width,
                highlightthickness=1, highlightbackground=C["HEADER_BG"],
            ).pack(side="left", ipady=3)   # ipady adds inner vertical padding

        # ── Local helper: multi-line text area ────────────────────────────────
        def textbox(label, height=4):
            """
            Add a label + multi-line Text widget for longer descriptions.

            Returns the Text widget so the caller can read/write its content.
            """
            tk.Label(
                parent, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11),
            ).pack(anchor="w", **P, pady=(6, 2))
            # A thin frame acts as a visible border around the text widget
            frame = tk.Frame(
                parent, bg=C["HEADER_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            frame.pack(fill="x", **P, pady=3)
            t = tk.Text(
                frame,
                bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                relief="flat", font=("Helvetica", 11), height=height,
                wrap="word",   # Wrap long lines at word boundaries
                padx=8, pady=6,
            )
            t.pack(fill="both")
            return t   # Return so the caller can .get() and .insert() later

        # ── Local helper: dropdown (combobox) ─────────────────────────────────
        def combo(label, key, values, default, width=30):
            """
            Add a label + read-only dropdown (combobox) field.

            Parameters:
                values  - List of strings shown in the dropdown
                default - Which value is pre-selected
            """
            v = tk.StringVar(value=default)
            self._ssp_vars[key] = v
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(
                row, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11), width=22, anchor="w",
            ).pack(side="left")
            # state="readonly" means the user can only choose from the list
            ttk.Combobox(
                row, textvariable=v, values=values,
                state="readonly", width=width,
            ).pack(side="left")

        # ── Local helper: table section (Treeview + Add/Remove buttons) ───────
        def list_section(title, hint, columns, add_cmd, list_key):
            """
            Build a complete table section: heading, hint text, Add/Remove
            buttons, and a Treeview table.

            Parameters:
                title    - Section heading text
                hint     - Small italic hint shown below the heading
                columns  - List of (col_id, heading_text, width, stretch) tuples
                add_cmd  - Method to call when user clicks Add
                list_key - The key in self._ssp that holds this table's data list
            """
            section(title)
            tk.Label(
                parent, text=f"  {hint}",
                bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            ).pack(anchor="w", **P)

            # Outer frame for the table and its buttons
            frame = tk.Frame(
                parent, bg=C["CARD_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            frame.pack(fill="x", padx=28, pady=6)

            # Button row above the table
            btn_row = tk.Frame(frame, bg=C["CARD_BG"])
            btn_row.pack(fill="x", padx=8, pady=6)

            tk.Button(
                btn_row, text="＋  Add",
                command=add_cmd,
                bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                relief="flat", padx=10, pady=3, cursor="hand2",
            ).pack(side="left")

            # The Treeview (table) widget for this section
            tree = ttk.Treeview(
                frame,
                columns=tuple(c[0] for c in columns),  # column IDs
                show="headings",   # hide the default blank first column
                height=4,
                selectmode="browse",   # only one row selected at a time
            )
            for col_id, heading, width, stretch in columns:
                tree.heading(col_id, text=heading, anchor="w")
                tree.column(col_id, width=width, anchor="w", stretch=stretch)
            tree.pack(fill="x", padx=8, pady=(0, 8))

            # The remove button needs to know which tree and list key to use.
            # We use a closure (make_remove) to "capture" the correct values.
            # Without the closure, all buttons would reference the same
            # tree variable — the last one created. This is a common Python gotcha.
            def make_remove(t, lk):
                def _remove():
                    sel = t.selection()
                    if sel:
                        idx = t.index(sel[0])    # row index in the tree
                        self._ssp[lk].pop(idx)   # remove from our data dict
                        t.delete(sel[0])         # remove from the display
                return _remove

            tk.Button(
                btn_row, text="✕  Remove Selected",
                command=make_remove(tree, list_key),
                bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                relief="flat", padx=10, pady=3, cursor="hand2",
            ).pack(side="left", padx=8)

            return tree   # Return so the caller can populate it later

        # =====================================================================
        # BUILD ALL SEVEN SECTIONS
        # =====================================================================

        # ── 1. SSP Metadata ───────────────────────────────────────────────────
        section("1 ·  SSP Metadata")
        field("SSP Title *",     "title",           width=60)
        field("Version *",       "version",         width=20, default="1.0")
        field("Date Authorized", "date_authorized",  width=20)
        tk.Label(
            parent, text="  * Required fields.  Date format: YYYY-MM-DD",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=28)

        # ── 2. System Characteristics ─────────────────────────────────────────
        section("2 ·  System Characteristics")
        field("System Name (Full) *", "system_name",       width=60)
        field("System Name (Short)",  "system_name_short", width=30)

        # The description text widget is stored as an instance variable
        # so _collect() and _populate() can read/write it later.
        self._system_desc = textbox("System Description *", height=4)

        combo(
            "Operational Status *", "status",
            ["operational", "under-development", "under-major-modification",
             "disposition", "other"],
            default="under-development",
        )
        combo(
            "Security Sensitivity Level", "security_sensitivity_level",
            ["fips-199-low", "fips-199-moderate", "fips-199-high"],
            default="fips-199-moderate",
        )
        self._status_remarks = textbox("Status Remarks", height=2)

        # ── 3. Authorization Boundary ─────────────────────────────────────────
        section("3 ·  Authorization Boundary")
        self._auth_boundary = textbox("Boundary Description *", height=4)

        # ── 4. Network Architecture & Data Flow (optional) ────────────────────
        section("4 ·  Network Architecture & Data Flow  (optional)")
        self._network  = textbox("Network Architecture", height=3)
        self._dataflow = textbox("Data Flow",            height=3)

        # ── 5. Information Types ──────────────────────────────────────────────
        # Stores the Treeview widget so _add_info_type/_collect/_populate
        # can insert/read rows.
        self._it_tree = list_section(
            title    = "5 ·  Information Types",
            hint     = "At least one information type is required by the OSCAL schema.",
            columns  = [
                ("title",    "Information Type Title", 300, True),
                ("c_impact", "Confidentiality",        120, False),
                ("i_impact", "Integrity",              120, False),
                ("a_impact", "Availability",           120, False),
            ],
            add_cmd  = self._add_info_type,
            list_key = "information_types",
        )

        # ── 6. Roles ──────────────────────────────────────────────────────────
        self._role_tree = list_section(
            title    = "6 ·  Roles",
            hint     = "Define roles responsible for the system (e.g. system-owner, isso).",
            columns  = [
                ("role_id", "Role ID",    200, False),
                ("title",   "Role Title", 400, True),
            ],
            add_cmd  = self._add_role,
            list_key = "roles",
        )

        # ── 7. Parties ────────────────────────────────────────────────────────
        self._party_tree = list_section(
            title    = "7 ·  Parties  (People & Organisations)",
            hint     = "Parties are the people or organisations referenced by roles.",
            columns  = [
                ("type",  "Type",  120, False),
                ("name",  "Name",  260, False),
                ("email", "Email", 260, True),
            ],
            add_cmd  = self._add_party,
            list_key = "parties",
        )

        # ── 8. System Components ──────────────────────────────────────────────
        self._build_section8(parent, section)

        # ── 9. Control Implementations ────────────────────────────────────────
        self._build_section9(parent, section)

        # Bottom padding so the last section is not flush against the edge
        tk.Frame(parent, bg=C["BG"], height=40).pack()

    # =========================================================================
    # SECTION 8 — SYSTEM COMPONENTS
    # =========================================================================

    def _build_section8(self, parent, section):
        """
        Build Section 8: a toolbar of actions plus a Treeview listing the
        system's components.

        Parameters:
            parent  - The scrollable form frame
            section - The local 'section' header helper from _build_form
        """
        C = self._colors

        section("8 ·  System Components")
        tk.Label(
            parent,
            text="  The components that make up this system (software, hardware,\n"
                 "  services, etc.). Add them by hand, or import existing component\n"
                 "  files — or pull them straight from the Component Editor.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            justify="left",
        ).pack(anchor="w", padx=28)

        # ── Toolbar of component actions ──────────────────────────────────────
        comp8_btn = tk.Frame(parent, bg=C["BG"])
        comp8_btn.pack(fill="x", padx=28, pady=4)
        tk.Button(
            comp8_btn, text="＋  Add Component", command=self._add_ssp_component,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            comp8_btn, text="📂  Import File(s)",
            command=self._import_components_from_files,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            comp8_btn, text="📁  Import Folder",
            command=self._import_components_from_folder,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            comp8_btn, text="✏  Edit Selected", command=self._edit_ssp_component,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            comp8_btn, text="✕  Remove", command=self._remove_ssp_component,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)

        # ── Component table ───────────────────────────────────────────────────
        comp8_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        comp8_frame.pack(fill="x", padx=28, pady=6)
        self._comp8_tree = ttk.Treeview(
            comp8_frame,
            columns=("type", "title", "status", "description"),
            show="headings", height=6, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("type",        "Type",        100, False),
            ("title",       "Title",       180, False),
            ("status",      "Status",      120, False),
            ("description", "Description", 300, True),
        ]:
            self._comp8_tree.heading(col, text=heading, anchor="w")
            self._comp8_tree.column(col, width=w, anchor="w", stretch=stretch)
        self._comp8_tree.pack(fill="x", padx=8, pady=8)

    # =========================================================================
    # SECTION 9 — CONTROL IMPLEMENTATIONS
    # =========================================================================

    def _build_section9(self, parent, section):
        """
        Build Section 9: a two-pane area. The left pane is a tabbed control
        list (All / Applied), the right pane shows the by-component entries
        for the selected control.

        If no catalog is loaded there are no controls to implement, so we show
        a placeholder instead of the two-pane editor. _refresh_ctrl9_list also
        guards on the catalog, so the editor stays inert until one is loaded.

        Parameters:
            parent  - The scrollable form frame
            section - The local 'section' header helper from _build_form
        """
        C = self._colors

        section("9 ·  Control Implementations")
        tk.Label(
            parent,
            text="  For each control, describe how the system's components implement\n"
                 "  it. Select a control on the left, then add one by-component entry\n"
                 "  per component that contributes.   ● = has entries   ○ = none yet",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            justify="left",
        ).pack(anchor="w", padx=28)

        ctrl9_outer = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        ctrl9_outer.pack(fill="both", expand=True, padx=28, pady=6)

        # Placeholder shown when no catalog is loaded (no controls to work with).
        self._ctrl9_placeholder = tk.Label(
            ctrl9_outer,
            text="Load a catalog (and optionally a profile) to implement controls.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11, "italic"),
        )
        self._ctrl9_placeholder.pack(padx=20, pady=30)

        # The actual two-pane editor lives inside _ctrl9_body, shown/hidden
        # as a unit by _refresh_ctrl9_list depending on whether a catalog exists.
        self._ctrl9_body = tk.Frame(ctrl9_outer, bg=C["CARD_BG"])
        # (Not packed yet — _refresh_ctrl9_list decides.)

        ctrl9_pane = tk.PanedWindow(
            self._ctrl9_body, orient="horizontal",
            bg=C["CARD_BG"], sashwidth=4, sashrelief="flat",
        )
        ctrl9_pane.pack(fill="both", expand=True)

        # ── LEFT: tabbed control list (mirrors ComponentTab Section 7) ─────────
        ctrl9_left = tk.Frame(ctrl9_pane, bg=C["SIDEBAR_BG"])
        ctrl9_pane.add(ctrl9_left, minsize=220, width=320)

        # Search box filters the All Controls tab.
        search_row = tk.Frame(ctrl9_left, bg=C["SIDEBAR_BG"])
        search_row.pack(fill="x", padx=6, pady=6)
        tk.Label(search_row, text="🔍", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="left")
        self._ctrl9_search_var = tk.StringVar()
        self._ctrl9_search_var.trace_add("write", self._on_ctrl9_search)
        tk.Entry(
            search_row, textvariable=self._ctrl9_search_var,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", fill="x", expand=True, ipady=3, padx=(4, 0))

        self._ctrl9_notebook = ttk.Notebook(ctrl9_left)
        self._ctrl9_notebook.pack(fill="both", expand=True, padx=4, pady=(0, 2))

        def make_ctrl9_tree(tab_parent):
            """Build a dot/label/statement Treeview inside a notebook tab."""
            frame = tk.Frame(tab_parent, bg=C["SIDEBAR_BG"])
            frame.pack(fill="both", expand=True)
            tree = ttk.Treeview(
                frame, columns=("dot", "label", "title"),
                show="headings", selectmode="browse",
            )
            tree.heading("dot",   text="",           anchor="center")
            tree.heading("label", text="ID / Label", anchor="w")
            tree.heading("title", text="Statement",  anchor="w")
            tree.column("dot",   width=24,  minwidth=24,  anchor="center", stretch=False)
            tree.column("label", width=100, minwidth=80,  anchor="w",      stretch=False)
            tree.column("title", width=180, minwidth=100, anchor="w",      stretch=True)
            tree.tag_configure("done",  foreground=C["GREEN"])
            tree.tag_configure("empty", foreground=C["SUBTEXT"])
            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            tree.bind("<<TreeviewSelect>>", self._on_ctrl9_select)
            return tree

        all_tab = tk.Frame(self._ctrl9_notebook, bg=C["SIDEBAR_BG"])
        self._ctrl9_notebook.add(all_tab, text="All Controls")
        self._ctrl9_tree = make_ctrl9_tree(all_tab)

        applied_tab = tk.Frame(self._ctrl9_notebook, bg=C["SIDEBAR_BG"])
        self._ctrl9_notebook.add(applied_tab, text="Applied Controls")
        self._applied9_tree = make_ctrl9_tree(applied_tab)

        # Clear the search and rebuild when the user switches tabs.
        self._ctrl9_notebook.bind(
            "<<NotebookTabChanged>>",
            lambda _e: (self._ctrl9_search_var.set(""), self._refresh_ctrl9_list()),
        )

        # Progress counter — MUST exist before any _refresh_ctrl9_list call.
        self._ctrl9_progress_lbl = tk.Label(
            ctrl9_left, text="", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9),
        )
        self._ctrl9_progress_lbl.pack(pady=(2, 6))

        # ── RIGHT: by-component entries for the selected control ───────────────
        ctrl9_right = tk.Frame(ctrl9_pane, bg=C["BG"])
        ctrl9_pane.add(ctrl9_right, minsize=300)

        self._ctrl9_stmt_lbl = tk.Label(
            ctrl9_right,
            text="Select a control from the list to add implementation entries.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
            wraplength=380, justify="left", anchor="nw",
        )
        self._ctrl9_stmt_lbl.pack(fill="x", padx=8, pady=(8, 4))

        tk.Frame(ctrl9_right, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=8, pady=4
        )

        # Buttons to manage by-component entries.
        bycomp_btn = tk.Frame(ctrl9_right, bg=C["BG"])
        bycomp_btn.pack(fill="x", padx=8, pady=(4, 4))
        tk.Button(
            bycomp_btn, text="＋  Add Entry", command=self._add_bycomp_entry,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            bycomp_btn, text="✏  Edit Selected", command=self._edit_bycomp_entry,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            bycomp_btn, text="✕  Remove", command=self._remove_bycomp_entry,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)

        # By-component entries table for the selected control.
        bycomp_frame = tk.Frame(
            ctrl9_right, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        bycomp_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._bycomp_tree = ttk.Treeview(
            bycomp_frame, columns=("component", "status", "description"),
            show="headings", height=5, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("component",   "Component",   160, False),
            ("status",      "Status",      120, False),
            ("description", "Description", 240, True),
        ]:
            self._bycomp_tree.heading(col, text=heading, anchor="w")
            self._bycomp_tree.column(col, width=w, anchor="w", stretch=stretch)
        self._bycomp_tree.pack(fill="both", expand=True, padx=8, pady=8)

        # Render the initial state (placeholder vs editor + empty trees).
        self._refresh_ctrl9_list()

    # =========================================================================
    # MODAL DIALOG HELPER
    # =========================================================================

    def _dialog(self, title, fields):
        """
        Show a small modal popup window to collect input from the user.

        'Modal' means the user cannot interact with the main window until
        they close this popup (by clicking OK or Cancel).

        Parameters:
            title  - Window title bar text
            fields - List of tuples: (label, dict_key, default_value, choices_or_None)
                     If choices is a list, a dropdown is shown; otherwise a text entry.

        Returns:
            A dictionary of {key: value} strings, or None if cancelled.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)    # Toplevel creates a separate window
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.grab_set()   # Make the dialog modal (blocks the main window)

        # Create one row per field
        vars_ = {}
        for label, key, default, choices in fields:
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=5)
            tk.Label(
                row, text=label,
                bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11), width=22, anchor="w",
            ).pack(side="left")

            v = tk.StringVar(value=default)
            vars_[key] = v

            if choices:
                # Dropdown for fields with a fixed set of options
                ttk.Combobox(
                    row, textvariable=v, values=choices,
                    state="readonly", width=28,
                ).pack(side="left")
            else:
                # Free-text entry for open fields
                tk.Entry(
                    row, textvariable=v,
                    bg=C["CARD_BG"], fg=C["TEXT"],
                    insertbackground=C["TEXT"], relief="flat",
                    font=("Helvetica", 11), width=32,
                    highlightthickness=1, highlightbackground=C["HEADER_BG"],
                ).pack(side="left", ipady=3)

        # The result dict is populated when the user clicks OK.
        # We use a dict rather than a simple variable because inner functions
        # in Python cannot re-assign variables from the outer scope
        # (they can only mutate mutable objects like dicts).
        result = {}

        def _ok():
            """Read all field values into result and close the dialog."""
            for k, v in vars_.items():
                result[k] = v.get().strip()
            dlg.destroy()

        # Button row at the bottom of the dialog
        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(
            btn, text="  OK  ", command=_ok,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=10,
        ).pack(side="left", padx=8)
        tk.Button(
            btn, text="Cancel", command=dlg.destroy,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=10,
        ).pack(side="left")

        # Pause here until the dialog window is closed
        dlg.wait_window()

        # Return the populated result dict, or None if Cancel was clicked
        return result if result else None

    def _make_dialog(self, title, width=420):
        """
        Create and return a modal Toplevel dialog (same skeleton used by
        ComponentTab and CapabilityTab).

        The caller adds its own content widgets, then calls self.wait_window(dlg)
        to block until the dialog closes. grab_set makes the dialog modal;
        transient keeps it above its parent. The height snaps to its content
        once widgets are packed.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry(f"{width}x1")
        return dlg

    # =========================================================================
    # SECTION 8 — SYSTEM COMPONENT METHODS
    # =========================================================================

    def _refresh_comp8_tree(self):
        """Clear and repopulate the Section 8 component table from memory."""
        self._comp8_tree.delete(*self._comp8_tree.get_children())
        for comp in self._ssp_components:
            self._comp8_tree.insert("", "end", values=(
                comp.get("type", ""),
                comp.get("title", ""),
                comp.get("status", ""),
                comp.get("description", ""),
            ))

    def _add_ssp_component(self):
        """Show the component dialog and append the result to Section 8."""
        comp = self._ssp_component_dialog()
        if not comp:
            return
        self._ssp_components.append(comp)
        self._refresh_comp8_tree()

    def _edit_ssp_component(self):
        """Edit the selected Section 8 component in place."""
        sel = self._comp8_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a component to edit.")
            return
        idx = self._comp8_tree.index(sel[0])
        updated = self._ssp_component_dialog(existing=self._ssp_components[idx])
        if not updated:
            return
        # Preserve the original UUID so any Section 9 references stay valid.
        updated["uuid"] = self._ssp_components[idx]["uuid"]
        self._ssp_components[idx] = updated
        self._refresh_comp8_tree()
        # A component's title may have changed — refresh the by-component table.
        self._refresh_bycomp_tree()

    def _remove_ssp_component(self):
        """
        Remove the selected component and any Section 9 by-component entries
        that reference it (those entries would otherwise dangle).
        """
        sel = self._comp8_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a component to remove.")
            return
        idx = self._comp8_tree.index(sel[0])
        removed_uuid = self._ssp_components[idx]["uuid"]
        self._ssp_components.pop(idx)

        # Drop any by-component entries that referenced the removed component,
        # then drop any control implementation left with no entries at all.
        for ci in self._ssp_ctrl_impls:
            ci["by_components"] = [
                bc for bc in ci["by_components"]
                if bc.get("component_uuid") != removed_uuid
            ]
        self._ssp_ctrl_impls[:] = [
            ci for ci in self._ssp_ctrl_impls if ci["by_components"]
        ]

        self._refresh_comp8_tree()
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())
        self._refresh_bycomp_tree()

    def _add_ssp_component_dict(self, comp_dict):
        """
        Append a component dict to Section 8 if its UUID is not already present.

        Returns True if added, False if a component with that UUID already
        exists (so imports never create duplicates).
        """
        if any(c["uuid"] == comp_dict["uuid"] for c in self._ssp_components):
            return False
        self._ssp_components.append(comp_dict)
        return True

    def _import_component_file(self, path):
        """
        Read one OSCAL component-definition file and import every component it
        defines into Section 8.

        Returns True if at least one component was added, False otherwise
        (unreadable file, wrong type, or all UUIDs already present).
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False

        comps = data.get("component-definition", {}).get("components", [])
        added_any = False
        for c in comps:
            # OSCAL stores operational status as a prop; pull it back out.
            status_prop = next(
                (p for p in c.get("props", [])
                 if p.get("name") == "operational-status"),
                None,
            )
            roles = [r.get("role-id", "")
                     for r in c.get("responsible-roles", [])]
            comp_dict = {
                "uuid":              c.get("uuid", new_uuid()),
                "type":              c.get("type", "software"),
                "title":             c.get("title", ""),
                "description":       c.get("description", ""),
                "purpose":           c.get("purpose", ""),
                "status":            status_prop["value"] if status_prop
                                     else "operational",
                "status_remarks":    status_prop.get("remarks", "")
                                     if status_prop else "",
                "responsible_roles": [r for r in roles if r],
                "remarks":           c.get("remarks", ""),
            }
            if self._add_ssp_component_dict(comp_dict):
                added_any = True
        return added_any

    def _import_components_from_files(self):
        """Import components from one or more chosen component JSON files."""
        paths = filedialog.askopenfilenames(
            title="Import Component File(s)",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not paths:
            return
        added = skipped = 0
        for path in paths:
            if self._import_component_file(path):
                added += 1
            else:
                skipped += 1
        self._refresh_comp8_tree()
        self._set_status(
            f"Imported components from {added} file(s); skipped {skipped}."
        )

    def _import_components_from_folder(self):
        """Import components from every JSON file in a chosen folder."""
        folder = filedialog.askdirectory(
            title="Import Components — loads all JSON files in the folder"
        )
        if not folder:
            return
        added = skipped = 0
        for path in sorted(Path(folder).glob("*.json")):
            if self._import_component_file(path):
                added += 1
            else:
                skipped += 1
        self._refresh_comp8_tree()
        self._set_status(
            f"Imported components from {added} file(s); skipped {skipped}."
        )

    def _ssp_component_dialog(self, existing=None):
        """
        Modal dialog to add or edit an SSP component (Section 8).

        Parameters:
            existing - An existing component dict to pre-fill (edit mode), or
                       None to start blank (add mode).

        Returns:
            A component dict (with a generated uuid in add mode), or None if
            the user cancelled or left a required field blank.
        """
        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit Component" if existing else "Add Component", width=460
        )

        def labelled(parent, text, width=18):
            """Pack a label and return the row frame for the input widget."""
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=width, anchor="w",
                     ).pack(side="left")
            return row

        def entry(row, var, width=40):
            tk.Entry(row, textvariable=var, width=width,
                     bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                     relief="flat", font=("Helvetica", 11), highlightthickness=1,
                     highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        # Title
        v_title = tk.StringVar(value=e.get("title", ""))
        entry(labelled(dlg, "Title *"), v_title)

        # Type
        v_type = tk.StringVar(value=e.get("type", SSP_COMPONENT_TYPES[0]))
        ttk.Combobox(labelled(dlg, "Type *"), textvariable=v_type,
                     values=SSP_COMPONENT_TYPES, state="readonly",
                     width=28).pack(side="left")

        # Description (multi-line)
        tk.Label(dlg, text="Description *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(anchor="w", padx=20, pady=(6, 2))
        desc_border = tk.Frame(dlg, bg=C["HEADER_BG"], highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        desc_border.pack(fill="x", padx=20)
        t_desc = tk.Text(desc_border, bg=C["CARD_BG"], fg=C["TEXT"],
                         insertbackground=C["TEXT"], relief="flat",
                         font=("Helvetica", 11), height=3, wrap="word",
                         padx=8, pady=6)
        t_desc.pack(fill="both")
        if e.get("description"):
            t_desc.insert("1.0", e["description"])

        # Purpose
        v_purpose = tk.StringVar(value=e.get("purpose", ""))
        entry(labelled(dlg, "Purpose"), v_purpose)

        # Status
        v_status = tk.StringVar(value=e.get("status", SSP_COMPONENT_STATUS[0]))
        ttk.Combobox(labelled(dlg, "Status *"), textvariable=v_status,
                     values=SSP_COMPONENT_STATUS, state="readonly",
                     width=28).pack(side="left")

        # Status remarks
        v_status_rem = tk.StringVar(value=e.get("status_remarks", ""))
        entry(labelled(dlg, "Status Remarks"), v_status_rem)

        # Responsible roles (comma-separated role IDs)
        v_roles = tk.StringVar(
            value=", ".join(e.get("responsible_roles", []))
        )
        entry(labelled(dlg, "Responsible Roles"), v_roles)

        # Remarks
        v_remarks = tk.StringVar(value=e.get("remarks", ""))
        entry(labelled(dlg, "Remarks"), v_remarks)

        result = {}

        def _ok():
            title = v_title.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            if not title:
                messagebox.showwarning("Required", "Title is required.")
                return
            if not desc:
                messagebox.showwarning("Required", "Description is required.")
                return
            # Split the comma-separated role IDs, dropping blanks.
            roles = [r.strip() for r in v_roles.get().split(",") if r.strip()]
            result.update({
                "uuid":              e.get("uuid") or new_uuid(),
                "type":              v_type.get(),
                "title":             title,
                "description":       desc,
                "purpose":           v_purpose.get().strip(),
                "status":            v_status.get(),
                "status_remarks":    v_status_rem.get().strip(),
                "responsible_roles": roles,
                "remarks":           v_remarks.get().strip(),
            })
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # SECTION 9 — CONTROL IMPLEMENTATION METHODS
    # =========================================================================

    def _ctrl9_responses(self):
        """
        Build the {control_id: non-empty-string} dict refresh_ctrl_list needs
        to draw the 'applied' dot. A control counts as applied when it has at
        least one by-component entry; we use "○" as a placeholder marker for
        controls with an entry list but (defensively) no usable description.
        """
        return {
            ci["control_id"]: (
                ci["by_components"][0]["description"]
                if ci["by_components"] and ci["by_components"][0].get("description")
                else ("○" if ci["by_components"] else "")
            )
            for ci in self._ssp_ctrl_impls
        }

    def _refresh_ctrl9_list(self, search_term=""):
        """
        Rebuild the All/Applied control lists in Section 9.

        Guarded on the catalog: with no catalog there are no controls, so we
        show the placeholder and hide the two-pane editor instead.
        """
        if not self._get_catalog():
            self._ctrl9_body.pack_forget()
            self._ctrl9_placeholder.pack(padx=20, pady=30)
            return

        # Catalog present — show the editor.
        self._ctrl9_placeholder.pack_forget()
        self._ctrl9_body.pack(fill="both", expand=True)

        from .models import get_profile_controls
        refresh_ctrl_list(
            ctrl_responses=self._ctrl9_responses(),
            all_controls=get_profile_controls(
                self._get_catalog(), self._get_profile()
            ),
            search_term=search_term,
            ctrl_tree=self._ctrl9_tree,
            applied_tree=self._applied9_tree,
            notebook=self._ctrl9_notebook,
            progress_lbl=self._ctrl9_progress_lbl,
        )

    def _on_ctrl9_search(self, *_args):
        """Filter the All Controls tab as the user types."""
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())

    def _on_ctrl9_select(self, _event=None):
        """
        Handle a click in either control tree. Works out which tree fired,
        clears the other's selection, records the control id, updates the
        statement label, and refreshes the by-component table.
        """
        ctrl_id = None
        for tree in (self._ctrl9_tree, self._applied9_tree):
            sel = tree.selection()
            if sel:
                ctrl_id = sel[0]   # iid is the control id
                other = (self._applied9_tree
                         if tree is self._ctrl9_tree else self._ctrl9_tree)
                other.selection_remove(*other.selection())
                break
        if ctrl_id is None:
            return

        self._sel_ctrl_id = ctrl_id

        # Show the control's label and statement for reference.
        catalog = self._get_catalog()
        ctrl_dict = None
        if catalog:
            ctrl_dict = next(
                (c for c in catalog["controls"] if c["id"] == ctrl_id), None
            )
        if ctrl_dict:
            label     = ctrl_dict.get("label", ctrl_id)
            statement = ctrl_dict.get("statement", ctrl_dict.get("title", ""))
            self._ctrl9_stmt_lbl.config(
                text=f"[{label}]  {statement}", fg=self._colors["TEXT"]
            )
        else:
            self._ctrl9_stmt_lbl.config(text=ctrl_id, fg=self._colors["SUBTEXT"])

        self._refresh_bycomp_tree()

    def _find_ctrl_impl(self, ctrl_id):
        """Return the ctrl_implementation entry for ctrl_id, or None."""
        return next(
            (ci for ci in self._ssp_ctrl_impls if ci["control_id"] == ctrl_id),
            None,
        )

    def _comp_title_for_uuid(self, comp_uuid):
        """Return a component's title for display, falling back to its UUID."""
        for c in self._ssp_components:
            if c["uuid"] == comp_uuid:
                return c.get("title", "") or comp_uuid
        return comp_uuid

    def _refresh_bycomp_tree(self):
        """Repopulate the by-component table for the selected control."""
        self._bycomp_tree.delete(*self._bycomp_tree.get_children())
        if not self._sel_ctrl_id:
            return
        ci = self._find_ctrl_impl(self._sel_ctrl_id)
        if not ci:
            return
        for bc in ci["by_components"]:
            self._bycomp_tree.insert("", "end", values=(
                self._comp_title_for_uuid(bc.get("component_uuid", "")),
                bc.get("impl_status", ""),
                bc.get("description", ""),
            ))

    def _add_bycomp_entry(self):
        """
        Add a by-component entry for the selected control. Requires a control
        to be selected and at least one component to exist in Section 8.
        """
        if not self._sel_ctrl_id:
            messagebox.showinfo(
                "No control selected", "Select a control from the list first."
            )
            return
        bc = self._bycomp_dialog()
        if not bc:
            return
        # Find or create the control implementation entry, then append.
        ci = self._find_ctrl_impl(self._sel_ctrl_id)
        if ci is None:
            ci = {"control_id": self._sel_ctrl_id, "remarks": "",
                  "by_components": []}
            self._ssp_ctrl_impls.append(ci)
        ci["by_components"].append(bc)
        self._refresh_bycomp_tree()
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())
        # Keep the row selected so the by-component table stays in view.
        self._reselect_ctrl9(self._sel_ctrl_id)

    def _edit_bycomp_entry(self):
        """Edit the selected by-component entry in place."""
        if not self._sel_ctrl_id:
            return
        sel = self._bycomp_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an entry to edit.")
            return
        ci = self._find_ctrl_impl(self._sel_ctrl_id)
        if not ci:
            return
        idx = self._bycomp_tree.index(sel[0])
        updated = self._bycomp_dialog(existing=ci["by_components"][idx])
        if not updated:
            return
        # Preserve the entry UUID so the OSCAL by-component identity is stable.
        updated["uuid"] = ci["by_components"][idx]["uuid"]
        ci["by_components"][idx] = updated
        self._refresh_bycomp_tree()

    def _remove_bycomp_entry(self):
        """Remove the selected by-component entry; drop the control if empty."""
        if not self._sel_ctrl_id:
            return
        sel = self._bycomp_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an entry to remove.")
            return
        ci = self._find_ctrl_impl(self._sel_ctrl_id)
        if not ci:
            return
        idx = self._bycomp_tree.index(sel[0])
        ci["by_components"].pop(idx)
        # A control with no entries is removed entirely so its dot clears.
        if not ci["by_components"]:
            self._ssp_ctrl_impls.remove(ci)
        self._refresh_bycomp_tree()
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())
        self._reselect_ctrl9(self._sel_ctrl_id)

    def _reselect_ctrl9(self, ctrl_id):
        """
        Restore the row selection for ctrl_id in whichever control tab is
        currently visible, so dot/count refreshes do not lose the selection.
        """
        active_tab = self._ctrl9_notebook.index("current")
        tree = self._ctrl9_tree if active_tab == 0 else self._applied9_tree
        try:
            tree.selection_set(ctrl_id)
            tree.see(ctrl_id)
        except Exception:
            pass   # Row may not exist in the Applied tab after a removal

    def _bycomp_dialog(self, existing=None):
        """
        Modal dialog to add or edit a by-component implementation entry.

        Requires at least one component in Section 8 (you cannot implement a
        control with no component). If none exist, prompts the user and returns
        None.

        Parameters:
            existing - An existing by-component dict to pre-fill, or None.

        Returns:
            A by-component dict (with a generated uuid in add mode), or None.
        """
        if not self._ssp_components:
            messagebox.showinfo(
                "No components",
                "Add at least one component in Section 8 before describing\n"
                "how it implements a control."
            )
            return None

        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit Implementation Entry" if existing else "Add Implementation Entry",
            width=460,
        )

        # Build "Title [type]" labels mapped to component UUIDs.
        choices = []
        label_to_uuid = {}
        for c in self._ssp_components:
            label = f"{c.get('title', '(untitled)')} [{c.get('type', '')}]"
            choices.append(label)
            label_to_uuid[label] = c["uuid"]

        # Pre-select the existing component if editing.
        default_label = choices[0]
        if e.get("component_uuid"):
            for lbl, u in label_to_uuid.items():
                if u == e["component_uuid"]:
                    default_label = lbl
                    break

        def labelled(text, width=18):
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=width, anchor="w",
                     ).pack(side="left")
            return row

        # Component
        v_comp = tk.StringVar(value=default_label)
        ttk.Combobox(labelled("Component *"), textvariable=v_comp,
                     values=choices, state="readonly", width=30).pack(side="left")

        # Implementation status
        v_status = tk.StringVar(value=e.get("impl_status", IMPL_STATUS_VALUES[0]))
        ttk.Combobox(labelled("Implementation Status *"), textvariable=v_status,
                     values=IMPL_STATUS_VALUES, state="readonly",
                     width=30).pack(side="left")

        # Description (multi-line)
        tk.Label(dlg, text="Description *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(anchor="w", padx=20, pady=(6, 2))
        desc_border = tk.Frame(dlg, bg=C["HEADER_BG"], highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        desc_border.pack(fill="x", padx=20)
        t_desc = tk.Text(desc_border, bg=C["CARD_BG"], fg=C["TEXT"],
                         insertbackground=C["TEXT"], relief="flat",
                         font=("Helvetica", 11), height=4, wrap="word",
                         padx=8, pady=6)
        t_desc.pack(fill="both")
        if e.get("description"):
            t_desc.insert("1.0", e["description"])

        # Remarks
        v_remarks = tk.StringVar(value=e.get("remarks", ""))
        rr = labelled("Remarks")
        tk.Entry(rr, textvariable=v_remarks, width=40,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}

        def _ok():
            desc = t_desc.get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Required", "Description is required.")
                return
            result.update({
                "uuid":           e.get("uuid") or new_uuid(),
                "component_uuid": label_to_uuid[v_comp.get()],
                "description":    desc,
                "impl_status":    v_status.get(),
                "remarks":        v_remarks.get().strip(),
            })
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # ADD ITEM METHODS (called when the user clicks an Add button)
    # =========================================================================

    def _add_info_type(self):
        """
        Show a dialog to collect information type details, then add
        the new entry to both the internal data dict and the table widget.
        """
        impacts = ["fips-199-low", "fips-199-moderate", "fips-199-high"]
        res = self._dialog("Add Information Type", [
            ("Title *",         "title",       "",                  None),
            ("Description *",   "description", "",                  None),
            ("Confidentiality", "c_impact",    "fips-199-moderate", impacts),
            ("Integrity",       "i_impact",    "fips-199-moderate", impacts),
            ("Availability",    "a_impact",    "fips-199-moderate", impacts),
        ])
        # If the user cancelled or left the title blank, do nothing
        if not res or not res.get("title"):
            return
        # Every information type needs a unique ID
        res["uuid"] = new_uuid()
        # Add to our internal data list
        self._ssp["information_types"].append(res)
        # Add a row to the table widget
        self._it_tree.insert(
            "", "end",
            values=(res["title"], res["c_impact"], res["i_impact"], res["a_impact"])
        )

    def _add_role(self):
        """Show a dialog to add a role to the SSP."""
        # Pre-populate the dropdown with common OSCAL role IDs
        common_roles = [
            "system-owner", "isso", "authorizing-official",
            "system-poc-management", "system-poc-technical",
            "system-poc-other", "privacy-officer", "security-operations",
        ]
        res = self._dialog("Add Role", [
            ("Role ID *",    "role_id", "", common_roles),
            ("Role Title *", "title",   "", None),
        ])
        if not res or not res.get("role_id"):
            return
        self._ssp["roles"].append(res)
        self._role_tree.insert("", "end", values=(res["role_id"], res["title"]))

    def _add_party(self):
        """Show a dialog to add a person or organisation to the SSP."""
        res = self._dialog("Add Party", [
            ("Type *", "type",  "person", ["person", "organization"]),
            ("Name *", "name",  "",       None),
            ("Email",  "email", "",       None),
        ])
        if not res or not res.get("name"):
            return
        res["uuid"] = new_uuid()
        self._ssp["parties"].append(res)
        self._party_tree.insert(
            "", "end",
            values=(res["type"], res["name"], res.get("email", ""))
        )

    # =========================================================================
    # DATA COLLECTION AND FORM POPULATION
    # These methods sync between the GUI widgets and self._ssp.
    # =========================================================================

    def _collect(self):
        """
        Read all form widget values and write them into self._ssp.

        Called just before saving, so self._ssp is up-to-date.
        StringVar fields update automatically, but Text widgets (textboxes)
        must be read explicitly with .get("1.0", "end-1c").
          - "1.0" means line 1, character 0 (the very start)
          - "end-1c" means the end minus one character (strips the trailing newline)
        """
        # Read all simple text entry fields (linked via StringVar)
        for key, var in self._ssp_vars.items():
            self._ssp[key] = var.get().strip()

        # Read multi-line text widgets (not linked to StringVar)
        self._ssp["system_description"]        = self._system_desc.get("1.0", "end-1c").strip()
        self._ssp["status_remarks"]            = self._status_remarks.get("1.0", "end-1c").strip()
        self._ssp["auth_boundary_description"] = self._auth_boundary.get("1.0", "end-1c").strip()
        self._ssp["network_architecture"]      = self._network.get("1.0", "end-1c").strip()
        self._ssp["data_flow"]                 = self._dataflow.get("1.0", "end-1c").strip()
        # Note: table data (roles, parties, info_types) is updated in real-time
        # by _add_* and _remove_* methods, so no collection needed here.

        # Sections 8 & 9 are edited in their own working lists; copy them back
        # into the canonical SSP dict so they are included when building OSCAL.
        self._ssp["components"]           = self._ssp_components
        self._ssp["ctrl_implementations"] = self._ssp_ctrl_impls

    def _populate(self):
        """
        Write values from self._ssp into all form widgets.

        Called when opening a saved SSP file, so the form shows the
        loaded data rather than blank fields.
        """
        ssp = self._ssp

        # Default values for fields that should never be empty
        defaults = {
            "version":                    "1.0",
            "status":                     "under-development",
            "security_sensitivity_level": "fips-199-moderate",
        }

        # Push values into the StringVar fields (this updates their Entry widgets)
        for key, var in self._ssp_vars.items():
            # Use ssp value if present, otherwise use the default, otherwise blank
            var.set(ssp.get(key) or defaults.get(key, ""))

        # Push values into the Text widgets
        for widget, key in [
            (self._system_desc,   "system_description"),
            (self._status_remarks, "status_remarks"),
            (self._auth_boundary, "auth_boundary_description"),
            (self._network,       "network_architecture"),
            (self._dataflow,      "data_flow"),
        ]:
            widget.delete("1.0", "end")    # Clear existing content
            val = ssp.get(key, "")
            if val:
                widget.insert("1.0", val)  # Insert at the very beginning

        # Rebuild the information types table
        self._it_tree.delete(*self._it_tree.get_children())
        for it in ssp.get("information_types", []):
            self._it_tree.insert("", "end", values=(
                it["title"],
                it.get("c_impact", "—"),
                it.get("i_impact", "—"),
                it.get("a_impact", "—"),
            ))

        # Rebuild the roles table
        self._role_tree.delete(*self._role_tree.get_children())
        for r in ssp.get("roles", []):
            self._role_tree.insert("", "end", values=(r["role_id"], r["title"]))

        # Rebuild the parties table
        self._party_tree.delete(*self._party_tree.get_children())
        for p in ssp.get("parties", []):
            self._party_tree.insert("", "end",
                values=(p["type"], p["name"], p.get("email", "")))

        # ── Sections 8 & 9: load working lists and rebuild their widgets ──────
        # list(...) makes shallow copies so editing the form does not mutate the
        # parsed dict until _collect() copies them back.
        self._ssp_components = list(ssp.get("components", []))
        self._ssp_ctrl_impls = list(ssp.get("ctrl_implementations", []))
        self._sel_ctrl_id    = None
        self._refresh_comp8_tree()
        self._refresh_ctrl9_list()
        self._refresh_bycomp_tree()

    def _reset(self):
        """
        Clear all form widgets back to their default values.
        Called when the user clicks 'New SSP'.
        """
        # Create a fresh blank SSP dictionary
        self._ssp = empty_ssp()

        # Reset StringVar fields to defaults
        defaults = {
            "version":                    "1.0",
            "status":                     "under-development",
            "security_sensitivity_level": "fips-199-moderate",
        }
        for key, var in self._ssp_vars.items():
            var.set(defaults.get(key, ""))

        # Clear all text widgets
        for w in (self._system_desc, self._status_remarks,
                  self._auth_boundary, self._network, self._dataflow):
            w.delete("1.0", "end")

        # Clear all tables
        for tree in (self._it_tree, self._role_tree, self._party_tree):
            tree.delete(*tree.get_children())

        # ── Reset Sections 8 & 9 working state and widgets ───────────────────
        self._ssp_components = []
        self._ssp_ctrl_impls = []
        self._sel_comp_index = None
        self._sel_ctrl_id    = None
        self._refresh_comp8_tree()
        self._refresh_ctrl9_list()
        self._refresh_bycomp_tree()

    # =========================================================================
    # SAVE / OPEN / NEW / EXPORT ACTIONS
    # =========================================================================

    def _export_docx(self):
        """
        Export the current SSP form data to a Microsoft Word (.docx) file.

        Collects the current form values (same as saving), asks the user where
        to save the file, then calls build_ssp_docx() to build and write it.
        build_ssp_docx returns None when python-docx is not installed, in which
        case we show an install hint instead of crashing.
        """
        self._collect()

        # Suggest a filename derived from the system name
        system_name = self._ssp.get("system_name", "SSP").replace(" ", "_")
        default_name = f"{system_name}.docx"

        path = filedialog.asksaveasfilename(
            title="Export SSP as Word Document",
            defaultextension=".docx",
            initialfile=default_name,
            filetypes=[("Word Document", "*.docx"), ("All files", "*.*")],
        )
        if not path:
            return   # User cancelled

        doc = build_ssp_docx(self._ssp)
        if doc is None:
            # python-docx was not available when the module was imported
            messagebox.showerror(
                "python-docx not installed",
                "Export to Word requires the python-docx library.\n\n"
                "Install it with:\n    pip install python-docx\n\n"
                "Then restart the application.",
            )
            return

        try:
            doc.save(path)
            self._set_status(f"Exported: {Path(path).name}")
            messagebox.showinfo(
                "Export Complete",
                f"SSP exported to:\n{path}",
            )
        except OSError as exc:
            messagebox.showerror("Export Failed", str(exc))

    def _save(self):
        """
        Validate the form and save the SSP to a JSON file chosen by the user.
        """
        # Collect the latest widget values before validating
        self._collect()

        # Ask the main app for the current profile and catalog
        profile = self._get_profile()
        catalog = self._get_catalog()

        # Check for missing required fields
        errors, warnings = validate_ssp(self._ssp, profile, catalog)

        if errors:
            # Hard errors — cannot save, show a message box listing the problems
            messagebox.showerror(
                "Cannot save SSP",
                "Please fix the following before saving:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        if warnings:
            # Soft warnings — ask whether to proceed anyway
            proceed = messagebox.askyesno(
                "Save with warnings?",
                "\n".join(f"• {w}" for w in warnings) + "\n\nSave anyway?"
            )
            if not proceed:
                return

        # Ask the user where to save the file
        path = filedialog.asksaveasfilename(
            title="Save OSCAL SSP",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            # Suggest a default filename based on the short system name
            initialfile=f"ssp_{self._ssp.get('system_name_short') or 'draft'}.json",
        )
        if not path:
            return   # User cancelled the save dialog

        # Convert our internal dict to the full OSCAL JSON structure
        doc = build_oscal_ssp(self._ssp, profile, catalog)

        # Write the JSON to disk.
        # indent=2 produces nicely formatted JSON (human-readable).
        # ensure_ascii=False allows non-ASCII characters (e.g. accented letters).
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        # Update the status labels
        self._status_lbl.config(
            text=f"Saved: {Path(path).name}", fg=self._colors["GREEN"]
        )
        self._set_status(f"SSP saved: {Path(path).name}")
        messagebox.showinfo("SSP Saved", f"OSCAL SSP saved successfully:\n{path}")

    def _open(self):
        """
        Ask the user to choose a saved SSP JSON file, then load it into
        the form so they can continue editing.
        """
        # Ask the user to choose a file
        path = filedialog.askopenfilename(
            title="Open OSCAL SSP",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return   # User cancelled

        # Read the file into a Python dictionary
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # json.JSONDecodeError: file is not valid JSON
            # OSError: file not found or permission denied
            messagebox.showerror("Failed to open SSP", str(exc))
            return

        # Check that this is actually an OSCAL SSP file
        if "system-security-plan" not in data:
            messagebox.showerror(
                "Invalid file",
                "Missing 'system-security-plan' key — not an OSCAL SSP."
            )
            return

        # Warn the user if there is already an SSP in the form
        current_title = self._ssp_vars.get("title", tk.StringVar()).get().strip()
        ssp, bm_info  = parse_ssp_file(data)
        if current_title:
            if not messagebox.askyesno(
                "Replace current SSP?",
                f"Replace '{current_title}' with "
                f"'{ssp['title'] or Path(path).name}'?"
            ):
                return   # User chose not to replace

        # Load the parsed data and rebuild the form
        self._ssp = ssp
        self._populate()

        # Update the profile info box from the SSP's back-matter
        self._update_profile_box_from_bm(bm_info)

        self._status_lbl.config(
            text=f"Opened: {Path(path).name}", fg=self._colors["BLUE"]
        )
        self._set_status(f"SSP opened: {Path(path).name}")

    def _new(self):
        """
        Clear the form and start a fresh SSP, after confirming with the user.
        """
        if messagebox.askyesno(
            "New SSP",
            "Clear the current SSP and start a new one?"
        ):
            self._reset()
            self._status_lbl.config(
                text="New SSP (unsaved)", fg=self._colors["SUBTEXT"]
            )

    def _update_profile_box_from_bm(self, bm_info):
        """
        Update the profile info box using information extracted from the
        SSP's back-matter section (used when loading a saved SSP).

        When we save an SSP, we store the profile title, version, and
        filename inside the SSP's back-matter. When we re-open it,
        we can show those details even if the profile file is not loaded.

        Parameters:
            bm_info - A dict with keys: title, file, version
                      (from models.parse_ssp_file)
        """
        C = self._colors
        if bm_info.get("title"):
            # Build a display string from whatever back-matter info is available
            text = bm_info["title"]
            if bm_info.get("version"):
                text += f"  (v{bm_info['version']})"
            if bm_info.get("file"):
                text += f"  |  {bm_info['file']}"
            self._profile_lbl.config(text=text, fg=C["YELLOW"])
        elif bm_info.get("file"):
            # Fall back to just showing the filename
            self._profile_lbl.config(text=bm_info["file"], fg=C["YELLOW"])
        else:
            # No profile information at all
            self._profile_lbl.config(
                text="No profile recorded in SSP", fg=C["SUBTEXT"]
            )
