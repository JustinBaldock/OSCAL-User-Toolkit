"""
catalog_tab.py
==============
This file defines the CatalogTab class — the Catalog Viewer tab of the
OSCAL User Toolkit.

WHAT MOVED HERE
---------------
Previously, the class filter dropdown, search box, and control count label
lived in the main application toolbar (app.py) — visible on every tab.
They have been moved into this tab's own filter toolbar because:
  - They only affect the catalog list; they are irrelevant on other tabs
  - Keeping them here makes the main toolbar cleaner
  - CatalogTab is fully self-contained: it owns its own filter state

DESIGN PATTERN
--------------
CatalogTab inherits from tk.Frame, so it IS a GUI widget (a panel).
It owns its filter state (_profile_ids, _selected_class, _search_var)
and applies all three filters itself whenever any one of them changes.

The main app communicates with CatalogTab only through:
  - tab.load_controls(controls) — called when a catalog is loaded
  - tab.apply_profile(profile_ids) — called when a profile is loaded/cleared
"""

import tkinter as tk
from tkinter import ttk


class CatalogTab(tk.Frame):
    """
    A self-contained catalog viewer panel.

    Layout:
      TOP    — Filter toolbar (Class dropdown, Search box, Count label)
      BOTTOM — Horizontal split pane:
                 LEFT  — Control list (Treeview + scrollbars)
                 RIGHT — Control detail view (scrollable canvas)

    Callbacks injected at construction time:
        on_select(ctrl)   Called when the user clicks a control row.
        get_catalog()     Returns the catalog dict, or None if not loaded.
    """

    def __init__(self, parent, colors, on_select, get_catalog):
        """
        Initialise the CatalogTab.

        Parameters:
            parent      - The ttk.Notebook this tab lives inside
            colors      - Shared colour dictionary from app.py
            on_select   - Callback: called with the ctrl dict when a row is clicked
            get_catalog - Callback: returns the catalog dict, or None
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors      = colors
        self._on_select   = on_select
        self._get_catalog = get_catalog

        # ── Filter state owned entirely by this tab ───────────────────────────
        self._all_controls      = []    # Full list from the loaded catalog
        self._filtered_controls = []    # Currently visible subset

        # Profile IDs from the loaded profile, or None for no profile filter.
        # Set by apply_profile() which is called by the main app.
        self._profile_ids = None

        # StringVars for filter dropdowns and the search box.
        self._selected_class     = tk.StringVar(value="All")
        self._selected_guideline = tk.StringVar(value="All")
        self._search_var         = tk.StringVar()
        self._wrap_labels        = []   # labels whose wraplength tracks canvas width

        # trace_add("write", fn) calls fn whenever the search box changes,
        # enabling live filtering as the user types.
        self._search_var.trace_add("write", self._on_search)

        self._build()

    # =========================================================================
    # PUBLIC API — called by app.py
    # =========================================================================

    def load_controls(self, controls):
        """
        Replace the full control list with a new catalog's controls.

        Called by app.py after a catalog is loaded. Resets the class
        dropdown options, clears the search box, clears the profile filter,
        and refreshes the tree display.

        Parameters:
            controls - Flat list of control dicts from models.collect_controls()
        """
        self._all_controls      = controls
        self._filtered_controls = list(controls)
        self._profile_ids       = None   # New catalog clears any profile filter

        # Populate filter dropdowns with unique values from this catalog.
        classes    = sorted({c["class"]     for c in controls if c["class"]})
        guidelines = sorted({c["guideline"] for c in controls if c.get("guideline")})
        self._class_combo["values"]     = ["All"] + classes
        self._guideline_combo["values"] = ["All"] + guidelines
        self._selected_class.set("All")
        self._selected_guideline.set("All")
        self._search_var.set("")

        self._populate_tree(controls)
        self._show_placeholder()
        self._update_count()

    def apply_profile(self, profile_ids):
        """
        Apply or remove the profile filter, then re-run all filters.

        Called by app.py when the user loads or clears a profile.
        The tab's own class filter and search term are kept unchanged —
        only the profile filter is updated.

        Parameters:
            profile_ids - A set of control ID strings to include,
                          or None to remove the profile filter entirely.
        """
        self._profile_ids = profile_ids
        self._apply_filters()

    def control_count(self):
        """
        Return (total_controls, visible_controls) as a tuple.
        Available to any external caller that needs the counts.
        """
        return len(self._all_controls), len(self._filtered_controls)

    # =========================================================================
    # PRIVATE BUILD METHODS
    # =========================================================================

    def _build(self):
        """Build the filter toolbar, then the split-pane body below it."""
        self._build_filter_toolbar()
        self._build_body()

    def _build_filter_toolbar(self):
        """
        Create the filter toolbar at the top of the Catalog Viewer tab.

        Contains (left to right):
          - Class label + dropdown  — filter by ISM-control, ISM-principle, or All
          - Search label + entry    — live text search
          - Search icon             — visual hint
          - Count label (right)     — "1150 controls" or "Showing 42 of 1150"

        Everything in this toolbar is owned by this tab — the main toolbar
        only has Open Catalog, Open Profile, and Clear Profile.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["HEADER_BG"], height=40)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)   # Fix toolbar height at 40px

        # ── Class filter ──────────────────────────────────────────────────────
        tk.Label(
            tb, text="Class:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="left", padx=(14, 4), pady=8)

        self._class_combo = ttk.Combobox(
            tb, textvariable=self._selected_class,
            values=["All"],    # Populated by load_controls() after a catalog loads
            state="readonly",
            width=14,
        )
        self._class_combo.pack(side="left", pady=8)
        self._class_combo.bind("<<ComboboxSelected>>", self._on_class_filter)

        # ── Guideline filter ──────────────────────────────────────────────────
        tk.Label(
            tb, text="Guideline:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="left", padx=(16, 4), pady=8)

        self._guideline_combo = ttk.Combobox(
            tb, textvariable=self._selected_guideline,
            values=["All"],    # Populated by load_controls()
            state="readonly",
            width=32,
        )
        self._guideline_combo.pack(side="left", pady=8)
        self._guideline_combo.bind("<<ComboboxSelected>>", self._on_guideline_filter)

        # ── Search box ────────────────────────────────────────────────────────
        tk.Label(
            tb, text="Search:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="left", padx=(16, 4))

        tk.Entry(
            tb, textvariable=self._search_var,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11), width=24,
        ).pack(side="left", ipady=4)

        tk.Label(
            tb, text="🔍", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 12),
        ).pack(side="left", padx=(4, 0))

        # ── Control count (right side) ────────────────────────────────────────
        # Updated by _update_count() whenever filters are applied.
        # Shows "1150 controls" when nothing is filtered, or
        # "Showing 42 of 1150 controls" when a filter is active.
        self._count_lbl = tk.Label(
            tb, text="",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10), anchor="e",
        )
        self._count_lbl.pack(side="right", padx=14)

    def _build_body(self):
        """
        Create the split pane below the filter toolbar:
          LEFT  — Control list (Treeview)
          RIGHT — Control detail canvas
        """
        C    = self._colors
        body = tk.PanedWindow(
            self, orient="horizontal",
            bg=C["BG"], sashwidth=5, sashrelief="flat",
        )
        body.pack(fill="both", expand=True)

        self._build_control_list(body)
        self._build_detail_pane(body)

    def _build_control_list(self, body):
        """
        Build the left pane: a Treeview showing all controls,
        with vertical and horizontal scrollbars.
        """
        C    = self._colors
        left = tk.Frame(body, bg=C["SIDEBAR_BG"])
        body.add(left, minsize=600, width=850)

        cols = ("label", "title", "class", "guideline")
        self._tree = ttk.Treeview(
            left, columns=cols, show="headings", selectmode="browse"
        )
        self._tree.heading("label",     text="ID / Label",        anchor="w")
        self._tree.heading("title",     text="Title / Statement", anchor="w")
        self._tree.heading("class",     text="Class",             anchor="w")
        self._tree.heading("guideline", text="Guideline",         anchor="w")
        self._tree.column("label",     width=110, minwidth=80,  anchor="w", stretch=False)
        self._tree.column("title",     width=260, minwidth=150, anchor="w", stretch=True)
        self._tree.column("class",     width=110, minwidth=80,  anchor="w", stretch=False)
        self._tree.column("guideline", width=260, minwidth=160, anchor="w", stretch=False)

        # Scrollbars must know which widget they scroll (command=...)
        # and the widget must know which scrollbar to update (yscrollcommand=...)
        vsb = ttk.Scrollbar(left, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # grid() lets us place widgets in a row/column table layout
        self._tree.grid(row=0, column=0, sticky="nsew")  # fills all space
        vsb.grid(row=0, column=1, sticky="ns")            # right edge
        hsb.grid(row=1, column=0, sticky="ew")            # bottom edge
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        self._tree.bind("<<TreeviewSelect>>", self._tree_selected)

    def _build_detail_pane(self, body):
        """
        Build the right pane: a scrollable canvas showing the full detail
        of the selected control.
        """
        C     = self._colors
        right = tk.Frame(body, bg=C["BG"])
        body.add(right, minsize=340)

        # Canvas + scrollbar for vertical scrolling
        self._canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        # Inner frame placed inside the canvas at position (0,0)
        self._detail = tk.Frame(self._canvas, bg=C["BG"])
        self._win = self._canvas.create_window(
            (0, 0), window=self._detail, anchor="nw"
        )

        # Resize events keep the scroll region and frame width in sync
        self._detail.bind("<Configure>", self._on_detail_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._show_placeholder()

    # =========================================================================
    # FILTERING
    # =========================================================================

    def _apply_filters(self):
        """
        Apply all three active filters and refresh the tree.

        Called internally whenever any filter state changes:
          - apply_profile() changes _profile_ids
          - _on_class_filter() changes _selected_class
          - _on_search() changes _search_var
        """
        result = self._all_controls

        # ── 1. Profile filter ─────────────────────────────────────────────────
        # Keep only controls whose ID is in the profile's set of selected IDs.
        # 'in' on a set is O(1) — very fast even for 1000+ controls.
        if self._profile_ids is not None:
            result = [c for c in result if c["id"] in self._profile_ids]

        # ── 2. Class filter ───────────────────────────────────────────────────
        cls = self._selected_class.get()
        if cls != "All":
            result = [c for c in result if c["class"] == cls]

        # ── 3. Guideline filter ───────────────────────────────────────────────
        guideline = self._selected_guideline.get()
        if guideline != "All":
            result = [c for c in result if c.get("guideline") == guideline]

        # ── 4. Text search ────────────────────────────────────────────────────
        term = self._search_var.get().lower()
        if term:
            result = [
                c for c in result
                if term in c["title"].lower()
                or term in c["label"].lower()
                or term in c["statement"].lower()
                or term in c["id"].lower()
                or term in c.get("guideline", "").lower()
            ]

        self._populate_tree(result)
        self._show_placeholder()
        self._update_count()

    def _on_class_filter(self, _event=None):
        """Called when the user picks a class from the dropdown."""
        self._apply_filters()

    def _on_guideline_filter(self, _event=None):
        """Called when the user picks a guideline from the dropdown."""
        self._apply_filters()

    def _on_search(self, *_args):
        """
        Called automatically every time the search box content changes.
        *_args absorbs the three arguments tkinter passes to trace callbacks.
        """
        self._apply_filters()

    def _update_count(self):
        """
        Update the count label to show how many controls are currently visible.

        Examples:
            "1150 controls"              — no filter active
            "Showing 42 of 1150 controls" — some filter active
        """
        total = len(self._all_controls)
        shown = len(self._filtered_controls)
        if total == 0:
            self._count_lbl.config(text="")
        elif shown == total:
            self._count_lbl.config(text=f"{total} controls")
        else:
            self._count_lbl.config(text=f"Showing {shown} of {total} controls")

    # =========================================================================
    # TREE POPULATION
    # =========================================================================

    def _populate_tree(self, controls):
        """
        Clear the Treeview and fill it with the given list of controls.

        Parameters:
            controls - The list of control dicts to display
        """
        C = self._colors

        # Remove all existing rows
        self._tree.delete(*self._tree.get_children())

        for i, ctrl in enumerate(controls):
            # Tag rows differently by class so we can colour them
            tag = "principle" if ctrl["class"] == "ISM-principle" else "control"

            # For controls whose title is a generated placeholder like
            # "Control: ism-1130", show the statement text instead
            display_title = ctrl["title"]
            if display_title.lower().startswith("control:") or not display_title:
                display_title = ctrl["statement"]

            # iid= is the internal row ID (used in _tree_selected to find the ctrl)
            self._tree.insert(
                "", "end", iid=str(i),
                values=(ctrl["label"], display_title, ctrl["class"],
                        ctrl.get("guideline", "")),
                tags=(tag,),
            )

        self._tree.tag_configure("principle", foreground=C["TEAL"])
        self._tree.tag_configure("control",   foreground=C["TEXT"])

        # Update the filtered list so _tree_selected can look up the right ctrl
        self._filtered_controls = controls

    # =========================================================================
    # SELECTION HANDLER
    # =========================================================================

    def _tree_selected(self, _event=None):
        """
        Called when the user clicks a row in the Treeview.
        Looks up the matching control dict and shows its detail.
        """
        sel = self._tree.selection()
        if not sel:
            return
        ctrl = self._filtered_controls[int(sel[0])]
        self._on_select(ctrl)
        self._show_detail(ctrl)

    # =========================================================================
    # DETAIL PANEL
    # =========================================================================

    def _show_placeholder(self):
        """Clear the detail panel and show a helpful prompt."""
        for w in self._detail.winfo_children():
            w.destroy()
        C = self._colors
        has_catalog = self._get_catalog() is not None
        msg = (
            "Select a control from the list to view details."
            if has_catalog else
            "Open an OSCAL catalog file to get started."
        )
        tk.Label(
            self._detail, text=msg,
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 13, "italic"),
            wraplength=400, justify="center",
        ).pack(expand=True, pady=80, padx=40)

    def _show_detail(self, ctrl):
        """
        Clear the detail panel and rebuild it for the given control.

        Parameters:
            ctrl - A control dictionary (one item from the controls list)
        """
        for w in self._detail.winfo_children():
            w.destroy()
        self._wrap_labels = []   # reset list so stale refs don't accumulate
        C   = self._colors
        pad = dict(padx=22)

        # ── Header: badge + title ─────────────────────────────────────────────
        header = tk.Frame(self._detail, bg=C["HEADER_BG"])
        header.pack(fill="x", **pad, pady=(18, 4))

        badge_fg = C["TEAL"] if ctrl["class"] == "ISM-principle" else C["BLUE"]
        tk.Label(
            header, text=f"  {ctrl['label']}  ",
            bg=badge_fg, fg=C["BG"],
            font=("Helvetica", 12, "bold"), relief="flat",
        ).pack(side="left", padx=10, pady=8)

        has_real_title = ctrl["title"] and not ctrl["title"].lower().startswith("control:")
        hdr_lbl = tk.Label(
            header,
            text=ctrl["title"] if has_real_title else ctrl["statement"],
            bg=C["HEADER_BG"], fg=C["TEXT"],
            font=("Helvetica", 13, "bold"),
            justify="left",
        )
        hdr_lbl.pack(side="left", padx=6, pady=8, fill="x", expand=True)
        self._wrap_labels.append(hdr_lbl)

        # ── Metadata rows ─────────────────────────────────────────────────────
        self._row("Category", ctrl["path"], value_color=C["SUBTEXT"], italic=True)
        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=22, pady=6
        )
        self._row("Control ID", ctrl["id"])
        self._row("Class",      ctrl["class"])
        if ctrl["revision"] != "—":
            self._row("Revision", ctrl["revision"])
        if ctrl["updated"] != "—":
            self._row("Updated",  ctrl["updated"])
        if ctrl["essential_eight"] != "—":
            self._row("Essential Eight", ctrl["essential_eight"],
                      value_color=C["YELLOW"])

        # ── Applicability chips ───────────────────────────────────────────────
        if ctrl["applicability"]:
            cf = tk.Frame(self._detail, bg=C["BG"])
            cf.pack(fill="x", **pad, pady=4)
            tk.Label(
                cf, text="Applicability:", bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11, "bold"), width=14, anchor="w",
            ).pack(side="left")
            for ap in ctrl["applicability"]:
                tk.Label(
                    cf, text=f" {ap} ",
                    bg=C["GREEN"], fg=C["BG"],
                    font=("Helvetica", 10, "bold"), relief="flat",
                ).pack(side="left", padx=3)

        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=22, pady=8
        )

        # ── Statement ─────────────────────────────────────────────────────────
        if ctrl["statement"]:
            tk.Label(
                self._detail, text="Statement",
                bg=C["BG"], fg=C["ACCENT"],
                font=("Helvetica", 12, "bold"),
            ).pack(anchor="w", **pad, pady=(4, 2))

            box = tk.Frame(
                self._detail, bg=C["SIDEBAR_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            box.pack(fill="x", padx=22, pady=4)
            stmt_lbl = tk.Label(
                box, text=ctrl["statement"],
                bg=C["SIDEBAR_BG"], fg=C["TEXT"],
                font=("Helvetica", 12),
                justify="left", anchor="nw",
            )
            stmt_lbl.pack(padx=14, pady=12, fill="x")
            self._wrap_labels.append(stmt_lbl)

        tk.Frame(self._detail, bg=C["BG"], height=30).pack()

    def _row(self, label, value, value_color=None, italic=False):
        """
        Add a label: value row to the detail panel.

        Parameters:
            label       - Field name (left side), e.g. "Control ID"
            value       - Field value (right side), e.g. "ism-1130"
            value_color - Optional colour override for the value text
            italic      - If True, render the value in italic font
        """
        C     = self._colors
        frame = tk.Frame(self._detail, bg=C["BG"])
        frame.pack(fill="x", padx=22, pady=2)
        tk.Label(
            frame, text=f"{label}:",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11, "bold"),
            width=14, anchor="w",
        ).pack(side="left")
        val_lbl = tk.Label(
            frame, text=value,
            bg=C["BG"], fg=value_color or C["TEXT"],
            font=("Helvetica", 11, "italic") if italic else ("Helvetica", 11),
            justify="left", anchor="w",
        )
        val_lbl.pack(side="left", fill="x", expand=True)
        self._wrap_labels.append(val_lbl)

    # =========================================================================
    # SCROLL HELPERS
    # =========================================================================

    def _on_detail_configure(self, _event):
        """Update the canvas scroll region when the inner frame resizes."""
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Stretch the inner frame to match the canvas width and rewrap text labels."""
        self._canvas.itemconfig(self._win, width=event.width)
        # Update wraplength for every label that was registered during _show_detail.
        # 88px = 22px side padding × 2 + 44px for the fixed-width label column.
        wrap = max(100, event.width - 88)
        for lbl in getattr(self, "_wrap_labels", []):
            try:
                lbl.configure(wraplength=wrap)
            except tk.TclError:
                pass  # widget was destroyed when detail was cleared

    def _on_mousewheel(self, event):
        """
        Scroll the detail canvas on mouse-wheel, only when the mouse
        is over the canvas or one of its child widgets.
        """
        widget = self.winfo_containing(event.x_root, event.y_root)
        if widget and (
            widget is self._canvas
            or str(widget).startswith(str(self._canvas))
        ):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
