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
import zipfile
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent / "settings.json"

# Subfolders created under a configured library path.
LIBRARY_SUBFOLDERS = ["catalogs", "profiles", "components", "capabilities"]

# Default library folder: the repo's own library/ directory (sibling of the
# oscal_user_toolkit package), used until the user picks a different one via
# the "📚 Library Folder" toolbar button.
DEFAULT_LIBRARY_PATH = Path(__file__).parent.parent / "library"

# Default systems folder: the repo's own systems/ directory — holds one
# subfolder per system (each with its own workspace manifest, SSP, AP, AR,
# POA&M), scanned by the "🌐 All Systems" tab for an organisation-wide
# rollup. Used until the user picks a different one via the "🗂 Systems
# Folder" toolbar button.
DEFAULT_SYSTEMS_PATH = Path(__file__).parent.parent / "systems"

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


def get_systems_path():
    """
    Return the configured systems folder as a Path.

    Falls back to DEFAULT_SYSTEMS_PATH (the repo's own systems/ folder) if
    the user hasn't chosen a different one yet. Creates it if missing, the
    same as the Library folder's default.
    """
    path_str = load_settings().get("systems_path")
    path = Path(path_str) if path_str else DEFAULT_SYSTEMS_PATH
    path.mkdir(parents=True, exist_ok=True)
    return path


def set_systems_path(path):
    """Persist the systems folder path, creating it if it doesn't exist."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    settings["systems_path"] = str(path)
    save_settings(settings)


def scan_oscal_versions(oscal_dir):
    """
    Scan oscal_dir for OSCAL schema zip files and return the versions found.

    A file named 'oscal-1.2.2.zip' becomes the label 'v1.2.2'. Versions are
    sorted newest-first so a dropdown built from the result defaults to the
    latest available version.

    Parameters:
        oscal_dir - Path to the folder containing OSCAL release zip files
                    (the repo's own oscal/ folder by default).

    Returns:
        A tuple of (version_labels, version_paths):
            version_labels - list of "vX.Y.Z" strings, newest first
            version_paths  - {"X.Y.Z": Path} map (unprefixed label -> zip path)
        Both are empty if oscal_dir doesn't exist or contains no zips.
    """
    oscal_dir = Path(oscal_dir)
    if not oscal_dir.is_dir():
        return [], {}

    versions = []
    for path in oscal_dir.glob("*.zip"):
        if zipfile.is_zipfile(path):
            # Strip leading 'oscal-' and trailing '.zip', e.g. 'oscal-1.2.2.zip' → '1.2.2'
            name = path.stem  # 'oscal-1.2.2'
            label = name.removeprefix("oscal-")  # '1.2.2'
            versions.append((label, path))

    # Sort by parsed version tuple so '1.2.10' > '1.2.2' correctly
    versions.sort(key=lambda x: [int(p) for p in x[0].split(".") if p.isdigit()], reverse=True)
    version_paths = {label: path for label, path in versions}
    return [f"v{label}" for label, _ in versions], version_paths


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
