# Getting started

**F1 StratLab is an open-source (Apache-2.0) multi-agent AI system for real-time Formula 1 race strategy**, combining seven ML models, six LangGraph sub-agents and one orchestrator. This page covers installation, for what it does and how it is wired, see the [architecture overview](#/architecture).

Three ways to get F1 StratLab running locally, from fastest to deepest.

<p align="center">
  <video src="/assets/demo/arcade-demo.mp4" poster="/assets/demo/arcade-demo-poster.jpg" width="760" autoplay loop muted playsinline preload="metadata" aria-label="F1 StratLab Arcade replay in action"></video>
  <br/>
  <sub>The <code>f1-arcade</code> replay: a 2D race with the strategy dashboard and live telemetry, all from one command.</sub>
</p>

## 1. Install the latest wheel

The quickest path. Installs the latest release into the current environment without cloning the repo.

```bash
uv pip install https://github.com/VforVitorio/F1-StratLab/releases/download/v__DOCS_VERSION__/f1_strat_manager-__DOCS_VERSION__-py3-none-any.whl
```

After install, seven console entry points are available:

```bash
f1-strat       # interactive launcher (recommended starting point)
f1-sim         # headless CLI simulation against a saved race
f1-arcade      # pyglet 2D replay plus the two PITWALL windows
f1-webapp      # post-race web app; requires a source checkout and Docker
f1-prefetch    # fill the arcade replay cache ahead of time
f1-eval        # regenerate the evaluation reports (registry, calibration, RAG, hygiene, projection, ...)
f1-pitwall     # attach the two PITWALL windows to an arcade already running
```

The wheel includes the `f1-webapp` command, but it cannot launch the web app
by itself because the wheel does not include `docker-compose.yml`. The entry
point wraps `docker compose up`; `uv run f1-webapp` starts the stack from a
source checkout with its submodule initialized. Compose also requires the
repository-root `.env` file; copy `.env.example` before starting the stack.

`f1-prefetch` exists because the first launch of any given race builds its replay telemetry, which takes minutes. It runs the same preparation the arcade menu runs, for a whole season or a rounds spec, so the wait can be paid in advance rather than while somebody is waiting to watch:

```bash
f1-prefetch --year 2025                   # the whole calendar
f1-prefetch --year 2025 --rounds 1,3,5-8  # commas and ranges
f1-prefetch --year 2025 --with-radio      # also fetch the team radio the agents read
f1-prefetch --year 2025 --force           # rebuild rounds that are already cached
```

A round whose file is already on disk is skipped without being read, which is what makes a second run cheap. The check is the presence of that file and nothing else, so it cannot see a cache left stale by a release that changed the replay format. After such a release the skip reports every round as cached and rebuilds nothing, and `--force` is the way past it.

Rounds already cached are skipped without being loaded, so re-running it costs one filesystem check per round.

`f1-eval` and `f1-pitwall` are developer tools rather than end-user surfaces. The first writes versioned markdown and JSON reports under `documents/eval_reports/` (`f1-eval registry`, `f1-eval rag`, `f1-eval calibration`, `f1-eval all`, ...); the second opens the PITWALL windows against an arcade process that is already running, which is how the UI is developed without restarting the replay.

The CLI bootstraps models and common reference data on first use. Arcade reads
those model files from the local cache and fetches race and radio data as
needed. On a fresh cache, run a one-lap `f1-sim` command with `--no-llm` and
`--no-real-radios` before enabling `--strategy` in Arcade. Arcade does not
download model weights. A source checkout stores assets under `data/`; a
global tool install uses `~/.f1-strat/data/`.
  `F1_STRAT_DATA_ROOT` overrides the data directory. For the first-run Hub
  download, its final path component must be named `data` (for example
  `/mnt/f1/data`), because the downloaded files retain the repository's
  `data/...` paths. Both Compose files bind the checkout's `data/` directory to
  `/app/data` and set that container path explicitly, so a host override in
  `.env` does not relocate the Compose cache. Compose does not run the bootstrap;
  prepare the dataset and models before starting `f1-webapp`.

## 2. Clone the repo for development

To edit the code, run the notebooks or contribute back:

```bash
git clone --recurse-submodules https://github.com/VforVitorio/F1-StratLab.git
cd F1-StratLab
uv sync --all-extras
```

`uv sync` reads `pyproject.toml`, resolves the lockfile and pulls the CUDA-routed PyTorch wheel automatically **on Windows**. Everything else, Linux and macOS included, resolves to the CPU wheel: CI runners and CPU-only Linux boxes were downloading about 5 GB of unused CUDA libraries, so the markers were narrowed deliberately (`pyproject.toml`, #251). A Linux GPU box opts back in by editing those markers.

`uv sync --all-extras` does not cover one notebook. `N19_sentiment_vader.ipynb` is the VADER sentiment baseline that RoBERTa replaced, so nothing on the three surfaces reaches it, and nltk was dropped from the dependencies rather than waived against an advisory with no patched release (#1176). That notebook runs with `uv run --with nltk jupyter lab`.

Run the simulation against a saved race:

```bash
uv run scripts/run_simulation_cli.py Sakhir NOR McLaren --no-llm
```

Drop `--no-llm` once an LLM provider is configured. Without `--provider`, `f1-sim` reads `F1_LLM_PROVIDER` from a repo-root `.env` and falls back to LM Studio at `http://localhost:1234/v1`; `--provider openai` selects OpenAI, which needs `OPENAI_API_KEY`.

## 3. Docker

For a reproducible all-in-one setup, see [Setup and deployment](#/setup) for the Docker compose recipe that boots the FastAPI backend and the React web app in one command. Qdrant runs on-disk inside the backend process rather than as its own container, so there is nothing extra to start.

## Where to next

- New to the architecture? Start at [Architecture overview](#/architecture).
- Want to see the agents in action? Open [Arcade quick start](#/arcade-quick-start).
- Looking for an API to call from external code? Jump to [Multi-agent system](#/agents-api).
- Curious about the numbers in the thesis? See [Thesis results](#/thesis).

## FAQ

### Do I need a GPU?

No, but it helps. `uv sync` pulls the CUDA-routed wheel **on Windows only**; Linux and macOS get the CPU build, so out of the box the stack runs on CPU almost everywhere. A GPU mainly accelerates Whisper radio transcription and the TCN tire model, the benchmark latencies on the [thesis results](#/thesis) page (Whisper 233.9 ms, NLP pipeline 42.1 ms) are GPU figures; on CPU it is slower but fully functional.

### Why is the first run slow?

The CLI downloads models and reference data on first use. Arcade loads model
files from the cache and fetches replay data and the selected GP's radio corpus
when needed. Docker Compose does not bootstrap these assets. The simulation
also warms Whisper and the agents before lap 1. `--no-llm` skips the LLM path;
`--no-real-radios` skips the real radio corpus and Whisper transcription, while
`--radio-every` can still generate synthetic messages.

### Which LLM providers are supported?

OpenAI and LM Studio are supported, and the default differs by surface. The `f1-strat` wizard defaults to **No LLM** and forwards its selected provider to `f1-sim`. Other surfaces resolve `F1_LLM_PROVIDER` according to their own configuration. The per-surface defaults and overrides are listed in [INSTALL.md](https://github.com/VforVitorio/F1-StratLab/blob/main/INSTALL.md#llm-provider-per-surface).

### Do I need an API key?

Only for the LLM synthesis layer. Run with `--no-llm` and the ML models plus Monte Carlo simulation still produce a recommendation with no key required. LM Studio needs no key; OpenAI needs `OPENAI_API_KEY` in `.env`.
