"""Boundary, privacy and lifecycle regression tests on synthetic observations."""

import asyncio
import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from custom_components.melcloud_diagnostics.core.models import DataError, Fault
from custom_components.melcloud_diagnostics.core.schema import validate_payload
from custom_components.melcloud_diagnostics.core.test_privacy import SchemaInspector
from custom_components.melcloud_diagnostics.core.test_session import validate_report
from custom_components.melcloud_diagnostics.test_entities import SENSOR_DESCRIPTIONS
from custom_components.melcloud_diagnostics.test_entities import TestSensor as SessionSensor
from custom_components.melcloud_diagnostics.test_manager import TestSessionStore as SessionStore

from .conftest import NOW, UNIT
from .test_diagnostic_test_session import collection as _collection
from .test_diagnostic_test_session import idle, poll

collection = _collection


async def test_duplicate_and_out_of_order_samples_are_not_new_acquisitions(collection, raw_unit):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    poll(manager, clock, raw_unit)
    await idle(manager)
    clock.advance(-60)
    poll(manager, clock, raw_unit)
    await idle(manager)
    assert manager.data["acquisition"]["successful"] == 1
    assert len(manager.data["temporal_observations"]) == 1


@pytest.mark.parametrize("placeholder", [None, "unknown", "unavailable", "", "null"])
async def test_missing_values_do_not_invent_changes_or_p1(collection, raw_unit, placeholder):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    changed = deepcopy(raw_unit)
    for field in changed["settings"]:
        if field["name"] in ("OperationModeZone1", "ErrorCode", "RoomTemperatureZone1"):
            field["value"] = placeholder
    clock.advance(60)
    poll(manager, clock, changed)
    await idle(manager)
    report = await manager.async_export()
    assert not report["p1_investigation"]["active_p1_observed"]
    assert report["configuration_observations"] == []
    for parameter in ("OperationModeZone1", "RoomTemperatureZone1"):
        assert report["decoded_parameters"][parameter]["changes"] == 0
        assert report["decoded_parameters"][parameter]["invalid"] == 0


async def test_p1_evidence_and_duplicate_history_without_assigning_sensor(collection, raw_unit):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    changed = deepcopy(raw_unit)
    changed["isInError"] = True
    next(f for f in changed["settings"] if f["name"] == "ErrorCode")["value"] = "P1"
    fault = Fault.parse({"timestamp": (NOW - timedelta(days=1)).isoformat(), "errorCode": "P1"})
    poll(manager, clock, changed, faults=[fault, fault])
    await idle(manager)
    clock.advance(60)
    poll(manager, clock, changed, faults=[fault])
    await idle(manager)
    report = await manager.async_export()
    p1 = report["p1_investigation"]
    assert p1["active_p1_observed"] and p1["historical_p1"] == 1
    assert p1["first_p1_observed_at"] == NOW.isoformat()
    assert p1["room_sensor_selection"] == p1["cause"] == "UNKNOWN"
    assert report["fault_history"]["duplicates"] == 2
    assert "TH1A" not in json.dumps(report)


async def test_three_timeouts_stop_only_session_and_unknown_error_is_redacted(collection):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    for error in ("TimeoutError", "TimeoutError", "private-token-in-exception"):
        poll(manager, clock, None, error=error, statuses=[])
        await idle(manager)
        clock.advance(60)
    await manager._task
    assert manager.status == "fallito"
    assert manager.data["session"]["stop_reason"] == "repeated_errors"
    assert "private-token" not in json.dumps(await manager.async_export())


async def test_timer_changes_only_local_states_and_never_saves(collection):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    entities = [SessionSensor(manager, "entry", description) for description in SENSOR_DESCRIPTIONS]
    removes = []
    for entity in entities:
        entity.async_write_ha_state = MagicMock()
        removes.append(manager.async_add_listener(entity._changed))
    await manager._tick(clock.now())
    for entity in entities:
        entity.async_write_ha_state.reset_mock()
    saved = store.saves
    for _ in range(10):
        await manager._tick(clock.now())
    assert sum(e.async_write_ha_state.call_count for e in entities) == 0
    clock.advance(30)
    await manager._tick(clock.now())
    assert (
        sum(e.async_write_ha_state.call_count for e in entities) == 3
    )  # progress, elapsed, remaining
    assert store.saves == saved
    for remove in removes:
        remove()


async def test_unload_removes_timer_listeners_and_worker(collection, raw_unit):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    manager.async_add_listener(MagicMock())
    old_task = manager._task
    await manager.async_close()
    assert old_task.done() and manager._task is None and manager._timer is None
    assert not manager._listeners and manager._queue.empty()
    assert manager.status == "interrotto"


async def test_session_file_rejects_unsafe_or_oversized_write_before_replacement(collection):
    manager, _, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    store = SessionStore(manager.hass, "melcloud_diagnostics.diagnostic_test.synthetic-faults")
    safe = {"unit_id": UNIT, "report": manager.data}
    await store.async_save(safe)
    broken = deepcopy(safe)
    broken["report"]["environment"]["python"] = "3.14.private-person@example.com"
    with pytest.raises(DataError):
        await store.async_save(broken)
    assert await store.async_load() == safe


def test_schema_type_changes_nulls_unknown_nested_keys_and_invalid_numbers(raw_unit):
    inspector = SchemaInspector(b"synthetic-private-key")
    secret = "private-email@example.com-secret-token"
    raw = deepcopy(raw_unit)
    raw[secret] = {secret: [secret]}
    raw["capabilities"][secret] = secret
    field = next(f for f in raw["settings"] if f["name"] == "RoomTemperatureZone1")
    for value, expected_type, invalid in [
        (None, "null", 0),
        ("unknown", "string", 0),
        ({secret: secret}, "object", 1),
        (True, "boolean", 1),
    ]:
        field["value"] = value
        frame = inspector.inspect(
            "account_context", {"buildings": [{"airToWaterUnits": [raw]}]}, UNIT
        )
        row = next(r for r in frame["rows"] if r["path"] == "settings[].RoomTemperatureZone1")
        assert row["types"] == {expected_type: 1} and row["invalid"] == invalid
        assert secret not in json.dumps(frame)


async def test_report_offline_validation_accepts_ha_download_wrapper_without_echoing_values(
    collection, raw_unit
):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False, export_values=True)
    poll(manager, clock, raw_unit)
    await idle(manager)
    report = await manager.async_export()
    result = validate_payload("report", {"data": {"diagnostic_test": report}})
    assert (
        result["schema_valid"]
        and result["units"][0]["parameters"]["RoomTemperatureZone1"] == "exposed"
    )
    assert "22.5" not in json.dumps(result)
    bad = deepcopy(report)
    bad["session"]["status"] = "PASS"
    with pytest.raises(DataError):
        validate_report(bad)
    assert not validate_payload("report", {"diagnostic_test": bad})["schema_valid"]


async def test_resource_limit_stops_before_unbounded_sample_growth(
    collection, raw_unit, monkeypatch
):
    manager, clock, _ = collection
    monkeypatch.setattr("custom_components.melcloud_diagnostics.core.test_session.MAX_SAMPLES", 2)
    await manager.async_start(UNIT, controls_enabled=False)
    for _ in range(3):
        poll(manager, clock, raw_unit)
        await idle(manager)
        clock.advance(60)
    await manager._task
    assert len(manager.data["temporal_observations"]) == 2
    assert manager.status == "parziale" and manager.data["session"]["stop_reason"] == "capacity"


async def test_storage_timeout_is_bounded_and_preserves_last_checkpoint(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    checkpoint = deepcopy(store.data)
    store.release = asyncio.Event()
    poll(manager, clock, raw_unit)
    await asyncio.wait_for(manager._task, 2.8)
    assert manager.storage_state == "error" and not manager.active
    assert store.data == checkpoint
    assert (await manager.async_export())["temporal_observations"]


async def test_cached_history_is_not_a_session_pass_and_storage_failure_is_explicit(
    collection, raw_unit
):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    from custom_components.melcloud_diagnostics.core.models import Snapshot

    manager.observe_poll(
        at=clock.now(),
        snapshots={UNIT: Snapshot.parse(raw_unit, clock.now())},
        events=[],
        histories={},
        history_status={UNIT: "available"},
        history_checked={UNIT: NOW - timedelta(minutes=5)},
        error=None,
        http_statuses=[200],
    )
    await idle(manager)
    report = await manager.async_export()
    assert report["fault_history"]["last_checked_at"] == (NOW - timedelta(minutes=5)).isoformat()
    assert (
        next(c for c in report["verification_results"] if c["check"] == "history")["result"]
        == "UNKNOWN"
    )
    await manager.async_stop()
    await manager._task
    store.error = OSError("synthetic disk error")
    await manager.async_compare("coerenti")
    report = await manager.async_export()
    assert (
        next(c for c in report["verification_results"] if c["check"] == "persistence")["result"]
        == "FAIL"
    )


async def test_history_schema_rejects_bad_timestamp_without_leaking_reason_or_nested_secrets(
    collection,
):
    manager, _, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    secret = "private-password-hidden-in-history"
    manager.capture_schema(
        "error_history",
        [
            {
                "timestamp": secret,
                "errorCode": "P1",
                "errorReason": secret,
                secret: [{secret: secret}],
            }
        ],
        UNIT,
    )
    await idle(manager)
    report = await manager.async_export()
    field = report["schema_inventory"]["fields"]["error_history.history[].timestamp"]
    assert field["invalid"] == 1 and secret not in json.dumps(report)
    assert (
        next(c for c in report["verification_results"] if c["check"] == "structure")["result"]
        == "FAIL"
    )
