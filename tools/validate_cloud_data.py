"""Validate already acquired files offline. Run from root: python -m tools.validate_cloud_data."""

import argparse
import json
from pathlib import Path

from custom_components.melcloud_diagnostics.core.models import DataError, timestamp
from custom_components.melcloud_diagnostics.core.schema import validate_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--kind", choices=("report", "context", "unit", "history"), default="report"
    )
    parser.add_argument(
        "--acquired-at", help="Explicit ISO timestamp with timezone, required for raw unit/context"
    )
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 5 * 1024 * 1024:
            raise ValueError("Input too large")
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        acquired_at = timestamp(args.acquired_at) if args.acquired_at else None
        result = validate_payload(args.kind, payload, acquired_at)
    except (OSError, ValueError, DataError, RecursionError):
        # Do not echo file contents, paths, parser exception text or values.
        result = {"schema_valid": False, "issues": [{"code": "unreadable_or_invalid_input"}]}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result["schema_valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
