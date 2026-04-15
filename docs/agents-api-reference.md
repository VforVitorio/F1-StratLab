# Agents API Reference

## Module Location

All agents live in `src/agents/`. Each file is extracted from its corresponding notebook (N25--N31).

## Entry Points

Every agent has two entry points:

| Agent | FastF1 Entry | RSM Adapter (no FastF1 session) |
|---|---|---|
| N25 Pace | `run_pace_agent(**kwargs)` | `run_pace_agent_from_state(lap_state, laps_df)` |
| N26 Tire | `run_tire_agent(stint_state)` | `run_tire_agent_from_state(lap_state, laps_df)` |
| N27 Situation | `run_race_situation_agent(lap_state)` | `run_race_situation_agent_from_state(lap_state, laps_df)` |
| N28 Pit | `run_pit_strategy_agent(lap_state)` | `run_pit_strategy_agent_from_state(lap_state, laps_df)` |
| N29 Radio | `run_radio_agent(lap_state)` | `run_radio_agent_from_state(lap_state, laps_df)` |
| N30 RAG | `run_rag_agent(question)` | `run_rag_agent_from_state(lap_state)` |
| N31 Orchestrator | `run_strategy_orchestrator(race_state, lap_state)` | `run_strategy_orchestrator_from_state(race_state, laps_df)` |

Each agent also exposes a `get_*_react_agent()` factory that returns a compiled LangGraph `CompiledGraph` for direct LangGraph usage.

## Output Dataclasses

### PaceOutput (N25)

| Field | Type | Description |
|---|---|---|
| `lap_time_pred` | float | Predicted lap time in seconds |
| `delta_vs_prev` | float | Delta vs previous lap (negative = faster) |
| `delta_vs_median` | float | Delta vs session median |
| `ci_p10` | float | 10th percentile bootstrap CI |
| `ci_p90` | float | 90th percentile bootstrap CI |
| `reasoning` | str | LLM-generated reasoning text |

### TireOutput (N26)

| Field | Type | Description |
|---|---|---|
| `compound` | str | Current compound name (SOFT, MEDIUM, HARD) |
| `current_tyre_life` | int | Current tire age in laps |
| `deg_rate` | float | Degradation rate (seconds lost per lap) |
| `laps_to_cliff_p10` | float | 10th percentile laps until cliff |
| `laps_to_cliff_p50` | float | 50th percentile laps until cliff |
| `laps_to_cliff_p90` | float | 90th percentile laps until cliff |
| `warning_level` | str | OK, MONITOR, PIT_SOON, or CRITICAL |
| `reasoning` | str | LLM-generated reasoning text |

### RaceSituationOutput (N27)

| Field | Type | Description |
|---|---|---|
| `overtake_prob` | float | Probability of being overtaken (0--1) |
| `sc_prob_3lap` | float | Safety car probability within 3 laps (0--1) |
| `threat_level` | str | LOW, MEDIUM, HIGH, CRITICAL |
| `gap_ahead_s` | float | Gap to car ahead in seconds |
| `pace_delta_s` | float | Pace difference vs car ahead |
| `reasoning` | str | LLM-generated reasoning text |

### PitStrategyOutput (N28)

| Field | Type | Description |
|---|---|---|
| `action` | str | STAY_OUT, PIT_NOW, UNDERCUT, OVERCUT |
| `recommended_lap` | int or None | Suggested pit lap |
| `compound_recommendation` | str | Suggested next compound |
| `stop_duration_p05` | float | 5th percentile stop duration (seconds) |
| `stop_duration_p50` | float | Median stop duration (seconds) |
| `stop_duration_p95` | float | 95th percentile stop duration (seconds) |
| `undercut_prob` | float or None | Undercut success probability (0--1) |
| `undercut_target` | str or None | Target driver for undercut |
| `sc_reactive` | bool | Whether recommendation is SC-reactive |
| `reasoning` | str | LLM-generated reasoning text |

### RadioOutput (N29)

| Field | Type | Description |
|---|---|---|
| `radio_events` | list | Processed radio messages with sentiment, intent, NER |
| `rcm_events` | list | Processed Race Control Messages |
| `alerts` | list | Deterministic alert flags from NLP pipeline |
| `reasoning` | str | LLM-generated reasoning text |
| `corrections` | list | Driver-reported corrections (e.g., damage, handling issues) |

### RegulationContext (N30)

| Field | Type | Description |
|---|---|---|
| `answer` | str | Synthesized answer from regulation passages |
| `articles` | list[str] | Referenced FIA article numbers |
| `chunks` | list | Raw retrieved text chunks |
| `reasoning` | str | Alias for `answer` |

### StrategyRecommendation (N31)

| Field | Type | Description |
|---|---|---|
| `action` | str | STAY_OUT, PIT_NOW, UNDERCUT, OVERCUT, ALERT |
| `pace_mode` | str | PUSH, NEUTRAL, MANAGE, LIFT_AND_COAST |
| `risk_posture` | str | AGGRESSIVE, BALANCED, DEFENSIVE |
| `reasoning` | str | Multi-sentence LLM synthesis |
| `confidence` | float | 0--1 confidence score |
| `scenario_scores` | dict | MC scores per strategy candidate |
| `contingencies` | list[Contingency] | Conditional plan branches |
| `regulation_context` | str | RAG answer if N30 was activated |

### Contingency

| Field | Type | Description |
|---|---|---|
| `trigger` | str | Event description that activates this branch |
| `switch_to` | str | Replacement action (same enum as primary action) |
| `priority` | str | HIGH, MEDIUM, LOW |

## RaceState Input (N31)

The orchestrator accepts a `RaceState` Pydantic model:

```python
class RaceState(BaseModel):
    driver: str           # Three-letter driver code
    lap: int              # Current lap number
    total_laps: int       # Total race laps
    position: int         # Current race position
    compound: str         # Current tire compound
    tyre_life: int        # Current tire age (laps)
    gap_ahead_s: float    # Gap to car ahead (seconds)
    pace_delta_s: float   # Pace delta vs car ahead
    air_temp: float       # Air temperature (C)
    track_temp: float     # Track temperature (C)
    rainfall: bool = False
    radio_msgs: list = []   # RadioMessage dicts for current lap window
    rcm_events: list = []   # RCMEvent dicts for current lap window
    risk_tolerance: float = 0.5  # 0=conservative, 1=aggressive
```

## Model Artifacts

| Agent | Model Directory | Files |
|---|---|---|
| N25 | `data/models/lap_time/` | XGBoost model |
| N26 | `data/models/tire_degradation/` | TireDegTCN `.pt` files + calibration JSON |
| N27 | `data/models/overtake_probability/` | LightGBM + calibrator + config |
| N27 | `data/models/safety_car_probability/` | LightGBM + calibrator + feature list |
| N28 | `data/models/pit_prediction/` | HistGBT P05/P50/P95 + undercut LightGBM |
| N29 | `data/models/nlp/` | pipeline_config_v1.json + .pt state dicts |
| N30 | `data/rag/` | Qdrant index (built by `scripts/build_rag_index.py`) |

## Testing Examples

**Tool-level (no LLM needed):**

```python
from src.agents.radio_agent import process_radio_tool
result = process_radio_tool.invoke({
    "driver": "NOR", "lap": 18, "text": "Box this lap."
})
```

**Agent-level (no LLM needed):**

```python
from src.agents.pace_agent import run_pace_agent_from_state
import pandas as pd

laps_df = pd.read_parquet("data/processed/laps_featured_2025.parquet")
lap_state = {"driver": "VER", "lap_number": 20, ...}
output = run_pace_agent_from_state(lap_state, laps_df)
```

**Full orchestrator (requires LM Studio or OpenAI):**

```python
from src.agents.strategy_orchestrator import RaceState, run_strategy_orchestrator_from_state
import pandas as pd

laps_df = pd.read_parquet("data/processed/laps_featured_2025.parquet")
race_state = RaceState(
    driver="NOR", lap=18, total_laps=57, position=3,
    compound="C2", tyre_life=20, gap_ahead_s=1.2, pace_delta_s=-0.3,
    air_temp=32.0, track_temp=48.0,
)
rec = run_strategy_orchestrator_from_state(race_state, laps_df)
print(rec.action, rec.confidence, rec.reasoning)
```
