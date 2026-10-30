"""Non-expert support workflow and machine-readable report contract."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from custom_components.melcloud_diagnostics.config_flow import DiagnosticOptionsFlow
from custom_components.melcloud_diagnostics.core.control import ConfirmationGate
from custom_components.melcloud_diagnostics.support import support_envelope
from tools.read_support_report import summarize


async def test_guided_support_does_not_read_or_write_device(source):
    runtime = SimpleNamespace(gate=ConfirmationGate(source), support_context=None)
    entry = SimpleNamespace(runtime_data=runtime, options={"allow_control": False})
    flow = DiagnosticOptionsFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_get_known_entry.return_value = entry
    flow.handler = "entry"
    result = await flow.async_step_support()
    assert result["step_id"] == "support"
    result = await flow.async_step_support({"category": "error_history"})
    assert result["step_id"] == "support_ready"
    assert result["description_placeholders"]["reference"] == runtime.support_context["report_id"]
    assert runtime.support_context["problem_category"] == "error_history"
    assert runtime.gate.writer is None and not source.writes
    result = await flow.async_step_support_ready({})
    assert result["data"] == entry.options


def test_envelope_is_versioned_and_separates_findings_from_diagnosis():
    coordinator = SimpleNamespace(
        support_context={"report_id": "synthetic-reference", "problem_category": "error_history"},
        history_status={"internal-id": "unsupported"},
        last_success=None,
    )
    data = support_envelope(coordinator)
    assert data["schema_version"] == 1
    assert data["format"] == "melcloud_diagnostics.support"
    assert data["report_id"] == "synthetic-reference"
    assert "error_history_unsupported" in data["findings"]
    assert data["collection_mode"] == "read_only"
    assert "internal-id" not in str(data)


def test_maintainer_reader_accepts_native_ha_wrapper():
    context = SimpleNamespace(history_status={}, last_success=None)
    envelope = support_envelope(context)
    data = {
        "support": envelope,
        "versions": {"integration": "0.2.1"},
        "units": {},
        "transport_health": None,
    }
    assert summarize({"data": data}) == summarize(data)
    assert envelope["report_id"] in summarize(data)
