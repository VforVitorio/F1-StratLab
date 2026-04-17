"""Constants and theme palette for the Arcade race replay.

Centralises every magic number used across `data.py`, `track.py`, `overlays.py`
and `app.py` so the visual design can be tuned from one place. Values are
ported from the Tom Shaw f1-race-replay reference (cached audits in
`c:/tmp/arcade_analysis/`) with TFG-specific overrides flagged inline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

# --- Playback & timing ----------------------------------------------------
FPS: Final[int] = 25
DT: Final[float] = 1.0 / FPS
PLAYBACK_SPEEDS: Final[tuple[float, ...]] = (0.25, 0.5, 1.0, 2.0, 4.0, 8.0)
DEFAULT_SPEED_IDX: Final[int] = PLAYBACK_SPEEDS.index(1.0)
SEEK_RATE_MULTIPLIER: Final[float] = 3.0

# --- Window geometry ------------------------------------------------------
SCREEN_WIDTH: Final[int] = 1280
SCREEN_HEIGHT: Final[int] = 720
WINDOW_TITLE: Final[str] = "F1 Strategy Manager - Race Replay"

# --- Viewport margins (reserve UI space before fitting track) -------------
MARGIN_LEFT: Final[int] = 340
MARGIN_RIGHT: Final[int] = 260
MARGIN_BOTTOM: Final[int] = 90
MARGIN_TOP: Final[int] = 20
TRACK_PADDING: Final[float] = 0.05

# --- Weather panel --------------------------------------------------------
WEATHER_LEFT: Final[int] = 20
WEATHER_TOP_OFFSET: Final[int] = 90
WEATHER_WIDTH: Final[int] = 280
WEATHER_ROW_GAP: Final[int] = 22
WEATHER_ICON_SIZE: Final[int] = 16

# --- Driver info panel ----------------------------------------------------
DRIVER_BOX_WIDTH: Final[int] = 300
DRIVER_BOX_HEIGHT: Final[int] = 145
DRIVER_BOX_GAP: Final[int] = 10
DRIVER_HEADER_HEIGHT: Final[int] = 28
DRIVER_ROW_GAP: Final[int] = 19

# --- Leaderboard ----------------------------------------------------------
LEADERBOARD_WIDTH: Final[int] = 240
LEADERBOARD_RIGHT_MARGIN: Final[int] = 260
LEADERBOARD_ROW_HEIGHT: Final[int] = 22
LEADERBOARD_N_SLOTS: Final[int] = 22

# --- Progress bar ---------------------------------------------------------
PROGRESS_BAR_BOTTOM: Final[int] = 30
PROGRESS_BAR_HEIGHT: Final[int] = 24

# --- Controls legend ------------------------------------------------------
LEGEND_X: Final[int] = 20
LEGEND_BOTTOM: Final[int] = 60

# --- Theme palette (RGB tuples) ------------------------------------------
# Mirrors src/telemetry/frontend/app/styles.py so the Arcade replay and the
# Streamlit app read as the same product. The Streamlit file owns the
# canonical hexes; duplicated here (not imported) to keep src/arcade/
# dependency-free from the backend package.
BG_COLOR: Final[tuple[int, int, int]] = (18, 17, 39)           # #121127 PRIMARY_BG
CONTENT_BG: Final[tuple[int, int, int]] = (24, 22, 51)         # #181633 CONTENT_BG (panels)
SECONDARY_BG: Final[tuple[int, int, int]] = (30, 27, 75)       # #1e1b4b SECONDARY_BG
BORDER_COLOR: Final[tuple[int, int, int]] = (45, 45, 58)       # #2d2d3a BORDER
TEXT_PRIMARY: Final[tuple[int, int, int]] = (255, 255, 255)    # #ffffff
TEXT_SECONDARY: Final[tuple[int, int, int]] = (209, 213, 219)  # #d1d5db
TEXT_TERTIARY: Final[tuple[int, int, int]] = (156, 163, 175)   # #9ca3af
ACCENT: Final[tuple[int, int, int]] = (167, 139, 250)          # #a78bfa purple
SUCCESS: Final[tuple[int, int, int]] = (16, 185, 129)          # #10b981 emerald
WARNING: Final[tuple[int, int, int]] = (245, 158, 11)          # #f59e0b amber
DANGER: Final[tuple[int, int, int]] = (239, 68, 68)            # #ef4444 red
INFO: Final[tuple[int, int, int]] = (59, 130, 246)             # #3b82f6 blue

# --- Typography (arcade.Text font_name accepts a fallback tuple) ---------
FONT_BODY: Final[tuple[str, ...]] = ("Inter", "Segoe UI", "Arial")
FONT_TITLE: Final[tuple[str, ...]] = ("Exo 2", "Inter", "Segoe UI", "Arial")

# --- Track rendering ------------------------------------------------------
TRACK_EDGE_COLOR: Final[tuple[int, int, int]] = (150, 150, 150)
TRACK_EDGE_WIDTH: Final[int] = 4
TRACK_FILL_COLOR: Final[tuple[int, int, int]] = (40, 40, 44)
DRS_COLOR: Final[tuple[int, int, int]] = (0, 220, 0)
DRS_WIDTH: Final[int] = 5
FINISH_CHEQUER_SEGMENTS: Final[int] = 20
FINISH_CHEQUER_WIDTH: Final[int] = 6
TRACK_WIDTH_WORLD: Final[float] = 200.0
TRACK_INTERP_REF: Final[int] = 4000
TRACK_INTERP_EDGE: Final[int] = 2000

# --- Tyre compounds (FastF1 int codes) -----------------------------------
COMPOUND_COLORS: Final[dict[int, tuple[int, int, int]]] = {
    0: (230, 50, 50),     # SOFT
    1: (230, 200, 50),    # MEDIUM
    2: (230, 230, 230),   # HARD
    3: (60, 200, 60),     # INTERMEDIATE
    4: (60, 130, 230),    # WET
}
COMPOUND_LETTERS: Final[dict[int, str]] = {
    0: "S", 1: "M", 2: "H", 3: "I", 4: "W",
}
COMPOUND_NAMES: Final[dict[int, str]] = {
    0: "SOFT", 1: "MEDIUM", 2: "HARD", 3: "INTER", 4: "WET",
}

# --- Car rendering --------------------------------------------------------
CAR_RADIUS: Final[float] = 7.0
CAR_BORDER_WIDTH: Final[float] = 2.0
CAR_BORDER_COLOR: Final[tuple[int, int, int]] = (255, 255, 255)
CAR_LABEL_FONT_SIZE: Final[int] = 11

# --- Progress bar flag colors --------------------------------------------
FLAG_COLORS: Final[dict[str, tuple[int, int, int]]] = {
    "yellow_flag": WARNING,
    "red_flag": DANGER,
    "safety_car": WARNING,
    "vsc": (245, 158, 11),
    "dnf": DANGER,
    "progress_fill": ACCENT,
    "lap_marker": BORDER_COLOR,
    "background": CONTENT_BG,
    "playhead": TEXT_PRIMARY,
}

# --- Paths ----------------------------------------------------------------
REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FASTF1_CACHE_DIR: Final[Path] = REPO_ROOT / "data" / "cache" / "fastf1"
ARCADE_CACHE_DIR: Final[Path] = REPO_ROOT / "data" / "cache" / "arcade"
CACHE_VERSION: Final[str] = "v3"  # ref_lap_drs now sourced from quali fastest (f1_replay pattern)

# --- Multiprocessing pool -------------------------------------------------
# Serial by default — Windows spawn + pickling a loaded session across 8
# workers has hung in cold-cache runs. Flip to >1 once FastF1 is warm.
POOL_SIZE: Final[int] = 1
