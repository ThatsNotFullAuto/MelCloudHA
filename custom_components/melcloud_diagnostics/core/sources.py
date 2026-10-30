"""Boundary for future local telemetry; no automatic cloud/local value substitution."""

from datetime import datetime
from typing import Protocol

from .models import Fault, Snapshot
from .telemetry import Observation


class DiagnosticSource(Protocol):
    """Legacy cloud boundary, retained for existing discovery and history callers."""

    async def discover(self, now: datetime) -> dict[str, Snapshot]: ...
    async def read_unit(self, identifier: str, now: datetime) -> Snapshot: ...
    async def history(self, identifier: str) -> list[Fault]: ...


class TelemetrySource(Protocol):
    """Future adapters return normalized facts; there is deliberately no command API.

    Acquisition failures must be explicit ACQUISITION_ERROR observations (value=None)
    or exceptions, never an empty healthy reading. Unit association must be explicitly
    verified before combining local and cloud data. This is a contract, not a driver.
    """

    async def observations(self, now: datetime) -> tuple[Observation, ...]: ...


class ServiceExportImporter(Protocol):
    """Offline-only contract. No proprietary format or concrete parser is implemented."""

    def parse(
        self, content: bytes, *, unit_id: str, acquired_at: datetime
    ) -> tuple[Observation, ...]: ...
