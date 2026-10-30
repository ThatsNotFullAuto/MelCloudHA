"""Polling and persistent diagnostics; history failures never imply a healthy machine."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from aiomelcloudhome.exceptions import MelCloudHomeAuthenticationError, MelCloudHomeError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .core.cloud import AuthenticationError, CloudError, HistoryUnsupported
from .core.models import DataError

LOGGER = logging.getLogger(__name__)


class DiagnosticCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, reader, store, journal):
        super().__init__(
            hass, LOGGER, name=DOMAIN, config_entry=entry, update_interval=timedelta(seconds=60)
        )
        self.reader = reader
        self.store = store
        self.journal = journal
        self.gate = None
        self.history_status = {}
        self.history_checked = {}
        self.history_success = {}
        self.last_success = None
        self.last_poll_attempt = None
        self.last_poll_error = None
        self.support_context = None
        self._save_lock = asyncio.Lock()

    async def save(self):
        async with self._save_lock:
            await self.store.async_save(self.journal.data)

    async def audit(self, record):
        self.journal.command(record)
        await self.save()

    async def _async_update_data(self):
        now = datetime.now(UTC)
        self.last_poll_attempt = now
        LOGGER.debug("Diagnostic poll started")
        try:
            snapshots = await self.reader.discover(now)
            selected = self.config_entry.data.get("unit_ids") if self.config_entry else None
            if selected is not None:
                snapshots = {k: s for k, s in snapshots.items() if k in selected}
        except (AuthenticationError, MelCloudHomeAuthenticationError) as err:
            self.last_poll_error = {"type": type(err).__name__, "at": now.isoformat()}
            LOGGER.debug(
                "Diagnostic poll needs reauthentication: error_type=%s", type(err).__name__
            )
            raise ConfigEntryAuthFailed("Riautenticazione MELCloud necessaria") from err
        except (CloudError, DataError, MelCloudHomeError) as err:
            self.last_poll_error = {"type": type(err).__name__, "at": now.isoformat()}
            LOGGER.debug("Diagnostic poll failed: error_type=%s", type(err).__name__)
            raise UpdateFailed("Acquisizione MELCloud non riuscita") from err
        events = []
        for identifier, snapshot in snapshots.items():
            events.extend(self.journal.observe(snapshot))
            checked = self.history_checked.get(identifier)
            if checked is None or now - checked >= timedelta(minutes=15):
                self.history_checked[identifier] = now
                try:
                    faults = await self.reader.history(identifier)
                except HistoryUnsupported:
                    self.history_status[identifier] = "unsupported"
                    LOGGER.debug("Error history is not supported or not authorized")
                except (AuthenticationError, MelCloudHomeAuthenticationError) as err:
                    raise ConfigEntryAuthFailed("Riautenticazione MELCloud necessaria") from err
                except (CloudError, DataError, MelCloudHomeError):
                    self.history_status[identifier] = "unavailable"
                    LOGGER.debug("Error history could not be read; previous records preserved")
                else:
                    events.extend(self.journal.merge_faults(identifier, faults))
                    self.history_status[identifier] = "available"
                    self.history_success[identifier] = now
        # Persist before notifying; restarts must not replay historical notifications.
        await self.save()
        self.last_success = now
        self.last_poll_error = None
        for event in events:
            self.hass.bus.async_fire(f"{DOMAIN}_observation", event)
        LOGGER.debug(
            "Diagnostic poll completed: units=%d observations=%d", len(snapshots), len(events)
        )
        return snapshots
