"""
F1 Strategy Manager — Interactive CLI Launcher

Usage
-----
    python scripts/f1_cli.py

Menu
----
    1  Single Driver   — lap-by-lap strategy for one driver
    2  Head-to-Head    — two drivers, same race, shown back-to-back
    3  Quit

All UI logic lives in scripts/cli/:
    theme.py    — colors, console, ASCII banner
    pickers.py  — Rich prompts (mode / race / driver / laps / provider)
    runner.py   — subprocess helpers + mode handlers
"""

from __future__ import annotations

import sys
import warnings
import logging as _logging
from pathlib import Path

# Ensure UTF-8 on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Silence noisy library output before any heavy imports
warnings.filterwarnings("ignore", message=".*builtin type.*__module__.*")
_logging.getLogger("transformers").setLevel(_logging.ERROR)
_logging.getLogger("setfit").setLevel(_logging.ERROR)
_logging.getLogger("sentence_transformers").setLevel(_logging.ERROR)
_logging.getLogger("torch").setLevel(_logging.ERROR)

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT  = next(
    (p for p in [_SCRIPT_DIR, *_SCRIPT_DIR.parents] if (p / ".git").exists()),
    _SCRIPT_DIR.parent,
)

# Add scripts/ to sys.path so `from cli.*` resolves correctly
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from dotenv import load_dotenv
    _env = _REPO_ROOT / ".env"
    if _env.exists():
        load_dotenv(_env)
except ImportError:
    pass

# ── CLI package imports ────────────────────────────────────────────────────────
from cli.theme   import F1_GRAY, F1_RED, console, make_banner
from cli.pickers import ask_again, discover_races, pick_mode
from cli.runner  import run_h2h, run_single

from rich.rule import Rule


# ─────────────────────────────────────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    console.print()
    console.print(make_banner())

    races = discover_races(_REPO_ROOT, year=2025)
    if not races:
        console.print(
            f"\n  [{F1_GRAY}]No races found in data/raw/2025/. "
            f"Run scripts/download_data.py first.[/{F1_GRAY}]\n"
        )
        return

    while True:
        mode = pick_mode()

        if mode == "quit":
            break
        elif mode == "single":
            run_single(races, _REPO_ROOT, _SCRIPT_DIR)
        elif mode == "h2h":
            run_h2h(races, _REPO_ROOT, _SCRIPT_DIR)

        if not ask_again():
            break

        console.print()
        console.print(Rule(style=F1_GRAY))
        console.print()
        console.print(make_banner())

    console.print()
    console.print(f"  [{F1_GRAY}]Goodbye. Chequered flag.[/{F1_GRAY}]")
    console.print()


if __name__ == "__main__":
    main()
