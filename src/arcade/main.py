"""Entry point for the `f1-arcade` console script.

Parses command-line arguments and dispatches to either the PySide6
launcher (interactive form for year, round, driver selection, ...) or
directly into the Arcade viewer when `--viewer` is supplied with the
race parameters pre-filled. The launcher is implemented in Phase 6;
earlier phases invoke the viewer flag directly for development.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    """Parse CLI arguments and route to the launcher or the viewer."""
    args = _parse_args()
    if args.viewer:
        _run_viewer(args)
    else:
        _run_launcher()


def _parse_args() -> argparse.Namespace:
    """Define every flag that the viewer or launcher consumes.

    The argument set mirrors the backend `SimulateRequest` schema so that
    both paths (viewer-direct and launcher-form) produce compatible
    payloads when the SSE stream is opened in Phase 3.
    """
    parser = argparse.ArgumentParser(
        prog="f1-arcade",
        description="F1 Strategy Manager — visual race replay with strategic overlays.",
    )
    parser.add_argument(
        "--viewer",
        action="store_true",
        help="Skip the launcher and open the Arcade window directly with the flags below.",
    )
    parser.add_argument("--year", type=int, default=None, help="Season year, e.g. 2024.")
    parser.add_argument("--round", type=int, default=None, help="Round number within the season.")
    parser.add_argument("--driver", type=str, default=None, help="Main driver code (3-letter).")
    parser.add_argument("--driver2", type=str, default=None, help="Rival driver code (optional).")
    parser.add_argument("--team", type=str, default=None, help="Main driver's team name.")
    parser.add_argument("--laps", type=str, default=None, help="Lap range as 'start-end'.")
    parser.add_argument(
        "--risk-tolerance",
        type=float,
        default=0.5,
        help="Strategic risk tolerance in [0.0, 1.0]. Default 0.5.",
    )
    parser.add_argument("--no-llm", action="store_true", help="Use guardrail-only no-LLM path.")
    parser.add_argument(
        "--provider",
        choices=("lmstudio", "openai"),
        default="lmstudio",
        help="LLM provider for agent synthesis. Default lmstudio.",
    )
    return parser.parse_args()


def _run_viewer(args: argparse.Namespace) -> None:
    """Open the Arcade window with the provided parameters and run the event loop."""
    import arcade

    from src.arcade.app import F1ArcadeWindow

    F1ArcadeWindow(args=args)
    arcade.run()


def _run_launcher() -> None:
    """Open the PySide6 launcher — implemented in Phase 6."""
    print(
        "Launcher not implemented yet (Phase 6). "
        "Use `f1-arcade --viewer` to open the viewer directly.",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
