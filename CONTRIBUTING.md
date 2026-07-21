# Contributing to OSCAL User Toolkit

Contributions, bug reports, and feature suggestions are welcome. This file covers what you need to know before opening an issue or pull request.

## Before you start

- Skim [README.md](README.md) for what the app does and how it's structured.
- Read [SECURE_CODING.md](SECURE_CODING.md) before touching any file-loading or exception-handling code — this app constantly parses OSCAL JSON files a user picked from disk, which the OpenSSF guide this project follows treats as untrusted input regardless of it being "just a local file."
- Check [todo.md](todo.md) for known gaps and planned features before starting something big, so you don't duplicate work already in progress or already deliberately deferred (with a reason noted).

## Project structure

The codebase follows a strict two-layer separation:

- **`oscal_user_toolkit/models.py`** — all data parsing, serialisation, and validation logic. No GUI code, no `tkinter` import. This is what makes it the one file in the codebase with real unit test coverage (see [Testing](#testing) below) — every function is plain dicts/lists in, plain dicts/lists out.
- **Everything else in `oscal_user_toolkit/`** (`*_tab.py`, `app.py`) — all GUI code. No direct JSON manipulation; a tab file should call into `models.py` to build or parse an OSCAL document, not construct the JSON structure itself.

Keep new code on the correct side of that line. A new feature that needs both a UI and a data transformation should add the transformation to `models.py` and call it from the tab file, not inline the JSON handling in the tab.

## Setting up

```bash
git clone https://github.com/JustinBaldock/OSCAL-User-Toolkit.git
cd OSCAL-User-Toolkit
pip install jsonschema python-docx     # optional runtime deps — see README.md#requirements
pip install -r requirements-dev.txt    # ruff, pytest — needed to run lint/tests locally
python main.py
```

## Making a change

1. **Open an issue first for anything non-trivial** — a quick description of the bug or feature before you write code saves everyone time if the approach needs discussion.
2. **Keep the two-layer separation** (above).
3. **Match the existing style** rather than introducing a new one — this codebase has consistent conventions (button colours/fonts, dialog patterns via `_make_dialog()`, docstring style) that a previous usability pass already normalized; deviating from them just creates a new inconsistency for someone else to clean up later.
4. **Write a test if you're touching `models.py`.** See [Testing](#testing) below.
5. **Run lint and tests locally before opening a PR** — CI will run the same checks, but catching it locally is faster:
   ```bash
   ruff check .
   pytest
   ```
6. **For UI changes**, actually run the app and exercise the change — `tests/` doesn't cover `tkinter` code (see below), so this is the only verification that catches a UI-level mistake.

## Testing

`tests/` currently covers `models.py` only, and deliberately so — it's the one file with no GUI code to mock. If you're adding or changing a function there:

- Add or update a test in `tests/test_models.py` (small pure helpers, `CatalogResolver`, control-list filtering) or `tests/test_roundtrip.py` (the SSP/AP/AR/POA&M build/parse round-trips).
- Build your test fixture, run it through the actual function, and read the real output before writing assertions — don't guess what the code "should" do from the schema. This project has already found two real bugs this way (see the design document §10.28) that a spec-based test would have missed by asserting the wrong thing with confidence.
- `tab_*.py` / `app.py` (GUI code) has no automated tests. If you're changing UI behaviour, describe how you manually verified it in your PR description.

## CI

Every push and pull request against `main` runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml): Ruff (lint) and pytest (unit tests). Ruff here is scoped to real correctness issues (unused imports/variables, undefined names, multi-statement lines) rather than full style/line-length rules — see [`pyproject.toml`](pyproject.toml) for the exact rule set and why.

## Reporting bugs

Open a [GitHub issue](https://github.com/JustinBaldock/OSCAL-User-Toolkit/issues) with:
- What you did, what you expected, what actually happened.
- The OSCAL document type involved (Catalog, Profile, Component, Capability, SSP, AP, AR, POA&M), if relevant.
- If the app crashed or logged an error, the relevant lines from `oscal_user_toolkit/error.log`.

For a security vulnerability, please don't open a public issue — contact the maintainer directly instead.

## Licence

By contributing, you agree your contribution is licensed under this project's [GPLv3 licence](LICENSE).
