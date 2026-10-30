"""Distribution compatibility, native dashboard safety and upgrade contracts."""

import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.loader import Integration
from PIL import Image

from custom_components.melcloud_diagnostics import async_migrate_entry
from custom_components.melcloud_diagnostics.binary_sensor import DESCRIPTIONS as BINARY
from custom_components.melcloud_diagnostics.dashboard import build_dashboard
from custom_components.melcloud_diagnostics.sensor import DESCRIPTIONS as SENSORS

from .conftest import UNIT

COMPONENT = Path("custom_components/melcloud_diagnostics")


def test_homeassistant_recognizes_local_brand_images():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    integration = Integration(
        MagicMock(),
        "custom_components.melcloud_diagnostics",
        COMPONENT,
        manifest,
        {p.name for p in COMPONENT.iterdir()},
    )
    assert integration.has_branding
    for prefix in ("", "dark_"):
        for suffix, size in (("", 256), ("@2x", 512)):
            with Image.open(COMPONENT / "brand" / f"{prefix}icon{suffix}.png") as image:
                assert image.size == (size, size) and image.mode == "RGBA"
                assert image.getbbox() is not None


def test_every_entity_has_an_icon_and_existing_ids_remain_stable():
    assert all(d.icon and d.icon.startswith("mdi:") for d in [*SENSORS, *BINARY])
    expected = {
        "error_code",
        "operation_mode",
        "zone1_mode",
        "zone2_mode",
        "last_error",
        "p1_30d",
        "history_status",
        "ftc_model",
        "TankWaterTemperature",
        "SetTankWaterTemperature",
        "RoomTemperatureZone1",
        "SetTemperatureZone1",
        "RoomTemperatureZone2",
        "SetTemperatureZone2",
        "rssi",
        "last_update",
        "last_error_at",
    }
    assert expected <= {d.key for d in SENSORS}
    assert {
        "error",
        "connected",
        "Power",
        "ForcedHotWaterMode",
        "ProhibitHotWater",
        "control_enabled",
    } == {d.key for d in BINARY}


def test_dashboard_uses_only_resolved_ids_and_has_no_control_actions():
    resolved = {
        UNIT: {
            "error": "binary_sensor.custom_fault",
            "TankWaterTemperature": "sensor.custom_water",
            "last_error": "sensor.custom_last",
        }
    }
    config = build_dashboard({UNIT: "Pompa di casa"}, resolved)
    assert config["views"][0]["type"] == "sections"
    assert config["views"][0]["title"] == "Pompa di casa"
    entities = []

    def visit(value):
        if isinstance(value, dict):
            if "entity" in value:
                entities.append(value["entity"])
            assert value.get("type", "").startswith("custom:") is False
            assert value.get("action") not in ("perform-action", "call-service", "toggle")
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(config)
    assert set(entities) == set(resolved[UNIT].values())
    assert "Zone2" not in json.dumps(config)


async def test_config_migration_does_not_reset_account_permissions_or_selection():
    entry = SimpleNamespace(
        version=1,
        minor_version=0,
        data={"email": "synthetic@example.com", "password": "synthetic", "unit_ids": [UNIT]},
        options={"allow_control": True},
    )
    hass = MagicMock()
    before = (entry.data.copy(), entry.options.copy())
    assert await async_migrate_entry(hass, entry)
    hass.config_entries.async_update_entry.assert_called_once_with(entry, minor_version=1)
    assert (entry.data, entry.options) == before


async def test_future_config_schema_is_not_silently_downgraded():
    hass = MagicMock()
    assert not await async_migrate_entry(hass, SimpleNamespace(version=2, minor_version=0))
    hass.config_entries.async_update_entry.assert_not_called()


async def test_version_030_config_entry_needs_no_migration_or_data_change():
    entry = SimpleNamespace(
        version=1, minor_version=1,
        data={"email": "synthetic@example.invalid", "password": "synthetic", "unit_ids": [UNIT]},
        options={"allow_control": False},
    )
    hass = MagicMock()
    before = (entry.data.copy(), entry.options.copy())
    assert await async_migrate_entry(hass, entry)
    hass.config_entries.async_update_entry.assert_not_called()
    assert (entry.data, entry.options) == before


def test_hacs_release_contract_and_readme_installation():
    hacs = json.loads(Path("hacs.json").read_text(encoding="utf-8"))
    assert hacs["zip_release"] is True
    assert hacs["filename"] == "melcloud_diagnostics.zip"
    assert hacs["hide_default_branch"] is True
    assert hacs["homeassistant"] == "2026.10.4"
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["issue_tracker"].startswith("https://github.com/ThatsNotFullAuto/MelCloudHA/")


def test_build_isolated_hacs_package_contains_foundations_and_no_private_files(tmp_path):
    subprocess.run(
        [sys.executable, "tools/build_release.py", "--output-dir", str(tmp_path)], check=True,
        capture_output=True, text=True,
    )
    with zipfile.ZipFile(tmp_path / "melcloud_diagnostics.zip") as archive:
        paths = set(archive.namelist())
        assert {"core/telemetry.py", "core/capabilities.py", "core/cloud_telemetry.py"} <= paths
        assert "manifest.json" in paths and "LICENSE" in paths
        assert all(not p.startswith("custom_components/") for p in paths)
        assert all("__pycache__" not in p and not p.endswith((".apk", ".txt")) for p in paths)
    for line in (tmp_path / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split()
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest
