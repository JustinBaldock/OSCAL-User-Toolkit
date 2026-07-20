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

*Not done*: visual cues for collapsible sections — not tackled in this pass.

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

## 5. Error Prevention
**Issues:**
- No validation feedback for input fields
- No confirmation for destructive actions
- No warnings for invalid OSCAL structure

**Recommendations:**
- Implement real-time form validation
- Add confirmation dialogs for delete/overwrite actions
- Add input format validation (e.g., port ranges, UUIDs)

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

## 9. Help Users Recognize, Diagnose, and Recover from Errors
**Issues:**
- Error messages are basic
- No guidance for correcting invalid input
- No error logs for troubleshooting

**Recommendations:**
- Improve error messaging with clear guidance
- Add context-specific help tooltips
- Implement error logging for developers

## 10. Help and Documentation
**Issues:**
- No embedded help system
- Documentation scattered across READMEs
- No in-app tutorials for new users

**Recommendations:**
- Add a help menu with quick reference
- Implement contextual help (hover tooltips)
- Create a basic walkthrough or tutorial for new users

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