"""
catalog_tab.py (Option 2) — CatalogTab is a proper tk.Frame subclass.
It owns its own widgets and state, and communicates back to the app
via callbacks passed in at construction time.
"""

import tkinter as tk
from tkinter import ttk


class CatalogTab(tk.Frame):
    """
    Self-contained catalog viewer panel.

    Callbacks injected by the app:
      on_select(ctrl)   — called when the user clicks a control row
      get_catalog()     — returns the currently loaded catalog dict or None
    """

    def __init__(self, parent, colors, on_select, get_catalog):
        super().__init__(parent, bg=colors["BG"])
        self._colors      = colors
        self._on_select   = on_select
        self._get_catalog = get_catalog

        self._all_controls      = []
        self._filtered_controls = []

        self._build()

    # ── Public API ────────────────────────────────────────────────────────────

    def load_controls(self, controls):
        """Replace the full control list and redisplay."""
        self._all_controls = controls
        self._filtered_controls = list(controls)
        self._populate_tree(controls)
        self._show_placeholder()

    def apply_filters(self, profile_ids=None, class_filter="All", search_term=""):
        result = self._all_controls
        if profile_ids is not None:
            result = [c for c in result if c["id"] in profile_ids]
        if class_filter != "All":
            result = [c for c in result if c["class"] == class_filter]
        if search_term:
            t = search_term.lower()
            result = [c for c in result
                      if t in c["title"].lower()
                      or t in c["label"].lower()
                      or t in c["statement"].lower()
                      or t in c["id"].lower()]
        self._populate_tree(result)
        self._show_placeholder()

    def control_count(self):
        return len(self._all_controls), len(self._filtered_controls)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        C = self._colors
        body = tk.PanedWindow(self, orient="horizontal",
                              bg=C["BG"], sashwidth=5, sashrelief="flat")
        body.pack(fill="both", expand=True)

        # Left: control list
        left = tk.Frame(body, bg=C["SIDEBAR_BG"])
        body.add(left, minsize=380, width=520)

        cols = ("label", "title", "class")
        self._tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="browse")
        self._tree.heading("label", text="ID / Label",        anchor="w")
        self._tree.heading("title", text="Title / Statement", anchor="w")
        self._tree.heading("class", text="Class",             anchor="w")
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
        self._tree.bind("<<TreeviewSelect>>", self._tree_selected)

        # Right: detail canvas
        right = tk.Frame(body, bg=C["BG"])
        body.add(right, minsize=340)
        self._canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb2 = ttk.Scrollbar(right, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)
        self._detail = tk.Frame(self._canvas, bg=C["BG"])
        self._win = self._canvas.create_window((0, 0), window=self._detail, anchor="nw")
        self._detail.bind("<Configure>", self._on_detail_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._show_placeholder()

    # ── Tree ──────────────────────────────────────────────────────────────────

    def _populate_tree(self, controls):
        C = self._colors
        self._tree.delete(*self._tree.get_children())
        for i, ctrl in enumerate(controls):
            tag = "principle" if ctrl["class"] == "ISM-principle" else "control"
            display = ctrl["title"]
            if display.lower().startswith("control:") or not display:
                display = ctrl["statement"]
            self._tree.insert("", "end", iid=str(i),
                              values=(ctrl["label"], display, ctrl["class"]),
                              tags=(tag,))
        self._tree.tag_configure("principle", foreground=C["TEAL"])
        self._tree.tag_configure("control",   foreground=C["TEXT"])
        self._filtered_controls = controls

    def _tree_selected(self, _=None):
        sel = self._tree.selection()
        if not sel:
            return
        ctrl = self._filtered_controls[int(sel[0])]
        self._on_select(ctrl)
        self._show_detail(ctrl)

    # ── Detail view ───────────────────────────────────────────────────────────

    def _show_placeholder(self):
        for w in self._detail.winfo_children():
            w.destroy()
        C = self._colors
        has_catalog = self._get_catalog() is not None
        msg = ("Select a control to view details."
               if has_catalog else
               "Open an OSCAL catalog file to get started.")
        tk.Label(self._detail, text=msg, bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 13, "italic"),
                 wraplength=400, justify="center",
                 ).pack(expand=True, pady=80, padx=40)

    def _show_detail(self, ctrl):
        for w in self._detail.winfo_children():
            w.destroy()
        C = self._colors
        pad = dict(padx=22)

        header = tk.Frame(self._detail, bg=C["HEADER_BG"])
        header.pack(fill="x", **pad, pady=(18, 4))
        badge_fg = C["TEAL"] if ctrl["class"] == "ISM-principle" else C["BLUE"]
        tk.Label(header, text=f"  {ctrl['label']}  ",
                 bg=badge_fg, fg=C["BG"],
                 font=("Helvetica", 12, "bold"), relief="flat",
                 ).pack(side="left", padx=10, pady=8)
        has_title = ctrl["title"] and not ctrl["title"].lower().startswith("control:")
        tk.Label(header,
                 text=ctrl["title"] if has_title else ctrl["statement"],
                 bg=C["HEADER_BG"], fg=C["TEXT"],
                 font=("Helvetica", 13, "bold"),
                 wraplength=480, justify="left",
                 ).pack(side="left", padx=6, pady=8, fill="x", expand=True)

        self._row("Category", ctrl["path"], value_color=C["SUBTEXT"], italic=True)
        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(fill="x", padx=22, pady=6)
        self._row("Control ID", ctrl["id"])
        self._row("Class",      ctrl["class"])
        if ctrl["revision"] != "—":
            self._row("Revision", ctrl["revision"])
        if ctrl["updated"] != "—":
            self._row("Updated",  ctrl["updated"])
        if ctrl["essential_eight"] != "—":
            self._row("Essential Eight", ctrl["essential_eight"], value_color=C["YELLOW"])

        if ctrl["applicability"]:
            cf = tk.Frame(self._detail, bg=C["BG"])
            cf.pack(fill="x", **pad, pady=4)
            tk.Label(cf, text="Applicability:", bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11, "bold"), width=14, anchor="w").pack(side="left")
            for ap in ctrl["applicability"]:
                tk.Label(cf, text=f" {ap} ", bg=C["GREEN"], fg=C["BG"],
                         font=("Helvetica", 10, "bold"), relief="flat",
                         ).pack(side="left", padx=3)

        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(fill="x", padx=22, pady=8)

        if ctrl["statement"]:
            tk.Label(self._detail, text="Statement",
                     bg=C["BG"], fg=C["ACCENT"],
                     font=("Helvetica", 12, "bold"),
                     ).pack(anchor="w", **pad, pady=(4, 2))
            box = tk.Frame(self._detail, bg=C["SIDEBAR_BG"],
                           highlightthickness=1, highlightbackground=C["HEADER_BG"])
            box.pack(fill="x", padx=22, pady=4)
            tk.Label(box, text=ctrl["statement"],
                     bg=C["SIDEBAR_BG"], fg=C["TEXT"],
                     font=("Helvetica", 12),
                     wraplength=520, justify="left", anchor="nw",
                     ).pack(padx=14, pady=12, fill="x")

        tk.Frame(self._detail, bg=C["BG"], height=30).pack()

    def _row(self, label, value, value_color=None, italic=False):
        C = self._colors
        frame = tk.Frame(self._detail, bg=C["BG"])
        frame.pack(fill="x", padx=22, pady=2)
        tk.Label(frame, text=f"{label}:", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11, "bold"), width=14, anchor="w").pack(side="left")
        tk.Label(frame, text=value, bg=C["BG"], fg=value_color or C["TEXT"],
                 font=("Helvetica", 11, "italic") if italic else ("Helvetica", 11),
                 wraplength=500, justify="left", anchor="w",
                 ).pack(side="left", fill="x", expand=True)

    # ── Scroll helpers ────────────────────────────────────────────────────────

    def _on_detail_configure(self, _):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, e):
        self._canvas.itemconfig(self._win, width=e.width)

    def _on_mousewheel(self, e):
        widget = self.winfo_containing(e.x_root, e.y_root)
        if widget and (widget is self._canvas
                       or str(widget).startswith(str(self._canvas))):
            self._canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
