"""Tests for the structured race-control penalty channel."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.f1_strat_manager.rcm_events import (
    RCMEvent,
    classify_rcm_event,
    parse_penalty_event,
)

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "processed" / "stop_purpose" / "2025" / "openf1_rcm"


def _event(message: str) -> RCMEvent:
    return RCMEvent(
        message=message,
        flag="",
        category="Other",
        lap=53,
        racing_number=None,
    )


def test_penalty_channel_survives_collision_precedence() -> None:
    event = _event("FIA STEWARDS: 10 SECOND PENALTY FOR CAR 81 (PIA) - CAUSING A COLLISION")

    penalty = parse_penalty_event(event)

    assert classify_rcm_event(event) == "CAR_COLLISION"
    assert penalty is not None
    assert penalty.penalty_type == "10s"
    assert penalty.phase == "awarded"
    assert penalty.car_numbers == (81,)
    assert penalty.incident_context is True


@pytest.mark.parametrize(
    ("message", "phase"),
    [
        ("PENALTY SERVED - 5 SECOND TIME PENALTY FOR CAR 22 (TSU)", "served"),
        (
            "FIA STEWARDS: TIME PENALTY UNDER INVESTIGATION FOR CAR 22 (TSU)",
            "under_investigation",
        ),
        (
            "CAR 22 (TSU) INCIDENT REVIEWED NO FURTHER INVESTIGATION - "
            "FAILING TO SERVE TIME PENALTY CORRECTLY",
            "no_further_action",
        ),
        ("FIA STEWARDS: PENALTY CANCELLED FOR CAR 22 (TSU)", "cancelled"),
    ],
)
def test_penalty_lifecycle_phases_are_distinct(message: str, phase: str) -> None:
    parsed = parse_penalty_event(_event(message))

    assert parsed is not None
    assert parsed.phase == phase
    assert parsed.car_numbers == (22,)


def test_stop_go_and_drive_through_are_not_time_penalties() -> None:
    drive = parse_penalty_event(_event("DRIVE THROUGH PENALTY FOR CAR 63 (RUS)"))
    stop_go = parse_penalty_event(_event("10 SECOND STOP/GO PENALTY FOR CAR 87 (BEA)"))

    assert drive is not None and drive.penalty_type == "drive_through"
    assert stop_go is not None and stop_go.penalty_type == "stop_go"


@pytest.mark.data
@pytest.mark.skipif(not CACHE.is_dir(), reason="complete OpenF1 RCM cache absent")
def test_complete_2025_penalty_corpus_keeps_each_target_car() -> None:
    rows = []
    for path in sorted(CACHE.glob("*.json")):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))

    penalty_rows = [row for row in rows if "PENALTY" in str(row.get("message", "")).upper()]
    parsed = [parse_penalty_event(_event(str(row["message"]))) for row in penalty_rows]

    assert len(penalty_rows) == 77
    assert sum(item is not None for item in parsed) == 77
    assert all(len(item.car_numbers) == 1 for item in parsed if item is not None)
    assert sum(item.phase == "served" for item in parsed if item is not None) == 23
    assert (
        sum(
            classify_rcm_event(_event(str(row["message"]))) == "CAR_COLLISION"
            for row in penalty_rows
        )
        == 22
    )
