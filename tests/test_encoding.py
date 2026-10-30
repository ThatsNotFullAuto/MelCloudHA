"""Regression for destructive shell code-page conversion in user-facing files."""

import json
import re
from pathlib import Path


def test_user_facing_files_have_no_lost_unicode_markers():
    paths = [
        Path("README.md"),
        *Path("docs").glob("*.md"),
        Path("custom_components/melcloud_diagnostics/strings.json"),
        Path("custom_components/melcloud_diagnostics/translations/it.json"),
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="strict")
        assert "\ufffd" not in text, path
        assert "Ã" not in text and "â€" not in text, path
        assert re.search(r"\w\?\w|\s\?\s|\?C", text) is None, path
        assert (
            re.search(r"\b(?:gi|pi|pu|ci|perch|verr|entit|modalit|disponibilit)\?", text) is None
        ), path


def test_italian_guide_contains_actual_accents_and_navigation_symbols():
    guide = Path("docs/GUIDA_UTENTE.md").read_text(encoding="utf-8")
    for symbol in ("è", "già", "può", "→", "⋮", "’"):
        assert symbol in guide


def test_wizard_degree_symbol_and_meaningful_question_are_preserved():
    for name in ("strings.json", "translations/it.json"):
        data = json.loads(
            (Path("custom_components/melcloud_diagnostics") / name).read_text(encoding="utf-8")
        )
        assert "°C" in data["options"]["step"]["value"]["description"]
        assert "–" in data["options"]["step"]["value"]["description"]
        assert data["config"]["step"]["discovery"]["data"]["account"].endswith("?")
