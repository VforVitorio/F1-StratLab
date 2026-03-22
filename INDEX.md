# F1 Strategy Manager — Project Index

_Revolutionising strategic decision-making in Formula 1 through AI-powered predictive models, computer vision, NLP radio analysis, and a multi-agent expert system._

The project integrates several ML stacks — XGBoost/LightGBM for race strategy signals, a TCN for tyre degradation, Whisper + BERT for radio communications, and YOLOv8 for team identification — into a unified **Strategy Orchestrator** that produces real-time race recommendations. A companion telemetry app (FastAPI + Streamlit) exposes the models interactively.

The current development phase (N25–N31) replaces the legacy Experta rule engine with a **LangGraph multi-agent architecture**: specialised sub-agents (pace, tyre, overtake, safety car, pit strategy, radio NLP, regulation RAG) coordinate under a Supervisor Orchestrator.

> For full documentation see the [README](README.md) and the [DeepWiki](https://deepwiki.com/VforVitorio/F1_Strat_Manager). For the project paper: [F1_Strategy_Manager_AI.pdf](documents/docs_legacy_strat_manager/F1_Strategy_Manager_AI.pdf).

Notebooks are the primary development artefact. `src/` modules are extracted from notebooks only when they need to be imported by other notebooks or the telemetry app.

---

## Quick Start / Navigation Guide

| Goal                         | Entry point                                                                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Download raw race data       | [`scripts/download_data.py`](scripts/download_data.py)                                                                                                              |
| Download FIA regulation PDFs | [`scripts/download_fia_pdfs.py`](scripts/download_fia_pdfs.py)                                                                                                      |
| Build RAG vector index       | [`scripts/build_rag_index.py`](scripts/build_rag_index.py)                                                                                                          |
| Full data pipeline           | N01 → N02 → N03 → N04                                                                                                                                               |
| Strategy ML models           | N05-N06 (pace) → N07-N10 (tires) → N11-N16 (overtake / SC / pit)                                                                                                    |
| NLP pipeline for radio       | N17-N24                                                                                                                                                             |
| Multi-agent system           | N25 (Pace) → N30 (RAG) → N26-N29 → N31 (Orchestrator)                                                                                                               |
| Query RAG at runtime         | [`src/rag/retriever.py`](src/rag/retriever.py) — `RagRetriever` + `query_rag_tool`                                                                                  |
| Telemetry web app            | [`src/telemetry/backend/main.py`](src/telemetry/backend/main.py) (FastAPI) + [`src/telemetry/frontend/app/main.py`](src/telemetry/frontend/app/main.py) (Streamlit) |

---

## Notebooks

### Data Engineering (`notebooks/data_engineering/`)

| Notebook                                                                                  | Description                                                                                                                                                   |
| ----------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N01_data_download.ipynb](notebooks/data_engineering/N01_data_download.ipynb)             | Downloads 46 GPs (2023-2024) from FastF1 and OpenF1 APIs; outputs raw parquets under `data/raw/`                                                              |
| [N02_eda_master.ipynb](notebooks/data_engineering/N02_eda_master.ipynb)                   | Global EDA across all 46 GPs — lap time distributions, data quality audit, cross-season patterns                                                              |
| [N03_circuit_clustering.ipynb](notebooks/data_engineering/N03_circuit_clustering.ipynb)   | K-means clustering of circuits into 4 archetypes (street / high-speed / technical / balanced); produces `circuit_clusters_k4.parquet`                         |
| [N04_feature_engineering.ipynb](notebooks/data_engineering/N04_feature_engineering.ipynb) | Full feature engineering pipeline from raw parquets to `laps_featured_<year>.parquet`; integrates interval gaps, cluster assignments, and anti-drift features |

### Lap Time Prediction (`notebooks/strategy/lap_time_prediction/`)

| Notebook                                                                                  | Description                                                                                        |
| ----------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| [N05_laptime_eda.ipynb](notebooks/strategy/lap_time_prediction/N05_laptime_eda.ipynb)     | EDA for the lap time model — concept drift analysis across seasons, feature selection for N06      |
| [N06_laptime_model.ipynb](notebooks/strategy/lap_time_prediction/N06_laptime_model.ipynb) | XGBoost delta-lap-time predictor; MAE 0.392 s on 2025 test set; exports to `data/models/lap_time/` |

### Tire Degradation (`notebooks/strategy/tire_degradation/`)

| Notebook                                                                                                           | Description                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N07_tiredeg_eda.ipynb](notebooks/strategy/tire_degradation/N07_tiredeg_eda.ipynb)                                 | EDA of tire degradation patterns by compound, stint length, and circuit — informs TCN architecture choices                                                     |
| [N08_tiredeg_sequence_config.ipynb](notebooks/strategy/tire_degradation/N08_tiredeg_sequence_config.ipynb)         | Analytical determination of optimal TCN window size per compound from empirical stint length distributions                                                     |
| [N09_tiredeg_tcn.ipynb](notebooks/strategy/tire_degradation/N09_tiredeg_tcn.ipynb)                                 | Global Causal TCN that predicts `FuelAdjustedDegAbsolute` (cumulative seconds lost to rubber wear) one step ahead; exports `tiredeg_modelA_v4.pt`              |
| [N10_tiredeg_compound_finetuning.ipynb](notebooks/strategy/tire_degradation/N10_tiredeg_compound_finetuning.ipynb) | Per-compound fine-tuning of the N09 global TCN (C1-C5); MC Dropout uncertainty + Platt calibration; exports compound models to `data/models/tire_degradation/` |

### Overtake Probability (`notebooks/strategy/overtake_probability/`)

| Notebook                                                                                     | Description                                                                                                                                                 |
| -------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N11_overtake_eda.ipynb](notebooks/strategy/overtake_probability/N11_overtake_eda.ipynb)     | Builds the labeled car-pair dataset (28,494 pairs, 2023-2025); EDA of overtake rates by DRS window, gap, pace delta                                         |
| [N12_overtake_model.ipynb](notebooks/strategy/overtake_probability/N12_overtake_model.ipynb) | LightGBM binary classifier for P(overtake\| lap state); AUC-PR 0.5491 / AUC-ROC 0.8758; exports to `data/models/overtake_probability/`                      |
| [N12B_overtake_tcn.ipynb](notebooks/strategy/overtake_probability/N12B_overtake_tcn.ipynb)   | **Archived negative result** — Causal TCN on 8-lap battle sequences; AUC-PR ~0.10 vs LightGBM 0.55; confirms feature-engineered N12 is the production model |

### Safety Car Probability (`notebooks/strategy/sc_probability/`)

| Notebook                                                                   | Description                                                                                                                                                                                     |
| -------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N13_sc_eda.ipynb](notebooks/strategy/sc_probability/N13_sc_eda.ipynb)     | Builds the labeled race-lap dataset (3,275 rows) for SC prediction; EDA of deployment rates, circuit-level base rates, and feature correlations                                                 |
| [N14_sc_model.ipynb](notebooks/strategy/sc_probability/N14_sc_model.ipynb) | LightGBM SC probability classifier (3-lap window); AUC-PR 0.0723 vs baseline 0.0432; framed as a soft contextual prior for the Strategy Agent; exports to `data/models/safety_car_probability/` |

### Pit Stop Prediction (`notebooks/strategy/pit_prediction/`)

| Notebook                                                                           | Description                                                                                                                                                            |
| ---------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N15_pit_duration.ipynb](notebooks/strategy/pit_prediction/N15_pit_duration.ipynb) | HistGBT quantile regression (P05/P50/P95) for physical pit stop time; P50 MAE 0.487 s; exports three quantile models to `data/models/pit_prediction/`                  |
| [N16_undercut.ipynb](notebooks/strategy/pit_prediction/N16_undercut.ipynb)         | LightGBM binary classifier for undercut success (driver X gains net position after pit sequence); AUC-PR 0.6739 (1.95× lift); exports to `data/models/pit_prediction/` |

### NLP — Radio Analysis (`notebooks/nlp/`)

| Notebook                                                                     | Description                                                                                                                                            |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [N17_radio_labeling.ipynb](notebooks/nlp/N17_radio_labeling.ipynb)           | Manual labeling of F1 team radio messages (sentiment + intent); filters out post-race messages                                                         |
| [N18_radio_transcription.ipynb](notebooks/nlp/N18_radio_transcription.ipynb) | Transcribes raw radio audio files to text using OpenAI Whisper ASR; outputs `radios_raw.csv`                                                           |
| [N19_sentiment_vader.ipynb](notebooks/nlp/N19_sentiment_vader.ipynb)         | NLTK VADER lexicon-based sentiment baseline; benchmarked against N17 ground truth                                                                      |
| [N20_bert_sentiment.ipynb](notebooks/nlp/N20_bert_sentiment.ipynb)           | Fine-tunes `roberta-base` on labeled radio messages for 3-class sentiment; 87.5% test accuracy                                                         |
| [N21_radio_intent.ipynb](notebooks/nlp/N21_radio_intent.ipynb)               | Intent classification (5 classes) via SetFit + ModernBERT; includes back-translation augmentation and a documented DeBERTa-v3-large negative result    |
| [N22_ner_models.ipynb](notebooks/nlp/N22_ner_models.ipynb)                   | F1-domain NER on short radio transcriptions; BERT-large CoNLL-03 BIO token classifier (F1 = 0.42); documents GLiNER zero-shot and fine-tuning failures |
| [N23_rcm_parser.ipynb](notebooks/nlp/N23_rcm_parser.ipynb)                   | Rule-based structured event extractor for FastF1 `race_control_messages`; deterministic, no ML required                                                |
| [N24_nlp_pipeline.ipynb](notebooks/nlp/N24_nlp_pipeline.ipynb)               | Unified inference pipeline merging N20-N23: sentiment + intent + NER + RCM parsing; GPU P95 latency 59.4 ms; exports `pipeline_config_v1.json`         |

### Agents (`notebooks/agents/`)

| Notebook                                                      | Description                                                                                                                                                                                 |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [N25_pace_agent.ipynb](notebooks/agents/N25_pace_agent.ipynb) | Pace Agent — wraps the N06 XGBoost model into a LangGraph ReAct agent; returns `PaceOutput` (lap time prediction + delta signals + bootstrap CI); first of seven sub-agents                 |
| [N30_rag_agent.ipynb](notebooks/agents/N30_rag_agent.ipynb)   | RAG Agent — retrieval-augmented generation over FIA Sporting and Technical Regulations (2023-2025) via local Qdrant; returns structured `RegulationContext` objects with article references |

> Notebooks N26 (Tire), N27 (Race Situation), N28 (Pit Strategy), N29 (Radio), and N31 (Orchestrator) are planned but not yet developed.

---

## Source Modules

### `src/rag/`

| File                                           | Description                                                                                                                                         |
| ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| [src/rag/retriever.py](src/rag/retriever.py)   | `RagRetriever` class (Qdrant client + BGE-M3 encoder) and `query_rag_tool` LangChain tool; requires the index built by `scripts/build_rag_index.py` |
| [src/rag/\_\_init\_\_.py](src/rag/__init__.py) | Package init                                                                                                                                        |

### `src/agents/` (legacy)

| File                                                         | Description                                                                                                                    |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| [src/agents/base_agent.py](src/agents/base_agent.py)         | `Fact` subclasses (`TelemetryFact`, `DegradationFact`, `GapFact`, `RadioFact`, `RaceStatusFact`) for the `experta` rule engine |
| [src/agents/strategy_agent.py](src/agents/strategy_agent.py) | Legacy rule-based Strategy Agent integrating tire / lap time / radio / gap rule sets via `experta`; will be replaced after N31 |

### `src/nlp/` (legacy)

| File                                                       | Description                                                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| [src/nlp/pipeline.py](src/nlp/pipeline.py)                 | Legacy jupytext-exported NLP pipeline (pre-N24); uses old model paths and `roberta-large` intent model — superseded by N24 |
| [src/nlp/ner.py](src/nlp/ner.py)                           | NER inference wrapper                                                                                                      |
| [src/nlp/sentiment.py](src/nlp/sentiment.py)               | Sentiment inference wrapper                                                                                                |
| [src/nlp/radio_classifier.py](src/nlp/radio_classifier.py) | Radio intent classification wrapper                                                                                        |

### `src/strategy/`

| File                                                                                           | Description                                          |
| ---------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| [src/strategy/models/lap_time_model.py](src/strategy/models/lap_time_model.py)                 | Jupytext-exported lap time model module              |
| [src/strategy/models/tire_degradation_model.py](src/strategy/models/tire_degradation_model.py) | Jupytext-exported tire degradation model module      |
| [src/strategy/inference/tire_predictor.py](src/strategy/inference/tire_predictor.py)           | Jupytext-exported tire degradation inference wrapper |

### `src/telemetry/`

A separate full-stack web application for live telemetry visualisation, independent of the agent notebooks.

| Component                                                                | Description                                                                                                             |
| ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------- |
| [src/telemetry/backend/main.py](src/telemetry/backend/main.py)           | FastAPI application entry point; mounts endpoints for telemetry, circuit domination, driver comparison, chat, and voice |
| `src/telemetry/backend/api/`                                             | Versioned API route handlers (`telemetry`, `comparison`, `chatbot`, `voice`)                                            |
| `src/telemetry/backend/services/`                                        | Business logic:`telemetry_service.py`, `comparison_service.py`, and sub-services for telemetry and voice                |
| [src/telemetry/frontend/app/main.py](src/telemetry/frontend/app/main.py) | Streamlit multi-page app entry point (dashboard, comparison, chat pages)                                                |
| `src/telemetry/frontend/app/pages/`                                      | Individual Streamlit pages                                                                                              |
| `src/telemetry/frontend/app/components/`                                 | Reusable UI components (auth, layout, navbar)                                                                           |

### `src/data_extraction/`

| File                                                                                               | Description                                      |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| [src/data_extraction/data_extraction.py](src/data_extraction/data_extraction.py)                   | FastF1 / OpenF1 extraction helpers               |
| [src/data_extraction/extract_openf1_intervals.py](src/data_extraction/extract_openf1_intervals.py) | Extracts inter-car interval data from OpenF1 API |
| [src/data_extraction/video_extraction.py](src/data_extraction/video_extraction.py)                 | Video frame extraction utilities                 |
| [src/data_extraction/data_augmentation.py](src/data_extraction/data_augmentation.py)               | Data augmentation helpers                        |

---

## Scripts

| Script                                                       | Description                                                                                                                       |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------- |
| [scripts/download_data.py](scripts/download_data.py)         | Downloads the full raw + processed dataset from Hugging Face Hub (`VforVitorio/f1-strategy-dataset`)                              |
| [scripts/download_fia_pdfs.py](scripts/download_fia_pdfs.py) | Scrapes and downloads FIA Sporting and Technical Regulation PDFs (2023-2025) into `data/rag/documents/`; falls back to known URLs |
| [scripts/build_rag_index.py](scripts/build_rag_index.py)     | One-shot ingestion: PDF → article chunks → BGE-M3 embeddings → local Qdrant collection; idempotent (hash-based deduplication)     |
