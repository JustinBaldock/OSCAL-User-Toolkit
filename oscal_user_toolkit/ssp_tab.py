"""
ssp_tab.py (Option 2) — SSPTab is a proper tk.Frame subclass.
It owns its widgets and state entirely; the app injects only
get_profile() and get_catalog() callbacks.
"""

import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .models import (empty_ssp, build_oscal_ssp, parse_ssp_file,
                     validate_ssp, new_uuid)


class SSPTab(tk.Frame):
    """
    Self-contained SSP editor panel.

    Callbacks injected by the app:
      get_profile()  — returns the currently loaded profile dict or None
      get_catalog()  — returns the currently loaded catalog dict or None
      set_status(msg) — updates the main window status bar
    """

    def __init__(self, parent, colors, get_profile, get_catalog, set_status):
        super().__init__(parent, bg=colors["BG"])
        self._colors      = colors
        self._get_profile = get_profile
        self._get_catalog = get_catalog
        self._set_status  = set_status
        self._ssp         = empty_ssp()
        self._ssp_vars    = {}

        self._build()
        self.refresh_profile_box()

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh_profile_box(self):
        """Called by the app whenever the profile is loaded or cleared."""
        C = self._colors
        p = self._get_profile()
        if p:
            label = p.get("title", "Unknown profile")
            if p.get("version") and p["version"] != "—":
                label += f"  (v{p['version']})"
            if p.get("oscal_version") and p["oscal_version"] != "—":
                label += f"  |  OSCAL {p['oscal_version']}"
            if p.get("ids"):
                label += f"  |  {len(p['ids'])} controls"
            if p.get("filepath"):
                label += f"  |  {Path(p['filepath']).name}"
            self._profile_lbl.config(text=label, fg=C["YELLOW"])
        else:
            self._profile_lbl.config(
                text="⚠  No profile loaded — open a profile before saving the SSP",
                fg=C["RED"])

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        C = self._colors
        self._build_toolbar()
        self._build_form_canvas()

    def _build_toolbar(self):
        C = self._colors
        tb = tk.Frame(self, bg=C["CARD_BG"], height=52)
        tb.pack(fill="x", side="top")
        tb.pack_propagate(False)

        tk.Button(tb, text="💾  Save SSP", command=self._save,
                  bg=C["GREEN"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#8cd39a", activeforeground=C["BG"],
                  ).pack(side="left", padx=12, pady=8)

        tk.Button(tb, text="📂  Open SSP", command=self._open,
                  bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  activebackground="#6a9fd8", activeforeground=C["BG"],
                  ).pack(side="left", padx=(0, 8), pady=8)

        tk.Button(tb, text="🆕  New SSP", command=self._new,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=12, pady=4, cursor="hand2",
                  ).pack(side="left", padx=(0, 8), pady=8)

        tk.Frame(tb, bg=C["HEADER_BG"], width=2).pack(
            side="left", fill="y", padx=8, pady=6)

        prof_box = tk.Frame(tb, bg=C["SIDEBAR_BG"],
                            highlightthickness=1, highlightbackground=C["HEADER_BG"])
        prof_box.pack(side="left", fill="y", pady=6, padx=(0, 8))
        tk.Label(prof_box, text="🔖 Profile:", bg=C["SIDEBAR_BG"], fg=C["SUBTEXT"],
                 font=("Helvetica", 9, "bold")).pack(side="left", padx=(10, 4))
        self._profile_lbl = tk.Label(prof_box, text="", bg=C["SIDEBAR_BG"],
                                     font=("Helvetica", 9))
        self._profile_lbl.pack(side="left", padx=(0, 10))

        self._status_lbl = tk.Label(
            tb, text="SSP not saved", bg=C["CARD_BG"], fg=C["SUBTEXT"],
            font=("Helvetica", 10, "italic"))
        self._status_lbl.pack(side="left", padx=16)

    def _build_form_canvas(self):
        C = self._colors
        canvas = tk.Canvas(self, bg=C["BG"], highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        form = tk.Frame(canvas, bg=C["BG"])
        win  = canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self._canvas = canvas
        self._build_form(form)

    def _on_mousewheel(self, e):
        # Only scroll this canvas when the SSP tab is active
        try:
            nb = self.master
            if hasattr(nb, "index") and nb.index("current") == 1:
                self._canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        except Exception:
            pass

    # ── Form sections ─────────────────────────────────────────────────────────

    def _build_form(self, parent):
        C = self._colors
        P = dict(padx=28)

        def section(title):
            hdr = tk.Frame(parent, bg=C["HEADER_BG"])
            hdr.pack(fill="x", **P, pady=(20, 4))
            tk.Label(hdr, text=title, bg=C["HEADER_BG"], fg=C["ACCENT"],
                     font=("Helvetica", 12, "bold"), anchor="w"
                     ).pack(side="left", padx=12, pady=6)

        def field(label, key, width=50, default=""):
            v = tk.StringVar(value=default)
            self._ssp_vars[key] = v
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            tk.Entry(row, textvariable=v, bg=C["CARD_BG"], fg=C["TEXT"],
                     insertbackground=C["TEXT"], relief="flat",
                     font=("Helvetica", 11), width=width,
                     highlightthickness=1, highlightbackground=C["HEADER_BG"],
                     ).pack(side="left", ipady=3)

        def textbox(label, height=4):
            tk.Label(parent, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11)).pack(anchor="w", **P, pady=(6, 2))
            frame = tk.Frame(parent, bg=C["HEADER_BG"],
                             highlightthickness=1, highlightbackground=C["HEADER_BG"])
            frame.pack(fill="x", **P, pady=3)
            t = tk.Text(frame, bg=C["CARD_BG"], fg=C["TEXT"],
                        insertbackground=C["TEXT"], relief="flat",
                        font=("Helvetica", 11), height=height,
                        wrap="word", padx=8, pady=6)
            t.pack(fill="both")
            return t

        def combo(label, key, values, default, width=30):
            v = tk.StringVar(value=default)
            self._ssp_vars[key] = v
            row = tk.Frame(parent, bg=C["BG"])
            row.pack(fill="x", **P, pady=3)
            tk.Label(row, text=label, bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            ttk.Combobox(row, textvariable=v, values=values,
                         state="readonly", width=width).pack(side="left")

        def list_section(title, hint, cols, col_widths, add_cmd, remove_cmd):
            section(title)
            tk.Label(parent, text=f"  {hint}", bg=C["BG"], fg=C["SUBTEXT"],
                     font=("Helvetica", 9, "italic")).pack(anchor="w", **P)
            frame = tk.Frame(parent, bg=C["CARD_BG"],
                             highlightthickness=1, highlightbackground=C["HEADER_BG"])
            frame.pack(fill="x", padx=28, pady=6)
            btn_row = tk.Frame(frame, bg=C["CARD_BG"])
            btn_row.pack(fill="x", padx=8, pady=6)
            tk.Button(btn_row, text="＋  Add", command=add_cmd,
                      bg=C["BLUE"], fg=C["BG"], font=("Helvetica", 10, "bold"),
                      relief="flat", padx=10, pady=3, cursor="hand2").pack(side="left")
            tree = ttk.Treeview(frame, columns=tuple(c[0] for c in cols),
                                show="headings", height=4, selectmode="browse")
            for col_id, heading, w, stretch in cols:
                tree.heading(col_id, text=heading, anchor="w")
                tree.column(col_id, width=w, anchor="w", stretch=stretch)
            tree.pack(fill="x", padx=8, pady=(0, 8))

            def make_remove(t, lk):
                def _remove():
                    sel = t.selection()
                    if sel:
                        idx = t.index(sel[0])
                        self._ssp[lk].pop(idx)
                        t.delete(sel[0])
                return _remove

            tk.Button(btn_row, text="✕  Remove Selected",
                      command=make_remove(tree, remove_cmd),
                      bg=C["HEADER_BG"], fg=C["SUBTEXT"], font=("Helvetica", 10),
                      relief="flat", padx=10, pady=3, cursor="hand2",
                      ).pack(side="left", padx=8)
            return tree

        # 1. Metadata
        section("1 ·  SSP Metadata")
        field("SSP Title *",     "title",           width=60)
        field("Version *",       "version",         width=20, default="1.0")
        field("Date Authorized", "date_authorized",  width=20)
        tk.Label(parent, text="  * Required.  Date format: YYYY-MM-DD",
                 bg=C["BG"], fg=C["SUBTEXT"], font=("Helvetica", 9, "italic")
                 ).pack(anchor="w", padx=28)

        # 2. System Characteristics
        section("2 ·  System Characteristics")
        field("System Name (Full) *", "system_name",       width=60)
        field("System Name (Short)",  "system_name_short", width=30)
        self._system_desc = textbox("System Description *", height=4)
        combo("Operational Status *", "status",
              ["operational", "under-development", "under-major-modification",
               "disposition", "other"], "under-development")
        combo("Security Sensitivity Level", "security_sensitivity_level",
              ["fips-199-low", "fips-199-moderate", "fips-199-high"],
              "fips-199-moderate")
        self._status_remarks = textbox("Status Remarks", height=2)

        # 3. Authorization Boundary
        section("3 ·  Authorization Boundary")
        self._auth_boundary = textbox("Boundary Description *", height=4)

        # 4. Network & Data Flow
        section("4 ·  Network Architecture & Data Flow  (optional)")
        self._network  = textbox("Network Architecture", height=3)
        self._dataflow = textbox("Data Flow", height=3)

        # 5. Information Types
        self._it_tree = list_section(
            "5 ·  Information Types",
            "At least one information type is required.",
            [("title",    "Information Type Title", 300, True),
             ("c_impact", "Confidentiality",        120, False),
             ("i_impact", "Integrity",              120, False),
             ("a_impact", "Availability",           120, False)],
            [300, 120, 120, 120],
            self._add_info_type,
            "information_types",
        )

        # 6. Roles
        self._role_tree = list_section(
            "6 ·  Roles", "Define roles responsible for the system.",
            [("role_id", "Role ID",    200, False),
             ("title",   "Role Title", 400, True)],
            [200, 400],
            self._add_role,
            "roles",
        )

        # 7. Parties
        self._party_tree = list_section(
            "7 ·  Parties  (People & Organisations)",
            "Parties are the people or organisations referenced by roles.",
            [("type",  "Type",  120, False),
             ("name",  "Name",  260, False),
             ("email", "Email", 260, True)],
            [120, 260, 260],
            self._add_party,
            "parties",
        )

        tk.Frame(parent, bg=C["BG"], height=40).pack()

    # ── Dialog ────────────────────────────────────────────────────────────────

    def _dialog(self, title, fields):
        C = self._colors
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
                     font=("Helvetica", 11), width=22, anchor="w").pack(side="left")
            v = tk.StringVar(value=default)
            vars_[key] = v
            if choices:
                ttk.Combobox(row, textvariable=v, values=choices,
                             state="readonly", width=28).pack(side="left")
            else:
                tk.Entry(row, textvariable=v, bg=C["CARD_BG"], fg=C["TEXT"],
                         insertbackground=C["TEXT"], relief="flat",
                         font=("Helvetica", 11), width=32,
                         highlightthickness=1,
                         highlightbackground=C["HEADER_BG"]).pack(side="left", ipady=3)
        result = {}
        def _ok():
            for k, v in vars_.items():
                result[k] = v.get().strip()
            dlg.destroy()
        btn = tk.Frame(dlg, bg=C["BG"])
        btn.pack(pady=12)
        tk.Button(btn, text="  OK  ", command=_ok,
                  bg=C["ACCENT"], fg=C["BG"], font=("Helvetica", 11, "bold"),
                  relief="flat", padx=10).pack(side="left", padx=8)
        tk.Button(btn, text="Cancel", command=dlg.destroy,
                  bg=C["HEADER_BG"], fg=C["TEXT"], font=("Helvetica", 11),
                  relief="flat", padx=10).pack(side="left")
        dlg.wait_window()
        return result if result else None

    # ── Add helpers ───────────────────────────────────────────────────────────

    def _add_info_type(self):
        impacts = ["fips-199-low", "fips-199-moderate", "fips-199-high"]
        res = self._dialog("Add Information Type", [
            ("Title *",         "title",       "",                  None),
            ("Description *",   "description", "",                  None),
            ("Confidentiality", "c_impact",    "fips-199-moderate", impacts),
            ("Integrity",       "i_impact",    "fips-199-moderate", impacts),
            ("Availability",    "a_impact",    "fips-199-moderate", impacts),
        ])
        if not res or not res.get("title"):
            return
        res["uuid"] = new_uuid()
        self._ssp["information_types"].append(res)
        self._it_tree.insert("", "end",
            values=(res["title"], res["c_impact"], res["i_impact"], res["a_impact"]))

    def _add_role(self):
        common = ["system-owner", "isso", "authorizing-official",
                  "system-poc-management", "system-poc-technical",
                  "system-poc-other", "privacy-officer", "security-operations"]
        res = self._dialog("Add Role", [
            ("Role ID *",    "role_id", "", common),
            ("Role Title *", "title",   "", None),
        ])
        if not res or not res.get("role_id"):
            return
        self._ssp["roles"].append(res)
        self._role_tree.insert("", "end", values=(res["role_id"], res["title"]))

    def _add_party(self):
        res = self._dialog("Add Party", [
            ("Type *", "type",  "person", ["person", "organization"]),
            ("Name *", "name",  "",       None),
            ("Email",  "email", "",       None),
        ])
        if not res or not res.get("name"):
            return
        res["uuid"] = new_uuid()
        self._ssp["parties"].append(res)
        self._party_tree.insert("", "end",
            values=(res["type"], res["name"], res.get("email", "")))

    # ── Collect / Populate / Reset ────────────────────────────────────────────

    def _collect(self):
        for key, var in self._ssp_vars.items():
            self._ssp[key] = var.get().strip()
        self._ssp["system_description"]        = self._system_desc.get("1.0", "end-1c").strip()
        self._ssp["status_remarks"]            = self._status_remarks.get("1.0", "end-1c").strip()
        self._ssp["auth_boundary_description"] = self._auth_boundary.get("1.0", "end-1c").strip()
        self._ssp["network_architecture"]      = self._network.get("1.0", "end-1c").strip()
        self._ssp["data_flow"]                 = self._dataflow.get("1.0", "end-1c").strip()

    def _populate(self):
        ssp = self._ssp
        defaults = {"version": "1.0", "status": "under-development",
                    "security_sensitivity_level": "fips-199-moderate"}
        for key, var in self._ssp_vars.items():
            var.set(ssp.get(key) or defaults.get(key, ""))
        for widget, key in [
            (self._system_desc,   "system_description"),
            (self._status_remarks, "status_remarks"),
            (self._auth_boundary, "auth_boundary_description"),
            (self._network,       "network_architecture"),
            (self._dataflow,      "data_flow"),
        ]:
            widget.delete("1.0", "end")
            val = ssp.get(key, "")
            if val:
                widget.insert("1.0", val)
        self._it_tree.delete(*self._it_tree.get_children())
        for it in ssp.get("information_types", []):
            self._it_tree.insert("", "end",
                values=(it["title"], it.get("c_impact","—"),
                        it.get("i_impact","—"), it.get("a_impact","—")))
        self._role_tree.delete(*self._role_tree.get_children())
        for r in ssp.get("roles", []):
            self._role_tree.insert("", "end", values=(r["role_id"], r["title"]))
        self._party_tree.delete(*self._party_tree.get_children())
        for p in ssp.get("parties", []):
            self._party_tree.insert("", "end",
                values=(p["type"], p["name"], p.get("email", "")))

    def _reset(self):
        self._ssp = empty_ssp()
        defaults = {"version": "1.0", "status": "under-development",
                    "security_sensitivity_level": "fips-199-moderate"}
        for key, var in self._ssp_vars.items():
            var.set(defaults.get(key, ""))
        for w in (self._system_desc, self._status_remarks,
                  self._auth_boundary, self._network, self._dataflow):
            w.delete("1.0", "end")
        for tree in (self._it_tree, self._role_tree, self._party_tree):
            tree.delete(*tree.get_children())

    # ── Save / Open / New ────────────────────────────────────────────────────

    def _save(self):
        self._collect()
        profile = self._get_profile()
        catalog = self._get_catalog()
        errors, warnings = validate_ssp(self._ssp, profile, catalog)
        if errors:
            messagebox.showerror("Cannot save SSP",
                                 "Please fix the following:\n\n" +
                                 "\n".join(f"• {e}" for e in errors))
            return
        if warnings:
            if not messagebox.askyesno("Save with warnings?",
                                       "\n".join(f"• {w}" for w in warnings) +
                                       "\n\nSave anyway?"):
                return
        path = filedialog.asksaveasfilename(
            title="Save OSCAL SSP", defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"ssp_{self._ssp.get('system_name_short') or 'draft'}.json")
        if not path:
            return
        doc = build_oscal_ssp(self._ssp, profile, catalog)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        self._status_lbl.config(text=f"Saved: {Path(path).name}", fg=self._colors["GREEN"])
        self._set_status(f"SSP saved: {Path(path).name}")
        messagebox.showinfo("SSP Saved", f"OSCAL SSP saved successfully:\n{path}")

    def _open(self):
        path = filedialog.askopenfilename(
            title="Open OSCAL SSP",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            messagebox.showerror("Failed to open SSP", str(exc))
            return
        if "system-security-plan" not in data:
            messagebox.showerror("Invalid file",
                                 "Missing 'system-security-plan' key — not an OSCAL SSP.")
            return
        current_title = self._ssp_vars.get("title", tk.StringVar()).get().strip()
        ssp, bm_info = parse_ssp_file(data)
        if current_title:
            if not messagebox.askyesno(
                    "Replace current SSP?",
                    f"Replace '{current_title}' with '{ssp['title'] or Path(path).name}'?"):
                return
        self._ssp = ssp
        self._populate()
        self._update_profile_box_from_bm(bm_info)
        self._status_lbl.config(text=f"Opened: {Path(path).name}",
                                fg=self._colors["BLUE"])
        self._set_status(f"SSP opened: {Path(path).name}")

    def _new(self):
        if messagebox.askyesno("New SSP", "Clear the current SSP and start a new one?"):
            self._reset()
            self._status_lbl.config(text="New SSP (unsaved)", fg=self._colors["SUBTEXT"])

    def _update_profile_box_from_bm(self, bm_info):
        C = self._colors
        if bm_info.get("title"):
            text = bm_info["title"]
            if bm_info.get("version"):
                text += f"  (v{bm_info['version']})"
            if bm_info.get("file"):
                text += f"  |  {bm_info['file']}"
            self._profile_lbl.config(text=text, fg=C["YELLOW"])
        elif bm_info.get("file"):
            self._profile_lbl.config(text=bm_info["file"], fg=C["YELLOW"])
        else:
            self._profile_lbl.config(text="No profile recorded in SSP", fg=C["SUBTEXT"])
