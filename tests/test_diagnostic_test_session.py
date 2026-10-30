"""Real session state machine and storage on synthetic facts; no network or installation."""

import asyncio
import json
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.melcloud_diagnostics.button import StopTestButton
from custom_components.melcloud_diagnostics.config_flow import DiagnosticOptionsFlow
from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.core.test_session import validate_report
from custom_components.melcloud_diagnostics.dashboard import build_dashboard
from custom_components.melcloud_diagnostics.diagnostics import async_get_config_entry_diagnostics
from custom_components.melcloud_diagnostics.test_entities import SENSOR_DESCRIPTIONS
from custom_components.melcloud_diagnostics.test_entities import TestSensor as SessionSensor
from custom_components.melcloud_diagnostics.test_manager import DiagnosticTestManager
from custom_components.melcloud_diagnostics.test_manager import TestSessionError as SessionError
from custom_components.melcloud_diagnostics.test_manager import TestSessionStore as SessionStore

from .conftest import NOW, UNIT


class Clock:
    seconds = 0

    def now(self):
        return NOW + timedelta(seconds=self.seconds)

    def monotonic(self):
        return self.seconds

    def advance(self, seconds):
        self.seconds += seconds


class MemoryStore:
    def __init__(self):
        self.data = None
        self.saves = 0
        self.error = None
        self.entered = asyncio.Event()
        self.release = None

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        self.saves += 1
        self.entered.set()
        if self.release:
            await self.release.wait()
        if self.error:
            raise self.error
        self.data = deepcopy(data)


@pytest.fixture
async def collection(tmp_path):
    clock, store = Clock(), MemoryStore()
    hass = HomeAssistant(str(tmp_path))
    manager = DiagnosticTestManager(hass, store, now=clock.now, clock=clock.monotonic)
    yield manager, clock, store
    await manager.async_close()


def poll(
    manager, clock, raw, *, error=None, history_status="available", faults=None, statuses=None
):
    snapshot = Snapshot.parse(raw, clock.now()) if raw is not None else None
    manager.observe_poll(
        at=clock.now(),
        snapshots={UNIT: snapshot} if snapshot else {},
        events=[],
        histories={UNIT: faults or []},
        history_status={UNIT: history_status},
        history_checked={UNIT: clock.now()},
        error=error,
        http_statuses=statuses or [200],
    )


async def idle(manager):
    await asyncio.wait_for(manager._idle.wait(), 3)


async def test_start_progress_deadline_and_quality_are_distinct(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, 1200, controls_enabled=False)
    assert manager.progress == 0 and manager.remaining == 1200
    poll(manager, clock, raw_unit)
    await idle(manager)
    clock.advance(600)
    await manager._tick(clock.now())
    assert manager.progress == 50 and manager.remaining == 600
    saves = store.saves
    await manager._tick(clock.now())
    assert store.saves == saves  # timer never saves or polls
    clock.advance(600)
    await manager._tick(clock.now())
    await manager._task
    assert manager.progress == 100 and manager.status == "parziale"
    report = await manager.async_export()
    assert report["session"]["read_only"] is True
    assert (
        next(v for v in report["verification_results"] if v["check"] == "physical")["result"]
        == "UNKNOWN"
    )
    validate_report(report)


async def test_default_duration_duplicate_start_and_24h_refusal(collection):
    manager, _, _ = collection
    with pytest.raises(SessionError, match="controls_enabled"):
        await manager.async_start(UNIT)
    with pytest.raises(SessionError, match="invalid_duration"):
        await manager.async_start(UNIT, 86400, controls_enabled=False)
    await manager.async_start(UNIT, controls_enabled=False)
    assert manager.remaining == 3600
    with pytest.raises(SessionError, match="already_running"):
        await manager.async_start(UNIT, controls_enabled=False)


async def test_manual_stop_preserves_partial_and_explicit_replacement(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    clock.advance(90)
    button = StopTestButton(manager, "entry", "test_stop")
    await button.async_press()
    await manager._task
    assert manager.status == "interrotto" and manager.elapsed == 90
    assert store.data["report"]["temporal_observations"]
    with pytest.raises(SessionError, match="replace_required"):
        await manager.async_start(UNIT, controls_enabled=False)
    await manager.async_start(UNIT, controls_enabled=False, replace_previous=True)
    assert manager.data["acquisition"]["successful"] == 0


async def test_no_data_never_passes(collection):
    manager, clock, _ = collection
    await manager.async_start(UNIT, 1200, controls_enabled=False)
    clock.advance(1200)
    await manager._tick(clock.now())
    await manager._task
    assert manager.status == "parziale"
    checks = (await manager.async_export())["verification_results"]
    assert next(c for c in checks if c["check"] == "acquisition")["result"] == "INCONCLUSIVE"


async def test_ui_closure_does_not_own_task_and_controls_enabled_refused(collection, raw_unit):
    manager, clock, _ = collection
    flow = DiagnosticOptionsFlow()
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(
            test_manager=manager, data={UNIT: Snapshot.parse(raw_unit, NOW)}
        ),
        data={"unit_ids": [UNIT]},
        options={"allow_control": True},
    )
    flow.hass = MagicMock()
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    flow.handler = "entry"
    flow.flow_id = "flow"
    result = await flow.async_step_test_setup({"unit_id": UNIT, "duration": "1200"})
    assert result["errors"]["base"] == "test_controls_enabled"
    assert entry.options == {"allow_control": True} and not manager.active
    entry.options = {"allow_control": False}
    result = await flow.async_step_test_setup({"unit_id": UNIT, "duration": "1200"})
    assert result["step_id"] == "test_status" and manager.active
    del flow  # no wizard task owns the session
    clock.advance(60)
    poll(manager, clock, raw_unit)
    await idle(manager)
    assert manager.active and manager.data["acquisition"]["successful"] == 1


async def test_restart_interrupts_without_resuming_and_corrupt_store_is_local(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    saved = deepcopy(store.data)
    await manager.async_close()
    store.data = saved  # emulate abrupt restart from the last durable running checkpoint
    resumed = DiagnosticTestManager(manager.hass, store, now=clock.now, clock=clock.monotonic)
    await resumed.async_load()
    assert resumed.status == "interrotto" and resumed._task is None
    assert resumed.data["session"]["stop_reason"] == "reload_or_restart"
    assert resumed.data["acquisition"]["successful"] == 1
    corrupt = DiagnosticTestManager(
        manager.hass, AsyncMock(async_load=AsyncMock(side_effect=ValueError("synthetic")))
    )
    await corrupt.async_load()
    assert not corrupt.available and corrupt.status == "fallito"


async def test_new_entities_are_independent_and_dashboard_uses_resolved_ids(collection):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    clock.advance(1500)
    entities = {d.key: SessionSensor(manager, "entry", d) for d in SENSOR_DESCRIPTIONS}
    assert entities["test_progress"].native_value == 41.7
    assert entities["test_remaining"].native_value == 35
    ids = {key: "sensor.actual_" + key for key in entities}
    ids["test_stop"] = "button.actual_stop"
    config = build_dashboard({}, {}, ids)
    cards = [card for section in config["views"][0]["sections"] for card in section["cards"]]
    assert next(c for c in cards if c.get("entity") == ids["test_progress"])["features"] == [
        {"type": "bar-gauge", "min": 0, "max": 100}
    ]
    assert (
        next(c for c in cards if c.get("entity") == ids["test_stop"])["features"][0]["type"]
        == "button"
    )
    assert all(e.unique_id == "entry_" + key for key, e in entities.items())


async def test_session_report_replaces_unsafe_legacy_data_and_default_values_are_redacted(
    collection, raw_unit
):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poisoned = deepcopy(raw_unit)
    secret = "PRIVATE-person@example.com-SECRET"
    poisoned["givenDisplayName"] = secret
    poisoned["ftcModel"] = secret
    poisoned["settings"] += [{"name": "OperationMode", "value": secret}]
    # Replace duplicate setting rather than asking the ordinary parser to accept it.
    poisoned["settings"] = [s for s in poisoned["settings"] if s["name"] != "OperationMode"] + [
        {"name": "OperationMode", "value": secret}
    ]
    poisoned[secret] = {secret: [secret]}
    manager.capture_schema("account_context", {"buildings": [{"airToWaterUnits": [poisoned]}]})
    poll(manager, clock, poisoned)
    await idle(manager)
    entry = SimpleNamespace(
        runtime_data=SimpleNamespace(test_manager=manager, journal={secret: secret})
    )
    report = await async_get_config_entry_diagnostics(None, entry)
    text = json.dumps(report)
    assert secret not in text and UNIT not in text and "22.5" not in text
    assert "field_" in text and report["diagnostic_test"]["schema_inventory"]["fields"]
    validate_report(report["diagnostic_test"])


async def test_technical_values_require_consent_and_manual_comparison_is_separate(
    collection, raw_unit
):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False, export_values=True)
    poll(manager, clock, raw_unit)
    await idle(manager)
    values = {f["parameter"]: f["value"] for f in manager.data["temporal_observations"][0]["facts"]}
    assert values["RoomTemperatureZone1"] == 22.5
    await manager.async_stop()
    await manager._task
    await manager.async_compare("coerenti")
    checks = (await manager.async_export())["verification_results"]
    assert next(c for c in checks if c["check"] == "manual")["result"] == "PASS"
    assert next(c for c in checks if c["check"] == "physical")["result"] == "UNKNOWN"


async def test_session_store_has_separate_key_and_roundtrips_report(collection):
    manager, _, _ = collection
    store = SessionStore(manager.hass, "melcloud_diagnostics.diagnostic_test.synthetic")
    await manager.async_start(UNIT, controls_enabled=False)
    await store.async_save({"unit_id": UNIT, "report": manager.data})
    assert (await store.async_load())["report"] == manager.data
    assert "diagnostic_test" in store._store.path
