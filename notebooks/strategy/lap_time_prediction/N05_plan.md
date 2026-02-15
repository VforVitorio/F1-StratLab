# N05 — Lap Time EDA: Plan de Notebook

**Archivo:** `N05_laptime_eda.ipynb`
**Carpeta:** `notebooks/strategy/lap_time_prediction/`
**Input:** `data/processed/laps_featured_2023.parquet` + `laps_featured_2024.parquet`
**Output:** `data/processed/feature_manifest_laptime.json`

---

## Step 1: Carga y visión general

- Cargar 2023 + 2024 concatenados → ~45,362 laps
- Shape, dtypes, null rates de las 49 columnas (48 de N04 + `lap_time_pct_of_race_fastest`)
- Distribución de filas por año / GP / compuesto

---

## Step 2: Análisis del target — `LapTime_s`

*Heredado del legacy `lap_prediction.ipynb`*

- Histograma global + por año → **visualizar el concept drift**
- Box plots por circuito ordenados por mediana (24 circuitos)
- Mediana `LapTime_s` por `Year + GP_Name`: línea que baja año a año → drift cuantificado en segundos
- Distribución por `Compound` (SOFT/MEDIUM/HARD): heredado del legacy `plot_tire_degradation_by_compound()`
- Distribución por `Cluster` (0–3): ¿los 4 arquetipos tienen rangos claramente separados?

---

## Step 3: Cuantificación del concept drift

*Nuevo — no estaba en el legacy*

- Tabla: mediana `LapTime_s` por `Year × GP_Name`, delta 2023→2024
- Distribución del delta: ¿cuántos circuitos mejoran más de 1 s?
- Validar que `lap_time_pct_of_race_fastest` es más estable entre años que `LapTime_s`
  → scatter con coeficiente de variación por circuito
- Comparativa: CV de `LapTime_s` vs CV de `lap_time_pct_of_race_fastest` por circuito

---

## Step 4: Features anti-drift adicionales

*Del `lap_time_prediction_plan.md` — features calculadas aquí en el EDA, no en N04*

| Feature nueva | Cálculo |
|---------------|---------|
| `delta_vs_year_circuit_median` | `LapTime_s - median(LapTime_s por Year+GP_Name)` |
| `year_circuit_median` | Mediana absoluta de la sesión (nivel base para el modelo) |
| `team_pace_rank` | Ranking del equipo por media de vuelta ese año en ese circuito |

- Describir distribuciones de las 3 nuevas features
- Añadirlas al dataframe → entran como features en N06
- **Limitación documentada:** en inferencia real 2026+ habría que estimar `year_circuit_median`
  desde datos de libres/clasificación; para el TFG se calcula directamente con datos 2025

---

## Step 5: Análisis de degradación por compuesto

*Heredado directo del legacy `N01_tire_prediction.ipynb`*

- `LapTime_s` vs `TyreLife` por compuesto — scatter con error bands (`plot_tire_degradation_by_compound()`)
- `LapTime_Delta` vs `TyreLife` por compuesto — tasa de degradación media
- Comparar `LapTime_s` vs `FuelAdjustedLapTime` vs `TyreLife` → confirmar que la corrección de combustible importa para lap time también
- Sector speeds vs TyreLife (`SpeedI1/I2/FL/ST`) — ¿qué sector se degrada más?

---

## Step 6: Correlaciones

*Del legacy `lap_prediction.ipynb`: correlation matrix full + reducida*

- Tabla de correlación con el target `LapTime_s` (todas las features, ordenadas por `|corr|`)
- Identificar redundancias conocidas:
  - `SpeedI1/I2/FL/ST` entre sí
  - `Prev_Speed*` vs `Speed*`
  - `FuelAdjustedLapTime` vs `LapTime_s`
- Heatmap reducido: solo features con `|corr| > 0.05` con el target

---

## Step 7: Feature importance rápida

*Del plan `lap_time_prediction_plan.md` — permutation importance*

- XGBoost con defaults, fit en 2023, evaluar en 2024 (split temporal mínimo)
- Feature importance nativa de XGBoost (gain) → barplot top-20
- Confirmar que `Prev_LapTime`, `TyreLife`, `FuelAdjustedLapTime`, `lap_time_pct_of_race_fastest` están en el top
- **Este modelo NO es el definitivo** — es solo orientación para la selección de features en N06

---

## Step 8: Outliers

- `LapTime_s` > percentil 99 y < percentil 1: ¿son válidos o ruido residual post-filtro?
- Por circuito: identificar circuitos con distribución rara (alto CV)
- Decisión documentada: ¿clipear o mantener?

---

## Step 9: Decisión del feature set final

- Lista explícita: features **IN** (con justificación) y **OUT** (con motivo)
- Candidatos OUT:
  - `Driver` (string, no codificable directamente)
  - `GP_Name` (usamos `Cluster` en su lugar)
  - Redundancias en speed deltas
- Tratamiento de categóricas: `Compound`, `race_phase` → one-hot en N06
- Exportar `data/processed/feature_manifest_laptime.json`

---

## Referencia legacy

| Notebook legacy | Qué reutilizamos |
|----------------|-----------------|
| `lap_prediction.ipynb` | Análisis correlaciones, DRS, feature importance, plots scatter predictions vs actual |
| `N01_tire_prediction.ipynb` | `plot_tire_degradation_by_compound()`, fuel adjustment analysis, sector speed vs TyreLife |
| `N00_model_lap_prediction.ipynb` | Lista de 25 features del modelo secuencial (referencia para no olvidar features que funcionaron) |
