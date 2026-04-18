# Strategy Pipeline — Arcade Duplicate

Why `src/arcade/strategy_pipeline.py` exists as a near-copy of
`src/agents/strategy_orchestrator.py::run_strategy_orchestrator_from_state`,
what gets duplicated, what does not, and how to keep the two bodies in
sync.

Written for backend developers who edit the orchestrator and wonder why
the arcade has its own version, and for arcade developers who want to
change the pipeline without understanding why the public path is off
limits.

---

## Why the arcade duplicates

The CLI (`scripts/run_simulation_cli.py`) and the Streamlit frontend
(via `backend/services/simulation/simulator.py`) both call
`run_strategy_orchestrator_from_state(race_state, laps_df)` and consume
its single return value: a `StrategyRecommendation` dataclass with
`action`, `reasoning`, `confidence`, `scenario_scores`, and
`regulation_context`. The public contract is narrow on purpose — the
orchestrator hides the six sub-agent dataclasses behind a single
synthesised decision.

The arcade dashboard needs the opposite. To render the six sub-agent
cards, the pace and tire charts, the scenario bars, and the reasoning
tabs, the dashboard must see the raw per-agent outputs:

- `PaceOutput.lap_time_pred`, `ci_p10`, `ci_p90`, `delta_vs_prev` — to
  paint the Pace chart band and the delta chip.
- `TireOutput.laps_to_cliff_p10 / p50 / p90`, `warning_level`,
  `deg_rate` — to annotate the Tire chart cliff line and colour the
  warning chip.
- `RaceSituationOutput.overtake_prob`, `sc_prob_3lap`, `threat_level` —
  to drive the Situation card gauge.
- `RadioOutput.alerts`, `radio_events`, `rcm_events`, `corrections` —
  to populate the Radio card feed.
- `PitStrategyOutput.action`, `compound_recommendation`,
  `stop_duration_p05 / p50 / p95`, `undercut_prob` — to drive the Pit
  card and to feed the orchestrator card's "Plan: PIT lap N, fit C3,
  target UNDERCUT HAM" strip.
- `RegulationContext.answer`, `articles` — to fill the RAG card.
- The Monte Carlo scenario scores before they collapse into the
  recommendation — to shade the four scenario bars.
- The set of conditional agents that fired this lap (the `active`
  list) — to dim the Pit and RAG cards when their routing flag was not
  set.

None of this is available from `StrategyRecommendation` alone.

Two obvious alternatives, both rejected:

1. **Extend the public orchestrator to return more fields.** Would
   force the CLI and Streamlit to depend on a wider return type and
   would break the documented contract in `src/agents/README.md` and
   `docs/agents-api-reference.md`. The CLI is also the TFG's PMV and is
   flagged untouchable in
   [`feedback_cli_intocable.md`](../memory/feedback_cli_intocable.md) —
   widening its upstream is off limits.
2. **Call each sub-agent from the arcade directly and skip the
   orchestrator.** Would duplicate the MoE routing logic, the Monte
   Carlo simulation, the LLM synthesis step, and the guardrail logic —
   four distinct concerns instead of one. Worse, the arcade and the
   CLI would drift as soon as a routing rule changed.

The chosen approach: duplicate the orchestrator body inside
`src/arcade/strategy_pipeline.py::run_strategy_pipeline` and return a
tuple `(StrategyRecommendation, raw_outputs_dict)`. The public
orchestrator is untouched, the CLI/Streamlit keep their narrow return
type, and the arcade sees everything.

The pattern is not new — `backend/services/simulation/simulator.py::_run_no_llm_path`
already imports the orchestrator's private helpers (the underscore-prefixed
`_run_always_on_agents_from_state`, `_decide_agents_to_call`,
`_run_conditional_agents`, `_run_mc_simulation`,
`_build_orchestrator_prompt`, `_get_orchestrator_llm`,
`_assemble_recommendation`) and runs the pipeline with `no_llm=True` for
tests. The arcade duplicate follows the same pattern.

---

## What gets duplicated

The full body of `run_strategy_orchestrator_from_state`, from the
always-on layer through the MC simulation and the LLM synthesis. The
duplicate lives in:

```
src/arcade/strategy_pipeline.py
    run_strategy_pipeline(race_state, laps_df, lap_state=None)
        -> tuple[StrategyRecommendation, dict]
```

The body mirrors the orchestrator's call sequence exactly:

1. `_run_always_on_agents_from_state(race_state, laps_df, lap_state)`
   — returns `(pace_out, tire_out, situation_out, radio_out)`.
2. `_decide_agents_to_call(tire_warning=..., sc_prob_3lap=...,
   radio_alerts=...)` — returns the `active` list.
3. `_run_conditional_agents(active=..., lap_state=..., tire_out=...,
   situation_out=..., race_state=..., laps_df=...)` — returns
   `(pit_out, regulation_context)`.
4. `_run_mc_simulation(pace_out, tire_out, situation_out, pit_out,
   race_state)` — returns the scenario score dict.
5. `_build_orchestrator_prompt(...)` and `_get_orchestrator_llm()` —
   build the structured-output prompt and the `ChatOpenAI` wrapper.
6. `_assemble_recommendation(...)` — builds the final
   `StrategyRecommendation`.

The arcade pipeline packages every intermediate value into the second
element of its return tuple — a dict under the keys `pace_out`,
`tire_out`, `situation_out`, `radio_out`, `pit_out`,
`regulation_context`, `active`, `scenario_scores`. The shape matches
the intermediate state of `run_strategy_orchestrator_from_state`
exactly, which is deliberate: any formatter written against the
orchestrator internals (for example in `scripts/run_simulation_cli.py`
or the backend debug routes) can be reused in the dashboard without
translation.

The file header in `strategy_pipeline.py` spells the duplication
agreement explicitly:

```
"Body is a copy of src.agents.strategy_orchestrator.run_strategy_orchestrator_from_state
kept intentionally separate: the CLI and Streamlit paths import the
orchestrator directly and must stay unaffected by anything the arcade
does. [...]

If you change the orchestrator body upstream, mirror the change here."
```

---

## What does NOT get duplicated

The six sub-agent modules are imported as-is via their public
`*_from_state` entry points:

- `src/agents/pace_agent.py` — `run_pace_agent_from_state`
- `src/agents/tire_agent.py` — `run_tire_agent_from_state`
- `src/agents/race_situation_agent.py` —
  `run_race_situation_agent_from_state`
- `src/agents/radio_agent.py` — `run_radio_agent_from_state`
- `src/agents/pit_strategy_agent.py` —
  `run_pit_strategy_agent_from_state`
- `src/agents/rag_agent.py` — `run_rag_agent_from_state`

These are consumed by the orchestrator's private helper
`_run_always_on_agents_from_state` (and by `_run_conditional_agents`
for the pit/RAG pair). The arcade calls the same private helpers, so
the sub-agent modules are reused without a byte of duplication. The
only copy is the orchestration glue.

Output dataclasses (`PaceOutput`, `TireOutput`, `RaceSituationOutput`,
`RadioOutput`, `PitStrategyOutput`, `RegulationContext`,
`StrategyRecommendation`) are also shared, imported from
`src/agents/strategy_orchestrator.py`. The dashboard's formatters in
`src/arcade/dashboard/agent_formatters.py` consume these dataclasses
directly.

In short: sub-agent logic and data types are shared; only the
orchestration sequence is duplicated.

---

## How to stay in sync

Any edit to `run_strategy_orchestrator_from_state` in
`src/agents/strategy_orchestrator.py` must be mirrored in
`run_strategy_pipeline` in `src/arcade/strategy_pipeline.py`. The
checklist:

1. Open both files side by side.
2. Transcribe the edit. If a new private helper was added, import it
   in the arcade file. If a call argument changed, update the arcade
   caller.
3. If the orchestrator grew a new intermediate value that the dashboard
   might want to render, add it to the `raw_outputs_dict` second
   return value. If not, omit it (the dict is not a public contract;
   only the dashboard formatters read it).
4. Run the smoke test below before committing.

### Smoke test

```bash
# CLI path — exercises run_strategy_orchestrator_from_state
python scripts/run_simulation_cli.py Melbourne VER McLaren --no-llm

# Arcade path — exercises run_strategy_pipeline
python -m src.arcade.main --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --strategy
```

Both should reach lap 2 without tracebacks. The CLI prints the Rich
panel with six agent sections; the arcade shows the dashboard with the
same six cards populated. If the orchestrator path succeeds and the
arcade path errors (or vice versa), the duplicate has drifted.

A CI regression suite for the duplicate is on the Phase 4 backlog; the
smoke test is the interim guardrail.

---

## SimConnector threading

The arcade strategy driver lives in
`src/arcade/strategy.py::SimConnector`. It is not a Qt object — it is a
plain Python class that spawns a `threading.Thread` inside
`F1ArcadeView._init_strategy_layer`.

Responsibilities:

- Own a `StrategyState` — a dataclass that caches the latest
  `LapDecision`, the per-agent outputs, and playback metadata. Protected
  by a `threading.Lock` so the pyglet main thread can safely read it to
  build broadcast snapshots while the worker thread writes it.
- Own a background thread that iterates
  `RaceReplayEngine.replay()` and calls
  `run_strategy_pipeline(race_state, laps_df)` per lap. Writes the
  result into `StrategyState` under the lock.
- Emit `StartEventDTO` once on first frame and `LapDecisionDTO` per
  lap. The DTOs are frozen dataclasses that serialise cleanly to JSON
  for the broadcast.

The previous incarnation of `SimConnector` consumed the FastAPI SSE
endpoint. That version was replaced in Phase 3.5 Proceso B — the public
signature (the `F1ArcadeView` wires the same constructor calls) is
unchanged so the view code was not touched. Inside, the SSE consumer is
gone; in its place is a direct `RaceReplayEngine` iterator driven by a
background thread.

---

## Why not SSE from the FastAPI backend

The arcade used to subscribe to
`GET /api/v1/strategy/simulate/stream` (the SSE endpoint documented in
[`project_sim_sse_endpoint_done.md`](../memory/project_sim_sse_endpoint_done.md))
and consume `event: lap_decision` frames. Phase 3.5 Proceso B
replaced that path with the direct local loop for three reasons:

- **Extra process**: running the arcade with strategy mode required
  starting `uvicorn` first, so a single-command launch was not
  possible. The user had to remember which terminal owned the backend
  and which owned the arcade. The local loop eliminates the dependency.
- **SSE consumer complexity**: the arcade's SSE client was a
  roll-your-own parser on top of `httpx.stream` with manual reconnect
  logic. Running the loop directly inside a thread is simpler, tested
  by the same `RaceReplayEngine` the CLI uses, and has no parsing
  layer to maintain.
- **Isolation**: the arcade can now ship as a standalone entry point
  without any FastAPI dependency. The backend remains the canonical
  path for the Streamlit frontend; the two are fully decoupled.

The backend SSE endpoint is still live and covered by TestClient
smoke tests — the arcade simply does not consume it any more.

---

## Related reading

- [`src/agents/README.md`](../src/agents/README.md) — public agent
  entry points and output dataclasses.
- [`docs/architecture.md`](architecture.md) — N25--N31 multi-agent
  pipeline reference, including the MoE routing rules and MC
  simulation equation.
- [`docs/arcade-dashboard.md`](arcade-dashboard.md) — Qt-side
  architecture deep dive.
- [`docs/arcade-quick-start.md`](arcade-quick-start.md) — end-user
  launch guide.
- [`docs/diagrams/`](diagrams/) — drawio sources; the forthcoming
  `arcade_pipeline_duplication.drawio` visualises the shared sub-agent
  imports alongside the duplicated orchestration glue.
