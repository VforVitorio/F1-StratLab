"""Smoke tests — verify CI infrastructure and project structure."""
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_src_structure():
    """src/ directory exists with expected sub-packages."""
    assert (ROOT / "src").is_dir()
    assert (ROOT / "src" / "rag").is_dir()
    assert (ROOT / "src" / "nlp").is_dir()
    assert (ROOT / "src" / "agents").is_dir()


def test_notebooks_structure():
    """Agent notebooks directory exists."""
    assert (ROOT / "notebooks" / "agents").is_dir()


def test_pyproject_exists():
    """pyproject.toml is present at repo root."""
    assert (ROOT / "pyproject.toml").is_file()
