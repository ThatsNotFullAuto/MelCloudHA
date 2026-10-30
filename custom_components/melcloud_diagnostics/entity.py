"""Common diagnostic entity."""

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class DiagnosticEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, identifier, description):
        super().__init__(coordinator)
        self.identifier = identifier
        self.entity_description = description
        self._attr_unique_id = f"{identifier}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=coordinator.data[identifier].name,
            manufacturer="Mitsubishi Electric",
            model="Ecodan (cloud diagnostics)",
        )

    @property
    def available(self):
        return super().available and self.identifier in self.coordinator.data

    @property
    def snapshot(self):
        return self.coordinator.data.get(self.identifier)

    @property
    def extra_state_attributes(self):
        if self.snapshot is None:
            return None
        return {
            "source": self.snapshot.source,
            "observed_at": self.snapshot.observed_at.isoformat(),
            "history_status": self.coordinator.history_status.get(self.identifier, "unknown"),
        }
