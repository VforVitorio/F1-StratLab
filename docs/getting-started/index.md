# Getting started

Three ways to get F1 StratLab running on your machine, from fastest to deepest.

## 1. Install the latest wheel

The quickest path. Installs the latest release into your current environment without cloning the repo.

```bash
uv pip install https://github.com/VforVitorio/F1-StratLab/releases/download/v1.1.0/f1_strat_manager-1.1.0-py3-none-any.whl
```

After install you have four console entry points:

```bash
f1-strat       # interactive launcher (recommended starting point)
f1-sim         # headless CLI simulation against a saved race
f1-arcade      # three-window PySide6 + pyglet experience
f1-streamlit   # Streamlit dashboards
```

First boot triggers a one-time download of the cached models and reference data into `~/.f1-strat/`. Subsequent runs are offline.

## 2. Clone the repo for development

If you want to edit the code, run the notebooks or contribute back:

```bash
git clone https://github.com/VforVitorio/F1-StratLab.git
cd F1-StratLab
uv sync --all-extras
```

`uv sync` reads `pyproject.toml`, resolves the lockfile and pulls the CUDA-routed PyTorch wheel automatically on Windows and Linux (CPU build on macOS).

Run the simulation against a saved race:

```bash
uv run scripts/run_simulation_cli.py Bahrain NOR McLaren --no-llm
```

Drop `--no-llm` once you have an LLM provider configured (LM Studio at `http://localhost:1234/v1` or `OPENAI_API_KEY` in `.env`).

## 3. Docker

For a reproducible all-in-one setup, see [Setup and deployment](../setup-and-deployment.md) for the Docker compose recipe that boots the FastAPI backend, the Streamlit frontend and the Qdrant store in one command.

## Where to next

- New to the architecture? Start at [Architecture overview](../architecture.md).
- Want to see the agents in action? Open [Arcade quick start](../arcade/quick-start.md).
- Looking for an API to call from your own code? Jump to [Multi-agent system](../agents-api-reference.md).
- Curious about the numbers in the thesis? See [Thesis results](../thesis-results/index.md).
