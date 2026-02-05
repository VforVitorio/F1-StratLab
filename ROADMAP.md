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

**Status:** Completed  
**Release Date:** Feb 5, 2025

Integrated F1_Telemetry_Manager submodule and established modular project structure. Set up Docker Compose orchestration and configured base YAML configs for models, Kafka, and logging.

**Deliverables:**
- Modular repository structure with src/, notebooks/, data/, legacy/
- Submodule integration preserving existing telemetry backend
- Python package setup with editable install
- Data organization by year/race hierarchy
- Base Docker Compose configuration

**Success Criteria:**
- Clean imports from src modules
- Docker Compose successfully launches base services
- Project installable via pip install -e .

---

## v0.2.0 - Refactoring & Testing (Weeks 2-5)

**Target:** Late February 2025

Code cleanup, test coverage, and CI/CD implementation. Audit and eliminate duplicate code between repositories. Extend FastAPI with new ML prediction endpoints.

**Goals:**
- Eliminate code duplication across modules
- Add FastAPI endpoints for predictions and agent recommendations
- Complete YAML configurations for all components
- Implement pytest suite with minimum 70% coverage
- Set up GitHub Actions CI/CD pipeline

**Success Metrics:**
- Test coverage exceeds 70%
- All linting checks pass (black, ruff)
- CI/CD pipeline operational
- Zero code duplication

---

## v0.3.0 - ML Foundation (Weeks 4-8.5)

**Target:** Late March 2025  
**Critical Milestone**

Optimize baseline ML models for lap time and tire degradation prediction. Implement circuit clustering and temporal features to handle concept drift from regulation changes.

**Dataset:**
- Training: 2023-2024 seasons (46 GPs, ~110k laps)
- Test: 2025 season (24 GPs, ~54k laps)
- Rationale: 2022 regulation overhaul creates excessive concept drift in pre-2022 data

**Circuit Clustering:**
Four clusters identified via K-means:
- Power circuits: Monza, Baku, Jeddah, Las Vegas, Montreal
- High downforce: Monaco, Singapore, Hungary, Zandvoort, Barcelona
- Balanced: Silverstone, Spa, Suzuka, COTA, Interlagos
- Street circuits: Miami, Albert Park, Shanghai

**Models:**
- Lap Time Predictor (XGBoost): RMSE target <0.5s, MAE <0.3s
- Tire Degradation (TCN with PyTorch Lightning): R² target >0.85

**Technical Tasks:**
- Feature engineering: circuit cluster, downforce level, avg speed, temporal trends
- TCN refactor to PyTorch Lightning for modularity
- Hyperparameter tuning via GridSearch
- ONNX export for <50ms inference latency
- Validation split from 2025 data

**Success Metrics:**
- Lap Time: RMSE <0.5s across all circuit clusters
- Tire Degradation: R² >0.85
- Inference latency <50ms per prediction

---

## v0.4.0 - Additional Predictors (Weeks 8-12)

**Target:** Late April 2025

Expand ML capabilities with three additional prediction models, all incorporating circuit clustering features.

**Models:**
- Sector Time Predictor (XGBoost Multi-Output): predicts S1, S2, S3 times, RMSE <0.3s per sector
- Overtake Probability (Gradient Boosting): binary classification for next 3 laps, F1-score >0.75
- Safety Car Probability (Random Forest): binary classification for next 5 laps, Precision >0.70

**Dataset Preparation:**
- Extract sector times from telemetry data
- Label overtake events based on gap reduction and position changes
- Incorporate historical safety car deployment data

**Success Metrics:**
- Five complete ML models operational
- Classification models achieve F1-score >0.75
- Per-cluster performance validated on 2025 test data

---

## v0.5.0 - Multi-Agent System (Weeks 9-13)

**Target:** Early May 2025

Implement coordinated three-agent architecture using LangGraph for orchestration. Each agent specializes in a specific aspect of race strategy analysis.

**Agent Architecture:**
- Telemetry Agent: Kafka stream processing, data normalization, anomaly detection
- Radio Agent: Whisper ASR for audio transcription, RoBERTa for sentiment analysis, BERT NER for entity extraction
- Strategy Agent: LLM-based reasoning combined with Experta rule engine for strategic recommendations

**Integration:**
- LangGraph workflow coordination between agents
- State management across agent transitions
- Demo with 2023 race data replay

**Success Metrics:**
- Three agents operational and coordinated
- End-to-end workflow from telemetry to strategy recommendation
- Successful demo with historical race data

---

## v0.6.0 - RAG System (Weeks 11.5-14)

**Target:** Mid-May 2025

Integrate retrieval-augmented generation for FIA sporting regulations. Provides normative support for strategic decision-making by Strategy Agent.

**Implementation:**
- Qdrant vector database deployment
- FIA regulation PDF scraping (2023-2025 sporting regulations)
- Document chunking and embedding pipeline (sentence-transformers)
- Semantic retrieval integration with Strategy Agent

**Technical Details:**
- Embeddings: all-MiniLM-L6-v2 model
- Chunk size: 500 tokens with 50-token overlap
- Top-k retrieval: 5 most relevant regulation sections

**Success Metrics:**
- RAG system successfully retrieves relevant regulations
- Strategy Agent incorporates regulatory context in recommendations
- Query response time <2 seconds

---

## v0.7.0 - User Interfaces (Weeks 12.5-15.5)

**Target:** Late May 2025

Develop dual interface system: Streamlit dashboard for analysis/configuration and Arcade visualization for real-time circuit representation.

**Streamlit Dashboard:**
- ML prediction displays with confidence metrics
- Agent recommendation panels
- Configuration interface for model parameters
- Historical data analysis views

**Arcade Visualization:**
- 2D circuit layout rendering
- Real-time car position updates (20 cars)
- DRS zone overlays
- Pit lane visualization

**Integration:**
- WebSocket client implementation for both UIs
- Backend FastAPI already provides WebSocket support
- Real-time telemetry streaming at 10Hz

**Success Metrics:**
- Both UIs operational and connected to backend
- Streamlit load time <3 seconds
- Arcade maintains >30 FPS during race replay

---

## v0.8.0 - Testing & Validation (Weeks 14.5-16.5)

**Target:** Early June 2025

End-to-end system validation across multiple race scenarios. Performance testing and critical bug resolution.

**Test Scenarios:**
- Monaco 2025 (street circuit, high downforce)
- Monza 2025 (power circuit, low downforce)
- Singapore 2025 (night race, humidity factors)

**Validation Activities:**
- E2E workflow testing with race replays
- ML metrics validation per circuit cluster
- Streaming performance verification (no packet loss)
- Load testing: API throughput >100 req/s, latency p95 <50ms
- Memory profiling: system usage <4GB

**Success Metrics:**
- All critical bugs resolved
- Per-cluster ML metrics meet targets
- System stable under load
- Zero packet loss during streaming

---

## v1.0.0 - Final Release (Week 18)

**Target:** June 20, 2025

Complete project delivery with thesis documentation and defense materials.

**Deliverables:**
- Complete thesis document with methodology, results, and conclusions
- Defense presentation (20 slides)
- 5-minute demonstration video
- Technical documentation: API docs, deployment guide
- Final code release with all features operational

**Success Criteria:**
- Thesis submitted on time
- Demonstration successfully showcases all system capabilities
- Code repository production-ready with comprehensive documentation

---

## Key Milestones

| Week | Milestone | Criteria |
|------|-----------|----------|
| 3 | Code Integration Complete | Docker Compose operational, WebSocket functional |
| 5 | Circuit Clustering Validated | 4 clusters defined with F1-scores calculated |
| 8 | Base Models Optimized | Lap Time RMSE <0.5s, Tire Deg R² >0.85 |
| 12 | All ML Models Complete | 5 models operational, classification F1 >0.75 |
| 13 | Multi-Agent Operational | 3 coordinated agents with successful demo |
| 14 | RAG Integrated | Strategy Agent leverages FIA regulations |
| 16 | Testing Complete | 3 race scenarios validated, critical bugs resolved |
| 18 | Thesis Delivered | Documentation complete, defense ready |

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
