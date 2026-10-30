"""Boundary for future local telemetry; no automatic cloud/local value substitution."""

from datetime import datetime
from typing import Protocol

from .models import Fault, Snapshot


class DiagnosticSource(Protocol):
    async def discover(self, now: datetime) -> dict[str, Snapshot]: ...
    async def read_unit(self, identifier: str, now: datetime) -> Snapshot: ...
    async def history(self, identifier: str) -> list[Fault]: ...
