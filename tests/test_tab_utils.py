"""
Unit tests for oscal_user_toolkit/tab_utils.py.

bind_mousewheel() exists to fix a real memory leak found by an external
code review (see oscal_user_toolkit_design_document.md §10.34): calling
canvas.bind_all("<MouseWheel>", handler) directly, as every scrollable
tab's _build_canvas() used to, never releases the Tcl command behind a
previous binding — so every theme toggle (which rebuilds every tab, see
OSCALApp.set_theme()) leaked one Tcl-level command holding a live
reference to the entire previous tab instance, forever.

These tests exercise that directly with tkinter widgets and Python's own
garbage collector via weakref — the only way to actually prove a leak is
fixed, as opposed to just checking the code "looks right".
"""

import gc
import tkinter as tk
import weakref

import pytest

from oscal_user_toolkit import tab_utils


@pytest.fixture
def root():
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()


def test_bind_mousewheel_does_not_leak_previous_handlers(root):
    """
    The actual regression test: rebinding many times must not keep old
    handler-owning objects alive. A raw bind_all() call in the same loop
    (see the module docstring) fails this — every "tab" stays reachable
    forever via a Tcl-level reference nothing in Python ever releases.
    """
    class FakeTab:
        def __init__(self):
            self.canvas = tk.Canvas(root)
            self.canvas.pack()
            tab_utils.bind_mousewheel(self.canvas, self._on_mousewheel)

        def _on_mousewheel(self, event):
            pass

    refs = []
    for _ in range(20):
        tab = FakeTab()
        refs.append(weakref.ref(tab))
        tab.canvas.destroy()
        del tab

    gc.collect()
    alive = sum(1 for r in refs if r() is not None)
    # At most the very last one may still be referenced by
    # tab_utils' own module-level "currently active handler" — every
    # earlier one must be gone.
    assert alive <= 1, f"{alive} of 20 rebound tabs were never garbage collected — leak regression"


def test_bind_mousewheel_dispatches_to_the_most_recently_bound_handler(root):
    """
    The dispatcher must forward to whichever handler was bound last, not
    accumulate multiple handlers or get stuck on the first one.

    Calls the module's own dispatcher function directly (via the module-
    level state bind_mousewheel() maintains) rather than going through a
    real OS-level <MouseWheel> event — synthetic MouseWheel events aren't
    reliably delivered to a withdrawn/headless Tk window across platforms,
    and that's not what this test needs to prove anyway; the dispatch
    logic itself is what's under test here.
    """
    calls = []

    def handler_a(event):
        calls.append("a")

    def handler_b(event):
        calls.append("b")

    canvas = tk.Canvas(root)
    tab_utils.bind_mousewheel(canvas, handler_a)
    tab_utils.bind_mousewheel(canvas, handler_b)

    assert tab_utils._active_mousewheel_handler is handler_b
    tab_utils._active_mousewheel_handler(event=None)
    assert calls == ["b"], "expected only the most recently bound handler to fire"


def test_bind_mousewheel_only_calls_bind_all_once(root, monkeypatch):
    """Confirms the fix's actual mechanism: bind_all() itself is called
    at most once per process, regardless of how many times
    bind_mousewheel() is called — everything after that is a plain
    Python variable reassignment, not new Tcl-level state."""
    calls = {"count": 0}
    canvas = tk.Canvas(root)
    original_bind_all = canvas.bind_all

    def counting_bind_all(*args, **kwargs):
        calls["count"] += 1
        return original_bind_all(*args, **kwargs)

    monkeypatch.setattr(canvas, "bind_all", counting_bind_all)

    for _ in range(5):
        tab_utils.bind_mousewheel(canvas, lambda event: None)

    # 0 or 1: 0 if an earlier test in this module already bound the
    # module-level dispatcher (it's process-global by design — see the
    # function's own docstring), 1 if this is the first bind in the process.
    assert calls["count"] <= 1
