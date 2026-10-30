"""Backend boundaries reached by frontend actions, with synthetic data only."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.melcloud_diagnostics import _options_updated
from custom_components.melcloud_diagnostics.core.test_session import validate_report
from custom_components.melcloud_diagnostics.test_entities import SENSOR_DESCRIPTIONS
from custom_components.melcloud_diagnostics.test_entities import TestSensor as SessionSensor

from .conftest import UNIT
from .test_diagnostic_test_session import collection as _collection
from .test_diagnostic_test_session import idle, poll

collection = _collection


async def test_broken_session_manager_does_not_prevent_ordinary_options_reload():
    reload = AsyncMock()
    entry = SimpleNamespace(
        entry_id="synthetic",
        options={"allow_control": True},
        runtime_data=SimpleNamespace(
            gate=SimpleNamespace(invalidate=MagicMock()),
            test_manager=SimpleNamespace(
                invalidate_control_conditions=MagicMock(side_effect=RuntimeError("synthetic"))
            ),
        ),
    )
    await _options_updated(
        SimpleNamespace(config_entries=SimpleNamespace(async_reload=reload)), entry
    )
    reload.assert_awaited_once_with("synthetic")


async def test_permission_invalidation_is_durable_before_ha_reloads_entry(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)

    async def reload_entry(identifier):
        assert store.data["report"]["session"]["stop_reason"] == "control_permissions_changed"
        assert not manager.active

    entry = SimpleNamespace(
        entry_id="synthetic",
        options={"allow_control": True},
        runtime_data=SimpleNamespace(
            gate=SimpleNamespace(invalidate=MagicMock()), test_manager=manager
        ),
    )
    await _options_updated(
        SimpleNamespace(config_entries=SimpleNamespace(async_reload=reload_entry)), entry
    )


async def test_final_checkpoint_check_results_match_loaded_report(collection):
    manager, clock, store = collection
    await manager.async_start(UNIT, 1200, controls_enabled=False)
    clock.advance(1200)
    await manager._tick(clock.now())
    await manager._task
    assert store.data["report"]["verification_results"] == manager.data["verification_results"]
    assert (await manager.async_export())["verification_results"] == manager.data[
        "verification_results"
    ]


async def test_storage_fault_ui_check_counts_equal_exported_checks(collection, raw_unit):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    store.error = OSError("synthetic full disk")
    clock.advance(60)
    poll(manager, clock, raw_unit)
    await manager._task
    report = await manager.async_export()
    sensor = SessionSensor(
        manager, "entry", next(d for d in SENSOR_DESCRIPTIONS if d.key == "test_checks_failed")
    )
    assert sensor.native_value == sum(
        check["result"] == "FAIL" for check in report["verification_results"]
    )
    assert sensor.native_value >= 1


async def test_frontend_duration_is_minutes_while_report_keeps_seconds(collection):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    clock.advance(1500)
    sensors = {d.key: SessionSensor(manager, "entry", d) for d in SENSOR_DESCRIPTIONS}
    assert sensors["test_duration"].native_value == 60
    assert sensors["test_elapsed"].native_value == 25
    assert sensors["test_remaining"].native_value == 35
    assert sensors["test_remaining"].native_unit_of_measurement == "min"
    assert manager.data["session"]["duration_seconds"] == 3600


@pytest.mark.parametrize("reload_fails", [False, True])
async def test_control_permission_change_invalidates_session_even_when_reload_fails(
    collection, raw_unit, reload_fails
):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    gate = SimpleNamespace(invalidate=MagicMock())
    entry = SimpleNamespace(
        entry_id="synthetic",
        options={"allow_control": True},
        runtime_data=SimpleNamespace(gate=gate, test_manager=manager),
    )
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(
            async_reload=AsyncMock(
                side_effect=RuntimeError("synthetic reload failure") if reload_fails else None
            )
        )
    )
    if reload_fails:
        with pytest.raises(RuntimeError):
            await _options_updated(hass, entry)
    else:
        await _options_updated(hass, entry)
    assert not manager._accepting
    await manager._task
    gate.invalidate.assert_called_once()
    assert entry.options == {"allow_control": True}  # Never rewrite user permissions.
    report = await manager.async_export()
    assert report["session"]["status"] == "parziale"
    assert report["session"]["stop_reason"] == "control_permissions_changed"
    assert (
        next(
            check for check in report["verification_results"] if check["check"] == "test_conditions"
        )["result"]
        == "FAIL"
    )
    validate_report(report)


async def test_other_option_changes_preserve_ordinary_reload_and_session_report(
    collection, raw_unit
):
    manager, clock, _ = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    gate = SimpleNamespace(invalidate=MagicMock())

    async def reload_entry(identifier):
        await manager.async_close()

    entry = SimpleNamespace(
        entry_id="synthetic",
        options={"allow_control": False},
        runtime_data=SimpleNamespace(gate=gate, test_manager=manager),
    )
    await _options_updated(
        SimpleNamespace(config_entries=SimpleNamespace(async_reload=reload_entry)), entry
    )
    assert manager.data["session"]["status"] == "interrotto"
    assert manager.data["session"]["stop_reason"] == "reload_or_restart"


async def test_permission_invalidation_remains_visible_when_session_storage_also_fails(
    collection, raw_unit
):
    manager, clock, store = collection
    await manager.async_start(UNIT, controls_enabled=False)
    poll(manager, clock, raw_unit)
    await idle(manager)
    store.error = OSError("synthetic full disk")
    manager.invalidate_control_conditions()
    await manager._task
    report = await manager.async_export()
    assert report["session"]["stop_reason"] == "control_permissions_changed"
    assert report["acquisition"]["storage"] == "error"
    assert (
        next(c for c in report["verification_results"] if c["check"] == "test_conditions")["result"]
        == "FAIL"
    )
