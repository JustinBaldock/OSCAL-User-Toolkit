"""
Round-trip tests for the SSP/AP/AR/POA&M build/parse functions in models.py.

Each test builds an internal working dict, runs it through build_oscal_*()
to produce an OSCAL JSON document, then through parse_*_file() to convert
it back — and checks the result matches what went in. This is the same
save-then-load a user actually does when they save a file and reopen it;
a break here means real data silently gets mangled on disk, not just a
crash somewhere obvious.

Every fixture below was built by running the actual functions and reading
their real output first (not guessed from the schema), so what's asserted
here is what the code actually does today — a baseline to catch future
regressions against, not a spec of what it "should" do.
"""

from oscal_user_toolkit.models import (
    empty_ap,
    empty_ar,
    empty_poam,
    empty_ssp,
    build_oscal_ap,
    build_oscal_ar,
    build_oscal_poam,
    build_oscal_ssp,
    new_uuid,
    parse_ap_file,
    parse_ar_file,
    parse_poam_file,
    parse_ssp_file,
)


# ── SSP ──────────────────────────────────────────────────────────────────────

def test_ssp_round_trip():
    ssp = empty_ssp()
    ssp["title"] = "Test SSP"
    ssp["system_name"] = "Test System"
    ssp["system_name_short"] = "TS"
    ssp["system_description"] = "A test system."
    ssp["roles"] = [{"role_id": "system-owner", "title": "System Owner"}]

    party_uuid = new_uuid()
    ssp["parties"] = [{"uuid": party_uuid, "type": "organization", "name": "Acme", "email": "a@b.com"}]
    ssp["responsible_parties"] = [
        {"role_id": "system-owner", "party_uuid": party_uuid, "party_name": "Acme", "remarks": ""}
    ]

    comp_uuid = new_uuid()
    ssp["components"] = [{
        "uuid": comp_uuid, "type": "software", "title": "Firewall", "description": "d",
        "purpose": "", "status": "operational", "status_remarks": "",
        "responsible_roles": [], "remarks": "",
    }]
    ssp["information_types"] = [{
        "uuid": new_uuid(), "title": "General Info", "description": "d",
        "c_impact": "moderate", "i_impact": "moderate", "a_impact": "moderate",
    }]
    ssp["vlans"] = [{"uuid": new_uuid(), "vlan_id": "10", "name": "Corp", "description": ""}]
    ssp["ctrl_implementations"] = [{
        "control_id": "ac-2", "remarks": "",
        "by_components": [{
            "uuid": new_uuid(), "component_uuid": comp_uuid,
            "description": "We do it.", "impl_status": "implemented", "remarks": "",
        }],
    }]
    ssp["users"] = [{
        "uuid": new_uuid(), "title": "Admin User", "short_name": "admin",
        "description": "d", "role_ids": ["system-owner"], "remarks": "",
    }]
    ssp["inventory_items"] = [{
        "uuid": new_uuid(), "description": "Server 1",
        "props": [{"name": "asset_tag", "value": "A1"}],
        "implemented_components": [comp_uuid], "remarks": "",
    }]

    doc = build_oscal_ssp(ssp, None, None, "1.2.2")
    result, _back_matter = parse_ssp_file(doc)

    assert result["title"] == "Test SSP"
    assert result["system_name"] == "Test System"
    assert result["system_name_short"] == "TS"
    assert result["system_description"] == "A test system."
    assert result["roles"] == ssp["roles"]
    assert result["parties"] == ssp["parties"]
    assert result["responsible_parties"] == ssp["responsible_parties"]
    assert result["information_types"] == ssp["information_types"]
    assert result["vlans"] == ssp["vlans"]
    assert result["ctrl_implementations"] == ssp["ctrl_implementations"]
    assert result["users"] == ssp["users"]
    assert result["inventory_items"] == ssp["inventory_items"]

    # The auto-generated "this-system" component is prepended — the
    # user-added component should still be present alongside it.
    saved_titles = [c["title"] for c in result["components"]]
    assert "Firewall" in saved_titles
    firewall = next(c for c in result["components"] if c["title"] == "Firewall")
    assert firewall["uuid"] == comp_uuid
    assert firewall["type"] == "software"


def test_ssp_round_trip_empty_is_safe():
    """A brand-new, never-touched SSP must build and parse without error."""
    ssp = empty_ssp()
    doc = build_oscal_ssp(ssp, None, None, "1.2.2")
    result, _back_matter = parse_ssp_file(doc)
    assert result["title"] == ""
    assert result["roles"] == []
    assert result["ctrl_implementations"] == []


# ── Assessment Plan ──────────────────────────────────────────────────────────

def test_ap_round_trip():
    ap = empty_ap()
    ap["title"] = "Test AP"
    ap["import_ssp"] = "ssp_test.json"
    ap["reviewed_controls_all"] = False
    ap["reviewed_control_ids"] = ["ac-2", "ac-3"]
    ap["tasks"] = [
        {
            "uuid": new_uuid(), "type": "milestone", "title": "Kickoff", "description": "d",
            "timing_type": "on-date", "timing_date": "2026-01-01",
            "timing_start": "", "timing_end": "", "timing_period": "", "timing_unit": "days",
            "remarks": "",
        },
        {
            "uuid": new_uuid(), "type": "action", "title": "Recurring scan", "description": "d",
            "timing_type": "at-frequency", "timing_date": "", "timing_start": "", "timing_end": "",
            "timing_period": "7", "timing_unit": "days", "remarks": "",
        },
    ]

    doc = build_oscal_ap(ap, oscal_version="1.2.2")
    result = parse_ap_file(doc)

    assert result["title"] == "Test AP"
    assert result["import_ssp"] == "ssp_test.json"
    assert result["reviewed_controls_all"] is False
    assert result["reviewed_control_ids"] == ["ac-2", "ac-3"]
    assert result["tasks"] == ap["tasks"]


def test_ap_round_trip_include_all_controls():
    ap = empty_ap()
    ap["reviewed_controls_all"] = True
    doc = build_oscal_ap(ap, oscal_version="1.2.2")
    result = parse_ap_file(doc)
    assert result["reviewed_controls_all"] is True
    assert result["reviewed_control_ids"] == []


def test_ap_build_requires_oscal_version():
    ap = empty_ap()
    import pytest
    with pytest.raises(ValueError):
        build_oscal_ap(ap)


# ── Assessment Results ──────────────────────────────────────────────────────

def test_ar_round_trip():
    ar = empty_ar()
    ar["title"] = "Test AR"
    ar["import_ap"] = "ap_test.json"
    ar["result_title"] = "Result 1"
    ar["result_description"] = "d"
    ar["result_start"] = "2026-01-01"
    ar["result_end"] = "2026-01-15"

    obs_uuid = new_uuid()
    ar["observations"] = [{
        "uuid": obs_uuid, "description": "Observed", "methods": ["TEST"],
        "title": "Obs 1", "types": ["control-objective"], "collected": "2026-01-01",
        "expires": "", "relevant_evidence": [], "remarks": "", "assessed_by": "",
    }]
    risk_uuid = new_uuid()
    ar["risks"] = [{
        "uuid": risk_uuid, "title": "Risk 1", "description": "d", "statement": "s",
        "status": "open", "deadline": "2026-06-01",
        "remediations": [{
            "uuid": new_uuid(), "lifecycle": "planned", "title": "Fix",
            "description": "d", "remarks": "",
        }],
        "remarks": "",
    }]
    ar["findings"] = [{
        "uuid": new_uuid(), "title": "Finding 1", "description": "d",
        "target_type": "statement-id", "target_id": "ac-2_smt.a",
        "status_state": "not-satisfied", "status_reason": "misconfigured",
        "impl_status": "partial",
        "related_obs_uuids": [obs_uuid], "related_risk_uuids": [risk_uuid],
        "remarks": "",
    }]
    ar["assessment_log"] = [{
        "uuid": new_uuid(), "start": "2026-01-01", "end": "2026-01-01",
        "description": "Kickoff meeting", "remarks": "",
    }]

    doc = build_oscal_ar(ar, oscal_version="1.2.2")
    result = parse_ar_file(doc)

    assert result["title"] == "Test AR"
    assert result["import_ap"] == "ap_test.json"
    assert result["result_title"] == "Result 1"
    assert result["result_description"] == "d"
    assert result["result_start"] == "2026-01-01"
    assert result["result_end"] == "2026-01-15"
    assert result["risks"] == ar["risks"]
    assert result["findings"] == ar["findings"]
    assert result["assessment_log"] == ar["assessment_log"]

    # NOTE: "assessed_by" does NOT currently round-trip for AR observations —
    # build_oscal_ar() never writes it to a prop (unlike build_oscal_poam(),
    # which does), even though parse_ar_file() reads it back via the shared
    # _parse_oscal_observation() helper and ar_tab.py's internal dict shape
    # carries the key. This assertion documents that CURRENT behaviour so a
    # future fix is a deliberate change, not a silent one — see the actual
    # value asserted is "", not the "assessor1" that would prove a real fix.
    assert result["observations"][0]["assessed_by"] == ""


# ── POA&M ────────────────────────────────────────────────────────────────────

def test_poam_round_trip():
    poam = empty_poam()
    poam["title"] = "Test POAM"
    poam["import_ssp"] = "ssp_test.json"
    poam["system_id"] = "test-system"

    poam["observations"] = [{
        "uuid": new_uuid(), "description": "Observed thing", "methods": ["EXAMINE"],
        "title": "Obs 1", "types": ["control-objective"], "collected": "2026-01-01T00:00:00Z",
        "expires": "", "relevant_evidence": [], "remarks": "", "assessed_by": "assessor1",
    }]
    poam["risks"] = [{
        "uuid": new_uuid(), "title": "Risk 1", "description": "d", "statement": "s",
        "status": "open", "deadline": "2026-06-01",
        "cia_c": "high", "cia_i": "moderate", "cia_a": "low",
        "remediations": [{
            "uuid": new_uuid(), "lifecycle": "planned", "title": "Fix it",
            "description": "d", "remarks": "",
        }],
        "remarks": "",
    }]
    poam["findings"] = [{
        "uuid": new_uuid(), "title": "Finding 1", "description": "d",
        "target_type": "statement-id", "target_id": "ac-2_smt.a",
        "status_state": "not-satisfied", "status_reason": "misconfigured",
        "remarks": "",
    }]
    poam["poam_items"] = [{
        "uuid": new_uuid(), "title": "Item 1", "description": "d",
        "scheduled_completion": "2026-12-31",
        "related_observation_uuids": [poam["observations"][0]["uuid"]],
        "related_risk_uuids": [poam["risks"][0]["uuid"]],
        "related_finding_uuids": [poam["findings"][0]["uuid"]],
        "remarks": "",
    }]

    doc = build_oscal_poam(poam, oscal_version="1.2.2")
    result = parse_poam_file(doc)

    assert result["title"] == "Test POAM"
    assert result["import_ssp"] == "ssp_test.json"
    assert result["system_id"] == "test-system"
    # POA&M DOES preserve assessed_by (unlike AR — see test_ar_round_trip).
    assert result["observations"][0]["assessed_by"] == "assessor1"
    assert result["risks"] == poam["risks"]
    assert result["findings"] == poam["findings"]
    assert result["poam_items"] == poam["poam_items"]


def test_poam_import_ssp_made_relative_to_save_path(tmp_path):
    """
    import_ssp is stored as an absolute path internally but should be
    written as a portable path relative to where the POA&M itself is
    saved, so the file still resolves correctly if the whole folder is
    moved — see build_oscal_poam()'s save_path parameter.
    """
    ssp_path = tmp_path / "system" / "ssp.json"
    poam_path = tmp_path / "system" / "poam.json"

    poam = empty_poam()
    poam["import_ssp"] = str(ssp_path)

    doc = build_oscal_poam(poam, oscal_version="1.2.2", save_path=str(poam_path))
    href = doc["plan-of-action-and-milestones"]["import-ssp"]["href"]
    assert href == "ssp.json"


def test_poam_build_requires_oscal_version():
    poam = empty_poam()
    import pytest
    with pytest.raises(ValueError):
        build_oscal_poam(poam)
