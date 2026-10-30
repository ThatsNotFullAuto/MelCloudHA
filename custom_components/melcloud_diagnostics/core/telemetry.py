"""Source-independent facts. No transport, controller commands or diagnostic guesses."""

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum


class FTCGeneration(StrEnum):
    UNKNOWN = "unknown"
    FTC4 = "FTC4"
    FTC5 = "FTC5"
    FTC6 = "FTC6"
    FTC7 = "FTC7"

    @classmethod
    def from_declared(cls, value: str | None) -> "FTCGeneration":
        # A unit model name, firmware number or presumed generation is not identification.
        return next((item for item in cls if item.value == value), cls.UNKNOWN)


class Source(StrEnum):
    MELCLOUD_HOME = "melcloud_home"
    ESPHOME = "esphome"
    SD_EXPORT = "mitsubishi_sd_export"
    E_MONITORING_EXPORT = "mitsubishi_e_monitoring_export"


class Availability(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"
    ACQUISITION_ERROR = "acquisition_error"
    STALE = "stale"


class Validation(StrEnum):
    UNVERIFIED = "unverified"
    STRUCTURAL = "structural"
    VERIFIED_REAL = "verified_real"
    INVALID = "invalid"


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(UTC)


@dataclass(frozen=True, kw_only=True)
class Observation:
    unit_id: str
    parameter: str
    value: str | float | bool | None
    unit: str | None
    acquired_at: datetime
    source: Source
    generation: FTCGeneration = FTCGeneration.UNKNOWN
    origin_at: datetime | None = None
    availability: Availability = Availability.UNKNOWN
    validation: Validation = Validation.UNVERIFIED
    protocol_revision: str | None = None
    source_instance: str = "default"

    def __post_init__(self):
        if not self.unit_id or not self.parameter or not self.source_instance:
            raise ValueError("Unit, parameter and source instance are required")
        object.__setattr__(self, "acquired_at", utc(self.acquired_at))
        if self.origin_at is not None:
            object.__setattr__(self, "origin_at", utc(self.origin_at))
        if not isinstance(self.value, (str, int, float, bool, type(None))):
            raise ValueError("Only scalar telemetry is accepted")
        if isinstance(self.value, (float, int)) and not isinstance(self.value, bool):
            if not math.isfinite(self.value):
                raise ValueError("Non-finite telemetry")
        if self.availability == Availability.AVAILABLE and self.value is None:
            raise ValueError("Available telemetry requires a value")
        if self.availability not in (Availability.AVAILABLE, Availability.STALE):
            if self.value is not None:
                raise ValueError("Unavailable telemetry cannot claim a measured value")

    @property
    def sample_at(self) -> datetime:
        return self.origin_at if self.origin_at is not None else self.acquired_at

    def at(self, now: datetime, max_age: timedelta) -> "Observation":
        """Freshness policy belongs to the consumer, never to the FTC generation."""
        now = utc(now)
        if max_age < timedelta(0):
            raise ValueError("Negative freshness limit")
        if self.acquired_at > now or self.sample_at > now:
            return replace(self, validation=Validation.INVALID)
        if self.availability == Availability.AVAILABLE and now - self.sample_at > max_age:
            return replace(self, availability=Availability.STALE)
        return self

    def export(self) -> dict:
        """Intentionally omit unit_id and source_instance from shareable reports."""
        return {
            "parameter": self.parameter,
            "value": self.value,
            "unit": self.unit,
            "acquired_at": self.acquired_at.isoformat(),
            "origin_at": self.origin_at.isoformat() if self.origin_at else None,
            "source": self.source.value,
            "ftc_generation": self.generation.value,
            "availability": self.availability.value,
            "validation": self.validation.value,
            "protocol_revision": self.protocol_revision,
        }


@dataclass(frozen=True)
class Comparison:
    observations: tuple[Observation, ...]
    candidates: tuple[Observation, ...]
    disagreement: bool | None


def compare(
    observations: tuple[Observation, ...],
    *,
    now: datetime,
    max_age: timedelta,
    max_skew: timedelta,
) -> Comparison:
    """Retain evidence; compare latest facts per source without choosing a winner.

    None means incomparable (missing data, units or timestamps too far apart).
    Disagreement is exact inequality, not a technical anomaly or threshold rule.
    Conflicting samples at the same acquisition time remain visible.
    """
    now = utc(now)
    if max_skew < timedelta(0) or max_age < timedelta(0):
        raise ValueError("Negative comparison window or freshness limit")
    if len({(o.unit_id, o.parameter) for o in observations}) > 1:
        raise ValueError("Compare one unit and parameter at a time")
    # Python treats False == 0.0: these are different typed facts, not duplicates.
    distinct = {(o.at(now, max_age), type(o.value)): o.at(now, max_age) for o in observations}
    evidence = tuple(distinct.values())
    latest = {}
    for o in evidence:
        key = (o.source, o.source_instance)
        latest[key] = max(latest.get(key, o.acquired_at), o.acquired_at)
    candidates = tuple(
        o
        for o in evidence
        if o.acquired_at == latest[(o.source, o.source_instance)]
        and o.availability == Availability.AVAILABLE
        and o.validation in (Validation.STRUCTURAL, Validation.VERIFIED_REAL)
    )
    comparable = (
        len(candidates) >= 2
        and len({o.unit for o in candidates}) == 1
        and len({type(o.value) for o in candidates}) == 1
        and max(o.sample_at for o in candidates) - min(o.sample_at for o in candidates) <= max_skew
    )
    disagreement = len({o.value for o in candidates}) > 1 if comparable else None
    return Comparison(evidence, candidates, disagreement)
