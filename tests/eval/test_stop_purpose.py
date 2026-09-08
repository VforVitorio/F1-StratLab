"""Tests for the 2025 retrospective pit-entry evidence inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.strategy.eval.stop_purpose import (
    PENALTY_SERVICE,
    STRATEGIC_TYRE_CHANGE,
    UNKNOWN,
    build_stop_purpose_records,
    parse_rcm_message,
)

ROOT = Path(__file__).resolve().parents[2]
HAS_2025_DATA = (ROOT / "data" / "raw" / "2025").is_dir()


def _laps(**rows: list) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in ("PitInTime", "PitOutTime", "LapStartTime"):
        if column in frame:
            frame[column] = pd.to_timedelta(frame[column], unit="s")
    return frame


def _rcm(**messages: list) -> pd.DataFrame:
    return pd.DataFrame(messages)


def test_penalty_parser_extracts_car_and_distinguishes_investigation() -> None:
    penalty = parse_rcm_message(
        {
            "session_key": 1,
            "lap_number": 53,
            "date": "2025-05-25T14:11:10Z",
            "message": "FIA STEWARDS: DRIVE THROUGH PENALTY FOR CAR 63 (RUS)",
        }
    )
    investigation = parse_rcm_message(
        {
            "session_key": 1,
            "lap_number": 51,
            "date": "2025-05-25T14:09:00Z",
            "message": "CAR 63 (RUS) UNDER INVESTIGATION",
        }
    )

    assert penalty is not None
    assert penalty.car_numbers == (63,)
    assert penalty.penalty_type == "drive_through"
    assert penalty.phase == "awarded"
    assert investigation is not None
    assert investigation.penalty_type == "unknown"
    assert investigation.phase == "under_investigation"


def test_drive_through_evidence_wins_over_conflicting_telemetry() -> None:
    laps = _laps(
        DriverNumber=["63", "63"],
        Driver=["RUS", "RUS"],
        LapNumber=[53, 54],
        LapStartTime=[100, 200],
        PitInTime=[210, None],
        PitOutTime=[None, 230],
        Compound=["HARD", "MEDIUM"],
        TyreLife=[53, 1],
        Stint=[1, 2],
        TrackStatus=["1", "1"],
    )
    rcm = _rcm(
        session_key=[9979],
        lap_number=[53],
        date=["2025-05-25T14:11:10Z"],
        message=["FIA STEWARDS: DRIVE THROUGH PENALTY FOR CAR 63 (RUS)"],
    )

    [record] = build_stop_purpose_records(
        laps,
        rcm,
        year=2025,
        race="Monaco",
        session_key=9979,
        meeting_key=100,
        sample_stops={("RUS", 53)},
    )

    assert record.primary_label == PENALTY_SERVICE
    assert record.penalty_type == "drive_through"
    assert record.source_conflict is True
    assert record.decision_comparable is False


def test_time_penalty_and_tyre_change_are_mixed_not_clean_strategy() -> None:
    laps = _laps(
        DriverNumber=["55", "55"],
        Driver=["SAI", "SAI"],
        LapNumber=[20, 21],
        LapStartTime=[100, 200],
        PitInTime=[210, None],
        PitOutTime=[None, 230],
        Compound=["MEDIUM", "HARD"],
        TyreLife=[20, 1],
        Stint=[1, 2],
        TrackStatus=["1", "1"],
    )
    rcm = _rcm(
        session_key=[1],
        lap_number=[19],
        date=["2025-04-01T12:00:00Z"],
        message=["TIME PENALTY 5 SECONDS FOR CAR 55 (SAI)"],
    )

    [record] = build_stop_purpose_records(
        laps,
        rcm,
        year=2025,
        race="Sakhir",
        session_key=1,
        meeting_key=2,
        sample_stops={("SAI", 20)},
    )

    assert record.primary_label == STRATEGIC_TYRE_CHANGE
    assert record.secondary_label == PENALTY_SERVICE
    assert record.mixed_purpose is True
    assert record.decision_comparable is False


def test_same_compound_without_age_reset_is_not_called_transit() -> None:
    laps = _laps(
        DriverNumber=["44", "44"],
        Driver=["HAM", "HAM"],
        LapNumber=[18, 19],
        LapStartTime=[100, 200],
        PitInTime=[210, None],
        PitOutTime=[None, 230],
        Compound=["HARD", "HARD"],
        TyreLife=[18, 19],
        Stint=[1, 1],
        TrackStatus=["1", "1"],
    )

    [record] = build_stop_purpose_records(
        laps,
        _rcm(),
        year=2025,
        race="Monaco",
        session_key=1,
        meeting_key=2,
        sample_stops=set(),
    )

    assert record.telemetry_set_change == "none_observed"
    assert record.primary_label == UNKNOWN
    assert record.comparison_cohort == "unknown"


@pytest.mark.data
@pytest.mark.skipif(not HAS_2025_DATA, reason="data/raw/2025 absent")
def test_real_2025_inventory_covers_all_pit_entries_once() -> None:
    from src.strategy.eval.projection import _neutralised_laps, green_flag_stops

    records = []
    for race_dir in sorted((ROOT / "data" / "raw" / "2025").iterdir()):
        if not race_dir.is_dir():
            continue
        laps = pd.read_parquet(race_dir / "laps.parquet")
        metadata = json.loads((race_dir / "metadata.json").read_text(encoding="utf-8"))
        matching_rcm = pd.DataFrame()
        for candidate in (ROOT / "data" / "processed" / "race_radios" / "2025").glob(
            "*/rcm.parquet"
        ):
            probe = pd.read_parquet(candidate)
            if not probe.empty and int(probe["session_key"].iloc[0]) == int(
                metadata["session_key_openf1"]
            ):
                matching_rcm = probe
                break
        sample = {
            (str(driver), int(lap))
            for driver, laps_for_driver in green_flag_stops(laps, _neutralised_laps(laps)).items()
            for lap in laps_for_driver
        }
        records.extend(
            build_stop_purpose_records(
                laps,
                matching_rcm,
                year=2025,
                race=str(metadata["gp_name"]),
                session_key=int(metadata["session_key_openf1"]),
                meeting_key=int(metadata["session_key_openf1"]),
                sample_stops=sample,
            )
        )

    assert len(records) == 841
    assert sum(record.in_715_sample for record in records) == 573
