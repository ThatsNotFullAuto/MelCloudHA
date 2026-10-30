"""MELCloud Diagnostics. No device commands are sent during setup or polling."""

import logging

from .const import ALLOW_CONTROL, DOMAIN, PLATFORMS

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    from aiomelcloudhome import MelCloudHomeAuth
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    from .coordinator import DiagnosticCoordinator
    from .core.cloud import CloudReader, SetpointWriter
    from .core.control import ConfirmationGate
    from .core.journal import Journal
    from .storage import JournalStore

    session = async_get_clientsession(hass)
    auth = MelCloudHomeAuth(entry.data["email"], entry.data["password"], session=session)
    reader = CloudReader(session, auth)
    store = JournalStore(hass, f"{DOMAIN}.{entry.entry_id}")
    coordinator = DiagnosticCoordinator(
        hass, entry, reader, store, Journal(await store.async_load())
    )
    writer = (
        SetpointWriter(session, auth, auth_lock=reader._auth_lock, health=reader.health)
        if entry.options.get(ALLOW_CONTROL, False)
        else None
    )
    coordinator.gate = ConfirmationGate(reader, writer, audit=coordinator.audit)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    from .test_manager import DiagnosticTestManager, TestSessionStore

    test_store = TestSessionStore(hass, f"{DOMAIN}.diagnostic_test.{entry.entry_id}")
    manager = DiagnosticTestManager(
        hass,
        test_store,
        task_factory=lambda coro: entry.async_create_background_task(
            hass, coro, "MELCloud diagnostic test"
        ),
    )
    await manager.async_load()  # Session storage errors are contained by the manager.
    coordinator.test_manager = manager
    reader.schema_observer = manager.capture_schema
    entry.async_on_unload(entry.add_update_listener(_options_updated))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _options_updated(hass, entry):
    # Revoke outstanding approvals immediately, even if reload fails.
    entry.runtime_data.gate.invalidate()
    manager = getattr(entry.runtime_data, "test_manager", None)
    if manager is not None and entry.options.get(ALLOW_CONTROL, False):
        try:
            manager.invalidate_control_conditions()
            await manager.async_wait_stopped()
        except Exception:
            LOGGER.warning("Diagnostic test finalization failed; ordinary options reload continues")
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    entry.runtime_data.gate.invalidate()
    manager = getattr(entry.runtime_data, "test_manager", None)
    if manager is not None:
        entry.runtime_data.reader.schema_observer = None
        try:
            await manager.async_close()
        except Exception:
            # A broken collection must not prevent ordinary integration unloading.
            pass
        entry.runtime_data.test_manager = None
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
