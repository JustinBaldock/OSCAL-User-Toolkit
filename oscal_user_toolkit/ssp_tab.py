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
    # Centralised OSCAL version constant — avoids hard-coded "1.1.2" (M1 fix)
    DEFAULT_OSCAL_VERSION,
)


# =============================================================================
# CONSTANTS — allowed values from the OSCAL SSP schema
# =============================================================================

# Component type enum for SSP system-implementation components (Section 8).
# Note this differs from the component-definition enum: an SSP may NOT use
# "this-system" here (that one is auto-generated), so it is omitted.
# Updated to OSCAL 1.2.2 valid values — removed "process-procedure" and
# "network" (not valid in OSCAL 1.2.2), added "process", "procedure",
# "defined-system", and kept "physical". (H3 fix)
SSP_COMPONENT_TYPES = [
    "defined-system", "system", "interconnection", "software", "hardware",
    "service", "policy", "process", "procedure", "plan", "guidance",
    "standard", "validation", "physical",
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
                 get_components=None, get_oscal_version=None, open_profile=None,
                 get_capabilities=None):
        """
        Set up the SSPTab panel.

        Parameters:
            parent            - The parent widget (the ttk.Notebook)
            colors            - Shared colour dictionary from app.py
            get_profile       - Callback: returns the loaded profile dict or None
            get_catalog       - Callback: returns the loaded catalog dict or None
            set_status        - Callback: set_status("message") updates the status bar
            get_components    - Optional callback returning ComponentTab's live list
                                of component dicts, used to import components into
                                Section 8. Defaults to a no-op returning an empty
                                list so the tab works even if the hook is not wired.
            get_oscal_version - Optional callback returning the OSCAL version string
                                selected in the toolbar (e.g. "1.2.2"). Defaults to
                                a lambda returning "1.1.2" so the tab works standalone.
            open_profile      - Optional callback that triggers the app's Open Profile
                                dialog so the user can change the profile from within
                                the SSP tab without switching to the toolbar.
            get_capabilities  - Optional callback returning the list of capability dicts
                                currently loaded in the Capability Editor tab. Used by
                                the draw.io export to place capabilities in the diagram.
        """
        super().__init__(parent, bg=colors["BG"])

        # Store the injected dependencies
        self._colors      = colors
        self._get_profile = get_profile
        self._get_catalog = get_catalog
        self._set_status  = set_status
        self._get_components    = get_components    or (lambda: [])
        # Use the shared DEFAULT_OSCAL_VERSION constant from models.py (M1 fix)
        self._get_oscal_version = get_oscal_version or (lambda: DEFAULT_OSCAL_VERSION)
        self._open_profile      = open_profile
        # Callback to read the Capability Editor's loaded capabilities. Returns
        # an empty list when not wired (e.g. unit tests or standalone use).
        self._get_capabilities  = get_capabilities  or (lambda: [])

        # Dirty flag — True when there are unsaved changes in the form.
        # Set by any add/edit/remove action; cleared after a successful save.
        self._dirty = False

        # The SSP data is stored as a plain Python dictionary.
        # All form widgets read from and write to this dictionary.
        self._ssp = empty_ssp()

        # ── Section 8 & 9 working state ───────────────────────────────────────
        # These mirror the lists inside self._ssp while the form is open, so the
        # tables and dialogs can mutate them directly without touching the
        # canonical dict until _collect() runs.
        self._ssp_components = []   # mirrors ssp["components"]
        self._ssp_ctrl_impls = []   # mirrors ssp["ctrl_implementations"]
        self._ssp_set_params = []   # mirrors ssp["set_parameters"]
        self._ssp_users      = []   # mirrors ssp["users"]
        self._ssp_inv_items  = []   # mirrors ssp["inventory_items"]
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
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(
            tb, text="📄  Export DOCX", command=self._export_docx,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 8), pady=8)

        # ── Visual separator before the draw.io export ────────────────────────
        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=8, pady=6
        )

        # Wrap the draw.io button and its hint label in a small frame so they
        # sit together as a visual unit in the toolbar.
        drawio_frame = tk.Frame(tb, bg=C["CARD_BG"])
        drawio_frame.pack(side="left", pady=4)

        tk.Button(
            drawio_frame, text="📐  Export draw.io Diagram",
            command=self._export_drawio,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 6))

        # Hint so users know to load capabilities in the Capability Editor first.
        # The hint is small and muted so it doesn't distract from the main toolbar.
        tk.Label(
            drawio_frame,
            text="Load capabilities in the\nCapability Editor tab first",
            bg=C["CARD_BG"], fg=C["MUTED"] if "MUTED" in C else "#888888",
            font=("Helvetica", 8), justify="left",
        ).pack(side="left")

        # ── Second visual separator before the profile info box ───────────────
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
        self._profile_lbl.pack(side="left", padx=(0, 4))

        tk.Button(
            prof_box, text="Change…",
            command=lambda: self._open_profile() if self._open_profile else None,
            bg=C["SIDEBAR_BG"], fg=C["ACCENT"], font=("Helvetica", 9),
            relief="flat", padx=4, pady=0, cursor="hand2",
            activebackground=C["HEADER_BG"], activeforeground=C["ACCENT"],
        ).pack(side="left", padx=(0, 8))

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
                        self._dirty = True
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

        # ── OSCAL 1.2.x structured security-impact-level dropdowns (M2 fix) ──
        # OSCAL 1.2.x uses a separate CIA objective for each dimension.
        # We add three Comboboxes so users can set each one independently.
        # These map to confidentiality_impact, integrity_impact, availability_impact
        # in the internal SSP dict (see models.py empty_ssp and build_oscal_ssp).
        _cia_options = ["fips-199-low", "fips-199-moderate", "fips-199-high"]
        combo(
            "Confidentiality Impact", "confidentiality_impact",
            _cia_options, default="fips-199-moderate",
        )
        combo(
            "Integrity Impact", "integrity_impact",
            _cia_options, default="fips-199-moderate",
        )
        combo(
            "Availability Impact", "availability_impact",
            _cia_options, default="fips-199-moderate",
        )

        self._status_remarks = textbox("Status Remarks", height=2)

        # ── 3. Authorization Boundary ─────────────────────────────────────────
        section("3 ·  Authorization Boundary")
        self._auth_boundary = textbox("Boundary Description *", height=4)

        # ── 4. Network Architecture & Data Flow (optional) ────────────────────
        section("4 ·  Network Architecture & Data Flow  (optional)")
        self._network  = textbox("Network Architecture", height=3)
        self._dataflow = textbox("Data Flow",            height=3)

        # ── 4b. Data Flow Diagrams sub-table (optional) ───────────────────────
        tk.Label(
            parent,
            text="Data Flow Diagrams  (optional — link to external diagram files)",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(anchor="w", **P, pady=(8, 2))

        diag_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        diag_frame.pack(fill="x", padx=28, pady=4)

        diag_btn_row = tk.Frame(diag_frame, bg=C["CARD_BG"])
        diag_btn_row.pack(fill="x", padx=8, pady=6)

        tk.Button(
            diag_btn_row, text="＋  Add Diagram",
            command=self._add_diagram,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            diag_btn_row, text="✕  Remove",
            command=self._remove_diagram,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)

        diag_tree_frame = tk.Frame(diag_frame, bg=C["CARD_BG"])
        diag_tree_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._diagram_tree = ttk.Treeview(
            diag_tree_frame,
            columns=("caption", "link"),
            show="headings", height=3, selectmode="browse",
        )
        self._diagram_tree.heading("caption", text="Caption",    anchor="w")
        self._diagram_tree.heading("link",    text="Link/Path",  anchor="w")
        self._diagram_tree.column("caption", width=200, anchor="w", stretch=False)
        self._diagram_tree.column("link",    width=340, anchor="w", stretch=True)

        diag_scroll = ttk.Scrollbar(
            diag_tree_frame, orient="vertical", command=self._diagram_tree.yview,
        )
        self._diagram_tree.configure(yscrollcommand=diag_scroll.set)
        diag_scroll.pack(side="right", fill="y")
        self._diagram_tree.pack(side="left", fill="x", expand=True)

        # ── 5. Information Types ──────────────────────────────────────────────
        # Stores the Treeview widget so _add_info_type/_collect/_populate
        # can insert/read rows.
        self._it_tree = list_section(
            title    = "5 ·  Information Types",
            hint     = "At least one information type is required by the OSCAL schema.",
            columns  = [
                ("title",      "Information Type Title", 220, True),
                ("c_impact",   "Confidentiality",        110, False),
                ("i_impact",   "Integrity",              110, False),
                ("a_impact",   "Availability",           110, False),
                ("components", "Components",             160, False),
            ],
            add_cmd  = self._add_info_type,
            list_key = "information_types",
        )
        # Add Edit button to the info types toolbar (it_tree's parent toolbar)
        # and bind double-click for editing.
        it_parent = self._it_tree.master.master   # frame > card_frame > parent
        # Find the btn_row (first child of the card frame)
        it_card = self._it_tree.master
        for child in it_card.winfo_children():
            if isinstance(child, tk.Frame):
                # This is the btn_row — add the Edit button here
                tk.Button(
                    child, text="✏  Edit Selected",
                    command=self._edit_info_type,
                    bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                    relief="flat", padx=10, pady=3, cursor="hand2",
                ).pack(side="left", padx=8)
                break
        self._it_tree.bind("<Double-1>", lambda _e: self._edit_info_type())

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

        # ── 7b. Responsible Parties ───────────────────────────────────────────
        # Maps each defined role to the party (person/org) who fills that role.
        # This becomes responsible-parties[] in the OSCAL metadata block.
        self._build_section7b(parent, section)

        # ── 8. System Components ──────────────────────────────────────────────
        self._build_section8(parent, section)

        # ── 9. Control Implementations ────────────────────────────────────────
        self._build_section9(parent, section)

        # ── 10. Network Protocols ─────────────────────────────────────────────
        self._build_section10(parent, section)

        # ── 11. System Users ──────────────────────────────────────────────────
        self._build_section11(parent, section)

        # ── 12. Inventory Items ───────────────────────────────────────────────
        self._build_section12(parent, section)

        # Bottom padding so the last section is not flush against the edge
        tk.Frame(parent, bg=C["BG"], height=40).pack()

    # =========================================================================
    # SECTION 7b — RESPONSIBLE PARTIES
    # Maps roles to the parties (people/orgs) responsible for filling them.
    # Becomes responsible-parties[] in the OSCAL metadata block.
    # =========================================================================

    def _build_section7b(self, parent, section):
        """
        Build Section 7b: Responsible Parties.

        Each row links one Role ID to one or more Party UUIDs.
        The Add dialog shows dropdowns populated from the Roles and Parties
        tables defined in Sections 6 and 7.
        """
        C = self._colors
        section("7b ·  Responsible Parties")
        tk.Label(
            parent,
            text="  Map each role to the person or organisation who fills it.  "
                 "Roles and parties must be defined in Sections 6 and 7 first.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=28)

        frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        frame.pack(fill="x", padx=28, pady=6)

        btn_row = tk.Frame(frame, bg=C["CARD_BG"])
        btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(
            btn_row, text="＋  Add",
            command=self._add_responsible_party,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            btn_row, text="✕  Remove",
            command=self._remove_responsible_party,
            bg=C["RED"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=(6, 0))

        self._rp_tree = ttk.Treeview(
            frame,
            columns=("role_id", "party_name"),
            show="headings",
            height=4,
            selectmode="browse",
        )
        self._rp_tree.heading("role_id",     text="Role ID",    anchor="w")
        self._rp_tree.heading("party_name",  text="Party Name", anchor="w")
        self._rp_tree.column("role_id",     width=220, anchor="w", stretch=False)
        self._rp_tree.column("party_name",  width=400, anchor="w", stretch=True)
        self._rp_tree.pack(fill="x", padx=8, pady=(0, 8))

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

        # ── Component counter ─────────────────────────────────────────────────
        # Updated by _refresh_comp8_tree every time the list changes.
        self._comp8_count_lbl = tk.Label(
            parent, text="0 components",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            anchor="w",
        )
        self._comp8_count_lbl.pack(anchor="w", padx=28, pady=(0, 2))

        # ── Component table ───────────────────────────────────────────────────
        comp8_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        comp8_frame.pack(fill="x", padx=28, pady=(0, 6))

        self._comp8_tree = ttk.Treeview(
            comp8_frame,
            columns=("type", "title", "status", "description"),
            show="headings", height=8, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("type",        "Type",        100, False),
            ("title",       "Title",       180, False),
            ("status",      "Status",      120, False),
            ("description", "Description", 300, True),
        ]:
            self._comp8_tree.heading(col, text=heading, anchor="w")
            self._comp8_tree.column(col, width=w, anchor="w", stretch=stretch)

        # Scrollbar — lets the user scroll when there are more than 8 components.
        # yscrollcommand links the scrollbar to the treeview; the scrollbar's
        # command links back so dragging the bar scrolls the treeview.
        comp8_scroll = ttk.Scrollbar(
            comp8_frame, orient="vertical", command=self._comp8_tree.yview,
        )
        self._comp8_tree.configure(yscrollcommand=comp8_scroll.set)

        # Pack scrollbar on the right BEFORE the treeview fills the rest.
        comp8_scroll.pack(side="right", fill="y", padx=(0, 4), pady=8)
        self._comp8_tree.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=8)

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

        # ── 9b. Set-Parameters ────────────────────────────────────────────────
        # Allow overriding catalog parameter values at the SSP level.
        tk.Label(
            parent,
            text="  Parameter Overrides  (optional — override catalog parameter values for this system)",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=28, pady=(6, 0))

        sp_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        sp_frame.pack(fill="x", padx=28, pady=(2, 8))

        sp_btn_row = tk.Frame(sp_frame, bg=C["CARD_BG"])
        sp_btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(
            sp_btn_row, text="＋  Add Parameter Override",
            command=self._add_set_param,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            sp_btn_row, text="✏  Edit Selected",
            command=self._edit_set_param,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)
        tk.Button(
            sp_btn_row, text="✕  Remove",
            command=self._remove_set_param,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=6)

        self._sp_tree = ttk.Treeview(
            sp_frame, columns=("param_id", "values", "remarks"),
            show="headings", height=3, selectmode="browse",
        )
        self._sp_tree.heading("param_id", text="Parameter ID", anchor="w")
        self._sp_tree.heading("values",   text="Values",       anchor="w")
        self._sp_tree.heading("remarks",  text="Remarks",      anchor="w")
        self._sp_tree.column("param_id", width=180, anchor="w", stretch=False)
        self._sp_tree.column("values",   width=260, anchor="w", stretch=True)
        self._sp_tree.column("remarks",  width=200, anchor="w", stretch=False)
        self._sp_tree.pack(fill="x", padx=8, pady=(0, 8))

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
    # SECTION 10 — NETWORK PROTOCOLS
    # =========================================================================

    def _build_section10(self, parent, section):
        """
        Build Section 10: a read-only consolidated table of every network
        protocol across all SSP components.  Data is inherited automatically
        when components are imported; the table refreshes whenever the
        component list changes.

        Per the OSCAL schema, protocols live on individual
        system-implementation.components[] entries — there is no top-level
        protocol collection in the SSP.  This section provides a single view
        that aggregates them for review.
        """
        C = self._colors

        section("10 ·  Network Protocols")
        tk.Label(
            parent,
            text="  Network protocols exposed or used by the system's components,\n"
                 "  inherited automatically when component files are imported.\n"
                 "  Per OSCAL, protocols are stored on each individual component.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            justify="left",
        ).pack(anchor="w", padx=28)

        # Counter label — shows total protocols across all components
        self._proto10_count_lbl = tk.Label(
            parent, text="0 protocols across 0 components",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            anchor="w",
        )
        self._proto10_count_lbl.pack(anchor="w", padx=28, pady=(4, 2))

        # ── Protocol table ────────────────────────────────────────────────────
        proto10_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        proto10_frame.pack(fill="x", padx=28, pady=(0, 6))

        self._proto10_tree = ttk.Treeview(
            proto10_frame,
            columns=("component", "protocol", "title", "port_ranges"),
            show="headings", height=8, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("component",  "Component",   160, False),
            ("protocol",   "Protocol",    100, False),
            ("title",      "Title",       140, False),
            ("port_ranges","Port Ranges", 260, True),
        ]:
            self._proto10_tree.heading(col, text=heading, anchor="w")
            self._proto10_tree.column(col, width=w, anchor="w", stretch=stretch)

        proto10_scroll = ttk.Scrollbar(
            proto10_frame, orient="vertical", command=self._proto10_tree.yview,
        )
        self._proto10_tree.configure(yscrollcommand=proto10_scroll.set)
        proto10_scroll.pack(side="right", fill="y", padx=(0, 4), pady=8)
        self._proto10_tree.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=8)

        self._refresh_proto10_tree()

    def _format_port_ranges_ssp(self, port_ranges):
        """Return a compact port-range summary, e.g. 'TCP:443  UDP:53  TCP:8000-8080'."""
        parts = []
        for pr in port_ranges:
            start = pr.get("start", "")
            end   = pr.get("end",   "")
            trans = pr.get("transport", "TCP")
            if start == end or not end:
                parts.append(f"{trans}:{start}")
            else:
                parts.append(f"{trans}:{start}-{end}")
        return "  ".join(parts) if parts else "—"

    def _refresh_proto10_tree(self):
        """Rebuild the Section 10 protocol table from the current component list."""
        if not hasattr(self, "_proto10_tree"):
            return
        self._proto10_tree.delete(*self._proto10_tree.get_children())
        total_protos = 0
        comps_with_protos = set()
        for comp in self._ssp_components:
            protos = comp.get("protocols", [])
            if not protos:
                continue
            comp_title = comp.get("title", comp.get("uuid", ""))
            for proto in protos:
                port_summary = self._format_port_ranges_ssp(proto.get("port_ranges", []))
                self._proto10_tree.insert("", "end", values=(
                    comp_title,
                    proto.get("name", ""),
                    proto.get("title", ""),
                    port_summary,
                ))
                total_protos += 1
                comps_with_protos.add(comp.get("uuid", comp_title))

        n_comps = len(comps_with_protos)
        self._proto10_count_lbl.config(
            text=f"{total_protos} protocol{'s' if total_protos != 1 else ''} "
                 f"across {n_comps} component{'s' if n_comps != 1 else ''}",
        )

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
        dlg.minsize(width, 10)   # enforce minimum width; height auto-sizes to content
        return dlg

    # =========================================================================
    # SECTION 8 — SYSTEM COMPONENT METHODS
    # =========================================================================

    def _refresh_comp8_tree(self):
        """Clear and repopulate the Section 8 component table and counter."""
        self._comp8_tree.delete(*self._comp8_tree.get_children())
        for comp in self._ssp_components:
            self._comp8_tree.insert("", "end", values=(
                comp.get("type", ""),
                comp.get("title", ""),
                comp.get("status", ""),
                comp.get("description", ""),
            ))
        n = len(self._ssp_components)
        self._comp8_count_lbl.config(
            text=f"{n} component{'s' if n != 1 else ''}",
        )
        self._refresh_proto10_tree()

    def _add_ssp_component(self):
        """Show the component dialog and append the result to Section 8."""
        comp = self._ssp_component_dialog()
        if not comp:
            return
        self._ssp_components.append(comp)
        self._refresh_comp8_tree()
        # Refresh Section 9 so the component is available in the by-component
        # dropdown immediately, and dot indicators stay accurate.
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())

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
        Read one OSCAL component-definition file, import every component it
        defines into Section 8, and automatically populate Section 9 with
        by-component entries derived from each component's control responses.

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
            # Carry over protocols defined in the component file so they
            # appear in the SSP's protocol summary and OSCAL output.
            protocols = []
            for proto in c.get("protocols", []):
                prs = [
                    {
                        "start":     pr.get("start", 0),
                        "end":       pr.get("end", pr.get("start", 0)),
                        "transport": pr.get("transport", "TCP"),
                        "remarks":   pr.get("remarks", ""),
                    }
                    for pr in proto.get("port-ranges", [])
                ]
                protocols.append({
                    "name":        proto.get("name", ""),
                    "title":       proto.get("title", ""),
                    "port_ranges": prs,
                })
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
                "protocols":         protocols,
                "remarks":           c.get("remarks", ""),
            }
            was_added = self._add_ssp_component_dict(comp_dict)
            if was_added:
                added_any = True
            # Always import ctrl_responses, even if the component UUID already
            # existed. This lets the user re-import a component file to
            # populate Section 9 for an SSP that was saved before Section 9
            # existed — without duplicating the component in Section 8.
            self._import_ctrl_responses(comp_dict["uuid"], c)
        return added_any

    def _import_ctrl_responses(self, comp_uuid, oscal_component):
        """
        Walk an OSCAL component's control-implementations and add a by-component
        entry to _ssp_ctrl_impls for every control that has a description.

        Skips any control for which this component already has a by-component
        entry (so re-importing a file never duplicates responses).
        """
        for ci in oscal_component.get("control-implementations", []):
            for ir in ci.get("implemented-requirements", []):
                ctrl_id    = ir.get("control-id", "")
                description = ir.get("description", "").strip()
                if not ctrl_id or not description:
                    continue

                # Find or create the SSP-level ctrl_impl entry for this control.
                existing = next(
                    (e for e in self._ssp_ctrl_impls
                     if e["control_id"] == ctrl_id),
                    None,
                )
                if existing is None:
                    existing = {
                        "control_id":    ctrl_id,
                        "remarks":       "",
                        "by_components": [],
                    }
                    self._ssp_ctrl_impls.append(existing)

                # Only add if this component does not already have an entry
                # for this control (guards against importing the same file twice).
                if any(bc["component_uuid"] == comp_uuid
                       for bc in existing["by_components"]):
                    continue

                existing["by_components"].append({
                    "uuid":           new_uuid(),
                    "component_uuid": comp_uuid,
                    "description":    description,
                    "impl_status":    "implemented",
                    "remarks":        "",
                })

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
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())
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
        self._refresh_ctrl9_list(self._ctrl9_search_var.get())
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
                # Preserve any protocols already on the component; manual-add
                # starts with an empty list (protocols come via import).
                "protocols":         e.get("protocols", []),
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

    # =========================================================================
    # DIAGRAM METHODS (Section 4)
    # =========================================================================

    def _add_diagram(self):
        """Show a dialog to add a data flow diagram reference."""
        C   = self._colors
        dlg = self._make_dialog("Add Diagram", width=500)

        def lrow(text, width=18):
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=width, anchor="w").pack(side="left")
            return row

        v_caption = tk.StringVar()
        tk.Entry(lrow("Caption *"), textvariable=v_caption, width=42,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        v_link = tk.StringVar()
        tk.Entry(lrow("Link/Path *"), textvariable=v_link, width=42,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        v_desc = tk.StringVar()
        tk.Entry(lrow("Description"), textvariable=v_desc, width=42,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}

        def _ok():
            caption = v_caption.get().strip()
            link    = v_link.get().strip()
            if not caption:
                messagebox.showwarning("Required", "Caption is required.", parent=dlg)
                return
            if not link:
                messagebox.showwarning("Required", "Link/Path is required.", parent=dlg)
                return
            result.update({
                "uuid":        new_uuid(),
                "caption":     caption,
                "link":        link,
                "description": v_desc.get().strip(),
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

        if result:
            self._ssp["data_flow_diagrams"].append(result)
            self._diagram_tree.insert("", "end", values=(result["caption"], result["link"]))

    def _remove_diagram(self):
        """Remove the selected diagram row."""
        sel = self._diagram_tree.selection()
        if not sel:
            return
        idx = self._diagram_tree.index(sel[0])
        self._ssp["data_flow_diagrams"].pop(idx)
        self._diagram_tree.delete(sel[0])

    # =========================================================================
    # INFORMATION TYPE METHODS (Section 5)
    # =========================================================================

    @staticmethod
    def _it_row_values(it):
        """Return the 5-element values tuple for inserting into self._it_tree."""
        comps = ", ".join(f["component_title"] for f in it.get("component_flows", []))
        return (
            it["title"],
            it.get("c_impact", ""),
            it.get("i_impact", ""),
            it.get("a_impact", ""),
            comps or "—",
        )

    def _info_type_dialog(self, existing=None):
        """
        Rich modal dialog for adding or editing an information type.

        Parameters:
            existing - An existing info type dict to pre-fill, or None.

        Returns:
            A dict {uuid, title, description, c_impact, i_impact, a_impact,
                    component_flows} or None if cancelled.
        """
        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit Information Type" if existing else "Add Information Type",
            width=520,
        )

        impacts = ["fips-199-low", "fips-199-moderate", "fips-199-high"]
        directions = ["inbound", "outbound", "internal", "bidirectional"]

        def lrow(parent, text, width=18):
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=width, anchor="w").pack(side="left")
            return row

        def eentry(row, var, width=36):
            tk.Entry(row, textvariable=var, width=width,
                     bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                     relief="flat", font=("Helvetica", 11), highlightthickness=1,
                     highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        v_title = tk.StringVar(value=e.get("title", ""))
        eentry(lrow(dlg, "Title *"), v_title)

        v_desc = tk.StringVar(value=e.get("description", ""))
        eentry(lrow(dlg, "Description *"), v_desc)

        tk.Label(
            dlg,
            text="FIPS-199 impact levels: Low = breach causes limited harm  |  "
                 "Moderate = serious harm  |  High = severe or catastrophic harm",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 8, "italic"),
        ).pack(anchor="w", padx=20, pady=(4, 0))

        v_c = tk.StringVar(value=e.get("c_impact", "fips-199-moderate"))
        ttk.Combobox(lrow(dlg, "Confidentiality"), textvariable=v_c,
                     values=impacts, state="readonly", width=28).pack(side="left")

        v_i = tk.StringVar(value=e.get("i_impact", "fips-199-moderate"))
        ttk.Combobox(lrow(dlg, "Integrity"), textvariable=v_i,
                     values=impacts, state="readonly", width=28).pack(side="left")

        v_a = tk.StringVar(value=e.get("a_impact", "fips-199-moderate"))
        ttk.Combobox(lrow(dlg, "Availability"), textvariable=v_a,
                     values=impacts, state="readonly", width=28).pack(side="left")

        # ── Component Data Flows card ──────────────────────────────────────────
        flow_card = tk.Frame(
            dlg, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        flow_card.pack(fill="x", padx=20, pady=8)

        tk.Label(
            flow_card,
            text="Component Data Flows",
            bg=C["CARD_BG"], fg=C["ACCENT"],
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(6, 0))
        tk.Label(
            flow_card,
            text="Map which SSP components process, store, or transmit this information type.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=8, pady=(0, 4))

        flow_btn_row = tk.Frame(flow_card, bg=C["CARD_BG"])
        flow_btn_row.pack(fill="x", padx=8, pady=4)

        # Inner treeview for flows
        flow_tree_frame = tk.Frame(flow_card, bg=C["CARD_BG"])
        flow_tree_frame.pack(fill="x", padx=8, pady=(0, 8))

        flow_tree = ttk.Treeview(
            flow_tree_frame,
            columns=("component", "direction"),
            show="headings", height=4, selectmode="browse",
        )
        flow_tree.heading("component",  text="Component",  anchor="w")
        flow_tree.heading("direction",  text="Direction",  anchor="w")
        flow_tree.column("component",  width=220, anchor="w", stretch=False)
        flow_tree.column("direction",  width=120, anchor="w", stretch=False)
        flow_tree.pack(side="left", fill="x", expand=True)

        # Working list of flows (copy so cancel doesn't mutate original)
        flows = list(e.get("component_flows", []))
        for fl in flows:
            flow_tree.insert("", "end", values=(fl["component_title"], fl["direction"]))

        def _add_flow():
            """Inner dialog: pick a component and direction."""
            if not self._ssp_components:
                messagebox.showinfo(
                    "No components",
                    "Add components in Section 8 before mapping data flows.",
                    parent=dlg,
                )
                return
            C2  = self._colors
            d2  = self._make_dialog("Add Component Flow", width=380)

            choices = []
            label_to_uuid = {}
            for comp in self._ssp_components:
                lbl = comp.get("title", "(untitled)")
                choices.append(lbl)
                label_to_uuid[lbl] = comp["uuid"]

            def lrow2(text):
                row = tk.Frame(d2, bg=C2["BG"])
                row.pack(fill="x", padx=20, pady=4)
                tk.Label(row, text=text, bg=C2["BG"], fg=C2["SUBTEXT"],
                         font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
                return row

            v_comp = tk.StringVar(value=choices[0] if choices else "")
            ttk.Combobox(lrow2("Component *"), textvariable=v_comp,
                         values=choices, state="readonly", width=28).pack(side="left")

            v_dir = tk.StringVar(value="internal")
            ttk.Combobox(lrow2("Direction *"), textvariable=v_dir,
                         values=directions, state="readonly", width=28).pack(side="left")

            inner_result = {}

            def _ok2():
                comp_lbl = v_comp.get()
                if not comp_lbl:
                    messagebox.showwarning("Required", "Select a component.", parent=d2)
                    return
                inner_result.update({
                    "component_uuid":  label_to_uuid[comp_lbl],
                    "component_title": comp_lbl,
                    "direction":       v_dir.get(),
                })
                d2.destroy()

            btn2 = tk.Frame(d2, bg=C2["BG"])
            btn2.pack(pady=12)
            tk.Button(btn2, text="  OK  ", command=_ok2,
                      bg=C2["ACCENT"], fg=C2["BG"], font=("Helvetica", 11, "bold"),
                      relief="flat", padx=10).pack(side="left", padx=8)
            tk.Button(btn2, text="Cancel", command=d2.destroy,
                      bg=C2["HEADER_BG"], fg=C2["TEXT"], font=("Helvetica", 11),
                      relief="flat", padx=10).pack(side="left")
            d2.wait_window()

            if inner_result:
                flows.append(inner_result)
                flow_tree.insert("", "end", values=(
                    inner_result["component_title"], inner_result["direction"]
                ))

        def _remove_flow():
            sel = flow_tree.selection()
            if not sel:
                return
            idx = flow_tree.index(sel[0])
            flows.pop(idx)
            flow_tree.delete(sel[0])

        tk.Button(
            flow_btn_row, text="＋  Add",
            command=_add_flow,
            bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            flow_btn_row, text="✕  Remove",
            command=_remove_flow,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)

        # ── OK / Cancel ────────────────────────────────────────────────────────
        result = {}

        def _ok():
            title = v_title.get().strip()
            desc  = v_desc.get().strip()
            if not title:
                messagebox.showwarning("Required", "Title is required.", parent=dlg)
                return
            if not desc:
                messagebox.showwarning("Required", "Description is required.", parent=dlg)
                return
            result.update({
                "uuid":            e.get("uuid") or new_uuid(),
                "title":           title,
                "description":     desc,
                "c_impact":        v_c.get(),
                "i_impact":        v_i.get(),
                "a_impact":        v_a.get(),
                "component_flows": list(flows),
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

    def _add_info_type(self):
        """Show the information type dialog and add the result."""
        res = self._info_type_dialog()
        if not res:
            return
        self._ssp["information_types"].append(res)
        self._it_tree.insert("", "end", values=self._it_row_values(res))

    def _edit_info_type(self):
        """Edit the selected information type in place."""
        sel = self._it_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an information type to edit.")
            return
        idx  = self._it_tree.index(sel[0])
        item = self._ssp["information_types"][idx]
        updated = self._info_type_dialog(existing=item)
        if not updated:
            return
        self._ssp["information_types"][idx] = updated
        # Replace the treeview row at the same position
        self._it_tree.delete(sel[0])
        self._it_tree.insert("", idx, values=self._it_row_values(updated))

    # =========================================================================
    # SET-PARAMETER METHODS (Section 9b)
    # =========================================================================

    def _sp_row_values(self, sp):
        return (sp["param_id"], ", ".join(sp.get("values", [])), sp.get("remarks", ""))

    def _set_param_dialog(self, existing=None):
        """Modal dialog to add or edit a control-implementation set-parameter."""
        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit Parameter Override" if existing else "Add Parameter Override",
            width=460,
        )

        def lrow(text):
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
            return row

        v_param = tk.StringVar(value=e.get("param_id", ""))
        tk.Entry(lrow("Parameter ID *"), textvariable=v_param, width=36,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        v_values = tk.StringVar(value=", ".join(e.get("values", [])))
        tk.Entry(lrow("Values *"), textvariable=v_values, width=36,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)
        tk.Label(dlg, text="  (comma-separated list of values)",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        v_remarks = tk.StringVar(value=e.get("remarks", ""))
        tk.Entry(lrow("Remarks"), textvariable=v_remarks, width=36,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}

        def _ok():
            pid = v_param.get().strip()
            if not pid:
                messagebox.showwarning("Required", "Parameter ID is required.", parent=dlg)
                return
            raw_vals = v_values.get()
            values = [v.strip() for v in raw_vals.split(",") if v.strip()]
            if not values:
                messagebox.showwarning("Required", "At least one value is required.", parent=dlg)
                return
            result.update({
                "param_id": pid,
                "values":   values,
                "remarks":  v_remarks.get().strip(),
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

    def _add_set_param(self):
        sp = self._set_param_dialog()
        if not sp:
            return
        self._ssp_set_params.append(sp)
        self._sp_tree.insert("", "end", values=self._sp_row_values(sp))

    def _edit_set_param(self):
        sel = self._sp_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a parameter override to edit.")
            return
        idx = self._sp_tree.index(sel[0])
        updated = self._set_param_dialog(existing=self._ssp_set_params[idx])
        if not updated:
            return
        self._ssp_set_params[idx] = updated
        self._sp_tree.delete(sel[0])
        self._sp_tree.insert("", idx, values=self._sp_row_values(updated))

    def _remove_set_param(self):
        sel = self._sp_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a parameter override to remove.")
            return
        idx = self._sp_tree.index(sel[0])
        self._ssp_set_params.pop(idx)
        self._sp_tree.delete(sel[0])

    # =========================================================================
    # SECTION 11 — SYSTEM USERS
    # =========================================================================

    def _build_section11(self, parent, section):
        C = self._colors

        section("11 ·  System Users")
        tk.Label(
            parent,
            text="  People or entities that interact with the system (e.g. administrators,\n"
                 "  operators, end-users). Each user can be assigned one or more role IDs.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            justify="left",
        ).pack(anchor="w", padx=28)

        usr_btn = tk.Frame(parent, bg=C["BG"])
        usr_btn.pack(fill="x", padx=28, pady=4)
        tk.Button(usr_btn, text="＋  Add User", command=self._add_ssp_user,
                  bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left")
        tk.Button(usr_btn, text="✏  Edit Selected", command=self._edit_ssp_user,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left", padx=6)
        tk.Button(usr_btn, text="✕  Remove", command=self._remove_ssp_user,
                  bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left", padx=6)

        usr_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        usr_frame.pack(fill="x", padx=28, pady=(0, 6))

        self._usr_tree = ttk.Treeview(
            usr_frame,
            columns=("title", "short_name", "role_ids", "description"),
            show="headings", height=5, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("title",       "Title",       180, False),
            ("short_name",  "Short Name",  120, False),
            ("role_ids",    "Role IDs",    180, False),
            ("description", "Description", 260, True),
        ]:
            self._usr_tree.heading(col, text=heading, anchor="w")
            self._usr_tree.column(col, width=w, anchor="w", stretch=stretch)

        usr_scroll = ttk.Scrollbar(usr_frame, orient="vertical",
                                   command=self._usr_tree.yview)
        self._usr_tree.configure(yscrollcommand=usr_scroll.set)
        usr_scroll.pack(side="right", fill="y", padx=(0, 4), pady=8)
        self._usr_tree.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=8)

    def _usr_row_values(self, u):
        return (
            u.get("title", ""),
            u.get("short_name", ""),
            ", ".join(u.get("role_ids", [])),
            u.get("description", ""),
        )

    def _ssp_user_dialog(self, existing=None):
        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit System User" if existing else "Add System User", width=460
        )

        def lrow(text):
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=4)
            tk.Label(row, text=text, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
            return row

        def eentry(row, var, width=36):
            tk.Entry(row, textvariable=var, width=width,
                     bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                     relief="flat", font=("Helvetica", 11), highlightthickness=1,
                     highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        v_title      = tk.StringVar(value=e.get("title", ""))
        eentry(lrow("Title *"), v_title)

        v_short_name = tk.StringVar(value=e.get("short_name", ""))
        eentry(lrow("Short Name"), v_short_name)

        v_role_ids   = tk.StringVar(value=", ".join(e.get("role_ids", [])))
        eentry(lrow("Role IDs"), v_role_ids)
        tk.Label(dlg, text="  (comma-separated role IDs, e.g. system-owner, isso)",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        # Description (multi-line)
        tk.Label(dlg, text="Description", bg=C["BG"], fg=C["SUBTEXT"],
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

        v_remarks = tk.StringVar(value=e.get("remarks", ""))
        eentry(lrow("Remarks"), v_remarks)

        result = {}

        def _ok():
            title = v_title.get().strip()
            if not title:
                messagebox.showwarning("Required", "Title is required.", parent=dlg)
                return
            roles = [r.strip() for r in v_role_ids.get().split(",") if r.strip()]
            result.update({
                "uuid":        e.get("uuid") or new_uuid(),
                "title":       title,
                "short_name":  v_short_name.get().strip(),
                "description": t_desc.get("1.0", "end-1c").strip(),
                "role_ids":    roles,
                "remarks":     v_remarks.get().strip(),
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

    def _add_ssp_user(self):
        u = self._ssp_user_dialog()
        if not u:
            return
        self._ssp_users.append(u)
        self._usr_tree.insert("", "end", values=self._usr_row_values(u))

    def _edit_ssp_user(self):
        sel = self._usr_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a user to edit.")
            return
        idx = self._usr_tree.index(sel[0])
        updated = self._ssp_user_dialog(existing=self._ssp_users[idx])
        if not updated:
            return
        updated["uuid"] = self._ssp_users[idx]["uuid"]
        self._ssp_users[idx] = updated
        self._usr_tree.delete(sel[0])
        self._usr_tree.insert("", idx, values=self._usr_row_values(updated))

    def _remove_ssp_user(self):
        sel = self._usr_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a user to remove.")
            return
        idx = self._usr_tree.index(sel[0])
        self._ssp_users.pop(idx)
        self._usr_tree.delete(sel[0])

    # =========================================================================
    # SECTION 12 — INVENTORY ITEMS
    # =========================================================================

    def _build_section12(self, parent, section):
        C = self._colors

        section("12 ·  Inventory Items")
        tk.Label(
            parent,
            text="  Hardware, software, and service assets that make up the system.\n"
                 "  Link each item to the components that implement it.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            justify="left",
        ).pack(anchor="w", padx=28)

        inv_btn = tk.Frame(parent, bg=C["BG"])
        inv_btn.pack(fill="x", padx=28, pady=4)
        tk.Button(inv_btn, text="＋  Add Item", command=self._add_inv_item,
                  bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left")
        tk.Button(inv_btn, text="✏  Edit Selected", command=self._edit_inv_item,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left", padx=6)
        tk.Button(inv_btn, text="✕  Remove", command=self._remove_inv_item,
                  bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left", padx=6)

        inv_frame = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        inv_frame.pack(fill="x", padx=28, pady=(0, 6))

        self._inv_tree = ttk.Treeview(
            inv_frame,
            columns=("description", "props", "components"),
            show="headings", height=5, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("description", "Description", 300, True),
            ("props",       "Properties",  200, False),
            ("components",  "Components",  200, False),
        ]:
            self._inv_tree.heading(col, text=heading, anchor="w")
            self._inv_tree.column(col, width=w, anchor="w", stretch=stretch)

        inv_scroll = ttk.Scrollbar(inv_frame, orient="vertical",
                                   command=self._inv_tree.yview)
        self._inv_tree.configure(yscrollcommand=inv_scroll.set)
        inv_scroll.pack(side="right", fill="y", padx=(0, 4), pady=8)
        self._inv_tree.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=8)

    def _inv_row_values(self, ii):
        props_str = ", ".join(
            f"{p['name']}={p['value']}" for p in ii.get("props", [])
        )
        comp_titles = ", ".join(
            self._comp_title_for_uuid(c) for c in ii.get("implemented_components", [])
        )
        return (ii.get("description", ""), props_str or "—", comp_titles or "—")

    def _inv_item_dialog(self, existing=None):
        C   = self._colors
        e   = existing or {}
        dlg = self._make_dialog(
            "Edit Inventory Item" if existing else "Add Inventory Item", width=520
        )

        # Description (required, multi-line)
        tk.Label(dlg, text="Description *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(anchor="w", padx=20, pady=(10, 2))
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

        # Properties sub-table
        tk.Label(dlg, text="Properties", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=20, pady=(10, 2))
        prop_card = tk.Frame(dlg, bg=C["CARD_BG"],
                             highlightthickness=1, highlightbackground=C["HEADER_BG"])
        prop_card.pack(fill="x", padx=20, pady=(0, 4))
        prop_btn_row = tk.Frame(prop_card, bg=C["CARD_BG"])
        prop_btn_row.pack(fill="x", padx=6, pady=4)

        prop_tree = ttk.Treeview(prop_card, columns=("name", "value"),
                                 show="headings", height=3, selectmode="browse")
        prop_tree.heading("name",  text="Name",  anchor="w")
        prop_tree.heading("value", text="Value", anchor="w")
        prop_tree.column("name",  width=160, anchor="w", stretch=False)
        prop_tree.column("value", width=240, anchor="w", stretch=True)
        prop_tree.pack(fill="x", padx=6, pady=(0, 6))

        props = list(e.get("props", []))
        for p in props:
            prop_tree.insert("", "end", values=(p["name"], p["value"]))

        def _add_prop():
            res = self._dialog("Add Property", [
                ("Name *",  "name",  "", None),
                ("Value *", "value", "", None),
            ])
            if not res or not res.get("name") or not res.get("value"):
                return
            props.append(res)
            prop_tree.insert("", "end", values=(res["name"], res["value"]))

        def _remove_prop():
            sel = prop_tree.selection()
            if not sel:
                return
            idx = prop_tree.index(sel[0])
            props.pop(idx)
            prop_tree.delete(sel[0])

        tk.Button(prop_btn_row, text="＋  Add", command=_add_prop,
                  bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                  relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left")
        tk.Button(prop_btn_row, text="✕  Remove", command=_remove_prop,
                  bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=6)

        # Implemented components (multi-select from Section 8)
        tk.Label(dlg, text="Implemented Components", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11, "bold")).pack(anchor="w", padx=20, pady=(8, 2))

        impl_comps = list(e.get("implemented_components", []))

        if self._ssp_components:
            comp_choices = [(c["uuid"], c.get("title", c["uuid"]))
                            for c in self._ssp_components]
            impl_card = tk.Frame(dlg, bg=C["CARD_BG"],
                                 highlightthickness=1, highlightbackground=C["HEADER_BG"])
            impl_card.pack(fill="x", padx=20, pady=(0, 4))
            impl_btn_row = tk.Frame(impl_card, bg=C["CARD_BG"])
            impl_btn_row.pack(fill="x", padx=6, pady=4)

            impl_tree = ttk.Treeview(impl_card, columns=("title",),
                                     show="headings", height=3, selectmode="browse")
            impl_tree.heading("title", text="Component", anchor="w")
            impl_tree.column("title", width=360, anchor="w", stretch=True)
            impl_tree.pack(fill="x", padx=6, pady=(0, 6))

            comp_title_map = {c["uuid"]: c.get("title", c["uuid"])
                              for c in self._ssp_components}
            for c_uuid in impl_comps:
                impl_tree.insert("", "end",
                                 values=(comp_title_map.get(c_uuid, c_uuid),),
                                 iid=c_uuid)

            def _add_impl_comp():
                available = [(u, t) for u, t in comp_choices
                             if u not in impl_comps]
                if not available:
                    messagebox.showinfo("No components",
                                        "All Section 8 components are already linked.",
                                        parent=dlg)
                    return
                choices_labels = [t for _, t in available]
                label_to_uuid  = {t: u for u, t in available}
                res = self._dialog("Link Component", [
                    ("Component *", "comp", choices_labels[0], choices_labels),
                ])
                if not res or not res.get("comp"):
                    return
                c_uuid = label_to_uuid[res["comp"]]
                impl_comps.append(c_uuid)
                impl_tree.insert("", "end",
                                 values=(comp_title_map.get(c_uuid, c_uuid),),
                                 iid=c_uuid)

            def _remove_impl_comp():
                sel = impl_tree.selection()
                if not sel:
                    return
                c_uuid = sel[0]
                impl_comps.remove(c_uuid)
                impl_tree.delete(c_uuid)

            tk.Button(impl_btn_row, text="＋  Link Component",
                      command=_add_impl_comp,
                      bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                      relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left")
            tk.Button(impl_btn_row, text="✕  Unlink", command=_remove_impl_comp,
                      bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                      relief="flat", padx=8, pady=2, cursor="hand2").pack(side="left", padx=6)
        else:
            tk.Label(dlg,
                     text="  Add components in Section 8 to link them to inventory items.",
                     bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                     ).pack(anchor="w", padx=20)

        # Remarks
        v_remarks = tk.StringVar(value=e.get("remarks", ""))
        rem_row = tk.Frame(dlg, bg=C["BG"])
        rem_row.pack(fill="x", padx=20, pady=4)
        tk.Label(rem_row, text="Remarks", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        tk.Entry(rem_row, textvariable=v_remarks, width=36,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}

        def _ok():
            desc = t_desc.get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Required", "Description is required.", parent=dlg)
                return
            result.update({
                "uuid":                   e.get("uuid") or new_uuid(),
                "description":            desc,
                "props":                  list(props),
                "implemented_components": list(impl_comps),
                "remarks":                v_remarks.get().strip(),
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

    def _add_inv_item(self):
        ii = self._inv_item_dialog()
        if not ii:
            return
        self._ssp_inv_items.append(ii)
        self._inv_tree.insert("", "end", values=self._inv_row_values(ii))

    def _edit_inv_item(self):
        sel = self._inv_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an inventory item to edit.")
            return
        idx = self._inv_tree.index(sel[0])
        updated = self._inv_item_dialog(existing=self._ssp_inv_items[idx])
        if not updated:
            return
        updated["uuid"] = self._ssp_inv_items[idx]["uuid"]
        self._ssp_inv_items[idx] = updated
        self._inv_tree.delete(sel[0])
        self._inv_tree.insert("", idx, values=self._inv_row_values(updated))

    def _remove_inv_item(self):
        sel = self._inv_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an inventory item to remove.")
            return
        idx = self._inv_tree.index(sel[0])
        self._ssp_inv_items.pop(idx)
        self._inv_tree.delete(sel[0])

    def _add_responsible_party(self):
        """
        Show a dialog to add a responsible-party mapping (role → party).

        The role dropdown is populated from the roles defined in Section 6.
        The party dropdown is populated from the parties defined in Section 7.
        """
        roles   = [r["role_id"] for r in self._ssp.get("roles",   []) if r.get("role_id")]
        parties = self._ssp.get("parties", [])
        if not roles:
            messagebox.showinfo(
                "No roles defined",
                "Add at least one role in Section 6 before assigning responsible parties."
            )
            return
        if not parties:
            messagebox.showinfo(
                "No parties defined",
                "Add at least one party in Section 7 before assigning responsible parties."
            )
            return

        # Build a label → uuid mapping so the dropdown shows names, not UUIDs
        party_labels = [f"{p['name']}  ({p['type']})" for p in parties]
        party_by_label = {
            f"{p['name']}  ({p['type']})": p["uuid"] for p in parties
        }

        C = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Add Responsible Party")
        dlg.configure(bg=C["BG"])
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        tk.Label(dlg, text="Role ID *",    bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 10)).grid(row=0, column=0, sticky="w", padx=16, pady=(16,4))
        tk.Label(dlg, text="Party *",      bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 10)).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 4))
        tk.Label(dlg, text="Remarks",      bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 10)).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 4))

        v_role    = tk.StringVar(value=roles[0])
        v_party   = tk.StringVar(value=party_labels[0])
        v_remarks = tk.StringVar()

        ttk.Combobox(dlg, textvariable=v_role,  values=roles,        state="readonly",
                     width=30).grid(row=0, column=1, padx=16, pady=(16, 4))
        ttk.Combobox(dlg, textvariable=v_party, values=party_labels, state="readonly",
                     width=30).grid(row=1, column=1, padx=16, pady=(0, 4))
        tk.Entry(dlg, textvariable=v_remarks,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10),
                 width=32).grid(row=2, column=1, padx=16, pady=(0, 4))

        result = {}

        def _ok():
            role_id    = v_role.get().strip()
            party_lbl  = v_party.get()
            party_uuid = party_by_label.get(party_lbl, "")
            if not role_id or not party_uuid:
                messagebox.showwarning("Required", "Please select a role and a party.",
                                       parent=dlg)
                return
            result["role_id"]     = role_id
            result["party_uuid"]  = party_uuid
            result["party_name"]  = v_party.get().split("  (")[0]
            result["remarks"]     = v_remarks.get().strip()
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=C["BG"])
        btn_row.grid(row=3, column=0, columnspan=2, pady=12)
        tk.Button(btn_row, text="OK",     command=_ok,          bg=C["GREEN"],
                  fg=C["BG"], font=("Helvetica", 10, "bold"), relief="flat",
                  padx=12, pady=4, cursor="hand2").pack(side="left", padx=6)
        tk.Button(btn_row, text="Cancel", command=dlg.destroy,  bg=C["HEADER_BG"],
                  fg=C["TEXT"], font=("Helvetica", 10), relief="flat",
                  padx=12, pady=4, cursor="hand2").pack(side="left", padx=6)

        self.wait_window(dlg)
        if not result:
            return

        # Store internally and add to treeview
        rp_list = self._ssp.setdefault("responsible_parties", [])
        rp_list.append(result)
        self._rp_tree.insert("", "end",
                             values=(result["role_id"], result["party_name"]))
        self._dirty = True

    def _remove_responsible_party(self):
        """Remove the selected responsible-party row."""
        sel = self._rp_tree.selection()
        if not sel:
            messagebox.showinfo("No selection",
                                "Select a responsible party row to remove.")
            return
        idx = self._rp_tree.index(sel[0])
        self._ssp.setdefault("responsible_parties", []).pop(idx)
        self._rp_tree.delete(sel[0])
        self._dirty = True

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
        self._dirty = True

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
        self._dirty = True

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
        self._dirty = True   # Any collection means the user has edited something
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

        # Sections 8, 9, 11, 12 are edited in their own working lists; copy them
        # back into the canonical SSP dict so they are included when building OSCAL.
        self._ssp["components"]           = self._ssp_components
        self._ssp["ctrl_implementations"] = self._ssp_ctrl_impls
        self._ssp["set_parameters"]       = self._ssp_set_params
        self._ssp["users"]                = self._ssp_users
        self._ssp["inventory_items"]      = self._ssp_inv_items

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

        # Rebuild the diagram tree (Section 4)
        self._diagram_tree.delete(*self._diagram_tree.get_children())
        for d in ssp.get("data_flow_diagrams", []):
            self._diagram_tree.insert("", "end", values=(d.get("caption", ""), d.get("link", "")))

        # Rebuild the information types table
        self._it_tree.delete(*self._it_tree.get_children())
        for it in ssp.get("information_types", []):
            self._it_tree.insert("", "end", values=self._it_row_values(it))

        # Rebuild the roles table
        self._role_tree.delete(*self._role_tree.get_children())
        for r in ssp.get("roles", []):
            self._role_tree.insert("", "end", values=(r["role_id"], r["title"]))

        # Rebuild the parties table
        self._party_tree.delete(*self._party_tree.get_children())
        for p in ssp.get("parties", []):
            self._party_tree.insert("", "end",
                values=(p["type"], p["name"], p.get("email", "")))

        # Rebuild the responsible parties table (Section 7b)
        self._rp_tree.delete(*self._rp_tree.get_children())
        for rp in ssp.get("responsible_parties", []):
            self._rp_tree.insert("", "end",
                values=(rp.get("role_id", ""), rp.get("party_name", rp.get("party_uuid", ""))))

        # ── Sections 8, 9, 11, 12: load working lists and rebuild widgets ────────
        # list(...) makes shallow copies so editing the form does not mutate the
        # parsed dict until _collect() copies them back.
        self._ssp_components = list(ssp.get("components", []))
        self._ssp_ctrl_impls = list(ssp.get("ctrl_implementations", []))
        self._ssp_set_params = list(ssp.get("set_parameters", []))
        self._ssp_users      = list(ssp.get("users", []))
        self._ssp_inv_items  = list(ssp.get("inventory_items", []))
        self._sel_ctrl_id    = None

        # Rebuild set-parameters tree
        self._sp_tree.delete(*self._sp_tree.get_children())
        for sp in self._ssp_set_params:
            self._sp_tree.insert("", "end", values=self._sp_row_values(sp))

        # Rebuild users tree
        self._usr_tree.delete(*self._usr_tree.get_children())
        for u in self._ssp_users:
            self._usr_tree.insert("", "end", values=self._usr_row_values(u))

        # Rebuild inventory items tree
        self._inv_tree.delete(*self._inv_tree.get_children())
        for ii in self._ssp_inv_items:
            self._inv_tree.insert("", "end", values=self._inv_row_values(ii))

        # If the SSP was saved before Section 9 existed (or was saved without
        # any control implementations), try to auto-populate _ssp_ctrl_impls
        # from the Component Editor's currently-loaded components. This lets
        # the user open an old SSP and immediately see Applied Controls without
        # having to re-import their component files.
        if not self._ssp_ctrl_impls and self._ssp_components:
            self._rebuild_ctrl_impls_from_component_editor()

        # Back-fill protocols for components that were saved without them
        # (SSPs saved before protocol support was added, or components added
        # manually).  Only fills components that have no protocols stored yet.
        if self._ssp_components:
            self._rebuild_protocols_from_component_editor()

        self._refresh_comp8_tree()
        self._refresh_ctrl9_list()
        self._refresh_bycomp_tree()
        # Population from a saved file is not a user edit — reset dirty flag
        self._dirty = False

    def _rebuild_ctrl_impls_from_component_editor(self):
        """
        Auto-populate _ssp_ctrl_impls by cross-referencing the SSP's components
        against the Component Editor's currently-loaded components.

        Called when opening an SSP that has components but no stored control
        implementations — typically an SSP saved before Section 9 was added, or
        one built manually without using the import-file feature.

        For each component in the SSP whose UUID matches a component loaded in
        the Component Editor, the component's ctrl_responses dict is walked and
        converted into by-component entries. This is identical to what
        _import_ctrl_responses does when importing from a file, but uses the
        in-memory Component Editor data instead.

        If the Component Editor has no components loaded, this is a no-op —
        the user can still populate Section 9 manually or by re-importing files.
        """
        # Build a UUID → Component Editor component dict lookup
        loaded = {c.get("uuid", ""): c for c in self._get_components()}
        if not loaded:
            return

        for ssp_comp in self._ssp_components:
            comp_uuid = ssp_comp.get("uuid", "")
            if comp_uuid not in loaded:
                continue

            editor_comp = loaded[comp_uuid]
            for ctrl_id, desc in editor_comp.get("ctrl_responses", {}).items():
                if not desc.strip():
                    continue

                # Find or create the SSP-level entry for this control.
                existing = next(
                    (e for e in self._ssp_ctrl_impls
                     if e["control_id"] == ctrl_id),
                    None,
                )
                if existing is None:
                    existing = {
                        "control_id":    ctrl_id,
                        "remarks":       "",
                        "by_components": [],
                    }
                    self._ssp_ctrl_impls.append(existing)

                # Guard against duplicates in case this method is called twice.
                if any(bc["component_uuid"] == comp_uuid
                       for bc in existing["by_components"]):
                    continue

                existing["by_components"].append({
                    "uuid":           new_uuid(),
                    "component_uuid": comp_uuid,
                    "description":    desc,
                    "impl_status":    "implemented",
                    "remarks":        "",
                })

    def _rebuild_protocols_from_component_editor(self):
        """
        Auto-populate protocols on SSP components by cross-referencing their
        UUIDs against the Component Editor's currently-loaded components.

        Called when opening an SSP whose components have no protocols stored —
        typically an SSP saved before protocol support was added, or one whose
        components were added manually rather than imported from a file.

        Mutates self._ssp_components in place: any component with an empty
        protocols list whose UUID matches a loaded Component Editor component
        gets its protocols replaced with the editor's current data.
        If the Component Editor has no components loaded, this is a no-op.
        """
        loaded = {c.get("uuid", ""): c for c in self._get_components()}
        if not loaded:
            return
        for ssp_comp in self._ssp_components:
            # Only backfill components that have no protocols already stored.
            if ssp_comp.get("protocols"):
                continue
            editor_comp = loaded.get(ssp_comp.get("uuid", ""))
            if editor_comp and editor_comp.get("protocols"):
                ssp_comp["protocols"] = editor_comp["protocols"]

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
        for tree in (self._diagram_tree, self._it_tree, self._role_tree, self._party_tree):
            tree.delete(*tree.get_children())
        self._ssp["data_flow_diagrams"] = []

        # ── Reset Sections 8, 9, 11, 12 working state and widgets ────────────
        self._ssp_components = []
        self._ssp_ctrl_impls = []
        self._ssp_set_params = []
        self._ssp_users      = []
        self._ssp_inv_items  = []
        self._sel_comp_index = None
        self._sel_ctrl_id    = None
        self._refresh_comp8_tree()
        self._refresh_ctrl9_list()
        self._refresh_bycomp_tree()
        for tree in (self._sp_tree, self._usr_tree, self._inv_tree):
            tree.delete(*tree.get_children())

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

        doc = build_ssp_docx(self._ssp, catalog=self._get_catalog())
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

    # =========================================================================
    # DRAW.IO DIAGRAM EXPORT
    # =========================================================================

    def _export_drawio(self):
        """
        Export a three-tier draw.io diagram showing:

            System  →  Capabilities  →  Components

        The diagram is saved as a .drawio XML file that can be opened directly
        in draw.io (desktop app or app.diagrams.net in a browser).

        Layout logic:
          1. Capabilities (loaded in the Capability Editor) are placed first,
             with their member components positioned beneath them.
          2. Any SSP components that are NOT already part of a capability are
             placed in a separate column on the right labelled "Uncategorised".
          3. The system node sits at the top, with arrows pointing down to each
             capability and to the uncategorised group (if any).

        Component boxes are colour-coded by type so the diagram is easy to read
        at a glance:
          - policy   → amber
          - software → blue
          - hardware → green
          - service  → purple
          - others   → grey
        """
        from tkinter import filedialog
        import xml.etree.ElementTree as ET

        # ── Gather data ───────────────────────────────────────────────────────

        # Read the current SSP form values into the internal dict so we have
        # the latest system name even if the user hasn't saved yet.
        self._collect()
        system_name = self._ssp.get("system_name") or self._ssp.get("title") or "System"

        # Get capabilities from the Capability Editor tab.
        capabilities = self._get_capabilities()

        # Build a set of all component UUIDs that appear in at least one
        # capability, so we know which SSP components are uncategorised.
        cap_component_uuids = set()
        for cap in capabilities:
            for uuid in cap.get("member_uuids", []):
                cap_component_uuids.add(uuid)

        # Get all components from the SSP's Section 8 list.
        ssp_components = self._ssp.get("components", [])

        # Separate SSP components into those covered by a capability and those
        # that are standalone (not referenced by any capability).
        uncategorised = [
            c for c in ssp_components
            if c.get("uuid", "") not in cap_component_uuids
        ]

        # Also pull the component details dictionary from the Component Editor
        # so we can look up titles and types by UUID.
        all_components = {c["uuid"]: c for c in self._get_components() if "uuid" in c}

        # ── Draw.io XML structure ─────────────────────────────────────────────
        # A draw.io file is XML with this hierarchy:
        #   <mxGraphModel>
        #     <root>
        #       <mxCell id="0"/>          ← required root cell
        #       <mxCell id="1" parent="0"/>  ← required default layer
        #       ... your nodes and edges ...
        #     </root>
        #   </mxGraphModel>
        #
        # Each node is an mxCell with vertex="1"; each arrow is an mxCell with
        # edge="1" and source/target attributes pointing to other cell ids.

        root_el = ET.Element("mxGraphModel",
                             dx="1422", dy="762", grid="1", gridSize="10",
                             guides="1", tooltips="1", connect="1", arrows="1",
                             fold="1", page="1", pageScale="1",
                             pageWidth="1169", pageHeight="827",
                             math="0", shadow="0")
        root_node = ET.SubElement(root_el, "root")

        # draw.io requires these two sentinel cells to exist.
        ET.SubElement(root_node, "mxCell", id="0")
        ET.SubElement(root_node, "mxCell", id="1", parent="0")

        # Counter for generating unique cell IDs — draw.io needs every cell
        # to have a unique string ID within the file.
        _id_counter = [2]

        def next_id():
            """Return the next unique cell ID as a string."""
            _id_counter[0] += 1
            return str(_id_counter[0])

        def add_node(label, x, y, width, height, style):
            """
            Add a rectangular node (vertex) to the draw.io diagram.

            Parameters:
                label  - Text shown inside the box
                x, y   - Top-left position in pixels
                width  - Box width in pixels
                height - Box height in pixels
                style  - draw.io style string controlling colour and shape

            Returns the unique cell ID, which can be used as a source or
            target for edges.
            """
            cid = next_id()
            cell = ET.SubElement(root_node, "mxCell",
                                 id=cid, value=label, style=style,
                                 vertex="1", parent="1")
            ET.SubElement(cell, "mxGeometry",
                          x=str(x), y=str(y),
                          width=str(width), height=str(height),
                          **{"as": "geometry"})
            return cid

        def add_edge(source_id, target_id, label=""):
            """
            Add an arrow (edge) from source_id to target_id.

            Parameters:
                source_id - Cell ID of the arrow's tail (start)
                target_id - Cell ID of the arrow's head (end)
                label     - Optional text to show along the arrow
            """
            eid = next_id()
            edge_style = (
                "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;"
                "jettySize=auto;exitX=0.5;exitY=1;exitDx=0;exitDy=0;"
                "entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
            )
            cell = ET.SubElement(root_node, "mxCell",
                                 id=eid, value=label, style=edge_style,
                                 edge="1", source=source_id, target=target_id,
                                 parent="1")
            ET.SubElement(cell, "mxGeometry", relative="1", **{"as": "geometry"})

        # ── Colour map: component type → draw.io fill and stroke colours ─────
        # Each component type gets a distinct background colour so the diagram
        # is easy to read without needing a legend.
        TYPE_STYLES = {
            "policy":    "fillColor=#FFE6CC;strokeColor=#d6b656;fontColor=#333333;",
            "software":  "fillColor=#DAE8FC;strokeColor=#6c8ebf;fontColor=#333333;",
            "hardware":  "fillColor=#D5E8D4;strokeColor=#82b366;fontColor=#333333;",
            "service":   "fillColor=#E1D5E7;strokeColor=#9673a6;fontColor=#333333;",
            "process":   "fillColor=#FFF2CC;strokeColor=#d6b656;fontColor=#333333;",
            "procedure": "fillColor=#FFF2CC;strokeColor=#d6b656;fontColor=#333333;",
            "plan":      "fillColor=#FFF2CC;strokeColor=#d6b656;fontColor=#333333;",
        }
        # Default style for types not in the map above.
        DEFAULT_COMP_STYLE = "fillColor=#f5f5f5;strokeColor=#666666;fontColor=#333333;"

        def comp_style(comp_type):
            """Return the draw.io style string for a given component type."""
            base = TYPE_STYLES.get(comp_type, DEFAULT_COMP_STYLE)
            return (
                f"{base}"
                "rounded=1;whiteSpace=wrap;html=1;"
                "arcSize=20;fontSize=10;"
            )

        # ── Layout constants ──────────────────────────────────────────────────
        # All measurements are in pixels. draw.io uses a default 1px = 1 unit.
        SYSTEM_W,  SYSTEM_H  = 280, 60   # System node (top)
        CAP_W,     CAP_H     = 200, 50   # Capability node (middle row)
        COMP_W,    COMP_H    = 180, 44   # Component node (bottom row)

        PAGE_MARGIN   = 40    # Gap from the left/top edge of the page
        CAP_GAP       = 30    # Horizontal gap between capability columns
        COMP_GAP      = 10    # Vertical gap between component boxes in a column
        ROW_GAP_1     = 80    # Vertical gap: system → capability row
        ROW_GAP_2     = 60    # Vertical gap: capability → first component

        # ── Compute column widths ─────────────────────────────────────────────
        # Each capability gets its own column wide enough to hold its components.
        # The column width is the wider of CAP_W and COMP_W.
        col_width = max(CAP_W, COMP_W)

        # ── Place the system node at the top centre ───────────────────────────
        # We'll figure out the total diagram width after laying out the columns,
        # then reposition the system node to be centred over everything.
        # For now, place it at (PAGE_MARGIN, PAGE_MARGIN) and adjust later.

        # First pass: calculate total layout width so we can centre the system.
        n_cols = len(capabilities) + (1 if uncategorised else 0)
        total_w = n_cols * col_width + max(0, n_cols - 1) * CAP_GAP

        sys_x = PAGE_MARGIN + (total_w - SYSTEM_W) // 2
        sys_y = PAGE_MARGIN

        # Style for the system node — dark header colour to make it stand out.
        system_style = (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=10;"
            "fillColor=#1e3a5f;strokeColor=#1e3a5f;"
            "fontColor=#ffffff;fontSize=13;fontStyle=1;"
        )
        system_id = add_node(system_name, sys_x, sys_y, SYSTEM_W, SYSTEM_H, system_style)

        # ── Capability style ──────────────────────────────────────────────────
        cap_style = (
            "rounded=1;whiteSpace=wrap;html=1;arcSize=15;"
            "fillColor=#0050ef;strokeColor=#0050ef;"
            "fontColor=#ffffff;fontSize=11;fontStyle=1;"
        )

        # ── Place capability columns and their components ──────────────────────
        cap_y = sys_y + SYSTEM_H + ROW_GAP_1   # Y position of the capability row

        col_x = PAGE_MARGIN   # X position of the current column's left edge

        for cap in capabilities:
            # Centre the capability box within its column.
            cap_node_x = col_x + (col_width - CAP_W) // 2
            cap_id = add_node(
                cap.get("name", "Capability"),
                cap_node_x, cap_y, CAP_W, CAP_H,
                cap_style
            )
            # Arrow from system → capability
            add_edge(system_id, cap_id)

            # Place each member component beneath the capability.
            comp_y = cap_y + CAP_H + ROW_GAP_2
            for member_uuid in cap.get("member_uuids", []):
                # Look up this component's title and type so the box has
                # useful text and the right colour.
                comp_data  = all_components.get(member_uuid, {})
                comp_title = comp_data.get("title", member_uuid[:8] + "…")
                comp_type  = comp_data.get("type", "")
                # Also check the capability's own member_descriptions for a
                # description of the component's role in this capability.
                role_desc  = cap.get("member_descriptions", {}).get(member_uuid, "")

                # The label shows the component title; the role description is
                # shown on a second line in smaller text if available.
                if role_desc:
                    label = f"{comp_title}\n{role_desc[:50]}"
                else:
                    label = comp_title

                comp_node_x = col_x + (col_width - COMP_W) // 2
                comp_id = add_node(
                    label, comp_node_x, comp_y, COMP_W, COMP_H,
                    comp_style(comp_type)
                )
                add_edge(cap_id, comp_id)
                comp_y += COMP_H + COMP_GAP

            col_x += col_width + CAP_GAP

        # ── Uncategorised SSP components (not in any capability) ──────────────
        if uncategorised:
            # Add a grey "Uncategorised" placeholder capability-level box so the
            # column has the same visual structure as the capability columns.
            uncat_style = (
                "rounded=1;whiteSpace=wrap;html=1;arcSize=15;"
                "fillColor=#666666;strokeColor=#444444;"
                "fontColor=#ffffff;fontSize=11;fontStyle=1;"
            )
            uncat_x = col_x + (col_width - CAP_W) // 2
            uncat_id = add_node(
                "Uncategorised Components",
                uncat_x, cap_y, CAP_W, CAP_H,
                uncat_style
            )
            add_edge(system_id, uncat_id)

            comp_y = cap_y + CAP_H + ROW_GAP_2
            for comp in uncategorised:
                comp_title = comp.get("title", "(untitled)")
                comp_type  = comp.get("type", "")
                comp_node_x = col_x + (col_width - COMP_W) // 2
                comp_id = add_node(
                    comp_title, comp_node_x, comp_y, COMP_W, COMP_H,
                    comp_style(comp_type)
                )
                add_edge(uncat_id, comp_id)
                comp_y += COMP_H + COMP_GAP

        # ── Serialise to XML ──────────────────────────────────────────────────
        # ET.indent makes the XML human-readable with consistent indentation.
        # It's available in Python 3.9+; we wrap it in a try/except for older
        # Python versions where it doesn't exist.
        try:
            ET.indent(root_el, space="  ")
        except AttributeError:
            pass  # Python < 3.9 — the file is still valid, just less readable.

        xml_string = ET.tostring(root_el, encoding="unicode", xml_declaration=False)

        # ── Ask user where to save ────────────────────────────────────────────
        save_path = filedialog.asksaveasfilename(
            title="Export draw.io Diagram",
            defaultextension=".drawio",
            filetypes=[("draw.io diagram", "*.drawio"), ("XML file", "*.xml"), ("All files", "*.*")],
            initialfile=f"{system_name.replace(' ', '_')}_system_diagram.drawio",
        )
        if not save_path:
            # User cancelled the dialog — do nothing.
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(xml_string)
            self._set_status(f"draw.io diagram exported → {save_path}")
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
        doc = build_oscal_ssp(self._ssp, profile, catalog,
                              oscal_version=self._get_oscal_version())

        # Write the JSON to disk.
        # indent=2 produces nicely formatted JSON (human-readable).
        # ensure_ascii=False allows non-ASCII characters (e.g. accented letters).
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        # Update the status labels
        self._dirty = False
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
