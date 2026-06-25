"""
app.py (Option 2) — Main application window.
Tab classes are proper tk.Frame subclasses; the app communicates
with them only through their public API and injected callbacks.
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import load_catalog, load_profile
from .catalog_tab import CatalogTab
from .ssp_tab import SSPTab

# Colour palette shared with all tabs via a dict
COLORS = {
    "BG":         "#1e1e2e",
    "SIDEBAR_BG": "#181825",
    "HEADER_BG":  "#313244",
    "INFO_BG":    "#252535",
    "CARD_BG":    "#2a2a3d",
    "ACCENT":     "#cba6f7",
    "TEXT":       "#cdd6f4",
    "SUBTEXT":    "#a6adc8",
    "GREEN":      "#a6e3a1",
    "YELLOW":     "#f9e2af",
    "RED":        "#f38ba8",
    "BLUE":       "#89b4fa",
    "TEAL":       "#94e2d5",
    "ORANGE":     "#fab387",
}


class OSCALApp(tk.Tk):

    # Expose colours as class attributes for convenience
    for _k, _v in COLORS.items():
        locals()[_k] = _v

    def __init__(self):
        super().__init__()
        self.title("OSCAL User Toolkit")
        self.geometry("1340x900")
        self.minsize(1000, 700)
        self.configure(bg=COLORS["BG"])

        self._catalog = None
        self._profile = None
        self._selected_class = tk.StringVar(value="All")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)

        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._style_ttk()
        self._build_toolbar()
        self._build_info_panel()
        self._build_notebook()
        self._build_statusbar()

    def _style_ttk(self):
        C = COLORS
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview",
                    background=C["SIDEBAR_BG"], foreground=C["TEXT"],
                    fieldbackground=C["SIDEBAR_BG"], borderwidth=0,
                    font=("Helvetica", 11), rowheight=26)
        s.configure("Treeview.Heading",
                    background=C["HEADER_BG"], foreground=C["ACCENT"],
                    font=("Helvetica", 11, "bold"), relief="flat")
        s.map("Treeview",
              background=[("selected", C["ACCENT"])],
              foreground=[("selected", C["BG"])])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar",
                        background=C["HEADER_BG"], troughcolor=C["SIDEBAR_BG"],
                        borderwidth=0, arrowcolor=C["SUBTEXT"])
        s.configure("TCombobox",
                    fieldbackground=C["HEADER_BG"], background=C["HEADER_BG"],
                    foreground=C["TEXT"], selectbackground=C["ACCENT"],
                    selectforeground=C["BG"])
        s.map("TCombobox",
              fieldbackground=[("readonly", C["HEADER_BG"])],
              foreground=[("readonly", C["TEXT"])])
        s.configure("TNotebook", background=C["BG"], borderwidth=0)
        s.configure("TNotebook.Tab",
                    background=C["HEADER_BG"], foreground=C["SUBTEXT"],
                    padding=[14, 6], font=("Helvetica", 11))
        s.map("TNotebook.Tab",
              background=[("selected", C["CARD_BG"])],
              foreground=[("selected", C["ACCENT"])])

    def _build_toolbar(self):
        C = COLORS
        tb = tk.Frame(self, bg=C["HEADER_BG"], height=54)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        tk.Button(tb, text="📂  Open Catalog", command=self._open_catalog,
                  bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 12, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  activebackground="#b4befe", activeforeground=C["BG"],
                  ).pack(side="left", padx=14, pady=10)

        tk.Button(tb, text="🔖  Open Profile", command=self._open_profile,
                  bg=C["YELLOW"], fg=C["BG"], font=("Helvetica", 12, "bold"),
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  activebackground="#f5c842", activeforeground=C["BG"],
                  ).pack(side="left", padx=(0, 8), pady=10)

        self._clear_profile_btn = tk.Button(
            tb, text="✕  Clear Profile", command=self._clear_profile,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 11),
            relief="flat", padx=10, pady=6, cursor="hand2", state="disabled",
            disabledforeground="#555570")
        self._clear_profile_btn.pack(side="left", pady=10)

        tk.Label(tb, text="OSCAL User Toolkit",
                 bg=C["HEADER_BG"], fg=C["TEXT"],
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=12)

        tk.Label(tb, text="🔍", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 13)).pack(side="right", padx=(0, 6))
        tk.Entry(tb, textvariable=self._search_var,
                 bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), width=22,
                 ).pack(side="right", padx=(0, 12), ipady=4)
        tk.Label(tb, text="Search:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="right")
        self._class_combo = ttk.Combobox(
            tb, textvariable=self._selected_class,
            values=["All"], state="readonly", width=18)
        self._class_combo.pack(side="right", padx=(0, 8), pady=14)
        self._class_combo.bind("<<ComboboxSelected>>", self._on_filter)
        tk.Label(tb, text="Class:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="right", padx=(16, 4))

    def _build_info_panel(self):
        C = COLORS
        panel = tk.Frame(self, bg=C["INFO_BG"])
        panel.pack(fill="x", side="top")

        def card(icon, label_text, fg, side_padx):
            c = tk.Frame(panel, bg=C["CARD_BG"],
                         highlightthickness=1, highlightbackground=C["HEADER_BG"])
            c.pack(side="left", fill="x", expand=True, padx=side_padx, pady=8)
            hdr = tk.Frame(c, bg=C["HEADER_BG"])
            hdr.pack(fill="x")
            tk.Label(hdr, text=f"{icon}  {label_text}", bg=C["HEADER_BG"], fg=fg,
                     font=("Helvetica", 10, "bold"), anchor="w").pack(side="left", padx=10, pady=4)
            title_lbl = tk.Label(hdr, text=f"No {label_text.lower()} loaded",
                                 bg=C["HEADER_BG"], fg=C["SUBTEXT"],
                                 font=("Helvetica", 10, "italic"), anchor="w")
            title_lbl.pack(side="left", padx=(0, 10), pady=4)
            ff = tk.Frame(c, bg=C["CARD_BG"])
            ff.pack(fill="x", padx=10, pady=6)
            return title_lbl, ff

        def field(parent, label):
            f = tk.Frame(parent, bg=C["CARD_BG"])
            f.pack(side="left", padx=(0, 20))
            tk.Label(f, text=label, bg=C["CARD_BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 9)).pack(anchor="w")
            lbl = tk.Label(f, text="—", bg=C["CARD_BG"], fg=C["TEXT"],
                           font=("Helvetica", 10, "bold"))
            lbl.pack(anchor="w")
            return lbl

        self._cat_title_lbl, cf = card("📄", "Catalog", C["ACCENT"], (10, 5))
        self._cat_version_lbl   = field(cf, "Version")
        self._cat_oscal_lbl     = field(cf, "OSCAL Version")
        self._cat_published_lbl = field(cf, "Published")
        self._cat_modified_lbl  = field(cf, "Last Modified")
        self._cat_controls_lbl  = field(cf, "Controls")

        self._prof_title_lbl, pf = card("🔖", "Profile", C["YELLOW"], (5, 10))
        self._prof_version_lbl   = field(pf, "Version")
        self._prof_oscal_lbl     = field(pf, "OSCAL Version")
        self._prof_published_lbl = field(pf, "Published")
        self._prof_modified_lbl  = field(pf, "Last Modified")
        self._prof_controls_lbl  = field(pf, "Controls")

    def _build_notebook(self):
        C = COLORS
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._notebook = nb

        # CatalogTab: inject callbacks, no shared state
        self._catalog_tab = CatalogTab(
            nb, C,
            on_select=lambda ctrl: None,   # detail shown inside CatalogTab itself
            get_catalog=lambda: self._catalog,
        )
        nb.add(self._catalog_tab, text="📋  Catalog Viewer")

        # SSPTab: inject get_profile, get_catalog, set_status callbacks
        self._ssp_tab = SSPTab(
            nb, C,
            get_profile=lambda: self._profile,
            get_catalog=lambda: self._catalog,
            set_status=lambda msg: self._status_lbl.config(text=msg),
        )
        nb.add(self._ssp_tab, text="🛡  SSP Editor")

    def _build_statusbar(self):
        C = COLORS
        sb = tk.Frame(self, bg=C["HEADER_BG"], height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)
        self._status_lbl = tk.Label(
            sb, text="No catalog loaded — click '📂 Open Catalog' to begin.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10), anchor="w")
        self._status_lbl.pack(side="left", padx=10)
        self._count_lbl = tk.Label(
            sb, text="", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10), anchor="e")
        self._count_lbl.pack(side="right", padx=10)

    # ── File loading ──────────────────────────────────────────────────────────

    def _open_catalog(self):
        C = COLORS
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
        classes = sorted({c["class"] for c in catalog["controls"] if c["class"]})
        self._class_combo["values"] = ["All"] + classes
        self._selected_class.set("All")
        self._search_var.set("")
        # Update info panel
        self._cat_title_lbl.config(text=catalog["title"], fg=C["TEXT"])
        self._cat_version_lbl.config(text=catalog["version"])
        self._cat_oscal_lbl.config(text=catalog["oscal_version"])
        self._cat_published_lbl.config(text=catalog["published"])
        self._cat_modified_lbl.config(text=catalog["last_modified"])
        self._cat_controls_lbl.config(text=str(len(catalog["controls"])))
        self._prof_title_lbl.config(text="No profile loaded", fg=C["SUBTEXT"])
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")
        self._clear_profile_btn.config(state="disabled")
        # Delegate to tab
        self._catalog_tab.load_controls(catalog["controls"])
        self._ssp_tab.refresh_profile_box()
        self._status_lbl.config(text=f"Loaded catalog: {Path(path).name}")
        self._update_count()

    def _open_profile(self):
        C = COLORS
        if not self._catalog:
            messagebox.showwarning("No catalog loaded",
                                   "Please open a catalog before loading a profile.")
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
        self._prof_title_lbl.config(text=profile["title"], fg=C["YELLOW"])
        self._prof_version_lbl.config(text=profile["version"])
        self._prof_oscal_lbl.config(text=profile["oscal_version"])
        self._prof_published_lbl.config(text=profile["published"])
        self._prof_modified_lbl.config(text=profile["last_modified"])
        self._prof_controls_lbl.config(text=str(len(profile["ids"])))
        self._ssp_tab.refresh_profile_box()
        self._apply_filters()
        self._status_lbl.config(text=f"Profile applied: {Path(path).name}")

    def _clear_profile(self):
        C = COLORS
        self._profile = None
        self._clear_profile_btn.config(state="disabled")
        self._prof_title_lbl.config(text="No profile loaded", fg=C["SUBTEXT"])
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")
        self._ssp_tab.refresh_profile_box()
        self._apply_filters()
        self._status_lbl.config(text="Profile cleared — showing full catalog.")

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _apply_filters(self):
        if not self._catalog:
            return
        profile_ids = self._profile["ids"] if self._profile else None
        self._catalog_tab.apply_filters(
            profile_ids=profile_ids,
            class_filter=self._selected_class.get(),
            search_term=self._search_var.get(),
        )
        self._update_count()

    def _on_filter(self, _=None): self._apply_filters()
    def _on_search(self, *_):    self._apply_filters()

    def _update_count(self):
        total, shown = self._catalog_tab.control_count()
        if total == 0:
            self._count_lbl.config(text="")
        elif shown == total:
            self._count_lbl.config(text=f"{total} controls")
        else:
            self._count_lbl.config(text=f"Showing {shown} of {total} controls")
