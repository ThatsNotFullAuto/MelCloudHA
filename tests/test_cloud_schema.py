"""Synthetic schema probes. No real customer payloads or network activity."""

import json
import subprocess
import sys
from copy import deepcopy

import pytest

from custom_components.melcloud_diagnostics.core.cloud import CloudReader
from custom_components.melcloud_diagnostics.core.cloud_telemetry import cloud_observations
from custom_components.melcloud_diagnostics.core.models import DataError, Snapshot
from custom_components.melcloud_diagnostics.core.schema import validate_payload

from .conftest import NOW, UNIT
from .test_cloud import session_for


def test_schema_checks_share_runtime_normalization_and_do_not_disclose_values(raw_unit):
    raw_unit["password"] = "private-synthetic-secret"
    raw_unit["settings"].append({"name": "AccessToken", "value": "private-synthetic-token"})
    before = deepcopy(raw_unit)
    result = validate_payload("unit", raw_unit, NOW)
    assert result["schema_valid"]
    fields = result["units"][0]["parameters"]
    facts = cloud_observations(Snapshot.parse(raw_unit, NOW))
    assert set(fields) == {o.parameter for o in facts}
    assert fields["RoomTemperatureZone1"] == "exposed"
    assert fields["FlowTemperature"] == "missing"
    assert "selected_room_sensor" in result["not_mapped_by_integration"]
    for private in (UNIT, "Synthetic Ecodan", "private-synthetic", "22.5", "AccessToken"):
        assert private not in json.dumps(result)
    assert raw_unit == before


def test_malformed_field_is_not_a_complete_schema_failure_or_a_measurement(raw_unit):
    raw_unit["settings"] = [
        {"name": "FlowTemperature", "value": "unknown"},
        {"name": "ReturnTemperature", "value": "0"},
    ]
    result = validate_payload("unit", raw_unit, NOW)
    assert result["schema_valid"]
    assert result["units"][0]["parameters"]["FlowTemperature"] == "invalid"
    assert result["units"][0]["parameters"]["ReturnTemperature"] == "exposed"
    assert not result["physical_accuracy_verified"]


@pytest.mark.parametrize(
    "kind,payload",
    [
        ("context", {}),
        ("context", {"buildings": [None]}),
        ("unit", {"settings": []}),
        ("history", {}),
        ("history", [{"errorCode": "unknown"}]),
        ("report", {}),
        ("report", {"support": {}}),
    ],
)
def test_invalid_captures_are_reported_safely(kind, payload):
    result = validate_payload(kind, payload, NOW)
    assert not result["schema_valid"] and result["issues"]


def test_raw_capture_requires_timezone_and_history_never_claims_completeness(raw_unit):
    assert not validate_payload("unit", raw_unit)["schema_valid"]
    result = validate_payload("history", [])
    assert result["schema_valid"] and not result["history_completeness_verified"]


async def test_duplicate_unit_is_rejected_by_transport_and_offline_checks(raw_unit, auth):
    raw = {"buildings": [{"airToWaterUnits": [raw_unit, raw_unit]}]}
    assert not validate_payload("context", raw, NOW)["schema_valid"]
    with pytest.raises(DataError):
        await CloudReader(session_for(raw), auth).discover(NOW)


@pytest.mark.parametrize("capabilities", [[], False, "unknown"])
def test_falsey_invalid_capability_containers_are_not_silently_empty(raw_unit, capabilities):
    raw_unit["capabilities"] = capabilities
    assert not validate_payload("unit", raw_unit, NOW)["schema_valid"]


def test_native_ha_report_and_old_report_without_normalized_view_are_accepted(raw_unit):
    observation = {
        "source": "melcloud_home",
        "observed_at": NOW.isoformat(),
        "connected": True,
        "in_error": False,
        "settings": {"RoomTemperatureZone1": "22.5"},
    }
    report = {
        "support": {"format": "melcloud_diagnostics.support", "schema_version": 1},
        "units": {"unit_1": {"faults": [], "current_observation": observation}},
    }
    result = validate_payload("report", {"data": report})
    assert result["schema_valid"]
    assert result == validate_payload("report", report)
    assert result["units"][0]["parameters"]["RoomTemperatureZone1"] == "exposed"
    assert result["units"][0]["parameters"]["rssi"] == "not_in_report"
    observation["observed_at"] = "2026-10-30T12:00:00"
    assert not validate_payload("report", report)["schema_valid"]


def test_normalized_report_checks_availability_dates_and_duplicate_parameters(raw_unit):
    facts = [o.export() for o in cloud_observations(Snapshot.parse(raw_unit, NOW))]
    report = {
        "support": {"format": "melcloud_diagnostics.support", "schema_version": 1},
        "units": {"private-unit-name": {"faults": [], "normalized_telemetry": facts}},
    }
    result = validate_payload("report", report)
    assert result["schema_valid"]
    assert result["units"][0]["parameters"]["rssi"] == "exposed"
    assert "private-unit-name" not in json.dumps(result)
    facts.append(facts[0])
    assert not validate_payload("report", report)["schema_valid"]
    facts.pop()
    facts[0]["acquired_at"] = "2026-10-30T12:00:00"
    assert not validate_payload("report", report)["schema_valid"]


def test_malformed_second_unit_cannot_change_first_unit_report_evidence():
    first = {
        "faults": [],
        "current_observation": {
            "source": "melcloud_home",
            "observed_at": NOW.isoformat(),
            "settings": {"RoomTemperatureZone1": "22.5"},
        },
    }
    second = deepcopy(first)
    second["current_observation"]["settings"] = {"invalid": {"structured": True}}
    report = {
        "support": {"format": "melcloud_diagnostics.support", "schema_version": 1},
        "units": {"first": first},
    }
    expected = validate_payload("report", report)["units"]
    report["units"]["second"] = second
    result = validate_payload("report", report)
    assert not result["schema_valid"] and result["units"] == expected


def test_cli_never_echoes_invalid_json_or_secrets_and_exits_nonzero(tmp_path):
    path = tmp_path / "capture.json"
    path.write_text('{"password": "private-synthetic-secret", broken', encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "tools.validate_cloud_data", str(path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "private-synthetic" not in result.stdout + result.stderr
    assert not json.loads(result.stdout)["schema_valid"]
    path.write_text("[]", encoding="utf-8")
    valid = subprocess.run(
        [sys.executable, "-m", "tools.validate_cloud_data", str(path), "--kind", "history"],
        capture_output=True,
        text=True,
    )
    assert valid.returncode == 0 and json.loads(valid.stdout)["schema_valid"]
