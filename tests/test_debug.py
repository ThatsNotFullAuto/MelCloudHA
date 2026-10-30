"""Debug must explain request outcomes without disclosing authentication data."""

import json
import logging
from types import SimpleNamespace

import pytest

from custom_components.melcloud_diagnostics.core.cloud import CloudError, CloudReader
from custom_components.melcloud_diagnostics.core.control import ConfirmationGate
from custom_components.melcloud_diagnostics.core.health import DiagnosticHealth
from custom_components.melcloud_diagnostics.core.journal import Journal
from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.diagnostics import async_get_config_entry_diagnostics

from .conftest import NOW, UNIT
from .test_cloud import session_for


async def test_debug_logs_capture_status_and_time_without_payload_or_token(raw_unit, auth, caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.melcloud_diagnostics")
    raw_unit["email"] = "private-synthetic@example.com"
    raw_unit["password"] = "synthetic-secret-password"
    session = session_for(raw_unit)
    reader = CloudReader(session, auth)
    await reader.read_unit(UNIT, NOW)
    assert "unit_snapshot" in caplog.text and "http_status=200" in caplog.text
    assert "elapsed_ms=" in caplog.text
    for private in (
        "synthetic-token",
        "private-synthetic@example.com",
        "synthetic-secret-password",
        UNIT,
        "Synthetic Ecodan",
    ):
        assert private not in caplog.text
    health = reader.health.export()
    assert health["counters"]["unit_snapshot:success"] == 1
    assert health["recent_requests"][0]["status"] == "success"


async def test_failed_requests_report_safe_error_class_and_http_status(auth, caplog):
    caplog.set_level(logging.DEBUG, logger="custom_components.melcloud_diagnostics")
    reader = CloudReader(session_for({"token": "never-log-this"}, 500), auth)
    with pytest.raises(CloudError):
        await reader.history(UNIT)
    data = reader.health.export()
    assert data["last_http_status"]["error_history"] == 500
    assert data["recent_requests"][-1]["error_type"] == "CloudError"
    assert "never-log-this" not in caplog.text and UNIT not in caplog.text


def test_request_trace_is_bounded():
    health = DiagnosticHealth()
    for _ in range(110):
        health.record("unit_snapshot", "success", 1.2)
    data = health.export()
    assert len(data["recent_requests"]) == 100
    assert data["counters"]["unit_snapshot:success"] == 110


async def test_report_has_versions_transport_health_and_allowlisted_snapshot(raw_unit, auth):
    snapshot = Snapshot.parse(raw_unit, NOW)
    snapshot.settings["Password"] = "synthetic-secret"
    journal = Journal()
    journal.observe(snapshot)
    reader = CloudReader(session_for(raw_unit), auth)
    await reader.read_unit(UNIT, NOW)
    runtime = SimpleNamespace(
        journal=journal,
        history_status={UNIT: "available"},
        gate=ConfirmationGate(reader),
        reader=reader,
        data={UNIT: snapshot},
        last_success=NOW,
    )
    entry = SimpleNamespace(
        runtime_data=runtime,
        version=1,
        minor_version=1,
        data={"email": "private-synthetic@example.com", "password": "synthetic-secret"},
    )
    data = await async_get_config_entry_diagnostics(None, entry)
    assert data["versions"]["integration"] == "0.2.1"
    assert data["last_successful_poll"] == NOW.isoformat()
    assert data["transport_health"]["counters"]["unit_snapshot:success"] == 1
    assert (
        data["units"]["unit_1"]["current_observation"]["settings"]["TankWaterTemperature"] == "42"
    )
    text = json.dumps(data)
    for private in (
        UNIT,
        "private-synthetic@example.com",
        "synthetic-secret",
        "synthetic-token",
        "Password",
    ):
        assert private not in text


def test_manifest_enables_only_our_loggers():
    from pathlib import Path

    data = json.loads(
        Path("custom_components/melcloud_diagnostics/manifest.json").read_text(encoding="utf-8")
    )
    assert data["loggers"] == ["custom_components.melcloud_diagnostics"]
