<div align="center">

# F1 Strategy Manager

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/) [![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/) [![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-orange)](https://pytorch.org/) [![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-purple)](https://pandas.pydata.org/) [![XGBoost](https://img.shields.io/badge/XGBoost-1.7%2B-green)](https://xgboost.readthedocs.io/) [![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-blue)](https://opencv.org/) [![FastF1](https://img.shields.io/badge/FastF1-3.1%2B-red)](https://github.com/theOehrly/Fast-F1) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/VforVitorio/F1_Strat_Manager)

</div>

**Revolutionizing strategic decision-making in Formula 1 through AI-powered models, computer vision, and expert systems. For a deeper insight, see the project's [paper here](documents/docs_legacy_strat_manager/F1_Strategy_Manager_AI.pdf).**

<p align="center">
  <img
    src="documents/banner/f1_strat_manager_banner.jpeg"
    alt="Banner VforVitorio"
    style="width:85%; max-width:900px; aspect-ratio:21/9; border-radius:20px;"
  />
</p>

---

## Project Overview

In Formula 1, strategic decisions must be made within seconds while considering complex, dynamic variables like weather, tire wear, track position, and fuel. The **F1 Strategy Manager** project proposes a solution by integrating advanced predictive models and expert systems to support real-time strategy recommendations.

---

## Docs

> [!WARNING]
> **Documentation & Wiki**
>
> This repository has a wiki generated automatically with GitHub Actions, based on **DeepWiki**.
>
> However, the documentation on the **DeepWiki** page is much better structured and highly recommended for obtaining clearer and more navigable information about the project.
>
> Access the full documentation here: [https://deepwiki.com/VforVitorio/F1_Strat_Manager](https://deepwiki.com/VforVitorio/F1_Strat_Manager)

---

## Main Objective

Develop an **intelligent strategy recommender** that, based on processed race data, can offer optimized strategic decisions to the team in real time.

---

## Project Structure

```
F1_Strat_Manager/
├── src/                        # Production code
│   ├── telemetry/              # Main app (FastAPI + Streamlit submodule)
│   ├── strategy/               # ML models (lap time, tire degradation)
│   │   ├── models/
│   │   ├── training/
│   │   └── inference/
│   ├── agents/                 # Expert system + rules
│   │   └── rules/
│   ├── nlp/                    # Radio processing (sentiment, NER)
│   ├── vision/                 # Computer vision
│   └── shared/                 # Common utilities
│       └── data_extraction/
├── notebooks/                  # Experimentation
├── data/                       # Datasets by year/race
│   ├── raw/
│   ├── processed/
│   ├── models/
│   └── cache/
├── configs/                    # YAML configurations
├── legacy/                     # Old code reference
│   ├── notebooks/
│   └── app_streamlit_v1/
└── documents/                  # TFG documentation
```

### Data Extraction & Preparation

- **Sources**: FastF1, OpenF1, Roboflow
- **HuggingFace Hub**: The dataset is also available on HuggingFace: [F1 Strategy Dataset](https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset)
- **Data Types**:
  - Weather data
  - Track and race conditions
  - Team radio communications
  - Video frames (used for computer vision models)
- **Augmentation & Labelling**:
  - Enhanced image dataset using flips, rotation, blur, etc.
  - Manual labelling of radios (sentiment, intent, NER)
- **Pipeline**:
  - All data merged into a single structured DataFrame
  - Generated synthetic variables and filtered irrelevant ones
  - Divided data by stint and lap sequences

### Machine Learning Models

- **XGBoost (N06)** : Delta lap time prediction — MAE 0.392s on 2025 holdout
- **TCN + MC Dropout (N09/N10)** : Tire degradation with uncertainty quantification (P10/P50/P90)
- **LightGBM (N12)** : Overtake probability — AUC-PR 0.5491, AUC-ROC 0.8758
- **LightGBM (N14)** : Safety car probability — soft contextual prior, lift 1.67×
- **HistGradientBoosting (N15)** : Pit stop duration quantile regression P05/P50/P95 — MAE 0.487s
- **LightGBM (N16)** : Undercut success prediction — AUC-ROC 0.7708
- **YOLOv8** : Team identification from race footage with >90% mAP50
  > This section is no longer updated. Further development continues in an independent repository, now using YOLOv12.
  > See: [VforVitorio/F1_AI_team_detection](https://github.com/VforVitorio/F1_AI_team_detection)
- **RoBERTa + SetFit + BERT-large (N20/N21/N22)** : NLP pipeline — sentiment, intent classification, F1 entity recognition
- **Whisper ASR (N18)** : Team radio transcription

### Multi-Agent System (current development)

- Six specialised **LangGraph ReAct** sub-agents (N25–N30) coordinate under a Strategy Orchestrator (N31)
- Each agent wraps one or more ML models as `@tool`-decorated LangChain tools
- **N29 Radio Agent** uses an NLP-first synthesis pattern (N06-style) with **Pydantic v2** structured output
- **N30 RAG Agent** answers regulation questions via **Qdrant** vector search over FIA Sporting Regulations (2023–2025) with BGE-M3 embeddings
- **N31 Orchestrator** uses MoE-style dynamic routing, Monte Carlo simulation over probabilistic sub-agent outputs, and LLM synthesis with Pydantic structured output

### Expert System (legacy)

- Originally developed using the **Experta** framework (see `src/agents/` legacy code).
- Being replaced by the LangGraph multi-agent architecture described above.

### App Interface

- Built using **Streamlit**.
- Allows:
  - Model interaction per section (Vision, NLP, ML)
  - Visual exploration and graphing
  - Chatbot Q&A via LLM for post-race reports and image analysis using Llama3.2-vision

---

## Data & Model Weights

> [!NOTE]
> **Datasets and trained model weights are hosted on Hugging Face.**
>
> The `data/` directory (raw/processed datasets, FastF1 cache, labeled parquets) and all exported model weights (`data/models/`) are **not included in this repository** due to size constraints.
>
> If you need the data or the model weights, download them from the project's Hugging Face dataset repository:
>
> 👉 **[https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset](https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset)**

---

## Environment Setup & Usage

### Requirements

- Python 3.10 or 3.11 (NOT 3.12+ due to dependency compatibility)
- CUDA-compatible GPU (for local training and video inference)
- venv recommended

### Quick Setup

```bash
# 1. Clone repository with submodule
git clone --recursive https://github.com/VforVitorio/F1_Strat_Manager.git
cd F1_Strat_Manager

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. Install PyTorch with CUDA (RTX 50xx series need cu128)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 4. Install project
pip install -e ".[dev]"

# 5. Verify installation
python -c "from src.strategy.models import *; print('OK')"
```

### Running with Docker (Recommended)

The easiest way to run the telemetry application is using Docker Compose:

```bash
# Start backend and frontend services
docker-compose up

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

**Access the application:**

- Frontend (Streamlit): http://localhost:8501
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Running Locally (Development)

For development with hot reload:

```bash
# Terminal 1: Backend
cd src/telemetry
uvicorn backend.main:app --reload

# Terminal 2: Frontend
streamlit run src/telemetry/frontend/app/main.py
```

### Headless CLI (Multi-Agent Simulator)

A Rich-powered command line interface is bundled for running the full
multi-agent pipeline (N25–N31) lap by lap against a real race. It needs
**no HTTP layer, no Streamlit, no Docker** — just Python and the race data.

#### One-command install — recommended (uv)

The project is configured for [`uv`](https://docs.astral.sh/uv/), Astral's
Rust-based package manager that replaces `pip` + `venv` + `pipx` +
`virtualenv` and is **10–100× faster**. With `uv`, the entire install
collapses to a single command — `pyproject.toml` already routes torch /
torchvision to the right CUDA wheel per platform via `[tool.uv.sources]`,
so there is **no manual PyTorch step on Windows or Linux**:

```bash
# 0. Install uv once per machine — pick the line for your OS
#    Windows (PowerShell):
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
#    Linux / macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh
#    Or via package manager:
#       winget install astral-sh.uv     # Windows
#       brew   install uv               # macOS
#       pipx   install uv               # any OS that already has pipx

# 1. Clone + install in one shot
git clone --recursive https://github.com/VforVitorio/F1_Strat_Manager.git
cd F1_Strat_Manager
uv sync           # creates .venv, resolves cu128 torch on Win/Linux, CPU on macOS

# 2. Run the interactive launcher — no venv activation needed
uv run f1-strat
```

That's it. `uv sync` reads `pyproject.toml`, builds a fresh `.venv/`,
pulls every runtime dependency (`fastf1`, `xgboost`, `lightgbm`,
`langgraph`, `langchain-openai`, `rich`, `torch`, etc.) and exposes the
two console scripts as `uv run f1-strat` / `uv run f1-sim`.

> **GPU with a different CUDA?** Edit the `[[tool.uv.index]]` URL in
> `pyproject.toml` (currently `https://download.pytorch.org/whl/cu128`)
> to match your driver — e.g. `cu121`, `cu118`, `rocm6.2`. Then re-run
> `uv sync`.

#### Fallback install — pip + venv

If you cannot install `uv` (corporate restrictions, etc.), the legacy
pip flow still works but you must install PyTorch manually because
`pip` ignores `[tool.uv.sources]`:

```bash
git clone --recursive https://github.com/VforVitorio/F1_Strat_Manager.git
cd F1_Strat_Manager
python -m venv .venv
.venv\Scripts\activate                 # Windows
# source .venv/bin/activate            # Linux / macOS

# CUDA torch first (skip on macOS, or use cu118 / cu121 to match your driver)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# Then the project (pulls everything else from pyproject.toml)
pip install -e .

# Verify
f1-strat
```

If `python -m venv .venv` produces a venv without `pip` (rare, happens
on broken Python installs), recreate it with `python -m venv --upgrade-deps .venv`
or just use the `uv` flow above — `uv` builds its own venv from scratch.

#### What you get

Two console scripts become available on your PATH after installation:

| Command   | What it launches                                                        |
| --------- | ----------------------------------------------------------------------- |
| `f1-strat`| Interactive menu — pick race / driver / lap range / provider visually   |
| `f1-sim`  | Headless simulator — `f1-sim <gp_name> <driver> <team> [options]`       |

**Interactive launcher**

```bash
f1-strat
```

Walks you through race → driver → lap range → provider with keyboard
pickers, then runs `f1-sim` in a subprocess with a live lap-by-lap panel
and a final "Run complete" summary (positions, actions mix, agent
firings, stint, timing).

**Direct headless mode**

```bash
# LLM orchestrator off — only MC scores (fastest, no provider required)
f1-sim Melbourne NOR McLaren --laps 1-5 --no-llm

# LLM mode with OpenAI (reads OPENAI_API_KEY from .env)
f1-sim Bahrain NOR McLaren --laps 15-25 --provider openai

# LLM mode with LM Studio (local, OpenAI-compatible API on :1234)
f1-sim Monaco LEC Ferrari --laps 1-10 --provider lmstudio
```

Use `f1-sim --help` for the full option list (rival tracking, radio
cadence, year, custom parquet paths, verbose traceback, etc.).

### Troubleshooting

**Windows: DLL load failed (scikit-learn)**

```bash
# Add .venv/ folder to Windows Defender exclusions, then:
pip install --no-cache-dir --force-reinstall scikit-learn
```

**Python 3.10+ AttributeError: collections.Mapping**

```bash
# Ensure frozendict>=2.4.0 is installed
pip install --upgrade frozendict>=2.4.0
```

---

## About This Project

This is a **personal project** that will serve as my **Final Degree Project (Thesis)**. While this is primarily an academic endeavor, I welcome feedback, suggestions, and collaboration from the F1 and AI community.

If you'd like to report bugs, suggest features, or collaborate, please use the [Issue Templates](ISSUE_TEMPLATES.md) to ensure clear communication.
