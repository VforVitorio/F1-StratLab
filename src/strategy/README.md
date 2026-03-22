# src/strategy — Strategy Model Modules (Jupytext exports)

**Status: Jupytext export / reference** — not imported by current agent notebooks.

These are Jupytext `.py` exports from early strategy notebooks. They contain the
model architectures and prediction utilities developed before the LightGBM-based
strategy models (N06–N16) replaced the earlier TCN and XGBoost experiments.

---

## Subdirectories

### `models/`

| File | Source | Description |
|---|---|---|
| `lap_time_model.py` | N05-N06 era | `load_lap_prediction_model()`, `predict_lap_times()`; XGBoost/pickle-based lap time predictor; hard-coded compound color maps |
| `tire_degradation_model.py` | N01-N08 era | `calculate_fuel_adjusted_metrics()` and supporting helpers; analytical fuel-adjusted degradation baseline used before the TCN |

### `inference/`

| File | Source | Description |
|---|---|---|
| `tire_predictor.py` | N09 era | `EnhancedTCN` PyTorch module (dilated conv1d, multi-scale, MC Dropout); `predict_tire_degradation()` inference function; loads `.pth` state dict |

### `training/`

Empty — training code lives in the notebooks.

---

## Production models

The current production tire degradation model is the per-compound fine-tuned TCN
from N10, exported to `data/models/tire_degradation/`. The lap time model is the
XGBoost delta predictor from N06 (`data/models/lap_time/`).

These `src/strategy/` files pre-date those exports and use different model
architectures or APIs. Do not rely on them for inference in agent code.

---

## Developed in

- [`notebooks/strategy/lap_time_prediction/N06_laptime_model.ipynb`](../../notebooks/strategy/lap_time_prediction/N06_laptime_model.ipynb)
- [`notebooks/strategy/tire_degradation/N09_tiredeg_tcn.ipynb`](../../notebooks/strategy/tire_degradation/N09_tiredeg_tcn.ipynb)
- [`notebooks/strategy/tire_degradation/N10_tiredeg_compound_finetuning.ipynb`](../../notebooks/strategy/tire_degradation/N10_tiredeg_compound_finetuning.ipynb)
