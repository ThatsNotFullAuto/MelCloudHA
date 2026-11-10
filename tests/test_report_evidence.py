"""Independent evidence regressions using newly constructed synthetic cloud data."""

import json
from copy import deepcopy
from datetime import timedelta

import pytest

from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.core.test_privacy import SchemaInspector, sample
from custom_components.melcloud_diagnostics.core.test_session import (
    add_schema,
    apply_record,
    evaluate,
    new_report,
    validate_report,
)
from tools.read_support_report import summarize

from .conftest import NOW, UNIT


def _unit(**fields):
    return {"id": UNIT, "settings": [], **fields}


def _report():
    return new_report(
        NOW,
        1200,
        False,
        dict.fromkeys(("integration", "homeassistant", "python", "aiomelcloudhome"), "1.0.0"),
    )


def _capture(report, raw, operation="unit_snapshot"):
    if operation == "account_context":
        raw = {"buildings": [{"airToWaterUnits": [raw]}]}
    frame = SchemaInspector(b"synthetic-evidence-tests").inspect(operation, raw, UNIT)
    add_schema(report, frame)


def _poll(report, raw, offset=0, faults=()):
    at = NOW + timedelta(seconds=offset)
    return apply_record(
        report,
        {
            "kind": "poll",
            "at": at.isoformat(),
            "sample": sample(Snapshot.parse(raw, at), False),
            "history_status": "available",
            "history_attempted": True,
            "history_checked_at": at.isoformat(),
            "faults": list(faults),
        },
        {},
    )[0]


def _absent(report):
    return evaluate(report)["missing_evidence"]["absent_in_observed_cloud"]


@pytest.mark.parametrize("operation", ["account_context", "unit_snapshot"])
@pytest.mark.parametrize("value", [None, "", "   ", "unknown", "--", "P1", 123, True])
def test_observed_error_code_is_never_structurally_absent(operation, value):
    raw = _unit(settings=[{"name": "ErrorCode", "value": value}])
    report = _report()
    _capture(report, raw, operation)
    report = _poll(report, raw)
    before = deepcopy(report["decoded_parameters"])

    result = evaluate(report)

    assert "ErrorCode" not in result["missing_evidence"]["absent_in_observed_cloud"]
    assert result["decoded_parameters"] == before
    assert result["p1_investigation"]["code_readable"] is (value == "P1")
    assert result["p1_investigation"]["active_p1_observed"] is False


@pytest.mark.parametrize("operation", ["account_context", "unit_snapshot"])
def test_omitted_setting_is_absent_with_complete_structural_coverage(operation):
    raw, report = _unit(), _report()
    _capture(report, raw, operation)
    report = _poll(report, raw)
    assert "ErrorCode" in _absent(report)


@pytest.mark.parametrize("limitation", ["no_inventory", "truncated", "no_settings", "null_settings",
                                          "context_not_selected", "history_only", "uncovered_poll",
                                          "dropped"])
def test_incomplete_inventory_cannot_certify_an_absent_setting(limitation):
    raw, report = _unit(), _report()
    if limitation == "history_only":
        _capture(report, [{"timestamp": NOW.isoformat(), "errorCode": "P1"}], "error_history")
    elif limitation == "context_not_selected":
        _capture(report, {"id": "22222222-2222-4222-8222-222222222222", "settings": []},
                 "account_context")
    elif limitation != "no_inventory":
        schema_raw = {"id": UNIT} if limitation == "no_settings" else raw
        if limitation == "null_settings":
            schema_raw = _unit(settings=None)
        _capture(report, schema_raw)
    report = _poll(report, raw)
    if limitation == "truncated":
        report["schema_inventory"]["truncated"] = 1
    elif limitation == "uncovered_poll":
        report = _poll(report, raw, 60)
    elif limitation == "dropped":
        report["acquisition"]["dropped"] = 1
    assert "ErrorCode" not in _absent(report)


@pytest.mark.parametrize("parameter,cloud_name", [("connected", "isConnected"),
                                                   ("in_error", "isInError"), ("rssi", "rssi")])
@pytest.mark.parametrize("value", [None, "unknown"])
def test_direct_unit_fields_map_to_normalized_names(parameter, cloud_name, value):
    raw, report = _unit(**{cloud_name: value}), _report()
    _capture(report, raw)
    report = _poll(report, raw)
    assert report["decoded_parameters"][parameter]["missing"] == 1
    assert parameter not in _absent(report)

    omitted = _report()
    _capture(omitted, _unit())
    omitted = _poll(omitted, _unit())
    assert parameter in _absent(omitted)


def test_redacted_numeric_value_remains_available_and_observed():
    raw = _unit(settings=[{"name": "RoomTemperatureZone1", "value": "22.5"}], rssi=-60)
    report = _report()
    _capture(report, raw)
    report = _poll(report, raw)
    for parameter in ("RoomTemperatureZone1", "rssi"):
        fact = next(f for f in report["temporal_observations"][0]["facts"]
                    if f["parameter"] == parameter)
        assert fact["availability"] == "available"
        assert fact["value"] is None and fact["value_exported"] is False
        assert report["decoded_parameters"][parameter]["present"] == 1
        assert parameter not in _absent(report)


@pytest.mark.parametrize("present_operation", ["account_context", "unit_snapshot"])
def test_positive_presence_wins_across_operations_and_incomplete_inventory(present_operation):
    report = _report()
    present = _unit(settings=[{"name": "ErrorCode", "value": ""}])
    omitted = _unit()
    _capture(report, present, present_operation)
    _capture(report, omitted,
             "unit_snapshot" if present_operation == "account_context" else "account_context")
    report = _poll(report, omitted)
    report["schema_inventory"]["truncated"] = 1
    assert "ErrorCode" not in _absent(report)


def test_a_partial_second_operation_prevents_an_absence_conclusion():
    report = _report()
    _capture(report, _unit(), "unit_snapshot")
    _capture(report, {"id": UNIT}, "account_context")
    report = _poll(report, _unit())
    assert "ErrorCode" not in _absent(report)


def test_partial_frame_of_the_same_operation_prevents_absence():
    report = _report()
    _capture(report, _unit())
    _capture(report, {"id": UNIT})
    report = _poll(report, _unit())
    assert "ErrorCode" not in _absent(report)


def _fault(code="P1"):
    return {"timestamp": (NOW - timedelta(days=2)).isoformat(), "code": code,
            "cleared_at": None, "source": "melcloud_home"}


def test_history_error_code_does_not_supply_a_current_code_or_active_fault():
    report = _report()
    _capture(report, _unit())
    _capture(report, [{"timestamp": NOW.isoformat(), "errorCode": "P1"}], "error_history")
    report = _poll(report, _unit(), faults=[_fault()])
    result = evaluate(report)
    assert "ErrorCode" in result["missing_evidence"]["absent_in_observed_cloud"]
    assert result["p1_investigation"]["code_readable"] is False
    assert result["p1_investigation"]["active_p1_observed"] is False
    assert result["p1_investigation"]["historical_p1"] == 1


@pytest.mark.parametrize("flag,code,active", [(True, "P1", True), (False, "P1", False),
                                             (None, "P1", False), (True, "P2", False)])
def test_active_p1_requires_true_flag_and_current_p1(flag, code, active):
    raw = _unit(isInError=flag, settings=[{"name": "ErrorCode", "value": code}])
    result = evaluate(_poll(_report(), raw))
    assert result["p1_investigation"]["code_readable"] is True
    assert result["p1_investigation"]["active_p1_observed"] is active
    assert result["p1_investigation"]["first_p1_observed_at"] == (NOW.isoformat() if active else None)


def test_flags_and_codes_from_different_samples_do_not_create_active_p1():
    report = _poll(_report(), _unit(isInError=True))
    report = _poll(report, _unit(isInError=False,
                               settings=[{"name": "ErrorCode", "value": "P1"}]), 60)
    result = evaluate(report)
    assert result["p1_investigation"]["code_readable"] is True
    assert result["p1_investigation"]["active_p1_observed"] is False


def test_history_counts_records_and_reobservations_without_inventing_episodes():
    report = _poll(_report(), _unit(), faults=[_fault(), _fault(), _fault("P2")])
    report = _poll(report, _unit(), 60, faults=[_fault()])
    result = evaluate(report)
    assert result["fault_history"]["duplicates"] == 2
    assert len(result["fault_history"]["records"]) == 2
    assert result["p1_investigation"]["historical_p1"] == 1
    assert result["p1_investigation"]["active_p1_observed"] is False


@pytest.mark.parametrize("model,generation", [("FTC7", "FTC7"), ("synthetic-model", "unknown"),
                                               (None, "unknown"), ("x" * 129, "unknown")])
def test_ftc_generation_and_field_observation_are_separate(model, generation):
    raw, report = _unit(ftcModel=model), _report()
    _capture(report, raw)
    report = _poll(report, raw)
    result = evaluate(report)
    assert result["ftc_capabilities"]["declared_generation"] == generation
    assert "unit_snapshot.unit.ftcModel" in result["schema_inventory"]["fields"]
    assert "synthetic-model" not in json.dumps(result)
    assert "x" * 129 not in json.dumps(result)


def test_evaluation_and_reader_leave_input_unchanged_and_keep_schema_one():
    report = _report()
    raw = _unit(ftcModel="synthetic-model", settings=[{"name": "ErrorCode", "value": ""}])
    _capture(report, raw)
    report = _poll(report, raw, faults=[_fault()])
    original = deepcopy(report)
    result = evaluate(report)
    assert report == original
    assert set(result) == set(original)
    assert result["schema_version"] == 1
    assert set(result["missing_evidence"]) == {
        "absent_in_observed_cloud", "present_uninterpreted", "unexpected_format",
        "history_inaccessible", "acquisition_failed", "ftc_unverifiable", "manual_required",
        "additional_source_to_evaluate",
    }
    validate_report(result)
    evaluated = deepcopy(result)
    text = summarize({"data": {"diagnostic_test": result}})
    assert result == evaluated
    assert "synthetic-model" not in text
    assert "UNKNOWN" in text


def test_reader_distinguishes_history_current_code_flag_and_unknown_ftc():
    raw = _unit(ftcModel="synthetic-model", isInError=False,
                settings=[{"name": "ErrorCode", "value": ""}])
    report = _report()
    _capture(report, raw)
    result = evaluate(_poll(report, raw, faults=[_fault()]))
    text = summarize(result)
    assert "Current interpretable error codes: none observed" in text
    assert "Active fault flag (samples): true=0, false=1, unknown=0" in text
    assert "Active P1 observed: false" in text
    assert "Historical records: 1; historical P1 records: 1 (not an episode count)" in text
    assert "FTC declared generation: unknown; ftcModel field observed: yes" in text
    assert "synthetic-model" not in text


@pytest.mark.parametrize("value", [None, "not-a-boolean", True, False])
def test_settings_error_flag_fallback_is_observed_even_when_not_decodable(value):
    raw = _unit(settings=[{"name": "IsInError", "value": value}])
    report = _report()
    _capture(report, raw)
    report = _poll(report, raw)
    validate_report(report)
    result = evaluate(report)
    assert "in_error" not in result["missing_evidence"]["absent_in_observed_cloud"]
    counts = result["decoded_parameters"]["in_error"]
    assert counts["present"] == int(type(value) is bool)
    assert counts["missing"] == int(type(value) is not bool)


def test_different_operations_cannot_compensate_for_an_uncovered_later_poll():
    report = _report()
    _capture(report, _unit(), "account_context")
    _capture(report, _unit(), "unit_snapshot")
    report = _poll(report, _unit())
    report = _poll(report, _unit(), 60)
    validate_report(report)
    assert "ErrorCode" not in _absent(report)


@pytest.mark.parametrize("parameter", ["in_error", "ErrorCode"])
@pytest.mark.parametrize("availability,validation", [("missing", "structural"),
                                                     ("stale", "structural"),
                                                     ("unavailable", "structural"),
                                                     ("available", "invalid")])
@pytest.mark.parametrize("consumer", ["reader", "evaluate"])
def test_unusable_current_fact_cannot_establish_active_p1(
    parameter, availability, validation, consumer
):
    raw = _unit(isInError=True, settings=[{"name": "ErrorCode", "value": "P1"}])
    report = _poll(_report(), raw)
    fact = next(f for f in report["temporal_observations"][0]["facts"]
                if f["parameter"] == parameter)
    fact.update(availability=availability, validation=validation)
    # Schema 1 accepts these metadata combinations; both consumers must honor them.
    validate_report(report)
    if consumer == "reader":
        text = summarize(report)
        assert "Active P1 observed: false" in text
        if parameter == "in_error":
            assert "Active fault flag (samples): true=0, false=0, unknown=1" in text
        else:
            assert "Current interpretable error codes: none observed" in text
    else:
        result = evaluate(report)
        assert result["p1_investigation"]["active_p1_observed"] is False
        assert result["p1_investigation"]["first_p1_observed_at"] is None
        if parameter == "ErrorCode":
            assert result["p1_investigation"]["code_readable"] is False
