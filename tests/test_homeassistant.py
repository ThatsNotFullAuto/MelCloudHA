"""Exercise Home Assistant flow/schema/entities/coordinator using synthetic acquisition."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant

from custom_components.melcloud_diagnostics.binary_sensor import (
    DESCRIPTIONS as BINARY_DESCRIPTIONS,
)
from custom_components.melcloud_diagnostics.binary_sensor import DiagnosticBinarySensor
from custom_components.melcloud_diagnostics.config_flow import DiagnosticOptionsFlow
from custom_components.melcloud_diagnostics.coordinator import DiagnosticCoordinator
from custom_components.melcloud_diagnostics.core.cloud import CloudError, HistoryUnsupported
from custom_components.melcloud_diagnostics.core.control import ConfirmationGate
from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.diagnostics import async_get_config_entry_diagnostics
from custom_components.melcloud_diagnostics.sensor import DESCRIPTIONS, DiagnosticSensor

from .conftest import NOW, UNIT


def options_flow(source, *, enabled=True):
    gate = ConfirmationGate(source, source if enabled else None)
    runtime = SimpleNamespace(
        gate=gate,
        reader=source,
        data={UNIT: Snapshot.parse(source.raw, NOW)},
        async_request_refresh=AsyncMock(),
    )
    entry = SimpleNamespace(runtime_data=runtime, options={"allow_control": enabled})
    flow = DiagnosticOptionsFlow()
    flow.hass = MagicMock()
    flow.hass.config.language = "it"
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    flow.handler = "test-entry"
    flow.flow_id = "test-flow"
    return flow, entry


async def prepare_change(flow):
    result = await flow.async_step_change({"unit_id": UNIT, "field": "SetTankWaterTemperature"})
    assert result["step_id"] == "value"
    assert result["description_placeholders"]["old"] == "45.0"
    return await flow.async_step_value({"value": 46})


async def test_real_ha_options_flow_requires_two_separate_explicit_submissions(source):
    flow, entry = options_flow(source)
    result = await prepare_change(flow)
    assert result["type"] == "form" and result["step_id"] == "confirm_first"
    assert result["data_schema"]({}) == {"confirm": False}
    assert not source.writes
    result = await flow.async_step_confirm_first({"confirm": True})
    assert result["step_id"] == "confirm_final"
    assert result["data_schema"]({}) == {"confirm": False}
    assert not source.writes
    result = await flow.async_step_confirm_final({"confirm": True})
    assert result["step_id"] == "result"
    assert len(source.writes) == 1
    entry.runtime_data.async_request_refresh.assert_awaited_once()


async def test_second_form_cannot_be_called_without_first(source):
    flow, _ = options_flow(source)
    await prepare_change(flow)
    assert (await flow.async_step_confirm_final({"confirm": True}))["type"] == "abort"
    assert not source.writes


@pytest.mark.parametrize("stage", ["confirm_first", "confirm_final"])
async def test_unchecked_confirmation_cancels(source, stage):
    flow, _ = options_flow(source)
    await prepare_change(flow)
    if stage == "confirm_final":
        await flow.async_step_confirm_first({"confirm": True})
    result = await getattr(flow, f"async_step_{stage}")({"confirm": False})
    assert result["reason"] == "cancelled"
    assert not source.writes


async def test_disabled_options_flow_never_proposes(source):
    flow, _ = options_flow(source, enabled=False)
    assert (await flow.async_step_change())["reason"] == "control_disabled"
    assert not source.writes


async def test_enabling_already_enabled_options_does_not_revoke_writer(source):
    flow, entry = options_flow(source)
    await flow.async_step_settings({"allow_control": True})
    assert entry.runtime_data.gate.writer is source
    await flow.async_step_settings({"allow_control": False})
    assert entry.runtime_data.gate.writer is None


async def test_polling_history_failure_persistence_and_entities(raw_unit, tmp_path):
    hass = HomeAssistant(str(tmp_path))
    reader = AsyncMock()
    reader.discover.return_value = {UNIT: Snapshot.parse(raw_unit, NOW)}
    reader.history.side_effect = HistoryUnsupported
    store = AsyncMock()
    coordinator = DiagnosticCoordinator(hass, None, reader, store, Journal())
    coordinator.data = await coordinator._async_update_data()
    assert coordinator.history_status[UNIT] == "unsupported"
    sensor = DiagnosticSensor(coordinator, UNIT, next(d for d in DESCRIPTIONS if d.key == "p1_30d"))
    assert sensor.native_value is None  # unavailable history is not zero errors
    error = DiagnosticBinarySensor(coordinator, UNIT, BINARY_DESCRIPTIONS[0])
    assert error.is_on is False
    coordinator.history_checked[UNIT] -= timedelta(minutes=16)
    reader.history.side_effect = None
    reader.history.return_value = []
    coordinator.data = await coordinator._async_update_data()
    assert sensor.native_value == 0
    store.async_save.assert_awaited()
    # Poll failure must fail coordinator update rather than fabricate healthy data.
    reader.discover.side_effect = CloudError("synthetic")
    from homeassistant.helpers.update_coordinator import UpdateFailed

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_diagnostics_do_not_export_credentials_ids_or_name(raw_unit):
    journal = Journal()
    journal.observe(Snapshot.parse(raw_unit, NOW))
    runtime = SimpleNamespace(journal=journal, history_status={}, gate=ConfirmationGate(None))
    entry = SimpleNamespace(
        data={"email": "private@example.com", "password": "secret"}, runtime_data=runtime
    )
    result = await async_get_config_entry_diagnostics(None, entry)
    text = str(result)
    assert "private@example.com" not in text and "secret" not in text
    assert UNIT not in text and "Synthetic Ecodan" not in text
    assert "unit_1" in result["units"]


async def test_only_selected_pumps_are_polled_for_history(raw_unit, tmp_path):
    from dataclasses import replace

    hass = HomeAssistant(str(tmp_path))
    snapshot = Snapshot.parse(raw_unit, NOW)
    other = replace(snapshot, id="22222222-2222-4222-8222-222222222222")
    reader = AsyncMock()
    reader.discover.return_value = {snapshot.id: snapshot, other.id: other}
    reader.history.return_value = []
    coordinator = DiagnosticCoordinator(hass, None, reader, AsyncMock(), Journal())
    coordinator.config_entry = SimpleNamespace(data={"unit_ids": [UNIT]})
    result = await coordinator._async_update_data()
    assert list(result) == [UNIT]
    reader.history.assert_awaited_once_with(UNIT)
