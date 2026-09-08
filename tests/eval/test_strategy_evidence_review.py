from __future__ import annotations

import json
from pathlib import Path

from scripts.export_strategy_evidence_review import build_export

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "documents" / "audits" / "MEASURE_724_stop_purpose.json"


def test_strategy_evidence_export_keeps_the_715_population_and_review_map() -> None:
    payload = build_export(json.loads(SOURCE.read_text(encoding="utf-8")))

    assert payload["sample_entries"] == 573
    assert payload["reviewed_entries"] == 36
    assert payload["unreviewed_entries"] == 537
    assert payload["disposition_counts"] == {
        "exclude_mixed_penalty": 9,
        "exclude_non_comparable": 18,
        "exclude_penalty_only": 3,
        "retain_external_candidate": 4,
        "retain_regulation_constrained": 2,
        "unreviewed": 537,
    }


def test_strategy_evidence_export_surfaces_unlinked_penalty_history() -> None:
    payload = build_export(json.loads(SOURCE.read_text(encoding="utf-8")))
    rows = {(row["race"], row["driver"], row["pit_in_lap"]): row for row in payload["rows"]}

    verstappen = rows[("Jeddah", "VER", 21)]
    piastri = rows[("Silverstone", "PIA", 43)]
    assert verstappen["session_key"] == 10022
    assert piastri["session_key"] == 9947
    assert verstappen["pit_in_utc"] is not None
    assert piastri["pit_in_utc"] is not None
    assert verstappen["penalty_history"]["unlinked_ids"]
    assert piastri["penalty_history"]["unlinked_ids"]
    assert verstappen["review_status"] == "unreviewed"
    assert piastri["review_status"] == "unreviewed"
