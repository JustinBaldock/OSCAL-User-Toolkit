# Secure Coding Practices — OSCAL User Toolkit

This project follows the OpenSSF Best Practices Working Group's
**[Secure Coding Guide for Python](https://github.com/ossf/wg-best-practices-os-developers/tree/main/docs/Secure-Coding-Guide-for-Python)**.

This document is the short, project-specific version: which parts of that guide actually apply here, and the concrete rules that follow from them. Read this first; go to the full guide for the "why" and more examples. This applies to human contributors and AI coding agents alike.

## Why this exists

This app repeatedly does one risky thing: **it parses OSCAL JSON files a user picked from disk** — catalogs, profiles, components, capabilities, SSPs, workspace manifests. Every one of those is untrusted input by the guide's definition, even though it's "just JSON on the user's own machine." A malformed, truncated, or hand-edited file should produce a friendly error dialog, never a crash or a silently-wrong result.

## Which sections of the guide apply here

| Guide section | Relevance | Why |
|---|---|---|
| §4 Neutralization | **High** | Constant `json.load()` on user-selected files — this is deserialization of untrusted input |
| §5 Exception handling | **High** | Same reason — file loads need specific, expected exception types, not silent catch-alls |
| §8 Coding standards | **Medium** | General hygiene: resource cleanup, no mutation-while-iterating, no builtin shadowing |
| §6 Logging | **Medium** | Status bar / error dialogs are this app's "logs" — keep them user-safe |
| §1 Introduction, §2 Encoding & strings | **Low-medium** | Consistent UTF-8 encoding when reading/writing files |
| §3 Numbers, §7 Concurrency, §9 Cryptography | **Not applicable** | No numeric-heavy logic, no threading (single-threaded Tkinter), no cryptography implemented directly (components only *describe* crypto controls) |

## Project-specific rules

**1. Every `json.load()` of a file the user selected must be inside a `try` that catches specific exceptions — never bare.**
At minimum: `json.JSONDecodeError` (malformed JSON — note this is already a subclass of `ValueError`, so `except ValueError` also catches it), `OSError` (file deleted/permission-denied/unreadable between selection and read), and `KeyError` if you then check for a required top-level key. Show the user a `messagebox.showerror(...)` with the exception text — never let it propagate to an unhandled traceback.
```python
try:
    data = load_catalog(path)
except (json.JSONDecodeError, OSError, KeyError, ValueError) as exc:
    messagebox.showerror("Failed to load catalog", str(exc))
    return
```
See `app.py`'s `_open_workspace()` and `all_systems_tab.py`'s workspace loader for the reference pattern — both already do this correctly.

**2. Catch the specific exception you actually expect — `except Exception:` is a last resort, not a default.**
The one exception type this app's Tkinter code legitimately can't always predict in advance is `tkinter.TclError` (a widget that's been destroyed, a tab index that no longer exists after a refresh, a tree-item id that's gone). That's fine to catch defensively — but write `except tk.TclError:`, not `except Exception:`. A bare `Exception` catch will also silently swallow an unrelated real bug (a typo causing an `AttributeError`, say) sitting in the same block, and you'll never find out.
```python
try:
    tree.selection_set(self._selected_ctrl_id)
except tk.TclError:
    pass   # Row no longer exists in this tab after a refresh
```
Exception: `models.py` deliberately never imports `tkinter` (it's the data layer — see the design document's architecture section) even though one or two of its functions take a live notebook widget as a parameter. Don't "fix" that file's exception handling by importing tkinter into it just to narrow an exception type; that trades one problem for a worse one (blurring the data/UI layer boundary). Leave it broad there and say why in a comment.

**3. No `eval`, `exec`, `pickle`, or `subprocess`/`os.system` — full stop.**
None of these have a legitimate use case in this app. If a future feature seems to need one, that's a sign to redesign the feature, not to add an exception to this rule.

**4. Archive/zip handling: read-only, entry-by-entry, never `extractall()` on anything user-supplied.**
The only zip files this app opens are its own bundled OSCAL schema releases (`oscal/oscal-*.zip`), and it only ever reads one known entry out of them (`zf.open("json/schema/...")`), never extracts to disk. Keep it that way — if a future feature needs to accept a zip from a user, `extractall()` on an untrusted zip is a path-traversal ("zip slip") risk and needs its own review.

**5. Every file handle uses a context manager (`with open(...) as f:`).** No manual `.close()` calls, no handles left to the garbage collector. This is already 100% consistent across the codebase — keep it that way.

**6. No secrets, credentials, or API keys in source.** This app doesn't handle any itself (it only *describes* credential/crypto controls in OSCAL component data), so this should never come up — but if a future integration needs one, it goes in a config file that's `.gitignore`d, never a literal in a `.py` file.

**7. No stray `print()` debugging left in committed code.** Use the existing `set_status()` callback pattern (writes to the status bar) if a tab needs to surface something to the user. For genuine errors, use the `logging` module — `app.py`'s `_setup_error_logging()` sets up a file handler on the `"oscal_user_toolkit"` logger (writing to `oscal_user_toolkit/error.log`, gitignored) and installs it as tkinter's `report_callback_exception` hook, so any uncaught exception in a UI callback is logged with a full traceback instead of silently vanishing into stderr. Get that logger with `logging.getLogger("oscal_user_toolkit")` rather than creating a new one if you need to log something explicitly.

## What's deliberately out of scope

- **Concurrency (§7)** — this app is single-threaded Tkinter; there's no thread pool, shared mutable state across threads, or locking to get wrong.
- **Cryptography (§9)** — the app never performs encryption/hashing/signing itself; components merely *record* that a system uses AES-256, TLS, etc. If that ever changes (e.g. an "encrypt this workspace file" feature), revisit this section before writing any crypto code — don't hand-roll it.

## When in doubt

Read the relevant section of the [full guide](https://github.com/ossf/wg-best-practices-os-developers/tree/main/docs/Secure-Coding-Guide-for-Python) before writing the code, not after. If a pattern in this codebase doesn't match a rule above, that's worth flagging in review rather than copying.
