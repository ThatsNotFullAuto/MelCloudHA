"""Versioned support envelope shared by the guided collector and diagnostics export."""

from datetime import UTC, datetime
from uuid import uuid4

PROBLEM_LABELS = {
    "connection": "Connessione o accesso all’account",
    "missing_values": "Sensori mancanti o non disponibili",
    "incorrect_values": "Valori diversi dall’app o dal display",
    "error_history": "Guasti P1 o storico errori",
    "manual_change": "Problema durante una modifica manuale",
    "dashboard": "Problema nella plancia",
    "other": "Altro problema",
}


def support_envelope(coordinator):
    context = getattr(coordinator, "support_context", None) or {}
    findings = []
    if getattr(coordinator, "last_success", None) is None:
        findings.append("no_successful_poll_since_load")
    if getattr(coordinator, "_pending", None) is not None:
        findings.append("journal_commit_pending")
    if getattr(coordinator, "storage_error", None):
        findings.append("journal_storage_error")
    if getattr(coordinator, "notification_errors", 0):
        findings.append("notification_delivery_failed")
    for status in set(coordinator.history_status.values()):
        if status in ("unsupported", "unavailable"):
            findings.append(f"error_history_{status}")
    return {
        "format": "melcloud_diagnostics.support",
        "schema_version": 1,
        "report_id": context.get("report_id") or str(uuid4()),
        "generated_at": datetime.now(UTC).isoformat(),
        "prepared_at": context.get("prepared_at"),
        "problem_category": context.get("problem_category", "not_specified"),
        "findings": sorted(findings),
        "privacy": {
            "credentials_included": False,
            "device_ids_pseudonymized": True,
            "contains_operational_values_and_timestamps": True,
        },
        "collection_mode": "read_only",
    }
