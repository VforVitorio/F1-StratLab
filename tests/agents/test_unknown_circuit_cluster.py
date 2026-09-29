"""Unknown circuit names keep the training-time cluster sentinel."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import HAS_TIRE_MODELS

ROOT = Path(__file__).parent.parent.parent


def test_pace_unknown_circuit_does_not_become_a_real_cluster():
    """N06's categorical encoding must preserve -1 for an unresolved circuit."""
    from src.agents.pace_agent import PaceAgent

    agent = object.__new__(PaceAgent)
    agent.compound_id = {"SOFT": 1}
    agent.circuit_cluster = {"Monaco": 2}
    agent.team_id = {"McLaren": 4}

    assert agent._encode_categorical("SOFT", "McLaren", "Unknown GP")[2] == -1


@pytest.mark.data
@pytest.mark.skipif(not HAS_TIRE_MODELS, reason="tire model artefacts absent")
def test_tire_unknown_circuit_preserves_the_explicit_fallback():
    """N26's resolver lets its caller choose the non-trained fallback."""
    from src.agents.tire_agent import TireAgentConfig

    config = object.__new__(TireAgentConfig)
    config.circuit_cluster_map = {"Monaco": 2}

    assert config.cluster_for("Unknown GP", -1) == -1


def test_tire_adapters_pass_the_unknown_sentinel():
    """Both N26 adapters must pass -1 rather than the real cluster 0."""
    source = (ROOT / "src" / "agents" / "tire_agent.py").read_text(encoding="utf-8")

    assert source.count("cluster_for(gp_name, -1)") == 4
