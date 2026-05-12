# Thesis results

Visual and numeric outputs referenced by chapter 5 of the TFG thesis. Every figure on this page is regenerated automatically from the notebooks under `notebooks/agents/` so it always tracks the latest model artefacts.

## Threshold sweeps

Each classifier sub-agent exposes a precision-recall trade-off that the strategist picks deliberately. The sweeps below scan the full threshold space and mark the production operating point.

### Overtake (N12)

![Overtake threshold sweep — precision and recall against threshold, plus parametric precision-recall curve with the 0,7976 production threshold ringed in red](../_external_images/05_results/threshold_sweep_overtake.png){ loading=lazy }

Production threshold 0,7976 was tuned in N12 step 5 on the raw LightGBM scores. The right panel shows the trade-off is robust around that point: F1 stays within a few hundredths across the neighbouring grid.

### Safety Car (N14)

![Safety Car threshold sweep — note the AUC-PR is 0,0723 (vs 0,0432 baseline) so the absolute precision stays low across all thresholds](../_external_images/05_results/threshold_sweep_sc.png){ loading=lazy }

The Safety Car model is a soft contextual prior, not an exact predictor. The 0,234 production threshold is F2-optimal (recall-weighted) because false alarms cost little and missing an imminent SC is expensive.

### Undercut (N16)

![Undercut threshold sweep — flat F1 region around the 0,522 production threshold confirms a robust operating point](../_external_images/05_results/threshold_sweep_undercut.png){ loading=lazy }

The undercut classifier sees the highest positive prevalence of the three (>30 % on the holdout) because the labelling step kept only pairs with a true undercut opportunity. The 0,522 threshold falls in the flat F1 region.

## MC Dropout coverage

The TCN tire-degradation model (N09 global + N10 per-compound fine-tunes) uses 50-pass MC Dropout to produce P10 / P50 / P90 percentile bands. The figure below reports both the raw [P10, P90] coverage (epistemic only) and the calibrated coverage that adds the empirical residual sigma (aleatoric included).

![MC Dropout coverage — bar chart per compound (raw blue, calibrated orange) with 0,80 reference line, plus a calibration scatter of mean predicted sigma vs empirical residual sigma](../_external_images/05_results/mc_dropout_coverage.png){ loading=lazy }

Raw coverage stays around 0,20 across all compounds — active dropout only captures the model-weight uncertainty, not the lap-to-lap aleatoric noise. The calibrated coverage matches the 0,80 nominal target by construction, and the right panel quantifies how much extra band width the production agent needs to add when projecting degradation forward several laps.

## How to regenerate

```bash
# Threshold sweeps + MC Dropout figures (one notebook, ~5 min on GPU)
uv run jupyter nbconvert --execute --inplace notebooks/agents/N33_thresholds_and_calibration.ipynb

# Quantitative RAG benchmark (10-15 min, builds 2 additional Qdrant collections)
uv run jupyter nbconvert --execute --inplace notebooks/agents/N30B_rag_benchmark.ipynb
```

Both notebooks emit CSV and Markdown tables alongside their PNGs:

- Sweeps: `data/eval/threshold_sweep_{overtake,sc,undercut}.{csv,md}`
- MC Dropout: `data/eval/mc_dropout_coverage.{csv,md}`
- RAG benchmark: `data/rag_eval/results_v1.md`

See [`data/eval/README.md`](https://github.com/VforVitorio/F1-StratLab/blob/main/data/eval/README.md) for the full inventory and [`data/rag_eval/README.md`](https://github.com/VforVitorio/F1-StratLab/blob/main/data/rag_eval/README.md) for the RAG eval set conventions.

## Numeric headline metrics

| Component | Metric | Value | Source |
|---|---|---|---|
| Pace model (N06 XGBoost) | MAE on 2025 holdout | 0,410 s | `data/eval/pace_baselines.{csv,md}` |
| Whisper turbo (CUDA) | mean per-clip latency | 233,9 ms (P95 325,8 ms) | `data/eval/whisper_results.{csv,md}` |
| NLP pipeline (GPU) | mean `run_pipeline` | 42,1 ms | `data/eval/nlp_pipeline_cpu.{csv,md}` |
| Sub-agent latency (single lap) | min / max mean | 270 ms (pace) / 4,4 s (rag w/ LLM) | `data/eval/subagent_latency.{csv,md}` |
| RAG agent | Content P@5 (production retriever) | 0,80 | `data/rag_eval/results_v1.md` |
| MC Dropout (C2) | calibrated 80% coverage | 0,840 | `data/eval/mc_dropout_coverage.{csv,md}` |

All numbers reproducible with the commands above.
