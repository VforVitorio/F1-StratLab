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
import contextlib
import io
import json
import os
import sys
import time
import traceback
import warnings
from pathlib import Path
from typing import Any

# Suppress stray SWIG DeprecationWarnings from C-extension imports.
warnings.filterwarnings("ignore", message=".*builtin type.*__module__.*")

# Suppress verbose logging from transformers / setfit / sentence-transformers.
# These libraries log LOAD REPORT tables via Python logging when loading
# state-dicts with mismatched keys (expected behaviour for fine-tuned heads).
import logging as _logging
_logging.getLogger("transformers").setLevel(_logging.ERROR)
_logging.getLogger("setfit").setLevel(_logging.ERROR)
_logging.getLogger("sentence_transformers").setLevel(_logging.ERROR)
_logging.getLogger("torch").setLevel(_logging.ERROR)

import pandas as pd
from rich.box import ROUNDED
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
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
# Imports — NLP models load eagerly when strategy_orchestrator imports radio_agent
# (RadioAgentCFG.__post_init__ runs at module level, loading 3 NLP models).
# Suppress C-level fd 1/2 during import so terminal stays clean.
# ---------------------------------------------------------------------------
try:
    from src.simulation.replay_engine import RaceReplayEngine
except ImportError as e:
    sys.exit(f"[FATAL] Cannot import simulation engine: {e}")

# Inline fd suppression — cannot use _devnull_fds() here because it's defined later.
# We redirect both:
#   • C-level fds 1/2 — for any C-extension that writes directly to the OS fd
#   • Python-level sys.stdout/stderr — for TextIOWrapper-buffered output that
#     would otherwise be flushed to the terminal after fds are restored.
_dn = os.open(os.devnull, os.O_WRONLY)
_fd1_save, _fd2_save = os.dup(1), os.dup(2)
os.dup2(_dn, 1); os.dup2(_dn, 2)
_py_out_save, _py_err_save = sys.stdout, sys.stderr
sys.stdout = sys.stderr = io.StringIO()
os.environ["TQDM_DISABLE"] = "1"
_import_err: str | None = None
try:
    from src.agents.strategy_orchestrator import RaceState, run_strategy_orchestrator_from_state
except ImportError as _e:
    _import_err = str(_e)
finally:
    sys.stdout, sys.stderr = _py_out_save, _py_err_save
    os.dup2(_fd1_save, 1); os.dup2(_fd2_save, 2)
    os.close(_fd1_save); os.close(_fd2_save); os.close(_dn)
    os.environ.pop("TQDM_DISABLE", None)
if _import_err:
    sys.exit(f"[FATAL] Cannot import strategy orchestrator: {_import_err}")


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

# ── Driver / team colours (mirrored from src/telemetry/backend/core/driver_colors.py) ──
# No import to avoid heavy telemetry import chain at CLI startup.
_DRIVER_COLORS: dict[str, str] = {
    "VER": "#0600EF", "PER": "#3671C6",          # Red Bull
    "LEC": "#DC0000", "SAI": "#FF6B6B",           # Ferrari
    "HAM": "#C0C0C0", "RUS": "#E8E8E8",           # Mercedes
    "NOR": "#FF8700", "PIA": "#FFB347",           # McLaren
    "ALO": "#00665F", "STR": "#2BA572",           # Aston Martin
    "GAS": "#FF87BC", "OCO": "#FFC0E3",           # Alpine
    "ALB": "#041E42", "SAR": "#1B4F91", "COL": "#2E6DB5",  # Williams
    "TSU": "#FFFFFF", "RIC": "#F5F5F5", "LAW": "#DCDCDC",  # RB
    "BOT": "#52E252", "ZHO": "#90EE90",           # Kick Sauber
    "MAG": "#787878", "HUL": "#A8A8A8", "BEA": "#959595",  # Haas
    "DOO": "#FFB0D3",                             # Reserve
}
_DEFAULT_DRIVER_COLOR = "#A259F7"

def _drv_color(code: str) -> str:
    """Return the hex colour for *code*, or a purple fallback."""
    return _DRIVER_COLORS.get(code.upper(), _DEFAULT_DRIVER_COLOR)

# ── Simulated radio message pool ──────────────────────────────────────────────
import random as _random

_RADIO_POOL: dict[str, list[str]] = {
    "box": [
        "Box box box. Tyres are completely gone.",
        "Box this lap, we're losing too much time.",
        "Come in, come in. The window is open.",
    ],
    "push": [
        "Push now, push push push!",
        "Go go go, gap is closing!",
        "Lap time, lap time! Everything you've got.",
    ],
    "manage": [
        "Tyres, tyres. Watch the degradation.",
        "Understood, just manage to the end.",
        "Keep it consistent, no heroics.",
    ],
    "info": [
        "Copy that, understood.",
        "What's the gap to the car behind?",
        "Careful of traffic in the last sector.",
        "Box? Box? Negative, stay out.",
    ],
    "problem": [
        "I've got a vibration on the rear-left.",
        "Something feels wrong with the balance.",
        "Flat spot, I have a flat spot!",
    ],
}

_RCM_POOL: list[dict] = [
    {"message": "TRACK LIMITS AT TURN 12 — NOTED",  "flag": "YELLOW",     "category": "Track Limits", "scope": "Track"},
    {"message": "YELLOW FLAG SECTOR 2",              "flag": "YELLOW",     "category": "Flag",         "scope": "Sector"},
    {"message": "VSC ENDING — SAFETY CAR IN THIS LAP","flag": "SAFETY CAR","category": "SafetyCar",    "scope": "Track"},
    {"message": "DRS ENABLED",                       "flag": "GREEN",      "category": "DRS",          "scope": "Track"},
    {"message": "INCIDENT UNDER INVESTIGATION",      "flag": "YELLOW",     "category": "Other",        "scope": "Driver"},
]


def _generate_radio_event(
    lap_num: int,
    driver:     str,
    compound:   str,
    tyre_life:  int,
    position:   int,
    gap_ahead:  float,
) -> dict:
    """Return a context-aware simulated radio message dict."""
    if compound in ("SOFT", "MEDIUM") and tyre_life > 22:
        intent = "box"
    elif gap_ahead < 1.0 and gap_ahead > 0:
        intent = "push"
    elif position == 1:
        intent = "manage"
    elif _random.random() < 0.15:
        intent = "problem"
    else:
        intent = _random.choice(["info", "manage"])
    return {
        "driver":    driver,
        "lap":       lap_num,
        "text":      _random.choice(_RADIO_POOL[intent]),
        "timestamp": None,
    }


def _generate_rcm_event(lap_num: int) -> dict | None:
    """Return a random RCM event (30 % chance when called) or None."""
    if _random.random() > 0.3:
        return None
    evt = dict(_random.choice(_RCM_POOL))
    evt["lap"]           = lap_num
    evt["racing_number"] = None
    return evt


def _score_float(v: Any) -> float:
    """Extract a scalar score from an MC simulation result entry.

    _run_mc_simulation returns {scenario: {"E": float, "P10": float, "P90": float,
    "score": float}}. When scenario_scores holds these inner dicts (full LLM path),
    we extract the "score" key. When it holds plain floats (no-llm path), we cast
    directly.
    """
    if isinstance(v, dict):
        return float(v.get("score", 0.0))
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


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


@contextlib.contextmanager
def _devnull_fds():
    """Redirect C-level stdout (fd 1) and stderr (fd 2) to os.devnull.

    contextlib.redirect_stdout/stderr only intercept Python-level sys.stdout/err.
    MLX weight-loading and tqdm write to the underlying C file descriptors
    directly (bypassing the Python layer), so os.dup2 is required for full
    suppression on all platforms including Windows.
    """
    import warnings
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved = {1: os.dup(1), 2: os.dup(2)}
    try:
        os.dup2(devnull_fd, 1)
        os.dup2(devnull_fd, 2)
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()), \
             warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        for fd, saved_fd in saved.items():
            os.dup2(saved_fd, fd)
            os.close(saved_fd)
        os.close(devnull_fd)


# ---------------------------------------------------------------------------
# LLM-unavailable detection — shared by _probe_core_agents and _run_no_llm
# ---------------------------------------------------------------------------

# Exception type-name fragments that indicate the LLM backend is unreachable
# or misconfigured. Matched via substring on type(exc).__name__. Covers both
# openai-python errors (BadRequestError, APIConnectionError, NotFoundError,
# AuthenticationError, APIStatusError, InternalServerError, RateLimitError,
# ServiceUnavailableError) and raw httpx/urllib failures (ConnectTimeout,
# RemoteDisconnected, etc.).
_LLM_ERR_TYPES = (
    "Connection", "APIConnection", "OpenAI", "HTTP", "Timeout",
    "RemoteDisconnected", "BadRequest", "NotFound", "Authentication",
    "APIError", "APIStatusError", "RateLimit", "InternalServerError",
    "ServiceUnavailable", "PermissionDenied",
)

# Substrings that reliably indicate "LLM backend alive but unusable" — used
# as a fallback when type name alone is ambiguous (e.g. generic OSError).
# "No models loaded" is the exact LM Studio message when the developer forgot
# to `lms load` a model; "model_not_found" covers OpenAI 404s.
_LLM_ERR_MSGS = (
    "Connection error", "connect ECONNREFUSED", "No models loaded",
    "model_not_found", "invalid_api_key", "Could not connect",
    "ENOTFOUND", "getaddrinfo failed",
)


def _is_llm_unavailable(exc: Exception) -> bool:
    """Return True when the exception indicates the LLM backend is unusable.

    Used by --no-llm mode and the LLM-mode probe layer to decide whether to
    swap an agent output for a stub. Errors unrelated to LLM connectivity
    (ML model bugs, bad lap_state, missing features) must NOT match — those
    should propagate up to the main try/except so they land in the error row
    and alert the user to a real problem.

    Matches on both the exception type name (substring) and the first ~300
    chars of the exception message. Intentionally broad to handle LM Studio
    "No models loaded" (BadRequestError), OpenAI rate limits, and plain
    socket failures uniformly.
    """
    tn  = type(exc).__name__
    msg = str(exc)[:300]
    return any(k in tn  for k in _LLM_ERR_TYPES) or \
           any(k in msg for k in _LLM_ERR_MSGS)


def _prewarm_agents(no_llm: bool) -> None:
    """Initialise all agent singletons before the Live loop with all output suppressed.

    Each agent module holds a lazy module-level singleton (_default_*_agent).
    Pre-initialising them here:
      1. Moves model-loading latency out of the first lap — every lap runs at
         the same speed from lap 1 onwards.
      2. Eliminates the ThreadPoolExecutor race condition on first call (two
         threads trying to initialise the same singleton simultaneously).
      3. Suppresses tqdm progress bars and NLP weight LOAD REPORTs at C level.

    LangGraph ReAct agents are NOT pre-warmed — they need a live LLM connection.
    """
    _old_tqdm = os.environ.get("TQDM_DISABLE")
    os.environ["TQDM_DISABLE"] = "1"
    try:
        with _devnull_fds():
            from src.agents.radio_agent          import CFG as _r          # noqa: F401
            from src.agents.pace_agent           import _get_default_pace_agent
            from src.agents.race_situation_agent import _get_default_situation_agent
            from src.agents.pit_strategy_agent   import _get_default_pit_agent
            from src.agents.tire_agent           import _get_default_tire_agent
            _get_default_pace_agent()
            _get_default_situation_agent()
            _get_default_pit_agent()
            _get_default_tire_agent()
    except Exception:
        pass  # best-effort; actual errors surface during the run loop
    finally:
        if _old_tqdm is None:
            os.environ.pop("TQDM_DISABLE", None)
        else:
            os.environ["TQDM_DISABLE"] = _old_tqdm


def _probe_core_agents(
    race_state: "RaceState",
    lap_state:  dict,
    laps_df:    "pd.DataFrame",
):
    """Run pace + tire + situation + radio agents and return their outputs.

    Used in LLM mode to populate the detail panel without waiting for the
    full orchestrator. All four always-on agents are probed (pit and RAG
    stay unprobed: both are LLM-backed internally, so they would just hit
    the LLM twice per lap). Returns a 4-tuple (pace, tire, sit, radio) —
    any element may be a stub on error.
    """
    from src.agents.pace_agent           import run_pace_agent_from_state, PaceOutput
    from src.agents.tire_agent           import run_tire_agent_from_state, TireOutput
    from src.agents.race_situation_agent import (
        run_race_situation_agent_from_state, RaceSituationOutput,
    )
    from src.agents.radio_agent          import run_radio_agent_from_state, RadioOutput

    def _safe(fn, *args, stub):
        try:
            return fn(*args)
        except Exception as exc:
            if _is_llm_unavailable(exc):
                return stub
            raise

    pace_stub = PaceOutput(
        lap_time_pred=90.0, delta_vs_prev=0.0, delta_vs_median=0.0,
        ci_p10=88.0, ci_p90=92.0, reasoning="[probe]",
    )
    tire_stub = TireOutput(
        compound=race_state.compound, current_tyre_life=race_state.tyre_life,
        deg_rate=0.05, laps_to_cliff_p10=20.0, laps_to_cliff_p50=25.0,
        laps_to_cliff_p90=30.0, gp_name="", reasoning="[probe]",
    )
    sit_stub = RaceSituationOutput(
        overtake_prob=0.1, sc_prob_3lap=0.05, reasoning="[probe]",
    )
    radio_stub = RadioOutput(
        radio_events=[], rcm_events=[], alerts=[],
        reasoning="[probe]", corrections=[],
    )

    pace_out = _safe(run_pace_agent_from_state, lap_state, stub=pace_stub)
    tire_out = _safe(run_tire_agent_from_state, lap_state, laps_df, stub=tire_stub)
    sit_out  = _safe(run_race_situation_agent_from_state, lap_state, laps_df, stub=sit_stub)

    # Radio probe — build a lap_state shim with the current race_state
    # radio/RCM buffers so the NLP pipeline sees whatever the wizard-level
    # --radio-every generator pushed in this lap. Without the shim it would
    # always see an empty buffer and render idle.
    radio_ls = {
        **lap_state,
        "lap":        race_state.lap,
        "radio_msgs": list(race_state.radio_msgs),
        "rcm_events": list(race_state.rcm_events),
    }
    radio_out = _safe(run_radio_agent_from_state, radio_ls, laps_df, stub=radio_stub)

    return pace_out, tire_out, sit_out, radio_out


def _make_table(has_rival: bool = False) -> Table:
    """Build and return the Rich Table skeleton (no rows yet).

    When *has_rival* is True an extra "Rival" column is inserted after
    "Gap Fwd" showing the tracked driver's position / compound / interval.
    """
    table = Table(
        box=ROUNDED,
        show_lines=True,
        show_header=True,
        header_style="bold white",
        expand=False,
    )
    table.add_column("Lap",       justify="right",  style="dim",    width=4)
    table.add_column("Tyre",      justify="left",                   width=8)
    table.add_column("Age",       justify="right",  style="dim",    width=4)
    table.add_column("Pos",       justify="right",  style="dim",    width=4)
    table.add_column("Lap (s)",   justify="right",                  width=8)
    table.add_column("Gap Fwd",   justify="right",  style="dim",    width=7)
    if has_rival:
        table.add_column("Rival",  justify="left",                  width=15)
    table.add_column("Decision",  justify="left",                   width=10)
    table.add_column("Conf",      justify="right",                  width=5)
    table.add_column("Stay",      justify="right",  style="green",  width=6)
    table.add_column("Pit",       justify="right",  style="red",    width=6)
    table.add_column("Ucut",      justify="right",  style="yellow", width=6)
    table.add_column("Ocut",      justify="right",  style="yellow", width=6)
    table.add_column("Reasoning",                                   min_width=40, max_width=70)
    return table


# ── Sub-agent inference panel ──────────────────────────────────────────────────
#
# Replaces the v1 single-line detail Text with a stacked two-section Panel:
#   • Inference section — one row per sub-agent (N25..N29) showing the raw
#     numeric outputs of each ML model. Always rendered when any sub-agent
#     output is available.
#   • Execution plan section — the StrategyRecommendation v2 fields filled by
#     the LLM (pit plan, pace mode, risk posture, contingencies, key risks).
#     Only rendered in LLM mode where those fields exist.
# The panel is returned as a Rich Panel so the main Live Group can stack it
# under the history table without any manual spacing logic.

# ── Design tokens — F1 pit-wall palette + TUI glyph convention ───────────────
# Research distilled from btop / k9s / lazygit (solid rendering on dark
# terminals) combined with F1 canonical colour semantics:
#   purple  = fastest, green = personal best / OK, yellow = watch, red = alert.
# Purple is reserved for the live table (fastest-lap highlight), the panel
# uses green/yellow/red + neutral greys so status is readable at a glance
# without competing with the table colouring.
COL_OK       = "green3"
COL_WATCH    = "gold1"
COL_ALERT    = "red3"
COL_LABEL    = "grey70"
COL_DIM      = "grey50"
COL_HEADLINE = "bright_white"

# Dot-style glyphs — one column wide, render identically on Windows Terminal,
# iTerm2, and kitty. ● for filled states, ◐ for the "watch" half-state, ○ for
# idle/no-op. Putting the glyph in its own column lets the eye scan the status
# column first and only drill into labels/headlines when something is hot.
GLYPH_OK    = "●"
GLYPH_WATCH = "◐"
GLYPH_ALERT = "●"
GLYPH_IDLE  = "○"

# Friendly short names for conditional sub-agents — used in the panel subtitle
# (and nowhere else now that the Routing row is gone).
_AGENT_DISPLAY: dict[str, str] = {
    "N25": "pace",
    "N26": "tire",
    "N27": "situation",
    "N28": "pit",
    "N29": "radio",
    "N30": "rag",
}


def _mini_grid() -> Table:
    """Return a borderless 4-column grid for one inference or plan row.

    Columns (fixed widths so every row lines up perfectly):

    * ``glyph``    — single-char status dot (●/◐/○), coloured green/amber/red.
    * ``label``    — short agent or section name ("Pace", "Tire", "Pit plan").
    * ``headline`` — the single most important number for that row, rendered
      in bright white so the eye lands on it first.
    * ``context``  — secondary details in dim grey. Free-form; may contain
      multi-span ``Text`` so individual tokens keep their own colouring.

    The 4-column layout is the key UX change from the v1 two-column label/value
    table: the dedicated glyph column turns each row into a visual leader that
    can be scanned top-to-bottom without reading any text.
    """
    t = Table.grid(padding=(0, 1), expand=False)
    t.add_column("glyph",    width=1,  justify="center")
    t.add_column("label",    width=10, justify="left",  no_wrap=True)
    t.add_column("headline", width=24, justify="left",  no_wrap=True)
    t.add_column("context",  justify="left",  no_wrap=False)
    return t


def _glyph_for(status: str) -> tuple[str, str]:
    """Return a (char, colour) tuple for a status leader column.

    Collapses the various per-agent status vocabularies (TireOutput
    warning_level, RaceSituationOutput threat_level, plus free-form strings
    like ``"ok"``/``"watch"``/``"alert"``) onto four shared states so every
    row uses identical glyphs. Unknown strings fall through to the idle
    (empty-circle) state so mis-typed callers render harmlessly instead of
    masquerading as OK.
    """
    s = (status or "").upper()
    if s in ("PIT_SOON", "HIGH", "ALERT"):
        return GLYPH_ALERT, COL_ALERT
    if s in ("MONITOR",  "MEDIUM", "WATCH"):
        return GLYPH_WATCH, COL_WATCH
    if s in ("OK", "LOW", "GOOD"):
        return GLYPH_OK, COL_OK
    return GLYPH_IDLE, COL_DIM


# ── Row helpers ──────────────────────────────────────────────────────────────
#
# Each helper appends ONE row to the 4-column inference grid. All six agents
# (pace / tire / situation / pit / radio / rag) are rendered every lap —
# conditional agents that the MoE layer did not activate still appear as a
# dimmed "idle" row so the viewer can see the full roster at a glance and
# notice the transition the moment an agent lights up.
#
# Idle rows share a common visual language: empty-circle glyph (○) in
# COL_DIM, label + headline + context all rendered in COL_DIM, and the
# context explains what *triggers* the agent so the viewer learns the
# activation rules by watching the panel.

def _pace_status(delta_vs_prev: float) -> str:
    """Bucket a Δprev lap-time delta onto the shared ok/watch/alert vocab.

    Green when the predicted lap is at or faster than the previous actual,
    amber for small losses (0 – 0.25 s — normal degradation within a stint),
    red for anything bigger (flat-spot, lift-and-coast, traffic). Loose by
    design — the headline already carries the precise delta, the glyph just
    surfaces the trend for a top-to-bottom scan of the panel.
    """
    if delta_vs_prev <= 0.0:
        return "OK"
    if delta_vs_prev <= 0.25:
        return "MONITOR"
    return "PIT_SOON"          # reuse the alert bucket (red glyph)


def _idle_row(tbl: Table, label: str, hint: str) -> None:
    """Append a dimmed 'idle' row for an agent that did not activate this lap.

    Used for conditional agents (Pit, RAG) when the MoE routing layer chose
    not to run them. The hint explains the activation rule so the viewer
    understands *why* the agent is dark — e.g. "triggers on cliff pressure
    or radio problem". Rendered 100 % in COL_DIM to visually recede behind
    the active rows above/below it.
    """
    tbl.add_row(
        Text(GLYPH_IDLE, style=COL_DIM),
        Text(label,      style=COL_DIM),
        Text("idle",     style=COL_DIM),
        Text(hint,       style=COL_DIM),
    )


def _add_pace_row(tbl: Table, pace_out) -> None:
    """Append the Pace row to an inference grid.

    Headline shifts to the *expected delta vs previous lap* — that is the
    number a strategist reads first ("am I getting faster or slower?"). The
    absolute predicted lap time moves into the context column alongside the
    delta vs session median and a compact ±CI half-range. Falls through to
    an idle row when lap_time_pred is missing (partial stub from a failed
    connection) so the row is still visible.
    """
    pred = getattr(pace_out, "lap_time_pred", None)
    if pred is None:
        _idle_row(tbl, "Pace", "no prediction — stub")
        return

    dv  = getattr(pace_out, "delta_vs_prev",   0.0)
    dm  = getattr(pace_out, "delta_vs_median", 0.0)
    p10 = getattr(pace_out, "ci_p10",          0.0)
    p90 = getattr(pace_out, "ci_p90",          0.0)
    ci_half = (p90 - p10) / 2.0

    glyph, g_col = _glyph_for(_pace_status(dv))

    # Headline — delta vs previous lap, coloured green (faster) / red (slower)
    headline = Text()
    headline.append(
        f"Δnext {'+' if dv >= 0 else ''}{dv:.3f}s",
        style=f"bold {COL_OK if dv <= 0 else COL_ALERT}",
    )

    # Context — absolute prediction + vs-median + ±CI half-range
    ctx = Text()
    ctx.append(f"pred {pred:.2f}s",                     style=COL_DIM)
    ctx.append(f"  vs median {'+' if dm >= 0 else ''}{dm:.2f}s", style=COL_DIM)
    ctx.append(f"  ±{ci_half:.2f}s",                    style=COL_DIM)

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("Pace", style=COL_LABEL),
        headline,
        ctx,
    )


def _add_tire_row(tbl: Table, tire_out) -> None:
    """Append the Tire row to an inference grid.

    Headline is now phrased as "cliff in ~N laps" where N is the MC-Dropout
    P50 — remaining laps is the natural frame (not an absolute lap number).
    Context carries the P10/P90 uncertainty band as "range A–B laps", the
    degradation rate, and the warning-level badge colour-coded via the
    shared glyph palette.
    """
    deg = getattr(tire_out, "deg_rate",          None)
    p10 = getattr(tire_out, "laps_to_cliff_p10", None)
    p50 = getattr(tire_out, "laps_to_cliff_p50", None)
    p90 = getattr(tire_out, "laps_to_cliff_p90", None)
    wl  = getattr(tire_out, "warning_level",     "OK")

    if p50 is None:
        _idle_row(tbl, "Tire", "no prediction — stub")
        return

    glyph, g_col = _glyph_for(wl)
    headline = Text(f"cliff in ~{int(p50)} laps", style=f"bold {COL_HEADLINE}")

    ctx = Text()
    if p10 is not None and p90 is not None:
        ctx.append(f"range {int(p10)}–{int(p90)} laps", style=COL_DIM)
    if deg is not None:
        ctx.append(f"  deg {deg:.3f}s/lap", style=COL_DIM)
    ctx.append(f"  {wl}", style=g_col)

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("Tire", style=COL_LABEL),
        headline,
        ctx,
    )


def _add_situation_row(tbl: Table, sit_out) -> None:
    """Append the Situation row to an inference grid.

    Headline is the derived threat level (LOW/MEDIUM/HIGH) coloured via the
    shared palette — that single word summarises everything. Context spells
    out the two raw probabilities with their full English names ("overtake"
    and "safety car") to kill the OT/SC jargon that made the v1 row
    unreadable at first glance.
    """
    ot = float(getattr(sit_out, "overtake_prob", 0.0)) * 100
    sc = float(getattr(sit_out, "sc_prob_3lap",  0.0)) * 100
    th = getattr(sit_out, "threat_level", "LOW")

    glyph, g_col = _glyph_for(th)
    headline = Text(f"threat {th}", style=f"bold {g_col}")

    ctx = Text()
    ctx.append(f"overtake {ot:.0f}%",                style=COL_DIM)
    ctx.append(
        f"  safety car {sc:.0f}%",
        style=COL_WATCH if sc > 15 else COL_DIM,
    )

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("Situation", style=COL_LABEL),
        headline,
        ctx,
    )


def _add_pit_row(tbl: Table, pit_out) -> None:
    """Append the Pit row to an inference grid (conditional agent N28).

    When the MoE routing layer did not activate N28 the row is rendered as
    a dimmed idle leader so the viewer can still see the agent exists —
    previously the entire row was skipped and the pipeline felt smaller
    than it really is. When active, headline is "pit P50s → COMPOUND" and
    the context carries the P05/P95 duration range plus undercut.
    """
    if pit_out is None:
        _idle_row(tbl, "Pit", "triggers on cliff pressure or problem radio")
        return

    p05 = getattr(pit_out, "stop_duration_p05",       None)
    p50 = getattr(pit_out, "stop_duration_p50",       None)
    p95 = getattr(pit_out, "stop_duration_p95",       None)
    rec = getattr(pit_out, "compound_recommendation", None)
    up  = getattr(pit_out, "undercut_prob",           None)
    ut  = getattr(pit_out, "undercut_target",         None)

    glyph, g_col = _glyph_for("WATCH")

    headline = Text()
    if p50 is not None:
        headline.append(f"pit {p50:.2f}s", style=f"bold {COL_HEADLINE}")
    if rec:
        if p50 is not None:
            headline.append("  ", style=COL_DIM)
        headline.append(f"→ {rec}", style=f"bold {COL_WATCH}")
    if p50 is None and not rec:
        headline.append("—", style=f"bold {COL_HEADLINE}")

    ctx = Text()
    if p05 is not None and p95 is not None:
        ctx.append(f"range {p05:.2f}–{p95:.2f}s", style=COL_DIM)
    if up is not None:
        if ctx.plain:
            ctx.append("  ", style=COL_DIM)
        ctx.append(f"undercut {up * 100:.0f}%", style=COL_DIM)
        if ut:
            ctx.append(f" → {ut}", style=COL_WATCH)

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("Pit", style=COL_LABEL),
        headline,
        ctx,
    )


def _add_radio_row(tbl: Table, radio_out) -> None:
    """Append the Radio row to an inference grid.

    Headline shifts meaning based on alerts: "quiet" (green) when the NLP
    pipeline found nothing of interest, or a compact intent list (amber)
    when one or more alerts fired. Radio/RCM event counts stay in the
    context column so the viewer can tell "no traffic at all" apart from
    "traffic but benign".
    """
    if radio_out is None:
        _idle_row(tbl, "Radio", "no radio/rcm pipeline output")
        return

    n_r   = len(getattr(radio_out, "radio_events", []) or [])
    n_rcm = len(getattr(radio_out, "rcm_events",   []) or [])
    alrts = getattr(radio_out, "alerts", []) or []

    if alrts:
        parts: list[str] = []
        for a in alrts[:3]:
            if isinstance(a, dict):
                parts.append(a.get("intent") or a.get("type") or "?")
            else:
                parts.append(str(a))
        headline = Text(" · ".join(parts), style=f"bold {COL_WATCH}")
        glyph, g_col = _glyph_for("WATCH")
    elif n_r == 0 and n_rcm == 0:
        headline = Text("quiet", style=f"bold {COL_HEADLINE}")
        glyph, g_col = _glyph_for("OK")
    else:
        headline = Text("no alerts", style=f"bold {COL_HEADLINE}")
        glyph, g_col = _glyph_for("OK")

    ctx = Text(f"{n_r} radios · {n_rcm} rcm", style=COL_DIM)

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("Radio", style=COL_LABEL),
        headline,
        ctx,
    )


def _add_rag_row(tbl: Table, rag_text: str) -> None:
    """Append the RAG row to an inference grid (conditional agent N30).

    Idle when the MoE routing layer did not trigger a regulation lookup
    (most laps: no SC pressure and no rule-based question this lap). When
    active, headline is "regulation loaded" + a compact preview of the
    retrieved passage. The dim idle leader makes the agent's existence
    visible at all times even though it rarely runs.
    """
    if not rag_text:
        _idle_row(tbl, "RAG", "triggers on SC >30% or rule query")
        return

    preview = rag_text.strip().split("\n", 1)[0][:60]
    glyph, g_col = _glyph_for("OK")
    headline = Text("regulation loaded", style=f"bold {COL_HEADLINE}")
    ctx = Text(preview or "—", style=COL_DIM)

    tbl.add_row(
        Text(glyph, style=g_col),
        Text("RAG", style=COL_LABEL),
        headline,
        ctx,
    )


def _plan_row(
    tbl:      Table,
    label:    str,
    headline: Text,
    context:  Text,
    status:   str = "IDLE",
) -> None:
    """Append one row to the execution-plan grid using the shared layout.

    Thin wrapper so every plan row goes through the same 4-cell emit as the
    inference rows above. The ``status`` parameter drives the leader glyph
    and defaults to IDLE so informational rows (pit plan, stint end) render
    with the empty-circle glyph and don't compete with the truly-red signals
    from contingencies or key-risks rows.
    """
    glyph, g_col = _glyph_for(status)
    tbl.add_row(
        Text(glyph, style=g_col),
        Text(label, style=COL_LABEL),
        headline,
        context,
    )


def _build_plan_table(strategy_rec) -> Table | None:
    """Build the execution-plan sub-grid from a StrategyRecommendation v2.

    Reads every optional field the LLM filled in the new schema (pit plan,
    pace mode, risk posture, contingencies, key risks, expected stint end)
    and emits one row per populated group using the shared 4-column grid.
    Returns None when strategy_rec is missing or none of the fields are
    populated — that signals "nothing to draw" so the caller can skip the
    rule separator and avoid an empty sub-panel in no-llm mode.
    """
    if strategy_rec is None:
        return None

    pit_lap   = getattr(strategy_rec, "pit_lap_target",     None)
    cmpd      = getattr(strategy_rec, "compound_next",      None)
    ucut_t    = getattr(strategy_rec, "undercut_target",    None)
    pm        = getattr(strategy_rec, "pace_mode",          None)
    tgt_lt    = getattr(strategy_rec, "target_lap_time_s",  None)
    rp        = getattr(strategy_rec, "risk_posture",       None)
    cont      = getattr(strategy_rec, "contingencies",      []) or []
    risks     = getattr(strategy_rec, "key_risks",          []) or []
    stint_end = getattr(strategy_rec, "expected_stint_end", None)

    # Treat NEUTRAL / BALANCED as "no explicit choice" so the default values
    # in StrategyRecommendation don't trigger an empty plan section.
    pm_populated = bool(pm) and pm != "NEUTRAL"
    rp_populated = bool(rp) and rp != "BALANCED"

    has_plan = any([
        pit_lap is not None, cmpd, ucut_t,
        pm_populated, tgt_lt is not None, rp_populated,
        cont, risks, stint_end is not None,
    ])
    if not has_plan:
        return None

    tbl = _mini_grid()

    # ── Pit plan row — "lap N → COMPOUND" headline, target driver in context
    if pit_lap is not None or cmpd or ucut_t:
        headline = Text()
        if pit_lap is not None:
            headline.append(f"lap {pit_lap}", style=f"bold {COL_HEADLINE}")
        if cmpd:
            if pit_lap is not None:
                headline.append("  ", style=COL_DIM)
            headline.append(f"→ {cmpd}", style=f"bold {COL_WATCH}")
        ctx = Text()
        if ucut_t:
            ctx.append(f"undercut {ucut_t}", style=COL_WATCH)
        _plan_row(tbl, "Pit plan", headline, ctx, status="WATCH")

    # ── Pace mode row — mode as headline, target lap time in context ─────────
    if pm_populated or tgt_lt is not None:
        pm_status = {
            "PUSH":           "ALERT",
            "MANAGE":         "WATCH",
            "LIFT_AND_COAST": "WATCH",
        }.get(pm or "", "IDLE")
        _, pm_col = _glyph_for(pm_status)
        headline = Text(pm or "—", style=f"bold {pm_col}")
        ctx = Text()
        if tgt_lt is not None:
            ctx.append(f"target {tgt_lt:.3f}s", style=COL_DIM)
        _plan_row(tbl, "Pace mode", headline, ctx, status=pm_status)

    # ── Risk posture row ────────────────────────────────────────────────────
    if rp_populated:
        rp_status = {
            "AGGRESSIVE": "ALERT",
            "DEFENSIVE":  "WATCH",
        }.get(rp or "", "IDLE")
        _, rp_col = _glyph_for(rp_status)
        _plan_row(
            tbl, "Risk",
            Text(rp, style=f"bold {rp_col}"),
            Text(""),
            status=rp_status,
        )

    # ── Expected stint end row ──────────────────────────────────────────────
    if stint_end is not None:
        _plan_row(
            tbl, "Stint end",
            Text(f"lap {stint_end}", style=f"bold {COL_HEADLINE}"),
            Text(""),
            status="IDLE",
        )

    # ── Contingencies row — first branch as headline, rest in context ───────
    if cont:
        def _unpack(c):
            if isinstance(c, dict):
                return (
                    c.get("trigger",  "?"),
                    c.get("switch_to","?"),
                    c.get("priority", ""),
                )
            return (
                getattr(c, "trigger",  "?"),
                getattr(c, "switch_to","?"),
                getattr(c, "priority", ""),
            )

        trig, sw, pr = _unpack(cont[0])
        pr_status = {"HIGH": "ALERT", "MEDIUM": "WATCH", "LOW": "IDLE"}.get(
            str(pr), "IDLE"
        )
        _, pr_col = _glyph_for(pr_status)
        headline = Text()
        headline.append("if ",       style=COL_DIM)
        headline.append(f"{str(trig)[:28]}", style=COL_HEADLINE)
        headline.append(" → ",       style=COL_DIM)
        headline.append(str(sw),     style=f"bold {pr_col}")

        # Any further branches collapse into a dim summary line.
        ctx = Text()
        if len(cont) > 1:
            extra = []
            for c in cont[1:3]:
                _, sw_i, _ = _unpack(c)
                extra.append(str(sw_i))
            ctx.append(f"+{len(cont) - 1} more → {', '.join(extra)}", style=COL_DIM)

        _plan_row(tbl, "Branch", headline, ctx, status=pr_status)

    # ── Key risks row — first risk as headline, count in context ───────────
    if risks:
        first = str(risks[0])[:48]
        headline = Text(first, style=f"bold {COL_WATCH}")
        ctx = Text()
        if len(risks) > 1:
            ctx.append(f"+{len(risks) - 1} more", style=COL_DIM)
        _plan_row(tbl, "Risks", headline, ctx, status="WATCH")

    return tbl


def _make_inference_panel(
    pace_out       = None,
    tire_out       = None,
    sit_out        = None,
    active_agents  = None,
    rival_data:   dict | None = None,
    lap_num:       int         = 0,
    radio_out      = None,
    pit_out        = None,
    strategy_rec   = None,
    rag_text:      str         = "",
) -> Panel:
    """Build the Rich Panel shown below the history table for the current lap.

    The panel groups three visual sections:

    1. Inference sub-table — one row per activated sub-agent (N25..N29) with
       the raw numeric outputs of each ML model. Rendered whenever any of the
       corresponding *_out arguments is non-None.
    2. Execution plan sub-table — the StrategyRecommendation v2 fields
       (pit plan, pace mode, risk posture, contingencies, key risks, stint
       end) populated by the LLM. Only rendered in LLM mode; no-llm mode
       passes strategy_rec=None so the section is skipped cleanly.
    3. Rival line — tracked driver's position, compound, age, and interval.
       Only rendered when --rival CODE is active on the CLI.

    pace_out / tire_out / sit_out / pit_out / radio_out:
        Sub-agent dataclass outputs for the current lap. Any subset may be
        None; each row helper no-ops when its input is missing, so a failed
        sub-agent does not crash the panel.
    active_agents:
        Set of conditional agent keys ({'N28', 'N30'}) returned by the MoE
        routing layer. When None the routing row is omitted (LLM mode does
        not expose the routing set through the orchestrator output).
    rival_data:
        Dict in the RaceStateManager rival format when a rival is tracked,
        otherwise None.
    lap_num:
        Lap number shown in the panel title. When 0 the title falls back to
        a neutral label so pre-lap or post-race renders still look sane.
    strategy_rec:
        Full StrategyRecommendation from run_strategy_orchestrator_*. Used
        exclusively to build the execution-plan sub-table. None in no-llm
        mode skips the plan section entirely.
    """
    # Always render all six agents (pace, tire, situation, pit, radio, rag).
    # Conditional agents that the MoE did not activate this lap render as a
    # dimmed idle row so the viewer sees the full pipeline roster at every
    # lap — previously only activated agents appeared and the UI made the
    # system feel smaller than it really is. The order matches the logical
    # execution order: always-on block first, then conditional block.
    inf = _mini_grid()
    _add_pace_row(inf,      pace_out)
    _add_tire_row(inf,      tire_out)
    _add_situation_row(inf, sit_out)
    _add_radio_row(inf,     radio_out)
    _add_pit_row(inf,       pit_out)
    _add_rag_row(inf,       rag_text)

    plan_table = _build_plan_table(strategy_rec)

    items: list = [inf]
    if plan_table is not None:
        items.append(Rule(style=COL_DIM, characters="·"))
        items.append(plan_table)

    if rival_data is not None:
        pos      = rival_data.get("position", "?")
        cmpd     = str(rival_data.get("compound", "?"))[:3]
        age      = rival_data.get("tyre_life", "?")
        intv     = rival_data.get("interval_to_driver_s")
        drv_code = rival_data.get("driver", "")
        r_color  = _drv_color(drv_code) if drv_code else "#f59e0b"
        intv_str = f" {intv:+.1f}s" if intv is not None else ""
        rival_line = Text()
        rival_line.append("  Rival  ", style=COL_DIM)
        rival_line.append(f"P{pos} {cmpd}/{age}{intv_str}", style=r_color)
        items.append(rival_line)

    # Title stays minimal — just the lap number so the eye locks on to the
    # per-lap boundary. The subtitle is gone: activation state is now
    # encoded in each row's glyph/colour, so repeating the same info at
    # the border would be redundant.
    title = f"[bold {COL_HEADLINE}]Lap {lap_num}[/bold {COL_HEADLINE}]" if lap_num else None

    return Panel(
        Group(*items),
        title          = title,
        title_align    = "left",
        border_style   = COL_DIM,
        padding        = (0, 1),
        expand         = False,
    )


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
    race_state:   RaceState,
    lap_state:    dict[str, Any],
    laps_df:      pd.DataFrame,
    extra_radio:  dict | None = None,
    extra_rcm:    dict | None = None,
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

    def _safe_call(fn, *args, stub):
        try:
            return fn(*args)
        except Exception as exc:
            if _is_llm_unavailable(exc):
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
    if extra_radio:
        radio_msgs.append(extra_radio)
    rcm_events = list(race_state.rcm_events)
    if extra_rcm:
        rcm_events.append(extra_rcm)
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

    # Conditional pit agent — also LLM-backed internally, so wrap it with
    # the same fallback logic: if the pit ReAct chain hits an LLM error the
    # result is simply "no pit call this lap" (pit_out=None), and the MC
    # simulator degrades gracefully to 3 scenarios (STAY/UNDERCUT/OVERCUT).
    try:
        pit_out, rag_text = _run_conditional_agents(
            active, lap_state, tire_out, sit_out, race_state, laps_df
        )
    except Exception as exc:
        if _is_llm_unavailable(exc):
            pit_out  = None
            rag_text = ""
        else:
            raise
    rag_text = rag_text or ""

    mc = _run_mc_simulation(
        pace_out, tire_out, sit_out, pit_out,
        alpha=race_state.risk_tolerance,
    )

    best = max(mc, key=lambda k: mc[k]["score"])
    return {
        "action":            best,
        "reasoning":         "[no-llm mode — LLM synthesis skipped]",
        "confidence":        0.0,
        "scenario_scores":   {k: round(v["score"], 3) for k, v in mc.items()},
        "regulation_context": "",
        # Sub-agent outputs exposed for the detail panel
        "_pace_out":         pace_out,
        "_tire_out":         tire_out,
        "_sit_out":          sit_out,
        "_pit_out":          pit_out,
        "_radio_out":        radio_out,
        "_rag_text":         rag_text,
        "_active_agents":    set(active),
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

    _load_tire_alloc(_REPO_ROOT)

    # ── Load data ────────────────────────────────────────────────────────────
    with console.status("[dim]Loading parquets…[/dim]", spinner="dots"):
        laps_df = pd.read_parquet(featured_path)
        engine  = RaceReplayEngine(race_dir, args.driver, args.team, interval_seconds=args.interval)

    # ── Pre-warm NLP models (suppresses tqdm + LOAD REPORT noise) ────────────
    mode_label = "no-LLM" if args.no_llm else f"LLM · {args.provider}"
    with console.status("[dim]Loading agents…[/dim]", spinner="dots"):
        _prewarm_agents(args.no_llm)

    # ── Header panel ─────────────────────────────────────────────────────────
    lap_start, lap_end = 1, engine.total_laps
    if args.laps:
        parts     = args.laps.split("-")
        lap_start = int(parts[0])
        lap_end   = int(parts[1]) if len(parts) > 1 else int(parts[0])

    drv_hex  = _drv_color(args.driver)
    header_text = (
        f"[bold cyan]F1 Strategy Manager[/bold cyan]\n"
        f"[dim]GP[/dim] [white]{args.gp_name}[/white]  "
        f"[dim]Driver[/dim] [bold {drv_hex}]{args.driver}[/bold {drv_hex}]  "
        f"[dim]Team[/dim] [white]{args.team}[/white]\n"
        f"[dim]Laps[/dim] [white]{lap_start}–{lap_end}[/white]  "
        f"[dim]Mode[/dim] [white]{mode_label}[/white]  "
        f"[dim]Total race laps[/dim] [white]{engine.total_laps}[/white]\n"
        f"[dim]Orchestrator actions (5):[/dim] "
        f"[green]STAY_OUT[/green] · [red]PIT_NOW[/red] · "
        f"[yellow]UNDERCUT[/yellow] · [yellow]OVERCUT[/yellow] · "
        f"[cyan]ALERT[/cyan]\n"
        f"[dim]Columns:[/dim] [dim]Stay/Pit/Ucut/Ocut = MC scenario scores (highest wins; can be negative) · "
        f"Conf = LLM confidence · panel below = sub-agent inference + execution plan[/dim]"
    )
    if args.rival:
        riv_hex = _drv_color(args.rival)
        header_text += (
            f"\n[dim]Rival tracked[/dim]  [bold {riv_hex}]{args.rival}[/bold {riv_hex}]  "
            f"[dim](position / compound / interval in table + detail line)[/dim]"
        )
    console.print(Panel(header_text, expand=False, border_style="cyan"))
    console.print()

    has_rival = bool(args.rival)
    table = _make_table(has_rival)
    errors:        list[str]   = []
    lap_times_s:   list[float] = []   # elapsed wall-clock time per lap
    prev_lap_time: float       = 0.0
    _detail: list = [None]     # mutable slot for the last-lap sub-agent detail Text

    _spinner = Spinner("dots", style="dim cyan")

    def _render(status: str = "") -> Group:
        items: list = [table]
        if _detail[0] is not None:
            items.append(_detail[0])
        if status:
            _spinner.text = Text(f"  {status}", style="dim cyan")
            items.append(_spinner)
        else:
            items.append(Text(""))
        return Group(*items)

    sim_start = time.monotonic()

    # Live render config:
    # - refresh_per_second=4 — slower than 10 Hz keeps the cursor-line counter
    #   in sync on narrow terminals. 10 Hz causes ghost frames when the panel
    #   below the table changes height mid-refresh.
    # - vertical_overflow="visible" — if the combined Group taller than the
    #   viewport, render the overflow below instead of silently cropping it.
    # - auto_refresh=False — we call live.refresh() manually after each row
    #   so the table and panel always update together, never half-drawn.
    with Live(
        _render(),
        console           = console,
        refresh_per_second = 4,
        vertical_overflow  = "visible",
        auto_refresh       = False,
    ) as live:
        for lap_state in engine.replay():
            lap_num = lap_state["lap_number"]

            if lap_num < lap_start:
                continue
            if lap_num > lap_end:
                break

            driver_st = lap_state.get("driver", {})
            if not driver_st:
                dnf_row = [str(lap_num), "—", "—", "—", "—", "—"]
                if has_rival:
                    dnf_row.append("—")
                dnf_row.extend([Text("[DNF]", style="dim"), "", "", "", "", "", ""])
                table.add_row(*dnf_row)
                live.update(_render(), refresh=True)
                continue

            compound  = driver_st.get("compound", "?")
            tyre_life = int(driver_st.get("tyre_life") or 0)
            position  = int(driver_st.get("position") or 0)
            # Force float — parquet columns can arrive as numpy scalars or dicts on edge cases
            try:
                lap_time = float(driver_st.get("lap_time_s") or 0.0)
            except (TypeError, ValueError):
                lap_time = 0.0

            # Gap to car directly ahead (from rivals list)
            rivals    = lap_state.get("rivals", [])
            car_ahead = next((r for r in rivals if r.get("position") == position - 1), None)
            try:
                gap_ahead = abs(float(car_ahead.get("interval_to_driver_s") or 0.0)) if car_ahead else 0.0
            except (TypeError, ValueError):
                gap_ahead = 0.0
            gap_str = f"{gap_ahead:.2f}" if gap_ahead > 0 else "—"

            # Rival lookup (only when --rival is specified)
            rival_data: dict | None = None
            if has_rival:
                rival_data = next(
                    (r for r in rivals if r.get("driver", "").upper() == args.rival.upper()),
                    None,
                )

            cmpd_text = _compound_text(compound, args.gp_name, args.year)

            lap_t0 = time.monotonic()
            live.update(_render(f"lap {lap_num} / {lap_end}  —  running agents…"), refresh=True)

            try:
                race_state = _build_race_state(lap_state, args.driver, prev_lap_time)
                prev_lap_time = lap_time or prev_lap_time

                # Simulated radio / RCM events (--radio-every N)
                sim_radio: dict | None = None
                sim_rcm:   dict | None = None
                if args.radio_every and args.radio_every > 0 and lap_num % args.radio_every == 0:
                    sim_radio = _generate_radio_event(
                        lap_num, args.driver, compound, tyre_life, position, gap_ahead
                    )
                    sim_rcm = _generate_rcm_event(lap_num)

                if args.no_llm:
                    # No-LLM: full ML stack (pace + tire + sit + radio + conditional + MC)
                    result     = _run_no_llm(race_state, lap_state, laps_df,
                                             extra_radio=sim_radio, extra_rcm=sim_rcm)
                    scores     = result["scenario_scores"]
                    action     = result["action"]
                    confidence = result["confidence"]
                    reasoning  = result["reasoning"]
                    _detail[0] = _make_inference_panel(
                        pace_out      = result.get("_pace_out"),
                        tire_out      = result.get("_tire_out"),
                        sit_out       = result.get("_sit_out"),
                        active_agents = result.get("_active_agents"),
                        rival_data    = rival_data,
                        lap_num       = lap_num,
                        radio_out     = result.get("_radio_out"),
                        pit_out       = result.get("_pit_out"),
                        rag_text      = result.get("_rag_text", ""),
                        strategy_rec  = None,
                    )
                else:
                    # LLM mode: inject simulated radio BEFORE probing so the
                    # radio agent sees the generated events, then run the
                    # full orchestrator.
                    if sim_radio:
                        try:
                            race_state.radio_msgs.append(sim_radio)
                        except (AttributeError, TypeError):
                            pass
                    if sim_rcm:
                        try:
                            race_state.rcm_events.append(sim_rcm)
                        except (AttributeError, TypeError):
                            pass

                    probe_pace, probe_tire, probe_sit, probe_radio = _probe_core_agents(
                        race_state, lap_state, laps_df
                    )
                    result     = run_strategy_orchestrator_from_state(race_state, laps_df, lap_state)
                    scores     = getattr(result, "scenario_scores", {})
                    action     = getattr(result, "action", "?")
                    confidence = getattr(result, "confidence", 0.0)
                    reasoning  = getattr(result, "reasoning", "")
                    _detail[0] = _make_inference_panel(
                        pace_out      = probe_pace,
                        tire_out      = probe_tire,
                        sit_out       = probe_sit,
                        radio_out     = probe_radio,
                        active_agents = None,
                        rival_data    = rival_data,
                        lap_num       = lap_num,
                        strategy_rec  = result,
                        rag_text      = getattr(result, "regulation_context", "") or "",
                    )

                elapsed = time.monotonic() - lap_t0
                lap_times_s.append(elapsed)

                if isinstance(scores, dict):
                    stay = _score_float(scores.get("STAY_OUT", 0.0))
                    pit  = _score_float(scores.get("PIT_NOW",  0.0))
                    ucut = _score_float(scores.get("UNDERCUT", 0.0))
                    ocut = _score_float(scores.get("OVERCUT",  0.0))
                else:
                    stay = pit = ucut = ocut = 0.0

                action_text = Text(str(action), style=ACTION_STYLE.get(str(action).upper(), ""))

                # Rival cell (only when --rival is set)
                if has_rival:
                    if rival_data:
                        r_pos  = rival_data.get("position", "?")
                        r_cmpd = str(rival_data.get("compound", "?"))[:3]
                        r_age  = rival_data.get("tyre_life", "?")
                        r_intv = rival_data.get("interval_to_driver_s")
                        r_intv_str = f" {r_intv:+.1f}s" if r_intv is not None else ""
                        rival_cell: Any = Text(
                            f"P{r_pos} {r_cmpd}/{r_age}{r_intv_str}",
                            style="#f59e0b",
                        )
                    else:
                        rival_cell = Text("—", style="dim")

                # Build row — rival column inserted after Gap Fwd
                row: list[Any] = [
                    str(lap_num),
                    cmpd_text,
                    str(tyre_life),
                    str(position),
                    f"{lap_time:.3f}" if lap_time else "—",
                    gap_str,
                ]
                if has_rival:
                    row.append(rival_cell)
                row.extend([
                    action_text,
                    f"{confidence:.2f}",
                    f"{stay:.3f}",
                    f"{pit:.3f}",
                    f"{ucut:.3f}",
                    f"{ocut:.3f}",
                    reasoning[:200],
                ])
                table.add_row(*row)

            except Exception as exc:
                elapsed = time.monotonic() - lap_t0
                lap_times_s.append(elapsed)
                err_msg = f"LAP {lap_num}: {type(exc).__name__}: {exc}"
                errors.append(err_msg)
                err_row: list[Any] = [
                    str(lap_num), cmpd_text, str(tyre_life), str(position), "—", gap_str,
                ]
                if has_rival:
                    err_row.append("—")
                err_row.extend([
                    Text("[ERROR]", style="bold red"), "", "", "", "", "",
                    str(exc)[:60],
                ])
                table.add_row(*err_row)
                if args.verbose:
                    console.print_exception()

            live.update(_render(), refresh=True)

    # ── Summary panel ─────────────────────────────────────────────────────────
    total_s   = time.monotonic() - sim_start
    avg_s     = sum(lap_times_s) / len(lap_times_s) if lap_times_s else 0.0
    n_laps    = len(lap_times_s)
    err_count = len(errors)

    status_line = (
        f"[green]All {n_laps} lap(s) OK[/green]"
        if not errors else
        f"[yellow]{n_laps} lap(s), {err_count} error(s)[/yellow]"
    )
    summary = (
        f"{status_line}\n"
        f"[dim]Total[/dim] [white]{total_s:.1f}s[/white]  "
        f"[dim]Avg/lap[/dim] [white]{avg_s:.1f}s[/white]"
    )
    console.print()
    console.print(Panel(summary, title="[bold]Run complete[/bold]", expand=False, border_style="green" if not errors else "yellow"))

    if errors:
        console.print()
        for e in errors:
            console.print(f"  [red]✗[/red] {e}")


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
        "--radio-every",
        type=int,
        default=0,
        metavar="N",
        help="Simulate a radio/RCM event every N laps to activate NLP agents "
             "(e.g. --radio-every 5).  0 = disabled (default).",
    )
    p.add_argument(
        "--rival",
        default=None,
        metavar="CODE",
        help="FIA three-letter code of a driver to track as rival (e.g. VER). "
             "Adds a Rival column to the table and shows their position / "
             "compound / interval in the detail line below.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Print full tracebacks on per-lap errors",
    )
    return p.parse_args()


if __name__ == "__main__":
    run(_parse_args())
