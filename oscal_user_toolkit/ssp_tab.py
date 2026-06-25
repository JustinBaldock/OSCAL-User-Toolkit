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
    empty_ssp,        # Creates a blank SSP dictionary
    build_oscal_ssp,  # Converts our dict to OSCAL JSON format
    parse_ssp_file,   # Reads a saved SSP back into our dict format
    validate_ssp,     # Checks required fields before saving
    new_uuid,         # Generates a unique ID string
)


class SSPTab(tk.Frame):
    """
    A self-contained SSP editor panel.

    The panel contains a scrollable form divided into seven sections:
        1. SSP Metadata
        2. System Characteristics
        3. Authorization Boundary
        4. Network Architecture & Data Flow (optional)
        5. Information Types (table)
        6. Roles (table)
        7. Parties / People & Organisations (table)
    """

    def __init__(self, parent, colors, get_profile, get_catalog, set_status):
        """
        Set up the SSPTab panel.

        Parameters:
            parent      - The parent widget (the ttk.Notebook)
            colors      - Shared colour dictionary from app.py
            get_profile - Callback: returns the loaded profile dict or None
            get_catalog - Callback: returns the loaded catalog dict or None
            set_status  - Callback: set_status("message") updates the status bar
        """
        super().__init__(parent, bg=colors["BG"])

        # Store the injected dependencies
        self._colors      = colors
        self._get_profile = get_profile
        self._get_catalog = get_catalog
        self._set_status  = set_status

        # The SSP data is stored as a plain Python dictionary.
        # All form widgets read from and write to this dictionary.
        self._ssp = empty_ssp()

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
        Scroll the form canvas when the user rolls the mouse wheel,
        but only when the SSP tab (tab index 1) is currently selected.
        """
        try:
            # self.master is the Notebook widget
            nb = self.master
            if hasattr(nb, "index") and nb.index("current") == 2:
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

        # Bottom padding so the last section is not flush against the edge
        tk.Frame(parent, bg=C["BG"], height=40).pack()

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

    # =========================================================================
    # SAVE / OPEN / NEW ACTIONS
    # =========================================================================

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
