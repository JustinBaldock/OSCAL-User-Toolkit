"""
tab_utils.py — Small shared helpers for tab widgets.

Currently just is_tab_active(), used by every tab's mousewheel-scroll
guard (bind_all("<MouseWheel>") fires regardless of which tab is visible,
so each tab checks whether it's the active one before scrolling).

app.py groups several tabs under an outer Notebook tab that itself
contains an inner Notebook (Data / System Overview / Audit — see
_build_notebook()), so "is this tab visible" now means walking up through
however many levels of nested ttk.Notebook exist, not just checking one
immediate parent's selection.
"""


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
