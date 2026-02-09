# Roadmap

**F1 Digital Twin Multi-Agent System - Final Degree Project**

Timeline: 18 weeks (Feb 3 - Jun 20, 2025)

---

## Overview

This project develops an intelligent multi-agent system for real-time Formula 1 telemetry analysis and race strategy optimization. The system integrates streaming telemetry via Kafka, five ML predictive models with circuit clustering, a coordinated multi-agent architecture using LangGraph, and RAG-based FIA regulation knowledge.

**Key Technologies:** Apache Kafka, FastAPI, XGBoost, PyTorch, LangGraph, Qdrant, Streamlit, Arcade

---

## Release Strategy

Development follows an incremental approach across 9 phases with 8 planned releases.

---

## v0.1.0 - Integration & Setup (Weeks 1-3)

- [X] **Status:** Completed
- [X] **Release Date:** Feb 5, 2025

Integrated F1_Telemetry_Manager submodule and established modular project structure. Set up Docker Compose orchestration and configured base YAML configs for models, Kafka, and logging.

**Note:** WebSocket streaming deferred to v0.7.0 (Interfaces). REST API endpoints are sufficient for ML development phases.

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

## v0.2.0 - Data Engineering (Weeks 2-4)

- [ ] **Status:** In Progress
- [ ] **Target:** Late February 2025

Prepare and organize all datasets needed for ML model development. Exploratory data analysis, circuit clustering, and feature engineering.

**Goals:**

- [X] Download and organize 2023-2024 seasons data (46 GPs, 52k laps)
- [ ] Master EDA: data exploration, cleaning, validation
- [ ] Circuit clustering using K-Means (4 clusters)
- [ ] Feature engineering: circuit-specific features (undercut windows, DRS effectiveness), temporal features
- [ ] Document all findings in notebooks/data_engineering/

**Deliverables:**

- [ ] Clean datasets in data/processed/
- [ ] Circuit clusters defined and validated
- [ ] notebooks/data_engineering/ with all EDA notebooks
- [ ] Feature engineering pipeline documented

**Success Metrics:**

- [ ] All 46 GPs downloaded and validated
- [ ] 4 circuit clusters identified with clear characteristics
- [ ] Data quality checks pass (no missing critical fields)
- [ ] Feature engineering pipeline reproducible

---

## v0.3.0 - Code Refactoring (Weeks 4-7)

- [ ] **Status:** Not Started
- [ ] **Target:** Early March 2025

Clean and modularize existing codebase (excluding telemetry submodule). Eliminate code duplication, centralize configurations, and implement testing infrastructure.

**Scope:**

- Refactor: src/strategy/, src/agents/, src/nlp/, src/vision/, src/shared/
- Do NOT modify: src/telemetry/ (independent submodule)

**Goals:**

- [ ] Audit code duplication across modules
- [ ] Extract shared utilities to src/shared/
- [ ] Refactor functions for modularity and reusability
- [ ] Centralize YAML configurations
- [ ] Implement structured logging
- [ ] Unit tests with >50% coverage (initial target)

**Success Metrics:**

- [ ] Zero code duplication detected
- [ ] All configurations in configs/ directory
- [ ] Test coverage >50%
- [ ] Linting passes (black, ruff)
- [ ] Code review checklist completed

---

## v0.4.0 - ML Foundation: Lap Time & Tire Degradation (Weeks 7-11)

- [ ] **Status:** Not Started
- [ ] **Target:** Late March 2025
- [ ] **Critical Milestone**

Develop and train the first two ML models: lap time prediction and tire degradation. All experimentation in notebooks, final models in src/strategy/models/.

**Development Approach:**

- Experiments and EDA in notebooks/models/
- Based on legacy notebooks but refactored with new 2023-2024 data
- Final production models implemented in src/strategy/models/

**Lap Time Predictor:**

- [ ] EDA and data exploration (notebooks/models/laptime_eda.ipynb)
- [ ] XGBoost experiments with circuit clustering features (notebooks/models/laptime_experiments.ipynb)
- [ ] Hyperparameter tuning via GridSearch
- [ ] Final model implementation in src/strategy/models/laptime.py
- [ ] Target: RMSE <0.5s, MAE <0.3s across all circuit clusters

**Tire Degradation Predictor:**

- [ ] EDA and degradation analysis (notebooks/models/tiredeg_eda.ipynb)
- [ ] TCN architecture refactor to PyTorch Lightning (notebooks/models/tiredeg_experiments.ipynb)
- [ ] Architecture improvements and experimentation
- [ ] Final model implementation in src/strategy/models/tiredeg.py
- [ ] Target: R² >0.85

**Important Note - Tire Compound Mapping:**
Current data (FastF1/OpenF1) only provides relative compound names (SOFT/MEDIUM/HARD) per race. For accurate degradation predictions, actual Pirelli compounds (C1-C5) are critical since the same "MEDIUM" can be C2 (harder) or C4 (softer) depending on circuit. Future enhancement required: manual mapping from [Pirelli press releases](https://press.pirelli.com) to create `data/tire_compounds_by_race.json`. This enables compound-specific degradation models (C1 vs C5 degrades very differently) combined with circuit clustering.

**Model Optimization:**

- [ ] ONNX export for inference optimization
- [ ] Quantization (FP32 → FP16)
- [ ] Inference latency <50ms per prediction

**Validation:**

- [ ] Test on 2025 season data
- [ ] Per-cluster performance metrics
- [ ] Documented results in notebooks

**Success Metrics:**

- [ ] Lap Time: RMSE <0.5s across all circuit clusters
- [ ] Tire Degradation: R² >0.85
- [ ] Inference latency <50ms per prediction
- [ ] All experiments documented in notebooks/models/

---

## v0.5.0 - Additional Predictors (Weeks 11-15)

- [ ] **Status:** Not Started
- [ ] **Target:** Late April 2025

Expand ML capabilities with three additional prediction models. All experimentation in notebooks/models/, production code in src/strategy/models/.

**Dataset Preparation:**

- [ ] Extract and label sector times from telemetry
- [ ] Label overtake events (gap reduction + position changes)
- [ ] Label historical safety car deployment events

**Sector Time Predictor:**

- [ ] EDA and sector analysis (notebooks/models/sector_eda.ipynb)
- [ ] XGBoost Multi-Output experiments (notebooks/models/sector_experiments.ipynb)
- [ ] Final implementation in src/strategy/models/sector.py
- [ ] Target: RMSE <0.3s per sector (S1, S2, S3)

**Overtake Probability:**

- [ ] EDA and overtake pattern analysis (notebooks/models/overtake_eda.ipynb)
- [ ] Gradient Boosting experiments (notebooks/models/overtake_experiments.ipynb)
- [ ] Final implementation in src/strategy/models/overtake.py
- [ ] Target: F1-score >0.75 for next 3 laps

**Safety Car Probability:**

- [ ] EDA and incident analysis (notebooks/models/safetycar_eda.ipynb)
- [ ] Random Forest experiments (notebooks/models/safetycar_experiments.ipynb)
- [ ] Final implementation in src/strategy/models/safetycar.py
- [ ] Target: Precision >0.70 for next 5 laps

**Success Metrics:**

- [ ] Five complete ML models operational
- [ ] Classification models achieve F1-score >0.75
- [ ] Per-cluster performance validated on 2025 test data
- [ ] All experiments documented in notebooks/models/

---

## v0.6.0 - Multi-Agent System (Weeks 15-18)

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

## v0.7.0 - RAG System (Weeks 18-20)

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

## v0.8.0 - User Interfaces (Weeks 20-23)

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

## v0.9.0 - Testing & Validation (Weeks 23-25)

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

## v1.0.0 - Final Release (Week 18)

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

| Week | Milestone                    | Criteria                                           | Status |
| ---- | ---------------------------- | -------------------------------------------------- | ------ |
| 3    | Code Integration Complete    | Docker Compose operational, WebSocket functional   | ✅     |
| 5    | Circuit Clustering Validated | 4 clusters defined with F1-scores calculated       | ⬜     |
| 8    | Base Models Optimized        | Lap Time RMSE <0.5s, Tire Deg R² >0.85            | ⬜     |
| 12   | All ML Models Complete       | 5 models operational, classification F1 >0.75      | ⬜     |
| 13   | Multi-Agent Operational      | 3 coordinated agents with successful demo          | ⬜     |
| 14   | RAG Integrated               | Strategy Agent leverages FIA regulations           | ⬜     |
| 16   | Testing Complete             | 3 race scenarios validated, critical bugs resolved | ⬜     |
| 18   | Thesis Delivered             | Documentation complete, defense ready              | ⬜     |

---

## Risk Mitigation

**Concept Drift (2024-2025):** Addressed via temporal features and cluster-based normalization. Continuous monitoring of model performance on 2025 data.

**LLM Latency:** Use quantized 7B models with INT8 precision. Target inference <2s. Fallback to smaller models if necessary.

**Kafka Streaming Reliability:** Implement buffering and retry logic. Monitor for packet loss with alerting.

**Test Data Availability:** If 2025 race data incomplete, use late 2024 season as fallback test set.

---

## Success Metrics

**ML Models:**

- Lap Time: RMSE <0.5s, MAE <0.3s
- Tire Degradation: R² >0.85
- Sector Time: RMSE <0.3s per sector
- Overtake/Safety Car: F1-score >0.75, Precision >0.70

**System Performance:**

- Streaming latency: p95 <50ms
- API throughput: >100 requests/second
- Test coverage: >70%
- Memory usage: <4GB

**User Interfaces:**

- Streamlit load time: <3 seconds
- Arcade frame rate: >30 FPS

---

**Last Updated:** February 2025
**Version:** 1.0
