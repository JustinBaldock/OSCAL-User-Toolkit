"""
data_sources_tab.py — Data Sources tab for the OSCAL User Toolkit.

Placeholder tab reserved for future multi-catalog / multi-profile
management (see the "Data Sources" idea discussed in todo.md, Feature 3
section 2b). Currently just a static "feature coming" notice — no data,
no callbacks into the rest of the app.
"""

import tkinter as tk


class DataSourcesTab(tk.Frame):
    """Static placeholder tab — real functionality not yet implemented."""

    def __init__(self, parent, colors, **kwargs):
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors = colors
        self._build()

    def theme_refresh(self):
        """Rebuild this tab's widgets after the colour theme changes."""
        self.configure(bg=self._colors["BG"])
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()

    def _build(self):
        C = self._colors
        tk.Label(
            self, text="📚  Data Sources",
            bg=C["BG"], fg=C["ACCENT"],
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            self,
            text="Feature coming soon — manage multiple loaded catalogs and\n"
                 "profiles from a single place, instead of the current one\n"
                 "catalog / one profile toolbar slot.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 11),
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 20))
