"""Exercise the actual command boundary, not just form fields."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from custom_components.melcloud_diagnostics.core.control import ConfirmationGate, ControlError

from .conftest import UNIT


async def confirmed(gate):
    proposal = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    return await gate.confirm_first(proposal.token, "flow-a")


async def test_read_only_by_default(source):
    gate = ConfirmationGate(source)
    with pytest.raises(ControlError):
        await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    assert not source.writes


async def test_two_confirmations_exact_one_write_and_replay_blocked(source):
    records = []

    async def audit(record):
        records.append(record.copy())

    gate = ConfirmationGate(source, source, audit=audit)
    first = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    assert not source.writes
    second = await gate.confirm_first(first.token, "flow-a")
    assert not source.writes
    assert second.token != first.token
    assert await gate.execute(second.token, "flow-a") == "observed_requested_value"
    assert source.writes == [(UNIT, "SetTankWaterTemperature", 46)]
    assert [r["status"] for r in records] == ["pending", "observed_requested_value"]
    with pytest.raises(ControlError):
        await gate.execute(second.token, "flow-a")
    assert len(source.writes) == 1


async def test_cannot_skip_first_confirmation(source):
    gate = ConfirmationGate(source, source)
    proposal = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    assert not source.writes


@pytest.mark.parametrize(
    "field,value",
    [
        ("Reset", 1),
        ("SetTankWaterTemperature", 61),
        ("SetTankWaterTemperature", float("nan")),
        ("SetTankWaterTemperature", True),
        ("SetTankWaterTemperature", 46.3),
        ("SetTemperatureZone2", 22),
    ],
)
async def test_unsupported_and_invalid_values(source, field, value):
    with pytest.raises(ControlError):
        await ConfirmationGate(source, source).propose("flow-a", UNIT, field, value)
    assert not source.writes


@pytest.mark.parametrize(
    "change", ["setpoint", "mode", "fault", "offline", "limits", "missing_increment"]
)
async def test_changes_since_first_confirmation_prevent_send(source, change):
    gate = ConfirmationGate(source, source)
    proposal = await confirmed(gate)
    if change == "setpoint":
        source.set("SetTankWaterTemperature", 44)
    if change == "mode":
        source.set("OperationModeZone1", "HeatFlowTemperature")
    if change == "fault":
        source.raw["isInError"] = True
    if change == "offline":
        source.raw["isConnected"] = False
    if change == "limits":
        source.raw["capabilities"]["maxSetTankTemperature"] = 55
    if change == "missing_increment":
        source.raw["capabilities"].pop("hasHalfDegrees")
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    assert not source.writes


async def test_flow_binding_expiry_and_disable(source):
    now = [0]
    gate = ConfirmationGate(source, source, clock=lambda: now[0])
    proposal = await confirmed(gate)
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "different-flow")
    proposal = await confirmed(gate)
    now[0] = 121
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    proposal = await confirmed(gate)
    gate.invalidate()
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    assert not source.writes


async def test_expiry_during_persist_does_not_send(source):
    now = [0]

    async def audit(record):
        now[0] = 121

    gate = ConfirmationGate(source, source, clock=lambda: now[0], audit=audit)
    proposal = await confirmed(gate)
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    assert not source.writes


async def test_unknown_outcome_never_retries(source):
    writer = AsyncMock()
    writer.write.side_effect = TimeoutError
    records = []

    async def audit(record):
        records.append(record.copy())

    gate = ConfirmationGate(source, writer, audit=audit)
    proposal = await confirmed(gate)
    with pytest.raises(TimeoutError):
        await gate.execute(proposal.token, "flow-a")
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    writer.write.assert_awaited_once()
    assert records[-1]["status"] == "outcome_unknown"


async def test_concurrent_final_confirmations_send_once(source):
    gate = ConfirmationGate(source, source)
    proposal = await confirmed(gate)
    results = await asyncio.gather(
        *(gate.execute(proposal.token, "flow-a") for _ in range(2)), return_exceptions=True
    )
    assert len(source.writes) == 1
    assert sum(isinstance(r, ControlError) for r in results) == 1


async def test_room_setpoint_cannot_change_flow_control(source):
    source.set("OperationModeZone1", "HeatFlowTemperature")
    with pytest.raises(ControlError):
        await ConfirmationGate(source, source).propose("flow-a", UNIT, "SetTemperatureZone1", 23)
    assert not source.writes


async def test_persistence_failure_prevents_send(source):
    audit = AsyncMock(side_effect=OSError("synthetic storage failure"))
    gate = ConfirmationGate(source, source, audit=audit)
    proposal = await confirmed(gate)
    with pytest.raises(OSError):
        await gate.execute(proposal.token, "flow-a")
    assert not source.writes


async def test_change_before_first_confirmation_requires_new_proposal(source):
    gate = ConfirmationGate(source, source)
    proposal = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    source.set("SetTankWaterTemperature", 44)
    with pytest.raises(ControlError):
        await gate.confirm_first(proposal.token, "flow-a")
    assert not source.writes
