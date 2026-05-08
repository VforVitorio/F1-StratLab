"""scripts/cli/runner.py

Subprocess helpers and mode-handler functions for the F1 CLI launcher.

Functions
---------
build_sim_cmd(race, driver, team, laps, provider, year, script_dir, rival) → list[str]
    Build the argv list for run_simulation_cli.py.

run_subprocess(cmd) → int
    Execute the simulation subprocess with the current terminal (real-time output).

run_single(races, repo_root, script_dir)
    Interactive wizard → single-driver simulation.

run_h2h(races, repo_root, script_dir)
    Interactive wizard → full sim for Driver 1, Driver 2 tracked as rival.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.panel import Panel
from rich.rule import Rule

from .pickers import (
    pick_driver,
    pick_laps,
    pick_provider,
    pick_race,
    pick_rival_code,
)
from .theme import F1_AMBER, F1_GREEN, F1_RED, F1_WHITE, console

# ─────────────────────────────────────────────────────────────────────────────
# Subprocess helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_sim_cmd(
    race: str,
    driver: str,
    team: str,
    laps: str | None,
    provider: str,
    year: int = 2025,
    script_dir: Path | None = None,
    rival: str | None = None,
    radio_every: int = 0,
) -> list[str]:
    """Return the argv list for run_simulation_cli.py with the given parameters."""
    if script_dir is None:
        script_dir = Path(__file__).resolve().parent.parent  # scripts/

    sim_script = str(script_dir / "run_simulation_cli.py")
    cmd = [sys.executable, sim_script, race, driver, team, "--year", str(year)]

    if provider == "no-llm":
        cmd.append("--no-llm")
    else:
        cmd.extend(["--provider", provider])

    if laps:
        cmd.extend(["--laps", laps])

    if rival:
        cmd.extend(["--rival", rival.upper()])

    if radio_every > 0:
        cmd.extend(["--radio-every", str(radio_every)])

    return cmd


def run_subprocess(cmd: list[str]) -> int:
    """Run a simulation subprocess inheriting the terminal (real-time Rich output).

    Passes PYTHONIOENCODING=utf-8 so box-drawing chars render correctly on
    Windows terminals regardless of the system code page.
    """
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    return subprocess.run(cmd, env=env).returncode


# ─────────────────────────────────────────────────────────────────────────────
# Mode handlers
# ─────────────────────────────────────────────────────────────────────────────


def run_single(races: list[str], repo_root: Path, script_dir: Path) -> None:
    """Collect params for one driver and delegate to run_simulation_cli.py."""
    race = pick_race(races)
    drv, team = pick_driver("Driver", repo_root)
    laps = pick_laps()
    provider = pick_provider()

    console.print()
    console.print(Rule(style=F1_RED))
    console.print()
    console.print(
        "  [dim]Initializing engine — NLP models loading, this may take a few seconds…[/dim]"
    )
    console.print()

    cmd = build_sim_cmd(
        race,
        drv,
        team,
        laps,
        provider,
        script_dir=script_dir,
    )
    run_subprocess(cmd)


def run_h2h(races: list[str], repo_root: Path, script_dir: Path) -> None:
    """Full sim for Driver 1; Driver 2 is tracked as a rival in the same run."""
    console.print()
    console.print(
        f"  [bold {F1_WHITE}]Head-to-Head setup[/bold {F1_WHITE}]  "
        f"[dim]full simulation for Driver 1 · Driver 2 tracked as rival[/dim]"
    )

    race = pick_race(races)
    drv1, tm1 = pick_driver("Driver 1  (full simulation)", repo_root)
    drv2 = pick_rival_code(repo_root)
    laps = pick_laps()
    provider = pick_provider()

    console.print()
    console.print(Rule(style=F1_RED))
    console.print()
    console.print(
        Panel(
            f"[bold {F1_RED}]{drv1}[/bold {F1_RED}]  [dim]{tm1}[/dim]  "
            f"[dim]tracking rival[/dim]  [bold {F1_AMBER}]{drv2}[/bold {F1_AMBER}]",
            border_style=F1_RED,
            expand=False,
            padding=(0, 2),
        )
    )
    console.print()
    console.print(
        "  [dim]Initializing engine — NLP models loading, this may take a few seconds…[/dim]"
    )
    console.print()

    cmd = build_sim_cmd(
        race,
        drv1,
        tm1,
        laps,
        provider,
        script_dir=script_dir,
        rival=drv2,
    )
    rc = run_subprocess(cmd)

    # ── Summary ───────────────────────────────────────────────────────────────
    ok = rc == 0
    status = (
        f"[{F1_GREEN}]Simulation completed successfully[/{F1_GREEN}]"
        if ok
        else f"[{F1_AMBER}]Completed with errors (rc={rc})[/{F1_AMBER}]"
    )
    console.print()
    console.print(
        Panel(
            f"[bold {F1_WHITE}]{drv1}[/bold {F1_WHITE}] tracking rival "
            f"[bold {F1_AMBER}]{drv2}[/bold {F1_AMBER}]  ·  "
            f"[dim]{race}[/dim]  ·  {status}",
            title="[bold]Head-to-Head complete[/bold]",
            border_style=F1_GREEN if ok else F1_AMBER,
            expand=False,
            padding=(0, 2),
        )
    )
