"""
poam_tab.py
===========
Defines the POAMTab class — the Plan of Action and Milestones editor tab.

A POA&M is the live tracking document that records every open finding,
observation, and risk discovered during security assessments, together with
the remediation actions planned to address them.  It is updated continuously
between assessments rather than replaced each cycle.

OSCAL POA&M top-level sections implemented here:
  1. Document Metadata   — title, version, SSP reference, system ID
  2. Observations        — evidence records from assessments (EXAMINE/INTERVIEW/TEST)
  3. Risks               — identified risks with status lifecycle and remediations
  4. Findings            — formal assessor verdicts (satisfied / not-satisfied)
  5. POA&M Items         — the action items that cross-reference all of the above
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import (
    new_uuid, now_iso,
    empty_poam, build_oscal_poam, parse_poam_file, parse_ssp_file,
    # Import shared enum constants — defined once in models.py so AR and POA&M
    # always display the same option lists. (L1 / M1 fix)
    DEFAULT_OSCAL_VERSION,
    OBSERVATION_METHODS, OBSERVATION_TYPES,
    RISK_STATUSES, REMEDIATION_LIFECYCLES,
    FINDING_STATUS_STATES, FINDING_STATUS_REASONS,
)
from .tab_utils import is_tab_active

# FINDING_TARGET_TYPES is specific to POA&M (not shared with AR) so it stays here.
FINDING_TARGET_TYPES = ["statement-id", "objective-id"]


class POAMTab(tk.Frame):
    """
    A self-contained OSCAL POA&M editor panel.

    Layout:
      TOP     — Toolbar (Save, Open, New buttons + save-status label)
      BODY    — Scrollable form with five sections:
                  1. Metadata
                  2. Observations table
                  3. Risks table
                  4. Findings table
                  5. POA&M Items table
    """

    def __init__(self, parent, colors, set_status, get_oscal_version=None):
        """
        Initialise the POAMTab.

        Parameters:
            parent            - The ttk.Notebook this tab lives inside
            colors            - Shared colour dictionary from app.py
            set_status        - Callback: updates the main window status bar
            get_oscal_version - Optional callback returning the OSCAL version string
                                selected in the toolbar (e.g. "1.2.2"). Defaults to
                                a lambda returning "1.1.2" so the tab works standalone.
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors            = colors
        self._set_status        = set_status
        # Use the shared DEFAULT_OSCAL_VERSION constant from models.py (M1 fix)
        self._get_oscal_version = get_oscal_version or (lambda: DEFAULT_OSCAL_VERSION)

        # Dirty flag — True when there are unsaved changes in the form.
        # Set by any add/edit/remove action; cleared after a successful save
        # or when a file is opened (populating the form is not a user edit).
        self._dirty = False

        # Path of the file this POA&M was last opened from or saved to.
        # Read by the Workspace tab when saving a workspace manifest.
        self._current_path = None

        # Working data — mirrors the POA&M dict while editing.
        # empty_poam() returns a blank dict with the correct keys pre-filled
        # so the rest of the code never needs to guard against missing keys.
        self._poam = empty_poam()

        # Working lists for the four tables.  Each list is the live copy while
        # the user edits; _collect() writes them back to self._poam before
        # saving, and _populate() reads from self._poam into them after loading.
        self._observations: list = []
        self._risks:        list = []
        self._findings:     list = []
        self._poam_items:   list = []

        # StringVar registry for simple single-line text and combobox fields.
        # Keys match the self._poam dict keys (e.g. "title", "version").
        # Using a dict avoids naming an instance variable for every field.
        self._vars: dict = {}

        self._build()

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        """Assemble the toolbar and the scrollable form canvas."""
        self._build_toolbar()
        self._build_canvas()

    def theme_refresh(self):
        """
        Rebuild this tab's widgets after the colour theme changes, without
        losing any in-progress edits or loaded document data. _collect()
        flushes current widget values into self._poam first; _populate()
        rebuilds every widget's content from self._poam afterward.
        """
        self._collect()
        self.configure(bg=self._colors["BG"])   # This tab's own Frame background
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()
        self._populate()

    def _build_toolbar(self):
        """
        Create the top toolbar with Save, Open, and New buttons, plus a
        save-status label that updates after each file operation.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        def btn(text, cmd, bg, abg):
            """Local helper — create and pack one toolbar button."""
            tk.Button(
                tb, text=text, command=cmd,
                bg=bg, fg=C["BUTTON_TEXT"], font=("Helvetica", 11, "bold"),
                relief="flat", padx=12, pady=4, cursor="hand2",
                activebackground=abg, activeforeground=C["BUTTON_TEXT"],
            ).pack(side="left", padx=(12, 0), pady=8)

        btn("💾  Save POA&M", self._save,   C["GREEN_BG"], "#8cd39a")
        btn("📂  Open POA&M", self._open,   C["BLUE_BG"],  "#6a9fd8")
        btn("🆕  New POA&M",  self._new,    C["BLUE_BG"],  "#6a9fd8")

        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=8, pady=6
        )

        btn("📥  Import from AR", self._import_from_ar, C["BLUE_BG"], "#6a9fd8")

        self._status_lbl = tk.Label(
            tb, text="POA&M not saved",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=16)

    def _build_canvas(self):
        """
        Create the scrollable canvas that contains the entire POA&M form.

        tkinter has no native scrollable Frame, so the standard approach is:
          1. Create a Canvas (which supports scrolling natively).
          2. Embed a plain Frame inside it via create_window().
          3. Bind <Configure> events to keep the scroll region and frame
             width in sync as the window resizes.
        """
        C      = self._colors
        canvas = tk.Canvas(self, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        form = tk.Frame(canvas, bg=C["BG"])
        win  = canvas.create_window((0, 0), window=form, anchor="nw")
        # Whenever the inner form grows taller, update the scrollable region
        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        # Whenever the canvas (window) is resized, stretch the form to match
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        self._canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._build_form(form)

    def _on_mousewheel(self, event):
        """
        Scroll the canvas on mouse-wheel, but only when this tab is active.

        bind_all("<MouseWheel>") fires on every tab in the notebook, so without
        this guard, scrolling on any tab would also scroll this canvas.
        is_tab_active() walks up through any nested Notebook grouping (see
        app.py's Data/System Overview/Audit tabs), not just the immediate
        parent's selection, to confirm this tab is the one being viewed.
        """
        try:
            if is_tab_active(self):
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass   # Canvas destroyed/not ready — see SECURE_CODING.md #2

    # =========================================================================
    # FORM
    # =========================================================================

    def _build_form(self, parent):
        """
        Build the five-section POA&M editing form inside the scrollable canvas.

        Uses three local helper functions (section, field, table_section) to
        keep the repetitive widget-creation code DRY.  Each helper is defined
        as a nested function because it only makes sense in this context and
        closes over the local variables C and P.
        """
        C = self._colors
        P = dict(padx=28)   # Standard horizontal padding, unpacked with **P

        def section(title):
            """Dark coloured section heading bar across the full width."""
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(20, 4))
            tk.Label(hdr, text=title,
                     bg=C["HEADER_BG"], fg=C["ACCENT"],
                     font=("Helvetica", 12, "bold"), anchor="w",
                     ).pack(side="left", padx=12, pady=6)

        def field(label, key, width=50, default=""):
            """
            Add a label + Entry row to the form and register its StringVar.

            The StringVar is stored in self._vars[key] so _collect() and
            _populate() can read/write it by key without needing a separate
            instance variable for each field.
            """
            v = tk.StringVar(value=default)
            self._vars[key] = v
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=22, anchor="w",
                     ).pack(side="left")
            tk.Entry(row, textvariable=v,
                     bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                     relief="flat", font=("Helvetica", 11), width=width,
                     highlightthickness=1, highlightbackground=C["HEADER_BG"],
                     ).pack(side="left", ipady=3)

        def table_section(title, hint, columns, add_cmd, edit_cmd, remove_cmd,
                          height=5, extra_buttons=None):
            """Build a standard table section and return the Treeview."""
            section(title)
            if hint:
                tk.Label(parent, text=f"  {hint}",
                         bg=C["BG"], fg=C["SUBTEXT"],
                         font=("Helvetica", 9, "italic"),
                         ).pack(anchor="w", **P)

            frame = tk.Frame(parent, bg=C["CARD_BG"],
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
            frame.pack(fill="x", padx=28, pady=6)

            btn_row = tk.Frame(frame, bg=C["CARD_BG"])
            btn_row.pack(fill="x", padx=8, pady=6)

            for text, cmd in [
                ("＋  Add",    add_cmd),
                ("✎  Edit",   edit_cmd),
                ("✕  Remove", remove_cmd),
            ]:
                tk.Button(btn_row, text=text, command=cmd,
                          bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"],
                          font=("Helvetica", 10, "bold"),
                          relief="flat", padx=10, pady=3, cursor="hand2",
                          activebackground="#6a9fd8", activeforeground=C["BUTTON_TEXT"],
                          ).pack(side="left", padx=(0, 6))

            if extra_buttons:
                tk.Frame(btn_row, bg=C["HEADER_BG"], width=2).pack(
                    side="left", fill="y", padx=6, pady=2
                )
                for text, cmd in extra_buttons:
                    tk.Button(btn_row, text=text, command=cmd,
                              bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"],
                              font=("Helvetica", 10, "bold"),
                              relief="flat", padx=10, pady=3, cursor="hand2",
                              activebackground="#6a9fd8", activeforeground=C["BUTTON_TEXT"],
                              ).pack(side="left", padx=(0, 6))

            tree = ttk.Treeview(frame,
                                columns=tuple(c[0] for c in columns),
                                show="headings", height=height,
                                selectmode="browse")
            for col_id, heading, width_px, stretch in columns:
                tree.heading(col_id, text=heading, anchor="w")
                tree.column(col_id, width=width_px, anchor="w", stretch=stretch)

            sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
            tree.pack(fill="x", padx=8, pady=(0, 8))
            return tree

        # ── Section 1: Metadata ───────────────────────────────────────────────
        section("1 ·  POA&M Metadata")
        field("POA&M Title *",     "title",      width=60)
        field("Version *",         "version",    width=20, default="1.0")
        # SSP Reference row — entry + Browse button side by side
        ssp_v = tk.StringVar()
        self._vars["import_ssp"] = ssp_v
        ssp_row = tk.Frame(parent, bg=C["BG"])
        ssp_row.pack(fill="x", **P, pady=3)
        tk.Label(ssp_row, text="SSP Reference (href)", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=22, anchor="w",
                 ).pack(side="left")
        tk.Entry(ssp_row, textvariable=ssp_v,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), width=48,
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", ipady=3)
        tk.Button(ssp_row, text="📂  Browse…", command=self._browse_ssp,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=(6, 0))

        # ── Read-only visibility of the referenced SSP's components/
        # capabilities (see ap_tab.py's equivalent section) — helps when
        # writing a weakness/observation to know what the system is built
        # from, without separately opening the SSP file.
        ssp_ref_btn_row = tk.Frame(parent, bg=C["BG"])
        ssp_ref_btn_row.pack(fill="x", **P, pady=(2, 2))
        tk.Button(ssp_ref_btn_row, text="🔄  Refresh from SSP",
                  command=self._refresh_ssp_components,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left")
        self._ssp_comp_status = tk.Label(
            ssp_ref_btn_row, text="No SSP referenced yet.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        )
        self._ssp_comp_status.pack(side="left", padx=(8, 0))

        ssp_ref_panes = tk.Frame(parent, bg=C["BG"])
        ssp_ref_panes.pack(fill="x", **P, pady=(0, 6))

        comp_pane = tk.Frame(ssp_ref_panes, bg=C["CARD_BG"],
                              highlightthickness=1, highlightbackground=C["HEADER_BG"])
        comp_pane.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(comp_pane, text="Components", bg=C["CARD_BG"], fg=C["ACCENT"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self._ssp_comp_tree = ttk.Treeview(
            comp_pane, columns=("component",), show="headings", height=4, selectmode="browse",
        )
        self._ssp_comp_tree.heading("component", text="Component", anchor="w")
        self._ssp_comp_tree.column("component", anchor="w", stretch=True)
        self._ssp_comp_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cap_pane = tk.Frame(ssp_ref_panes, bg=C["CARD_BG"],
                             highlightthickness=1, highlightbackground=C["HEADER_BG"])
        cap_pane.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(cap_pane, text="Capabilities", bg=C["CARD_BG"], fg=C["ACCENT"],
                 font=("Helvetica", 9, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        self._ssp_cap_tree = ttk.Treeview(
            cap_pane, columns=("capability",), show="headings", height=4, selectmode="browse",
        )
        self._ssp_cap_tree.heading("capability", text="Capability", anchor="w")
        self._ssp_cap_tree.column("capability", anchor="w", stretch=True)
        self._ssp_cap_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Refresh automatically whenever the SSP path changes (typed or browsed to).
        ssp_v.trace_add("write", lambda *_a: self._refresh_ssp_components())

        field("System ID",         "system_id",  width=40)
        tk.Label(parent,
                 text="  * Required fields.  SSP Reference: select the linked SSP file — "
                      "saved as a relative path in the OSCAL output.\n"
                      "  System ID: enter a UUID (preferred) or a plain system name.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=28)

        # ── Section 2: Observations ───────────────────────────────────────────
        self._obs_tree = table_section(
            title="2 ·  Observations",
            hint="Evidence records collected during assessments (EXAMINE / INTERVIEW / TEST).",
            columns=[
                ("title",     "Title",       200, True),
                ("methods",   "Methods",     130, False),
                ("types",     "Types",       150, False),
                ("collected", "Collected",   130, False),
                ("expires",   "Expires",     110, False),
            ],
            add_cmd=self._add_observation,
            edit_cmd=self._edit_observation,
            remove_cmd=self._remove_observation,
            extra_buttons=[("📥  Import from AR", self._import_from_ar)],
        )

        # ── Section 3: Risks ─────────────────────────────────────────────────
        self._risk_tree = table_section(
            title="3 ·  Risks",
            hint="Identified risks with status lifecycle and optional remediation plans.",
            columns=[
                ("title",    "Title",              110, False),
                ("status",   "Status",              75, False),
                ("deadline", "Deadline",            70, False),
                ("rem_detail", "Remediation Details", 345, True),
            ],
            add_cmd=self._add_risk,
            edit_cmd=self._edit_risk,
            remove_cmd=self._remove_risk,
        )

        # ── Section 4: Findings ───────────────────────────────────────────────
        self._finding_tree = table_section(
            title="4 ·  Findings",
            hint="Formal assessor verdicts against control statement IDs or objective IDs. "
                 "UUID shown for cross-reference back to the source Assessment Results document.",
            columns=[
                ("uuid",         "UUID (AR ref)",  90, False),
                ("title",        "Title",          200, True),
                ("target_id",    "Target ID",      120, False),
                ("state",        "State",           90, False),
                ("reason",       "Reason",          70, False),
            ],
            add_cmd=self._add_finding,
            edit_cmd=self._edit_finding,
            remove_cmd=self._remove_finding,
        )

        # ── Section 5: POA&M Items ────────────────────────────────────────────
        self._item_tree = table_section(
            title="5 ·  POA&M Items",
            hint="Action items that cross-reference observations, risks, and findings.",
            columns=[
                ("title",     "Title",                200, True),
                ("sched",     "Scheduled Completion", 140, False),
                ("obs",       "Obs",                   45, False),
                ("risks",     "Risks",                 45, False),
                ("finds",     "Findings",              55, False),
            ],
            add_cmd=self._add_poam_item,
            edit_cmd=self._edit_poam_item,
            remove_cmd=self._remove_poam_item,
            height=6,
        )

        # bottom padding
        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # DIALOG HELPER
    # =========================================================================

    def _make_dialog(self, title, width=480):
        """
        Create and return a modal Toplevel dialog window.

        transient() keeps the dialog stacked above the main window.
        grab_set() makes it modal — all keyboard and mouse events are routed
        exclusively to this dialog until it is closed, preventing the user from
        clicking behind it.  The caller adds content widgets and then calls
        self.wait_window(dlg) to block until the dialog closes.

        Parameters:
            title - Dialog window title
            width - Minimum window width in pixels

        Returns:
            A configured tk.Toplevel ready to receive content widgets.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.minsize(width, 10)
        # usability_review_2.md — Escape always means Cancel.
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        return dlg

    def _dlg_field(self, parent, label, row_idx, width=40, default=""):
        """Add a label+entry pair to a dialog grid. Returns the StringVar."""
        C = self._colors
        tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="w",
                 ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=4)
        v = tk.StringVar(value=default)
        tk.Entry(parent, textvariable=v,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10), width=width,
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).grid(row=row_idx, column=1, sticky="ew", padx=(0, 12), pady=4)
        return v

    def _dlg_combo(self, parent, label, row_idx, values, default=""):
        """Add a label+combobox pair to a dialog grid. Returns the StringVar."""
        C = self._colors
        tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="w",
                 ).grid(row=row_idx, column=0, sticky="w", padx=12, pady=4)
        v = tk.StringVar(value=default)
        ttk.Combobox(parent, textvariable=v, values=values,
                     state="readonly", width=30,
                     ).grid(row=row_idx, column=1, sticky="w",
                            padx=(0, 12), pady=4)
        return v

    def _dlg_text(self, parent, label, row_idx, height=3):
        """Add a label+Text area to a dialog grid. Returns the Text widget."""
        C = self._colors
        tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=row_idx, column=0, sticky="nw", padx=12, pady=4)
        t = tk.Text(parent,
                    bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                    relief="flat", font=("Helvetica", 10), height=height,
                    wrap="word", padx=6, pady=4,
                    highlightthickness=1, highlightbackground=C["HEADER_BG"],
                    )
        t.grid(row=row_idx, column=1, sticky="ew", padx=(0, 12), pady=4)
        return t

    def _ok_cancel(self, dlg, ok_cmd):
        """Add OK / Cancel button row at the bottom of a dialog."""
        C    = self._colors
        brow = tk.Frame(dlg, bg=C["BG"])
        brow.pack(fill="x", pady=(4, 12), padx=12)
        tk.Button(brow, text="OK", command=ok_cmd,
                  bg=C["GREEN_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
                  relief="flat", padx=16, pady=4, cursor="hand2",
                  ).pack(side="left")
        tk.Button(brow, text="Cancel", command=dlg.destroy,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  ).pack(side="left", padx=8)

    # =========================================================================
    # OBSERVATION CRUD
    # =========================================================================

    def _obs_row(self, o):
        """Convert an observation dict into a tuple of display values for the Treeview row."""
        return (
            o.get("title", "") or o.get("description", "")[:60],
            ", ".join(o.get("methods", [])),
            ", ".join(o.get("types", [])),
            o.get("collected", "")[:10],
            o.get("expires", "")[:10],
        )

    def _refresh_obs_tree(self):
        """Clear and repopulate the Observations Treeview from self._observations."""
        self._obs_tree.delete(*self._obs_tree.get_children())
        for o in self._observations:
            self._obs_tree.insert("", "end", values=self._obs_row(o))

    def _observation_dialog(self, existing=None):
        """
        Show a modal dialog to add or edit one observation.

        Parameters:
            existing - An existing observation dict to pre-fill the form,
                       or None to start with an empty form.

        Returns:
            A filled observation dict, or None if the user cancelled.
        """
        C   = self._colors
        dlg = self._make_dialog(
            "Edit Observation" if existing else "Add Observation", width=560
        )
        # 'ex or {}' means: use 'existing' if provided, otherwise use an empty
        # dict so all the .get() calls below return their defaults safely.
        ex  = existing or {}

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title      = self._dlg_field(body, "Title",       0, default=ex.get("title",""))
        v_assessed   = self._dlg_field(body, "Assessed by", 1, default=ex.get("assessed_by",""),
                                       width=40)
        default_collected = ex.get("collected", "") if existing else now_iso()[:10]
        v_collected  = self._dlg_field(body, "Collected *", 2, default=default_collected)
        v_expires    = self._dlg_field(body, "Expires",     3, default=ex.get("expires",""))

        # Methods — multi-select via Listbox
        tk.Label(body, text="Methods *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=4, column=0, sticky="nw", padx=12, pady=4)
        meth_frame = tk.Frame(body, bg=C["BG"])
        meth_frame.grid(row=4, column=1, sticky="w", padx=(0, 12), pady=4)
        meth_lb = tk.Listbox(meth_frame, selectmode="multiple",
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             font=("Helvetica", 10), height=4, width=20,
                             relief="flat", exportselection=False,
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        for m in OBSERVATION_METHODS:
            meth_lb.insert("end", m)
        existing_methods = ex.get("methods", [])
        for i, m in enumerate(OBSERVATION_METHODS):
            if m in existing_methods:
                meth_lb.selection_set(i)
        meth_lb.pack(side="left")

        # Types — multi-select via Listbox
        tk.Label(body, text="Types", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=5, column=0, sticky="nw", padx=12, pady=4)
        type_frame = tk.Frame(body, bg=C["BG"])
        type_frame.grid(row=5, column=1, sticky="w", padx=(0, 12), pady=4)
        type_lb = tk.Listbox(type_frame, selectmode="multiple",
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             font=("Helvetica", 10), height=6, width=30,
                             relief="flat", exportselection=False,
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        for t in OBSERVATION_TYPES:
            type_lb.insert("end", t)
        existing_types = ex.get("types", [])
        for i, t in enumerate(OBSERVATION_TYPES):
            if t in existing_types:
                type_lb.selection_set(i)
        type_lb.pack(side="left")

        t_desc = self._dlg_text(body, "Description *", 6, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        # Relevant Evidence sub-table
        tk.Label(body, text="Relevant Evidence", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=7, column=0, sticky="nw", padx=12, pady=4)

        ev_frame = tk.Frame(body, bg=C["CARD_BG"],
                            highlightthickness=1,
                            highlightbackground=C["HEADER_BG"])
        ev_frame.grid(row=7, column=1, sticky="ew", padx=(0, 12), pady=4)

        ev_btn_row = tk.Frame(ev_frame, bg=C["CARD_BG"])
        ev_btn_row.pack(fill="x", padx=6, pady=4)

        ev_list: list = list(ex.get("relevant_evidence", []))

        ev_tree = ttk.Treeview(ev_frame,
                               columns=("href", "desc"),
                               show="headings", height=3, selectmode="browse")
        ev_tree.heading("href", text="Href / Link", anchor="w")
        ev_tree.heading("desc", text="Description", anchor="w")
        ev_tree.column("href", width=200, anchor="w", stretch=True)
        ev_tree.column("desc", width=200, anchor="w", stretch=True)

        def _refresh_ev():
            ev_tree.delete(*ev_tree.get_children())
            for e in ev_list:
                ev_tree.insert("", "end",
                               values=(e.get("href",""), e.get("description","")))

        def _add_ev():
            d2 = self._make_dialog("Add Evidence", width=400)
            f2 = tk.Frame(d2, bg=C["BG"])
            f2.pack(fill="both", expand=True, padx=4, pady=4)
            f2.columnconfigure(1, weight=1)
            v_href = self._dlg_field(f2, "Href / Link", 0, width=40)
            v_edesc = self._dlg_field(f2, "Description", 1, width=40)

            def _ok2():
                ev_list.append({"href": v_href.get().strip(),
                                "description": v_edesc.get().strip()})
                _refresh_ev()
                d2.destroy()
            self._ok_cancel(d2, _ok2)
            self.wait_window(d2)

        def _remove_ev():
            sel = ev_tree.selection()
            if sel:
                ev_list.pop(ev_tree.index(sel[0]))
                _refresh_ev()

        tk.Button(ev_btn_row, text="＋  Add", command=_add_ev,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9, "bold"),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left")
        tk.Button(ev_btn_row, text="✕  Remove Selected", command=_remove_ev,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left", padx=6)
        ev_tree.pack(fill="x", padx=6, pady=(0, 6))
        _refresh_ev()

        t_remarks = self._dlg_text(body, "Remarks", 8, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            desc = t_desc.get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Required", "Description is required.",
                                       parent=dlg)
                return
            methods = [OBSERVATION_METHODS[i]
                       for i in meth_lb.curselection()]
            if not methods:
                messagebox.showwarning("Required",
                                       "At least one Method is required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":             ex.get("uuid", new_uuid()),
                "title":            v_title.get().strip(),
                "assessed_by":      v_assessed.get().strip(),
                "description":      desc,
                "methods":          methods,
                "types":            [OBSERVATION_TYPES[i]
                                     for i in type_lb.curselection()],
                "collected":        v_collected.get().strip() or now_iso(),
                "expires":          v_expires.get().strip(),
                "relevant_evidence": ev_list,
                "remarks":          t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_observation(self):
        """Open the observation dialog and append the result to the list."""
        obs = self._observation_dialog()
        if obs:
            self._observations.append(obs)
            self._refresh_obs_tree()
            self._dirty = True

    def _edit_observation(self):
        """Open the observation dialog pre-filled with the selected row's data."""
        sel = self._obs_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an observation to edit.")
            return
        idx = self._obs_tree.index(sel[0])
        updated = self._observation_dialog(existing=self._observations[idx])
        if updated:
            # Preserve the original UUID — only the content fields change
            updated["uuid"] = self._observations[idx]["uuid"]
            self._observations[idx] = updated
            self._refresh_obs_tree()
            self._dirty = True

    def _remove_observation(self):
        """Delete the selected observation from the list after finding its index."""
        sel = self._obs_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an observation to remove.")
            return
        idx = self._obs_tree.index(sel[0])
        self._observations.pop(idx)
        self._refresh_obs_tree()
        self._dirty = True

    # =========================================================================
    # RISK CRUD
    # =========================================================================

    def _risk_row(self, r):
        """Convert a risk dict into a tuple of display values for the Treeview row."""
        rems = r.get("remediations", [])
        parts = []
        for rem in rems:
            lc = rem.get("lifecycle", "")
            t  = rem.get("title", "")
            parts.append(f"[{lc}] {t}" if lc and t else (lc or t))
        detail = "  |  ".join(parts)
        return (
            r.get("title", ""),
            r.get("status", "open"),
            r.get("deadline", "")[:10],
            detail,
        )

    def _refresh_risk_tree(self):
        self._risk_tree.delete(*self._risk_tree.get_children())
        for r in self._risks:
            self._risk_tree.insert("", "end", values=self._risk_row(r))

    def _risk_dialog(self, existing=None):
        C   = self._colors
        dlg = self._make_dialog(
            "Edit Risk" if existing else "Add Risk", width=580
        )
        ex  = existing or {}

        if existing and existing.get("uuid"):
            tk.Label(
                dlg,
                text="⚠  This risk was imported from an Assessment Results file. "
                     "Review the description, impact statement, and add an "
                     "organisational remediation plan before saving.",
                bg="#4a3800", fg="#ffe080",
                font=("Helvetica", 9, "italic"),
                wraplength=540, justify="left", padx=10, pady=6,
            ).pack(fill="x", padx=8, pady=(4, 0))

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title    = self._dlg_field(body, "Title *",    0, default=ex.get("title",""))
        v_status   = self._dlg_combo(body, "Status *",   1, RISK_STATUSES,
                                     default=ex.get("status","open"))
        v_deadline = self._dlg_field(body, "Deadline",   2,
                                     default=ex.get("deadline",""))

        CIA_IMPACTS = ["", "high", "moderate", "low", "very-low", "not-applicable"]
        v_cia_c = self._dlg_combo(body, "Confidentiality Impact", 3, CIA_IMPACTS,
                                  default=ex.get("cia_c", ""))
        v_cia_i = self._dlg_combo(body, "Integrity Impact",       4, CIA_IMPACTS,
                                  default=ex.get("cia_i", ""))
        v_cia_a = self._dlg_combo(body, "Availability Impact",    5, CIA_IMPACTS,
                                  default=ex.get("cia_a", ""))

        t_desc = self._dlg_text(body, "Description *", 6, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        t_stmt = self._dlg_text(body, "Impact Statement *", 7, height=3)
        t_stmt.insert("1.0", ex.get("statement", ""))

        # Remediations sub-table
        tk.Label(body, text="Remediations", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=8, column=0, sticky="nw", padx=12, pady=4)

        rem_frame = tk.Frame(body, bg=C["CARD_BG"],
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        rem_frame.grid(row=8, column=1, sticky="ew", padx=(0, 12), pady=4)

        rem_btn_row = tk.Frame(rem_frame, bg=C["CARD_BG"])
        rem_btn_row.pack(fill="x", padx=6, pady=4)

        rem_list: list = list(ex.get("remediations", []))

        rem_tree = ttk.Treeview(rem_frame,
                                columns=("lifecycle", "title", "desc"),
                                show="headings", height=3, selectmode="browse")
        rem_tree.heading("lifecycle", text="Lifecycle",   anchor="w")
        rem_tree.heading("title",     text="Title",       anchor="w")
        rem_tree.heading("desc",      text="Description", anchor="w")
        rem_tree.column("lifecycle", width=120, anchor="w", stretch=False)
        rem_tree.column("title",     width=160, anchor="w", stretch=False)
        rem_tree.column("desc",      width=200, anchor="w", stretch=True)

        def _refresh_rem():
            rem_tree.delete(*rem_tree.get_children())
            for rem in rem_list:
                rem_tree.insert("", "end", values=(
                    rem.get("lifecycle",""),
                    rem.get("title",""),
                    rem.get("description","")[:60],
                ))

        def _add_rem():
            d2 = self._make_dialog("Add Remediation", width=440)
            f2 = tk.Frame(d2, bg=C["BG"])
            f2.pack(fill="both", expand=True, padx=4, pady=4)
            f2.columnconfigure(1, weight=1)
            v_rlc   = self._dlg_combo(f2, "Lifecycle *", 0,
                                      REMEDIATION_LIFECYCLES, "recommendation")
            v_rtitle = self._dlg_field(f2, "Title *",    1, width=38)
            t_rdesc  = self._dlg_text(f2, "Description *", 2, height=3)
            t_rrem   = self._dlg_text(f2, "Remarks",      3, height=2)

            def _ok2():
                t = v_rtitle.get().strip()
                d = t_rdesc.get("1.0", "end-1c").strip()
                if not t or not d:
                    messagebox.showwarning("Required",
                                          "Title and Description are required.",
                                          parent=d2)
                    return
                rem_list.append({
                    "uuid":        new_uuid(),
                    "lifecycle":   v_rlc.get(),
                    "title":       t,
                    "description": d,
                    "remarks":     t_rrem.get("1.0", "end-1c").strip(),
                })
                _refresh_rem()
                d2.destroy()
            self._ok_cancel(d2, _ok2)
            self.wait_window(d2)

        def _remove_rem():
            sel2 = rem_tree.selection()
            if sel2:
                rem_list.pop(rem_tree.index(sel2[0]))
                _refresh_rem()

        tk.Button(rem_btn_row, text="＋  Add", command=_add_rem,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9, "bold"),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left")
        tk.Button(rem_btn_row, text="✕  Remove Selected", command=_remove_rem,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left", padx=6)
        rem_tree.pack(fill="x", padx=6, pady=(0, 6))
        _refresh_rem()

        t_remarks = self._dlg_text(body, "Remarks", 9, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            stmt  = t_stmt.get("1.0", "end-1c").strip()
            if not title or not desc or not stmt:
                messagebox.showwarning("Required",
                                       "Title, Description, and Impact Statement are required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":         ex.get("uuid", new_uuid()),
                "title":        title,
                "description":  desc,
                "statement":    stmt,
                "status":       v_status.get(),
                "deadline":     v_deadline.get().strip(),
                "cia_c":        v_cia_c.get(),
                "cia_i":        v_cia_i.get(),
                "cia_a":        v_cia_a.get(),
                "remediations": rem_list,
                "remarks":      t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_risk(self):
        r = self._risk_dialog()
        if r:
            self._risks.append(r)
            self._refresh_risk_tree()
            self._dirty = True

    def _edit_risk(self):
        sel = self._risk_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a risk to edit.")
            return
        idx = self._risk_tree.index(sel[0])
        updated = self._risk_dialog(existing=self._risks[idx])
        if updated:
            updated["uuid"] = self._risks[idx]["uuid"]
            self._risks[idx] = updated
            self._refresh_risk_tree()
            self._dirty = True

    def _remove_risk(self):
        sel = self._risk_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a risk to remove.")
            return
        self._risks.pop(self._risk_tree.index(sel[0]))
        self._refresh_risk_tree()
        self._dirty = True

    # =========================================================================
    # FINDING CRUD
    # =========================================================================

    def _finding_row(self, f):
        uuid = f.get("uuid", "")
        short_uuid = uuid[:8] + "…" if len(uuid) > 8 else uuid
        return (
            short_uuid,
            f.get("title", ""),
            f.get("target_id", ""),
            f.get("status_state", ""),
            f.get("status_reason", ""),
        )

    def _refresh_finding_tree(self):
        self._finding_tree.delete(*self._finding_tree.get_children())
        for f in self._findings:
            self._finding_tree.insert("", "end", values=self._finding_row(f))

    def _finding_dialog(self, existing=None):
        C   = self._colors
        dlg = self._make_dialog(
            "Edit Finding" if existing else "Add Finding", width=520
        )
        ex  = existing or {}

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title  = self._dlg_field(body, "Title *",       0, default=ex.get("title",""))
        v_ttype  = self._dlg_combo(body, "Target Type *", 1, FINDING_TARGET_TYPES,
                                   default=ex.get("target_type","statement-id"))
        v_tid    = self._dlg_field(body, "Target ID *",   2, default=ex.get("target_id",""))
        v_state  = self._dlg_combo(body, "Status State *", 3, FINDING_STATUS_STATES,
                                   default=ex.get("status_state","not-satisfied"))
        v_reason = self._dlg_combo(body, "Status Reason", 4,
                                   [r for r in FINDING_STATUS_REASONS],
                                   default=ex.get("status_reason",""))

        t_desc = self._dlg_text(body, "Description *", 5, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        t_remarks = self._dlg_text(body, "Remarks", 6, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            tid   = v_tid.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            if not title or not tid or not desc:
                messagebox.showwarning("Required",
                                       "Title, Target ID, and Description are required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":          ex.get("uuid", new_uuid()),
                "title":         title,
                "description":   desc,
                "target_type":   v_ttype.get(),
                "target_id":     tid,
                "status_state":  v_state.get(),
                "status_reason": v_reason.get(),
                "remarks":       t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_finding(self):
        f = self._finding_dialog()
        if f:
            self._findings.append(f)
            self._refresh_finding_tree()
            self._dirty = True

    def _edit_finding(self):
        sel = self._finding_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a finding to edit.")
            return
        idx = self._finding_tree.index(sel[0])
        updated = self._finding_dialog(existing=self._findings[idx])
        if updated:
            updated["uuid"] = self._findings[idx]["uuid"]
            self._findings[idx] = updated
            self._refresh_finding_tree()
            self._dirty = True

    def _remove_finding(self):
        sel = self._finding_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a finding to remove.")
            return
        self._findings.pop(self._finding_tree.index(sel[0]))
        self._refresh_finding_tree()
        self._dirty = True

    # =========================================================================
    # POA&M ITEM CRUD
    # =========================================================================

    def _item_row(self, item):
        return (
            item.get("title", ""),
            item.get("scheduled_completion", ""),
            str(len(item.get("related_observation_uuids", []))) or "",
            str(len(item.get("related_risk_uuids", []))) or "",
            str(len(item.get("related_finding_uuids", []))) or "",
        )

    def _refresh_item_tree(self):
        self._item_tree.delete(*self._item_tree.get_children())
        for item in self._poam_items:
            self._item_tree.insert("", "end", values=self._item_row(item))

    def _poam_item_dialog(self, existing=None):
        C   = self._colors
        dlg = self._make_dialog(
            "Edit POA&M Item" if existing else "Add POA&M Item", width=560
        )
        ex  = existing or {}

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title      = self._dlg_field(body, "Title *",               0, default=ex.get("title",""))
        v_sched_comp = self._dlg_field(body, "Scheduled Completion", 1,
                                       default=ex.get("scheduled_completion", ""),
                                       width=20)
        tk.Label(body, text="  (YYYY-MM-DD)", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).grid(row=1, column=1, sticky="w", padx=(210, 0))
        t_desc  = self._dlg_text(body, "Description *", 2, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        # Cross-reference pickers ─ show UUID+title of available records
        def _obs_label(o):
            t = o.get("title","") or o.get("description","")[:40]
            return f"{o['uuid'][:8]}…  {t}"

        def _risk_label(r):
            return f"{r['uuid'][:8]}…  {r.get('title','')}"

        def _find_label(f):
            return f"{f['uuid'][:8]}…  {f.get('title','')}"

        def _xref_section(parent, row, label, all_items, label_fn, selected_uuids):
            """Build a multi-select Listbox for cross-referencing by UUID."""
            tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 10), anchor="nw",
                     ).grid(row=row, column=0, sticky="nw", padx=12, pady=4)
            lb = tk.Listbox(parent, selectmode="multiple",
                            bg=C["CARD_BG"], fg=C["TEXT"],
                            font=("Helvetica", 9), height=min(len(all_items)+1, 6),
                            width=55, relief="flat", exportselection=False,
                            highlightthickness=1,
                            highlightbackground=C["HEADER_BG"])
            for item in all_items:
                lb.insert("end", label_fn(item))
            # Pre-select matching items
            for i, item in enumerate(all_items):
                if item["uuid"] in selected_uuids:
                    lb.selection_set(i)
            lb.grid(row=row, column=1, sticky="ew", padx=(0, 12), pady=4)
            return lb

        obs_lb  = _xref_section(body, 3, "Related Observations",
                                 self._observations, _obs_label,
                                 ex.get("related_observation_uuids", []))
        risk_lb = _xref_section(body, 4, "Related Risks",
                                 self._risks, _risk_label,
                                 ex.get("related_risk_uuids", []))
        find_lb = _xref_section(body, 5, "Related Findings",
                                 self._findings, _find_label,
                                 ex.get("related_finding_uuids", []))

        t_remarks = self._dlg_text(body, "Remarks", 6, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            if not title or not desc:
                messagebox.showwarning("Required",
                                       "Title and Description are required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":                 ex.get("uuid", new_uuid()),
                "title":                title,
                "scheduled_completion": v_sched_comp.get().strip(),
                "description":          desc,
                "related_observation_uuids": [
                    self._observations[i]["uuid"]
                    for i in obs_lb.curselection()
                ],
                "related_risk_uuids": [
                    self._risks[i]["uuid"]
                    for i in risk_lb.curselection()
                ],
                "related_finding_uuids": [
                    self._findings[i]["uuid"]
                    for i in find_lb.curselection()
                ],
                "remarks": t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_poam_item(self):
        item = self._poam_item_dialog()
        if item:
            self._poam_items.append(item)
            self._refresh_item_tree()
            self._dirty = True

    def _edit_poam_item(self):
        sel = self._item_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a POA&M item to edit.")
            return
        idx = self._item_tree.index(sel[0])
        updated = self._poam_item_dialog(existing=self._poam_items[idx])
        if updated:
            updated["uuid"] = self._poam_items[idx]["uuid"]
            self._poam_items[idx] = updated
            self._refresh_item_tree()
            self._dirty = True

    def _remove_poam_item(self):
        sel = self._item_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a POA&M item to remove.")
            return
        self._poam_items.pop(self._item_tree.index(sel[0]))
        self._refresh_item_tree()
        self._dirty = True

    def _browse_ssp(self):
        """Open a file picker and write the chosen SSP path into the SSP Reference field."""
        path = filedialog.askopenfilename(
            title="Select SSP JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._vars["import_ssp"].set(path)

    def _refresh_ssp_components(self):
        """
        Parse the referenced SSP file and populate the read-only Components/
        Capabilities panes, so a weakness/observation can be written with
        visibility into what the system is built from — mirrors ap_tab.py's
        equivalent method. Reads directly from disk (not from the SSP Editor
        tab), and shows any problem as a quiet inline status message rather
        than a popup, since this runs on every keystroke in the SSP field.
        """
        if not hasattr(self, "_ssp_comp_tree"):
            return   # Called before the form is built yet — nothing to do

        self._ssp_comp_tree.delete(*self._ssp_comp_tree.get_children())
        self._ssp_cap_tree.delete(*self._ssp_cap_tree.get_children())

        raw_path = self._vars["import_ssp"].get().strip()
        if not raw_path:
            self._ssp_comp_status.config(text="No SSP referenced yet.")
            return

        # A path saved into a POA&M file is a relative href (relative to the
        # POA&M file's own directory), so try it as-is first, then relative
        # to this POA&M's own file location.
        path = Path(raw_path)
        if not path.is_file() and not path.is_absolute() and self._current_path:
            candidate = Path(self._current_path).resolve().parent / raw_path
            if candidate.is_file():
                path = candidate
        if not path.is_file():
            self._ssp_comp_status.config(text=f"SSP file not found: {raw_path}")
            return

        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            if "system-security-plan" not in raw:
                self._ssp_comp_status.config(
                    text="Not a valid OSCAL SSP file (missing 'system-security-plan')."
                )
                return
            ssp, _bm_info = parse_ssp_file(raw)
        except (json.JSONDecodeError, OSError) as exc:
            self._ssp_comp_status.config(text=f"Could not read SSP: {exc}")
            return

        components = ssp.get("components", [])
        for comp in components:
            self._ssp_comp_tree.insert("", "end", values=(comp.get("title", "").strip() or "(untitled)",))

        capabilities = ssp.get("capabilities_used", [])
        for cap in capabilities:
            self._ssp_cap_tree.insert("", "end", values=(cap.get("name", "").strip() or "(untitled)",))

        self._ssp_comp_status.config(
            text=f"{len(components)} component(s), {len(capabilities)} capability(ies) "
                 f"loaded from {Path(path).name}."
        )

    def _import_from_ar(self):
        """
        Load an OSCAL Assessment Results file and import its not-satisfied
        findings as POA&M items, copying related observations across too.

        This is the Phase 3 reverse flow — the POA&M tab can pull from any
        saved AR file even when the AR tab is not open.
        """
        from .models import parse_ar_file

        path = filedialog.askopenfilename(
            title="Select Assessment Results JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return

        if "assessment-results" not in raw:
            messagebox.showerror(
                "Not an Assessment Results file",
                "The selected file does not contain an 'assessment-results' key.",
            )
            return

        try:
            ar = parse_ar_file(raw)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            return

        not_satisfied = [
            f for f in ar.get("findings", [])
            if f.get("status_state") == "not-satisfied"
        ]
        if not not_satisfied:
            messagebox.showinfo(
                "No not-satisfied findings",
                "The selected Assessment Results file has no 'not-satisfied' findings.",
            )
            return

        if not messagebox.askyesno(
            "Import findings",
            f"Import {len(not_satisfied)} not-satisfied finding(s) from:\n"
            f"{Path(path).name}\n\nProceed?",
        ):
            return

        obs_by_uuid  = {o["uuid"]: o for o in ar.get("observations", [])}
        risk_by_uuid = {r["uuid"]: r for r in ar.get("risks", [])}

        existing_obs_uuids     = {o["uuid"] for o in self._observations}
        existing_risk_uuids    = {r["uuid"] for r in self._risks}
        existing_finding_uuids = {f["uuid"] for f in self._findings}

        added_obs:      set = set()
        added_risks:    set = set()
        added_findings: set = set()
        skipped = 0
        added_items = 0

        for f in not_satisfied:
            finding_uuid = f.get("uuid", "")
            if finding_uuid and finding_uuid in existing_finding_uuids:
                skipped += 1
                continue

            # ── finding ───────────────────────────────────────────────────────
            self._findings.append({
                "uuid":          finding_uuid or new_uuid(),
                "title":         f.get("title", ""),
                "description":   f.get("description", ""),
                "target_type":   f.get("target_type", "statement-id"),
                "target_id":     f.get("target_id", ""),
                "status_state":  f.get("status_state", "not-satisfied"),
                "status_reason": f.get("status_reason", ""),
                "remarks":       f.get("remarks", ""),
            })
            if finding_uuid:
                existing_finding_uuids.add(finding_uuid)
                added_findings.add(finding_uuid)

            # ── observations ──────────────────────────────────────────────────
            new_obs_uuids = []
            for obs_uuid in f.get("related_obs_uuids", []):
                if obs_uuid in obs_by_uuid and obs_uuid not in existing_obs_uuids:
                    self._observations.append(dict(obs_by_uuid[obs_uuid]))
                    existing_obs_uuids.add(obs_uuid)
                    added_obs.add(obs_uuid)
                if obs_uuid in obs_by_uuid:
                    new_obs_uuids.append(obs_uuid)

            # ── risks ─────────────────────────────────────────────────────────
            new_risk_uuids = []
            for risk_uuid in f.get("related_risk_uuids", []):
                if risk_uuid in risk_by_uuid and risk_uuid not in existing_risk_uuids:
                    self._risks.append(dict(risk_by_uuid[risk_uuid]))
                    existing_risk_uuids.add(risk_uuid)
                    added_risks.add(risk_uuid)
                if risk_uuid in risk_by_uuid:
                    new_risk_uuids.append(risk_uuid)

            ctrl_id = f.get("target_id", "")
            title   = f.get("title") or f"Not-satisfied: {ctrl_id}"
            self._poam_items.append({
                "uuid":                      new_uuid(),
                "title":                     title,
                "scheduled_completion":      "",
                "description":               (
                    f.get("description", "")
                    or f"Control {ctrl_id} was assessed as not-satisfied."
                ),
                "related_observation_uuids": new_obs_uuids,
                "related_risk_uuids":        new_risk_uuids,
                "related_finding_uuids":     [finding_uuid] if finding_uuid else [],
                "remarks":                   f.get("remarks", ""),
            })
            added_items += 1

        if added_findings:
            self._refresh_finding_tree()
        if added_obs:
            self._refresh_obs_tree()
        if added_risks:
            self._refresh_risk_tree()
        self._refresh_item_tree()
        self._dirty = True

        parts = [f"{added_items} POA&M item(s)", f"{len(added_findings)} finding(s)"]
        if added_obs:
            parts.append(f"{len(added_obs)} observation(s)")
        if added_risks:
            parts.append(f"{len(added_risks)} risk(s)")
        summary = "Added " + ", ".join(parts) + "."
        if skipped:
            summary += f"\n{skipped} finding(s) skipped (already imported)."
        messagebox.showinfo("Import complete", summary)

    # =========================================================================
    # COLLECT / POPULATE / RESET
    # =========================================================================

    def _collect(self):
        """Gather all form values into self._poam before save."""
        self._dirty = True   # Any collection signals a user edit
        self._poam["title"]       = self._vars["title"].get().strip()
        self._poam["version"]     = self._vars["version"].get().strip() or "1.0"
        self._poam["import_ssp"]  = self._vars["import_ssp"].get().strip()
        self._poam["system_id"]   = self._vars["system_id"].get().strip()
        self._poam["observations"] = list(self._observations)
        self._poam["risks"]        = list(self._risks)
        self._poam["findings"]     = list(self._findings)
        self._poam["poam_items"]   = list(self._poam_items)

    def _populate(self):
        """Load self._poam values into all form widgets and tables."""
        def setv(key, val):
            if key in self._vars:
                self._vars[key].set(val)

        setv("title",      self._poam.get("title", ""))
        setv("version",    self._poam.get("version", "1.0"))
        setv("import_ssp", self._poam.get("import_ssp", ""))
        setv("system_id",  self._poam.get("system_id", ""))

        self._observations = list(self._poam.get("observations", []))
        self._risks        = list(self._poam.get("risks", []))
        self._findings     = list(self._poam.get("findings", []))
        self._poam_items   = list(self._poam.get("poam_items", []))

        self._refresh_obs_tree()
        self._refresh_risk_tree()
        self._refresh_finding_tree()
        self._refresh_item_tree()
        self._dirty = False   # Populating from a file is not a user edit

    def _reset(self):
        """Reset the editor to a blank POA&M."""
        self._poam         = empty_poam()
        self._observations = []
        self._risks        = []
        self._findings     = []
        self._poam_items   = []
        self._populate()
        self._dirty = False

    # =========================================================================
    # SAVE / OPEN / NEW
    # =========================================================================

    def _save(self):
        self._collect()

        if not self._poam.get("title"):
            messagebox.showwarning("Required", "POA&M Title is required before saving.")
            return
        if not self._poam.get("poam_items"):
            if not messagebox.askyesno(
                "No POA&M Items",
                "The POA&M has no items yet. Save anyway?",
            ):
                return

        path = filedialog.asksaveasfilename(
            title="Save POA&M as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"poam_{self._poam['title'][:30].replace(' ','_')}.json",
        )
        if not path:
            return

        try:
            doc = build_oscal_poam(self._poam,
                                   oscal_version=self._get_oscal_version(),
                                   save_path=path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self._current_path = path
        self._dirty = False
        name = Path(path).name
        self._status_lbl.config(text=f"Saved: {name}", fg=self._colors["GREEN"])
        self._set_status(f"Saved POA&M: {name}")

    def _open(self, path=None):
        """
        Load a POA&M JSON file.

        Parameters:
            path - If given, load this file directly (used by the Workspace
                   tab). If None, ask the user via a file dialog.
        """
        if path is None:
            path = filedialog.askopenfilename(
                title="Open OSCAL POA&M",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return

        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Invalid JSON", str(exc))
            return

        if "plan-of-action-and-milestones" not in raw:
            messagebox.showerror(
                "Not a POA&M",
                "This file does not appear to be an OSCAL POA&M document.\n"
                "(Missing 'plan-of-action-and-milestones' key.)",
            )
            return

        try:
            self._poam = parse_poam_file(raw)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            return

        self._populate()
        self._current_path = path
        name = Path(path).name
        self._status_lbl.config(
            text=f"Opened: {name}", fg=self._colors["TEXT"]
        )
        self._set_status(f"Opened POA&M: {name}")
        return True

    def _new(self):
        if messagebox.askyesno(
            "New POA&M",
            "Discard the current POA&M and start a new blank one?",
        ):
            self._reset()
            self._status_lbl.config(text="New POA&M", fg=self._colors["SUBTEXT"])
            self._set_status("New POA&M started.")
