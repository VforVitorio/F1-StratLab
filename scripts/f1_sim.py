"""Headless CLI simulation demo for the F1 StratLab agent pipeline.

The command loads a race from ``data/raw/<year>/<gp_name>/`` and iterates lap
by lap through ``RaceReplayEngine``. Each lap builds a ``RaceState``, runs one
inference through the shared engine with either rich LLM synthesis or the
deterministic ``--no-llm`` profile, and renders a live Rich table.

Usage
-----
    f1-sim <gp_name> <driver> <team> [options]

Examples
--------
    # No LLM synthesis, prints Monte Carlo scores only (no LM Studio required)
    f1-sim Melbourne NOR McLaren --no-llm

    # Laps 15-25 with LLM synthesis (LM Studio must be running unless
    # .env or --provider selects openai)
    f1-sim Sakhir NOR McLaren --laps 15-25

    # Custom data paths
    f1-sim Monaco LEC Ferrari --raw-dir data/raw/2025 \\
        --featured data/processed/laps_featured_2025.parquet

Output columns
--------------
    Lap | Cmpd | Life | Action | Conf | STAY / PIT / UDCT / OVCT | Reasoning
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from cli.theme import package_version  # noqa: E402


def _parse_laps(value: str | None, parser: argparse.ArgumentParser) -> tuple[int, int] | None:
    """Parse a positive single lap or ascending inclusive range."""
    if value is None:
        return None
    match = re.fullmatch(r"([1-9]\d*)(?:-([1-9]\d*))?", value)
    if match is None:
        parser.error("--laps must be a positive lap number or ascending range, such as 5-7")
    try:
        start = int(match.group(1))
        end = int(match.group(2) or start)
    except ValueError:
        parser.error("lap numbers are too large")
    if end < start:
        parser.error("the last lap must be greater than or equal to the first")
    return start, end


def _runner_arguments(args: argparse.Namespace) -> list[str]:
    """Rebuild validated arguments with FIA codes in the runner's canonical case."""
    result = [args.gp_name, args.driver.upper(), args.team]
    if args.year != 2025:
        result.extend(["--year", str(args.year)])
    if args.raw_dir:
        result.extend(["--raw-dir", args.raw_dir])
    if args.featured:
        result.extend(["--featured", args.featured])
    if args.no_first_run:
        result.append("--no-first-run")
    if args.laps:
        result.extend(["--laps", args.laps])
    if args.no_llm:
        result.append("--no-llm")
    if args.provider:
        result.extend(["--provider", args.provider])
    if args.interval:
        result.extend(["--interval", str(args.interval)])
    if args.radio_every:
        result.extend(["--radio-every", str(args.radio_every)])
    if args.no_real_radios:
        result.append("--no-real-radios")
    if args.whisper_model != "turbo":
        result.extend(["--whisper-model", args.whisper_model])
    if args.rival:
        result.extend(["--rival", args.rival.upper()])
    if args.verbose:
        result.append("--verbose")
    return result


def main() -> None:
    """Handle fast version/input checks, then delegate unchanged to the PMV runner."""
    parser = argparse.ArgumentParser(
        prog="f1-sim",
        description="F1 StratLab headless CLI simulation demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("gp_name", help="Grand Prix folder name, such as Melbourne")
    parser.add_argument("driver", help="FIA three-letter driver code, such as NOR")
    parser.add_argument("team", help="Team name stored in the laps parquet")
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Season year, used for tyre compound allocation lookup (default: 2025)",
    )
    parser.add_argument(
        "--raw-dir",
        default=None,
        help="Base directory for raw race parquets (default: <data_root>/raw/<year>)",
    )
    parser.add_argument(
        "--featured",
        default=None,
        help="Path to featured parquet for agent RSM adapters (default: <data_root>/processed/laps_featured_<year>.parquet)",
    )
    parser.add_argument(
        "--no-first-run",
        action="store_true",
        help=(
            "Skip the first-run Hugging Face Hub download check. Useful for CI "
            "or when the data cache is already populated out-of-band."
        ),
    )
    parser.add_argument(
        "--laps",
        default=None,
        help="Lap range to simulate, e.g. 15-40 (default: all laps)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM synthesis and print MC scores only (no LM Studio required)",
    )
    parser.add_argument(
        "--provider",
        default=None,
        choices=["lmstudio", "openai"],
        help=(
            "LLM provider, overriding F1_LLM_PROVIDER from .env. "
            "Unset: use .env, falling back to 'lmstudio'."
        ),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.0,
        metavar="SECONDS",
        help=(
            "Pause between laps in seconds (default: 0.0, no pause). "
            "E.g. --interval 2.0 pauses 2 s after each lap row is printed."
        ),
    )
    parser.add_argument(
        "--radio-every",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Simulate a radio/RCM event every N laps to activate NLP agents "
            "(e.g. --radio-every 5). 0 = disabled (default). Suppressed when "
            "the real radio corpus loads successfully."
        ),
    )
    parser.add_argument(
        "--no-real-radios",
        action="store_true",
        help=(
            "Skip the static OpenF1 radio corpus and Whisper transcription. "
            "Falls back to the synthetic --radio-every generator. Useful for "
            "smoke tests on machines without the data tree or without GPU."
        ),
    )
    parser.add_argument(
        "--whisper-model",
        default="turbo",
        metavar="NAME",
        help=(
            "Whisper model name passed to RadioPipelineRunner (default: turbo). "
            "Smaller variants like 'base' or 'small' trade accuracy for speed."
        ),
    )
    parser.add_argument(
        "--rival",
        default=None,
        metavar="CODE",
        help=(
            "FIA three-letter code of a driver to track as rival (e.g. VER). "
            "Adds a Rival column and shows their position / compound / interval."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Print full per-lap tracebacks")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version()}",
    )
    args = parser.parse_args()

    lap_range = _parse_laps(args.laps, parser)
    from scripts.cli.pickers import _load_driver_data, max_lap_for_driver

    featured_path = Path(args.featured) if args.featured else None
    driver_data = _load_driver_data(_REPO_ROOT, args.gp_name, args.year, featured_path)
    if args.driver.upper() not in driver_data:
        parser.error(f"driver {args.driver.upper()} is not present at {args.gp_name}")

    raw_dir = Path(args.raw_dir) if args.raw_dir else None
    max_lap = max_lap_for_driver(_REPO_ROOT, args.gp_name, args.driver, args.year, raw_dir)
    if max_lap is None:
        parser.error(f"cannot read raw lap data for {args.gp_name}; check --raw-dir")
    if max_lap < 1:
        parser.error(f"driver {args.driver.upper()} is not present at {args.gp_name}")
    if lap_range is not None and lap_range[1] > max_lap:
        parser.error(f"this driver's data ends at lap {max_lap}")

    from scripts.run_simulation_cli import main as simulation_main

    sys.argv = [sys.argv[0], *_runner_arguments(args)]
    simulation_main()


if __name__ == "__main__":
    main()
