# OSCAL User Toolkit Usability Review

## Overview
This document summarizes usability issues and recommendations for the OSCAL User Toolkit based on Jakob Nielsen's 10 usability heuristics.

> **Note on this pass**: three items below were verified directly against the current codebase (not just re-stated) and then implemented — marked ✅ **Done** with the evidence. A couple of the original findings turned out to be stale (already addressed, or based on a UI that has since changed) — marked ⚠️ **Superseded** with what's actually true today. Everything else is unchanged from the original review and still reflects a real gap.

## 1. Visibility of System Status
**Issues:**
- Minimal status messages in status bar only
- No indicators for save status or file changes
- No progress indicators for long operations

**Recommendations:**
- Add "unsaved changes" indicator in tab titles
- Include save status in toolbar
- Show loading indicators during file operations

**✅ Done — "unsaved changes" indicator in tab titles.** Every editor tab already tracked its own `_dirty` flag internally (used by `_on_close()`'s exit confirmation), but never surfaced it while the app was open — the only way to discover unsaved work was to try closing the window. `app.py`'s `_refresh_dirty_indicators()` now polls every 500ms and appends a trailing `*` to a tab's label whenever its `_dirty` flag is set (and clears it once saved), using the same convention as most text editors/IDEs (ties into heuristic #2 below too). The marker also propagates up through nested tab groups — e.g. if the Component Editor inside **⚙ System Overview** is dirty, the **⚙ System Overview** group tab itself shows the `*` too, so you can tell something needs saving without having to open every group to check. Verified functionally: setting a leaf tab's `_dirty` flag and running the refresh logic correctly marks both the leaf tab and its parent group, and clears both once `_dirty` is reset.

*Not done*: save status in the toolbar (the status bar already shows the most recent save message, e.g. "Component saved: firewall.json", but it's transient, not a persistent toolbar indicator) and progress indicators for long operations — neither tackled in this pass.

## 2. Match Between System and Real World
**Issues:**
- Unclear tab names (e.g., "Audit" tab for POA&M)
- No visual indicators that sections are collapsible

**Recommendations:**
- Rename tabs for clarity (e.g., "POA&M" instead of "Audit")
- Use visual cues like arrows or icons for collapsible sections
- Add tooltips to clarify function of each interface element

**⚠️ Superseded — "Audit tab for POA&M".** Checked `app.py`'s current tab structure directly: POA&M has its own clearly-named tab, **📋 POA&M Editor**, alongside **📝 Assessment Plan** and **🔍 Assessment Results**. "Audit" is the *group* label containing all three (a `ttk.Notebook` of sub-tabs, added when the tab bar was reorganised into Data/Organisation/System Overview/Audit groups) — a reasonable grouping name for that trio, not a mislabelling of POA&M itself. No change made; the original finding no longer applies to the current UI.

**✅ Done — tooltips added, though not to every element.** Attached tooltips (new `attach_tooltip()` helper in `tab_utils.py`) to the interface elements that most needed one: genuinely icon-only buttons whose action isn't in the label at all (Data Sources tab's unlabelled 🔄 refresh button), and buttons whose label states the action but not its less-obvious consequence (the Library editors' "🔄 Refresh from Library" doesn't say it discards unsaved edits; "📌 Save New Version" doesn't say it archives history first — both now spelled out on hover). Also added to the main toolbar's "📚 Library Folder"/"🗂 Systems Folder" buttons, clarifying these are persisted app-wide settings, not per-file actions. *Not done*: an exhaustive pass over every button/icon in the app — the many icon **+ text** buttons elsewhere (e.g. "📥 Add File to Library") already name their own action reasonably well, so were left alone; a full audit for tooltip coverage would be a separate, larger task.

**✅ Done — visual cues for collapsible sections.** New `tab_utils.make_collapsible()`: a ▼/▶ arrow + clickable header bar that shows/hides a body frame. First applied to the Component/Capability Editors' "🗂 Document Metadata" card (version/revision history plus the new creator/links fields — see the feature that prompted this), which was becoming the single largest fixed-height element in the form, especially in `library_mode` where dozens of these cards exist across different components. *Not done*: applying this to any other section of the app — only the one card that prompted it uses it so far.

## 3. User Control and Freedom
**Issues:**
- No undo/redo functionality
- Limited keyboard shortcuts
- No way to cancel actions during long operations

**Recommendations:**
- Implement undo/redo functionality for edits
- Add more keyboard shortcuts (Ctrl+S, Ctrl+O)
- Add cancel buttons to long-running operations

**✅ Done (partial) — Ctrl+S / Ctrl+O keyboard shortcuts.** Confirmed via direct search that the app previously had zero keyboard shortcuts and no menu bar at all — only `bind_all("<MouseWheel>")` scroll-guards existed. Added:
- **Ctrl+S** — saves whichever editor tab is currently active (dispatches to that tab's own save method — e.g. `ComponentTab._save_file`, `SSPTab._save` — via a lookup table built once at startup), so it works consistently across all 8 save-capable tabs (System Overview's and the Library's Component/Capability Editors, SSP, Assessment Plan, Assessment Results, POA&M) without needing 8 separate bindings.
- **Ctrl+O** — opens files, wired only where "open" is unambiguous: the two System Overview editors that have their own "📂 Open File(s)" button. Deliberately *not* wired for the Library editors (locked to the Library folder by design — no Open File(s) exists there at all) or for tabs with no open/save concept (Dashboard, All Systems, Data Sources, Catalog Viewer), where it's a harmless no-op rather than an error.
- Verified Tk's `Text` widget has its own default `<Control-o>` binding (an Emacs-style "insert newline" left over from Tk's stock keybindings) that fires *before* a `bind_all` handler can intercept it — so Ctrl+O is suppressed while focus is in any multi-line description field, preventing a stray newline from being inserted every time the shortcut is used elsewhere. Ctrl+S has no such conflict on any platform tested.

Both confirmed functionally: dispatch correctly targets whichever tab is actually selected (including through nested tab groups), and the Ctrl+O Text-widget guard was verified to suppress the action with a `Text` widget focused while still firing normally from an `Entry`.

*Not done*: undo/redo (a real change-tracking layer across every tab's edit operations — scoped as a separate, larger project, not a quick addition) and cancel buttons for long operations.

## 4. Consistency and Standards
**Issues:**
- Inconsistent UI element usage across tabs
- Button styles and positioning vary between sections
- Different terminology for similar concepts

**Recommendations:**
- Standardize button shapes, colors, and positions
- Consistent use of icons and visual elements
- Use standard terminology throughout

**⚠️ Superseded (partially) — button relief/font/cursor were already consistent.** Checked directly: every button in the app already uses `relief="flat"` and `cursor="hand2"` (245+ occurrences each), so "button styles... vary" didn't hold up as originally worded. The real, verifiable inconsistencies were narrower:

**✅ Done — icon/text spacing standardized.** ~13 buttons used a single space between their icon and label (`"✕ Remove"`, `"＋ Add"`, `"⧉ Duplicate"`, `"📂 Browse…"`, `"⊞ By type"`, `"🔤 A–Z"`) while the app's dominant convention (200+ other buttons) uses a double space (`"💾  Save..."`, `"📂  Open File(s)"`). All normalized to double-space, across `ar_tab.py`, `poam_tab.py`, `ap_tab.py`, and `component_tab.py`.

**✅ Done — "Remove" terminology unified to "Remove Selected".** 15 buttons across `ssp_tab.py`, `ar_tab.py`, and `poam_tab.py` said bare "✕ Remove"/"✕  Remove" for an action that removes whichever row is currently selected in a Treeview — verified every one of them sits directly next to an "✏ Edit Selected" button acting on the same selection, so the inconsistent wording wasn't a deliberate distinction, just drift. Left "✕ Delete" alone (2 places, `component_tab.py`/`capability_tab.py`) — that's a genuinely different action (deletes the whole component/capability, not a sub-item row), so keeping a different verb there is correct, not inconsistent.

*Not done*: standardizing button positioning across tabs, and a full pass on terminology beyond Remove/Delete — neither independently re-audited this pass.

## 5. Error Prevention
**Issues:**
- No validation feedback for input fields
- No confirmation for destructive actions
- No warnings for invalid OSCAL structure

**Recommendations:**
- Implement real-time form validation
- Add confirmation dialogs for delete/overwrite actions
- Add input format validation (e.g., port ranges, UUIDs)

**⚠️ Superseded (partially) — confirmations and structure warnings already existed.** Checked directly: `askyesno` confirmation dialogs are already used in 7 files (deletes, clears, unsaved-changes-on-close), and `validate_oscal_file()` + a "Load anyway?" prompt already warns on invalid OSCAL structure at 6 load points (catalog, profile, component, capability saves). The doc's blanket claims didn't hold up — but the one specific, named example it called out, port range validation, was a real gap.

**✅ Done — port range validation now checks the actual valid range, not just "is it a number".** `component_tab.py`'s protocol dialog already validated that Start/End port fields parsed as integers (submit-time, via the existing "+ Add" button — not live-as-you-type, but does prevent bad data reaching the model either way), but accepted any integer at all — `0`, a negative number, `99999`, or an end port lower than the start port would all have been silently accepted into a saved OSCAL file. Added range checks (1–65535, the valid TCP/UDP port range) for both fields, plus an end-cannot-be-lower-than-start check. Verified all boundary cases (0, 65536, reversed range, non-numeric, valid single port, valid range, the 1/65535 boundary values themselves) against the exact logic added.

*Not done*: UUID format validation — checked whether this applies at all first: every UUID in the app is auto-generated (`new_uuid()`) and shown read-only (e.g. the Version & Revision History card's Component/Document UUID labels) — there is no user-typed UUID field anywhere to validate. The original recommendation doesn't actually apply to this app as built. Real-time (as-you-type) validation more broadly, and OSCAL structure warnings beyond what already existed, weren't tackled.

## 6. Recognition Rather Than Recall
**Issues:**
- No clear visual hierarchy
- Tab structure doesn't immediately communicate content
- Tooltips missing from many interface elements

**Recommendations:**
- Improve visual hierarchy with consistent typography
- Add tool tips to all interactive elements
- Provide better labels with context for each section

## 7. Flexibility and Efficiency of Use
**Issues:**
- Limited keyboard shortcuts
- No shortcuts for common actions
- No batch operations for multiple components

**Recommendations:**
- Add more keyboard shortcuts for common actions
- Implement batch editing capabilities
- Add multi-select functionality

## 8. Aesthetic and Minimalist Design
**Issues:**
- UI appears cluttered in some sections
- Text and colors could be more readable
- Inconsistent spacing and padding

**Recommendations:**
- Reduce visual clutter by grouping related elements
- Improve color contrast and readability
- Standardize spacing and padding throughout

**✅ Done — a real, severe color-contrast bug found and fixed.** Rather than relying on subjective "could be more readable," computed actual WCAG 2.1 contrast ratios for every `fg`/`bg` colour pair used together anywhere in the app (26 distinct combinations found), in both themes. Formula verified against the known white-on-black reference (21.0:1) before trusting the results. Found: **74 buttons** across 7 files (`ssp_tab.py` alone had 40) paired `fg=C["BUTTON_TEXT"]` (a fixed near-black `#1a1a1a`, intended only for use on the light pastel `_BG` fills like `GREEN_BG`/`BLUE_BG`) with `bg=C["HEADER_BG"]` (dark slate `#313244` in dark mode) — a **1.38:1 contrast ratio** in dark mode, far below even the most lenient WCAG threshold (3:1), on every "secondary" button in the app (Remove Selected, Edit Selected, Cancel, etc.). Fixed by changing all 74 to `fg=C["TEXT"]` instead — the pattern 2 buttons already used correctly — which gives 8.69:1 in dark mode and 12.06:1 in light mode, comfortably passing WCAG AA in both. Verified the fix doesn't touch any of the correct `BUTTON_TEXT`-on-pastel-fill pairings (checked every real `BUTTON_TEXT` call site individually — all pair with `GREEN_BG`/`TEAL_BG`/`ACCENT_BG`/`BLUE_BG`, none with a raw background colour).

**Known, deliberately unfixed**: `GREEN`/`TEAL` used as direct text colour (status labels, section headings) come out marginal in **light mode only** — 3.1–3.9:1, above the 3:1 "large/bold text" threshold but below the stricter 4.5:1 normal-text one. Left alone rather than changed, because `GREEN`/`TEAL` are load-bearing brand/identity colours used consistently across many components (capability editor branding, success indicators) — adjusting their hue to fix a marginal contrast shortfall would be a visual-identity change, not a surgical accessibility fix, and deserves a deliberate decision rather than being bundled into this pass.

*Not done*: "reduce visual clutter," "standardize spacing/padding" — neither is answerable by direct code inspection the way contrast is; would need actual visual/screenshot review, not just grep.

## 9. Help Users Recognize, Diagnose, and Recover from Errors
**Issues:**
- Error messages are basic
- No guidance for correcting invalid input
- No error logs for troubleshooting

**Recommendations:**
- Improve error messaging with clear guidance
- Add context-specific help tooltips
- Implement error logging for developers

**✅ Done — a real gap found: tkinter's default uncaught-exception behaviour is silent failure, not "basic error messages."** Checked directly: nothing in the app overrode `report_callback_exception`, and no `logging` module usage existed anywhere (confirmed independently during the SECURE_CODING.md audit too). This means any exception raised inside a button click, key binding, or `.after()` callback that wasn't already wrapped in a `try/except` — i.e. anything not already covered by the many specific handlers added in earlier passes — hit tkinter's *own* default handler, which prints a traceback to stderr and otherwise does nothing. A user running the packaged app (not from a terminal) would never see that traceback; the button they clicked would just appear to silently do nothing, with no indication anything went wrong and nothing to report. That's a worse failure mode than the "basic error messages" the review described — there was no error message at all for this class of failure.

Fixed via `app.py`'s new `_setup_error_logging()` (called first thing in `__init__`, before any widgets are built) and `_on_uncaught_exception()`:
- Every uncaught callback exception now writes a full timestamped traceback to `oscal_user_toolkit/error.log` (via Python's `logging` module — gitignored, this app's first real use of that module).
- The user sees a plain-language dialog ("Something went wrong... try the action again, or save your work in other tabs first") naming the log file location and the exception type/message, rather than either a silent failure or a raw traceback dumped in their face.

Verified functionally: simulated an uncaught exception the same way tkinter's dispatch loop actually triggers this hook, and confirmed the dialog fires with the correct title/content and the log file receives the full traceback, exception type, and message.

*Not done*: "guidance for correcting invalid input" beyond what error-prevention validation (see #5) already provides at the point of entry, and "context-specific help tooltips" for errors specifically — general tooltips were already covered under #2/#10.

## 10. Help and Documentation
**Issues:**
- No embedded help system
- Documentation scattered across READMEs
- No in-app tutorials for new users

**Recommendations:**
- Add a help menu with quick reference
- Implement contextual help (hover tooltips)
- Create a basic walkthrough or tutorial for new users

**✅ Done — Help menu added.** Confirmed directly that the app had no `tk.Menu` at all before this — the toolbar's buttons were the only affordance. Added a native menu bar (`app.py`'s `_build_menu_bar()`) with a single **Help** menu:
- **Keyboard Shortcuts** — the Ctrl+S/Ctrl+O reference for #3/#7's shortcuts, kept as plain text describing exactly what's actually wired (not auto-generated from the `_SAVE_ACTIONS`/`_OPEN_ACTIONS` dictionaries, so it needs a manual update if that coverage changes — noted in a comment).
- **Workspace Guide** — jumps straight to the existing Workspace tab's per-tab guidance cards (the app's existing, if easy-to-miss, help content), giving it a second, more discoverable entry point rather than building a parallel help system.
- **About OSCAL User Toolkit** — what the app is, and where the fuller docs (`README.md`, the design document, `RELEASE_NOTES.md`) live.

Verified functionally: the menu bar is actually attached (`self.cget("menu")`), the Help cascade has the 3 expected entries in order, both `showinfo` dialogs fire with the right title, and invoking "Workspace Guide" actually switches the active tab to index 0.

**✅ Done (partial) — "contextual help (hover tooltips)" is largely covered already**, via #2's `attach_tooltip()` work in the previous pass — not repeated here since it's the same item under two heuristics in the original review.

*Not done*: a full in-app walkthrough/tutorial for new users. Scoped out deliberately — a real tutorial system (guided first-run flow, highlighting UI elements in sequence, etc.) is a substantially larger project than a quick-reference menu, and the Workspace tab's existing per-tab guidance cards already cover a good chunk of what a tutorial would otherwise need to explain from scratch.

## Implementation Status Specific Observations
The implementation status values are correctly defined and consistent between:
- `component_tab.py`
- `ssp_tab.py`

Both files define the same values: "implemented", "partial", "planned", "alternative", "not-applicable" with no apparent bugs in the persistence mechanism.

## Visual Design Issues
1. **Color Consistency** - Inconsistent application of color palettes
2. **Typography and Readability** - Non-standard text sizes and weights
3. **Layout and Spacing** - Inconsistent padding and margins
4. **Visual Feedback** - Limited hover effects and visual feedback for interactive elements