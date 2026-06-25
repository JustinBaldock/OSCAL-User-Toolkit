"""
app.py
======
This file defines OSCALApp — the main application window.

OSCALApp is responsible for:
  - Creating the overall window (title bar, size, background)
  - Building the shared toolbar (Open Catalog, Open Profile buttons)
  - Building the info panel (catalog and profile summary cards)
  - Creating the notebook (tabbed layout) and adding the two tabs
  - Building the status bar at the bottom
  - Handling catalog and profile file loading
  - Applying filters and passing results to the CatalogTab

OSCALApp does NOT build the content inside each tab — that is handled
by CatalogTab (catalog_tab.py) and SSPTab (ssp_tab.py). The app only
communicates with those tabs through their public methods, keeping
each piece of code focused on one job.

INHERITANCE
-----------
OSCALApp inherits from tk.Tk, which means it IS the main window.
Calling super().__init__() sets up the window; everything else we
add (toolbar, notebook, etc.) goes inside it.
"""

import json        # For parsing JSON files and error handling
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path   # Cross-platform file path handling

# Import the data-loading functions from our models module
from .models import load_catalog, load_profile

# Import the two tab classes
from .catalog_tab import CatalogTab
from .ssp_tab import SSPTab
from .component_tab import ComponentTab

# ── Shared colour palette ─────────────────────────────────────────────────────
# All colours are defined once here as a dictionary and passed to each tab,
# so changing a colour here updates the whole application.
# Colours are hex strings: "#RRGGBB" (red, green, blue in hexadecimal).
COLORS = {
    "BG":         "#1e1e2e",   # Main background (very dark navy)
    "SIDEBAR_BG": "#181825",   # Slightly darker background for the list pane
    "HEADER_BG":  "#313244",   # Section headers and toolbar
    "INFO_BG":    "#252535",   # Info panel background
    "CARD_BG":    "#2a2a3d",   # Card/form field backgrounds
    "ACCENT":     "#cba6f7",   # Lavender — used for headings and highlights
    "TEXT":       "#cdd6f4",   # Main text colour (light blue-white)
    "SUBTEXT":    "#a6adc8",   # Secondary/hint text (slightly dimmer)
    "GREEN":      "#a6e3a1",   # Success / positive indicators
    "YELLOW":     "#f9e2af",   # Warnings and profile info
    "RED":        "#f38ba8",   # Errors and alerts
    "BLUE":       "#89b4fa",   # Information and links
    "TEAL":       "#94e2d5",   # Principle controls in the catalog list
    "ORANGE":     "#fab387",   # Reserved for future use
}


class OSCALApp(tk.Tk):
    """
    The main application window for the OSCAL User Toolkit.

    This class inherits from tk.Tk, making it the root (main) window.
    Only one instance of this class is ever created — in main.py.
    """

    def __init__(self):
        """
        Initialise the main window and build all the GUI components.

        __init__ is called automatically when you write OSCALApp().
        """
        # Set up the underlying tkinter window.
        # This MUST be called before any other tkinter code.
        super().__init__()

        # ── Window properties ─────────────────────────────────────────────────
        self.title("OSCAL User Toolkit")
        self.geometry("1340x900")    # Initial width x height in pixels
        self.minsize(1000, 700)      # Minimum window size (prevents squashing)
        self.configure(bg=COLORS["BG"])

        # ── Application state ─────────────────────────────────────────────────
        # These variables hold the currently loaded data.
        # None means "nothing loaded yet".
        self._catalog = None    # The loaded catalog dict (from models.load_catalog)
        self._profile = None    # The loaded profile dict (from models.load_profile)

        # StringVars for the toolbar filter controls.
        # tkinter StringVar objects automatically update linked widgets.
        self._selected_class = tk.StringVar(value="All")
        self._search_var     = tk.StringVar()

        # trace_add("write", ...) calls _on_search every time the search box changes.
        # This enables live filtering as the user types.
        self._search_var.trace_add("write", self._on_search)

        # ── Build the GUI ─────────────────────────────────────────────────────
        # Each method below creates one layer of the UI.
        # Order matters: statusbar must be packed before the notebook
        # so that it appears at the bottom.
        self._style_ttk()       # Apply custom colours to ttk widgets
        self._build_toolbar()   # Top bar with Open Catalog/Profile buttons
        self._build_info_panel()# Cards showing catalog and profile metadata
        self._build_notebook()  # Tabbed area with CatalogTab and SSPTab
        self._build_statusbar() # Bottom bar with status message

    # =========================================================================
    # STYLING
    # =========================================================================

    def _style_ttk(self):
        """
        Apply custom colours and fonts to ttk (themed) widgets.

        ttk widgets (Treeview, Combobox, Scrollbar, Notebook, etc.) have a
        separate styling system from plain tk widgets. We use ttk.Style to
        override the default 'clam' theme with our dark colour palette.
        """
        C = COLORS
        s = ttk.Style(self)
        s.theme_use("clam")   # 'clam' is a clean theme that accepts overrides

        # Treeview (the table/list widget used in both tabs)
        s.configure(
            "Treeview",
            background=C["SIDEBAR_BG"], foreground=C["TEXT"],
            fieldbackground=C["SIDEBAR_BG"],
            borderwidth=0, font=("Helvetica", 11), rowheight=26,
        )
        s.configure(
            "Treeview.Heading",   # Column header row
            background=C["HEADER_BG"], foreground=C["ACCENT"],
            font=("Helvetica", 11, "bold"), relief="flat",
        )
        # Change selected row colour
        s.map("Treeview",
              background=[("selected", C["ACCENT"])],
              foreground=[("selected", C["BG"])])

        # Scrollbars (both vertical and horizontal)
        for orient in ("Vertical", "Horizontal"):
            s.configure(
                f"{orient}.TScrollbar",
                background=C["HEADER_BG"], troughcolor=C["SIDEBAR_BG"],
                borderwidth=0, arrowcolor=C["SUBTEXT"],
            )

        # Combobox (dropdown)
        s.configure(
            "TCombobox",
            fieldbackground=C["HEADER_BG"], background=C["HEADER_BG"],
            foreground=C["TEXT"], selectbackground=C["ACCENT"],
            selectforeground=C["BG"],
        )
        s.map("TCombobox",
              fieldbackground=[("readonly", C["HEADER_BG"])],
              foreground=[("readonly", C["TEXT"])])

        # Notebook (the tabbed container)
        s.configure("TNotebook", background=C["BG"], borderwidth=0)
        s.configure(
            "TNotebook.Tab",   # Individual tab labels
            background=C["HEADER_BG"], foreground=C["SUBTEXT"],
            padding=[14, 6], font=("Helvetica", 11),
        )
        # Active tab gets a different colour
        s.map("TNotebook.Tab",
              background=[("selected", C["CARD_BG"])],
              foreground=[("selected", C["ACCENT"])])

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _build_toolbar(self):
        """
        Create the top toolbar with:
          - Open Catalog button (purple)
          - Open Profile button (yellow)
          - Clear Profile button (disabled until a profile is loaded)
          - App title label
          - Class filter dropdown (right side)
          - Search box (right side)
        """
        C  = COLORS
        tb = tk.Frame(self, bg=C["HEADER_BG"], height=54)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)   # Keep the toolbar at exactly 54px tall

        # ── Left-side buttons ─────────────────────────────────────────────────
        tk.Button(
            tb, text="📂  Open Catalog", command=self._open_catalog,
            bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BG"],
        ).pack(side="left", padx=14, pady=10)

        tk.Button(
            tb, text="🔖  Open Profile", command=self._open_profile,
            bg=C["YELLOW"], fg=C["BG"], font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#f5c842", activeforeground=C["BG"],
        ).pack(side="left", padx=(0, 8), pady=10)

        # Clear Profile button — stored as an instance variable so we can
        # enable/disable it when a profile is loaded/cleared.
        self._clear_profile_btn = tk.Button(
            tb, text="✕  Clear Profile", command=self._clear_profile,
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 11),
            relief="flat", padx=10, pady=6, cursor="hand2",
            state="disabled",              # Greyed out until a profile is loaded
            disabledforeground="#555570",  # Colour when disabled
        )
        self._clear_profile_btn.pack(side="left", pady=10)

        # App title
        tk.Label(
            tb, text="OSCAL User Toolkit",
            bg=C["HEADER_BG"], fg=C["TEXT"],
            font=("Helvetica", 14, "bold"),
        ).pack(side="left", padx=12)

        # ── Right-side controls (packed right-to-left) ────────────────────────
        # Note: pack(side="right") items appear in reverse order visually,
        # so we pack the rightmost item first.

        # Search box icon
        tk.Label(
            tb, text="🔍", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 13),
        ).pack(side="right", padx=(0, 6))

        # Search text entry — linked to _search_var which triggers _on_search
        tk.Entry(
            tb, textvariable=self._search_var,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11), width=22,
        ).pack(side="right", padx=(0, 12), ipady=4)

        tk.Label(
            tb, text="Search:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="right")

        # Class filter dropdown — lets user show only ISM-control or ISM-principle
        self._class_combo = ttk.Combobox(
            tb, textvariable=self._selected_class,
            values=["All"],    # Populated properly after a catalog is loaded
            state="readonly",  # User can only select, not type
            width=18,
        )
        self._class_combo.pack(side="right", padx=(0, 8), pady=14)
        # Call _on_filter whenever the user picks a different class
        self._class_combo.bind("<<ComboboxSelected>>", self._on_filter)

        tk.Label(
            tb, text="Class:", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="right", padx=(16, 4))

    # =========================================================================
    # INFO PANEL
    # =========================================================================

    def _build_info_panel(self):
        """
        Create the info panel — two side-by-side cards showing metadata
        about the currently loaded catalog (left) and profile (right).

        Each card has:
          - A coloured header bar with an icon and the document title
          - A row of labelled fields (Version, OSCAL Version, etc.)
        """
        C     = COLORS
        panel = tk.Frame(self, bg=C["INFO_BG"])
        panel.pack(fill="x", side="top")

        # ── Helper: create one card ────────────────────────────────────────────
        def card(icon, label_text, fg, side_padx):
            """
            Build a metadata card and return (title_label, fields_frame).

            Parameters:
                icon       - Emoji icon, e.g. "📄"
                label_text - Card type text, e.g. "Catalog"
                fg         - Heading colour (accent or yellow)
                side_padx  - (left_pad, right_pad) tuple for the card frame
            """
            # Outer card frame with a subtle border
            c = tk.Frame(
                panel, bg=C["CARD_BG"],
                highlightthickness=1, highlightbackground=C["HEADER_BG"]
            )
            c.pack(side="left", fill="x", expand=True, padx=side_padx, pady=8)

            # Coloured header bar across the top of the card
            hdr = tk.Frame(c, bg=C["HEADER_BG"])
            hdr.pack(fill="x")
            tk.Label(
                hdr, text=f"{icon}  {label_text}",
                bg=C["HEADER_BG"], fg=fg,
                font=("Helvetica", 10, "bold"), anchor="w",
            ).pack(side="left", padx=10, pady=4)

            # Title label — updated when a file is loaded
            title_lbl = tk.Label(
                hdr, text=f"No {label_text.lower()} loaded",
                bg=C["HEADER_BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 10, "italic"), anchor="w",
            )
            title_lbl.pack(side="left", padx=(0, 10), pady=4)

            # Frame for the metadata fields row below the header
            fields_frame = tk.Frame(c, bg=C["CARD_BG"])
            fields_frame.pack(fill="x", padx=10, pady=6)

            return title_lbl, fields_frame

        # ── Helper: create one field within a card ────────────────────────────
        def field(parent, label):
            """
            Add a label + value pair to a card's fields row.
            Returns the value label so the app can update it later.
            """
            f = tk.Frame(parent, bg=C["CARD_BG"])
            f.pack(side="left", padx=(0, 20))
            # Small grey label above the value
            tk.Label(
                f, text=label, bg=C["CARD_BG"], fg=C["SUBTEXT"],
                font=("Helvetica", 9),
            ).pack(anchor="w")
            # Bold value below — starts as "—" (em dash = no data)
            lbl = tk.Label(
                f, text="—", bg=C["CARD_BG"], fg=C["TEXT"],
                font=("Helvetica", 10, "bold"),
            )
            lbl.pack(anchor="w")
            return lbl   # Return so we can .config(text=...) later

        # ── Catalog card (left) ───────────────────────────────────────────────
        # Store labels as instance variables so _open_catalog() can update them
        self._cat_title_lbl, cf = card("📄", "Catalog", C["ACCENT"], (10, 5))
        self._cat_version_lbl   = field(cf, "Version")
        self._cat_oscal_lbl     = field(cf, "OSCAL Version")
        self._cat_published_lbl = field(cf, "Published")
        self._cat_modified_lbl  = field(cf, "Last Modified")
        self._cat_controls_lbl  = field(cf, "Controls")

        # ── Profile card (right) ──────────────────────────────────────────────
        self._prof_title_lbl, pf = card("🔖", "Profile", C["YELLOW"], (5, 10))
        self._prof_version_lbl   = field(pf, "Version")
        self._prof_oscal_lbl     = field(pf, "OSCAL Version")
        self._prof_published_lbl = field(pf, "Published")
        self._prof_modified_lbl  = field(pf, "Last Modified")
        self._prof_controls_lbl  = field(pf, "Controls")

    # =========================================================================
    # NOTEBOOK (TABBED LAYOUT)
    # =========================================================================

    def _build_notebook(self):
        """
        Create the ttk.Notebook (tabbed container) and add both tabs.

        We create CatalogTab and SSPTab as proper widget objects and add
        them to the notebook. The notebook shows one at a time with
        clickable tab labels.

        Notice how we pass callbacks (lambda functions) into each tab:
          - get_catalog=lambda: self._catalog
            This gives the tab a way to ask "what catalog is loaded?"
            without the tab needing a direct reference to 'self' (the app).
          - set_status=lambda msg: self._status_lbl.config(text=msg)
            This lets SSPTab update the status bar without knowing about it.

        Using lambdas like this is called "dependency injection" — the tab
        gets what it needs without being tightly coupled to the app class.
        """
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._notebook = nb   # Store so SSPTab can check which tab is active

        # ── Catalog Viewer tab ────────────────────────────────────────────────
        self._catalog_tab = CatalogTab(
            parent     = nb,
            colors     = COLORS,
            # on_select: called when user clicks a control — reserved for Stage 2
            on_select  = lambda ctrl: None,
            # get_catalog: lets the tab check if a catalog is loaded
            get_catalog= lambda: self._catalog,
        )
        nb.add(self._catalog_tab, text="📋  Catalog Viewer")

        # ── Component Editor tab ──────────────────────────────────────────────
        # This tab sits BETWEEN Catalog Viewer and SSP Editor.
        # It lets users create and save OSCAL Component Definition JSON files.
        self._component_tab = ComponentTab(
            parent     = nb,
            colors     = COLORS,
            # The component tab can read the catalog for future control lookups
            get_catalog= lambda: self._catalog,
            # The component tab can read the profile for future filtering
            get_profile= lambda: self._profile,
            # Let the component tab update the main window status bar
            set_status = lambda msg: self._status_lbl.config(text=msg),
        )
        nb.add(self._component_tab, text="⚙  Component Editor")

        # ── SSP Editor tab ────────────────────────────────────────────────────
        self._ssp_tab = SSPTab(
            parent     = nb,
            colors     = COLORS,
            # The SSP tab needs to read the profile when saving
            get_profile= lambda: self._profile,
            # The SSP tab needs to read the catalog as a fallback reference
            get_catalog= lambda: self._catalog,
            # The SSP tab can update the main status bar via this callback
            set_status = lambda msg: self._status_lbl.config(text=msg),
        )
        nb.add(self._ssp_tab, text="🛡  SSP Editor")

    # =========================================================================
    # STATUS BAR
    # =========================================================================

    def _build_statusbar(self):
        """
        Create the status bar — a thin strip at the very bottom of the window
        that shows messages like "Loaded catalog: ISM_catalog.json".

        It also shows a control count on the right side.
        """
        C  = COLORS
        sb = tk.Frame(self, bg=C["HEADER_BG"], height=26)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)   # Keep exactly 26px tall

        # Left side: general status message
        self._status_lbl = tk.Label(
            sb,
            text="No catalog loaded — click '📂 Open Catalog' to begin.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10), anchor="w",
        )
        self._status_lbl.pack(side="left", padx=10)

        # Right side: "Showing X of Y controls"
        self._count_lbl = tk.Label(
            sb, text="",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10), anchor="e",
        )
        self._count_lbl.pack(side="right", padx=10)

    # =========================================================================
    # FILE LOADING
    # =========================================================================

    def _open_catalog(self):
        """
        Ask the user to select an OSCAL catalog JSON file, load it,
        and update the catalog card and control list.
        """
        C = COLORS

        # Open a file browser dialog. Returns the chosen path, or "" if cancelled.
        path = filedialog.askopenfilename(
            title="Open OSCAL Catalog",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return   # User cancelled — do nothing

        # Try to load the file. If it fails, show an error message.
        try:
            catalog = load_catalog(path)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            # json.JSONDecodeError: file is not valid JSON
            # KeyError / ValueError: file doesn't have the right OSCAL structure
            messagebox.showerror("Failed to load catalog", str(exc))
            return

        # Store the loaded catalog and clear any previously loaded profile
        self._catalog = catalog
        self._profile = None   # Loading a new catalog clears the profile

        # Update the class filter dropdown with the classes found in this catalog
        classes = sorted({c["class"] for c in catalog["controls"] if c["class"]})
        self._class_combo["values"] = ["All"] + classes
        self._selected_class.set("All")
        self._search_var.set("")   # Clear the search box

        # ── Update the catalog info card ──────────────────────────────────────
        self._cat_title_lbl.config(text=catalog["title"], fg=C["TEXT"])
        self._cat_version_lbl.config(text=catalog["version"])
        self._cat_oscal_lbl.config(text=catalog["oscal_version"])
        self._cat_published_lbl.config(text=catalog["published"])
        self._cat_modified_lbl.config(text=catalog["last_modified"])
        # Show the total number of controls in the catalog
        self._cat_controls_lbl.config(text=str(len(catalog["controls"])))

        # ── Reset the profile info card (profile was cleared above) ───────────
        self._prof_title_lbl.config(text="No profile loaded", fg=C["SUBTEXT"])
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")
        # Disable Clear Profile (no profile to clear)
        self._clear_profile_btn.config(state="disabled")

        # ── Tell the tabs about the new data ─────────────────────────────────
        # load_controls() replaces the tree contents with the full control list
        self._catalog_tab.load_controls(catalog["controls"])
        # Update the SSP tab's profile info box (will show the warning)
        self._ssp_tab.refresh_profile_box()

        self._status_lbl.config(text=f"Loaded catalog: {Path(path).name}")
        self._update_count()

    def _open_profile(self):
        """
        Ask the user to select an OSCAL profile JSON file, load it,
        and filter the control list to only show selected controls.

        A profile must be loaded AFTER a catalog — it filters the catalog.
        """
        C = COLORS

        # Require a catalog to be loaded first
        if not self._catalog:
            messagebox.showwarning(
                "No catalog loaded",
                "Please open a catalog file before loading a profile."
            )
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

        # Store the profile and enable the Clear Profile button
        self._profile = profile
        self._clear_profile_btn.config(state="normal")

        # ── Update the profile info card ──────────────────────────────────────
        self._prof_title_lbl.config(text=profile["title"], fg=C["YELLOW"])
        self._prof_version_lbl.config(text=profile["version"])
        self._prof_oscal_lbl.config(text=profile["oscal_version"])
        self._prof_published_lbl.config(text=profile["published"])
        self._prof_modified_lbl.config(text=profile["last_modified"])
        # Show how many controls this profile selects
        self._prof_controls_lbl.config(text=str(len(profile["ids"])))

        # Tell the SSP tab to update its profile info box
        self._ssp_tab.refresh_profile_box()

        # Re-apply all filters — the profile filter is now active
        self._apply_filters()
        self._status_lbl.config(text=f"Profile applied: {Path(path).name}")

    def _clear_profile(self):
        """
        Clear the loaded profile and return to showing the full catalog.
        """
        C = COLORS

        self._profile = None
        # Disable the button again (nothing to clear now)
        self._clear_profile_btn.config(state="disabled")

        # Reset the profile info card to its default state
        self._prof_title_lbl.config(text="No profile loaded", fg=C["SUBTEXT"])
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")

        # Tell the SSP tab to show the "no profile" warning
        self._ssp_tab.refresh_profile_box()

        # Re-apply filters — profile filter is now inactive, shows all controls
        self._apply_filters()
        self._status_lbl.config(text="Profile cleared — showing full catalog.")

    # =========================================================================
    # FILTERING
    # =========================================================================

    def _apply_filters(self):
        """
        Pass the current filter settings to the CatalogTab so it can
        update which controls are shown in the list.

        This is called whenever any filter changes:
          - Profile loaded/cleared    → different set of control IDs
          - Class dropdown changed    → different class filter
          - User types in search box  → different search term
        """
        if not self._catalog:
            return   # Nothing to filter if no catalog is loaded

        # Get the profile's control IDs (or None if no profile is loaded)
        profile_ids = self._profile["ids"] if self._profile else None

        # Delegate filtering to the CatalogTab — it owns the tree widget
        self._catalog_tab.apply_filters(
            profile_ids  = profile_ids,
            class_filter = self._selected_class.get(),
            search_term  = self._search_var.get(),
        )
        # Update the status bar count
        self._update_count()

    def _on_filter(self, _event=None):
        """Called by the class dropdown when the user selects a class."""
        self._apply_filters()

    def _on_search(self, *_args):
        """
        Called automatically whenever the search box content changes.
        The *_args accepts the arguments tkinter passes but we don't use them.
        """
        self._apply_filters()

    def _update_count(self):
        """
        Update the control count label in the status bar.

        Shows either "1150 controls" or "Showing 42 of 1150 controls"
        depending on whether any filtering is active.
        """
        # Ask the catalog tab for the current counts
        total, shown = self._catalog_tab.control_count()

        if total == 0:
            # No catalog loaded yet
            self._count_lbl.config(text="")
        elif shown == total:
            # No filtering active — show everything
            self._count_lbl.config(text=f"{total} controls")
        else:
            # Filtered — show the subset count
            self._count_lbl.config(text=f"Showing {shown} of {total} controls")
