"""Effect checks for the Arcade strategy wake gate (#1201).

These tests keep the model boundary fake and drive the connector loop itself.
The scheduling contract is what matters here: context is collected on every
lap, dormant laps do not append decisions, and a manual wake can release the
currently held lap without a second connector.
"""

from __future__ import annotations

from pathlib import Path
from threading import Thread

import pandas as pd

from src.arcade.strategy import SimConnector, SimulateRequestDTO, StrategyState


def _connector(*, current_lap_provider=None, lap_range=None, no_llm=True) -> SimConnector:
    request = SimulateRequestDTO(
        year=2025,
        gp="Lusail",
        driver="NOR",
        team="McLaren",
        lap_range=lap_range,
        no_llm=no_llm,
    )
    return SimConnector(
        request=request,
        state=StrategyState(),
        current_lap_provider=current_lap_provider,
    )


def _lap(lap: int, *, track_status: str = "") -> dict:
    return {
        "lap_number": lap,
        "driver": {
            "position": 1,
            "tyre_life": lap,
            "compound": "MEDIUM",
            "lap_time_s": 90.0,
        },
        "weather": {"track_status": track_status},
    }


def test_stop_admissibility_reuses_the_existing_rail_and_cliff_exception():
    from src.strategy.inference.guard_rails import stop_is_admissible

    assert not stop_is_admissible(4, 12, "MEDIUM", 6, False)
    assert stop_is_admissible(6, 12, "MEDIUM", 7, False)
    assert not stop_is_admissible(10, 12, "MEDIUM", 20, False)
    assert stop_is_admissible(54, 57, "MEDIUM", 20, False, cliff_p10=1)
    assert not stop_is_admissible(54, 57, "MEDIUM", 20, False, cliff_p10=99)


def test_dormant_laps_still_ingest_context_and_keep_the_step_boundary(monkeypatch):
    import src.simulation.replay_engine as replay_module

    connector = _connector(lap_range=(4, 12))
    state = connector._state
    connector._load_laps_df = lambda _year: pd.DataFrame()
    connector._resolve_race_dir = lambda _year, _gp: Path(".")
    connector._emit_start = lambda *_args: None
    connector._warmup_models = lambda: None
    connector._load_radio_corpus = lambda _laps_df: None

    laps = [_lap(lap) for lap in range(1, 13)]

    class FakeEngine:
        total_laps = 12

        def __init__(self, *_args, **_kwargs):
            pass

        def replay(self):
            return iter(laps)

    monkeypatch.setattr(replay_module, "RaceReplayEngine", FakeEngine)

    ingested: list[int] = []
    stepped: list[int] = []

    def collect(lap_number: int):
        ingested.append(lap_number)
        return [], []

    def step(_laps_df, lap_state, _prev_lap_time):
        stepped.append(lap_state["lap_number"])
        return 90.0

    connector._collect_lap_context = collect
    connector._step_once = step
    connector._drive_pipeline()

    assert ingested == list(range(1, 13))
    assert stepped == [6, 7, 8]
    assert state.finished is True


def test_track_status_wakes_when_the_radio_corpus_has_no_deploy_event():
    connector = _connector()

    reason = connector._wake_reason(
        _lap(2, track_status="4"),
        total_laps=12,
        sc_active=False,
        manual_override=False,
    )

    assert reason == "track neutralisation"


def test_rich_profile_remains_ungated_until_its_paid_measurement(monkeypatch):
    import src.simulation.replay_engine as replay_module

    connector = _connector(lap_range=(1, 3), no_llm=False)
    connector._load_laps_df = lambda _year: pd.DataFrame()
    connector._resolve_race_dir = lambda _year, _gp: Path(".")
    connector._emit_start = lambda *_args: None
    connector._warmup_models = lambda: None
    connector._load_radio_corpus = lambda _laps_df: None
    laps = [_lap(lap) for lap in range(1, 4)]

    class FakeEngine:
        total_laps = 3

        def __init__(self, *_args, **_kwargs):
            pass

        def replay(self):
            return iter(laps)

    monkeypatch.setattr(replay_module, "RaceReplayEngine", FakeEngine)
    stepped: list[int] = []
    connector._collect_lap_context = lambda _lap_number: ([], [])
    connector._step_once = lambda _df, lap_state, _prev: (
        stepped.append(lap_state["lap_number"]) or 90.0
    )

    connector._drive_pipeline()

    assert stepped == [1, 2, 3]
    assert connector._state.wake_state == "awake · rich profile ungated"


def test_manual_wake_releases_a_current_dormant_lap():
    connector = _connector(current_lap_provider=lambda: 5)
    result: list[bool] = []
    worker = Thread(
        target=lambda: result.append(connector._wait_for_dormant_progress(5, poll_interval_s=0.01))
    )
    worker.start()
    connector.toggle_manual_override()
    worker.join(timeout=1.0)

    assert not worker.is_alive()
    assert result == [True]


def test_dormant_status_identifies_the_held_decision_lap():
    from src.pitwall.agents_view.panels import build_status_bar

    payload = {
        "arcade": {"lap": 9},
        "strategy": {
            "wake_state": "dormant · no admissible stop",
            "latest": {"lap_number": 8},
        },
    }

    assert build_status_bar(payload) == {
        "text": "lap 9 · dormant · no admissible stop · last decision L8",
        "transient": False,
    }
