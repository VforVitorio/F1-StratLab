"""Historical Arcade flag intervals from cached race status and frame data."""

import numpy as np

from src.arcade.data import (
    CACHE_VERSION,
    DriverFrames,
    SessionData,
    SessionLoader,
    _build_race_events,
)


def _frames_with_laps(laps: list[int]) -> DriverFrames:
    count = len(laps)
    numbers = np.zeros(count, dtype=np.int64)
    values = np.zeros(count, dtype=np.float64)
    return DriverFrames(
        t=values,
        x=values,
        y=values,
        speed=values,
        gear=numbers,
        drs=numbers,
        throttle=values,
        brake=values,
        lap=np.asarray(laps, dtype=np.int64),
        dist=values,
        rel_dist=values,
        tyre=numbers,
        tyre_life=values,
        active=np.ones(count, dtype=np.bool_),
    )


def test_events_use_race_leader_lap_boundaries_and_status_priority() -> None:
    frames = {
        "NOR": _frames_with_laps([1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6]),
        "PIA": _frames_with_laps([1, 1, 1, 2, 2, 3, 3, 3, 4, 4, 5, 5]),
    }

    events = _build_race_events(
        {1: "1", 2: "4", 3: "41", 4: "1", 5: "6", 6: "245"},
        frames,
        total_frames=12,
    )

    assert events == [
        {"type": "safety_car", "frame": 2, "end_frame": 6},
        {"type": "vsc", "frame": 8, "end_frame": 10},
        {"type": "red_flag", "frame": 10, "end_frame": 12},
    ]


def test_clear_or_unknown_laps_break_intervals_and_missing_boundaries_are_ignored() -> None:
    frames = {"NOR": _frames_with_laps([1, 1, 2, 2, 3, 3, 4, 4, 5, 5])}

    events = _build_race_events({1: "2", 2: "1", 3: "2", 4: "", 9: "5"}, frames, total_frames=10)

    assert events == [
        {"type": "yellow_flag", "frame": 0, "end_frame": 2},
        {"type": "yellow_flag", "frame": 4, "end_frame": 6},
    ]


def test_cached_session_rebuilds_empty_events_without_invalidating_the_cache(
    tmp_path, monkeypatch
) -> None:
    loader = SessionLoader(cache_dir=tmp_path)
    cache_path = loader._cache_path(2025, 1)
    cache_path.touch()
    cached = SessionData(
        version=CACHE_VERSION,
        gp_name="Melbourne",
        year=2025,
        frames_by_driver={"NOR": _frames_with_laps([1, 1, 2, 2, 3, 3])},
        total_frames=6,
        events=[],
        track_status_by_lap={2: "4"},
    )
    monkeypatch.setattr(loader, "_read_cache", lambda _path: cached)

    result = loader.load(2025, 1, "Melbourne")

    assert result.events == [{"type": "safety_car", "frame": 2, "end_frame": 4}]
