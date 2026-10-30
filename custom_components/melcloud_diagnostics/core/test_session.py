"""Deterministic collection model and strict shareable report contract, no I/O."""

import json
import math
import re
from copy import deepcopy
from datetime import timedelta
from typing import TypedDict

from .models import ZONE_MODES, DataError, timestamp
from .test_privacy import (
    CANDIDATES,
    CAPABILITIES,
    FAULT_FIELDS,
    MAX_SCHEMA_FIELDS,
    OPERATING_MODES,
    PARAMETERS,
    UNIT_FIELDS,
    safe_code,
)

FORMAT = "melcloud_diagnostics.diagnostic_test"
DURATIONS = (1200, 3600)
MAX_REPORT_BYTES = 1_048_576
MAX_SAMPLES = 75
MAX_EVENTS = 128
MAX_FAULTS = 128
STATUSES = ("non_avviato", "in_esecuzione", "completato", "parziale", "interrotto", "fallito")
REASONS = (
    "deadline",
    "user",
    "reload_or_restart",
    "shutdown",
    "queue_full",
    "capacity",
    "storage_error",
    "processing_error",
    "rate_limited",
    "reauth_required",
    "repeated_errors",
    "control_permissions_changed",
)
COMPARISONS = ("coerenti", "diversi", "non_confrontabili", "non_verificati")


class SessionInfo(TypedDict):
    status: str
    started_at: str
    planned_end: str
    duration_seconds: int
    elapsed_seconds: float
    read_only: bool
    export_values: bool


class DiagnosticTestReport(TypedDict):
    format: str
    schema_version: int
    session: SessionInfo
    environment: dict
    acquisition: dict
    transport_health: dict
    schema_inventory: dict
    decoded_parameters: dict
    temporal_observations: list
    configuration_observations: list
    fault_history: dict
    ftc_capabilities: dict
    p1_investigation: dict
    verification_results: list
    missing_evidence: dict
    limitations: list


def new_report(now, duration, export_values, environment):
    if duration not in DURATIONS:
        raise ValueError("Unsupported duration")
    return {
        "format": FORMAT,
        "schema_version": 1,
        "session": {
            "status": "in_esecuzione",
            "started_at": now.isoformat(),
            "planned_end": (now + timedelta(seconds=duration)).isoformat(),
            "ended_at": None,
            "duration_seconds": duration,
            "elapsed_seconds": 0,
            "read_only": True,
            "export_values": bool(export_values),
            "stop_reason": None,
            "manual_comparison": "non_verificati",
        },
        "environment": environment,
        "acquisition": {
            "successful": 0,
            "failed": 0,
            "poll_errors": 0,
            "dropped": 0,
            "last_acquisition": None,
            "last_persisted_at": None,
            "consecutive_errors": 0,
            "storage": "regular",
            "cloud": "unknown",
        },
        "transport_health": {"http_status_counts": {}, "errors": []},
        "schema_inventory": {"frames": {}, "fields": {}, "truncated": 0},
        "decoded_parameters": {},
        "temporal_observations": [],
        "configuration_observations": [],
        "fault_history": {
            "status": "unknown",
            "last_checked_at": None,
            "successful": 0,
            "failed": 0,
            "duplicates": 0,
            "records": [],
        },
        "ftc_capabilities": {"declared_generation": "unknown", "real_validation": "UNKNOWN"},
        "p1_investigation": {},
        "verification_results": [],
        "missing_evidence": {},
        "limitations": [
            "no_physical_validation",
            "cloud_history_may_be_incomplete",
            "no_sensor_selection_decoder",
            "no_additional_cloud_requests",
            "software_timestamps_are_not_physical_event_times",
        ],
    }


def add_schema(report, frame):
    inventory = report["schema_inventory"]
    operation = frame["operation"]
    inventory["frames"][operation] = inventory["frames"].get(operation, 0) + 1
    inventory["truncated"] += frame["truncated"]
    for row in frame["rows"]:
        path = operation + "." + row["path"]
        if path not in inventory["fields"]:
            if len(inventory["fields"]) >= MAX_SCHEMA_FIELDS:
                inventory["truncated"] += 1
                continue
            inventory["fields"][path] = {
                **row,
                "operation": operation,
                "present_frames": 0,
                "occurrences": 0,
                "nulls": 0,
                "invalid": 0,
                "types": {},
            }
        saved = inventory["fields"][path]
        saved["present_frames"] += 1
        for key in ("occurrences", "nulls", "invalid"):
            saved[key] += row[key]
        for typ, count in row["types"].items():
            saved["types"][typ] = saved["types"].get(typ, 0) + count


def apply_record(report, record, previous):
    """Called in HA's executor with bounded data; never touches coordinator state."""
    result = deepcopy(report)
    previous = previous.copy()
    if record["kind"] == "schema":
        add_schema(result, record["frame"])
        validate_report(result)
        return result, previous
    acq = result["acquisition"]
    current = record.get("sample")
    now = record["at"]
    if current and acq["last_acquisition"] != current["acquired_at"]:
        stamp = timestamp(current["acquired_at"])
        start = timestamp(result["session"]["started_at"])
        if not start <= stamp <= timestamp(result["session"]["planned_end"]):
            current = None
        elif acq["last_acquisition"] and stamp < timestamp(acq["last_acquisition"]):
            current = None
    elif current:
        current = None
    if current:
        if len(result["temporal_observations"]) >= MAX_SAMPLES:
            raise DataError("Session capacity reached")
        acq["successful"] += 1
        acq["last_acquisition"] = current["acquired_at"]
        result["temporal_observations"].append(current)
        result["ftc_capabilities"]["declared_generation"] = current["ftc_generation"]
        for fact in current["facts"]:
            key = fact["parameter"]
            stat = result["decoded_parameters"].setdefault(
                key, {"present": 0, "missing": 0, "invalid": 0, "changes": 0}
            )
            stat["present" if fact["availability"] == "available" else "missing"] += 1
            stat["invalid"] += fact["validation"] == "invalid"
            value = record.get("comparison_values", {}).get(key)
            if value is not None:
                if key in previous and previous[key] != value:
                    stat["changes"] += 1
                previous[key] = value
    elif record.get("failed"):
        acq["failed"] += 1
    if record.get("error"):
        acq["poll_errors"] += 1
        acq["consecutive_errors"] += 1
        result["transport_health"]["errors"] = (
            result["transport_health"]["errors"] + [{"at": now, "type": record["error"]}]
        )[-16:]
    else:
        acq["consecutive_errors"] = 0
    acq["cloud"] = (
        "operativa" if current else "unavailable" if record.get("failed") else acq["cloud"]
    )
    for code in record.get("http_statuses", []):
        key = str(code)
        counts = result["transport_health"]["http_status_counts"]
        counts[key] = counts.get(key, 0) + 1
    history = result["fault_history"]
    if record.get("history_status") in ("available", "unsupported", "unavailable", "unknown"):
        history["status"] = record["history_status"]
    if record.get("history_checked_at") is not None:
        history["last_checked_at"] = record["history_checked_at"]
    if record.get("history_attempted"):
        history["successful" if record["history_status"] == "available" else "failed"] += 1
    keys = {(r["timestamp"], r["code"]) for r in history["records"]}
    for fault in record.get("faults", []):
        key = (fault["timestamp"], fault["code"])
        if fault["code"] is not None and key in keys:
            history["duplicates"] += 1
            if fault["cleared_at"]:
                next(r for r in history["records"] if (r["timestamp"], r["code"]) == key)[
                    "cleared_at"
                ] = fault["cleared_at"]
            continue
        if len(history["records"]) >= MAX_FAULTS:
            raise DataError("Session capacity reached")
        history["records"].append(fault)
        keys.add(key)
    for event in record.get("events", []):
        if len(result["configuration_observations"]) >= MAX_EVENTS:
            raise DataError("Session capacity reached")
        result["configuration_observations"].append({**event, "at": now})
    validate_report(result)
    return result, previous


def verification_results(result):
    """Bounded aggregate checks shared by the UI checkpoint and exported report."""
    acq, history = result["acquisition"], result["fault_history"]
    invalid = sum(v["invalid"] for v in result["decoded_parameters"].values())
    invalid += sum(v["invalid"] for v in result["schema_inventory"]["fields"].values())
    return [
        {
            "check": "acquisition",
            "result": "PASS"
            if acq["successful"] >= 2 and not acq["failed"] and not acq["dropped"]
            else "FAIL"
            if acq["failed"] or acq["dropped"]
            else "INCONCLUSIVE",
        },
        {
            "check": "structure",
            "result": "FAIL" if invalid else "PASS" if acq["successful"] else "UNKNOWN",
        },
        {
            "check": "acquisition_timestamps",
            "result": "PASS" if acq["successful"] >= 2 else "INCONCLUSIVE",
        },
        {"check": "origin_freshness", "result": "UNKNOWN"},
        {
            "check": "history",
            "result": "PASS"
            if history["status"] == "available" and history["successful"] > 0
            else "UNSUPPORTED"
            if history["status"] == "unsupported"
            else "UNKNOWN",
        },
        {"check": "physical", "result": "UNKNOWN"},
        {
            "check": "manual",
            "result": {"coerenti": "PASS", "diversi": "FAIL"}.get(
                result["session"]["manual_comparison"], "INCONCLUSIVE"
            ),
        },
        {
            "check": "persistence",
            "result": "FAIL"
            if acq["storage"] == "error"
            else "PASS"
            if acq["last_persisted_at"]
            else "UNKNOWN",
        },
        {
            "check": "test_conditions",
            "result": "FAIL"
            if result["session"].get("stop_reason") == "control_permissions_changed"
            else "PASS",
        },
    ]


def evaluate(report):
    """Software checks only; temporal acquisition does not verify cloud freshness."""
    result = deepcopy(report)
    acq, history = result["acquisition"], result["fault_history"]
    result["verification_results"] = verification_results(result)
    facts = [f for sample in result["temporal_observations"] for f in sample["facts"]]
    codes = [f["value"] for f in facts if f["parameter"] == "ErrorCode" and f["value"]]
    active = [
        sample
        for sample in result["temporal_observations"]
        if any(f["parameter"] == "in_error" and f["value"] is True for f in sample["facts"])
        and any(f["parameter"] == "ErrorCode" and f["value"] == "P1" for f in sample["facts"])
    ]
    result["p1_investigation"] = {
        "code_readable": bool(codes),
        "active_p1_observed": bool(active),
        "first_p1_observed_at": active[0]["acquired_at"] if active else None,
        "historical_p1": sum(r["code"] == "P1" for r in history["records"]),
        "historical_timestamp_available": any(r["code"] == "P1" for r in history["records"]),
        "room_sensor_selection": "UNKNOWN",
        "room_sensor_presence": "UNKNOWN",
        "cause": "UNKNOWN",
    }
    fields = result["schema_inventory"]["fields"]
    for field in fields.values():
        field["absent_frames"] = max(
            0,
            result["schema_inventory"]["frames"].get(field["operation"], 0)
            - field["present_frames"],
        )
        field["inconsistent_types"] = len(set(field["types"]) - {"null"}) > 1
        field["interpretation"] = "mapped" if field["decoder"] else "uninterpreted"
        field["source"] = "melcloud_home"
    result["missing_evidence"] = {
        "absent_in_observed_cloud": [
            k for k, v in result["decoded_parameters"].items() if not v["present"]
        ],
        "present_uninterpreted": [k for k, v in fields.items() if v["decoder"] is None],
        "unexpected_format": [k for k, v in result["decoded_parameters"].items() if v["invalid"]],
        "history_inaccessible": history["status"] != "available",
        "acquisition_failed": bool(acq["failed"] or acq["dropped"]),
        "ftc_unverifiable": [
            "selected_room_sensor",
            "selected_sensor_presence",
            "complete_ftc_history",
        ],
        "manual_required": ["independent_temperature_comparison", "controller_identification"],
        "additional_source_to_evaluate": ["service_report_or_cloud_decoder_review"],
    }
    validate_report(result)
    return result


def finish(report, now, elapsed, reason, dropped=0):
    result = evaluate(report)
    session, acq = result["session"], result["acquisition"]
    acq["dropped"] = dropped
    session.update(ended_at=now.isoformat(), elapsed_seconds=elapsed, stop_reason=reason)
    if reason in ("user", "reload_or_restart", "shutdown"):
        session["status"] = "interrotto"
    elif not acq["successful"]:
        session["status"] = "fallito" if acq["failed"] else "parziale"
    elif (
        reason != "deadline"
        or acq["successful"] < 2
        or acq["failed"]
        or acq["poll_errors"]
        or dropped
        or result["schema_inventory"]["truncated"]
        or result["fault_history"]["status"] != "available"
        or any(v["invalid"] for v in result["decoded_parameters"].values())
    ):
        session["status"] = "parziale"
    else:
        session["status"] = "completato"
    # Re-evaluate missing evidence after recording drops.
    return evaluate(result)


def validate_report(report):
    """Recursive output guard: no arbitrary string/key is accepted, including on reload."""
    required = {
        "format",
        "schema_version",
        "session",
        "environment",
        "acquisition",
        "transport_health",
        "schema_inventory",
        "decoded_parameters",
        "temporal_observations",
        "configuration_observations",
        "fault_history",
        "ftc_capabilities",
        "p1_investigation",
        "verification_results",
        "missing_evidence",
        "limitations",
    }
    if (
        not isinstance(report, dict)
        or set(report) != required
        or report["format"] != FORMAT
        or report["schema_version"] != 1
    ):
        raise DataError("Invalid session report")
    session = report["session"]
    if (
        set(session)
        != {
            "status",
            "started_at",
            "planned_end",
            "ended_at",
            "duration_seconds",
            "elapsed_seconds",
            "read_only",
            "export_values",
            "stop_reason",
            "manual_comparison",
        }
        or session["duration_seconds"] not in DURATIONS
        or session["read_only"] is not True
        or session["status"] not in STATUSES
        or session["stop_reason"] not in (*REASONS, None)
        or session["manual_comparison"] not in COMPARISONS
        or type(session["export_values"]) is not bool
        or not isinstance(session["elapsed_seconds"], (int, float))
        or not 0 <= session["elapsed_seconds"] <= session["duration_seconds"]
    ):
        raise DataError("Invalid session configuration")
    if set(report["environment"]) != {"integration", "homeassistant", "python", "aiomelcloudhome"}:
        raise DataError("Invalid environment")
    for version in report["environment"].values():
        if not isinstance(version, str) or not re.fullmatch(
            r"\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?(?:\.dev\d+)?(?:\.post\d+)?", version
        ):
            raise DataError("Invalid software version")
    for key in ("successful", "failed", "poll_errors", "dropped", "consecutive_errors"):
        count = report["acquisition"][key]
        if type(count) is not int or not 0 <= count <= 1_000_000:
            raise DataError("Invalid acquisition counter")
    if report["acquisition"]["successful"] != len(report["temporal_observations"]):
        raise DataError("Inconsistent acquisition counter")
    for field in ("started_at", "planned_end", "ended_at"):
        if session[field] is not None:
            timestamp(session[field])
    if timestamp(session["planned_end"]) - timestamp(session["started_at"]) != timedelta(
        seconds=session["duration_seconds"]
    ):
        raise DataError("Invalid session deadline")
    if (
        len(report["temporal_observations"]) > MAX_SAMPLES
        or len(report["configuration_observations"]) > MAX_EVENTS
        or len(report["fault_history"]["records"]) > MAX_FAULTS
        or len(report["schema_inventory"]["fields"]) > MAX_SCHEMA_FIELDS
    ):
        raise DataError("Session capacity reached")
    vocabulary = (
        set(PARAMETERS)
        | set(CANDIDATES)
        | set(CAPABILITIES)
        | set(UNIT_FIELDS)
        | set(FAULT_FIELDS)
        | set(ZONE_MODES)
        | set(OPERATING_MODES)
        | set(STATUSES)
        | set(REASONS)
        | set(COMPARISONS)
    )
    vocabulary |= set(
        "format schema_version session environment acquisition transport_health schema_inventory decoded_parameters temporal_observations configuration_observations fault_history ftc_capabilities p1_investigation verification_results missing_evidence limitations status started_at planned_end ended_at duration_seconds elapsed_seconds read_only export_values stop_reason manual_comparison successful failed poll_errors dropped last_acquisition last_persisted_at consecutive_errors storage cloud http_status_counts errors frames fields truncated path name name_redacted types occurrences nulls invalid decoder parameter operation present_frames present missing changes acquired_at unit facts ftc_generation capabilities value value_exported source origin_at availability validation protocol_revision code timestamp cleared_at duplicates records declared_generation real_validation code_readable active_p1_observed first_p1_observed_at historical_p1 historical_timestamp_available room_sensor_selection room_sensor_presence cause check result old new at type integration homeassistant python aiomelcloudhome absent_in_observed_cloud present_uninterpreted unexpected_format history_inaccessible acquisition_failed ftc_unverifiable manual_required additional_source_to_evaluate account_context unit_snapshot error_history settings[] unit capabilities history[] field_1 regular pending error unknown operativa unavailable available unsupported acquisition_error stale structural unverified verified_real null boolean number string object array other PASS FAIL UNKNOWN UNSUPPORTED INCONCLUSIVE acquisition structure acquisition_timestamps origin_freshness history physical manual unit_1 melcloud_home FTC4 FTC5 FTC6 FTC7 setting_changed active_fault selected_room_sensor selected_sensor_presence complete_ftc_history independent_temperature_comparison controller_identification service_report_or_cloud_decoder_review no_physical_validation cloud_history_may_be_incomplete no_sensor_selection_decoder no_additional_cloud_requests software_timestamps_are_not_physical_event_times AuthenticationError CloudError DataError TimeoutError CancelledError JournalStorageError MelCloudHomeAuthenticationError MelCloudHomeError UnexpectedError".split()
    )
    vocabulary |= {FORMAT, "Snapshot.parse", "cloud_observations", "Fault.parse", "°C", "dBm"}
    vocabulary |= {
        "last_checked_at",
        "persistence",
        "test_conditions",
        "absent_frames",
        "inconsistent_types",
        "interpretation",
        "mapped",
        "uninterpreted",
    }

    def allowed(text):
        if (
            text in vocabulary
            or re.fullmatch(r"field_(?:[1-9]\d{0,2})", text)
            or re.fullmatch(r"[1-5]\d{2}", text)
        ):
            return True
        if re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?\+00:00", text):
            timestamp(text)
            return True
        if re.fullmatch(r"\d+\.\d+(?:\.\d+)?(?:(?:a|b|rc)\d+)?(?:\.dev\d+)?(?:\.post\d+)?", text):
            return True
        if safe_code(text):
            return True
        if "." in text:
            prefix, _, leaf = text.rpartition(".")
            prefixes = {
                op + "." + section
                for op in ("account_context", "unit_snapshot", "error_history")
                for section in ("unit", "settings[]", "capabilities", "history[]")
            }
            return (
                prefix in prefixes or prefix in ("unit", "settings[]", "capabilities", "history[]")
            ) and (leaf in vocabulary or bool(re.fullmatch(r"field_[1-9]\d{0,2}", leaf)))
        return False

    def visit(value, depth=0):
        if depth > 12:
            raise DataError("Report nesting exceeded")
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str) or not allowed(key):
                    raise DataError("Unsafe report key")
                visit(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                visit(item, depth + 1)
        elif isinstance(value, str):
            if not allowed(value):
                raise DataError("Unsafe report value")
        elif value is not None and not isinstance(value, (bool, int, float)):
            raise DataError("Unexpected report type")
        elif isinstance(value, (int, float)) and (
            not math.isfinite(value) or abs(value) > 1_000_000_000
        ):
            raise DataError("Invalid report number")

    visit(report)
    if len(json.dumps(report, allow_nan=False).encode()) > MAX_REPORT_BYTES:
        raise DataError("Session capacity reached")
    return report
