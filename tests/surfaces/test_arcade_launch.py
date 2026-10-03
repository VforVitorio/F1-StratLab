"""Guard Arcade's launch configuration through the menu and direct viewer.

The parser, menu validation, replay constructor and strategy DTO run for real.
Only graphics, race preparation and process/network startup are replaced.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

arcade = pytest.importorskip("arcade", reason="the arcade replay is an optional surface")

from src.arcade import main as arcade_main  # noqa: E402
from src.arcade.app import F1ArcadeView  # noqa: E402
from src.arcade.data import SessionData  # noqa: E402
from src.arcade.strategy import SimConnector  # noqa: E402
from src.arcade.stream import TelemetryStreamServer  # noqa: E402
from src.arcade.views import MenuView  # noqa: E402


@pytest.fixture
def launch_window(monkeypatch):
    """Keep configuration real while isolating graphics and external work."""
    window = SimpleNamespace(width=1280, height=720, current_view=None)
    window.show_view = lambda view: setattr(window, "current_view", view)
    window.push_handlers = lambda **handlers: None
    monkeypatch.setattr(arcade, "Window", lambda *args, **kwargs: window)
    monkeypatch.setattr(arcade, "Text", lambda *args, **kwargs: SimpleNamespace())
    monkeypatch.setattr(arcade, "set_background_color", lambda color: None)
    monkeypatch.setattr(arcade, "run", lambda: None)
    session = SessionData(year=2025, location="Melbourne")
    monkeypatch.setattr("src.arcade.views.prepare_race", lambda *args, **kwargs: session)
    monkeypatch.setattr(SimConnector, "start", lambda self: None)
    monkeypatch.setattr(TelemetryStreamServer, "start", lambda self: None)
    monkeypatch.setattr(F1ArcadeView, "_spawn_pitwall", lambda self: None)
    return window


def _launch(monkeypatch, window, route: str, year: int, provider: str | None = None):
    argv = ["f1-arcade"]
    if provider is not None:
        argv.extend(["--provider", provider])
    if route == "viewer":
        argv.extend(["--viewer", "--year", str(year), "--strategy", "--no-llm"])
    monkeypatch.setattr(sys, "argv", argv)
    arcade_main.main()
    menu = window.current_view
    if route == "menu":
        menu._cfg.year = year
        menu._cfg.strategy_mode = True
        menu._cfg.no_llm = True
        menu.on_key_press(arcade.key.ENTER, 0)
    return menu


@pytest.mark.parametrize("route", ["menu", "viewer"])
@pytest.mark.parametrize(
    ("explicit", "environment", "expected"),
    [
        ("openai", "lmstudio", "openai"),
        ("lmstudio", "openai", "lmstudio"),
        (None, "lmstudio", "lmstudio"),
        (None, None, "openai"),
        (None, "", "openai"),
    ],
)
def test_provider_reaches_strategy_request(
    monkeypatch, launch_window, route, explicit, environment, expected
):
    """An explicit CLI provider wins; omission preserves the environment."""
    if environment is None:
        monkeypatch.delenv("F1_LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("F1_LLM_PROVIDER", environment)
    menu = _launch(monkeypatch, launch_window, route, 2025, explicit)
    worker = menu._prep_thread
    assert worker is not None
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert menu._prep_error == ""
    menu.on_update(0.0)

    replay = launch_window.current_view
    assert isinstance(replay, F1ArcadeView)
    request = replay._strategy_connector._request
    assert request.provider == expected
    assert request.year == 2025
    assert request.no_llm is True


@pytest.mark.parametrize("route", ["menu", "viewer"])
@pytest.mark.parametrize("year", [2023, 2024])
def test_strategy_year_is_rejected_before_preparation(monkeypatch, launch_window, route, year):
    """Both entry paths stop before creating a preparation worker."""
    menu = _launch(monkeypatch, launch_window, route, year)

    assert isinstance(menu, MenuView)
    assert menu._error == "strategy requires year 2025"
    assert menu._loading is False
    assert menu._prep_thread is None
    assert menu._prep_result is None
    assert launch_window.current_view is menu
