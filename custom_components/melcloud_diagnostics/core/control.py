"""Expiring, one-use double confirmation for a single exact setpoint change."""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from .models import Snapshot, boolean, number

LOGGER = logging.getLogger(__name__)


class ControlError(ValueError):
    """Unsafe, stale, disabled or unconfirmed proposal."""


@dataclass(frozen=True)
class Field:
    api: str
    minimum: str
    maximum: str
    zone: int | None = None


FIELDS = {
    "SetTankWaterTemperature": Field(
        "setTankWaterTemperature", "minSetTankTemperature", "maxSetTankTemperature"
    ),
    "SetTemperatureZone1": Field(
        "setTemperatureZone1", "minSetTemperature", "maxSetTemperature", 1
    ),
    "SetTemperatureZone2": Field(
        "setTemperatureZone2", "minSetTemperature", "maxSetTemperature", 2
    ),
}


def field_details(snapshot: Snapshot, field: str) -> dict:
    """Describe one supported parameter without proposing a write."""
    if field not in FIELDS:
        raise ControlError("Parametro non modificabile")
    if snapshot.connected is not True or snapshot.in_error is not False:
        raise ControlError("Connessione o assenza di guasti non confermata")
    spec = FIELDS[field]
    cap = snapshot.capabilities
    minimum, maximum = number(cap.get(spec.minimum)), number(cap.get(spec.maximum))
    old = number(snapshot.settings.get(field))
    if None in (minimum, maximum, old) or minimum >= maximum:
        raise ControlError("Valori o limiti Mitsubishi mancanti/non validi")
    if spec.zone:
        if spec.zone == 2 and boolean(cap.get("hasZone2")) is not True:
            raise ControlError("Zona 2 non confermata")
        mode = snapshot.settings.get(f"OperationModeZone{spec.zone}")
        if mode not in ("HeatRoomTemperature", "CoolRoomTemperature"):
            raise ControlError(
                "Il setpoint ambiente richiede regolazione ambiente: mandata esclusa"
            )
    elif boolean(cap.get("hasHotWater")) is not True:
        raise ControlError("Accumulo ACS non confermato")
    increment = number(cap.get("temperatureIncrement"))
    if increment is None:
        half = boolean(cap.get("hasHalfDegrees"))
        if half is None:
            raise ControlError("Passo di regolazione non dichiarato")
        increment = 0.5 if half else 1.0
    if increment <= 0:
        raise ControlError("Il servizio Mitsubishi non indica un passo di regolazione valido")
    # Relevant operating conditions and limits must still match at confirmation.
    return {
        "old": old,
        "mode1": snapshot.settings.get("OperationModeZone1"),
        "mode2": snapshot.settings.get("OperationModeZone2"),
        "power": snapshot.settings.get("Power"),
        "prohibit_hot_water": snapshot.settings.get("ProhibitHotWater"),
        "minimum": minimum,
        "maximum": maximum,
        "increment": increment,
    }


def validate(snapshot: Snapshot, field: str, value: float) -> dict:
    details = field_details(snapshot, field)
    value = number(value)
    if value is None or not details["minimum"] <= value <= details["maximum"]:
        raise ControlError("Scegli una temperatura compresa nei limiti indicati")
    if value == details["old"]:
        raise ControlError(
            "La temperatura è già impostata su questo valore: scegli un valore diverso o annulla"
        )
    if Decimal(str(value)) % Decimal(str(details["increment"])):
        raise ControlError("Usa gli incrementi di temperatura indicati nel campo")
    return details


@dataclass(frozen=True)
class Proposal:
    token: str
    owner: str
    unit: str
    field: str
    value: float
    context: dict
    expires: float
    stage: int = 0


class ConfirmationGate:
    def __init__(self, reader, writer=None, *, clock=time.monotonic, audit=None):
        self.reader = reader
        self.writer = writer
        self.clock = clock
        self.audit = audit
        self.pending: dict[str, Proposal] = {}
        self.lock = asyncio.Lock()

    def invalidate(self):
        LOGGER.debug("Manual control revoked; outstanding proposal count=%d", len(self.pending))
        self.pending.clear()
        self.writer = None

    def _take(self, token, owner, stage):
        proposal = self.pending.pop(token, None)
        if (
            self.writer is None
            or proposal is None
            or proposal.owner != owner
            or proposal.stage != stage
            or self.clock() >= proposal.expires
        ):
            raise ControlError("Proposta scaduta, non confermata o controllo disabilitato")
        return proposal

    async def propose(self, owner, unit, field, value) -> Proposal:
        async with self.lock:
            if self.writer is None:
                LOGGER.debug("Change proposal rejected: read-only mode")
                raise ControlError("Controllo disabilitato: modalità sola lettura")
            snapshot = await self.reader.read_unit(unit, datetime.now(UTC))
            context = validate(snapshot, field, value)
            self.pending = {
                k: p
                for k, p in self.pending.items()
                if p.expires > self.clock() and p.owner != owner
            }
            proposal = Proposal(
                secrets.token_urlsafe(32),
                owner,
                snapshot.id,
                field,
                float(value),
                context,
                self.clock() + 120,
            )
            self.pending[proposal.token] = proposal
            LOGGER.debug("Change proposal prepared: field=%s confirmations=0", field)
            return proposal

    async def confirm_first(self, token, owner) -> Proposal:
        async with self.lock:
            proposal = self._take(token, owner, 0)
            snapshot = await self.reader.read_unit(proposal.unit, datetime.now(UTC))
            if validate(snapshot, proposal.field, proposal.value) != proposal.context:
                raise ControlError("Valori o condizioni cambiati: creare una nuova proposta")
            if self.writer is None or self.clock() >= proposal.expires:
                raise ControlError("Proposta scaduta o controllo disabilitato")
            from dataclasses import replace

            confirmed = replace(proposal, token=secrets.token_urlsafe(32), stage=1)
            self.pending[confirmed.token] = confirmed
            LOGGER.debug("First confirmation accepted: field=%s", proposal.field)
            return confirmed

    async def execute(self, token, owner) -> str:
        async with self.lock:
            proposal = self._take(token, owner, 1)
            snapshot = await self.reader.read_unit(proposal.unit, datetime.now(UTC))
            if validate(snapshot, proposal.field, proposal.value) != proposal.context:
                raise ControlError("Valori o condizioni cambiati: nessun invio")
            if self.writer is None or self.clock() >= proposal.expires:
                raise ControlError("Proposta scaduta o controllo disabilitato")
            # Persist intent BEFORE issuing the non-idempotently-retried command.
            record = {
                "unit_id": proposal.unit,
                "field": proposal.field,
                "old": proposal.context["old"],
                "requested": proposal.value,
                "at": datetime.now(UTC).isoformat(),
                "status": "pending",
            }
            if self.audit:
                await self.audit(record)
            if self.writer is None or self.clock() >= proposal.expires:
                record["status"] = "cancelled_before_send"
                if self.audit:
                    await self.audit(record)
                raise ControlError("Proposta scaduta o controllo disabilitato prima dell'invio")
            try:
                LOGGER.debug(
                    "Second confirmation accepted: field=%s; checking final authorization",
                    proposal.field,
                )
                writer = self.writer

                def authorize():
                    if self.writer is not writer or self.clock() >= proposal.expires:
                        raise ControlError("Proposta scaduta o controllo revocato prima dell'invio")

                await writer.write(
                    proposal.unit, proposal.field, proposal.value, authorize=authorize
                )
            except ControlError:
                LOGGER.debug("Setpoint request cancelled before network send")
                record["status"] = "cancelled_before_send"
                if self.audit:
                    await self.audit(record)
                raise
            except Exception:
                LOGGER.debug("Setpoint request outcome unknown; no automatic retry")
                # Timeout may mean the command was applied. Never automatically resend.
                record["status"] = "outcome_unknown"
                if self.audit:
                    await self.audit(record)
                raise
            record["status"] = "accepted_unverified"
            try:
                after = await self.reader.read_unit(proposal.unit, datetime.now(UTC))
                if number(after.settings.get(proposal.field)) == proposal.value:
                    record["status"] = "observed_requested_value"
            except Exception:
                pass
            if self.audit:
                await self.audit(record)
            LOGGER.debug(
                "Setpoint request finished: field=%s status=%s", proposal.field, record["status"]
            )
            return record["status"]
