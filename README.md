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
- **HuggingFace Hub**: The dataset is also available on HuggingFace for easy download: [F1 Strategy Dataset](https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset)
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

- **XGBoost** : Lap time prediction with MAE = 0.09s and RMSE = 0.15s
- **TCN (Temporal Convolutional Networks)** : For tire degradation modeling
- **YOLOv8** : Team identification from race footage with >90% mAP50
  > This section is no longer updated. Further development continues in an independent repository, now using YOLOv12.
  > See: [VforVitorio/F1_AI_team_detection](https://github.com/VforVitorio/F1_AI_team_detection)
- **Whisper Turbo + BERT** : NLP pipeline for radio communication analysis

### Expert System

- Developed using the **Experta** framework.
- Integrates all processed data and model results for strategy suggestion.

### App Interface

- Built using **Streamlit**.
- Allows:
  - Model interaction per section (Vision, NLP, ML)
  - Visual exploration and graphing
  - Chatbot Q&A via LLM for post-race reports and image analysis using Llama3.2-vision

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
