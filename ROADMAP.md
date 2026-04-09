# Roadmap

**F1 Digital Twin Multi-Agent System - Final Degree Project**

Timeline: 18 weeks (Feb 3 - Jun 20, 2025)

---

## Overview

This project develops an intelligent multi-agent system for real-time Formula 1 telemetry analysis and race strategy optimization. The system integrates streaming telemetry via Kafka, five ML predictive models with circuit clustering, a coordinated multi-agent architecture using LangGraph, and RAG-based FIA regulation knowledge.

**Key Technologies:** Apache Kafka, FastAPI, XGBoost, PyTorch, LangGraph, Qdrant, Streamlit, Arcade

---

## Release Strategy

Development follows an incremental approach. v0.1–v0.5 covered project setup and integration; v0.6 closed out the data engineering phase; v0.7–v0.8.2 built the ML and NLP foundations; v0.9–v0.11 delivered the multi-agent system, RAG, and CLI distribution.

**Three-release distribution model (v0.12+):** The project ships as three independent artifacts because each has different distribution mechanics:
- **R1 — CLI wheel** (`f1-strat`, `f1-sim`): pip-installable wheel on GitHub Releases, lazy HF data download
- **R2 — Arcade**: container deploy for interactive race replay visualization
- **R3 — Streamlit + Backend**: Docker Compose (FastAPI + Streamlit + Qdrant + LM Studio) or Streamlit Cloud

---

## v0.1–v0.5 - Integration & Setup

- [X] **Status:** Completed
- [X] **Release Date:** Feb 5, 2025

Integrated F1_Telemetry_Manager submodule and established modular project structure. Set up Docker Compose orchestration and configured base YAML configs for models, Kafka, and logging. Incremental releases covered submodule wiring, package setup, FastAPI verification, and base configuration.

**Note:** WebSocket streaming deferred to v0.12.0 (Interfaces). REST API endpoints are sufficient for ML development phases.

**Deliverables:**

- [X] Modular repository structure with src/, notebooks/, data/, legacy/
- [X] Submodule integration preserving existing telemetry backend
- [X] Python package setup with editable install
- [X] Data organization by year/race hierarchy
- [X] Base Docker Compose configuration
- [X] FastAPI backend verification (7 endpoint categories operational)

**Success Criteria:**

- [X] Clean imports from src modules
- [X] Docker Compose successfully launches base services
- [X] Project installable via pip install -e .
- [X] REST API endpoints verified and documented

---

## v0.6.0 - Data Engineering Pipeline

- [X] **Status:** Completed
- [X] **Release Date:** February 2025

Closed out the full data engineering phase. From raw FastF1 telemetry to a clean, feature-rich dataset ready to feed into the ML models. Previous notebooks moved to `legacy/`; new structure built around TFG architecture.

**Goals:**

- [X] Download and organize 2023-2025 seasons data (N01 — extended to 2025, Miami/Barcelona alias fixes)
- [X] Master EDA: data exploration, cleaning, validation
- [X] Circuit clustering using K-Means k=4, fitted on 2023–2024, serialized with joblib; 2025 inference via `kmeans.predict()` without refit (N03)
- [X] Feature engineering: 48-column dataset, ~45k clean racing laps; fuel-corrected degradation, sequential lap features, rolling 3-lap degradation, race context, circuit cluster merge (N04)
- [X] 2025 saved as held-out test set — never touches training data

**Deliverables:**

- [X] Clean datasets in data/processed/ (2023, 2024, 2025 separate)
- [X] Circuit clusters defined and validated (`circuit_clusters_k4.parquet`, 25 circuits, 0 unknowns on 2023–2025)
- [X] notebooks/data_engineering/ with all EDA and pipeline notebooks
- [X] Dataset published to HuggingFace Hub (`VforVitorio/f1-strategy-dataset`)

**Success Metrics:**

- [X] All GPs downloaded and validated (2023–2025)
- [X] 4 circuit clusters identified with clear characteristics
- [X] Data quality checks pass (no missing critical fields)
- [X] Feature engineering pipeline reproducible

---

## v0.7.0 - ML Foundation: Lap Time & Tire Degradation

- [X] **Status:** Completed
- [X] **Release Date:** March 2025
- [X] **Critical Milestone**

Developed and trained the first two ML models: lap time prediction (XGBoost) and tire degradation (TCN + MC Dropout). All experimentation in notebooks, models exported to `data/models/`.

**Lap Time Predictor (N06):**

- [X] EDA and data exploration
- [X] XGBoost delta-lap-time model with circuit clustering features
- [X] Hyperparameter tuning via GridSearch / cross-validation
- [X] Model exported to `data/models/lap_time/`
- [X] Target: MAE <0.5s — **Achieved: MAE 0.392s on 2025 test data** ✅

**Tire Degradation Predictor (N07–N10):**

- [X] EDA and degradation analysis (N07, N08)
- [X] TCN (Temporal Convolutional Network) architecture in PyTorch (N09)
- [X] Per-compound fine-tuning (SOFT / MEDIUM / HARD)
- [X] MC Dropout for uncertainty quantification (N=50 forward passes)
- [X] Calibration JSON exported alongside model weights
- [X] Model exported to `data/models/tire_degradation/`
- [ ] Target R² >0.85 — *pending formal evaluation on 2025 holdout*

**Important Note - Tire Compound Mapping:**
Current data (FastF1/OpenF1) only provides relative compound names (SOFT/MEDIUM/HARD) per race. For accurate degradation predictions, actual Pirelli compounds (C1-C5) are critical since the same "MEDIUM" can be C2 (harder) or C4 (softer) depending on circuit. Future enhancement: manual mapping from [Pirelli press releases](https://press.pirelli.com) into `data/tire_compounds_by_race.json`.

**Success Metrics:**

- [X] Lap Time: MAE 0.392s on 2025 (target <0.5s ✅ / stretch <0.3s ⬜)
- [X] Tire Degradation model operational with MC Dropout uncertainty
- [X] All experiments documented in notebooks/strategy/

---

## v0.8.0 - Additional Predictors

- [X] **Status:** Completed
- [X] **Release Date:** April 2025

Expand ML capabilities with additional prediction models for overtake probability and safety car deployment. Sector time predictor descoped (no meaningful contribution over N06 delta model for the Strategy Agent).

**Sector Time Predictor:**

- [ ] ~~Descoped~~ — does not add value over lap delta model for Strategy Agent use case

**Overtake Probability (N11 + N12):**

- [X] EDA and overtake pattern analysis — `N11_overtake_eda.ipynb`
- [X] 28,494 labeled pairs (2023–2025), gap ≤ 2.5s, 8.44% positive rate
- [X] LightGBM binary classifier, Optuna hyperparameter search
- [X] Platt calibration on 2024 validation set
- [X] Window simulation: P(overtake in N laps) = 1 − ∏(1 − Pₖ)
- [X] Model exported to `data/models/overtake_probability/`
- [X] Labeled dataset published to HuggingFace Hub
- [X] **Achieved: AUC-PR 0.5491, AUC-ROC 0.8758, threshold 0.80** ✅

**Safety Car Probability (N13 + N14):**

- [X] Dataset construction — `N13_sc_eda.ipynb`
  - 58 races loaded, 3,275 labeled race-lap rows; SC+VSC: 6.6% of all laps
  - Sources: `session.laps` + `session.track_status` + `session.race_control_messages`
  - Three SC targets built: `sc_within_3_laps` (3.5%), `sc_within_5_laps` (5.6%), `sc_within_7_laps` (7.5%)
  - `circuit_sc_rate` added as historical prior per circuit
  - Dataset exported: `data/processed/sc_labeled/sc_labeled_2023_2025.parquet` (43 cols, 3,275 rows)
- [X] LightGBM binary classifier + Optuna + Platt calibration — `N14_sc_model.ipynb`
  - **Achieved: AUC-PR 0.0723 (baseline 0.0432, lift 1.67×), AUC-ROC 0.6411** ✅
  - Target selected: `sc_within_3_laps` (best lift vs 5-lap 1.44×, 7-lap 1.29×)
  - Threshold (F2): 0.234 | F2=0.2537 | Precision=0.08 | Recall=0.56
  - SHAP top: lap_time_std_z > tyre_life_max > track_temp > circuit_sc_rate > air_temp
  - Framing: **soft contextual prior** for Strategy Agent, not deterministic SC predictor
- [X] Model exported to `data/models/safety_car_probability/`
  - `lgbm_sc_v1.pkl` + `calibrator_sc_v1.pkl` + `feature_list_v1.json`

**Success Metrics:**

- [X] Overtake: AUC-PR 0.5491, AUC-ROC 0.8758 (train 2023+2024 / test 2025) ✅
- [X] Safety Car: AUC-PR 0.0723, lift 1.67× over baseline, AUC-ROC 0.6411 ✅ (reframed as soft prior)
- [X] Per-cluster performance validated on 2025 test data (overtake) ✅

---

## v0.8.1 - Extended ML Models

- [X] **Status:** Completed
- [X] **Release Date:** March 2026

Additional predictive models extending the ML foundation: pit stop duration quantile regression and undercut success classification. Causal TCN alternative archived as negative result.

**Battle Outcome Temporal — Causal TCN (N12B) — Negative Result:**

- [X] Causal TCN implemented and trained — `notebooks/strategy/overtake_probability/N12B_overtake_tcn.ipynb`
- [X] **Result: negative** — AUC-PR ~0.10 vs N12 LightGBM 0.5491
- [X] Root cause: N12 already encodes temporal signal via `pace_delta_rolling3` / `gap_trend`; TCN cannot rediscover what is already explicit on ~18k sequences
- [X] **N12 LightGBM remains production model.** N12B archived as documented negative result — valid finding: explicit feature engineering dominates raw sequence modeling on small datasets.

**Pit Stop Duration — Quantile Regression (N15):**

- [X] EDA integrated in same notebook
- [X] **Model:** `sklearn.HistGradientBoostingRegressor(loss='quantile')` × 3 fits (P05/P50/P95)
- [X] Target: `physical_stop_est` [2.0–4.5s] — physical stop only, pit lane traversal subtracted per circuit
- [X] Features: team, year, tyre_life_in, lap_number, compound_id, compound_change, under_sc, tight_pit_box, team_year_median
- [X] Notebook: `notebooks/strategy/pit_prediction/N15_pit_duration.ipynb`
- [X] Export: `data/models/pit_prediction/hist_pit_p05/p50/p95_v1.pkl` + `model_config.json`
- [X] **Achieved: P50 MAE 0.487s vs baseline 0.555s** ✅

**Undercut Success Predictor (N16):**

- [X] Label: driver X pits before rival Y (≤5 laps) → X gains position after pit sequence = success
- [X] Dataset: 1,032 labeled pairs (2023–2025), DRY_COMPOUNDS only (SOFT/MEDIUM/HARD)
- [X] **Model:** LightGBM binary (same architecture as N12/N14) + Platt calibration
- [X] Features (13): pos_gap_at_pit, pace_delta, tyre_life_diff, circuit_undercut_rate, lap_race_pct, compound_x/y_id, compound_delta, pit_duration_delta, circuit_undercut_rate (target enc), team_x_undercut_rate (target enc)
- [X] SHAP top: pos_gap_at_pit > pace_delta > circuit_undercut_rate > tyre_life_diff
- [X] Notebook: `notebooks/strategy/pit_prediction/N16_undercut.ipynb`
- [X] Export: `data/models/pit_prediction/lgbm_undercut_v1.pkl` + `calibrator_undercut_v1.pkl` + `model_config_undercut_v1.json`
- [X] **Achieved: AUC-PR 0.6739, AUC-ROC 0.7708, threshold 0.522** ✅

**Success Metrics:**

- [X] N12B Causal TCN: archived — AUC-PR ~0.10, N12 production model unchanged ✅
- [X] N15 Pit Duration: P50 MAE 0.487s (target <0.5s ✅)
- [X] N16 Undercut: AUC-ROC 0.7708 (target >0.75 ✅)

---

## v0.8.2 - NLP Radio Processing Pipeline

- [X] **Status:** Completed
- [X] **Release Date:** March 2026

NLP pipeline for the Radio Agent: converts raw team radio audio into structured signals (sentiment, intent, F1 entities) consumed by the Strategy Agent. Legacy notebooks `legacy/notebooks/NLP_radio_processing/N00-N06` migrated and updated to `notebooks/nlp/N17-N23`, plus a new N24 notebook for Race Control Messages.

**Pipeline architecture:**

```
Audio (MP3/WAV) → N18 Whisper ASR → text
                                      ├─► N20 BERT Sentiment
                                      ├─► N21 Intent Classifier
                                      └─► N22 Custom NER (F1 entities)
                                                    └─► N23 Merging → JSON output

N24 Race Control Messages → structured SC/VSC/flags/penalties
```

**N17 — Data Labeling & Dataset Radio:**

- [X] Label transcriptions with intent + sentiment + entities
- [X] Source: `VforVitorio/f1-strategy-dataset` (HuggingFace)
- [X] Notebook: `notebooks/nlp/N17_radio_labeling.ipynb`

**N18 — Radio Transcription (Whisper ASR):**

- [X] Whisper ASR for F1 radio transcription
- [X] Notebook: `notebooks/nlp/N18_radio_transcription.ipynb`

**N19 — Sentiment Baseline (VADER):**

- [X] Rule-based VADER baseline benchmark
- [X] Notebook: `notebooks/nlp/N19_sentiment_vader.ipynb`

**N20 — RoBERTa Sentiment Fine-tuning:**

- [X] Fine-tuned `roberta-base` — 3-class sentiment on labeled radio messages
- [X] **Achieved: 87.5% test accuracy** ✅
- [X] Export: model state dict to `data/models/nlp/`
- [X] Notebook: `notebooks/nlp/N20_bert_sentiment.ipynb`

**N21 — Intent Classification:**

- [X] 5 intent classes via SetFit + ModernBERT; back-translation augmentation; DeBERTa-v3-large negative result documented
- [X] Notebook: `notebooks/nlp/N21_radio_intent.ipynb`

**N22 — Custom NER (F1 Entities):**

- [X] BERT-large CoNLL-03 BIO token classifier; GLiNER zero-shot negative result documented
- [X] **Achieved: F1 = 0.42** (short radio transcriptions — limited training data)
- [X] Notebook: `notebooks/nlp/N22_ner_models.ipynb`

**N23 — RCM Parser (Rule-based):**

- [X] Deterministic structured event extractor for `session.race_control_messages` — no ML required
- [X] Notebook: `notebooks/nlp/N23_rcm_parser.ipynb`

**N24 — Unified NLP Pipeline:**

- [X] `run_pipeline(text)` → sentiment + intent + NER | `run_rcm_pipeline(rcm_row)` → structured event
- [X] **Achieved: GPU P95 latency 59.4 ms** ✅ (target <500 ms)
- [X] Export: `data/models/nlp/pipeline_config_v1.json`
- [X] Notebook: `notebooks/nlp/N24_nlp_pipeline.ipynb`

**Success Metrics:**

- [X] N20 RoBERTa Sentiment: 87.5% test accuracy ✅
- [X] N21 Intent: SetFit 5-class classifier operational ✅
- [X] N22 NER: F1 = 0.42 (short-text constraint documented) ✅
- [X] N24 Pipeline: GPU P95 latency 59.4 ms (target <500 ms ✅)

---

## v0.9.0 - src/ Extraction & CLI Distribution

- [X] **Status:** Completed
- [X] **Release Date:** April 2026

Extracted N25-N31 agent entry points to importable `src/agents/` modules. Built headless CLI simulation (`f1-sim`) with Rich Live rendering. Integrated OpenF1 team radio corpus with Whisper transcription pipeline. Published dataset and models to HuggingFace Hub.

**Agent extraction (all complete):**

1. [X] `src/agents/pace_agent.py` — `run_pace_agent()` → `PaceOutput`
2. [X] `src/agents/tire_agent.py` — `run_tire_agent()` → `TireOutput` (TireDegTCN bundles)
3. [X] `src/agents/race_situation_agent.py` — `run_race_situation_agent()` → `RaceSituationOutput`
4. [X] `src/agents/radio_agent.py` — `run_radio_agent()` → `RadioOutput` (3 NLP models)
5. [X] `src/agents/pit_strategy_agent.py` — `run_pit_strategy_agent()` → `PitStrategyOutput`
6. [X] `src/agents/rag_agent.py` — `run_rag_agent()` → `RegulationContext` (wraps src/rag/)
7. [X] `src/agents/strategy_orchestrator.py` — `run_strategy_orchestrator()` → `StrategyRecommendation`

**CLI simulation (`scripts/run_simulation_cli.py`):**

- [X] Rich Live lap-by-lap rendering with inference detail panel
- [X] Decision column: `ACTION·PACE·RISK` + Plan column (`→ L8 HARD vs NOR`)
- [X] No-LLM mode: ML models + MC simulation only, no API keys required
- [X] LLM mode: Full N31 orchestrator synthesis via OpenAI/LM Studio
- [X] Lap-1 hardening: `_get_lap_row` fallback, `_clamp_triangular`, incomplete-data guard
- [X] F1 strategic guard-rails: pit window (laps 5-last 3), minimum stint, compound-vs-distance, opening-lap threat discount, REACTIVE_SC only on confirmed SC

**Radio corpus pipeline (Track A):**

- [X] `src/f1_strat_manager/gp_slugs.py` — GP name → corpus slug resolution
- [X] `src/nlp/radio_runner.py` — `RadioPipelineRunner` + `WhisperTranscriber` + JSON cache
- [X] `src/f1_strat_manager/data_cache.py` — `ensure_radio_corpus()` lazy per-GP downloader
- [X] OpenF1 slug disambiguation for multi-race countries (Italy, United States)
- [X] Radio corpus published: 529 MP3s + 48 parquets on HuggingFace Hub

**CLI distribution:**

- [X] `pyproject.toml` with `[project.scripts]` entry points (`f1-strat`, `f1-sim`)
- [X] Lazy first-run data download from HuggingFace Hub (`ensure_setup()`)
- [X] Installable via `uv tool install git+https://github.com/VforVitorio/F1_Strat_Manager.git`

**Success Metrics:**

- [X] All 7 `run_*` agent functions importable from `src/agents/`
- [X] CLI 4-gate test: Sakhir, Sakhir LLM, Spielberg VER, Imola — all pass
- [X] Linting passes (ruff)
- [X] Typecheck passes (mypy)

---

## v0.10.0 - Multi-Agent System

- [X] **Status:** Completed
- [X] **Release Date:** March 2026

LangGraph multi-agent architecture replacing the legacy Experta rule engine. Seven specialised sub-agents (N25–N30) coordinate under a Supervisor Orchestrator (N31). Each agent wraps one or more ML models as `@tool`-decorated LangChain tools and returns a typed dataclass output including a `reasoning` field forwarded to N31.

N31 architecture has three layers: (1) dynamic MoE-style routing — only activates the sub-agents relevant to the current race state; (2) Monte Carlo simulation — samples from the probabilistic outputs of N25–N28 (bootstrap CI, MC Dropout P10/P50/P90, Platt-calibrated probabilities, quantile regression intervals) to rank strategy candidates by risk-adjusted expected outcome; (3) LLM synthesis — aggregates all sub-agent reasoning texts plus MC scenario scores, with N30 regulation context acting as a hard constraint that eliminates illegal options before the LLM decides.

**Sub-agents:**

- [X] N25 — Pace Agent: XGBoost N06 → `PaceOutput` (lap time + delta + bootstrap CI) ✅
- [X] N26 — Tire Agent: TCN N09/N10 → `TireOutput` ✅
- [X] N27 — Race Situation Agent: LightGBM N12/N14 → `RaceSituationOutput` ✅
- [X] N28 — Pit Strategy Agent: N15/N16 + analytical undercut logic → `PitStrategyOutput` ✅
- [X] N29 — Radio Agent: N24 NLP pipeline (N06-style synthesizer + Pydantic structured output) → `RadioOutput` ✅
- [X] N30 — RAG Agent: Qdrant + BGE-M3 + LangGraph ReAct → `RegulationContext` ✅
- [X] N31 — Strategy Orchestrator: LangGraph supervisor + Monte Carlo simulation layer + dynamic routing (MoE-style) ✅

**Success Metrics:**

- [X] All seven agents operational and coordinated ✅
- [X] End-to-end workflow from lap state to strategy recommendation ✅
- [X] Successful demo with historical race data (Bahrain 2025 multi-lap replay) ✅

---

## v0.11.0 - RAG System

- [X] **Status:** Completed
- [X] **Release Date:** March 2026

Retrieval-augmented generation over FIA Sporting Regulations (2023–2025). Provides normative support for strategic decision-making. Implemented as N30 (notebook) + `src/rag/retriever.py` (importable module for N31).

**Implementation:**

- [X] `scripts/download_fia_pdfs.py` — scrapes FIA Sporting Reg PDFs into `data/rag/documents/`
- [X] `scripts/build_rag_index.py` — PDF → chunks → BGE-M3 embeddings → Qdrant local collection
- [X] `src/rag/retriever.py` — `RagRetriever` class + `query_rag_tool` LangChain tool
- [X] N30 notebook — LangGraph ReAct agent demo; `RegulationContext` structured output

**Technical Details:**

- [X] Embeddings: `BAAI/bge-m3` (1024-dim, RTX 5070)
- [X] Chunk size: 512 characters with 64-character overlap
- [X] Top-k: 5 chunks per query | 2,279 chunks indexed (3 PDFs)
- [X] Export: `data/models/agents/rag_agent_config_v1.json`

**Success Metrics:**

- [X] RAG retrieves relevant regulation passages (scores 0.62–0.76 on demo queries) ✅
- [X] `query_rag_tool` importable by N31 via `from src.rag.retriever import query_rag_tool` ✅
- [X] `RegulationContext.articles` provides reliable article citations from chunk metadata ✅

---

## v0.12.0 - Interfaces & Distribution

- [ ] **Status:** In Progress
- [ ] **Target:** May 2026

Wire the multi-agent system into the FastAPI backend, expose strategy tools via FastMCP, build Streamlit dashboard pages, and integrate Arcade for race replay visualization. Three independent releases ship from this work (R1 CLI wheel, R2 Arcade, R3 Streamlit + Backend).

**R1 — CLI Release (wheel):**

- [X] `pyproject.toml` entry points (`f1-strat`, `f1-sim`) ✅
- [X] Lazy first-run HF data download (`ensure_setup()`) ✅
- [X] Wheel build via `uv build` → `dist/f1_strat_manager-*.whl` ✅
- [ ] Tag v0.1.1, attach wheel to GitHub Release
- [ ] README install section: `uv tool install <release-url>/*.whl`

**Step 9 — FastAPI wiring (`src/telemetry/backend/`):**

- [ ] 9a: New router `api/v1/endpoints/strategy.py` — HTTP endpoints for each agent + orchestrator
  - POST /strategy/pace, /tire, /situation, /pit, /radio, /rag, /recommend
- [ ] 9b: Upgrade `chat.py` — route strategy-intent queries to orchestrator via MCP tools
- [ ] Fix sys.path so telemetry backend imports from `src/agents/`

**Step 10 — FastMCP + Streamlit pages:**

- [ ] FastMCP server mounted alongside FastAPI (`app.mount("/mcp", ...)`)
  - Tools: `get_strategy_recommendation`, `get_tire_status`, `get_race_situation`, `query_regulations`
  - LangGraph agent in `/chat/` connects to MCP server for tool calls
- [ ] `pages/strategy.py` — Live strategy card (action badge, confidence bar, scenario scores, reasoning)
  - Sub-agent tabs: Pace (CI ribbon), Tyres (cliff gauge), Race Situation (overtake + SC gauges), Pit Analysis (undercut + duration)
- [ ] `pages/race_analysis.py` — 5-tab race view (Overview, Competitive, Gap Analysis, Degradation, Predictions)
  - Port legacy components from `legacy/app_streamlit_v1/` with N25-N31 API data sources

**Driver + Team selection (single-driver perspective):**

At session start, the user selects `TEAM` and `DRIVER` (e.g. McLaren / NOR). This pair feeds `RaceStateManager`, which constructs every `RaceState` from that driver's perspective. All downstream agents operate within this boundary automatically.

**Arcade Visualization (R2):**

- [ ] 2D circuit layout rendering with real-time car positions
- [ ] DRS zone overlays + pit lane visualization
- [ ] Frame streaming from `RaceReplayEngine` at 10Hz
- [ ] Deployed via container (Modal or similar)

**Voice Mode — low-latency upgrade (optional):**

- [ ] **GPT-4o Realtime API** (preferred — integrates with existing OpenAI SDK, ~200-300ms)
- [ ] **Moshi** (Kyutai, open-source, local GPU, ~160ms full-duplex — offline fallback)
- [ ] Keep N24 NLP pipeline active for text-based analysis in parallel

**Integration (Hybrid Architecture):**

- [ ] Add WebSocket endpoints to existing FastAPI backend (hybrid REST + WebSocket)
- [ ] MVP: /ws/replay endpoint for offline race replay from CSV/Parquet files
- [ ] WebSocket client implementation for Streamlit dashboard
- [ ] WebSocket client implementation for Arcade visualization
- [ ] Frame streaming at 10Hz for smooth visualization
- [ ] Extension: /ws/live endpoint with Kafka consumer for real-time data

**Note:** REST endpoints remain unchanged. WebSocket is added only for real-time streaming needs.

**R3 — Streamlit + Backend Release:**

- [ ] Docker Compose: FastAPI backend + Streamlit frontend + Qdrant + Kafka + LM Studio sidecar
- [ ] Alternative: Streamlit Cloud + hosted FastAPI
- [ ] Legacy cleanup: archive `base_agent.py`, `strategy_agent.py`, `rules/`; update `src/nlp/pipeline.py` to match N24

**Success Metrics:**

- [ ] Strategy endpoints return valid agent outputs via REST
- [ ] FastMCP tools callable from `/chat/` with structured rendering
- [ ] Streamlit load time <3 seconds
- [ ] Arcade maintains >30 FPS during race replay
- [ ] Zero packet loss during Kafka streaming

---

## v0.13.0 - Testing & Validation

- [ ] **Status:** Not Started
- [ ] **Target:** June 2026

End-to-end system validation across multiple race scenarios and circuit clusters. Performance testing and critical bug resolution.

**Test Scenarios (one per circuit cluster):**

- [ ] Monaco 2025 — street circuit cluster (high downforce, overtake-starved)
- [ ] Monza 2025 — power circuit cluster (low downforce, DRS-heavy)
- [ ] Spielberg 2025 — standard circuit cluster (baseline validation)
- [ ] Singapore 2025 — street/night circuit (humidity, safety car frequency)

**Validation Activities:**

- [ ] E2E CLI simulation on each test scenario (no-llm + LLM mode)
- [ ] ML metrics validation per circuit cluster (overtake AUC-PR, SC lift, tire MAE)
- [ ] Streaming performance verification (no Kafka packet loss)
- [ ] FastAPI endpoint integration tests (strategy router round-trip)
- [ ] FastMCP tool call validation from `/chat/` endpoint
- [ ] Load testing: API throughput >100 req/s, latency p95 <50ms
- [ ] Memory profiling: system usage <4 GB peak

**Success Metrics:**

- [ ] All four circuit-cluster test scenarios pass without errors
- [ ] Per-cluster ML metrics within documented tolerances
- [ ] Strategy endpoints return valid outputs under concurrent requests
- [ ] Zero packet loss during Kafka streaming
- [ ] System stable under load
- [ ] All critical bugs resolved before v1.0 tag

---

## v1.0.0 - Final Release

- [ ] **Status:** Not Started
- [ ] **Target:** June 2026

Complete project delivery with thesis documentation, defense materials, and three distribution artifacts (CLI wheel, Arcade deploy, Streamlit app).

**Deliverables:**

- [ ] Complete thesis document with methodology, results, and conclusions
- [ ] Defense presentation (20 slides)
- [ ] 5-minute demonstration video (CLI + Streamlit + Arcade)
- [ ] Technical documentation: API docs, deployment guide
- [ ] R1 CLI wheel on GitHub Releases (tagged)
- [ ] R2 Arcade deployment (container)
- [ ] R3 Streamlit + Backend (Docker Compose or Streamlit Cloud)

**Success Criteria:**

- [ ] Thesis submitted on time
- [ ] Demonstration showcases: CLI inference, Streamlit dashboard, Arcade replay, voice mode
- [ ] All three release artifacts installable/deployable from scratch
- [ ] Code repository production-ready with comprehensive documentation

---

## Key Milestones

| Release | Milestone                     | Criteria                                                                           | Status |
| ------- | ----------------------------- | ---------------------------------------------------------------------------------- | ------ |
| v0.5    | Code Integration Complete     | Docker Compose operational, API verified                                           | ✅     |
| v0.6    | Data Engineering Complete     | 4 clusters, 45k laps, 2025 held-out, HuggingFace published                        | ✅     |
| v0.7    | Base Models Complete          | Lap Time MAE 0.392s ✅ / Tire Deg TCN + MC Dropout ✅                             | ✅     |
| v0.8    | Core ML Models Complete       | Overtake ✅ / SC ✅ (soft prior, lift 1.67×) / Sector descoped                    | ✅     |
| v0.8.1  | Extended ML Models            | N12B archived (neg. result) / N15 MAE 0.487s ✅ / N16 AUC-ROC 0.7708 ✅          | ✅     |
| v0.8.2  | NLP Radio Pipeline            | N17–N24: RoBERTa 87.5% / SetFit intent / BERT NER / pipeline P95 59.4ms          | ✅     |
| v0.9    | src/ Extraction + CLI + Radio | 7 agents extracted, CLI sim, radio corpus, HF lazy download, guard-rails          | ✅     |
| v0.10   | Multi-Agent Operational       | N25–N31 all complete, Bahrain 2025 end-to-end demo ✅                             | ✅     |
| v0.11   | RAG Integrated                | 2,279 chunks indexed, BGE-M3, `src/rag/` module complete                          | ✅     |
| R1      | CLI Wheel Release             | Tagged wheel on GitHub Releases, `uv tool install` works                           | ⬜     |
| v0.12   | Interfaces + Distribution     | FastAPI endpoints, FastMCP tools, Streamlit pages, Arcade replay                   | ⬜     |
| R2      | Arcade Release                | Container deploy, 2D circuit replay at >30 FPS                                    | ⬜     |
| R3      | Streamlit + Backend Release   | Docker Compose / Streamlit Cloud, full web dashboard                               | ⬜     |
| v0.13   | Testing Complete              | 4 circuit-cluster scenarios validated, critical bugs resolved                      | ⬜     |
| v1.0    | Thesis Delivered              | Documentation complete, defense ready, all 3 releases shipped                      | ⬜     |

---

## Risk Mitigation

**Concept Drift (2024-2025):** Addressed via temporal features and cluster-based normalization. Continuous monitoring of model performance on 2025 data.

**LLM Latency:** Use quantized 7B models with INT8 precision. Target inference <2s. Fallback to smaller models if necessary.

**Kafka Streaming Reliability:** Implement buffering and retry logic. Monitor for packet loss with alerting.

**Test Data Availability:** If 2025 race data incomplete, use late 2024 season as fallback test set.

---

## Success Metrics

**ML Models:**

- Lap Time: target MAE <0.3s — **achieved MAE 0.392s** (within <0.5s tolerance ✅)
- Tire Degradation: target R² >0.85 — *pending formal holdout evaluation*
- Sector Time: **descoped**
- Overtake Probability: target AUC-PR >0.50 — **achieved AUC-PR 0.5491, AUC-ROC 0.8758** ✅
- Safety Car Probability: reframed as soft prior — **achieved AUC-PR 0.0723 (lift 1.67×), AUC-ROC 0.6411** ✅
- Battle Outcome TCN (N12B): archived — AUC-PR ~0.10, N12 LightGBM remains production ✅
- Pit Stop Duration (N15): **achieved P50 MAE 0.487s** (target <0.5s ✅)
- Undercut Success (N16): **achieved AUC-ROC 0.7708, AUC-PR 0.6739** (target >0.75 ✅)

**System Performance:**

- Streaming latency: p95 <50ms
- API throughput: >100 requests/second
- Test coverage: >70%
- Memory usage: <4GB

**User Interfaces:**

- Streamlit load time: <3 seconds
- Arcade frame rate: >30 FPS

---

**Last Updated:** April 2026
**Version:** 1.6
