"""Entry point for the `f1-arcade` console script.

Data loading happens in the main thread before the Arcade window is created,
which is the only reliable way to avoid pyglet GL-context errors: every
`arcade.Text` we allocate inside panels needs a live context, and async
background loaders don't provide one. `main()` parses CLI args, loads the
session, builds the track geometry, and hands both to `F1ArcadeWindow`.
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


_GP_NAMES: dict[int, str] = {
    1: "Bahrain", 2: "SaudiArabia", 3: "Australia", 4: "Japan",
    5: "China", 6: "Miami", 7: "Monaco", 8: "Canada", 9: "Spain",
    10: "Austria", 11: "Britain", 12: "Hungary", 13: "Belgium",
    14: "Netherlands", 15: "Italy", 16: "Singapore", 17: "Mexico",
    18: "Brazil", 19: "LasVegas", 20: "AbuDhabi", 21: "Qatar",
    22: "USA", 23: "Monza",
}


def main() -> None:
    """Parse CLI arguments and route to the viewer (launcher ships in Phase 6)."""
    args = _parse_args()
    if args.viewer:
        _run_viewer(args)
    else:
        _run_launcher_stub()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="f1-arcade",
        description="F1 Strategy Manager - visual race replay.",
    )
    parser.add_argument("--viewer", action="store_true")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--round", type=int, default=3)
    parser.add_argument("--driver", type=str, default=None)
    parser.add_argument("--driver2", type=str, default=None)
    parser.add_argument("--team", type=str, default=None)
    parser.add_argument("--laps", type=str, default=None)
    parser.add_argument("--risk-tolerance", type=float, default=0.5)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--provider", choices=("lmstudio", "openai"), default="lmstudio")
    return parser.parse_args()


def _run_viewer(args: argparse.Namespace) -> None:
    """Load session, build track, open window. Every heavy step is logged."""
    import arcade

    from src.arcade.app import F1ArcadeWindow
    from src.arcade.data import SessionLoader
    from src.arcade.track import Track

    year = args.year
    round_num = args.round
    gp = _GP_NAMES.get(round_num, f"Round{round_num}")

    logger.info("Loading session: %d round %d (%s)", year, round_num, gp)
    loader = SessionLoader()
    session_data = loader.load(year, round_num, gp)
    logger.info(
        "Loaded: %d drivers, laps %d-%d, %d frames",
        len(session_data.frames_by_driver), session_data.min_lap_number,
        session_data.max_lap_number, session_data.total_frames,
    )

    ref_x, ref_y = session_data.ref_lap_xy
    track = Track(
        ref_x=ref_x,
        ref_y=ref_y,
        drs_flags=session_data.ref_lap_drs,
        rotation_deg=session_data.circuit_rotation_deg,
    )
    logger.info("Track geometry built (rotation %.2f deg)", session_data.circuit_rotation_deg)

    driver_main = args.driver or _pick_default_driver(session_data)
    driver_rival = args.driver2
    if driver_main not in session_data.frames_by_driver:
        logger.warning("Driver %s not in session; falling back", driver_main)
        driver_main = _pick_default_driver(session_data)
    if driver_rival and driver_rival not in session_data.frames_by_driver:
        logger.warning("Rival %s not in session; ignoring", driver_rival)
        driver_rival = None

    F1ArcadeWindow(
        session_data=session_data,
        track=track,
        driver_main=driver_main,
        driver_rival=driver_rival,
        year=year,
    )
    arcade.run()


def _pick_default_driver(session_data) -> str:
    """Prefer a finisher of the final lap; fall back to first driver otherwise."""
    codes = list(session_data.frames_by_driver.keys())
    if not codes:
        raise RuntimeError("Session has no drivers")
    for code in codes:
        frames = session_data.frames_by_driver[code]
        if frames and frames[-1].active:
            return code
    return codes[0]


def _run_launcher_stub() -> None:
    print(
        "Launcher not implemented yet. Use `f1-arcade --viewer` with CLI flags:\n"
        "  f1-arcade --viewer --year 2024 --round 3 --driver NOR --driver2 LEC",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
