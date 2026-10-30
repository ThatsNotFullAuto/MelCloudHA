"""Polling and persistent diagnostics; history failures never imply a healthy machine."""

import asyncio
import logging
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from aiomelcloudhome.exceptions import MelCloudHomeAuthenticationError, MelCloudHomeError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .core.cloud import AuthenticationError, CloudError, HistoryUnsupported
from .core.cloud_telemetry import cloud_observations
from .core.journal import Journal
from .core.models import DataError
from .storage import JournalStorageError

LOGGER = logging.getLogger(__name__)


@dataclass
class PendingCommit:
    journal: Journal
    events: list
    snapshots: dict | None = None
    at: datetime | None = None
    history: tuple | None = None
    telemetry: dict | None = None


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
        self.telemetry = {}
        self._save_lock = asyncio.Lock()
        self._poll_lock = asyncio.Lock()
        self._pending = None
        self.storage_error = None
        self.notification_errors = 0

    async def _write_pending(self):
        pending = self._pending
        try:
            await self.store.async_save(deepcopy(pending.journal.data))
        except Exception as err:
            self.storage_error = {"type": type(err).__name__, "at": datetime.now(UTC).isoformat()}
            raise JournalStorageError(
                "Diagnostic persistence failed; commit retained for retry"
            ) from err
        # No await between acknowledgement, adoption and notifications.
        self.journal.data = pending.journal.data
        self.storage_error = None
        self._pending = None
        if pending.snapshots is not None:
            self.data = pending.snapshots
            self.telemetry = pending.telemetry
            self.last_success = pending.at
            self.history_status, self.history_checked, self.history_success = pending.history
        for event in pending.events:
            try:
                self.hass.bus.async_fire(f"{DOMAIN}_observation", deepcopy(event))
            except Exception as err:
                # The durable journal is authoritative; never roll back or replay a commit.
                self.notification_errors += 1
                LOGGER.error("Diagnostic notification failed: error_type=%s", type(err).__name__)

    async def _finish_pending(self):
        """Hold the transaction lock until the write settles, even on cancellation.

        Retrying an uncertain write must use the identical staged journal, before
        acquiring new data. This also covers a write that reached disk then raised.
        """
        if self._pending is None:
            return
        task = asyncio.create_task(self._write_pending())
        cancelled = False
        while True:
            try:
                await asyncio.shield(task)
                break
            except asyncio.CancelledError:
                if task.cancelled():
                    raise
                cancelled = True
        if cancelled:
            raise asyncio.CancelledError

    async def save(self):
        async with self._save_lock:
            if self._pending is None:
                self._pending = PendingCommit(Journal(self.journal.data), [])
            await self._finish_pending()

    async def audit(self, record):
        # Same transaction boundary as polling; no changes to control authorization.
        async with self._save_lock:
            await self._finish_pending()
            staged = Journal(self.journal.data)
            staged.command(record)
            self._pending = PendingCommit(staged, [])
            await self._finish_pending()

    async def _async_update_data(self):
        async with self._poll_lock:
            return await self._poll()

    async def _poll(self):
        now = datetime.now(UTC)
        self.last_poll_attempt = now
        LOGGER.debug("Diagnostic poll started")
        phase = "storage"
        try:
            async with self._save_lock:
                await self._finish_pending()
            phase = "snapshot"
            snapshots = await self.reader.discover(now)
            selected = self.config_entry.data.get("unit_ids") if self.config_entry else None
            if selected is not None:
                snapshots = {k: s for k, s in snapshots.items() if k in selected}
            normalized = {key: cloud_observations(value) for key, value in snapshots.items()}
            statuses, checks, successes = (
                self.history_status.copy(),
                self.history_checked.copy(),
                self.history_success.copy(),
            )
            histories = {}
            terminal_error = None
            phase = "history"
            for identifier in snapshots:
                checked = checks.get(identifier)
                if checked is not None and now - checked < timedelta(minutes=15):
                    continue
                checks[identifier] = now
                try:
                    histories[identifier] = await self.reader.history(identifier)
                except HistoryUnsupported:
                    statuses[identifier] = "unsupported"
                except (
                    AuthenticationError,
                    MelCloudHomeAuthenticationError,
                    asyncio.CancelledError,
                ) as err:
                    statuses[identifier] = "unavailable"
                    terminal_error = err
                    break
                except (CloudError, DataError, MelCloudHomeError, TimeoutError):
                    statuses[identifier] = "unavailable"
                else:
                    statuses[identifier] = "available"
                    successes[identifier] = now
            phase = "storage"
            async with self._save_lock:
                # Audits may have committed while history I/O was in progress.
                await self._finish_pending()
                staged = Journal(self.journal.data)
                events = []
                for identifier, snapshot in snapshots.items():
                    events.extend(staged.observe(snapshot))
                    if identifier in histories:
                        events.extend(staged.merge_faults(identifier, histories[identifier], now))
                self._pending = PendingCommit(
                    staged, events, snapshots, now, (statuses, checks, successes), normalized
                )
                await self._finish_pending()
            if terminal_error is not None:
                phase = "history"
                raise terminal_error
        except (AuthenticationError, MelCloudHomeAuthenticationError) as err:
            self.last_poll_error = {
                "type": type(err).__name__,
                "at": now.isoformat(),
                "phase": phase,
            }
            LOGGER.debug(
                "Diagnostic poll needs reauthentication: error_type=%s", type(err).__name__
            )
            raise ConfigEntryAuthFailed("Riautenticazione MELCloud necessaria") from err
        except asyncio.CancelledError:
            self.last_poll_error = {"type": "CancelledError", "at": now.isoformat(), "phase": phase}
            raise
        except (
            CloudError,
            DataError,
            MelCloudHomeError,
            TimeoutError,
            JournalStorageError,
            OSError,
        ) as err:
            self.last_poll_error = {
                "type": type(err).__name__,
                "at": now.isoformat(),
                "phase": phase,
            }
            LOGGER.debug("Diagnostic poll failed: error_type=%s", type(err).__name__)
            raise UpdateFailed("Acquisizione o persistenza diagnostica non riuscita") from err
        self.last_poll_error = None
        LOGGER.debug(
            "Diagnostic poll completed: units=%d observations=%d", len(snapshots), len(events)
        )
        return snapshots
