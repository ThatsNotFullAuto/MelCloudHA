"""Ephemeral real HA frontend harness. Synthetic transport; no Mitsubishi networking."""

import argparse
import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
UNIT = "11111111-1111-4111-8111-111111111111"


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18123)
    parser.add_argument(
        "--install-requirements",
        action="store_true",
        help="Allow HA to install its development dependencies",
    )
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("Run this synthetic frontend harness under Linux or WSL")
    directory = ROOT / ".tools/frontend-ha"
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / "SYNTHETIC_DEMO_ONLY"
    if any(directory.iterdir()) and not marker.exists():
        raise RuntimeError("Refusing an existing non-demo directory")
    marker.write_text("Synthetic HA only; no real credentials or devices.\n")
    pid_file = directory / "server.pid"
    if pid_file.exists():
        try:
            os.kill(int(pid_file.read_text()), 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError("A demo process is already running; stop it before restarting")
    target = directory / "custom_components/melcloud_diagnostics"
    shutil.copytree(
        ROOT / "custom_components/melcloud_diagnostics",
        target,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    sys.path.insert(0, str(directory))
    from homeassistant import bootstrap, loader
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, SupportsResponse

    import custom_components.melcloud_diagnostics.config_flow as flow_module
    import custom_components.melcloud_diagnostics.coordinator as coordinator_module
    from custom_components.melcloud_diagnostics.core.cloud import CloudReader, operation_name
    from custom_components.melcloud_diagnostics.dashboard import dashboard_for_entry
    from custom_components.melcloud_diagnostics.test_manager import DiagnosticTestManager

    offset = 0
    calls = []

    def now(*_):
        return datetime.now(UTC) + timedelta(seconds=offset)

    original_manager_init = DiagnosticTestManager.__init__

    def demo_manager_init(manager, hass, store, **kwargs):
        kwargs.update(now=now, clock=lambda: time.monotonic() + offset)
        original_manager_init(manager, hass, store, **kwargs)

    DiagnosticTestManager.__init__ = demo_manager_init

    coordinator_module.datetime = SimpleNamespace(now=now)

    async def no_local_discovery(*_):
        return [], "unavailable"

    flow_module.async_local_hints = no_local_discovery

    raw = {
        "id": UNIT,
        "givenDisplayName": "Ecodan demo (dati sintetici)",
        "isConnected": True,
        "isInError": False,
        "ftcModel": "FTC7",
        "rssi": -60,
        "capabilities": {"hasHotWater": True, "hasZone2": False},
        "settings": [
            {"name": k, "value": v}
            for k, v in {
                "Power": "True",
                "OperationMode": "Heating",
                "OperationModeZone1": "HeatRoomTemperature",
                "RoomTemperatureZone1": "22.5",
                "SetTemperatureZone1": "21",
                "TankWaterTemperature": "42",
                "SetTankWaterTemperature": "45",
                "ErrorCode": "",
            }.items()
        ],
    }

    async def synthetic_request(reader, path, *, payload=None, writer=False, authorize=None):
        if writer or payload is not None:
            raise PermissionError("Synthetic frontend harness rejects ALL operational writes")
        if path not in (
            "/context",
            f"/monitor/atwunit/{UNIT}",
            f"/monitor/atwunit/{UNIT}/errorlog",
        ):
            raise PermissionError("Synthetic endpoint not allowlisted")
        calls.append(
            {
                "method": "GET",
                "path": "context"
                if path == "/context"
                else "history"
                if path.endswith("errorlog")
                else "unit",
            }
        )
        reader.health.http_statuses[operation_name(path, False)] = 200
        return (
            {"buildings": [{"airToWaterUnits": [raw]}]}
            if path == "/context"
            else []
            if path.endswith("errorlog")
            else raw
        )

    CloudReader._perform_request = synthetic_request
    # All cloud transport, including inherited writer transport, is intercepted above.
    storage = directory / ".storage"
    storage.mkdir(exist_ok=True)
    (storage / "onboarding").write_text(
        json.dumps(
            {
                "version": 4,
                "minor_version": 1,
                "key": "onboarding",
                "data": {"done": ["user", "core_config", "integration", "analytics"]},
            }
        )
    )
    config = {
        "homeassistant": {
            "name": "HA demo sintetica",
            "latitude": 0,
            "longitude": 0,
            "elevation": 0,
            "unit_system": "metric",
            "time_zone": "Europe/Rome",
            "country": "IT",
        },
        "http": {"server_host": "127.0.0.1", "server_port": args.port},
        "frontend": {},
        "config": {},
        "lovelace": {"mode": "yaml"},
        "logger": {"default": "warning"},
        "history": {},
        "recorder": {"purge_keep_days": 1, "commit_interval": 30},
    }
    (directory / "configuration.yaml").write_text(
        "# Synthetic frontend harness; launched programmatically.\n"
    )
    (directory / "ui-lovelace.yaml").write_text("title: Demo sintetica\nviews: []\n")
    hass = HomeAssistant(str(directory))
    hass.config.skip_pip = not args.install_requirements
    loader.async_setup(hass)
    # Confirm this harness's explicit loopback config before opening the listener.
    from homeassistant.components.http.config import async_get_and_load_store

    http_store = await async_get_and_load_store(hass)
    await http_store.async_migrate_yaml(config["http"])
    if http_store.pending is not None:
        await http_store.async_promote_pending()
    if await bootstrap.async_from_config_dict(config, hass) is None:
        raise RuntimeError("HA bootstrap failed")
    users = await hass.auth.async_get_users()
    user = next((u for u in users if u.name == "Demo"), None)
    if user is None:
        user = await hass.auth.async_create_user(
            "Demo", group_ids=["system-admin"], local_only=True
        )
    refresh = await hass.auth.async_create_refresh_token(
        user, client_id=f"http://127.0.0.1:{args.port}/"
    )
    access = hass.auth.async_create_access_token(refresh)
    # Private local fixture. Never print this material or copy it into screenshots/repository.
    (directory / "browser-auth.json").write_text(
        json.dumps(
            {
                "hassUrl": f"http://127.0.0.1:{args.port}",
                "clientId": f"http://127.0.0.1:{args.port}/",
                "access_token": access,
                "refresh_token": refresh.token,
                "expires_in": 1800,
                "expires": int(time.time() * 1000) + 1800000,
                "token_type": "Bearer",
            }
        )
    )
    entries = hass.config_entries.async_entries("melcloud_diagnostics")
    if entries:
        entry = entries[0]
    else:
        entry = ConfigEntry(
            version=1,
            minor_version=1,
            domain="melcloud_diagnostics",
            title="Ecodan demo sintetica",
            data={
                "email": "demo@example.invalid",
                "password": "synthetic-only",
                "unit_ids": [UNIT],
            },
            options={"allow_control": False},
            source="user",
            unique_id="synthetic-frontend-demo",
            discovery_keys=MappingProxyType({}),
            subentries_data=None,
        )
        await hass.config_entries.async_add(entry)
    if not hasattr(entry, "runtime_data"):
        raise RuntimeError("Synthetic integration did not load")
    dashboard = dashboard_for_entry(hass, entry)
    dashboard["title"] = "Ecodan demo - dati sintetici"
    for view in dashboard["views"]:
        view["title"] += " (demo)"
        if view["path"] == "diagnostica":
            view["sections"][0]["cards"][0]["heading"] += " - dati sintetici"
    (directory / "ui-lovelace.yaml").write_text(json.dumps(dashboard, ensure_ascii=True, indent=2))

    async def demo_control(call):
        nonlocal offset
        manager = entry.runtime_data.test_manager
        action = call.data.get("action", "inspect")
        if action == "advance":
            count = min(60, max(0, int(call.data.get("minutes", 1))))
            for _ in range(count):
                offset += 60
                await entry.runtime_data.async_refresh()
                if manager.active:
                    await asyncio.wait_for(manager._idle.wait(), 4)
            await manager._tick(now())
        elif action == "partial":
            manager._request_stop("queue_full")
            await manager._task
        elif action == "storage_failure":

            async def broken_save(data):
                raise OSError("Synthetic storage fault")

            manager.store.async_save = broken_save
        elif action != "inspect":
            raise ValueError("Unknown synthetic action")
        return {
            "synthetic": True,
            "status": manager.status,
            "progress": manager.progress,
            "get_calls": len(calls),
            "calls": calls,
            "entry_id": entry.entry_id,
            "now": now().isoformat(),
        }

    hass.services.async_register(
        "frontend_demo", "control", demo_control, supports_response=SupportsResponse.ONLY
    )
    from homeassistant.helpers.service import async_set_service_schema

    async_set_service_schema(
        hass, "frontend_demo", "control", {"name": "Synthetic test driver", "fields": {}}
    )
    await hass.async_start()
    (directory / "server.pid").write_text(str(os.getpid()))
    (directory / "ready.json").write_text(
        json.dumps(
            {"ready": True, "port": args.port, "entry_id": entry.entry_id, "synthetic": True}
        )
    )
    print("Synthetic HA frontend ready on loopback. No Mitsubishi account/network.", flush=True)
    done = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, done.set)
    try:
        await done.wait()
    finally:
        hass.auth.async_remove_refresh_token(refresh)
        (directory / "browser-auth.json").unlink(missing_ok=True)
        (directory / "ready.json").unlink(missing_ok=True)
        await hass.async_stop()
        pid_file.unlink(missing_ok=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
