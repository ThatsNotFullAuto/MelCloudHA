"""Assert exact allowed HTTP operations without reaching the network."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.melcloud_diagnostics.core.cloud import (
    AuthenticationError,
    CloudError,
    CloudReader,
    HistoryUnsupported,
    SetpointWriter,
)
from custom_components.melcloud_diagnostics.core.models import DataError

from .conftest import NOW, UNIT


def session_for(body, status=200, headers=None):
    response = MagicMock(status=status, headers=headers or {})
    response.json = AsyncMock(return_value=body)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(request=MagicMock(return_value=context))


async def test_context_only_get(raw_unit, auth):
    session = session_for({"buildings": [{"airToWaterUnits": [raw_unit]}]})
    data = await CloudReader(session, auth).discover(NOW)
    assert data[UNIT].settings["SetTankWaterTemperature"] == "45"
    args, kwargs = session.request.call_args
    assert args == ("GET", "https://mobile.bff.melcloudhome.com/context")
    assert kwargs["allow_redirects"] is False
    assert kwargs["json"] is None


async def test_reader_cannot_write_or_access_arbitrary_endpoint(auth):
    session = session_for({})
    reader = CloudReader(session, auth)
    for path, writer in [
        (f"/monitor/atwunit/{UNIT}", True),
        ("/operational-data/request", False),
        ("https://example.com", False),
    ]:
        with pytest.raises(PermissionError):
            await reader._request(path, writer=writer)
    session.request.assert_not_called()


async def test_writer_exact_single_field_payload(auth):
    session = session_for(None, 204)
    writer = SetpointWriter(session, auth)
    await writer.write(UNIT, "SetTankWaterTemperature", 46, authorize=lambda: None)
    args, kwargs = session.request.call_args
    assert args == ("PUT", f"https://mobile.bff.melcloudhome.com/monitor/atwunit/{UNIT}")
    assert kwargs["json"] == {"setTankWaterTemperature": 46}
    with pytest.raises(ValueError):
        await writer.write(UNIT, "Reset", 1, authorize=lambda: None)
    assert session.request.call_count == 1


@pytest.mark.parametrize("identifier", ["../../reset", "https://example.com", "not-a-uuid"])
async def test_unit_id_path_injection_rejected(identifier, auth):
    session = session_for({})
    with pytest.raises(ValueError):
        await CloudReader(session, auth).history(identifier)
    session.request.assert_not_called()


@pytest.mark.parametrize(
    "status,error",
    [
        (401, AuthenticationError),
        (403, HistoryUnsupported),
        (404, HistoryUnsupported),
        (500, CloudError),
        (302, CloudError),
    ],
)
async def test_errors_are_not_empty_healthy_history(auth, status, error):
    with pytest.raises(error):
        await CloudReader(session_for([], status), auth).history(UNIT)


async def test_rate_limit_stops_next_request(auth):
    session = session_for({}, 429, {"Retry-After": "120"})
    reader = CloudReader(session, auth)
    for _ in range(2):
        with pytest.raises(CloudError):
            await reader.history(UNIT)
    assert session.request.call_count == 1


async def test_unknown_history_shape_not_empty(auth):
    with pytest.raises(DataError):
        await CloudReader(session_for({}), auth).history(UNIT)


async def test_gate_through_real_transport_sends_only_after_both_confirmations(raw_unit, auth):
    from custom_components.melcloud_diagnostics.core.control import ConfirmationGate

    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        if method == "PUT":
            for setting in raw_unit["settings"]:
                if setting["name"] == "SetTankWaterTemperature":
                    setting["value"] = kwargs["json"]["setTankWaterTemperature"]
            return session_for(None, 204).request.return_value
        return session_for(raw_unit).request.return_value

    session = MagicMock(request=MagicMock(side_effect=request))
    reader = CloudReader(session, auth)
    writer = SetpointWriter(session, auth, auth_lock=reader._auth_lock)
    gate = ConfirmationGate(reader, writer)
    proposal = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    assert all(c[0] == "GET" for c in calls)
    proposal = await gate.confirm_first(proposal.token, "flow-a")
    assert all(c[0] == "GET" for c in calls)
    assert await gate.execute(proposal.token, "flow-a") == "observed_requested_value"
    assert [c[0] for c in calls] == ["GET", "GET", "GET", "PUT", "GET"]
    assert calls[3][2] == {"setTankWaterTemperature": 46}


@pytest.mark.parametrize("invalidate", ["revoke", "expire"])
async def test_revocation_or_expiry_during_writer_auth_prevents_network_send(
    raw_unit, auth, invalidate
):
    from custom_components.melcloud_diagnostics.core.control import ConfirmationGate, ControlError

    now = [0]
    session = session_for(raw_unit)
    reader = CloudReader(session, auth)
    writer = SetpointWriter(session, auth, auth_lock=reader._auth_lock)
    records = []

    async def audit(record):
        records.append(record.copy())

    gate = ConfirmationGate(reader, writer, clock=lambda: now[0], audit=audit)
    proposal = await gate.propose("flow-a", UNIT, "SetTankWaterTemperature", 46)
    proposal = await gate.confirm_first(proposal.token, "flow-a")
    token_calls = 0

    async def token():
        nonlocal token_calls
        token_calls += 1
        if token_calls == 2:  # final read, then writer's authentication
            if invalidate == "revoke":
                gate.invalidate()
            else:
                now[0] = 121
        return "synthetic-token"

    auth.async_get_access_token.side_effect = token
    with pytest.raises(ControlError):
        await gate.execute(proposal.token, "flow-a")
    assert all(call.args[0] == "GET" for call in session.request.call_args_list)
    assert records[-1]["status"] == "cancelled_before_send"
