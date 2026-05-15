# Strategy Pipeline — Arcade Duplicate

Why `src/arcade/strategy_pipeline.py` exists as a near-copy of `src/agents/strategy_orchestrator.py::run_strategy_orchestrator_from_state`, what gets duplicated, what does not, and how to keep the two bodies in sync.

## Why the arcade duplicates

The CLI (`scripts/run_simulation_cli.py`) and the Streamlit frontend both call `run_strategy_orchestrator_from_state(race_state, laps_df)` and consume its single return value: a `StrategyRecommendation` dataclass with `action`, `reasoning`, `confidence`, `scenario_scores`, and `regulation_context`. The public contract is narrow on purpose — the orchestrator hides the six sub-agent dataclasses behind a single synthesised decision.

The arcade dashboard needs the opposite. To render the six sub-agent cards, the pace and tire charts, the scenario bars, and the reasoning tabs, the dashboard must see the **raw per-agent outputs**:

- `PaceOutput.lap_time_pred`, `ci_p10`, `ci_p90`, `delta_vs_prev`
- `TireOutput.laps_to_cliff_p10 / p50 / p90`, `warning_level`, `deg_rate`
- `RaceSituationOutput.overtake_prob`, `sc_prob_3lap`, `threat_level`
- `RadioOutput.alerts`, `radio_events`, `rcm_events`, `corrections`
- `PitStrategyOutput.action`, `compound_recommendation`, `stop_duration_p05 / p50 / p95`, `undercut_prob`
- `RegulationContext.answer`, `articles`
- The Monte Carlo scenario scores before they collapse into the recommendation
- The set of conditional agents that fired this lap (the `active` list)

None of this is available from `StrategyRecommendation` alone.

Two obvious alternatives, both rejected:

1. **Extend the public orchestrator to return more fields.** Would force the CLI and Streamlit to depend on a wider return type and break the documented contract. The CLI is also the TFG's PMV and is flagged untouchable.
2. **Call each sub-agent from the arcade directly and skip the orchestrator.** Would duplicate the MoE routing logic, the Monte Carlo simulation, the LLM synthesis step, and the guardrail logic — four distinct concerns instead of one.

The chosen approach: duplicate the orchestrator body inside `src/arcade/strategy_pipeline.py::run_strategy_pipeline` and return a tuple `(StrategyRecommendation, raw_outputs_dict)`. The public orchestrator is untouched, the CLI/Streamlit keep their narrow return type, and the arcade sees everything.

## What gets duplicated

The full body of `run_strategy_orchestrator_from_state`, from the always-on layer through the MC simulation and the LLM synthesis. The duplicate lives in:

```
src/arcade/strategy_pipeline.py
    run_strategy_pipeline(race_state, laps_df, lap_state=None)
        -> tuple[StrategyRecommendation, dict]
```

The body mirrors the orchestrator's call sequence exactly:

1. `_run_always_on_agents_from_state(race_state, laps_df, lap_state)` — returns `(pace_out, tire_out, situation_out, radio_out)`.
2. `_decide_agents_to_call(tire_warning=..., sc_prob_3lap=..., radio_alerts=...)` — returns the `active` list.
3. `_run_conditional_agents(active=..., lap_state=..., tire_out=..., situation_out=..., race_state=..., laps_df=...)` — returns `(pit_out, regulation_context)`.
4. `_run_mc_simulation(pace_out, tire_out, situation_out, pit_out, race_state)` — returns the scenario score dict.
5. `_build_orchestrator_prompt(...)` and `_get_orchestrator_llm()`.
6. `_assemble_recommendation(...)` — builds the final `StrategyRecommendation`.

The arcade pipeline packages every intermediate value into the second element of its return tuple — a dict under the keys `pace_out`, `tire_out`, `situation_out`, `radio_out`, `pit_out`, `regulation_context`, `active`, `scenario_scores`.

## What does NOT get duplicated

The six sub-agent modules are imported as-is via their public `*_from_state` entry points:

- `src/agents/pace_agent.py` — `run_pace_agent_from_state`
- `src/agents/tire_agent.py` — `run_tire_agent_from_state`
- `src/agents/race_situation_agent.py` — `run_race_situation_agent_from_state`
- `src/agents/radio_agent.py` — `run_radio_agent_from_state`
- `src/agents/pit_strategy_agent.py` — `run_pit_strategy_agent_from_state`
- `src/agents/rag_agent.py` — `run_rag_agent_from_state`

Output dataclasses (`PaceOutput`, `TireOutput`, `RaceSituationOutput`, `RadioOutput`, `PitStrategyOutput`, `RegulationContext`, `StrategyRecommendation`) are also shared, imported from `src/agents/strategy_orchestrator.py`.

In short: sub-agent logic and data types are shared; only the orchestration sequence is duplicated.

## How to stay in sync

Any edit to `run_strategy_orchestrator_from_state` in `src/agents/strategy_orchestrator.py` must be mirrored in `run_strategy_pipeline` in `src/arcade/strategy_pipeline.py`. The checklist:

1. Open both files side by side.
2. Transcribe the edit. If a new private helper was added, import it. If a call argument changed, update the arcade caller.
3. If the orchestrator grew a new intermediate value that the dashboard might want to render, add it to the `raw_outputs_dict` second return value.
4. Run the smoke test below before committing.

### Smoke test

```bash
# CLI path — exercises run_strategy_orchestrator_from_state
python scripts/run_simulation_cli.py Melbourne VER McLaren --no-llm

# Arcade path — exercises run_strategy_pipeline
python -m src.arcade.main --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --strategy
```

Both should reach lap 2 without tracebacks.

## SimConnector threading

The arcade strategy driver lives in `src/arcade/strategy.py::SimConnector`. It is not a Qt object — it is a plain Python class that spawns a `threading.Thread` inside `F1ArcadeView._init_strategy_layer`.

Responsibilities:

- Own a `StrategyState` — a dataclass that caches the latest `LapDecision`, the per-agent outputs, and playback metadata. Protected by a `threading.Lock`.
- Own a background thread that iterates `RaceReplayEngine.replay()` and calls `run_strategy_pipeline(race_state, laps_df)` per lap.
- Emit `StartEventDTO` once on first frame and `LapDecisionDTO` per lap.

## Why not SSE from the FastAPI backend

The arcade used to subscribe to `GET /api/v1/strategy/simulate/stream`. Phase 3.5 Proceso B replaced that path with the direct local loop for three reasons:

- **Extra process**: running the arcade with strategy mode required starting `uvicorn` first. The local loop eliminates the dependency.
- **SSE consumer complexity**: the arcade's SSE client was a roll-your-own parser on top of `httpx.stream` with manual reconnect logic. Running the loop directly inside a thread is simpler.
- **Isolation**: the arcade can now ship as a standalone entry point without any FastAPI dependency.

The backend SSE endpoint is still live and covered by TestClient smoke tests — the arcade simply does not consume it any more.
