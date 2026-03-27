# Roadmap

**F1 Digital Twin Multi-Agent System - Final Degree Project**

Timeline: 18 weeks (Feb 3 - Jun 20, 2025)

---

## Overview

This project develops an intelligent multi-agent system for real-time Formula 1 telemetry analysis and race strategy optimization. The system integrates streaming telemetry via Kafka, five ML predictive models with circuit clustering, a coordinated multi-agent architecture using LangGraph, and RAG-based FIA regulation knowledge.

**Key Technologies:** Apache Kafka, FastAPI, XGBoost, PyTorch, LangGraph, Qdrant, Streamlit, Arcade

---

## Release Strategy

Development follows an incremental approach. v0.1–v0.5 covered project setup and integration; v0.6 closed out the data engineering phase. Subsequent releases track the ML, agent, and interface phases.

---

## v0.1–v0.5 - Integration & Setup

- [x] **Status:** Completed
- [x] **Release Date:** Feb 5, 2025

Integrated F1_Telemetry_Manager submodule and established modular project structure. Set up Docker Compose orchestration and configured base YAML configs for models, Kafka, and logging. Incremental releases covered submodule wiring, package setup, FastAPI verification, and base configuration.

**Note:** WebSocket streaming deferred to v0.12.0 (Interfaces). REST API endpoints are sufficient for ML development phases.

**Deliverables:**

- [x] Modular repository structure with src/, notebooks/, data/, legacy/
- [x] Submodule integration preserving existing telemetry backend
- [x] Python package setup with editable install
- [x] Data organization by year/race hierarchy
- [x] Base Docker Compose configuration
- [x] FastAPI backend verification (7 endpoint categories operational)

**Success Criteria:**

- [x] Clean imports from src modules
- [x] Docker Compose successfully launches base services
- [x] Project installable via pip install -e .
- [x] REST API endpoints verified and documented

---

## v0.6.0 - Data Engineering Pipeline

- [x] **Status:** Completed
- [x] **Release Date:** February 2025

Closed out the full data engineering phase. From raw FastF1 telemetry to a clean, feature-rich dataset ready to feed into the ML models. Previous notebooks moved to `legacy/`; new structure built around TFG architecture.

**Goals:**

- [x] Download and organize 2023-2025 seasons data (N01 — extended to 2025, Miami/Barcelona alias fixes)
- [x] Master EDA: data exploration, cleaning, validation
- [x] Circuit clustering using K-Means k=4, fitted on 2023–2024, serialized with joblib; 2025 inference via `kmeans.predict()` without refit (N03)
- [x] Feature engineering: 48-column dataset, ~45k clean racing laps; fuel-corrected degradation, sequential lap features, rolling 3-lap degradation, race context, circuit cluster merge (N04)
- [x] 2025 saved as held-out test set — never touches training data

**Deliverables:**

- [x] Clean datasets in data/processed/ (2023, 2024, 2025 separate)
- [x] Circuit clusters defined and validated (`circuit_clusters_k4.parquet`, 25 circuits, 0 unknowns on 2023–2025)
- [x] notebooks/data_engineering/ with all EDA and pipeline notebooks
- [x] Dataset published to HuggingFace Hub (`VforVitorio/f1-strategy-dataset`)

**Success Metrics:**

- [x] All GPs downloaded and validated (2023–2025)
- [x] 4 circuit clusters identified with clear characteristics
- [x] Data quality checks pass (no missing critical fields)
- [x] Feature engineering pipeline reproducible

---

## v0.7.0 - ML Foundation: Lap Time & Tire Degradation

- [x] **Status:** Completed
- [x] **Release Date:** March 2025
- [x] **Critical Milestone**

Developed and trained the first two ML models: lap time prediction (XGBoost) and tire degradation (TCN + MC Dropout). All experimentation in notebooks, models exported to `data/models/`.

**Lap Time Predictor (N06):**

- [x] EDA and data exploration
- [x] XGBoost delta-lap-time model with circuit clustering features
- [x] Hyperparameter tuning via GridSearch / cross-validation
- [x] Model exported to `data/models/lap_time/`
- [x] Target: MAE <0.5s — **Achieved: MAE 0.392s on 2025 test data** ✅

**Tire Degradation Predictor (N07–N10):**

- [x] EDA and degradation analysis (N07, N08)
- [x] TCN (Temporal Convolutional Network) architecture in PyTorch (N09)
- [x] Per-compound fine-tuning (SOFT / MEDIUM / HARD)
- [x] MC Dropout for uncertainty quantification (N=50 forward passes)
- [x] Calibration JSON exported alongside model weights
- [x] Model exported to `data/models/tire_degradation/`
- [ ] Target R² >0.85 — *pending formal evaluation on 2025 holdout*

**Important Note - Tire Compound Mapping:**
Current data (FastF1/OpenF1) only provides relative compound names (SOFT/MEDIUM/HARD) per race. For accurate degradation predictions, actual Pirelli compounds (C1-C5) are critical since the same "MEDIUM" can be C2 (harder) or C4 (softer) depending on circuit. Future enhancement: manual mapping from [Pirelli press releases](https://press.pirelli.com) into `data/tire_compounds_by_race.json`.

**Success Metrics:**

- [x] Lap Time: MAE 0.392s on 2025 (target <0.5s ✅ / stretch <0.3s ⬜)
- [x] Tire Degradation model operational with MC Dropout uncertainty
- [x] All experiments documented in notebooks/strategy/

---

## v0.8.0 - Additional Predictors

- [x] **Status:** Completed
- [x] **Release Date:** April 2025

Expand ML capabilities with additional prediction models for overtake probability and safety car deployment. Sector time predictor descoped (no meaningful contribution over N06 delta model for the Strategy Agent).

**Sector Time Predictor:**

- [ ] ~~Descoped~~ — does not add value over lap delta model for Strategy Agent use case

**Overtake Probability (N11 + N12):**

- [x] EDA and overtake pattern analysis — `N11_overtake_eda.ipynb`
- [x] 28,494 labeled pairs (2023–2025), gap ≤ 2.5s, 8.44% positive rate
- [x] LightGBM binary classifier, Optuna hyperparameter search
- [x] Platt calibration on 2024 validation set
- [x] Window simulation: P(overtake in N laps) = 1 − ∏(1 − Pₖ)
- [x] Model exported to `data/models/overtake_probability/`
- [x] Labeled dataset published to HuggingFace Hub
- [x] **Achieved: AUC-PR 0.5491, AUC-ROC 0.8758, threshold 0.80** ✅

**Safety Car Probability (N13 + N14):**

- [x] Dataset construction — `N13_sc_eda.ipynb`
  - 58 races loaded, 3,275 labeled race-lap rows; SC+VSC: 6.6% of all laps
  - Sources: `session.laps` + `session.track_status` + `session.race_control_messages`
  - Three SC targets built: `sc_within_3_laps` (3.5%), `sc_within_5_laps` (5.6%), `sc_within_7_laps` (7.5%)
  - `circuit_sc_rate` added as historical prior per circuit
  - Dataset exported: `data/processed/sc_labeled/sc_labeled_2023_2025.parquet` (43 cols, 3,275 rows)
- [x] LightGBM binary classifier + Optuna + Platt calibration — `N14_sc_model.ipynb`
  - **Achieved: AUC-PR 0.0723 (baseline 0.0432, lift 1.67×), AUC-ROC 0.6411** ✅
  - Target selected: `sc_within_3_laps` (best lift vs 5-lap 1.44×, 7-lap 1.29×)
  - Threshold (F2): 0.234 | F2=0.2537 | Precision=0.08 | Recall=0.56
  - SHAP top: lap_time_std_z > tyre_life_max > track_temp > circuit_sc_rate > air_temp
  - Framing: **soft contextual prior** for Strategy Agent, not deterministic SC predictor
- [x] Model exported to `data/models/safety_car_probability/`
  - `lgbm_sc_v1.pkl` + `calibrator_sc_v1.pkl` + `feature_list_v1.json`

**Success Metrics:**

- [x] Overtake: AUC-PR 0.5491, AUC-ROC 0.8758 (train 2023+2024 / test 2025) ✅
- [x] Safety Car: AUC-PR 0.0723, lift 1.67× over baseline, AUC-ROC 0.6411 ✅ (reframed as soft prior)
- [x] Per-cluster performance validated on 2025 test data (overtake) ✅

---

## v0.8.1 - Extended ML Models

- [x] **Status:** Completed
- [x] **Release Date:** March 2026

Additional predictive models extending the ML foundation: pit stop duration quantile regression and undercut success classification. Causal TCN alternative archived as negative result.

**Battle Outcome Temporal — Causal TCN (N12B) — Negative Result:**

- [x] Causal TCN implemented and trained — `notebooks/strategy/overtake_probability/N12B_overtake_tcn.ipynb`
- [x] **Result: negative** — AUC-PR ~0.10 vs N12 LightGBM 0.5491
- [x] Root cause: N12 already encodes temporal signal via `pace_delta_rolling3` / `gap_trend`; TCN cannot rediscover what is already explicit on ~18k sequences
- [x] **N12 LightGBM remains production model.** N12B archived as documented negative result — valid finding: explicit feature engineering dominates raw sequence modeling on small datasets.

**Pit Stop Duration — Quantile Regression (N15):**

- [x] EDA integrated in same notebook
- [x] **Model:** `sklearn.HistGradientBoostingRegressor(loss='quantile')` × 3 fits (P05/P50/P95)
- [x] Target: `physical_stop_est` [2.0–4.5s] — physical stop only, pit lane traversal subtracted per circuit
- [x] Features: team, year, tyre_life_in, lap_number, compound_id, compound_change, under_sc, tight_pit_box, team_year_median
- [x] Notebook: `notebooks/strategy/pit_prediction/N15_pit_duration.ipynb`
- [x] Export: `data/models/pit_prediction/hist_pit_p05/p50/p95_v1.pkl` + `model_config.json`
- [x] **Achieved: P50 MAE 0.487s vs baseline 0.555s** ✅

**Undercut Success Predictor (N16):**

- [x] Label: driver X pits before rival Y (≤5 laps) → X gains position after pit sequence = success
- [x] Dataset: 1,032 labeled pairs (2023–2025), DRY_COMPOUNDS only (SOFT/MEDIUM/HARD)
- [x] **Model:** LightGBM binary (same architecture as N12/N14) + Platt calibration
- [x] Features (13): pos_gap_at_pit, pace_delta, tyre_life_diff, circuit_undercut_rate, lap_race_pct, compound_x/y_id, compound_delta, pit_duration_delta, circuit_undercut_rate (target enc), team_x_undercut_rate (target enc)
- [x] SHAP top: pos_gap_at_pit > pace_delta > circuit_undercut_rate > tyre_life_diff
- [x] Notebook: `notebooks/strategy/pit_prediction/N16_undercut.ipynb`
- [x] Export: `data/models/pit_prediction/lgbm_undercut_v1.pkl` + `calibrator_undercut_v1.pkl` + `model_config_undercut_v1.json`
- [x] **Achieved: AUC-PR 0.6739, AUC-ROC 0.7708, threshold 0.522** ✅

**Success Metrics:**

- [x] N12B Causal TCN: archived — AUC-PR ~0.10, N12 production model unchanged ✅
- [x] N15 Pit Duration: P50 MAE 0.487s (target <0.5s ✅)
- [x] N16 Undercut: AUC-ROC 0.7708 (target >0.75 ✅)

---

## v0.8.2 - NLP Radio Processing Pipeline

- [x] **Status:** Completed
- [x] **Release Date:** March 2026

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

- [x] Label transcriptions with intent + sentiment + entities
- [x] Source: `VforVitorio/f1-strategy-dataset` (HuggingFace)
- [x] Notebook: `notebooks/nlp/N17_radio_labeling.ipynb`

**N18 — Radio Transcription (Whisper ASR):**

- [x] Whisper ASR for F1 radio transcription
- [x] Notebook: `notebooks/nlp/N18_radio_transcription.ipynb`

**N19 — Sentiment Baseline (VADER):**

- [x] Rule-based VADER baseline benchmark
- [x] Notebook: `notebooks/nlp/N19_sentiment_vader.ipynb`

**N20 — RoBERTa Sentiment Fine-tuning:**

- [x] Fine-tuned `roberta-base` — 3-class sentiment on labeled radio messages
- [x] **Achieved: 87.5% test accuracy** ✅
- [x] Export: model state dict to `data/models/nlp/`
- [x] Notebook: `notebooks/nlp/N20_bert_sentiment.ipynb`

**N21 — Intent Classification:**

- [x] 5 intent classes via SetFit + ModernBERT; back-translation augmentation; DeBERTa-v3-large negative result documented
- [x] Notebook: `notebooks/nlp/N21_radio_intent.ipynb`

**N22 — Custom NER (F1 Entities):**

- [x] BERT-large CoNLL-03 BIO token classifier; GLiNER zero-shot negative result documented
- [x] **Achieved: F1 = 0.42** (short radio transcriptions — limited training data)
- [x] Notebook: `notebooks/nlp/N22_ner_models.ipynb`

**N23 — RCM Parser (Rule-based):**

- [x] Deterministic structured event extractor for `session.race_control_messages` — no ML required
- [x] Notebook: `notebooks/nlp/N23_rcm_parser.ipynb`

**N24 — Unified NLP Pipeline:**

- [x] `run_pipeline(text)` → sentiment + intent + NER | `run_rcm_pipeline(rcm_row)` → structured event
- [x] **Achieved: GPU P95 latency 59.4 ms** ✅ (target <500 ms)
- [x] Export: `data/models/nlp/pipeline_config_v1.json`
- [x] Notebook: `notebooks/nlp/N24_nlp_pipeline.ipynb`

**Success Metrics:**

- [x] N20 RoBERTa Sentiment: 87.5% test accuracy ✅
- [x] N21 Intent: SetFit 5-class classifier operational ✅
- [x] N22 NER: F1 = 0.42 (short-text constraint documented) ✅
- [x] N24 Pipeline: GPU P95 latency 59.4 ms (target <500 ms ✅)

---

## v0.9.0 - Code Refactoring

- [ ] **Status:** Deferred — src/ modules implemented after all notebooks complete
- [ ] **Target:** Post-notebook phase

Clean and modularize the codebase. Eliminate code duplication, centralize configurations, implement testing infrastructure.

**Scope:**

- Refactor: src/strategy/, src/agents/, src/nlp/, src/vision/, src/shared/
- Do NOT modify: src/telemetry/ (independent submodule)

**Goals:**

- [ ] Audit code duplication across modules
- [ ] Extract shared utilities to src/shared/
- [ ] Refactor functions for modularity and reusability
- [ ] Centralize YAML configurations
- [ ] Implement structured logging
- [ ] Unit tests with >50% coverage

**Success Metrics:**

- [ ] Zero code duplication detected
- [ ] All configurations in configs/ directory
- [ ] Test coverage >50%
- [ ] Linting passes (black, ruff)

---

## v0.10.0 - Multi-Agent System

- [ ] **Status:** In Progress
- [ ] **Target:** April–May 2026

LangGraph multi-agent architecture replacing the legacy Experta rule engine. Seven specialised sub-agents (N25–N30) coordinate under a Supervisor Orchestrator (N31). Each agent wraps one or more ML models as `@tool`-decorated LangChain tools and returns a typed dataclass output including a `reasoning` field forwarded to N31.

N31 architecture has three layers: (1) dynamic MoE-style routing — only activates the sub-agents relevant to the current race state; (2) Monte Carlo simulation — samples from the probabilistic outputs of N25–N28 (bootstrap CI, MC Dropout P10/P50/P90, Platt-calibrated probabilities, quantile regression intervals) to rank strategy candidates by risk-adjusted expected outcome; (3) LLM synthesis — aggregates all sub-agent reasoning texts plus MC scenario scores, with N30 regulation context acting as a hard constraint that eliminates illegal options before the LLM decides.

**Sub-agents:**

- [x] N25 — Pace Agent: XGBoost N06 → `PaceOutput` (lap time + delta + bootstrap CI) ✅
- [x] N26 — Tire Agent: TCN N09/N10 → `TireOutput` ✅
- [x] N27 — Race Situation Agent: LightGBM N12/N14 → `RaceSituationOutput` ✅
- [x] N28 — Pit Strategy Agent: N15/N16 + analytical undercut logic → `PitStrategyOutput` ✅
- [x] N29 — Radio Agent: N24 NLP pipeline (N06-style synthesizer + Pydantic structured output) → `RadioOutput` ✅
- [x] N30 — RAG Agent: Qdrant + BGE-M3 + LangGraph ReAct → `RegulationContext` ✅
- [ ] N31 — Strategy Orchestrator: LangGraph supervisor + Monte Carlo simulation layer + dynamic routing (MoE-style)

**Success Metrics:**

- [ ] All seven agents operational and coordinated
- [ ] End-to-end workflow from lap state to strategy recommendation
- [ ] Successful demo with historical race data

---

## v0.11.0 - RAG System

- [x] **Status:** Completed
- [x] **Release Date:** March 2026

Retrieval-augmented generation over FIA Sporting Regulations (2023–2025). Provides normative support for strategic decision-making. Implemented as N30 (notebook) + `src/rag/retriever.py` (importable module for N31).

**Implementation:**

- [x] `scripts/download_fia_pdfs.py` — scrapes FIA Sporting Reg PDFs into `data/rag/documents/`
- [x] `scripts/build_rag_index.py` — PDF → chunks → BGE-M3 embeddings → Qdrant local collection
- [x] `src/rag/retriever.py` — `RagRetriever` class + `query_rag_tool` LangChain tool
- [x] N30 notebook — LangGraph ReAct agent demo; `RegulationContext` structured output

**Technical Details:**

- [x] Embeddings: `BAAI/bge-m3` (1024-dim, RTX 5070)
- [x] Chunk size: 512 characters with 64-character overlap
- [x] Top-k: 5 chunks per query | 2,279 chunks indexed (3 PDFs)
- [x] Export: `data/models/agents/rag_agent_config_v1.json`

**Success Metrics:**

- [x] RAG retrieves relevant regulation passages (scores 0.62–0.76 on demo queries) ✅
- [x] `query_rag_tool` importable by N31 via `from src.rag.retriever import query_rag_tool` ✅
- [x] `RegulationContext.articles` provides reliable article citations from chunk metadata ✅

---

## v0.12.0 - User Interfaces

- [ ] **Status:** Not Started
- [ ] **Target:** Late May 2025

Develop dual interface system: Streamlit dashboard for analysis/configuration and Arcade visualization for real-time circuit representation.

**Streamlit Dashboard:**

- [ ] ML prediction displays with confidence metrics
- [ ] Agent recommendation panels
- [ ] Configuration interface for model parameters
- [ ] Historical data analysis views

**Arcade Visualization:**

- [ ] 2D circuit layout rendering
- [ ] Real-time car position updates (20 cars)
- [ ] DRS zone overlays
- [ ] Pit lane visualization

**Integration (Hybrid Architecture):**

- [ ] Add WebSocket endpoints to existing FastAPI backend (hybrid REST + WebSocket)
- [ ] MVP: /ws/replay endpoint for offline race replay from CSV/Parquet files
- [ ] WebSocket client implementation for Streamlit dashboard
- [ ] WebSocket client implementation for Arcade visualization
- [ ] Frame streaming at 10Hz for smooth visualization
- [ ] Extension: /ws/live endpoint with Kafka consumer for real-time data

**Note:** REST endpoints remain unchanged. WebSocket is added only for real-time streaming needs.

**Success Metrics:**

- [ ] Both UIs operational and connected to backend
- [ ] Streamlit load time <3 seconds
- [ ] Arcade maintains >30 FPS during race replay

---

## v0.13.0 - Testing & Validation

- [ ] **Status:** Not Started
- [ ] **Target:** Early June 2025

End-to-end system validation across multiple race scenarios. Performance testing and critical bug resolution.

**Test Scenarios:**

- [ ] Monaco 2025 (street circuit, high downforce)
- [ ] Monza 2025 (power circuit, low downforce)
- [ ] Singapore 2025 (night race, humidity factors)

**Validation Activities:**

- [ ] E2E workflow testing with race replays
- [ ] ML metrics validation per circuit cluster
- [ ] Streaming performance verification (no packet loss)
- [ ] Load testing: API throughput >100 req/s, latency p95 <50ms
- [ ] Memory profiling: system usage <4GB

**Success Metrics:**

- [ ] All critical bugs resolved
- [ ] Per-cluster ML metrics meet targets
- [ ] System stable under load
- [ ] Zero packet loss during streaming

---

## v1.0.0 - Final Release

- [ ] **Status:** Not Started
- [ ] **Target:** June 20, 2025

Complete project delivery with thesis documentation and defense materials.

**Deliverables:**

- [ ] Complete thesis document with methodology, results, and conclusions
- [ ] Defense presentation (20 slides)
- [ ] 5-minute demonstration video
- [ ] Technical documentation: API docs, deployment guide
- [ ] Final code release with all features operational

**Success Criteria:**

- [ ] Thesis submitted on time
- [ ] Demonstration successfully showcases all system capabilities
- [ ] Code repository production-ready with comprehensive documentation

---

## Key Milestones

| Release | Milestone                    | Criteria                                                        | Status |
| ------- | ---------------------------- | --------------------------------------------------------------- | ------ |
| v0.5    | Code Integration Complete    | Docker Compose operational, API verified                        | ✅     |
| v0.6    | Data Engineering Complete    | 4 clusters, 45k laps, 2025 held-out, HuggingFace published     | ✅     |
| v0.7    | Base Models Complete         | Lap Time MAE 0.392s ✅ / Tire Deg TCN + MC Dropout ✅           | ✅     |
| v0.8    | Core ML Models Complete      | Overtake ✅ / SC ✅ (soft prior, lift 1.67×) / Sector descoped  | ✅     |
| v0.8.1  | Extended ML Models           | N12B archived (neg. result) / N15 MAE 0.487s ✅ / N16 AUC-ROC 0.7708 ✅ | ✅     |
| v0.8.2  | NLP Radio Pipeline           | N17–N24: RoBERTa sentiment 87.5% / SetFit intent / BERT NER / pipeline P95 59.4ms | ✅     |
| v0.9    | Code Refactoring             | Deferred to post-notebooks                                      | ⏸️     |
| v0.10   | Multi-Agent Operational      | N25 ✅ N26 ✅ N27 ✅ N28 ✅ N29 ✅ N30 ✅ — N31 remaining          | 🔄     |
| v0.11   | RAG Integrated               | 2,279 chunks indexed, BGE-M3, `src/rag/` module complete        | ✅     |
| v0.12   | Interfaces Live              | Streamlit + Arcade connected to backend                         | ⬜     |
| v0.13   | Testing Complete             | 3 race scenarios validated, critical bugs resolved              | ⬜     |
| v1.0    | Thesis Delivered             | Documentation complete, defense ready                           | ⬜     |

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

**Last Updated:** March 2026
**Version:** 1.5
