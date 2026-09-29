from __future__ import annotations

import pandas as pd

from scripts.measure_public_relative_pace import measure_candidate


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


def test_relative_pace_uses_only_pre_cutoff_public_rows() -> None:
    laps = pd.DataFrame(
        {
            "LapNumber": [2, 2],
            "DriverNumber": [44, 1],
            "Position": [2, 1],
            "LapTime": pd.to_timedelta([90.0, 91.0], unit="s"),
        }
    )
    intervals = pd.DataFrame(
        {
            "session_key": [1, 1, 1, 1, 1, 1],
            "driver_number": [44, 1, 44, 1, 44, 1],
            "date": pd.to_datetime(
                [
                    "2025-01-01T00:01:20Z",
                    "2025-01-01T00:01:21Z",
                    "2025-01-01T00:02:50Z",
                    "2025-01-01T00:02:51Z",
                    "2025-01-01T00:03:10Z",
                    "2025-01-01T00:03:11Z",
                ],
                utc=True,
            ),
            "gap_to_leader_seconds": [5.0, 4.0, 6.0, 4.0, 8.0, 5.0],
        }
    )

    result = measure_candidate(_candidate(), laps, intervals)

    assert result["status"] == "comparable_pre_cutoff_pair"
    assert result["raw_relative_pace_s"] == -1.0
    assert result["public_current_gap_s"] == 2.0
    assert result["public_previous_gap_s"] == 1.0
    assert result["public_relative_pace_s"] == 1.0


def test_relative_pace_keeps_missing_anchor_out() -> None:
    candidate = _candidate()
    candidate["pit_in_utc"] = None

    result = measure_candidate(candidate, pd.DataFrame(), pd.DataFrame())

    assert result["status"] == "no_anchor"


def test_relative_pace_rejects_a_pair_with_a_pit_transition() -> None:
    laps = pd.DataFrame(
        {
            "LapNumber": [2, 2],
            "DriverNumber": [44, 1],
            "Position": [2, 1],
            "LapTime": pd.to_timedelta([90.0, 91.0], unit="s"),
            "PitOutTime": [pd.NaT, pd.Timedelta(seconds=1)],
        }
    )

    result = measure_candidate(_candidate(), laps, pd.DataFrame())

    assert result["status"] == "pre_lap_pair_has_pit_transition"


def test_relative_pace_rejects_a_public_gap_discontinuity() -> None:
    laps = pd.DataFrame(
        {
            "LapNumber": [2, 2],
            "DriverNumber": [44, 1],
            "Position": [2, 1],
            "LapTime": pd.to_timedelta([90.0, 91.0], unit="s"),
        }
    )
    intervals = pd.DataFrame(
        {
            "session_key": [1, 1, 1, 1],
            "driver_number": [44, 1, 44, 1],
            "date": pd.to_datetime(
                [
                    "2025-01-01T00:01:20Z",
                    "2025-01-01T00:01:21Z",
                    "2025-01-01T00:02:50Z",
                    "2025-01-01T00:02:51Z",
                ],
                utc=True,
            ),
            "gap_to_leader_seconds": [14.0, 0.0, 3.0, 0.0],
        }
    )

    result = measure_candidate(_candidate(), laps, intervals)

    assert result["status"] == "public_gap_discontinuity"
    assert result["public_gap_change_s"] == -11.0
