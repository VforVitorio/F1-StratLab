"""src/agents/strategy_orchestrator.py

Strategy Orchestrator — extraction from N31_strategy_orchestrator.ipynb.

End-to-end multi-agent supervisor that integrates N25–N30 sub-agents through
three processing layers:

  Layer 1 — MoE routing: deterministic if-else rules decide which conditional
             agents (N28, N30) to activate based on N26/N27/N29 outputs.
  Layer 2 — Monte Carlo simulation: draws CFG.n_sim samples from sub-agent
             probability distributions and evaluates four strategy candidates.
  Layer 3 — LLM synthesis: structured-output LLM aggregates all reasoning strings
             and MC scores into a StrategyRecommendation.

Entry points
------------
run_strategy_orchestrator(race_state, lap_state)
    Primary entry point. Accepts a RaceState Pydantic model and a lap_state dict
    (compatible with the FastF1 entry points of the sub-agents). The sub-agents
    are called with their standard entry points — requires populated FastF1 session
    globals inside each sub-agent module.

run_strategy_orchestrator_from_state(race_state, laps_df)
    RSM adapter. Calls the *_from_state entry points of each sub-agent so no
    FastF1 session is required. laps_df is the full lap DataFrame from
    RaceStateManager. lap_state is built internally from race_state + laps_df.

References
----------
Heilmeier et al. (2020) ApplSci 10/4229 — MC motorsport simulation
Wang et al. (2024) arXiv:2406.04692 — MoA reasoning aggregation
Liu et al. (2024) arXiv:2402.02392 — DeLLMa decision under uncertainty with LLM
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

# ── Repo root ──────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / ".git").exists():
    _REPO_ROOT = _REPO_ROOT.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Optional LangChain imports ─────────────────────────────────────────────────
try:
    from langchain_openai import ChatOpenAI
    _LC_OK = True
except ImportError:
    _LC_OK = False

# ── Sub-agent imports ──────────────────────────────────────────────────────────
from src.agents.pace_agent         import run_pace_agent, run_pace_agent_from_state
from src.agents.tire_agent         import run_tire_agent, run_tire_agent_from_state
from src.agents.race_situation_agent import (
    run_race_situation_agent,
    run_race_situation_agent_from_state,
)
from src.agents.pit_strategy_agent import (
    run_pit_strategy_agent,
    run_pit_strategy_agent_from_state,
)
from src.agents.radio_agent        import (
    run_radio_agent,
    run_radio_agent_from_state,
    RadioMessage,
    RCMEvent,
)
from src.agents.rag_agent          import run_rag_agent


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class OrchestratorCFG:
    """Runtime configuration for the Strategy Orchestrator (N31).

    n_sim controls Monte Carlo draws per strategy candidate in Layer 2. 500 draws
    keep variance of the mean below 0.01 position units within lap-level latency.

    sc_prob_threshold is the N27.sc_prob_3lap cutoff above which N30 is activated
    to retrieve safety-car regulation context for the pit decision.

    risk_tolerance_default (α) weights expected value vs worst-case in the MC
    score: score(S) = α·E[S] + (1−α)·P10[S]. α=1.0 aggressive, α=0.0 conservative.

    temperature=0.0 ensures deterministic structured output from Layer 3 LLM.
    """

    model_name:             str   = "gpt-5.4-mini"
    base_url:               str   = "http://localhost:1234/v1"
    temperature:            float = 0.0
    n_sim:                  int   = 500
    sc_prob_threshold:      float = 0.30
    risk_tolerance_default: float = 0.5


CFG = OrchestratorCFG()

# Lazy LLM singleton — created on first call to avoid connection at import time
_orchestrator_llm = None


def _get_orchestrator_llm():
    """Return the cached structured-output LLM, creating it on first call.

    Returns a Runnable that produces StrategyRecommendation Pydantic objects.
    Raises ImportError when langchain_openai is not installed.
    """
    global _orchestrator_llm
    if _orchestrator_llm is None:
        if not _LC_OK:
            raise ImportError(
                "langchain_openai is not installed. "
                "Install with: pip install langchain-openai"
            )
        llm = ChatOpenAI(
            model=CFG.model_name,
            base_url=CFG.base_url,
            api_key="lm-studio",
            temperature=CFG.temperature,
            model_kwargs={"parallel_tool_calls": False},
        )
        _orchestrator_llm = llm.with_structured_output(StrategyRecommendation)
    return _orchestrator_llm


# ==============================================================================
# Input / output dataclasses
# ==============================================================================

class RaceState(BaseModel):
    """Per-lap context slice passed to the Strategy Orchestrator.

    driver identifies the driver whose strategy is being evaluated — all gap
    and pace features are relative to this driver.

    lap and total_laps enable race-percentage features used by N28 (lap_race_pct)
    and the MC simulation for fuel load estimation.

    compound and tyre_life are the current stint values forwarded to N26.

    gap_ahead_s and pace_delta_s are the primary inputs for N27 overtake scoring.

    weather fields (air_temp, track_temp, rainfall) are forwarded to N14 (SC model)
    as contextual features.

    radio_msgs and rcm_events are pre-filtered to the current lap ±1 window by the
    caller before passing to N29 — the orchestrator does not filter them itself.
    Items may be RadioMessage/RCMEvent instances or dicts with matching fields;
    the orchestrator converts dicts automatically before passing to N29.

    risk_tolerance (α) is the MC score weight: score = α·E[S] + (1−α)·P10[S].
    Validated in [0, 1] by Pydantic; default 0.5 is neutral risk stance.
    """

    driver:         str
    lap:            int
    total_laps:     int
    position:       int
    compound:       str
    tyre_life:      int
    gap_ahead_s:    float
    pace_delta_s:   float
    air_temp:       float
    track_temp:     float
    rainfall:       bool  = False
    radio_msgs:     list  = Field(default_factory=list)
    rcm_events:     list  = Field(default_factory=list)
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)

    model_config = {"arbitrary_types_allowed": True}


class StrategyRecommendation(BaseModel):
    """Final structured output of the Strategy Orchestrator (N31).

    action is one of five values: STAY_OUT defers the pit stop, PIT_NOW calls
    an immediate box, UNDERCUT pits before the target rival to gain track position,
    OVERCUT stays out to exploit fresh-tyre pace later, and ALERT flags a critical
    event (radio PROBLEM, SC deployed) that overrides standard strategy logic.

    reasoning is the LLM's narrative synthesis of all sub-agent inputs, MC scores,
    and regulation constraints — forwarded verbatim to the UI and post-race analysis.

    confidence is the LLM's self-assessed certainty in [0, 1]. Treat it as a
    qualitative signal rather than a calibrated probability estimate.

    scenario_scores carries the full MC output dict so downstream consumers can
    inspect the distribution without re-running the simulation.

    regulation_context is the N30 answer string when activated, empty string
    otherwise. Included in the recommendation so the UI can surface the regulatory
    basis for the action without re-querying N30.
    """

    action:             str   = Field(
        description="STAY_OUT | PIT_NOW | UNDERCUT | OVERCUT | ALERT"
    )
    reasoning:          str   = Field(
        description="Narrative synthesis of all agent inputs and MC scores"
    )
    confidence:         float = Field(
        ge=0.0, le=1.0,
        description="LLM self-assessed certainty",
    )
    scenario_scores:    dict  = Field(
        default_factory=dict,
        description="MC scores per strategy",
    )
    regulation_context: str   = Field(
        default="",
        description="N30 answer if activated, else empty",
    )


# ==============================================================================
# Layer 1 — MoE routing
# ==============================================================================

def _decide_agents_to_call(
    tire_warning:  str,
    sc_prob_3lap:  float,
    radio_alerts:  list,
) -> set:
    """Layer 1 MoE routing — returns set of conditional agent keys to activate.

    N25, N26, N27, N29 are always called by run_strategy_orchestrator and are
    not returned here. This function only decides N28 and N30.

    tire_warning is TireOutput.warning_level ("OK" | "MONITOR" | "PIT_SOON").
    sc_prob_3lap is RaceSituationOutput.sc_prob_3lap from N27.
    radio_alerts is RadioOutput.alerts — each dict has keys 'source' and 'intent'
    or 'event_type'.

    N28 is activated if the tyre is near the cliff or if radio signals a problem.
    N30 is activated whenever N28 is active (regulation check on the pit decision)
    or if SC probability is high (fetch SC procedure articles).
    """
    activate: set = set()

    if tire_warning == "PIT_SOON":
        activate.add("N28")

    alert_intents = {a.get("intent", "") for a in radio_alerts}
    if alert_intents & {"PROBLEM", "WARNING"}:
        activate.add("N28")

    if sc_prob_3lap > CFG.sc_prob_threshold:
        activate.add("N30")

    if "N28" in activate:
        activate.add("N30")

    return activate


# ==============================================================================
# Layer 2 — Monte Carlo simulation
# ==============================================================================

# Simulation constants (Heilmeier et al. 2020 § 3.2 — race-sim parameters)
WINDOW_LAPS  = 5     # lap horizon for each strategy evaluation
FRESH_GAIN   = 0.25  # s/lap advantage of fresh vs degraded tyre
CLIFF_LOSS   = 0.80  # s/lap lost when tyre passes the cliff
POS_GAP_S    = 1.50  # seconds per position gap (midfield approximation)
SC_PIT_BONUS = 8.0   # seconds saved by pitting under SC (no delta-lap loss)


def simulate_lap_window(
    strategy: str,
    cliff_i:  float,
    sc_i:     bool,
    pit_i:    float,
    ucut_i:   bool,
    window:   int = WINDOW_LAPS,
) -> float:
    """Estimate position gain vs STAY_OUT baseline over a W-lap window.

    Returns a position-equivalent score (positive = positions gained).
    STAY_OUT is the reference — all other strategies are scored relative to it.

    strategy:
        One of STAY_OUT / PIT_NOW / UNDERCUT / OVERCUT.
    cliff_i:
        Laps remaining before tyre cliff (from Triangular N26 draw). Laps
        beyond the cliff contribute CLIFF_LOSS s/lap of time loss, converted
        to position units using POS_GAP_S.
    sc_i:
        Whether a Safety Car event occurs in the window (Bernoulli N27 draw).
        Pitting under SC avoids the delta-lap penalty (SC_PIT_BONUS saved).
        OVERCUT under SC scores like PIT_NOW (free opportunity to pit).
    pit_i:
        Pit stop duration sample in seconds (Triangular N28 / prior draw).
    ucut_i:
        Whether the undercut succeeds (Bernoulli N16 draw). Gates the extra
        +POS_GAP_S bonus of UNDERCUT vs PIT_NOW.
    window:
        Lap horizon for the evaluation. Default is WINDOW_LAPS=5.
    """
    if strategy == "STAY_OUT":
        cliff_laps = max(0.0, window - cliff_i)
        time_delta = -cliff_laps * CLIFF_LOSS

    elif strategy == "PIT_NOW":
        sc_saving  = SC_PIT_BONUS if sc_i else 0.0
        time_delta = -pit_i + sc_saving + FRESH_GAIN * window

    elif strategy == "UNDERCUT":
        sc_saving  = SC_PIT_BONUS if sc_i else 0.0
        ucut_bonus = POS_GAP_S if ucut_i else 0.0
        time_delta = -pit_i + sc_saving + FRESH_GAIN * window + ucut_bonus

    elif strategy == "OVERCUT":
        if sc_i:
            time_delta = SC_PIT_BONUS + FRESH_GAIN * window
        else:
            cliff_laps = max(0.0, (window // 2) - cliff_i)
            time_delta = FRESH_GAIN * (window // 2) - cliff_laps * CLIFF_LOSS

    else:
        time_delta = 0.0

    return time_delta / POS_GAP_S


def _run_mc_simulation(
    pace_out,
    tire_out,
    situation_out,
    pit_out=None,
    alpha: float = 0.5,
) -> dict:
    """Layer 2 Monte Carlo simulation over strategy candidates.

    Draws CFG.n_sim samples from the probability distributions exposed by the
    sub-agent outputs and evaluates each strategy over WINDOW_LAPS laps.

    pace_out:
        PaceOutput from N25 — used to derive pace sigma from the bootstrap CI.
        σ = (ci_p90 − ci_p10) / (2 × 1.645). pace_i is sampled but not yet
        used inside simulate_lap_window — available for future extensions.
    tire_out:
        TireOutput from N26 — provides P10/P50/P90 of laps-to-cliff for the
        Triangular distribution.
    situation_out:
        RaceSituationOutput from N27 — sc_prob_3lap drives the Bernoulli SC draw.
    pit_out:
        PitStrategyOutput from N28, or None. When None, pit duration falls back
        to a conservative Triangular(2.2, 2.8, 3.8) prior and undercut_prob=0.5.
    alpha:
        RaceState.risk_tolerance. score = alpha·E[S] + (1−alpha)·P10[S].
        α=1.0 is pure expected value (aggressive); α=0.0 is worst-case only.
    """
    rng = np.random.default_rng(seed=42)
    n   = CFG.n_sim

    sigma_pace = (pace_out.ci_p90 - pace_out.ci_p10) / (2 * 1.645)

    p10_cliff = tire_out.laps_to_cliff_p10
    p50_cliff = tire_out.laps_to_cliff_p50
    p90_cliff = tire_out.laps_to_cliff_p90

    sc_prob = situation_out.sc_prob_3lap

    if pit_out is not None:
        pit_p05   = pit_out.stop_duration_p05
        pit_p50   = pit_out.stop_duration_p50
        pit_p95   = pit_out.stop_duration_p95
        ucut_prob = (
            pit_out.undercut_prob
            if pit_out.undercut_prob is not None
            else 0.5
        )
    else:
        pit_p05, pit_p50, pit_p95 = 2.2, 2.8, 3.8
        ucut_prob = 0.5

    pace_s  = rng.normal(pace_out.lap_time_pred, sigma_pace, n)  # noqa: F841
    cliff_s = rng.triangular(p10_cliff, p50_cliff, p90_cliff, n)
    sc_s    = rng.random(n) < sc_prob
    pit_s   = rng.triangular(pit_p05, pit_p50, pit_p95, n)
    ucut_s  = rng.random(n) < ucut_prob

    strategies = ["STAY_OUT", "PIT_NOW", "UNDERCUT", "OVERCUT"]
    results    = {}

    for s in strategies:
        outcomes = np.array([
            simulate_lap_window(s, cliff_s[i], sc_s[i], pit_s[i], ucut_s[i])
            for i in range(n)
        ])
        e_val   = float(np.mean(outcomes))
        p10_val = float(np.percentile(outcomes, 10))
        p90_val = float(np.percentile(outcomes, 90))
        score   = alpha * e_val + (1 - alpha) * p10_val
        results[s] = {
            "E":     round(e_val, 3),
            "P10":   round(p10_val, 3),
            "P90":   round(p90_val, 3),
            "score": round(score, 3),
        }

    return results


# ==============================================================================
# Layer 3 — LLM synthesis
# ==============================================================================

def _build_rag_question(
    sc_active:  bool,
    pit_action: str | None,
    compound:   str,
) -> str:
    """Generate a targeted FIA regulation query based on active race conditions.

    sc_active triggers a safety car procedure query. pit_action drives a
    compound-change or undercut-specific query. Falls back to a generic
    pit stop regulation question when neither condition is specific.
    """
    if sc_active:
        return (
            "What are the FIA regulations for pit stops and tyre changes "
            "during a Safety Car period?"
        )
    if pit_action == "UNDERCUT":
        return (
            f"Are there any restrictions on changing to {compound} compound "
            "tyres mid-race?"
        )
    return "What are the mandatory tyre compound regulations for a dry race?"


def _build_orchestrator_prompt(
    race_state:          "RaceState",
    mc_results:          dict,
    best_mc:             str,
    pace_reasoning:      str = "",
    tire_reasoning:      str = "",
    situation_reasoning: str = "",
    pit_reasoning:       str = "",
    radio_reasoning:     str = "",
    regulation_context:  str = "",
) -> str:
    """Build the LLM synthesis prompt for Layer 3.

    Assembles sub-agent reasoning strings, MC scenario scores, and regulation
    context into a single prompt. N30 regulation context is injected as a hard
    constraint block — the LLM is told explicitly which actions are regulation-
    compliant before it decides, so illegal options cannot appear in the output.

    best_mc is the MC argmax passed as a hint. The LLM may override it if
    regulation context or radio alerts justify a different action.
    """
    mc_table = "\n".join(
        f"  {s}: E={v['E']:+.3f}  P10={v['P10']:+.3f}  P90={v['P90']:+.3f}  score={v['score']:+.3f}"
        for s, v in mc_results.items()
    )

    reg_block = (
        f"REGULATION CONSTRAINT (hard — exclude non-compliant actions):\n"
        f"{regulation_context}"
        if regulation_context
        else "REGULATION CONSTRAINT: none flagged — all four actions are compliant."
    )

    return (
        f"You are the F1 Strategy Orchestrator. Synthesise the sub-agent outputs below\n"
        f"into a single StrategyRecommendation. Choose the action that maximises risk-adjusted\n"
        f"position gain while respecting the regulation constraint.\n\n"
        f"RACE CONTEXT:\n"
        f"  Driver: {race_state.driver} | Lap: {race_state.lap}/{race_state.total_laps}\n"
        f"  Position: P{race_state.position} | Compound: {race_state.compound} "
        f"TyreLife {race_state.tyre_life}\n"
        f"  Gap ahead: {race_state.gap_ahead_s:.2f}s | "
        f"Pace delta: {race_state.pace_delta_s:+.3f}s\n"
        f"  Risk tolerance α: {race_state.risk_tolerance}\n\n"
        f"SUB-AGENT REASONING:\n"
        f"  [N25 Pace]      {pace_reasoning or 'not activated'}\n"
        f"  [N26 Tire]      {tire_reasoning or 'not activated'}\n"
        f"  [N27 Situation] {situation_reasoning or 'not activated'}\n"
        f"  [N28 Pit]       {pit_reasoning or 'not activated'}\n"
        f"  [N29 Radio]     {radio_reasoning or 'not activated'}\n\n"
        f"MONTE CARLO SCENARIO SCORES "
        f"(N_SIM={CFG.n_sim}, α={race_state.risk_tolerance}, window={WINDOW_LAPS} laps):\n"
        f"{mc_table}\n"
        f"  → Best MC candidate: {best_mc}\n\n"
        f"{reg_block}\n\n"
        f"Return a StrategyRecommendation with:\n"
        f"- action: one of STAY_OUT / PIT_NOW / UNDERCUT / OVERCUT / ALERT\n"
        f"- reasoning: concise narrative (2-4 sentences) citing the key inputs\n"
        f"- confidence: your certainty in [0, 1]\n"
    )


# ==============================================================================
# Helpers — input coercion
# ==============================================================================

def _to_radio_message(item) -> RadioMessage:
    """Convert a dict or RadioMessage instance to a RadioMessage.

    Accepts both RadioMessage dataclass instances (passed through unchanged)
    and dicts with keys driver, lap, text. Used so callers can pass either
    type in RaceState.radio_msgs without explicit conversion.
    """
    if isinstance(item, RadioMessage):
        return item
    return RadioMessage(
        driver=item.get("driver", "UNK"),
        lap=item.get("lap", 0),
        text=item.get("text", ""),
        timestamp=item.get("timestamp"),
    )


def _to_rcm_event(item) -> RCMEvent:
    """Convert a dict or RCMEvent instance to a RCMEvent.

    Accepts both RCMEvent dataclass instances (passed through unchanged) and
    dicts with keys message, flag, category, lap. Used so callers can pass
    FastF1 RCM row dicts directly into RaceState.rcm_events.
    """
    if isinstance(item, RCMEvent):
        return item
    return RCMEvent(
        message=str(item.get("message", "")),
        flag=str(item.get("flag", "") or ""),
        category=str(item.get("category", "")),
        lap=int(item.get("lap", 0) or 0),
        racing_number=item.get("racing_number") or item.get("RacingNumber"),
        scope=str(item.get("scope", "") or ""),
    )


# ==============================================================================
# Entry point helpers
# ==============================================================================

def _run_always_on_agents(race_state: "RaceState", lap_state: dict) -> tuple:
    """Run N25, N26, N27, N29 — always activated regardless of race state.

    race_state:
        Current RaceState with all lap and session fields.
    lap_state:
        Dict of scalar lap features consumed by the sub-agent entry points.
        Must contain: driver_number, stint, team, year, gp_name and optionally
        laps_since_pit, fuel_load, prev_lap_time, prev_speed_st, humidity.

    Returns (pace_out, tire_out, situation_out, radio_out) — typed dataclass
    outputs from N25, N26, N27, N29 respectively.
    """
    pace_out = run_pace_agent(
        driver_number  = lap_state["driver_number"],
        lap_number     = race_state.lap,
        stint          = lap_state["stint"],
        tyre_life      = race_state.tyre_life,
        compound       = race_state.compound,
        position       = race_state.position,
        team           = lap_state["team"],
        laps_since_pit = lap_state.get("laps_since_pit", race_state.tyre_life),
        fuel_load      = lap_state.get(
            "fuel_load", 1 - race_state.lap / race_state.total_laps
        ),
        year           = lap_state["year"],
        prev_lap_time  = lap_state.get("prev_lap_time", 92.0),
        prev_tyre_life = race_state.tyre_life - 1,
        prev_speed_st  = lap_state.get("prev_speed_st", 300.0),
        air_temp       = race_state.air_temp,
        track_temp     = race_state.track_temp,
        humidity       = lap_state.get("humidity", 50.0),
        rainfall       = race_state.rainfall,
        total_laps     = race_state.total_laps,
        gp_name        = lap_state["gp_name"],
    )

    tire_out      = run_tire_agent(lap_state)
    situation_out = run_race_situation_agent(lap_state)

    radio_msgs = [_to_radio_message(m) for m in race_state.radio_msgs]
    rcm_events = [_to_rcm_event(e) for e in race_state.rcm_events]
    radio_out  = run_radio_agent({
        **lap_state,
        "lap":        race_state.lap,
        "radio_msgs": radio_msgs,
        "rcm_events": rcm_events,
    })

    return pace_out, tire_out, situation_out, radio_out


def _run_always_on_agents_from_state(
    race_state: "RaceState",
    laps_df:    pd.DataFrame,
    lap_state:  dict,
) -> tuple:
    """RSM adapter version of _run_always_on_agents.

    Calls the *_from_state entry points of each sub-agent so no FastF1 session
    is required. laps_df is passed to each adapter to populate sub-agent globals.

    Returns (pace_out, tire_out, situation_out, radio_out).
    """
    pace_out      = run_pace_agent_from_state(lap_state)
    tire_out      = run_tire_agent_from_state(lap_state, laps_df)
    situation_out = run_race_situation_agent_from_state(lap_state, laps_df)

    radio_msgs = [_to_radio_message(m) for m in race_state.radio_msgs]
    rcm_events = [_to_rcm_event(e) for e in race_state.rcm_events]
    radio_out  = run_radio_agent_from_state(
        {**lap_state, "lap": race_state.lap,
         "radio_msgs": radio_msgs, "rcm_events": rcm_events},
        laps_df,
    )

    return pace_out, tire_out, situation_out, radio_out


def _run_conditional_agents(
    active:       set,
    lap_state:    dict,
    tire_out,
    situation_out,
    race_state:   "RaceState",
    laps_df:      pd.DataFrame | None = None,
) -> tuple:
    """Run N28 and N30 when the routing layer activates them.

    active:
        Set of agent names from _decide_agents_to_call ('N28', 'N30').
    lap_state:
        Scalar lap feature dict, extended with laps_to_cliff and sc_prob
        before being forwarded to N28.
    tire_out:
        TireOutput from N26, provides cliff timing for N28.
    situation_out:
        RaceSituationOutput from N27, provides sc_prob for N28 and the N30
        routing decision.
    race_state:
        Full RaceState used to build the FIA regulation query for N30.
    laps_df:
        When provided, N28 is called via run_pit_strategy_agent_from_state.
        When None, run_pit_strategy_agent is used (FastF1 entry point).

    Returns (pit_out, regulation_context_str). Both may be None if the
    respective agent was not activated this lap.
    """
    pit_out = None
    if "N28" in active:
        pit_lap_state = {
            **lap_state,
            "laps_to_cliff": tire_out.laps_to_cliff_p50,
            "sc_prob":       situation_out.sc_prob_3lap,
        }
        if laps_df is not None:
            pit_out = run_pit_strategy_agent_from_state(pit_lap_state, laps_df)
        else:
            pit_out = run_pit_strategy_agent(pit_lap_state)

    regulation_context = None
    if "N30" in active:
        pit_action = pit_out.action if pit_out else None
        question   = _build_rag_question(
            sc_active  = situation_out.sc_prob_3lap > CFG.sc_prob_threshold,
            pit_action = pit_action,
            compound   = race_state.compound,
        )
        reg_out            = run_rag_agent(question)
        regulation_context = reg_out.answer

    return pit_out, regulation_context


# ==============================================================================
# Entry points
# ==============================================================================

def run_strategy_orchestrator(
    race_state: "RaceState",
    lap_state:  dict,
) -> "StrategyRecommendation":
    """Run the Strategy Orchestrator for one lap and return a StrategyRecommendation.

    Primary entry point. Uses the FastF1-dependent entry points of each sub-agent,
    which require the sub-agent LAPS/SESSION_META globals to be populated in advance
    (i.e. each sub-agent's setup_session or equivalent must have been called).

    race_state:
        Validated Pydantic RaceState for this lap. Contains driver, position,
        compound, tyre_life, weather fields, and pre-filtered radio/RCM events.
    lap_state:
        Dict of scalar lap features forwarded to sub-agent entry points. Must
        contain: driver_number, stint, team, year, gp_name. Optional keys:
        laps_since_pit, fuel_load, prev_lap_time, prev_speed_st, humidity,
        rivals (list of rival dicts for N27/N28).

    Returns a StrategyRecommendation with action, reasoning, confidence,
    scenario_scores, and regulation_context populated. scenario_scores and
    regulation_context are attached after the LLM call, not parsed from it.
    """
    # Layer 1a — always-on agents
    pace_out, tire_out, situation_out, radio_out = _run_always_on_agents(
        race_state, lap_state
    )

    # Layer 1b — routing
    active = _decide_agents_to_call(
        tire_warning = tire_out.warning_level,
        sc_prob_3lap = situation_out.sc_prob_3lap,
        radio_alerts = radio_out.alerts,
    )

    # Layer 1c — conditional agents
    pit_out, regulation_context = _run_conditional_agents(
        active        = active,
        lap_state     = lap_state,
        tire_out      = tire_out,
        situation_out = situation_out,
        race_state    = race_state,
        laps_df       = None,
    )
    regulation_context = regulation_context or ""

    # Layer 2 — MC simulation
    mc_results = _run_mc_simulation(
        pace_out      = pace_out,
        tire_out      = tire_out,
        situation_out = situation_out,
        pit_out       = pit_out,
        alpha         = race_state.risk_tolerance,
    )
    best_mc = max(mc_results, key=lambda s: mc_results[s]["score"])

    # Layer 3 — LLM synthesis
    prompt = _build_orchestrator_prompt(
        race_state           = race_state,
        mc_results           = mc_results,
        best_mc              = best_mc,
        pace_reasoning       = pace_out.reasoning,
        tire_reasoning       = tire_out.reasoning,
        situation_reasoning  = situation_out.reasoning,
        pit_reasoning        = pit_out.reasoning if pit_out else "",
        radio_reasoning      = radio_out.reasoning,
        regulation_context   = regulation_context,
    )

    rec                    = _get_orchestrator_llm().invoke(prompt)
    rec.scenario_scores    = mc_results
    rec.regulation_context = regulation_context

    return rec


def run_strategy_orchestrator_from_state(
    race_state: "RaceState",
    laps_df:    pd.DataFrame,
    lap_state:  dict | None = None,
) -> "StrategyRecommendation":
    """RSM adapter — run the orchestrator without a live FastF1 session.

    Calls the *_from_state entry points of every sub-agent so the orchestrator
    can run from a pre-loaded laps DataFrame (e.g. from RaceStateManager replay
    or offline backtesting) without any FastF1 session object.

    race_state:
        Validated Pydantic RaceState for this lap.
    laps_df:
        Full lap DataFrame from RaceStateManager. Forwarded to each sub-agent's
        RSM adapter to populate LAPS / SESSION_META globals.
    lap_state:
        Optional supplementary scalar dict. When None, a minimal lap_state is
        derived automatically from race_state and laps_df. Provide it when
        additional features (prev_lap_time, prev_speed_st, humidity, rivals)
        are available from the RaceStateManager.

    Returns a StrategyRecommendation identical to run_strategy_orchestrator().
    """
    if lap_state is None:
        driver_rows = laps_df[laps_df["Driver"] == race_state.driver]
        lap_row     = driver_rows[driver_rows["LapNumber"] == race_state.lap]
        year        = int(laps_df["Year"].iloc[0]) if "Year" in laps_df.columns else 2025
        gp_name     = (
            str(laps_df["GP_Name"].iloc[0]) if "GP_Name" in laps_df.columns else ""
        )
        stint = int(lap_row["Stint"].iloc[0]) if not lap_row.empty else 1
        team  = (
            str(lap_row["Team"].iloc[0]) if not lap_row.empty and "Team" in lap_row else "Unknown"
        )
        lap_state = {
            "lap_number": race_state.lap,
            "driver": {
                "driver":        race_state.driver,
                "driver_number": 0,
                "team":          team,
                "position":      race_state.position,
                "compound":      race_state.compound,
                "tyre_life":     race_state.tyre_life,
                "stint":         stint,
                "lap_time_s":    None,
                "speed_st":      300.0,
                "fuel_load":     1 - race_state.lap / max(race_state.total_laps, 1),
            },
            "session_meta": {
                "gp_name":    gp_name,
                "gp":         gp_name,
                "year":       year,
                "driver":     race_state.driver,
                "team":       team,
                "total_laps": race_state.total_laps,
            },
            "weather": {
                "air_temp":   race_state.air_temp,
                "track_temp": race_state.track_temp,
                "rainfall":   race_state.rainfall,
                "humidity":   50.0,
            },
            "rivals": [],
        }

    # Layer 1a — always-on agents (RSM variants)
    pace_out, tire_out, situation_out, radio_out = _run_always_on_agents_from_state(
        race_state, laps_df, lap_state
    )

    # Layer 1b — routing
    active = _decide_agents_to_call(
        tire_warning = tire_out.warning_level,
        sc_prob_3lap = situation_out.sc_prob_3lap,
        radio_alerts = radio_out.alerts,
    )

    # Layer 1c — conditional agents (RSM variants)
    pit_out, regulation_context = _run_conditional_agents(
        active        = active,
        lap_state     = lap_state,
        tire_out      = tire_out,
        situation_out = situation_out,
        race_state    = race_state,
        laps_df       = laps_df,
    )
    regulation_context = regulation_context or ""

    # Layer 2 — MC simulation (same as primary entry point)
    mc_results = _run_mc_simulation(
        pace_out      = pace_out,
        tire_out      = tire_out,
        situation_out = situation_out,
        pit_out       = pit_out,
        alpha         = race_state.risk_tolerance,
    )
    best_mc = max(mc_results, key=lambda s: mc_results[s]["score"])

    # Layer 3 — LLM synthesis (same as primary entry point)
    prompt = _build_orchestrator_prompt(
        race_state           = race_state,
        mc_results           = mc_results,
        best_mc              = best_mc,
        pace_reasoning       = pace_out.reasoning,
        tire_reasoning       = tire_out.reasoning,
        situation_reasoning  = situation_out.reasoning,
        pit_reasoning        = pit_out.reasoning if pit_out else "",
        radio_reasoning      = radio_out.reasoning,
        regulation_context   = regulation_context,
    )

    rec                    = _get_orchestrator_llm().invoke(prompt)
    rec.scenario_scores    = mc_results
    rec.regulation_context = regulation_context

    return rec
