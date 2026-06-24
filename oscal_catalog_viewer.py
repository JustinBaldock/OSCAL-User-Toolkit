"""
OSCAL Catalog Viewer + SSP Editor
Requires only Python standard library (tkinter + json).
"""

import json
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timezone
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_prop(props, name, default="—"):
    for p in props:
        if p.get("name") == name:
            return p.get("value", default)
    return default

def get_all_props(props, name):
    return [p.get("value", "") for p in props if p.get("name") == name]

def get_statement(parts):
    for part in parts:
        if part.get("name") == "statement":
            return part.get("prose", "").strip()
    return ""

def collect_controls(obj, parent_titles=None):
    if parent_titles is None:
        parent_titles = []
    result = []
    title = obj.get("title", "")
    path = parent_titles + ([title] if title else [])
    for ctrl in obj.get("controls", []):
        props = ctrl.get("props", [])
        ctrl_id = ctrl.get("id", "")
        label = get_prop(props, "label", default=None) or ctrl_id
        result.append({
            "id":             ctrl_id,
            "label":          label,
            "class":          ctrl.get("class", ""),
            "title":          ctrl.get("title", ""),
            "statement":      get_statement(ctrl.get("parts", [])),
            "applicability":  get_all_props(props, "applicability"),
            "revision":       get_prop(props, "revision"),
            "updated":        get_prop(props, "updated"),
            "essential_eight": get_prop(props, "essential-eight-applicability"),
            "path":           " › ".join(path),
        })
    for grp in obj.get("groups", []):
        result.extend(collect_controls(grp, path))
    return result

def load_catalog(filepath):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "catalog" not in data:
        raise ValueError("Missing 'catalog' key — not an OSCAL catalog.")
    catalog = data["catalog"]
    meta = catalog.get("metadata", {})
    return {
        "title":         meta.get("title", "Untitled catalog"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        "controls":      collect_controls(catalog),
        "filepath":      filepath,
    }

def load_profile(filepath):
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "profile" not in data:
        raise ValueError("Missing 'profile' key — not an OSCAL profile.")
    profile = data["profile"]
    meta = profile.get("metadata", {})
    included_ids = set()
    for imp in profile.get("imports", []):
        for selector in imp.get("include-controls", []):
            for ctrl_id in selector.get("with-ids", []):
                included_ids.add(ctrl_id)
    return {
        "title":         meta.get("title", "Untitled profile"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        "ids":           included_ids,
        "filepath":      filepath,
    }

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def new_uuid():
    return str(uuid.uuid4())


# ── Main Application ──────────────────────────────────────────────────────────

class OSCALViewer(tk.Tk):

    BG         = "#1e1e2e"
    SIDEBAR_BG = "#181825"
    HEADER_BG  = "#313244"
    INFO_BG    = "#252535"
    CARD_BG    = "#2a2a3d"
    ACCENT     = "#cba6f7"
    TEXT       = "#cdd6f4"
    SUBTEXT    = "#a6adc8"
    GREEN      = "#a6e3a1"
    YELLOW     = "#f9e2af"
    RED        = "#f38ba8"
    BLUE       = "#89b4fa"
    TEAL       = "#94e2d5"
    ORANGE     = "#fab387"

    def __init__(self):
        super().__init__()
        self.title("OSCAL Catalog Viewer & SSP Editor")
        self.geometry("1340x900")
        self.minsize(1000, 700)
        self.configure(bg=self.BG)

        self._catalog = None
        self._profile = None
        self._all_controls = []
        self._filtered_controls = []
        self._selected_class = tk.StringVar(value="All")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)

        # SSP data model
        self._ssp = self._empty_ssp()

        self._build_ui()

    # ── SSP data model ────────────────────────────────────────────────────────

    def _empty_ssp(self):
        """Return a blank SSP data dict that mirrors the OSCAL structure."""
        return {
            "uuid": new_uuid(),
            # Metadata
            "title": "",
            "version": "1.0",
            "date_authorized": "",
            # System characteristics
            "system_name": "",
            "system_name_short": "",
            "system_description": "",
            "security_sensitivity_level": "fips-199-moderate",
            "status": "under-development",
            "status_remarks": "",
            # Authorization boundary
            "auth_boundary_description": "",
            # Network architecture & data flow (optional text)
            "network_architecture": "",
            "data_flow": "",
            # Roles  — list of {"role_id": str, "title": str}
            "roles": [],
            # Parties — list of {"uuid": str, "type": str, "name": str, "email": str}
            "parties": [],
            # Information types — list of {uuid, title, description, c_impact, i_impact, a_impact}
            "information_types": [],
        }

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._style_ttk()
        self._build_toolbar()
        self._build_info_panel()
        self._build_notebook()
        self._build_statusbar()

    def _style_ttk(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=self.SIDEBAR_BG, foreground=self.TEXT,
                    fieldbackground=self.SIDEBAR_BG, borderwidth=0,
                    font=("Helvetica", 11), rowheight=26)
        s.configure("Treeview.Heading",
                    background=self.HEADER_BG, foreground=self.ACCENT,
                    font=("Helvetica", 11, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", self.ACCENT)],
              foreground=[("selected", self.BG)])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar",
                        background=self.HEADER_BG, troughcolor=self.SIDEBAR_BG,
                        borderwidth=0, arrowcolor=self.SUBTEXT)
        s.configure("TCombobox",
                    fieldbackground=self.HEADER_BG, background=self.HEADER_BG,
                    foreground=self.TEXT, selectbackground=self.ACCENT,
                    selectforeground=self.BG)
        s.map("TCombobox",
              fieldbackground=[("readonly", self.HEADER_BG)],
              foreground=[("readonly", self.TEXT)])
        # Notebook tabs
        s.configure("TNotebook", background=self.BG, borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=self.HEADER_BG, foreground=self.SUBTEXT,
                    padding=[14, 6], font=("Helvetica", 11))
        s.map("TNotebook.Tab",
              background=[("selected", self.CARD_BG)],
              foreground=[("selected", self.ACCENT)])

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=self.HEADER_BG, height=54)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        tk.Button(tb, text="📂  Open Catalog", command=self._open_file,
                  bg=self.ACCENT, fg=self.BG, font=("Helvetica", 12, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  activebackground="#b4befe", activeforeground=self.BG,
                  ).pack(side="left", padx=14, pady=10)

        tk.Button(tb, text="🔖  Open Profile", command=self._open_profile,
                  bg=self.YELLOW, fg=self.BG, font=("Helvetica", 12, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  activebackground="#f5c842", activeforeground=self.BG,
                  ).pack(side="left", padx=(0, 8), pady=10)

        self._clear_profile_btn = tk.Button(
            tb, text="✕  Clear Profile", command=self._clear_profile,
            bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 11),
            relief="flat", padx=10, pady=6, cursor="hand2", state="disabled",
            disabledforeground="#555570")
        self._clear_profile_btn.pack(side="left", pady=10)

        tk.Label(tb, text="OSCAL Catalog Viewer & SSP Editor",
                 bg=self.HEADER_BG, fg=self.TEXT,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=12)

        # Search & filter (right side)
        tk.Label(tb, text="🔍", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 13)).pack(side="right", padx=(0, 6))
        tk.Entry(tb, textvariable=self._search_var,
                 bg=self.SIDEBAR_BG, fg=self.TEXT, insertbackground=self.TEXT,
                 relief="flat", font=("Helvetica", 11), width=22,
                 ).pack(side="right", padx=(0, 12), ipady=4)
        tk.Label(tb, text="Search:", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(side="right")
        self._class_combo = ttk.Combobox(tb, textvariable=self._selected_class,
                                         values=["All"], state="readonly", width=18)
        self._class_combo.pack(side="right", padx=(0, 8), pady=14)
        self._class_combo.bind("<<ComboboxSelected>>", self._on_filter)
        tk.Label(tb, text="Class:", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(side="right", padx=(16, 4))

    def _build_info_panel(self):
        panel = tk.Frame(self, bg=self.INFO_BG)
        panel.pack(fill="x", side="top")

        # Catalog card
        self._cat_card = tk.Frame(panel, bg=self.CARD_BG,
                                  highlightthickness=1, highlightbackground=self.HEADER_BG)
        self._cat_card.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=8)
        cat_hdr = tk.Frame(self._cat_card, bg=self.HEADER_BG)
        cat_hdr.pack(fill="x")
        tk.Label(cat_hdr, text="📄  Catalog", bg=self.HEADER_BG, fg=self.ACCENT,
                 font=("Helvetica", 10, "bold"), anchor="w").pack(side="left", padx=10, pady=4)
        self._cat_title_lbl = tk.Label(cat_hdr, text="No catalog loaded",
                                       bg=self.HEADER_BG, fg=self.SUBTEXT,
                                       font=("Helvetica", 10, "italic"), anchor="w")
        self._cat_title_lbl.pack(side="left", padx=(0, 10), pady=4)
        f = tk.Frame(self._cat_card, bg=self.CARD_BG)
        f.pack(fill="x", padx=10, pady=6)
        self._cat_version_lbl   = self._info_field(f, "Version",       "—")
        self._cat_oscal_lbl     = self._info_field(f, "OSCAL Version", "—")
        self._cat_published_lbl = self._info_field(f, "Published",     "—")
        self._cat_modified_lbl  = self._info_field(f, "Last Modified", "—")
        self._cat_controls_lbl  = self._info_field(f, "Controls",      "—")

        # Profile card
        self._prof_card = tk.Frame(panel, bg=self.CARD_BG,
                                   highlightthickness=1, highlightbackground=self.HEADER_BG)
        self._prof_card.pack(side="left", fill="x", expand=True, padx=(5, 10), pady=8)
        prof_hdr = tk.Frame(self._prof_card, bg=self.HEADER_BG)
        prof_hdr.pack(fill="x")
        tk.Label(prof_hdr, text="🔖  Profile", bg=self.HEADER_BG, fg=self.YELLOW,
                 font=("Helvetica", 10, "bold"), anchor="w").pack(side="left", padx=10, pady=4)
        self._prof_title_lbl = tk.Label(prof_hdr, text="No profile loaded",
                                        bg=self.HEADER_BG, fg=self.SUBTEXT,
                                        font=("Helvetica", 10, "italic"), anchor="w")
        self._prof_title_lbl.pack(side="left", padx=(0, 10), pady=4)
        g = tk.Frame(self._prof_card, bg=self.CARD_BG)
        g.pack(fill="x", padx=10, pady=6)
        self._prof_version_lbl   = self._info_field(g, "Version",       "—")
        self._prof_oscal_lbl     = self._info_field(g, "OSCAL Version", "—")
        self._prof_published_lbl = self._info_field(g, "Published",     "—")
        self._prof_modified_lbl  = self._info_field(g, "Last Modified", "—")
        self._prof_controls_lbl  = self._info_field(g, "Controls",      "—")

    def _info_field(self, parent, label, value):
        frame = tk.Frame(parent, bg=self.CARD_BG)
        frame.pack(side="left", padx=(0, 20))
        tk.Label(frame, text=label, bg=self.CARD_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 9)).pack(anchor="w")
        lbl = tk.Label(frame, text=value, bg=self.CARD_BG, fg=self.TEXT,
                       font=("Helvetica", 10, "bold"))
        lbl.pack(anchor="w")
        return lbl

    # ── Notebook ──────────────────────────────────────────────────────────────

    def _build_notebook(self):
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=0, pady=0)
        self._build_catalog_tab()
        self._build_ssp_tab()

    # ── Tab 1: Catalog viewer ─────────────────────────────────────────────────

    def _build_catalog_tab(self):
        tab = tk.Frame(self._notebook, bg=self.BG)
        self._notebook.add(tab, text="📋  Catalog Viewer")

        body = tk.PanedWindow(tab, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        body.pack(fill="both", expand=True)

        # Left: control list
        left = tk.Frame(body, bg=self.SIDEBAR_BG)
        body.add(left, minsize=380, width=520)

        cols = ("label", "title", "class")
        self._tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("label", text="ID / Label", anchor="w")
        self._tree.heading("title", text="Title / Statement", anchor="w")
        self._tree.heading("class", text="Class", anchor="w")
        self._tree.column("label", width=120, minwidth=90,  anchor="w")
        self._tree.column("title", width=310, minwidth=150, anchor="w", stretch=True)
        self._tree.column("class", width=110, minwidth=90,  anchor="w")
        vsb = ttk.Scrollbar(left, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Right: scrollable detail
        right = tk.Frame(body, bg=self.BG)
        body.add(right, minsize=340)
        self._detail_canvas = tk.Canvas(right, bg=self.BG, highlightthickness=0)
        detail_vsb = ttk.Scrollbar(right, orient="vertical",
                                   command=self._detail_canvas.yview)
        self._detail_canvas.configure(yscrollcommand=detail_vsb.set)
        detail_vsb.pack(side="right", fill="y")
        self._detail_canvas.pack(fill="both", expand=True)
        self._detail_frame = tk.Frame(self._detail_canvas, bg=self.BG)
        self._detail_window = self._detail_canvas.create_window(
            (0, 0), window=self._detail_frame, anchor="nw")
        self._detail_frame.bind("<Configure>", self._on_detail_configure)
        self._detail_canvas.bind("<Configure>", self._on_canvas_configure)
        self._detail_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._show_placeholder()

    # ── Tab 2: SSP Editor ─────────────────────────────────────────────────────

    def _build_ssp_tab(self):
        tab = tk.Frame(self._notebook, bg=self.BG)
        self._notebook.add(tab, text="🛡  SSP Editor")

        # SSP toolbar
        ssp_tb = tk.Frame(tab, bg=self.CARD_BG, height=46)
        ssp_tb.pack(fill="x", side="top")
        ssp_tb.pack_propagate(False)

        tk.Button(ssp_tb, text="💾  Save SSP", command=self._save_ssp,
                  bg=self.GREEN, fg=self.BG, font=("Helvetica", 11, "bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#8cd39a", activeforeground=self.BG,
                  ).pack(side="left", padx=12, pady=8)

        tk.Button(ssp_tb, text="📂  Open SSP", command=self._open_ssp,
                  bg=self.BLUE, fg=self.BG, font=("Helvetica", 11, "bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#6a9fd8", activeforeground=self.BG,
                  ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(ssp_tb, text="🆕  New SSP", command=self._new_ssp,
                  bg=self.HEADER_BG, fg=self.TEXT, font=("Helvetica", 11),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  ).pack(side="left", padx=(0, 8), pady=8)

        self._ssp_status_lbl = tk.Label(
            ssp_tb, text="SSP not saved", bg=self.CARD_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10, "italic"))
        self._ssp_status_lbl.pack(side="left", padx=8)

        # Scrollable SSP form
        ssp_canvas = tk.Canvas(tab, bg=self.BG, highlightthickness=0)
        ssp_vsb = ttk.Scrollbar(tab, orient="vertical", command=ssp_canvas.yview)
        ssp_canvas.configure(yscrollcommand=ssp_vsb.set)
        ssp_vsb.pack(side="right", fill="y")
        ssp_canvas.pack(fill="both", expand=True)

        self._ssp_form = tk.Frame(ssp_canvas, bg=self.BG)
        ssp_form_win = ssp_canvas.create_window((0, 0), window=self._ssp_form, anchor="nw")

        def _on_ssp_configure(e):
            ssp_canvas.configure(scrollregion=ssp_canvas.bbox("all"))
        def _on_ssp_canvas_resize(e):
            ssp_canvas.itemconfig(ssp_form_win, width=e.width)
        self._ssp_form.bind("<Configure>", _on_ssp_configure)
        ssp_canvas.bind("<Configure>", _on_ssp_canvas_resize)
        ssp_canvas.bind_all("<MouseWheel>",
            lambda e: ssp_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
            if self._notebook.index("current") == 1 else None)

        self._build_ssp_form(self._ssp_form)

    def _build_ssp_form(self, parent):
        """Build all SSP editor sections inside the scrollable form frame."""
        P = dict(padx=28)

        # ── Section helper ────────────────────────────────────────────────────
        def section(title, color=None):
            hdr = tk.Frame(parent, bg=color or self.HEADER_BG)
            hdr.pack(fill="x", **P, pady=(20, 4))
            tk.Label(hdr, text=title, bg=color or self.HEADER_BG,
                     fg=self.ACCENT, font=("Helvetica", 12, "bold"),
                     anchor="w").pack(side="left", padx=12, pady=6)
            return hdr

        def field_row(label, var_or_widget=None, width=50, row_parent=None):
            rp = row_parent or parent
            row = tk.Frame(rp, bg=self.BG)
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            if var_or_widget is None:
                return row
            if isinstance(var_or_widget, tk.Variable):
                e = tk.Entry(row, textvariable=var_or_widget,
                             bg=self.CARD_BG, fg=self.TEXT, insertbackground=self.TEXT,
                             relief="flat", font=("Helvetica", 11), width=width,
                             highlightthickness=1, highlightbackground=self.HEADER_BG)
                e.pack(side="left", ipady=3)
            return row

        def text_block(label, height=4):
            row = tk.Frame(parent, bg=self.BG)
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11), width=22, anchor="nw").pack(side="left", anchor="n")
            frame = tk.Frame(row, bg=self.HEADER_BG, highlightthickness=1,
                             highlightbackground=self.HEADER_BG)
            frame.pack(side="left", fill="x", expand=True)
            t = tk.Text(frame, bg=self.CARD_BG, fg=self.TEXT, insertbackground=self.TEXT,
                        relief="flat", font=("Helvetica", 11), height=height,
                        wrap="word", padx=8, pady=6)
            t.pack(fill="both")
            return t

        def combo_row(label, var, values, width=30):
            row = tk.Frame(parent, bg=self.BG)
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            cb = ttk.Combobox(row, textvariable=var, values=values,
                              state="readonly", width=width)
            cb.pack(side="left")
            return cb

        # ═══════════════════════════════════════════════════════════════════
        # 1. SSP METADATA
        # ═══════════════════════════════════════════════════════════════════
        section("1 ·  SSP Metadata")

        self._ssp_vars = {}
        for key, label, w in [
            ("title",          "SSP Title *",          60),
            ("version",        "Version *",             20),
            ("date_authorized","Date Authorized",       20),
        ]:
            v = tk.StringVar()
            self._ssp_vars[key] = v
            field_row(label, v, width=w)

        tk.Label(parent,
                 text="  * Required fields.  Date format: YYYY-MM-DD",
                 bg=self.BG, fg=self.SUBTEXT, font=("Helvetica", 9, "italic")
                 ).pack(anchor="w", padx=28)

        # ═══════════════════════════════════════════════════════════════════
        # 2. SYSTEM CHARACTERISTICS
        # ═══════════════════════════════════════════════════════════════════
        section("2 ·  System Characteristics")

        for key, label, w in [
            ("system_name",       "System Name (Full) *",  60),
            ("system_name_short", "System Name (Short)",   30),
        ]:
            v = tk.StringVar()
            self._ssp_vars[key] = v
            field_row(label, v, width=w)

        tk.Label(parent, text="System Description *", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(anchor="w", padx=28, pady=(6, 2))
        self._ssp_system_desc = text_block("", height=4)

        # Status dropdown
        self._ssp_vars["status"] = tk.StringVar(value="under-development")
        combo_row("Operational Status *", self._ssp_vars["status"], [
            "operational", "under-development", "under-major-modification",
            "disposition", "other"])

        # Sensitivity level
        self._ssp_vars["security_sensitivity_level"] = tk.StringVar(value="fips-199-moderate")
        combo_row("Security Sensitivity Level", self._ssp_vars["security_sensitivity_level"],
                  ["fips-199-low", "fips-199-moderate", "fips-199-high"])

        tk.Label(parent, text="Status Remarks", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(anchor="w", padx=28, pady=(6, 2))
        self._ssp_status_remarks = text_block("", height=2)

        # ═══════════════════════════════════════════════════════════════════
        # 3. AUTHORIZATION BOUNDARY
        # ═══════════════════════════════════════════════════════════════════
        section("3 ·  Authorization Boundary")

        tk.Label(parent, text="Boundary Description *", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(anchor="w", padx=28, pady=(6, 2))
        self._ssp_auth_boundary = text_block("", height=4)

        # ═══════════════════════════════════════════════════════════════════
        # 4. NETWORK ARCHITECTURE & DATA FLOW  (optional)
        # ═══════════════════════════════════════════════════════════════════
        section("4 ·  Network Architecture & Data Flow  (optional)")

        tk.Label(parent, text="Network Architecture", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(anchor="w", padx=28, pady=(6, 2))
        self._ssp_network = text_block("", height=3)

        tk.Label(parent, text="Data Flow", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(anchor="w", padx=28, pady=(6, 2))
        self._ssp_dataflow = text_block("", height=3)

        # ═══════════════════════════════════════════════════════════════════
        # 5. INFORMATION TYPES
        # ═══════════════════════════════════════════════════════════════════
        section("5 ·  Information Types")
        tk.Label(parent,
                 text="  At least one information type is required by the OSCAL SSP schema.",
                 bg=self.BG, fg=self.SUBTEXT, font=("Helvetica", 9, "italic")
                 ).pack(anchor="w", padx=28)

        # Info-type list
        it_frame = tk.Frame(parent, bg=self.CARD_BG,
                            highlightthickness=1, highlightbackground=self.HEADER_BG)
        it_frame.pack(fill="x", padx=28, pady=6)

        it_btn_row = tk.Frame(it_frame, bg=self.CARD_BG)
        it_btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(it_btn_row, text="＋  Add Information Type",
                  command=self._add_info_type,
                  bg=self.BLUE, fg=self.BG, font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(it_btn_row, text="✕  Remove Selected",
                  command=self._remove_info_type,
                  bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        it_cols = ("title", "c_impact", "i_impact", "a_impact")
        self._it_tree = ttk.Treeview(it_frame, columns=it_cols,
                                     show="headings", height=4, selectmode="browse")
        self._it_tree.heading("title",    text="Information Type Title", anchor="w")
        self._it_tree.heading("c_impact", text="Confidentiality", anchor="w")
        self._it_tree.heading("i_impact", text="Integrity",        anchor="w")
        self._it_tree.heading("a_impact", text="Availability",     anchor="w")
        self._it_tree.column("title",    width=300, anchor="w", stretch=True)
        self._it_tree.column("c_impact", width=120, anchor="w")
        self._it_tree.column("i_impact", width=120, anchor="w")
        self._it_tree.column("a_impact", width=120, anchor="w")
        self._it_tree.pack(fill="x", padx=8, pady=(0, 8))

        # ═══════════════════════════════════════════════════════════════════
        # 6. ROLES
        # ═══════════════════════════════════════════════════════════════════
        section("6 ·  Roles")
        tk.Label(parent,
                 text="  Define roles responsible for the system (e.g. system-owner, isso).",
                 bg=self.BG, fg=self.SUBTEXT, font=("Helvetica", 9, "italic")
                 ).pack(anchor="w", padx=28)

        role_frame = tk.Frame(parent, bg=self.CARD_BG,
                              highlightthickness=1, highlightbackground=self.HEADER_BG)
        role_frame.pack(fill="x", padx=28, pady=6)

        role_btn_row = tk.Frame(role_frame, bg=self.CARD_BG)
        role_btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(role_btn_row, text="＋  Add Role",
                  command=self._add_role,
                  bg=self.BLUE, fg=self.BG, font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(role_btn_row, text="✕  Remove Selected",
                  command=self._remove_role,
                  bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        role_cols = ("role_id", "title")
        self._role_tree = ttk.Treeview(role_frame, columns=role_cols,
                                       show="headings", height=4, selectmode="browse")
        self._role_tree.heading("role_id", text="Role ID",    anchor="w")
        self._role_tree.heading("title",   text="Role Title", anchor="w")
        self._role_tree.column("role_id", width=200, anchor="w")
        self._role_tree.column("title",   width=400, anchor="w", stretch=True)
        self._role_tree.pack(fill="x", padx=8, pady=(0, 8))

        # ═══════════════════════════════════════════════════════════════════
        # 7. PARTIES
        # ═══════════════════════════════════════════════════════════════════
        section("7 ·  Parties  (People & Organisations)")
        tk.Label(parent,
                 text="  Parties are the people or organisations referenced by roles.",
                 bg=self.BG, fg=self.SUBTEXT, font=("Helvetica", 9, "italic")
                 ).pack(anchor="w", padx=28)

        party_frame = tk.Frame(parent, bg=self.CARD_BG,
                               highlightthickness=1, highlightbackground=self.HEADER_BG)
        party_frame.pack(fill="x", padx=28, pady=6)

        party_btn_row = tk.Frame(party_frame, bg=self.CARD_BG)
        party_btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(party_btn_row, text="＋  Add Party",
                  command=self._add_party,
                  bg=self.BLUE, fg=self.BG, font=("Helvetica", 10, "bold"),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(party_btn_row, text="✕  Remove Selected",
                  command=self._remove_party,
                  bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 10),
                  relief="flat", padx=10, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        party_cols = ("type", "name", "email")
        self._party_tree = ttk.Treeview(party_frame, columns=party_cols,
                                        show="headings", height=4, selectmode="browse")
        self._party_tree.heading("type",  text="Type",         anchor="w")
        self._party_tree.heading("name",  text="Name",         anchor="w")
        self._party_tree.heading("email", text="Email",        anchor="w")
        self._party_tree.column("type",  width=120, anchor="w")
        self._party_tree.column("name",  width=260, anchor="w")
        self._party_tree.column("email", width=260, anchor="w", stretch=True)
        self._party_tree.pack(fill="x", padx=8, pady=(0, 8))

        # Bottom padding
        tk.Frame(parent, bg=self.BG, height=40).pack()

    # ── SSP sub-dialogs ───────────────────────────────────────────────────────

    def _dialog(self, title, fields):
        """
        Generic modal dialog. fields = list of (label, key, default, choices|None).
        Returns dict of values, or None if cancelled.
        """
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=self.BG)
        dlg.resizable(False, False)
        dlg.grab_set()

        vars_ = {}
        for label, key, default, choices in fields:
            row = tk.Frame(dlg, bg=self.BG)
            row.pack(fill="x", padx=20, pady=5)
            tk.Label(row, text=label, bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            v = tk.StringVar(value=default)
            vars_[key] = v
            if choices:
                ttk.Combobox(row, textvariable=v, values=choices,
                             state="readonly", width=28).pack(side="left")
            else:
                tk.Entry(row, textvariable=v, bg=self.CARD_BG, fg=self.TEXT,
                         insertbackground=self.TEXT, relief="flat",
                         font=("Helvetica", 11), width=32,
                         highlightthickness=1,
                         highlightbackground=self.HEADER_BG).pack(side="left", ipady=3)

        result = {}
        def _ok():
            for k, v in vars_.items():
                result[k] = v.get().strip()
            dlg.destroy()
        def _cancel():
            dlg.destroy()

        btn_row = tk.Frame(dlg, bg=self.BG)
        btn_row.pack(pady=12)
        tk.Button(btn_row, text="  OK  ", command=_ok,
                  bg=self.ACCENT, fg=self.BG, font=("Helvetica", 11, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn_row, text="Cancel", command=_cancel,
                  bg=self.HEADER_BG, fg=self.TEXT, font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")

        dlg.wait_window()
        return result if result else None

    def _add_info_type(self):
        impact_choices = ["fips-199-low", "fips-199-moderate", "fips-199-high"]
        res = self._dialog("Add Information Type", [
            ("Title *",           "title",       "",                    None),
            ("Description *",     "description", "",                    None),
            ("Confidentiality",   "c_impact",    "fips-199-moderate",   impact_choices),
            ("Integrity",         "i_impact",    "fips-199-moderate",   impact_choices),
            ("Availability",      "a_impact",    "fips-199-moderate",   impact_choices),
        ])
        if not res or not res.get("title"):
            return
        res["uuid"] = new_uuid()
        self._ssp["information_types"].append(res)
        self._it_tree.insert("", "end",
            values=(res["title"], res["c_impact"], res["i_impact"], res["a_impact"]))

    def _remove_info_type(self):
        sel = self._it_tree.selection()
        if not sel:
            return
        idx = self._it_tree.index(sel[0])
        self._ssp["information_types"].pop(idx)
        self._it_tree.delete(sel[0])

    def _add_role(self):
        common = ["system-owner", "isso", "authorizing-official",
                  "system-poc-management", "system-poc-technical",
                  "system-poc-other", "privacy-officer", "security-operations"]
        res = self._dialog("Add Role", [
            ("Role ID *",    "role_id", "", common),
            ("Role Title *", "title",   "", None),
        ])
        if not res or not res.get("role_id"):
            return
        self._ssp["roles"].append(res)
        self._role_tree.insert("", "end", values=(res["role_id"], res["title"]))

    def _remove_role(self):
        sel = self._role_tree.selection()
        if not sel:
            return
        idx = self._role_tree.index(sel[0])
        self._ssp["roles"].pop(idx)
        self._role_tree.delete(sel[0])

    def _add_party(self):
        res = self._dialog("Add Party", [
            ("Type *", "type",  "person",       ["person", "organization"]),
            ("Name *", "name",  "",             None),
            ("Email",  "email", "",             None),
        ])
        if not res or not res.get("name"):
            return
        res["uuid"] = new_uuid()
        self._ssp["parties"].append(res)
        self._party_tree.insert("", "end",
            values=(res["type"], res["name"], res.get("email", "")))

    def _remove_party(self):
        sel = self._party_tree.selection()
        if not sel:
            return
        idx = self._party_tree.index(sel[0])
        self._ssp["parties"].pop(idx)
        self._party_tree.delete(sel[0])

    # ── SSP save / new ────────────────────────────────────────────────────────

    def _collect_ssp_form(self):
        """Read all form widgets back into self._ssp."""
        for key, var in self._ssp_vars.items():
            self._ssp[key] = var.get().strip()
        self._ssp["system_description"] = self._ssp_system_desc.get("1.0", "end-1c").strip()
        self._ssp["status_remarks"]     = self._ssp_status_remarks.get("1.0", "end-1c").strip()
        self._ssp["auth_boundary_description"] = self._ssp_auth_boundary.get("1.0", "end-1c").strip()
        self._ssp["network_architecture"] = self._ssp_network.get("1.0", "end-1c").strip()
        self._ssp["data_flow"]            = self._ssp_dataflow.get("1.0", "end-1c").strip()

    def _validate_ssp(self):
        """Return a list of validation error strings (empty = valid)."""
        errors = []
        if not self._ssp.get("title"):
            errors.append("SSP Title is required (Section 1).")
        if not self._ssp.get("system_name"):
            errors.append("System Name (Full) is required (Section 2).")
        if not self._ssp.get("system_description"):
            errors.append("System Description is required (Section 2).")
        if not self._ssp.get("auth_boundary_description"):
            errors.append("Authorization Boundary Description is required (Section 3).")
        if not self._ssp.get("information_types"):
            errors.append("At least one Information Type is required (Section 5).")
        if not self._catalog:
            errors.append("No catalog is loaded — the SSP import-profile cannot be set.")
        return errors

    def _build_oscal_ssp(self):
        """Convert self._ssp into a valid OSCAL SSP JSON dict."""
        ssp = self._ssp
        now = now_iso()

        # Roles
        roles = [{"id": r["role_id"], "title": r["title"]}
                 for r in ssp.get("roles", [])]

        # Parties
        parties = []
        for p in ssp.get("parties", []):
            entry = {"uuid": p["uuid"], "type": p["type"],
                     "name": p["name"]}
            if p.get("email"):
                entry["email-addresses"] = [p["email"]]
            parties.append(entry)

        # Information types
        info_types = []
        for it in ssp.get("information_types", []):
            info_types.append({
                "uuid":        it["uuid"],
                "title":       it["title"],
                "description": it.get("description", ""),
                "confidentiality-impact": {
                    "base": it.get("c_impact", "fips-199-moderate")},
                "integrity-impact": {
                    "base": it.get("i_impact", "fips-199-moderate")},
                "availability-impact": {
                    "base": it.get("a_impact", "fips-199-moderate")},
            })

        # Import profile href — prefer loaded profile filepath, else catalog
        if self._profile and self._profile.get("filepath"):
            import_href = Path(self._profile["filepath"]).name
        elif self._catalog and self._catalog.get("filepath"):
            import_href = Path(self._catalog["filepath"]).name
        else:
            import_href = "PROFILE_OR_CATALOG_HREF"

        # Auto-generate a single "this-system" component (required by schema)
        component_uuid = new_uuid()

        doc = {
            "system-security-plan": {
                "uuid": ssp["uuid"],
                "metadata": {
                    "title":         ssp["title"],
                    "last-modified": now,
                    "version":       ssp.get("version", "1.0"),
                    "oscal-version": "1.1.2",
                    **({"roles": roles} if roles else {}),
                    **({"parties": parties} if parties else {}),
                },
                "import-profile": {
                    "href": import_href,
                },
                "system-characteristics": {
                    "system-ids": [{"id": ssp["uuid"], "identifier-type": "https://ietf.org/rfc/rfc4122"}],
                    "system-name": ssp.get("system_name", ""),
                    **({"system-name-short": ssp["system_name_short"]}
                       if ssp.get("system_name_short") else {}),
                    "description": ssp.get("system_description", ""),
                    **({"date-authorized": ssp["date_authorized"]}
                       if ssp.get("date_authorized") else {}),
                    **({"security-sensitivity-level": ssp["security_sensitivity_level"]}
                       if ssp.get("security_sensitivity_level") else {}),
                    "system-information": {
                        "information-types": info_types,
                    },
                    "status": {
                        "state": ssp.get("status", "under-development"),
                        **({"remarks": ssp["status_remarks"]}
                           if ssp.get("status_remarks") else {}),
                    },
                    "authorization-boundary": {
                        "description": ssp.get("auth_boundary_description", ""),
                    },
                    **({"network-architecture": {"description": ssp["network_architecture"]}}
                       if ssp.get("network_architecture") else {}),
                    **({"data-flow": {"description": ssp["data_flow"]}}
                       if ssp.get("data_flow") else {}),
                },
                "system-implementation": {
                    "components": [
                        {
                            "uuid":        component_uuid,
                            "type":        "this-system",
                            "title":       ssp.get("system_name", "This System"),
                            "description": ssp.get("system_description", ""),
                            "status":      {"state": ssp.get("status", "under-development")},
                        }
                    ]
                },
                "control-implementation": {
                    "description": "Control implementation statements will be added in Stage 2.",
                    "implemented-requirements": [],
                },
            }
        }
        return doc

    def _save_ssp(self):
        self._collect_ssp_form()
        errors = self._validate_ssp()
        if errors:
            messagebox.showerror("Cannot save SSP",
                                 "Please fix the following before saving:\n\n" +
                                 "\n".join(f"• {e}" for e in errors))
            return

        path = filedialog.asksaveasfilename(
            title="Save OSCAL SSP",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"ssp_{self._ssp.get('system_name_short') or 'draft'}.json",
        )
        if not path:
            return

        doc = self._build_oscal_ssp()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        self._ssp_status_lbl.config(
            text=f"Saved: {Path(path).name}",
            fg=self.GREEN)
        self._status_lbl.config(text=f"SSP saved: {Path(path).name}")
        messagebox.showinfo("SSP Saved",
                            f"OSCAL SSP saved successfully:\n{path}")

    def _new_ssp(self):
        if messagebox.askyesno("New SSP",
                               "Clear the current SSP and start a new one?"):
            self._ssp = self._empty_ssp()
            self._reset_ssp_form()
            self._ssp_status_lbl.config(text="New SSP (unsaved)", fg=self.SUBTEXT)

    def _open_ssp(self):
        """Load a previously saved OSCAL SSP JSON file back into the editor."""
        path = filedialog.askopenfilename(
            title="Open OSCAL SSP",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showerror("Failed to open SSP", str(exc))
            return

        root = data.get("system-security-plan")
        if not root:
            messagebox.showerror("Invalid file",
                                 "This file does not appear to be an OSCAL SSP "
                                 "(missing 'system-security-plan' key).")
            return

        # ── Parse the OSCAL JSON back into our internal model ─────────────────
        meta   = root.get("metadata", {})
        sc     = root.get("system-characteristics", {})
        status = sc.get("status", {})
        ab     = sc.get("authorization-boundary", {})
        na     = sc.get("network-architecture", {})
        df     = sc.get("data-flow", {})
        si     = root.get("system-information", sc.get("system-information", {}))

        # Roles
        roles = [{"role_id": r.get("id", ""), "title": r.get("title", "")}
                 for r in meta.get("roles", [])]

        # Parties
        parties = []
        for p in meta.get("parties", []):
            emails = p.get("email-addresses", [])
            parties.append({
                "uuid":  p.get("uuid", new_uuid()),
                "type":  p.get("type", "person"),
                "name":  p.get("name", ""),
                "email": emails[0] if emails else "",
            })

        # Information types
        info_types = []
        for it in sc.get("system-information", {}).get("information-types", []):
            info_types.append({
                "uuid":        it.get("uuid", new_uuid()),
                "title":       it.get("title", ""),
                "description": it.get("description", ""),
                "c_impact":    it.get("confidentiality-impact", {}).get("base", "fips-199-moderate"),
                "i_impact":    it.get("integrity-impact",       {}).get("base", "fips-199-moderate"),
                "a_impact":    it.get("availability-impact",    {}).get("base", "fips-199-moderate"),
            })

        ssp = {
            "uuid":            root.get("uuid", new_uuid()),
            "title":           meta.get("title", ""),
            "version":         meta.get("version", "1.0"),
            "date_authorized": sc.get("date-authorized", ""),
            "system_name":     sc.get("system-name", ""),
            "system_name_short": sc.get("system-name-short", ""),
            "system_description": sc.get("description", ""),
            "security_sensitivity_level": sc.get("security-sensitivity-level", "fips-199-moderate"),
            "status":          status.get("state", "under-development"),
            "status_remarks":  status.get("remarks", ""),
            "auth_boundary_description": ab.get("description", ""),
            "network_architecture": na.get("description", ""),
            "data_flow":       df.get("description", ""),
            "roles":           roles,
            "parties":         parties,
            "information_types": info_types,
        }

        # Confirm if there is unsaved work in the current form
        current_title = self._ssp_vars.get("title", tk.StringVar()).get().strip()
        if current_title:
            if not messagebox.askyesno("Replace current SSP?",
                                       f"Replace the current SSP '{current_title}' "
                                       f"with '{ssp['title'] or Path(path).name}'?"):
                return

        self._ssp = ssp
        self._populate_ssp_form()
        self._ssp_status_lbl.config(
            text=f"Opened: {Path(path).name}", fg=self.BLUE)
        self._status_lbl.config(text=f"SSP opened: {Path(path).name}")
        # Switch to the SSP tab automatically
        self._notebook.select(1)

    def _populate_ssp_form(self):
        """Push self._ssp back into every form widget."""
        ssp = self._ssp
        defaults = {"version": "1.0", "status": "under-development",
                    "security_sensitivity_level": "fips-199-moderate"}

        # Simple StringVar fields
        for key, var in self._ssp_vars.items():
            var.set(ssp.get(key) or defaults.get(key, ""))

        # Text widgets
        for widget, key in [
            (self._ssp_system_desc,  "system_description"),
            (self._ssp_status_remarks, "status_remarks"),
            (self._ssp_auth_boundary, "auth_boundary_description"),
            (self._ssp_network,       "network_architecture"),
            (self._ssp_dataflow,      "data_flow"),
        ]:
            widget.delete("1.0", "end")
            val = ssp.get(key, "")
            if val:
                widget.insert("1.0", val)

        # Information types tree
        self._it_tree.delete(*self._it_tree.get_children())
        for it in ssp.get("information_types", []):
            self._it_tree.insert("", "end",
                values=(it["title"], it.get("c_impact", "—"),
                        it.get("i_impact", "—"), it.get("a_impact", "—")))

        # Roles tree
        self._role_tree.delete(*self._role_tree.get_children())
        for r in ssp.get("roles", []):
            self._role_tree.insert("", "end", values=(r["role_id"], r["title"]))

        # Parties tree
        self._party_tree.delete(*self._party_tree.get_children())
        for p in ssp.get("parties", []):
            self._party_tree.insert("", "end",
                values=(p["type"], p["name"], p.get("email", "")))

    def _reset_ssp_form(self):
        """Reset all SSP form widgets to blank/defaults."""
        defaults = {"version": "1.0", "status": "under-development",
                    "security_sensitivity_level": "fips-199-moderate"}
        for key, var in self._ssp_vars.items():
            var.set(defaults.get(key, ""))
        for widget in (self._ssp_system_desc, self._ssp_status_remarks,
                       self._ssp_auth_boundary, self._ssp_network, self._ssp_dataflow):
            widget.delete("1.0", "end")
        self._it_tree.delete(*self._it_tree.get_children())
        self._role_tree.delete(*self._role_tree.get_children())
        self._party_tree.delete(*self._party_tree.get_children())

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=self.HEADER_BG, height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(
            sb, text="No catalog loaded — click '📂 Open Catalog' to begin.",
            bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 10), anchor="w")
        self._status_lbl.pack(side="left", padx=10)
        self._count_lbl = tk.Label(
            sb, text="", bg=self.HEADER_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10), anchor="e")
        self._count_lbl.pack(side="right", padx=10)

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open OSCAL Catalog",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            catalog = load_catalog(path)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            messagebox.showerror("Failed to load catalog", str(exc))
            return

        self._catalog = catalog
        self._profile = None
        self._all_controls = catalog["controls"]
        self._filtered_controls = list(self._all_controls)

        classes = sorted({c["class"] for c in self._all_controls if c["class"]})
        self._class_combo["values"] = ["All"] + classes
        self._selected_class.set("All")
        self._search_var.set("")

        self._cat_title_lbl.config(text=catalog["title"], fg=self.TEXT)
        self._cat_version_lbl.config(text=catalog["version"])
        self._cat_oscal_lbl.config(text=catalog["oscal_version"])
        self._cat_published_lbl.config(text=catalog["published"])
        self._cat_modified_lbl.config(text=catalog["last_modified"])
        self._cat_controls_lbl.config(text=str(len(catalog["controls"])))

        self._prof_title_lbl.config(text="No profile loaded", fg=self.SUBTEXT)
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")
        self._clear_profile_btn.config(state="disabled")

        self._populate_tree(self._all_controls)
        self._show_placeholder()
        self._status_lbl.config(text=f"Loaded catalog: {Path(path).name}")
        self._update_count()

    def _open_profile(self):
        if not self._catalog:
            messagebox.showwarning("No catalog loaded",
                                   "Please open a catalog file before loading a profile.")
            return
        path = filedialog.askopenfilename(
            title="Open OSCAL Profile",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            profile = load_profile(path)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            messagebox.showerror("Failed to load profile", str(exc))
            return

        self._profile = profile
        self._clear_profile_btn.config(state="normal")
        self._prof_title_lbl.config(text=profile["title"], fg=self.YELLOW)
        self._prof_version_lbl.config(text=profile["version"])
        self._prof_oscal_lbl.config(text=profile["oscal_version"])
        self._prof_published_lbl.config(text=profile["published"])
        self._prof_modified_lbl.config(text=profile["last_modified"])
        self._prof_controls_lbl.config(text=str(len(profile["ids"])))

        self._apply_filters()
        self._show_placeholder()
        self._status_lbl.config(text=f"Profile applied: {Path(path).name}")

    def _clear_profile(self):
        self._profile = None
        self._clear_profile_btn.config(state="disabled")
        self._prof_title_lbl.config(text="No profile loaded", fg=self.SUBTEXT)
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")
        self._apply_filters()
        self._show_placeholder()
        self._status_lbl.config(text="Profile cleared — showing full catalog.")

    # ── Tree / Filtering ──────────────────────────────────────────────────────

    def _populate_tree(self, controls):
        self._tree.delete(*self._tree.get_children())
        for i, ctrl in enumerate(controls):
            tag = "principle" if ctrl["class"] == "ISM-principle" else "control"
            display_title = ctrl["title"]
            if display_title.lower().startswith("control:") or not display_title:
                display_title = ctrl["statement"]
            self._tree.insert("", "end", iid=str(i),
                              values=(ctrl["label"], display_title, ctrl["class"]),
                              tags=(tag,))
        self._tree.tag_configure("principle", foreground=self.TEAL)
        self._tree.tag_configure("control",   foreground=self.TEXT)
        self._filtered_controls = controls
        self._update_count()

    def _apply_filters(self):
        if not self._all_controls:
            return
        cls  = self._selected_class.get()
        term = self._search_var.get().lower().strip()
        result = self._all_controls
        if self._profile:
            ids = self._profile["ids"]
            result = [c for c in result if c["id"] in ids]
        if cls != "All":
            result = [c for c in result if c["class"] == cls]
        if term:
            result = [c for c in result
                      if term in c["title"].lower()
                      or term in c["label"].lower()
                      or term in c["statement"].lower()
                      or term in c["id"].lower()]
        self._populate_tree(result)
        self._show_placeholder()

    def _on_filter(self, _=None): self._apply_filters()
    def _on_search(self, *_):    self._apply_filters()

    # ── Detail view ───────────────────────────────────────────────────────────

    def _on_select(self, _=None):
        sel = self._tree.selection()
        if not sel:
            return
        self._show_detail(self._filtered_controls[int(sel[0])])

    def _show_placeholder(self):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        msg = ("Select a control from the list to view details."
               if self._catalog else
               "Open an OSCAL catalog file to get started.")
        tk.Label(self._detail_frame, text=msg,
                 bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 13, "italic"),
                 wraplength=400, justify="center",
                 ).pack(expand=True, pady=80, padx=40)

    def _show_detail(self, ctrl):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        pad = dict(padx=22)

        header = tk.Frame(self._detail_frame, bg=self.HEADER_BG)
        header.pack(fill="x", **pad, pady=(18, 4))
        badge_fg = self.TEAL if ctrl["class"] == "ISM-principle" else self.BLUE
        tk.Label(header, text=f"  {ctrl['label']}  ",
                 bg=badge_fg, fg=self.BG,
                 font=("Helvetica", 12, "bold"), relief="flat",
                 ).pack(side="left", padx=10, pady=8)
        has_real_title = ctrl["title"] and not ctrl["title"].lower().startswith("control:")
        tk.Label(header,
                 text=ctrl["title"] if has_real_title else ctrl["statement"],
                 bg=self.HEADER_BG, fg=self.TEXT,
                 font=("Helvetica", 13, "bold"),
                 wraplength=480, justify="left",
                 ).pack(side="left", padx=6, pady=8, fill="x", expand=True)

        self._row(self._detail_frame, "Category", ctrl["path"],
                  value_color=self.SUBTEXT, italic=True)
        tk.Frame(self._detail_frame, bg=self.HEADER_BG, height=1).pack(
            fill="x", padx=22, pady=6)
        self._row(self._detail_frame, "Control ID", ctrl["id"])
        self._row(self._detail_frame, "Class",      ctrl["class"])
        if ctrl["revision"] != "—":
            self._row(self._detail_frame, "Revision", ctrl["revision"])
        if ctrl["updated"] != "—":
            self._row(self._detail_frame, "Updated",  ctrl["updated"])
        if ctrl["essential_eight"] != "—":
            self._row(self._detail_frame, "Essential Eight", ctrl["essential_eight"],
                      value_color=self.YELLOW)

        if ctrl["applicability"]:
            cf = tk.Frame(self._detail_frame, bg=self.BG)
            cf.pack(fill="x", **pad, pady=4)
            tk.Label(cf, text="Applicability:", bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11, "bold"), width=14, anchor="w").pack(side="left")
            for ap in ctrl["applicability"]:
                tk.Label(cf, text=f" {ap} ", bg=self.GREEN, fg=self.BG,
                         font=("Helvetica", 10, "bold"), relief="flat",
                         ).pack(side="left", padx=3)

        tk.Frame(self._detail_frame, bg=self.HEADER_BG, height=1).pack(
            fill="x", padx=22, pady=8)

        if ctrl["statement"]:
            tk.Label(self._detail_frame, text="Statement",
                     bg=self.BG, fg=self.ACCENT,
                     font=("Helvetica", 12, "bold"),
                     ).pack(anchor="w", **pad, pady=(4, 2))
            box = tk.Frame(self._detail_frame, bg=self.SIDEBAR_BG,
                           highlightthickness=1, highlightbackground=self.HEADER_BG)
            box.pack(fill="x", padx=22, pady=4)
            tk.Label(box, text=ctrl["statement"],
                     bg=self.SIDEBAR_BG, fg=self.TEXT,
                     font=("Helvetica", 12),
                     wraplength=520, justify="left", anchor="nw",
                     ).pack(padx=14, pady=12, fill="x")

        tk.Frame(self._detail_frame, bg=self.BG, height=30).pack()

    def _row(self, parent, label, value, value_color=None, italic=False):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill="x", padx=22, pady=2)
        tk.Label(frame, text=f"{label}:", bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11, "bold"), width=14, anchor="w").pack(side="left")
        tk.Label(frame, text=value, bg=self.BG, fg=value_color or self.TEXT,
                 font=("Helvetica", 11, "italic") if italic else ("Helvetica", 11),
                 wraplength=500, justify="left", anchor="w",
                 ).pack(side="left", fill="x", expand=True)

    # ── Scroll helpers ────────────────────────────────────────────────────────

    def _on_detail_configure(self, _):
        self._detail_canvas.configure(scrollregion=self._detail_canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._detail_canvas.itemconfig(self._detail_window, width=e.width)

    def _on_mousewheel(self, e):
        widget = self.winfo_containing(e.x_root, e.y_root)
        canvas = self._detail_canvas
        if widget and (widget is canvas or str(widget).startswith(str(canvas))):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def _update_count(self):
        total = len(self._all_controls)
        shown = len(self._filtered_controls)
        if total == 0:
            self._count_lbl.config(text="")
        elif shown == total:
            self._count_lbl.config(text=f"{total} controls")
        else:
            self._count_lbl.config(text=f"Showing {shown} of {total} controls")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = OSCALViewer()
    app.mainloop()
