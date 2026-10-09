# Simulation development guide

Run commands from the repository root. Use `uv run` so each command uses the locked environment. See [INSTALL.md](../../INSTALL.md) for surface setup and provider configuration, and [testing-guide.md](testing-guide.md) for test tiers.

## Headless replay

For a fast one-lap smoke without LLM synthesis, radio-corpus loading, or Whisper:

```powershell
uv run f1-sim Melbourne NOR McLaren --year 2025 --no-llm --no-real-radios --laps 1-1
```

`f1-sim` reads the race from `data/raw/<year>/<gp>/` and the agent frame from `data/processed/laps_featured_<year>.parquet`. The first run may download data or models from Hugging Face. Use `--verbose` to print full per-lap tracebacks.

The `f1-sim` entry point checks lap syntax and the selected driver's recorded lap range before loading the runner. The `f1-strat` wizard lists only drivers in the selected race and applies the same lap-range check. Both commands accept `--version`.

For a multi-lap run with LLM synthesis, select a configured provider and range:

```powershell
uv run f1-sim Sakhir NOR McLaren --laps 15-25 --provider lmstudio
```

LM Studio must be serving at the configured local endpoint. `--provider openai` uses the API and requires its key. `--rival VER` adds a rival column. The full option list is available with `uv run f1-sim --help`.

## Debug one agent

`scripts/debug_agent.py` builds a minimal `lap_state` and calls the selected `*_from_state` entry point. It does not run `RaceReplayEngine`; selecting `orchestrator` still runs N31 for that one state.

```powershell
uv run python scripts/debug_agent.py --agent situation --gp Melbourne --lap 20 --driver NOR --team McLaren
uv run python scripts/debug_agent.py --agent tire --gp Melbourne --lap 20 --driver NOR --team McLaren --override tyre_life=25 compound=MEDIUM position=3
```

Use `--print-state` to inspect the input. Radio and RAG agents take `--radio` and `--query`; RAG and the orchestrator require an LLM provider. Run `uv run python scripts/debug_agent.py --help` for all agents and options.

For the Arcade viewer, webapp, backend endpoints, or voice services, use the current setup in `INSTALL.md`. This guide does not document retired Streamlit or voice paths.
