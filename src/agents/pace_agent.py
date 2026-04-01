"""Pace Agent — src/agents/pace_agent.py

Extracted from N25_pace_agent.ipynb. Wraps the N06 XGBoost delta-lap-time
model into a clean agent interface that returns lap time predictions, delta
signals, and bootstrap confidence intervals.

Public API
----------
run_pace_agent(**kwargs)               → PaceOutput   (flat kwargs, same signature as N25)
run_pace_agent_from_state(lap_state)   → PaceOutput   (adapter for RaceStateManager output)
get_pace_react_agent()                 → LangGraph ReAct agent (lazy, LLM required)

Module-level singletons
-----------------------
MODEL, FEATURES       — N06 XGBoost model + ordered feature list, loaded at import
COMPOUND_ID           — compound string → int encoding
CIRCUIT_CLUSTER       — GP name → cluster int (0-3)
TEAM_ID               — team name → int encoding
LAPS_REF              — reference parquet for session median computation
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

# ── Repo root (module-relative, works regardless of cwd) ─────────────────────
_REPO_ROOT = Path(__file__).resolve().parent
while not (_REPO_ROOT / '.git').exists():
    _REPO_ROOT = _REPO_ROOT.parent

_MODELS_DIR   = _REPO_ROOT / 'data' / 'models' / 'lap_time'
_PROCESSED    = _REPO_ROOT / 'data' / 'processed'

# ── Constants ─────────────────────────────────────────────────────────────────
N_BOOTSTRAP = 200
_NOISE_PCT   = 0.02   # 2% Gaussian noise on continuous features — approximates sensor noise

# ── Artifact paths ────────────────────────────────────────────────────────────
_CLUSTER_PARQUET  = _PROCESSED / 'circuit_clustering' / 'circuit_clusters_k4_2025.parquet'
_LAPS_FEATURED    = _PROCESSED / 'laps_featured_2025.parquet'
_FEATURE_MANIFEST = _PROCESSED / 'feature_manifest_laptime.json'


# ─────────────────────────────────────────────────────────────────────────────
# Model loading
# ─────────────────────────────────────────────────────────────────────────────

def load_pace_model(models_dir: Path = _MODELS_DIR):
    """Load the N06 XGBoost lap time delta model and its ordered feature name list.

    Separates model loading from inference so the expensive I/O happens once at
    module import time. Both artifacts are returned together to guarantee the
    feature order is always consistent with the model version on disk — callers
    must not reorder or drop features between load and predict.

    Args:
        models_dir: Directory containing xgb_laptime_delta_final.json and
            xgb_laptime_delta_feature_names.json. Defaults to the global path
            resolved from the repo root at import time.

    Returns:
        Tuple (model, features) where model is a fitted xgb.XGBRegressor and
        features is a list of column name strings in the exact order the model
        expects at predict time.
    """
    features = json.loads(
        (models_dir / 'xgb_laptime_delta_feature_names.json').read_text()
    )
    model = xgb.XGBRegressor()
    model.load_model(models_dir / 'xgb_laptime_delta_final.json')
    return model, features


def load_encoding_maps():
    """Load the three categorical encoding maps used by build_lap_state.

    Reads the compound encoding from the N06 feature manifest, the circuit
    cluster assignments from the k=4 clustering parquet (N05), and the
    team-to-integer map derived from the laps_featured parquet. All three are
    static training artifacts — they must not be recomputed at inference time
    to avoid encoding drift between train and serve.

    Returns:
        Tuple (compound_id, circuit_cluster, team_id) where:
        - compound_id (dict): maps Pirelli compound string → integer code.
        - circuit_cluster (dict): maps GP_Name string → cluster integer (0–3).
        - team_id (dict): maps team name string → integer code used by N06.
    """
    manifest    = json.loads(_FEATURE_MANIFEST.read_text())
    compound_id = manifest['categorical_encoding']['Compound']

    clusters_df = pd.read_parquet(_CLUSTER_PARQUET)[['GP_Name', 'Cluster']]
    circuit_cluster = dict(
        zip(clusters_df['GP_Name'], clusters_df['Cluster'].astype(int))
    )

    laps = pd.read_parquet(_LAPS_FEATURED, columns=['Team', 'TeamID']).dropna()
    team_id = (
        laps.drop_duplicates('Team')
            .set_index('Team')['TeamID']
            .astype(int)
            .to_dict()
    )

    return compound_id, circuit_cluster, team_id


# ── Module-level singletons (loaded once at import) ──────────────────────────
MODEL, FEATURES               = load_pace_model()
COMPOUND_ID, CIRCUIT_CLUSTER, TEAM_ID = load_encoding_maps()
LAPS_REF = pd.read_parquet(
    _LAPS_FEATURED,
    columns=['GP_Name', 'Year', 'Compound', 'LapTime_s']
)


# ─────────────────────────────────────────────────────────────────────────────
# Feature preparation
# ─────────────────────────────────────────────────────────────────────────────

def build_lap_state(
    driver_number, lap_number, stint, tyre_life, compound,
    position, team, laps_since_pit, fuel_load, year,
    prev_lap_time, prev_tyre_life, prev_speed_st,
    air_temp, track_temp, humidity, rainfall,
    total_laps, gp_name,
    mean_sector_speed=None,
    prev_deg_rate=0.0, prev_cum_deg=0.0, prev_deg_accel=0.0,
) -> pd.DataFrame:
    """Pack raw race state into a single-row DataFrame ready for MODEL.predict().

    Encodes categorical inputs (compound, team, circuit cluster) using the global
    lookup maps loaded from training artifacts, derives computed features (FreshTyre,
    FuelEffect, laps_remaining), and selects columns in the exact order FEATURES
    expects. Unknown categories degrade gracefully: compound→1, team→0, cluster→1.

    mean_sector_speed defaults to prev_speed_st when None — covers the case where
    circuit_features data is unavailable for the current GP.

    Args:
        driver_number: Car number (int) for TeamID lookup.
        lap_number: Current race lap number (1-indexed).
        stint: Stint number (1-indexed).
        tyre_life: Laps on the current tyre set.
        compound: Pirelli compound string ('SOFT', 'MEDIUM', 'HARD', etc.).
        position: Current race position (1-based integer).
        team: Team name string matching TEAM_ID keys.
        laps_since_pit: Integer laps elapsed since the last pit stop.
        fuel_load: Fuel fraction in [0, 1] estimated as laps_remaining/total_laps.
        year: Race year integer (2023/2024/2025).
        prev_lap_time: Previous lap time in seconds.
        prev_tyre_life: TyreLife on the previous lap.
        prev_speed_st: Speed trap (km/h) from the previous lap.
        air_temp: Air temperature in °C.
        track_temp: Track surface temperature in °C.
        humidity: Relative humidity in %.
        rainfall: Boolean; True if rain was recorded.
        total_laps: Total scheduled race laps.
        gp_name: GP name string matching CIRCUIT_CLUSTER keys.
        mean_sector_speed: Average sector speed in km/h; defaults to prev_speed_st.
        prev_deg_rate: Degradation rate (s/lap) at the previous lap.
        prev_cum_deg: Cumulative degradation (s) at the previous lap.
        prev_deg_accel: Degradation acceleration (s/lap²) at the previous lap.

    Returns:
        Single-row pd.DataFrame with columns in FEATURES order, ready for
        MODEL.predict(). All values are numeric; no NaN cells.
    """
    c_id       = COMPOUND_ID.get(compound, 1)
    t_id       = TEAM_ID.get(team, 0)
    cluster    = CIRCUIT_CLUSTER.get(gp_name, 1)
    fresh_tyre = int(tyre_life <= 1)
    fuel_effect = fuel_load * 0.03
    laps_remaining = max(0, total_laps - lap_number)
    mss = mean_sector_speed if mean_sector_speed is not None else prev_speed_st

    row = {
        'DriverNumber':          driver_number,
        'LapNumber':             lap_number,
        'Stint':                 stint,
        'TyreLife':              tyre_life,
        'FreshTyre':             fresh_tyre,
        'Position':              position,
        'CompoundID':            c_id,
        'TeamID':                t_id,
        'LapsSincePitStop':      laps_since_pit,
        'FuelLoad':              fuel_load,
        'Year':                  year,
        'FuelEffect':            fuel_effect,
        'Prev_LapTime':          prev_lap_time,
        'Prev_TyreLife':         prev_tyre_life,
        'Prev_SpeedST':          prev_speed_st,
        'AirTemp':               air_temp,
        'TrackTemp':             track_temp,
        'Humidity':              humidity,
        'Rainfall':              rainfall,
        'laps_remaining':        laps_remaining,
        'Cluster':               cluster,
        'mean_sector_speed':     mss,
        'Prev_DegradationRate':  prev_deg_rate,
        'Prev_CumulativeDeg':    prev_cum_deg,
        'Prev_DegAcceleration':  prev_deg_accel,
    }
    return pd.DataFrame([row])[FEATURES]


# ─────────────────────────────────────────────────────────────────────────────
# Inference
# ─────────────────────────────────────────────────────────────────────────────

def predict_lap_time(lap_state_df: pd.DataFrame, model=None) -> float:
    """Predict the absolute lap time for the current lap.

    The N06 XGBoost model predicts a signed delta vs the previous lap
    (Prev_LapTime), not an absolute time. This function adds the delta back to
    Prev_LapTime so callers always receive an absolute lap time in seconds — the
    unit expected by PaceOutput and N31 Monte Carlo simulation.

    Args:
        lap_state_df: Single-row pd.DataFrame produced by build_lap_state(),
            with columns in FEATURES order. Prev_LapTime must be present.
        model: Trained xgb.XGBRegressor (default: module-level MODEL).

    Returns:
        Absolute predicted lap time in seconds (float).
    """
    m     = model if model is not None else MODEL
    delta = float(m.predict(lap_state_df)[0])
    prev  = float(lap_state_df['Prev_LapTime'].iloc[0])
    return prev + delta


def bootstrap_confidence_interval(
    lap_state_df: pd.DataFrame, model=None, n: int = N_BOOTSTRAP, seed: int = 42
) -> tuple[float, float]:
    """Estimate a P10/P90 confidence interval around the lap time prediction.

    Runs n forward passes, each time adding independent Gaussian noise
    (sigma = NOISE_PCT * feature_value) to the continuous features most subject to
    real-world variability: Prev_LapTime, Prev_SpeedST, mean_sector_speed, AirTemp,
    TrackTemp, TyreLife. The noise scale approximates sensor noise and lap-to-lap
    variation; it is not formal Bayesian uncertainty.

    N31 uses the returned interval to sample pace scenarios in Monte Carlo
    strategy evaluation.

    Args:
        lap_state_df: Single-row pd.DataFrame from build_lap_state().
        model: Trained xgb.XGBRegressor (default: module-level MODEL).
        n: Number of bootstrap samples (default N_BOOTSTRAP = 200).
        seed: Integer seed for the numpy random generator.

    Returns:
        Tuple (p10, p90) of absolute lap times in seconds (float).
    """
    m    = model if model is not None else MODEL
    rng  = np.random.default_rng(seed)
    noise_cols = ['Prev_LapTime', 'Prev_SpeedST', 'mean_sector_speed',
                  'AirTemp', 'TrackTemp', 'TyreLife']

    base    = lap_state_df.values.copy().astype(float)
    col_idx = {c: lap_state_df.columns.get_loc(c) for c in noise_cols}

    preds = []
    for _ in range(n):
        row = base.copy()
        for col, idx in col_idx.items():
            sigma = abs(base[0, idx]) * _NOISE_PCT
            row[0, idx] += rng.normal(0, sigma)
        df_row = pd.DataFrame(row, columns=lap_state_df.columns)
        delta  = float(m.predict(df_row)[0])
        preds.append(float(df_row['Prev_LapTime'].iloc[0]) + delta)

    return float(np.percentile(preds, 10)), float(np.percentile(preds, 90))


def session_median_lap_time(
    gp_name: str, year: int, compound: str, laps_df: pd.DataFrame = None
) -> float | None:
    """Compute the representative median lap time for a GP / year / compound.

    Filters laps_df to the matching GP, year, and compound, then returns the
    median of LapTime_s. The median is a robust baseline unaffected by SC/VSC
    laps (those are excluded from LAPS_REF at load time).

    N31 uses this value to contextualise the absolute predicted lap time —
    a large positive delta_vs_median signals a degrading tyre or a slower
    compound choice relative to historical pace at this circuit.

    Args:
        gp_name: GP name matching the GP_Name column (e.g. 'Barcelona').
        year: Race year integer (2023/2024/2025).
        compound: Pirelli compound string ('SOFT', 'MEDIUM', 'HARD', etc.).
        laps_df: Reference DataFrame; defaults to module-level LAPS_REF.

    Returns:
        Median lap time in seconds (float), or None when no matching laps exist.
    """
    df   = laps_df if laps_df is not None else LAPS_REF
    mask = (
        (df['GP_Name']  == gp_name) &
        (df['Year']     == year)    &
        (df['Compound'] == compound)
    )
    subset = df.loc[mask, 'LapTime_s'].dropna()
    return float(subset.median()) if len(subset) > 0 else None


# ─────────────────────────────────────────────────────────────────────────────
# PaceOutput + entry point
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PaceOutput:
    """Structured output of the Pace Agent for one lap.

    lap_time_pred is the N06 XGBoost prediction in absolute seconds — the model
    outputs a delta vs Prev_LapTime internally; this field adds Prev_LapTime back
    so all downstream agents work in absolute lap time.

    delta_vs_prev is the raw model delta (predicted lap_time minus Prev_LapTime).
    Negative means the driver is faster than the previous lap.

    delta_vs_median is the difference between lap_time_pred and the historical
    session median for this GP/year/compound combination. NaN when no median
    reference is available (new circuits or sparse data).

    ci_p10 and ci_p90 are the P10/P90 bootstrap confidence bounds on
    lap_time_pred, computed over N_BOOTSTRAP perturbations of the continuous
    input features. N31 Monte Carlo simulation samples from this interval to
    model pace uncertainty across strategy candidates.

    reasoning is a human-readable summary forwarded verbatim to the N31
    Orchestrator for LLM synthesis. Format:
    "Lap N: predicted X.XXXs (+/-Xs, faster/slower than prev). CI [X.X-X.Xs]. X.XXXs vs median."
    """
    lap_time_pred:   float
    delta_vs_prev:   float
    delta_vs_median: float
    ci_p10:          float
    ci_p90:          float
    reasoning:       str = ""


def run_pace_agent(
    driver_number, lap_number, stint, tyre_life, compound,
    position, team, laps_since_pit, fuel_load, year,
    prev_lap_time, prev_tyre_life, prev_speed_st,
    air_temp, track_temp, humidity, rainfall,
    total_laps, gp_name,
    mean_sector_speed=None,
    prev_deg_rate=0.0, prev_cum_deg=0.0, prev_deg_accel=0.0,
) -> PaceOutput:
    """Run the Pace Agent for a single lap and return a structured PaceOutput.

    Builds the full N06 feature vector from raw race state, calls the XGBoost
    model, computes a bootstrap P10/P90 uncertainty interval, and looks up the
    historical session median for the current GP/year/compound. Returns a
    PaceOutput with all fields populated and a reasoning string for N31.

    This is the entry point used by predict_pace_tool (LangGraph) and
    run_pace_agent_from_state (RSM adapter). It is stateless — singletons
    (MODEL, LAPS_REF, encoding maps) are loaded once at module import.

    Args:
        driver_number: Car number used to look up TeamID encoding.
        lap_number: Current race lap; used for FuelLoad = laps_remaining/total_laps.
        stint: Stint number (1-indexed), forwarded as a raw feature.
        tyre_life: Laps on current tyre set; drives FreshTyre flag.
        compound: Pirelli compound name ('SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET').
        position: Current race position (1-based).
        team: Team name matching TEAM_ID encoding map (e.g. 'McLaren').
        laps_since_pit: Laps since most recent pit stop.
        fuel_load: Estimated fuel fraction in [0, 1].
        year: Race year (2023/2024/2025).
        prev_lap_time: Previous lap time in seconds.
        prev_tyre_life: TyreLife on the previous lap.
        prev_speed_st: Speed trap reading in km/h from the previous lap.
        air_temp: Air temperature in °C.
        track_temp: Track surface temperature in °C.
        humidity: Relative humidity in %.
        rainfall: True if rain was recorded during this lap.
        total_laps: Total scheduled race laps.
        gp_name: GP name matching CIRCUIT_CLUSTER keys (e.g. 'Sakhir').
        mean_sector_speed: Average sector speed in km/h; defaults to prev_speed_st.
        prev_deg_rate: Degradation rate from the previous lap (s/lap).
        prev_cum_deg: Cumulative degradation at the previous lap.
        prev_deg_accel: Second derivative of degradation (s/lap^2).

    Returns:
        PaceOutput with lap_time_pred, delta_vs_prev, delta_vs_median,
        ci_p10, ci_p90, and a reasoning string for N31 LLM synthesis.
    """
    lap_df = build_lap_state(
        driver_number=driver_number, lap_number=lap_number, stint=stint,
        tyre_life=tyre_life, compound=compound, position=position, team=team,
        laps_since_pit=laps_since_pit, fuel_load=fuel_load, year=year,
        prev_lap_time=prev_lap_time, prev_tyre_life=prev_tyre_life,
        prev_speed_st=prev_speed_st, air_temp=air_temp, track_temp=track_temp,
        humidity=humidity, rainfall=rainfall, total_laps=total_laps,
        gp_name=gp_name, mean_sector_speed=mean_sector_speed,
        prev_deg_rate=prev_deg_rate, prev_cum_deg=prev_cum_deg,
        prev_deg_accel=prev_deg_accel,
    )

    lap_time_pred   = predict_lap_time(lap_df)
    delta_vs_prev   = lap_time_pred - prev_lap_time
    p10, p90        = bootstrap_confidence_interval(lap_df)
    median          = session_median_lap_time(gp_name, year, compound)
    delta_vs_median = (lap_time_pred - median) if median is not None else float('nan')

    trend  = "faster" if delta_vs_prev < 0 else "slower"
    vs_med = (
        f"{delta_vs_median:+.3f}s vs median"
        if median is not None else "no median reference"
    )
    reasoning = (
        f"Lap {lap_number}: predicted {round(lap_time_pred, 3):.3f}s "
        f"({round(delta_vs_prev, 3):+.3f}s, {trend} than prev). "
        f"CI [{round(p10, 1):.1f}-{round(p90, 1):.1f}s]. {vs_med}."
    )

    return PaceOutput(
        lap_time_pred   = round(lap_time_pred, 3),
        delta_vs_prev   = round(delta_vs_prev, 3),
        delta_vs_median = round(delta_vs_median, 3),
        ci_p10          = round(p10, 3),
        ci_p90          = round(p90, 3),
        reasoning       = reasoning,
    )


def run_pace_agent_from_state(lap_state: dict) -> PaceOutput:
    """Adapter: run the Pace Agent from a RaceStateManager lap_state dict.

    Translates the nested lap_state produced by RaceStateManager.get_lap_state()
    into the flat kwargs expected by run_pace_agent. This adapter is used by the
    N31 orchestrator to call sub-agents without knowledge of the RSM schema.

    The RSM provides full telemetry for our driver in lap_state['driver'] and
    session metadata in lap_state['session_meta']. Weather lives in
    lap_state['weather']. Fields absent from the RSM schema (prev_deg_rate,
    prev_cum_deg, prev_deg_accel, mean_sector_speed) default to 0.0/None since
    the replay engine does not compute degradation history.

    Args:
        lap_state: Dict produced by RaceStateManager.get_lap_state(). Expected
            keys: lap_number, driver (full telemetry dict), weather (dict),
            session_meta (gp_name, year, driver, team, total_laps).

    Returns:
        PaceOutput with all fields populated.
    """
    d    = lap_state['driver']
    meta = lap_state['session_meta']
    wx   = lap_state.get('weather', {})

    lap_number    = lap_state['lap_number']
    total_laps    = meta['total_laps']
    laps_remaining = max(0, total_laps - lap_number)

    return run_pace_agent(
        driver_number  = d.get('driver_number', 0),
        lap_number     = lap_number,
        stint          = d.get('stint', 1),
        tyre_life      = d.get('tyre_life', 1),
        compound       = d.get('compound', 'MEDIUM'),
        position       = d.get('position', 1),
        team           = meta.get('team', 'Unknown'),
        laps_since_pit = d.get('tyre_life', 1),       # proxy: tyre_life since last stop
        fuel_load      = laps_remaining / max(total_laps, 1),
        year           = meta.get('year', 2025),
        prev_lap_time  = d.get('lap_time_s') or 90.0,
        prev_tyre_life = max(0, d.get('tyre_life', 1) - 1),
        prev_speed_st  = d.get('speed_st', 300.0),
        air_temp       = wx.get('air_temp', 25.0),
        track_temp     = wx.get('track_temp', 35.0),
        humidity       = wx.get('humidity', 50.0),
        rainfall       = float(wx.get('rainfall', 0)),
        total_laps     = total_laps,
        gp_name        = meta.get('gp_name', ''),
        # degradation history not available from RSM replay — defaults to 0
        prev_deg_rate  = 0.0,
        prev_cum_deg   = 0.0,
        prev_deg_accel = 0.0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph ReAct agent
# ─────────────────────────────────────────────────────────────────────────────

try:
    from langchain_core.tools import tool as lc_tool
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


if _LANGGRAPH_AVAILABLE:

    @lc_tool
    def predict_pace_tool(
        driver_number: int, lap_number: int, stint: int, tyre_life: int,
        compound: str, position: int, team: str, laps_since_pit: int,
        fuel_load: float, year: int, prev_lap_time: float, prev_tyre_life: int,
        prev_speed_st: float, air_temp: float, track_temp: float,
        humidity: float, rainfall: float, total_laps: int, gp_name: str,
    ) -> dict:
        """Predict the absolute lap time (seconds) for the current lap using the N06 XGBoost model.

        Call this whenever a lap time prediction is needed for pace or strategy analysis.

        Args:
            driver_number: Car number used to look up TeamID encoding.
            lap_number: Current race lap number (1-indexed).
            stint: Stint number (1-indexed).
            tyre_life: Laps on the current tyre set.
            compound: Pirelli compound string ('SOFT', 'MEDIUM', 'HARD', etc.).
            position: Current race position (1-based).
            team: Team name matching TEAM_ID encoding map (e.g. 'McLaren').
            laps_since_pit: Laps elapsed since the last pit stop.
            fuel_load: Fuel fraction in [0, 1].
            year: Race year integer (2023/2024/2025).
            prev_lap_time: Previous lap time in seconds.
            prev_tyre_life: TyreLife on the previous lap.
            prev_speed_st: Speed trap reading in km/h from the previous lap.
            air_temp: Air temperature in degrees C.
            track_temp: Track surface temperature in degrees C.
            humidity: Relative humidity in %.
            rainfall: True if rain was recorded during this lap.
            total_laps: Total scheduled race laps.
            gp_name: GP name matching CIRCUIT_CLUSTER keys (e.g. 'Sakhir').

        Returns:
            Dict with keys: lap_time_pred, delta_vs_prev, delta_vs_median,
            ci_p10, ci_p90 (all floats in seconds).
        """
        out = run_pace_agent(
            driver_number=driver_number, lap_number=lap_number, stint=stint,
            tyre_life=tyre_life, compound=compound, position=position, team=team,
            laps_since_pit=laps_since_pit, fuel_load=fuel_load, year=year,
            prev_lap_time=prev_lap_time, prev_tyre_life=prev_tyre_life,
            prev_speed_st=prev_speed_st, air_temp=air_temp, track_temp=track_temp,
            humidity=humidity, rainfall=rainfall, total_laps=total_laps,
            gp_name=gp_name,
        )
        return {
            'lap_time_pred':   out.lap_time_pred,
            'delta_vs_prev':   out.delta_vs_prev,
            'delta_vs_median': out.delta_vs_median,
            'ci_p10':          out.ci_p10,
            'ci_p90':          out.ci_p90,
        }

    @lc_tool
    def get_session_median_tool(gp_name: str, year: int, compound: str) -> dict:
        """Return the historical median lap time (seconds) for a GP / year / compound.

        Use this as a reference baseline to contextualise a predicted lap time from
        predict_pace_tool. The median is computed from the N06 training parquet,
        filtered to IsAccurate laps in non-SC, non-VSC conditions.

        Args:
            gp_name: GP name matching the parquet GP_Name column (e.g. 'Sakhir').
            year: Race year integer (2023/2024/2025).
            compound: Pirelli compound string ('SOFT', 'MEDIUM', 'HARD').

        Returns:
            Dict with key: median_lap_time (float, seconds). NaN when no data.
        """
        median = session_median_lap_time(gp_name, year, compound)
        return {'median_lap_time': median if median is not None else float('nan')}

    _PACE_SYSTEM_PROMPT = """You are the Pace Agent in an F1 race strategy system.

Your responsibility: answer the question "how fast is this car going this lap?"

Tools available:
- `predict_pace_tool` — predicts absolute lap time using the N06 XGBoost model
- `get_session_median_tool` — returns the historical median for this GP/compound as a baseline

Always call `predict_pace_tool` first, then `get_session_median_tool` to contextualise the result.
Respond with a concise JSON summary: lap_time_pred, delta_vs_prev, delta_vs_median, ci_p10, ci_p90.
Never invent numbers — use only the values returned by the tools."""

    PACE_TOOLS = [predict_pace_tool, get_session_median_tool]

    # Lazy singleton — created on first call to get_pace_react_agent()
    _pace_react_agent = None

    def get_pace_react_agent(
        provider: str = 'lmstudio',
        model_name: str = 'local-model',
        base_url: str = 'http://localhost:1234/v1',
        api_key: str = 'lmstudio',
    ):
        """Return the LangGraph ReAct agent, creating it on the first call.

        Lazy initialization avoids connecting to the LLM at import time — the
        agent is only created when actually needed (N31 orchestrator, tests).

        provider controls which backend to use:
        - 'lmstudio': local LM Studio server at base_url (default, no API key needed)
        - 'openai': OpenAI API; set model_name to 'gpt-4o-mini' or similar

        Args:
            provider: 'lmstudio' or 'openai'.
            model_name: Model identifier for the ChatOpenAI client.
            base_url: Base URL for LM Studio (ignored when provider='openai').
            api_key: API key; use 'lmstudio' for local server.

        Returns:
            LangGraph CompiledGraph — invoke with {"messages": [("user", query)]}.
        """
        global _pace_react_agent
        if _pace_react_agent is not None:
            return _pace_react_agent

        if provider == 'lmstudio':
            llm = ChatOpenAI(
                model=model_name,
                base_url=base_url,
                api_key=api_key,
                temperature=0,
            )
        else:
            llm = ChatOpenAI(model=model_name, temperature=0)

        _pace_react_agent = create_react_agent(
            model=llm,
            tools=PACE_TOOLS,
            prompt=_PACE_SYSTEM_PROMPT,
        )
        return _pace_react_agent

else:
    # Stubs when LangGraph is not installed — core inference still works
    PACE_TOOLS = []

    def get_pace_react_agent(**kwargs):
        raise ImportError(
            "LangGraph / LangChain not installed. "
            "Install with: pip install langgraph langchain-openai"
        )
