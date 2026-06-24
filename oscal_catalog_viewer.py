"""
OSCAL Catalog Viewer
A desktop application to browse and explore OSCAL catalog JSON files.
Requires only Python standard library (tkinter + json).
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_prop(props: list, name: str, default="—") -> str:
    for p in props:
        if p.get("name") == name:
            return p.get("value", default)
    return default


def get_all_props(props: list, name: str) -> list:
    return [p.get("value", "") for p in props if p.get("name") == name]


def get_statement(parts: list) -> str:
    for part in parts:
        if part.get("name") == "statement":
            return part.get("prose", "").strip()
    return ""


def collect_controls(obj: dict, parent_titles=None) -> list:
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


def load_catalog(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "catalog" not in data:
        raise ValueError("File does not appear to be an OSCAL catalog (missing 'catalog' key).")
    catalog = data["catalog"]
    meta = catalog.get("metadata", {})
    return {
        "title":         meta.get("title", "Untitled catalog"),
        "published":     meta.get("published", "—"),
        "last_modified": meta.get("last-modified", "—"),
        "version":       meta.get("version", "—"),
        "oscal_version": meta.get("oscal-version", "—"),
        "controls":      collect_controls(catalog),
    }


def load_profile(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if "profile" not in data:
        raise ValueError("File does not appear to be an OSCAL profile (missing 'profile' key).")
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
    }


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

    def __init__(self):
        super().__init__()
        self.title("OSCAL Catalog Viewer")
        self.geometry("1280x820")
        self.minsize(900, 640)
        self.configure(bg=self.BG)

        self._catalog = None
        self._profile = None
        self._all_controls = []
        self._filtered_controls = []
        self._selected_class = tk.StringVar(value="All")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._style_ttk()
        self._build_toolbar()
        self._build_info_panel()
        self._build_body()
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
        s.configure("Vertical.TScrollbar",
                    background=self.HEADER_BG, troughcolor=self.SIDEBAR_BG,
                    borderwidth=0, arrowcolor=self.SUBTEXT)
        s.configure("Horizontal.TScrollbar",
                    background=self.HEADER_BG, troughcolor=self.SIDEBAR_BG,
                    borderwidth=0, arrowcolor=self.SUBTEXT)
        s.configure("TCombobox",
                    fieldbackground=self.HEADER_BG, background=self.HEADER_BG,
                    foreground=self.TEXT, selectbackground=self.ACCENT,
                    selectforeground=self.BG)
        s.map("TCombobox",
              fieldbackground=[("readonly", self.HEADER_BG)],
              foreground=[("readonly", self.TEXT)])

    def _build_toolbar(self):
        tb = tk.Frame(self, bg=self.HEADER_BG, height=54)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        # Open Catalog
        tk.Button(
            tb, text="📂  Open Catalog", command=self._open_file,
            bg=self.ACCENT, fg=self.BG, font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#b4befe", activeforeground=self.BG,
        ).pack(side="left", padx=14, pady=10)

        # Open Profile
        tk.Button(
            tb, text="🔖  Open Profile", command=self._open_profile,
            bg=self.YELLOW, fg=self.BG, font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#f5c842", activeforeground=self.BG,
        ).pack(side="left", padx=(0, 8), pady=10)

        # Clear Profile — disabled until a profile is loaded
        self._clear_profile_btn = tk.Button(
            tb, text="✕  Clear Profile", command=self._clear_profile,
            bg=self.HEADER_BG, fg=self.SUBTEXT, font=("Helvetica", 11),
            relief="flat", padx=10, pady=6, cursor="hand2", state="disabled",
            disabledforeground="#555570",
        )
        self._clear_profile_btn.pack(side="left", pady=10)

        # App title
        tk.Label(
            tb, text="OSCAL Catalog Viewer",
            bg=self.HEADER_BG, fg=self.TEXT,
            font=("Helvetica", 14, "bold"),
        ).pack(side="left", padx=12)

        # Search (right side)
        tk.Label(tb, text="🔍", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 13)).pack(side="right", padx=(0, 6))
        tk.Entry(
            tb, textvariable=self._search_var,
            bg=self.SIDEBAR_BG, fg=self.TEXT, insertbackground=self.TEXT,
            relief="flat", font=("Helvetica", 11), width=22,
        ).pack(side="right", padx=(0, 12), ipady=4)
        tk.Label(tb, text="Search:", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(side="right")

        # Class filter
        self._class_combo = ttk.Combobox(
            tb, textvariable=self._selected_class,
            values=["All"], state="readonly", width=18,
        )
        self._class_combo.pack(side="right", padx=(0, 8), pady=14)
        self._class_combo.bind("<<ComboboxSelected>>", self._on_filter)
        tk.Label(tb, text="Class:", bg=self.HEADER_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11)).pack(side="right", padx=(16, 4))

    def _build_info_panel(self):
        """Two side-by-side info cards: catalog (left) and profile (right)."""
        panel = tk.Frame(self, bg=self.INFO_BG)
        panel.pack(fill="x", side="top")

        # ── Catalog card ──────────────────────────────────────────────────────
        self._cat_card = tk.Frame(panel, bg=self.CARD_BG,
                                  highlightthickness=1,
                                  highlightbackground=self.HEADER_BG)
        self._cat_card.pack(side="left", fill="x", expand=True,
                            padx=(10, 5), pady=8)

        # header row
        cat_hdr = tk.Frame(self._cat_card, bg=self.HEADER_BG)
        cat_hdr.pack(fill="x")
        tk.Label(cat_hdr, text="📄  Catalog", bg=self.HEADER_BG, fg=self.ACCENT,
                 font=("Helvetica", 10, "bold"), anchor="w",
                 ).pack(side="left", padx=10, pady=4)
        self._cat_title_lbl = tk.Label(
            cat_hdr, text="No catalog loaded",
            bg=self.HEADER_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10, "italic"), anchor="w",
        )
        self._cat_title_lbl.pack(side="left", padx=(0, 10), pady=4)

        # fields row
        self._cat_fields = tk.Frame(self._cat_card, bg=self.CARD_BG)
        self._cat_fields.pack(fill="x", padx=10, pady=6)
        self._cat_version_lbl    = self._info_field(self._cat_fields, "Version",       "—")
        self._cat_oscal_lbl      = self._info_field(self._cat_fields, "OSCAL Version", "—")
        self._cat_published_lbl  = self._info_field(self._cat_fields, "Published",     "—")
        self._cat_modified_lbl   = self._info_field(self._cat_fields, "Last Modified", "—")
        self._cat_controls_lbl   = self._info_field(self._cat_fields, "Controls",      "—")

        # ── Profile card ──────────────────────────────────────────────────────
        self._prof_card = tk.Frame(panel, bg=self.CARD_BG,
                                   highlightthickness=1,
                                   highlightbackground=self.HEADER_BG)
        self._prof_card.pack(side="left", fill="x", expand=True,
                             padx=(5, 10), pady=8)

        # header row
        prof_hdr = tk.Frame(self._prof_card, bg=self.HEADER_BG)
        prof_hdr.pack(fill="x")
        tk.Label(prof_hdr, text="🔖  Profile", bg=self.HEADER_BG, fg=self.YELLOW,
                 font=("Helvetica", 10, "bold"), anchor="w",
                 ).pack(side="left", padx=10, pady=4)
        self._prof_title_lbl = tk.Label(
            prof_hdr, text="No profile loaded",
            bg=self.HEADER_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10, "italic"), anchor="w",
        )
        self._prof_title_lbl.pack(side="left", padx=(0, 10), pady=4)

        # fields row
        self._prof_fields = tk.Frame(self._prof_card, bg=self.CARD_BG)
        self._prof_fields.pack(fill="x", padx=10, pady=6)
        self._prof_version_lbl   = self._info_field(self._prof_fields, "Version",       "—")
        self._prof_oscal_lbl     = self._info_field(self._prof_fields, "OSCAL Version", "—")
        self._prof_published_lbl = self._info_field(self._prof_fields, "Published",     "—")
        self._prof_modified_lbl  = self._info_field(self._prof_fields, "Last Modified", "—")
        self._prof_controls_lbl  = self._info_field(self._prof_fields, "Controls",      "—")

    def _info_field(self, parent, label: str, value: str) -> tk.Label:
        """Create a small label+value pair packed left; returns the value label."""
        frame = tk.Frame(parent, bg=self.CARD_BG)
        frame.pack(side="left", padx=(0, 20))
        tk.Label(frame, text=label, bg=self.CARD_BG, fg=self.SUBTEXT,
                 font=("Helvetica", 9)).pack(anchor="w")
        val_lbl = tk.Label(frame, text=value, bg=self.CARD_BG, fg=self.TEXT,
                           font=("Helvetica", 10, "bold"))
        val_lbl.pack(anchor="w")
        return val_lbl

    def _build_body(self):
        body = tk.PanedWindow(self, orient="horizontal",
                              bg=self.BG, sashwidth=5, sashrelief="flat")
        body.pack(fill="both", expand=True)

        # ── Left: control list ────────────────────────────────────────────────
        left = tk.Frame(body, bg=self.SIDEBAR_BG)
        body.add(left, minsize=380, width=500)

        cols = ("label", "title", "class")
        self._tree = ttk.Treeview(left, columns=cols, show="headings",
                                  selectmode="browse")
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

        # ── Right: detail view ────────────────────────────────────────────────
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

    def _build_statusbar(self):
        sb = tk.Frame(self, bg=self.HEADER_BG, height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(
            sb, text="No catalog loaded — click '📂 Open Catalog' to begin.",
            bg=self.HEADER_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10), anchor="w")
        self._status_lbl.pack(side="left", padx=10)
        self._count_lbl = tk.Label(
            sb, text="", bg=self.HEADER_BG, fg=self.SUBTEXT,
            font=("Helvetica", 10), anchor="e")
        self._count_lbl.pack(side="right", padx=10)

    # ── File Loading ──────────────────────────────────────────────────────────

    def _open_file(self):
        path = filedialog.askopenfilename(
            title="Open OSCAL Catalog",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
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

        # Class filter
        classes = sorted({c["class"] for c in self._all_controls if c["class"]})
        self._class_combo["values"] = ["All"] + classes
        self._selected_class.set("All")
        self._search_var.set("")

        # Update catalog info card
        self._cat_title_lbl.config(text=catalog["title"], fg=self.TEXT)
        self._cat_version_lbl.config(text=catalog["version"])
        self._cat_oscal_lbl.config(text=catalog["oscal_version"])
        self._cat_published_lbl.config(text=catalog["published"])
        self._cat_modified_lbl.config(text=catalog["last_modified"])
        self._cat_controls_lbl.config(text=str(len(catalog["controls"])))

        self._prof_title_lbl.config(text="No profile loaded", fg=self.SUBTEXT)
        self._prof_version_lbl.config(text="—")
        self._prof_oscal_lbl.config(text="—")
        self._prof_published_lbl.config(text="—")
        self._prof_modified_lbl.config(text="—")
        self._prof_controls_lbl.config(text="—")
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
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            profile = load_profile(path)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            messagebox.showerror("Failed to load profile", str(exc))
            return

        self._profile = profile
        self._clear_profile_btn.config(state="normal")

        # Update profile info card
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

        # Reset profile info card
        self._prof_title_lbl.config(text="No profile loaded", fg=self.SUBTEXT)
        self._prof_version_lbl.config(text="—")
        self._prof_oscal_lbl.config(text="—")
        self._prof_published_lbl.config(text="—")
        self._prof_modified_lbl.config(text="—")
        self._prof_controls_lbl.config(text="—")

        self._apply_filters()
        self._show_placeholder()
        self._status_lbl.config(text="Profile cleared — showing full catalog.")

    # ── Tree Population ───────────────────────────────────────────────────────

    def _populate_tree(self, controls: list):
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

    # ── Filtering / Searching ─────────────────────────────────────────────────

    def _apply_filters(self):
        if not self._all_controls:
            return
        cls  = self._selected_class.get()
        term = self._search_var.get().lower().strip()
        result = self._all_controls

        if self._profile:
            profile_ids = self._profile["ids"]
            result = [c for c in result if c["id"] in profile_ids]
        if cls != "All":
            result = [c for c in result if c["class"] == cls]
        if term:
            result = [
                c for c in result
                if term in c["title"].lower()
                or term in c["label"].lower()
                or term in c["statement"].lower()
                or term in c["id"].lower()
            ]
        self._populate_tree(result)
        self._show_placeholder()

    def _on_filter(self, _event=None):
        self._apply_filters()

    def _on_search(self, *_):
        self._apply_filters()

    # ── Selection / Detail ────────────────────────────────────────────────────

    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        ctrl = self._filtered_controls[idx]
        self._show_detail(ctrl)

    def _show_placeholder(self):
        for w in self._detail_frame.winfo_children():
            w.destroy()
        msg = ("Select a control from the list to view details."
               if self._catalog else
               "Open an OSCAL catalog file to get started.")
        tk.Label(
            self._detail_frame, text=msg,
            bg=self.BG, fg=self.SUBTEXT,
            font=("Helvetica", 13, "italic"),
            wraplength=400, justify="center",
        ).pack(expand=True, pady=80, padx=40)

    def _show_detail(self, ctrl: dict):
        for w in self._detail_frame.winfo_children():
            w.destroy()

        pad = dict(padx=22)

        # Header: badge + title/statement
        header = tk.Frame(self._detail_frame, bg=self.HEADER_BG)
        header.pack(fill="x", **pad, pady=(18, 4))

        badge_fg = self.TEAL if ctrl["class"] == "ISM-principle" else self.BLUE
        tk.Label(
            header, text=f"  {ctrl['label']}  ",
            bg=badge_fg, fg=self.BG,
            font=("Helvetica", 12, "bold"), relief="flat",
        ).pack(side="left", padx=10, pady=8)

        has_real_title = ctrl["title"] and not ctrl["title"].lower().startswith("control:")
        header_text = ctrl["title"] if has_real_title else ctrl["statement"]
        tk.Label(
            header, text=header_text,
            bg=self.HEADER_BG, fg=self.TEXT,
            font=("Helvetica", 13, "bold"),
            wraplength=480, justify="left",
        ).pack(side="left", padx=6, pady=8, fill="x", expand=True)

        # Breadcrumb
        self._row(self._detail_frame, "Category", ctrl["path"],
                  value_color=self.SUBTEXT, italic=True)

        tk.Frame(self._detail_frame, bg=self.HEADER_BG, height=1).pack(
            fill="x", padx=22, pady=6)

        # Metadata fields
        self._row(self._detail_frame, "Control ID", ctrl["id"])
        self._row(self._detail_frame, "Class",      ctrl["class"])
        if ctrl["revision"] != "—":
            self._row(self._detail_frame, "Revision", ctrl["revision"])
        if ctrl["updated"] != "—":
            self._row(self._detail_frame, "Updated",  ctrl["updated"])
        if ctrl["essential_eight"] != "—":
            self._row(self._detail_frame, "Essential Eight", ctrl["essential_eight"],
                      value_color=self.YELLOW)

        # Applicability chips
        if ctrl["applicability"]:
            chip_frame = tk.Frame(self._detail_frame, bg=self.BG)
            chip_frame.pack(fill="x", **pad, pady=4)
            tk.Label(chip_frame, text="Applicability:",
                     bg=self.BG, fg=self.SUBTEXT,
                     font=("Helvetica", 11, "bold"),
                     width=14, anchor="w").pack(side="left")
            for ap in ctrl["applicability"]:
                tk.Label(chip_frame, text=f" {ap} ",
                         bg=self.GREEN, fg=self.BG,
                         font=("Helvetica", 10, "bold"),
                         relief="flat").pack(side="left", padx=3)

        tk.Frame(self._detail_frame, bg=self.HEADER_BG, height=1).pack(
            fill="x", padx=22, pady=8)

        # Statement
        if ctrl["statement"]:
            tk.Label(
                self._detail_frame, text="Statement",
                bg=self.BG, fg=self.ACCENT,
                font=("Helvetica", 12, "bold"),
            ).pack(anchor="w", **pad, pady=(4, 2))

            stmt_box = tk.Frame(self._detail_frame, bg=self.SIDEBAR_BG,
                                highlightthickness=1,
                                highlightbackground=self.HEADER_BG)
            stmt_box.pack(fill="x", padx=22, pady=4)
            tk.Label(
                stmt_box, text=ctrl["statement"],
                bg=self.SIDEBAR_BG, fg=self.TEXT,
                font=("Helvetica", 12),
                wraplength=520, justify="left", anchor="nw",
            ).pack(padx=14, pady=12, fill="x")

        tk.Frame(self._detail_frame, bg=self.BG, height=30).pack()

    def _row(self, parent, label: str, value: str,
             value_color=None, italic: bool = False):
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill="x", padx=22, pady=2)
        tk.Label(frame, text=f"{label}:",
                 bg=self.BG, fg=self.SUBTEXT,
                 font=("Helvetica", 11, "bold"),
                 width=14, anchor="w").pack(side="left")
        font = ("Helvetica", 11, "italic") if italic else ("Helvetica", 11)
        tk.Label(frame, text=value,
                 bg=self.BG, fg=value_color or self.TEXT,
                 font=font, wraplength=500,
                 justify="left", anchor="w").pack(side="left", fill="x", expand=True)

    # ── Scroll / Layout Helpers ───────────────────────────────────────────────

    def _on_detail_configure(self, _event):
        self._detail_canvas.configure(
            scrollregion=self._detail_canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._detail_canvas.itemconfig(self._detail_window, width=event.width)

    def _on_mousewheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        canvas = self._detail_canvas
        if widget and (widget is canvas or str(widget).startswith(str(canvas))):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _update_count(self):
        total = len(self._all_controls)
        shown = len(self._filtered_controls)
        if total == 0:
            self._count_lbl.config(text="")
        elif shown == total:
            self._count_lbl.config(text=f"{total} controls")
        else:
            self._count_lbl.config(text=f"Showing {shown} of {total} controls")


# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = OSCALViewer()
    app.mainloop()
