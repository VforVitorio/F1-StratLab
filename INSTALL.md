# Install Guide: F1 StratLab

The CLI and Arcade can be installed as `uv` tools. The web app runs from a
repository checkout with Docker Compose. The Arcade setup below builds the
PITWALL UI before installing the tool.

---

## Prerequisites

- Python **3.10, 3.11, or 3.12** (the project pins `>=3.10,<3.13` in
  `pyproject.toml`; CI runs on 3.12).
- `OPENAI_API_KEY` in a `.env` at the repo root (or exported in the shell)
  when the resolved provider is OpenAI. `.env.example` ships
  `F1_LLM_PROVIDER=openai`; which surface reads it, and what each one falls
  back to, is in [LLM provider, per surface](#llm-provider-per-surface)
  below. Every surface can also skip the LLM step entirely, in which case no
  key is needed.
- For the web app Docker flow: **Docker Desktop** (Windows/Mac) or
  `docker + compose` plugin (Linux).
- For Arcade: a working OpenGL graphics stack and a platform webview. Linux
  also needs the WebKitGTK system dependency.
- Node.js 20.19+ or 22.12+ and npm to build the PITWALL UI or run the web app
  development server.
- For CLI / Arcade wheel install: [`uv`](https://docs.astral.sh/uv/)
  (recommended) or plain `pip`. `uv` resolves the CUDA-specific PyTorch
  wheel automatically via the `[tool.uv.sources]` table in
  `pyproject.toml`.
- **First-run budget**: the CLI bootstrap downloads models and reference data
  from Hugging Face (about 7-8 GB over a session; keep ~15-20 GB free). Arcade
  reads model files from that cache and fetches race data and radio assets as
  needed. The first replay may also fetch an extra ~1.5 GB Whisper checkpoint.
  Cached assets are reused; another GP may need its radio corpus on first use.

---

## LLM provider, per surface

Each surface resolves the LLM provider on its own. The table is the single
place that records how, and every cell is checkable against the file named
in it. `tests/infra/test_install_provider_table.py` reads those files and
fails when a value here stops matching the code.

| Surface | Reads `.env` | Provider when nothing is set | Overridden by | Model |
|---|---|---|---|---|
| `f1-sim` | repo root, source checkout only (`scripts/run_simulation_cli.py`) | `lmstudio` (`src/agents/strategy_orchestrator.py`) | `--provider openai\|lmstudio`, or `--no-llm` to skip the step | sub-agents `gpt-4.1-mini` (`F1_LLM_MODEL_AGENTS`), orchestrator `gpt-5.4-mini` (`F1_LLM_MODEL_ORCHESTRATOR`) |
| `f1-strat` | repo root in a source checkout (`scripts/f1_cli.py`) | the wizard's LLM-mode pick, which highlights "No LLM" | the wizard, always forwarded to `f1-sim` as `--provider` or `--no-llm` (`scripts/cli/runner.py`) | as `f1-sim` |
| `f1-arcade`, `f1-pitwall` | `f1-arcade` uses python-dotenv's search from `src/arcade/main.py`; `f1-pitwall` inherits its process environment | `openai` for Arcade (`src/arcade/app.py`); PITWALL has no separate provider | `F1_LLM_PROVIDER`, or `--no-llm` for Arcade | as `f1-sim` for Arcade; none for PITWALL |
| `f1-webapp` chat tab | repo root, then `src/telemetry/.env` as an override (`src/telemetry/backend/core/config.py`) | `lmstudio` (`src/telemetry/backend/services/chatbot/llm_service.py`) | `F1_LLM_PROVIDER`, then a bare `LLM_PROVIDER` | `gpt-5.4-mini`, or `OPENAI_CHAT_MODEL` |
| backend `POST /simulate` | as the chat tab | `F1_LLM_PROVIDER`, then `lmstudio` | optional request `provider`; process-wide, not isolated per request (#1192, #1261) | as `f1-sim` |

Four things the table cannot fit:

**The shell wins over the file.** None of the nine `load_dotenv` calls passes
`override=True` except the second one in
`src/telemetry/backend/core/config.py`, so an exported `F1_LLM_PROVIDER`
beats the repo-root `.env` everywhere. For the backend only, a
`src/telemetry/.env` beats both. An omitted `provider` in `POST /simulate`
leaves the resolved value alone. An explicit value changes the process
environment, and N31 caches one client per process. Concurrent requests with
different explicit providers are not isolated; use one provider for the backend
process until #1261 is addressed.

**A global tool install does not read the checkout's `.env`.** In a source
checkout, `f1-sim` and `f1-strat` load the repo-root file. `f1-arcade` uses
python-dotenv's default search from its module path. Set variables in the
process environment for a global install; `f1-sim` also accepts `--provider`.

The CLI and backend default to LM Studio. Arcade defaults to OpenAI.
`F1_LLM_PROVIDER` selects a provider explicitly on surfaces that read it.

The model names in the table are defaults. `F1_LLM_MODEL_AGENTS` and
`F1_LLM_MODEL_ORCHESTRATOR` override the strategy models. `OPENAI_CHAT_MODEL`
configures the web app chat model.

---

## CLI, headless strategy replay with Rich live panels

```bash
uv tool install "git+https://github.com/VforVitorio/F1-StratLab.git"
f1-strat
```

This guide uses `f1-strat` (the interactive wizard with race, driver, lap,
provider and rival pickers) and `f1-sim` (the headless argparse form). The
wizard auto-resolves the team from
`laps_featured_2025.parquet`, shells out to `f1-sim` under the hood and
turns Ctrl+C into a clean italic *Interrupted.* notice.

Prefer the scripted form for demos and CI:

```bash
f1-sim Suzuka VER "Red Bull Racing" --year 2025
```

`--no-llm` runs the ML-only path (no OpenAI spend). See
`python -m scripts.run_simulation_cli --help` for every flag.

Already installed from a source checkout? `uv sync && uv run f1-strat`
(or `uv run f1-sim ...`) works too.

---

## Arcade, 3-window race replay + live dashboard + telemetry

```bash
set -e
git clone https://github.com/VforVitorio/F1-StratLab.git
cd F1-StratLab
cd src/pitwall/ui
npm ci && npm run build
cd ../../..
uv tool install .
# First run: populate the model cache used by Arcade strategy mode.
f1-sim Suzuka VER "Red Bull Racing" --year 2025 --no-llm --no-real-radios --laps 1-1
f1-arcade --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --driver2 LEC --strategy
```

The PITWALL bundle is ignored build output, so it must be built from the
checkout before installation for the two PITWALL windows to open.

Three windows spawn from that one command:

1. Arcade replay (pyglet), track · leaderboard · weather · driver info
2. **PITWALL · AGENTS**, orchestrator + 6 agent cards + charts
3. **PITWALL · DATA**, status strip, timing tower, bests, own-car traces,
   race pace and race trace

The two PITWALL windows are React built to static files and hosted in the
platform webview, in one subprocess sharing a single stream client. They
replaced a PySide6 pair.

**Docker is NOT recommended for Arcade**: pyglet and the platform webview need a
host OpenGL context and a native display. Cross-platform X forwarding from a
container is fragile on Windows / Mac and has no benefit over a local
install. Use `uv tool install` and run on the host.

See [`docs/pages/arcade-quick-start.md`](docs/pages/arcade-quick-start.md) for the
controls legend, troubleshooting and window tour.

---

## Web app, post-race analysis UI (backend + React SPA)

```bash
git clone --recurse-submodules https://github.com/VforVitorio/F1-StratLab.git
cd F1-StratLab
cp .env.example .env          # add OPENAI_API_KEY, or set F1_LLM_PROVIDER=lmstudio
uv run f1-webapp              # wraps `docker compose up` and prints the URLs
```

`--recurse-submodules` is required: both containers build from `src/telemetry`,
which is empty without it. `cp .env.example .env` is required too: Compose
aborts with "env file ./.env not found" otherwise. The backend reads race data
from `./data`; Compose mounts the dataset read-only and gives FastF1 and RAG
their own writable cache mounts. Seed the required dataset and model assets on
the host first (see [Data bootstrap](#data-bootstrap)) or the data endpoints
return 404.

Opens:

- React web app at `http://localhost:8501`
- FastAPI backend at `http://localhost:8000`

The backend container mounts `./src/telemetry` so its edits reload without a
rebuild; the web app ships as a built nginx image (rebuild to pick up frontend
changes, or use the dev server below). `.env` at repo root is picked up by the
backend image.

For frontend development without Docker:

```bash
cd src/telemetry/webapp
npm install && npm run dev   # Vite dev server, proxies /api to :8000
```

The legacy Streamlit app has been removed from the repo (the `f1-streamlit`
entry point with it); it survives in git history and in the `legacy_version`
branch. `f1-webapp` is the single launcher for the post-race surface.

---

## Data bootstrap

Source checkouts use `data/`. Global CLI and Arcade installs use
`~/.f1-strat/data/`, unless `F1_STRAT_DATA_ROOT` overrides the location.
Docker maps the host's `./data` to `/app/data`.

- `data/processed/laps_featured_<year>.parquet`, featured lap data
- `data/raw/<year>/<Location>/`, per-race FastF1 pickle cache
- `data/processed/race_radios/<year>/<slug>/`: OpenF1 radio corpus +
  `rcm.parquet` for Race Control messages
- `data/tire_compounds_by_race.json`, canonical per-year GP calendar
  and compound allocation

The CLI and Arcade call `ensure_radio_corpus()` and populate the FastF1 cache
when needed, then reuse cached files. A different GP may still need its radio
corpus on first use. Docker Compose does not bootstrap the Hugging Face
dataset or model assets, so prepare them on the host before startup. The
FastF1 and RAG cache mounts remain writable inside the backend container.

Prepare the dataset and model assets on the host before `docker compose up`,
either by running the CLI path once (`uv run f1-sim Melbourne VER "Red Bull Racing" --year 2025 --no-llm --laps 1-1`)
or directly:

```bash
uv run python -c "from src.f1_strat_manager.data_cache import ensure_setup; ensure_setup(show_progress=True)"
```

---

## Verification commands

After install, a quick sanity:

```bash
# CLI path — runs one lap with no LLM spend
f1-sim Melbourne VER "Red Bull Racing" --year 2025 --no-llm --laps 1-1

# Arcade path — opens the replay with strategy pipeline warmup
f1-arcade --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --strategy

# DRS zones audit (cross-check against FIA 2025 Event Notes)
python scripts/verify_drs_zones.py --year 2025 --summary
```

---

## Uninstall

```bash
uv tool uninstall f1-strat-manager
docker compose down      # from the repo root for the web app stack
```
