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

- [ ] **Status:** In Progress
- [ ] **Target:** April–May 2025

Additional predictive models extending the ML foundation: temporal battle sequence modeling, pit stop duration quantile regression, and undercut success classification.

**Battle Outcome Temporal — Causal TCN (N12B):**

- [ ] No separate EDA — N11 covers full overtake analysis; notebook will reference N11
- [ ] **Architecture:** Causal TCN (NOT bidirectional — future leakage forbidden)
  - 2-3 layers, dilation [1,2,4], kernel size 3 → receptive field ~15 timesteps (~5-8 laps)
  - Input: sequence of last 5-8 laps of [gap_ahead, pace_delta, drs_window] per pair (X,Y)
  - Causal TCN > LSTM: parallelizable, no vanishing gradient, better on short sequences
- [ ] Same binary target as N12 (overtake yes/no), same parquet; add temporal windowing
- [ ] Expected improvement: AUC-ROC 0.875 → ~0.90+ (captures gap momentum, not just snapshot)
- [ ] Notebook: `notebooks/strategy/overtake_probability/N12B_overtake_tcn.ipynb`
- [ ] Export: `data/models/overtake_probability/tcn_overtake_v1.pt` + `model_config.json`

**Pit Stop Duration — Quantile Regression (N15):**

- [ ] EDA integrated in same notebook (pit stop data never explored before)
- [ ] **Model:** `sklearn.HistGradientBoostingRegressor(loss='quantile')` × 3 fits (P10/P50/P90)
  - LightGBM overkill for ~1000 rows; HistGBT equivalent, no extra deps
  - Bimodal distribution (normal ~24s vs slow ~29-36s) → quantile regression over point estimate
  - P50 = expected duration (undercut), P10 = best case, P90 = worst case
- [ ] Features: team, circuit, year, track_status (SC/VSC/normal), tyre_life_in, lap_number, compound_change
- [ ] Expected MAE P50 ~0.3-0.4s on normal stops; team explains ~70% variance
- [ ] Notebook: `notebooks/strategy/pit_prediction/N15_pit_duration.ipynb`
- [ ] Export: `data/models/pit_prediction/hist_pit_duration_v1.pkl` + `model_config.json`

**Undercut Success Predictor (N16):**

- [ ] No separate EDA — reference N11 (gaps/pace) and N15 (pit stop context); labeling documented in notebook Step 0
- [ ] Label: driver X pits before rival Y (≤5 laps) → X gains position after pit sequence = success
- [ ] Dataset: ~400-600 labelable strategic pairs (2023-2025)
- [ ] **Model:** LightGBM binary (same architecture as N12/N14)
- [ ] Features: gap_to_rival_ahead, pace_delta, tyre_age_diff, circuit_undercut_rate, lap_pct, pit_duration_delta, fresh_tyre_pace_gain
- [ ] Expected: AUC-ROC ~0.75-0.85 (more deterministic than SC)
- [ ] Notebook: `notebooks/strategy/pit_prediction/N16_undercut.ipynb`
- [ ] Export: `data/models/pit_prediction/lgbm_undercut_v1.pkl` + `model_config.json`

**Success Metrics:**

- [ ] N12B Causal TCN: AUC-ROC >0.90
- [ ] N15 Pit Duration: P50 MAE <0.5s on normal stops
- [ ] N16 Undercut: AUC-ROC >0.75

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

- [ ] **Status:** Not Started
- [ ] **Target:** Early May 2025

Implement coordinated three-agent architecture using LangGraph for orchestration. Each agent specializes in a specific aspect of race strategy analysis.

**Agent Architecture:**

- [ ] Telemetry Agent: Kafka stream processing, data normalization, anomaly detection
- [ ] Radio Agent: Whisper ASR for audio transcription, RoBERTa for sentiment analysis, BERT NER for entity extraction
- [ ] Strategy Agent: LLM-based reasoning combined with Experta rule engine for strategic recommendations

**Integration:**

- [ ] LangGraph workflow coordination between agents
- [ ] State management across agent transitions
- [ ] Demo with 2023 race data replay

**Success Metrics:**

- [ ] Three agents operational and coordinated
- [ ] End-to-end workflow from telemetry to strategy recommendation
- [ ] Successful demo with historical race data

---

## v0.11.0 - RAG System

- [ ] **Status:** Not Started
- [ ] **Target:** Mid-May 2025

Integrate retrieval-augmented generation for FIA sporting regulations. Provides normative support for strategic decision-making by Strategy Agent.

**Implementation:**

- [ ] Qdrant vector database deployment
- [ ] FIA regulation PDF scraping (2023-2025 sporting regulations)
- [ ] Document chunking and embedding pipeline (sentence-transformers)
- [ ] Semantic retrieval integration with Strategy Agent

**Technical Details:**

- [ ] Embeddings: all-MiniLM-L6-v2 model
- [ ] Chunk size: 500 tokens with 50-token overlap
- [ ] Top-k retrieval: 5 most relevant regulation sections

**Success Metrics:**

- [ ] RAG system successfully retrieves relevant regulations
- [ ] Strategy Agent incorporates regulatory context in recommendations
- [ ] Query response time <2 seconds

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
| v0.8.1  | Extended ML Models           | N12B Causal TCN / N15 Pit Duration / N16 Undercut              | 🔄     |
| v0.9    | Code Refactoring             | Deferred to post-notebooks                                      | ⏸️     |
| v0.10   | Multi-Agent Operational      | 3 coordinated agents with successful demo                       | ⬜     |
| v0.11   | RAG Integrated               | Strategy Agent leverages FIA regulations                        | ⬜     |
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
- Battle Outcome TCN (N12B): target AUC-ROC >0.90 — *in progress*
- Pit Stop Duration (N15): target P50 MAE <0.5s — *in progress*
- Undercut Success (N16): target AUC-ROC >0.75 — *in progress*

**System Performance:**

- Streaming latency: p95 <50ms
- API throughput: >100 requests/second
- Test coverage: >70%
- Memory usage: <4GB

**User Interfaces:**

- Streamlit load time: <3 seconds
- Arcade frame rate: >30 FPS

---

**Last Updated:** March 2025
**Version:** 1.4
