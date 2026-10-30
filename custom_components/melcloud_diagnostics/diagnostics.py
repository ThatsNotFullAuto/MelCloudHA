"""Export useful diagnostics without credentials, tokens or household identifiers."""


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
    commands = [
        {**item, "unit_id": aliases.get(item["unit_id"], "unknown")}
        for item in coordinator.journal.data["commands"]
    ]
    return {
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
