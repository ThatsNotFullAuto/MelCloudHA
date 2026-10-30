"""Synthetic fault injection. No device, account, real HA deployment or network."""

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.file import WriteError

from custom_components.melcloud_diagnostics.const import DOMAIN
from custom_components.melcloud_diagnostics.coordinator import DiagnosticCoordinator
from custom_components.melcloud_diagnostics.core.cloud import AuthenticationError, CloudError
from custom_components.melcloud_diagnostics.core.control import ConfirmationGate
from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.models import DataError, Fault, Snapshot
from custom_components.melcloud_diagnostics.storage import JournalStorageError, JournalStore

from .conftest import NOW, UNIT


class Disk:
    def __init__(self, data=None):
        self.data = deepcopy(data)
        self.fail = None
        self.after_write = False
        self.entered = asyncio.Event()
        self.release = None

    async def async_save(self, data):
        self.entered.set()
        if self.release is not None:
            await self.release.wait()
        if self.fail and not self.after_write:
            raise self.fail
        self.data = json.loads(json.dumps(data))
        if self.fail:
            raise self.fail


def coordinator(tmp_path, raw, disk=None):
    reader = AsyncMock()
    reader.discover.return_value = {UNIT: Snapshot.parse(raw, NOW)}
    reader.history.return_value = []
    disk = disk if disk is not None else Disk()
    result = DiagnosticCoordinator(
        HomeAssistant(str(tmp_path)), None, reader, disk, Journal(disk.data)
    )
    # Keep actual HA coordinator initialization, replace only notification sink.
    result.hass = SimpleNamespace(bus=SimpleNamespace(async_fire=Mock()))
    return result


def active(raw):
    raw = deepcopy(raw)
    raw["isInError"] = True
    raw["settings"] = [{"name": "ErrorCode", "value": "P1"}]
    return raw


@pytest.mark.parametrize("failure", [OSError("synthetic"), TimeoutError("synthetic")])
async def test_failed_save_preserves_baseline_then_retries_identical_facts_before_cloud(
    tmp_path, raw_unit, failure
):
    c = coordinator(tmp_path, raw_unit)
    await c._async_update_data()
    before = deepcopy(c.journal.data)
    c.reader.discover.return_value = {
        UNIT: Snapshot.parse(active(raw_unit), NOW + timedelta(seconds=60))
    }
    c.store.fail = failure
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    assert c.journal.data == before == c.store.data
    assert c.data[UNIT].in_error is False and c._pending is not None
    c.hass.bus.async_fire.assert_not_called()
    # The machine might clear before the next poll: pending P1 must still be saved.
    c.reader.discover.side_effect = CloudError("synthetic outage")
    c.store.fail = None
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    events = c.journal.unit(UNIT)["observations"]
    assert len(events) == 1 and events[0]["code"] == "P1"
    assert events[0]["observed_at"] == (NOW + timedelta(seconds=60)).isoformat()
    assert c._pending is None and c.journal.data == c.store.data
    c.hass.bus.async_fire.assert_called_once()
    # Reload from disk must not replay a previously committed notification.
    restarted = coordinator(tmp_path, active(raw_unit), c.store)
    await restarted._async_update_data()
    restarted.hass.bus.async_fire.assert_not_called()
    assert len(restarted.journal.unit(UNIT)["observations"]) == 1


async def test_write_reaches_disk_then_raises_recovery_does_not_overwrite_committed_event(
    tmp_path, raw_unit
):
    c = coordinator(tmp_path, active(raw_unit))
    c.store.fail, c.store.after_write = OSError("uncertain acknowledgement"), True
    with pytest.raises(UpdateFailed):
        await c._async_update_data()
    persisted = deepcopy(c.store.data)
    assert len(persisted["units"][UNIT]["observations"]) == 1
    assert not c.journal.data["units"]
    c.store.fail = None
    await c.save()
    assert c.store.data == persisted == c.journal.data
    c.hass.bus.async_fire.assert_called_once()
    restarted = coordinator(tmp_path, active(raw_unit), c.store)
    await restarted._async_update_data()
    restarted.hass.bus.async_fire.assert_not_called()


async def test_cancel_during_disk_write_waits_for_commit_and_never_replays(tmp_path, raw_unit):
    c = coordinator(tmp_path, active(raw_unit))
    c.store.release = asyncio.Event()
    task = asyncio.create_task(c._async_update_data())
    await c.store.entered.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done() and not c.journal.data["units"]
    task.cancel()  # repeated cancellation cannot abandon an executor write
    c.store.release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert c._pending is None and c.journal.data == c.store.data
    assert len(c.journal.unit(UNIT)["observations"]) == 1
    c.hass.bus.async_fire.assert_called_once()
    restarted = coordinator(tmp_path, active(raw_unit), c.store)
    await restarted._async_update_data()
    restarted.hass.bus.async_fire.assert_not_called()


@pytest.mark.parametrize("failure", [AuthenticationError("synthetic"), asyncio.CancelledError()])
async def test_history_interruption_preserves_already_acquired_p1(tmp_path, raw_unit, failure):
    c = coordinator(tmp_path, active(raw_unit))
    c.reader.history.side_effect = failure
    expected = (
        asyncio.CancelledError
        if isinstance(failure, asyncio.CancelledError)
        else ConfigEntryAuthFailed
    )
    with pytest.raises(expected):
        await c._async_update_data()
    assert len(c.store.data["units"][UNIT]["observations"]) == 1
    assert c.last_poll_error["phase"] == "history"
    assert c.history_status[UNIT] == "unavailable"
    assert c.data[UNIT].in_error is True


async def test_cancel_during_discovery_changes_no_durable_state(tmp_path, raw_unit):
    c = coordinator(tmp_path, raw_unit)
    c.reader.discover.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await c._async_update_data()
    assert c.store.data is None and c._pending is None and not c.telemetry


async def test_concurrent_audit_is_not_lost_by_poll_commit(tmp_path, raw_unit):
    c = coordinator(tmp_path, active(raw_unit))
    entered, release = asyncio.Event(), asyncio.Event()

    async def history(_):
        entered.set()
        await release.wait()
        return []

    c.reader.history.side_effect = history
    task = asyncio.create_task(c._async_update_data())
    await entered.wait()
    record = {"unit_id": UNIT, "at": NOW.isoformat(), "status": "pending"}
    await c.audit(record)
    release.set()
    await task
    assert c.store.data["commands"] == [record]
    assert len(c.store.data["units"][UNIT]["observations"]) == 1


async def test_bus_failure_leaves_durable_record_and_reports_error_without_replay(
    tmp_path, raw_unit
):
    c = coordinator(tmp_path, active(raw_unit))
    c.hass.bus.async_fire.side_effect = RuntimeError("synthetic notification failure")
    await c._async_update_data()
    assert c.notification_errors == 1
    assert len(c.store.data["units"][UNIT]["observations"]) == 1
    await c._async_update_data()
    assert c.hass.bus.async_fire.call_count == 1


async def test_historical_notification_has_durable_evidence_and_acquisition_time(
    tmp_path, raw_unit
):
    c = coordinator(tmp_path, raw_unit)
    await c._async_update_data()
    c.history_checked[UNIT] -= timedelta(minutes=16)
    c.reader.history.return_value = [Fault(NOW - timedelta(days=1), "P1", "synthetic", None)] * 2
    await c._async_update_data()
    event = c.store.data["units"][UNIT]["observations"][0]
    assert event["type"] == "cloud_fault_added" and event["event_id"]
    assert event["timestamp"] != event["observed_at"]
    assert c.journal.p1_count(UNIT, NOW) == 1
    c.hass.bus.async_fire.assert_called_once()


@pytest.mark.parametrize("value", [None, "unknown", "unavailable", "", "NaN", True])
def test_unusable_setpoints_never_change_baseline_or_create_fault(raw_unit, value):
    journal = Journal()
    first = Snapshot.parse(raw_unit, NOW)
    journal.observe(first)
    altered = replace(
        first,
        observed_at=NOW + timedelta(seconds=60),
        settings=first.settings | {"SetTemperatureZone1": value, "OperationModeZone1": "unknown"},
        in_error=None,
    )
    assert journal.observe(altered) == []
    assert journal.observe(replace(first, observed_at=NOW + timedelta(seconds=120))) == []


def test_numeric_formatting_and_out_of_order_snapshots_are_not_configuration_changes(raw_unit):
    journal = Journal()
    first = Snapshot.parse(raw_unit, NOW)
    journal.observe(first)
    formatted = replace(
        first,
        observed_at=NOW + timedelta(seconds=60),
        settings=first.settings | {"SetTemperatureZone1": "21.00"},
    )
    assert journal.observe(formatted) == []
    assert (
        journal.observe(
            replace(
                first,
                observed_at=NOW - timedelta(seconds=60),
                settings=first.settings | {"SetTemperatureZone1": "25"},
            )
        )
        == []
    )
    assert journal.unit(UNIT)["previous"]["SetTemperatureZone1"] == "21.00"


@pytest.mark.parametrize(
    "data", [{}, [], {"units": {}, "commands": None}, {"units": {UNIT: {}}, "commands": []}]
)
def test_invalid_storage_never_becomes_empty_journal(data):
    with pytest.raises(DataError):
        Journal(data)


async def test_real_ha_store_detects_swallowed_write_errors_and_preserves_original(
    tmp_path, monkeypatch
):
    hass = HomeAssistant(str(tmp_path))
    store = JournalStore(hass, f"{DOMAIN}.synthetic")
    assert await store.async_load() is None
    initial = Journal().data
    await store.async_save(initial)
    path = Path(store._store.path)
    original = path.read_bytes()

    def fail(*args, **kwargs):
        raise WriteError("synthetic atomic failure")

    monkeypatch.setattr("homeassistant.helpers.storage.write_utf8_file_atomic", fail)
    changed = deepcopy(initial)
    changed["commands"].append({"unit_id": UNIT, "at": NOW.isoformat(), "status": "pending"})
    with pytest.raises(JournalStorageError):
        await store.async_save(changed)
    assert path.read_bytes() == original
    assert await JournalStore(hass, f"{DOMAIN}.synthetic").async_load() == initial


async def test_storage_deletion_and_corruption_are_not_silently_reinitialized(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    store = JournalStore(hass, f"{DOMAIN}.synthetic")
    data = Journal().data
    await store.async_save(data)
    path = Path(store._store.path)
    original = path.read_bytes()
    path.unlink()
    with pytest.raises(JournalStorageError):
        await store.async_load()
    with pytest.raises(JournalStorageError):
        await store.async_save(data)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(JournalStorageError):
        await JournalStore(hass, f"{DOMAIN}.synthetic").async_load()
    assert path.read_text() == "{broken"
    path.write_bytes(original)
    await store.async_save(data)
    assert await store.async_load() == data


async def test_storage_cannot_acknowledge_deferred_shutdown_write(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    store = JournalStore(hass, f"{DOMAIN}.synthetic")
    hass.set_state(CoreState.stopping)
    with pytest.raises(JournalStorageError):
        await store.async_save(Journal().data)


async def test_legacy_storage_envelope_and_added_facts_remain_readable_by_old_store(
    tmp_path, raw_unit
):
    hass = HomeAssistant(str(tmp_path))
    key = f"{DOMAIN}.synthetic"
    legacy = Store(hass, 1, key)
    journal = Journal()
    journal.observe(Snapshot.parse(raw_unit, NOW))
    # Simulate storage created before the optional observation watermark existed.
    journal.unit(UNIT).pop("previous_observed_at")
    await legacy.async_save(journal.data)
    upgraded = JournalStore(hass, key)
    restored = Journal(await upgraded.async_load())
    assert restored.observe(Snapshot.parse(raw_unit, NOW)) == []
    await upgraded.async_save(restored.data)
    assert await Store(hass, 1, key).async_load() == restored.data


async def test_incomplete_context_does_not_remove_durable_history_or_replay_p1(tmp_path, raw_unit):
    c = coordinator(tmp_path, active(raw_unit))
    await c._async_update_data()
    stored = deepcopy(c.journal.data)
    c.reader.discover.return_value = {}
    await c._async_update_data()
    assert not c.data and c.journal.data == stored
    c.reader.discover.return_value = {
        UNIT: Snapshot.parse(active(raw_unit), NOW + timedelta(minutes=1))
    }
    await c._async_update_data()
    c.hass.bus.async_fire.assert_called_once()


def test_legacy_fault_case_and_timezone_do_not_duplicate_or_lose_cleared_time(raw_unit):
    journal = Journal()
    fault = Fault.parse(
        {
            "timestamp": "2026-10-30T13:00:00+01:00",
            "errorCode": "p1",
            "clearedTimestamp": "2026-10-30T13:30:00+01:00",
        }
    )
    legacy_key = f"{fault.started.isoformat()}|p1"
    journal.unit(UNIT)["faults"][legacy_key] = fault.serialize()
    journal.unit(UNIT)["history_initialized"] = True
    assert journal.merge_faults(UNIT, [Fault(NOW, "P1", "synthetic", None)], NOW) == []
    assert list(journal.unit(UNIT)["faults"]) == [legacy_key]
    assert journal.faults(UNIT)[0].cleared is not None
    first = Snapshot.parse(active(raw_unit), NOW)
    journal.observe(first)
    journal.unit(UNIT)["previous"]["ErrorCode"] = "p1 "
    assert journal.observe(replace(first, observed_at=NOW + timedelta(minutes=1))) == []


async def test_confirmed_clear_and_new_p1_survive_restart_as_distinct_observations(
    tmp_path, raw_unit
):
    c = coordinator(tmp_path, active(raw_unit))
    await c._async_update_data()
    c.reader.discover.return_value = {UNIT: Snapshot.parse(raw_unit, NOW + timedelta(minutes=1))}
    await c._async_update_data()
    restarted = coordinator(tmp_path, active(raw_unit), c.store)
    restarted.reader.discover.return_value = {
        UNIT: Snapshot.parse(active(raw_unit), NOW + timedelta(minutes=2))
    }
    await restarted._async_update_data()
    records = restarted.journal.unit(UNIT)["observations"]
    assert len(records) == 2 and records[0]["event_id"] != records[1]["event_id"]


async def test_transactional_audit_failure_still_prevents_optional_writer(
    tmp_path, raw_unit, source
):
    c = coordinator(tmp_path, raw_unit)
    c.store.fail = OSError("synthetic storage outage")
    gate = ConfirmationGate(source, source, audit=c.audit)
    proposed = await gate.propose("synthetic", UNIT, "SetTankWaterTemperature", 46)
    confirmed = await gate.confirm_first(proposed.token, "synthetic")
    with pytest.raises(JournalStorageError):
        await gate.execute(confirmed.token, "synthetic")
    assert not source.writes
    c.store.fail = None
    await c.save()
    assert c.journal.data["commands"][0]["status"] == "pending"
    assert not source.writes and not gate.pending  # no automatic resume


async def test_normalized_view_preserves_existing_entity_ids_values_and_history(tmp_path, raw_unit):
    from custom_components.melcloud_diagnostics.binary_sensor import DESCRIPTIONS as BINARY
    from custom_components.melcloud_diagnostics.binary_sensor import DiagnosticBinarySensor
    from custom_components.melcloud_diagnostics.core.cloud_telemetry import cloud_observations
    from custom_components.melcloud_diagnostics.sensor import DESCRIPTIONS, DiagnosticSensor

    c = coordinator(tmp_path, raw_unit)
    c.config_entry = SimpleNamespace(options={"allow_control": False}, data={"unit_ids": [UNIT]})
    await c._async_update_data()
    sensors = [DiagnosticSensor(c, UNIT, description) for description in DESCRIPTIONS]
    binary = [DiagnosticBinarySensor(c, UNIT, description) for description in BINARY]

    def states():
        return (
            [(s.unique_id, s.native_value) for s in sensors],
            [(s.unique_id, s.is_on) for s in binary],
        )

    before = states(), deepcopy(c.data), deepcopy(c.journal.data)
    assert c.telemetry[UNIT] == cloud_observations(c.data[UNIT])
    assert (states(), c.data, c.journal.data) == before
    assert all(
        entity.unique_id == f"{UNIT}_{entity.entity_description.key}" for entity in sensors + binary
    )
    c.reader.read_unit.assert_not_awaited()


def test_missing_code_during_new_generic_fault_never_reuses_an_old_p1(raw_unit):
    journal = Journal()
    first = Snapshot.parse(active(raw_unit), NOW)
    journal.observe(first)
    journal.observe(
        replace(first, observed_at=NOW + timedelta(minutes=1), in_error=False, settings={})
    )
    events = journal.observe(
        replace(
            first, observed_at=NOW + timedelta(minutes=2), settings={"ErrorCode": "unavailable"}
        )
    )
    assert len(events) == 1 and events[0]["code"] is None
