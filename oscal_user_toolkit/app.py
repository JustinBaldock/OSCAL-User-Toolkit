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
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path   # Cross-platform file path handling

# Import the data-loading functions from our models module
from .models import (load_catalog, load_profile, validate_oscal_file,
                     build_workspace_manifest, load_workspace_manifest)
from . import settings

# Import the tab classes
from .catalog_tab import CatalogTab
from .ssp_tab import SSPTab
from .component_tab import ComponentTab
from .capability_tab import CapabilityTab
from .poam_tab import POAMTab
from .ap_tab import APTab
from .ar_tab import ARTab
from .dashboard_tab import DashboardTab
from .workspace_tab import WorkspaceTab
from .data_sources_tab import DataSourcesTab

# ── Shared colour palette ─────────────────────────────────────────────────────
# All colours are defined once here as a dictionary and passed to each tab
# (colors=COLORS), so changing a colour here updates the whole application.
# Every tab stores this SAME dict object as self._colors — dicts are passed
# by reference in Python, so mutating COLORS's contents in place (see
# set_theme() below) is visible to every tab immediately, without needing to
# hand a new dict to each one. Colours are hex strings: "#RRGGBB".
#
# Two named palettes with IDENTICAL keys support the dark/light toggle on the
# Workspace tab. COLORS itself starts as a copy of DARK_COLORS and is mutated
# in place when the theme changes — see OSCALApp.set_theme().
# WHY TWO VARIANTS OF EACH ACCENT COLOUR (e.g. BLUE and BLUE_BG)
# -----------------------------------------------------------------
# ACCENT/BLUE/GREEN/YELLOW/RED/TEAL serve two different jobs that need
# different lightness in light mode:
#   1. As TEXT/heading colour sitting directly on a plain BG/HEADER_BG/
#      CARD_BG background — needs to be dark & saturated in light mode
#      (mirroring how TEXT itself flips dark<->light) so it reads clearly
#      against a light page.
#   2. As the BACKGROUND FILL of a button or badge, paired with fixed
#      BUTTON_TEXT (near-black) on top — needs to stay light/pastel in
#      BOTH modes, since black text on a dark, saturated fill would be
#      unreadable (that combination was the actual bug reported).
# The plain keys (BLUE, GREEN, ...) serve job 1. The _BG keys (BLUE_BG,
# GREEN_BG, ...) serve job 2. In dark mode both jobs happen to want the
# same light pastel colour, so the _BG keys just duplicate the plain ones.
DARK_COLORS = {
    "BG":          "#1e1e2e",   # Main background (very dark navy)
    "SIDEBAR_BG":  "#181825",   # Slightly darker background for the list pane
    "HEADER_BG":   "#313244",   # Section headers and toolbar
    "INFO_BG":     "#252535",   # Info panel background
    "CARD_BG":     "#2a2a3d",   # Card/form field backgrounds
    "ACCENT":      "#cba6f7",   # Lavender — used for headings and highlights
    "TEXT":        "#cdd6f4",   # Main text colour (light blue-white)
    "SUBTEXT":     "#a6adc8",   # Secondary/hint text (slightly dimmer)
    "GREEN":       "#a6e3a1",   # Success / positive indicators
    "YELLOW":      "#f9e2af",   # Warnings and profile info
    "RED":         "#f38ba8",   # Errors and alerts
    "BLUE":        "#89b4fa",   # Information and links
    "TEAL":        "#94e2d5",   # Principle controls in the catalog list
    "ORANGE":      "#fab387",   # Reserved for future use
    # Button/badge fill variants — see module-level note above.
    # Same values as the plain keys: dark mode's pastels already work for
    # both text-on-page and fill-under-black-text uses.
    "ACCENT_BG":   "#cba6f7",
    "GREEN_BG":    "#a6e3a1",
    "YELLOW_BG":   "#f9e2af",
    "RED_BG":      "#f38ba8",
    "BLUE_BG":     "#89b4fa",
    "TEAL_BG":     "#94e2d5",
    # Text colour used on top of the _BG fills above. Fixed (not
    # theme-swapped) because every _BG colour is light/pastel in BOTH
    # palettes by design.
    "BUTTON_TEXT": "#1a1a1a",
}

LIGHT_COLORS = {
    "BG":          "#f4f4f8",   # Main background (soft off-white)
    "SIDEBAR_BG":  "#e9e9f2",   # Slightly darker background for the list pane
    "HEADER_BG":   "#dcdce8",   # Section headers and toolbar
    "INFO_BG":     "#eceef5",   # Info panel background
    "CARD_BG":     "#ffffff",   # Card/form field backgrounds
    "ACCENT":      "#6a3fc4",   # Purple — used for headings and highlights (text use)
    "TEXT":        "#1e1e2e",   # Main text colour (near-black)
    "SUBTEXT":     "#5c5c70",   # Secondary/hint text
    "GREEN":       "#1f8a4c",   # Success / positive indicators (text use)
    "YELLOW":      "#7a5606",   # Warnings and profile info (text use)
    "RED":         "#c53f5c",   # Errors and alerts (text use)
    "BLUE":        "#2864c9",   # Information and links (text use)
    "TEAL":        "#128a76",   # Principle controls in the catalog list (text use)
    "ORANGE":      "#c4622a",   # Reserved for future use
    # Button/badge fill variants — pastel, NOT the darker text-use shades
    # above, and paired with fixed BUTTON_TEXT. See module-level note.
    "ACCENT_BG":   "#ab95e3",
    "GREEN_BG":    "#a5d6a7",
    "YELLOW_BG":   "#ffe082",
    "RED_BG":      "#ef9a9a",
    "BLUE_BG":     "#90caf9",
    "TEAL_BG":     "#80cbc4",
    "BUTTON_TEXT": "#1a1a1a",   # Same fixed near-black as DARK_COLORS
}

COLORS = dict(DARK_COLORS)


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
        self.geometry("1400x900")    # Initial width x height in pixels
        self.minsize(1200, 700)      # Minimum window size (prevents squashing)
        self.configure(bg=COLORS["BG"])

        # ── Application state ─────────────────────────────────────────────────
        # These variables hold the currently loaded data.
        # None means "nothing loaded yet".
        self._catalog = None    # The loaded catalog dict (from models.load_catalog)
        self._profile = None    # The loaded profile dict (from models.load_profile)
        # Path of the last workspace manifest opened or saved. Used so
        # "Save Workspace" can default to overwriting the same file, and
        # as the basis for the "current system folder" that Component/
        # Capability Editor import into (see get_system_folder() below).
        self._workspace_path = None
        # Configured Library folder (catalogs/profiles/components/
        # capabilities shared across systems) — persisted via settings.py,
        # so it survives between app launches. None until first set.
        self._library_path = settings.get_library_path()
        # Current colour theme — "dark" or "light". Toggled from the
        # Workspace tab via set_theme(). See DARK_COLORS/LIGHT_COLORS above.
        self._theme = "dark"
        # Note: the class filter, search box and control count all live inside
        # CatalogTab now — they are only relevant to the catalog viewer.

        # ── Build the GUI ─────────────────────────────────────────────────────
        # Each method below creates one layer of the UI.
        # Order matters: statusbar must be packed before the notebook
        # so that it appears at the bottom.
        self._oscal_versions    = self._scan_oscal_versions()
        self._oscal_version_var = tk.StringVar(
            value=self._oscal_versions[0] if self._oscal_versions else "No versions found"
        )

        self._style_ttk()       # Apply custom colours to ttk widgets
        self._build_toolbar()   # Top bar with Open Catalog/Profile buttons
        self._build_info_panel()# Cards showing catalog and profile metadata
        self._build_notebook()  # Tabbed area with CatalogTab and SSPTab
        self._build_statusbar() # Bottom bar with status message

        # Guard against closing the window with unsaved changes in any editor tab.
        # tkinter fires WM_DELETE_WINDOW when the user clicks the × button.
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =========================================================================
    # OSCAL VERSION DISCOVERY
    # =========================================================================

    def _scan_oscal_versions(self):
        """
        Scan the oscal/ folder (sibling of this package) for zip files and
        return a sorted list of version labels derived from their filenames.

        A file named 'oscal-1.2.2.zip' becomes the label 'v1.2.2'.
        Versions are sorted newest-first so the dropdown defaults to the
        latest available version.

        Returns an empty list if the folder does not exist or contains no zips.
        """
        oscal_dir = Path(__file__).parent.parent / "oscal"
        if not oscal_dir.is_dir():
            return []

        versions = []
        for path in oscal_dir.glob("*.zip"):
            if zipfile.is_zipfile(path):
                # Strip leading 'oscal-' and trailing '.zip', e.g. 'oscal-1.2.2.zip' → '1.2.2'
                name = path.stem  # 'oscal-1.2.2'
                label = name.removeprefix("oscal-")  # '1.2.2'
                versions.append((label, path))

        # Sort by parsed version tuple so '1.2.10' > '1.2.2' correctly
        versions.sort(key=lambda x: [int(p) for p in x[0].split(".") if p.isdigit()], reverse=True)
        self._oscal_version_paths = {label: path for label, path in versions}
        return [f"v{label}" for label, _ in versions]

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
    # THEME (DARK / LIGHT)
    # =========================================================================

    def set_theme(self, theme_name):
        """
        Switch the whole application between the "dark" and "light" palettes.

        WHY THIS WORKS WITHOUT RECREATING EVERY TAB
        ---------------------------------------------
        Every tab was constructed with colors=COLORS — the SAME dict object,
        not a copy. Mutating COLORS's contents in place (COLORS.clear() then
        COLORS.update(...)) is therefore visible to every tab's self._colors
        immediately, with no need to hand out a new dict.

        That alone does nothing to widgets that already exist, though —
        plain tk widgets read a colour once at creation time and never look
        at the dict again. So after swapping the palette, this method:

          1. Re-runs _style_ttk() so ttk widgets (Treeview, Notebook,
             Combobox, Scrollbar) re-read the new colours from their style,
             which they DO support live.
          2. Destroys and rebuilds this app's own toolbar, info panel, and
             status bar frames (plain tk widgets), restoring their dynamic
             content (status text, loaded catalog/profile info) from state
             already held on self — nothing here is destroyed except widgets.
          3. Calls theme_refresh() on every tab. Each tab's theme_refresh()
             destroys only that tab's OWN CHILD WIDGETS (not the tab object
             itself, and not the Notebook that owns it), rebuilds them via
             its existing _build() method, then repopulates them from the
             SAME internal data dicts it already held (self._ssp,
             self._components, etc.) — those were never touched, so no
             document data is lost by toggling the theme.

        The ttk.Notebook widget itself is never destroyed — only its style
        changes and the child tab frames inside it get their own contents
        rebuilt in place.
        """
        if theme_name == self._theme:
            return   # Already in this theme — nothing to do

        new_palette = DARK_COLORS if theme_name == "dark" else LIGHT_COLORS
        COLORS.clear()
        COLORS.update(new_palette)
        self._theme = theme_name

        self.configure(bg=COLORS["BG"])
        self._style_ttk()

        # ── Rebuild this app's own chrome, preserving its dynamic content ──────
        saved_status_text = self._status_lbl.cget("text")

        self._toolbar_frame.destroy()
        self._info_panel_frame.destroy()
        self._statusbar_frame.destroy()

        # before=self._notebook is required here (but not at initial startup,
        # when the Notebook doesn't exist yet) — see _build_toolbar()'s
        # docstring for why plain pack(side="top") would stack these below
        # the Notebook instead of above it once it already exists.
        self._build_toolbar(before=self._notebook)
        self._build_info_panel(before=self._notebook)
        self._build_statusbar()

        self._status_lbl.config(text=saved_status_text)
        if self._catalog:
            self._apply_catalog_info_labels(self._catalog)
        if self._profile:
            self._apply_profile_info_labels(self._profile)
            self._clear_profile_btn.config(state="normal")

        # ── Rebuild every tab's own widgets in place ────────────────────────────
        # Order doesn't matter — each tab only touches its own children.
        for tab in (self._workspace_tab, self._data_sources_tab, self._dashboard_tab,
                    self._catalog_tab, self._component_tab, self._capability_tab,
                    self._ssp_tab, self._ap_tab, self._ar_tab, self._poam_tab):
            tab.theme_refresh()

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _build_toolbar(self, before=None):
        """
        Create the top toolbar with:
          - Open Catalog button (purple)
          - Open Profile button (yellow)
          - Clear Profile button (disabled until a profile is loaded)
          - App title label

        The class filter dropdown, search box, and control count have moved
        into the Catalog Viewer tab (catalog_tab.py) where they belong —
        they are only relevant when browsing the catalog.

        Parameters:
            before - Optional widget to pack this frame immediately above.
                     Used by set_theme() when rebuilding the toolbar after
                     the Notebook already exists — plain pack(side="top")
                     would otherwise stack the new frame BELOW the Notebook
                     rather than above it, since the Notebook was packed
                     first and pack() stacks same-side widgets in call order.
        """
        C  = COLORS
        tb = tk.Frame(self, bg=C["HEADER_BG"], height=54)
        self._toolbar_frame = tb   # Stored so set_theme() can destroy+rebuild it
        tb.pack(fill="x", side="top", **({"before": before} if before else {}))
        tb.pack_propagate(False)

        # ── OSCAL version selector ────────────────────────────────────────────
        tk.Label(
            tb, text="OSCAL Version:",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11),
        ).pack(side="left", padx=(14, 4), pady=10)

        version_box = ttk.Combobox(
            tb,
            textvariable=self._oscal_version_var,
            values=self._oscal_versions,
            state="readonly",
            width=9,
            font=("Helvetica", 11),
        )
        version_box.pack(side="left", padx=(0, 14), pady=10)

        # ── Left-side buttons ─────────────────────────────────────────────────
        tk.Button(
            tb, text="📂  Open Catalog", command=self._open_catalog,
            bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=14, pady=10)

        tk.Button(
            tb, text="🔖  Open Profile", command=self._open_profile,
            bg=C["YELLOW_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#f5c842", activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=(0, 8), pady=10)

        # Clear Profile button — stored as an instance variable so we can
        # enable/disable it when a profile is loaded/cleared.
        self._clear_profile_btn = tk.Button(
            tb, text="✕  Clear Profile", command=self._clear_profile,
            bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=10, pady=6, cursor="hand2",
            state="disabled",              # Greyed out until a profile is loaded
            disabledforeground="#555570",
        )
        self._clear_profile_btn.pack(side="left", pady=10)

        # Visual separator
        tk.Frame(tb, bg=C["SUBTEXT"], width=1).pack(
            side="left", fill="y", padx=8, pady=12
        )

        # Library Folder button — sets/changes the persisted library path
        # (settings.py) that Component/Capability Editor import from.
        tk.Button(
            tb, text="📚  Library Folder", command=self._set_library_folder,
            bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 12, "bold"),
            relief="flat", padx=14, pady=6, cursor="hand2",
        ).pack(side="left", padx=(8, 8), pady=10)

        self._library_path_lbl = tk.Label(
            tb, text=self._library_path_display(),
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._library_path_lbl.pack(side="left", padx=(0, 8))

        # App title
        tk.Label(
            tb, text="OSCAL User Toolkit",
            bg=C["HEADER_BG"], fg=C["TEXT"],
            font=("Helvetica", 14, "bold"),
        ).pack(side="left", padx=12)

    # =========================================================================
    # INFO PANEL
    # =========================================================================

    def _build_info_panel(self, before=None):
        """
        Create the info panel — two side-by-side cards showing metadata
        about the currently loaded catalog (left) and profile (right).

        Each card has:
          - A coloured header bar with an icon and the document title
          - A row of labelled fields (Version, OSCAL Version, etc.)

        Parameters:
            before - Optional widget to pack this frame immediately above.
                     See _build_toolbar() for why this is needed during a
                     theme rebuild.
        """
        C     = COLORS
        panel = tk.Frame(self, bg=C["INFO_BG"])
        self._info_panel_frame = panel   # Stored so set_theme() can destroy+rebuild it
        panel.pack(fill="x", side="top", **({"before": before} if before else {}))

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
            get_catalog= lambda: self._catalog,
            get_profile= lambda: self._profile,
            set_status = lambda msg: self._status_lbl.config(text=msg),
            get_oscal_version = lambda: self._oscal_version_var.get().lstrip("v"),
            get_library_path  = self.get_library_path,
            get_system_folder = self.get_system_folder,
        )
        nb.add(self._component_tab, text="⚙  Component Editor")

        # ── Capability Editor tab ─────────────────────────────────────────────
        # Sits between Component Editor and SSP Editor.
        # Requires a catalog loaded AND at least one component in the
        # Component Editor before editing is allowed.
        self._capability_tab = CapabilityTab(
            parent              = nb,
            colors              = COLORS,
            get_catalog         = lambda: self._catalog,
            get_components      = lambda: self._component_tab._components,
            get_profile         = lambda: self._profile,
            set_status          = lambda msg: self._status_lbl.config(text=msg),
            get_oscal_version   = lambda: self._oscal_version_var.get().lstrip("v"),
            get_oscal_zip_path  = lambda: self._oscal_version_paths.get(
                self._oscal_version_var.get().lstrip("v")
            ),
            # Allows CapabilityTab to import bundled components from saved
            # capability files directly into ComponentTab's live list.
            add_component       = self._component_tab.add_component,
            get_library_path    = self.get_library_path,
            get_system_folder   = self.get_system_folder,
        )
        nb.add(self._capability_tab, text="🔗  Capability Editor")

        # Wire up the component-change notification so the Capability Editor
        # re-evaluates its guard whenever the component list grows or shrinks.
        # This must be done AFTER both tabs exist (they reference each other).
        self._component_tab.set_on_components_changed(
            self._capability_tab.on_state_changed
        )

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
            # Lets Section 8 import components straight from the Component Editor
            get_components    = lambda: self._component_tab._components,
            # Passes the toolbar OSCAL version selection so saved files declare
            # the correct oscal-version field
            get_oscal_version = lambda: self._oscal_version_var.get().lstrip("v"),
            # Lets the SSP tab's "Change Profile…" button trigger the toolbar action
            open_profile      = self._open_profile,
            # Provides the draw.io export with the live list of loaded capabilities
            # from the Capability Editor tab. The lambda is evaluated at export time,
            # not at construction time, so it always reflects the current state.
            get_capabilities  = lambda: self._capability_tab._capabilities,
        )
        nb.add(self._ssp_tab, text="🛡  SSP Editor")

        # ── Assessment Plan Editor tab ────────────────────────────────────────
        self._ap_tab = APTab(
            parent            = nb,
            colors            = COLORS,
            set_status        = lambda msg: self._status_lbl.config(text=msg),
            get_oscal_version = lambda: self._oscal_version_var.get().lstrip("v"),
            get_profile       = lambda: self._profile,
        )
        nb.add(self._ap_tab, text="📝  Assessment Plan")

        # ── Assessment Results Editor tab ─────────────────────────────────────
        # Must be created before POAMTab so get_poam_tab can reference it,
        # but POAMTab must exist first for the lambda to resolve at call time.
        # We create POAMTab first (not yet added to nb), then ARTab, then add
        # POAMTab to nb last so the tab order is AP → AR → POA&M.
        self._poam_tab = POAMTab(
            parent     = nb,
            colors     = COLORS,
            set_status = lambda msg: self._status_lbl.config(text=msg),
            get_oscal_version = lambda: self._oscal_version_var.get().lstrip("v"),
        )

        self._ar_tab = ARTab(
            parent            = nb,
            colors            = COLORS,
            set_status        = lambda msg: self._status_lbl.config(text=msg),
            get_oscal_version = lambda: self._oscal_version_var.get().lstrip("v"),
            # Lets the AR tab push findings directly into the POA&M editor
            get_poam_tab      = lambda: self._poam_tab,
        )
        nb.add(self._ar_tab, text="🔍  Assessment Results")

        # ── POA&M Editor tab ─────────────────────────────────────────────────
        nb.add(self._poam_tab, text="📋  POA&M Editor")

        # ── Authorization Dashboard tab ───────────────────────────────────────
        # Constructed last so all tab lambdas resolve, then added at the end
        # so it appears as the FAR RIGHT tab, after POA&M Editor.
        self._dashboard_tab = DashboardTab(
            parent       = nb,
            colors       = COLORS,
            get_ssp_tab  = lambda: self._ssp_tab,
            get_ap_tab   = lambda: self._ap_tab,
            get_ar_tab   = lambda: self._ar_tab,
            get_poam_tab = lambda: self._poam_tab,
        )
        nb.add(self._dashboard_tab, text="📊  Dashboard")

        # ── Data Sources tab (placeholder) ────────────────────────────────────
        # Inserted at index 0 (before the Workspace insert below pushes it to
        # index 1), so it lands between Workspace and Catalog Viewer. No
        # real functionality yet — see data_sources_tab.py.
        self._data_sources_tab = DataSourcesTab(parent=nb, colors=COLORS)
        nb.insert(0, self._data_sources_tab, text="📚  Data Sources")

        # ── Workspace tab ──────────────────────────────────────────────────────
        # Inserted at index 0 so it appears first and is the tab shown when
        # the application starts. Provides Open/Save Workspace buttons plus
        # the static per-tab reference cards (formerly the Welcome tab).
        self._workspace_tab = WorkspaceTab(
            parent         = nb,
            colors         = COLORS,
            open_workspace = self._open_workspace,
            save_workspace = self._save_workspace,
            get_theme      = lambda: self._theme,
            set_theme      = self.set_theme,
        )
        nb.insert(0, self._workspace_tab, text="🗂  Workspace")
        nb.select(0)

    # =========================================================================
    # STATUS BAR
    # =========================================================================

    def _build_statusbar(self):
        """
        Create the status bar — a thin strip at the very bottom of the window
        that shows messages like "Loaded catalog: ISM_catalog.json".

        The control count has moved into the Catalog Viewer tab toolbar,
        where it is more contextually relevant.
        """
        C  = COLORS
        sb = tk.Frame(self, bg=C["HEADER_BG"], height=26)
        self._statusbar_frame = sb   # Stored so set_theme() can destroy+rebuild it
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self._status_lbl = tk.Label(
            sb,
            text="No catalog loaded — click '📂 Open Catalog' to begin.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10), anchor="w",
        )
        self._status_lbl.pack(side="left", padx=10)

    # =========================================================================
    # WINDOW CLOSE GUARD
    # =========================================================================

    def _on_close(self):
        """
        Called when the user clicks the window's × button.

        Checks every editor tab for unsaved changes.  If any tab has a dirty
        flag set, the user is prompted to confirm before the window closes.
        Cancelling keeps the window open so they can save first.
        """
        # Collect names of tabs that have unsaved changes.
        # Each tab exposes a _dirty bool; tabs that predate this feature
        # default to False via getattr so the check never crashes.
        dirty_tabs = []
        checks = [
            (getattr(self, "_component_tab", None), "Component Editor"),
            (getattr(self, "_capability_tab", None), "Capability Editor"),
            (getattr(self, "_ssp_tab",        None), "SSP Editor"),
            (getattr(self, "_poam_tab",        None), "POA&M Editor"),
            (getattr(self, "_ap_tab",          None), "Assessment Plan"),
            (getattr(self, "_ar_tab",          None), "Assessment Results"),
        ]
        for tab, name in checks:
            if tab is not None and getattr(tab, "_dirty", False):
                dirty_tabs.append(name)

        if dirty_tabs:
            tab_list = "\n".join(f"  • {t}" for t in dirty_tabs)
            proceed = messagebox.askyesno(
                "Unsaved Changes",
                f"The following tabs have unsaved changes:\n\n{tab_list}\n\n"
                "Exit without saving?",
                icon="warning",
            )
            if not proceed:
                return   # User chose to stay — do not close

        self.destroy()

    # =========================================================================
    # FILE LOADING
    # =========================================================================

    def _reset_profile_card(self):
        """Reset the profile info card to its default (no-profile) state."""
        C = COLORS
        self._prof_title_lbl.config(text="No profile loaded", fg=C["SUBTEXT"])
        for lbl in (self._prof_version_lbl, self._prof_oscal_lbl,
                    self._prof_published_lbl, self._prof_modified_lbl,
                    self._prof_controls_lbl):
            lbl.config(text="—")

    def _apply_catalog_info_labels(self, catalog):
        """
        Push a loaded catalog's metadata into the catalog info card labels.

        Factored out so both _open_catalog() and the theme-rebuild path in
        set_theme() (which recreates the info panel widgets from scratch)
        can populate them the same way.
        """
        C = COLORS
        self._cat_title_lbl.config(text=catalog["title"], fg=C["TEXT"])
        self._cat_version_lbl.config(text=catalog["version"])
        self._cat_oscal_lbl.config(text=catalog["oscal_version"])
        self._cat_published_lbl.config(text=catalog["published"])
        self._cat_modified_lbl.config(text=catalog["last_modified"])
        self._cat_controls_lbl.config(text=str(len(catalog["controls"])))

    def _apply_profile_info_labels(self, profile):
        """
        Push a loaded profile's metadata into the profile info card labels.

        Factored out so both _open_profile() and the theme-rebuild path in
        set_theme() can populate them the same way.
        """
        C = COLORS
        self._prof_title_lbl.config(text=profile["title"], fg=C["YELLOW"])
        self._prof_version_lbl.config(text=profile["version"])
        self._prof_oscal_lbl.config(text=profile["oscal_version"])
        self._prof_published_lbl.config(text=profile["published"])
        self._prof_modified_lbl.config(text=profile["last_modified"])
        self._prof_controls_lbl.config(text=str(len(profile["ids"])))

    def _open_catalog(self, path=None):
        """
        Load an OSCAL catalog JSON file and update the catalog card and
        control list.

        Parameters:
            path - If given, load this file directly (used by the Workspace
                   tab's "Open Workspace" action). If None (the normal
                   toolbar button case), ask the user via a file dialog.
        """
        C = COLORS

        if path is None:
            # Open a file browser dialog. Returns the chosen path, or "" if cancelled.
            path = filedialog.askopenfilename(
                title="Open OSCAL Catalog",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            )
            if not path:
                return   # User cancelled — do nothing

        # Try to parse the raw JSON first so we can validate it before loading.
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as exc:
            messagebox.showerror("Failed to load catalog", str(exc))
            return

        # ── Schema validation ─────────────────────────────────────────────────
        # Use the schema bundled in the selected OSCAL version zip.
        version_label = self._oscal_version_var.get().lstrip("v")  # e.g. '1.2.2'
        zip_path = self._oscal_version_paths.get(version_label)
        if zip_path:
            valid, errors = validate_oscal_file(
                raw, "oscal_catalog_schema.json", zip_path
            )
            if not valid:
                detail = "\n".join(errors)
                proceed = messagebox.askyesno(
                    "Schema validation failed",
                    f"This file does not fully conform to the OSCAL {version_label} "
                    f"catalog schema.\n\n{detail}\n\n"
                    "Load it anyway?",
                    icon="warning",
                )
                if not proceed:
                    return

        # Try to load the file. If it fails, show an error message.
        try:
            catalog = load_catalog(path)
        except (KeyError, ValueError) as exc:
            messagebox.showerror("Failed to load catalog", str(exc))
            return

        # Store the loaded catalog and clear any previously loaded profile
        self._catalog = catalog
        self._profile = None   # Loading a new catalog clears the profile

        # ── Update the catalog info card ──────────────────────────────────────
        self._apply_catalog_info_labels(catalog)

        # ── Reset the profile info card (profile was cleared above) ───────────
        self._reset_profile_card()
        self._clear_profile_btn.config(state="disabled")

        # ── Tell the tabs about the new data ─────────────────────────────────
        # load_controls() hands the full control list to the CatalogTab, which
        # also resets its own class filter, search box, and count label.
        self._catalog_tab.load_controls(catalog["controls"])
        self._ssp_tab.refresh_profile_box()
        self._component_tab.on_catalog_or_profile_changed()
        # Notify the capability tab — catalog changed, re-evaluate guard
        self._capability_tab.on_state_changed()

        self._status_lbl.config(text=f"Loaded catalog: {Path(path).name}")
        return True

    def _open_profile(self, path=None):
        """
        Load an OSCAL profile JSON file and filter the control list to only
        show selected controls.

        A profile must be loaded AFTER a catalog — it filters the catalog.

        Parameters:
            path - If given, load this file directly (used by the Workspace
                   tab's "Open Workspace" action). If None (the normal
                   toolbar button case), ask the user via a file dialog.
        """
        C = COLORS

        # Require a catalog to be loaded first
        if not self._catalog:
            messagebox.showwarning(
                "No catalog loaded",
                "Please open a catalog file before loading a profile."
            )
            return

        if path is None:
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
        self._apply_profile_info_labels(profile)

        self._ssp_tab.refresh_profile_box()
        self._component_tab.on_catalog_or_profile_changed()
        # Profile changed — capability control list may need to update
        self._capability_tab.on_state_changed()

        # Tell the CatalogTab to filter by the new profile's control IDs.
        # The tab keeps its own class filter and search term unchanged.
        self._catalog_tab.apply_profile(profile["ids"])
        self._status_lbl.config(text=f"Profile applied: {Path(path).name}")
        return True

    def _clear_profile(self):
        """
        Clear the loaded profile and return to showing the full catalog.
        """
        C = COLORS

        self._profile = None
        # Disable the button again (nothing to clear now)
        self._clear_profile_btn.config(state="disabled")

        # Reset the profile info card to its default state
        self._reset_profile_card()

        self._ssp_tab.refresh_profile_box()
        self._component_tab.on_catalog_or_profile_changed()
        # Profile cleared — capability control list may need to update
        self._capability_tab.on_state_changed()

        # Remove the profile filter — pass None so all controls are shown.
        # The tab keeps its own class filter and search term unchanged.
        self._catalog_tab.apply_profile(None)
        self._status_lbl.config(text="Profile cleared — showing full catalog.")

    # =========================================================================
    # LIBRARY — shared catalogs/profiles/components/capabilities folder,
    # separate from any one system's own workspace (see settings.py and
    # user_stories.md US-12/US-13 for the design behind this).
    # =========================================================================

    def _library_path_display(self):
        """Return the label text for the current library path (or 'not set')."""
        return f"📚 {self._library_path}" if self._library_path else "📚 Library: not set"

    def _set_library_folder(self):
        """
        Ask the user to choose a library folder, persist it (settings.py),
        and ensure its standard subfolders exist.
        """
        folder = filedialog.askdirectory(title="Choose Library Folder")
        if not folder:
            return
        settings.set_library_path(folder)
        self._library_path = Path(folder)
        self._library_path_lbl.config(text=self._library_path_display())
        self._status_lbl.config(text=f"Library folder set: {folder}")

    def get_library_path(self):
        """Callback passed to Component/Capability Editor: the configured library Path, or None."""
        return self._library_path

    def get_system_folder(self):
        """
        Callback passed to Component/Capability Editor: the current
        system's folder, i.e. the directory containing the currently
        open/saved workspace manifest, or None if no workspace is active.

        This is what "Import from Library" copies files into — it treats
        the workspace file's own folder as the system's folder, so every
        file for one system naturally lives together without introducing
        a second, separate "system folder" concept to track.
        """
        return Path(self._workspace_path).parent if self._workspace_path else None

    # =========================================================================
    # WORKSPACE — load/save a manifest of every file for one system
    # =========================================================================
    #
    # A workspace is a small JSON file (see build_workspace_manifest() and
    # load_workspace_manifest() in models.py) that records which catalog,
    # profile, SSP, components, capabilities, Assessment Plan, Assessment
    # Results, and POA&M files belong together for one system. These two
    # methods are the only place that knows about every other tab at once —
    # exactly the same reason DashboardTab's callbacks are wired here rather
    # than inside any individual tab.

    def _open_workspace(self):
        """
        Ask the user to choose a workspace JSON file, then load every file
        it references into the matching tab.

        Files are loaded in dependency order: catalog before profile (a
        profile cannot be applied without a catalog), then everything else.
        Any referenced file that no longer exists is skipped with a warning
        collected into the final summary rather than aborting the whole load.
        """
        path = filedialog.askopenfilename(
            title="Open Workspace",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            ws = load_workspace_manifest(path)
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            messagebox.showerror("Failed to open workspace", str(exc))
            return

        loaded  = []
        missing = []

        def _exists(p):
            return p and Path(p).is_file()

        # ── Load order matters ──────────────────────────────────────────────────
        # Catalog before profile — a profile cannot be applied without one.
        # Components and capabilities before the SSP — the SSP Editor's
        # Section 8 "Capabilities Used" table resolves each capability's
        # member components from the Capability/Component Editor's LIVE
        # lists at the moment the SSP is populated (see _refresh_cap8_tree()
        # in ssp_tab.py). If the SSP loaded first, those lists would still be
        # empty and every capability row would wrongly show "capability not
        # currently loaded in Capability Editor" even though it's about to be.
        if ws["catalog"]:
            if _exists(ws["catalog"]):
                if self._open_catalog(path=ws["catalog"]):
                    loaded.append(f"Catalog: {Path(ws['catalog']).name}")
            else:
                missing.append(f"Catalog: {ws['catalog']}")

        if ws["profile"]:
            if _exists(ws["profile"]):
                if self._open_profile(path=ws["profile"]):
                    loaded.append(f"Profile: {Path(ws['profile']).name}")
            else:
                missing.append(f"Profile: {ws['profile']}")

        if ws["components"]:
            existing = [p for p in ws["components"] if _exists(p)]
            missing += [f"Component: {p}" for p in ws["components"] if not _exists(p)]
            if existing:
                added, _skipped = self._component_tab.load_from_paths(existing)
                if added:
                    loaded.append(f"Components: {added} loaded")

        if ws["capabilities"]:
            existing = [p for p in ws["capabilities"] if _exists(p)]
            missing += [f"Capability: {p}" for p in ws["capabilities"] if not _exists(p)]
            if existing:
                added, _skipped = self._capability_tab.load_from_paths(existing)
                if added:
                    loaded.append(f"Capabilities: {added} loaded")

        if ws["ssp"]:
            if _exists(ws["ssp"]):
                if self._ssp_tab._open(path=ws["ssp"]):
                    loaded.append(f"SSP: {Path(ws['ssp']).name}")
            else:
                missing.append(f"SSP: {ws['ssp']}")

        if ws["assessment_plan"]:
            if _exists(ws["assessment_plan"]):
                if self._ap_tab._open(path=ws["assessment_plan"]):
                    loaded.append(f"Assessment Plan: {Path(ws['assessment_plan']).name}")
            else:
                missing.append(f"Assessment Plan: {ws['assessment_plan']}")

        if ws["assessment_results"]:
            if _exists(ws["assessment_results"]):
                if self._ar_tab._open(path=ws["assessment_results"]):
                    loaded.append(f"Assessment Results: {Path(ws['assessment_results']).name}")
            else:
                missing.append(f"Assessment Results: {ws['assessment_results']}")

        if ws["poam"]:
            if _exists(ws["poam"]):
                if self._poam_tab._open(path=ws["poam"]):
                    loaded.append(f"POA&M: {Path(ws['poam']).name}")
            else:
                missing.append(f"POA&M: {ws['poam']}")

        # Defensive re-sync: re-run the Capabilities Used lookup now that
        # every tab has finished loading, regardless of the order above.
        # Cheap no-op if the SSP has no capabilities_used entries.
        self._ssp_tab._refresh_cap8_tree()

        self._workspace_path = path

        summary = f"Workspace: {ws['title'] or Path(path).name}\n\n"
        summary += "Loaded:\n" + "\n".join(f"  • {x}" for x in loaded) if loaded else "Nothing was loaded."
        if missing:
            summary += "\n\nMissing (skipped):\n" + "\n".join(f"  • {x}" for x in missing)
        messagebox.showinfo("Workspace Opened", summary)
        self._status_lbl.config(text=f"Workspace opened: {Path(path).name}")

    def _save_workspace(self):
        """
        Ask the user where to save a workspace manifest, then write down the
        path of every file currently loaded across every tab, relative to
        the manifest's own location.

        Nothing is re-saved here — this only records the paths of files
        that have already been saved/opened in each tab. If a tab has
        unsaved changes, save it in that tab first so the path it records
        points at the latest version.
        """
        path = filedialog.asksaveasfilename(
            title="Save Workspace",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="workspace.json",
        )
        if not path:
            return

        # Deduplicate component/capability paths while preserving order —
        # a file may appear twice in _loaded_paths if opened then re-saved.
        def dedup(paths):
            seen = []
            for p in paths:
                if p not in seen:
                    seen.append(p)
            return seen

        manifest = build_workspace_manifest(
            workspace_path      = path,
            title               = Path(path).stem,
            catalog             = self._catalog.get("filepath") if self._catalog else None,
            profile             = self._profile.get("filepath") if self._profile else None,
            ssp                 = self._ssp_tab._current_path,
            components          = dedup(self._component_tab._loaded_paths),
            capabilities        = dedup(self._capability_tab._loaded_paths),
            assessment_plan     = self._ap_tab._current_path,
            assessment_results  = self._ar_tab._current_path,
            poam                = self._poam_tab._current_path,
        )

        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        self._workspace_path = path
        self._status_lbl.config(text=f"Workspace saved: {Path(path).name}")
        messagebox.showinfo("Workspace Saved", f"Workspace saved successfully:\n{path}")

    # =========================================================================
    # FILTERING
    # =========================================================================

    def _apply_filters(self):
        """
        Tell the CatalogTab to re-apply its filters using the current profile.

        The class filter and search term are now owned entirely by CatalogTab —
        this method only needs to pass through the profile IDs so the tab
        knows which controls to include or exclude.
        """
        if not self._catalog:
            return

        # Pass the profile's control IDs (or None for no profile filter).
        # CatalogTab combines this with its own class and search filters.
        profile_ids = self._profile["ids"] if self._profile else None
        self._catalog_tab.apply_profile(profile_ids)
