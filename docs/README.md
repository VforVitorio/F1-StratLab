# F1 Strategy Manager — Developer Docs

Technical documentation for each `src/` module. Written for developers working on the codebase, not for end users.

## Modules

| Module | Status | Doc |
|---|---|---|
| `src/simulation/` | done (v0.9) | [overview](simulation/overview.md) |
| `src/agents/` | done (v0.9) | [README](../src/agents/README.md) |
| `src/rag/` | done | — |
| `src/api/` | planned (Step 9) | — |

## Conventions

- **lap_state dict**: canonical data contract between simulation and agents. Schema in [simulation/overview.md](simulation/overview.md#lap_state-schema).
- **data/models/**: all trained model artifacts. Layout mirrors the agent that owns them.
- **data/raw/2025/<GP>/**: race parquets from FastF1. Each GP dir has `laps.parquet`, `weather.parquet`, `metadata.json`.
