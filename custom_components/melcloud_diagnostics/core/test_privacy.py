"""Bounded, value-free raw schema inspection and allowlisted diagnostic facts."""

import hashlib
import hmac
import re
from dataclasses import replace
from itertools import islice

from .cloud_telemetry import TEMPERATURE_FIELDS, TEXT_FIELDS, cloud_observations
from .models import MISSING_TEXT, ZONE_MODES, DataError, boolean, number, timestamp
from .telemetry import FTCGeneration

EXTRA_BOOLEANS = ("Power", "ForcedHotWaterMode", "ProhibitHotWater")
PARAMETERS = (*TEMPERATURE_FIELDS, *TEXT_FIELDS, "connected", "in_error", "rssi", *EXTRA_BOOLEANS)
OPERATING_MODES = frozenset(
    (
        "Stop",
        "HotWater",
        "Heating",
        "Cooling",
        "FreezeStat",
        "LegionellaPrevention",
        "Heat",
        "HeatZones",
        "Cool",
    )
)
CAPABILITIES = (
    "hasHotWater",
    "hasZone2",
    "hasHalfDegrees",
    "temperatureIncrement",
    "minSetTankTemperature",
    "maxSetTankTemperature",
    "minSetTemperature",
    "maxSetTemperature",
)
# Safe names to inventory, NOT claims that Mitsubishi exposes or documents them.
CANDIDATES = (
    "RoomSensorSelection",
    "RoomTemperatureSourceZone1",
    "RoomTemperatureSourceZone2",
    "RoomSensorZone1",
    "RoomSensorZone2",
    "FirmwareVersion",
    "ControllerFirmwareVersion",
    "ExternalThermostatZone1",
    "ExternalThermostatZone2",
    "Thermistor",
    "SensorSource",
)
UNIT_FIELDS = ("settings", "capabilities", "isConnected", "isInError", "rssi", "ftcModel")
FAULT_FIELDS = ("timestamp", "errorCode", "clearedTimestamp")
MAX_SCHEMA_FIELDS = 128
MAX_INSPECT_ITEMS = 128


def safe_code(value):
    if not isinstance(value, str) or len(value) > 8:
        return None
    code = value.strip().upper()
    return code if re.fullmatch(r"(?:[A-Z][0-9A-F]|[0-9]{4})", code) else None


def safe_value(parameter, value, export_values=False):
    if parameter in ("connected", "in_error", *EXTRA_BOOLEANS):
        return value if isinstance(value, bool) else None
    if parameter == "ErrorCode":
        return safe_code(value)
    if parameter in ("OperationModeZone1", "OperationModeZone2"):
        return value if isinstance(value, str) and value in ZONE_MODES else None
    if parameter == "OperationMode":
        return value if isinstance(value, str) and value in OPERATING_MODES else None
    if not export_values or parameter not in (*TEMPERATURE_FIELDS, "rssi", *CAPABILITIES):
        return None
    if isinstance(value, str) and not re.fullmatch(r"[+-]?\d{1,4}(?:\.\d{1,4})?", value):
        return None
    parsed = number(value)
    # Export-format bound, not an official temperature limit or diagnostic threshold.
    return round(parsed, 4) if parsed is not None and abs(parsed) < 10000 else None


def sample(snapshot, export_values):
    snapshot = bounded_snapshot(snapshot)
    facts = []
    for fact in cloud_observations(snapshot):
        row = fact.export()
        row["value"] = safe_value(fact.parameter, fact.value, export_values)
        row["value_exported"] = row["value"] is not None
        row["source"] = "melcloud_home"
        row["protocol_revision"] = None
        raw = snapshot.settings.get(fact.parameter)
        if isinstance(raw, str) and raw.strip().lower() in MISSING_TEXT:
            row["validation"] = "unverified"
        if fact.parameter in TEXT_FIELDS and fact.value is not None and row["value"] is None:
            row["validation"] = "invalid"
        facts.append(row)
    for parameter in EXTRA_BOOLEANS:
        value = boolean(snapshot.settings.get(parameter))
        facts.append(
            {
                "parameter": parameter,
                "value": value,
                "unit": None,
                "acquired_at": snapshot.observed_at.isoformat(),
                "origin_at": None,
                "source": "melcloud_home",
                "ftc_generation": FTCGeneration.from_declared(snapshot.ftc_model).value,
                "availability": "available" if value is not None else "missing",
                "validation": "structural" if value is not None else "unverified",
                "protocol_revision": None,
                "value_exported": value is not None,
            }
        )
    return {
        "acquired_at": snapshot.observed_at.isoformat(),
        "unit": "unit_1",
        "facts": facts,
        "ftc_generation": FTCGeneration.from_declared(snapshot.ftc_model).value,
        "capabilities": {
            key: (
                boolean(snapshot.capabilities.get(key))
                if key.startswith("has")
                else safe_value(key, snapshot.capabilities.get(key), export_values)
            )
            for key in CAPABILITIES
        },
    }


def bounded_snapshot(snapshot):
    def scalar(value):
        return (
            value
            if isinstance(value, (bool, float, int))
            or value is None
            or isinstance(value, str)
            and len(value) <= 128
            else None
        )

    return replace(
        snapshot,
        settings={key: scalar(snapshot.settings.get(key)) for key in PARAMETERS},
        capabilities={key: scalar(snapshot.capabilities.get(key)) for key in CAPABILITIES},
        ftc_model=snapshot.ftc_model
        if isinstance(snapshot.ftc_model, str) and len(snapshot.ftc_model) <= 16
        else None,
    )


def safe_events(events, identifier, export_values):
    result = []
    for event in events[:32]:
        if event.get("unit_id") != identifier:
            continue
        if event.get("type") == "setting_changed" and event.get("field") in PARAMETERS:
            field = event["field"]
            result.append(
                {
                    "type": "setting_changed",
                    "parameter": field,
                    "old": safe_value(field, event.get("old"), export_values),
                    "new": safe_value(field, event.get("new"), export_values),
                }
            )
        elif event.get("type") == "active_fault":
            result.append({"type": "active_fault", "code": safe_code(event.get("code"))})
    return result


def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (float, int)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "object" if isinstance(value, dict) else "array" if isinstance(value, list) else "other"


class SchemaInspector:
    """Only bounded metadata survives this synchronous pre-parser callback.

    No payload references/values/names of unknown fields are retained. HMAC aliases
    are session-local and the key/mapping are never exported or persisted.
    """

    def __init__(self, key: bytes):
        self.key = key
        self.aliases = {}

    def inspect(self, operation, raw, identifier):
        rows = {}
        truncated = 0

        def field(section, name, value, known_names, decoder=None):
            nonlocal truncated
            known = isinstance(name, str) and name in known_names
            if known:
                label = name
            else:
                # Hash bounded prefixes; excessively long names are only aggregated.
                bounded = name if isinstance(name, str) and len(name) <= 128 else "unclassified"
                digest = hmac.digest(self.key, (section + "/" + bounded).encode(), hashlib.sha256)
                if digest not in self.aliases:
                    if len(self.aliases) >= MAX_SCHEMA_FIELDS:
                        truncated += 1
                        return
                    self.aliases[digest] = f"field_{len(self.aliases) + 1}"
                label = self.aliases[digest]
            path = section + "." + label
            if path not in rows and len(rows) >= MAX_SCHEMA_FIELDS:
                truncated += 1
                return
            row = rows.setdefault(
                path,
                {
                    "path": path,
                    "name": label,
                    "name_redacted": not known,
                    "types": {},
                    "occurrences": 0,
                    "nulls": 0,
                    "invalid": 0,
                    "decoder": decoder if known and label not in CANDIDATES else None,
                    "parameter": label if known and label in PARAMETERS else None,
                },
            )
            typ = kind(value)
            row["types"][typ] = row["types"].get(typ, 0) + 1
            row["occurrences"] += 1
            row["nulls"] += value is None
            if (
                known
                and name in TEMPERATURE_FIELDS
                and value is not None
                and not (
                    isinstance(value, str)
                    and len(value) <= 128
                    and value.strip().lower() in MISSING_TEXT
                )
            ):
                row["invalid"] += (
                    isinstance(value, str) and len(value) > 128 or number(value) is None
                )
            if known and name in ("timestamp", "clearedTimestamp") and value is not None:
                try:
                    if not isinstance(value, str) or len(value) > 64:
                        raise DataError("Timestamp format exceeded")
                    timestamp(value)
                except (DataError, TypeError, ValueError):
                    row["invalid"] += 1

        if operation == "account_context":
            units = []
            buildings = raw.get("buildings") if isinstance(raw, dict) else None
            if isinstance(buildings, list):
                for building in buildings[:MAX_INSPECT_ITEMS]:
                    listed = building.get("airToWaterUnits") if isinstance(building, dict) else None
                    if isinstance(listed, list):
                        units.extend(listed[: MAX_INSPECT_ITEMS - len(units)])
                    if len(units) >= MAX_INSPECT_ITEMS:
                        break
            selected = next(
                (
                    u
                    for u in units
                    if isinstance(u, dict)
                    and isinstance(u.get("id"), str)
                    and len(u["id"]) == 36
                    and u["id"].lower() == identifier
                ),
                None,
            )
            if selected is None:
                return {
                    "operation": operation,
                    "rows": [],
                    "truncated": 0,
                    "selected_present": False,
                }
            raw = selected
        if operation in ("account_context", "unit_snapshot") and isinstance(raw, dict):
            # Identity/location/free text excluded even from name aliases.
            excluded = {
                "id",
                "name",
                "givenDisplayName",
                "address",
                "email",
                "latitude",
                "longitude",
            }
            truncated += max(0, len(raw) - MAX_INSPECT_ITEMS)
            for name in islice(raw, MAX_INSPECT_ITEMS):
                if name not in excluded:
                    field("unit", name, raw[name], (*UNIT_FIELDS, *CANDIDATES), "Snapshot.parse")
            settings = raw.get("settings")
            if isinstance(settings, list):
                truncated += max(0, len(settings) - MAX_INSPECT_ITEMS)
                for item in settings[:MAX_INSPECT_ITEMS]:
                    if isinstance(item, dict):
                        field(
                            "settings[]",
                            item.get("name"),
                            item.get("value"),
                            (*PARAMETERS, *CANDIDATES),
                            "cloud_observations",
                        )
            cap = raw.get("capabilities")
            if isinstance(cap, dict):
                truncated += max(0, len(cap) - MAX_INSPECT_ITEMS)
                for name in islice(cap, MAX_INSPECT_ITEMS):
                    field("capabilities", name, cap[name], CAPABILITIES, "Snapshot.parse")
        elif operation == "error_history" and isinstance(raw, list):
            truncated += max(0, len(raw) - MAX_INSPECT_ITEMS)
            for fault in raw[:MAX_INSPECT_ITEMS]:
                if isinstance(fault, dict):
                    for name in islice(fault, 16):
                        if name != "errorReason":
                            field("history[]", name, fault[name], FAULT_FIELDS, "Fault.parse")
        return {
            "operation": operation,
            "rows": list(rows.values()),
            "truncated": truncated,
            "selected_present": True,
        }
