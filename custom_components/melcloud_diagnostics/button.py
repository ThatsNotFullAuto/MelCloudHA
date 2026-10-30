"""Stop only local diagnostic collection. No Mitsubishi controls."""

from homeassistant.components.button import ButtonEntity

from .test_entities import TestEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(
        [StopTestButton(entry.runtime_data.test_manager, entry.entry_id, "test_stop")]
    )


class StopTestButton(TestEntity, ButtonEntity):
    _attr_name = "Collaudo - Interrompi collaudo"
    _attr_icon = "mdi:stop-circle-outline"

    @property
    def available(self):
        return self.manager.active and self.manager._accepting

    async def async_press(self):
        await self.manager.async_stop()
