"""
catalog_tab.py
==============
This file defines the CatalogTab class — the left-hand tab of the
OSCAL User Toolkit that lets users browse catalog controls.

DESIGN PATTERN — Why a class?
-------------------------------
CatalogTab inherits from tk.Frame, which means it IS a GUI widget
(a panel) rather than just an object that creates widgets. This makes
it self-contained: it owns its own buttons, lists, and scroll bars,
and it manages its own internal data.

The main app creates one instance and drops it into the notebook:
    tab = CatalogTab(notebook, colors, ...)
    notebook.add(tab, text="Catalog Viewer")

The app communicates with CatalogTab through:
  - Method calls on the instance:  tab.load_controls(controls)
  - Injected callbacks passed at construction time (see __init__)
"""

import tkinter as tk
from tkinter import ttk   # ttk provides themed (nicer-looking) widgets


class CatalogTab(tk.Frame):
    """
    A self-contained catalog viewer panel.

    This class manages:
      - A searchable, filterable list of controls (left side)
      - A scrollable detail panel showing the selected control (right side)
      - All scroll events and widget layout

    ── Callbacks injected by the app at creation time ──────────────────
    on_select(ctrl)   Called when the user clicks a control row.
                      'ctrl' is the control dictionary for that row.
                      (Currently unused externally, but available for
                      future Stage 2 integration with the SSP tab.)

    get_catalog()     Called to check whether a catalog is loaded.
                      Returns the catalog dict, or None if not loaded.
                      Used to decide what placeholder message to show.
    """

    def __init__(self, parent, colors, on_select, get_catalog):
        """
        Set up the CatalogTab panel.

        Parameters:
            parent      - The parent widget (the ttk.Notebook)
            colors      - A dictionary of colour hex strings shared across the app
            on_select   - Callback: called with the ctrl dict when a row is clicked
            get_catalog - Callback: returns the catalog dict, or None
        """
        # Call the parent class (tk.Frame) constructor.
        # bg= sets the background colour of this frame.
        super().__init__(parent, bg=colors["BG"])

        # Store everything we were given so methods can use them later.
        # Storing the colour dict means we never hardcode colours here.
        self._colors      = colors
        self._on_select   = on_select
        self._get_catalog = get_catalog

        # These two lists hold the full set of controls and the currently
        # visible (filtered) subset. We start with both empty.
        self._all_controls      = []
        self._filtered_controls = []

        # Build all the GUI widgets
        self._build()

    # =========================================================================
    # PUBLIC API
    # These methods are called by the main app (app.py) to update this tab.
    # Think of them as the "official interface" between the tab and the app.
    # =========================================================================

    def load_controls(self, controls):
        """
        Replace the full control list with a new set (called after a catalog
        is loaded) and refresh the display.

        Parameters:
            controls - A list of control dictionaries from models.load_catalog()
        """
        # Store the complete list — filtering always starts from this
        self._all_controls      = controls
        self._filtered_controls = list(controls)  # list() makes a copy

        # Push the data into the tree widget and reset the detail panel
        self._populate_tree(controls)
        self._show_placeholder()

    def apply_filters(self, profile_ids=None, class_filter="All", search_term=""):
        """
        Filter the control list and refresh the tree widget.

        Called by the app whenever the user changes the class dropdown,
        types in the search box, or loads/clears a profile.

        Parameters:
            profile_ids  - A set of control ID strings from the loaded profile,
                           or None to show all controls
            class_filter - A class name string like "ISM-control", or "All"
            search_term  - Text the user typed in the search box
        """
        # Start with the complete unfiltered list
        result = self._all_controls

        # ── Profile filter ────────────────────────────────────────────────────
        # If a profile is loaded, only keep controls whose id is in the profile
        if profile_ids is not None:
            # 'c["id"] in profile_ids' is fast because profile_ids is a set
            result = [c for c in result if c["id"] in profile_ids]

        # ── Class filter ──────────────────────────────────────────────────────
        if class_filter != "All":
            result = [c for c in result if c["class"] == class_filter]

        # ── Text search ───────────────────────────────────────────────────────
        if search_term:
            # Convert to lowercase once so the comparison is case-insensitive
            t = search_term.lower()
            result = [
                c for c in result
                if t in c["title"].lower()
                or t in c["label"].lower()
                or t in c["statement"].lower()
                or t in c["id"].lower()
            ]

        # Rebuild the tree with whatever is left after filtering
        self._populate_tree(result)
        # Reset the detail panel (clears any previously shown control)
        self._show_placeholder()

    def control_count(self):
        """
        Return the total and currently visible control counts.

        Used by the app to update the status bar label at the bottom.

        Returns:
            A tuple of (total_count, visible_count)
        """
        return len(self._all_controls), len(self._filtered_controls)

    # =========================================================================
    # PRIVATE METHODS — Building the GUI
    # Methods starting with _ (underscore) are "private" by convention in
    # Python. They are implementation details not meant to be called from
    # outside the class.
    # =========================================================================

    def _build(self):
        """
        Create all the widgets inside this tab.

        Layout: a horizontal PanedWindow (resizable split pane) with:
          - Left side:  the control list (tree + scrollbars)
          - Right side: the detail view (scrollable canvas)
        """
        C = self._colors  # Short alias to keep lines readable

        # PanedWindow creates a split view with a draggable divider between
        # two sides. orient="horizontal" means the split is left/right.
        body = tk.PanedWindow(
            self, orient="horizontal",
            bg=C["BG"], sashwidth=5, sashrelief="flat"
        )
        body.pack(fill="both", expand=True)
        # fill="both" + expand=True means: use all available space

        # Build each side
        self._build_control_list(body)
        self._build_detail_pane(body)

    def _build_control_list(self, body):
        """
        Build the left pane: a Treeview (table) showing all controls,
        with vertical and horizontal scrollbars.

        The Treeview widget is tkinter's table/list widget. We configure
        it with three columns: label, title/statement, and class.
        """
        C = self._colors

        # Create a frame to hold the tree and its scrollbars
        left = tk.Frame(body, bg=C["SIDEBAR_BG"])
        # Add it to the split pane. minsize prevents it being squashed too small.
        body.add(left, minsize=380, width=520)

        # ── Treeview (the table widget) ───────────────────────────────────────
        # columns= names the columns (these are internal IDs, not display text)
        # show="headings" hides the default empty first column
        cols = ("label", "title", "class")
        self._tree = ttk.Treeview(
            left, columns=cols, show="headings", selectmode="browse"
        )
        # Set the visible heading text for each column
        self._tree.heading("label", text="ID / Label",        anchor="w")
        self._tree.heading("title", text="Title / Statement", anchor="w")
        self._tree.heading("class", text="Class",             anchor="w")
        # Set column widths. stretch=True lets the title column expand to fill space.
        self._tree.column("label", width=120, minwidth=90,  anchor="w")
        self._tree.column("title", width=310, minwidth=150, anchor="w", stretch=True)
        self._tree.column("class", width=110, minwidth=90,  anchor="w")

        # ── Scrollbars ────────────────────────────────────────────────────────
        # Scrollbars need to know which widget to scroll (command=...)
        # and the widget needs to know which scrollbar to update (yscrollcommand=...)
        vsb = ttk.Scrollbar(left, orient="vertical",   command=self._tree.yview)
        hsb = ttk.Scrollbar(left, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Use .grid() to arrange the tree and scrollbars precisely.
        # grid() lets us place widgets in a row/column layout.
        self._tree.grid(row=0, column=0, sticky="nsew")  # fills all space
        vsb.grid(row=0, column=1, sticky="ns")           # right edge, full height
        hsb.grid(row=1, column=0, sticky="ew")           # bottom edge, full width
        # Make row 0 and column 0 expand to fill the available space
        left.rowconfigure(0, weight=1)
        left.columnconfigure(0, weight=1)

        # When the user clicks a row, call our _tree_selected method
        self._tree.bind("<<TreeviewSelect>>", self._tree_selected)

    def _build_detail_pane(self, body):
        """
        Build the right pane: a scrollable canvas that shows the full
        details of whichever control the user has selected.

        We use a Canvas widget rather than a plain Frame because Canvas
        supports scrolling — a Frame cannot scroll on its own.

        Inside the Canvas we place a Frame (_detail), and inside that
        Frame we add all the label widgets for the control details.
        When the user selects a different control we clear the Frame
        and rebuild it.
        """
        C = self._colors

        right = tk.Frame(body, bg=C["BG"])
        body.add(right, minsize=340)

        # ── Canvas + scrollbar ────────────────────────────────────────────────
        self._canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb = ttk.Scrollbar(right, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(fill="both", expand=True)

        # ── Inner frame inside the canvas ─────────────────────────────────────
        # create_window() places a widget inside the canvas at position (0,0).
        # anchor="nw" means the top-left corner of the frame is at (0,0).
        self._detail = tk.Frame(self._canvas, bg=C["BG"])
        self._win = self._canvas.create_window(
            (0, 0), window=self._detail, anchor="nw"
        )

        # When the inner frame changes size (because we add/remove labels),
        # update the canvas scroll region so the scrollbar knows the new size.
        self._detail.bind("<Configure>", self._on_detail_configure)

        # When the canvas itself is resized (user drags the split pane),
        # stretch the inner frame to match the canvas width.
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Bind mouse wheel scrolling on any widget inside the canvas
        self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Show the initial placeholder message
        self._show_placeholder()

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

        # Remove every existing row from the tree
        self._tree.delete(*self._tree.get_children())

        # Add one row per control
        for i, ctrl in enumerate(controls):
            # Tag rows differently based on class so we can colour them
            tag = "principle" if ctrl["class"] == "ISM-principle" else "control"

            # For controls whose title is a generated placeholder
            # (e.g. "Control: ism-1130"), show the statement text instead
            display_title = ctrl["title"]
            if display_title.lower().startswith("control:") or not display_title:
                display_title = ctrl["statement"]

            # iid= is the internal row ID — we use the list index so we can
            # look up the control dict later when the user clicks the row.
            self._tree.insert(
                "", "end", iid=str(i),
                values=(ctrl["label"], display_title, ctrl["class"]),
                tags=(tag,)
            )

        # Apply different foreground colours per tag
        self._tree.tag_configure("principle", foreground=C["TEAL"])
        self._tree.tag_configure("control",   foreground=C["TEXT"])

        # Remember the filtered list so _tree_selected can look up the right ctrl
        self._filtered_controls = controls

    # =========================================================================
    # SELECTION HANDLER
    # =========================================================================

    def _tree_selected(self, _event=None):
        """
        Called automatically by tkinter when the user clicks a row in the tree.

        The underscore in '_event' indicates we receive but don't use the
        event object — it is there because tkinter always passes it.
        """
        # selection() returns a tuple of selected row IDs (we allow only one)
        sel = self._tree.selection()
        if not sel:
            return  # Nothing selected — do nothing

        # Convert the row ID (a string like "42") back to an integer index
        ctrl = self._filtered_controls[int(sel[0])]

        # Notify the app (for future Stage 2 SSP integration)
        self._on_select(ctrl)

        # Update the detail panel to show this control
        self._show_detail(ctrl)

    # =========================================================================
    # DETAIL PANEL
    # =========================================================================

    def _show_placeholder(self):
        """
        Clear the detail panel and show a helpful message prompting the user
        to either open a catalog or select a control.
        """
        # Remove all existing child widgets from the detail frame
        for w in self._detail.winfo_children():
            w.destroy()

        C = self._colors
        # Show different messages depending on whether a catalog is loaded
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
        Clear the detail panel and rebuild it with information about 'ctrl'.

        Parameters:
            ctrl - A control dictionary (one item from the controls list)
        """
        # Destroy all existing widgets in the detail frame before rebuilding
        for w in self._detail.winfo_children():
            w.destroy()

        C   = self._colors
        pad = dict(padx=22)  # Common horizontal padding used throughout

        # ── Header bar: coloured label badge + title ──────────────────────────
        header = tk.Frame(self._detail, bg=C["HEADER_BG"])
        header.pack(fill="x", **pad, pady=(18, 4))

        # Principles use teal badges; regular controls use blue
        badge_fg = C["TEAL"] if ctrl["class"] == "ISM-principle" else C["BLUE"]
        tk.Label(
            header, text=f"  {ctrl['label']}  ",
            bg=badge_fg, fg=C["BG"],
            font=("Helvetica", 12, "bold"), relief="flat",
        ).pack(side="left", padx=10, pady=8)

        # Decide what text to show as the heading.
        # Controls with generated titles (starting with "Control:") should
        # show their statement instead — it is more meaningful.
        has_real_title = ctrl["title"] and not ctrl["title"].lower().startswith("control:")
        tk.Label(
            header,
            text=ctrl["title"] if has_real_title else ctrl["statement"],
            bg=C["HEADER_BG"], fg=C["TEXT"],
            font=("Helvetica", 13, "bold"),
            wraplength=480, justify="left",
        ).pack(side="left", padx=6, pady=8, fill="x", expand=True)

        # ── Breadcrumb path ───────────────────────────────────────────────────
        self._row("Category", ctrl["path"], value_color=C["SUBTEXT"], italic=True)

        # ── Horizontal divider line ───────────────────────────────────────────
        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=22, pady=6
        )

        # ── Metadata fields ───────────────────────────────────────────────────
        self._row("Control ID", ctrl["id"])
        self._row("Class",      ctrl["class"])
        # Only show optional fields if they actually have a value
        if ctrl["revision"] != "—":
            self._row("Revision", ctrl["revision"])
        if ctrl["updated"] != "—":
            self._row("Updated",  ctrl["updated"])
        if ctrl["essential_eight"] != "—":
            self._row("Essential Eight", ctrl["essential_eight"],
                      value_color=C["YELLOW"])

        # ── Applicability chips (coloured badges) ─────────────────────────────
        if ctrl["applicability"]:
            # Create a row frame to hold the label and all the chips side by side
            cf = tk.Frame(self._detail, bg=C["BG"])
            cf.pack(fill="x", **pad, pady=4)
            tk.Label(
                cf, text="Applicability:", bg=C["BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 11, "bold"), width=14, anchor="w"
            ).pack(side="left")
            # One green badge per applicability value (e.g. NC, OS, P, S, TS)
            for ap in ctrl["applicability"]:
                tk.Label(
                    cf, text=f" {ap} ",
                    bg=C["GREEN"], fg=C["BG"],
                    font=("Helvetica", 10, "bold"), relief="flat",
                ).pack(side="left", padx=3)

        # ── Second divider ────────────────────────────────────────────────────
        tk.Frame(self._detail, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=22, pady=8
        )

        # ── Statement (the control requirement text) ──────────────────────────
        if ctrl["statement"]:
            tk.Label(
                self._detail, text="Statement",
                bg=C["BG"], fg=C["ACCENT"],
                font=("Helvetica", 12, "bold"),
            ).pack(anchor="w", **pad, pady=(4, 2))

            # Put the statement text inside a bordered box frame
            box = tk.Frame(
                self._detail, bg=C["SIDEBAR_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            box.pack(fill="x", padx=22, pady=4)
            tk.Label(
                box, text=ctrl["statement"],
                bg=C["SIDEBAR_BG"], fg=C["TEXT"],
                font=("Helvetica", 12),
                wraplength=520, justify="left", anchor="nw",
            ).pack(padx=14, pady=12, fill="x")

        # ── Bottom padding ────────────────────────────────────────────────────
        tk.Frame(self._detail, bg=C["BG"], height=30).pack()

    def _row(self, label, value, value_color=None, italic=False):
        """
        Add a single label: value row to the detail panel.

        This is a helper to avoid repeating the same layout code
        every time we want to show a field like "Control ID: ism-1130".

        Parameters:
            label       - The field name (left side), e.g. "Control ID"
            value       - The field value (right side), e.g. "ism-1130"
            value_color - Optional colour override for the value text
            italic      - If True, render the value in italic font
        """
        C     = self._colors
        frame = tk.Frame(self._detail, bg=C["BG"])
        frame.pack(fill="x", padx=22, pady=2)

        # Fixed-width label column (14 characters wide) keeps values aligned
        tk.Label(
            frame, text=f"{label}:",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11, "bold"),
            width=14, anchor="w",
        ).pack(side="left")

        # Value column — use italic font if requested
        font = ("Helvetica", 11, "italic") if italic else ("Helvetica", 11)
        tk.Label(
            frame, text=value,
            bg=C["BG"], fg=value_color or C["TEXT"],
            font=font,
            wraplength=500, justify="left", anchor="w",
        ).pack(side="left", fill="x", expand=True)

    # =========================================================================
    # SCROLL EVENT HANDLERS
    # =========================================================================

    def _on_detail_configure(self, _event):
        """
        Called when the inner detail frame changes size.
        Updates the canvas scroll region so the scrollbar stays accurate.
        bbox("all") returns a bounding box covering all widgets in the canvas.
        """
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """
        Called when the canvas is resized (e.g. user drags the split pane).
        Stretches the inner frame to match the new canvas width so labels
        wrap correctly and do not overflow to the right.
        """
        self._canvas.itemconfig(self._win, width=event.width)

    def _on_mousewheel(self, event):
        """
        Called when the user scrolls the mouse wheel anywhere in the app.
        We only scroll the detail canvas if the mouse is actually over it.

        event.x_root and event.y_root give the mouse's screen position.
        winfo_containing() finds which widget is at that position.
        """
        widget = self.winfo_containing(event.x_root, event.y_root)
        # Check if the widget under the mouse is the canvas or something inside it.
        # str(widget).startswith(str(canvas)) checks for child widgets.
        if widget and (
            widget is self._canvas
            or str(widget).startswith(str(self._canvas))
        ):
            # delta is the scroll amount; dividing by 120 gives +1 or -1 steps
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
