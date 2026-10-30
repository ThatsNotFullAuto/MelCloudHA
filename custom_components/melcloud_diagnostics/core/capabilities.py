"""Evidence registry: documentation never implies a working transport or real validation."""

from dataclasses import dataclass
from enum import StrEnum

from .telemetry import FTCGeneration, Source


class EvidenceStatus(StrEnum):
    UNKNOWN = "unknown"
    DOCUMENTED = "documented_unverified"
    VERIFIED = "verified_real"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, kw_only=True)
class Capability:
    generation: FTCGeneration
    source: Source
    parameter: str
    status: EvidenceStatus
    reference: str | None = None
    model: str | None = None
    firmware: str | None = None
    adapter: str | None = None
    transport: str | None = None
    note: str = ""

    def __post_init__(self):
        if self.status != EvidenceStatus.UNKNOWN and not self.reference:
            raise ValueError("Capability claims require evidence")


class CapabilityRegistry:
    def __init__(self, entries: tuple[Capability, ...] = ()):
        self.entries = entries

    def lookup(
        self, generation: FTCGeneration, source: Source, parameter: str, **context
    ) -> Capability:
        matches = [
            e
            for e in self.entries
            if (e.generation, e.source, e.parameter) == (generation, source, parameter)
            and all(
                getattr(e, k) is None or getattr(e, k) == context.get(k)
                for k in ("model", "firmware", "adapter", "transport")
            )
        ]
        if matches:

            def specificity(entry):
                return sum(
                    getattr(entry, k) is not None
                    for k in ("model", "firmware", "adapter", "transport")
                )

            most_specific = max(map(specificity, matches))
            best = [e for e in matches if specificity(e) == most_specific]
            if len(best) == 1:
                return best[0]
        # Ambiguous evidence is not an affirmative compatibility claim.
        return Capability(
            generation=generation, source=source, parameter=parameter, status=EvidenceStatus.UNKNOWN
        )


UPSTREAM_REVISION = "c5527d47c54150a81ed493decb77dc91cd4cf23e"
UPSTREAM_MANUAL = (
    f"https://github.com/gekkekoe/esphome-ecodan-hp/blob/{UPSTREAM_REVISION}/asgard/manual.md"
)
REGISTRY = CapabilityRegistry(
    tuple(
        Capability(
            generation=generation,
            source=Source.ESPHOME,
            parameter="realtime_energy_consumption",
            status=EvidenceStatus.UNAVAILABLE,
            transport="cn105",
            reference=UPSTREAM_MANUAL,
            note="Upstream limitation; no local adapter implemented or tested here",
        )
        for generation in (FTCGeneration.FTC5,)
    )
    + tuple(
        Capability(
            generation=generation,
            source=Source.ESPHOME,
            parameter="controller_identification",
            status=EvidenceStatus.DOCUMENTED,
            transport="cn105",
            reference=f"https://github.com/gekkekoe/esphome-ecodan-hp/blob/{UPSTREAM_REVISION}/protocol.md",
            note="0xC9 mapping documented upstream; no local transport or real validation here",
        )
        for generation in FTCGeneration
        if generation != FTCGeneration.UNKNOWN
    )
)
