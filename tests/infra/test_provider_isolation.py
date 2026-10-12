"""The simulation API rejects provider changes without affecting chat requests."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[2]
TELEMETRY_ROOT = ROOT / "src" / "telemetry"


def test_matching_provider_is_returned_in_the_start_event(monkeypatch):
    if not (TELEMETRY_ROOT / "backend").is_dir():
        pytest.skip("src/telemetry/backend is not present in this checkout")
    monkeypatch.syspath_prepend(str(TELEMETRY_ROOT))

    from backend.api.v1.endpoints import strategy
    from backend.core.config import resolve_simulation_provider
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    monkeypatch.setenv("F1_LLM_PROVIDER", "openai")
    monkeypatch.setattr(strategy, "resolve_race_dir", lambda *_args: Path("."))
    monkeypatch.setattr(strategy, "_resolve_race_dir", lambda *_args: Path("."))
    monkeypatch.setattr(strategy, "validate_radio_paths", lambda *_args: None)

    configs = []
    simulation_service = ModuleType("backend.services.simulation")

    class SimConfig:
        def __init__(self, **values):
            self.__dict__.update(values)

    def simulate_race(config):
        configs.append(config)
        provider = resolve_simulation_provider(config.provider)
        return iter([{"type": "start", "data": {"provider": provider}}])

    simulation_service.SimConfig = SimConfig
    simulation_service.simulate_race = simulate_race
    monkeypatch.setitem(sys.modules, "backend.services.simulation", simulation_service)

    app = FastAPI()
    app.include_router(strategy.router, prefix="/api/v1")
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/strategy/simulate",
            json={
                "year": 2025,
                "gp": "Melbourne",
                "driver": "NOR",
                "team": "McLaren",
                "no_llm": True,
                "provider": "openai",
            },
        )

    assert response.status_code == 200, response.text
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert '"provider": "openai"' in response.text
    assert configs[0].provider == "openai"
    assert os.environ["F1_LLM_PROVIDER"] == "openai"


def test_provider_conflict_is_rejected_while_chat_is_in_flight(monkeypatch):
    if not (TELEMETRY_ROOT / "backend").is_dir():
        pytest.skip("src/telemetry/backend is not present in this checkout")
    monkeypatch.syspath_prepend(str(TELEMETRY_ROOT))

    from backend.api.v1.endpoints import chat, strategy
    from backend.services.chatbot import llm_service
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    monkeypatch.setenv("F1_LLM_PROVIDER", "lmstudio")
    chat_provider = llm_service.LLM_PROVIDER
    chat_started = Event()
    finish_chat = Event()
    chat_observations: list[tuple[str | None, str]] = []

    def local_chat_stub(**_kwargs):
        chat_observations.append((os.environ.get("F1_LLM_PROVIDER"), llm_service.LLM_PROVIDER))
        chat_started.set()
        if not finish_chat.wait(timeout=10):
            raise TimeoutError("the provider isolation test did not release the chat stub")
        return {
            "choices": [{"message": {"content": "local test response"}}],
            "model": "local-test",
            "usage": {"total_tokens": 1},
        }

    monkeypatch.setattr(chat, "lm_send_message", local_chat_stub)
    monkeypatch.setattr(strategy, "resolve_race_dir", lambda *_args: Path("."))
    monkeypatch.setattr(strategy, "_resolve_race_dir", lambda *_args: Path("."))
    monkeypatch.setattr(strategy, "validate_radio_paths", lambda *_args: None)

    app = FastAPI()
    app.include_router(strategy.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")

    def send_chat():
        with TestClient(app) as client:
            return client.post("/api/v1/chat/message", json={"text": "status"})

    def send_conflicting_simulation():
        with TestClient(app) as client:
            return client.post(
                "/api/v1/strategy/simulate",
                json={
                    "year": 2025,
                    "gp": "Melbourne",
                    "driver": "NOR",
                    "team": "McLaren",
                    "no_llm": True,
                    "provider": "openai",
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        chat_future = executor.submit(send_chat)
        try:
            assert chat_started.wait(timeout=5), "chat did not reach the local LLM boundary"
            simulation_response = executor.submit(send_conflicting_simulation).result(timeout=5)
            assert simulation_response.status_code == 409, simulation_response.text
            assert "text/event-stream" not in simulation_response.headers.get("content-type", "")
            assert os.environ["F1_LLM_PROVIDER"] == "lmstudio"
        finally:
            finish_chat.set()

        chat_response = chat_future.result(timeout=10)

    assert chat_response.status_code == 200, chat_response.text
    assert chat_response.json()["response"] == "local test response"
    assert chat_observations == [("lmstudio", chat_provider)]
    assert llm_service.LLM_PROVIDER == chat_provider
