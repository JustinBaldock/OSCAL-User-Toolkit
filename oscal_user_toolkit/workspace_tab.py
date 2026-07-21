"""
workspace_tab.py — Workspace tab for the OSCAL User Toolkit.

This is the very first tab shown when the application starts. It has two
jobs:

1. A reference page describing what each other tab does and which tabs
   require a catalog and/or profile to be loaded before they can be used
   (unchanged from the original Welcome tab this replaces).

2. Open Workspace / Save Workspace buttons. A "workspace" is a small JSON
   manifest file (see build_workspace_manifest()/apply_workspace_manifest()
   in models.py) that records which catalog, profile, SSP, components,
   capabilities, Assessment Plan, Assessment Results, and POA&M files
   belong together for one system — so a system owner or auditor can load
   everything for that system in one action instead of opening each file
   individually across six tabs.

The actual reading/writing of files happens in app.py (via the
open_workspace/save_workspace callbacks) because only the main app has
direct references to every other tab. This tab just provides the buttons
and the manifest-relative-path resolution helper used by both callbacks.
"""

import tkinter as tk
from tkinter import ttk


# Each entry describes one tab, grouped the same way the Notebook groups
# them (see app.py._build_notebook() — Data / System Overview / Audit are
# each a group of sub-tabs; Dashboard and All Systems stay top-level).
# "group" is None for a top-level tab, or the group's name to render a
# section heading before it. "requires" is shown as a small badge so users
# know up front why a tab might look empty or locked — reflects an actual
# hard gate (each tab's _ready()/_build_gate_panel()), not just "useful to
# have loaded", so tabs that only use a profile for an optional convenience
# button (e.g. Assessment Plan's "Load IDs from profile") show no badge.
TAB_INFO = [
    {
        "icon":     "📚",
        "name":     "Data Sources",
        "group":    "Data",
        "requires": None,
        "desc":     "Browse and load catalogs/profiles from the configured "
                    "Library folder, or browse elsewhere for anything "
                    "outside it. This is the only place to open or clear "
                    "the active catalog/profile.",
    },
    {
        "icon":     "📋",
        "name":     "Catalog Viewer",
        "group":    "Data",
        "requires": "catalog",
        "desc":     "Browse every control in the loaded OSCAL catalog, with "
                    "profile filtering to show only the controls relevant to "
                    "your selected baseline.",
    },
    {
        "icon":     "⚙",
        "name":     "Component Editor",
        "group":    "System Overview",
        "requires": "catalog",
        "desc":     "Create OSCAL Component Definition files describing how "
                    "policies, software, hardware, and services implement "
                    "specific controls from the loaded catalog. "
                    "'📚 Import from Library' pulls in a shared component "
                    "as an editable copy for the current system.",
    },
    {
        "icon":     "🔗",
        "name":     "Capability Editor",
        "group":    "System Overview",
        "requires": "catalog + components",
        "desc":     "Bundle related components (e.g. a policy, an operating "
                    "system, and a monitoring tool) into a named capability "
                    "that satisfies a group of controls together. Also has "
                    "'📚 Import from Library'.",
    },
    {
        "icon":     "🛡",
        "name":     "SSP Editor",
        "group":    "System Overview",
        "requires": "catalog + profile",
        "desc":     "Build a System Security Plan: system characteristics, "
                    "authorisation boundary, network architecture (including "
                    "VLANs), data flow (including Data Flow Links), "
                    "information types, roles, components, control "
                    "implementations, system users, and inventory. "
                    "'🔄 Sync from System Folder' pulls in everything "
                    "imported for this system. Exports to OSCAL JSON, Word, "
                    "and draw.io diagrams.",
    },
    {
        "icon":     "📝",
        "name":     "Assessment Plan",
        "group":    "Audit",
        "requires": None,
        "desc":     "Define the scope, objectives, methods, and schedule for "
                    "assessing a system's controls ahead of a formal "
                    "assessment. Shows the referenced SSP's components and "
                    "capabilities read-only; can optionally load control IDs "
                    "from a loaded profile.",
    },
    {
        "icon":     "🔍",
        "name":     "Assessment Results",
        "group":    "Audit",
        "requires": None,
        "desc":     "Record observations, findings, and risks discovered "
                    "during an assessment. Findings can be pushed directly "
                    "into the POA&M Editor.",
    },
    {
        "icon":     "📋",
        "name":     "POA&M Editor",
        "group":    "Audit",
        "requires": None,
        "desc":     "Track Plan of Action and Milestones items — "
                    "weaknesses, remediation plans, milestones, and status — "
                    "for risks that cannot be closed immediately. Shows the "
                    "referenced SSP's components and capabilities read-only.",
    },
    {
        "icon":     "📊",
        "name":     "Dashboard",
        "group":    None,
        "requires": None,
        "desc":     "Read-only summary of the currently open SSP, Assessment "
                    "Plan, Assessment Results, and POA&M documents — system "
                    "identity, assessment currency, compliance posture, and "
                    "risk status at a glance, for the one system currently "
                    "open in the editor tabs.",
    },
    {
        "icon":     "🌐",
        "name":     "All Systems",
        "group":    None,
        "requires": None,
        "desc":     "Organisation-wide rollup across every system in the "
                    "configured Systems folder — one row per system "
                    "(compliance, open risks, POA&M health) plus aggregate "
                    "totals, read directly from disk rather than the live "
                    "editor tabs.",
    },
]


class WorkspaceTab(tk.Frame):
    """
    First tab shown on startup: Open/Save Workspace buttons plus a static
    reference describing every other tab.

    The Open/Save Workspace buttons delegate to callbacks supplied by the
    main app (open_workspace, save_workspace) — this tab has no direct
    references to the other tabs, so it stays decoupled the same way every
    other tab in this app is decoupled from its siblings.
    """

    def __init__(self, parent, colors, open_workspace=None, save_workspace=None,
                 new_workspace=None, get_theme=None, set_theme=None, **kwargs):
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors         = colors
        self._open_workspace = open_workspace or (lambda: None)
        self._save_workspace = save_workspace or (lambda: None)
        self._new_workspace  = new_workspace or (lambda: None)
        # Theme toggle callbacks — get_theme() returns "dark"/"light",
        # set_theme(name) asks the main app to switch the whole application's
        # colour palette. Both are owned by OSCALApp (see app.py's
        # set_theme()) since only it has references to every tab at once.
        self._get_theme = get_theme or (lambda: "dark")
        self._set_theme = set_theme or (lambda name: None)
        self._build()

    def theme_refresh(self):
        """
        Rebuild this tab's widgets after the colour theme changes.

        This tab has no document data of its own to preserve — it's purely
        static reference content plus the two Open/Save Workspace buttons —
        so a full destroy-and-rebuild is all that's needed.
        """
        self.configure(bg=self._colors["BG"])   # This tab's own Frame background
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        C = self._colors

        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=C["HEADER_BG"])
        header.pack(fill="x", side="top")

        title_row = tk.Frame(header, bg=C["HEADER_BG"])
        title_row.pack(fill="x", padx=20, pady=(14, 2))
        tk.Label(
            title_row, text="🗂  Workspace",
            bg=C["HEADER_BG"], fg=C["ACCENT"],
            font=("Helvetica", 16, "bold"),
        ).pack(side="left")

        # ── Dark/Light theme toggle ──────────────────────────────────────────
        # A single button that alternates label and action based on the
        # CURRENT theme (read via get_theme()) — the same toggle-button
        # pattern used elsewhere in this app (e.g. the Component Editor's
        # sort-order toggle) rather than a custom slider widget.
        current = self._get_theme()
        toggle_text = "☀️  Switch to Light Mode" if current == "dark" else "🌙  Switch to Dark Mode"
        tk.Button(
            title_row, text=toggle_text,
            command=lambda: self._set_theme("light" if current == "dark" else "dark"),
            bg=C["ACCENT_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="right")

        tk.Label(
            header,
            text="A quick tour of each tab, and what you need loaded before using it.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        ).pack(anchor="w", padx=20, pady=(0, 6))

        # ── Open/Save Workspace buttons ──────────────────────────────────────
        # A workspace is a small JSON manifest recording which catalog,
        # profile, SSP, components, capabilities, AP, AR, and POA&M files
        # belong together for one system, so they can all be loaded in one
        # action. See build_workspace_manifest()/apply_workspace_manifest()
        # in models.py for the manifest format.
        btn_row = tk.Frame(header, bg=C["HEADER_BG"])
        btn_row.pack(anchor="w", padx=20, pady=(0, 14))
        tk.Button(
            btn_row, text="📂  Open Workspace", command=lambda: self._open_workspace(),
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left")
        tk.Button(
            btn_row, text="💾  Save Workspace", command=lambda: self._save_workspace(),
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        tk.Button(
            btn_row, text="🆕  Create New Workspace", command=lambda: self._new_workspace(),
            bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=12, pady=4, cursor="hand2",
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            btn_row,
            text="  A workspace remembers every file for one system — catalog, "
                 "profile, SSP, components, capabilities, AP, AR, and POA&M.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=(10, 0))

        # ── Scrollable body ──────────────────────────────────────────────────
        outer = tk.Frame(self, bg=C["BG"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=C["BG"], highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas, bg=C["BG"])
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_body_configure(_event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            # Keep the inner frame's width matched to the canvas so labels
            # can word-wrap correctly instead of growing off to the right.
            canvas.itemconfigure(body_id, width=event.width)

        body.bind("<Configure>", _on_body_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling while hovering over the tab
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # ── "Getting started" hint card ─────────────────────────────────────
        hint_card = tk.Frame(
            body, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        hint_card.pack(fill="x", padx=20, pady=(16, 12))
        tk.Label(
            hint_card, text="Getting started",
            bg=C["CARD_BG"], fg=C["BLUE"], font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=12, pady=(10, 2))
        tk.Label(
            hint_card,
            text="Open the '📚 Data Sources' tab and load an OSCAL catalog first — "
                 "most editor tabs are locked behind a gate panel until one is "
                 "loaded. Loading a profile afterwards narrows the control list to "
                 "a specific baseline and is required by the SSP Editor.\n\n"
                 "Shared components/capabilities/catalogs/profiles live in a "
                 "'📚 Library' folder (toolbar button above) — import a copy into "
                 "the current system from the Component/Capability Editor, then use "
                 "the SSP Editor's '🔄 Sync from System Folder' to pull them into "
                 "the SSP. A '🗂 Systems' folder (also a toolbar button) holds one "
                 "subfolder per system, which the '🌐 All Systems' tab rolls up into "
                 "an organisation-wide summary.\n\n"
                 "If someone has already saved a workspace file for this system, use "
                 "'📂 Open Workspace' above instead — it loads the catalog, profile, "
                 "SSP, components, capabilities, Assessment Plan, Assessment Results, "
                 "and POA&M all in one step. Use '💾 Save Workspace' once you have "
                 "everything loaded to create that file for next time.",
            bg=C["CARD_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            justify="left", wraplength=760,
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # ── One card per tab, with a heading whenever the group changes ──────
        current_group = "__unset__"
        for info in TAB_INFO:
            if info["group"] != current_group:
                current_group = info["group"]
                if current_group:
                    tk.Label(
                        body, text=current_group,
                        bg=C["BG"], fg=C["ACCENT"], font=("Helvetica", 12, "bold"),
                    ).pack(anchor="w", padx=20, pady=(14, 0))
            self._build_tab_card(body, info)

        # Bottom spacer so the last card isn't flush against the edge
        tk.Frame(body, bg=C["BG"], height=12).pack(fill="x")

    def _build_tab_card(self, parent, info):
        C = self._colors
        card = tk.Frame(
            parent, bg=C["CARD_BG"],
            highlightthickness=1, highlightbackground=C["HEADER_BG"],
        )
        card.pack(fill="x", padx=20, pady=6)

        top_row = tk.Frame(card, bg=C["CARD_BG"])
        top_row.pack(fill="x", padx=12, pady=(10, 2))

        tk.Label(
            top_row, text=f"{info['icon']}  {info['name']}",
            bg=C["CARD_BG"], fg=C["ACCENT"], font=("Helvetica", 12, "bold"),
        ).pack(side="left")

        if info["requires"]:
            tk.Label(
                top_row, text=f"requires: {info['requires']}",
                bg=C["HEADER_BG"], fg=C["YELLOW"], font=("Helvetica", 9, "bold"),
                padx=8, pady=2,
            ).pack(side="right")
        else:
            tk.Label(
                top_row, text="no prerequisites",
                bg=C["HEADER_BG"], fg=C["GREEN"], font=("Helvetica", 9, "bold"),
                padx=8, pady=2,
            ).pack(side="right")

        tk.Label(
            card, text=info["desc"],
            bg=C["CARD_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
            justify="left", wraplength=760,
        ).pack(anchor="w", padx=12, pady=(2, 10))
