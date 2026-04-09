"""Smoke tests — verify CI infrastructure and project structure."""

from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_src_structure():
    """src/ directory exists with expected sub-packages."""
    assert (ROOT / "src").is_dir()
    assert (ROOT / "src" / "rag").is_dir()
    assert (ROOT / "src" / "nlp").is_dir()
    assert (ROOT / "src" / "agents").is_dir()
    assert (ROOT / "src" / "simulation").is_dir()


def test_notebooks_structure():
    """Agent notebooks directory exists."""
    assert (ROOT / "notebooks" / "agents").is_dir()


def test_pyproject_exists():
    """pyproject.toml is present at repo root."""
    assert (ROOT / "pyproject.toml").is_file()


def test_simulation_imports():
    """RaceStateManager and RaceReplayEngine are importable."""
    pytest = __import__("pytest")
    pd = pytest.importorskip("pandas", reason="pandas not installed in this environment")  # noqa: F841
    from src.simulation.race_state_manager import RaceStateManager  # noqa: F401
    from src.simulation.replay_engine import RaceReplayEngine  # noqa: F401


def test_race_state_manager_melbourne():
    """RaceStateManager produces a valid lap_state from the Melbourne 2025 parquet."""
    import pytest

    pd = pytest.importorskip("pandas", reason="pandas not installed in this environment")
    from src.simulation.race_state_manager import RaceStateManager

    laps_path = ROOT / "data" / "raw" / "2025" / "Melbourne" / "laps.parquet"
    if not laps_path.exists():
        pytest.skip("Melbourne 2025 parquet not available in this environment")

    laps = pd.read_parquet(laps_path)
    rsm = RaceStateManager(laps, "NOR", "McLaren", gp_name="Melbourne", year=2025)

    assert rsm.total_laps == 57
    state = rsm.get_lap_state(20)

    assert state["lap_number"] == 20
    assert state["driver"]["driver"] == "NOR"
    assert state["driver"]["position"] == 1
    assert len(state["rivals"]) > 0
    assert "gp_name" in state["session_meta"]
