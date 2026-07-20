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
