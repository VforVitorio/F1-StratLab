"""Immutable constants shared across the Arcade package.

Centralising window geometry, playback timing, backend URLs, and
filesystem paths here means the rest of the package can depend on a
single import site without re-reading environment variables or walking
the filesystem in hot paths. Palette dictionaries (compound, driver,
action) are added phase by phase as features require them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

SCREEN_WIDTH: Final[int] = 1280
SCREEN_HEIGHT: Final[int] = 720
WINDOW_TITLE: Final[str] = "F1 Strategy Manager — Race Replay"

FPS: Final[int] = 25
DT: Final[float] = 1.0 / FPS
PLAYBACK_SPEEDS: Final[tuple[float, ...]] = (
    0.1, 0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, 64.0, 128.0, 256.0,
)
DEFAULT_PLAYBACK_SPEED: Final[float] = 1.0

BACKEND_URL: Final[str] = os.environ.get("F1_BACKEND_URL", "http://localhost:8000")
SIMULATE_ENDPOINT: Final[str] = "/api/v1/strategy/simulate"
HEALTH_ENDPOINT: Final[str] = "/api/v1/health"


def _find_repo_root() -> Path:
    """Walk up from this file until a `.git` directory is located.

    Preferred over a hard-coded `parents[N]` index because it keeps
    working if the package is relocated within the repository.
    """
    current = Path(__file__).resolve().parent
    while not (current / ".git").exists():
        if current.parent == current:
            raise RuntimeError("Could not locate repo root (no .git ancestor found).")
        current = current.parent
    return current


REPO_ROOT: Final[Path] = _find_repo_root()
CACHE_DIR: Final[Path] = REPO_ROOT / "data" / "cache" / "arcade"
FASTF1_CACHE_DIR: Final[Path] = REPO_ROOT / "data" / "cache" / "fastf1"
