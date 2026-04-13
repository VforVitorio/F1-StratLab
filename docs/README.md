# F1 Strategy Manager -- Developer Docs

Technical documentation for each `src/` module. Written for developers working on the codebase, not for end users.

## Modules

| Module | Status | Doc |
|---|---|---|
| `src/agents/` | done (v0.9) | [Multi-Agent Architecture](architecture.md) |
| `src/simulation/` | done (v0.9) | [Simulation Overview](simulation/overview.md) |
| `src/telemetry/frontend/` | done | [Frontend (Streamlit)](frontend.md) |
| `src/telemetry/backend/` | done | [Backend (FastAPI)](backend-api.md) |
| `src/rag/` | done | -- |

## Guides

| Guide | Description |
|---|---|
| [Setup and Deployment](setup-and-deployment.md) | Docker, local dev, environment variables |
| [Agents API Reference](agents-api-reference.md) | Entry points, output schemas, request/response models |
| [Driver Colors](driver-colors.md) | Year-aware color palette system (2023--2025) |
| [Frontend CSS Fixes](frontend-css-fixes.md) | Scroll fix, spinner removal, chart styling |

## Conventions

- **lap_state dict**: canonical data contract between simulation and agents. Schema in [simulation/overview.md](simulation/overview.md#data-boundary-architectural-constraint).
- **data/models/**: all trained model artifacts. Layout mirrors the agent that owns them.
- **data/raw/2025/<GP>/**: race parquets from FastF1. Each GP dir has `laps.parquet`, `weather.parquet`, `metadata.json`.
