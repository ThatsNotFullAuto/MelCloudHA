from datetime import timedelta

import pytest

from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.models import DataError, Fault, Snapshot, number

from .conftest import NOW, UNIT


def fault(cleared=None):
    return Fault(NOW - timedelta(days=1), "P1", "Synthetic room sensor fault", cleared)


def test_history_deduplicates_clearing_and_survives_empty_response():
    journal = Journal()
    assert journal.merge_faults(UNIT, [fault()]) == []
    journal = Journal(journal.data)
    assert journal.merge_faults(UNIT, [fault(NOW)]) == []
    journal.merge_faults(UNIT, [])
    assert journal.p1_count(UNIT, NOW) == 1
    assert journal.faults(UNIT)[0].cleared == NOW
    assert len(journal.merge_faults(UNIT, [Fault(NOW, "P1", "", None)])) == 1


def test_observation_change_preserves_snapshot_and_deduplicates(raw_unit):
    journal = Journal()
    first = Snapshot.parse(raw_unit, NOW)
    assert journal.observe(first) == []
    raw_unit["isInError"] = True
    raw_unit["settings"].append({"name": "SetCoolFlowTemperatureZone1", "value": "11"})
    raw_unit["settings"] = [
        dict(i, value="P1") if i["name"] == "ErrorCode" else i for i in raw_unit["settings"]
    ]
    second = Snapshot.parse(raw_unit, NOW)
    events = journal.observe(second)
    assert len(events) == 1 and events[0]["type"] == "active_fault"
    assert events[0]["snapshot"]["TankWaterTemperature"] == "42"
    assert journal.observe(second) == []


def test_missing_values_stay_unknown(raw_unit):
    raw_unit.pop("isConnected")
    raw_unit.pop("isInError")
    raw_unit["settings"] = []
    parsed = Snapshot.parse(raw_unit, NOW)
    assert parsed.connected is None and parsed.in_error is None
    assert number(None) is None and number("nan") is None and number(True) is None


def test_ambiguous_dates_rejected_instead_of_guessing_timezone():
    with pytest.raises(DataError):
        Fault.parse({"timestamp": "2026-10-01T12:00:00", "errorCode": "P1"})
