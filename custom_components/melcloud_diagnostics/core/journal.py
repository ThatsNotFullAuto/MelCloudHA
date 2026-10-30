"""Persistent diagnostic history, deduplication and observed transitions."""

from datetime import timedelta

from .models import Fault, Snapshot

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
        self.data = data or {"units": {}, "commands": []}

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
        current = {k: snapshot.settings[k] for k in OBSERVED if k in snapshot.settings}
        current["is_in_error"] = snapshot.in_error
        previous = unit["previous"]
        events = []
        if snapshot.in_error is True and (
            previous is None
            or previous.get("is_in_error") is not True
            or previous.get("ErrorCode") != current.get("ErrorCode")
        ):
            events.append({"type": "active_fault", "code": current.get("ErrorCode")})
        if previous is not None:
            for key in WATCHED:
                # Missing data does not count as a real change.
                if key in current and key in previous and current[key] != previous[key]:
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
        unit["observations"].extend(events)
        unit["observations"] = unit["observations"][-1000:]
        # Keep last known values across temporarily missing fields, but don't invent new ones.
        unit["previous"] = {**(previous or {}), **current}
        return events

    def merge_faults(self, identifier: str, faults: list[Fault]) -> list[dict]:
        unit = self.unit(identifier)
        events = []
        for fault in faults:
            if fault.key not in unit["faults"] and unit["history_initialized"]:
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
            old = unit["faults"].get(fault.key)
            if old and old.get("clearedTimestamp") and not record["clearedTimestamp"]:
                record["clearedTimestamp"] = old["clearedTimestamp"]
            unit["faults"][fault.key] = record
        unit["history_initialized"] = True
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
