"""
settings.py — Persisted application settings for the OSCAL User Toolkit.

Holds settings that should survive between launches but aren't OSCAL
content: the configured Library folder path (see
oscal_user_toolkit_design_document.md §10.13 and todo.md for the Library
concept) and the default light/dark theme.

Stored as settings.json inside this package folder, alongside the source
code — a single-user desktop install, so per-installation storage here is
simpler than a per-user home-directory file. This file is machine-specific
(it records a local library folder path), so it should not be committed —
see .gitignore.
"""

import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent / "settings.json"

# Subfolders created under a configured library path.
LIBRARY_SUBFOLDERS = ["catalogs", "profiles", "components", "capabilities"]

# Default library folder: the repo's own library/ directory (sibling of the
# oscal_user_toolkit package), used until the user picks a different one via
# the "📚 Library Folder" toolbar button.
DEFAULT_LIBRARY_PATH = Path(__file__).parent.parent / "library"

VALID_THEMES  = ("dark", "light")
DEFAULT_THEME = "dark"


def load_settings():
    """Read the settings file, returning {} if it doesn't exist or is invalid."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings):
    """Write the settings dict to the settings file."""
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_library_path():
    """
    Return the configured library folder as a Path.

    Falls back to DEFAULT_LIBRARY_PATH (the repo's own library/ folder) if
    the user hasn't chosen a different one yet, rather than returning None
    and forcing a manual "Library Folder" click before the app is usable.
    """
    path_str = load_settings().get("library_path")
    if path_str:
        return Path(path_str)
    ensure_library_structure(DEFAULT_LIBRARY_PATH)
    return DEFAULT_LIBRARY_PATH


def set_library_path(path):
    """
    Persist the library folder path and ensure its standard subfolders
    (catalogs/, profiles/, components/, capabilities/) exist.
    """
    path = Path(path)
    ensure_library_structure(path)
    settings = load_settings()
    settings["library_path"] = str(path)
    save_settings(settings)


def ensure_library_structure(path):
    """Create the standard library subfolders under path if they don't exist."""
    path = Path(path)
    for sub in LIBRARY_SUBFOLDERS:
        (path / sub).mkdir(parents=True, exist_ok=True)


def get_theme():
    """Return the saved default theme ('dark' or 'light'), or DEFAULT_THEME if unset."""
    theme = load_settings().get("theme")
    return theme if theme in VALID_THEMES else DEFAULT_THEME


def set_theme(theme_name):
    """Persist the default theme to use on the next launch."""
    if theme_name not in VALID_THEMES:
        return
    settings = load_settings()
    settings["theme"] = theme_name
    save_settings(settings)
