"""Offline checks of already acquired cloud facts; outputs contain no input values."""

from datetime import datetime

from .cloud_telemetry import TEMPERATURE_FIELDS, TEXT_FIELDS, cloud_observations
from .models import DataError, Fault, Snapshot, number, timestamp
from .telemetry import Availability, FTCGeneration, Observation, Source, Validation

PARAMETERS = (*TEMPERATURE_FIELDS, *TEXT_FIELDS, "connected", "in_error", "rssi")

# Lack of a mapping is not a claim that Mitsubishi cannot provide the information.
UNMAPPED = (
    "selected_room_sensor",
    "selected_room_sensor_present",
    "fault_controller_address",
    "complete_ftc_fault_history",
    "commissioning_configuration",
)


def validate_payload(kind: str, payload, acquired_at: datetime | None = None) -> dict:
    """Check actual runtime parsers and downloaded reports without retaining raw data.

    Raw captures require an explicit, timezone-aware acquisition time supplied by
    the operator. Report observations use their own acquisition timestamps.
    Unknown input keys, labels, codes, dates and values are never echoed.
    """
    result = {
        "format": "melcloud_diagnostics.cloud_schema_check",
        "schema_version": 1,
        "input_kind": kind if kind in ("unit", "context", "history", "report") else "unsupported",
        "schema_valid": True,
        "issues": [],
        "units": [],
        "not_mapped_by_integration": list(UNMAPPED),
        "physical_accuracy_verified": False,
        "history_completeness_verified": False,
    }

    def issue(path, code):
        result["schema_valid"] = False
        result["issues"].append({"path": path, "code": code})

    def unit(raw, now, path):
        try:
            facts = cloud_observations(Snapshot.parse(raw, now))
        except (DataError, ValueError, TypeError, AttributeError):
            issue(path, "invalid_unit_snapshot")
            return
        parameters = {}
        for fact in facts:
            if fact.validation == Validation.INVALID:
                state = "invalid"
            elif fact.availability == Availability.AVAILABLE:
                state = "exposed"
            else:
                state = "missing"
            parameters[fact.parameter] = state
        result["units"].append(
            {
                "alias": f"unit_{len(result['units']) + 1}",
                "source": "melcloud_home",
                "ftc_generation_declared": facts[0].generation.value,
                "parameters": parameters,
            }
        )

    def history(raw, path):
        if not isinstance(raw, list):
            issue(path, "invalid_history_container")
            return
        for index, row in enumerate(raw):
            try:
                Fault.parse(row)
            except (DataError, ValueError, TypeError):
                issue(f"{path}[{index}]", "invalid_fault_record")

    def normalized(raw, path, alias):
        if not isinstance(raw, list):
            issue(path, "invalid_normalized_container")
            return
        parameters = {key: "not_in_report" for key in PARAMETERS}
        seen = set()
        for index, record in enumerate(raw):
            if not isinstance(record, dict):
                issue(f"{path}[{index}]", "invalid_normalized_record")
                continue
            key = record.get("parameter")
            if not isinstance(key, str) or key not in PARAMETERS:
                # Future/unknown fields are not interpreted or echoed.
                continue
            if key in seen:
                issue(f"{path}[{index}]", "duplicate_normalized_parameter")
            seen.add(key)
            try:
                fact = Observation(
                    unit_id="offline-placeholder",
                    parameter=key,
                    value=record.get("value"),
                    unit=record.get("unit"),
                    acquired_at=timestamp(record.get("acquired_at")),
                    origin_at=timestamp(record["origin_at"]) if record.get("origin_at") else None,
                    source=Source(record.get("source")),
                    generation=FTCGeneration(record.get("ftc_generation")),
                    availability=Availability(record.get("availability")),
                    validation=Validation(record.get("validation")),
                )
                if fact.source != Source.MELCLOUD_HOME:
                    raise ValueError("Unsupported source")
                expected_unit = (
                    "°C" if key in TEMPERATURE_FIELDS else "dBm" if key == "rssi" else None
                )
                if fact.unit != expected_unit or (
                    expected_unit and fact.value is not None and number(fact.value) is None
                ):
                    raise ValueError("Invalid unit or numeric value")
            except (DataError, ValueError, TypeError):
                issue(f"{path}[{index}]", "invalid_normalized_record")
                continue
            parameters[key] = (
                "invalid"
                if fact.validation == Validation.INVALID
                else "exposed"
                if fact.availability == Availability.AVAILABLE
                else fact.availability.value
            )
        result["units"].append(
            {
                "alias": alias,
                "source": "melcloud_home",
                "evidence_scope": "exported_report_fields",
                "parameters": parameters,
            }
        )

    if kind in ("unit", "context"):
        if acquired_at is None or acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
            issue("acquired_at", "explicit_timezone_required")
            return result
    if kind == "unit":
        unit(payload, acquired_at, "unit")
    elif kind == "context":
        if not isinstance(payload, dict) or not isinstance(payload.get("buildings"), list):
            issue("context", "invalid_context")
            return result
        identifiers = set()
        for index, building in enumerate(payload["buildings"]):
            path = f"buildings[{index}]"
            if not isinstance(building, dict) or not isinstance(
                building.get("airToWaterUnits", []), list
            ):
                issue(path, "invalid_building")
                continue
            for j, raw in enumerate(building.get("airToWaterUnits", [])):
                unit(raw, acquired_at, f"{path}.airToWaterUnits[{j}]")
                try:
                    identifier = Snapshot.parse(raw, acquired_at).id
                except (DataError, ValueError, TypeError, AttributeError):
                    continue
                if identifier in identifiers:
                    issue(f"{path}.airToWaterUnits[{j}]", "duplicate_unit")
                identifiers.add(identifier)
    elif kind == "history":
        history(payload, "history")
    elif kind == "report":
        data = payload.get("data", payload) if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("support"), dict):
            issue("report", "invalid_report")
            return result
        support = data["support"]
        if (
            support.get("format") != "melcloud_diagnostics.support"
            or support.get("schema_version") != 1
        ):
            issue("support", "unsupported_report_schema")
            return result
        if not isinstance(data.get("units"), dict):
            issue("units", "invalid_unit_container")
            return result
        for index, saved in enumerate(data["units"].values()):
            path = f"units[{index}]"
            if not isinstance(saved, dict):
                issue(path, "invalid_saved_unit")
                continue
            history(saved.get("faults", []), f"{path}.faults")
            if "normalized_telemetry" in saved:
                normalized(
                    saved["normalized_telemetry"],
                    f"{path}.normalized_telemetry",
                    f"unit_{index + 1}",
                )
                continue
            observation = saved.get("current_observation")
            if observation is None:
                result["units"].append(
                    {"alias": f"unit_{index + 1}", "current_observation": "missing"}
                )
                continue
            if not isinstance(observation, dict) or not isinstance(
                observation.get("settings"), dict
            ):
                issue(path, "invalid_current_observation")
                continue
            try:
                now = timestamp(observation.get("observed_at"))
            except DataError:
                issue(path, "invalid_acquisition_timestamp")
                continue
            if observation.get("source") != "melcloud_home":
                issue(path, "unsupported_source")
                continue
            previous_count = len(result["units"])
            unit(
                {
                    "id": "11111111-1111-4111-8111-111111111111",  # local parsing placeholder only
                    "settings": [
                        {"name": k, "value": v} for k, v in observation["settings"].items()
                    ],
                    "isConnected": observation.get("connected"),
                    "isInError": observation.get("in_error"),
                    "ftcModel": observation.get("ftc_model"),
                    "capabilities": observation.get("capabilities"),
                },
                now,
                path,
            )
            if len(result["units"]) > previous_count:
                result["units"][-1]["evidence_scope"] = "exported_report_fields"
                # An older report omits some fields even when the cloud exposed them.
                for key in PARAMETERS:
                    if key not in observation["settings"] and key not in ("connected", "in_error"):
                        result["units"][-1]["parameters"][key] = "not_in_report"
    else:
        issue("input_kind", "unsupported_input_kind")
    return result
