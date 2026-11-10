"""Conservative field-presence evidence from schema-1 metadata, without values."""

from .test_privacy import MAX_SCHEMA_FIELDS

OPERATIONS = ("account_context", "unit_snapshot")
DIRECT_FIELDS = {"connected": "isConnected", "in_error": "isInError", "rssi": "rssi", "ftcModel": "ftcModel"}


def interpretable_fact(fact):
    """Only current, structurally interpreted facts can support active faults."""
    return fact.get("availability") == "available" and fact.get("validation") in (
        "structural", "verified_real"
    )


def observed_parameter_presence(report, parameter):
    """Return True/False/None for observed presence/proven absence/uncertainty.

    A schema-1 frame does not retain selected_present. A settings array present
    in every frame is a conservative witness that the selected unit/container
    was inspected. Normalized missing/redacted values are never absence proof.
    """
    inventory = report.get("schema_inventory", {})
    fields = inventory.get("fields", {})
    frames = inventory.get("frames", {})
    section = "unit" if parameter in DIRECT_FIELDS else "settings[]"
    name = DIRECT_FIELDS.get(parameter, parameter)
    paths = {op: f"{op}.{section}.{name}" for op in OPERATIONS}
    if any(fields.get(path, {}).get("present_frames", 0) > 0 for path in paths.values()):
        return True
    # Decoded availability can establish presence, including a redacted value.
    if report.get("decoded_parameters", {}).get(parameter, {}).get("present", 0) > 0:
        return True
    acquisition = report.get("acquisition", {})
    if (
        inventory.get("truncated", 0)
        or acquisition.get("dropped", 0)
        or len(fields) >= MAX_SCHEMA_FIELDS
    ):
        return None
    observed = [(op, frames.get(op, 0)) for op in OPERATIONS if frames.get(op, 0) > 0]
    # Different operations can describe the same poll; their counts cannot be
    # added to compensate for another acquisition without schema evidence.
    if not observed or max(count for _, count in observed) < acquisition.get("successful", 0):
        return None
    for op, count in observed:
        container = fields.get(f"{op}.unit.settings", {})
        if (
            container.get("operation") != op
            or container.get("present_frames") != count
            or container.get("occurrences") != count
            or container.get("types") != {"array": count}
            or container.get("nulls", 0)
            or container.get("invalid", 0)
        ):
            return None
        # A malformed/partial target row cannot establish absence.
        if paths[op] in fields:
            return None
        if parameter == "in_error" and any(
            path.startswith(f"{op}.settings[].")
            and (row.get("name_redacted") or path.rsplit(".", 1)[-1].startswith("field_"))
            for path, row in fields.items()
        ):
            # Snapshot.parse also accepts settings.IsInError. That name is
            # deliberately aliased in schema 1, so any aliased setting might
            # be the fallback; only an inventory without such settings rules
            # it out. Never reveal or add its name to the report vocabulary.
            return None
    return False
