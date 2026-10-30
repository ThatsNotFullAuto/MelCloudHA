"""Read-only status, temperatures and fault history."""

from dataclasses import replace
from datetime import UTC, datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from .core.models import number
from .entity import DiagnosticEntity

STATUS = [
    ("error_code", "Codice errore"),
    ("operation_mode", "Stato operativo"),
    ("zone1_mode", "Zona 1 metodo regolazione"),
    ("zone2_mode", "Zona 2 metodo regolazione"),
    ("last_error", "Ultimo errore registrato"),
    ("last_error_reason", "Descrizione ultimo errore"),
    ("p1_30d", "P1 conosciuti negli ultimi 30 giorni"),
    ("history_status", "Disponibilità storico errori"),
    ("ftc_model", "Modello FTC dichiarato"),
]
TEMPERATURES = {
    "TankWaterTemperature": "Temperatura ACS",
    "SetTankWaterTemperature": "Setpoint ACS",
    "RoomTemperatureZone1": "Zona 1 temperatura ambiente",
    "SetTemperatureZone1": "Zona 1 setpoint",
    "RoomTemperatureZone2": "Zona 2 temperatura ambiente",
    "SetTemperatureZone2": "Zona 2 setpoint",
}
DESCRIPTIONS = (
    [SensorEntityDescription(key=k, name=n) for k, n in STATUS]
    + [
        SensorEntityDescription(
            key=k,
            name=n,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
        for k, n in TEMPERATURES.items()
    ]
    + [
        SensorEntityDescription(
            key="rssi",
            name="Segnale Wi-Fi",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        SensorEntityDescription(
            key="last_update",
            name="Ultima acquisizione cloud",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        ),
        SensorEntityDescription(
            key="last_error_at", name="Data ultimo errore", device_class=SensorDeviceClass.TIMESTAMP
        ),
        SensorEntityDescription(
            key="last_error_cleared",
            name="Data cessazione ultimo errore",
            device_class=SensorDeviceClass.TIMESTAMP,
        ),
    ]
)


ENUMS = {
    "operation_mode": [
        "Unknown",
        "Stop",
        "HotWater",
        "Heating",
        "Cooling",
        "FreezeStat",
        "LegionellaPrevention",
        "Heat",
        "HeatZones",
        "Cool",
    ],
    "zone1_mode": [
        "HeatRoomTemperature",
        "HeatFlowTemperature",
        "HeatCurve",
        "CoolRoomTemperature",
        "CoolFlowTemperature",
        "DryFloor",
    ],
    "zone2_mode": [
        "HeatRoomTemperature",
        "HeatFlowTemperature",
        "HeatCurve",
        "CoolRoomTemperature",
        "CoolFlowTemperature",
        "DryFloor",
    ],
    "history_status": ["available", "unavailable", "unsupported", "unknown"],
}
ICONS = {
    "error_code": "mdi:alert-circle-outline",
    "operation_mode": "mdi:heat-pump",
    "zone1_mode": "mdi:radiator",
    "zone2_mode": "mdi:radiator",
    "last_error": "mdi:history",
    "last_error_reason": "mdi:clipboard-text-outline",
    "p1_30d": "mdi:counter",
    "history_status": "mdi:database-outline",
    "ftc_model": "mdi:chip",
    "rssi": "mdi:wifi",
    "last_update": "mdi:update",
    "last_error_at": "mdi:calendar-clock",
    "last_error_cleared": "mdi:calendar-check",
}
DESCRIPTIONS = [replace(d, icon=ICONS.get(d.key, "mdi:thermometer")) for d in DESCRIPTIONS]
DESCRIPTIONS = [
    replace(
        d,
        device_class=SensorDeviceClass.ENUM,
        options=ENUMS[d.key],
        translation_key="zone_mode" if d.key.startswith("zone") else d.key,
    )
    if d.key in ENUMS
    else d
    for d in DESCRIPTIONS
]


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        entities = []
        for identifier, snapshot in coordinator.data.items():
            for description in DESCRIPTIONS:
                key = description.key
                if (
                    key.startswith("zone2") or key.endswith("Zone2")
                ) and "OperationModeZone2" not in snapshot.settings:
                    continue
                if (identifier, key) not in known:
                    known.add((identifier, key))
                    entities.append(DiagnosticSensor(coordinator, identifier, description))
        async_add_entities(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))


class DiagnosticSensor(DiagnosticEntity, SensorEntity):
    @property
    def native_value(self):
        snapshot = self.snapshot
        if snapshot is None:
            return None
        key = self.entity_description.key
        settings = snapshot.settings
        faults = self.coordinator.journal.faults(self.identifier)
        if key in TEMPERATURES:
            return number(settings.get(key))
        if key == "last_error":
            return faults[-1].code if faults else None
        if key == "last_error_at":
            return faults[-1].started if faults else None
        if key == "last_error_reason":
            return faults[-1].reason[:255] if faults else None
        if key == "last_error_cleared":
            return faults[-1].cleared if faults else None
        if key == "p1_30d":
            if not self.coordinator.journal.unit(self.identifier)["history_initialized"]:
                return None
            return self.coordinator.journal.p1_count(self.identifier, datetime.now(UTC))
        values = {
            "error_code": settings.get("ErrorCode"),
            "operation_mode": settings.get("OperationMode"),
            "zone1_mode": settings.get("OperationModeZone1"),
            "zone2_mode": settings.get("OperationModeZone2"),
            "history_status": self.coordinator.history_status.get(self.identifier, "unknown"),
            "ftc_model": snapshot.ftc_model,
            "rssi": snapshot.rssi,
            "last_update": snapshot.observed_at,
        }
        value = values.get(key)
        return value if key not in ENUMS or value in ENUMS[key] else None
