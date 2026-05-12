---
hide:
  - navigation
  - toc
---

<div class="stratlab-hero" markdown>
  <span class="eyebrow">F1 StratLab · Documentation</span>
  # AI for real-time F1 race strategy
  <p>Open-source multi-agent system that fuses seven ML models, six LangGraph sub-agents and one strategy orchestrator into a single Formula 1 strategy recommender. This site is the technical reference for the codebase.</p>
  <div class="stratlab-hero-cta">
    <a class="md-button" href="getting-started/">Get started</a>
    <a class="md-button md-button--secondary" href="https://f1stratlab.com/">Visit landing</a>
    <a class="md-button md-button--secondary" href="https://github.com/VforVitorio/F1-StratLab">View on GitHub</a>
  </div>
</div>

## What lives here

<div class="stratlab-grid" markdown>

<div class="stratlab-card" markdown>
### Architecture
End-to-end view of how the seven ML models, six sub-agents and the N31 orchestrator connect. Includes the data contract (`lap_state`) that crosses every layer.

[Open ->](architecture.md)
</div>

<div class="stratlab-card" markdown>
### Multi-agent system
Pace, Tire, Race Situation, Pit Strategy, Radio, RAG. Each agent's entry point, output schema and request / response model, ready to call from your own pipelines.

[Open ->](agents-api-reference.md)
</div>

<div class="stratlab-card" markdown>
### Simulation engine
Lap-by-lap replay engine that drives the agents during development. Covers the `RaceReplayEngine`, `RaceStateManager` and the canonical `lap_state` schema.

[Open ->](simulation/overview.md)
</div>

<div class="stratlab-card" markdown>
### Arcade dashboard
Three-window PySide6 + pyglet experience that ships the live strategy view. Quick-start, dashboard layout and the local strategy pipeline that bypasses the backend.

[Open ->](arcade/quick-start.md)
</div>

<div class="stratlab-card" markdown>
### Backend API
FastAPI routers, SSE streaming endpoint and the simulator entry point used by Streamlit and the arcade. Includes auth-removal notes and CORS expectations.

[Open ->](backend-api.md)
</div>

<div class="stratlab-card" markdown>
### Streamlit frontend
Tab-by-tab walkthrough of the Streamlit app: race analysis, chat with charts, MCP integration and voice. Read alongside the backend API for the full pipeline.

[Open ->](streamlit-frontend.md)
</div>

</div>

## External companions

<div class="stratlab-grid" markdown>

<div class="stratlab-card" markdown>
### Landing
The public-facing site with the hero animation, agent gallery and project narrative aimed at non-technical visitors.

[Open f1stratlab.com ->](https://f1stratlab.com/)
</div>

<div class="stratlab-card" markdown>
### DeepWiki
Auto-generated codebase wiki with deep-linked summaries of every file. Best for ad-hoc "where does X live" questions.

[Open DeepWiki ->](https://deepwiki.com/VforVitorio/F1-StratLab)
</div>

<div class="stratlab-card" markdown>
### Releases
Every published wheel and source distribution, plus the release notes for v1.0.0 onwards and the changelog seeded retroactively to v0.6.

[Open releases ->](https://github.com/VforVitorio/F1-StratLab/releases)
</div>

</div>

## Install the latest release

```bash
uv pip install https://github.com/VforVitorio/F1-StratLab/releases/download/v1.1.0/f1_strat_manager-1.1.0-py3-none-any.whl
```

Then run any of the console entry points:

```bash
f1-strat       # interactive launcher
f1-sim         # headless CLI simulation
f1-arcade      # three-window arcade experience
f1-streamlit   # Streamlit dashboards
```

See [Setup and deployment](setup-and-deployment.md) for the full installation matrix (Windows, Linux, macOS, Docker).

## Project status

| Component | Version | Status |
|---|---|---|
| Multi-agent orchestrator (N31) | v1.0.0 | shipped |
| Arcade three-window MVP | v1.0.0 | shipped |
| Benchmark suite (Chapter 5) | v1.1.0 | shipped |
| Release automation (`release-please`) | v1.1.0 | shipped |

The current focus is documentation polish for the thesis defence; see the [project changelog](https://github.com/VforVitorio/F1-StratLab/blob/main/CHANGELOG.md) for the full history.
