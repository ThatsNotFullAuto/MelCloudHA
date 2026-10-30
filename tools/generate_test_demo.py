"""Generate reproducible SYNTHETIC reports/UI states offline, never connect to HA/cloud.

Run from root: python -m tools.generate_test_demo --output-dir dist/collaudo-demo
"""

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from custom_components.melcloud_diagnostics.core.models import Snapshot
from custom_components.melcloud_diagnostics.core.test_privacy import SchemaInspector, sample
from custom_components.melcloud_diagnostics.core.test_session import (
    apply_record,
    evaluate,
    finish,
    new_report,
    validate_report,
)
from custom_components.melcloud_diagnostics.dashboard import build_dashboard
from custom_components.melcloud_diagnostics.test_entities import SENSOR_DESCRIPTIONS

START = datetime(2026, 10, 30, 12, tzinfo=UTC)
DEMO_UNIT = "11111111-1111-4111-8111-111111111111"
ENVIRONMENT = {
    "integration": "0.3.0",
    "homeassistant": "2026.10.4",
    "python": "3.14.2",
    "aiomelcloudhome": "0.3.1",
}


def demo_reports():
    """Exercise the same report reducer as production with explicit fake fixtures."""
    reports = {}
    for state, count, elapsed in (
        ("start", 0, 0),
        ("running", 25, 1500),
        ("complete", 60, 3600),
        ("partial", 8, 600),
    ):
        report = new_report(START, 3600, True, ENVIRONMENT.copy())
        previous = {}
        inspector = SchemaInspector(b"synthetic-demo-only")
        for index in range(count):
            at = START + timedelta(minutes=index)
            raw = {
                "id": DEMO_UNIT,
                "givenDisplayName": "Ecodan demo",
                "isConnected": True,
                "isInError": False,
                "ftcModel": "FTC7",
                "capabilities": {"hasHotWater": True},
                "settings": [
                    {"name": key, "value": value}
                    for key, value in {
                        "OperationMode": "Heating",
                        "OperationModeZone1": "HeatRoomTemperature",
                        "TankWaterTemperature": "42",
                        "SetTankWaterTemperature": "45",
                        "RoomTemperatureZone1": "22.5",
                        "SetTemperatureZone1": "21",
                    }.items()
                ],
            }
            frame = inspector.inspect(
                "account_context", {"buildings": [{"airToWaterUnits": [raw]}]}, DEMO_UNIT
            )
            report, previous = apply_record(report, {"kind": "schema", "frame": frame}, previous)
            report, previous = apply_record(
                report,
                {
                    "kind": "poll",
                    "at": at.isoformat(),
                    "sample": sample(Snapshot.parse(raw, at), True),
                    "comparison_values": {},
                    "history_status": "available",
                    "history_attempted": index % 15 == 0,
                    "faults": [],
                    "events": [],
                    "failed": False,
                    "error": None,
                    "http_statuses": [200],
                },
                previous,
            )
        if state == "complete":
            report = finish(report, START + timedelta(seconds=elapsed), elapsed, "deadline")
        elif state == "partial":
            report = finish(report, START + timedelta(seconds=elapsed), elapsed, "queue_full", 1)
        else:
            report["session"]["elapsed_seconds"] = elapsed
            report["session"]["status"] = "non_avviato" if state == "start" else "in_esecuzione"
            report = evaluate(report)
        validate_report(report)
        reports[state] = report
    return reports


def demo_states(report):
    """Synthetic state values for an isolated HA frontend screenshot fixture."""
    session, acq = report["session"], report["acquisition"]
    active = session["status"] == "in_esecuzione"
    values = {
        "test_progress": round(session["elapsed_seconds"] * 100 / session["duration_seconds"], 1),
        "test_elapsed": session["elapsed_seconds"],
        "test_duration": session["duration_seconds"],
        "test_remaining": session["duration_seconds"] - session["elapsed_seconds"] if active else 0,
        "test_end": session["planned_end"],
        "test_status": session["status"],
        "test_success": acq["successful"],
        "test_failed": acq["failed"],
        "test_last_acquisition": acq["last_acquisition"],
        "test_history": report["fault_history"]["status"],
        "test_storage": acq["storage"],
        "test_cloud": acq["cloud"],
        "test_quality": "inconcludente"
        if acq["successful"] < 2
        else "parziale"
        if acq["dropped"]
        else "raccolta_strutturale",
        "test_dropped": acq["dropped"],
        "test_reason": session["stop_reason"],
        "test_checks_passed": sum(c["result"] == "PASS" for c in report["verification_results"])
        if not active
        else None,
        "test_checks_failed": sum(c["result"] == "FAIL" for c in report["verification_results"])
        if not active
        else None,
        "test_checks_unknown": sum(
            c["result"] in ("UNKNOWN", "UNSUPPORTED", "INCONCLUSIVE")
            for c in report["verification_results"]
        )
        if not active
        else None,
    }
    return [
        {
            "entity_id": "sensor.demo_" + description.key,
            "state": round(values[description.key] / 60, 1)
            if description.key in ("test_elapsed", "test_remaining", "test_duration")
            else values[description.key],
            "attributes": {
                "friendly_name": description.name,
                **(
                    {"unit_of_measurement": description.native_unit_of_measurement}
                    if description.native_unit_of_measurement
                    else {}
                ),
                **({"device_class": description.device_class} if description.device_class else {}),
            },
        }
        for description in SENSOR_DESCRIPTIONS
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/collaudo-demo"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for state, report in demo_reports().items():
        for name, value in (
            (state + ".json", report),
            (state + "-states.json", demo_states(report)),
        ):
            (args.output_dir / name).write_text(
                json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
            )
    # Sensor IDs here belong ONLY to this synthetic fixture. Production uses the registry.
    dashboard = build_dashboard(
        {},
        {},
        {description.key: "sensor.demo_" + description.key for description in SENSOR_DESCRIPTIONS},
    )
    (args.output_dir / "dashboard.json").write_text(
        json.dumps(dashboard, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )
    print("Synthetic offline fixtures generated. No HA/cloud access performed.")


if __name__ == "__main__":
    main()
