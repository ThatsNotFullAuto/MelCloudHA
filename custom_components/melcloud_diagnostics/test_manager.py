"""Independent bounded observer. No cloud client, writer, gate or refresh API."""

import asyncio
import logging
import secrets
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from platform import python_version

from homeassistant.helpers.event import async_track_time_interval

from .const import VERSION
from .core.cloud_telemetry import cloud_observations
from .core.models import DataError, unit_id
from .core.test_privacy import (
    SchemaInspector,
    bounded_snapshot,
    safe_code,
    safe_events,
    safe_value,
    sample,
)
from .core.test_session import (
    COMPARISONS,
    DURATIONS,
    MAX_REPORT_BYTES,
    apply_record,
    evaluate,
    finish,
    new_report,
    validate_report,
    verification_results,
)
from .storage import JournalStorageError, JournalStore

LOGGER = logging.getLogger(__name__)
QUEUE_SIZE = 4
UI_INTERVAL = 30
ERROR_NAMES = frozenset(
    (
        "AuthenticationError",
        "CloudError",
        "DataError",
        "TimeoutError",
        "CancelledError",
        "JournalStorageError",
        "MelCloudHomeAuthenticationError",
        "MelCloudHomeError",
    )
)


class TestSessionError(ValueError):
    """A local session operation was refused."""


def validate_session_store(data):
    if not isinstance(data, dict) or set(data) != {"unit_id", "report"}:
        raise DataError("Invalid session storage")
    unit_id(data["unit_id"])
    validate_report(data["report"])


class TestSessionStore(JournalStore):
    def __init__(self, hass, key):
        super().__init__(hass, key, validator=validate_session_store, clone_in_executor=True)

    def _read(self):
        path = Path(self._store.path)
        if path.exists() and path.stat().st_size > MAX_REPORT_BYTES + 4096:
            raise JournalStorageError("Session storage size exceeded")
        return super()._read()

    async def async_save(self, data):
        # Refuse oversized/unsafe data BEFORE replacing the last durable checkpoint.
        await self.hass.async_add_executor_job(validate_session_store, data)
        await super().async_save(data)


class DiagnosticTestManager:
    def __init__(
        self,
        hass,
        store,
        *,
        now=lambda: datetime.now(UTC),
        clock=time.monotonic,
        task_factory=asyncio.create_task,
    ):
        self.hass, self.store = hass, store
        self.now, self.clock, self._task_factory = now, clock, task_factory
        self.data = None
        self.unit_id = None
        self.available = True
        self.storage_state = "regular"
        self._queue = asyncio.Queue(maxsize=QUEUE_SIZE)
        self._wake = asyncio.Event()
        self._task = None
        self._timer = None
        self._listeners = set()
        self._lifecycle = asyncio.Lock()
        self._export_task = None
        self._accepting = False
        self._reason = None
        self._started = 0.0
        self._dropped = 0
        self._inspector = None
        self._comparisons = {}
        self._idle = asyncio.Event()
        self._idle.set()

    @property
    def active(self):
        return self.data is not None and self.data["session"]["status"] == "in_esecuzione"

    @property
    def elapsed(self):
        if self.data is None:
            return 0
        if not self.active:
            return self.data["session"]["elapsed_seconds"]
        return max(0, min(self.data["session"]["duration_seconds"], self.clock() - self._started))

    @property
    def remaining(self):
        return max(0, self.data["session"]["duration_seconds"] - self.elapsed) if self.active else 0

    @property
    def progress(self):
        return (
            round(100 * self.elapsed / self.data["session"]["duration_seconds"], 1)
            if self.data
            else 0
        )

    @property
    def status(self):
        return (
            self.data["session"]["status"]
            if self.data
            else "non_avviato"
            if self.available
            else "fallito"
        )

    def async_add_listener(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def _notify(self):
        for listener in tuple(self._listeners):
            try:
                listener()
            except Exception:
                LOGGER.debug("Diagnostic test UI listener failed")

    async def async_load(self):
        try:
            saved = await asyncio.wait_for(self.store.async_load(), 2)
            if saved:
                self.unit_id, self.data = saved["unit_id"], saved["report"]
                if self.active:
                    self.data = await self.hass.async_add_executor_job(
                        finish,
                        self.data,
                        self.now(),
                        self.data["session"]["elapsed_seconds"],
                        "reload_or_restart",
                    )
                    await asyncio.wait_for(
                        self.store.async_save({"unit_id": self.unit_id, "report": self.data}), 2
                    )
        except Exception:
            self.available = False
            self.storage_state = "error"
            LOGGER.warning("Diagnostic test storage unavailable; ordinary monitoring continues")

    async def async_start(
        self,
        identifier,
        duration=3600,
        *,
        controls_enabled=True,
        export_values=False,
        replace_previous=False,
    ):
        async with self._lifecycle:
            if controls_enabled:
                raise TestSessionError("test_controls_enabled")
            if not self.available:
                raise TestSessionError("test_storage_error")
            if self.active or self._task is not None and not self._task.done():
                raise TestSessionError("test_already_running")
            if self.data is not None and not replace_previous:
                raise TestSessionError("test_replace_required")
            if duration not in DURATIONS:
                raise TestSessionError("test_invalid_duration")
            identifier = unit_id(identifier)
            environment = await self.hass.async_add_executor_job(self._environment)
            candidate = new_report(self.now(), duration, export_values, environment)
            try:
                await asyncio.wait_for(
                    self.store.async_save({"unit_id": identifier, "report": candidate}), 2
                )
            except Exception as err:
                self.storage_state = "error"
                raise TestSessionError("test_storage_error") from err
            self.unit_id, self.data = identifier, candidate
            self._queue = asyncio.Queue(maxsize=QUEUE_SIZE)
            self._reason = None
            self._dropped = 0
            self._comparisons = {}
            self._started = self.clock()
            self._inspector = SchemaInspector(secrets.token_bytes(32))
            self._accepting = True
            self.storage_state = "regular"
            self._task = self._task_factory(self._run())
            self._timer = async_track_time_interval(
                self.hass, self._tick, timedelta(seconds=UI_INTERVAL), cancel_on_shutdown=True
            )
            self._notify()

    @staticmethod
    def _environment():
        return {
            "integration": VERSION,
            "homeassistant": version("homeassistant"),
            "python": python_version(),
            "aiomelcloudhome": version("aiomelcloudhome"),
        }

    def _enqueue(self, record):
        if not self._accepting:
            return
        if self.remaining <= 0:
            self._request_stop("deadline")
            return
        try:
            self._queue.put_nowait(record)
            self._idle.clear()
        except asyncio.QueueFull:
            self._dropped += 1
            self._request_stop("queue_full")
        self._wake.set()

    def capture_schema(self, operation, raw, identifier=None):
        """Synchronous bounded metadata only; never await in the cloud path."""
        if not self._accepting or operation not in (
            "account_context",
            "error_history",
            "unit_snapshot",
        ):
            return
        if operation != "account_context" and identifier != self.unit_id:
            return
        try:
            frame = self._inspector.inspect(operation, raw, self.unit_id)
            self._enqueue({"kind": "schema", "frame": frame})
        except Exception:
            self._request_stop("processing_error")

    def observe_poll(
        self,
        *,
        at,
        snapshots,
        events,
        histories,
        history_status,
        history_checked,
        error,
        http_statuses,
    ):
        """Copy only bounded safe facts; never keep raw snapshots or journal references."""
        if not self._accepting:
            return
        try:
            snapshot = snapshots.get(self.unit_id)
            if snapshot is not None:
                snapshot = bounded_snapshot(snapshot)
            consent = self.data["session"]["export_values"]
            current = sample(snapshot, consent) if snapshot is not None else None
            compared = (
                {
                    fact.parameter: safe_value(fact.parameter, fact.value, True)
                    for fact in cloud_observations(snapshot)
                }
                if snapshot
                else {}
            )
            history = histories.get(self.unit_id, [])
            faults = [
                {
                    "timestamp": fault.started.isoformat(),
                    "code": safe_code(fault.code),
                    "cleared_at": fault.cleared.isoformat() if fault.cleared else None,
                }
                for fault in history[:128]
            ]
            if len(history) > 128 or len(events) > 32:
                self._dropped += max(0, len(history) - 128) + max(0, len(events) - 32)
                self._request_stop("capacity")
                return
            attempted = history_checked.get(self.unit_id) == at
            self._enqueue(
                {
                    "kind": "poll",
                    "at": at.isoformat(),
                    "sample": current,
                    "comparison_values": compared,
                    "faults": faults,
                    "events": safe_events(events, self.unit_id, consent),
                    "failed": snapshot is None,
                    "error": error
                    if error in ERROR_NAMES
                    else "UnexpectedError"
                    if error
                    else None,
                    "history_status": history_status.get(self.unit_id, "unknown"),
                    "history_attempted": attempted,
                    "history_checked_at": history_checked[self.unit_id].isoformat()
                    if history_checked.get(self.unit_id)
                    else None,
                    "http_statuses": [
                        code
                        for code in http_statuses
                        if isinstance(code, int) and 100 <= code <= 599
                    ],
                }
            )
        except Exception:
            self._request_stop("processing_error")

    def _request_stop(self, reason):
        if not self.active:
            return
        self._accepting = False
        self._reason = self._reason or reason
        self._wake.set()

    async def async_stop(self):
        self._request_stop("user")
        self._notify()

    def invalidate_control_conditions(self):
        """Stop local collection before an options reload can create any writer."""
        if self.active:
            # Invalidation takes precedence over a simultaneous user/deadline stop.
            self._reason = "control_permissions_changed"
            self._request_stop(self._reason)
            self._notify()

    async def _tick(self, now):
        if self.active and self.remaining <= 0:
            self._request_stop("deadline")
        self._notify()

    async def _persist(self):
        self.storage_state = "pending"
        candidate = await self.hass.async_add_executor_job(deepcopy, self.data)
        candidate["acquisition"]["last_persisted_at"] = self.now().isoformat()
        candidate["session"]["elapsed_seconds"] = self.elapsed
        candidate["verification_results"] = verification_results(candidate)
        await asyncio.wait_for(
            self.store.async_save({"unit_id": self.unit_id, "report": candidate}), 2
        )
        self.data = candidate
        self.storage_state = "regular"

    async def _run(self):
        try:
            while True:
                await self._wake.wait()
                self._wake.clear()
                while not self._queue.empty():
                    record = self._queue.get_nowait()
                    self.data, self._comparisons = await self.hass.async_add_executor_job(
                        apply_record, self.data, record, self._comparisons
                    )
                    if record["kind"] == "poll":
                        if 429 in record["http_statuses"]:
                            self._request_stop("rate_limited")
                        elif record["error"] in (
                            "AuthenticationError",
                            "MelCloudHomeAuthenticationError",
                        ):
                            self._request_stop("reauth_required")
                        elif self.data["acquisition"]["consecutive_errors"] >= 3:
                            self._request_stop("repeated_errors")
                        await self._persist()
                    self._notify()
                if self._reason:
                    reason = self._reason
                    self.data = await self.hass.async_add_executor_job(
                        finish, self.data, self.now(), self.elapsed, reason, self._dropped
                    )
                    if self._reason != reason:
                        self.data = await self.hass.async_add_executor_job(
                            finish, self.data, self.now(), self.elapsed, self._reason, self._dropped
                        )
                    await self._persist()
                    break
                self._idle.set()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            self._accepting = False
            storage_failed = self.storage_state == "pending"
            reason = (
                "capacity"
                if isinstance(err, DataError)
                else "storage_error"
                if self.storage_state == "pending"
                else "processing_error"
            )
            if self._reason == "control_permissions_changed":
                reason = self._reason
            self.data = await self.hass.async_add_executor_job(
                finish, self.data, self.now(), self.elapsed, reason, self._dropped
            )
            if storage_failed:
                self.storage_state = "error"
                self.data["acquisition"]["storage"] = "error"
            LOGGER.warning("Diagnostic test stopped locally: %s", reason)
        finally:
            self._accepting = False
            if self._timer:
                self._timer()
                self._timer = None
            if self.active:
                # Even a failure of final report evaluation must remain local.
                elapsed = self.elapsed
                self.data = {
                    **self.data,
                    "session": {
                        **self.data["session"],
                        "status": "parziale",
                        "elapsed_seconds": elapsed,
                        "stop_reason": self._reason or "processing_error",
                        "ended_at": self.now().isoformat(),
                    },
                }
            self._idle.set()
            while not self._queue.empty():
                self._queue.get_nowait()
                self._dropped += 1
            if self.data:
                self.data = {
                    **self.data,
                    "acquisition": {**self.data["acquisition"], "dropped": self._dropped},
                }
                # Storage errors/drops may be recorded after finish() evaluated checks.
                # Keep the visible counters consistent with a subsequent export.
                self.data["verification_results"] = verification_results(self.data)
            self._notify()

    async def async_compare(self, result):
        if result not in COMPARISONS or self.data is None:
            raise TestSessionError("test_not_started")
        # Manual annotations are local only; serialize through the worker when active.
        if self.active:
            raise TestSessionError("test_compare_after_stop")
        async with self._lifecycle:
            candidate = await self.hass.async_add_executor_job(deepcopy, self.data)
            candidate["session"]["manual_comparison"] = result
            self.data = await self.hass.async_add_executor_job(evaluate, candidate)
            try:
                await self._persist()
            except Exception:
                self.storage_state = "error"
                self.data = {
                    **self.data,
                    "acquisition": {**self.data["acquisition"], "storage": "error"},
                }
                self.data["verification_results"] = verification_results(self.data)
            self._notify()

    async def async_export(self):
        if self.data is None:
            return None
        # Export cannot acquire any coordinator/journal lock.
        # Coalesce downloads; closing one browser cannot start parallel executor work.
        if self._export_task is None or self._export_task.done():
            self._export_task = self._task_factory(self._export(self.data, self.elapsed))
        return await asyncio.shield(self._export_task)

    async def _export(self, report, elapsed):
        return await self.hass.async_add_executor_job(self._export_report, report, elapsed)

    @staticmethod
    def _export_report(report, elapsed):
        result = evaluate(report)
        result["session"]["elapsed_seconds"] = elapsed
        return result

    async def async_close(self):
        if self._timer:
            self._timer()
            self._timer = None
        self._request_stop("reload_or_restart")
        await self.async_wait_stopped()
        self._task = None
        if self._export_task is not None:
            if not self._export_task.done():
                self._export_task.cancel()
            await asyncio.gather(self._export_task, return_exceptions=True)
            self._export_task = None
        self._listeners.clear()

    async def async_wait_stopped(self):
        """Bounded local finalization before options reload cancels entry-owned tasks."""
        if self._task:
            try:
                if not self._task.done():
                    await asyncio.wait_for(asyncio.shield(self._task), 3)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            except Exception:
                LOGGER.debug("Diagnostic test task failed during local cleanup")
            await asyncio.gather(self._task, return_exceptions=True)
