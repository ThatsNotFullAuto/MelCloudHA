"""Wizard discovery tests never probe the real LAN or use actual credentials."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.melcloud_diagnostics.config_flow import DiagnosticConfigFlow
from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.discovery import (
    LocalHint,
    account_label,
    existing_accounts,
    relevant_device,
)

from .conftest import NOW, UNIT


def flow_for_test():
    flow = DiagnosticConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config.language = "it"
    flow.flow_id = "setup-flow"
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    return flow


async def test_welcome_does_not_contact_cloud_or_network():
    flow = flow_for_test()
    with (
        patch("custom_components.melcloud_diagnostics.config_flow.async_local_hints") as search,
        patch("custom_components.melcloud_diagnostics.config_flow.validate_credentials") as cloud,
    ):
        result = await flow.async_step_user()
    assert result["step_id"] == "user"
    search.assert_not_called()
    cloud.assert_not_called()


async def test_existing_account_reuse_device_selection_and_read_only_finish(raw_unit):
    flow = flow_for_test()
    account = SimpleNamespace(data={"email": "person@example.com", "password": "synthetic-secret"})
    units = {UNIT: Snapshot.parse(raw_unit, NOW)}
    with (
        patch(
            "custom_components.melcloud_diagnostics.config_flow.existing_accounts",
            return_value={"saved-account": account},
        ),
        patch(
            "custom_components.melcloud_diagnostics.config_flow.async_local_hints",
            new=AsyncMock(return_value=([LocalHint("Asgard", "mdns_candidate")], "completed")),
        ),
        patch(
            "custom_components.melcloud_diagnostics.config_flow.validate_credentials",
            new=AsyncMock(return_value=units),
        ) as connect,
    ):
        result = await flow.async_step_user({})
        assert result["step_id"] == "discovery"
        assert "synthetic-secret" not in str(result)
        assert "person@example.com" not in str(result)
        assert "Asgard" in result["description_placeholders"]["local_devices"]
        result = await flow.async_step_discovery({"account": "saved-account"})
        assert result["step_id"] == "units"
        assert "password" not in result.get("data_schema", {}).schema
        assert connect.await_args.args[1]["password"] == "synthetic-secret"
        result = await flow.async_step_units({"unit_ids": [UNIT]})
        assert result["step_id"] == "finish"
        assert result["description_placeholders"]["units"] == "Synthetic Ecodan"
        result = await flow.async_step_finish({})
        assert result["type"] == "create_entry"
        assert result["data"]["unit_ids"] == [UNIT]
        assert result["options"] == {"allow_control": False}


async def test_no_local_discovery_does_not_block_manual_cloud_account(raw_unit):
    flow = flow_for_test()
    with (
        patch(
            "custom_components.melcloud_diagnostics.config_flow.existing_accounts", return_value={}
        ),
        patch(
            "custom_components.melcloud_diagnostics.config_flow.async_local_hints",
            new=AsyncMock(return_value=([], "unavailable")),
        ),
        patch(
            "custom_components.melcloud_diagnostics.config_flow.validate_credentials",
            new=AsyncMock(return_value={UNIT: Snapshot.parse(raw_unit, NOW)}),
        ),
    ):
        result = await flow.async_step_user({})
        assert result["step_id"] == "discovery"
        result = await flow.async_step_discovery({"account": "manual"})
        assert result["step_id"] == "account"
        result = await flow.async_step_account(
            {"email": "synthetic@example.com", "password": "not-a-real-password"}
        )
        assert result["step_id"] == "units"


async def test_unit_selection_rejects_empty_or_unknown_units(raw_unit):
    flow = flow_for_test()
    flow._credentials = {"email": "synthetic@example.com", "password": "synthetic"}
    flow._units = {UNIT: Snapshot.parse(raw_unit, NOW)}
    for selected in [[], ["unknown"]]:
        result = await flow.async_step_units({"unit_ids": selected})
        assert result["errors"] == {"base": "select_unit"}


def test_account_search_only_uses_known_schema_and_masks_display():
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [
        SimpleNamespace(
            entry_id="valid", data={"email": "user@example.com", "password": "synthetic"}
        ),
        SimpleNamespace(entry_id="invalid", data={"username": "user", "token": "synthetic"}),
    ]
    assert list(existing_accounts(hass)) == ["valid"]
    assert account_label("user@example.com") == "u***@example.com"
    assert relevant_device("gekkekoe Ecodan")
    assert not relevant_device("kitchen lamp")


def test_italian_wizard_and_confirmation_copy_present():
    root = Path("custom_components/melcloud_diagnostics")
    en = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    it = json.loads((root / "translations/it.json").read_text(encoding="utf-8"))
    for language in (en, it):
        assert {"user", "discovery", "account", "units", "finish"} <= language["config"][
            "step"
        ].keys()
        assert {"change", "value", "confirm_first", "confirm_final", "result"} <= language[
            "options"
        ]["step"].keys()
    assert "SetTankWaterTemperature" not in json.dumps(it)
