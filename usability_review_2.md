# OSCAL User Toolkit — Usability Review (Second Pass)

## Overview

A second pass against Jakob Nielsen's 10 usability heuristics, done after every finding in [usability_review.md](usability_review.md) was addressed or explicitly deferred. This is not a re-statement of that document — every item below was checked directly against the current code, with a specific focus on what's been built *since* that review (the Document Metadata collapsible card, tooltips, the Upgrade OSCAL Version dialog, the New Workspace button), since new code is exactly where new gaps hide. Findings are evidence-based (file/line references, not impressions) and ranked by how much they actually matter, not by heuristic number.

Anything from the first review still open (undo/redo, batch/multi-select, an in-app tutorial, the marginal light-mode `GREEN`/`TEAL` contrast) was re-verified as still open and is not repeated here in detail — see that document.

---

## 🔴 High-priority finding

### The "Upgrade OSCAL Version" button can silently skip the validation it promises

**Heuristic #1 (Visibility of system status) / #9 (honest error recovery).**

`component_tab.py:2166` and `capability_tab.py:2255` both guard the entire validation step with `if zip_path:` — and `zip_path` comes from `self._get_oscal_version_paths().get(target_version)`, which returns `None` if that version's schema zip isn't found. When that happens, the code falls straight through to committing the upgrade (`comp["doc_oscal_version"] = target_version`) **with no indication to the user that validation never actually ran.** The button's own tooltip and in-dialog copy both explicitly promise "re-validates... before re-labelling" — this is the one path where that promise is silently broken.

In practice this needs a genuinely missing/renamed schema zip to trigger, which is rare — but it's exactly the kind of silent-failure-instead-of-a-message this session's error-logging work (`_setup_error_logging()`) was built to eliminate elsewhere. Fix is small: if `zip_path` is falsy, show a `messagebox.showwarning` ("Could not find the OSCAL {version} schema — proceeding without validation") before committing, rather than proceeding silently.

---

## 🟡 Real, smaller gaps

### 1. The collapsible Document Metadata card hides status when collapsed, with no summary

**Heuristic #1 / #8.** `tab_utils.make_collapsible()` (added to fix the *previous* review's "no collapsible cues" finding) shows only a static title in its header — collapsing it gives no hint of what's inside. Concretely: if a component's OSCAL version doesn't match the rest of the Library (like the CivicActions examples), and a user has collapsed this card (intentionally, or because someone else collapsed it earlier in the session — the collapse state is shared UI chrome, not per-component), that mismatch is now invisible until they think to expand it. A card built specifically to *surface* a mismatch can now hide it. Worth a small follow-up: show a one-line summary in the collapsed header (e.g. "v1.0.0 · CivicActions · 1 link") rather than just the bare title.

### 2. "Create New Workspace" has no tooltip, despite being the clearest case for one

**Heuristic #2 / #10.** `workspace_tab.py` has zero `attach_tooltip()` calls — none of its three buttons (Open/Save/**New** Workspace) have one. This is the exact pattern the tooltip work under the *first* review targeted (buttons whose label doesn't reveal a real consequence) — "Create New Workspace" clears every open document plus the catalog/profile, which is not obvious from the label alone, and is currently only explained in the confirmation dialog *after* the button is already clicked.

### 3. No dialog in the entire app supports Enter-to-confirm or Escape-to-cancel

**Heuristic #3 / #7.** Checked directly: zero `<Return>` or `<Escape>` bindings exist anywhere in the codebase. Every modal dialog — Add Component, Add Link, Save New Version, Upgrade OSCAL Version, Add Member, the New Workspace confirmation, all of them — requires a mouse click to proceed or cancel, with no keyboard path through. This is a bigger, cross-cutting gap than the Ctrl+S/Ctrl+O work covered (that was app-level shortcuts; this is entirely absent *inside* every dialog), and would be a meaningful, self-contained follow-up: bind `<Return>` to whichever button is the dialog's primary action and `<Escape>` to Cancel, ideally via one shared helper in `_make_dialog()` rather than dialog-by-dialog.

### 4. The Upgrade dialog's version list doesn't distinguish "current" from "latest"

**Heuristic #6 (Recognition over recall).** The target-version `Combobox` (`component_tab.py:2133`) lists every bundled version as a bare string ("1.0.0", "1.1.2", "1.2.2") with no marker for which one the app currently defaults new saves to, or which is the newest available. A user has to already know or go check the toolbar dropdown. Minor — but cheap to fix (e.g. append "(current)"/"(latest)" to the relevant combobox entries).

### 5. Schema-validation failure details are raw jsonschema paths, not plain language

**Heuristic #9.** Not new — this is a pattern already used for catalog/profile validation, and the Upgrade dialog just inherited it — but worth naming now that it's used in a third place: the "doesn't fully conform" dialogs show `validate_oscal_file()`'s error strings directly (e.g. `component-definition → metadata: 'oscal-version' is a required property`), which is accurate but not written for a non-technical System Owner. Deliberately not scored as high-priority since it's consistent existing behaviour, not a regression — but a real candidate if a future pass wants to tackle #9 further (e.g. a small lookup table translating the most common jsonschema failure shapes into plain sentences).

---

## Re-verified: previously-open items are still accurately described

Checked directly rather than assumed carried-over:
- **No undo/redo** — still true, no change-tracking layer anywhere.
- **No batch/multi-select** — every `Treeview` in the app still uses `selectmode="browse"`.
- **No in-app tutorial** — still just the Workspace tab's static guidance cards.
- **`GREEN`/`TEAL` marginal light-mode contrast** — unchanged, still 3.1–3.9:1 in light mode only.
- **The app's menu bar has only Help** — confirmed no File/Edit/View menu exists; Save/Open/New Workspace remain button-only, spread across the Workspace tab rather than consolidated anywhere. Not necessarily wrong (the buttons are visible and labelled), but worth naming as a design choice rather than an oversight: a File menu is the conventional place a user might look first.

---

## Suggested priority if tackled

1. Fix the silent validation-skip in the Upgrade dialog (🔴 above) — small, and it's the one place this session's own "never claim compliance you haven't checked" principle was accidentally broken.
2. Tooltip on "Create New Workspace" — trivial, same pattern already used everywhere else.
3. Enter/Escape support in dialogs — bigger, but high value, and a natural `_make_dialog()` enhancement that benefits every dialog in the app at once rather than needing 15+ individual fixes.
4. Collapsed-state summary label, "current/latest" marker in the Upgrade dropdown — cosmetic polish, lowest urgency.
