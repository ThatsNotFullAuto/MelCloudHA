"""MELCloud Diagnostics. No device commands are sent during setup or polling."""

from .const import ALLOW_CONTROL, DOMAIN, PLATFORMS


async def async_setup_entry(hass, entry):
    from aiomelcloudhome import MelCloudHomeAuth
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.storage import Store

    from .coordinator import DiagnosticCoordinator
    from .core.cloud import CloudReader, SetpointWriter
    from .core.control import ConfirmationGate
    from .core.journal import Journal

    session = async_get_clientsession(hass)
    auth = MelCloudHomeAuth(entry.data["email"], entry.data["password"], session=session)
    reader = CloudReader(session, auth)
    store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
    coordinator = DiagnosticCoordinator(
        hass, entry, reader, store, Journal(await store.async_load())
    )
    writer = (
        SetpointWriter(session, auth, auth_lock=reader._auth_lock)
        if entry.options.get(ALLOW_CONTROL, False)
        else None
    )
    coordinator.gate = ConfirmationGate(reader, writer, audit=coordinator.audit)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _options_updated(hass, entry):
    # Revoke outstanding approvals immediately, even if reload fails.
    entry.runtime_data.gate.invalidate()
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    entry.runtime_data.gate.invalidate()
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.save()
        return True
    return False


async def async_migrate_entry(hass, entry):
    """Preserve credentials, selections and options; never downgrade a future schema."""
    if entry.version != 1:
        return False
    if entry.minor_version < 1:
        hass.config_entries.async_update_entry(entry, minor_version=1)
    return True
