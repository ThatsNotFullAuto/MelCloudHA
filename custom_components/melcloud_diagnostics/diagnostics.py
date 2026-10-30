"""Export useful diagnostics without credentials, tokens or household identifiers."""

from importlib.metadata import version
from platform import python_version

from .const import VERSION
from .core.journal import OBSERVED
from .support import support_envelope


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    units = {}
    aliases = {
        identifier: f"unit_{i + 1}"
        for i, identifier in enumerate(coordinator.journal.data["units"])
    }
    for identifier, saved in coordinator.journal.data["units"].items():
        observations = [
            {k: v for k, v in item.items() if k != "unit_id"} for item in saved["observations"]
        ]
        units[aliases[identifier]] = {
            "faults": list(saved["faults"].values()),
            "observations": observations,
            "history_status": coordinator.history_status.get(identifier, "unknown"),
        }
        snapshot = getattr(coordinator, "data", {}).get(identifier)
        if snapshot:
            units[aliases[identifier]]["current_observation"] = {
                "observed_at": snapshot.observed_at.isoformat(),
                "source": snapshot.source,
                "connected": snapshot.connected,
                "in_error": snapshot.in_error,
                "ftc_model": snapshot.ftc_model,
                "settings": {
                    key: snapshot.settings[key] for key in OBSERVED if key in snapshot.settings
                },
                "capabilities": {
                    key: snapshot.capabilities.get(key)
                    for key in (
                        "hasHotWater",
                        "hasZone2",
                        "hasHalfDegrees",
                        "temperatureIncrement",
                        "minSetTankTemperature",
                        "maxSetTankTemperature",
                        "minSetTemperature",
                        "maxSetTemperature",
                    )
                },
            }
    commands = [
        {**item, "unit_id": aliases.get(item["unit_id"], "unknown")}
        for item in coordinator.journal.data["commands"]
    ]
    return {
        "support": support_envelope(coordinator),
        "versions": {
            "integration": VERSION,
            "homeassistant": version("homeassistant"),
            "aiomelcloudhome": version("aiomelcloudhome"),
            "python": python_version(),
        },
        "config_schema": {
            "version": getattr(entry, "version", None),
            "minor_version": getattr(entry, "minor_version", None),
        },
        "acquisition_state": {
            "last_attempt": coordinator.last_poll_attempt.isoformat()
            if getattr(coordinator, "last_poll_attempt", None)
            else None,
            "last_error": getattr(coordinator, "last_poll_error", None),
        },
        "last_successful_poll": coordinator.last_success.isoformat()
        if getattr(coordinator, "last_success", None)
        else None,
        "transport_health": coordinator.reader.health.export()
        if getattr(coordinator, "reader", None)
        else None,
        "units": units,
        "commands": commands,
        "source": "melcloud_home",
        "control_enabled": coordinator.gate.writer is not None,
        "limitations": [
            "Cloud history may be incomplete",
            "Observed settings are not commissioning settings",
            "Account token is not server-enforced read-only",
        ],
    }
