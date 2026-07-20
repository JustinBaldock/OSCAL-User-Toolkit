"""
data_sources_tab.py — Data Sources tab for the OSCAL User Toolkit.

Browses the Library's catalogs/ and profiles/ subfolders (see settings.py
and oscal_user_toolkit_design_document.md §10.13) and is the app's only
way to open or clear the active catalog/profile — this replaced the
toolbar's "Open Catalog"/"Open Profile"/"Clear Profile" buttons, which are
no longer built in app.py.

This tab holds no data of its own: it reads the Library folder from disk
on refresh() and reflects app.py's currently-loaded catalog/profile via
the get_catalog/get_profile callbacks. All loading/clearing actions are
delegated back to app.py (open_catalog/open_profile/clear_profile), which
remain the single source of truth for self._catalog/self._profile.
"""

import json
import tkinter as tk
from tkinter import ttk

from .tab_utils import attach_tooltip


class DataSourcesTab(tk.Frame):
    """Browses the Library's catalogs/profiles and manages the active selection."""

    def __init__(self, parent, colors, get_library_path=None, get_catalog=None,
                 get_profile=None, open_catalog=None, open_profile=None,
                 clear_profile=None, set_status=None, get_resolver=None, **kwargs):
        """
        Parameters:
            parent           - The ttk.Notebook this tab lives inside
            colors           - Shared colour dictionary from app.py
            get_library_path - Callback: returns the configured Library Path
            get_catalog      - Callback: returns the currently loaded catalog dict or None
            get_profile      - Callback: returns the currently loaded profile dict or None
            open_catalog     - Callback: app.py._open_catalog(path=None) — loads a
                                catalog; path=None triggers app.py's own file dialog
            open_profile     - Callback: app.py._open_profile(path=None), same shape
            clear_profile    - Callback: app.py._clear_profile()
            set_status       - Callback: updates the main window status bar text
            get_resolver     - Callback: returns app.py's CatalogResolver, used
                                only to show how many catalogs a multi-catalog
                                profile has auto-loaded (see models.CatalogResolver)
        """
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors           = colors
        self._get_library_path = get_library_path or (lambda: None)
        self._get_catalog      = get_catalog       or (lambda: None)
        self._get_profile      = get_profile       or (lambda: None)
        self._open_catalog     = open_catalog       or (lambda path=None: None)
        self._open_profile     = open_profile       or (lambda path=None: None)
        self._clear_profile    = clear_profile      or (lambda: None)
        self._set_status       = set_status         or (lambda msg: None)
        self._get_resolver     = get_resolver       or (lambda: None)

        self._build()

    def theme_refresh(self):
        """Rebuild this tab's widgets after the colour theme changes, then repopulate."""
        self.configure(bg=self._colors["BG"])
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()

    def refresh(self):
        """
        Public method called by app.py whenever the catalog/profile changes
        elsewhere (e.g. via Open Workspace), or the Library folder changes,
        so this tab's lists and "currently loaded" labels stay in sync.
        """
        self._refresh_catalog_list()
        self._refresh_profile_list()
        self._refresh_current_labels()

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _build(self):
        C = self._colors
        tk.Label(
            self, text="📚  Data Sources",
            bg=C["BG"], fg=C["ACCENT"],
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            self,
            text="Browse and load catalogs/profiles from the Library folder — "
                 "this is now the only place to open or clear a catalog/profile.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 11),
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 4))

        self._library_lbl = tk.Label(
            self, text="", bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"),
        )
        self._library_lbl.pack(anchor="w", padx=20, pady=(0, 12))

        # Currently loaded catalog/profile status row
        status_row = tk.Frame(self, bg=C["CARD_BG"], highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        status_row.pack(fill="x", padx=20, pady=(0, 12))
        self._current_catalog_lbl = tk.Label(
            status_row, text="", bg=C["CARD_BG"], fg=C["TEXT"],
            font=("Helvetica", 10, "bold"), anchor="w",
        )
        self._current_catalog_lbl.pack(anchor="w", padx=10, pady=(8, 2))
        self._current_profile_lbl = tk.Label(
            status_row, text="", bg=C["CARD_BG"], fg=C["TEXT"],
            font=("Helvetica", 10, "bold"), anchor="w",
        )
        self._current_profile_lbl.pack(anchor="w", padx=10, pady=(0, 4))
        self._clear_profile_btn = tk.Button(
            status_row, text="✕  Clear Profile", command=self._on_clear_profile,
            bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        )
        self._clear_profile_btn.pack(anchor="w", padx=10, pady=(0, 8))

        # Two side-by-side panes: Catalogs (left) and Profiles (right)
        panes = tk.Frame(self, bg=C["BG"])
        panes.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._catalog_tree = self._build_pane(
            panes, side="left", padx=(0, 10),
            heading="📄  Catalogs", load_cmd=self._on_load_catalog,
            browse_cmd=self._on_browse_catalog,
        )
        self._profile_tree = self._build_pane(
            panes, side="left", padx=(10, 0),
            heading="🔖  Profiles", load_cmd=self._on_load_profile,
            browse_cmd=self._on_browse_profile,
        )

        self.refresh()

    def _build_pane(self, parent, side, padx, heading, load_cmd, browse_cmd):
        """Build one Catalogs/Profiles pane and return its Treeview."""
        C = self._colors
        pane = tk.Frame(parent, bg=C["CARD_BG"], highlightthickness=1,
                         highlightbackground=C["HEADER_BG"])
        pane.pack(side=side, fill="both", expand=True, padx=padx)

        header = tk.Frame(pane, bg=C["HEADER_BG"])
        header.pack(fill="x")
        tk.Label(
            header, text=heading, bg=C["HEADER_BG"], fg=C["ACCENT"],
            font=("Helvetica", 11, "bold"),
        ).pack(side="left", padx=10, pady=6)

        btn_row = tk.Frame(pane, bg=C["CARD_BG"])
        btn_row.pack(fill="x", padx=8, pady=6)
        tk.Button(
            btn_row, text="📂  Load Selected", command=load_cmd,
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            btn_row, text="…  Browse Elsewhere", command=browse_cmd,
            bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left", padx=8)
        refresh_btn = tk.Button(
            btn_row, text="🔄", command=self.refresh,
            bg=C["HEADER_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
            relief="flat", padx=8, pady=3, cursor="hand2",
        )
        refresh_btn.pack(side="left")
        attach_tooltip(refresh_btn, "Refresh this list from disk", C)

        tree_frame = tk.Frame(pane, bg=C["CARD_BG"])
        tree_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        tree = ttk.Treeview(
            tree_frame, columns=("title",), show="headings",
            selectmode="browse",
        )
        tree.heading("title", text="File / Title", anchor="w")
        tree.column("title", anchor="w", stretch=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", lambda _e: load_cmd())
        return tree

    # =========================================================================
    # LIST POPULATION
    # =========================================================================

    @staticmethod
    def _describe_json_file(path, top_key):
        """
        Return "filename.json — Title" if the file's metadata.title can be
        read, otherwise just "filename.json". Never raises — a malformed
        or unrelated JSON file just falls back to showing its filename.
        """
        name = path.name
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            title = data.get(top_key, {}).get("metadata", {}).get("title")
            return f"{name} — {title}" if title else name
        except (OSError, json.JSONDecodeError, AttributeError):
            return name

    def _library_subfolder(self, name):
        """Return the Library's <name> subfolder Path, or None if no library is set."""
        library = self._get_library_path()
        return (library / name) if library else None

    def _refresh_catalog_list(self):
        self._populate_tree(self._catalog_tree, self._library_subfolder("catalogs"), "catalog")

    def _refresh_profile_list(self):
        self._populate_tree(self._profile_tree, self._library_subfolder("profiles"), "profile")

    def _populate_tree(self, tree, folder, top_key):
        tree.delete(*tree.get_children())
        if not folder or not folder.is_dir():
            return
        for path in sorted(folder.glob("*.json")):
            tree.insert("", "end", iid=str(path), values=(self._describe_json_file(path, top_key),))

    def _refresh_current_labels(self):
        C = self._colors
        library = self._get_library_path()
        self._library_lbl.config(
            text=f"Library folder: {library}" if library else "No Library folder configured."
        )

        catalog  = self._get_catalog()
        resolver = self._get_resolver()
        extra    = (len(resolver.catalogs()) - 1) if (catalog and resolver and not resolver.is_empty()) else 0
        extra_note = f"  (+{extra} more via profile imports)" if extra > 0 else ""
        self._current_catalog_lbl.config(
            text=f"📄 Current catalog: {catalog['title']}{extra_note}" if catalog else "📄 No catalog loaded.",
            fg=C["TEXT"] if catalog else C["SUBTEXT"],
        )
        profile = self._get_profile()
        self._current_profile_lbl.config(
            text=f"🔖 Current profile: {profile['title']}" if profile else "🔖 No profile loaded.",
            fg=C["TEXT"] if profile else C["SUBTEXT"],
        )
        self._clear_profile_btn.config(state="normal" if profile else "disabled")

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def _on_load_catalog(self):
        sel = self._catalog_tree.selection()
        if not sel:
            return
        self._open_catalog(sel[0])
        self.refresh()

    def _on_load_profile(self):
        sel = self._profile_tree.selection()
        if not sel:
            return
        self._open_profile(sel[0])
        self.refresh()

    def _on_browse_catalog(self):
        self._open_catalog()   # path=None triggers app.py's own file dialog
        self.refresh()

    def _on_browse_profile(self):
        self._open_profile()
        self.refresh()

    def _on_clear_profile(self):
        self._clear_profile()
        self.refresh()
