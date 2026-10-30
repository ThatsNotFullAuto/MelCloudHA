"""Fault injection proving collection cannot wait on or command the installation."""

import ast
import asyncio
import json
import threading
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.melcloud_diagnostics.coordinator import DiagnosticCoordinator
from custom_components.melcloud_diagnostics.core.cloud import CloudReader
from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.test_privacy import (
    MAX_SCHEMA_FIELDS,
    SchemaInspector,
)
from custom_components.melcloud_diagnostics.test_manager import QUEUE_SIZE, DiagnosticTestManager

from .conftest import UNIT
from .test_cloud import session_for
from .test_diagnostic_test_session import Clock, MemoryStore, idle


def ordinary(hass, raw_unit, clock):
    calls = []
    state = {"context_status": 200, "history_status": 200, "raw": raw_unit, "history": []}

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        history = url.endswith("errorlog")
        body = state["history"] if history else {"buildings": [{"airToWaterUnits": [state["raw"]]}]}
        status = state["history_status"] if history else state["context_status"]
        return session_for(body, status).request.return_value

    reader = CloudReader(
        MagicMock(request=MagicMock(side_effect=request)),
        AsyncMock(async_get_access_token=AsyncMock(return_value="synthetic-token")),
    )
    coordinator = DiagnosticCoordinator(hass, None, reader, MemoryStore(), Journal())
    return coordinator, calls, state


def clocks(monkeypatch, clock):
    monkeypatch.setattr(
        "custom_components.melcloud_diagnostics.coordinator.datetime",
        SimpleNamespace(now=lambda _: clock.now()),
    )
    monkeypatch.setattr(
        "custom_components.melcloud_diagnostics.core.cloud.time",
        SimpleNamespace(monotonic=clock.monotonic),
    )


async def test_simulated_hour_has_exactly_the_same_cloud_requests_and_journal(
    monkeypatch, tmp_path, raw_unit
):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    with_test, calls, _ = ordinary(hass, raw_unit, clock)
    baseline, normal_calls, _ = ordinary(hass, raw_unit, clock)
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    with_test.test_manager = manager
    with_test.reader.schema_observer = manager.capture_schema
    await manager.async_start(UNIT, controls_enabled=False)
    try:
        for minute in range(60):
            clock.seconds = minute * 60
            await baseline._async_update_data()
            await with_test._async_update_data()
            await idle(manager)
        clock.seconds = 3600
        await manager._tick(clock.now())
        await manager._task
        assert calls == normal_calls
        assert len(calls) == 64  # 60 context + history at minute 0/15/30/45
        assert all(method == "GET" and payload is None for method, _, payload in calls)
        assert (
            with_test.update_interval.total_seconds()
            == baseline.update_interval.total_seconds()
            == 60
        )
        assert with_test.journal.data == baseline.journal.data
        assert manager.data["acquisition"]["successful"] == 60
        assert manager.status == "completato" and manager.progress == 100, (
            manager.data["session"],
            manager.data["acquisition"],
            manager.data["fault_history"],
            manager.data["decoded_parameters"],
            manager.data["schema_inventory"]["truncated"],
        )
        assert len(json.dumps(await manager.async_export()).encode()) <= 1_048_576
    finally:
        await manager.async_close()


async def test_slow_export_does_not_hold_poll_lock_or_block_household_callbacks(
    monkeypatch, tmp_path, raw_unit
):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, _ = ordinary(hass, raw_unit, clock)
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    started, release = threading.Event(), threading.Event()
    from custom_components.melcloud_diagnostics.test_manager import evaluate

    def slow(report):
        started.set()
        release.wait(3)
        return evaluate(report)

    monkeypatch.setattr("custom_components.melcloud_diagnostics.test_manager.evaluate", slow)
    task = asyncio.create_task(manager.async_export())
    await hass.async_add_executor_job(started.wait, 1)
    household = []

    @callback
    def automation(event):
        household.append(True)

    remove = hass.bus.async_listen("synthetic_household", automation)
    try:
        hass.bus.async_fire("synthetic_household")
        await asyncio.wait_for(coordinator._async_update_data(), 0.5)
        await asyncio.sleep(0)
        assert household == [True] and len(calls) == 2
        assert not task.done()
    finally:
        release.set()
        await task
        remove()
        await manager.async_close()


async def test_slow_reducer_does_not_block_ordinary_sensor_listener(
    monkeypatch, tmp_path, raw_unit
):
    from custom_components.melcloud_diagnostics.sensor import DESCRIPTIONS, DiagnosticSensor
    from custom_components.melcloud_diagnostics.test_manager import apply_record

    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, state = ordinary(hass, raw_unit, clock)
    await coordinator.async_refresh()  # Normal setup precedes entity creation/session start.
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    entered, release = threading.Event(), threading.Event()

    def slow(*args):
        entered.set()
        release.wait(3)
        return apply_record(*args)

    monkeypatch.setattr("custom_components.melcloud_diagnostics.test_manager.apply_record", slow)
    sensor = DiagnosticSensor(
        coordinator, UNIT, next(d for d in DESCRIPTIONS if d.key == "TankWaterTemperature")
    )
    values = []

    @callback
    def ordinary_listener():
        values.append(sensor.native_value)

    remove = coordinator.async_add_listener(ordinary_listener)
    try:
        await coordinator.async_refresh()
        assert await hass.async_add_executor_job(entered.wait, 1)
        next(row for row in state["raw"]["settings"] if row["name"] == "TankWaterTemperature")[
            "value"
        ] = "43"
        clock.advance(60)
        await asyncio.wait_for(coordinator.async_refresh(), 0.5)
        assert values == [42.0, 43.0] and len(calls) == 4
    finally:
        release.set()
        await manager.async_close()
        remove()


async def test_full_queue_trips_only_collection_and_ordinary_updates_continue(
    monkeypatch, tmp_path, raw_unit
):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, _ = ordinary(hass, raw_unit, clock)
    store = MemoryStore()
    manager = DiagnosticTestManager(hass, store, now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    store.entered.clear()
    store.release = asyncio.Event()
    await coordinator._async_update_data()
    await store.entered.wait()
    for _ in range(QUEUE_SIZE + 2):
        clock.advance(60)
        await asyncio.wait_for(coordinator._async_update_data(), 0.5)
    assert not manager._accepting and manager._queue.qsize() <= QUEUE_SIZE
    assert manager._dropped >= 1 and coordinator.data[UNIT].settings["TankWaterTemperature"] == "42"
    store.release.set()
    await manager._task
    assert manager.status == "parziale" and manager.data["session"]["stop_reason"] == "queue_full"
    count = len(calls)
    clock.advance(60)
    await coordinator._async_update_data()
    assert len(calls) == count + 1
    await manager.async_close()


async def test_disk_full_breaks_collection_not_main_journal(monkeypatch, tmp_path, raw_unit):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, _ = ordinary(hass, raw_unit, clock)
    session_store = MemoryStore()
    manager = DiagnosticTestManager(hass, session_store, now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    session_store.error = OSError("synthetic disk full")
    await coordinator._async_update_data()
    await manager._task
    assert manager.storage_state == "error" and not manager.active
    assert manager.data["temporal_observations"]  # RAM partial remains exportable
    assert coordinator.store.data == coordinator.journal.data
    clock.advance(60)
    await coordinator._async_update_data()
    assert len(calls) == 3 and coordinator.data[UNIT].in_error is False
    assert (await manager.async_export())["session"]["stop_reason"] == "storage_error"
    await manager.async_close()


async def test_unexpected_processing_and_observer_exceptions_do_not_escape(
    monkeypatch, tmp_path, raw_unit
):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, _, _ = ordinary(hass, raw_unit, clock)
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)

    def broken(*args):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr("custom_components.melcloud_diagnostics.test_manager.apply_record", broken)
    await coordinator._async_update_data()
    await manager._task
    assert manager.status == "parziale"
    manager.observe_poll = broken
    clock.advance(60)
    await coordinator._async_update_data()
    assert coordinator.data[UNIT].in_error is False
    await manager.async_close()


@pytest.mark.parametrize("code", [401, 429, 500])
async def test_cloud_failure_never_causes_collection_retry(monkeypatch, tmp_path, raw_unit, code):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, state = ordinary(hass, raw_unit, clock)
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    state["context_status"] = code
    with pytest.raises((UpdateFailed, ConfigEntryAuthFailed)):
        await coordinator._async_update_data()
    await idle(manager)
    if code in (401, 429):
        await manager._task
        assert not manager.active
    assert len(calls) == 1
    assert all(method == "GET" for method, _, _ in calls)
    await manager.async_close()


@pytest.mark.parametrize("code", [403, 404])
async def test_inaccessible_history_is_explicit_and_does_not_break_entities(
    monkeypatch, tmp_path, raw_unit, code
):
    clock = Clock()
    clocks(monkeypatch, clock)
    hass = HomeAssistant(str(tmp_path))
    coordinator, calls, state = ordinary(hass, raw_unit, clock)
    manager = DiagnosticTestManager(hass, MemoryStore(), now=clock.now, clock=clock.monotonic)
    coordinator.test_manager = manager
    await manager.async_start(UNIT, controls_enabled=False)
    state["history_status"] = code
    await coordinator._async_update_data()
    await idle(manager)
    assert manager.data["fault_history"]["status"] == "unsupported"
    assert coordinator.data[UNIT].settings["TankWaterTemperature"] == "42" and len(calls) == 2
    await manager.async_close()


def test_manager_has_no_control_transport_or_refresh_imports():
    path = Path("custom_components/melcloud_diagnostics/test_manager.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {
        "SetpointWriter",
        "ConfirmationGate",
        "async_request_refresh",
        "write",
        "write_setpoint",
    }
    assert not any(
        isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(tree)
    )
    assert not any(isinstance(node, ast.Name) and node.id in forbidden for node in ast.walk(tree))


def test_unknown_schema_cardinality_is_bounded_and_names_never_escape(raw_unit):
    raw = deepcopy(raw_unit)
    raw["settings"] = [
        {"name": f"secret-email-{i}@example.com", "value": {"token": "private"}}
        for i in range(1000)
    ]
    inspector = SchemaInspector(b"synthetic-session-key")
    frame = inspector.inspect("account_context", {"buildings": [{"airToWaterUnits": [raw]}]}, UNIT)
    assert len(frame["rows"]) <= MAX_SCHEMA_FIELDS and len(inspector.aliases) <= MAX_SCHEMA_FIELDS
    assert frame["truncated"] > 0
    assert "secret-email" not in json.dumps(frame) and "private" not in json.dumps(frame)
