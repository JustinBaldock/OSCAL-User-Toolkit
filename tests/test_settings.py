"""
Unit tests for oscal_user_toolkit/settings.py.

scan_oscal_versions() was extracted out of app.py (previously
OSCALApp._scan_oscal_versions(), a private method with no widget/self
dependency at all) specifically because it's pure filesystem scanning —
these tests are the payoff for that extraction.
"""

from oscal_user_toolkit.settings import scan_oscal_versions


def test_scan_oscal_versions_missing_dir_returns_empty(tmp_path):
    labels, paths = scan_oscal_versions(tmp_path / "does-not-exist")
    assert labels == []
    assert paths == {}


def test_scan_oscal_versions_empty_dir_returns_empty(tmp_path):
    labels, paths = scan_oscal_versions(tmp_path)
    assert labels == []
    assert paths == {}


def test_scan_oscal_versions_ignores_non_zip_and_non_oscal_files(tmp_path):
    (tmp_path / "readme.txt").write_text("not a zip")
    (tmp_path / "oscal-1.0.0.zip").write_bytes(b"not actually a valid zip")
    labels, paths = scan_oscal_versions(tmp_path)
    assert labels == []
    assert paths == {}


def test_scan_oscal_versions_sorts_newest_first(tmp_path):
    import zipfile

    for version in ("1.1.2", "1.2.2", "1.2.0"):
        with zipfile.ZipFile(tmp_path / f"oscal-{version}.zip", "w") as zf:
            zf.writestr("marker.txt", "placeholder")

    labels, paths = scan_oscal_versions(tmp_path)

    assert labels == ["v1.2.2", "v1.2.0", "v1.1.2"]
    assert set(paths.keys()) == {"1.2.2", "1.2.0", "1.1.2"}
    assert paths["1.2.2"].name == "oscal-1.2.2.zip"
