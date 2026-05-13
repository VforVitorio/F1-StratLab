> **Note:** this page is a manually-refreshed mirror. The canonical source
> is [CHANGELOG.md](https://github.com/VforVitorio/F1-StratLab/blob/main/CHANGELOG.md)
> on GitHub.

> Mirrored from the repo root `CHANGELOG.md`. Maintained automatically by
> [release-please](https://github.com/googleapis/release-please) on each
> merge to `main` — see [CI/CD pipeline](#/ci-cd) for the full flow.

# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

From v1.2.0 onwards this file is maintained automatically by
[release-please](https://github.com/googleapis/release-please). Anything
above v1.1.0 was seeded retroactively from the GitHub Releases history.

<!-- next-version-placeholder -->

## [1.3.1](https://github.com/VforVitorio/F1-StratLab/compare/v1.3.0...v1.3.1) (2026-05-12)


### Bug Fixes

* **docs:** repair slate scheme contrast and add brand-aligned theme variables ([6516709](https://github.com/VforVitorio/F1-StratLab/commit/6516709ffbe2d6ff36f8b96f0c0aca7b9ea58512))


### Documentation

* add architecture hub landing with sequence diagram and key contracts ([3fb717e](https://github.com/VforVitorio/F1-StratLab/commit/3fb717ea90c8fbb335d2b19dfebba9d8785fc8a4))
* add branded 404 page with hero styling and recovery links ([188491b](https://github.com/VforVitorio/F1-StratLab/commit/188491b64c67527aa320358c059badcbb7e27e90))
* add CI/CD pipeline narrative covering branching releases and deployment ([db48476](https://github.com/VforVitorio/F1-StratLab/commit/db48476ba7db5198981e01803c7a79b6cfd34855))
* add development hub landing with conventional commits cheat sheet ([5e28bb1](https://github.com/VforVitorio/F1-StratLab/commit/5e28bb11e2f09233021013894a170f2831cecf9e))
* redesign landing with hero, agent grid, mermaid system diagram and stats ([e6525cc](https://github.com/VforVitorio/F1-StratLab/commit/e6525ccb7e4f51c391d31c5ca8aee4112c3ead7c))
* ship docs site revamp with CI/CD narrative and contrast fix ([b64ce12](https://github.com/VforVitorio/F1-StratLab/commit/b64ce12471fd1ecc0cd4272f403ca079224e0f3c))

## [1.3.0](https://github.com/VforVitorio/F1-StratLab/compare/v1.2.0...v1.3.0) (2026-05-12)


### Features

* **docs:** point GitHub Pages at docs.f1stratlab.com via CNAME ([52b3238](https://github.com/VforVitorio/F1-StratLab/commit/52b3238454e1ac702cc80d4976ed55a1809ed818))
* **docs:** update mkdocs site_url to docs.f1stratlab.com ([cf6cda6](https://github.com/VforVitorio/F1-StratLab/commit/cf6cda6679d1eb14d3624046fa812484320acc7c))
* **docs:** wire docs.f1stratlab.com custom domain ([1fcf6ea](https://github.com/VforVitorio/F1-StratLab/commit/1fcf6ea756a661d554676b0359b018adfba1f187))

## [1.2.0](https://github.com/VforVitorio/F1-StratLab/compare/v1.1.1...v1.2.0) (2026-05-12)


### Features

* **docs:** add F1 StratLab brand theme and external-image hook ([0dc3db1](https://github.com/VforVitorio/F1-StratLab/commit/0dc3db1f84540864c8ac2d20a5452d5ca1ddd31f))
* **docs:** launch mkdocs-material docs site with F1 StratLab branding ([7f7006d](https://github.com/VforVitorio/F1-StratLab/commit/7f7006de940dc8c7054a6f119e907a75119ab4b7))


### Documentation

* add landing, getting started, thesis results and maintenance pages ([defed4e](https://github.com/VforVitorio/F1-StratLab/commit/defed4e689508bcbce397292f1bbc8469abfcad8))

## [1.1.1](https://github.com/VforVitorio/F1-StratLab/compare/v1.1.0...v1.1.1) (2026-05-12)


### Bug Fixes

* **ci:** use PAT for release-please so required checks run on release PRs ([b293342](https://github.com/VforVitorio/F1-StratLab/commit/b29334288c1c852dd0617b337de6451fd187652a))
* **ci:** use PAT for release-please so required checks run on release PRs ([e276d45](https://github.com/VforVitorio/F1-StratLab/commit/e276d454d01d2a4fbc11d784aed667247290ab30))


### Documentation

* add data/eval/README inventory for benchmark outputs ([1f533fb](https://github.com/VforVitorio/F1-StratLab/commit/1f533fbcb7d935bac99c670b1dbf62f1d39528b6))
* add data/rag_eval/README for the RAG ground-truth set ([f0c54a1](https://github.com/VforVitorio/F1-StratLab/commit/f0c54a1ec19c8eb7ae105ff7028df1044415cf6e))
* add documents/images/README manifest for thesis figures ([f7c25d3](https://github.com/VforVitorio/F1-StratLab/commit/f7c25d3d06d2c86a41a594e0e780b98c9d47c961))
* document Conventional Commits convention in CONTRIBUTING ([78049cb](https://github.com/VforVitorio/F1-StratLab/commit/78049cb0551bf8a6bdad5842aa2738d4c324b644))
* seed CHANGELOG retroactively with release-please marker ([c870bcc](https://github.com/VforVitorio/F1-StratLab/commit/c870bcc27cfa8fcd52c80a1db24c577fdefb00ff))

## [1.1.0] - 2026-05-11

Benchmark suite for the TFG thesis chapter 5 plus full English localization of
strategy notebooks, scripts and evaluation artefacts. No model retraining and
no breaking changes to runtime APIs.

- Four standalone benchmark scripts under `scripts/bench_*.py` with a shared
  `BenchResult` dataclass and Rich panel layout: pace baselines vs production
  XGBoost (MAE matches the 0.4104 s anchor within +/-0.001 s), Whisper turbo
  latency (P50 / P95 / mean), six sub-agent latency on a Suzuka 2025 fixture,
  and the sentiment + intent + NER pipeline on CPU and GPU.
- New `notebooks/agents/N33_thresholds_and_calibration.ipynb` with
  precision-recall sweeps for overtake (N12), safety car (N14) and undercut
  (N16), plus MC Dropout empirical coverage on the 20,284 tire-degradation
  sequences.
- New `notebooks/agents/N30B_rag_benchmark.ipynb` evaluating BGE-M3 1024d
  (production), MiniLM-L6-v2 384d and BGE-M3 chunk 256 over 15 ground-truth
  queries with Precision@1 / 3 / 5, MRR and latency.
- Figures relocated to `documents/images/05_results/` (300 DPI), CSV + Markdown
  bench outputs under `data/eval/` and `data/rag_eval/`.
- `jiwer>=3.0.0` added to `pyproject.toml` as a forward-looking dependency.
  All bench scripts pass `ruff check` and `ruff format --check` on CI.
- Console entry points (`f1-strat`, `f1-sim`, `f1-arcade`, `f1-streamlit`)
  unchanged from v1.0.0.

## [1.0.0] - 2026-04-20

First stable release. Ships the three-window arcade experience, the full
seven-model ML stack and the N25 to N31 multi-agent LangGraph orchestrator
with FIA RAG over Qdrant.

- Three surfaces from one install: `f1-sim` CLI, `f1-arcade` three-window
  replay (2D circuit + PySide6 strategy dashboard + live telemetry window)
  and `f1-streamlit` post-race dashboard.
- Arcade runs the strategy pipeline locally without the FastAPI backend.
- Per-agent model outputs rendered live: lap time predicted vs actual with CI
  band, tire cliff percentiles, overtake and SC probabilities, stop duration
  percentiles, radio intents and regulation snippets.
- Six-tab reasoning panel with syntax-highlighted LLM narratives for each
  sub-agent plus the N31 orchestrator.
- Live telemetry window with 2x2 delta / speed / brake / throttle grid and
  rival overlay in two-driver mode.
- README slimmed to 85 lines with landing page link and F1 trademark
  disclaimer. Docs reorganised under `docs/arcade` plus five drawio
  architecture diagrams.
- Install via `uv tool install git+https://github.com/VforVitorio/F1_Strat_Manager.git`.

## [0.12.0] - 2026-04-15

Interfaces and distribution milestone. Closes R3 (Streamlit + Backend) and
lands infrastructure for R2 (Arcade). The CLI (R1) stays untouched.

- Voice chat full rewrite: STT migrated from Nemotron to
  `openai/whisper-small` via transformers pipeline; TTS migrated from Qwen3
  to edge-tts with a curated four-voice catalogue (Aria, Guy, Ryan, Sonia);
  LLM is now provider-agnostic via `F1_LLM_PROVIDER`.
- Voice chat UI redesigned end-to-end: Material icons, triadic palette,
  audio-reactive orb, native `st.audio_input` replacing the third-party
  recorder, voice selector dropdown wired end-to-end, health-check polling
  with spinner during cold starts.
- Chat charts: `lap_times` and `race_data` now show tyre compound on hover
  with per-driver pit-stop vlines annotated `DRIVER - COMPOUND`. Shared
  `COMPOUND_COLORS` palette mirrors the Rich palette used by the CLI.
- New `POST /api/v1/strategy/simulate` SSE endpoint streaming start / lap /
  summary events; ready for Arcade consumption.
- Breaking: `streamlit` bumped to `>=1.37`, `audio-recorder-streamlit`
  removed from deps. Backend Dockerfile now installs `ffmpeg` and
  `libsndfile1` for browser WebM decoding.

## [0.11.0] - 2026-03-30

Multi-agent system complete plus the RAG regulation layer. Seven specialized
agents coordinate under a Strategy Orchestrator to produce real-time pit
strategy recommendations from live race data.

- N25 Pace Agent (XGBoost lap time + bootstrap CI), N26 Tire Agent (TCN with
  MC Dropout), N27 Race Situation Agent (LightGBM overtake plus safety car
  prior), N28 Pit Strategy Agent (pit duration quantiles plus undercut
  scorer), N29 Radio Agent (RoBERTa sentiment + SetFit intent + BERT-large
  NER + RCM parser), N30 RAG Agent (Qdrant + BGE-M3) and N31 Strategy
  Orchestrator (three-layer MoE-style routing into Monte Carlo simulation
  into GPT-4o structured synthesis).
- `scripts/build_rag_index.py` indexes the FIA Sporting Regulations into
  2,279 BGE-M3 chunks. Retrieval scores 0.62 to 0.76 on demo queries.
- `src/rag/retriever.py` exports `RagRetriever` and `query_rag_tool` as
  reusable LangChain components imported by N31.
- GitHub Actions CI added: lint (ruff), typecheck (mypy), tests (pytest).
- SRP refactors across every agent notebook plus LangGraph computation graph
  visualization cells.

## [0.10.0] - 2026-03-22

Multi-agent infrastructure milestone. Two of seven sub-agents complete plus
the full RAG indexing pipeline and the importable `src/rag/` module.

- N25 Pace Agent wraps the N06 XGBoost model as a LangGraph ReAct agent and
  returns `PaceOutput` (lap time + delta vs session median + bootstrap CI
  P10 / P90 with N=200).
- N30 RAG Agent runs retrieval-augmented generation over FIA Sporting
  Regulations 2023 to 2025. Embedding via `BAAI/bge-m3` (1024-dim), Qdrant
  local vector store, 2,279 indexed chunks.
- First active `src/` module outside telemetry: `src/rag/` exposes
  `RagRetriever` (singleton via `get_retriever()`) and the `query_rag_tool`
  LangChain tool.
- `scripts/download_fia_pdfs.py` scrapes FIA PDF URLs via `DownloadConfig`.
  `scripts/build_rag_index.py` performs PDF chunking, embedding and Qdrant
  upsert with hash-based deduplication.
- README files added for `src/rag/`, `src/agents/`, `src/nlp/`,
  `src/strategy/` and `src/data_extraction/` covering API surface and
  legacy status.

## [0.9.0] - 2026-03-17

NLP pipeline complete. All notebooks N17 to N24 shipped; the radio analysis
pipeline is operational and integrated into the unified inference entry
point used by the Strategy Agent.

- N17 labels 659 messages (610 clean after manual inspection of 49 post-race
  removals). N18 runs Whisper turbo ASR. N19 establishes a VADER rule-based
  baseline.
- N20 fine-tunes RoBERTa-base for three-class sentiment. N21 uses SetFit
  with ModernBERT-base for five-class intent (370 examples). N22 fine-tunes
  BERT-large CoNLL-03 with BIO tagging for nine F1 entity types
  (weighted F1 = 0.42 on 399 examples). N23 ships a deterministic
  rule-based RCM parser covering 25 event types with 100% Flag / DRS / SC
  coverage.
- N24 unified pipeline exposes `run_pipeline(text)` for team radio and
  `run_rcm_pipeline(rcm_row)` for race control messages on a single JSON
  schema. GPU end-to-end latency: mean 47.8 ms, P95 59.4 ms.
- Model weights and configs uploaded to
  `VforVitorio/f1-strategy-models` on Hugging Face, plus the N16 undercut
  artefacts that were missing from v0.8.1.

## [0.8.1] - 2026-03-13

Strategy ML suite: pit-stop prediction and undercut intelligence.

- N15 Pit Stop Duration: HistGradientBoostingRegressor at P05 / P50 / P95
  on the normal physical window of 2.0 to 4.5 s. P50 MAE 0.487 s vs
  baseline 0.555 s. Coverage P05 to P95 is 70.5% on the test set.
- N16 Undercut Success: LightGBM binary classifier on 1,032 labeled
  pair-laps (2023 to 2025) with DRY_COMPOUNDS filter. AUC-PR 0.6739,
  AUC-ROC 0.7708, Platt-calibrated threshold 0.522. SHAP top features:
  `pos_gap_at_pit`, `pace_delta`, `circuit_undercut_rate`,
  `tyre_life_diff`.
- N12B Causal TCN Overtake archived as a valid negative result
  (AUC-PR ~0.10 vs N12's 0.5491). Confirms feature-engineered LightGBM
  wins on this dataset.
- Roadmap lists N17 to N24 for the upcoming NLP radio pipeline.

## [0.7.0] - 2026-03-05

ML foundation phase closes out. Two predictive models trained, validated on
held-out 2025 data and exported under `data/models/`.

- N06 Lap Time Predictor: XGBoost delta-lap-time model with circuit
  clustering features, trained on 2023 to 2024 and tested on 2025.
  MAE 0.392 s. Features include fuel-corrected lap time, tyre life,
  compound, circuit cluster and race phase.
- N07 to N10 Tire Degradation Predictor: Temporal Convolutional Network in
  PyTorch with per-compound fine-tuning (SOFT / MEDIUM / HARD) and MC
  Dropout for uncertainty (N=50 forward passes at inference). Calibration
  JSON exported alongside the model weights.
- `src/` module integration deferred to v0.9.0 (post-notebook phase). Tire
  compound mapping to C1 through C5 flagged as a future enhancement.

## [0.6.0] - 2026-02-12

Data engineering phase closes out. End-to-end pipeline from raw FastF1
telemetry to a clean feature-rich dataset ready to feed the ML models.

- Repo restructure: previous notebooks and code moved to `legacy/` to
  preserve the original work. New structure built around the TFG
  architecture: `notebooks/data_engineering/`, `notebooks/strategy/`,
  `src/strategy/`, `src/agents/`, `src/telemetry/`.
- N01 download pipeline extended to support the 2025 season alongside 2023
  to 2024. FastF1 naming inconsistencies aliased (Miami_Gardens, Spain
  vs Barcelona) for canonical cross-season names.
- N03 circuit clustering: K-Means with k=4 fitted on 2023 to 2024 and
  serialized with joblib. 2025 inference runs `kmeans.predict()` on the
  saved model without refitting. Las Vegas missing speed-trap data imputed
  with training means from the scaler.
- N04 feature engineering: 48-column dataset across ~45,000 clean racing
  laps. Fuel-corrected degradation (0.055 s/lap from Pirelli literature),
  sequential lap features, rolling 3-lap degradation rate via polyfit
  clipped to +/-2 s/lap, race-context fields, circuit cluster merge from
  N03. 2025 saved as a held-out test set.
- Dataset published to `VforVitorio/f1-strategy-dataset` on Hugging Face;
  `scripts/download_data.py` pulls everything locally.

## [0.1.1] - 2026-04-09

First CLI release (R1 milestone). Distributed as the
`f1_strat_manager-0.1.1-py3-none-any.whl` wheel.

- Seven-agent multi-agent system (N25 to N31) on LangGraph.
- `f1-sim` CLI simulation with Rich Live rendering.
- No-LLM mode (ML + Monte Carlo simulation only).
- OpenF1 radio corpus with Whisper transcription.
- F1 strategic guard-rails baked into every sub-agent.
- Lazy Hugging Face data download on first run.
- Eight ML models (pace, tire degradation, overtake, safety car, pit
  duration, undercut) plus the NLP pipeline (sentiment, intent, NER) and
  RAG over FIA regulations.

[1.1.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v1.1.0
[1.0.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v1.0.0
[0.12.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.12.0
[0.11.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.11.0
[0.10.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.10.0
[0.9.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.9.0
[0.8.1]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.8.1
[0.7.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.7.0
[0.6.0]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.6
[0.1.1]: https://github.com/VforVitorio/F1-StratLab/releases/tag/v0.1.1
