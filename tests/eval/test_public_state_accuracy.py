from __future__ import annotations

import pandas as pd

from scripts.measure_public_state_accuracy import measure_candidate


def _candidate() -> dict:
    return {
        "event_id": "2025:1:44:3:1",
        "race": "Test",
        "driver": "HAM",
        "driver_number": 44,
        "session_key": 1,
        "pit_in_lap": 3,
        "review_status": "unreviewed",
        "review_disposition": "unreviewed",
        "pit_in_utc": "2025-01-01T00:03:00Z",
    }


def test_state_accuracy_compares_pair_order_and_gap_without_future_rows() -> None:
    laps = pd.DataFrame(
        {
            "LapNumber": [2, 2],
            "DriverNumber": [44, 1],
            "Position": [2, 1],
            "Time": pd.to_timedelta([191.0, 190.0], unit="s"),
        }
    )
    intervals = pd.DataFrame(
        {
            "session_key": [1, 1, 1, 1, 1],
            "driver_number": [44, 1, 2, 3, 4],
            "date": pd.to_datetime(
                [
                    "2025-01-01T00:02:59Z",
                    "2025-01-01T00:02:59Z",
                    "2025-01-01T00:02:58Z",
                    "2025-01-01T00:02:57Z",
                    "2025-01-01T00:02:56Z",
                ],
                utc=True,
            ),
            "gap_to_leader_seconds": [5.0, 0.0, 8.0, 12.0, 16.0],
            "is_lapped": [False, False, False, False, False],
        }
    )

    result = measure_candidate(_candidate(), laps, intervals)

    assert result["status"] == "comparable_pre_cutoff_pair"
    assert result["raw_position"] == 2
    assert result["public_pair_order_matches"] is True
    assert result["raw_pair_gap_s"] == 1.0
    assert result["public_pair_gap_s"] == 5.0
    assert result["pair_gap_error_s"] == 4.0


def test_state_accuracy_keeps_missing_anchor_out() -> None:
    candidate = _candidate()
    candidate["pit_in_utc"] = None
    candidate["cutoff_utc"] = None

    result = measure_candidate(candidate, pd.DataFrame(), pd.DataFrame())

    assert result["status"] == "no_anchor"


def test_state_accuracy_records_a_public_pair_order_mismatch() -> None:
    laps = pd.DataFrame(
        {
            "LapNumber": [2, 2],
            "DriverNumber": [44, 1],
            "Position": [2, 1],
            "Time": pd.to_timedelta([191.0, 190.0], unit="s"),
        }
    )
    intervals = pd.DataFrame(
        {
            "session_key": [1, 1],
            "driver_number": [44, 1],
            "date": pd.to_datetime(["2025-01-01T00:02:59Z", "2025-01-01T00:02:59Z"], utc=True),
            "gap_to_leader_seconds": [0.0, 1.0],
            "is_lapped": [False, False],
        }
    )

    result = measure_candidate(_candidate(), laps, intervals)

    assert result["status"] == "comparable_pre_cutoff_pair"
    assert result["public_pair_order_matches"] is False
