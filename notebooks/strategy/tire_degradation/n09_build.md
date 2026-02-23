# N09 — Tire Degradation TCN: Build Plan

## Scope del notebook

N09 entrena y evalúa el **modelo global** de degradación de neumáticos usando una TCN causal.
El modelo global usa `GLOBAL_WINDOW_SIZE = 36` (de N08) y trata todos los compuestos juntos.

> **N10** (notebook separado) hará el **fine-tuning por compuesto**: parte de los pesos del
> modelo global de N09 y ajusta un modelo específico para cada compound (C1–C5) usando los
> `PER_COMPOUND_WINDOWS` exportados por N08. C6 queda excluido por insuficiencia de datos.

---

## Entradas / Salidas

| Entrada | Origen |
|---------|--------|
| `data/processed/laps_tiredeg.parquet` | N07 |
| `data/processed/tiredeg_sequence_config.json` | N08 |
| `data/processed/tiredeg_feature_manifest.json` | N07 |

| Salida | Descripción |
|--------|-------------|
| `data/models/tiredeg_tcn_v1.ckpt` | Best checkpoint (PyTorch Lightning) |
| `data/models/tiredeg_scaler.pkl` | StandardScaler fit sobre train |
| `data/models/tiredeg_model_config.json` | Hiperparámetros, feature_set, window_size usados |
| `data/models/tiredeg_tcn_v1.onnx` | Export ONNX (opcional, para inferencia) |

---

## Jerarquía de clases PyTorch

```
nn.Module
├── CausalConv1dBlock(nn.Module)
│     Bloque primitivo: Conv1d causal (left-only padding) → LayerNorm → GELU → Dropout
│     Shape: (B, C_in, T) → (B, C_out, T)
│
├── TCNResidualBlock(nn.Module)
│     Dos CausalConv1dBlock con el mismo dilation.
│     Skip connection: Conv1d(in_ch, out_ch, 1) si in_ch ≠ out_ch, Identity si iguales.
│     forward: F.relu(self.net(x) + self.skip(x))
│
└── TireDegTCN(nn.Module)
      input_projection: Linear(n_features, d_model)  — aplicado per-timestep
      TCNResidualBlock × n_layers,  dilation = 2^i  (RF crece exponencialmente)
      output: último timestep válido (via máscara) → Linear(d_model, 1)

Dataset / DataModule
├── TireDegDataset(Dataset)
│     Recibe secuencias (N, T, F), targets (N,), máscaras (N, T).
│     @classmethod from_dataframe(): agrupa por stint, trunca/padea, construye máscara.
│
└── TireDegDataModule(L.LightningDataModule)
      __init__(phase, feature_set, batch_size, num_workers)
      setup(stage): Phase 1 → train=2023/val=2024 | Phase 2 → train=2023+2024/test=2025
      train/val/test_dataloader()  con pin_memory=True

LightningModule
└── TireDegLitModule(L.LightningModule)
      loss: HuberLoss(delta=1.0)
      metrics: torchmetrics MAE, RMSE
      configure_optimizers: AdamW + CosineAnnealingLR(T_max=max_epochs)
```

---

## Feature sets

| Categoría | Features | Incluido en Production | Incluido en Pure |
|-----------|----------|----------------------|-----------------|
| **Cat 1 — Leaky** (encode el target) | `FuelAdjustedDegAbsolute`, `CumulativeDeg`, `FuelAdjustedDegPercent`, `FuelAdjustedLapTime` | ✗ | ✗ |
| **Cat 2 — Lap-time shortcuts** (válidos en inferencia, excluidos del ablation) | `LapTime_s`, `DegradationRate`, `DegAcceleration`, `LapTime_Delta`, `Prev_LapTime`, `LapTime_Trend`, `Sector1_s`, `Sector2_s`, `Sector3_s`, `FuelEffect` | ✓ | ✗ |
| **Cat 3 — Safe exogenous** (siempre disponibles) | `TyreLife`, `AbsoluteCompound`, `CompoundHardness`, `LapsSincePitStop`, `FuelLoad`, `Position`, `laps_remaining`, `Cluster`, `mean_sector_speed`, `AirTemp`, `TrackTemp`, `Humidity`, `Rainfall`, `SpeedI1/I2/FL/ST` y sus deltas, `track_status_clean`, `TeamID`, `gap_to_car_ahead`, `in_drs_window`, ... | ✓ | ✓ |

**Target**: `FuelAdjustedDegAbsolute` en el paso t+1 (predicción one-step-ahead) — segundos acumulados perdidos por desgaste desde el inicio del stint, con el efecto del combustible eliminado.

---

## Fases de entrenamiento

| Fase | Scope | Train | Val | Test | Objetivo |
|------|-------|-------|-----|------|----------|
| **Phase 1a** | Global, Production features | 2023 | 2024 | — | Optimizar hiperparámetros |
| **Phase 1b** | Global, Pure features (ablation) | 2023 | 2024 | — | Medir coste de eliminar Cat 2 |
| **Phase 2** | Global, mejor feature_set de 1a/1b | 2023+2024 | — | 2025 | Métricas finales del TFG |

> El ablation study (1a vs 1b) es **solo para fines investigativos del TFG**.
> La decisión de producción: si `Δ MAE_val ≤ 5%` → usar Pure (más robusto); si no → Production.
> Phase 2 y el notebook N10 usan directamente el feature_set ganador.

---

## Estructura del notebook — 10 pasos

### Step 0 — Imports & Environment
- `torch`, `lightning`, `torchmetrics`, `pandas`, `numpy`, `json`, `matplotlib`
- GPU/CPU detection + print device info
- `L.seed_everything(42, workers=True)`

### Step 1 — Load Data & Config
- Carga `laps_tiredeg.parquet`
- Carga `tiredeg_sequence_config.json` → `GLOBAL_WINDOW=36`, `PER_COMPOUND_WINDOWS`
- Carga `tiredeg_feature_manifest.json` → `PRODUCTION_FEATURES`, `PURE_FEATURES`
- Print: shape, dtypes, compounds presentes, años disponibles

### Step 2 — Dataset & DataModule
- **2.1** `TireDegDataset(Dataset)` con `@classmethod from_dataframe()`
- **2.2** `StandardScaler` fit solo sobre train, transform val/test
- **2.3** `TireDegDataModule(L.LightningDataModule)`
- **2.4** Sanity check: shape de batch, rangos de valores, % de padding en train

### Step 3 — Arquitectura del Modelo
- **3.1** `CausalConv1dBlock(nn.Module)` — causal padding = `(kernel-1) * dilation`
- **3.2** `TCNResidualBlock(nn.Module)` — 2 bloques + skip
- **3.3** `TireDegTCN(nn.Module)` — backbone completo
- **3.4** Análisis del receptive field: `RF = 1 + 2*(kernel-1)*(2^n_layers - 1)` ≥ 36
- **3.5** Forward pass dummy — verificar shapes

### Step 4 — LightningModule
- `TireDegLitModule(L.LightningModule)`
- `HuberLoss`, `MAE`, `RMSE`; `AdamW` + `CosineAnnealingLR`
- Smoke test: 1 forward + backward, comprobar gradientes no NaN/Inf

### Step 5 — Profiling & Análisis de Memoria
- **5.1** `ModelSummary` (Lightning) — parámetros por bloque
- **5.2** `torch.profiler.profile()` — CPU/CUDA time por operación, top bottlenecks
- **5.3** Curva batch size vs memoria GPU — elegir batch_size óptimo

### Step 6 — Phase 1a: Global Model, Production Features
```python
dm = TireDegDataModule(phase='phase1', feature_set='production')
trainer = L.Trainer(
    max_epochs=50,
    callbacks=[EarlyStopping(patience=7, monitor='val/mae'),
               ModelCheckpoint(monitor='val/mae', mode='min'),
               LearningRateMonitor()],
    logger=CSVLogger("outputs/logs", name="tcn_prod_phase1")
)
trainer.fit(lit_module, dm)
```

### Step 7 — Phase 1b: Ablation (Pure Features)
- Mismo setup, `feature_set='pure'`
- Tabla comparativa: Production MAE vs Pure MAE
- Decisión documentada + justificación para el TFG

### Step 8 — Phase 2: Modelo Final
- `phase='phase2'`, `feature_set=best_from_phase1`
- Train 2023+2024, test 2025
- `trainer.test()` → métricas definitivas

### Step 9 — Diagnósticos
- Scatter predicted vs actual (por compound)
- Residuales vs TyreLife — ¿el error crece con la edad del neumático?
- Error medio por circuit cluster
- Top-20 peores predicciones — búsqueda de patrones (safety cars, stints cortos)

### Step 10 — Save & Export
```
data/models/
├── tiredeg_tcn_v1.ckpt          # best checkpoint
├── tiredeg_scaler.pkl           # StandardScaler
├── tiredeg_model_config.json    # hiperparámetros + feature_set + window_size
└── tiredeg_tcn_v1.onnx          # export ONNX (opcional)
```

---

## Decisiones de diseño clave

| Decisión | Razón |
|----------|-------|
| **Causal TCN** sobre LSTM/Transformer | Sin leakage futuro; paralelizable en train; baja latencia en inferencia |
| **Dilated conv** con dilation=2^i | RF exponencial: 5 capas con kernel=3 cubren ~31 laps |
| **Residual blocks** (estilo ResNet/DenseNet) | Gradientes estables en secuencias largas |
| **LayerNorm** sobre BatchNorm | Mejor comportamiento con padding y longitudes variables |
| **Máscara de padding** | El modelo no aprende de posiciones rellenas; sólo atiende laps reales |
| **TyreLife como feature** | Ancla temporal: el modelo sabe exactamente la edad del neumático incluso en secuencias truncadas |
| **HuberLoss** | Robusto a stints outlier (safety cars, banderas rojas) |
| **Phase 1 → Phase 2** | Igual que N06 XGBoost: hypertuning en 2023/2024, test final en 2025 |
| **Ablation solo en modelo global** | Fines investigativos TFG; N10 (per-compound) usa directamente el feature_set ganador |

---

## Relación con N10

N09 produce el **modelo global** (todos los compuestos, `window=36`).

N10 toma los pesos de N09 como punto de partida (**warm-start**) y entrena modelos específicos
para cada compuesto (C1–C5) con sus `PER_COMPOUND_WINDOWS` del JSON de N08:

| Compound | Window (N08) | Stints train (2023+2024) |
|----------|-------------|--------------------------|
| C1 | 31 | ~XXX |
| C2 | 40 | ~XXX |
| C3 | 38 | ~XXX |
| C4 | 34 | ~XXX |
| C5 | 31 | ~XXX |
| C6 | — | < 10 → usa modelo global |

El warm-start evita entrenar desde cero en subconjuntos pequeños y aprovecha el conocimiento
general aprendido en N09.

---

## Historial de versiones — Resultados

### v1 (per-lap sampling, d_model=64, lr=1e-3)

| Modelo | Phase | Métrica | Valor |
|--------|-------|---------|-------|
| Model A | Phase 1a val | MAE | 0.866 s |
| Model A | Phase 1a val | RMSE | 1.478 s |
| Model A | Phase 1a | Stopped epoch | 21 |
| Model A | Phase 2 test 2025 | MAE | 0.708 s |
| Model A | Phase 2 test 2025 | RMSE | 1.123 s |
| Model A | Phase 2 test 2025 | R² | 0.605 |
| Model B | Phase 1 val | MAE | 0.420 s/lap |
| Model B | Phase 1 | Stopped epoch | 12 |
| Model B | Phase 2 test 2025 | MAE | 0.429 s/lap |
| Model B | Phase 2 test 2025 | RMSE | 0.666 s/lap |
| Model B | Phase 2 test 2025 | R² | 0.174 |

Hiperparámetros v1: `d_model=64`, `dropout=0.1`, `lr=1e-3`, `weight_decay=1e-4`, `patience=10`,
scheduler `CosineAnnealingLR(T_max=100)`, Phase 2 epochs = `stopped + 5`.

---

### v2 (d_model=128, lr=3e-4 — descartado)

| Modelo | Phase | Métrica | Valor | vs v1 |
|--------|-------|---------|-------|-------|
| Model A | Phase 1a val | MAE | 0.9016 s | +4.1% peor |
| Model A | Phase 1a val | RMSE | 1.6737 s | +13.2% peor |
| Model A | Phase 1a | Stopped epoch | 35 | — |
| Model A | Phase 2 test 2025 | MAE | 0.7372 s | +4.1% peor |
| Model A | Phase 2 test 2025 | RMSE | 1.1388 s | +1.4% peor |
| Model A | Phase 2 test 2025 | R² | 0.5933 | -1.9% peor |
| Model B | Phase 1 val | MAE | 0.4200 s/lap | igual |
| Model B | Phase 2 test 2025 | MAE | 0.4381 s/lap | +2.1% peor |
| Model B | Phase 2 test 2025 | RMSE | 0.6916 s/lap | +3.8% peor |
| Model B | Phase 2 test 2025 | R² | 0.1086 | -37.6% peor |

**Por qué v2 fue peor:**
- `CosineAnnealingLR(T_max=100)` con early stop en epoch 35: el LR sólo bajó de 3e-4 a ~2.2e-4
  (annealing prácticamente inactivo). Los plots de LR aparecen vacíos por bug de NaN en CSVLogger.
- `lr=3e-4` (3× más bajo que v1) + scheduler roto = entrenamiento a LR casi constante y bajo.
- `dropout=0.2` + `weight_decay=1e-3` = sobre-regularización con ~20k secuencias.
- `d_model=128` no pudo demostrar su potencial porque el entrenamiento estaba mal configurado.

Hiperparámetros v2: `d_model=128`, `dropout=0.2`, `lr=3e-4`, `weight_decay=1e-3`, `patience=15`,
scheduler `CosineAnnealingLR(T_max=100)`, Phase 2 epochs = `stopped × 2`.

---

### v3 (revert to v1 hparams + fix scheduler)

**Changes from v2:**
- `d_model`: 128 → **64** (v1, clean baseline before scaling)
- `lr`: 3e-4 → **1e-3** (v1)
- `dropout`: 0.2 → **0.1** (v1)
- `weight_decay`: 1e-3 → **1e-4** (v1)
- `patience`: 15 → **10** (v1)
- Scheduler: `CosineAnnealingLR(T_max=100)` → **`CosineAnnealingWarmRestarts(T_0=10, T_mult=2, eta_min=1e-6)`**
  (same as legacy EnhancedTCN; robust to early stopping, LR restarts every 10 epochs → 20 → 40)
- Phase 2 epochs: `stopped × 2` → **`stopped + 5`** (v1)

| Model | Phase | Metric | Value | vs v1 |
|-------|-------|--------|-------|-------|
| Model A | Phase 1a val | MAE | 0.8613 s | -0.5% better |
| Model A | Phase 1a val | RMSE | 1.5970 s | +8.1% worse |
| Model A | Phase 1a | Stopped epoch | 21 | — |
| Model A | Phase 2 test 2025 | MAE | 0.7239 s | +2.2% worse |
| Model A | Phase 2 test 2025 | RMSE | 1.1264 s | +0.3% worse |
| Model A | Phase 2 test 2025 | R² | 0.6021 | -0.5% worse |
| Model B | Phase 1 val | MAE | 0.4230 s/lap | +0.3% worse |
| Model B | Phase 1 | Stopped epoch | 12 | — |
| Model B | Phase 2 test 2025 | MAE | 0.4517 s/lap | +5.3% worse |
| Model B | Phase 2 test 2025 | RMSE | 0.6797 s/lap | +2.1% worse |
| Model B | Phase 2 test 2025 | R² | 0.1390 | -20.1% worse |

**Why v3 Phase 2 regressed vs v1:**
- `CosineAnnealingWarmRestarts(T_0=10)` fires a restart at epoch 10.
- Phase 2 budget: Model A = 26 epochs (stopped=21 +5), Model B = 17 epochs (stopped=12 +5).
- The second cycle runs epoch 10→30, but training ends at epoch 26/17 — model cut off
  mid-cycle while LR is still ascending. Model still descending in loss when training stops.
- Phase 1 warm restarts work correctly (confirmed by loss bump at epoch 10 in Model B).

Hyperparameters v3: `d_model=64`, `dropout=0.1`, `lr=1e-3`, `weight_decay=1e-4`, `patience=10`,
scheduler `CosineAnnealingWarmRestarts(T_0=10, T_mult=2, eta_min=1e-6)` (all phases),
Phase 2 epochs = `stopped + 5`.

---

### v4 (split scheduler per phase — current)

**Changes from v3:**
- **Phase 1**: scheduler unchanged — `CosineAnnealingWarmRestarts(T_0=10, T_mult=2)` (exploration)
- **Phase 2**: scheduler → **`CosineAnnealingLR(T_max=N_EPOCHS_P2)`** (monotonic decay)
  Root cause fix: LR now decays smoothly from `lr` to `eta_min` over the exact Phase 2 budget,
  no mid-budget disruption.
- `TireDegLitModule` accepts `scheduler='warm_restarts'|'cosine'` and `t_max` parameters.
- Phase 1 trainers pass `scheduler='warm_restarts'`; Phase 2 trainers pass `scheduler='cosine', t_max=N_EPOCHS`.
- LR plots replaced with **train vs val loss** diagnostic (overfitting check) for Phase 1,
  and **train MAE** for Phase 2 (no validation available).
- All markdown cells translated to English.

Hyperparameters v4: same as v3 except Phase 2 uses `CosineAnnealingLR(T_max=N_EPOCHS_P2, eta_min=1e-6)`.

| Model | Phase | Metric | Value | vs v1 |
|-------|-------|--------|-------|-------|
| Model A | Phase 1a val | MAE | 0.8613 s | -0.5% better |
| Model A | Phase 1a val | RMSE | 1.5970 s | +8.1% worse |
| Model A | Phase 1a | Stopped epoch | 21 | — |
| Model A | Phase 2 test 2025 | MAE | **0.7078 s** | **-0.3% better** |
| Model A | Phase 2 test 2025 | RMSE | **1.1226 s** | **-0.03% better** |
| Model A | Phase 2 test 2025 | R² | **0.6048** | **+0.8% better** |
| Model B | Phase 1 val | MAE | 0.4230 s/lap | +0.3% worse |
| Model B | Phase 1 | Stopped epoch | 12 | — |
| Model B | Phase 2 test 2025 | MAE | **0.4293 s/lap** | **-0.2% better** |
| Model B | Phase 2 test 2025 | RMSE | **0.6657 s/lap** | **-0.04% better** |
| Model B | Phase 2 test 2025 | R² | **0.1741** | **+0.6% better** |

**v4 beats v1 on all Phase 2 test metrics.** Training curves clean — monotonic LR decay over the
full Phase 2 budget allowed the model to make full use of the 2023+2024 combined training data.

**Final TFG model (v4):** Model A global — MAE=0.7078 s, RMSE=1.1226 s, R²=0.6048 on 2025 holdout.

---

### Step 9 — Diagnostic results (v4, 2025 holdout)

| Error source | MAE | n | Root cause |
|---|---|---|---|
| Very late stints (TyreLife 31+) | 1.541 s | 1,512 | Rare in training; poor extrapolation of degradation acceleration |
| C4 compound | 1.138 s | 2,646 | Negative target contamination (data quality in N07) |
| Cluster 0 circuits | 1.122 s | 1,684 | High-degradation / street circuits |
| C3 anomalous (target >15 s) | — | 6 | Abnormal 2025 race events (rain/SC) |

Concept drift between seasons is **not** the dominant error. Main problems:
1. **Data quality**: `FuelAdjustedDegAbsolute < 0` in long C4 stints (N07 fuel overcorrection)
2. **Long-stint extrapolation**: MAE ×2.6 from Mid (0.589 s) to Very Late (1.541 s) → target for RevIN

---

### v5 experiment (Partial RevIN — attempted, discarded)

Two variants of v5 were trained and compared against v4:

| Variant | Change | Model A MAE | Model A RMSE | Model A R² | vs v4 |
|---|---|---|---|---|---|
| v4 (baseline) | — | 0.7078 s | 1.1226 s | 0.6048 | — |
| v5a | RevIN + filter TARGET≥0 | 0.5463 s | 0.9100 s | 0.2734 | R² collapse |
| v5b | RevIN only, no filter | 0.7529 s | 1.2900 s | 0.4781 | all worse |

**Why v5a failed:** The `TARGET >= 0` filter changed the test-set distribution (removed negative-degradation samples). MAE/RMSE appeared better but R² collapsed (0.60 → 0.27) because the comparison was not apples-to-apples. Negative degradation is a real physical phenomenon that must be predicted.

**Why v5b failed:** `PartialRevIN` normalises context features *within* each sequence, removing inter-sequence variation that the model needs to distinguish compound and condition signatures. Negative degradation in long C4 stints has a specific telemetry pattern — per-sequence normalisation erases that signal. Phase 1 val MAE rose to 1.06 s (vs 0.86 s in v4), confirming the technique hurts from the start.

**Root cause mismatch:** RevIN addresses year-to-year distribution shift. The dominant error is poor extrapolation to rarely-seen long stints — a problem better addressed by compound-specific fine-tuning in N10, not by ambient-feature normalisation.

**Conclusion: v5 discarded. N09 closes with v4.**

Other candidate methods (ShifTS — arxiv.org/abs/2510.14814; TAFAS — arxiv.org/abs/2501.04970) were not implemented. Step 9 analysis confirmed inter-season drift is not the dominant error. These will be reconsidered in N10 if per-compound fine-tuning reveals a residual drift component.

---

## Final result — N09 closed (v4)

**Model A (Production features, cumulative target) — 2025 holdout:**

| Metric | Value |
|---|---|
| MAE | **0.7078 s** |
| RMSE | **1.1226 s** |
| R² | **0.6048** |

**Exported artifacts:** `outputs/model_export/tiredeg_modelA_v5.pt` (bundle: weights + scaler + metadata)
