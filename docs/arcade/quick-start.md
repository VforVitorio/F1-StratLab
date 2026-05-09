# Arcade Quick Start

End-user guide for running the F1 StratLab arcade replay with the
live strategy dashboard. Aimed at someone who has cloned the repository
and wants to see three synchronised windows on screen inside ten minutes.

One command launches everything: the arcade replay window (pyglet), the
strategy dashboard (PySide6), and the telemetry window (PySide6). The
arcade process owns the simulation loop and broadcasts merged state on a
local TCP port; the dashboard subprocess subscribes and renders.

---

## Prerequisites

- **Python**: 3.10 or newer. The project pins dependencies with `uv`.
- **Dependencies**: run `uv sync` from the repo root. The lockfile pulls
  `arcade`, `PySide6`, `pyqtgraph`, `fastf1`, `langchain-openai`, the
  model stack (`xgboost`, `lightgbm`, `torch`), and the NLP stack
  (`transformers`, `sentence-transformers`, `setfit`). No manual install
  steps are required beyond `uv sync`.
- **LLM credentials**: either set `OPENAI_API_KEY` in a repo-root `.env`
  (the canonical TFG setup, uses `gpt-4.1-mini` for sub-agents and the
  orchestrator) or run LM Studio locally on `http://localhost:1234/v1`
  and export `F1_LLM_PROVIDER=lmstudio`. The dashboard will render
  perfectly well in either configuration; only the wording of the
  orchestrator's reasoning changes.
- **Race data cache**: the replay reads
  `data/raw/{year}/{Location}/laps.parquet` and optionally
  `weather.parquet`. The parquet files are produced by FastF1 on first
  run; the cache populates automatically the first time a given round is
  requested. Expect a 20--40 second delay on the first launch of a round
  while FastF1 downloads and resamples the session, and instant launches
  on subsequent runs.
- **Vector store (optional)**: the N30 RAG agent reads a local Qdrant
  index under `data/rag/`. If the index is missing, the orchestrator
  degrades gracefully — regulation lookups return an empty context and
  the dashboard shows a placeholder in the RAG card. Run
  `python scripts/build_rag_index.py` once to build it.

---

## One-command launch

From the repository root:

```bash
python -m src.arcade.main --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --driver2 LEC --strategy
```

What happens:

1. `src.arcade.main` parses the CLI and opens the arcade `Window`.
2. The `--viewer` flag skips the menu and goes straight to
   `F1ArcadeView`.
3. The view loads the 2025 Round 3 (Suzuka) parquet for Verstappen.
4. With `--strategy` set, the view starts a `TelemetryStreamServer` on
   `127.0.0.1:9998`, owns a `StrategyState`, and spawns the dashboard
   subprocess with `python -m src.arcade.dashboard`.
5. The dashboard opens two PySide6 windows that both connect back to the
   stream.

Three windows are now on screen. The arcade window drives playback; the
two Qt windows react to broadcasts.

---

## What each window shows

### Arcade replay (pyglet)

Track outline with the DRS zones drawn in green, two driver icons (our
driver in team colour, rival in rival-team colour), a leaderboard on the
right with compound pills and gaps, a weather panel, a driver-info
strip, and a progress bar with the current lap. The strategy panel that
used to sit in the bottom-right is gone in Phase 3.5 Proceso B — the
dashboard window replaces it.

### Strategy dashboard (PySide6)

A `QSplitter` divides the window into two halves.

- **Left panel (540 px wide)**: orchestrator card on top (action badge,
  confidence bar, pace/risk chips, plan strip with compound pill, and a
  guardrail line that shows when the no-LLM hard guard overrode the LLM
  pick), scenario bars in the middle (four bars for STAY_OUT / PIT_NOW /
  UNDERCUT / OVERCUT with shift+normalise so negative Monte Carlo scores
  still render), reasoning tabs on the bottom (six tabs with syntax
  highlighting).
- **Right panel (740 px wide)**: a 3x2 grid of sub-agent cards. Pace
  (N25), Tire (N26), Situation (N27), Radio (N29), Pit (N28, dimmed
  when inactive), RAG (N30, dimmed when inactive). Each card has a
  headline, a short body, and a reserved chart slot — Pace and Tire
  host embedded `pyqtgraph` plots.

### Telemetry window (PySide6)

Standalone `QMainWindow` with a 2x2 grid of `pyqtgraph` plots:
**Delta** (our driver vs rival), **Speed**, **Brake**, **Throttle**.
The window owns its own `TelemetryStreamClient` so it can be closed or
moved across monitors without interfering with the strategy dashboard.

Visual overview of the three-window topology lives in
[`docs/diagrams/arcade_3window_architecture.drawio`](diagrams/arcade_3window_architecture.drawio)
— open it in draw.io desktop or diagrams.net for the widget breakdown
and TCP arrows.

---

## Menu mode vs `--viewer`

Drop the `--viewer` flag and the arcade opens `MenuView` first:

```bash
python -m src.arcade.main --strategy
```

`MenuView` is a pure-keyboard navigator (Arrow keys + Enter, Escape to
go back). It lists years (2023--2025), rounds per year (from
`data/tire_compounds_by_race.json`, the canonical mapping), drivers, and
teams. The driver selection auto-fills the team via the
`DRIVER_TO_TEAM_2025` map. Pressing Enter on the final confirmation
screen boots the replay with the same
`F1ArcadeView` the `--viewer` shortcut loads directly.

The `--viewer` shortcut exists for regression testing and for the "I
know what I want" path — it accepts `--year`, `--round`, `--driver`,
`--driver2`, `--team`, `--provider`, and `--strategy` exactly as the
menu would produce.

---

## Single-driver vs two-driver mode

Omit `--driver2` and only the main driver renders on track and in the
telemetry charts. The Delta trace in the telemetry window stays empty
(no rival to compare against) and the Situation card focuses solely on
safety-car probability.

Pass `--driver2 LEC` and:

- The rival icon appears on the track in the rival-team colour.
- The Delta plot renders the rolling gap between our driver and the
  rival.
- The Situation card gains the overtake-probability gauge driven by the
  N27 LightGBM model.
- The Pit card's undercut probability is computed against the rival.

---

## Playback controls (arcade window)

Hotkeys are handled by `F1ArcadeView.on_key_press`:

- `Space` — pause / resume
- `Right Arrow` — step one lap forward
- `Left Arrow` — step one lap backward
- `+` / `-` — increase / decrease playback speed
- `Escape` — return to the menu (or exit if launched with `--viewer`)

The dashboard chip in the header bar mirrors the `playback` state (PLAY
/ PAUSE / SEEK) in real time; the user never has to click inside the Qt
window to know whether the replay is still running.

---

## Known limitations

- **First-lap warmup**: the orchestrator runs cold for the first
  ~15 seconds while agent models load (XGBoost, TireDegTCN, LightGBM
  models, NLP pipelines). The Situation and Tire cards may read
  "loading" until the first inference completes.
- **Cold FastF1 cache**: the first time a given round is requested,
  FastF1 downloads the session and the multiprocessing resampler rebuilds
  the parquet. Expect roughly 30 seconds on cold cache, instant on
  subsequent runs.
- **Dashboard dependencies**: `PySide6` and `pyqtgraph` must be
  installed. `uv sync` handles both, but if the dashboard subprocess
  fails at import time the arcade window logs a warning and keeps
  running without a dashboard.
- **Port 9998**: the TCP broadcaster binds `127.0.0.1:9998`. If another
  process holds the port, the dashboard cannot connect. The arcade logs
  `Address already in use`; kill the stale process or wait for
  `SO_REUSEADDR` to clear.
- **Strategy mode requires year 2025**: the multi-agent pipeline only
  ships with 2025-season features. Running `--strategy` against a 2023
  or 2024 round falls back to arcade-only replay.

---

## Troubleshooting

**"race dir missing"**

```
FileNotFoundError: data/raw/2025/Suzuka/laps.parquet
```

The FastF1 cache has not been built for that round. Run the arcade once
without `--strategy`, or build the parquet explicitly with
`python -m src.simulation.builder 2025 3`. Verify the round label
matches the Location in `data/tire_compounds_by_race.json` — stale
labels (for example "Australia" for round 3 in 2025 when the 2025
schedule moved to Suzuka) are the most common cause.

**"Backend offline" / "Connection refused"**

The dashboard subscribes to `127.0.0.1:9998`, which the arcade owns. If
you see this message, the arcade has not started the stream server yet
(usually because `--strategy` was not passed) or the arcade window has
been closed. Restart the arcade with `--strategy`.

**"No module named pyqtgraph"**

`uv sync` did not complete. Re-run it from the repo root. If you are
outside the `uv` environment, activate it first:

```bash
uv sync
uv run python -m src.arcade.main --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --strategy
```

**"OpenAI api_key missing"**

The `.env` file is missing or `OPENAI_API_KEY` is unset. Either add the
key to `.env` at the repo root, or switch to LM Studio:

```bash
F1_LLM_PROVIDER=lmstudio python -m src.arcade.main --viewer ...
```

LM Studio must be running on `http://localhost:1234/v1` with a compatible
chat-completion model loaded.

**Dashboard renders but charts stay empty**

The first broadcast carries only the arcade frame; per-agent outputs
arrive on the second broadcast (after the orchestrator completes its
first inference). If the charts never populate, check the arcade log
for orchestrator exceptions.

---

## Related reading

- [`docs/arcade-dashboard.md`](arcade-dashboard.md) — developer-level
  architecture deep dive on the dashboard package.
- [`docs/strategy-pipeline-arcade.md`](strategy-pipeline-arcade.md) —
  why the arcade keeps its own copy of the orchestrator body.
- [`docs/architecture.md`](architecture.md) — N25--N31 multi-agent
  pipeline reference.
- [`docs/diagrams/`](diagrams/) — drawio sources including
  `arcade_3window_architecture.drawio`, `strategy_pipeline_flow.drawio`,
  `tcp_broadcast_dataflow.drawio`, `subprocess_launch_sequence.drawio`,
  and `system_architecture.drawio`.
