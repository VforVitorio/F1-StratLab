"""
Headless CLI simulation demo — validates the full v0.9 agent pipeline without
any HTTP layer.

Loads a race from data/raw/2025/<gp_name>/ and iterates lap by lap through
RaceReplayEngine. For each lap it builds a RaceState, calls
run_strategy_orchestrator_from_state, and prints a per-lap summary table.

Usage
-----
    python scripts/run_simulation_cli.py <gp_name> <driver> <team> [options]

Examples
--------
    # No LLM — prints MC scores only (fast, no LM Studio required)
    python scripts/run_simulation_cli.py Melbourne NOR McLaren --no-llm

    # Laps 15-25 with LLM synthesis (LM Studio must be running)
    python scripts/run_simulation_cli.py Bahrain NOR McLaren --laps 15-25

    # Custom data paths
    python scripts/run_simulation_cli.py Monaco LEC Ferrari \\
        --raw-dir data/raw/2025 \\
        --featured data/processed/laps_featured_2025.parquet

Output columns
--------------
    Lap | Cmpd | Life | Action     | Conf | STAY  / PIT   / UDCT  / OVCT  | Reasoning
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

# ---------------------------------------------------------------------------
# Repo-root sys.path injection — must happen before any src.* import
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = next(
    (p for p in [_SCRIPT_DIR, *_SCRIPT_DIR.parents] if (p / ".git").exists()),
    _SCRIPT_DIR.parent,
)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Lazy imports — surface missing-model errors clearly
# ---------------------------------------------------------------------------
try:
    from src.simulation.replay_engine import RaceReplayEngine
except ImportError as e:
    sys.exit(f"[FATAL] Cannot import simulation engine: {e}")

try:
    from src.agents.strategy_orchestrator import RaceState, run_strategy_orchestrator_from_state
except ImportError as e:
    sys.exit(f"[FATAL] Cannot import strategy orchestrator: {e}")


# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_RED    = "\033[91m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"

_ACTION_COLOUR = {
    "STAY_OUT":  _GREEN,
    "PIT_NOW":   _RED,
    "UNDERCUT":  _YELLOW,
    "OVERCUT":   _YELLOW,
    "ALERT":     _CYAN,
}


def _colour_action(action: str) -> str:
    col = _ACTION_COLOUR.get(action.upper(), "")
    return f"{_BOLD}{col}{action:<10}{_RESET}"


# ---------------------------------------------------------------------------
# RaceState builder
# ---------------------------------------------------------------------------

def _build_race_state(
    lap_state: dict[str, Any],
    driver_code: str,
    prev_lap_time: float,
) -> RaceState:
    """Map RaceStateManager's lap_state dict → RaceState Pydantic model."""
    driver_st = lap_state["driver"]
    rivals    = lap_state.get("rivals", [])
    weather   = lap_state.get("weather", {})

    # Gap to the car directly ahead (position = our_pos - 1)
    our_pos = driver_st.get("position", 99)
    car_ahead = next(
        (r for r in rivals if r.get("position") == our_pos - 1), None
    )
    if car_ahead is not None:
        gap_ahead_s = abs(car_ahead.get("interval_to_driver_s") or 0.0)
    else:
        gap_ahead_s = 0.0

    # Pace delta vs own previous lap (0.0 on lap 1)
    cur_lap_time = driver_st.get("lap_time_s") or 0.0
    pace_delta_s = cur_lap_time - prev_lap_time if prev_lap_time else 0.0

    return RaceState(
        driver        = driver_code,
        lap           = driver_st["lap_number"],
        total_laps    = lap_state["session_meta"]["total_laps"],
        position      = our_pos,
        compound      = driver_st.get("compound", "UNKNOWN"),
        tyre_life     = driver_st.get("tyre_life", 0),
        gap_ahead_s   = gap_ahead_s,
        pace_delta_s  = pace_delta_s,
        air_temp      = weather.get("air_temp", 25.0),
        track_temp    = weather.get("track_temp", 40.0),
        rainfall      = bool(weather.get("rainfall", False)),
    )


# ---------------------------------------------------------------------------
# no-LLM mode: run sub-agents + MC sim, skip LLM synthesis
# ---------------------------------------------------------------------------

def _run_no_llm(
    race_state: RaceState,
    lap_state: dict[str, Any],
    laps_df: pd.DataFrame,
) -> dict[str, Any]:
    """Run ML models only — no LLM synthesis at any layer.

    Calls each sub-agent individually, catching connection errors so that a
    failing LLM call in one agent does not abort the whole lap. Falls back to
    a stub output for any agent that raises a connection/API error (these happen
    when a sub-agent tries to call LM Studio for its own reasoning synthesis).

    Returns a dict with the same keys as StrategyRecommendation but produced
    deterministically from the MC simulation scores.
    """
    from src.agents.pace_agent           import run_pace_agent_from_state, PaceOutput
    from src.agents.tire_agent           import run_tire_agent_from_state, TireOutput
    from src.agents.race_situation_agent import (
        run_race_situation_agent_from_state, RaceSituationOutput,
    )
    from src.agents.radio_agent          import run_radio_agent_from_state, RadioOutput
    from src.agents.strategy_orchestrator import (
        _run_mc_simulation,
        _decide_agents_to_call,
        _run_conditional_agents,
    )

    _CONN_ERRORS = ("Connection", "APIConnection", "OpenAI", "HTTP", "Timeout", "RemoteDisconnected")

    def _is_connection_err(exc: Exception) -> bool:
        return any(k in type(exc).__name__ for k in _CONN_ERRORS) or \
               any(k in str(exc)[:120] for k in ("Connection error", "connect ECONNREFUSED"))

    def _safe_call(fn, *args, stub):
        try:
            return fn(*args)
        except Exception as exc:
            if _is_connection_err(exc):
                return stub  # LLM unreachable — ML already ran, return stub
            raise  # re-raise real errors (dtype, key, etc.)

    # Default stubs for when LLM synthesis inside sub-agents fails
    pace_stub = PaceOutput(
        lap_time_pred=90.0, delta_vs_prev=0.0, delta_vs_median=0.0,
        ci_p10=88.0, ci_p90=92.0, reasoning="[stub — LLM unreachable]",
    )
    tire_stub = TireOutput(
        compound=race_state.compound,
        current_tyre_life=race_state.tyre_life,
        deg_rate=0.05,
        laps_to_cliff_p10=20.0, laps_to_cliff_p50=25.0, laps_to_cliff_p90=30.0,
        gp_name="", reasoning="[stub — LLM unreachable]",
    )
    sit_stub = RaceSituationOutput(
        overtake_prob=0.1, sc_prob_3lap=0.05,
        reasoning="[stub — LLM unreachable]",
    )
    radio_stub = RadioOutput(
        radio_events=[], rcm_events=[], alerts=[],
        reasoning="[stub — LLM unreachable]", corrections=[],
    )

    # Layer 1 — always-on agents (each call isolated so one failure doesn't abort the lap)
    pace_out  = _safe_call(run_pace_agent_from_state, lap_state, stub=pace_stub)
    tire_out  = _safe_call(run_tire_agent_from_state, lap_state, laps_df, stub=tire_stub)
    sit_out   = _safe_call(run_race_situation_agent_from_state, lap_state, laps_df, stub=sit_stub)

    radio_msgs = [m for m in race_state.radio_msgs]
    rcm_events = [e for e in race_state.rcm_events]
    radio_out = _safe_call(
        run_radio_agent_from_state,
        {**lap_state, "lap": race_state.lap,
         "radio_msgs": radio_msgs, "rcm_events": rcm_events},
        laps_df,
        stub=radio_stub,
    )

    # MoE routing
    alerts = [a["type"] for a in (radio_out.alerts if radio_out else [])]
    active = _decide_agents_to_call(
        tire_out.warning_level if tire_out else "OK",
        sit_out.sc_prob_3lap   if sit_out  else 0.0,
        alerts,
    )

    # Layer 1 conditional
    pit_out, _ = _run_conditional_agents(
        active, lap_state, tire_out, sit_out, race_state, laps_df
    )

    # Layer 2 — MC simulation
    mc = _run_mc_simulation(
        pace_out, tire_out, sit_out, pit_out,
        alpha=race_state.risk_tolerance,
    )

    best = max(mc, key=lambda k: mc[k]["score"])
    return {
        "action":          best,
        "reasoning":       "[no-llm mode — LLM synthesis skipped]",
        "confidence":      0.0,
        "scenario_scores": {k: round(v["score"], 3) for k, v in mc.items()},
        "regulation_context": "",
    }


# ---------------------------------------------------------------------------
# Table printing helpers
# ---------------------------------------------------------------------------

_HEADER = (
    f"{'Lap':>3}  {'Cmpd':<8}  {'Life':>4}  {'Action':<12}  "
    f"{'Conf':>5}  {'STAY':>6} {'PIT':>6} {'UDCT':>6} {'OVCT':>6}  Reasoning"
)
_SEP = "-" * len(_HEADER)


def _print_row(lap: int, rec: Any, scores: dict[str, float]) -> None:
    s = scores
    stay = s.get("STAY_OUT", 0.0)
    pit  = s.get("PIT_NOW",  0.0)
    ucut = s.get("UNDERCUT", 0.0)
    ocut = s.get("OVERCUT",  0.0)

    action = getattr(rec, "action", rec.get("action", "?")) if not hasattr(rec, "action") or isinstance(rec, dict) else rec.action
    confidence = getattr(rec, "confidence", rec.get("confidence", 0.0)) if not isinstance(rec, dict) else rec.get("confidence", 0.0)
    reasoning  = getattr(rec, "reasoning",  rec.get("reasoning",  "")) if not isinstance(rec, dict) else rec.get("reasoning", "")

    col_action = _colour_action(action)
    print(
        f"{lap:>3}  {_DIM}{'':8}{_RESET}  {'':>4}  {col_action}  "
        f"{confidence:>5.2f}  {stay:>6.3f} {pit:>6.3f} {ucut:>6.3f} {ocut:>6.3f}  "
        f"{reasoning[:70]}"
    )


def _print_row_with_state(
    lap: int,
    compound: str,
    tyre_life: int,
    rec: Any,
    scores: dict[str, float],
) -> None:
    s = scores
    stay = s.get("STAY_OUT", 0.0)
    pit  = s.get("PIT_NOW",  0.0)
    ucut = s.get("UNDERCUT", 0.0)
    ocut = s.get("OVERCUT",  0.0)

    if isinstance(rec, dict):
        action     = rec.get("action", "?")
        confidence = rec.get("confidence", 0.0)
        reasoning  = rec.get("reasoning", "")
    else:
        action     = rec.action
        confidence = rec.confidence
        reasoning  = rec.reasoning

    col_action = _colour_action(action)
    print(
        f"{lap:>3}  {compound:<8}  {tyre_life:>4}  {col_action}  "
        f"{confidence:>5.2f}  {stay:>6.3f} {pit:>6.3f} {ucut:>6.3f} {ocut:>6.3f}  "
        f"{reasoning[:70]}"
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    raw_dir  = Path(args.raw_dir)
    race_dir = raw_dir / args.gp_name

    if not race_dir.exists():
        sys.exit(f"[FATAL] Race directory not found: {race_dir}")

    featured_path = Path(args.featured)
    if not featured_path.exists():
        sys.exit(f"[FATAL] Featured parquet not found: {featured_path}")

    print(f"\n{_BOLD}F1 Strategy Manager — CLI Simulation{_RESET}")
    print(f"  GP      : {args.gp_name}")
    print(f"  Driver  : {args.driver}")
    print(f"  Team    : {args.team}")
    print(f"  Mode    : {'no-LLM (MC scores only)' if args.no_llm else 'full (LLM synthesis)'}")
    print()

    # Load featured parquet once (passed to all agent RSM adapters)
    print(f"{_DIM}Loading featured parquet …{_RESET}", end=" ", flush=True)
    laps_df = pd.read_parquet(featured_path)
    print(f"done ({len(laps_df):,} rows)")

    # Build replay engine (loads raw race parquet internally)
    print(f"{_DIM}Loading race parquet from {race_dir} …{_RESET}", end=" ", flush=True)
    engine = RaceReplayEngine(race_dir, args.driver, args.team, interval_seconds=0.0)
    print(f"done ({engine.total_laps} laps)")
    print()

    # Lap range filter
    lap_start, lap_end = 1, engine.total_laps
    if args.laps:
        parts = args.laps.split("-")
        lap_start = int(parts[0])
        lap_end   = int(parts[1]) if len(parts) > 1 else int(parts[0])

    print(_HEADER)
    print(_SEP)

    prev_lap_time: float = 0.0
    errors: list[str]   = []

    for lap_state in engine.replay():
        lap_num = lap_state["lap_number"]

        if lap_num < lap_start:
            continue
        if lap_num > lap_end:
            break

        driver_st = lap_state.get("driver", {})
        if not driver_st:
            print(f"{lap_num:>3}  [DNF — no driver state]")
            continue

        compound  = driver_st.get("compound", "?")
        tyre_life = driver_st.get("tyre_life", 0)

        try:
            race_state = _build_race_state(lap_state, args.driver, prev_lap_time)
            prev_lap_time = driver_st.get("lap_time_s") or prev_lap_time

            if args.no_llm:
                result = _run_no_llm(race_state, lap_state, laps_df)
                scores = result["scenario_scores"]
            else:
                result = run_strategy_orchestrator_from_state(race_state, laps_df, lap_state)
                scores = getattr(result, "scenario_scores", {})

            _print_row_with_state(lap_num, compound, tyre_life, result, scores)

        except Exception as exc:
            err_msg = f"[LAP {lap_num} ERROR: {type(exc).__name__}: {exc}]"
            print(f"{_RED}{err_msg}{_RESET}")
            errors.append(err_msg)
            if args.verbose:
                traceback.print_exc()

    print(_SEP)
    if errors:
        print(f"\n{_YELLOW}Completed with {len(errors)} error(s):{_RESET}")
        for e in errors:
            print(f"  {e}")
    else:
        print(f"\n{_GREEN}Completed successfully.{_RESET}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="F1 Strategy Manager — headless CLI simulation demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("gp_name", help="Grand Prix folder name (e.g. Melbourne, Bahrain)")
    p.add_argument("driver",  help="FIA three-letter driver code (e.g. NOR, HAM)")
    p.add_argument("team",    help="Team name as stored in laps parquet (e.g. McLaren)")
    p.add_argument(
        "--raw-dir",
        default="data/raw/2025",
        help="Base directory for raw race parquets (default: data/raw/2025)",
    )
    p.add_argument(
        "--featured",
        default="data/processed/laps_featured_2025.parquet",
        help="Path to featured parquet for agent RSM adapters",
    )
    p.add_argument(
        "--laps",
        default=None,
        help="Lap range to simulate, e.g. 15-40 (default: all laps)",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM synthesis — print MC scores only (no LM Studio required)",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full tracebacks on per-lap errors",
    )
    return p.parse_args()


if __name__ == "__main__":
    run(_parse_args())
