"""Atomic journal writes with disk verification, including HA's logged-only failures."""

import json
from copy import deepcopy
from pathlib import Path

from homeassistant.core import CoreState
from homeassistant.helpers.storage import Store

from .core.journal import Journal
from .core.models import DataError


class JournalStorageError(Exception):
    """Persistence could not be confirmed; never include file contents in errors."""


class JournalStore:
    """Keep the existing HA storage envelope/key/schema; never reset damaged data."""

    def __init__(self, hass, key):
        self.hass = hass
        self._store = Store(hass, 1, key, atomic_writes=True)
        self._had_file = False

    def _read(self):
        try:
            with Path(self._store.path).open(encoding="utf-8") as stream:
                envelope = json.load(stream)
        except FileNotFoundError:
            return None
        except (OSError, ValueError) as err:
            raise JournalStorageError("Cannot read diagnostic storage") from err
        if (
            not isinstance(envelope, dict)
            or envelope.get("version") != 1
            or envelope.get("minor_version", 1) != 1
            or envelope.get("key") != self._store.key
            or not isinstance(envelope.get("data"), dict)
        ):
            raise JournalStorageError("Unsupported diagnostic storage envelope")
        try:
            Journal(envelope["data"])
        except DataError as err:
            raise JournalStorageError("Invalid diagnostic journal; restore a backup") from err
        return envelope["data"]

    async def async_load(self):
        data = await self.hass.async_add_executor_job(self._read)
        if data is None and self._had_file:
            raise JournalStorageError("Diagnostic storage disappeared; restore before continuing")
        self._had_file = self._had_file or data is not None
        return data

    async def async_save(self, data):
        # HA defers async_save while stopping: it cannot acknowledge a durable commit.
        if self.hass.state == CoreState.stopping:
            raise JournalStorageError("Diagnostic storage unavailable during shutdown")
        existing = await self.hass.async_add_executor_job(self._read)
        if existing is None and self._had_file:
            raise JournalStorageError("Diagnostic storage disappeared; restore before continuing")
        expected = deepcopy(data)
        await self._store.async_save(expected)
        actual = await self.hass.async_add_executor_job(self._read)
        if actual != expected:
            raise JournalStorageError("Diagnostic storage write was not confirmed")
        self._had_file = True
