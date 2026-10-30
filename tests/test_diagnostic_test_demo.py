"""Reproducible screenshot fixtures must remain safe and exercise real reducers."""

import json

from tools.generate_test_demo import DEMO_UNIT, demo_reports, demo_states


def test_screenshot_fixtures_have_real_progress_and_distinct_outcomes():
    first = demo_reports()
    assert first == demo_reports()
    assert set(first) == {"start", "running", "complete", "partial"}
    assert first["complete"]["session"]["status"] == "completato"
    assert first["partial"]["session"]["status"] == "parziale"
    states = {row["entity_id"]: row for row in demo_states(first["running"])}
    assert states["sensor.demo_test_progress"]["state"] == 41.7
    assert states["sensor.demo_test_remaining"]["state"] == 35
    assert DEMO_UNIT not in json.dumps(first)
    assert all(
        report["verification_results"][5] == {"check": "physical", "result": "UNKNOWN"}
        for report in first.values()
    )
