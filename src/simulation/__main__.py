"""
CLI entry point for the race replay simulation.

Usage
-----
    python -m src.simulation <gp_name> <driver> <team> [--interval N] [--laps N-M]

Examples
--------
    python -m src.simulation Melbourne NOR McLaren
    python -m src.simulation Monaco HAM Mercedes --interval 2
    python -m src.simulation Monza LEC Ferrari --laps 10-30
    python -m src.simulation Silverstone VER "Red Bull Racing" --interval 0

Arguments
---------
    gp_name   : Grand Prix folder name under data/raw/2025/ (e.g. Melbourne)
    driver    : Three-letter FIA driver code (e.g. NOR, HAM, VER)
    team      : Team name exactly as stored in the laps parquet
    --interval: Seconds between lap emissions (default 0 = as fast as possible)
    --laps    : Lap range to replay, e.g. 15-40 (default: all laps)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running from repo root without installing the package
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.simulation.replay_engine import RaceReplayEngine

# Folder name → canonical key used in tire_compounds_by_race.json.
# Only entries that differ from a simple underscore→space replacement are listed.
_GP_FOLDER_ALIASES: dict[str, str] = {
    "Miami_Gardens": "Miami",
    "Marina_Bay":    "Marina Bay",
    "Mexico_City":   "Mexico City",
    "Las_Vegas":     "Las Vegas",
    "Montréal":      "Montréal",
}


def _load_compound_map(year: int) -> dict[str, dict[str, str]]:
    """Load Pirelli compound allocation from data/tire_compounds_by_race.json.

    Returns a dict mapping canonical GP name → {HARD/MEDIUM/SOFT: Cx}.
    Falls back to an empty dict if the file is missing or the year is absent.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    json_path = repo_root / "data" / "tire_compounds_by_race.json"
    if not json_path.exists():
        return {}
    import json
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get(str(year), {})

_RESET = "\033[0m"
_BOLD  = "\033[1m"
_GREEN = "\033[32m"
_CYAN  = "\033[36m"
_YEL   = "\033[33m"
_RED   = "\033[31m"
_GREY  = "\033[90m"


def _compound_color(compound: str) -> str:
    c = compound.upper()
    if c in ("SOFT", "S"):
        return "\033[31m"   # red
    if c in ("MEDIUM", "M"):
        return "\033[33m"   # yellow
    if c in ("HARD", "H"):
        return "\033[37m"   # white
    if c in ("INTERMEDIATE", "I"):
        return "\033[32m"   # green
    if c in ("WET", "W"):
        return "\033[34m"   # blue
    return _GREY


def _fmt_gap(gap: float | None) -> str:
    if gap is None:
        return "   ---  "
    return f"{gap:>+8.3f}s"


def _fmt_lap(lt: float | None) -> str:
    if lt is None:
        return "  ---.- "
    m, s = divmod(lt, 60)
    return f"{int(m)}:{s:06.3f}"


def _print_header(gp: str, driver: str, team: str, total_laps: int) -> None:
    sep = "-" * 72
    print(f"\n{_BOLD}{sep}{_RESET}")
    print(f"  {_BOLD}{_CYAN}F1 Strategy - Race Replay{_RESET}   "
          f"{_BOLD}{gp}{_RESET}  |  {driver} / {team}  |  {total_laps} laps")
    print(sep)
    print(f"  {'Lap':>4}  {'Pos':>3}  {'Compound':>12}  {'LapTime':>8}  "
          f"{'Gap Leader':>10}  {'Ahead':>24}  {'Behind':>24}")
    print(sep)


def _resolve_gp_key(folder_name: str) -> str:
    """Convert a folder name to the canonical key used in tire_compounds_by_race.json."""
    if folder_name in _GP_FOLDER_ALIASES:
        return _GP_FOLDER_ALIASES[folder_name]
    return folder_name.replace("_", " ")


def _cx(compound: str, gp_name: str, compound_map: dict) -> str:
    """Return Pirelli Cx label for dry compounds, empty string for wet/intermediate."""
    key = _resolve_gp_key(gp_name)
    cx  = compound_map.get(key, {}).get(compound.upper(), "")
    return f"-{cx}" if cx else ""


def _print_lap(lap_state: dict, gp_name: str = "", compound_map: dict | None = None) -> None:
    cmap   = compound_map or {}
    d      = lap_state["driver"]
    rivals = lap_state["rivals"]
    lap    = lap_state["lap_number"]
    pos    = d.get("position") or "?"
    cmp    = d.get("compound", "?")
    life   = d.get("tyre_life") or 0
    ccolor = _compound_color(cmp)
    cmp_s  = f"{ccolor}{cmp[:3]}{_cx(cmp, gp_name, cmap)}({life:>2}L){_RESET}"

    lt_s   = _fmt_lap(d.get("lap_time_s"))
    gap_s  = _fmt_gap(d.get("gap_to_leader_s"))

    our_pos = d.get("position") or 0
    ahead  = next((r for r in rivals if r.get("position") == our_pos - 1), None)
    behind = next((r for r in rivals if r.get("position") == our_pos + 1), None)

    def rival_str(r: dict | None, label: str) -> str:
        if r is None:
            return " " * 24
        drv    = r.get("driver", "???")
        itv    = r.get("interval_to_driver_s")
        cmp_r  = r.get("compound", "?")
        life_r = r.get("tyre_life") or 0
        cc     = _compound_color(cmp_r)
        itv_s  = f"{itv:>+7.3f}s" if itv is not None else "   ---  "
        return f"{label}:{_BOLD}{drv}{_RESET} {cc}{cmp_r[:3]}{_cx(cmp_r, gp_name, cmap)}({life_r}L){_RESET} {itv_s}"

    # In-lap / out-lap flags
    flags = ""
    if d.get("is_in_lap"):
        flags += f" {_YEL}[IN]{_RESET}"
    if d.get("is_out_lap"):
        flags += f" {_GREEN}[OUT]{_RESET}"

    print(
        f"  {lap:>4}  {str(pos):>3}  {cmp_s:>12}  {lt_s}  {gap_s}  "
        f"{rival_str(ahead, 'P' + str(our_pos-1)):>24}  "
        f"{rival_str(behind, 'P' + str(our_pos+1)):>24}"
        f"{flags}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay a race lap-by-lap using the F1 strategy simulation engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("gp_name", help="Grand Prix folder name (e.g. Melbourne)")
    parser.add_argument("driver",  help="FIA driver code (e.g. NOR)")
    parser.add_argument("team",    help="Team name (e.g. McLaren)")
    parser.add_argument(
        "--interval", type=float, default=0.0,
        help="Seconds between lap emissions (default: 0 = no sleep)",
    )
    parser.add_argument(
        "--laps", type=str, default=None,
        help="Lap range to replay, e.g. 10-40 (default: all)",
    )
    parser.add_argument(
        "--data-dir", type=str, default="data/raw/2025",
        help="Base directory for race parquets (default: data/raw/2025)",
    )
    args = parser.parse_args()

    race_dir = Path(args.data_dir) / args.gp_name
    if not race_dir.exists():
        print(f"{_RED}Error:{_RESET} race directory not found: {race_dir}", file=sys.stderr)
        print(f"Available GPs: {', '.join(sorted(p.name for p in Path(args.data_dir).iterdir() if p.is_dir()))}")
        sys.exit(1)

    engine = RaceReplayEngine(race_dir, args.driver, args.team, interval_seconds=args.interval)

    # Parse lap range
    lap_start, lap_end = 1, engine.total_laps
    if args.laps:
        try:
            parts = args.laps.split("-")
            lap_start = int(parts[0])
            lap_end   = int(parts[1]) if len(parts) > 1 else engine.total_laps
        except (ValueError, IndexError):
            print(f"{_RED}Error:{_RESET} --laps must be N or N-M (e.g. 10-40)", file=sys.stderr)
            sys.exit(1)

    compound_map = _load_compound_map(engine.rsm.year)

    _print_header(args.gp_name, args.driver, args.team, engine.total_laps)

    for lap_state in engine.replay():
        if lap_state["lap_number"] < lap_start:
            continue
        if lap_state["lap_number"] > lap_end:
            break
        _print_lap(lap_state, gp_name=args.gp_name, compound_map=compound_map)

    print(f"\n{'-'*72}")
    print(f"  Replay complete - {lap_end - lap_start + 1} laps shown.\n")


if __name__ == "__main__":
    main()
