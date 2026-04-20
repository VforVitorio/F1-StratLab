<div align="center">

# F1 Strategy Manager

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/) [![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/) [![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-orange)](https://pytorch.org/) [![FastF1](https://img.shields.io/badge/FastF1-3.1%2B-red)](https://github.com/theOehrly/Fast-F1) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/VforVitorio/F1_Strat_Manager)

**AI-powered race strategy toolkit — multi-agent orchestrator, 2D race replay with live strategy dashboard, and a post-race analytics UI.**

[Landing page](https://vforvitorio.github.io/f1stratlab-web/) · [Full documentation (DeepWiki)](https://deepwiki.com/VforVitorio/F1_Strat_Manager) · [Paper](documents/docs_legacy_strat_manager/F1_Strategy_Manager_AI.pdf) · [Hugging Face dataset](https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset)

</div>

<p align="center">
  <img
    src="documents/banner/f1_strat_manager_banner.jpeg"
    alt="F1 Strategy Manager banner"
    style="width:85%; max-width:900px; border-radius:20px;"
  />
</p>

---

## What it is

In Formula 1, strategic decisions must be made within seconds while juggling weather, tire wear, track position, and fuel. **F1 Strategy Manager** packages a multi-agent AI system (seven specialised agents coordinated by an orchestrator) plus a 2D race replay and a post-race analytics UI into a single repository. Data comes from FastF1 and OpenF1; models span XGBoost, TCN + MC Dropout, LightGBM, RoBERTa / SetFit / BERT-large, Whisper, and FIA RAG over Qdrant.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the one-page topology and [`docs/`](docs/) for the deep dives.

## Three surfaces, one codebase

| Surface | Command | When to use |
|---|---|---|
| **CLI** | `f1-sim VER Melbourne "Red Bull Racing" --year 2025` | Headless Rich-based live inference panel for a single race. |
| **Arcade** (primary live UI) | `f1-arcade --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing" --driver2 LEC --strategy` | Three-window 2D race replay + PySide6 strategy dashboard + live telemetry grid. No backend required. |
| **Streamlit** (post-race) | `docker compose up` *or* `f1-streamlit` | Analytics dashboard, chat Q&A, model lab, voice mode. Backed by FastAPI. |

## Install in 30 seconds

```bash
uv tool install "git+https://github.com/VforVitorio/F1_Strat_Manager.git"
```

All three console scripts land on your PATH. For full install options (Docker Compose for the Streamlit stack, pip fallback, data bootstrap, LM Studio local provider) see [`INSTALL.md`](INSTALL.md).

Requires Python 3.10 / 3.11 and an `OPENAI_API_KEY` (or `F1_LLM_PROVIDER=lmstudio` for a local server). Dataset (~15 GB of models + race parquets) downloads lazily from Hugging Face on first run.

## Project layout

- [`src/arcade/`](src/arcade/) — 2D race replay (pyglet) + PySide6 strategy dashboard
- [`src/agents/`](src/agents/) — multi-agent orchestrator (N25 → N31)
- [`src/simulation/`](src/simulation/) — `RaceReplayEngine` + `RaceStateManager`
- [`src/telemetry/`](src/telemetry/) — FastAPI backend + Streamlit post-race UI (git submodule)
- [`src/nlp/`](src/nlp/) — radio transcription + sentiment/intent/NER pipeline
- [`src/rag/`](src/rag/) — Qdrant retriever over FIA sporting regulations
- [`src/f1_strat_manager/`](src/f1_strat_manager/) — CLI infrastructure (data bootstrap, GP slug resolver)
- [`scripts/`](scripts/) — CLI entry points and maintenance tools
- [`docs/`](docs/) — architecture, API reference, arcade guides, draw.io diagrams

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev setup, code-style rules, and the untouchable-files list. Bug reports, feature ideas, and data anomalies go through the templates under [.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE/).

## Related

This project is part of a broader F1 AI suite:

- [F1 Strategy Manager (this repo)](https://github.com/VforVitorio/F1_Strat_Manager) — strategy engine
- [F1 AI Team Detection](https://github.com/VforVitorio/F1_AI_team_detection) — YOLOv12 team identification from race footage
- [F1 Strategy Dataset (Hugging Face)](https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset) — trained weights and processed race data

## About

**Final Degree Project (Trabajo Fin de Grado)** — Fourth year, Grado en Ingeniería de Sistemas Inteligentes. Feedback, suggestions and contributions are welcome via the issue templates.

---

> **Disclaimer — no copyright infringement intended.** Formula 1, F1, and related marks are trademarks of Formula One Licensing B.V. and are used here for reference only. All race data is sourced from public APIs (FastF1, OpenF1) and is used strictly for educational and non-commercial purposes. This project is not affiliated with, endorsed by, or in any way officially connected to Formula 1, the FIA, or any F1 team.
