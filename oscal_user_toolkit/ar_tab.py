"""
ar_tab.py
=========
Defines the ARTab class — the Assessment Results editor tab.

An Assessment Results document records what an assessor actually found
during a security assessment. It references the Assessment Plan that
scoped the work and contains:
  - Observations  — raw evidence (what was examined/tested/interviewed)
  - Risks         — risks identified during the assessment
  - Findings      — formal per-control verdicts (satisfied / not-satisfied)
  - Assessment Log — timestamped audit trail of assessment activities

Findings that are not-satisfied can be exported to the POA&M editor
with a single button click to begin the remediation tracking workflow.

OSCAL Assessment Results sections implemented here:
  1. Document Metadata     — title, version
  2. Assessment Plan Ref   — import-ap.href (which AP scoped this assessment)
  3. Result Header         — title, description, start/end dates
  4. Observations          — evidence records (EXAMINE / INTERVIEW / TEST)
  5. Risks                 — risks found during the assessment
  6. Findings              — per-control verdicts with status and impl-status
  7. Assessment Log        — Phase 3 — audit trail of activities
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import (
    new_uuid, now_iso,
    empty_ar, build_oscal_ar, parse_ar_file,
    empty_poam, build_oscal_poam,
    # Import shared enum constants from models.py instead of defining duplicates
    # here. This ensures AR and POA&M always show the same option lists. (L1 fix)
    DEFAULT_OSCAL_VERSION,
    OBSERVATION_METHODS, OBSERVATION_TYPES,
    RISK_STATUSES, REMEDIATION_LIFECYCLES,
    FINDING_STATUS_STATES, FINDING_STATUS_REASONS,
)
from .tab_utils import is_tab_active

# IMPL_STATUS_VALUES is specific to AR (not shared with POA&M) so it stays here.
IMPL_STATUS_VALUES = [
    "implemented", "partial", "planned", "alternative", "not-applicable",
]


class ARTab(tk.Frame):
    """
    Self-contained OSCAL Assessment Results editor panel.

    Layout:
      TOP  — Toolbar (Save, Open, New, Generate POA&M buttons)
      BODY — Scrollable form with seven sections:
               1. Metadata
               2. Assessment Plan Reference
               3. Result Header
               4. Observations
               5. Risks
               6. Findings
               7. Assessment Log
    """

    def __init__(self, parent, colors, set_status,
                 get_oscal_version=None,
                 get_poam_tab=None):
        """
        Initialise the ARTab.

        Parameters:
            parent            - The ttk.Notebook this tab lives inside
            colors            - Shared colour dictionary from app.py
            set_status        - Callback: updates the main window status bar
            get_oscal_version - Optional callback returning the OSCAL version
                                string (e.g. "1.2.2").
            get_poam_tab      - Optional callback returning the POAMTab instance
                                so the "Generate POA&M" button can push findings
                                directly into the POA&M editor.
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors            = colors
        self._set_status        = set_status
        # Use the shared DEFAULT_OSCAL_VERSION constant from models.py (M1 fix)
        self._get_oscal_version = get_oscal_version or (lambda: DEFAULT_OSCAL_VERSION)
        self._get_poam_tab      = get_poam_tab      or (lambda: None)

        self._dirty        = False
        # Path of the file this Assessment Results doc was last opened from
        # or saved to. Read by the Workspace tab when saving a manifest.
        self._current_path = None
        self._ar           = empty_ar()
        self._observations: list = []
        self._risks:        list = []
        self._findings:     list = []
        self._log_entries:  list = []
        self._vars:         dict = {}

        self._build()

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        self._build_toolbar()
        self._build_canvas()

    def theme_refresh(self):
        """
        Rebuild this tab's widgets after the colour theme changes, without
        losing any in-progress edits or loaded document data. _collect()
        flushes current widget values into self._ar first; _populate()
        rebuilds every widget's content from self._ar afterward.
        """
        self._collect()
        self.configure(bg=self._colors["BG"])   # This tab's own Frame background
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()
        self._populate()

    def _build_toolbar(self):
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        def btn(text, cmd, bg, abg, fg=None):
            tk.Button(
                tb, text=text, command=cmd,
                bg=bg, fg=fg or C["BUTTON_TEXT"],
                font=("Helvetica", 11, "bold"),
                relief="flat", padx=12, pady=4, cursor="hand2",
                activebackground=abg, activeforeground=fg or C["BUTTON_TEXT"],
            ).pack(side="left", padx=(12, 0), pady=8)

        btn("💾  Save Results",  self._save,              C["GREEN_BG"], "#8cd39a")
        btn("📂  Open Results",  self._open,              C["BLUE_BG"],  "#6a9fd8")
        btn("🆕  New Results",   self._new,               C["BLUE_BG"],  "#6a9fd8")

        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=8, pady=6
        )

        tk.Button(
            tb,
            text="📋  Generate POA&M from Findings",
            command=self._generate_poam,
            bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"],
            font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=4, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=(0, 0), pady=8)
        tk.Label(
            tb,
            text="  Creates POA&M items for every not-satisfied finding",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=(6, 0))

        self._status_lbl = tk.Label(
            tb, text="Assessment Results not saved",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=16)

    def _build_canvas(self):
        C      = self._colors
        canvas = tk.Canvas(self, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        form = tk.Frame(canvas, bg=C["BG"])
        win  = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))
        self._canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._build_form(form)

    def _on_mousewheel(self, event):
        try:
            if is_tab_active(self):
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except tk.TclError:
            pass   # Canvas destroyed/not ready — see SECURE_CODING.md #2

    # =========================================================================
    # FORM
    # =========================================================================

    def _build_form(self, parent):
        C = self._colors
        P = dict(padx=28)

        def section(title):
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(20, 4))
            tk.Label(hdr, text=title,
                     bg=C["HEADER_BG"], fg=C["ACCENT"],
                     font=("Helvetica", 12, "bold"), anchor="w",
                     ).pack(side="left", padx=12, pady=6)

        def field(label, key, width=50, default=""):
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
                          height=5):
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
            for text, cmd, bg in [
                ("＋  Add",    add_cmd,    C["BLUE_BG"]),
                ("✎  Edit",   edit_cmd,   C["HEADER_BG"]),
                ("✕  Remove", remove_cmd, C["HEADER_BG"]),
            ]:
                tk.Button(btn_row, text=text, command=cmd,
                          # Fixed BUTTON_TEXT regardless of bg — on macOS,
                          # tk.Button often ignores bg= and always shows a
                          # native light-grey face, so theme-flipping TEXT
                          # (light in dark mode) becomes unreadable against it.
                          bg=bg, fg=C["BUTTON_TEXT"],
                          font=("Helvetica", 10,
                                "bold" if bg == C["BLUE_BG"] else "normal"),
                          relief="flat", padx=10, pady=3, cursor="hand2",
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
        section("1 ·  Assessment Results Metadata")
        field("Results Title *", "title",   width=60)
        field("Version *",       "version", width=20, default="1.0")

        # ── Section 2: Assessment Plan Reference ──────────────────────────────
        section("2 ·  Assessment Plan Reference")
        tk.Label(parent,
                 text="  Link these results to the Assessment Plan that scoped the work.\n"
                      "  The path is saved as a relative URI-reference.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", **P, pady=(0, 4))

        ap_v = tk.StringVar()
        self._vars["import_ap"] = ap_v
        ap_row = tk.Frame(parent, bg=C["BG"])
        ap_row.pack(fill="x", **P, pady=3)
        tk.Label(ap_row, text="Assessment Plan (href)",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=22, anchor="w",
                 ).pack(side="left")
        tk.Entry(ap_row, textvariable=ap_v,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), width=48,
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", ipady=3)
        tk.Button(ap_row, text="📂  Browse…", command=self._browse_ap,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=(6, 0))

        # ── Section 3: Result Header ──────────────────────────────────────────
        section("3 ·  Result")
        field("Result Title *",       "result_title",       width=60)
        field("Result Description",   "result_description", width=60)
        field("Assessment Start *",   "result_start",       width=20,
              default=now_iso()[:10])
        field("Assessment End",       "result_end",         width=20)
        tk.Label(parent,
                 text="  Dates in YYYY-MM-DD format.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", **P)

        # ── Section 4: Observations ───────────────────────────────────────────
        self._obs_tree = table_section(
            title="4 ·  Observations",
            hint="Evidence records collected during the assessment (EXAMINE / INTERVIEW / TEST).",
            columns=[
                ("title",     "Title",     200, True),
                ("methods",   "Methods",   130, False),
                ("types",     "Types",     150, False),
                ("collected", "Collected", 110, False),
                ("expires",   "Expires",   100, False),
            ],
            add_cmd=self._add_obs,
            edit_cmd=self._edit_obs,
            remove_cmd=self._remove_obs,
        )

        # ── Section 5: Risks ──────────────────────────────────────────────────
        self._risk_tree = table_section(
            title="5 ·  Risks",
            hint="Risks identified during the assessment with lifecycle status.",
            columns=[
                ("title",    "Title",        220, True),
                ("status",   "Status",       130, False),
                ("deadline", "Deadline",     100, False),
                ("rems",     "Remediations",  80, False),
            ],
            add_cmd=self._add_risk,
            edit_cmd=self._edit_risk,
            remove_cmd=self._remove_risk,
        )

        # ── Section 6: Findings ───────────────────────────────────────────────
        self._finding_tree = table_section(
            title="6 ·  Findings",
            hint="Formal per-control verdicts (satisfied / not-satisfied). "
                 "Use 'Generate POA&M' to push not-satisfied findings to the POA&M editor.",
            columns=[
                ("title",       "Title",         200, True),
                ("target_id",   "Control ID",    130, False),
                ("state",       "Status",        110, False),
                ("reason",      "Reason",         80, False),
                ("impl_status", "Impl. Status",  120, False),
                ("obs",         "Observations",   80, False),
            ],
            add_cmd=self._add_finding,
            edit_cmd=self._edit_finding,
            remove_cmd=self._remove_finding,
        )

        # ── Section 7: Assessment Log ─────────────────────────────────────────
        self._log_tree = table_section(
            title="7 ·  Assessment Log",
            hint="Chronological record of assessment activities (who did what, when).",
            columns=[
                ("start",       "Start",       110, False),
                ("end",         "End",         110, False),
                ("description", "Description", 300, True),
            ],
            add_cmd=self._add_log_entry,
            edit_cmd=self._edit_log_entry,
            remove_cmd=self._remove_log_entry,
            height=4,
        )

        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # OBSERVATION CRUD  (identical logic to POAMTab)
    # =========================================================================

    def _obs_row(self, o):
        return (
            o.get("title", "") or o.get("description", "")[:60],
            ", ".join(o.get("methods", [])),
            ", ".join(o.get("types", [])),
            o.get("collected", "")[:10],
            o.get("expires", "")[:10],
        )

    def _refresh_obs_tree(self):
        self._obs_tree.delete(*self._obs_tree.get_children())
        for o in self._observations:
            self._obs_tree.insert("", "end", values=self._obs_row(o))

    def _obs_dialog(self, existing=None):
        C   = self._colors
        ex  = existing or {}
        dlg = self._make_dialog(
            "Edit Observation" if existing else "Add Observation", width=560
        )

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title     = self._dlg_field(body, "Title",       0,
                                       default=ex.get("title", ""))
        default_col = ex.get("collected", "") if existing else now_iso()[:10]
        v_collected = self._dlg_field(body, "Collected *", 1,
                                       default=default_col)
        v_expires   = self._dlg_field(body, "Expires",     2,
                                       default=ex.get("expires", ""))

        tk.Label(body, text="Methods *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=3, column=0, sticky="nw", padx=12, pady=4)
        mf = tk.Frame(body, bg=C["BG"])
        mf.grid(row=3, column=1, sticky="w", padx=(0, 12), pady=4)
        meth_lb = tk.Listbox(mf, selectmode="multiple",
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             font=("Helvetica", 10), height=4, width=20,
                             relief="flat", exportselection=False,
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        for m in OBSERVATION_METHODS:
            meth_lb.insert("end", m)
        for i, m in enumerate(OBSERVATION_METHODS):
            if m in ex.get("methods", []):
                meth_lb.selection_set(i)
        meth_lb.pack(side="left")

        tk.Label(body, text="Types", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=4, column=0, sticky="nw", padx=12, pady=4)
        tf2 = tk.Frame(body, bg=C["BG"])
        tf2.grid(row=4, column=1, sticky="w", padx=(0, 12), pady=4)
        type_lb = tk.Listbox(tf2, selectmode="multiple",
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             font=("Helvetica", 10), height=6, width=30,
                             relief="flat", exportselection=False,
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        for t in OBSERVATION_TYPES:
            type_lb.insert("end", t)
        for i, t in enumerate(OBSERVATION_TYPES):
            if t in ex.get("types", []):
                type_lb.selection_set(i)
        type_lb.pack(side="left")

        t_desc    = self._dlg_text(body, "Description *", 5, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        # Relevant evidence sub-table
        tk.Label(body, text="Relevant Evidence", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=6, column=0, sticky="nw", padx=12, pady=4)
        ev_frame = tk.Frame(body, bg=C["CARD_BG"],
                            highlightthickness=1,
                            highlightbackground=C["HEADER_BG"])
        ev_frame.grid(row=6, column=1, sticky="ew", padx=(0, 12), pady=4)
        ev_btn_row = tk.Frame(ev_frame, bg=C["CARD_BG"])
        ev_btn_row.pack(fill="x", padx=6, pady=4)

        ev_list: list = list(ex.get("relevant_evidence", []))
        ev_tree = ttk.Treeview(ev_frame, columns=("href", "desc"),
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
            v_h = self._dlg_field(f2, "Href / Link",  0, width=40)
            v_d = self._dlg_field(f2, "Description",  1, width=40)
            def _ok2():
                ev_list.append({"href": v_h.get().strip(),
                                "description": v_d.get().strip()})
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

        t_remarks = self._dlg_text(body, "Remarks", 7, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            desc = t_desc.get("1.0", "end-1c").strip()
            if not desc:
                messagebox.showwarning("Required", "Description is required.",
                                       parent=dlg)
                return
            methods = [OBSERVATION_METHODS[i] for i in meth_lb.curselection()]
            if not methods:
                messagebox.showwarning("Required",
                                       "At least one Method is required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":             ex.get("uuid", new_uuid()),
                "title":            v_title.get().strip(),
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

    def _add_obs(self):
        o = self._obs_dialog()
        if o:
            self._observations.append(o)
            self._refresh_obs_tree()
            self._dirty = True

    def _edit_obs(self):
        sel = self._obs_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an observation to edit.")
            return
        idx = self._obs_tree.index(sel[0])
        updated = self._obs_dialog(existing=self._observations[idx])
        if updated:
            updated["uuid"] = self._observations[idx]["uuid"]
            self._observations[idx] = updated
            self._refresh_obs_tree()
            self._dirty = True

    def _remove_obs(self):
        sel = self._obs_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select an observation to remove.")
            return
        self._observations.pop(self._obs_tree.index(sel[0]))
        self._refresh_obs_tree()
        self._dirty = True

    # =========================================================================
    # RISK CRUD  (same pattern as POAMTab)
    # =========================================================================

    def _risk_row(self, r):
        return (
            r.get("title", ""),
            r.get("status", "open"),
            r.get("deadline", "")[:10],
            str(len(r.get("remediations", []))) or "",
        )

    def _refresh_risk_tree(self):
        self._risk_tree.delete(*self._risk_tree.get_children())
        for r in self._risks:
            self._risk_tree.insert("", "end", values=self._risk_row(r))

    def _risk_dialog(self, existing=None):
        C   = self._colors
        ex  = existing or {}
        dlg = self._make_dialog(
            "Edit Risk" if existing else "Add Risk", width=580
        )

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title    = self._dlg_field(body, "Title *",           0,
                                      default=ex.get("title", ""))
        v_status   = self._dlg_combo(body, "Status *",          1,
                                      RISK_STATUSES,
                                      default=ex.get("status", "open"))
        v_deadline = self._dlg_field(body, "Deadline",          2,
                                      default=ex.get("deadline", ""))
        t_desc     = self._dlg_text(body,  "Description *",     3, height=3)
        t_desc.insert("1.0", ex.get("description", ""))
        t_stmt     = self._dlg_text(body,  "Impact Statement *", 4, height=3)
        t_stmt.insert("1.0", ex.get("statement", ""))

        # Remediations sub-table
        tk.Label(body, text="Remediations", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=5, column=0, sticky="nw", padx=12, pady=4)
        rem_frame = tk.Frame(body, bg=C["CARD_BG"],
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        rem_frame.grid(row=5, column=1, sticky="ew", padx=(0, 12), pady=4)
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
                    rem.get("lifecycle", ""),
                    rem.get("title", ""),
                    rem.get("description", "")[:60],
                ))

        def _add_rem():
            d2 = self._make_dialog("Add Remediation", width=440)
            f2 = tk.Frame(d2, bg=C["BG"])
            f2.pack(fill="both", expand=True, padx=4, pady=4)
            f2.columnconfigure(1, weight=1)
            v_rlc    = self._dlg_combo(f2, "Lifecycle *",   0,
                                       REMEDIATION_LIFECYCLES, "recommendation")
            v_rtitle = self._dlg_field(f2, "Title *",       1, width=38)
            t_rdesc  = self._dlg_text(f2,  "Description *", 2, height=3)
            t_rrem   = self._dlg_text(f2,  "Remarks",       3, height=2)
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

        t_remarks = self._dlg_text(body, "Remarks", 6, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            stmt  = t_stmt.get("1.0", "end-1c").strip()
            if not title or not desc or not stmt:
                messagebox.showwarning(
                    "Required",
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
        return (
            f.get("title", ""),
            f.get("target_id", ""),
            f.get("status_state", ""),
            f.get("status_reason", ""),
            f.get("impl_status", ""),
            str(len(f.get("related_obs_uuids", []))) or "",
        )

    def _refresh_finding_tree(self):
        self._finding_tree.delete(*self._finding_tree.get_children())
        for f in self._findings:
            self._finding_tree.insert("", "end", values=self._finding_row(f))

    def _finding_dialog(self, existing=None):
        C   = self._colors
        ex  = existing or {}
        dlg = self._make_dialog(
            "Edit Finding" if existing else "Add Finding", width=540
        )

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_title  = self._dlg_field(body, "Title *",              0,
                                    default=ex.get("title", ""))
        v_tid    = self._dlg_field(body, "Control ID *",         1,
                                    default=ex.get("target_id", ""))
        v_state  = self._dlg_combo(body, "Status State *",       2,
                                    FINDING_STATUS_STATES,
                                    default=ex.get("status_state", "not-satisfied"))
        v_reason = self._dlg_combo(body, "Status Reason",        3,
                                    FINDING_STATUS_REASONS,
                                    default=ex.get("status_reason", ""))
        v_impl   = self._dlg_combo(body, "Implementation Status", 4,
                                    IMPL_STATUS_VALUES,
                                    default=ex.get("impl_status", "implemented"))

        t_desc = self._dlg_text(body, "Description *", 5, height=3)
        t_desc.insert("1.0", ex.get("description", ""))

        # Related observations picker
        def _obs_label(o):
            t = o.get("title", "") or o.get("description", "")[:40]
            return f"{o['uuid'][:8]}…  {t}"

        tk.Label(body, text="Related Observations", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=6, column=0, sticky="nw", padx=12, pady=4)
        obs_lb = tk.Listbox(body, selectmode="multiple",
                            bg=C["CARD_BG"], fg=C["TEXT"],
                            font=("Helvetica", 9),
                            height=min(len(self._observations) + 1, 5),
                            width=55, relief="flat", exportselection=False,
                            highlightthickness=1,
                            highlightbackground=C["HEADER_BG"])
        for o in self._observations:
            obs_lb.insert("end", _obs_label(o))
        selected_obs = ex.get("related_obs_uuids", [])
        for i, o in enumerate(self._observations):
            if o["uuid"] in selected_obs:
                obs_lb.selection_set(i)
        obs_lb.grid(row=6, column=1, sticky="ew", padx=(0, 12), pady=4)

        # Related risks picker
        def _risk_label(r):
            return f"{r['uuid'][:8]}…  {r.get('title', '')}"

        tk.Label(body, text="Related Risks", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=7, column=0, sticky="nw", padx=12, pady=4)
        risk_lb = tk.Listbox(body, selectmode="multiple",
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             font=("Helvetica", 9),
                             height=min(len(self._risks) + 1, 4),
                             width=55, relief="flat", exportselection=False,
                             highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])
        for r in self._risks:
            risk_lb.insert("end", _risk_label(r))
        selected_risks = ex.get("related_risk_uuids", [])
        for i, r in enumerate(self._risks):
            if r["uuid"] in selected_risks:
                risk_lb.selection_set(i)
        risk_lb.grid(row=7, column=1, sticky="ew", padx=(0, 12), pady=4)

        t_remarks = self._dlg_text(body, "Remarks", 8, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            tid   = v_tid.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            if not title or not tid or not desc:
                messagebox.showwarning(
                    "Required",
                    "Title, Control ID, and Description are required.",
                    parent=dlg)
                return
            result.update({
                "uuid":          ex.get("uuid", new_uuid()),
                "title":         title,
                "description":   desc,
                "target_type":   "statement-id",
                "target_id":     tid,
                "status_state":  v_state.get(),
                "status_reason": v_reason.get(),
                "impl_status":   v_impl.get(),
                "related_obs_uuids": [
                    self._observations[i]["uuid"]
                    for i in obs_lb.curselection()
                ],
                "related_risk_uuids": [
                    self._risks[i]["uuid"]
                    for i in risk_lb.curselection()
                ],
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
    # ASSESSMENT LOG CRUD  (Phase 3)
    # =========================================================================

    def _log_row(self, le):
        return (
            le.get("start", ""),
            le.get("end", ""),
            le.get("description", "")[:100],
        )

    def _refresh_log_tree(self):
        self._log_tree.delete(*self._log_tree.get_children())
        for le in self._log_entries:
            self._log_tree.insert("", "end", values=self._log_row(le))

    def _log_dialog(self, existing=None):
        C   = self._colors
        ex  = existing or {}
        dlg = self._make_dialog(
            "Edit Log Entry" if existing else "Add Log Entry", width=500
        )

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        default_start = ex.get("start", "") if existing else now_iso()[:10]
        v_start   = self._dlg_field(body, "Start *", 0, default=default_start)
        v_end     = self._dlg_field(body, "End",     1, default=ex.get("end", ""))
        t_desc    = self._dlg_text(body, "Description *", 2, height=3)
        t_desc.insert("1.0", ex.get("description", ""))
        t_remarks = self._dlg_text(body, "Remarks", 3, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        tk.Label(body,
                 text="  Dates in YYYY-MM-DD format.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 8, "italic"),
                 ).grid(row=4, column=1, sticky="w", padx=(0, 12))

        result = {}

        def _ok():
            start = v_start.get().strip()
            desc  = t_desc.get("1.0", "end-1c").strip()
            if not start or not desc:
                messagebox.showwarning("Required",
                                       "Start and Description are required.",
                                       parent=dlg)
                return
            result.update({
                "uuid":        ex.get("uuid", new_uuid()),
                "start":       start,
                "end":         v_end.get().strip(),
                "description": desc,
                "remarks":     t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_log_entry(self):
        le = self._log_dialog()
        if le:
            self._log_entries.append(le)
            self._refresh_log_tree()
            self._dirty = True

    def _edit_log_entry(self):
        sel = self._log_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a log entry to edit.")
            return
        idx = self._log_tree.index(sel[0])
        updated = self._log_dialog(existing=self._log_entries[idx])
        if updated:
            updated["uuid"] = self._log_entries[idx]["uuid"]
            self._log_entries[idx] = updated
            self._refresh_log_tree()
            self._dirty = True

    def _remove_log_entry(self):
        sel = self._log_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a log entry to remove.")
            return
        self._log_entries.pop(self._log_tree.index(sel[0]))
        self._refresh_log_tree()
        self._dirty = True

    # =========================================================================
    # GENERATE POA&M  (Phase 3 cross-document linkage)
    # =========================================================================

    def _generate_poam(self):
        """
        Push every not-satisfied finding as a new POA&M item into the POA&M tab.

        Each finding becomes:
          - A POA&M observation (if it has related observations)
          - A POA&M item with title, description, and links to those observations

        Findings that are already satisfied are skipped.
        """
        not_satisfied = [
            f for f in self._findings
            if f.get("status_state") == "not-satisfied"
        ]
        if not not_satisfied:
            messagebox.showinfo(
                "Nothing to export",
                "There are no 'not-satisfied' findings to export.\n\n"
                "All findings have status 'satisfied'.",
            )
            return

        poam_tab = self._get_poam_tab()
        if poam_tab is None:
            messagebox.showerror(
                "POA&M tab not available",
                "Could not reach the POA&M Editor tab. "
                "Please restart the application.",
            )
            return

        # Confirm before mutating the POA&M tab
        if not messagebox.askyesno(
            "Generate POA&M entries",
            f"This will add {len(not_satisfied)} POA&M item(s) for the "
            f"following not-satisfied findings:\n\n"
            + "\n".join(f"  • {f.get('title') or f.get('target_id','')}"
                        for f in not_satisfied[:10])
            + ("\n  …" if len(not_satisfied) > 10 else "")
            + "\n\nProceed?",
        ):
            return

        # Build UUID lookup maps for observations and risks in this AR result.
        # The POA&M item will reference these by UUID, so the referenced objects
        # must also exist in the POA&M — OSCAL requires referential integrity,
        # meaning you cannot have a related-observation UUID that points to nothing. (M4)
        ar_obs_by_uuid  = {o["uuid"]: o for o in self._observations}
        ar_risk_by_uuid = {r["uuid"]: r for r in self._risks}

        added_obs_uuids:  set = set()
        added_risk_uuids: set = set()

        for f in not_satisfied:
            # ── Copy related observations that aren't already in the POA&M ──
            new_obs_uuids = []
            for obs_uuid in f.get("related_obs_uuids", []):
                if obs_uuid in ar_obs_by_uuid and obs_uuid not in added_obs_uuids:
                    poam_tab._observations.append(
                        dict(ar_obs_by_uuid[obs_uuid])
                    )
                    added_obs_uuids.add(obs_uuid)
                if obs_uuid in ar_obs_by_uuid:
                    new_obs_uuids.append(obs_uuid)

            # ── Copy related risks that aren't already in the POA&M (M4 fix) ──
            # Without copying risks, the POA&M related-risks[] UUIDs would
            # point to objects that do not exist in the document — invalid OSCAL.
            new_risk_uuids = []
            for risk_uuid in f.get("related_risk_uuids", []):
                if risk_uuid in ar_risk_by_uuid and risk_uuid not in added_risk_uuids:
                    # Copy the AR risk into the POA&M risks list.
                    # We keep all fields; POA&M risks use the same internal format.
                    poam_tab._risks.append(dict(ar_risk_by_uuid[risk_uuid]))
                    added_risk_uuids.add(risk_uuid)
                if risk_uuid in ar_risk_by_uuid:
                    new_risk_uuids.append(risk_uuid)

            # Create the POA&M item
            ctrl_id = f.get("target_id", "")
            title   = f.get("title") or f"Not-satisfied: {ctrl_id}"
            poam_tab._poam_items.append({
                "uuid":        new_uuid(),
                "title":       title,
                "description": (
                    f.get("description", "")
                    or f"Control {ctrl_id} was assessed as not-satisfied."
                ),
                "related_observation_uuids": new_obs_uuids,
                # Link to the copied risks so the POA&M references are valid (M4)
                "related_risk_uuids":        new_risk_uuids,
                "related_finding_uuids":     [],
                "remarks":                   f.get("remarks", ""),
            })

        # Refresh the POA&M tab's tables
        if added_obs_uuids:
            poam_tab._refresh_obs_tree()
        if added_risk_uuids:
            # Refresh the risks tree if POA&M tab has that method
            if hasattr(poam_tab, "_refresh_risk_tree"):
                poam_tab._refresh_risk_tree()
        poam_tab._refresh_item_tree()
        poam_tab._dirty = True

        messagebox.showinfo(
            "POA&M updated",
            f"Added {len(not_satisfied)} POA&M item(s), "
            f"{len(added_obs_uuids)} observation(s), and "
            f"{len(added_risk_uuids)} risk(s) to the POA&M Editor.\n\n"
            "Switch to the POA&M Editor tab to review and save.",
        )

    # =========================================================================
    # DIALOG HELPERS
    # =========================================================================

    def _make_dialog(self, title, width=480):
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.transient(self)
        dlg.grab_set()
        dlg.minsize(width, 10)
        return dlg

    def _dlg_field(self, parent, label, row_idx, width=36, default=""):
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
        C = self._colors
        tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="nw",
                 ).grid(row=row_idx, column=0, sticky="nw", padx=12, pady=4)
        t = tk.Text(parent,
                    bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                    relief="flat", font=("Helvetica", 10), height=height,
                    wrap="word", padx=6, pady=4,
                    highlightthickness=1, highlightbackground=C["HEADER_BG"])
        t.grid(row=row_idx, column=1, sticky="ew", padx=(0, 12), pady=4)
        return t

    def _ok_cancel(self, dlg, ok_cmd):
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
    # FILE BROWSE
    # =========================================================================

    def _browse_ap(self):
        path = filedialog.askopenfilename(
            title="Select Assessment Plan JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._vars["import_ap"].set(path)
            self._dirty = True

    # =========================================================================
    # COLLECT / POPULATE / RESET
    # =========================================================================

    def _collect(self):
        self._dirty = True
        self._ar["title"]              = self._vars["title"].get().strip()
        self._ar["version"]            = self._vars["version"].get().strip() or "1.0"
        self._ar["import_ap"]          = self._vars["import_ap"].get().strip()
        self._ar["result_title"]       = self._vars["result_title"].get().strip()
        self._ar["result_description"] = self._vars["result_description"].get().strip()
        self._ar["result_start"]       = self._vars["result_start"].get().strip()
        self._ar["result_end"]         = self._vars["result_end"].get().strip()
        self._ar["observations"]       = list(self._observations)
        self._ar["risks"]              = list(self._risks)
        self._ar["findings"]           = list(self._findings)
        self._ar["assessment_log"]     = list(self._log_entries)

    def _populate(self):
        def setv(key, val):
            if key in self._vars:
                self._vars[key].set(val)

        setv("title",              self._ar.get("title", ""))
        setv("version",            self._ar.get("version", "1.0"))
        setv("import_ap",          self._ar.get("import_ap", ""))
        setv("result_title",       self._ar.get("result_title", ""))
        setv("result_description", self._ar.get("result_description", ""))
        setv("result_start",       self._ar.get("result_start", ""))
        setv("result_end",         self._ar.get("result_end", ""))

        self._observations = list(self._ar.get("observations", []))
        self._risks        = list(self._ar.get("risks", []))
        self._findings     = list(self._ar.get("findings", []))
        self._log_entries  = list(self._ar.get("assessment_log", []))

        self._refresh_obs_tree()
        self._refresh_risk_tree()
        self._refresh_finding_tree()
        self._refresh_log_tree()
        self._dirty = False

    def _reset(self):
        self._ar           = empty_ar()
        self._observations = []
        self._risks        = []
        self._findings     = []
        self._log_entries  = []
        self._populate()

    # =========================================================================
    # SAVE / OPEN / NEW
    # =========================================================================

    def _save(self):
        self._collect()
        if not self._ar.get("title"):
            messagebox.showwarning("Required",
                                   "Results Title is required before saving.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Assessment Results as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"ar_{self._ar['title'][:30].replace(' ','_')}.json",
        )
        if not path:
            return

        try:
            doc = build_oscal_ar(self._ar,
                                 oscal_version=self._get_oscal_version(),
                                 save_path=path)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return

        self._current_path = path
        self._dirty = False
        name = Path(path).name
        self._status_lbl.config(text=f"Saved: {name}",
                                fg=self._colors["GREEN"])
        self._set_status(f"Saved Assessment Results: {name}")

    def _open(self, path=None):
        """
        Load an Assessment Results JSON file.

        Parameters:
            path - If given, load this file directly (used by the Workspace
                   tab). If None, ask the user via a file dialog.
        """
        if path is None:
            path = filedialog.askopenfilename(
                title="Open OSCAL Assessment Results",
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
                "This file does not appear to be an OSCAL Assessment Results "
                "document.\n(Missing 'assessment-results' key.)",
            )
            return

        try:
            self._ar = parse_ar_file(raw)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            return

        self._populate()
        self._current_path = path
        name = Path(path).name
        self._status_lbl.config(text=f"Opened: {name}",
                                fg=self._colors["TEXT"])
        self._set_status(f"Opened Assessment Results: {name}")
        return True

    def _new(self):
        if messagebox.askyesno(
            "New Assessment Results",
            "Discard the current results and start a new blank document?",
        ):
            self._reset()
            self._status_lbl.config(text="New Assessment Results",
                                    fg=self._colors["SUBTEXT"])
            self._set_status("New Assessment Results started.")
