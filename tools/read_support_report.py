"""Summarize a downloaded HA diagnostics JSON for the integration maintainer."""

import argparse
import json
from pathlib import Path


def summarize(raw):
    data = raw.get("data", raw)
    if "diagnostic_test" in data or data.get("format") == "melcloud_diagnostics.diagnostic_test":
        from custom_components.melcloud_diagnostics.core.report_evidence import (
            interpretable_fact,
            observed_parameter_presence,
        )
        from custom_components.melcloud_diagnostics.core.test_privacy import safe_code
        from custom_components.melcloud_diagnostics.core.test_session import validate_report

        report = validate_report(data.get("diagnostic_test", data))
        samples = report["temporal_observations"]
        codes = set()
        flags = {"true": 0, "false": 0, "unknown": 0}
        active_p1 = False
        for sample in samples:
            facts = sample["facts"]
            current_codes = {
                code
                for fact in facts
                if fact["parameter"] == "ErrorCode"
                and interpretable_fact(fact)
                and (code := safe_code(fact["value"])) is not None
            }
            codes.update(current_codes)
            flag = next((
                f["value"] for f in facts
                if f["parameter"] == "in_error"
                and type(f["value"]) is bool
                and interpretable_fact(f)
            ), None)
            flags["true" if flag is True else "false" if flag is False else "unknown"] += 1
            active_p1 |= flag is True and "P1" in current_codes
        records = report["fault_history"]["records"]
        ftc_presence = observed_parameter_presence(report, "ftcModel")
        ftc_observed = "yes" if ftc_presence is True else "no" if ftc_presence is False else "unknown"
        return "\n".join([
            "Diagnostic test (read only)",
            f"Status: {report['session']['status']}",
            f"Acquisition counts: {report['acquisition']['successful']} successful, {report['acquisition']['failed']} failed",
            f"History: {report['fault_history']['status']}",
            f"Current interpretable error codes: {', '.join(sorted(codes)) or 'none observed'}",
            f"Active fault flag (samples): true={flags['true']}, false={flags['false']}, unknown={flags['unknown']}",
            f"Active P1 observed: {str(active_p1).lower()}",
            f"Historical records: {len(records)}; historical P1 records: {sum(r['code'] == 'P1' for r in records)} (not an episode count)",
            f"FTC declared generation: {report['ftc_capabilities']['declared_generation']}; ftcModel field observed: {ftc_observed}",
            f"Checks: {json.dumps(report['verification_results'])}",
            "Physical accuracy: UNKNOWN",
        ])
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
