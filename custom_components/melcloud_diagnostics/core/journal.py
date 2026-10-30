"""Persistent diagnostic history, deduplication and observed transitions."""

import hashlib
import json
from copy import deepcopy
from datetime import timedelta

from .models import ZONE_MODES, DataError, Fault, Snapshot, error_code, number, timestamp

WATCHED = (
    "OperationModeZone1",
    "OperationModeZone2",
    "SetTankWaterTemperature",
    "SetTemperatureZone1",
    "SetTemperatureZone2",
    "SetHeatFlowTemperatureZone1",
    "SetCoolFlowTemperatureZone1",
    "SetHeatFlowTemperatureZone2",
    "SetCoolFlowTemperatureZone2",
)
OBSERVED = WATCHED + (
    "ErrorCode",
    "OperationMode",
    "TankWaterTemperature",
    "RoomTemperatureZone1",
    "RoomTemperatureZone2",
    "FlowTemperature",
    "ReturnTemperature",
)


class Journal:
    """Store upstream facts separately from software-generated observations."""

    def __init__(self, data=None):
        if data is None:
            data = {"units": {}, "commands": []}
        if (
            not isinstance(data, dict)
            or not isinstance(data.get("units"), dict)
            or not isinstance(data.get("commands"), list)
            or any(not isinstance(record, dict) for record in data["commands"])
        ):
            raise DataError("Invalid diagnostic journal")
        for saved in data["units"].values():
            if (
                not isinstance(saved, dict)
                or not isinstance(saved.get("faults"), dict)
                or not isinstance(saved.get("observations"), list)
                or any(not isinstance(item, dict) for item in saved["observations"])
                or not isinstance(saved.get("previous"), (dict, type(None)))
                or not isinstance(saved.get("history_initialized"), bool)
            ):
                raise DataError("Invalid stored unit")
            for fault in saved["faults"].values():
                Fault.parse(fault)
            if saved.get("previous_observed_at"):
                timestamp(saved["previous_observed_at"])
        self.data = deepcopy(data)

    @staticmethod
    def _settings(settings):
        current = {}
        for key in OBSERVED:
            value = settings.get(key)
            if key.startswith("OperationModeZone"):
                valid = isinstance(value, str) and value in ZONE_MODES
            elif key == "ErrorCode":
                value = error_code(value)
                valid = value is not None
            elif key == "OperationMode":
                valid = isinstance(value, str) and value.lower() not in (
                    "",
                    "unknown",
                    "unavailable",
                )
            else:
                valid = number(value) is not None
            if valid:
                current[key] = value
        return current

    def _append(self, unit, events):
        for event in events:
            event["event_id"] = hashlib.sha256(
                json.dumps(event, sort_keys=True, ensure_ascii=True).encode()
            ).hexdigest()
        unit["observations"].extend(deepcopy(events))
        unit["observations"] = unit["observations"][-1000:]

    def unit(self, identifier):
        return self.data["units"].setdefault(
            identifier,
            {
                "faults": {},
                "observations": [],
                "previous": None,
                "history_initialized": False,
            },
        )

    def observe(self, snapshot: Snapshot) -> list[dict]:
        unit = self.unit(snapshot.id)
        if unit.get("previous_observed_at") and snapshot.observed_at < timestamp(
            unit["previous_observed_at"]
        ):
            return []
        current = self._settings(snapshot.settings)
        current["is_in_error"] = snapshot.in_error
        previous = unit["previous"]
        events = []
        if snapshot.in_error is True and (
            previous is None
            or previous.get("is_in_error") is not True
            or (
                "ErrorCode" in current
                and error_code(previous.get("ErrorCode")) != current["ErrorCode"]
            )
        ):
            events.append({"type": "active_fault", "code": current.get("ErrorCode")})
        if previous is not None:
            previous_settings = self._settings(previous)
            for key in WATCHED:
                # Missing data does not count as a real change.
                if key not in current or key not in previous_settings:
                    continue
                old, new = previous_settings[key], current[key]
                if not key.startswith("OperationMode"):
                    old, new = number(old), number(new)
                if old != new:
                    events.append(
                        {
                            "type": "setting_changed",
                            "field": key,
                            "old": previous[key],
                            "new": current[key],
                        }
                    )
        for event in events:
            event.update(
                {
                    "unit_id": snapshot.id,
                    "observed_at": snapshot.observed_at.isoformat(),
                    "source": snapshot.source,
                    "snapshot": current.copy(),
                }
            )
        self._append(unit, events)
        # Keep last known values across temporarily missing fields, but don't invent new ones.
        unit["previous"] = {
            **(previous or {}),
            **{k: v for k, v in current.items() if v is not None},
        }
        unit["previous_observed_at"] = snapshot.observed_at.isoformat()
        return events

    def merge_faults(self, identifier: str, faults: list[Fault], observed_at=None) -> list[dict]:
        unit = self.unit(identifier)
        events = []
        # Preserve legacy dictionary keys while comparing canonical fault identity.
        keys = {Fault.parse(value).key: key for key, value in unit["faults"].items()}
        for fault in faults:
            stored_key = keys.get(fault.key, fault.key)
            if fault.key not in keys and unit["history_initialized"]:
                events.append(
                    {
                        "type": "cloud_fault_added",
                        "unit_id": identifier,
                        "source": "melcloud_home",
                        **fault.serialize(),
                    }
                )
            # Do not lose a previously known cleared time if upstream temporarily omits it.
            record = fault.serialize()
            old = unit["faults"].get(stored_key)
            if old and old.get("clearedTimestamp") and not record["clearedTimestamp"]:
                record["clearedTimestamp"] = old["clearedTimestamp"]
            unit["faults"][stored_key] = record
            keys[fault.key] = stored_key
        unit["history_initialized"] = True
        if observed_at is not None:
            for event in events:
                event["observed_at"] = observed_at.isoformat()
            self._append(unit, events)
        return events

    def faults(self, identifier):
        return sorted(
            (Fault.parse(v) for v in self.unit(identifier)["faults"].values()),
            key=lambda f: f.started,
        )

    def p1_count(self, identifier, now):
        return sum(
            f.code.upper() == "P1" and now - timedelta(days=30) <= f.started <= now
            for f in self.faults(identifier)
        )

    def command(self, record):
        # Updates to one attempt replace its status rather than creating three attempts.
        items = self.data["commands"]
        key = (record["unit_id"], record["at"])
        items[:] = [r for r in items if (r["unit_id"], r["at"]) != key]
        items.append(record.copy())
        del items[:-1000]
