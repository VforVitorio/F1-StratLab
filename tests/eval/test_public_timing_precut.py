from __future__ import annotations

import pandas as pd

from scripts.measure_public_timing_precut import measure_row


def test_public_timing_cutoff_excludes_future_rows() -> None:
    intervals = pd.DataFrame(
        {
            "session_key": [1, 1, 1],
            "driver_number": [44, 44, 44],
            "date": pd.to_datetime(
                [
                    "2025-01-01T00:00:05Z",
                    "2025-01-01T00:00:09Z",
                    "2025-01-01T00:00:11Z",
                ],
                utc=True,
            ),
            "interval_seconds": [2.1, 1.8, 0.4],
            "gap_to_leader_seconds": [8.0, 7.5, 7.1],
        }
    )
    row = {
        "event_id": "2025:1:44:10:1",
        "race": "Test",
        "driver": "HAM",
        "driver_number": 44,
        "session_key": 1,
        "pit_in_lap": 10,
        "review_status": "unreviewed",
        "review_disposition": "unreviewed",
        "pit_in_utc": "2025-01-01T00:00:10Z",
    }

    result = measure_row(row, intervals)

    assert result["status"] == "precut_snapshot"
    assert result["latest_public_utc"] == "2025-01-01T00:00:09+00:00"
    assert result["driver_interval_seconds"] == 1.8
    assert result["cutoff_lag_s"] == 1.0


def test_public_timing_marks_an_old_snapshot_stale() -> None:
    intervals = pd.DataFrame(
        {
            "session_key": [1],
            "driver_number": [44],
            "date": pd.to_datetime(["2025-01-01T00:00:00Z"], utc=True),
            "interval_seconds": [1.8],
            "gap_to_leader_seconds": [7.5],
        }
    )
    row = {
        "event_id": "2025:1:44:10:1",
        "race": "Test",
        "driver": "HAM",
        "driver_number": 44,
        "session_key": 1,
        "pit_in_lap": 10,
        "review_status": "unreviewed",
        "review_disposition": "unreviewed",
        "pit_in_utc": "2025-01-01T00:00:20Z",
    }

    result = measure_row(row, intervals)

    assert result["status"] == "precut_snapshot_stale"


def test_public_timing_keeps_missing_anchor_explicit() -> None:
    row = {
        "event_id": "2025:1:44:10:1",
        "race": "Test",
        "driver": "HAM",
        "driver_number": 44,
        "session_key": 1,
        "pit_in_lap": 10,
        "review_status": "unreviewed",
        "review_disposition": "unreviewed",
        "pit_in_utc": None,
    }

    result = measure_row(row, pd.DataFrame())

    assert result["status"] == "no_anchor"
    assert result["latest_public_utc"] is None
