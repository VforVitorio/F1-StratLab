"""An omitted per-run provider must leave the process configuration untouched."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_ROOT = ROOT / "src" / "telemetry"
TIRE_ROUTING_CONFIG = ROOT / "data" / "models" / "tire_degradation" / "routing_config.json"


def _load_simulator_or_skip(monkeypatch):
    if not TIRE_ROUTING_CONFIG.is_file():
        pytest.skip("the backend imports model routing config from the HF dataset")
    monkeypatch.syspath_prepend(str(TELEMETRY_ROOT))
    return importlib.import_module("backend.services.simulation.simulator")


@pytest.mark.parametrize(("override", "expected"), [(None, "openai"), ("lmstudio", "lmstudio")])
def test_debug_agent_provider_is_inherited_unless_explicitly_overridden(
    monkeypatch, capsys, override, expected
):
    from scripts import debug_agent

    monkeypatch.setenv("F1_LLM_PROVIDER", "openai")
    argv = [
        "debug_agent.py",
        "--agent",
        "pace",
        "--gp",
        "Lusail",
        "--driver",
        "NOR",
        "--team",
        "McLaren",
        "--featured",
        "data/.debug-agent-provider-test-missing.parquet",
    ]
    if override is not None:
        argv.extend(["--provider", override])
    monkeypatch.setattr(sys, "argv", argv)
    observed: list[str | None] = []
    monkeypatch.setitem(
        debug_agent._RUNNERS,
        "pace",
        lambda _state, _laps, _args: observed.append(os.environ.get("F1_LLM_PROVIDER")),
    )

    debug_agent.main()
    capsys.readouterr()

    assert observed == [expected]


def test_sim_config_leaves_provider_unset_by_default(monkeypatch):
    simulator = _load_simulator_or_skip(monkeypatch)
    config = simulator.SimConfig(year=2025, gp="Lusail", driver="NOR", team="McLaren")

    assert config.provider is None


def test_simulate_generator_preserves_environment_provider_when_omitted(monkeypatch):
    simulator = _load_simulator_or_skip(monkeypatch)
    config = simulator.SimConfig(year=2025, gp="Lusail", driver="NOR", team="McLaren", no_llm=True)

    class StopBeforeDataLoad(Exception):
        pass

    def stop_before_data_load(_year):
        raise StopBeforeDataLoad

    monkeypatch.setenv("F1_LLM_PROVIDER", "openai")
    monkeypatch.setattr(simulator, "_load_laps_df", stop_before_data_load)

    with pytest.raises(StopBeforeDataLoad):
        next(simulator.simulate_race(config))

    assert os.environ["F1_LLM_PROVIDER"] == "openai"
