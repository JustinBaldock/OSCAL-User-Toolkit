"""
capability_tab.py
=================
This file defines the CapabilityTab class — a top-level tab in the
OSCAL User Toolkit placed between the Component Editor and the SSP Editor.

WHAT IS AN OSCAL CAPABILITY?
------------------------------
A capability is a named security function (e.g. "Account Management",
"Audit and Logging") that is delivered by combining two or more components.

Per the OSCAL Component Definition schema (oscal_component_metaschema.xml):

  - A capability lives at the same level as 'components' inside a
    'component-definition' file — it is NOT nested inside a component.
  - It references member components by their UUID via 'incorporates-components'.
  - Each referenced component-uuid must be unique within the same capability
    (enforced by schema constraint).
  - A capability can have its own 'control-implementations' array, separate
    from those of its member components, describing how the COMBINED set of
    components satisfies a control — something no single component can claim alone.

OSCAL JSON STRUCTURE:
  component-definition
    metadata
    components[]             ← member components (bundled in the same file)
      uuid, type, title, description, purpose
      props[], responsible-roles[], control-implementations[]
    capabilities[]           ← the capability itself
      uuid, name, description
      incorporates-components[]   (component-uuid + role description)
      control-implementations[]   (capability-level control responses)

SAVE BEHAVIOUR
--------------
When saving a capability the file contains:
  1. The capability definition (name, description, incorporates-components,
     control-implementations)
  2. ALL of the capability's member components

This is required by the OSCAL schema — the incorporates-components entries
reference component UUIDs that must resolve within the same
component-definition document.

GUARD CONDITION
---------------
The Capability Editor checks two things before allowing editing:
  1. An OSCAL catalog must be loaded (provides the control list for
     capability-level control implementations).
  2. At least one component must be loaded in the Component Editor
     (you cannot build a capability with no components to reference).

If either condition is not met, a clear gate panel is shown.
The tab calls on_state_changed() whenever it needs to re-evaluate.
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import new_uuid, now_iso, build_component_oscal_entry, refresh_ctrl_list

# ── Dot indicators for the control implementation list ────────────────────────
DOT_DONE  = "●"   # Filled circle  (green) — response has been written
DOT_EMPTY = "○"   # Empty circle   (grey)  — no response yet


class CapabilityTab(tk.Frame):
    """
    A self-contained OSCAL Capability editor tab.

    Layout:
      TOP    — Toolbar (Save, Clear buttons + filename display)
      MIDDLE — Gate panel (shown when guard conditions not met)
               OR horizontal split pane:
                 LEFT   — Capability list + Add/Delete buttons
                 RIGHT  — Scrollable capability editing form (3 sections)

    Callbacks injected at construction time:
        get_catalog()     Returns the loaded catalog dict, or None.
        get_components()  Returns the list of component dicts currently
                          loaded in the Component Editor, or [].
        get_profile()     Returns the loaded profile dict, or None.
        set_status(msg)   Updates the main window status bar.
    """

    def __init__(self, parent, colors,
                 get_catalog, get_components, get_profile, set_status):
        """
        Initialise the CapabilityTab.

        Parameters:
            parent         - The ttk.Notebook this tab lives inside
            colors         - Shared colour dictionary from app.py
            get_catalog    - Callback: returns catalog dict or None
            get_components - Callback: returns list of component dicts
            get_profile    - Callback: returns profile dict or None
            set_status     - Callback: updates the main window status bar
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors         = colors
        self._get_catalog    = get_catalog
        self._get_components = get_components
        self._get_profile    = get_profile
        self._set_status     = set_status

        # ── File-level state ──────────────────────────────────────────────────
        # Each saved capability gets its own component-definition file.
        # We generate a fresh file UUID when clearing, and preserve it on load.
        self._file_version = tk.StringVar(value="1.0")

        # ── Capability list state ─────────────────────────────────────────────
        # Each capability dict in memory:
        # {
        #   uuid:                str,
        #   name:                str,
        #   description:         str,
        #   remarks:             str,
        #   member_uuids:        [str, ...],    # component UUIDs
        #   member_descriptions: {uuid: str},   # role of each member
        #   ctrl_responses:      {ctrl_id: str} # capability-level responses
        # }
        self._capabilities       = []
        self._sel_index          = None   # index into self._capabilities
        self._dirty              = False

        # ── Control implementation state ──────────────────────────────────────
        self._ctrl_responses  = {}    # {control_id: description} for selected cap
        self._sel_ctrl_id     = None  # which control is currently shown in editor

        self._build()

    # =========================================================================
    # PUBLIC API — called by app.py
    # =========================================================================

    def on_state_changed(self):
        """
        Called by the main app whenever:
          - A catalog is loaded or cleared
          - A profile is loaded or cleared
          - The Component Editor's component list changes

        Re-evaluates the guard conditions and shows the editor or gate panel
        accordingly. Also refreshes the control list if a capability is open.
        """
        if not hasattr(self, "_gate_frame"):
            return
        if self._ready():
            self._gate_frame.pack_forget()
            self._body_pane.pack(fill="both", expand=True)
            self._update_gate_label()
            # If a capability is open, refresh its control list
            # (the catalog or component list may have changed)
            if self._sel_index is not None:
                self._refresh_ctrl_list()
        else:
            self._body_pane.pack_forget()
            self._gate_frame.pack(fill="both", expand=True)
            self._update_gate_label()

    # =========================================================================
    # GUARD CHECK
    # =========================================================================

    def _ready(self):
        """
        Return True only when both guard conditions are met:
          1. An OSCAL catalog is loaded
          2. At least one component exists in the Component Editor

        The profile is NOT required — capabilities reference controls from
        the full catalog, not just a profile subset. However, if a profile
        is loaded the control list will be filtered to that profile.
        """
        catalog    = self._get_catalog()
        components = self._get_components()
        return catalog is not None and len(components) > 0

    # =========================================================================
    # BUILD — top-level layout
    # =========================================================================

    def _build(self):
        """Create the toolbar, gate panel, and editing body."""
        self._build_toolbar()
        self._build_gate_panel()
        self._build_body()
        # Show the correct panel right away
        self.on_state_changed()

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _build_toolbar(self):
        """
        Top bar with Save and Clear buttons plus a version field and status.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)   # Keep the bar at a fixed 52-pixel height

        # Save the selected capability (bundles member components in same file)
        tk.Button(
            tb, text="💾  Save Capability", command=self._save_capability,
            bg=C["GREEN"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground="#8cd39a", activeforeground=C["BG"],
        ).pack(side="left", padx=12, pady=8)

        # Clear all capabilities and start fresh
        tk.Button(
            tb, text="🗑  Clear All", command=self._clear_all,
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(0, 12), pady=8)

        # Visual separator between action buttons and metadata fields
        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=4, pady=6
        )

        # Version number for the output file
        tk.Label(tb, text="Version:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left", padx=(8, 4))
        tk.Entry(
            tb, textvariable=self._file_version, width=8,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", ipady=3, pady=10)

        # Inline note about the save behaviour
        tk.Label(
            tb,
            text="  Saving a capability bundles its member components in the same file.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=8)

        # Status label (right side) — updated after save/load operations
        self._status_lbl = tk.Label(
            tb, text="Add a capability to begin",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=12)

    # =========================================================================
    # GATE PANEL — shown when guard conditions are not met
    # =========================================================================

    def _build_gate_panel(self):
        """
        Build the gate panel that blocks editing until the guard conditions
        are satisfied. Shows exactly what is still missing.
        """
        C = self._colors

        # This frame fills the whole body area when shown
        self._gate_frame = tk.Frame(self, bg=C["BG"])

        # Centre the content vertically and horizontally
        inner = tk.Frame(self._gate_frame, bg=C["BG"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text="🔗", bg=C["BG"], fg=C["TEAL"],
                 font=("Helvetica", 48)).pack(pady=(0, 10))

        tk.Label(inner, text="Capability Editor — Requirements",
                 bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 16, "bold")).pack()

        tk.Label(
            inner,
            text="Before creating capabilities you need:\n\n"
                 "1.  An OSCAL catalog loaded (provides the control list)\n"
                 "2.  At least one component in the Component Editor\n"
                 "    (a capability must reference existing components)\n\n"
                 "A profile is optional but recommended — if loaded,\n"
                 "the control list will be filtered to your baseline.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), justify="center",
        ).pack(pady=(8, 20))

        # Dynamic label updated by _update_gate_label()
        self._gate_status_lbl = tk.Label(
            inner, text="",
            bg=C["BG"], fg=C["RED"],
            font=("Helvetica", 11, "bold"), justify="center",
        )
        self._gate_status_lbl.pack()

        tk.Label(
            inner,
            text="Use 📂 Open Catalog and ⚙ Component Editor\n"
                 "in the tabs above to satisfy these requirements.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"), justify="center",
        ).pack(pady=(16, 0))

        self._update_gate_label()

    def _update_gate_label(self):
        """
        Refresh the gate panel status label to show exactly what is missing.
        Called by on_state_changed() whenever conditions may have changed.
        """
        catalog    = self._get_catalog()
        components = self._get_components()

        lines = []
        lines.append("✅  Catalog loaded"    if catalog    else "❌  No catalog loaded")
        if len(components) > 0:
            n = len(components)
            lines.append(f"✅  {n} component{'s' if n != 1 else ''} loaded")
        else:
            lines.append("❌  No components loaded  (open files in the Component Editor)")

        if hasattr(self, "_gate_status_lbl"):
            self._gate_status_lbl.config(text="\n".join(lines))

    # =========================================================================
    # BODY — horizontal split pane
    # =========================================================================

    def _build_body(self):
        """
        Build the editing area: a horizontal PanedWindow with:
          LEFT  — capability list + Add/Delete buttons
          RIGHT — scrollable capability editing form
        """
        C = self._colors
        self._body_pane = tk.PanedWindow(
            self, orient="horizontal",
            bg=C["BG"], sashwidth=5, sashrelief="flat",
        )
        # Not packed yet — shown by on_state_changed()

        self._build_capability_list(self._body_pane)
        self._build_detail_form(self._body_pane)

    # =========================================================================
    # LEFT PANE — capability list
    # =========================================================================

    def _build_capability_list(self, pane):
        """
        Build the left pane: a Listbox of capabilities with Add/Delete buttons.
        """
        C    = self._colors
        left = tk.Frame(pane, bg=C["SIDEBAR_BG"])
        pane.add(left, minsize=240, width=280)

        # Heading bar
        hdr = tk.Frame(left, bg=C["HEADER_BG"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="🔗  Capabilities",
                 bg=C["HEADER_BG"], fg=C["TEAL"],
                 font=("Helvetica", 11, "bold"), anchor="w",
                 ).pack(side="left", padx=10, pady=8)

        # Add / Delete buttons
        btn_row = tk.Frame(left, bg=C["SIDEBAR_BG"])
        btn_row.pack(fill="x", padx=8, pady=6)

        tk.Button(
            btn_row, text="＋  Add Capability",
            command=self._add_capability,
            bg=C["TEAL"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2",
            activebackground="#7ad5c6", activeforeground=C["BG"],
        ).pack(side="left")

        tk.Button(
            btn_row, text="✕  Delete",
            command=self._delete_capability,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="right")

        # Listbox + scrollbar
        lf = tk.Frame(left, bg=C["SIDEBAR_BG"])
        lf.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        self._cap_listbox = tk.Listbox(
            lf,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"],
            selectbackground=C["TEAL"], selectforeground=C["BG"],
            font=("Helvetica", 11), relief="flat",
            activestyle="none", highlightthickness=0,
        )
        vsb = ttk.Scrollbar(lf, orient="vertical",
                            command=self._cap_listbox.yview)
        self._cap_listbox.configure(yscrollcommand=vsb.set)
        self._cap_listbox.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._cap_listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # Small reminder about save behaviour
        tk.Label(
            left,
            text="  Saving bundles member\n  components in the same file.",
            bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 8, "italic"), justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 6))

    # =========================================================================
    # RIGHT PANE — scrollable editing form
    # =========================================================================

    def _build_detail_form(self, pane):
        """
        Build the right pane: a scrollable canvas containing the
        capability editing form.
        """
        C     = self._colors
        right = tk.Frame(pane, bg=C["BG"])
        pane.add(right, minsize=500)

        # Canvas + scrollbar for vertical scrolling
        canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        # Inner frame placed inside the canvas
        self._form_frame = tk.Frame(canvas, bg=C["BG"])
        self._form_win   = canvas.create_window(
            (0, 0), window=self._form_frame, anchor="nw"
        )
        # Keep the scroll region in sync with the form height
        self._form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Keep the form width in sync with the canvas width
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._form_win, width=e.width)
        )
        self._canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_form_widgets(self._form_frame)
        self._show_placeholder()

    def _on_mousewheel(self, event):
        """
        Scroll the canvas on mouse-wheel, but only when the Capability
        Editor tab (index 3) is the active tab in the main notebook.
        """
        try:
            nb = self.master   # The main ttk.Notebook
            if hasattr(nb, "index") and nb.index("current") == 3:
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # =========================================================================
    # FORM WIDGETS
    # =========================================================================

    def _build_form_widgets(self, parent):
        """
        Build the three-section capability editing form:
          Section 1 — Basic Information  (name, description, remarks)
          Section 2 — Member Components  (which components form this capability)
          Section 3 — Control Implementations (capability-level responses)
        """
        C = self._colors
        P = dict(padx=20)   # Standard horizontal padding

        # ── Local helpers for common widget patterns ──────────────────────────

        def section(title):
            """Dark coloured section heading bar."""
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(16, 4))
            tk.Label(hdr, text=title, bg=C["HEADER_BG"], fg=C["TEAL"],
                     font=("Helvetica", 11, "bold"), anchor="w",
                     ).pack(side="left", padx=10, pady=5)

        def field(label, var, width=50):
            """Label + Entry row linked to a StringVar."""
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=20, anchor="w",
                     ).pack(side="left")
            tk.Entry(
                row, textvariable=var, width=width,
                bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                relief="flat", font=("Helvetica", 11),
                highlightthickness=1, highlightbackground=C["HEADER_BG"],
            ).pack(side="left", ipady=3, fill="x", expand=True)

        def textbox(label, height=4):
            """Label + multi-line Text widget. Returns the Text widget."""
            if label:
                tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                         font=("Helvetica", 11),
                         ).pack(anchor="w", **P, pady=(6, 2))
            border = tk.Frame(parent, bg=C["HEADER_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
            border.pack(fill="x", **P, pady=2)
            t = tk.Text(
                border, bg=C["CARD_BG"], fg=C["TEXT"],
                insertbackground=C["TEXT"], relief="flat",
                font=("Helvetica", 11), height=height,
                wrap="word", padx=8, pady=6,
            )
            t.pack(fill="both")
            return t

        # ── Placeholder shown when nothing is selected ────────────────────────
        self._placeholder_lbl = tk.Label(
            parent,
            text="Add a capability using '＋ Add Capability'.\n\n"
                 "A capability combines existing components to describe\n"
                 "a named security function, for example:\n"
                 "  • Account Management\n"
                 "  • Audit and Logging\n"
                 "  • Boundary Protection",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 12, "italic"), justify="center",
        )
        self._placeholder_lbl.pack(pady=60, padx=40)

        # All real form content lives here — shown/hidden as a unit
        self._form_content = tk.Frame(parent, bg=C["BG"])

        # From here on, widgets go inside _form_content
        parent = self._form_content

        # =====================================================================
        # SECTION 1 — BASIC INFORMATION
        # =====================================================================
        section("1 ·  Basic Information")
        tk.Label(
            parent,
            text="  Name and describe this security capability.\n"
                 "  The name becomes part of the saved filename.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        # StringVars — linked to Entry widgets, auto-update on typing
        self._v_name    = tk.StringVar()
        self._v_remarks = tk.StringVar()

        field("Capability Name *", self._v_name, width=50)

        # Live-rename the listbox entry as the user types
        self._v_name.trace_add("write", self._on_name_change)

        tk.Label(parent, text="Description *",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(anchor="w", padx=20, pady=(6, 2))
        self._v_desc = textbox("", height=4)

        field("Remarks", self._v_remarks, width=50)

        tk.Label(parent, text="  * Required fields",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        # =====================================================================
        # SECTION 2 — MEMBER COMPONENTS
        # =====================================================================
        section("2 ·  Member Components")
        tk.Label(
            parent,
            text="  Select the components that together deliver this capability.\n"
                 "  Components must already be open in the Component Editor.\n"
                 "  The schema requires each component UUID to appear at most once\n"
                 "  within a single capability.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        mem_frame = tk.Frame(parent, bg=C["CARD_BG"],
                             highlightthickness=1, highlightbackground=C["HEADER_BG"])
        mem_frame.pack(fill="x", padx=20, pady=6)

        # Add / Remove buttons for the member table
        mem_btn = tk.Frame(mem_frame, bg=C["CARD_BG"])
        mem_btn.pack(fill="x", padx=8, pady=6)

        tk.Button(
            mem_btn, text="＋  Add Member Component",
            command=self._add_member,
            bg=C["TEAL"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=8, pady=3, cursor="hand2",
            activebackground="#7ad5c6", activeforeground=C["BG"],
        ).pack(side="left")

        tk.Button(
            mem_btn, text="✕  Remove Selected",
            command=self._remove_member,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)

        # Table showing member components
        # Columns: component title, type, and its role in this capability
        self._mem_tree = ttk.Treeview(
            mem_frame,
            columns=("title", "type", "role"),
            show="headings", height=4, selectmode="browse",
        )
        self._mem_tree.heading("title", text="Component Title",    anchor="w")
        self._mem_tree.heading("type",  text="Type",               anchor="w")
        self._mem_tree.heading("role",  text="Role in Capability", anchor="w")
        self._mem_tree.column("title", width=180, anchor="w")
        self._mem_tree.column("type",  width=100, anchor="w")
        self._mem_tree.column("role",  width=280, anchor="w", stretch=True)
        self._mem_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =====================================================================
        # SECTION 3 — CONTROL IMPLEMENTATIONS (CAPABILITY-LEVEL)
        # =====================================================================
        section("3 ·  Control Implementations  (capability-level)")
        tk.Label(
            parent,
            text="  Describe how this CAPABILITY (the combination of components)\n"
                 "  implements each control.  Use this section when the combined\n"
                 "  capability provides something no single component can claim alone.\n"
                 "  Individual component responses are stored in the Component Editor.\n"
                 "  Dot legend:  ● = response written   ○ = no response yet",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        # Inner split: control list on the left, response editor on the right
        ctrl_outer = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        ctrl_outer.pack(fill="both", expand=True, padx=20, pady=6)

        ctrl_pane = tk.PanedWindow(
            ctrl_outer, orient="horizontal",
            bg=C["CARD_BG"], sashwidth=4, sashrelief="flat",
        )
        ctrl_pane.pack(fill="both", expand=True)

        # ── Left sub-pane: control list with search ───────────────────────────
        ctrl_left = tk.Frame(ctrl_pane, bg=C["SIDEBAR_BG"])
        ctrl_pane.add(ctrl_left, minsize=200, width=300)

        # Search box — filters the control list live as the user types
        search_row = tk.Frame(ctrl_left, bg=C["SIDEBAR_BG"])
        search_row.pack(fill="x", padx=6, pady=6)
        tk.Label(search_row, text="🔍", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="left")
        self._ctrl_search_var = tk.StringVar()
        self._ctrl_search_var.trace_add("write", self._on_ctrl_search)
        tk.Entry(
            search_row, textvariable=self._ctrl_search_var,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", fill="x", expand=True, ipady=3, padx=(4, 0))

        # The control list uses a two-tab inner notebook so the user can
        # quickly find controls they have already responded to without
        # scrolling through the full list.
        s = ttk.Style()
        s.configure("Cap.TNotebook", background=C["SIDEBAR_BG"], borderwidth=0)
        s.configure("Cap.TNotebook.Tab",
                    background=C["HEADER_BG"], foreground=C["SUBTEXT"],
                    padding=[10, 4], font=("Helvetica", 9))
        s.map("Cap.TNotebook.Tab",
              background=[("selected", C["CARD_BG"])],
              foreground=[("selected", C["TEAL"])])

        self._ctrl_nb = ttk.Notebook(ctrl_left, style="Cap.TNotebook")
        self._ctrl_nb.pack(fill="both", expand=True, padx=4, pady=(0, 2))
        self._ctrl_nb.bind("<<NotebookTabChanged>>", self._on_ctrl_tab_changed)

        def make_ctrl_tree(tab_parent):
            """
            Create a Treeview for displaying controls inside a tab.
            Columns: dot indicator, label, statement.
            Returns the Treeview widget.
            """
            frame = tk.Frame(tab_parent, bg=C["SIDEBAR_BG"])
            frame.pack(fill="both", expand=True)
            tree = ttk.Treeview(
                frame,
                columns=("dot", "label", "title"),
                show="headings", selectmode="browse",
            )
            tree.heading("dot",   text="",           anchor="center")
            tree.heading("label", text="ID / Label", anchor="w")
            tree.heading("title", text="Statement",  anchor="w")
            tree.column("dot",   width=24,  minwidth=24,  anchor="center", stretch=False)
            tree.column("label", width=100, minwidth=80,  anchor="w",      stretch=False)
            tree.column("title", width=200, minwidth=100, anchor="w",      stretch=True)
            tree.tag_configure("done",  foreground=C["GREEN"])
            tree.tag_configure("empty", foreground=C["SUBTEXT"])
            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")
            tree.bind("<<TreeviewSelect>>", self._on_ctrl_select)
            return tree

        # Tab 1 — all controls from the catalog (filtered by profile if loaded)
        all_tab = tk.Frame(self._ctrl_nb, bg=C["SIDEBAR_BG"])
        self._ctrl_nb.add(all_tab, text="All Controls")
        self._ctrl_tree = make_ctrl_tree(all_tab)

        # Tab 2 — only controls that already have a capability-level response
        applied_tab = tk.Frame(self._ctrl_nb, bg=C["SIDEBAR_BG"])
        self._ctrl_nb.add(applied_tab, text="Applied Controls")
        self._applied_ctrl_tree = make_ctrl_tree(applied_tab)

        # Progress counter below the tabs
        self._progress_lbl = tk.Label(
            ctrl_left, text="",
            bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"], font=("Helvetica", 9),
        )
        self._progress_lbl.pack(pady=(2, 6))

        # ── Right sub-pane: response text editor ──────────────────────────────
        ctrl_right = tk.Frame(ctrl_pane, bg=C["BG"])
        ctrl_pane.add(ctrl_right, minsize=300)

        # Shows the selected control's statement as a read-only reference
        self._stmt_lbl = tk.Label(
            ctrl_right,
            text="Select a control from the list to write a capability-level response.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
            wraplength=380, justify="left", anchor="nw",
        )
        self._stmt_lbl.pack(fill="x", padx=8, pady=(8, 4))

        tk.Frame(ctrl_right, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=8, pady=4
        )
        tk.Label(
            ctrl_right,
            text="How does this CAPABILITY implement this control?",
            bg=C["BG"], fg=C["TEAL"],
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(4, 2))

        # Multi-line text area for the response
        resp_border = tk.Frame(ctrl_right, bg=C["HEADER_BG"],
                               highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        resp_border.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._response_text = tk.Text(
            resp_border,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            wrap="word", padx=8, pady=6,
        )
        self._response_text.pack(fill="both", expand=True)

        # Save Response button
        save_row = tk.Frame(ctrl_right, bg=C["BG"])
        save_row.pack(fill="x", padx=8, pady=(4, 8))
        tk.Button(
            save_row, text="✔  Save Response",
            command=self._save_ctrl_response,
            bg=C["GREEN"], fg=C["BG"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
            activebackground="#8cd39a", activeforeground=C["BG"],
        ).pack(side="left")
        tk.Label(
            save_row,
            text="  Saves to memory — use '💾 Save Capability' to write to disk.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 8, "italic"),
        ).pack(side="left", padx=8)

        # ── Apply + bottom padding ────────────────────────────────────────────
        apply_row = tk.Frame(parent, bg=C["BG"])
        apply_row.pack(fill="x", padx=20, pady=(16, 8))
        tk.Button(
            apply_row, text="✔  Apply Capability Changes",
            command=self._apply_capability,
            bg=C["TEAL"], fg=C["BG"], font=("Helvetica", 11, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#7ad5c6", activeforeground=C["BG"],
        ).pack(side="left")
        tk.Label(
            apply_row,
            text="  (Saves to memory — use '💾 Save Capability' to write to disk)",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=8)

        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # PLACEHOLDER / FORM VISIBILITY
    # =========================================================================

    def _show_placeholder(self):
        """Hide the form and show the 'add a capability' placeholder."""
        self._form_content.pack_forget()
        self._placeholder_lbl.pack(pady=60, padx=40)

    def _show_form(self):
        """Hide the placeholder and show the editing form."""
        self._placeholder_lbl.pack_forget()
        self._form_content.pack(fill="both", expand=True)

    # =========================================================================
    # CAPABILITY LIST MANAGEMENT
    # =========================================================================

    def _refresh_list(self):
        """Rebuild the Listbox from self._capabilities."""
        self._cap_listbox.delete(0, "end")
        for cap in self._capabilities:
            name  = cap.get("name", "").strip() or "(unnamed)"
            n     = len(cap.get("member_uuids", []))
            label = f"{name}  [{n} component{'s' if n != 1 else ''}]"
            self._cap_listbox.insert("end", label)

    def _on_list_select(self, _event=None):
        """
        Called when the user clicks a capability in the left list.
        Saves pending changes to the previously selected capability, then
        loads the newly selected one into the form.
        """
        sel = self._cap_listbox.curselection()
        if not sel:
            return
        new_idx = int(sel[0])

        # Save pending changes before switching
        if self._sel_index is not None:
            self._collect_into(self._sel_index)

        self._sel_index = new_idx
        self._populate_from(new_idx)
        self._show_form()

    def _add_capability(self):
        """Create a new blank capability, add it to the list, and select it."""
        new_cap = {
            "uuid":                new_uuid(),
            "name":                "",
            "description":         "",
            "remarks":             "",
            "member_uuids":        [],
            "member_descriptions": {},
            "ctrl_responses":      {},
        }
        self._capabilities.append(new_cap)
        self._dirty = True
        self._refresh_list()

        new_idx = len(self._capabilities) - 1
        self._cap_listbox.selection_clear(0, "end")
        self._cap_listbox.selection_set(new_idx)
        self._cap_listbox.see(new_idx)

        if self._sel_index is not None:
            self._collect_into(self._sel_index)

        self._sel_index = new_idx
        self._populate_from(new_idx)
        self._show_form()
        self._status_lbl.config(
            text="New capability added", fg=self._colors["TEAL"]
        )

    def _delete_capability(self):
        """Delete the selected capability after asking for confirmation."""
        if self._sel_index is None:
            messagebox.showinfo("No selection", "Select a capability to delete.")
            return

        name = self._capabilities[self._sel_index].get("name", "(unnamed)")
        if not messagebox.askyesno(
            "Delete capability?",
            f"Delete '{name}'? This cannot be undone.\n\n"
            "The member components will NOT be deleted — only this\n"
            "capability grouping will be removed."
        ):
            return

        self._capabilities.pop(self._sel_index)
        self._sel_index      = None
        self._ctrl_responses = {}
        self._dirty          = True
        self._refresh_list()
        self._show_placeholder()

    def _on_name_change(self, *_args):
        """
        Called by the StringVar trace whenever the Capability Name field changes.
        Renames the matching Listbox entry live as the user types.
        """
        if self._sel_index is None:
            return
        name  = self._v_name.get().strip() or "(unnamed)"
        n     = len(self._capabilities[self._sel_index].get("member_uuids", []))
        label = f"{name}  [{n} component{'s' if n != 1 else ''}]"
        self._cap_listbox.delete(self._sel_index)
        self._cap_listbox.insert(self._sel_index, label)
        self._cap_listbox.selection_set(self._sel_index)

    # =========================================================================
    # FORM POPULATE AND COLLECT
    # =========================================================================

    def _populate_from(self, index):
        """
        Load self._capabilities[index] into all form widgets.
        Called when a capability is selected from the list.
        """
        cap = self._capabilities[index]

        # Simple text fields
        self._v_name.set(cap.get("name", ""))
        self._v_remarks.set(cap.get("remarks", ""))

        # Multi-line description
        self._v_desc.delete("1.0", "end")
        desc = cap.get("description", "")
        if desc:
            self._v_desc.insert("1.0", desc)

        # Member components table
        self._mem_tree.delete(*self._mem_tree.get_children())
        mem_descs = cap.get("member_descriptions", {})
        for comp_uuid in cap.get("member_uuids", []):
            # Look up the component in the Component Editor's list
            comp = self._find_component(comp_uuid)
            if comp:
                self._mem_tree.insert("", "end", iid=comp_uuid, values=(
                    comp.get("title", ""),
                    comp.get("type", ""),
                    mem_descs.get(comp_uuid, ""),
                ))

        # Control responses
        self._ctrl_responses = dict(cap.get("ctrl_responses", {}))
        self._sel_ctrl_id    = None
        self._response_text.delete("1.0", "end")
        self._stmt_lbl.config(
            text="Select a control from the list to write a capability-level response.",
            fg=self._colors["SUBTEXT"],
        )
        self._ctrl_search_var.set("")
        self._refresh_ctrl_list()

    def _collect_into(self, index):
        """
        Read all form widget values and store them into self._capabilities[index].
        Called before switching capabilities and before saving.
        """
        cap = self._capabilities[index]

        cap["name"]        = self._v_name.get().strip()
        cap["description"] = self._v_desc.get("1.0", "end-1c").strip()
        cap["remarks"]     = self._v_remarks.get().strip()

        # Save any pending control response before collecting
        if self._sel_ctrl_id:
            text = self._response_text.get("1.0", "end-1c").strip()
            if text:
                self._ctrl_responses[self._sel_ctrl_id] = text
            else:
                self._ctrl_responses.pop(self._sel_ctrl_id, None)

        cap["ctrl_responses"] = dict(self._ctrl_responses)

        # Preserve member_descriptions from the table rows
        if "member_descriptions" not in cap:
            cap["member_descriptions"] = {}
        for iid in self._mem_tree.get_children():
            values = self._mem_tree.item(iid)["values"]
            if len(values) >= 3:
                cap["member_descriptions"][iid] = values[2]

        self._dirty = True

    def _apply_capability(self):
        """
        Save form state to the selected capability dict and refresh the list.
        Does NOT write to disk.
        """
        if self._sel_index is None:
            return
        self._collect_into(self._sel_index)
        self._refresh_list()
        self._cap_listbox.selection_set(self._sel_index)
        self._refresh_ctrl_list()
        self._status_lbl.config(
            text="Capability changes applied  (not yet saved to disk)",
            fg=self._colors["YELLOW"],
        )

    # =========================================================================
    # MEMBER COMPONENT MANAGEMENT
    # =========================================================================

    def _find_component(self, comp_uuid):
        """
        Look up a component by UUID in the Component Editor's list.
        Returns the component dict, or None if not found.
        """
        return next(
            (c for c in self._get_components() if c["uuid"] == comp_uuid),
            None
        )

    def _add_member(self):
        """
        Show a dialog to pick a component (from the Component Editor)
        and add it as a member of the current capability.
        """
        if self._sel_index is None:
            messagebox.showinfo("No capability", "Select a capability first.")
            return

        components = self._get_components()
        if not components:
            messagebox.showinfo(
                "No components",
                "Open component files in the Component Editor first."
            )
            return

        cap            = self._capabilities[self._sel_index]
        existing_uuids = set(cap.get("member_uuids", []))

        # Only offer components not already in this capability
        available = [c for c in components if c["uuid"] not in existing_uuids]
        if not available:
            messagebox.showinfo(
                "All components added",
                "Every open component is already a member of this capability."
            )
            return

        result = self._member_dialog(available)
        if not result:
            return

        comp_uuid = result["uuid"]
        role_desc = result["description"]

        cap["member_uuids"] = cap.get("member_uuids", []) + [comp_uuid]
        if "member_descriptions" not in cap:
            cap["member_descriptions"] = {}
        cap["member_descriptions"][comp_uuid] = role_desc

        # Add the row to the table
        comp = self._find_component(comp_uuid)
        if comp:
            self._mem_tree.insert("", "end", iid=comp_uuid, values=(
                comp.get("title", ""),
                comp.get("type", ""),
                role_desc,
            ))

        self._refresh_list()
        self._dirty = True

    def _remove_member(self):
        """Remove the selected row from the member components table."""
        sel = self._mem_tree.selection()
        if not sel:
            return
        comp_uuid = sel[0]   # The Treeview iid is the component UUID

        if self._sel_index is not None:
            cap = self._capabilities[self._sel_index]
            cap["member_uuids"] = [
                u for u in cap.get("member_uuids", []) if u != comp_uuid
            ]
            cap.get("member_descriptions", {}).pop(comp_uuid, None)

        self._mem_tree.delete(comp_uuid)
        self._refresh_list()
        self._dirty = True

    def _member_dialog(self, available):
        """
        Show a modal dialog to select a component and provide its role
        description within this capability.

        Parameters:
            available - List of component dicts not yet in this capability

        Returns:
            {"uuid": str, "description": str} or None if the user cancelled.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Add Member Component")
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.grab_set()   # Make modal

        tk.Label(
            dlg, text="Select a component to add to this capability:",
            bg=C["BG"], fg=C["TEXT"], font=("Helvetica", 11),
        ).pack(padx=20, pady=(16, 4), anchor="w")

        # Dropdown showing available component titles + types
        comp_labels = [
            f"{c.get('title', '?')}  [{c.get('type', '')}]"
            for c in available
        ]
        v_comp = tk.StringVar(value=comp_labels[0])
        ttk.Combobox(
            dlg, textvariable=v_comp, values=comp_labels,
            state="readonly", width=50,
        ).pack(padx=20, pady=4)

        tk.Label(
            dlg, text="Role / description of this component in the capability  (required):",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
        ).pack(padx=20, pady=(10, 2), anchor="w")

        tk.Label(
            dlg,
            text="  e.g. 'Provides the LDAP directory store for account lookups.'",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(padx=20, anchor="w")

        v_desc = tk.StringVar()
        tk.Entry(
            dlg, textvariable=v_desc, width=55,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(padx=20, pady=4, ipady=3)

        result = {}

        def _ok():
            if not v_desc.get().strip():
                messagebox.showwarning(
                    "Description required",
                    "Please describe this component's role in the capability."
                )
                return
            idx = comp_labels.index(v_comp.get())
            result["uuid"]        = available[idx]["uuid"]
            result["description"] = v_desc.get().strip()
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  Add  ", command=_ok,
                  bg=C["TEAL"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")

        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # CONTROL IMPLEMENTATION LIST (Section 3)
    # =========================================================================

    def _get_controls(self):
        """
        Return the list of controls to show in Section 3.

        If a profile is loaded, only controls in the profile are shown.
        Otherwise, all controls from the catalog are shown.
        This mirrors the approach used in the Component Editor.
        """
        catalog = self._get_catalog()
        if not catalog:
            return []
        profile = self._get_profile()
        if profile and profile.get("ids"):
            return [c for c in catalog["controls"] if c["id"] in profile["ids"]]
        return catalog["controls"]

    def _refresh_ctrl_list(self, search_term=""):
        """Rebuild both control list tabs from the current catalog/profile controls."""
        refresh_ctrl_list(
            ctrl_responses=self._ctrl_responses,
            all_controls=self._get_controls(),
            search_term=search_term,
            ctrl_tree=self._ctrl_tree,
            applied_tree=self._applied_ctrl_tree,
            notebook=self._ctrl_nb,
            progress_lbl=self._progress_lbl,
        )

    def _on_ctrl_tab_changed(self, _event=None):
        """Called when the user switches between All / Applied tabs."""
        # Clear the search so results are not confusingly pre-filtered
        self._ctrl_search_var.set("")
        self._refresh_ctrl_list()

    def _on_ctrl_search(self, *_args):
        """Called on every keystroke in the search box."""
        self._refresh_ctrl_list(self._ctrl_search_var.get())

    def _on_ctrl_select(self, _event=None):
        """
        Called when the user clicks a row in either control list tab.
        Saves any pending response for the previously selected control,
        then loads the response for the newly selected control.
        """
        # Determine which tree fired the event and clear the other's selection
        ctrl_id = None
        for tree in (self._ctrl_tree, self._applied_ctrl_tree):
            sel = tree.selection()
            if sel:
                ctrl_id = sel[0]   # Row iid is the control ID
                other   = (self._applied_ctrl_tree
                           if tree is self._ctrl_tree
                           else self._ctrl_tree)
                other.selection_remove(*other.selection())
                break

        if ctrl_id is None:
            return

        # Save the current response before switching controls
        if self._sel_ctrl_id and self._sel_ctrl_id != ctrl_id:
            text = self._response_text.get("1.0", "end-1c").strip()
            if text:
                self._ctrl_responses[self._sel_ctrl_id] = text
            else:
                self._ctrl_responses.pop(self._sel_ctrl_id, None)

        self._sel_ctrl_id = ctrl_id

        # Find the control dict so we can show its statement
        catalog   = self._get_catalog()
        ctrl_dict = None
        if catalog:
            ctrl_dict = next(
                (c for c in catalog["controls"] if c["id"] == ctrl_id), None
            )

        # Update the read-only statement label
        if ctrl_dict:
            label     = ctrl_dict.get("label", ctrl_id)
            statement = ctrl_dict.get("statement", ctrl_dict.get("title", ""))
            self._stmt_lbl.config(
                text=f"[{label}]  {statement}",
                fg=self._colors["TEXT"],
            )
        else:
            self._stmt_lbl.config(text=ctrl_id, fg=self._colors["SUBTEXT"])

        # Load existing response into the editor
        self._response_text.delete("1.0", "end")
        existing = self._ctrl_responses.get(ctrl_id, "")
        if existing:
            self._response_text.insert("1.0", existing)

        # Move focus to the editor so the user can start typing immediately
        self._response_text.focus_set()

    def _save_ctrl_response(self):
        """
        Save the text currently in the response editor for the selected control.
        Updates _ctrl_responses and refreshes the dot indicators.
        """
        if not self._sel_ctrl_id:
            messagebox.showinfo(
                "No control selected",
                "Select a control from the list first."
            )
            return

        text = self._response_text.get("1.0", "end-1c").strip()
        if text:
            self._ctrl_responses[self._sel_ctrl_id] = text
        else:
            # Empty text — remove the entry so the dot clears
            self._ctrl_responses.pop(self._sel_ctrl_id, None)

        # Rebuild both tabs so dots and counts update immediately
        self._refresh_ctrl_list(self._ctrl_search_var.get())

        # Restore selection in whichever tab is active
        active      = self._ctrl_nb.index("current")
        active_tree = self._ctrl_tree if active == 0 else self._applied_ctrl_tree
        try:
            active_tree.selection_set(self._sel_ctrl_id)
            active_tree.see(self._sel_ctrl_id)
        except Exception:
            pass

        self._dirty = True
        self._status_lbl.config(
            text="Response saved to memory — use '💾 Save Capability' to write to disk",
            fg=self._colors["YELLOW"],
        )

    # =========================================================================
    # OSCAL JSON — BUILD CAPABILITY FILE
    # =========================================================================

    def _build_oscal_document(self, cap):
        """
        Convert one capability dict into a valid OSCAL Component Definition
        JSON document.

        Per the schema, capability entries reference component UUIDs that
        MUST resolve within the same component-definition document. So this
        method bundles ALL member components alongside the capability.

        Parameters:
            cap - A capability dict from self._capabilities

        Returns:
            A tuple of (document_dict, safe_filename_stem).
        """
        now = now_iso()

        # Determine the source URI for control-implementations
        profile = self._get_profile()
        catalog = self._get_catalog()
        if profile and profile.get("filepath"):
            source_href = Path(profile["filepath"]).name
        elif catalog and catalog.get("filepath"):
            source_href = Path(catalog["filepath"]).name
        else:
            source_href = "PROFILE_OR_CATALOG_HREF"

        # ── Build member component entries ────────────────────────────────────
        # Only include components that are referenced by this capability
        member_uuids = set(cap.get("member_uuids", []))
        member_comps = [
            c for c in self._get_components() if c["uuid"] in member_uuids
        ]

        oscal_components = [
            build_component_oscal_entry(comp, source_href)
            for comp in member_comps
        ]

        # ── Build the capability entry ─────────────────────────────────────────
        mem_descs    = cap.get("member_descriptions", {})
        incorporates = [
            {
                "component-uuid": uid,
                "description":    mem_descs.get(
                    uid, "Member component of this capability."
                ),
            }
            for uid in cap.get("member_uuids", [])
        ]

        # Capability-level control implementations
        cap_implemented = [
            {
                "uuid":        new_uuid(),
                "control-id":  ctrl_id,
                "description": desc.strip(),
            }
            for ctrl_id, desc in cap.get("ctrl_responses", {}).items()
            if desc.strip()
        ]

        oscal_cap = {
            "uuid":        cap["uuid"],
            "name":        cap.get("name", ""),
            "description": cap.get("description", ""),
        }
        if incorporates:
            oscal_cap["incorporates-components"] = incorporates
        if cap_implemented:
            oscal_cap["control-implementations"] = [{
                "uuid":        new_uuid(),
                "source":      source_href,
                "description": (
                    f"Capability-level control implementations for "
                    f"{cap.get('name', 'this capability')}."
                ),
                "implemented-requirements": cap_implemented,
            }]
        if cap.get("remarks"):
            oscal_cap["remarks"] = cap["remarks"]

        # Build the filename stem: "capability_AccountManagement"
        cap_name = cap.get("name", "capability").replace(" ", "_")
        file_title = f"Capability: {cap.get('name', 'Unnamed Capability')}"

        doc = {
            "component-definition": {
                "uuid": new_uuid(),
                "metadata": {
                    "title":         file_title,
                    "last-modified": now,
                    "version":       self._file_version.get().strip() or "1.0",
                    "oscal-version": "1.1.2",
                },
                # Member components must be present for UUID resolution
                **({"components": oscal_components} if oscal_components else {}),
                # The capability itself
                "capabilities": [oscal_cap],
            }
        }
        return doc, cap_name

    # =========================================================================
    # FILE ACTIONS
    # =========================================================================

    def _validate_selected(self):
        """
        Validate the currently selected capability before saving.

        Returns a list of error strings. An empty list means ready to save.
        """
        errors = []

        if self._sel_index is None:
            errors.append("No capability is selected.")
            return errors

        cap = self._capabilities[self._sel_index]

        if not cap.get("name", "").strip():
            errors.append("Capability Name is required (Section 1).")
        if not cap.get("description", "").strip():
            errors.append("Capability Description is required (Section 1).")
        if not cap.get("member_uuids"):
            errors.append(
                "At least one member component is required (Section 2)."
            )

        # Check that all referenced component UUIDs exist in the current list
        available_uuids = {c["uuid"] for c in self._get_components()}
        missing = set(cap.get("member_uuids", [])) - available_uuids
        if missing:
            errors.append(
                f"{len(missing)} member component(s) are not currently open "
                "in the Component Editor. Open the missing files before saving."
            )

        return errors

    def _save_capability(self):
        """
        Validate and save the selected capability to an OSCAL Component
        Definition JSON file.

        The saved file contains:
          - The capability definition (name, description,
            incorporates-components, control-implementations)
          - All member components (required by the OSCAL schema so that
            the component UUIDs resolve within the same document)
        """
        # Collect current form state first
        if self._sel_index is not None:
            self._collect_into(self._sel_index)

        errors = self._validate_selected()
        if errors:
            messagebox.showerror(
                "Cannot save capability",
                "Please fix the following before saving:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        cap      = self._capabilities[self._sel_index]
        cap_name = cap.get("name", "capability").replace(" ", "_")

        path = filedialog.asksaveasfilename(
            title="Save OSCAL Capability Definition",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"capability_{cap_name}.json",
        )
        if not path:
            return   # User cancelled the save dialog

        doc, _ = self._build_oscal_document(cap)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        self._dirty = False
        n_comps     = len(cap.get("member_uuids", []))
        fname       = Path(path).name

        self._status_lbl.config(
            text=f"Saved: {fname}", fg=self._colors["GREEN"]
        )
        self._set_status(f"Capability saved: {fname}")
        messagebox.showinfo(
            "Capability Saved",
            f"Capability '{cap.get('name', '')}' saved with "
            f"{n_comps} member component{'s' if n_comps != 1 else ''}:\n{path}"
        )

    def _clear_all(self):
        """Clear all capabilities and start fresh, with confirmation."""
        if self._dirty and self._capabilities:
            if not messagebox.askyesno(
                "Clear all capabilities?",
                "This will remove all capabilities from the list.\n"
                "Unsaved changes will be lost. Continue?"
            ):
                return

        self._capabilities   = []
        self._sel_index      = None
        self._ctrl_responses = {}
        self._sel_ctrl_id    = None
        self._dirty          = False

        self._refresh_list()
        self._show_placeholder()
        self._status_lbl.config(
            text="Cleared — ready for new capabilities.",
            fg=self._colors["SUBTEXT"],
        )
        self._set_status("Capability list cleared.")
