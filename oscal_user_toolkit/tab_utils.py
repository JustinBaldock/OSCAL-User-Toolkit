"""
tab_utils.py — Small shared helpers for tab widgets.

is_tab_active() is used by every tab's mousewheel-scroll guard
(bind_all("<MouseWheel>") fires regardless of which tab is visible, so
each tab checks whether it's the active one before scrolling).

app.py groups several tabs under an outer Notebook tab that itself
contains an inner Notebook (Data / System Overview / Audit — see
_build_notebook()), so "is this tab visible" now means walking up through
however many levels of nested ttk.Notebook exist, not just checking one
immediate parent's selection.

Tooltip is a small hover-label helper — see usability_review.md §2/§6/§10
(recognition rather than recall): icon-only toolbar buttons like "📥" or
"🔄" don't self-explain, so attach_tooltip() lets a widget name what it
does without needing a permanently-visible label next to every icon.
"""

import tkinter as tk


def attach_tooltip(widget, text, colors=None, delay_ms=500):
    """
    Show `text` in a small popup near `widget` after the mouse hovers over
    it for `delay_ms`, and hide it on mouse-out or click.

    Parameters:
        widget   - Any tkinter/ttk widget (Button, Label, Entry, ...).
        text     - The tooltip text to show.
        colors   - Optional theme colors dict (see app.py's DARK_COLORS/
                   LIGHT_COLORS). If omitted, uses a plain black-on-pale-
                   yellow tooltip regardless of the app's current theme.
        delay_ms - Hover delay before the tooltip appears (default 500ms —
                   long enough that moving the mouse across the toolbar
                   doesn't flash a tooltip on every button it passes over).

    Usage:
        attach_tooltip(save_btn, "Save this component to the Library", COLORS)
    """
    state = {"after_id": None, "popup": None}

    def show():
        if state["popup"] is not None:
            return
        x = widget.winfo_rootx() + widget.winfo_width() // 2
        y = widget.winfo_rooty() + widget.winfo_height() + 4
        popup = tk.Toplevel(widget)
        popup.wm_overrideredirect(True)   # No title bar/border
        popup.wm_geometry(f"+{x}+{y}")
        bg = colors["HEADER_BG"] if colors else "#ffffe0"
        fg = colors["TEXT"]      if colors else "#000000"
        tk.Label(
            popup, text=text, bg=bg, fg=fg, font=("Helvetica", 9),
            padx=8, pady=4, relief="solid", borderwidth=1,
        ).pack()
        state["popup"] = popup

    def hide(_event=None):
        if state["after_id"] is not None:
            widget.after_cancel(state["after_id"])
            state["after_id"] = None
        if state["popup"] is not None:
            state["popup"].destroy()
            state["popup"] = None

    def schedule(_event=None):
        hide()
        state["after_id"] = widget.after(delay_ms, show)

    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hide, add="+")
    widget.bind("<ButtonPress>", hide, add="+")


def make_collapsible(parent, title, colors, start_expanded=True):
    """
    Build a collapsible section: a clickable header bar (▼/▶ + title) and
    a body frame that's shown/hidden by clicking it.

    Addresses usability_review.md #2/#8: sections with no visual cue that
    they're collapsible, and — for the metadata cards this was built for —
    reducing how much vertical space document-metadata fields (version,
    UUIDs, revision history, creator, links) take up by default, since
    they're consulted far less often than the fields below them.

    Parameters:
        parent         - Widget to pack this section into.
        title          - Header text, shown after the ▼/▶ arrow.
        colors         - The app's colour dict (COLORS/DARK_COLORS/etc.).
        start_expanded - Whether the body starts visible (default True,
                          so existing behaviour/layout doesn't change for
                          anyone who hasn't collapsed anything yet).

    Returns:
        The body Frame — pack whatever content belongs in this section
        into it, exactly as if it were `parent`.

    Usage:
        body = make_collapsible(parent, "Document Metadata", C)
        tk.Label(body, text="...").pack(...)
    """
    state = {"expanded": start_expanded}

    section = tk.Frame(parent, bg=colors["CARD_BG"], highlightthickness=1,
                        highlightbackground=colors["HEADER_BG"])
    section.pack(fill="x", padx=20, pady=(10, 4))

    header = tk.Frame(section, bg=colors["HEADER_BG"], cursor="hand2")
    header.pack(fill="x")
    arrow_lbl = tk.Label(
        header, text="▼" if start_expanded else "▶",
        bg=colors["HEADER_BG"], fg=colors["ACCENT"], font=("Helvetica", 10, "bold"),
    )
    arrow_lbl.pack(side="left", padx=(10, 4), pady=4)
    tk.Label(
        header, text=title, bg=colors["HEADER_BG"], fg=colors["ACCENT"],
        font=("Helvetica", 10, "bold"),
    ).pack(side="left", pady=4)

    body = tk.Frame(section, bg=colors["CARD_BG"])
    if start_expanded:
        body.pack(fill="x")

    def toggle(_event=None):
        state["expanded"] = not state["expanded"]
        if state["expanded"]:
            body.pack(fill="x")
            arrow_lbl.config(text="▼")
        else:
            body.pack_forget()
            arrow_lbl.config(text="▶")

    header.bind("<Button-1>", toggle)
    for child in header.winfo_children():
        child.bind("<Button-1>", toggle)

    return body


def is_tab_active(widget):
    """
    Return True if `widget` is currently visible: it is the selected tab
    of its immediate parent Notebook, that parent is itself the selected
    tab of ITS parent Notebook, and so on up to the window.

    Works for any nesting depth (including zero — a tab with no Notebook
    ancestor at all is trivially "active"), unlike checking only the
    immediate parent's .select(), which is resilient to tab reordering
    but not to nesting.
    """
    current = widget
    parent = widget.master
    while parent is not None:
        if hasattr(parent, "select") and parent.select() != str(current):
            return False
        current = parent
        parent = getattr(parent, "master", None)
    return True
