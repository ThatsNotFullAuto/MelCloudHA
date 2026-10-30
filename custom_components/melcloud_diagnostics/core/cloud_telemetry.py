"""Pure read-only adaptation of existing snapshots; never performs extra cloud requests."""

from .models import MISSING_TEXT, ZONE_MODES, Snapshot, number
from .telemetry import Availability, FTCGeneration, Observation, Source, Validation

# Keep zone setpoints distinct from measured room/water temperatures.
# No room sensor selection, CN105 address or service parameter is inferred.
TEMPERATURE_FIELDS = (
    "TankWaterTemperature",
    "SetTankWaterTemperature",
    "RoomTemperatureZone1",
    "RoomTemperatureZone2",
    "SetTemperatureZone1",
    "SetTemperatureZone2",
    "FlowTemperature",
    "ReturnTemperature",
    "SetHeatFlowTemperatureZone1",
    "SetHeatFlowTemperatureZone2",
    "SetCoolFlowTemperatureZone1",
    "SetCoolFlowTemperatureZone2",
)
TEXT_FIELDS = ("ErrorCode", "OperationMode", "OperationModeZone1", "OperationModeZone2")


def cloud_observations(snapshot: Snapshot) -> tuple[Observation, ...]:
    if snapshot.source != Source.MELCLOUD_HOME:
        raise ValueError("This adapter accepts MELCloud Home snapshots only")
    result = []
    fields = {key: snapshot.settings.get(key) for key in (*TEMPERATURE_FIELDS, *TEXT_FIELDS)}
    fields.update(connected=snapshot.connected, in_error=snapshot.in_error, rssi=snapshot.rssi)
    for key, raw in fields.items():
        unit = "°C" if key in TEMPERATURE_FIELDS else "dBm" if key == "rssi" else None
        if unit is not None:
            value = number(raw)
        elif key in TEXT_FIELDS:
            value = (
                raw if isinstance(raw, str) and raw.strip().lower() not in MISSING_TEXT else None
            )
            if key.startswith("OperationModeZone") and value not in ZONE_MODES:
                value = None
        else:
            value = raw if isinstance(raw, bool) else None
        result.append(
            Observation(
                unit_id=snapshot.id,
                parameter=key,
                value=value,
                unit=unit,
                acquired_at=snapshot.observed_at,
                source=Source.MELCLOUD_HOME,
                generation=FTCGeneration.from_declared(snapshot.ftc_model),
                availability=Availability.AVAILABLE if value is not None else Availability.MISSING,
                validation=(
                    Validation.STRUCTURAL
                    if value is not None
                    else Validation.INVALID
                    if raw is not None
                    else Validation.UNVERIFIED
                ),
            )
        )
    return tuple(result)
