"""
Agent import + contract smoke tests.

These tests verify that:
  1. Every src/agents/ module is importable
  2. The public entry-point functions exist with the expected signature
  3. Per-agent request schemas in strategy.py are correctly structured

No LLM calls are made — model loading is NOT triggered (lazy imports / singleton).
Run with:
    pytest tests/test_agents.py -v
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Import checks — verify module-level imports don't blow up
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_path", [
    "src.agents.pace_agent",
    "src.agents.tire_agent",
    "src.agents.race_situation_agent",
    "src.agents.pit_strategy_agent",
    "src.agents.radio_agent",
    "src.agents.rag_agent",
    "src.agents.strategy_orchestrator",
])
def test_agent_module_importable(module_path):
    """Each agent module must import without errors."""
    mod = importlib.import_module(module_path)
    assert mod is not None


# ---------------------------------------------------------------------------
# Entry-point function existence
# ---------------------------------------------------------------------------

def test_pace_agent_entry_points():
    from src.agents.pace_agent import run_pace_agent_from_state
    assert callable(run_pace_agent_from_state)


def test_tire_agent_entry_points():
    from src.agents.tire_agent import run_tire_agent_from_state
    assert callable(run_tire_agent_from_state)


def test_situation_agent_entry_points():
    from src.agents.race_situation_agent import run_race_situation_agent_from_state
    assert callable(run_race_situation_agent_from_state)


def test_pit_agent_entry_points():
    from src.agents.pit_strategy_agent import run_pit_strategy_agent_from_state
    assert callable(run_pit_strategy_agent_from_state)


def test_radio_agent_entry_points():
    from src.agents.radio_agent import run_radio_agent_from_state
    assert callable(run_radio_agent_from_state)


def test_rag_agent_entry_points():
    from src.agents.rag_agent import run_rag_agent
    assert callable(run_rag_agent)


def test_orchestrator_entry_points():
    from src.agents.strategy_orchestrator import run_strategy_orchestrator_from_state, RaceState
    assert callable(run_strategy_orchestrator_from_state)
    assert RaceState is not None


# ---------------------------------------------------------------------------
# Output dataclass fields
# ---------------------------------------------------------------------------

def test_pace_output_fields():
    from src.agents.pace_agent import PaceOutput
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PaceOutput)}
    assert {"lap_time_pred", "ci_p10", "ci_p90", "delta_vs_median", "reasoning"} <= fields


def test_tire_output_fields():
    from src.agents.tire_agent import TireOutput
    import dataclasses
    fields = {f.name for f in dataclasses.fields(TireOutput)}
    assert {"laps_to_cliff_p10", "laps_to_cliff_p50", "laps_to_cliff_p90", "warning_level"} <= fields


def test_race_situation_output_fields():
    from src.agents.race_situation_agent import RaceSituationOutput
    import dataclasses
    fields = {f.name for f in dataclasses.fields(RaceSituationOutput)}
    assert {"overtake_prob", "sc_prob_3lap", "threat_level"} <= fields


def test_pit_output_fields():
    from src.agents.pit_strategy_agent import PitStrategyOutput
    import dataclasses
    fields = {f.name for f in dataclasses.fields(PitStrategyOutput)}
    assert {"stop_duration_p05", "stop_duration_p50", "stop_duration_p95", "undercut_prob"} <= fields


def test_strategy_recommendation_fields():
    from src.agents.strategy_orchestrator import StrategyRecommendation
    # StrategyRecommendation is a Pydantic BaseModel, not a dataclass
    fields = set(StrategyRecommendation.model_fields.keys())
    assert {"action", "confidence", "reasoning", "scenario_scores"} <= fields


# ---------------------------------------------------------------------------
# Strategy endpoint Pydantic schemas
# ---------------------------------------------------------------------------

def test_strategy_schemas_importable():
    """Per-agent request models must exist in strategy.py (no StrategyRequest)."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    from backend.api.v1.endpoints.strategy import (
        PaceRequest, TireRequest, SituationRequest, PitRequest, RadioRequest,
        RagRequest, RecommendRequest, StrategyResponse,
    )
    # StrategyRequest must no longer exist
    import backend.api.v1.endpoints.strategy as strategy_module
    assert not hasattr(strategy_module, "StrategyRequest"), \
        "StrategyRequest was not removed — split into per-agent schemas"


def test_pace_request_schema():
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    from backend.api.v1.endpoints.strategy import PaceRequest
    req = PaceRequest(lap_state={"driver": {}, "session_meta": {}})
    assert req.lap_state == {"driver": {}, "session_meta": {}}


def test_radio_request_defaults():
    """RadioRequest must default radio_msgs and rcm_events to empty lists."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    from backend.api.v1.endpoints.strategy import RadioRequest
    req = RadioRequest(lap_state={})
    assert req.radio_msgs == []
    assert req.rcm_events == []


def test_tire_request_defaults():
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    from backend.api.v1.endpoints.strategy import TireRequest
    req = TireRequest(lap_state={})
    assert req.gp_name == ""
    assert req.year == 2025


# ---------------------------------------------------------------------------
# Voice config constants
# ---------------------------------------------------------------------------

def test_voice_config_nemotron():
    """voice_config.py must expose Nemotron + Qwen3-TTS constants."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    from backend.core.voice_config import (
        NEMOTRON_MODEL, NEMOTRON_DEVICE, NEMOTRON_CHUNK_MS,
        QWEN3_TTS_MODEL, QWEN3_SAMPLE_RATE,
    )
    assert "nemotron" in NEMOTRON_MODEL.lower()
    assert "qwen" in QWEN3_TTS_MODEL.lower()
    assert QWEN3_SAMPLE_RATE == 24000


def test_voice_config_no_whisper():
    """Old Whisper/EdgeTTS constants must be gone."""
    import sys
    sys.path.insert(0, str(ROOT / "src" / "telemetry"))
    import backend.core.voice_config as vc
    assert not hasattr(vc, "WHISPER_MODEL"), "WHISPER_MODEL still present"
    assert not hasattr(vc, "TTS_ENGINE"), "TTS_ENGINE still present"
    assert not hasattr(vc, "TTS_VOICE"), "TTS_VOICE still present"
