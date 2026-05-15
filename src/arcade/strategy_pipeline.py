"""Arcade-local strategy pipeline.

The arcade process runs the full N31 multi-agent pipeline without going
through the backend SSE endpoint, so the dashboard subprocess can subscribe
to the arcade TCP stream and receive both the synthesised
``StrategyRecommendation`` and the raw per-sub-agent outputs (predicted lap
time, CI bounds, tyre cliff percentiles, overtake and SC probabilities,
undercut probability, pit duration percentiles, RAG text, …) on the same
wire.

Body is a copy of ``src.agents.strategy_orchestrator.run_strategy_orchestrator_from_state``
kept intentionally separate: the CLI and Streamlit paths import the
orchestrator directly and must stay unaffected by anything the arcade
does. Private helpers are imported from the orchestrator module — the same
pattern ``backend/services/simulation/simulator.py::_run_no_llm_path``
already uses (L339-L343), so it is an established way of reusing
implementation details without touching ``src/agents/``.

If you change the orchestrator body upstream, mirror the change here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

from src.agents.strategy_orchestrator import (
    _assemble_recommendation,
    _build_orchestrator_prompt,
    _decide_agents_to_call,
    _get_orchestrator_llm,
    _run_always_on_agents_from_state,
    _run_conditional_agents,
    _run_mc_simulation,
)

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from src.agents.strategy_orchestrator import RaceState, StrategyRecommendation


def run_strategy_pipeline(
    race_state: "RaceState",
    laps_df: pd.DataFrame,
    lap_state: dict | None = None,
) -> tuple["StrategyRecommendation", dict]:
    """Run the full N31 pipeline and return both the recommendation and the
    raw per-agent outputs.

    The agent outputs dict carries the six sub-agent dataclasses under
    ``pace_out``, ``tire_out``, ``situation_out``, ``radio_out``,
    ``pit_out``, plus ``regulation_context`` (string from N30 RAG) and
    ``active`` (list of conditional agents that fired this lap). Shape is
    identical to the intermediate state inside
    ``run_strategy_orchestrator_from_state`` — so any formatter that knows
    the orchestrator internals can be reused unchanged.

    Pipeline order matches the orchestrator exactly: always-on agents →
    routing decision → conditional agents → MC simulation → LLM synthesis.
    """
    if lap_state is None:
        lap_state = _build_default_lap_state(race_state, laps_df)

    pace_out, tire_out, situation_out, radio_out = _run_always_on_agents_from_state(
        race_state, laps_df, lap_state
    )

    active = _decide_agents_to_call(
        tire_warning=tire_out.warning_level,
        sc_prob_3lap=situation_out.sc_prob_3lap,
        radio_alerts=radio_out.alerts,
        sc_currently_active=situation_out.sc_currently_active,
    )

    pit_out, regulation_context, rag_dict = _run_conditional_agents(
        active=active,
        lap_state=lap_state,
        tire_out=tire_out,
        situation_out=situation_out,
        race_state=race_state,
        laps_df=laps_df,
    )
    regulation_context = regulation_context or ""

    mc_results = _run_mc_simulation(
        pace_out=pace_out,
        tire_out=tire_out,
        situation_out=situation_out,
        pit_out=pit_out,
        alpha=race_state.risk_tolerance,
    )
    best_mc = max(mc_results, key=lambda s: mc_results[s]["score"])

    prompt = _build_orchestrator_prompt(
        race_state=race_state,
        mc_results=mc_results,
        best_mc=best_mc,
        pace_out=pace_out,
        tire_out=tire_out,
        situation_out=situation_out,
        pit_out=pit_out,
        radio_out=radio_out,
        regulation_context=regulation_context,
    )
    synth = _get_orchestrator_llm().invoke(prompt)
    rec = _assemble_recommendation(synth, pit_out, mc_results, regulation_context)

    agent_outputs = {
        "pace_out": pace_out,
        "tire_out": tire_out,
        "situation_out": situation_out,
        "radio_out": radio_out,
        "pit_out": pit_out,
        "regulation_context": regulation_context,
        # Structured RAG payload (question / answer / articles / chunks)
        # for the dashboard's RAG card. ``regulation_context`` above keeps
        # the legacy answer string for the orchestrator's LLM prompt.
        "rag": rag_dict,
        "active": list(active),
    }
    return rec, agent_outputs


def _build_default_lap_state(race_state: "RaceState", laps_df: pd.DataFrame) -> dict:
    """Build the minimal lap_state that every sub-agent expects.

    Mirrors the default branch inside
    ``run_strategy_orchestrator_from_state`` — kept private to this module
    so the arcade pipeline stays self-contained and orchestrator internals
    do not leak into the arcade's call sites.
    """
    driver_rows = laps_df[laps_df["Driver"] == race_state.driver]
    lap_row = driver_rows[driver_rows["LapNumber"] == race_state.lap]
    year = int(laps_df["Year"].iloc[0]) if "Year" in laps_df.columns else 2025
    gp_name = str(laps_df["GP_Name"].iloc[0]) if "GP_Name" in laps_df.columns else ""
    stint = int(lap_row["Stint"].iloc[0]) if not lap_row.empty else 1
    team = str(lap_row["Team"].iloc[0]) if not lap_row.empty and "Team" in lap_row else "Unknown"
    return {
        "lap_number": race_state.lap,
        "driver": {
            "driver": race_state.driver,
            "driver_number": 0,
            "team": team,
            "position": race_state.position,
            "compound": race_state.compound,
            "tyre_life": race_state.tyre_life,
            "stint": stint,
            "lap_time_s": None,
            "speed_st": 300.0,
            "fuel_load": 1 - race_state.lap / max(race_state.total_laps, 1),
        },
        "session_meta": {
            "gp_name": gp_name,
            "gp": gp_name,
            "year": year,
            "driver": race_state.driver,
            "team": team,
            "total_laps": race_state.total_laps,
        },
        "weather": {
            "air_temp": race_state.air_temp,
            "track_temp": race_state.track_temp,
            "rainfall": race_state.rainfall,
            "humidity": 50.0,
        },
        "rivals": [],
    }
