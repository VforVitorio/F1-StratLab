# F1 StratLab — Developer Docs

Technical documentation for each `src/` module. Written for developers working on the codebase, not for end users.

## Modules

| Module | Status | Doc |
|---|---|---|
| `src/agents/` | done (v0.9) | [Multi-Agent Architecture](architecture.md) |
| `src/simulation/` | done (v0.9) | [Simulation Overview](simulation/overview.md) |
| `src/arcade/` | done (Phase 3.5) | [Arcade Dashboard](arcade/dashboard.md) |
| `src/telemetry/frontend/` | done | [Streamlit Frontend](streamlit-frontend.md) |
| `src/telemetry/backend/` | done | [Backend (FastAPI)](backend-api.md) |
| `src/rag/` | done | -- |

## Guides

| Guide | Description |
|---|---|
| [Agents API Reference](agents-api-reference.md) | Entry points, output schemas, request/response models |
| [Arcade Quick Start](arcade/quick-start.md) | One-command launch of the 3-window arcade MVP |
| [Arcade Dashboard Architecture](arcade/dashboard.md) | PySide6 package layout, wire protocol, thread model |
| [Arcade Strategy Pipeline](arcade/strategy-pipeline.md) | Why the arcade duplicates the N31 orchestrator body |
| [Setup and Deployment](setup-and-deployment.md) | Docker, local dev, environment variables |
| [Driver Colors](driver-colors.md) | Year-aware color palette system (2023--2025) |
| [Diagrams](diagrams/README.md) | Index of draw.io sources (architecture, data flow, sequences) |

## Conventions

- **lap_state dict**: canonical data contract between simulation and agents. Schema in [simulation/overview.md](simulation/overview.md#data-boundary-architectural-constraint).
- **data/models/**: all trained model artifacts. Layout mirrors the agent that owns them.
- **data/raw/2025/<GP>/**: race parquets from FastF1. Each GP dir has `laps.parquet`, `weather.parquet`, `metadata.json`.
