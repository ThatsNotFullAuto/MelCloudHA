"""Normalize only observed fields; absence is never a zero or a healthy state."""

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID


class DataError(ValueError):
    """Unexpected or incomplete upstream data."""


def unit_id(value: str) -> str:
    return str(UUID(value))


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise DataError("Missing timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise DataError("Invalid timestamp") from err
    if parsed.tzinfo is None:
        # Do not guess whether a cloud timestamp is UTC or installation local time.
        raise DataError("Timestamp has no timezone")
    return parsed.astimezone(UTC)


def boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) else None


@dataclass(frozen=True)
class Snapshot:
    id: str
    name: str
    observed_at: datetime
    settings: dict[str, Any]
    capabilities: dict[str, Any]
    connected: bool | None
    in_error: bool | None
    rssi: float | None
    ftc_model: str | None
    source: str = "melcloud_home"

    @classmethod
    def parse(cls, raw: dict, now: datetime) -> "Snapshot":
        if not isinstance(raw, dict) or not isinstance(raw.get("settings"), list):
            raise DataError("Invalid unit snapshot")
        settings = {}
        for item in raw["settings"]:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                raise DataError("Invalid setting")
            if item["name"] in settings:
                raise DataError("Duplicate setting")
            if not isinstance(item.get("value"), (str, int, float, bool, type(None))):
                raise DataError("Unexpected structured setting value")
            settings[item["name"]] = item.get("value")
        capabilities = raw.get("capabilities") or {}
        if not isinstance(capabilities, dict):
            raise DataError("Invalid capabilities")
        try:
            identifier = unit_id(raw["id"])
        except (ValueError, KeyError, TypeError, AttributeError) as err:
            raise DataError("Invalid unit ID") from err
        return cls(
            identifier,
            str(raw.get("givenDisplayName") or raw.get("name") or "Ecodan"),
            now,
            settings,
            capabilities,
            boolean(raw.get("isConnected")),
            boolean(raw.get("isInError", settings.get("IsInError"))),
            number(raw.get("rssi")),
            str(raw["ftcModel"]) if raw.get("ftcModel") is not None else None,
        )


@dataclass(frozen=True)
class Fault:
    started: datetime
    code: str
    reason: str
    cleared: datetime | None

    @property
    def key(self) -> str:
        # Cleared time is mutable; do not duplicate an error when it clears.
        return f"{self.started.isoformat()}|{self.code}"

    def serialize(self) -> dict:
        return {
            "timestamp": self.started.isoformat(),
            "errorCode": self.code,
            "errorReason": self.reason,
            "clearedTimestamp": self.cleared.isoformat() if self.cleared else None,
        }

    @classmethod
    def parse(cls, raw: dict) -> "Fault":
        if not isinstance(raw, dict) or not isinstance(raw.get("errorCode"), str):
            raise DataError("Invalid error log entry")
        started = timestamp(raw.get("timestamp"))
        cleared = timestamp(raw["clearedTimestamp"]) if raw.get("clearedTimestamp") else None
        if cleared and cleared < started:
            raise DataError("Error cleared before it started")
        return cls(started, raw["errorCode"].strip(), str(raw.get("errorReason") or ""), cleared)
