"""Local session entities; no dependency on cloud availability or control services."""

from dataclasses import replace
from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory

from .const import DOMAIN
from .core.test_session import REASONS, STATUSES

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="test_progress",
        name="Collaudo - Avanzamento",
        icon="mdi:progress-clock",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="test_elapsed",
        name="Collaudo - Tempo trascorso",
        icon="mdi:timer-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="test_remaining",
        name="Collaudo - Tempo residuo",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="test_duration",
        name="Collaudo - Durata prevista",
        icon="mdi:timer-cog-outline",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorEntityDescription(
        key="test_end",
        name="Collaudo - Fine prevista",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="test_status", name="Collaudo - Stato", icon="mdi:clipboard-pulse-outline"
    ),
    SensorEntityDescription(
        key="test_success", name="Collaudo - Acquisizioni riuscite", icon="mdi:counter"
    ),
    SensorEntityDescription(
        key="test_failed", name="Collaudo - Acquisizioni fallite", icon="mdi:alert-outline"
    ),
    SensorEntityDescription(
        key="test_last_acquisition",
        name="Collaudo - Ultima acquisizione",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key="test_history", name="Collaudo - Storico errori", icon="mdi:history"
    ),
    SensorEntityDescription(
        key="test_storage", name="Collaudo - Persistenza", icon="mdi:database-check-outline"
    ),
    SensorEntityDescription(
        key="test_cloud", name="Collaudo - Connessione cloud", icon="mdi:cloud-check-outline"
    ),
    SensorEntityDescription(
        key="test_quality", name="Collaudo - Qualità raccolta", icon="mdi:clipboard-check-outline"
    ),
    SensorEntityDescription(
        key="test_dropped", name="Collaudo - Osservazioni perse", icon="mdi:database-alert-outline"
    ),
    SensorEntityDescription(
        key="test_reason", name="Collaudo - Motivo di arresto", icon="mdi:information-outline"
    ),
    SensorEntityDescription(
        key="test_checks_passed", name="Collaudo - Controlli PASS", icon="mdi:check-circle-outline"
    ),
    SensorEntityDescription(
        key="test_checks_failed", name="Collaudo - Controlli FAIL", icon="mdi:alert-circle-outline"
    ),
    SensorEntityDescription(
        key="test_checks_unknown",
        name="Collaudo - Controlli non verificabili",
        icon="mdi:help-circle-outline",
    ),
]

# Keep persisted states/unique IDs stable; let HA render readable state labels.
ENUM_STATES = {
    "test_status": STATUSES,
    "test_reason": REASONS,
    "test_quality": ("inconcludente", "parziale", "raccolta_strutturale"),
    "test_cloud": ("unknown", "operativa", "unavailable"),
    "test_storage": ("regular", "pending", "error"),
    "test_history": ("available", "unavailable", "unsupported", "unknown"),
}
SENSOR_DESCRIPTIONS = [
    replace(
        description,
        device_class=SensorDeviceClass.ENUM,
        options=list(ENUM_STATES[description.key]),
        translation_key=description.key,
    )
    if description.key in ENUM_STATES
    else description
    for description in SENSOR_DESCRIPTIONS
]


class TestEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager, entry_id, key):
        self.manager = manager
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_diagnostic_test")},
            name="Collaudo diagnostico",
            manufacturer="MELCloud Diagnostics",
        )
        self._last_value = object()

    async def async_added_to_hass(self):
        self.async_on_remove(self.manager.async_add_listener(self._changed))

    def _changed(self):
        value = self.native_value if isinstance(self, SensorEntity) else self.available
        if self._last_value != value:
            self._last_value = value
            self.async_write_ha_state()


class TestSensor(TestEntity, SensorEntity):
    def __init__(self, manager, entry_id, description):
        super().__init__(manager, entry_id, description.key)
        self.entity_description = description

    @property
    def native_value(self):
        m = self.manager
        key = self.entity_description.key
        if key == "test_progress":
            return m.progress
        if key == "test_elapsed":
            return round(m.elapsed / 60, 1)
        if key == "test_remaining":
            return round(m.remaining / 60, 1)
        if key == "test_status":
            return m.status
        if key == "test_storage":
            return m.storage_state
        if m.data is None:
            return None
        data = m.data
        values = {
            "test_duration": data["session"]["duration_seconds"] // 60,
            "test_end": data["session"]["planned_end"],
            "test_success": data["acquisition"]["successful"],
            "test_failed": data["acquisition"]["failed"],
            "test_last_acquisition": data["acquisition"]["last_acquisition"],
            "test_history": data["fault_history"]["status"],
            "test_cloud": data["acquisition"]["cloud"],
            "test_dropped": m._dropped or data["acquisition"]["dropped"],
            "test_reason": m._reason or data["session"]["stop_reason"],
            "test_checks_passed": sum(c["result"] == "PASS" for c in data["verification_results"])
            if not m.active
            else None,
            "test_checks_failed": sum(c["result"] == "FAIL" for c in data["verification_results"])
            if not m.active
            else None,
            "test_checks_unknown": sum(
                c["result"] in ("UNKNOWN", "UNSUPPORTED", "INCONCLUSIVE")
                for c in data["verification_results"]
            )
            if not m.active
            else None,
            "test_quality": "inconcludente"
            if data["acquisition"]["successful"] < 2
            else "parziale"
            if data["session"]["status"] == "parziale"
            or m._dropped
            or data["acquisition"]["failed"]
            or data["acquisition"]["poll_errors"]
            or any(v["invalid"] for v in data["decoded_parameters"].values())
            else "raccolta_strutturale",
        }
        value = values.get(key)
        if key in ("test_end", "test_last_acquisition"):
            return datetime.fromisoformat(value) if value else None
        return value
