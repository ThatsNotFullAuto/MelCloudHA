"""Small allowlisted transport; upstream authentication is reused, controls are not."""

import asyncio
import logging
import re
import time
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .health import DiagnosticHealth
from .models import DataError, Fault, Snapshot, unit_id

API_BASE = "https://mobile.bff.melcloudhome.com"
LOGGER = logging.getLogger(__name__)


def operation_name(path, writer):
    if writer:
        return "setpoint_write"
    if path == "/context":
        return "account_context"
    return "error_history" if path.endswith("/errorlog") else "unit_snapshot"


class CloudError(Exception):
    """Cloud acquisition failed."""


class AuthenticationError(CloudError):
    """Authentication needs user attention."""


class HistoryUnsupported(CloudError):
    """History endpoint unavailable or not authorized for this account."""


class CloudReader:
    """Only exposes diagnostic GETs; no arbitrary URL or request method."""

    def __init__(self, session: ClientSession, auth, *, auth_lock=None, health=None) -> None:
        self._session = session
        self._auth = auth
        self._auth_lock = auth_lock if auth_lock is not None else asyncio.Lock()
        self._retry_after = 0.0
        self.health = health if health is not None else DiagnosticHealth()

    async def _request(
        self, path: str, *, payload: dict | None = None, writer: bool = False, authorize=None
    ) -> Any:
        operation = operation_name(path, writer)
        started = time.monotonic()
        LOGGER.debug("Cloud request started: operation=%s", operation)
        try:
            result = await self._perform_request(
                path, payload=payload, writer=writer, authorize=authorize
            )
        except asyncio.CancelledError:
            self.health.record(operation, "cancelled", (time.monotonic() - started) * 1000)
            LOGGER.debug("Cloud request cancelled: operation=%s", operation)
            raise
        except Exception as error:
            elapsed = (time.monotonic() - started) * 1000
            self.health.record(operation, "error", elapsed, type(error).__name__)
            LOGGER.debug(
                "Cloud request failed: operation=%s error_type=%s elapsed_ms=%.1f",
                operation,
                type(error).__name__,
                elapsed,
            )
            raise
        elapsed = (time.monotonic() - started) * 1000
        self.health.record(operation, "success", elapsed)
        LOGGER.debug("Cloud request completed: operation=%s elapsed_ms=%.1f", operation, elapsed)
        return result

    async def _perform_request(
        self, path: str, *, payload: dict | None = None, writer: bool = False, authorize=None
    ) -> Any:
        unit_path = re.fullmatch(r"/monitor/atwunit/[0-9a-f-]{36}", path)
        if writer:
            if not isinstance(self, SetpointWriter) or not unit_path:
                raise PermissionError("Device writes are disabled on this transport")
            if authorize is None:
                raise PermissionError("No confirmation gate authorization")
        elif path != "/context" and not re.fullmatch(
            r"/monitor/atwunit/[0-9a-f-]{36}(?:/errorlog)?", path
        ):
            raise PermissionError("Endpoint outside diagnostic allowlist")
        if time.monotonic() < self._retry_after:
            raise CloudError("Server rate limit: waiting before next request")
        # All callers construct paths internally from canonical UUIDs.
        async with self._auth_lock:
            token = await self._auth.async_get_access_token()
        if writer:
            # Authentication can await for seconds: recheck revocation/expiry at send time.
            authorize()
        try:
            async with self._session.request(
                "PUT" if writer else "GET",
                API_BASE + path,
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=ClientTimeout(total=20),
                allow_redirects=False,
            ) as response:
                operation = operation_name(path, writer)
                self.health.http_statuses[operation] = response.status
                LOGGER.debug(
                    "Cloud response: operation=%s http_status=%d", operation, response.status
                )
                if response.status == 401:
                    raise AuthenticationError("Authentication expired")
                if response.status == 429:
                    delay = response.headers.get("Retry-After", "60")
                    self._retry_after = time.monotonic() + min(
                        3600, max(60, int(delay) if delay.isdigit() else 60)
                    )
                    raise CloudError("Server rate limit")
                if response.status in (403, 404) and path.endswith("/errorlog"):
                    raise HistoryUnsupported("History unavailable for this unit/account")
                if not 200 <= response.status < 300:
                    raise CloudError(f"Cloud HTTP {response.status}")
                if writer:
                    return None
                return await response.json(content_type=None)
        except (ClientError, TimeoutError, ValueError) as err:
            # Never include URLs, headers, response bodies or credentials in errors.
            raise CloudError("Cloud request failed or returned invalid JSON") from err

    async def discover(self, now) -> dict[str, Snapshot]:
        raw = await self._request("/context")
        if not isinstance(raw, dict) or not isinstance(raw.get("buildings"), list):
            raise DataError("Invalid account context")
        result = {}
        for building in raw["buildings"]:
            if not isinstance(building, dict) or not isinstance(
                building.get("airToWaterUnits", []), list
            ):
                raise DataError("Invalid building")
            for item in building.get("airToWaterUnits", []):
                snapshot = Snapshot.parse(item, now)
                result[snapshot.id] = snapshot
        return result

    async def read_unit(self, identifier: str, now) -> Snapshot:
        identifier = unit_id(identifier)
        result = Snapshot.parse(await self._request(f"/monitor/atwunit/{identifier}"), now)
        if result.id != identifier:
            raise DataError("Response belongs to a different unit")
        return result

    async def history(self, identifier: str) -> list[Fault]:
        raw = await self._request(f"/monitor/atwunit/{unit_id(identifier)}/errorlog")
        if not isinstance(raw, list):
            raise DataError("Invalid error log")
        return [Fault.parse(item) for item in raw]


class SetpointWriter(CloudReader):
    """Created only when control is enabled; called only by ConfirmationGate."""

    async def write(self, identifier: str, field: str, value: float, *, authorize) -> None:
        from .control import FIELDS

        if field not in FIELDS:
            raise ValueError("Unsupported writable field")
        await self._request(
            f"/monitor/atwunit/{unit_id(identifier)}",
            payload={FIELDS[field].api: value},
            writer=True,
            authorize=authorize,
        )
