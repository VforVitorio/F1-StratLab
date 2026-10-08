"""Lightweight validation and version entry point for the headless simulator."""

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
    start = int(match.group(1))
    end = int(match.group(2) or start)
    if end < start:
        parser.error("the last lap must be greater than or equal to the first")
    return start, end


def main() -> None:
    """Handle fast version/input checks, then delegate unchanged to the PMV runner."""
    parser = argparse.ArgumentParser(prog="f1-sim", add_help=False)
    parser.add_argument("gp_name", nargs="?")
    parser.add_argument("driver", nargs="?")
    parser.add_argument("team", nargs="?")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--laps")
    parser.add_argument("--version", action="store_true")
    args, _ = parser.parse_known_args()
    if args.version:
        print(f"f1-sim {package_version()}")
        return

    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        from scripts.run_simulation_cli import main as simulation_main

        simulation_main()
        return

    if not args.gp_name or not args.driver or not args.team:
        parser.error("gp_name, driver, and team are required")
    lap_range = _parse_laps(args.laps, parser)
    if lap_range is not None:
        from scripts.cli.pickers import max_lap_for_driver

        max_lap = max_lap_for_driver(_REPO_ROOT, args.gp_name, args.driver, args.year)
        if max_lap is not None and lap_range[1] > max_lap:
            parser.error(f"this driver's data ends at lap {max_lap}")

    from scripts.run_simulation_cli import main as simulation_main

    simulation_main()


if __name__ == "__main__":
    main()
