"""
welcome_tab.py — static Welcome tab for the OSCAL User Toolkit.

This is the very first tab shown when the application starts. It has no
live state and reads nothing from the rest of the app — it is a plain,
scrollable reference page describing what each tab does and which tabs
require a catalog and/or profile to be loaded before they can be used.

Being static keeps this tab simple to maintain: there is no data to keep
in sync, no callbacks into other tabs. If the purpose or prerequisites of
a tab change, update the TAB_INFO list below to match.
"""

import tkinter as tk
from tkinter import ttk


# Each entry describes one tab in the Notebook, in the same left-to-right
# order they appear. "requires" is shown as a small badge so users know
# up front why a tab might look empty or locked.
TAB_INFO = [
    {
        "icon":     "📊",
        "name":     "Dashboard",
        "requires": None,
        "desc":     "Read-only summary of the currently open SSP, Assessment "
                    "Plan, Assessment Results, and POA&M documents — system "
                    "identity, assessment currency, compliance posture, and "
                    "risk status at a glance.",
    },
    {
        "icon":     "📋",
        "name":     "Catalog Viewer",
        "requires": "catalog",
        "desc":     "Browse every control in the loaded OSCAL catalog, with "
                    "profile filtering to show only the controls relevant to "
                    "your selected baseline.",
    },
    {
        "icon":     "⚙",
        "name":     "Component Editor",
        "requires": "catalog",
        "desc":     "Create OSCAL Component Definition files describing how "
                    "policies, software, hardware, and services implement "
                    "specific controls from the loaded catalog.",
    },
    {
        "icon":     "🔗",
        "name":     "Capability Editor",
        "requires": "catalog + components",
        "desc":     "Bundle related components (e.g. a policy, an operating "
                    "system, and a monitoring tool) into a named capability "
                    "that satisfies a group of controls together.",
    },
    {
        "icon":     "🛡",
        "name":     "SSP Editor",
        "requires": "catalog + profile",
        "desc":     "Build a System Security Plan: system characteristics, "
                    "information types, roles, components, control "
                    "implementations, system users, and inventory. Exports to "
                    "OSCAL JSON, Word, and draw.io diagrams.",
    },
    {
        "icon":     "📝",
        "name":     "Assessment Plan",
        "requires": "profile",
        "desc":     "Define the scope, objectives, methods, and schedule for "
                    "assessing a system's controls ahead of a formal "
                    "assessment.",
    },
    {
        "icon":     "🔍",
        "name":     "Assessment Results",
        "requires": None,
        "desc":     "Record observations, findings, and risks discovered "
                    "during an assessment. Findings can be pushed directly "
                    "into the POA&M Editor.",
    },
    {
        "icon":     "📋",
        "name":     "POA&M Editor",
        "requires": None,
        "desc":     "Track Plan of Action and Milestones items — "
                    "weaknesses, remediation plans, milestones, and status — "
                    "for risks that cannot be closed immediately.",
    },
]


class WelcomeTab(tk.Frame):
    """
    Static reference tab shown first, describing every other tab.

    Deliberately has no callbacks into the rest of the app — it only
    reads the TAB_INFO list above, so there is no live state to keep in
    sync with the rest of the application.
    """

    def __init__(self, parent, colors, **kwargs):
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors = colors
        self._build()

    # =========================================================================
    # BUILD
    # =========================================================================

    def _build(self):
        C = self._colors

        # ── Header ───────────────────────────────────────────────────────────
        header = tk.Frame(self, bg=C["HEADER_BG"])
        header.pack(fill="x", side="top")
        tk.Label(
            header, text="👋  Welcome to the OSCAL User Toolkit",
            bg=C["HEADER_BG"], fg=C["ACCENT"],
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(14, 2))
        tk.Label(
            header,
            text="A quick tour of each tab, and what you need loaded before using it.",
            bg=C["HEADER_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"),
        ).pack(anchor="w", padx=20, pady=(0, 14))

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
            text="Click '📂 Open Catalog' in the toolbar above to load an OSCAL "
                 "catalog first — most tabs are locked behind a gate panel until "
                 "one is loaded. Loading a '🔖 Profile' afterwards narrows the "
                 "control list to a specific baseline and is required by some tabs.",
            bg=C["CARD_BG"], fg=C["TEXT"], font=("Helvetica", 10),
            justify="left", wraplength=760,
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # ── One card per tab ─────────────────────────────────────────────────
        for info in TAB_INFO:
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
