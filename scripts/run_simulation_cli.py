"""
Headless CLI simulation demo — validates the full v0.9 agent pipeline without
any HTTP layer.

Loads a race from data/raw/2025/<gp_name>/ and iterates lap by lap through
RaceReplayEngine. For each lap it builds a RaceState, calls
run_strategy_orchestrator_from_state, and renders a live per-lap Rich table.

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
    Lap | Cmpd | Life | Action | Conf | STAY / PIT / UDCT / OVCT | Reasoning
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
from rich.box import ROUNDED
from rich.console import Console, Group
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

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

# Load .env so OPENAI_API_KEY is available when --provider openai is used
try:
    from dotenv import load_dotenv
    _env = _REPO_ROOT / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

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
# Rich setup
# ---------------------------------------------------------------------------
console = Console()

ACTION_STYLE: dict[str, str] = {
    "STAY_OUT": "bold green",
    "PIT_NOW":  "bold red",
    "UNDERCUT": "bold yellow",
    "OVERCUT":  "bold yellow",
    "ALERT":    "bold cyan",
}

# Pirelli tyre-compound colours
_COMPOUND_STYLE: dict[str, str] = {
    "SOFT":         "bold red",
    "MEDIUM":       "bold yellow",
    "HARD":         "white",
    "INTERMEDIATE": "bold green",
    "WET":          "bold blue",
    "INT":          "bold green",
}

# Loaded once in run() — maps year → gp → compound → Cx
_TIRE_ALLOC: dict = {}


def _load_tire_alloc(repo_root: Path) -> None:
    """Populate _TIRE_ALLOC from data/tire_compounds_by_race.json."""
    global _TIRE_ALLOC
    path = repo_root / "data" / "tire_compounds_by_race.json"
    if path.exists():
        with open(path) as f:
            _TIRE_ALLOC = json.load(f)


def _compound_text(compound: str, gp_name: str, year: int) -> Text:
    """Return a coloured Rich Text showing compound + Cx (e.g. 'SOF/C4')."""
    cu = compound.upper()
    cx = _TIRE_ALLOC.get(str(year), {}).get(gp_name, {}).get(cu)
    if cx:
        label = f"{cu[:3]}/{cx}"   # SOF/C4, MED/C3, HAR/C2
    else:
        label = cu[:4]             # INTE, WET (no Cx for wet compounds)
    return Text(label, style=_COMPOUND_STYLE.get(cu, ""))


def _make_table() -> Table:
    """Build and return the Rich Table skeleton (no rows yet)."""
    table = Table(
        box=ROUNDED,
        show_header=True,
        header_style="bold white",
        expand=False,
    )
    table.add_column("Lap",       justify="right",  style="dim",    width=4)
    table.add_column("Tyre",      justify="left",                   width=8)
    table.add_column("Age",       justify="right",  style="dim",    width=4)
    table.add_column("P",         justify="right",  style="dim",    width=3)
    table.add_column("Lap (s)",   justify="right",                  width=8)
    table.add_column("Gap Fwd",   justify="right",  style="dim",    width=7)
    table.add_column("Decision",  justify="left",                   width=10)
    table.add_column("Conf",      justify="right",                  width=5)
    table.add_column("Stay",      justify="right",  style="green",  width=6)
    table.add_column("Pit",       justify="right",  style="red",    width=6)
    table.add_column("Ucut",      justify="right",  style="yellow", width=6)
    table.add_column("Ocut",      justify="right",  style="yellow", width=6)
    table.add_column("Reasoning",                                   min_width=36)
    return table


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

    our_pos = driver_st.get("position", 99)
    car_ahead = next(
        (r for r in rivals if r.get("position") == our_pos - 1), None
    )
    gap_ahead_s = abs(car_ahead.get("interval_to_driver_s") or 0.0) if car_ahead else 0.0

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
    """Run ML models only — no LLM synthesis at any layer."""
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
                return stub
            raise

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

    pace_out  = _safe_call(run_pace_agent_from_state, lap_state, stub=pace_stub)
    tire_out  = _safe_call(run_tire_agent_from_state, lap_state, laps_df, stub=tire_stub)
    sit_out   = _safe_call(run_race_situation_agent_from_state, lap_state, laps_df, stub=sit_stub)

    radio_msgs = list(race_state.radio_msgs)
    rcm_events = list(race_state.rcm_events)
    radio_out = _safe_call(
        run_radio_agent_from_state,
        {**lap_state, "lap": race_state.lap,
         "radio_msgs": radio_msgs, "rcm_events": rcm_events},
        laps_df,
        stub=radio_stub,
    )

    alerts = [a["type"] for a in (radio_out.alerts if radio_out else [])]
    active = _decide_agents_to_call(
        tire_out.warning_level if tire_out else "OK",
        sit_out.sc_prob_3lap   if sit_out  else 0.0,
        alerts,
    )

    pit_out, _ = _run_conditional_agents(
        active, lap_state, tire_out, sit_out, race_state, laps_df
    )

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
# Main loop
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    # Set provider before any agent singleton is created
    os.environ["F1_LLM_PROVIDER"] = args.provider

    raw_dir  = Path(args.raw_dir)
    race_dir = raw_dir / args.gp_name

    if not race_dir.exists():
        sys.exit(f"[FATAL] Race directory not found: {race_dir}")

    featured_path = Path(args.featured)
    if not featured_path.exists():
        sys.exit(f"[FATAL] Featured parquet not found: {featured_path}")

    console.print(f"\n[bold]F1 Strategy Manager — CLI Simulation[/bold]")
    console.print(f"  GP      : {args.gp_name}")
    console.print(f"  Driver  : {args.driver}")
    console.print(f"  Team    : {args.team}")
    console.print(
        f"  Mode    : {'[dim]no-LLM (MC scores only)[/dim]' if args.no_llm else '[bold]full (LLM synthesis)[/bold]'}"
    )
    console.print()

    _load_tire_alloc(_REPO_ROOT)

    console.print("[dim]Loading featured parquet…[/dim]", end=" ")
    laps_df = pd.read_parquet(featured_path)
    console.print(f"done ([dim]{len(laps_df):,} rows[/dim])")

    console.print(f"[dim]Loading race parquet from {race_dir}…[/dim]", end=" ")
    engine = RaceReplayEngine(race_dir, args.driver, args.team, interval_seconds=args.interval)
    console.print(f"done ([dim]{engine.total_laps} laps[/dim])")
    console.print()

    lap_start, lap_end = 1, engine.total_laps
    if args.laps:
        parts = args.laps.split("-")
        lap_start = int(parts[0])
        lap_end   = int(parts[1]) if len(parts) > 1 else int(parts[0])

    table = _make_table()
    errors: list[str] = []
    prev_lap_time: float = 0.0

    _spinner = Spinner("dots", style="dim cyan")

    def _render(status: str = "") -> Group:
        if status:
            _spinner.text = Text(f"  lap {status}", style="dim cyan")
            return Group(table, _spinner)
        return Group(table, Text(""))

    with Live(_render(), console=console, refresh_per_second=10) as live:
        for lap_state in engine.replay():
            lap_num = lap_state["lap_number"]

            if lap_num < lap_start:
                continue
            if lap_num > lap_end:
                break

            driver_st = lap_state.get("driver", {})
            if not driver_st:
                table.add_row(str(lap_num), "—", "—", "—", "—", "—",
                              Text("[DNF]", style="dim"), "", "", "", "", "", "")
                live.update(_render())
                continue

            compound  = driver_st.get("compound", "?")
            tyre_life = driver_st.get("tyre_life", 0)
            position  = driver_st.get("position", 0)
            lap_time  = driver_st.get("lap_time_s") or 0.0

            # Gap to car directly ahead (from rivals list)
            rivals   = lap_state.get("rivals", [])
            car_ahead = next((r for r in rivals if r.get("position") == position - 1), None)
            gap_ahead = abs(car_ahead.get("interval_to_driver_s") or 0.0) if car_ahead else 0.0
            gap_str   = f"{gap_ahead:.2f}" if gap_ahead > 0 else "—"

            cmpd_text = _compound_text(compound, args.gp_name, args.year)

            # Show spinner while agents / LLM run
            live.update(_render(f"{lap_num} / {lap_end}  —  running agents…"))

            try:
                race_state = _build_race_state(lap_state, args.driver, prev_lap_time)
                prev_lap_time = lap_time or prev_lap_time

                if args.no_llm:
                    result = _run_no_llm(race_state, lap_state, laps_df)
                    scores = result["scenario_scores"]
                    action     = result["action"]
                    confidence = result["confidence"]
                    reasoning  = result["reasoning"]
                else:
                    result     = run_strategy_orchestrator_from_state(race_state, laps_df, lap_state)
                    scores     = getattr(result, "scenario_scores", {})
                    action     = getattr(result, "action", "?")
                    confidence = getattr(result, "confidence", 0.0)
                    reasoning  = getattr(result, "reasoning", "")

                stay = scores.get("STAY_OUT", 0.0)
                pit  = scores.get("PIT_NOW",  0.0)
                ucut = scores.get("UNDERCUT", 0.0)
                ocut = scores.get("OVERCUT",  0.0)

                action_text = Text(action, style=ACTION_STYLE.get(action.upper(), ""))

                table.add_row(
                    str(lap_num),
                    cmpd_text,
                    str(tyre_life),
                    str(position),
                    f"{lap_time:.2f}" if lap_time else "—",
                    gap_str,
                    action_text,
                    f"{confidence:.2f}",
                    f"{stay:.3f}",
                    f"{pit:.3f}",
                    f"{ucut:.3f}",
                    f"{ocut:.3f}",
                    reasoning[:80],
                )

            except Exception as exc:
                err_msg = f"LAP {lap_num} ERROR: {type(exc).__name__}: {exc}"
                errors.append(err_msg)
                table.add_row(
                    str(lap_num), cmpd_text, str(tyre_life),
                    str(position), "—", gap_str,
                    Text("[ERROR]", style="bold red"), "", "", "", "", "",
                    str(exc)[:60],
                )
                if args.verbose:
                    console.print_exception()

            # Clear spinner once row is in the table
            live.update(_render())

    if errors:
        console.print(f"\n[yellow]Completed with {len(errors)} error(s):[/yellow]")
        for e in errors:
            console.print(f"  [red]{e}[/red]")
    else:
        console.print("\n[green]Completed successfully.[/green]")


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
        "--year",
        type=int,
        default=2025,
        help="Season year — used for tyre compound allocation lookup (default: 2025)",
    )
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
        "--provider",
        default="lmstudio",
        choices=["lmstudio", "openai"],
        help="LLM provider: 'lmstudio' (default) or 'openai' (needs OPENAI_API_KEY in .env)",
    )
    p.add_argument(
        "--interval",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help="Pause between laps in seconds (default: 0.0 — no pause). "
             "E.g. --interval 2.0 pauses 2 s after each lap row is printed.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full tracebacks on per-lap errors",
    )
    return p.parse_args()


if __name__ == "__main__":
    run(_parse_args())
