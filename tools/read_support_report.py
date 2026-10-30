"""Summarize a downloaded HA diagnostics JSON for the integration maintainer."""

import argparse
import json
from pathlib import Path


def summarize(raw):
    data = raw.get("data", raw)
    support = data.get("support", {})
    if (
        support.get("format") != "melcloud_diagnostics.support"
        or support.get("schema_version") != 1
    ):
        raise ValueError("Unsupported diagnostics report format or schema version")
    lines = [
        f"Report: {support['report_id']}",
        f"Generated: {support['generated_at']}",
        f"Problem: {support['problem_category']}",
        f"Versions: {json.dumps(data.get('versions', {}), ensure_ascii=False)}",
        f"Last successful poll: {data.get('last_successful_poll')}",
        f"Findings: {', '.join(support['findings']) or 'none detected by software'}",
    ]
    for alias, unit in data.get("units", {}).items():
        observation = unit.get("current_observation", {})
        lines.append(
            f"{alias}: connected={observation.get('connected')} error={observation.get('in_error')} history={unit.get('history_status')} recorded_faults={len(unit.get('faults', []))}"
        )
    lines.append(
        f"Request counters: {json.dumps((data.get('transport_health') or {}).get('counters', {}))}"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    print(summarize(json.loads(args.report.read_text(encoding="utf-8-sig"))))
