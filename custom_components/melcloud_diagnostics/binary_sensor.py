"""Binary observations, preserving unknowns."""

from dataclasses import replace

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .const import ALLOW_CONTROL
from .core.models import boolean
from .entity import DiagnosticEntity

DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="error", name="Errore attivo", device_class=BinarySensorDeviceClass.PROBLEM
    ),
    BinarySensorEntityDescription(
        key="connected",
        name="Connessione unità al cloud",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
    ),
    BinarySensorEntityDescription(key="Power", name="Abilitazione macchina"),
    BinarySensorEntityDescription(key="ForcedHotWaterMode", name="Forzatura ACS"),
    BinarySensorEntityDescription(key="ProhibitHotWater", name="ACS inibita"),
    BinarySensorEntityDescription(
        key="control_enabled", name="Modifiche abilitate", entity_category=EntityCategory.DIAGNOSTIC
    ),
]


ICONS = {
    "error": "mdi:alert-circle-outline",
    "connected": "mdi:cloud-check-outline",
    "Power": "mdi:power",
    "ForcedHotWaterMode": "mdi:water-boiler",
    "ProhibitHotWater": "mdi:water-off",
    "control_enabled": "mdi:shield-lock-outline",
}
DESCRIPTIONS = [replace(d, icon=ICONS[d.key]) for d in DESCRIPTIONS]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        entities = []
        for identifier in coordinator.data:
            if identifier not in known:
                known.add(identifier)
                entities.extend(
                    DiagnosticBinarySensor(coordinator, identifier, d) for d in DESCRIPTIONS
                )
        async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class DiagnosticBinarySensor(DiagnosticEntity, BinarySensorEntity):
    @property
    def is_on(self):
        snapshot = self.snapshot
        if snapshot is None:
            return None
        key = self.entity_description.key
        if key == "error":
            return snapshot.in_error
        if key == "connected":
            return snapshot.connected
        if key == "control_enabled":
            return self.coordinator.config_entry.options.get(ALLOW_CONTROL, False)
        return boolean(snapshot.settings.get(key))
