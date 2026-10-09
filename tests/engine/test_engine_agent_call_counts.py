"""Guard per-lap dispatch through the real engine without loading model weights."""

from __future__ import annotations

import dataclasses
import os
import subprocess
import sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from threading import Lock
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
ALWAYS_ON = ("N25", "N26", "N27", "N29")


class _CallCountMismatch(AssertionError):
    """Identify a dispatch regression separately from import or assembly failures."""

    def __init__(self, actual: Counter, expected: Counter) -> None:
        super().__init__(f"dispatch counts: {dict(actual)} != {dict(expected)}")
        self.actual = actual
        self.expected = expected


def test_engine_agent_call_counts() -> None:
    """Check per-profile calls and reject duplicate or misrouted dispatches."""
    env = {
        **os.environ,
        "F1_STRAT_OFFLINE": "1",
        "F1_STRAT_NO_FIRST_RUN": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for mode in ("normal", "duplicate", "profile-mismatch"):
        child = subprocess.run(
            [sys.executable, "-B", str(Path(__file__).resolve()), mode],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        assert child.returncode == 0, f"{mode}:\n{child.stdout}\n{child.stderr}"
        assert f"call-count guard: {mode} passed" in child.stdout


def _exercise(engine, orchestrator, no_llm, profile, retain, duplicate=False, misroute=None):
    """Run consecutive active/quiet laps, substituting only agent-stage boundaries."""
    import math

    import pandas as pd

    from src.agents.pace_agent import PaceOutput
    from src.agents.pit_strategy_agent import PitStrategyOutput
    from src.agents.race_situation_agent import RaceSituationOutput
    from src.agents.radio_agent import RadioMessage, RadioOutput
    from src.agents.rag_agent import RegulationContext
    from src.agents.tire_agent import TireOutput
    from src.f1_strat_manager.rcm_events import RCMEvent
    from src.rag.retriever import RegulationChunk

    calls = Counter()
    entry_calls = Counter()
    expected = Counter()
    expected_entries = Counter()
    lock = Lock()
    prompts = []
    recommendations = []
    lap = 20
    regulation = "In-memory regulation context for the active lap."
    passage = "In-memory passage with an explicit applicability condition."

    def record(agent, state=None, frame=None):
        if state is not None:
            assert state["lap_number"] == lap
            assert state["session_meta"]["driver"] == "NOR"
            assert state["session_meta"]["year"] == 2025
        if frame is not None:
            assert set(frame["GP_Name"]) == {"Lusail"}
            assert list(frame["LapNumber"]) == [20, 21]
        with lock:
            calls[lap, agent] += 1

    def pace(state):
        record("N25", state)
        return PaceOutput(95.0, 0.2, 0.3, 94.0, 96.0, "pace evidence")

    def tire(state, frame):
        record("N26", state, frame)
        p10, p50, p90 = (1.0, 2.0, 3.0) if lap == 20 else (10.0, 12.0, 14.0)
        return TireOutput(
            compound="MEDIUM",
            current_tyre_life=lap,
            deg_rate=0.1,
            laps_to_cliff_p10=p10,
            laps_to_cliff_p50=p50,
            laps_to_cliff_p90=p90,
            gp_name="Lusail",
            cumulative_deg_s=0.4,
            deg_cost_s=0.4,
            reasoning="tire evidence",
        )

    def situation(state, frame):
        record("N27", state, frame)
        assert all(isinstance(event, RCMEvent) for event in state["rcm_events"])
        assert len(state["rcm_events"]) == (1 if lap == 20 else 0)
        return RaceSituationOutput(
            overtake_prob=0.0 if lap == 20 else 0.1,
            sc_prob_3lap=1.0 if lap == 20 else 0.0,
            gap_ahead_s=None,
            pace_delta_s=0.2,
            reasoning="situation evidence",
            sc_currently_active=lap == 20,
            vsc_active=False,
        )

    def radio(state, frame=None):
        record("N29", state, frame)
        assert state["lap"] == lap
        assert len(state["radio_msgs"]) == 1
        assert isinstance(state["radio_msgs"][0], RadioMessage)
        assert state["radio_msgs"][0].lap == lap
        return RadioOutput(reasoning="radio evidence")

    def pit(state, frame):
        record("N28", state, frame)
        assert lap == 20
        assert state["laps_to_cliff"] == 2.0
        assert state["sc_prob"] == 1.0
        assert state["sc_currently_active"] is True
        return PitStrategyOutput(
            action="PIT_NOW",
            recommended_lap=lap,
            compound_recommendation="HARD",
            stop_duration_p05=2.2,
            stop_duration_p50=2.8,
            stop_duration_p95=3.8,
            undercut_prob=0.5,
            undercut_target=None,
            sc_reactive=True,
            reasoning="pit evidence",
        )

    def rag(question, year=None):
        record("N30")
        assert lap == 20 and year == 2025
        assert "Safety Car" in question
        return RegulationContext(
            question=question,
            answer=regulation,
            articles=["Article 55.8"],
            chunks=[RegulationChunk(passage, "Article 55.8", "sporting", 2025, 0.9)],
        )

    def track_entry(agent, route, callback):
        def tracked(*args, **kwargs):
            with lock:
                entry_calls[lap, route, agent] += 1
            return callback(*args, **kwargs)

        return tracked

    class Synthesis:
        def invoke(self, prompt):
            assert profile == "rich", "no-llm reached LLM synthesis"
            assert f"Driver: NOR | Lap: {lap}/57" in prompt
            for evidence in (
                "pace evidence",
                "tire evidence",
                "situation evidence",
                "radio evidence",
                "STAY_OUT",
                "PIT_NOW",
                "UNDERCUT",
                "OVERCUT",
            ):
                assert evidence in prompt
            if lap == 20:
                assert regulation in prompt and passage in prompt
                assert "Article 55.8" in prompt and "pit evidence" in prompt
            else:
                assert regulation not in prompt and passage not in prompt
                assert "not activated (no cliff pressure, no radio problem)" in prompt
            prompts.append(lap)
            return orchestrator._LLMSynthesis(
                action="STAY_OUT",
                reasoning="assembled from in-memory synthesis",
                confidence=0.7,
                pace_mode="NEUTRAL",
                target_lap_time_s=95.0,
                risk_posture="BALANCED",
                undercut_target="GHOST",
            )

    frame = pd.DataFrame(
        [
            {"Driver": "NOR", "LapNumber": number, "GP_Name": gp, "Year": 2025}
            for gp in ("Lusail", "Monza")
            for number in (20, 21)
        ]
    )
    with ExitStack() as patches:
        rich_entries = {
            "run_pace_agent_from_state": track_entry("N25", "shared", pace),
            "run_tire_agent_from_state": track_entry("N26", "rich", tire),
            "run_race_situation_agent_from_state": track_entry("N27", "rich", situation),
            "run_radio_agent_from_state": track_entry("N29", "rich", radio),
            "run_pit_strategy_agent_from_state": track_entry("N28", "rich", pit),
            "run_rag_agent": track_entry("N30", "rich", rag),
        }
        for name, replacement in rich_entries.items():
            patches.enter_context(patch.object(orchestrator, name, replacement))

        no_llm_entries = {
            "run_pace_agent_from_state": track_entry("N25", "shared", pace),
            "_tire_no_llm": track_entry("N26", "no-llm", tire),
            "_situation_no_llm": track_entry("N27", "no-llm", situation),
            "_run_radio_no_llm": track_entry("N29", "no-llm", radio),
        }
        if misroute == "tire":
            no_llm_entries["_tire_no_llm"] = rich_entries["run_tire_agent_from_state"]
        elif misroute == "situation":
            no_llm_entries["_situation_no_llm"] = rich_entries[
                "run_race_situation_agent_from_state"
            ]
        elif misroute == "radio":
            no_llm_entries["_run_radio_no_llm"] = rich_entries["run_radio_agent_from_state"]
        for name, replacement in no_llm_entries.items():
            patches.enter_context(patch.object(no_llm, name, replacement))
        patches.enter_context(patch.object(engine, "_get_orchestrator_llm", Synthesis))
        if duplicate:
            dispatch = engine._run_always_on_agents_from_state

            def dispatch_twice(*args, **kwargs):
                dispatch(*args, **kwargs)
                return dispatch(*args, **kwargs)

            patches.enter_context(
                patch.object(engine, "_run_always_on_agents_from_state", dispatch_twice)
            )

        for lap in (20, 21):
            race = orchestrator.RaceState(
                driver="NOR",
                lap=lap,
                total_laps=57,
                position=2,
                compound="MEDIUM",
                tyre_life=lap,
                gap_ahead_s=None,
                pace_delta_s=0.2,
                air_temp=28.0,
                track_temp=35.0,
                radio_msgs=[{"driver": "NOR", "lap": lap, "text": "Current lap report"}],
                rcm_events=[
                    {
                        "message": "SAFETY CAR DEPLOYED",
                        "category": "SafetyCar",
                        "flag": "",
                        "lap": lap,
                    }
                ]
                if lap == 20
                else [],
            )
            state = {
                "lap_number": lap,
                "year": 2025,
                "driver": {"driver": "NOR", "position": 2, "compound": "MEDIUM", "tyre_life": lap},
                "session_meta": {
                    "driver": "NOR",
                    "gp_name": "Lusail",
                    "year": 2025,
                    "total_laps": 57,
                },
                "rivals": [{"driver": "VER", "position": 1, "interval_to_driver_s": None}],
                "weather": {"air_temp": 28.0, "track_temp": 35.0, "rainfall": False},
            }
            rec, outputs, timings = engine.run_lap(
                race, frame, state, profile=profile, return_agent_outputs=retain
            )
            expected.update({(lap, agent): 1 for agent in ALWAYS_ON})
            expected_entries[(lap, "shared", "N25")] = 1
            route = "rich" if profile == "rich" else "no-llm"
            expected_entries.update({(lap, route, agent): 1 for agent in ("N26", "N27", "N29")})
            if profile == "rich" and lap == 20:
                expected.update({(lap, "N28"): 1, (lap, "N30"): 1})
                expected_entries.update({(lap, "rich", agent): 1 for agent in ("N28", "N30")})
            with lock:
                actual = calls.copy()
                actual_entries = entry_calls.copy()
            if actual != expected:
                raise _CallCountMismatch(actual, expected.copy())
            if actual_entries != expected_entries:
                raise _CallCountMismatch(actual_entries, expected_entries)

            assert isinstance(rec, orchestrator.StrategyRecommendation)
            assert set(rec.scenario_scores) == {"STAY_OUT", "PIT_NOW", "UNDERCUT", "OVERCUT"}
            for scores in rec.scenario_scores.values():
                assert set(scores) == {"E", "P10", "P90", "score"}
                assert all(math.isfinite(value) for value in scores.values())
            assert set(timings) == {
                "always_on",
                "routing",
                "conditional",
                "mc",
                "synthesis",
                "total",
            }
            assert all(math.isfinite(value) and value >= 0 for value in timings.values())
            context = regulation if profile == "rich" and lap == 20 else ""
            assert rec.regulation_context == context
            if profile == "rich":
                assert rec.action == "STAY_OUT" and rec.confidence == 0.7
                assert rec.undercut_target is None
                assert rec.target_lap_time_s == (None if lap == 20 else 95.0)
                assert rec.pit_lap_target == (20 if lap == 20 else None)
                assert rec.compound_next == ("HARD" if lap == 20 else None)
            else:
                best = orchestrator.best_mc_candidate(rec.scenario_scores)
                action, reason = no_llm.apply_guard_rails(
                    best,
                    lap,
                    57,
                    "MEDIUM",
                    lap,
                    1.0 if lap == 20 else 10.0,
                    sc_active=lap == 20,
                )
                assert rec.action == action and rec.confidence == 0.0
                assert rec.reasoning.startswith("[no-llm mode")
                assert rec.pit_lap_target is None and rec.compound_next is None
                assert rec.target_lap_time_s is None
                if outputs is not None:
                    assert outputs["guardrail_reason"] == reason
            if not retain:
                assert outputs is None
            else:
                assert set(outputs) == {
                    "pace_out",
                    "tire_out",
                    "situation_out",
                    "radio_out",
                    "pit_out",
                    "regulation_context",
                    "rag",
                    "active",
                    "guardrail_reason",
                    "pit_exit",
                }
                for key, output_type in (
                    ("pace_out", PaceOutput),
                    ("tire_out", TireOutput),
                    ("situation_out", RaceSituationOutput),
                    ("radio_out", RadioOutput),
                ):
                    assert isinstance(outputs[key], output_type)
                assert outputs["tire_out"].warning_level == ("PIT_SOON" if lap == 20 else "OK")
                assert outputs["situation_out"].sc_currently_active == (lap == 20)
                assert set(outputs["active"]) == ({"N28", "N30"} if lap == 20 else set())
                assert outputs["regulation_context"] == context
                assert outputs["pit_exit"] is None  # No measured rival gap was supplied.
                if context:
                    assert isinstance(outputs["pit_out"], PitStrategyOutput)
                    assert outputs["rag"]["answer"] == regulation
                    assert outputs["rag"]["articles"] == ["Article 55.8"]
                    assert outputs["rag"]["chunks"][0]["text"] == passage
                    assert outputs["rag"]["chunks"][0]["year"] == 2025
                else:
                    assert outputs["pit_out"] is None and outputs["rag"] is None
            recommendations.append(rec.model_dump())
    assert prompts == ([20, 21] if profile == "rich" else [])
    return recommendations


def _child(mode: str) -> None:
    """Keep the two import-time configuration exceptions out of the pytest process."""
    sys.path.insert(0, str(ROOT))

    def forbid_network(event, args):
        if event in {"socket.connect", "socket.sendto", "socket.getaddrinfo"}:
            raise AssertionError(f"unexpected network access: {event}")

    sys.addaudithook(forbid_network)
    from src.f1_strat_manager import data_cache

    missing_data = ROOT / "tests" / "fixtures" / "__engine_call_counts_no_data__"
    assert not missing_data.exists()
    os.environ["F1_STRAT_DATA_ROOT"] = str(missing_data)
    targets = {
        ("src.agents.tire_agent", "TireAgentConfig"),
        ("src.agents.race_situation_agent", "RaceSituationConfig"),
    }
    intercepted = set()
    decorate = dataclasses.dataclass

    def import_only_config(cls=None, **kwargs):
        if cls is None:
            return lambda candidate: import_only_config(candidate, **kwargs)
        key = (cls.__module__, cls.__name__)
        if key in targets:
            intercepted.add(key)

            def configure_without_artifacts(self):
                if key == ("src.agents.tire_agent", "TireAgentConfig"):
                    self.circuit_cluster_map = {}
                    self.cliff_pit_soon_by_cluster = {}
                    self.cliff_monitor_by_cluster = {}
                    self.cliff_overrides_by_gp = {}

            cls.__post_init__ = configure_without_artifacts
        return decorate(cls, **kwargs)

    with patch.object(data_cache, "get_data_root", lambda: missing_data):
        with patch.object(dataclasses, "dataclass", import_only_config):
            from src.agents import strategy_orchestrator as orchestrator
            from src.strategy.inference import engine, no_llm

        assert intercepted == targets
        if mode == "duplicate":
            try:
                _exercise(engine, orchestrator, no_llm, "rich", True, duplicate=True)
            except _CallCountMismatch as failure:
                assert failure.expected == Counter(
                    {(20, agent): 1 for agent in (*ALWAYS_ON, "N28", "N30")}
                )
                assert failure.actual == Counter(
                    {
                        **{(20, agent): 2 for agent in ALWAYS_ON},
                        (20, "N28"): 1,
                        (20, "N30"): 1,
                    }
                )
            else:
                raise AssertionError("duplicate always-on dispatch escaped the guard")
        elif mode == "profile-mismatch":
            agent_for = {"tire": "N26", "situation": "N27", "radio": "N29"}
            for target, agent in agent_for.items():
                try:
                    _exercise(
                        engine,
                        orchestrator,
                        no_llm,
                        "no-llm",
                        True,
                        misroute=target,
                    )
                except _CallCountMismatch as failure:
                    assert failure.actual != failure.expected
                    assert any(
                        route == "rich" and called_agent == agent
                        for _, route, called_agent in failure.actual
                    )
                else:
                    raise AssertionError(f"no-llm {target} entrypoint misroute escaped the guard")
        else:
            assert mode == "normal"
            for profile in ("rich", "no-llm"):
                retained = _exercise(engine, orchestrator, no_llm, profile, True)
                discarded = _exercise(engine, orchestrator, no_llm, profile, False)
                assert retained == discarded
    assert not missing_data.exists()
    print(f"call-count guard: {mode} passed")


if __name__ == "__main__":
    _child(sys.argv[1])
