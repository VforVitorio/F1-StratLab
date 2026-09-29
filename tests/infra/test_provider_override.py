"""An omitted per-run provider must leave the process configuration untouched."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_ROOT = ROOT / "src" / "telemetry"


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


def test_simulate_request_leaves_provider_unset_when_omitted(monkeypatch):
    monkeypatch.syspath_prepend(str(TELEMETRY_ROOT))
    request_module = importlib.import_module("backend.api.v1.endpoints.strategy")
    simulator = importlib.import_module("backend.services.simulation.simulator")

    request = request_module.SimulateRequest(year=2025, gp="Lusail", driver="NOR", team="McLaren")
    config = simulator.SimConfig(**request.model_dump())

    assert request.provider is None
    assert config.provider is None

    explicit = request_module.SimulateRequest(
        year=2025, gp="Lusail", driver="NOR", team="McLaren", provider="openai"
    )
    assert simulator.SimConfig(**explicit.model_dump()).provider == "openai"


def test_simulate_generator_preserves_environment_provider_when_omitted(monkeypatch):
    monkeypatch.syspath_prepend(str(TELEMETRY_ROOT))
    simulator = importlib.import_module("backend.services.simulation.simulator")
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
