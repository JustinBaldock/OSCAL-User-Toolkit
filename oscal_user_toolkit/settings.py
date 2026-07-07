"""
settings.py — Persisted application settings for the OSCAL User Toolkit.

Currently holds just the configured Library folder path (see
oscal_user_toolkit_design_document.md and todo.md for the Library concept:
a shared, organisation-level collection of catalogs/profiles/components/
capabilities, kept separate from any one system's own workspace).

Settings are stored in a small JSON file under the user's home directory,
independent of any project or workspace file, since the library path is a
per-installation preference rather than OSCAL content.
"""

import json
from pathlib import Path

SETTINGS_DIR  = Path.home() / ".oscal_user_toolkit"
SETTINGS_PATH = SETTINGS_DIR / "settings.json"

# Subfolders created under a configured library path.
LIBRARY_SUBFOLDERS = ["catalogs", "profiles", "components", "capabilities"]


def load_settings():
    """Read the settings file, returning {} if it doesn't exist or is invalid."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings):
    """Write the settings dict to the settings file, creating its folder if needed."""
    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def get_library_path():
    """Return the configured library folder as a Path, or None if not set."""
    path_str = load_settings().get("library_path")
    return Path(path_str) if path_str else None


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
