"""
ap_tab.py
=========
Defines the APTab class — the Assessment Plan editor tab.

An Assessment Plan is the document that declares the scope and methodology
of a security assessment before it begins. It references the SSP under
assessment, specifies which controls are in scope, and lists the tasks
(milestones and actions) that make up the assessment schedule.

OSCAL Assessment Plan top-level sections implemented here:
  1. Document Metadata   — title, version, dates
  2. SSP Reference       — import-ssp.href (which SSP is being assessed)
  3. Reviewed Controls   — include-all OR a specific list of control IDs
  4. Tasks               — milestones and actions with optional timing
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import (
    new_uuid, now_iso,
    empty_ap, build_oscal_ap, parse_ap_file,
    # DEFAULT_OSCAL_VERSION is the version string used when no toolbar value is
    # available. Centralised in models.py so updating it there updates all tabs. (M1)
    DEFAULT_OSCAL_VERSION,
)

TASK_TYPES    = ["milestone", "action"]
TIMING_TYPES  = ["none", "on-date", "within-date-range", "at-frequency"]


class APTab(tk.Frame):
    """
    Self-contained OSCAL Assessment Plan editor panel.

    Layout:
      TOP  — Toolbar (Save, Open, New buttons + save-status label)
      BODY — Scrollable form with four sections:
               1. Metadata
               2. SSP Reference
               3. Reviewed Controls
               4. Tasks
    """

    def __init__(self, parent, colors, set_status,
                 get_oscal_version=None, get_profile=None):
        """
        Initialise the APTab.

        Parameters:
            parent            - The ttk.Notebook this tab lives inside
            colors            - Shared colour dictionary from app.py
            set_status        - Callback: updates the main window status bar
            get_oscal_version - Optional callback returning the OSCAL version
                                string (e.g. "1.2.2"). Defaults to "1.1.2".
            get_profile       - Optional callback returning the loaded profile
                                dict, used to populate the control ID picker.
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors            = colors
        self._set_status        = set_status
        # Fall back to the constant from models.py instead of a hard-coded
        # "1.1.2" string, so upgrading the target version only needs one edit. (M1)
        self._get_oscal_version = get_oscal_version or (lambda: DEFAULT_OSCAL_VERSION)
        self._get_profile       = get_profile       or (lambda: None)

        self._dirty = False
        # Path of the file this Assessment Plan was last opened from or saved
        # to. Read by the Workspace tab when saving a workspace manifest.
        self._current_path = None
        self._ap    = empty_ap()
        self._tasks: list = []
        self._vars:  dict = {}

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
        flushes current widget values into self._ap first; _populate()
        rebuilds every widget's content from self._ap afterward.
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

        def btn(text, cmd, bg, abg):
            tk.Button(
                tb, text=text, command=cmd,
                bg=bg, fg=C["BUTTON_TEXT"], font=("Helvetica", 11, "bold"),
                relief="flat", padx=12, pady=4, cursor="hand2",
                activebackground=abg, activeforeground=C["BUTTON_TEXT"],
            ).pack(side="left", padx=(12, 0), pady=8)

        btn("💾  Save Plan", self._save, C["GREEN_BG"], "#8cd39a")
        btn("📂  Open Plan", self._open, C["BLUE_BG"],  "#6a9fd8")
        btn("🆕  New Plan",  self._new,  C["BLUE_BG"],  "#6a9fd8")

        self._status_lbl = tk.Label(
            tb, text="Assessment Plan not saved",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="left", padx=16)

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
            nb = self.master
            if hasattr(nb, "select") and nb.select() == str(self):
                self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

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

        # ── Section 1: Metadata ───────────────────────────────────────────────
        section("1 ·  Assessment Plan Metadata")
        field("Plan Title *",  "title",   width=60)
        field("Version *",     "version", width=20, default="1.0")

        # ── Section 2: SSP Reference ──────────────────────────────────────────
        section("2 ·  SSP Reference")
        tk.Label(parent,
                 text="  Link this plan to the SSP it will assess.\n"
                      "  The path is saved as a relative URI-reference.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", **P, pady=(0, 4))

        ssp_v = tk.StringVar()
        self._vars["import_ssp"] = ssp_v
        ssp_row = tk.Frame(parent, bg=C["BG"])
        ssp_row.pack(fill="x", **P, pady=3)
        tk.Label(ssp_row, text="SSP File (href)",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=22, anchor="w",
                 ).pack(side="left")
        tk.Entry(ssp_row, textvariable=ssp_v,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), width=48,
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", ipady=3)
        tk.Button(ssp_row, text="📂 Browse…", command=self._browse_ssp,
                  # Fixed dark text (not theme-flipping TEXT) — on macOS, plain
                  # tk.Button widgets often ignore bg= and always render a
                  # native light-grey face, so light TEXT (correct for dark
                  # mode's intended HEADER_BG fill) becomes unreadable against
                  # that native face. BUTTON_TEXT is safe either way.
                  bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=(6, 0))

        # ── Section 3: Reviewed Controls ──────────────────────────────────────
        section("3 ·  Reviewed Controls")
        tk.Label(parent,
                 text="  Declare which controls are in scope for this assessment.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", **P, pady=(0, 4))

        rc_frame = tk.Frame(parent, bg=C["CARD_BG"],
                            highlightthickness=1,
                            highlightbackground=C["HEADER_BG"])
        rc_frame.pack(fill="x", padx=28, pady=6)

        self._rc_all_var = tk.BooleanVar(value=True)

        rb_all = tk.Radiobutton(
            rc_frame, text="All controls  (include-all)",
            variable=self._rc_all_var, value=True,
            command=self._on_rc_mode_changed,
            bg=C["CARD_BG"], fg=C["TEXT"],
            selectcolor=C["HEADER_BG"],
            font=("Helvetica", 11),
            activebackground=C["CARD_BG"],
        )
        rb_all.pack(anchor="w", padx=12, pady=(8, 2))

        rb_specific = tk.Radiobutton(
            rc_frame, text="Specific control IDs (one per line)",
            variable=self._rc_all_var, value=False,
            command=self._on_rc_mode_changed,
            bg=C["CARD_BG"], fg=C["TEXT"],
            selectcolor=C["HEADER_BG"],
            font=("Helvetica", 11),
            activebackground=C["CARD_BG"],
        )
        rb_specific.pack(anchor="w", padx=12, pady=(2, 4))

        self._rc_text = tk.Text(
            rc_frame,
            bg=C["BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            height=6, wrap="none", padx=8, pady=6,
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
            state="disabled",
        )
        self._rc_text.pack(fill="x", padx=12, pady=(0, 8))

        # "Load from profile" button to auto-populate from the loaded profile
        load_row = tk.Frame(rc_frame, bg=C["CARD_BG"])
        load_row.pack(fill="x", padx=12, pady=(0, 8))
        tk.Button(load_row, text="📋  Load IDs from profile",
                  command=self._load_ids_from_profile,
                  bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Label(load_row,
                 text="  Requires a profile to be loaded in the toolbar.",
                 bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(side="left", padx=8)

        # ── Section 4: Tasks ─────────────────────────────────────────────────
        task_frame = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])

        section("4 ·  Tasks")
        tk.Label(parent,
                 text="  Milestones and actions that make up the assessment schedule.",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", **P, pady=(0, 4))

        task_frame = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        task_frame.pack(fill="x", padx=28, pady=6)

        btn_row = tk.Frame(task_frame, bg=C["CARD_BG"])
        btn_row.pack(fill="x", padx=8, pady=6)
        # fg is fixed BUTTON_TEXT (not theme-flipping TEXT/SUBTEXT) for the
        # same reason as the Browse/Load IDs buttons above — on macOS,
        # tk.Button often ignores bg= and always shows a native light-grey
        # face, so light text meant for a dark HEADER_BG fill becomes
        # unreadable. Fixed dark text is safe regardless of what actually
        # renders.
        for text, cmd, bg, fg in [
            ("＋  Add",    self._add_task,    C["BLUE_BG"],   C["BUTTON_TEXT"]),
            ("✎  Edit",   self._edit_task,   C["HEADER_BG"], C["BUTTON_TEXT"]),
            ("✕  Remove", self._remove_task, C["HEADER_BG"], C["BUTTON_TEXT"]),
        ]:
            tk.Button(btn_row, text=text, command=cmd,
                      bg=bg, fg=fg,
                      font=("Helvetica", 10, "bold" if bg == C["BLUE_BG"] else "normal"),
                      relief="flat", padx=10, pady=3, cursor="hand2",
                      ).pack(side="left", padx=(0, 6))

        self._task_tree = ttk.Treeview(
            task_frame,
            columns=("type", "title", "timing", "description"),
            show="headings", height=6, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("type",        "Type",        90,  False),
            ("title",       "Title",       220, True),
            ("timing",      "Timing",      160, False),
            ("description", "Description", 200, True),
        ]:
            self._task_tree.heading(col, text=heading, anchor="w")
            self._task_tree.column(col, width=w, anchor="w", stretch=stretch)

        tsb = ttk.Scrollbar(task_frame, orient="vertical",
                            command=self._task_tree.yview)
        self._task_tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side="right", fill="y", padx=(0, 8), pady=(0, 8))
        self._task_tree.pack(fill="x", padx=8, pady=(0, 8))

        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # REVIEWED CONTROLS
    # =========================================================================

    def _on_rc_mode_changed(self):
        if self._rc_all_var.get():
            self._rc_text.config(state="disabled", bg=self._colors["HEADER_BG"])
        else:
            self._rc_text.config(state="normal", bg=self._colors["CARD_BG"])

    def _load_ids_from_profile(self):
        """Populate the control IDs text box from the loaded profile."""
        profile = self._get_profile()
        if not profile or not profile.get("ids"):
            messagebox.showinfo(
                "No profile loaded",
                "Load a profile in the toolbar first, then click this button "
                "to populate the control ID list.",
            )
            return
        ids = sorted(profile["ids"])
        self._rc_all_var.set(False)
        self._on_rc_mode_changed()
        self._rc_text.delete("1.0", "end")
        self._rc_text.insert("1.0", "\n".join(ids))
        self._dirty = True

    # =========================================================================
    # TASK CRUD
    # =========================================================================

    def _task_row(self, t):
        ttype = t.get("timing_type", "none")
        if ttype == "on-date":
            timing = f"On: {t.get('timing_date', '')}"
        elif ttype == "within-date-range":
            timing = f"{t.get('timing_start','')} – {t.get('timing_end','')}"
        elif ttype == "at-frequency":
            timing = f"Every: {t.get('timing_period','')}"
        else:
            timing = ""
        return (
            t.get("type", ""),
            t.get("title", ""),
            timing,
            t.get("description", "")[:80],
        )

    def _refresh_task_tree(self):
        self._task_tree.delete(*self._task_tree.get_children())
        for t in self._tasks:
            self._task_tree.insert("", "end", values=self._task_row(t))

    def _task_dialog(self, existing=None):
        C   = self._colors
        ex  = existing or {}
        dlg = self._make_dialog(
            "Edit Task" if existing else "Add Task", width=500
        )

        body = tk.Frame(dlg, bg=C["BG"])
        body.pack(fill="both", expand=True, padx=4, pady=4)
        body.columnconfigure(1, weight=1)

        v_type  = self._dlg_combo(body, "Task Type *", 0, TASK_TYPES,
                                   default=ex.get("type", "milestone"))
        v_title = self._dlg_field(body, "Title *",     1,
                                   default=ex.get("title", ""))

        # Timing
        tk.Label(body, text="Timing", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="w",
                 ).grid(row=2, column=0, sticky="w", padx=12, pady=4)
        v_ttype = tk.StringVar(value=ex.get("timing_type", "none"))
        timing_frame = tk.Frame(body, bg=C["BG"])
        timing_frame.grid(row=2, column=1, sticky="w", padx=(0, 12), pady=4)
        ttk.Combobox(timing_frame, textvariable=v_ttype,
                     values=TIMING_TYPES, state="readonly", width=18,
                     ).pack(side="left")

        v_date  = self._dlg_field(body, "Date (on-date)",        3,
                                   default=ex.get("timing_date", ""))
        v_start = self._dlg_field(body, "Start (date-range)",    4,
                                   default=ex.get("timing_start", ""))
        v_end   = self._dlg_field(body, "End (date-range)",      5,
                                   default=ex.get("timing_end", ""))
        v_period = self._dlg_field(body, "Period (at-frequency)", 6,
                                    default=ex.get("timing_period", ""))

        # Unit Combobox — the OSCAL at-frequency.unit field (H5 fix).
        # OSCAL 1.2.2 requires both 'period' (an integer) and 'unit' (a string
        # like "days") in the at-frequency object. The old code only stored period.
        tk.Label(body, text="Unit (at-frequency)", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), anchor="w",
                 ).grid(row=7, column=0, sticky="w", padx=12, pady=4)
        v_unit = tk.StringVar(value=ex.get("timing_unit", "days"))
        ttk.Combobox(
            body, textvariable=v_unit,
            # These values match the OSCAL at-frequency.unit enum
            values=["seconds", "minutes", "hours", "days", "months", "years"],
            state="readonly", width=12,
        ).grid(row=7, column=1, sticky="w", padx=(0, 12), pady=4)

        t_desc    = self._dlg_text(body, "Description",  9, height=3)
        t_desc.insert("1.0", ex.get("description", ""))
        t_remarks = self._dlg_text(body, "Remarks",     10, height=2)
        t_remarks.insert("1.0", ex.get("remarks", ""))

        result = {}

        def _ok():
            title = v_title.get().strip()
            if not title:
                messagebox.showwarning("Required", "Title is required.", parent=dlg)
                return
            result.update({
                "uuid":          ex.get("uuid", new_uuid()),
                "type":          v_type.get(),
                "title":         title,
                "description":   t_desc.get("1.0", "end-1c").strip(),
                "timing_type":   v_ttype.get(),
                "timing_date":   v_date.get().strip(),
                "timing_start":  v_start.get().strip(),
                "timing_end":    v_end.get().strip(),
                "timing_period": v_period.get().strip(),
                # Save timing_unit so build_oscal_ap() can write the 'unit' field (H5)
                "timing_unit":   v_unit.get(),
                "remarks":       t_remarks.get("1.0", "end-1c").strip(),
            })
            dlg.destroy()

        self._ok_cancel(dlg, _ok)
        self.wait_window(dlg)
        return result or None

    def _add_task(self):
        t = self._task_dialog()
        if t:
            self._tasks.append(t)
            self._refresh_task_tree()
            self._dirty = True

    def _edit_task(self):
        sel = self._task_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a task to edit.")
            return
        idx     = self._task_tree.index(sel[0])
        updated = self._task_dialog(existing=self._tasks[idx])
        if updated:
            updated["uuid"]  = self._tasks[idx]["uuid"]
            self._tasks[idx] = updated
            self._refresh_task_tree()
            self._dirty = True

    def _remove_task(self):
        sel = self._task_tree.selection()
        if not sel:
            messagebox.showinfo("No selection", "Select a task to remove.")
            return
        self._tasks.pop(self._task_tree.index(sel[0]))
        self._refresh_task_tree()
        self._dirty = True

    # =========================================================================
    # DIALOG HELPERS  (identical pattern to POAMTab)
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

    def _browse_ssp(self):
        path = filedialog.askopenfilename(
            title="Select SSP JSON file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._vars["import_ssp"].set(path)
            self._dirty = True

    # =========================================================================
    # COLLECT / POPULATE / RESET
    # =========================================================================

    def _collect(self):
        self._dirty = True
        self._ap["title"]      = self._vars["title"].get().strip()
        self._ap["version"]    = self._vars["version"].get().strip() or "1.0"
        self._ap["import_ssp"] = self._vars["import_ssp"].get().strip()

        self._ap["reviewed_controls_all"] = bool(self._rc_all_var.get())
        if not self._ap["reviewed_controls_all"]:
            raw = self._rc_text.get("1.0", "end-1c")
            self._ap["reviewed_control_ids"] = [
                ln.strip() for ln in raw.splitlines() if ln.strip()
            ]
        else:
            self._ap["reviewed_control_ids"] = []

        self._ap["tasks"] = list(self._tasks)

    def _populate(self):
        def setv(key, val):
            if key in self._vars:
                self._vars[key].set(val)

        setv("title",      self._ap.get("title", ""))
        setv("version",    self._ap.get("version", "1.0"))
        setv("import_ssp", self._ap.get("import_ssp", ""))

        all_ctrl = self._ap.get("reviewed_controls_all", True)
        self._rc_all_var.set(all_ctrl)
        self._on_rc_mode_changed()
        if not all_ctrl:
            ids = self._ap.get("reviewed_control_ids", [])
            self._rc_text.config(state="normal")
            self._rc_text.delete("1.0", "end")
            self._rc_text.insert("1.0", "\n".join(ids))
        else:
            self._rc_text.config(state="disabled")
            self._rc_text.delete("1.0", "end")

        self._tasks = list(self._ap.get("tasks", []))
        self._refresh_task_tree()
        self._dirty = False

    def _reset(self):
        self._ap    = empty_ap()
        self._tasks = []
        self._populate()

    # =========================================================================
    # SAVE / OPEN / NEW
    # =========================================================================

    def _save(self):
        self._collect()
        if not self._ap.get("title"):
            messagebox.showwarning("Required",
                                   "Plan Title is required before saving.")
            return

        path = filedialog.asksaveasfilename(
            title="Save Assessment Plan as JSON",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"ap_{self._ap['title'][:30].replace(' ','_')}.json",
        )
        if not path:
            return

        try:
            doc = build_oscal_ap(self._ap,
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
        self._set_status(f"Saved Assessment Plan: {name}")

    def _open(self, path=None):
        """
        Load an Assessment Plan JSON file.

        Parameters:
            path - If given, load this file directly (used by the Workspace
                   tab). If None, ask the user via a file dialog.
        """
        if path is None:
            path = filedialog.askopenfilename(
                title="Open OSCAL Assessment Plan",
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

        if "assessment-plan" not in raw:
            messagebox.showerror(
                "Not an Assessment Plan",
                "This file does not appear to be an OSCAL Assessment Plan.\n"
                "(Missing 'assessment-plan' key.)",
            )
            return

        try:
            self._ap = parse_ap_file(raw)
        except Exception as exc:
            messagebox.showerror("Parse error", str(exc))
            return

        self._populate()
        self._current_path = path
        name = Path(path).name
        self._status_lbl.config(text=f"Opened: {name}",
                                fg=self._colors["TEXT"])
        self._set_status(f"Opened Assessment Plan: {name}")
        return True

    def _new(self):
        if messagebox.askyesno(
            "New Assessment Plan",
            "Discard the current plan and start a new blank one?",
        ):
            self._reset()
            self._status_lbl.config(text="New Assessment Plan",
                                    fg=self._colors["SUBTEXT"])
            self._set_status("New Assessment Plan started.")
