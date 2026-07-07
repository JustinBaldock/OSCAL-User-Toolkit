"""
all_systems_tab.py — All Systems tab for the OSCAL User Toolkit.

Scans the configured Systems folder (settings.py — one subfolder per
system, each expected to hold a workspace manifest alongside that
system's SSP/AP/AR/POA&M) and shows an organisation-wide rollup: one row
per system plus aggregate totals, so a System Owner or auditor overseeing
several networks doesn't have to open each one individually to see how
the organisation as a whole is tracking. See user_stories.md US-13 and
oscal_user_toolkit_design_document.md §10.19 for the design behind this.

This tab is read-only and self-contained: it reads files directly from
disk on refresh(), independent of whatever the single-system editor tabs
currently have open (unlike dashboard_tab.py, which reads the live editor
tabs for the one currently-open system).
"""

import json
import tkinter as tk
from tkinter import ttk
from datetime import date, datetime

from .models import load_workspace_manifest, parse_ssp_file, parse_ar_file, parse_poam_file


class AllSystemsTab(tk.Frame):
    """Read-only organisation-wide rollup across every system in the Systems folder."""

    def __init__(self, parent, colors, get_systems_path=None, **kwargs):
        """
        Parameters:
            parent           - The ttk.Notebook this tab lives inside
            colors           - Shared colour dictionary from app.py
            get_systems_path - Callback: returns the configured Systems folder Path
        """
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors           = colors
        self._get_systems_path = get_systems_path or (lambda: None)
        self._build()

    def theme_refresh(self):
        """Rebuild this tab's widgets after the colour theme changes, then repopulate."""
        self.configure(bg=self._colors["BG"])
        for w in list(self.winfo_children()):
            w.destroy()
        self._build()

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _build(self):
        C = self._colors
        tk.Label(
            self, text="🌐  All Systems",
            bg=C["BG"], fg=C["ACCENT"],
            font=("Helvetica", 16, "bold"),
        ).pack(anchor="w", padx=20, pady=(20, 4))
        tk.Label(
            self,
            text="Organisation-wide rollup across every system in the Systems folder.",
            bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 11),
        ).pack(anchor="w", padx=20, pady=(0, 4))

        toolbar = tk.Frame(self, bg=C["BG"])
        toolbar.pack(fill="x", padx=20, pady=(4, 4))
        tk.Button(
            toolbar, text="🔄  Refresh", command=self.refresh,
            bg=C["BLUE_BG"], fg=C["BUTTON_TEXT"], font=("Helvetica", 10, "bold"),
            relief="flat", padx=10, pady=3, cursor="hand2",
        ).pack(side="left")
        self._systems_path_lbl = tk.Label(
            toolbar, text="", bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        )
        self._systems_path_lbl.pack(side="left", padx=(10, 0))
        self._refreshed_lbl = tk.Label(
            toolbar, text="", bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic"),
        )
        self._refreshed_lbl.pack(side="right")

        # Organisation-wide rollup row
        rollup = tk.Frame(self, bg=C["CARD_BG"], highlightthickness=1,
                           highlightbackground=C["HEADER_BG"])
        rollup.pack(fill="x", padx=20, pady=(0, 10))
        self._rollup_frame = rollup

        # Per-system table
        table_frame = tk.Frame(self, bg=C["CARD_BG"], highlightthickness=1,
                                highlightbackground=C["HEADER_BG"])
        table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        self._tree = ttk.Treeview(
            table_frame,
            columns=("system", "last_assessed", "compliance", "risks", "poam", "notes"),
            show="headings", selectmode="browse",
        )
        for col, heading, w, stretch in [
            ("system",        "System",         200, False),
            ("last_assessed", "Last Assessed",  120, False),
            ("compliance",    "Compliance",     100, False),
            ("risks",         "Open Risks",      90, False),
            ("poam",          "POA&M Overdue",  110, False),
            ("notes",         "Notes",          220, True),
        ]:
            self._tree.heading(col, text=heading, anchor="w")
            self._tree.column(col, width=w, anchor="w", stretch=stretch)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y", pady=8)
        self._tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)

        self.refresh()

    # =========================================================================
    # DATA
    # =========================================================================

    @staticmethod
    def _find_workspace_manifest(system_dir):
        """
        Return the path to the workspace manifest inside a system folder,
        or None if none is found. Looks at every top-level *.json file
        (not just ones named "workspace*.json") and checks for the
        top-level "workspace" key, since a system folder's own manifest
        filename isn't standardised (see workspace_ERN.json vs workspace.json
        in the bundled examples).
        """
        for path in sorted(system_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if "workspace" in data:
                return path
        return None

    def _summarize_system(self, system_dir):
        """
        Build one row's worth of data for a system folder. Never raises —
        any missing/unreadable file just leaves that part of the summary
        blank, since a system may not have every document yet (e.g.
        example-02/ in this repo has no SSP/AR/POA&M at all).
        """
        name = system_dir.name
        manifest_path = self._find_workspace_manifest(system_dir)
        if not manifest_path:
            return {
                "system": name, "last_assessed": "", "compliance": "",
                "risks": "", "poam": "", "notes": "No workspace manifest found",
            }

        try:
            ws = load_workspace_manifest(manifest_path)
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            return {
                "system": name, "last_assessed": "", "compliance": "",
                "risks": "", "poam": "", "notes": f"Could not read workspace: {exc}",
            }

        ssp_title = name
        if ws.get("ssp"):
            try:
                with open(ws["ssp"], encoding="utf-8") as f:
                    raw = json.load(f)
                ssp, _ = parse_ssp_file(raw)
                ssp_title = ssp.get("title") or name
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        last_assessed = ""
        ar_findings = []
        if ws.get("assessment_results"):
            try:
                with open(ws["assessment_results"], encoding="utf-8") as f:
                    raw = json.load(f)
                ar = parse_ar_file(raw)
                last_assessed = ar.get("result_end", "")
                ar_findings = ar.get("findings", [])
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        open_risks = 0
        poam_overdue = 0
        if ws.get("poam"):
            try:
                with open(ws["poam"], encoding="utf-8") as f:
                    raw = json.load(f)
                poam = parse_poam_file(raw)
                open_risks = sum(1 for r in poam.get("risks", []) if r.get("status", "open") == "open")
                today = date.today()
                for item in poam.get("poam_items", []):
                    sc = item.get("scheduled_completion", "").strip()
                    if sc:
                        try:
                            if date.fromisoformat(sc[:10]) < today:
                                poam_overdue += 1
                        except ValueError:
                            pass
            except (OSError, json.JSONDecodeError, KeyError):
                pass

        total = len(ar_findings)
        not_sat = sum(
            1 for f in ar_findings
            if (f.get("status_state") or f.get("target", {}).get("status", {}).get("state")) == "not-satisfied"
        )
        compliance = f"{round((total - not_sat) / total * 100)}%" if total else "—"

        notes = []
        if not ws.get("ssp"):
            notes.append("no SSP")
        if not ws.get("assessment_results"):
            notes.append("not yet assessed")
        if not ws.get("poam"):
            notes.append("no POA&M")

        return {
            "system":        ssp_title,
            "last_assessed": last_assessed or "—",
            "compliance":    compliance,
            "risks":         open_risks,
            "poam":          poam_overdue,
            "notes":         ", ".join(notes),
        }

    def refresh(self):
        """Rescan the Systems folder and repopulate the table + rollup."""
        C = self._colors
        systems_path = self._get_systems_path()
        self._systems_path_lbl.config(
            text=f"Systems folder: {systems_path}" if systems_path else "No Systems folder configured."
        )

        self._tree.delete(*self._tree.get_children())
        rows = []
        if systems_path and systems_path.is_dir():
            for system_dir in sorted(p for p in systems_path.iterdir() if p.is_dir()):
                rows.append(self._summarize_system(system_dir))

        for row in rows:
            self._tree.insert("", "end", values=(
                row["system"], row["last_assessed"], row["compliance"],
                row["risks"], row["poam"], row["notes"],
            ))

        # Rollup
        for w in self._rollup_frame.winfo_children():
            w.destroy()
        total_systems  = len(rows)
        total_risks    = sum(r["risks"] for r in rows if isinstance(r["risks"], int))
        total_overdue  = sum(r["poam"] for r in rows if isinstance(r["poam"], int))
        not_assessed   = sum(1 for r in rows if "not yet assessed" in r["notes"])

        for label, value, color in [
            ("Systems",           total_systems, C["TEXT"]),
            ("Total Open Risks",  total_risks,   C.get("RED", "#e06c6c") if total_risks else C["TEXT"]),
            ("POA&M Items Overdue", total_overdue, C.get("RED", "#e06c6c") if total_overdue else C["TEXT"]),
            ("Not Yet Assessed",  not_assessed,  C.get("YELLOW", "#e5c07b") if not_assessed else C["TEXT"]),
        ]:
            stat = tk.Frame(self._rollup_frame, bg=C["CARD_BG"])
            stat.pack(side="left", padx=20, pady=10)
            tk.Label(stat, text=str(value), bg=C["CARD_BG"], fg=color,
                     font=("Helvetica", 18, "bold")).pack(anchor="w")
            tk.Label(stat, text=label, bg=C["CARD_BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 9)).pack(anchor="w")

        self._refreshed_lbl.config(text=f"Last refreshed: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
