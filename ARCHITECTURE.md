# Architecture

One-page map linking the detail docs. Read this first, then descend
into the deep dives as needed.

## Three user-facing surfaces, one shared core

- **CLI** (`f1-sim`) — headless Rich-based live inference panel.
- **Arcade** (`f1-arcade`) — 2D race replay + PySide6 strategy dashboard
  + PySide6 telemetry window (one command spawns all three).
- **Streamlit app** (`f1-streamlit` or `docker compose up`) — post-race
  analysis, chat, voice.

All three consume the same core:

- `src/agents/` — N25-N31 multi-agent stack (pace, tire, race situation,
  pit strategy, radio NLP, RAG regulations, orchestrator).
- `src/simulation/` — `RaceReplayEngine` + `RaceStateManager`.
- `data/processed/laps_featured_<year>.parquet` + `data/raw/<year>/<Location>/` +
  `data/tire_compounds_by_race.json`.

The Streamlit path also runs a FastAPI backend (`src/telemetry/backend/`).
The Arcade path runs the strategy pipeline locally without the backend
(see [`docs/arcade/strategy-pipeline.md`](docs/arcade/strategy-pipeline.md)).

## Multi-agent pipeline

N25 Pace · N26 Tire · N27 Situation · N29 Radio are always-on. N28 Pit
Strategy and N30 RAG are conditional (routing decides per-lap). N31
Orchestrator fuses all outputs through a Monte Carlo simulation and an
LLM synthesis pass into a `StrategyRecommendation`. Full flow:
[`docs/architecture.md`](docs/architecture.md) + the
[`docs/diagrams/strategy_pipeline_flow.drawio`](docs/diagrams/strategy_pipeline_flow.drawio)
diagram.

## Arcade three-window topology

`f1-arcade --strategy` spawns:

1. The pyglet replay window (this process).
2. One PySide6 subprocess hosting **two** Qt windows in a shared
   `QApplication` event loop: `MainWindow` (strategy dashboard) and
   `TelemetryWindow` (2×2 circuit-comparison grid).

Both windows subscribe to the arcade's `TelemetryStreamServer` on
`127.0.0.1:9998`. Details:
[`docs/arcade/dashboard.md`](docs/arcade/dashboard.md) and the
[`docs/diagrams/arcade_3window_architecture.drawio`](docs/diagrams/arcade_3window_architecture.drawio)
diagram.

## Data flow

- First run downloads the canonical data tree from Hugging Face
  (`VforVitorio/f1-strategy-dataset`) via
  `src/f1_strat_manager/data_cache.py::ensure_setup()`.
- FastF1 session cache lives under `data/cache/fastf1/` (local only,
  gitignored).
- Featured laps parquets + per-race raw dirs + tire-compound-by-race
  map form the input to the multi-agent stack.

See [`docs/diagrams/tcp_broadcast_dataflow.drawio`](docs/diagrams/tcp_broadcast_dataflow.drawio)
and [`docs/diagrams/data_pipeline.drawio`](docs/diagrams/data_pipeline.drawio)
for the wire-level view.

## Where to go next

- **Install:** [`INSTALL.md`](INSTALL.md).
- **Roadmap:** [`ROADMAP.md`](ROADMAP.md).
- **Agents reference:** [`docs/agents-api-reference.md`](docs/agents-api-reference.md).
- **Backend API:** [`docs/backend-api.md`](docs/backend-api.md).
- **Streamlit frontend:** [`docs/streamlit-frontend.md`](docs/streamlit-frontend.md).
- **Simulation engine:** [`docs/simulation/overview.md`](docs/simulation/overview.md).
- **All draw.io diagrams:** [`docs/diagrams/`](docs/diagrams/).
