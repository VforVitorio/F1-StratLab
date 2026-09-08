"""Tests for the 2025 retrospective pit-entry evidence inventory."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.measure_stop_purpose import _manifest_entry
from src.strategy.eval.stop_purpose import (
    PENALTY_SERVICE,
    STRATEGIC_TYRE_CHANGE,
    UNKNOWN,
    build_penalty_lifecycle,
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
    stop_go = parse_rcm_message(
        {
            "session_key": 1,
            "lap_number": 40,
            "date": "2025-04-01T12:00:00Z",
            "message": "10 SECOND STOP/GO PENALTY FOR CAR 87 (BEA)",
        }
    )
    assert investigation is not None
    assert investigation.penalty_type == "unknown"
    assert investigation.phase == "under_investigation"
    assert stop_go is not None
    assert stop_go.penalty_type == "stop_go"


def test_openf1_manifest_pins_payload_and_date_range() -> None:
    entry = _manifest_entry(
        "race_control",
        9979,
        [
            {"date": "2025-05-25T14:00:00Z"},
            {"date": "2025-05-25T14:45:00Z"},
        ],
        retrieved_at="2025-05-25T15:00:00+00:00",
        http_status=200,
        cache_status="fetched",
    )

    assert entry["endpoint"] == "/v1/race_control"
    assert entry["row_count"] == 2
    assert len(entry["sha256"]) == 64
    assert entry["date_min_utc"] == "2025-05-25T14:00:00+00:00"
    assert entry["date_max_utc"] == "2025-05-25T14:45:00+00:00"


def test_fastf1_pit_time_uses_the_openf1_driver_lap_anchor() -> None:
    laps = _laps(
        DriverNumber=["44", "44"],
        Driver=["HAM", "HAM"],
        LapNumber=[18, 19],
        LapStartTime=[100, 200],
        PitInTime=[110, None],
        PitOutTime=[None, 230],
        Compound=["HARD", "MEDIUM"],
        TyreLife=[18, 1],
        Stint=[1, 2],
        TrackStatus=["1", "1"],
    )
    openf1_laps = pd.DataFrame(
        {
            "driver_number": [44, 44],
            "lap_number": [18, 19],
            "date_start": [
                "2025-01-01T00:00:00Z",
                "2025-01-01T00:01:00Z",
            ],
        }
    )

    [record] = build_stop_purpose_records(
        laps,
        _rcm(),
        year=2025,
        race="Monaco",
        session_key=1,
        meeting_key=2,
        sample_stops=set(),
        openf1_laps=openf1_laps,
    )

    assert record.pit_in_utc == "2025-01-01T00:00:10+00:00"
    assert record.openf1_lap_date_start_utc == "2025-01-01T00:00:00+00:00"
    assert record.intra_lap_offset_s == 10.0
    assert record.anchor_source == "openf1_v1_laps"
    assert record.anchor_precision == "approximate"
    assert record.timestamp_alignment == "anchored_openf1_lap_approximate"


def test_late_penalty_confirmation_is_not_attached_to_a_later_stop() -> None:
    laps = _laps(
        DriverNumber=["63", "63", "63", "63"],
        Driver=["RUS", "RUS", "RUS", "RUS"],
        LapNumber=[53, 54, 68, 69],
        LapStartTime=[100, 200, 300, 400],
        PitInTime=[210, None, 410, None],
        PitOutTime=[None, 230, None, 430],
        Compound=["HARD", "MEDIUM", "MEDIUM", "HARD"],
        TyreLife=[53, 1, 15, 1],
        Stint=[1, 2, 2, 3],
        TrackStatus=["1", "1", "1", "1"],
    )
    rcm = _rcm(
        session_key=[9979],
        lap_number=[78],
        date=["2025-05-25T14:45:40Z"],
        message=["PENALTY SERVED - DRIVE THROUGH PENALTY FOR CAR 63 (RUS)"],
    )
    openf1_laps = pd.DataFrame(
        {
            "driver_number": [63, 63, 63, 63],
            "lap_number": [53, 54, 68, 69],
            "date_start": [
                "2025-05-25T14:13:00Z",
                "2025-05-25T14:14:00Z",
                "2025-05-25T14:33:00Z",
                "2025-05-25T14:34:00Z",
            ],
        }
    )

    records = build_stop_purpose_records(
        laps,
        rcm,
        year=2025,
        race="Monaco",
        session_key=9979,
        meeting_key=1261,
        sample_stops=set(),
        openf1_laps=openf1_laps,
    )

    assert [(record.pit_in_lap, record.primary_label) for record in records] == [
        (53, STRATEGIC_TYRE_CHANGE),
        (68, STRATEGIC_TYRE_CHANGE),
    ]
    assert all(record.penalty_type == "none" for record in records)


def test_penalty_lifecycle_resolves_russell_to_the_compatible_entry_only() -> None:
    laps = _laps(
        DriverNumber=["63"] * 6,
        Driver=["RUS"] * 6,
        LapNumber=[53, 54, 62, 63, 68, 69],
        LapStartTime=[100, 200, 300, 400, 500, 600],
        PitInTime=[210, None, 1310, None, 1510, None],
        PitOutTime=[None, 230, None, 1330, None, 1530],
        Compound=["HARD", "MEDIUM", "MEDIUM", "MEDIUM", "MEDIUM", "HARD"],
        TyreLife=[53, 1, 9, 10, 15, 1],
        Stint=[1, 2, 2, 2, 2, 3],
        TrackStatus=["1"] * 6,
    )
    rcm = _rcm(
        session_key=[9979, 9979],
        lap_number=[53, 78],
        date=["2025-05-25T14:11:10Z", "2025-05-25T14:45:40Z"],
        message=[
            "FIA STEWARDS: DRIVE THROUGH PENALTY FOR CAR 63 (RUS)",
            "PENALTY SERVED - DRIVE THROUGH PENALTY FOR CAR 63 (RUS)",
        ],
    )
    openf1_laps = pd.DataFrame(
        {
            "driver_number": [63] * 6,
            "lap_number": [53, 54, 62, 63, 68, 69],
            "date_start": [
                "2025-05-25T14:13:00Z",
                "2025-05-25T14:14:00Z",
                "2025-05-25T14:25:00Z",
                "2025-05-25T14:26:00Z",
                "2025-05-25T14:33:00Z",
                "2025-05-25T14:34:00Z",
            ],
        }
    )
    records = build_stop_purpose_records(
        laps,
        rcm,
        year=2025,
        race="Monaco",
        session_key=9979,
        meeting_key=1261,
        sample_stops=set(),
        openf1_laps=openf1_laps,
    )
    evidence = [parse_rcm_message(row) for _, row in rcm.iterrows()]

    [lifecycle] = build_penalty_lifecycle(records, [item for item in evidence if item is not None])

    assert lifecycle.status == "resolved_with_conflict"
    assert lifecycle.candidate_event_ids == ("2025:9979:63:53:1",)
    assert lifecycle.served_evidence_id is not None


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
