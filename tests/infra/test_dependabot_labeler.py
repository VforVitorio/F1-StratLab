"""Keep Dependabot's changed-file labels aligned with the tracked manifests."""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
LABELER_CONFIG = ROOT / ".github" / "labeler.yml"


def _matched_labels(path: str) -> set[str]:
    config = yaml.safe_load(LABELER_CONFIG.read_text(encoding="utf-8"))
    return {
        label
        for label, rules in config.items()
        if any(
            fnmatchcase(path, pattern)
            for rule in rules
            for changed_files in rule.get("changed-files", [])
            for pattern in changed_files.get("any-glob-to-any-file", [])
        )
    }


def test_pitwall_dependency_manifests_keep_dependency_and_codebase_labels() -> None:
    for path in (
        "src/pitwall/ui/package.json",
        "src/pitwall/ui/package-lock.json",
    ):
        labels = _matched_labels(path)
        assert {"area: deps", "area: codebase"} <= labels, (path, labels)


def test_telemetry_gitlink_gets_data_and_codebase_labels() -> None:
    labels = _matched_labels("src/telemetry")
    assert {"area: data", "area: codebase"} <= labels
