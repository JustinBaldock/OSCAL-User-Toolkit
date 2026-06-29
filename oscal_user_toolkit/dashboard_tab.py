"""
dashboard_tab.py — Authorization Dashboard tab for the OSCAL User Toolkit.

Reads across the currently open SSP, AP, AR, and POA&M documents and presents
a single-page summary for the Authorising Officer: system identity, assessment
currency, compliance posture, risk status, and POA&M health.

No data is written here — the tab is read-only and refreshes on demand.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date, datetime


class DashboardTab(tk.Frame):
    """Read-only authorization dashboard that aggregates all open documents."""

    def __init__(self, parent, colors,
                 get_ssp_tab=None,
                 get_ap_tab=None,
                 get_ar_tab=None,
                 get_poam_tab=None,
                 **kwargs):
        super().__init__(parent, bg=colors["BG"], **kwargs)
        self._colors       = colors
        self._get_ssp_tab  = get_ssp_tab  or (lambda: None)
        self._get_ap_tab   = get_ap_tab   or (lambda: None)
        self._get_ar_tab   = get_ar_tab   or (lambda: None)
        self._get_poam_tab = get_poam_tab or (lambda: None)

        self._build_toolbar()
        self._build_scroll_area()
        self._build_cards()

    # =========================================================================
    # LAYOUT
    # =========================================================================

    def _build_toolbar(self):
        C  = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        tk.Button(
            tb, text="🔄  Refresh Dashboard",
            command=self.refresh,
            bg=C["BLUE"], fg=C["BG"],
            font=("Helvetica", 11, "bold"),
            relief="flat", padx=14, pady=4, cursor="hand2",
            activebackground="#6a9fd8", activeforeground=C["BG"],
        ).pack(side="left", padx=12, pady=8)

        tk.Label(
            tb,
            text="Aggregates the currently open SSP, Assessment Plan, "
                 "Assessment Results, and POA&M documents.",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"),
        ).pack(side="left", padx=4)

        self._refreshed_lbl = tk.Label(
            tb, text="",
            bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 9, "italic"),
        )
        self._refreshed_lbl.pack(side="right", padx=16)

    def _build_scroll_area(self):
        C = self._colors
        container = tk.Frame(self, bg=C["BG"])
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=C["BG"], highlightthickness=0)
        sb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(canvas, bg=C["BG"])
        self._inner_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")

        def _on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(self._inner_id, width=event.width)

        self._inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", _on_configure)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        self._canvas = canvas

    def _build_cards(self):
        """Create all card frames (empty on first load, populated by refresh)."""
        C = self._colors
        pad = {"padx": 18, "pady": 8}

        def section_label(text):
            tk.Label(self._inner, text=text,
                     bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 10, "bold")).pack(
                anchor="w", padx=18, pady=(14, 2))

        def card(parent):
            f = tk.Frame(parent, bg=C["CARD_BG"],
                         highlightthickness=1,
                         highlightbackground=C["HEADER_BG"])
            return f

        # ── Row 1: System card (full width) ──────────────────────────────────
        section_label("SYSTEM")
        self._sys_card = card(self._inner)
        self._sys_card.pack(fill="x", **pad)

        # ── Row 2: Assessment | Compliance (side by side) ─────────────────────
        section_label("ASSESSMENT & COMPLIANCE")
        row2 = tk.Frame(self._inner, bg=C["BG"])
        row2.pack(fill="x", padx=18, pady=8)
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)

        self._assess_card = card(row2)
        self._assess_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._comply_card = card(row2)
        self._comply_card.grid(row=0, column=1, sticky="nsew")

        # ── Row 3: Risks | POA&M (side by side) ───────────────────────────────
        section_label("RISKS & POA&M")
        row3 = tk.Frame(self._inner, bg=C["BG"])
        row3.pack(fill="x", padx=18, pady=8)
        row3.columnconfigure(0, weight=1)
        row3.columnconfigure(1, weight=1)

        self._risk_card  = card(row3)
        self._risk_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self._poam_card  = card(row3)
        self._poam_card.grid(row=0, column=1, sticky="nsew")

        # ── Row 4: Observations summary ───────────────────────────────────────
        section_label("OBSERVATIONS")
        self._obs_card = card(self._inner)
        self._obs_card.pack(fill="x", **pad)

        tk.Frame(self._inner, bg=C["BG"], height=20).pack()

        self.refresh()

    # =========================================================================
    # REFRESH
    # =========================================================================

    def refresh(self):
        """Pull current data from all open tabs and repopulate every card."""
        ssp_tab  = self._get_ssp_tab()
        ap_tab   = self._get_ap_tab()
        ar_tab   = self._get_ar_tab()
        poam_tab = self._get_poam_tab()

        ssp  = getattr(ssp_tab,  "_ssp", {}) or {}
        ap   = getattr(ap_tab,   "_ap",  {}) or {}
        ar   = getattr(ar_tab,   "_ar",  {}) or {}

        poam_items   = getattr(poam_tab, "_poam_items",   []) or []
        poam_risks   = getattr(poam_tab, "_risks",        []) or []
        poam_finds   = getattr(poam_tab, "_findings",     []) or []
        poam_obs     = getattr(poam_tab, "_observations", []) or []

        ar_findings  = ar.get("findings",     [])
        ar_risks     = ar.get("risks",        [])
        ar_obs       = ar.get("observations", [])

        self._populate_system(ssp, ap, ar)
        self._populate_assessment(ap, ar)
        self._populate_compliance(ar_findings, poam_finds)
        self._populate_risks(ar_risks, poam_risks)
        self._populate_poam(poam_items)
        self._populate_observations(ar_obs, poam_obs)

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._refreshed_lbl.config(text=f"Last refreshed: {now}")

    # =========================================================================
    # CARD BUILDERS
    # =========================================================================

    def _clear(self, frame):
        for w in frame.winfo_children():
            w.destroy()

    def _heading(self, parent, text, color=None):
        C = self._colors
        tk.Label(parent, text=text,
                 bg=C["CARD_BG"], fg=color or C["TEXT"],
                 font=("Helvetica", 12, "bold"),
                 ).pack(anchor="w", padx=14, pady=(10, 4))

    def _row(self, parent, label, value, value_color=None):
        C = self._colors
        row = tk.Frame(parent, bg=C["CARD_BG"])
        row.pack(fill="x", padx=14, pady=2)
        tk.Label(row, text=label,
                 bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10), width=26, anchor="w",
                 ).pack(side="left")
        tk.Label(row, text=value or "—",
                 bg=C["CARD_BG"], fg=value_color or C["TEXT"],
                 font=("Helvetica", 10),
                 ).pack(side="left")

    def _divider(self, parent):
        C = self._colors
        tk.Frame(parent, bg=C["HEADER_BG"], height=1).pack(
            fill="x", padx=14, pady=6)

    def _stat_row(self, parent, label, count, color=None):
        """Bold count + label for key metrics."""
        C = self._colors
        row = tk.Frame(parent, bg=C["CARD_BG"])
        row.pack(fill="x", padx=14, pady=3)
        tk.Label(row, text=str(count),
                 bg=C["CARD_BG"], fg=color or C["TEXT"],
                 font=("Helvetica", 14, "bold"), width=5, anchor="e",
                 ).pack(side="left")
        tk.Label(row, text=f"  {label}",
                 bg=C["CARD_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 10),
                 ).pack(side="left")

    def _bottom_pad(self, parent):
        tk.Frame(parent, bg=self._colors["CARD_BG"], height=10).pack()

    # ── System card ───────────────────────────────────────────────────────────

    def _populate_system(self, ssp, ap, ar):
        C = self._colors
        self._clear(self._sys_card)
        self._heading(self._sys_card, "🏢  System Identity")

        title     = ssp.get("title", "")
        version   = ssp.get("version", "")
        system_id = ssp.get("system_id", "") or ssp.get("system_id_value", "")

        profile_title = ""
        profile_info  = ssp.get("import_href", "") or ssp.get("profile_title", "")
        if not profile_title and ssp.get("profile_resource_title"):
            profile_title = ssp["profile_resource_title"]

        self._row(self._sys_card, "System Name",     title or "No SSP loaded")
        self._row(self._sys_card, "System ID",        system_id)
        self._row(self._sys_card, "SSP Version",      version)
        self._row(self._sys_card, "Profile / Baseline", profile_info)
        self._row(self._sys_card, "AR Title",         ar.get("title", ""))
        self._row(self._sys_card, "AP Title",         ap.get("title", ""))
        self._bottom_pad(self._sys_card)

    # ── Assessment card ───────────────────────────────────────────────────────

    def _populate_assessment(self, ap, ar):
        C = self._colors
        self._clear(self._assess_card)
        self._heading(self._assess_card, "📋  Assessment Currency")

        start = ar.get("result_start", "")
        end   = ar.get("result_end",   "")

        days_since = ""
        days_color = C["TEXT"]
        if end:
            try:
                end_date   = date.fromisoformat(str(end)[:10])
                delta      = (date.today() - end_date).days
                days_since = f"{delta} days ago"
                if delta > 365:
                    days_color = C.get("RED", "#e06c6c")
                elif delta > 180:
                    days_color = C.get("YELLOW", "#e5c07b")
                else:
                    days_color = C.get("GREEN", "#98c379")
            except ValueError:
                pass

        self._row(self._assess_card, "Assessment Start",  str(start)[:10] if start else "")
        self._row(self._assess_card, "Assessment End",    str(end)[:10]   if end   else "")
        self._row(self._assess_card, "Time Since Assessment", days_since, days_color)

        ap_title   = ap.get("title", "")
        ap_version = ap.get("version", "")
        self._divider(self._assess_card)
        self._row(self._assess_card, "Assessment Plan",   ap_title)
        self._row(self._assess_card, "AP Version",        ap_version)
        self._bottom_pad(self._assess_card)

    # ── Compliance card ───────────────────────────────────────────────────────

    def _populate_compliance(self, ar_findings, poam_finds):
        C = self._colors
        self._clear(self._comply_card)
        self._heading(self._comply_card, "✅  Compliance Posture")

        all_findings = ar_findings or poam_finds
        total     = len(all_findings)
        satisfied = sum(1 for f in all_findings
                        if f.get("status_state") == "satisfied" or
                           (f.get("target", {}).get("status", {}).get("state") == "satisfied"))
        not_sat   = total - satisfied

        pct_ok  = f"{round(satisfied / total * 100)}%" if total else "—"
        pct_nok = f"{round(not_sat  / total * 100)}%" if total else "—"

        source_note = "source: AR" if ar_findings else ("source: POA&M" if poam_finds else "no data")

        self._stat_row(self._comply_card, f"total findings  ({source_note})", total)
        self._divider(self._comply_card)
        self._stat_row(self._comply_card,
                       f"satisfied  ({pct_ok})",
                       satisfied,
                       C.get("GREEN", "#98c379"))
        self._stat_row(self._comply_card,
                       f"not-satisfied  ({pct_nok})",
                       not_sat,
                       C.get("RED", "#e06c6c") if not_sat else C["TEXT"])

        if not_sat and all_findings:
            self._divider(self._comply_card)
            tk.Label(self._comply_card,
                     text="  Not-satisfied controls:",
                     bg=C["CARD_BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 9, "italic"),
                     ).pack(anchor="w", padx=14)
            for f in all_findings:
                state = (f.get("status_state") or
                         f.get("target", {}).get("status", {}).get("state", ""))
                if state == "not-satisfied":
                    tid = (f.get("target_id") or
                           f.get("target", {}).get("target-id", ""))
                    tk.Label(self._comply_card,
                             text=f"    • {tid}",
                             bg=C["CARD_BG"], fg=C.get("RED", "#e06c6c"),
                             font=("Helvetica", 9),
                             ).pack(anchor="w", padx=14)

        self._bottom_pad(self._comply_card)

    # ── Risks card ────────────────────────────────────────────────────────────

    def _populate_risks(self, ar_risks, poam_risks):
        C = self._colors
        self._clear(self._risk_card)
        self._heading(self._risk_card, "⚠  Risk Status")

        all_risks   = ar_risks or poam_risks
        source_note = "source: AR" if ar_risks else ("source: POA&M" if poam_risks else "no data")

        statuses = [
            ("open",                 C.get("RED",    "#e06c6c")),
            ("investigating",        C.get("YELLOW", "#e5c07b")),
            ("remediating",          C.get("YELLOW", "#e5c07b")),
            ("deviation-requested",  C.get("YELLOW", "#e5c07b")),
            ("deviation-approved",   C.get("YELLOW", "#e5c07b")),
            ("closed",               C.get("GREEN",  "#98c379")),
        ]

        counts = {}
        for r in all_risks:
            s = r.get("status", "open")
            counts[s] = counts.get(s, 0) + 1

        total = len(all_risks)
        self._stat_row(self._risk_card, f"total risks  ({source_note})", total)
        self._divider(self._risk_card)

        for status, color in statuses:
            n = counts.get(status, 0)
            self._stat_row(self._risk_card, status, n,
                           color if n > 0 else C["SUBTEXT"])

        self._bottom_pad(self._risk_card)

    # ── POA&M card ────────────────────────────────────────────────────────────

    def _populate_poam(self, items):
        C = self._colors
        self._clear(self._poam_card)
        self._heading(self._poam_card, "📋  POA&M Health")

        total    = len(items)
        overdue  = 0
        no_date  = 0
        today    = date.today()

        for item in items:
            sc = item.get("scheduled_completion", "").strip()
            if not sc:
                no_date += 1
            else:
                try:
                    if date.fromisoformat(sc[:10]) < today:
                        overdue += 1
                except ValueError:
                    pass

        on_track = total - overdue - no_date

        self._stat_row(self._poam_card, "total POA&M items", total)
        self._divider(self._poam_card)
        self._stat_row(self._poam_card, "on track",
                       on_track,
                       C.get("GREEN", "#98c379") if on_track else C["SUBTEXT"])
        self._stat_row(self._poam_card, "overdue",
                       overdue,
                       C.get("RED", "#e06c6c") if overdue else C["SUBTEXT"])
        self._stat_row(self._poam_card, "no completion date set",
                       no_date,
                       C.get("YELLOW", "#e5c07b") if no_date else C["SUBTEXT"])

        self._bottom_pad(self._poam_card)

    # ── Observations card ─────────────────────────────────────────────────────

    def _populate_observations(self, ar_obs, poam_obs):
        C = self._colors
        self._clear(self._obs_card)
        self._heading(self._obs_card, "🔍  Observations")

        all_obs     = ar_obs or poam_obs
        source_note = "source: AR" if ar_obs else ("source: POA&M" if poam_obs else "no data")
        total       = len(all_obs)

        method_counts = {}
        type_counts   = {}
        for o in all_obs:
            for m in o.get("methods", []):
                method_counts[m] = method_counts.get(m, 0) + 1
            for t in o.get("types", []):
                type_counts[t] = type_counts.get(t, 0) + 1

        cols_frame = tk.Frame(self._obs_card, bg=C["CARD_BG"])
        cols_frame.pack(fill="x", padx=14, pady=6)
        cols_frame.columnconfigure(0, weight=1)
        cols_frame.columnconfigure(1, weight=1)

        left  = tk.Frame(cols_frame, bg=C["CARD_BG"])
        right = tk.Frame(cols_frame, bg=C["CARD_BG"])
        left.grid(row=0, column=0, sticky="nw")
        right.grid(row=0, column=1, sticky="nw")

        def mini_row(parent, label, val):
            row = tk.Frame(parent, bg=C["CARD_BG"])
            row.pack(anchor="w", pady=1)
            tk.Label(row, text=str(val),
                     bg=C["CARD_BG"], fg=C["TEXT"],
                     font=("Helvetica", 11, "bold"), width=4, anchor="e",
                     ).pack(side="left")
            tk.Label(row, text=f"  {label}",
                     bg=C["CARD_BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 10),
                     ).pack(side="left")

        mini_row(left, f"total observations  ({source_note})", total)
        for method in ("EXAMINE", "INTERVIEW", "TEST", "UNKNOWN"):
            n = method_counts.get(method, 0)
            if n or method in ("EXAMINE", "INTERVIEW", "TEST"):
                mini_row(left, f"method: {method}", n)

        for t, n in sorted(type_counts.items(), key=lambda x: -x[1]):
            mini_row(right, f"type: {t}", n)

        self._bottom_pad(self._obs_card)
