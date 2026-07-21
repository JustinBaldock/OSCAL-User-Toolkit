"""
Unit tests for oscal_user_toolkit/models.py — the data layer.

models.py deliberately contains no GUI code (see its own module docstring),
which is exactly what makes it easy to unit test: every function here is
plain data in, dict/list out, with no tkinter widgets to construct or fake.

These tests focus on the pieces most likely to actually break something if
changed carelessly: multi-catalog OSCAL output grouping, profile-based
control filtering, the CatalogResolver, and a couple of round-trip
prop-encoding helpers (VLANs, data-flow links) that have no other coverage.
"""

import uuid

import pytest

from oscal_user_toolkit.models import (
    CatalogResolver,
    build_component_oscal_entry,
    get_prop,
    get_profile_controls,
    get_source_href,
    new_uuid,
    now_iso,
    safe_filename_component,
    _build_vlan_props,
    _parse_vlan_props,
    _build_data_flow_link_props,
    _parse_data_flow_link_props,
)


# ── Small pure helpers ───────────────────────────────────────────────────────

def test_new_uuid_returns_unique_valid_uuids():
    a, b = new_uuid(), new_uuid()
    assert a != b
    # Raises ValueError if not a well-formed UUID string.
    uuid.UUID(a)
    uuid.UUID(b)


def test_now_iso_format():
    stamp = now_iso()
    # OSCAL requires this exact "Z"-suffixed UTC format for last-modified fields.
    assert stamp.endswith("Z")
    assert len(stamp) == 20  # "YYYY-MM-DDTHH:MM:SSZ"


@pytest.mark.parametrize("text, expected", [
    ("Simple Title", "Simple_Title"),
    ("ManageEngine ServiceDesk Plus (ITSM : Helpdesk)", "ManageEngine_ServiceDesk_Plus_ITSM_Helpdesk"),
    ('Bad\\/:*?"<>|Chars', "Bad_Chars"),
    ("", ""),
])
def test_safe_filename_component(text, expected):
    assert safe_filename_component(text) == expected


def test_get_prop_found_and_missing():
    props = [{"name": "label", "value": "GOV-01"}]
    assert get_prop(props, "label") == "GOV-01"
    assert get_prop(props, "colour") == "—"
    assert get_prop(props, "colour", default="none") == "none"


# ── get_source_href — preference order: profile > catalog > placeholder ────

def test_get_source_href_prefers_profile():
    profile = {"filepath": "/lib/profiles/my_profile.json"}
    catalog = {"filepath": "/lib/catalogs/my_catalog.json"}
    assert get_source_href(profile, catalog) == "my_profile.json"


def test_get_source_href_falls_back_to_catalog():
    catalog = {"filepath": "/lib/catalogs/my_catalog.json"}
    assert get_source_href(None, catalog) == "my_catalog.json"


def test_get_source_href_placeholder_when_neither_loaded():
    assert get_source_href(None, None) == "PROFILE_OR_CATALOG_HREF"


# ── get_profile_controls — single-catalog filtering ─────────────────────────

def _control(cid):
    return {"id": cid, "label": cid, "title": "", "statement": ""}


def test_get_profile_controls_no_catalog_returns_empty():
    assert get_profile_controls(None, None) == []


def test_get_profile_controls_no_profile_returns_full_catalog():
    catalog = {"controls": [_control("ism-1"), _control("ism-2")]}
    result = get_profile_controls(catalog, None)
    assert [c["id"] for c in result] == ["ism-1", "ism-2"]


def test_get_profile_controls_filters_by_profile_ids():
    catalog = {"controls": [_control("ism-1"), _control("ism-2"), _control("ism-3")]}
    profile = {"ids": {"ism-1", "ism-3"}}
    result = get_profile_controls(catalog, profile)
    assert {c["id"] for c in result} == {"ism-1", "ism-3"}


# ── CatalogResolver ──────────────────────────────────────────────────────────

def test_catalog_resolver_add_and_get_by_path(tmp_path):
    resolver = CatalogResolver()
    assert resolver.is_empty()

    path = tmp_path / "ISM_catalog.json"
    catalog = {"controls": [_control("ism-1")]}
    resolver.add_catalog(path, catalog)

    assert not resolver.is_empty()
    assert resolver.get_catalog(path) == catalog
    # A differently-spelled but equivalent path resolves to the same entry.
    assert resolver.get_catalog(str(path)) == catalog


def test_catalog_resolver_resolve_control(tmp_path):
    resolver = CatalogResolver()
    path = tmp_path / "ISM_catalog.json"
    resolver.add_catalog(path, {"controls": [_control("ism-1490")]})

    found = resolver.resolve_control(path, "ism-1490")
    assert found["id"] == "ism-1490"
    assert resolver.resolve_control(path, "does-not-exist") is None


def test_catalog_resolver_all_controls_combines_every_catalog(tmp_path):
    resolver = CatalogResolver()
    ism_path = tmp_path / "ISM_catalog.json"
    nist_path = tmp_path / "NIST_catalog.json"
    resolver.add_catalog(ism_path, {"controls": [_control("ism-1")]})
    resolver.add_catalog(nist_path, {"controls": [_control("ac-2")]})

    combined = resolver.all_controls()
    assert len(combined) == 2
    ids = {c["id"] for _path, c in combined}
    assert ids == {"ism-1", "ac-2"}


def test_catalog_resolver_clear():
    resolver = CatalogResolver()
    resolver.add_catalog("/some/path.json", {"controls": []})
    resolver.clear()
    assert resolver.is_empty()


# ── build_component_oscal_entry — multi-catalog grouping ────────────────────
# See oscal_user_toolkit_design_document.md §10.24 for the design this
# covers: a component can hold responses against controls from more than
# one catalog, and each control-implementations block must carry its own
# correct "source" rather than being forced into a single block.

def test_build_component_oscal_entry_single_source_backward_compatible():
    """A component with no ctrl_response_sources (every pre-existing
    single-catalog component/capability) falls back to one block using the
    passed-in source_href — this must keep working unchanged."""
    comp = {
        "uuid": new_uuid(),
        "type": "software",
        "title": "Example",
        "description": "An example component.",
        "ctrl_responses": {"ism-1490": "We do the thing."},
    }
    entry = build_component_oscal_entry(comp, "fallback.json")

    blocks = entry["control-implementations"]
    assert len(blocks) == 1
    assert blocks[0]["source"] == "fallback.json"
    assert blocks[0]["implemented-requirements"][0]["control-id"] == "ism-1490"


def test_build_component_oscal_entry_groups_by_recorded_source():
    comp = {
        "uuid": new_uuid(),
        "type": "software",
        "title": "AWS",
        "description": "Cloud platform.",
        "ctrl_responses": {
            "ism-1490": "ISM response.",
            "ac-2": "NIST response.",
        },
        "ctrl_response_sources": {
            "ism-1490": "ISM_catalog.json",
            "ac-2": "NIST_SP-800-53_rev5_catalog.json",
        },
    }
    entry = build_component_oscal_entry(comp, "fallback.json")

    blocks = entry["control-implementations"]
    assert len(blocks) == 2
    by_source = {b["source"]: [r["control-id"] for r in b["implemented-requirements"]] for b in blocks}
    assert by_source == {
        "ISM_catalog.json": ["ism-1490"],
        "NIST_SP-800-53_rev5_catalog.json": ["ac-2"],
    }


def test_build_component_oscal_entry_mixed_recorded_and_unrecorded_source():
    """A control with no entry in ctrl_response_sources falls back to
    source_href, even when other controls on the same component do have
    a recorded source — the two should NOT be merged into the fallback's
    bucket by mistake."""
    comp = {
        "uuid": new_uuid(),
        "type": "software",
        "title": "Mixed",
        "description": "d",
        "ctrl_responses": {"ism-1490": "resp1", "ac-2": "resp2"},
        "ctrl_response_sources": {"ism-1490": "ISM_catalog.json"},
    }
    entry = build_component_oscal_entry(comp, "fallback.json")

    by_source = {
        b["source"]: [r["control-id"] for r in b["implemented-requirements"]]
        for b in entry["control-implementations"]
    }
    assert by_source == {
        "ISM_catalog.json": ["ism-1490"],
        "fallback.json": ["ac-2"],
    }


def test_build_component_oscal_entry_skips_empty_responses():
    comp = {
        "uuid": new_uuid(),
        "type": "software",
        "title": "Example",
        "description": "d",
        "ctrl_responses": {"ism-1490": "   ", "ism-1491": "real response"},
    }
    entry = build_component_oscal_entry(comp, "fallback.json")
    ids = [r["control-id"] for b in entry["control-implementations"] for r in b["implemented-requirements"]]
    assert ids == ["ism-1491"]


def test_build_component_oscal_entry_no_responses_omits_control_implementations():
    comp = {
        "uuid": new_uuid(),
        "type": "software",
        "title": "Example",
        "description": "d",
        "ctrl_responses": {},
    }
    entry = build_component_oscal_entry(comp, "fallback.json")
    assert "control-implementations" not in entry


def test_build_component_oscal_entry_basic_fields():
    comp = {
        "uuid": "fixed-uuid",
        "type": "hardware",
        "title": "Firewall",
        "description": "Perimeter firewall.",
        "purpose": "Filter traffic.",
        "ctrl_responses": {},
    }
    entry = build_component_oscal_entry(comp, "fallback.json")
    assert entry["uuid"] == "fixed-uuid"
    assert entry["type"] == "hardware"
    assert entry["title"] == "Firewall"
    assert entry["purpose"] == "Filter traffic."


# ── VLAN / data-flow-link prop round-trips ──────────────────────────────────
# These have no other test coverage and are pure encode/decode logic, so a
# round trip (build -> parse -> compare) is cheap insurance against a future
# refactor silently breaking either half.

def test_vlan_props_round_trip():
    vlans = [
        {"uuid": "vlan-1", "vlan_id": "10", "name": "Corporate", "description": "Staff LAN"},
        {"uuid": "vlan-2", "vlan_id": "20", "name": "Guest", "description": ""},
    ]
    props = _build_vlan_props(vlans)
    result = _parse_vlan_props(props)

    by_uuid = {v["uuid"]: v for v in result}
    assert by_uuid["vlan-1"] == vlans[0]
    # An empty description isn't written as a prop, so it round-trips as ""
    # rather than being dropped or raising.
    assert by_uuid["vlan-2"]["vlan_id"] == "20"
    assert by_uuid["vlan-2"]["name"] == "Guest"


def test_vlan_props_ignores_foreign_namespace_props():
    # A prop from an unrelated feature (e.g. a data-flow-link prop) sharing
    # the same "group" value must not bleed into VLAN parsing.
    foreign = _build_data_flow_link_props([{
        "uuid": "shared-group-id", "source_component_uuid": "a",
        "target_component_uuid": "b", "protocol": "https",
    }])
    assert _parse_vlan_props(foreign) == []


def test_data_flow_link_props_round_trip():
    flows = [{
        "uuid": "flow-1",
        "source_component_uuid": "comp-a",
        "source_component_title": "Web Server",
        "target_component_uuid": "comp-b",
        "target_component_title": "Database",
        "protocol": "https",
        "port": "443",
        "transport": "TCP",
        "direction": "outbound",
        "description": "API calls",
    }]
    props = _build_data_flow_link_props(flows)
    result = _parse_data_flow_link_props(props)

    assert len(result) == 1
    assert result[0] == flows[0]
