"""Pit Strategy Agent — src/agents/pit_strategy_agent.py

Extracted from N28_pit_strategy_agent.ipynb. Wraps N15 (physical pit stop duration
P05/P50/P95) and N16 (undercut success probability) in a LangGraph ReAct agent
that recommends when to pit, what compound to fit, and whether to undercut.

Public API
----------
run_pit_strategy_agent(lap_state)                     → PitStrategyOutput  (FastF1 session)
run_pit_strategy_agent_from_state(lap_state, laps_df) → PitStrategyOutput  (RSM adapter)

Module-level singletons
-----------------------
CFG            — PitAgentCFG: N15 HistGBT×3, N16 LightGBM+calibrator, lookups
TIRE_COMPOUNDS — compound allocation from data/tire_compounds_by_race.json
LAPS / SESSION_META — globals set by entry points before tool invocation
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

# ── Repo root ─────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parent
while not (_REPO_ROOT / '.git').exists():
    _REPO_ROOT = _REPO_ROOT.parent

_MODELS    = _REPO_ROOT / 'data' / 'models'
_PROCESSED = _REPO_ROOT / 'data' / 'processed'
_AGENTS    = _REPO_ROOT / 'data' / 'models' / 'agents'

# ── Compound allocation (SOFT/MEDIUM/HARD → Cx per GP/year) ───────────────────
_compounds_path = _REPO_ROOT / 'data' / 'tire_compounds_by_race.json'
TIRE_COMPOUNDS: dict = (
    json.loads(_compounds_path.read_text(encoding='utf-8'))
    if _compounds_path.exists() else {}
)

# FastF1 team name variants → N15 training names
_TEAM_ALIASES: dict[str, str] = {'Racing Bulls': 'RB'}

# Fallback color→compound_id when TIRE_COMPOUNDS has no entry for the circuit/year
_COMPOUND_FALLBACK: dict[str, int] = {'HARD': 1, 'MEDIUM': 3, 'SOFT': 5}

# Pirelli average stint capacities — Heilmeier et al. (2020, SAE 2020-01-1413)
_STINT_CAPACITY_LAPS: dict[str, int] = {'SOFT': 18, 'MEDIUM': 30, 'HARD': 38}

CLIFF_IMMINENT_LAPS = 3    # laps_to_cliff_p10 below this → PIT_NOW
CLIFF_SOON_LAPS     = 10   # laps_to_cliff_p10 below this → prefer harder compound


# ─────────────────────────────────────────────────────────────────────────────
# PitAgentCFG
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PitAgentCFG:
    """Runtime configuration for the Pit Strategy Agent.

    Loads three N15 quantile regressors (physical stop P05/P50/P95), the N16
    undercut LightGBM + Platt calibrator, and both JSON configs. All loaded with
    joblib — required on Windows paths with non-ASCII characters.

    circuit_traversal maps GP event name → pit lane traversal time (s). Subtracting
    it from total pit time yields physical_stop_est, the N15 target variable.

    team_encoder is a sklearn LabelEncoder reconstructed from the class list in
    model_config.json — no separate .pkl needed.

    team_year_median_fallback (2.8 s): per-team×year medians were not exported from
    N15. This constant is the centre of the [2.0, 4.5 s] training range; the feature
    ranks low in permutation importance so the approximation is adequate.

    circuit_undercut_rate and team_x_undercut_rate are pre-aggregated at startup
    from undercut_clean.parquet so tool calls are stateless.

    Attributes:
        model_name: LM Studio model identifier for the ReAct agent LLM.
        team_year_median_fallback: Global fallback for team_year_median feature (s).
    """

    model_name: str = 'local-model'
    team_year_median_fallback: float = 2.8

    def __post_init__(self):
        self.export_dir = _AGENTS
        self.export_dir.mkdir(parents=True, exist_ok=True)

        _pit = _MODELS / 'pit_prediction'

        # N15: physical stop duration models
        self.pit_p05_model = joblib.load(_pit / 'hist_pit_p05_v1.pkl')
        self.pit_p50_model = joblib.load(_pit / 'hist_pit_p50_v1.pkl')
        self.pit_p95_model = joblib.load(_pit / 'hist_pit_p95_v1.pkl')

        with open(_pit / 'model_config.json') as f:
            pit_cfg = json.load(f)

        self.pit_features: list[str]   = pit_cfg['features']
        self.circuit_traversal: dict   = pit_cfg['circuit_traversal_lookup']

        # Reconstruct LabelEncoder from saved class list
        le = LabelEncoder()
        le.classes_ = np.array(pit_cfg['label_encoder_classes']['team'])
        self.team_encoder: LabelEncoder = le

        # N16: undercut classifier + calibrator
        self.undercut_model      = joblib.load(_pit / 'lgbm_undercut_v1.pkl')
        self.undercut_calibrator = joblib.load(_pit / 'calibrator_undercut_v1.pkl')

        with open(_pit / 'model_config_undercut_v1.json') as f:
            uc_cfg = json.load(f)

        self.undercut_features: list[str] = uc_cfg['features']
        self.undercut_threshold: float    = uc_cfg['best_threshold']
        self.dry_compounds: list[str]     = uc_cfg['dry_compounds']

        # Pre-aggregate circuit and team undercut rates from N16 training parquet
        _uc = pd.read_parquet(_PROCESSED / 'undercut_labeled' / 'undercut_clean.parquet')
        self.circuit_undercut_rate: dict = (
            _uc.groupby('GP_Name')['undercut_success'].mean().to_dict()
        )
        self.team_x_undercut_rate: dict = (
            _uc.groupby('Team_X')['undercut_success'].mean().to_dict()
        )


# ── Module-level singletons ───────────────────────────────────────────────────
CFG = PitAgentCFG()

# ── Globals set by entry points before tool invocation ────────────────────────
LAPS:         pd.DataFrame = pd.DataFrame()
SESSION_META: dict         = {}


# ─────────────────────────────────────────────────────────────────────────────
# PitStrategyOutput
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PitStrategyOutput:
    """Structured output of the Pit Strategy Agent for one driver at one lap.

    Attributes:
        action: Strategy recommendation — PIT_NOW, STAY_OUT, UNDERCUT, OVERCUT,
            or REACTIVE_SC (box under an active/imminent Safety Car).
        recommended_lap: Lap on which the stop is recommended. None when STAY_OUT.
        compound_recommendation: SOFT, MEDIUM, or HARD for the next stint.
        stop_duration_p05: 5th-percentile physical stop time (s) from N15.
        stop_duration_p50: Median physical stop time (s). Used for timing decisions.
        stop_duration_p95: 95th-percentile physical stop time (s). Pessimistic bound.
        undercut_prob: Calibrated N16 P(undercut success). None when no dry rival
            is within 5 positions or conditions are wet.
        undercut_target: Driver abbreviation of the undercut target. None when
            undercut_prob is None.
        sc_reactive: True when recommendation was triggered by SC probability from
            N27, not by tyre degradation or position logic alone.
        reasoning: LLM synthesis explaining the recommendation.
    """

    action: str
    recommended_lap: int | None
    compound_recommendation: str
    stop_duration_p05: float
    stop_duration_p50: float
    stop_duration_p95: float
    undercut_prob: float | None
    undercut_target: str | None
    sc_reactive: bool
    reasoning: str


# ─────────────────────────────────────────────────────────────────────────────
# Encoding helpers
# ─────────────────────────────────────────────────────────────────────────────

def _compound_to_id(compound: str, gp_name: str, year: int) -> int:
    """Convert SOFT/MEDIUM/HARD to Pirelli compound number (C1–C5/C6).

    Uses the nested TIRE_COMPOUNDS structure {year_str: {gp_name: {compound: Cx}}}.
    The Cx string (e.g. 'C3') is stripped to its integer (3). Falls back to
    _COMPOUND_FALLBACK when the circuit/year is not in the map.
    """
    cx_str = TIRE_COMPOUNDS.get(str(year), {}).get(gp_name, {}).get(compound.upper(), '')
    if cx_str and cx_str.startswith('C') and cx_str[1:].isdigit():
        return int(cx_str[1:])
    return _COMPOUND_FALLBACK.get(compound.upper(), 3)


def _encode_team(team_raw: str) -> int:
    """Encode team name to integer using the N15 LabelEncoder in CFG.

    Applies _TEAM_ALIASES before encoding so FastF1 2025 variants resolve to
    training-time names. Unknown teams encode to 0 to avoid inference crashes.
    """
    team_str = _TEAM_ALIASES.get(team_raw, team_raw)
    try:
        return int(CFG.team_encoder.transform([team_str])[0])
    except ValueError:
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Lap data helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_lap_row(driver: str, lap_number: int) -> pd.Series | None:
    """Return the single LAPS row for driver at lap_number, or None if missing."""
    rows = LAPS[(LAPS['Driver'] == driver) & (LAPS['LapNumber'] == lap_number)]
    return rows.iloc[0] if not rows.empty else None


def _get_position_map(lap_number: int) -> dict[str, float]:
    """Return {driver: position} for all drivers at lap_number with valid position."""
    lap_data = LAPS[LAPS['LapNumber'] == lap_number][['Driver', 'Position']].dropna()
    return dict(zip(lap_data['Driver'], lap_data['Position']))


def _compounds_are_dry(comp_x: str, comp_y: str) -> bool:
    """Return True only if both compounds are in CFG.dry_compounds."""
    return comp_x in CFG.dry_compounds and comp_y in CFG.dry_compounds


# ─────────────────────────────────────────────────────────────────────────────
# Feature builders
# ─────────────────────────────────────────────────────────────────────────────

def build_pit_duration_features(
    driver: str,
    lap_number: int,
    compound: str,
    compound_change: bool,
    under_sc: bool,
) -> pd.DataFrame:
    """Build the 9-feature input row for the N15 quantile regressors.

    Assembles features from LAPS, SESSION_META, and CFG lookups.
    team_year_median uses CFG.team_year_median_fallback (2.8 s) because
    per-team×year medians were not exported from N15.
    tight_pit_box is hardcoded False — near-zero permutation importance in N15.

    Args:
        driver: FastF1 driver abbreviation.
        lap_number: Lap on which the stop would occur.
        compound: Compound being fitted ('SOFT', 'MEDIUM', 'HARD').
        compound_change: True if switching compound vs current.
        under_sc: True if Safety Car is active during the stop.

    Returns:
        Single-row DataFrame with 9 columns in CFG.pit_features order.

    Raises:
        ValueError: When no lap row exists for the driver at lap_number.
    """
    row = _get_lap_row(driver, lap_number)
    if row is None:
        raise ValueError(f'No lap data for {driver} at lap {lap_number}')

    gp_name  = SESSION_META.get('gp_name', '')
    year     = SESSION_META.get('year', 2025)
    team_raw = SESSION_META.get('team_lookup', {}).get(driver, 'Unknown')

    feat = {
        'team':             _encode_team(team_raw),
        'year':             year,
        'tyre_life_in':     int(row.get('TyreLife', 1)),
        'lap_number':       lap_number,
        'compound_id':      _compound_to_id(compound, gp_name, year),
        'compound_change':  int(compound_change),
        'under_sc':         int(under_sc),
        'tight_pit_box':    0,
        'team_year_median': CFG.team_year_median_fallback,
    }
    return pd.DataFrame([feat])[CFG.pit_features]


def build_undercut_features(
    driver_x: str,
    driver_y: str,
    lap_number: int,
) -> pd.DataFrame | None:
    """Build the 13-feature input row for the N16 undercut classifier.

    Returns None if either driver has no lap row at lap_number or if either
    compound is not dry (wet/intermediate conditions are out of N16's scope).

    pit_delta_X estimates total stop cost as circuit_traversal + 4.5 s
    (conservative physical stop median), representing inlap + outlap minus
    two representative race laps.

    Args:
        driver_x: FastF1 abbreviation of the driver considering pitting first.
        driver_y: FastF1 abbreviation of the rival to undercut.
        lap_number: Current lap number.

    Returns:
        Single-row DataFrame with 13 columns in CFG.undercut_features order,
        or None when preconditions are not met.
    """
    x_row = _get_lap_row(driver_x, lap_number)
    y_row = _get_lap_row(driver_y, lap_number)
    if x_row is None or y_row is None:
        return None

    comp_x = str(x_row.get('Compound', 'MEDIUM')).upper()
    comp_y = str(y_row.get('Compound', 'MEDIUM')).upper()
    if not _compounds_are_dry(comp_x, comp_y):
        return None

    gp_name    = SESSION_META.get('gp_name', '')
    year       = SESSION_META.get('year', 2025)
    total_laps = SESSION_META.get('total_laps', 57)
    team_x_raw = SESSION_META.get('team_lookup', {}).get(driver_x, 'Unknown')
    team_x     = _TEAM_ALIASES.get(team_x_raw, team_x_raw)

    comp_x_id = _compound_to_id(comp_x, gp_name, year)
    comp_y_id = _compound_to_id(comp_y, gp_name, year)

    feat = {
        'pos_gap':               float(y_row.get('Position', 9)) - float(x_row.get('Position', 10)),
        'Lap_gap':               lap_number,
        'tyre_life_diff':        float(x_row.get('TyreLife', 10)) - float(y_row.get('TyreLife', 10)),
        'TyreLife_X':            float(x_row.get('TyreLife', 10)),
        'TyreLife_Y':            float(y_row.get('TyreLife', 10)),
        'compound_x_id':         comp_x_id,
        'compound_y_id':         comp_y_id,
        'compound_delta':        comp_x_id - comp_y_id,
        'pit_delta_X':           CFG.circuit_traversal.get(gp_name, 20.0) + 4.5,
        'lap_race_pct':          lap_number / total_laps,
        'pos_X_before':          float(x_row.get('Position', 10)),
        'circuit_undercut_rate': CFG.circuit_undercut_rate.get(gp_name, 0.38),
        'team_x_undercut_rate':  CFG.team_x_undercut_rate.get(team_x, 0.38),
    }
    return pd.DataFrame([feat])[CFG.undercut_features]


def get_undercut_candidates(
    driver: str,
    lap_number: int,
    max_pos_gap: int = 5,
) -> list[str]:
    """Return drivers strictly ahead of driver within max_pos_gap positions.

    Result is sorted ascending by position so the immediate car ahead is first —
    the most likely undercut target. Uses _get_position_map for the current lap.
    """
    pos_map = _get_position_map(lap_number)
    my_pos  = pos_map.get(driver)
    if my_pos is None:
        return []
    candidates = [
        d for d, p in pos_map.items()
        if d != driver and (my_pos - max_pos_gap) <= p < my_pos
    ]
    return sorted(candidates, key=lambda d: pos_map[d])


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph tools
# ─────────────────────────────────────────────────────────────────────────────

try:
    from langchain_core.tools import tool as lc_tool
    from langchain_core.messages import HumanMessage
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


if _LANGGRAPH_AVAILABLE:

    @lc_tool
    def predict_pit_duration_tool(
        driver: str,
        lap_number: int,
        compound: str,
        compound_change: bool,
        under_sc: bool,
    ) -> str:
        """Predict physical pit stop duration (P05/P50/P95) and total pit lane time.

        Builds the 9 N15 features, runs the three HistGBT quantile regressors,
        adds circuit traversal time from CFG.

        Args:
            driver: FastF1 driver abbreviation (e.g. 'NOR').
            lap_number: Lap on which the stop would occur.
            compound: Compound being fitted ('SOFT', 'MEDIUM', 'HARD').
            compound_change: True if switching from current compound.
            under_sc: True if Safety Car is active during the stop.

        Returns:
            "physical_stop: P05={p05:.2f}s | P50={p50:.2f}s | P95={p95:.2f}s | total_pit_P50={total:.2f}s (traversal={traversal:.2f}s)"
        """
        feat_df = build_pit_duration_features(driver, lap_number, compound, compound_change, under_sc)

        p05 = float(CFG.pit_p05_model.predict(feat_df)[0])
        p50 = float(CFG.pit_p50_model.predict(feat_df)[0])
        p95 = float(CFG.pit_p95_model.predict(feat_df)[0])

        gp_name   = SESSION_META.get('gp_name', '')
        traversal = CFG.circuit_traversal.get(gp_name, 20.0)

        return (
            f'physical_stop: P05={p05:.2f}s | P50={p50:.2f}s | P95={p95:.2f}s | '
            f'total_pit_P50={p50 + traversal:.2f}s (traversal={traversal:.2f}s)'
        )

    @lc_tool
    def score_undercut_tool(driver_x: str, driver_y: str, lap_number: int) -> str:
        """Score the probability that driver_x successfully undercuts driver_y.

        Builds the 13 N16 features and applies LightGBM + Platt calibration.
        Returns early when conditions fall outside N16's training scope.

        Args:
            driver_x: FastF1 abbreviation of the driver considering pitting first.
            driver_y: FastF1 abbreviation of the rival to undercut.
            lap_number: Current lap number.

        Returns:
            "P(undercut_success)={prob:.3f} | threshold={threshold} | pos_gap={gap:.0f} | tyre_life_diff={diff:+.0f} laps | verdict={YES/NO}"
        """
        feat_df = build_undercut_features(driver_x, driver_y, lap_number)
        if feat_df is None:
            return (
                f'Undercut scoring N/A — wet compound or missing lap data '
                f'for {driver_x}/{driver_y} at lap {lap_number}'
            )

        raw_proba   = CFG.undercut_model.predict_proba(feat_df)[:, 1]
        calib_proba = CFG.undercut_calibrator.predict_proba(raw_proba.reshape(-1, 1))[:, 1][0]

        verdict   = 'YES' if calib_proba >= CFG.undercut_threshold else 'NO'
        pos_gap   = feat_df['pos_gap'].iloc[0]
        tyre_diff = feat_df['tyre_life_diff'].iloc[0]

        return (
            f'P(undercut_success)={calib_proba:.3f} | threshold={CFG.undercut_threshold} | '
            f'pos_gap={pos_gap:.0f} | tyre_life_diff={tyre_diff:+.0f} laps | verdict={verdict}'
        )

    @lc_tool
    def recommend_compound_tool(
        driver: str,
        lap_number: int,
        current_compound: str,
        laps_to_cliff: float | None = None,
    ) -> str:
        """Recommend the optimal next compound using N26 cliff signal or Pirelli stint windows.

        Priority 1 — laps_to_cliff from N26 TireOutput: drives compound choice
        directly when available. Priority 2 — Pirelli average stint capacities
        (SOFT ~18 laps, MEDIUM ~30 laps, HARD ~38 laps) as fallback.
        FIA mandatory two-compound rule is always applied.

        Args:
            driver: FastF1 driver abbreviation.
            lap_number: Current lap number.
            current_compound: Compound currently fitted.
            laps_to_cliff: P10 laps-to-cliff from N26 TireOutput (optional).

        Returns:
            "Recommended: {compound} | {strategy} | {urgency} | laps_remaining={n} | current={current} | source={source}"
        """
        total_laps       = SESSION_META.get('total_laps', 57)
        laps_remaining   = total_laps - lap_number
        current_compound = current_compound.upper()

        must_differ = current_compound in CFG.dry_compounds
        valid       = [c for c in CFG.dry_compounds if c != current_compound] if must_differ else list(CFG.dry_compounds)
        candidates  = sorted(valid, key=lambda c: _STINT_CAPACITY_LAPS[c])

        if laps_to_cliff is not None:
            source  = 'N26_laps_to_cliff'
            urgency = (
                'CLIFF_IMMINENT' if laps_to_cliff <= CLIFF_IMMINENT_LAPS
                else 'CLIFF_SOON' if laps_to_cliff <= CLIFF_SOON_LAPS
                else 'PLANNED'
            )
        else:
            source  = 'Pirelli_stint_windows'
            urgency = 'PLANNED'

        recommendation = next(
            (c for c in candidates if _STINT_CAPACITY_LAPS[c] >= laps_remaining),
            candidates[-1],
        )

        one_stop_viable = _STINT_CAPACITY_LAPS.get(recommendation, 30) >= laps_remaining
        strategy        = '1-stop viable' if one_stop_viable else '2-stop likely'
        cliff_str       = f' | laps_to_cliff={laps_to_cliff:.1f}' if laps_to_cliff is not None else ''

        return (
            f'Recommended: {recommendation} | {strategy} | {urgency} | '
            f'laps_remaining={laps_remaining} | current={current_compound} | '
            f'source={source}{cliff_str}'
        )

    _PIT_STRATEGY_SYSTEM_PROMPT = """You are the Pit Strategy Agent for an F1 race.
Your job is to decide whether a driver should pit now, and if so, what compound to fit.

You have three tools:
- predict_pit_duration_tool: estimates physical stop duration (P05/P50/P95) and total pit lane time.
- score_undercut_tool: scores the probability that pitting before a specific rival earns track position.
- recommend_compound_tool: recommends the optimal next compound based on remaining laps and FIA rules.

Decision rules:
1. Always call predict_pit_duration_tool first to know the stop cost.
2. Call score_undercut_tool for each rival within 5 positions ahead.
3. Call recommend_compound_tool to determine the optimal compound.
4. If P(undercut_success) >= 0.522 for any rival → recommend UNDERCUT.
5. If sc_prob context is provided and >= 0.30 → recommend REACTIVE_SC pit.
6. If tyre_cliff context is provided and laps_to_cliff <= 3 → recommend PIT_NOW.
7. Otherwise → STAY_OUT unless a clear strategic window exists.

Always end your response with a structured summary:
ACTION: <PIT_NOW|STAY_OUT|UNDERCUT|OVERCUT|REACTIVE_SC>
COMPOUND: <SOFT|MEDIUM|HARD>
REASONING: <one sentence>
"""

    PIT_TOOLS = [predict_pit_duration_tool, score_undercut_tool, recommend_compound_tool]

    _pit_strategy_react_agent = None

    def get_pit_strategy_react_agent(
        provider: str = 'lmstudio',
        model_name: str = 'local-model',
        base_url: str = 'http://localhost:1234/v1',
        api_key: str = 'lm-studio',
    ):
        """Return the LangGraph ReAct agent, creating it on the first call (lazy singleton).

        parallel_tool_calls is disabled via model_kwargs to avoid a Jinja NullValue
        rendering error in LM Studio when the agent sends tool results back.
        disable_streaming avoids partial-chunk issues with local models.

        Args:
            provider: 'lmstudio' or 'openai'.
            model_name: Model identifier for ChatOpenAI.
            base_url: Base URL for LM Studio (ignored when provider='openai').
            api_key: API key; 'lm-studio' for local server.

        Returns:
            LangGraph CompiledGraph.
        """
        global _pit_strategy_react_agent
        if _pit_strategy_react_agent is not None:
            return _pit_strategy_react_agent

        if provider == 'lmstudio':
            llm = ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model=model_name,
                temperature=0,
                model_kwargs={'parallel_tool_calls': False},
                disable_streaming=True,
            )
        else:
            llm = ChatOpenAI(model=model_name, temperature=0)

        _pit_strategy_react_agent = create_react_agent(
            llm, PIT_TOOLS, prompt=_PIT_STRATEGY_SYSTEM_PROMPT
        )
        return _pit_strategy_react_agent

else:
    PIT_TOOLS = []

    def get_pit_strategy_react_agent(**kwargs):
        raise ImportError('LangGraph / LangChain not installed.')


# ─────────────────────────────────────────────────────────────────────────────
# Parse helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_tool_outputs(messages: list) -> dict:
    """Extract numeric values from tool call results in the agent message history.

    Scans ToolMessage content for structured strings from each tool. Values
    default to None when the corresponding tool was not called.

    Returns:
        Dict with: stop_duration_p05/p50/p95, undercut_prob, undercut_target,
        compound_recommendation. Missing keys default to None.
    """
    result = {
        'stop_duration_p05':       None,
        'stop_duration_p50':       None,
        'stop_duration_p95':       None,
        'undercut_prob':           None,
        'undercut_target':         None,
        'compound_recommendation': None,
    }
    for msg in messages:
        content = getattr(msg, 'content', '')
        if not isinstance(content, str):
            continue
        m = re.search(r'P05=(\d+(?:\.\d+)?)s.*?P50=(\d+(?:\.\d+)?)s.*?P95=(\d+(?:\.\d+)?)s', content)
        if m:
            result['stop_duration_p05'] = float(m.group(1))
            result['stop_duration_p50'] = float(m.group(2))
            result['stop_duration_p95'] = float(m.group(3))
        m = re.search(r'P\(undercut_success\)=(\d+(?:\.\d+)?)', content)
        if m and result['undercut_prob'] is None:
            result['undercut_prob'] = float(m.group(1))
        m = re.search(r'Recommended:\s*(SOFT|MEDIUM|HARD)', content)
        if m:
            result['compound_recommendation'] = m.group(1)
    return result


def _parse_agent_summary(final_content: str) -> tuple[str, str, str]:
    """Extract ACTION, COMPOUND, and REASONING from the agent's structured summary.

    Falls back to ('STAY_OUT', 'MEDIUM', first 200 chars) when the structured
    block is absent — prevents crashes when the LLM deviates from format.
    """
    action   = re.search(r'ACTION:\s*(PIT_NOW|STAY_OUT|UNDERCUT|OVERCUT|REACTIVE_SC)', final_content)
    compound = re.search(r'COMPOUND:\s*(SOFT|MEDIUM|HARD)', final_content)
    reason   = re.search(r'REASONING:\s*(.+)', final_content)
    return (
        action.group(1)          if action   else 'STAY_OUT',
        compound.group(1)        if compound else 'MEDIUM',
        reason.group(1).strip()  if reason   else final_content[:200],
    )


def _build_pit_prompt(
    driver: str, lap_number: int, tyre_life: int, compound: str,
    team: str, position: int, rival_str: str,
    sc_prob: float, laps_to_cliff_p10: float,
) -> str:
    """Build the natural-language prompt for the Pit Strategy ReAct agent."""
    return (
        f'Driver {driver} | Lap {lap_number} | P{position} | '
        f'Tyre: {compound} (life {tyre_life} laps)\n'
        f'Rival ahead: {rival_str}\n'
        f'SC probability (next 3 laps): {sc_prob:.2f}\n'
        f'Laps to tyre cliff P10: {laps_to_cliff_p10:.1f}\n\n'
        f'Team: {team}\n\n'
        'Analyse the pit stop window. Call predict_pit_duration_tool, '
        'score_undercut_tool, and recommend_compound_tool. '
        'Then give a final recommendation.'
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry points
# ─────────────────────────────────────────────────────────────────────────────

def run_pit_strategy_agent(lap_state: dict) -> PitStrategyOutput:
    """Run the Pit Strategy Agent for a driver at a given lap.

    Sets LAPS and SESSION_META from the FastF1 session in lap_state, invokes
    the ReAct agent, and parses the response into a PitStrategyOutput.

    Args:
        lap_state: Dict with keys:
            session     — Loaded FastF1 Session.
            driver      — FastF1 driver abbreviation (e.g. 'NOR').
            lap_number  — Current lap number.
            compound    — Compound currently fitted (default 'MEDIUM').
            rival       — Abbreviation of the nearest rival ahead (optional).
            sc_prob     — SC probability from N27 (float, default 0.0).
            laps_to_cliff — P10 laps-to-cliff from N26 (float, optional).

    Returns:
        PitStrategyOutput with action, compound, stop durations, undercut signal.
    """
    global LAPS, SESSION_META

    session    = lap_state['session']
    driver     = lap_state['driver']
    lap_number = lap_state['lap_number']
    compound   = lap_state.get('compound', 'MEDIUM')
    rival      = lap_state.get('rival')
    sc_prob    = lap_state.get('sc_prob', 0.0)
    laps_cliff = lap_state.get('laps_to_cliff')

    laps                = session.laps.pick_accurate().copy()
    laps['LapNumber']   = laps['LapNumber'].astype(int)
    LAPS                = laps

    team_lookup = (
        laps[['Driver', 'Team']].drop_duplicates()
            .set_index('Driver')['Team'].to_dict()
    )
    SESSION_META = {
        'gp_name':    session.event['EventName'],
        'year':       session.event['EventDate'].year,
        'total_laps': int(laps['LapNumber'].max()),
        'team_lookup': team_lookup,
    }

    return _run_pit_strategy_core(driver, lap_number, compound, rival, sc_prob, laps_cliff)


def run_pit_strategy_agent_from_state(
    lap_state: dict,
    laps_df: pd.DataFrame,
) -> PitStrategyOutput:
    """RSM adapter: run the Pit Strategy Agent from a RaceStateManager lap_state.

    Sets LAPS and SESSION_META from laps_df and lap_state without requiring a
    FastF1 session object. The rival ahead is derived from lap_state['rivals']
    by finding the car with position = driver_position - 1.

    team_lookup is built from the rivals list (each rival has a 'team' field)
    plus the driver's team from session_meta.

    Args:
        lap_state: Dict from RaceStateManager.get_lap_state(). Keys used:
            lap_number, driver (telemetry), rivals (list), session_meta, weather.
        laps_df: Full race laps DataFrame. LapNumber must be int-castable.
            LapTime as Timedelta (FastF1) or float seconds (LapTime_s) both accepted.

    Returns:
        PitStrategyOutput with all fields populated.
    """
    global LAPS, SESSION_META

    d      = lap_state['driver']
    meta   = lap_state['session_meta']
    rivals = lap_state.get('rivals', [])

    lap_number = lap_state['lap_number']
    driver     = meta['driver']
    gp_name    = meta.get('gp_name', '')
    total_laps = meta.get('total_laps', 60)
    year       = meta.get('year', 2025)
    team       = meta.get('team', 'Unknown')
    compound   = d.get('compound', 'MEDIUM')

    # Derive rival ahead by position
    driver_pos  = d.get('position', 20)
    rival_ahead = next(
        (r['driver'] for r in rivals if r.get('position') == driver_pos - 1),
        None,
    )

    # Build team_lookup from rivals + our driver
    team_lookup = {r['driver']: r.get('team', 'Unknown') for r in rivals}
    team_lookup[driver] = team

    LAPS = laps_df.copy()
    if 'LapNumber' in LAPS.columns:
        LAPS['LapNumber'] = LAPS['LapNumber'].astype(int)

    SESSION_META = {
        'gp_name':    gp_name,
        'year':       year,
        'total_laps': total_laps,
        'team_lookup': team_lookup,
    }

    # Optional context from other agents
    sc_prob    = lap_state.get('sc_prob', 0.0)
    laps_cliff = lap_state.get('laps_to_cliff')

    return _run_pit_strategy_core(driver, lap_number, compound, rival_ahead, sc_prob, laps_cliff)


def _run_pit_strategy_core(
    driver: str,
    lap_number: int,
    compound: str,
    rival: str | None,
    sc_prob: float,
    laps_cliff: float | None,
) -> PitStrategyOutput:
    """Core: LAPS/SESSION_META already set. Build prompt, invoke agent, parse output."""
    candidates = get_undercut_candidates(driver, lap_number)
    rival_str  = rival if rival else (candidates[0] if candidates else 'no rival in range')

    driver_row = _get_lap_row(driver, lap_number)
    tyre_life  = int(driver_row.get('TyreLife', 1)) if driver_row is not None else 1
    position   = int(driver_row.get('Position', 0)) if driver_row is not None else 0
    team       = SESSION_META.get('team_lookup', {}).get(driver, 'Unknown')

    message  = _build_pit_prompt(
        driver=driver, lap_number=lap_number, tyre_life=tyre_life,
        compound=compound, team=team, position=position, rival_str=rival_str,
        sc_prob=sc_prob,
        laps_to_cliff_p10=laps_cliff if laps_cliff is not None else 0.0,
    )

    agent    = get_pit_strategy_react_agent()
    response = agent.invoke({'messages': [HumanMessage(content=message)]})
    messages = response['messages']

    parsed                        = _parse_tool_outputs(messages)
    action, compound_rec, reasoning = _parse_agent_summary(messages[-1].content)

    sc_reactive = (action == 'REACTIVE_SC') or (
        sc_prob >= 0.30 and action in ('PIT_NOW', 'UNDERCUT')
    )

    return PitStrategyOutput(
        action                  = action,
        recommended_lap         = lap_number if action != 'STAY_OUT' else None,
        compound_recommendation = compound_rec or parsed.get('compound_recommendation') or 'MEDIUM',
        stop_duration_p05       = parsed['stop_duration_p05'] or 0.0,
        stop_duration_p50       = parsed['stop_duration_p50'] or 0.0,
        stop_duration_p95       = parsed['stop_duration_p95'] or 0.0,
        undercut_prob           = parsed['undercut_prob'],
        undercut_target         = rival_str if parsed['undercut_prob'] else None,
        sc_reactive             = sc_reactive,
        reasoning               = reasoning,
    )
