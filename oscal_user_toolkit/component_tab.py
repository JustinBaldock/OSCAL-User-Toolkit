"""
component_tab.py
================
This file defines the ComponentTab class — the middle tab of the
OSCAL User Toolkit where users create and save OSCAL Component Definition
files.

WHAT IS AN OSCAL COMPONENT?
-----------------------------
A component describes a piece of a system that helps implement security
controls. Components can be software, hardware, services, policies,
processes, procedures, plans, guidance, standards, or validation activities.

Each component definition file can contain one or more components.
Components can declare how they implement specific controls from a catalog
via the 'control-implementations' section — a core part of the schema.

STRUCTURE OF A COMPONENT (per oscal_component_metaschema.xml):
  component
    ├── title, type, description, purpose, remarks  (basic info)
    ├── props[]                                      (metadata properties)
    ├── responsible-roles[]                          (who is accountable)
    └── control-implementations[]                   (how controls are met)
          ├── uuid, source, description              (group-level info)
          └── implemented-requirements[]             (one per control)
                ├── uuid, control-id                 (which control)
                └── description                      (how it is implemented)

CATALOG + PROFILE GUARD
------------------------
Before any editing is allowed, the tab checks that an OSCAL catalog has been
loaded. A profile is optional — if loaded it filters the control list in
Section 8 to the profile's baseline; without one the full catalog is shown.
  - Without both, the control-implementations section cannot be populated

If no catalog is loaded, a clear message is shown and editing is blocked
until the user loads one in the 📚 Data Sources tab.
"""

import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import (new_uuid, now_iso, build_component_oscal_entry,
                     refresh_ctrl_list, get_source_href, get_profile_controls,
                     safe_filename_component, validate_oscal_file)
from .tab_utils import is_tab_active, attach_tooltip, make_collapsible

# =============================================================================
# CONSTANTS — Allowed values from the OSCAL Component schema
# =============================================================================

# Updated to match OSCAL 1.2.2 allowed set. Added "physical" and
# "defined-system" which were missing. (M7 fix)
COMPONENT_TYPES = [
    "defined-system", # A system defined in an SSP or component definition
    "system",         # A generic system reference
    "interconnection", # System interconnection agreement
    "software",       # Applications, operating systems
    "hardware",       # Physical or virtual hardware devices
    "service",        # External or internal services (APIs, cloud)
    "policy",         # Documented policy
    "process",        # Repeatable business or technical process
    "procedure",      # Step-by-step procedure document
    "plan",           # Formal plan (e.g. incident response)
    "guidance",       # Guidance document (e.g. configuration guide)
    "standard",       # Technical or security standard
    "validation",     # Validation or audit activity
    "physical",       # Physical facility or hardware component
]

COMPONENT_STATUS = [
    "under-development",         # Being built or planned
    "operational",               # In active use
    "disposition",               # Being retired
    "other",                     # None of the above
]

RESPONSIBLE_ROLES = [
    "asset-owner",               # Owns the asset
    "asset-administrator",       # Administers the asset
    "security-operations",       # Security operations team
    "network-operations",        # Network operations team
    "incident-response",         # Incident response team
    "help-desk",                 # Help desk / support
    "configuration-management",  # Configuration management
    "maintainer",                # Maintains the component
    "provider",                  # Provides the component
    "system-owner",              # Overall system owner
    "isso",                      # Information System Security Officer
    "authorizing-official",      # Authorises the system
]

PROP_NAMES = [
    "asset-type", "asset-id", "asset-tag", "public", "virtual",
    "implementation-point", "allows-authenticated-scan",
    "baseline-configuration-name", "release-date", "version",
    "patch-level", "model", "fqdn", "uri", "scan-type",
]

COMMON_PROTOCOLS = [
    "https", "http", "ssh", "ftp", "sftp", "smtp", "smtps",
    "pop3", "pop3s", "imap", "imaps", "dns", "ntp", "snmp",
    "syslog", "ldap", "ldaps", "kerberos", "rdp", "vnc",
    "smb", "nfs", "iscsi", "radius", "tacacs+",
]

YES_NO_VALUES     = ["yes", "no"]
IMPL_POINT_VALUES = ["internal", "external"]
ASSET_TYPE_VALUES = [
    "os", "database", "web-server", "dns-server", "email-server",
    "directory-server", "pbx", "firewall", "router", "switch",
    "storage-array", "appliance",
]

# Colour used for the "response written" dot in the control list
DOT_DONE  = "●"   # Filled circle — response has been written
DOT_EMPTY = "○"   # Empty circle  — no response yet


class ComponentTab(tk.Frame):
    """
    A self-contained OSCAL Component Definition editor panel.

    Layout:
      TOP     — Toolbar (Save, Open, New buttons + auto filename display)
      MIDDLE  — Gate panel (shown when catalog/profile not loaded)
              OR split pane:
                LEFT   — Component list + Add/Delete buttons
                RIGHT  — Scrollable component editing form (8 sections)
    """

    def __init__(self, parent, colors, get_catalog, get_profile, set_status,
                 get_oscal_version=None, get_oscal_versions=None,
                 get_oscal_version_paths=None, get_library_path=None,
                 get_system_folder=None, library_mode=False):
        """
        Initialise the ComponentTab.

        Parameters:
            parent            - The ttk.Notebook this tab lives inside
            colors            - Shared colour dictionary from app.py
            get_catalog       - Callback: returns the loaded catalog dict or None
            get_profile       - Callback: returns the loaded profile dict or None
            set_status        - Callback: updates the main window status bar text
            get_oscal_version - Optional callback returning the OSCAL version
                                string selected in the toolbar (e.g. "1.2.2").
                                Defaults to a lambda returning "1.1.2" so the
                                tab still works if constructed standalone.
            get_oscal_versions      - Optional callback returning every OSCAL
                                schema version bundled with the app (not just
                                the toolbar's current selection) — used by
                                "🔼 Upgrade OSCAL Version" to offer targets.
            get_oscal_version_paths - Optional callback returning the full
                                {version: zip_path} map, so any available
                                target version's schema can be validated
                                against, not just the currently-selected one.
            get_library_path  - Optional callback returning the configured
                                Library folder Path, or None if not set.
            get_system_folder - Optional callback returning the current
                                system's folder Path (see app.py
                                get_system_folder()), or None if no
                                workspace is active. Used by "Import from
                                Library" to know where to copy files to.
            library_mode      - When True, this instance is the Organisation
                                tab's "Library Component Editor" (see
                                user_stories.md US-14): it only ever reads/
                                writes library/components/ — no Open File(s)/
                                Open Folder/Import from Library, no save
                                location prompt (saves back to the file a
                                component was loaded from, or auto-names a
                                new one into the Library) — see
                                oscal_user_toolkit_design_document.md §10.20.
        """
        super().__init__(parent, bg=colors["BG"])

        self._colors            = colors
        self._get_catalog       = get_catalog
        self._get_profile       = get_profile
        self._set_status        = set_status
        self._get_oscal_version = get_oscal_version or (lambda: "1.1.2")
        self._get_oscal_versions      = get_oscal_versions or (lambda: [])
        self._get_oscal_version_paths = get_oscal_version_paths or (lambda: {})
        self._get_library_path  = get_library_path  or (lambda: None)
        self._get_system_folder = get_system_folder or (lambda: None)
        self._library_mode      = library_mode

        # ── File-level state ──────────────────────────────────────────────────
        # Per-component version/revision/UUID state (see design document
        # §10.21) lives on each component's own dict — "file_uuid",
        # "version", "revisions" — NOT here. A file's document uuid/version
        # are just that component's own file_uuid/version at save time
        # (see _build_single_component_oscal()).
        self._file_title   = tk.StringVar(value="")

        # ── Component list state ──────────────────────────────────────────────
        self._components      = []   # List of component dicts
        # Paths of every component file opened or saved, in load/save order.
        # Used by the Workspace tab to record which files this tab currently
        # represents. Deduplicated (order-preserving) whenever it is read.
        self._loaded_paths   = []
        # Maps component uuid -> the file path it was loaded from/saved to.
        # Only meaningful in library_mode, where Save has nowhere else to
        # ask — a component with no entry here yet is new and gets an
        # auto-generated path inside the Library on first save.
        self._component_paths = {}
        self._selected_index  = None # Index into self._components (not listbox position)
        self._dirty           = False
        self._search_after_id = None  # debounce handle for component search
        # Filtered view: list of self._components indices currently visible in
        # the listbox. A search or type-filter reduces this to a subset.
        # When no filter is active this is simply [0, 1, 2, …].
        self._filtered_indices = []
        # Sort mode: "type" = group by type then A-Z; "alpha" = A-Z only
        self._sort_mode = "type"

        # ── Control implementation state ──────────────────────────────────────
        # _ctrl_responses maps control_id → response text for the currently
        # selected component. It is loaded from the component dict whenever
        # the user selects a component, and saved back when they switch away
        # or click Apply.
        self._ctrl_responses    = {}   # {control_id: description_string}
        self._ctrl_impl_status  = {}   # {control_id: implementation-status string}
        self._selected_ctrl_id  = None # ID of the control row currently shown

        # Valid OSCAL implementation-status values (schema enum)
        self._IMPL_STATUS_VALUES = [
            "implemented", "partial", "planned",
            "alternative", "not-applicable",
        ]

        # ── External notification hook ────────────────────────────────────────
        # Called whenever self._components changes (add, delete, open, clear).
        # The app sets this after construction so the Capability Editor tab
        # can re-evaluate its guard condition whenever the component list
        # grows or shrinks. Starts as a no-op lambda so it is always safe
        # to call regardless of whether the hook has been registered yet.
        self._on_components_changed = lambda: None

        # Build the GUI
        self._build()

        # library_mode auto-loads every file in the Library's components/
        # folder right away — there is no "Open" action to trigger this
        # manually, since the whole point is that this editor only ever
        # shows/edits what's actually in the Library (see class docstring).
        if self._library_mode:
            self._load_library_folder()

    # =========================================================================
    # PUBLIC API — called by app.py when catalog/profile state changes
    # =========================================================================

    def set_on_components_changed(self, callback):
        """
        Register a callback that fires whenever the component list changes.

        Called by app.py after both the ComponentTab and CapabilityTab have
        been constructed, so the Capability Editor can re-evaluate its guard
        condition (which requires at least one component to be loaded).

        Parameters:
            callback - A zero-argument callable, e.g.
                       lambda: self._capability_tab.on_state_changed()
        """
        self._on_components_changed = callback

    def add_component(self, comp):
        """
        Add a component dict to the list if its UUID is not already present.

        Called by CapabilityTab when loading a capability file that has bundled
        member components. Importing them here means they are immediately
        available to the Capability Editor for control inheritance re-sync,
        and also visible to the user if they switch to this tab.

        Parameters:
            comp - A component dict with at least 'uuid', 'title', 'type',
                   'description', and 'ctrl_responses' keys.

        Returns:
            True if the component was added, False if the UUID already existed.
        """
        if any(c["uuid"] == comp["uuid"] for c in self._components):
            return False
        self._components.append(comp)
        return True

    def on_catalog_or_profile_changed(self):
        """
        Called by the main app whenever the catalog or profile is loaded,
        cleared, or changed.

        Re-evaluates the guard (catalog required) and shows either the editor
        or the gate panel. Also refreshes the Section 8 control list so it
        immediately reflects any profile change (filtered vs full catalog).
        """
        if self._ready():
            # Catalog is loaded — show the editor
            self._gate_frame.pack_forget()
            self._body_pane.pack(fill="both", expand=True)
            self._update_gate_label()
            # If a component is being edited, refresh its control list
            if self._selected_index is not None:
                self._refresh_control_list()
            self._refresh_control_source_label()
        else:
            # No catalog — hide editor, show gate
            self._body_pane.pack_forget()
            self._gate_frame.pack(fill="both", expand=True)
            self._update_gate_label()

    # =========================================================================
    # GUARD CHECK
    # =========================================================================

    def _ready(self):
        """
        Return True when a catalog is loaded.

        A profile is optional — if one is loaded, Section 7 shows only the
        profile's controls; otherwise it shows the full catalog control list.
        """
        return self._get_catalog() is not None

    def _refresh_control_source_label(self):
        """
        Update the Section 9 label showing which catalog/profile filename will
        be written to control-implementations[].source when this component is
        saved. Uses the same get_source_href() logic as the actual save path,
        so the label always matches what ends up in the OSCAL output.
        """
        if not hasattr(self, "_ctrl_source_lbl"):
            return
        source_href = get_source_href(self._get_profile(), self._get_catalog())
        self._ctrl_source_lbl.config(text=f"  Source: {source_href}")

    # =========================================================================
    # BUILD — top-level layout
    # =========================================================================

    def _build(self):
        """Create the toolbar, then the gate panel, then the editing body."""
        self._build_toolbar()
        self._build_gate_panel()
        self._build_body()
        # Show whichever layer is appropriate right now
        self.on_catalog_or_profile_changed()

    def theme_refresh(self):
        """
        Rebuild this tab's widgets after the colour theme changes, without
        losing self._components or the currently selected item's in-progress
        edits.

        Unlike ssp_tab/ap_tab/ar_tab/poam_tab, this tab edits the selected
        component inline (in the right-hand detail form) rather than through
        modal dialogs, so any in-progress edit must be collected into
        self._components BEFORE the form widgets holding it are destroyed.
        The selection itself is then cleared — the freshly rebuilt detail
        form has no widgets bound to the old selection, so showing the
        placeholder is the only safe option; self._components (the data)
        is unaffected and the list repopulates from it via _refresh_list().
        """
        if self._selected_index is not None:
            self._collect_into(self._selected_index)
        self._selected_index = None
        self.configure(bg=self._colors["BG"])   # This tab's own Frame background
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()
        self._refresh_list()
        if hasattr(self, "_show_form_placeholder"):
            self._show_form_placeholder()

    # =========================================================================
    # TOOLBAR
    # =========================================================================

    def _build_toolbar(self):
        """
        Top bar with Save / Open / New buttons and the auto-filename display.

        In library_mode, this is a different, smaller set of actions (see
        class docstring) — no Open File(s)/Open Folder/Import from Library/
        Clear All, since this instance never touches anything outside the
        Library, and a "🔄 Refresh from Library"/"📥 Add File to Library"
        pair instead.
        """
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        if self._library_mode:
            self._build_library_toolbar(tb)
            self._build_library_hint()
            return

        tk.Button(
            tb, text="💾  Save Component", command=self._save_file,
            bg=C["GREEN_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=C["GREEN_BG"], activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=12, pady=8)

        # "Open File(s)" lets the user pick one or more files at once.
        # Components are APPENDED to the list, not replacing it.
        tk.Button(
            tb, text="📂  Open File(s)", command=self._open_files,
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=C["BLUE_BG"], activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=(0, 6), pady=8)

        # "Open Folder" loads every component JSON file in a chosen folder.
        # Also appends to the list.
        tk.Button(
            tb, text="📁  Open Folder", command=self._open_folder,
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=C["BLUE_BG"], activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=(0, 8), pady=8)

        # "Import from Library" copies component file(s) from the shared
        # Library folder (see settings.py) into the current system's
        # folder, then loads the copies into this list — see
        # _import_from_library().
        tk.Button(
            tb, text="📚  Import from Library", command=self._import_from_library,
            bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
            activebackground=C["TEAL_BG"], activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(
            tb, text="🗑  Clear All", command=self._new_file,
            bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(0, 12), pady=8)

        # Visual separator
        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=4, pady=6
        )

        # Auto-generated filename display (read-only, updated by _update_file_title)
        tk.Label(tb, text="File:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left", padx=(8, 4))

        self._file_title_lbl = tk.Label(
            tb, text="(load a catalog, then add a component)",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._file_title_lbl.pack(side="left", padx=(0, 8))

        self._status_lbl = tk.Label(
            tb, text="Load a catalog to begin",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=12)

        self._build_folder_hint()

    def _build_folder_hint(self):
        """
        Explanatory banner under the toolbar (non-library-mode only)
        naming where the components shown in this tab actually live on
        disk — the current system's own folder, not the shared Library.
        Nielsen #1 (visibility of status) / #2 (match the real world):
        without this, there's nothing in the tab itself indicating that
        "the list you're looking at" corresponds to a specific folder.

        The folder can change during a session (opening or saving a
        different workspace), so the label is refreshed every time
        _refresh_list() runs, not just once at construction.
        """
        C = self._colors
        hint = tk.Frame(self, bg=C["HEADER_BG"])
        hint.pack(fill="x", side="top")
        self._folder_hint_lbl = tk.Label(
            hint, text="", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"), wraplength=900, justify="left",
        )
        self._folder_hint_lbl.pack(anchor="w", padx=12, pady=4)
        self._update_folder_hint()

    def _update_folder_hint(self):
        """Refresh _build_folder_hint()'s label text — see its docstring."""
        if not hasattr(self, "_folder_hint_lbl"):
            return   # library_mode has no such label
        system_folder = self._get_system_folder()
        if system_folder:
            text = (
                "ℹ️  The components listed here are the ones currently loaded for "
                f"this system — saved to and loaded from: {Path(system_folder) / 'components'}"
            )
        else:
            text = (
                "ℹ️  The components listed here are the ones currently loaded for "
                "this system. Open or save a workspace first to fix a system folder "
                "for them — until then, they're wherever you last opened/saved each file."
            )
        self._folder_hint_lbl.config(text=text)

    def _build_library_toolbar(self, tb):
        """Toolbar contents for library_mode — see _build_toolbar()."""
        C = self._colors
        save_btn = tk.Button(
            tb, text="💾  Save to Library", command=self._save_file,
            bg=C["GREEN_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        save_btn.pack(side="left", padx=12, pady=8)
        attach_tooltip(save_btn, "Save the selected component back to the Library", C)

        refresh_btn = tk.Button(
            tb, text="🔄  Refresh from Library", command=self._load_library_folder,
            bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        refresh_btn.pack(side="left", padx=(0, 6), pady=8)
        attach_tooltip(
            refresh_btn,
            "Reload every component from disk — discards any unsaved edits in this tab",
            C,
        )

        add_file_btn = tk.Button(
            tb, text="📥  Add File to Library", command=self._add_file_to_library,
            bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=12, pady=4, cursor="hand2",
        )
        add_file_btn.pack(side="left", padx=(0, 12), pady=8)
        attach_tooltip(
            add_file_btn,
            "Copy an external component file into the Library, then load it",
            C,
        )

        self._status_lbl = tk.Label(
            tb, text="", bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._status_lbl.pack(side="right", padx=12)

    def _build_library_hint(self):
        """Explanatory banner shown under the toolbar in library_mode."""
        C = self._colors
        hint = tk.Frame(self, bg=C["TEAL_BG"])
        hint.pack(fill="x", side="top")
        tk.Label(
            hint,
            text="✏️  Library Component Editor — edits the shared master components in "
                 "your Library folder. Systems that already imported a copy will not "
                 "automatically receive changes made here.",
            bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9, "italic"),
            wraplength=900, justify="left",
        ).pack(anchor="w", padx=12, pady=4)

    # =========================================================================
    # GATE PANEL — shown when catalog or profile is not loaded
    # =========================================================================

    def _build_gate_panel(self):
        """
        Build the gate panel that blocks editing until both a catalog and
        a profile have been loaded.

        The panel shows exactly what is missing and directs the user to
        the Data Sources tab, which is now the only place to open a
        catalog or profile (see data_sources_tab.py).
        """
        C = self._colors

        # This frame fills the whole tab body when shown.
        # It is hidden (_gate_frame.pack_forget()) once both files are loaded.
        self._gate_frame = tk.Frame(self, bg=C["BG"])
        # (Will be shown/hidden by on_catalog_or_profile_changed)

        # Centre everything vertically
        inner = tk.Frame(self._gate_frame, bg=C["BG"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # Lock icon and heading
        tk.Label(
            inner, text="🔒",
            bg=C["BG"], fg=C["YELLOW"],
            font=("Helvetica", 48),
        ).pack(pady=(0, 10))

        tk.Label(
            inner, text="Catalog Required",
            bg=C["BG"], fg=C["TEXT"],
            font=("Helvetica", 16, "bold"),
        ).pack()

        tk.Label(
            inner,
            text="The Component Editor needs an OSCAL catalog to be loaded\n"
                 "before components can be created or edited.\n\n"
                 "A profile is optional — if one is loaded, the control list in\n"
                 "Section 8 will show only the controls in that profile's baseline.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 11), justify="center",
        ).pack(pady=(8, 20))

        # Dynamic status label — shows exactly what is still missing
        # Updated by _update_gate_label() whenever the catalog/profile changes
        self._gate_status_lbl = tk.Label(
            inner, text="",
            bg=C["BG"], fg=C["RED"],
            font=("Helvetica", 11, "bold"), justify="center",
        )
        self._gate_status_lbl.pack()

        tk.Label(
            inner,
            text="Load a catalog (and optionally a profile) in the\n"
                 "📚 Data Sources tab.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"), justify="center",
        ).pack(pady=(16, 0))

        # Run the label update once to set the initial text
        self._update_gate_label()

    def _update_gate_label(self):
        """
        Update the gate panel status label to show whether a catalog is loaded.
        Called whenever the catalog or profile state changes.
        """
        if not hasattr(self, "_gate_status_lbl"):
            return
        if self._get_catalog():
            msg = "✅  Catalog loaded"
        else:
            msg = "❌  No catalog loaded"
        self._gate_status_lbl.config(text=msg)

    # =========================================================================
    # BODY — split pane with component list + editing form
    # =========================================================================

    def _build_body(self):
        """
        Build the main editing area: a horizontal split pane with the
        component list on the left and the detail form on the right.

        This is hidden behind the gate panel until both files are loaded.
        """
        C = self._colors

        # Store as an instance variable so on_catalog_or_profile_changed
        # can show/hide it
        self._body_pane = tk.PanedWindow(
            self, orient="horizontal",
            bg=C["BG"], sashwidth=5, sashrelief="flat",
        )
        # Not packed yet — shown by on_catalog_or_profile_changed

        self._build_component_list(self._body_pane)
        self._build_detail_form(self._body_pane)

    # =========================================================================
    # LEFT PANE — component list
    # =========================================================================

    def _build_component_list(self, pane):
        """Build the left pane: search/filter bar, component list, Add/Delete buttons."""
        C    = self._colors
        left = tk.Frame(pane, bg=C["SIDEBAR_BG"])
        pane.add(left, minsize=240, width=300)

        # Heading
        hdr = tk.Frame(left, bg=C["HEADER_BG"])
        hdr.pack(fill="x")
        tk.Label(hdr, text="⚙  Components", bg=C["HEADER_BG"], fg=C["ACCENT"],
                 font=("Helvetica", 11, "bold"), anchor="w",
                 ).pack(side="left", padx=10, pady=8)
        # Component count label (top-right of header)
        self._comp_count_lbl = tk.Label(
            hdr, text="", bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9),
        )
        self._comp_count_lbl.pack(side="right", padx=8)

        # ── Search box ────────────────────────────────────────────────────────
        search_row = tk.Frame(left, bg=C["SIDEBAR_BG"])
        search_row.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(search_row, text="🔍", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="left")
        self._comp_search_var = tk.StringVar()
        self._comp_search_var.trace_add("write", self._on_comp_filter_changed)
        tk.Entry(
            search_row, textvariable=self._comp_search_var,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 10),
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        ).pack(side="left", fill="x", expand=True, ipady=3, padx=(4, 0))

        # ── Type filter ───────────────────────────────────────────────────────
        type_row = tk.Frame(left, bg=C["SIDEBAR_BG"])
        type_row.pack(fill="x", padx=8, pady=(2, 4))
        tk.Label(type_row, text="Type:", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9)).pack(side="left")
        self._comp_type_filter_var = tk.StringVar(value="all")
        self._comp_type_filter_var.trace_add("write", self._on_comp_filter_changed)
        self._comp_type_combo = ttk.Combobox(
            type_row, textvariable=self._comp_type_filter_var,
            values=["all"] + COMPONENT_TYPES,
            state="readonly", width=18,
        )
        self._comp_type_combo.pack(side="left", padx=(4, 0))

        # Sort toggle button — cycles between "Sort by type" and "Sort A–Z"
        self._sort_btn = tk.Button(
            type_row, text="⊞  By type",
            command=self._toggle_sort,
            bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9),
            relief="flat", padx=6, pady=1, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BUTTON_TEXT"],
        )
        self._sort_btn.pack(side="right")

        # Add / Duplicate / Delete buttons
        btn_row = tk.Frame(left, bg=C["SIDEBAR_BG"])
        btn_row.pack(fill="x", padx=8, pady=(2, 4))
        tk.Button(btn_row, text="＋  Add Component",
                  command=self._add_component,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground="#b4befe", activeforeground=C["BUTTON_TEXT"],
                  ).pack(side="left")
        tk.Button(btn_row, text="⧉  Duplicate",
                  command=self._duplicate_component,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=(4, 0))
        tk.Button(btn_row, text="✕  Delete",
                  command=self._delete_component,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="right")

        # Listbox
        list_frame = tk.Frame(left, bg=C["SIDEBAR_BG"])
        list_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._comp_listbox = tk.Listbox(
            list_frame,
            bg=C["SIDEBAR_BG"], fg=C["TEXT"],
            selectbackground=C["ACCENT"], selectforeground=C["BG"],
            font=("Helvetica", 11), relief="flat",
            activestyle="none", highlightthickness=0,
        )
        vsb = ttk.Scrollbar(list_frame, orient="vertical",
                            command=self._comp_listbox.yview)
        self._comp_listbox.configure(yscrollcommand=vsb.set)
        self._comp_listbox.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._comp_listbox.bind("<<ListboxSelect>>", self._on_list_select)

    # =========================================================================
    # RIGHT PANE — scrollable detail form
    # =========================================================================

    def _build_detail_form(self, pane):
        """
        Build the right pane: a scrollable canvas containing the component
        editing form. The form has eight sections.
        """
        C     = self._colors
        right = tk.Frame(pane, bg=C["BG"])
        pane.add(right, minsize=500)

        canvas = tk.Canvas(right, bg=C["BG"], highlightthickness=0)
        vsb    = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        self._form_frame = tk.Frame(canvas, bg=C["BG"])
        self._form_win   = canvas.create_window(
            (0, 0), window=self._form_frame, anchor="nw"
        )
        self._form_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._form_win, width=e.width)
        )
        self._detail_canvas = canvas
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self._build_form_widgets(self._form_frame)
        self._show_form_placeholder()

    def _on_mousewheel(self, event):
        """Scroll the detail canvas on mouse-wheel, only when this tab is active.

        bind_all means this fires regardless of which tab is visible, so we
        check whether THIS tab is the currently selected one before scrolling.
        is_tab_active() walks up through any nested Notebook grouping (see
        app.py's Data/System Overview/Audit tabs), not just the immediate
        parent, so this stays correct regardless of how deeply nested.
        """
        try:
            if is_tab_active(self):
                self._detail_canvas.yview_scroll(
                    int(-1 * (event.delta / 120)), "units"
                )
        except tk.TclError:
            pass   # Canvas destroyed/not ready — see SECURE_CODING.md #2

    # =========================================================================
    # FORM WIDGET CONSTRUCTION
    # =========================================================================

    def _build_form_widgets(self, parent):
        """
        Create all sections of the component editing form.
        The form is always present but hidden behind _placeholder_lbl
        until a component is selected.
        """
        C = self._colors
        P = dict(padx=20)   # Standard horizontal padding

        # ── Local helpers ─────────────────────────────────────────────────────

        def section(title):
            """Dark header bar for a section."""
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(16, 4))
            tk.Label(hdr, text=title, bg=C["HEADER_BG"], fg=C["ACCENT"],
                     font=("Helvetica", 11, "bold"), anchor="w",
                     ).pack(side="left", padx=10, pady=5)

        def field(label, var, width=50):
            """Label + Entry row linked to a StringVar."""
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=20, anchor="w",
                     ).pack(side="left")
            tk.Entry(row, textvariable=var, width=width,
                     bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                     relief="flat", font=("Helvetica", 11),
                     highlightthickness=1, highlightbackground=C["HEADER_BG"],
                     ).pack(side="left", ipady=3, fill="x", expand=True)

        def combo(label, var, values, width=30):
            """Label + read-only Combobox row linked to a StringVar."""
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=20, anchor="w",
                     ).pack(side="left")
            ttk.Combobox(row, textvariable=var, values=values,
                         state="readonly", width=width,
                         ).pack(side="left")

        def textbox(label, height=4):
            """Label + multi-line Text widget. Returns the Text widget."""
            if label:
                tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                         font=("Helvetica", 11),
                         ).pack(anchor="w", **P, pady=(6, 2))
            border = tk.Frame(parent, bg=C["HEADER_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
            border.pack(fill="x", **P, pady=2)
            t = tk.Text(border, bg=C["CARD_BG"], fg=C["TEXT"],
                        insertbackground=C["TEXT"],
                        relief="flat", font=("Helvetica", 11), height=height,
                        wrap="word", padx=8, pady=6)
            t.pack(fill="both")
            return t

        # ── Placeholder (shown when nothing is selected) ──────────────────────
        self._placeholder_lbl = tk.Label(
            parent,
            text="Add a component using '＋ Add Component',\n"
                 "or open an existing file with '📂 Open File'.",
            bg=C["BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 12, "italic"), justify="center",
        )
        self._placeholder_lbl.pack(pady=60, padx=40)

        # All real form content lives inside _form_content, which is shown
        # and hidden as a unit by _show_form_placeholder/_show_component_form.
        self._form_content = tk.Frame(parent, bg=C["BG"])
        # (Not packed yet)

        # From this point all widgets go inside _form_content, not parent
        parent = self._form_content

        # =====================================================================
        # SECTION 1 — BASIC INFORMATION
        # =====================================================================
        section("1 ·  Basic Information")

        self._v_title   = tk.StringVar()
        self._v_purpose = tk.StringVar()

        field("Component Title *", self._v_title, width=50)

        self._v_type = tk.StringVar(value=COMPONENT_TYPES[0])
        combo("Component Type *", self._v_type, COMPONENT_TYPES, width=28)

        field("Purpose", self._v_purpose, width=50)

        # trace_add("write", fn) calls fn every time the StringVar's value
        # changes — this makes the toolbar filename label and the component
        # list entry update live as the user types, without needing a button.
        self._v_title.trace_add("write", self._update_file_title)
        self._v_type.trace_add("write",  self._update_file_title)

        tk.Label(parent, text="  * Required fields",
                 bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        # ── Metadata: Document Metadata (§10.21, extended) ──────────────────
        # Kept inside Section 1 rather than its own numbered section, to
        # avoid renumbering every section below it. Each component carries
        # its own document uuid/version/revisions/creator/links — never
        # shared tab-level state — so this stays correct even when many
        # components share one tab instance (library_mode). Collapsible
        # (make_collapsible(), tab_utils.py) since it's consulted far less
        # often than the fields below it, especially in library_mode where
        # dozens of these cards would otherwise all sit expanded at once —
        # see usability_review.md #2/#8.
        ver_card = make_collapsible(parent, "🗂  Document Metadata", C, start_expanded=True)

        tk.Label(
            ver_card,
            text="  Editing the Version field and clicking Apply/Save just relabels "
                 "the current version in place. To keep a record of what changed, use "
                 "'Save New Version' instead — it archives the current version and your "
                 "remarks into the history below (dated automatically) before moving to "
                 "the new version number.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
            wraplength=760, justify="left",
        ).pack(anchor="w", padx=10, pady=(6, 4))

        ver_row = tk.Frame(ver_card, bg=C["CARD_BG"])
        ver_row.pack(fill="x", padx=10, pady=(0, 2))
        tk.Label(ver_row, text="Version:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left")
        self._v_version = tk.StringVar(value="1.0")
        tk.Entry(ver_row, textvariable=self._v_version, width=10,
                 bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10),
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", padx=(6, 16), ipady=2)
        save_version_btn = tk.Button(ver_row, text="📌  Save New Version",
                  command=self._save_new_version,
                  bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  )
        save_version_btn.pack(side="left")
        attach_tooltip(
            save_version_btn,
            "Archive the current version into history, then set a new version number",
            C,
        )

        id_row = tk.Frame(ver_card, bg=C["CARD_BG"])
        id_row.pack(fill="x", padx=10, pady=(6, 2))
        self._v_component_uuid_lbl = tk.Label(
            id_row, text="Component UUID: —", bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 8),
        )
        self._v_component_uuid_lbl.pack(anchor="w")
        self._v_file_uuid_lbl = tk.Label(
            id_row, text="Document UUID: —", bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 8),
        )
        self._v_file_uuid_lbl.pack(anchor="w")
        # Which OSCAL version this component's file actually declares —
        # read back on load (see _parse_single_component()), not always
        # the app's currently-selected version. Surfaces mismatches like
        # the Library's CivicActions examples, which declare "1.0.0"
        # while everything else in the Library declares 1.1.2/1.2.2.
        oscal_ver_row = tk.Frame(ver_card, bg=C["CARD_BG"])
        oscal_ver_row.pack(fill="x", padx=10, pady=(0, 2))
        self._v_oscal_version_lbl = tk.Label(
            oscal_ver_row, text="OSCAL Version: —", bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 8),
        )
        self._v_oscal_version_lbl.pack(side="left")
        upgrade_btn = tk.Button(
            oscal_ver_row, text="🔼  Upgrade OSCAL Version",
            command=self._upgrade_oscal_version,
            bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 8),
            relief="flat", padx=6, pady=0, cursor="hand2",
        )
        upgrade_btn.pack(side="left", padx=(10, 0))
        attach_tooltip(
            upgrade_btn,
            "Re-validate this component against a different OSCAL schema "
            "version and, if you confirm, re-stamp it to that version",
            C,
        )

        tk.Label(ver_card, text="Revision History:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic")).pack(anchor="w", padx=10, pady=(4, 0))
        hist_cols = ("version", "date", "remarks")
        self._revision_tree = ttk.Treeview(
            ver_card, columns=hist_cols, show="headings", height=3,
        )
        for col, label, width in [
            ("version", "Version", 70), ("date", "Date", 150), ("remarks", "Remarks", 300),
        ]:
            self._revision_tree.heading(col, text=label)
            self._revision_tree.column(col, width=width, anchor="w")
        self._revision_tree.pack(fill="x", padx=10, pady=(2, 8))

        # ── Creator / Organisation (metadata.parties, role=creator) ────────
        # e.g. the CivicActions attribution seen on the aws.json/django.json/
        # etc. Library examples: metadata.parties + responsible-parties +
        # a role, all standard OSCAL — see this feature's design discussion.
        tk.Label(ver_card, text="Creator / Organisation:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic")).pack(anchor="w", padx=10, pady=(6, 0))
        creator_row = tk.Frame(ver_card, bg=C["CARD_BG"])
        creator_row.pack(fill="x", padx=10, pady=(2, 6))
        self._v_creator = tk.StringVar()
        tk.Entry(creator_row, textvariable=self._v_creator, width=40,
                 bg=C["SIDEBAR_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10),
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", ipady=3)

        # ── Document Links (metadata.links) ─────────────────────────────────
        # Distinct from Section 7's per-component links below (vendor docs,
        # CVE advisories about the *component*) — these describe the *file*
        # itself, e.g. a "latest-version" link back to where it's published.
        # Reuses the same _link_dialog()/_LINK_REL_VALUES as Section 7.
        tk.Label(ver_card, text="Document Links:", bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic")).pack(anchor="w", padx=10, pady=(0, 0))
        doc_link_btn_row = tk.Frame(ver_card, bg=C["CARD_BG"])
        doc_link_btn_row.pack(fill="x", padx=10, pady=(2, 2))
        tk.Button(doc_link_btn_row, text="＋  Add Link", command=self._add_doc_link,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left")
        tk.Button(doc_link_btn_row, text="✕  Remove Selected", command=self._remove_doc_link,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, pady=2, cursor="hand2",
                  ).pack(side="left", padx=6)
        self._doc_link_tree = ttk.Treeview(
            ver_card, columns=("rel", "href", "text"), show="headings", height=2,
        )
        for col, heading, w, stretch in [
            ("rel",  "Relationship", 140, False),
            ("href", "URL / Reference", 260, False),
            ("text", "Label",         160, True),
        ]:
            self._doc_link_tree.heading(col, text=heading, anchor="w")
            self._doc_link_tree.column(col, width=w, anchor="w", stretch=stretch)
        self._doc_link_tree.pack(fill="x", padx=10, pady=(0, 8))

        # =====================================================================
        # SECTION 2 — DESCRIPTION
        # =====================================================================
        section("2 ·  Description")
        tk.Label(parent,
                 text="  A description of the component and its function.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)
        self._v_description = textbox("Component Description *", height=4)

        # =====================================================================
        # SECTION 3 — OPERATIONAL STATUS
        # =====================================================================
        section("3 ·  Operational Status")
        tk.Label(parent, text="  The lifecycle state of this component.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)
        self._v_status  = tk.StringVar(value=COMPONENT_STATUS[0])
        self._v_remarks = tk.StringVar()
        combo("Status *", self._v_status, COMPONENT_STATUS, width=28)
        field("Status Remarks", self._v_remarks, width=50)

        # =====================================================================
        # SECTION 4 — PROPERTIES
        # =====================================================================
        section("4 ·  Properties")
        tk.Label(parent,
                 text="  Structured metadata (name/value pairs) about the component.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        prop_frame = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        prop_frame.pack(fill="x", padx=20, pady=6)
        prop_btn = tk.Frame(prop_frame, bg=C["CARD_BG"])
        prop_btn.pack(fill="x", padx=8, pady=6)
        tk.Button(prop_btn, text="＋  Add Property",
                  command=self._add_property,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(prop_btn, text="✕  Remove Selected",
                  command=self._remove_property,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        self._prop_tree = ttk.Treeview(
            prop_frame, columns=("name", "value", "remarks"),
            show="headings", height=4, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("name",    "Property Name", 200, False),
            ("value",   "Value",         180, False),
            ("remarks", "Remarks",       200, True),
        ]:
            self._prop_tree.heading(col, text=heading, anchor="w")
            self._prop_tree.column(col, width=w, anchor="w", stretch=stretch)
        self._prop_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =====================================================================
        # SECTION 5 — RESPONSIBLE ROLES
        # =====================================================================
        section("5 ·  Responsible Roles")
        tk.Label(parent, text="  Who is accountable for this component.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)

        role_frame = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        role_frame.pack(fill="x", padx=20, pady=6)
        role_btn = tk.Frame(role_frame, bg=C["CARD_BG"])
        role_btn.pack(fill="x", padx=8, pady=6)
        tk.Button(role_btn, text="＋  Add Role", command=self._add_role,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(role_btn, text="✕  Remove Selected",
                  command=self._remove_role,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        self._role_tree = ttk.Treeview(
            role_frame, columns=("role_id", "remarks"),
            show="headings", height=4, selectmode="browse",
        )
        self._role_tree.heading("role_id",  text="Role ID",  anchor="w")
        self._role_tree.heading("remarks",  text="Remarks",  anchor="w")
        self._role_tree.column("role_id",  width=240, anchor="w")
        self._role_tree.column("remarks",  width=340, anchor="w", stretch=True)
        self._role_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =====================================================================
        # SECTION 6 — PROTOCOLS
        # =====================================================================
        section("6 ·  Protocols  (optional)")
        proto_hint_row = tk.Frame(parent, bg=C["BG"])
        proto_hint_row.pack(fill="x", padx=20)
        tk.Label(proto_hint_row,
                 text="  Network protocols and port ranges this component exposes or uses.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(side="left", anchor="w")
        self._proto_count_lbl = tk.Label(
            proto_hint_row, text="0 protocols",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        )
        self._proto_count_lbl.pack(side="right", anchor="n", padx=(8, 0))

        proto_frame = tk.Frame(parent, bg=C["CARD_BG"],
                               highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        proto_frame.pack(fill="x", padx=20, pady=6)
        proto_btn = tk.Frame(proto_frame, bg=C["CARD_BG"])
        proto_btn.pack(fill="x", padx=8, pady=6)
        tk.Button(proto_btn, text="＋  Add Protocol",
                  command=self._add_protocol,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(proto_btn, text="✕  Remove Selected",
                  command=self._remove_protocol,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        proto_tree_frame = tk.Frame(proto_frame, bg=C["CARD_BG"])
        proto_tree_frame.pack(fill="x", padx=8, pady=(0, 8))

        self._proto_tree = ttk.Treeview(
            proto_tree_frame, columns=("name", "title", "ports"),
            show="headings", height=4, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("name",  "Protocol",    160, False),
            ("title", "Title",       220, False),
            ("ports", "Port Ranges", 300, True),
        ]:
            self._proto_tree.heading(col, text=heading, anchor="w")
            self._proto_tree.column(col, width=w, anchor="w", stretch=stretch)

        proto_scroll = ttk.Scrollbar(
            proto_tree_frame, orient="vertical", command=self._proto_tree.yview,
        )
        self._proto_tree.configure(yscrollcommand=proto_scroll.set)
        proto_scroll.pack(side="right", fill="y")
        self._proto_tree.pack(side="left", fill="both", expand=True)

        # =====================================================================
        # SECTION 7 — LINKS
        # =====================================================================
        section("7 ·  Links  (optional)")
        tk.Label(
            parent,
            text="  External references: vendor documentation, CVE advisories,\n"
                 "  configuration baselines, policy documents, and related resources.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)

        link_frame = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        link_frame.pack(fill="x", padx=20, pady=6)
        link_btn = tk.Frame(link_frame, bg=C["CARD_BG"])
        link_btn.pack(fill="x", padx=8, pady=6)
        tk.Button(link_btn, text="＋  Add Link",
                  command=self._add_link,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left")
        tk.Button(link_btn, text="✕  Remove Selected",
                  command=self._remove_link,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(side="left", padx=8)

        self._link_tree = ttk.Treeview(
            link_frame, columns=("rel", "href", "text"),
            show="headings", height=4, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("rel",  "Relationship", 160, False),
            ("href", "URL / Reference", 260, False),
            ("text", "Label",         180, True),
        ]:
            self._link_tree.heading(col, text=heading, anchor="w")
            self._link_tree.column(col, width=w, anchor="w", stretch=stretch)
        self._link_tree.pack(fill="x", padx=8, pady=(0, 8))

        # =====================================================================
        # SECTION 8 — REMARKS
        # =====================================================================
        section("8 ·  Remarks  (optional)")
        tk.Label(parent, text="  Additional notes about this component.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20)
        self._v_remarks_text = textbox("", height=3)

        # =====================================================================
        # SECTION 9 — CONTROL IMPLEMENTATIONS
        # =====================================================================
        section("9 ·  Control Implementations")
        tk.Label(
            parent,
            text="  Select a control from the list and describe how this component\n"
                 "  implements it. Controls are drawn from the loaded profile.\n"
                 "  Dot legend:  ● = response written   ○ = no response yet",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(anchor="w", padx=20)
        # Shows the filename that will be written to control-implementations[].source
        # when this component is saved — i.e. the catalog or profile these controls
        # are drawn from. Kept in sync via _refresh_control_source_label().
        self._ctrl_source_lbl = tk.Label(
            parent, text="", bg=C["BG"], fg=C["ACCENT"], font=("Helvetica", 9, "bold"),
        )
        self._ctrl_source_lbl.pack(anchor="w", padx=20, pady=(2, 0))

        # This section uses an inner horizontal split:
        #   LEFT  — scrollable list of controls from the profile
        #   RIGHT — text editor for the implementation description

        ctrl_outer = tk.Frame(parent, bg=C["CARD_BG"],
                              highlightthickness=1,
                              highlightbackground=C["HEADER_BG"])
        ctrl_outer.pack(fill="both", expand=True, padx=20, pady=6)

        ctrl_pane = tk.PanedWindow(ctrl_outer, orient="horizontal",
                                   bg=C["CARD_BG"], sashwidth=4,
                                   sashrelief="flat")
        ctrl_pane.pack(fill="both", expand=True)

        # ── Left sub-pane: tabbed control lists ───────────────────────────────
        # We use a small inner Notebook to provide two tabs:
        #   Tab 1 — "All Controls":     every control from the profile
        #   Tab 2 — "Applied Controls": only controls that have a response
        #
        # This solves the problem of very long lists — the user can switch
        # to "Applied Controls" to quickly find and edit existing responses
        # without scrolling through hundreds of unrelated controls.
        ctrl_left = tk.Frame(ctrl_pane, bg=C["SIDEBAR_BG"])
        ctrl_pane.add(ctrl_left, minsize=220, width=300)

        # ── Search box (shared across both tabs) ──────────────────────────────
        # The search filters whichever tab is currently active.
        search_row = tk.Frame(ctrl_left, bg=C["SIDEBAR_BG"])
        search_row.pack(fill="x", padx=6, pady=6)
        tk.Label(search_row, text="🔍", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11)).pack(side="left")
        self._ctrl_search_var = tk.StringVar()
        self._ctrl_search_var.trace_add("write", self._on_ctrl_search)
        tk.Entry(search_row, textvariable=self._ctrl_search_var,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10),
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", fill="x", expand=True, ipady=3, padx=(4, 0))

        # ── Inner notebook for the two list tabs ──────────────────────────────
        ctrl_nb = ttk.Notebook(ctrl_left)
        ctrl_nb.pack(fill="both", expand=True, padx=4, pady=(0, 2))
        # Store the notebook so _on_ctrl_search knows which tab is active
        self._ctrl_notebook = ctrl_nb

        # Helper: build a Treeview with dot/label/title columns inside a tab frame
        def make_ctrl_treeview(tab_parent):
            """
            Create a Treeview with scrollbar for displaying controls.
            Returns the Treeview widget.

            Each row shows:
              col 1 (dot)   — ● green if response written, ○ grey if not
              col 2 (label) — the control label (e.g. "ism-1130" or "GOV-01")
              col 3 (title) — the control statement text
            """
            frame = tk.Frame(tab_parent, bg=C["SIDEBAR_BG"])
            frame.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                frame,
                columns=("dot", "label", "title"),
                show="headings",
                selectmode="browse",
            )
            tree.heading("dot",   text="",           anchor="center")
            tree.heading("label", text="ID / Label", anchor="w")
            tree.heading("title", text="Statement",  anchor="w")
            tree.column("dot",   width=24,  minwidth=24,  anchor="center", stretch=False)
            tree.column("label", width=100, minwidth=80,  anchor="w",      stretch=False)
            tree.column("title", width=180, minwidth=100, anchor="w",      stretch=True)

            # Tags control the colour of the dot indicator column
            tree.tag_configure("done",  foreground=C["GREEN"])
            tree.tag_configure("empty", foreground=C["SUBTEXT"])

            vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=vsb.set)
            tree.pack(side="left", fill="both", expand=True)
            vsb.pack(side="right", fill="y")

            # When the user clicks a row, call our selection handler
            tree.bind("<<TreeviewSelect>>", self._on_ctrl_select)
            return tree

        # ── Tab 1: All Controls ───────────────────────────────────────────────
        # Shows every control in the loaded profile, with dot indicators.
        # This is the full list — useful when adding new responses.
        all_tab = tk.Frame(ctrl_nb, bg=C["SIDEBAR_BG"])
        ctrl_nb.add(all_tab, text="All Controls")
        self._ctrl_tree = make_ctrl_treeview(all_tab)

        # ── Tab 2: Applied Controls ───────────────────────────────────────────
        # Shows ONLY controls that already have a response written for this
        # component. This makes it fast to find and edit existing responses
        # without scrolling through the full list.
        applied_tab = tk.Frame(ctrl_nb, bg=C["SIDEBAR_BG"])
        ctrl_nb.add(applied_tab, text="Applied Controls")
        self._applied_ctrl_tree = make_ctrl_treeview(applied_tab)

        # When the user switches tabs, refresh whichever list is now visible
        ctrl_nb.bind("<<NotebookTabChanged>>", self._on_ctrl_tab_changed)

        # ── Progress counter below the notebook ───────────────────────────────
        # Shows e.g. "42 of 1024 controls have responses"
        self._ctrl_progress_lbl = tk.Label(
            ctrl_left, text="",
            bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9),
        )
        self._ctrl_progress_lbl.pack(pady=(2, 6))

        # ── Right sub-pane: implementation response editor ────────────────────
        ctrl_right = tk.Frame(ctrl_pane, bg=C["BG"])
        ctrl_pane.add(ctrl_right, minsize=300)

        # Header showing the selected control's statement (read-only reference)
        self._ctrl_stmt_lbl = tk.Label(
            ctrl_right,
            text="Select a control from the list to write an implementation response.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
            wraplength=380, justify="left", anchor="nw",
        )
        self._ctrl_stmt_lbl.pack(fill="x", padx=8, pady=(8, 4))

        # Separator
        tk.Frame(ctrl_right, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=8, pady=4
        )

        # Implementation status dropdown (OSCAL implementation-status field)
        status_row = tk.Frame(ctrl_right, bg=C["BG"])
        status_row.pack(fill="x", padx=8, pady=(4, 2))
        tk.Label(
            status_row,
            text="Implementation Status:",
            bg=C["BG"], fg=C["TEXT"],
            font=("Helvetica", 10, "bold"),
        ).pack(side="left")
        self._ctrl_impl_status_var = tk.StringVar(value="implemented")
        status_menu = ttk.Combobox(
            status_row,
            textvariable=self._ctrl_impl_status_var,
            values=self._IMPL_STATUS_VALUES,
            state="readonly", width=20,
            font=("Helvetica", 11),
        )
        status_menu.pack(side="left", padx=(8, 0))

        # Label for the response text area
        tk.Label(
            ctrl_right,
            text="How does this component implement this control?",
            bg=C["BG"], fg=C["ACCENT"],
            font=("Helvetica", 10, "bold"),
        ).pack(anchor="w", padx=8, pady=(4, 2))

        # Multi-line text area for writing the implementation response
        resp_border = tk.Frame(ctrl_right, bg=C["HEADER_BG"],
                               highlightthickness=1,
                               highlightbackground=C["HEADER_BG"])
        resp_border.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self._ctrl_response_text = tk.Text(
            resp_border,
            bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
            relief="flat", font=("Helvetica", 11),
            wrap="word", padx=8, pady=6,
        )
        self._ctrl_response_text.pack(fill="both", expand=True)

        # ── Apply + bottom padding ────────────────────────────────────────────
        apply_row = tk.Frame(parent, bg=C["BG"])
        apply_row.pack(fill="x", padx=20, pady=(16, 8))
        tk.Button(
            apply_row,
            text="✔  Apply Component Changes",
            command=self._apply_component,
            bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
            relief="flat", padx=14, pady=6, cursor="hand2",
            activebackground="#b4befe", activeforeground=C["BUTTON_TEXT"],
        ).pack(side="left")
        tk.Label(
            apply_row,
            text="  Saves all fields including the current control response — "
                 "use '💾 Save Component' to write to disk",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=8)

        tk.Frame(parent, bg=C["BG"], height=30).pack()

    # =========================================================================
    # SHOW / HIDE PLACEHOLDER vs FORM
    # =========================================================================

    def _show_form_placeholder(self):
        """Hide the form and show the 'add a component' placeholder."""
        self._form_content.pack_forget()
        self._placeholder_lbl.pack(pady=60, padx=40)

    def _show_component_form(self):
        """Hide the placeholder and show the editing form."""
        self._placeholder_lbl.pack_forget()
        self._form_content.pack(fill="both", expand=True)

    # =========================================================================
    # AUTO FILENAME + LIST RENAME
    # =========================================================================

    def _update_file_title(self, *_args):
        """
        Called automatically by StringVar traces whenever the Component Title
        or Component Type fields change.

        Does two things:
          1. Updates the toolbar filename display label (not built in
             library_mode — see _build_library_toolbar())
          2. Renames the currently selected entry in the left component list
        """
        comp_type  = self._v_type.get().strip()  if hasattr(self, "_v_type")  else ""
        comp_title = self._v_title.get().strip() if hasattr(self, "_v_title") else ""
        has_title_lbl = hasattr(self, "_file_title_lbl")

        if comp_type and comp_title:
            auto_title    = f"{comp_type} - {comp_title}"
            safe_title    = safe_filename_component(comp_title)
            auto_filename = f"{comp_type}_{safe_title}.json"
            if has_title_lbl:
                self._file_title_lbl.config(
                    text=f"{auto_title}  →  {auto_filename}",
                    fg=self._colors["TEXT"], font=("Helvetica", 10),
                )
            self._file_title.set(auto_title)
        elif comp_type or comp_title:
            if has_title_lbl:
                self._file_title_lbl.config(
                    text="(enter both type and title to generate filename)",
                    fg=self._colors["SUBTEXT"], font=("Helvetica", 10, "italic"),
                )
            self._file_title.set(comp_type or comp_title)
        else:
            if has_title_lbl:
                self._file_title_lbl.config(
                    text="(enter component type and title below)",
                    fg=self._colors["SUBTEXT"], font=("Helvetica", 10, "italic"),
                )
            self._file_title.set("")

        # ── Update the matching Listbox entry in real time ────────────────────
        if self._selected_index is not None and self._selected_index in self._filtered_indices:
            title   = comp_title or "(untitled)"
            display = f"{title}  [{comp_type}]" if comp_type else title
            list_pos = self._filtered_indices.index(self._selected_index)
            self._comp_listbox.delete(list_pos)
            self._comp_listbox.insert(list_pos, display)
            self._comp_listbox.selection_set(list_pos)
            self._comp_listbox.see(list_pos)

    # =========================================================================
    # COMPONENT LIST MANAGEMENT
    # =========================================================================

    # ── Filter helpers ────────────────────────────────────────────────────────

    def _on_comp_filter_changed(self, *_args):
        """
        Callback wired to both the search Entry and the type Combobox via
        StringVar.trace_add("write", ...).

        Debounced: waits 250 ms after the last keystroke before rebuilding
        the list so rapid typing doesn't trigger a full rebuild on every key.
        """
        if hasattr(self, "_search_after_id") and self._search_after_id:
            try:
                self.after_cancel(self._search_after_id)
            except tk.TclError:
                pass   # Timer id already invalid/fired — see SECURE_CODING.md #2
        self._search_after_id = self.after(250, self._refresh_list)

    def _toggle_sort(self):
        """Switch between grouping by type-then-title and sorting purely A-Z."""
        if self._sort_mode == "type":
            self._sort_mode = "alpha"
            self._sort_btn.config(text="🔤  A–Z")
        else:
            self._sort_mode = "type"
            self._sort_btn.config(text="⊞  By type")
        self._refresh_list()

    def _build_filtered_indices(self):
        """
        Return a list of indices into self._components that pass the current
        search text and type-filter.

        WHY RETURN INDICES INSTEAD OF COMPONENTS?
        ------------------------------------------
        The Listbox widget shows items at sequential positions 0, 1, 2, ... but
        those positions have nothing to do with where the matching component
        actually sits in self._components.

        For example, if self._components has 10 items and the search matches
        only items at positions 2, 5, and 8, the Listbox will show three rows
        at positions 0, 1, 2.  _filtered_indices = [2, 5, 8] records that
        mapping so that when the user clicks Listbox row 1 (the second visible
        row), we can look up _filtered_indices[1] = 5 and find the real
        component without a linear search.

        When no filter is active, _filtered_indices is simply [0, 1, 2, ...],
        so the mapping is trivially correct.

        SEARCH LOGIC
        ------------
        Both filters are ANDed together: a component must pass the type check
        AND contain the search term somewhere in its title, type, or description.
        Matching is case-insensitive (everything is lowercased before comparing).
        """
        search = self._comp_search_var.get().lower().strip() if hasattr(self, "_comp_search_var") else ""
        type_f = self._comp_type_filter_var.get() if hasattr(self, "_comp_type_filter_var") else "all"

        result = []
        for i, comp in enumerate(self._components):
            # Type filter — skip if the dropdown is not "all" and the type doesn't match
            if type_f and type_f != "all" and comp.get("type", "") != type_f:
                continue
            # Text search: check if the search term appears anywhere in the
            # combined title + type + description string
            if search:
                haystack = " ".join([
                    comp.get("title", ""),
                    comp.get("type", ""),
                    comp.get("description", ""),
                ]).lower()
                if search not in haystack:
                    continue
            result.append(i)

        # Sort the matching indices according to the current sort mode.
        # Both modes sort by title within a group; "type" adds type as the
        # primary key so components are grouped by their type first.
        if self._sort_mode == "type":
            result.sort(key=lambda i: (
                self._components[i].get("type", "").lower(),
                self._components[i].get("title", "").lower(),
            ))
        else:
            result.sort(key=lambda i: self._components[i].get("title", "").lower())

        return result

    def _refresh_list(self):
        """
        Rebuild the Listbox from self._components, applying the current filter.

        This method is the single point responsible for keeping the Listbox and
        _filtered_indices in sync. Any time self._components changes (add,
        delete, open, clear) or the filter changes, call this method and it
        will bring the Listbox up to date.

        It also preserves the current selection: if the previously selected
        component is still visible after filtering, it stays highlighted and
        scrolled into view.
        """
        self._filtered_indices = self._build_filtered_indices()

        self._comp_listbox.delete(0, "end")
        for idx in self._filtered_indices:
            comp    = self._components[idx]
            title   = comp.get("title", "").strip() or "(untitled)"
            c_type  = comp.get("type", "")
            display = f"{title}  [{c_type}]" if c_type else title
            self._comp_listbox.insert("end", display)

        # Update the count label
        total    = len(self._components)
        showing  = len(self._filtered_indices)
        if hasattr(self, "_comp_count_lbl"):
            if showing == total:
                self._comp_count_lbl.config(text=f"{total}")
            else:
                self._comp_count_lbl.config(text=f"{showing} / {total}")

        # Re-select the currently selected component if it is still visible
        if self._selected_index is not None and self._selected_index in self._filtered_indices:
            pos = self._filtered_indices.index(self._selected_index)
            self._comp_listbox.selection_set(pos)
            self._comp_listbox.see(pos)

        self._update_folder_hint()

    def _on_list_select(self, _event=None):
        """
        Called when the user clicks a component in the left list.

        The two-step translate-then-load pattern here is important:
          1. Save the CURRENT component's form data into self._components
             before changing the selection, so no edits are silently lost.
          2. Translate the Listbox position to a self._components index via
             _filtered_indices (see _build_filtered_indices for why this is
             needed), then load that component into the form widgets.
        """
        sel = self._comp_listbox.curselection()
        if not sel:
            return
        # curselection() returns a tuple of selected Listbox row positions.
        # We use selectmode="browse" so there is always at most one item.
        list_pos  = int(sel[0])
        if list_pos >= len(self._filtered_indices):
            return
        new_index = self._filtered_indices[list_pos]

        # Save any pending changes from the previously selected component
        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        self._selected_index = new_index
        self._populate_from(new_index)
        self._show_component_form()

    def _add_component(self):
        """Create a new blank component, add it to the list, and select it."""
        new_comp = {
            "uuid":            new_uuid(),
            "title":           "",
            "type":            COMPONENT_TYPES[0],
            "description":     "",
            "purpose":         "",
            "status":          COMPONENT_STATUS[0],
            "status_remarks":  "",
            "remarks":         "",
            "props":           [],
            "roles":           [],
            "protocols":       [],
            "links":           [],
            "ctrl_responses":   {},  # {control_id: description_string}
            "ctrl_impl_status": {},  # {control_id: implementation-status string}
            # Per-component document identity/version — see §10.21.
            "file_uuid":  new_uuid(),
            "version":    "1.0",
            "revisions":  [],  # [{version, date, remarks}], latest-first
            # Document-level metadata.parties/links — e.g. the CivicActions
            # attribution on the Library's aws.json/django.json/etc.
            "doc_creator": "",
            "doc_links":   [],  # [{rel, href, text}]
            "doc_oscal_version": "",  # set on first save/load — see below
        }
        self._components.append(new_comp)
        self._dirty = True

        # Clear filters so the new component is immediately visible
        if hasattr(self, "_comp_search_var"):
            self._comp_search_var.set("")
        if hasattr(self, "_comp_type_filter_var"):
            self._comp_type_filter_var.set("all")

        self._refresh_list()

        new_index = len(self._components) - 1
        self._comp_listbox.selection_clear(0, "end")
        # new_index is last in _filtered_indices when no filter is active
        list_pos = self._filtered_indices.index(new_index) if new_index in self._filtered_indices else 0
        self._comp_listbox.selection_set(list_pos)
        self._comp_listbox.see(list_pos)

        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        self._selected_index = new_index
        self._populate_from(new_index)
        self._show_component_form()
        self._status_lbl.config(
            text="New component added", fg=self._colors["ACCENT"]
        )
        # Notify the Capability Editor so it can re-evaluate its guard condition
        # (it requires at least one component to be loaded before editing)
        self._on_components_changed()

    def _delete_component(self):
        """Delete the currently selected component after confirmation."""
        if self._selected_index is None:
            messagebox.showinfo("No selection", "Please select a component to delete.")
            return
        title = self._components[self._selected_index].get("title", "(untitled)")
        if not messagebox.askyesno(
            "Delete component?",
            f"Delete '{title}'? This cannot be undone."
        ):
            return
        self._components.pop(self._selected_index)
        self._selected_index = None
        self._ctrl_responses  = {}
        self._dirty = True
        self._refresh_list()
        self._show_form_placeholder()
        self._status_lbl.config(
            text="Component deleted", fg=self._colors["SUBTEXT"]
        )
        # Component count changed — let the Capability Editor re-check its guard
        self._on_components_changed()

    def _duplicate_component(self):
        """Deep-copy the selected component, assign a new UUID and suffix the title."""
        if self._selected_index is None:
            messagebox.showinfo("No selection", "Please select a component to duplicate.")
            return
        # Capture any unsaved form edits first
        self._collect_into(self._selected_index)
        import copy
        clone = copy.deepcopy(self._components[self._selected_index])
        clone["uuid"]  = new_uuid()
        clone["title"] = clone.get("title", "") + " (copy)"
        self._components.append(clone)
        self._dirty = True
        # Clear filters so the clone is visible
        if hasattr(self, "_comp_search_var"):
            self._comp_search_var.set("")
        if hasattr(self, "_comp_type_filter_var"):
            self._comp_type_filter_var.set("all")
        self._refresh_list()
        new_index = len(self._components) - 1
        self._comp_listbox.selection_clear(0, "end")
        list_pos = self._filtered_indices.index(new_index) if new_index in self._filtered_indices else 0
        self._comp_listbox.selection_set(list_pos)
        self._comp_listbox.see(list_pos)
        self._selected_index = new_index
        self._populate_from(new_index)
        self._show_component_form()
        self._status_lbl.config(
            text=f"Duplicated '{clone['title']}'  (not yet saved to disk)",
            fg=self._colors["YELLOW"],
        )
        self._on_components_changed()

    # =========================================================================
    # FORM POPULATION AND DATA COLLECTION
    # =========================================================================

    def _populate_from(self, index):
        """
        Load self._components[index] into all form widgets.

        This is the "dict → form" direction of the roundtrip.
        The opposite direction is _collect_into(), which reads the widgets
        back into the dict.

        Each section of the form is populated in order.  Note that for
        tk.Text widgets we use widget.delete("1.0", "end") before inserting
        because Text widgets do not have a StringVar — their content must be
        managed with explicit delete/insert calls. The "1.0" notation means
        "line 1, character 0" (tkinter text indices are 1-based for lines).
        """
        comp = self._components[index]

        # ── Simple fields ─────────────────────────────────────────────────────
        self._v_title.set(comp.get("title", ""))
        self._v_type.set(comp.get("type", COMPONENT_TYPES[0]))
        self._v_purpose.set(comp.get("purpose", ""))
        self._v_status.set(comp.get("status", COMPONENT_STATUS[0]))
        self._v_remarks.set(comp.get("status_remarks", ""))

        # ── Version & Revision History (§10.21) ─────────────────────────────
        self._v_version.set(comp.get("version", "1.0"))
        self._v_component_uuid_lbl.config(text=f"Component UUID: {comp.get('uuid', '—')}")
        self._v_file_uuid_lbl.config(text=f"Document UUID: {comp.get('file_uuid', '—')}")
        self._v_oscal_version_lbl.config(
            text=f"OSCAL Version: {comp.get('doc_oscal_version') or '—'}"
        )
        self._revision_tree.delete(*self._revision_tree.get_children())
        for rev in comp.get("revisions", []):
            self._revision_tree.insert("", "end", values=(
                rev.get("version", ""), rev.get("date", ""), rev.get("remarks", "")
            ))
        self._v_creator.set(comp.get("doc_creator", ""))
        self._doc_link_tree.delete(*self._doc_link_tree.get_children())
        for link in comp.get("doc_links", []):
            self._doc_link_tree.insert("", "end", values=(
                link.get("rel", ""), link.get("href", ""), link.get("text", "")
            ))

        # ── Text areas ────────────────────────────────────────────────────────
        for widget, key in [
            (self._v_description,  "description"),
            (self._v_remarks_text, "remarks"),
        ]:
            widget.delete("1.0", "end")
            val = comp.get(key, "")
            if val:
                widget.insert("1.0", val)

        # ── Properties table ──────────────────────────────────────────────────
        self._prop_tree.delete(*self._prop_tree.get_children())
        for prop in comp.get("props", []):
            self._prop_tree.insert("", "end", values=(
                prop.get("name", ""), prop.get("value", ""), prop.get("remarks", "")
            ))

        # ── Roles table ───────────────────────────────────────────────────────
        self._role_tree.delete(*self._role_tree.get_children())
        for role in comp.get("roles", []):
            self._role_tree.insert("", "end", values=(
                role.get("role_id", ""), role.get("remarks", "")
            ))

        # ── Protocols table ───────────────────────────────────────────────
        self._proto_tree.delete(*self._proto_tree.get_children())
        for proto in comp.get("protocols", []):
            self._proto_tree.insert("", "end", values=(
                proto.get("name", ""),
                proto.get("title", ""),
                self._format_port_ranges(proto.get("port_ranges", [])),
            ))
        self._update_proto_count()

        # ── Links table ───────────────────────────────────────────────────────
        self._link_tree.delete(*self._link_tree.get_children())
        for link in comp.get("links", []):
            self._link_tree.insert("", "end", values=(
                link.get("rel", ""),
                link.get("href", ""),
                link.get("text", ""),
            ))

        # ── Control responses ─────────────────────────────────────────────────
        # Load the saved responses and implementation statuses for this component.
        self._ctrl_responses   = dict(comp.get("ctrl_responses", {}))
        self._ctrl_impl_status = dict(comp.get("ctrl_impl_status", {}))
        self._selected_ctrl_id = None

        # Clear the response editor and reset status to default
        self._ctrl_response_text.delete("1.0", "end")
        self._ctrl_impl_status_var.set("implemented")
        self._ctrl_stmt_lbl.config(
            text="Select a control from the list to write an implementation response.",
            fg=self._colors["SUBTEXT"],
        )
        # Clear the search box when switching components
        self._ctrl_search_var.set("")
        self._refresh_control_list()

    def _collect_into(self, index):
        """
        Read all form widget values and write them into self._components[index].

        This is the "form → dict" direction of the roundtrip.
        The opposite direction is _populate_from(), which loads the dict into
        the widgets.

        Called in two situations:
          1. Before switching to a different component — so any edits in the
             currently displayed form are not silently discarded when the user
             clicks a different name in the list.
          2. Before saving — so the most recent widget values are captured even
             if the user hasn't clicked 'Apply' yet.

        WHY _dirty IS SET HERE
        ----------------------
        Calling _collect_into always marks self._dirty = True because we cannot
        know whether the user actually changed anything (tkinter has no built-in
        "has this widget been modified?" flag). The flag is reset to False only
        after a successful disk write in _save_file(). Its only practical use is
        to show a confirmation prompt in _new_file() if there are unsaved changes.
        """
        comp = self._components[index]

        comp["title"]          = self._v_title.get().strip()
        comp["type"]           = self._v_type.get()
        comp["purpose"]        = self._v_purpose.get().strip()
        comp["status"]         = self._v_status.get()
        comp["status_remarks"] = self._v_remarks.get().strip()
        comp["version"]        = self._v_version.get().strip() or "1.0"
        comp["doc_creator"]    = self._v_creator.get().strip()
        comp["description"]    = self._v_description.get("1.0", "end-1c").strip()
        comp["remarks"]        = self._v_remarks_text.get("1.0", "end-1c").strip()

        # Save any unsaved response for the currently displayed control
        if self._selected_ctrl_id:
            text = self._ctrl_response_text.get("1.0", "end-1c").strip()
            if text:
                self._ctrl_responses[self._selected_ctrl_id] = text
            else:
                # If the user cleared the response, remove it
                self._ctrl_responses.pop(self._selected_ctrl_id, None)
            # Always capture the current implementation status
            self._ctrl_impl_status[self._selected_ctrl_id] = \
                self._ctrl_impl_status_var.get() or "implemented"

        # Write both dicts back into the component
        comp["ctrl_responses"]   = dict(self._ctrl_responses)
        comp["ctrl_impl_status"] = dict(self._ctrl_impl_status)
        self._dirty = True

    def _apply_component(self):
        """
        Save the current form into the selected component's dict and refresh
        the list. Does NOT write to disk.
        """
        if self._selected_index is None:
            return
        if not self._v_title.get().strip():
            messagebox.showwarning(
                "Title required",
                "Please enter a Component Title (Section 1) before applying."
            )
            return
        self._collect_into(self._selected_index)
        self._refresh_list()
        self._comp_listbox.selection_set(self._selected_index)
        self._refresh_control_list()   # Update dots after saving
        self._status_lbl.config(
            text="Component changes applied  (not yet saved to disk)",
            fg=self._colors["YELLOW"],
        )

    def _save_new_version(self):
        """
        Archive the component's current version into its revision history,
        then let the user set a new version number — see §10.21.

        Distinct from a plain save: an ordinary save just rewrites the
        current version in place, this records what the version *was*
        (with optional remarks on what changed) before bumping it.
        Does not itself write to disk — Apply/Save still do that.
        """
        if self._selected_index is None:
            return
        self._collect_into(self._selected_index)
        comp = self._components[self._selected_index]
        old_version = comp.get("version", "1.0")

        C = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Save New Version")
        dlg.configure(bg=C["BG"])
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        # usability_review_2.md — this dialog builds its own Toplevel
        # rather than going through _make_dialog(), so it needs its own
        # Escape binding too (Return is bound below, once do_save exists).
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        tk.Label(dlg, text=f"Current version: {old_version}",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                 ).pack(anchor="w", padx=16, pady=(14, 4))

        row = tk.Frame(dlg, bg=C["BG"])
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text="New version:", bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 10), width=14, anchor="w").pack(side="left")
        new_version_var = tk.StringVar(value=old_version)
        tk.Entry(row, textvariable=new_version_var, width=14,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10),
                 highlightthickness=1, highlightbackground=C["HEADER_BG"],
                 ).pack(side="left", ipady=3)

        tk.Label(dlg, text="What changed? (optional)", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "italic")).pack(anchor="w", padx=16, pady=(10, 2))
        remarks_text = tk.Text(dlg, width=44, height=3, bg=C["CARD_BG"], fg=C["TEXT"],
                                insertbackground=C["TEXT"], relief="flat",
                                font=("Helvetica", 10), wrap="word")
        remarks_text.pack(padx=16, pady=(0, 10))

        def do_save():
            new_version = new_version_var.get().strip()
            if not new_version:
                messagebox.showwarning("Version required",
                                        "Please enter a new version number.")
                return
            if new_version == old_version:
                messagebox.showwarning(
                    "Version unchanged",
                    "The new version must be different from the current version."
                )
                return
            remarks = remarks_text.get("1.0", "end-1c").strip()
            revisions = comp.setdefault("revisions", [])
            revisions.insert(0, {
                "version": old_version,
                "date":    now_iso(),
                "remarks": remarks,
            })
            comp["version"] = new_version
            self._dirty = True
            dlg.destroy()
            self._populate_from(self._selected_index)
            self._refresh_list()
            self._status_lbl.config(
                text=f"Version {new_version} recorded  (not yet saved to disk)",
                fg=C["YELLOW"],
            )

        btn_row = tk.Frame(dlg, bg=C["BG"])
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(btn_row, text="Save New Version", command=do_save,
                  bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  ).pack(side="left")
        tk.Button(btn_row, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  ).pack(side="left", padx=(8, 0))
        dlg.bind("<Return>", lambda _e: do_save())

    def _upgrade_oscal_version(self):
        """
        Let the user pick a target OSCAL schema version, validate this
        component against THAT version's schema (not just whichever one
        the toolbar currently has selected), and — only if they confirm —
        re-stamp metadata.oscal-version to it.

        This does not migrate content across OSCAL schema versions (this
        app has no such migration logic for any schema change between
        releases) — it only re-validates and re-labels. If validation
        fails, the user is warned and can still proceed, matching the
        same "doesn't fully conform — save anyway?" pattern already used
        elsewhere (e.g. app.py's _open_catalog()), so the button is never
        able to silently claim compliance it hasn't actually checked.

        Does not itself write to disk — Apply/Save still do that, same as
        _save_new_version().
        """
        if self._selected_index is None:
            messagebox.showinfo("No component", "Please select a component first.")
            return

        available = self._get_oscal_versions()
        if not available:
            messagebox.showwarning(
                "No OSCAL schema versions found",
                "No bundled OSCAL schema zip files were found to upgrade against.",
            )
            return

        self._collect_into(self._selected_index)
        comp = self._components[self._selected_index]
        current_version = comp.get("doc_oscal_version", "") or "unknown"

        C = self._colors
        dlg = tk.Toplevel(self)
        dlg.title("Upgrade OSCAL Version")
        dlg.configure(bg=C["BG"])
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        dlg.bind("<Escape>", lambda _e: dlg.destroy())

        tk.Label(dlg, text=f"Current OSCAL version: {current_version}",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                 ).pack(anchor="w", padx=16, pady=(14, 4))

        row = tk.Frame(dlg, bg=C["BG"])
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text="Upgrade to:", bg=C["BG"], fg=C["TEXT"],
                 font=("Helvetica", 10), width=14, anchor="w").pack(side="left")
        default_target = current_version if current_version in available else available[0]
        target_var = tk.StringVar(value=default_target)
        ttk.Combobox(row, textvariable=target_var, values=available,
                     state="readonly", width=14).pack(side="left")

        tk.Label(
            dlg,
            text="Re-validates this component against the chosen version's schema\n"
                 "before re-labelling it — this does not migrate any content, it\n"
                 "only checks and re-stamps metadata.oscal-version.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"), justify="left",
        ).pack(anchor="w", padx=16, pady=(8, 10))

        def do_upgrade():
            target_version = target_var.get().strip()
            if not target_version:
                messagebox.showwarning("Version required", "Please choose a target version.")
                return
            if target_version == current_version:
                messagebox.showinfo(
                    "Already at this version",
                    f"This component is already stamped as OSCAL {target_version}.",
                )
                return

            # Build from a shallow copy, not comp itself — comp is a plain
            # top-level dict of simple values/lists here (no nested dicts
            # get mutated by the build), so a shallow copy safely isolates
            # _build_single_component_oscal()'s side effects (it writes
            # comp["file_uuid"]/comp["doc_oscal_version"] directly) until
            # the user actually confirms, below. Without this, even
            # clicking Cancel or declining after a failed validation would
            # silently re-stamp doc_oscal_version to whatever the toolbar
            # currently has selected.
            doc = self._build_single_component_oscal(dict(comp))
            doc["component-definition"]["metadata"]["oscal-version"] = target_version

            zip_path = self._get_oscal_version_paths().get(target_version)
            if zip_path:
                valid, errors = validate_oscal_file(doc, "oscal_component_schema.json", zip_path)
                if not valid:
                    detail = "\n".join(errors)
                    proceed = messagebox.askyesno(
                        "Schema validation failed",
                        f"This component does not fully conform to the OSCAL "
                        f"{target_version} schema.\n\n{detail}\n\nUpgrade anyway?",
                        icon="warning",
                    )
                    if not proceed:
                        return
            else:
                # usability_review_2.md — this used to fall through silently
                # here, committing the upgrade with no indication validation
                # never ran at all. The button promises to validate first;
                # a missing schema zip shouldn't let that promise go unmet
                # without at least telling the user.
                proceed = messagebox.askyesno(
                    "OSCAL schema not found",
                    f"Could not find the bundled OSCAL {target_version} schema to "
                    f"validate against, so this component's compliance with that "
                    f"version can't be checked.\n\nUpgrade anyway, without validation?",
                    icon="warning",
                )
                if not proceed:
                    return

            comp["doc_oscal_version"] = target_version
            comp.setdefault("revisions", []).insert(0, {
                "version": comp.get("version", "1.0"),
                "date":    now_iso(),
                "remarks": f"OSCAL version upgraded from {current_version} to {target_version}.",
            })
            self._dirty = True
            dlg.destroy()
            self._populate_from(self._selected_index)
            self._refresh_list()
            self._status_lbl.config(
                text=f"OSCAL version upgraded to {target_version}  (not yet saved to disk)",
                fg=C["YELLOW"],
            )

        btn_row = tk.Frame(dlg, bg=C["BG"])
        btn_row.pack(fill="x", padx=16, pady=(0, 14))
        tk.Button(btn_row, text="Upgrade", command=do_upgrade,
                  bg=C["TEAL_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  ).pack(side="left")
        tk.Button(btn_row, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=10, pady=4, cursor="hand2",
                  ).pack(side="left", padx=(8, 0))
        dlg.bind("<Return>", lambda _e: do_upgrade())

    # =========================================================================
    # CONTROL IMPLEMENTATION — Section 7
    # =========================================================================

    def _get_profile_controls(self):
        """Return the controls to show in Section 7 (shared logic in models.py)."""
        return get_profile_controls(self._get_catalog(), self._get_profile())

    def _on_ctrl_tab_changed(self, _event=None):
        """
        Called when the user switches between the 'All Controls' and
        'Applied Controls' tabs in Section 7.

        Refreshes whichever list just became visible so its contents are
        current, and clears the search box to avoid stale filtering.
        """
        # Clear the search so results are not confusingly pre-filtered
        # when the user switches tabs.
        self._ctrl_search_var.set("")
        # Rebuild both lists to ensure they reflect the latest responses
        self._refresh_control_list()

    def _refresh_control_list(self, search_term=""):
        """Rebuild both control list tabs from the current profile controls."""
        refresh_ctrl_list(
            ctrl_responses=self._ctrl_responses,
            all_controls=self._get_profile_controls(),
            search_term=search_term,
            ctrl_tree=self._ctrl_tree,
            applied_tree=self._applied_ctrl_tree,
            notebook=self._ctrl_notebook,
            progress_lbl=self._ctrl_progress_lbl,
        )

    def _on_ctrl_search(self, *_args):
        """
        Called when the user types in the Section 7 search box.

        Only filters the 'All Controls' tab — the 'Applied Controls' tab
        always shows the complete set of responded controls so the user
        never loses sight of what they have already written.
        """
        self._refresh_control_list(self._ctrl_search_var.get())

    def _on_ctrl_select(self, _event=None):
        """
        Called when the user clicks a row in either the 'All Controls' or
        'Applied Controls' Treeview.

        Works out which tree fired the event, saves any pending response for
        the previously selected control, then loads the response (if any) for
        the newly selected one into the response editor on the right.
        """
        # ── Work out which tree was just clicked ──────────────────────────────
        # Both trees are bound to this same method. We check each one's
        # selection() to find which one actually has a selection.
        ctrl_id = None
        for tree in (self._ctrl_tree, self._applied_ctrl_tree):
            sel = tree.selection()
            if sel:
                ctrl_id = sel[0]   # The iid is the control ID
                # Clear the selection in the other tree so only one row
                # appears highlighted at a time across both tabs.
                other = (self._applied_ctrl_tree
                         if tree is self._ctrl_tree
                         else self._ctrl_tree)
                other.selection_remove(*other.selection())
                break

        if ctrl_id is None:
            return   # Nothing selected in either tree

        # ── Save the current response before switching ────────────────────────
        if self._selected_ctrl_id and self._selected_ctrl_id != ctrl_id:
            current_text = self._ctrl_response_text.get("1.0", "end-1c").strip()
            if current_text:
                self._ctrl_responses[self._selected_ctrl_id] = current_text
            else:
                self._ctrl_responses.pop(self._selected_ctrl_id, None)
            # Persist the implementation status for the control we're leaving
            self._ctrl_impl_status[self._selected_ctrl_id] = \
                self._ctrl_impl_status_var.get() or "implemented"

        self._selected_ctrl_id = ctrl_id

        # ── Find this control's full details from the catalog ─────────────────
        catalog   = self._get_catalog()
        ctrl_dict = None
        if catalog:
            ctrl_dict = next(
                (c for c in catalog["controls"] if c["id"] == ctrl_id), None
            )

        # ── Update the statement label (read-only reference) ──────────────────
        if ctrl_dict:
            label     = ctrl_dict.get("label", ctrl_id)
            statement = ctrl_dict.get("statement", ctrl_dict.get("title", ""))
            self._ctrl_stmt_lbl.config(
                text=f"[{label}]  {statement}",
                fg=self._colors["TEXT"],
            )
        else:
            self._ctrl_stmt_lbl.config(text=ctrl_id, fg=self._colors["SUBTEXT"])

        # ── Load any existing response and status into the editor ────────────
        self._ctrl_response_text.delete("1.0", "end")
        existing = self._ctrl_responses.get(ctrl_id, "")
        if existing:
            self._ctrl_response_text.insert("1.0", existing)
        # Load implementation status (default to "implemented" if not set)
        self._ctrl_impl_status_var.set(
            self._ctrl_impl_status.get(ctrl_id, "implemented")
        )

        # Move focus to the text editor so the user can start typing immediately
        self._ctrl_response_text.focus_set()

    def _save_ctrl_response(self):
        """
        Save the response currently in the text editor for the selected control.

        Updates _ctrl_responses, then refreshes both list tabs so their dot
        indicators and the Applied Controls count stay current.
        """
        if not self._selected_ctrl_id:
            messagebox.showinfo(
                "No control selected",
                "Please select a control from the list first."
            )
            return

        text = self._ctrl_response_text.get("1.0", "end-1c").strip()
        if text:
            self._ctrl_responses[self._selected_ctrl_id] = text
        else:
            # Empty response — remove the entry so the dot clears
            self._ctrl_responses.pop(self._selected_ctrl_id, None)

        # Always persist the implementation status (even when the text is cleared)
        self._ctrl_impl_status[self._selected_ctrl_id] = \
            self._ctrl_impl_status_var.get() or "implemented"

        # Rebuild both lists so dots and tab counts update immediately
        self._refresh_control_list(self._ctrl_search_var.get())

        # Restore the row selection in whichever tree is currently visible.
        # The active tab index: 0 = All Controls, 1 = Applied Controls.
        active_tab = self._ctrl_notebook.index("current")
        active_tree = self._ctrl_tree if active_tab == 0 else self._applied_ctrl_tree
        try:
            active_tree.selection_set(self._selected_ctrl_id)
            active_tree.see(self._selected_ctrl_id)
        except tk.TclError:
            pass   # Row may not exist in Applied tab if response was cleared

        self._dirty = True
        self._status_lbl.config(
            text="Response saved to memory — click 'Apply' then 'Save File'",
            fg=self._colors["YELLOW"],
        )

    # =========================================================================
    # PROPERTY AND ROLE DIALOGS
    # =========================================================================

    def _make_dialog(self, title, width=400):
        """
        Create and return a modal Toplevel dialog centred over the app window.

        This is the shared skeleton used by _property_dialog, _role_dialog,
        and any other dialogs in this tab. It handles the boilerplate that
        would otherwise be copy-pasted into every dialog method:
          - Creating the Toplevel window
          - Setting its background colour
          - Making it modal (grab_set blocks input to all other windows)
          - Making it non-resizable

        The caller is responsible for:
          - Adding content widgets to the returned window
          - Calling dlg.destroy() when done (usually in an _ok() closure)
          - Calling self.wait_window(dlg) to block until the user closes it

        Parameters:
            title - The dialog window title
            width - Window width in pixels (height auto-adjusts to content)

        Returns:
            A configured tk.Toplevel instance ready for content to be added.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        # transient keeps the dialog on top of its parent window even when
        # the parent is clicked — prevents the dialog from disappearing behind
        dlg.transient(self)
        # grab_set makes the dialog modal: all mouse/keyboard input is directed
        # to this dialog until it is closed. Without this, the user could keep
        # clicking the main window while the dialog is open.
        dlg.grab_set()
        dlg.minsize(width, 10)   # enforce minimum width; height auto-sizes to content
        # usability_review_2.md — Escape always means Cancel, regardless of
        # what this particular dialog does, so it's safe to bind here once
        # rather than needing every dialog method to do it individually.
        dlg.bind("<Escape>", lambda _e: dlg.destroy())
        return dlg

    def _dialog(self, title, fields):
        """
        Show a generic modal dialog to collect field values.

        Parameters:
            title  - Window title
            fields - List of (label, key, default, choices_or_None) tuples

        Returns:
            A {key: value} dict, or None if cancelled.
        """
        C   = self._colors
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.configure(bg=C["BG"])
        dlg.resizable(False, False)
        dlg.grab_set()

        vars_ = {}
        for label, key, default, choices in fields:
            row = tk.Frame(dlg, bg=C["BG"])
            row.pack(fill="x", padx=20, pady=5)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=22, anchor="w",
                     ).pack(side="left")
            v = tk.StringVar(value=default)
            vars_[key] = v
            if choices:
                ttk.Combobox(row, textvariable=v, values=choices,
                             state="readonly", width=28, font=("Helvetica", 11),
                             ).pack(side="left")
            else:
                tk.Entry(row, textvariable=v, bg=C["CARD_BG"], fg=C["TEXT"],
                         insertbackground=C["TEXT"], relief="flat",
                         font=("Helvetica", 11), width=32,
                         highlightthickness=1,
                         highlightbackground=C["HEADER_BG"],
                         ).pack(side="left", ipady=3)

        result = {}
        def _ok():
            for k, v in vars_.items():
                result[k] = v.get().strip()
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.wait_window()
        return result if result else None

    def _add_property(self):
        """Show the property dialog and add the result to the table."""
        if self._selected_index is None:
            messagebox.showinfo("No component",
                                "Please select or add a component first.")
            return
        result = self._property_dialog()
        if not result:
            return
        self._components[self._selected_index]["props"].append(result)
        self._prop_tree.insert("", "end", values=(
            result["name"], result["value"], result.get("remarks", "")
        ))
        self._dirty = True

    def _remove_property(self):
        """Remove the selected property row."""
        sel = self._prop_tree.selection()
        if not sel:
            return
        idx = self._prop_tree.index(sel[0])
        if self._selected_index is not None:
            self._components[self._selected_index]["props"].pop(idx)
        self._prop_tree.delete(sel[0])
        self._dirty = True

    def _property_dialog(self, existing=None):
        """
        Show a modal dialog for adding a property.
        The value widget adapts (dropdown vs free entry) based on the name.
        """
        C   = self._colors
        dlg = self._make_dialog("Add Property", width=420)

        # Property name dropdown
        row1 = tk.Frame(dlg, bg=C["BG"])
        row1.pack(fill="x", padx=20, pady=8)
        tk.Label(row1, text="Property Name *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_name = tk.StringVar(value=(existing or {}).get("name", PROP_NAMES[0]))
        ttk.Combobox(row1, textvariable=v_name, values=PROP_NAMES,
                     state="normal", width=28).pack(side="left")

        # Value widget — swaps between dropdown and entry based on name
        row2 = tk.Frame(dlg, bg=C["BG"])
        row2.pack(fill="x", padx=20, pady=4)
        tk.Label(row2, text="Value *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_value = tk.StringVar(value=(existing or {}).get("value", ""))
        val_frame = tk.Frame(row2, bg=C["BG"])
        val_frame.pack(side="left", fill="x", expand=True)

        val_combo = ttk.Combobox(val_frame, textvariable=v_value,
                                 state="readonly", width=28)
        val_entry = tk.Entry(val_frame, textvariable=v_value, width=32,
                             bg=C["CARD_BG"], fg=C["TEXT"],
                             insertbackground=C["TEXT"], relief="flat",
                             font=("Helvetica", 11), highlightthickness=1,
                             highlightbackground=C["HEADER_BG"])

        VALUE_OPTIONS = {
            "public":                    YES_NO_VALUES,
            "virtual":                   YES_NO_VALUES,
            "allows-authenticated-scan": YES_NO_VALUES,
            "implementation-point":      IMPL_POINT_VALUES,
            "asset-type":                ASSET_TYPE_VALUES,
        }

        def refresh_value(*_):
            name = v_name.get()
            opts = VALUE_OPTIONS.get(name)
            if opts:
                val_entry.pack_forget()
                val_combo.configure(values=opts)
                v_value.set(opts[0])
                val_combo.pack(side="left")
            else:
                val_combo.pack_forget()
                v_value.set("")
                val_entry.pack(side="left", ipady=3)

        v_name.trace_add("write", refresh_value)
        refresh_value()

        # Remarks
        row3 = tk.Frame(dlg, bg=C["BG"])
        row3.pack(fill="x", padx=20, pady=4)
        tk.Label(row3, text="Remarks", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_remarks = tk.StringVar(value=(existing or {}).get("remarks", ""))
        tk.Entry(row3, textvariable=v_remarks, width=32,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}
        def _ok():
            if not v_name.get().strip():
                messagebox.showwarning("Required", "Property Name is required.")
                return
            if not v_value.get().strip():
                messagebox.showwarning("Required", "Value is required.")
                return
            result["name"]    = v_name.get().strip()
            result["value"]   = v_value.get().strip()
            result["remarks"] = v_remarks.get().strip()
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.bind("<Return>", lambda _e: _ok())
        dlg.wait_window()
        return result if result else None

    def _add_role(self):
        """Show the role dialog and add the result to the table."""
        if self._selected_index is None:
            messagebox.showinfo("No component",
                                "Please select or add a component first.")
            return
        result = self._role_dialog()
        if not result:
            return
        self._components[self._selected_index]["roles"].append(result)
        self._role_tree.insert("", "end", values=(
            result["role_id"], result.get("remarks", "")
        ))
        self._dirty = True

    def _remove_role(self):
        """Remove the selected role row."""
        sel = self._role_tree.selection()
        if not sel:
            return
        idx = self._role_tree.index(sel[0])
        if self._selected_index is not None:
            self._components[self._selected_index]["roles"].pop(idx)
        self._role_tree.delete(sel[0])
        self._dirty = True

    def _role_dialog(self):
        """Show a modal dialog to add a responsible role."""
        C   = self._colors
        dlg = self._make_dialog("Add Responsible Role", width=400)

        row1 = tk.Frame(dlg, bg=C["BG"])
        row1.pack(fill="x", padx=20, pady=8)
        tk.Label(row1, text="Role ID *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=16, anchor="w").pack(side="left")
        v_role = tk.StringVar(value=RESPONSIBLE_ROLES[0])
        ttk.Combobox(row1, textvariable=v_role, values=RESPONSIBLE_ROLES,
                     state="normal", width=28).pack(side="left")

        row2 = tk.Frame(dlg, bg=C["BG"])
        row2.pack(fill="x", padx=20, pady=4)
        tk.Label(row2, text="Remarks", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=16, anchor="w").pack(side="left")
        v_remarks = tk.StringVar()
        tk.Entry(row2, textvariable=v_remarks, width=32,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        result = {}
        def _ok():
            if not v_role.get().strip():
                messagebox.showwarning("Required", "Role ID is required.")
                return
            result["role_id"]  = v_role.get().strip()
            result["remarks"]  = v_remarks.get().strip()
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.bind("<Return>", lambda _e: _ok())
        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # PROTOCOLS — Section 6
    # =========================================================================

    def _format_port_ranges(self, port_ranges):
        """
        Return a short display string for a list of port-range dicts, e.g.
        "TCP:443  TCP:80" or "TCP:8000-8080". Returns "—" for an empty list.
        """
        if not port_ranges:
            return "—"
        parts = []
        for pr in port_ranges:
            transport = pr.get("transport", "TCP")
            start = pr.get("start")
            end   = pr.get("end", start)
            if start is None:
                continue
            # Collapse single-port ranges (start == end) to just the number
            port = str(start) if end in (None, start) else f"{start}-{end}"
            parts.append(f"{transport}:{port}")
        return "  ".join(parts) if parts else "—"

    def _update_proto_count(self):
        """Refresh the "N protocols" label next to the Section 6 hint text."""
        n = len(self._proto_tree.get_children())
        self._proto_count_lbl.config(text=f"{n} protocol{'s' if n != 1 else ''}")

    def _refresh_proto_tree(self):
        """Clear and repopulate the protocol tree from the current component."""
        self._proto_tree.delete(*self._proto_tree.get_children())
        if self._selected_index is None:
            self._update_proto_count()
            return
        comp = self._components[self._selected_index]
        for proto in comp.get("protocols", []):
            self._proto_tree.insert("", "end", values=(
                proto.get("name", ""),
                proto.get("title", ""),
                self._format_port_ranges(proto.get("port_ranges", [])),
            ))
        self._update_proto_count()

    def _add_protocol(self):
        """Show the protocol dialog and add the result to the table."""
        if self._selected_index is None:
            messagebox.showinfo("No component",
                                "Please select or add a component first.")
            return
        result = self._protocol_dialog()
        if not result:
            return
        comp = self._components[self._selected_index]
        comp.setdefault("protocols", []).append(result)
        self._refresh_proto_tree()
        self._dirty = True

    def _remove_protocol(self):
        """Remove the selected protocol row."""
        if self._selected_index is None:
            return
        sel = self._proto_tree.selection()
        if not sel:
            return
        idx = self._proto_tree.index(sel[0])
        comp = self._components[self._selected_index]
        protocols = comp.setdefault("protocols", [])
        if 0 <= idx < len(protocols):
            protocols.pop(idx)
        self._refresh_proto_tree()
        self._dirty = True

    def _protocol_dialog(self, existing=None):
        """
        Show a modal dialog for adding a protocol with its port ranges.
        Returns a protocol dict or None if cancelled.
        """
        C   = self._colors
        dlg = self._make_dialog("Add Protocol", width=480)

        # ── Protocol name (free-entry combobox) ───────────────────────────────
        tk.Label(dlg,
                 text="Select a common protocol from the list or type your own name.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20, pady=(8, 2))
        row1 = tk.Frame(dlg, bg=C["BG"])
        row1.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(row1, text="Protocol Name *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=16, anchor="w").pack(side="left")
        v_name = tk.StringVar(value=(existing or {}).get("name", ""))
        ttk.Combobox(row1, textvariable=v_name, values=COMMON_PROTOCOLS,
                     state="normal", width=28).pack(side="left")

        # ── Title ──────────────────────────────────────────────────────────────
        row2 = tk.Frame(dlg, bg=C["BG"])
        row2.pack(fill="x", padx=20, pady=4)
        tk.Label(row2, text="Title", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=16, anchor="w").pack(side="left")
        v_title = tk.StringVar(value=(existing or {}).get("title", ""))
        tk.Entry(row2, textvariable=v_title, width=36,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)

        # ── Port ranges section ──────────────────────────────────────────────
        tk.Label(dlg, text="Port Ranges", bg=C["BG"], fg=C["ACCENT"],
                 font=("Helvetica", 10, "bold")).pack(anchor="w", padx=20, pady=(10, 2))

        pr_frame = tk.Frame(dlg, bg=C["BG"])
        pr_frame.pack(fill="x", padx=20, pady=2)
        pr_tree = ttk.Treeview(
            pr_frame, columns=("start", "end", "transport", "remarks"),
            show="headings", height=4, selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("start",     "Start",     60,  False),
            ("end",       "End",       60,  False),
            ("transport", "Transport", 80,  False),
            ("remarks",   "Remarks",   160, True),
        ]:
            pr_tree.heading(col, text=heading, anchor="w")
            pr_tree.column(col, width=w, anchor="w", stretch=stretch)
        pr_tree.pack(fill="x")

        # Local list mirroring the inner treeview rows
        port_ranges = []
        for pr in (existing or {}).get("port_ranges", []):
            port_ranges.append(dict(pr))
            pr_tree.insert("", "end", values=(
                pr.get("start", ""), pr.get("end", ""),
                pr.get("transport", "TCP"), pr.get("remarks", ""),
            ))

        # ── Add-port-range entry row ──────────────────────────────────────────
        add_row = tk.Frame(dlg, bg=C["BG"])
        add_row.pack(fill="x", padx=20, pady=(6, 2))

        tk.Label(add_row, text="Start", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left")
        v_start = tk.StringVar()
        pr_start_entry = tk.Entry(add_row, textvariable=v_start, width=6,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"])
        pr_start_entry.pack(side="left", padx=(2, 6))

        tk.Label(add_row, text="End", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left")
        v_end = tk.StringVar()
        pr_end_entry = tk.Entry(add_row, textvariable=v_end, width=6,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"])
        pr_end_entry.pack(side="left", padx=(2, 6))

        tk.Label(add_row, text="Transport", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left")
        v_transport = tk.StringVar(value="TCP")
        ttk.Combobox(add_row, textvariable=v_transport, values=["TCP", "UDP"],
                     state="readonly", width=6).pack(side="left", padx=(2, 6))

        tk.Label(add_row, text="Remarks", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10)).pack(side="left")
        v_pr_remarks = tk.StringVar()
        pr_remarks_entry = tk.Entry(add_row, textvariable=v_pr_remarks, width=20,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 10), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"])
        pr_remarks_entry.pack(side="left", padx=(2, 6))

        def _add_pr():
            start_raw = v_start.get().strip()
            if not start_raw:
                messagebox.showwarning("Required", "Start port is required.")
                return
            try:
                start = int(start_raw)
            except ValueError:
                messagebox.showwarning("Invalid", "Start port must be a number.")
                return
            if not (1 <= start <= 65535):
                messagebox.showwarning(
                    "Invalid Port",
                    "Start port must be a whole number between 1 and 65535.",
                )
                return
            end_raw = v_end.get().strip()
            if end_raw:
                try:
                    end = int(end_raw)
                except ValueError:
                    messagebox.showwarning("Invalid", "End port must be a number.")
                    return
                if not (1 <= end <= 65535):
                    messagebox.showwarning(
                        "Invalid Port",
                        "End port must be a whole number between 1 and 65535.",
                    )
                    return
                if end < start:
                    messagebox.showwarning(
                        "Invalid Range",
                        "End port cannot be lower than the start port.",
                    )
                    return
            else:
                end = start   # default end to the start port
            transport = v_transport.get()
            remarks   = v_pr_remarks.get().strip()
            port_ranges.append({
                "start": start, "end": end,
                "transport": transport, "remarks": remarks,
            })
            pr_tree.insert("", "end", values=(start, end, transport, remarks))
            # Clear entry fields for the next addition
            v_start.set(""); v_end.set(""); v_pr_remarks.set("")

        tk.Button(add_row, text="＋  Add", command=_add_pr,
                  bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 9),
                  relief="flat", padx=8, cursor="hand2").pack(side="left")
        # usability_review_2.md — Return here should add the port range being
        # typed, not submit the whole dialog (that's what the OK button is
        # for), so these get their own binding instead of a dialog-wide one.
        for _entry in (pr_start_entry, pr_end_entry, pr_remarks_entry):
            _entry.bind("<Return>", lambda _e: _add_pr())

        def _remove_pr():
            sel = pr_tree.selection()
            if not sel:
                return
            idx = pr_tree.index(sel[0])
            if 0 <= idx < len(port_ranges):
                port_ranges.pop(idx)
            pr_tree.delete(sel[0])

        tk.Button(dlg, text="✕  Remove Selected Port Range", command=_remove_pr,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  ).pack(anchor="w", padx=20, pady=(4, 2))

        result = {}
        def _ok():
            if not v_name.get().strip():
                messagebox.showwarning("Required", "Protocol Name is required.")
                return
            result["name"]        = v_name.get().strip()
            result["title"]       = v_title.get().strip()
            result["port_ranges"] = [dict(pr) for pr in port_ranges]
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # LINKS — Section 7
    # =========================================================================

    # Relationship values defined by the OSCAL component-definition schema plus
    # common extension values used in practice.
    _LINK_REL_VALUES = [
        "reference",
        "vendor-documentation",
        "security-advisory",
        "configuration-baseline",
        "policy",
        "homepage",
        "related",
        "dependency",
        "required-by",
    ]

    def _add_link(self):
        """Show the link dialog and add the result to the links table."""
        if self._selected_index is None:
            messagebox.showinfo("No component",
                                "Please select or add a component first.")
            return
        result = self._link_dialog()
        if not result:
            return
        self._components[self._selected_index].setdefault("links", []).append(result)
        self._link_tree.insert("", "end", values=(
            result["rel"], result["href"], result.get("text", "")
        ))
        self._dirty = True

    def _remove_link(self):
        """Remove the selected link row."""
        if self._selected_index is None:
            return
        sel = self._link_tree.selection()
        if not sel:
            return
        idx = self._link_tree.index(sel[0])
        links = self._components[self._selected_index].setdefault("links", [])
        if 0 <= idx < len(links):
            links.pop(idx)
        self._link_tree.delete(sel[0])
        self._dirty = True

    def _add_doc_link(self):
        """
        Same as _add_link(), but for the Document Metadata card's
        metadata.links — describes the file itself, not the component.
        """
        if self._selected_index is None:
            messagebox.showinfo("No component",
                                "Please select or add a component first.")
            return
        result = self._link_dialog()
        if not result:
            return
        self._components[self._selected_index].setdefault("doc_links", []).append(result)
        self._doc_link_tree.insert("", "end", values=(
            result["rel"], result["href"], result.get("text", "")
        ))
        self._dirty = True

    def _remove_doc_link(self):
        """Remove the selected document-link row — see _add_doc_link()."""
        if self._selected_index is None:
            return
        sel = self._doc_link_tree.selection()
        if not sel:
            return
        idx = self._doc_link_tree.index(sel[0])
        doc_links = self._components[self._selected_index].setdefault("doc_links", [])
        if 0 <= idx < len(doc_links):
            doc_links.pop(idx)
        self._doc_link_tree.delete(sel[0])
        self._dirty = True

    def _link_dialog(self, existing=None):
        """
        Show a modal dialog for adding or editing a link.
        Returns a link dict {rel, href, text} or None if cancelled.
        """
        C   = self._colors
        dlg = self._make_dialog("Add Link", width=520)

        tk.Label(dlg,
                 text="Add an external reference — vendor docs, CVE advisories,\n"
                      "configuration baselines, policy documents, or related resources.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
                 ).pack(anchor="w", padx=20, pady=(10, 6))

        # Relationship (rel)
        row1 = tk.Frame(dlg, bg=C["BG"])
        row1.pack(fill="x", padx=20, pady=4)
        tk.Label(row1, text="Relationship *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_rel = tk.StringVar(value=(existing or {}).get("rel", self._LINK_REL_VALUES[0]))
        ttk.Combobox(row1, textvariable=v_rel, values=self._LINK_REL_VALUES,
                     state="normal", width=28).pack(side="left")

        # Relationship hint label — updates as the user changes rel
        hint_lbl = tk.Label(dlg, text="", bg=C["BG"], fg=C["SUBTEXT"],
                            font=("Helvetica", 9, "italic"))
        hint_lbl.pack(anchor="w", padx=20)

        _REL_HINTS = {
            "reference":             "A general reference to supporting documentation.",
            "vendor-documentation":  "Official vendor product documentation or user guide.",
            "security-advisory":     "CVE advisory, vendor security bulletin, or CERT notice.",
            "configuration-baseline":"CIS Benchmark, ASD hardening guide, or DISA STIG.",
            "policy":                "An organisational policy document.",
            "homepage":              "The product or project home page.",
            "related":               "A related component, system, or resource.",
            "dependency":            "A dependency this component requires.",
            "required-by":           "A component or system that requires this component.",
        }

        def _update_hint(*_):
            hint_lbl.config(text=_REL_HINTS.get(v_rel.get(), ""))
        v_rel.trace_add("write", _update_hint)
        _update_hint()

        # URL / href
        row2 = tk.Frame(dlg, bg=C["BG"])
        row2.pack(fill="x", padx=20, pady=4)
        tk.Label(row2, text="URL / Reference *", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_href = tk.StringVar(value=(existing or {}).get("href", "https://"))
        tk.Entry(row2, textvariable=v_href, width=38,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3,
                                                          fill="x", expand=True)

        tk.Label(dlg,
                 text="  Use a full URL (https://...) for external links, or a relative\n"
                      "  path / fragment (#uuid) for internal back-matter references.",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 8, "italic"),
                 ).pack(anchor="w", padx=20)

        # Display text
        row3 = tk.Frame(dlg, bg=C["BG"])
        row3.pack(fill="x", padx=20, pady=4)
        tk.Label(row3, text="Label / Text", bg=C["BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 11), width=18, anchor="w").pack(side="left")
        v_text = tk.StringVar(value=(existing or {}).get("text", ""))
        tk.Entry(row3, textvariable=v_text, width=38,
                 bg=C["CARD_BG"], fg=C["TEXT"], insertbackground=C["TEXT"],
                 relief="flat", font=("Helvetica", 11), highlightthickness=1,
                 highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3,
                                                          fill="x", expand=True)

        result = {}

        def _ok():
            href = v_href.get().strip()
            rel  = v_rel.get().strip()
            if not rel:
                messagebox.showwarning("Required", "Relationship is required.")
                return
            if not href:
                messagebox.showwarning("Required", "URL / Reference is required.")
                return
            result["rel"]  = rel
            result["href"] = href
            result["text"] = v_text.get().strip()
            dlg.destroy()

        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10, pady=2, cursor="hand2",
                  activebackground=C["ACCENT_BG"], activeforeground=C["BUTTON_TEXT"]).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["SECONDARY_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10, pady=2, cursor="hand2",
                  activebackground=C["HEADER_BG"], activeforeground=C["BUTTON_TEXT"]).pack(side="left")
        dlg.bind("<Return>", lambda _e: _ok())
        dlg.wait_window()
        return result if result else None

    # =========================================================================
    # OSCAL JSON CONVERSION
    # =========================================================================

    def _build_single_component_oscal(self, comp):
        """
        Convert ONE component dict into a valid OSCAL Component Definition
        JSON document containing only that single component.

        Per the OSCAL schema (oscal_component_metaschema.xml), a
        component-definition file MAY contain multiple components, but
        the intended workflow here is one component per file so each
        component is independently referenceable and shareable.

        Parameters:
            comp - A single component dict from self._components

        Returns:
            A nested Python dict ready to be written as JSON.
        """
        now = now_iso()

        # Resolve the source URI for control-implementations (shared helper).
        source_href = get_source_href(self._get_profile(), self._get_catalog())

        # ── Build the single OSCAL component entry ────────────────────────────
        c = build_component_oscal_entry(comp, source_href)

        # ── Assemble the full OSCAL component-definition document ─────────────
        # The file-level title is derived from the component type and title
        # so the file is clearly identified without opening it.
        file_title = self._file_title.get().strip() or comp.get("title", "Component Definition")

        # Document identity/version come from the component itself, not
        # shared tab-level state — see §10.21. Every component keeps its
        # own file_uuid/version/revisions so multiple components can be
        # tracked independently in the same tab (essential in library_mode).
        if not comp.get("file_uuid"):
            comp["file_uuid"] = new_uuid()
        metadata = {
            "title":         file_title,
            "last-modified": now,
            "version":       comp.get("version", "").strip() or "1.0",
            "oscal-version": self._get_oscal_version(),
        }
        # Keep the displayed "OSCAL Version" label (Document Metadata card)
        # in sync with what's actually about to be written, so it reflects
        # reality immediately after a save rather than only after a reload.
        comp["doc_oscal_version"] = metadata["oscal-version"]
        revisions = comp.get("revisions") or []
        if revisions:
            metadata["revisions"] = [
                {
                    "title":         rev.get("title", "Previous version"),
                    "version":       rev["version"],
                    "last-modified": rev.get("date", now),
                    **({"remarks": rev["remarks"]} if rev.get("remarks") else {}),
                }
                for rev in revisions
            ]

        # Document-level metadata.parties/links — e.g. the CivicActions
        # attribution seen on the Library's aws.json/django.json/etc. All
        # standard OSCAL: a party with a "creator" role via responsible-
        # parties, and a links[] array describing the file itself (not the
        # component — that's Section 7's per-component links, kept separate).
        if comp.get("doc_creator"):
            party_uuid = new_uuid()
            metadata["roles"] = [{"id": "creator", "title": "Creator"}]
            metadata["parties"] = [{
                "uuid": party_uuid, "type": "organization", "name": comp["doc_creator"],
            }]
            metadata["responsible-parties"] = [{
                "role-id": "creator", "party-uuids": [party_uuid],
            }]
        if comp.get("doc_links"):
            metadata["links"] = [
                {
                    "rel": link["rel"], "href": link["href"],
                    **({"text": link["text"]} if link.get("text") else {}),
                }
                for link in comp["doc_links"]
            ]

        doc = {
            "component-definition": {
                "uuid": comp["file_uuid"],
                "metadata": metadata,
                # The schema requires components to be in an array.
                # We always write exactly one component per file.
                "components": [c],
            }
        }
        return doc

    def _parse_single_component(self, data):
        """
        Parse one OSCAL Component Definition JSON file and extract the
        first component from it as an internal dict.

        Since we now save one component per file, each file will normally
        have exactly one entry in its 'components' array. This method
        extracts that component and returns it ready to be appended to
        self._components. It does NOT reset the component list — that is
        intentional so multiple files can be loaded one after another.

        Parameters:
            data - A Python dict from json.load() of a saved component file.

        Returns:
            A component dict in the internal format, or None if the file
            contains no components.
        """
        root = data.get("component-definition", {})
        raw  = root.get("components", [])
        if not raw:
            return None

        # Take the first (normally only) component in the file
        c = raw[0]

        # Document-level identity/version — see §10.21. Read back onto the
        # component itself (not shared tab-level state) so each component
        # keeps its own version/UUID history independent of any other
        # component loaded into the same tab.
        meta = root.get("metadata", {})
        revisions = [
            {
                "version": rev.get("version", ""),
                "date":    rev.get("last-modified", ""),
                "remarks": rev.get("remarks", ""),
            }
            for rev in meta.get("revisions", [])
        ]

        # Document-level metadata.parties/links — see the matching build
        # side in _build_single_component_oscal() for what these represent.
        # Prefer the party tied to a "creator" role (responsible-parties);
        # fall back to the first party if the file has one but no explicit
        # creator role (still schema-valid, just less specific attribution).
        parties = meta.get("parties", [])
        doc_creator = ""
        if parties:
            creator_party_uuid = next(
                (rp["party-uuids"][0]
                 for rp in meta.get("responsible-parties", [])
                 if rp.get("role-id") == "creator" and rp.get("party-uuids")),
                None,
            )
            if creator_party_uuid:
                doc_creator = next(
                    (p.get("name", "") for p in parties if p.get("uuid") == creator_party_uuid),
                    "",
                )
            else:
                doc_creator = parties[0].get("name", "")
        doc_links = [
            {"rel": link.get("rel", ""), "href": link.get("href", ""), "text": link.get("text", "")}
            for link in meta.get("links", [])
        ]

        all_props   = c.get("props", [])
        status_prop = next(
            (p for p in all_props if p.get("name") == "operational-status"),
            None
        )
        # Separate out the status prop from the user-defined props
        user_props = [
            {"name": p["name"], "value": p["value"],
             "remarks": p.get("remarks", "")}
            for p in all_props
            if p.get("name") != "operational-status"
        ]

        roles = [
            {"role_id": r.get("role-id", ""), "remarks": r.get("remarks", "")}
            for r in c.get("responsible-roles", [])
        ]

        # Parse protocols
        protocols = []
        for proto in c.get("protocols", []):
            prs = []
            for pr in proto.get("port-ranges", []):
                prs.append({
                    "start":     pr.get("start", 0),
                    "end":       pr.get("end",   pr.get("start", 0)),
                    "transport": pr.get("transport", "TCP"),
                    "remarks":   pr.get("remarks", ""),
                })
            protocols.append({
                "name":        proto.get("name", ""),
                "title":       proto.get("title", ""),
                "port_ranges": prs,
            })

        # Parse links
        links = [
            {
                "href": lnk.get("href", ""),
                "rel":  lnk.get("rel",  "reference"),
                "text": lnk.get("text", ""),
            }
            for lnk in c.get("links", [])
            if lnk.get("href", "").strip()
        ]

        # Flatten OSCAL control-implementations back to internal dicts
        ctrl_responses   = {}
        ctrl_impl_status = {}
        for ci in c.get("control-implementations", []):
            for req in ci.get("implemented-requirements", []):
                ctrl_id = req.get("control-id", "")
                desc    = req.get("description", "")
                if ctrl_id and desc:
                    ctrl_responses[ctrl_id] = desc
                # Parse implementation-status if present (defaults to "implemented")
                impl_st = req.get("implementation-status", {})
                if ctrl_id and impl_st.get("state"):
                    ctrl_impl_status[ctrl_id] = impl_st["state"]

        return {
            "uuid":             c.get("uuid", new_uuid()),
            "title":            c.get("title", ""),
            "type":             c.get("type", COMPONENT_TYPES[0]),
            "description":      c.get("description", ""),
            "purpose":          c.get("purpose", ""),
            "status":           status_prop["value"] if status_prop else COMPONENT_STATUS[0],
            "status_remarks":   status_prop.get("remarks", "") if status_prop else "",
            "remarks":          c.get("remarks", ""),
            "props":            user_props,
            "roles":            roles,
            "protocols":        protocols,
            "links":            links,
            "ctrl_responses":   ctrl_responses,
            "ctrl_impl_status": ctrl_impl_status,
            "file_uuid":        root.get("uuid") or new_uuid(),
            "version":          meta.get("version", "1.0"),
            "revisions":        revisions,
            "doc_creator":      doc_creator,
            "doc_links":        doc_links,
            "doc_oscal_version": meta.get("oscal-version", ""),
        }

    def _load_component_from_path(self, path):
        """
        Load one component from a JSON file at the given path and append
        it to self._components.

        This is the shared core used by both _open_files() and
        _open_folder(). Returns True on success, False if the file was
        skipped (not a valid component definition, or a duplicate UUID).

        Parameters:
            path - A string or Path object pointing to a JSON file.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            # Cannot read the file or it is not valid JSON — skip it silently
            return False

        if "component-definition" not in data:
            # Not a component definition file — skip silently
            return False

        comp = self._parse_single_component(data)
        if comp is None:
            return False

        # Skip duplicate UUIDs — prevents loading the same file twice if
        # the user accidentally selects it again or opens a folder that
        # contains a file already in the list.
        existing_uuids = {c["uuid"] for c in self._components}
        if comp["uuid"] in existing_uuids:
            return False

        self._components.append(comp)
        self._loaded_paths.append(str(path))
        self._component_paths[comp["uuid"]] = str(path)
        return True

    def load_from_paths(self, paths):
        """
        Load multiple component files by path, e.g. from a Workspace manifest.

        Shares the same _load_component_from_path()/_after_open() logic as
        _open_files() and _open_folder(), so duplicate UUIDs and invalid
        files are handled identically. Returns (added, skipped) counts.
        """
        added   = 0
        skipped = 0
        for path in paths:
            if self._load_component_from_path(path):
                added += 1
            else:
                skipped += 1
        self._after_open(added, skipped)
        return added, skipped

    # =========================================================================
    # FILE ACTIONS
    # =========================================================================

    def _validate_selected(self):
        """
        Validate that the currently selected component is ready to save.

        Returns a list of error strings. An empty list means ready to save.
        Only the selected component is checked because each is saved as its
        own independent file.
        """
        errors = []

        if self._selected_index is None:
            errors.append("No component is selected. Select one from the list first.")
            return errors

        comp = self._components[self._selected_index]

        # Both title and description are required by the OSCAL schema
        if not comp.get("title", "").strip():
            errors.append("Component Title is required (Section 1).")
        if not comp.get("description", "").strip():
            errors.append("Component Description is required (Section 2).")

        return errors

    def _save_file(self):
        """
        Validate and save the CURRENTLY SELECTED component to its own
        OSCAL Component Definition JSON file.

        Each component is saved as a separate file — one component per file.
        The filename is auto-generated from the component type and title.

        In library_mode there is no save-location dialog — see
        _save_to_library_path() — since this editor only ever writes into
        the Library's components/ folder.
        """
        if self._selected_index is not None:
            self._collect_into(self._selected_index)

        errors = self._validate_selected()
        if errors:
            messagebox.showerror(
                "Cannot save component",
                "Please fix the following before saving:\n\n" +
                "\n".join(f"• {e}" for e in errors)
            )
            return

        comp       = self._components[self._selected_index]
        comp_type  = comp.get("type", "").strip()
        comp_title = comp.get("title", "").strip()

        if self._library_mode:
            path = self._save_to_library_path(comp)
            if path is None:
                return
        else:
            if comp_type and comp_title:
                initial_file = f"{comp_type}_{safe_filename_component(comp_title)}.json"
            else:
                initial_file = "component_definition.json"

            path = filedialog.asksaveasfilename(
                title="Save OSCAL Component Definition",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                initialfile=initial_file,
            )
            if not path:
                return

        doc = self._build_single_component_oscal(comp)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)

        self._loaded_paths.append(str(path))
        self._component_paths[comp["uuid"]] = str(path)
        self._dirty = False
        fname = Path(path).name
        self._status_lbl.config(text=f"Saved: {fname}", fg=self._colors["GREEN"])
        self._set_status(f"Component saved: {fname}")
        if not self._library_mode:
            messagebox.showinfo(
                "Component Saved",
                f"Component '{comp_title}' saved successfully:\n{path}"
            )

    def _save_to_library_path(self, comp):
        """
        Resolve where to save `comp` when in library_mode, with no dialog:
        the path it was already loaded from/saved to if known, otherwise a
        new auto-generated filename inside the Library's components/ folder
        — the same naming convention as the normal Save dialog's default,
        disambiguated with a short UUID suffix if that name is already
        taken by a different component (rather than silently overwriting
        an unrelated file with the same type+title).

        Returns the path, or None if no Library folder is configured (the
        caller should already have one, since library_mode instances are
        always constructed with a real get_library_path — this is a
        defensive fallback, not an expected path).
        """
        existing = self._component_paths.get(comp["uuid"])
        if existing:
            return existing

        library = self._get_library_path()
        if not library:
            messagebox.showerror(
                "No Library folder set",
                "Set a Library folder first, using the '📚 Library Folder' "
                "button in the main toolbar.",
            )
            return None

        comp_dir  = Path(library) / "components"
        comp_dir.mkdir(parents=True, exist_ok=True)
        comp_type  = comp.get("type", "").strip() or "component"
        comp_title = safe_filename_component(comp.get("title", "").strip()) or "untitled"

        candidate = comp_dir / f"{comp_type}_{comp_title}.json"
        if candidate.exists():
            # Same generated name already on disk — only reuse it if it's
            # actually this same component (re-saving after a rename that
            # happens to produce the same filename); otherwise disambiguate
            # rather than silently overwrite an unrelated file.
            try:
                with open(candidate, encoding="utf-8") as f:
                    existing_doc = json.load(f)
                existing_uuids = {
                    c.get("uuid") for c in existing_doc.get("component-definition", {}).get("components", [])
                }
            except (OSError, json.JSONDecodeError):
                existing_uuids = set()
            if comp["uuid"] not in existing_uuids:
                candidate = comp_dir / f"{comp_type}_{comp_title}_{comp['uuid'][:8]}.json"

        return str(candidate)

    def _open_files(self):
        """
        Open one or more component JSON files selected by the user.

        Each file's component is APPENDED to the current component list —
        existing components are kept. The user can select multiple files
        at once using Ctrl+click or Shift+click in the file browser.
        Duplicate components (same UUID) are silently skipped.
        """
        # askopenfilenames (plural) returns a tuple of selected paths,
        # or an empty tuple if the user cancelled. The user can select
        # multiple files in one dialog using Ctrl+click / Shift+click.
        paths = filedialog.askopenfilenames(
            title="Open Component File(s) — Ctrl+click to select multiple",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not paths:
            return

        added   = 0
        skipped = 0
        for path in paths:
            if self._load_component_from_path(path):
                added += 1
            else:
                skipped += 1

        self._after_open(added, skipped)

    def _open_folder(self):
        """
        Open a folder and load every valid component JSON file inside it.

        Each file's component is APPENDED to the current component list.
        Files that are not valid OSCAL Component Definition documents are
        silently ignored. Duplicate UUIDs are also skipped.
        """
        folder = filedialog.askdirectory(
            title="Open Folder — loads all component JSON files inside"
        )
        if not folder:
            return

        # Path.glob("*.json") finds all .json files in the folder (not recursive).
        # sorted() makes the order consistent across operating systems.
        json_files = sorted(Path(folder).glob("*.json"))
        if not json_files:
            messagebox.showinfo(
                "No JSON files found",
                f"No .json files were found in:\n{folder}"
            )
            return

        added   = 0
        skipped = 0
        for path in json_files:
            if self._load_component_from_path(path):
                added += 1
            else:
                skipped += 1

        self._after_open(added, skipped)

    def _import_from_library(self):
        """
        Copy one or more component files from the shared Library folder
        into the current system's folder, then load the copies into this
        list — the System Owner's way of inheriting a component from an
        organisation-level library rather than defining it from scratch
        (see user_stories.md US-12).

        Requires both a configured Library folder (app.py "📚 Library
        Folder" button) and an active system folder (a workspace must be
        open/saved — see app.py get_system_folder()), since otherwise
        there is nowhere to copy the file to.
        """
        library = self._get_library_path()
        if not library:
            messagebox.showinfo(
                "No Library folder set",
                "Set a Library folder first, using the '📚 Library Folder' "
                "button in the main toolbar.",
            )
            return

        system_folder = self._get_system_folder()
        if not system_folder:
            messagebox.showinfo(
                "No active system",
                "Open or save a Workspace first, so the app knows which "
                "system's folder to import into.",
            )
            return

        library_components = Path(library) / "components"
        paths = filedialog.askopenfilenames(
            title="Import Component(s) from Library — Ctrl+click to select multiple",
            initialdir=str(library_components) if library_components.is_dir() else str(library),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not paths:
            return

        dest_folder = Path(system_folder) / "components"
        dest_folder.mkdir(parents=True, exist_ok=True)

        copied_paths = []
        skipped_existing = 0
        for src in paths:
            dest = dest_folder / Path(src).name
            if dest.exists():
                # Don't clobber a copy that's already been imported and
                # possibly edited locally for this system.
                skipped_existing += 1
                continue
            shutil.copy2(src, dest)
            copied_paths.append(str(dest))

        added, skipped_invalid = self.load_from_paths(copied_paths)

        parts = [f"{added} imported"]
        if skipped_existing:
            parts.append(f"{skipped_existing} already in this system's folder")
        if skipped_invalid:
            parts.append(f"{skipped_invalid} not valid component files")
        self._set_status("Import from Library: " + ", ".join(parts))

    def _load_library_folder(self):
        """
        library_mode only: clear the current list and reload every
        component file in the Library's components/ folder from disk.

        This is the ONLY way this instance's list is ever populated — no
        Open File(s)/Open Folder — so it doubles as both the initial load
        (called once from __init__) and the "🔄 Refresh from Library"
        button, in case files were added/changed on disk since the tab
        was built (e.g. by another running instance, or externally).
        """
        self._components      = []
        self._loaded_paths    = []
        self._component_paths = {}
        self._selected_index  = None

        library = self._get_library_path()
        added = skipped = 0
        if library:
            comp_dir = Path(library) / "components"
            if comp_dir.is_dir():
                for path in sorted(comp_dir.glob("*.json")):
                    if self._load_component_from_path(path):
                        added += 1
                    else:
                        skipped += 1

        self._selected_index   = None
        self._ctrl_responses   = {}
        self._ctrl_impl_status = {}
        if hasattr(self, "_comp_search_var"):
            self._comp_search_var.set("")
        if hasattr(self, "_comp_type_filter_var"):
            self._comp_type_filter_var.set("all")
        self._refresh_list()
        self._show_form_placeholder()

        msg = f"Loaded {added} component(s) from Library"
        if skipped:
            msg += f" ({skipped} skipped — invalid files)"
        if hasattr(self, "_status_lbl"):
            self._status_lbl.config(text=msg, fg=self._colors["TEXT"])
        self._set_status(msg)
        self._on_components_changed()

    def _add_file_to_library(self):
        """
        library_mode only: copy an external component file into the
        Library's components/ folder, then load the copy — the one
        controlled way anything enters this editor from outside the
        Library (e.g. a vendor-provided or another team's component file),
        without ever letting this editor open or save anywhere else.
        """
        library = self._get_library_path()
        if not library:
            messagebox.showerror(
                "No Library folder set",
                "Set a Library folder first, using the '📚 Library Folder' "
                "button in the main toolbar.",
            )
            return

        paths = filedialog.askopenfilenames(
            title="Add Component File(s) to Library — Ctrl+click to select multiple",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not paths:
            return

        dest_folder = Path(library) / "components"
        dest_folder.mkdir(parents=True, exist_ok=True)

        copied_paths = []
        skipped_existing = 0
        for src in paths:
            dest = dest_folder / Path(src).name
            if dest.exists():
                skipped_existing += 1
                continue
            shutil.copy2(src, dest)
            copied_paths.append(str(dest))

        added, skipped_invalid = self.load_from_paths(copied_paths)

        parts = [f"{added} added"]
        if skipped_existing:
            parts.append(f"{skipped_existing} already in the Library")
        if skipped_invalid:
            parts.append(f"{skipped_invalid} not valid component files")
        self._set_status("Add to Library: " + ", ".join(parts))

    def _after_open(self, added, skipped):
        """
        Shared cleanup after _open_files() or _open_folder() finishes.

        Rebuilds the component list widget, clears the selection, shows
        the placeholder, and updates the status bar with a summary message.

        Parameters:
            added   - Number of components successfully added
            skipped - Number of files skipped (not valid or duplicate)
        """
        self._selected_index   = None
        self._ctrl_responses   = {}
        self._ctrl_impl_status = {}
        # Reset filters so all newly loaded components are visible
        if hasattr(self, "_comp_search_var"):
            self._comp_search_var.set("")
        if hasattr(self, "_comp_type_filter_var"):
            self._comp_type_filter_var.set("all")
        self._refresh_list()
        self._show_form_placeholder()

        total = len(self._components)
        if added == 0:
            msg = "No new components loaded (files may already be in the list)."
            self._status_lbl.config(text=msg, fg=self._colors["YELLOW"])
        elif skipped > 0:
            msg = (f"Added {added} component{'s' if added != 1 else ''}, "
                   f"skipped {skipped} (not valid or duplicate). "
                   f"{total} total.")
            self._status_lbl.config(text=msg, fg=self._colors["BLUE"])
        else:
            msg = (f"Loaded {added} component{'s' if added != 1 else ''}. "
                   f"{total} total in list.")
            self._status_lbl.config(text=msg, fg=self._colors["BLUE"])

        self._set_status(msg)
        # Component list changed — let the Capability Editor re-check its guard
        self._on_components_changed()

    def _new_file(self):
        """
        Clear all components from the list and start fresh.
        Prompts for confirmation if there are unsaved changes.
        """
        if self._dirty and self._components:
            if not messagebox.askyesno(
                "Clear all components?",
                "This will remove all components from the list.\n"
                "Any unsaved changes will be lost. Continue?"
            ):
                return

        self._file_title.set("")
        self._components       = []
        self._loaded_paths     = []
        self._filtered_indices = []
        self._selected_index   = None
        self._ctrl_responses   = {}
        self._dirty            = False
        if hasattr(self, "_comp_search_var"):
            self._comp_search_var.set("")
        if hasattr(self, "_comp_type_filter_var"):
            self._comp_type_filter_var.set("all")

        self._file_title_lbl.config(
            text="(enter component type and title below)",
            fg=self._colors["SUBTEXT"], font=("Helvetica", 10, "italic"),
        )
        self._refresh_list()
        self._show_form_placeholder()

        self._status_lbl.config(
            text="Cleared — ready for new components.", fg=self._colors["SUBTEXT"]
        )
        self._set_status("Component list cleared.")
        # Components were cleared — Capability Editor guard may now block editing
        self._on_components_changed()
