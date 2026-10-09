"""Raw augmentation must never follow data paths outside the selected race."""

import os
import subprocess
from pathlib import Path

import pandas as pd

from src.f1_strat_manager.laps_augment import augment_featured_laps


def _write_laps(path: Path, elapsed_seconds: int) -> None:
    pd.DataFrame(
        {
            "Driver": ["NOR"],
            "LapNumber": [1],
            "Stint": [1],
            "TyreLife": [1],
            "Compound": ["MEDIUM"],
            "PitInTime": [pd.NaT],
            "Time": [pd.Timedelta(seconds=elapsed_seconds)],
            "TrackStatus": ["1"],
        }
    ).to_parquet(path)


def _make_directory_link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
    else:
        link.symlink_to(target, target_is_directory=True)


def test_augmentation_uses_safe_gp_alias_when_preferred_alias_escapes(tmp_path):
    data_root = tmp_path / "data"
    raw_year = data_root / "raw" / "2025"
    safe_race = raw_year / "Miami_Gardens"
    outside = tmp_path / "outside"
    safe_race.mkdir(parents=True)
    outside.mkdir()
    _write_laps(safe_race / "laps.parquet", 60)
    _write_laps(outside / "laps.parquet", 999)
    _make_directory_link(raw_year / "Miami", outside)

    augmented = augment_featured_laps(
        pd.DataFrame({"GP_Name": ["Miami"], "Driver": ["NOR"], "LapNumber": [1]}),
        2025,
        data_root=data_root,
    )

    assert augmented.loc[0, "Time_s"] == 60


def test_augmentation_skips_race_with_escaped_laps_path(tmp_path):
    data_root = tmp_path / "data"
    race = data_root / "raw" / "2025" / "Melbourne"
    outside = tmp_path / "outside"
    race.mkdir(parents=True)
    outside.mkdir()
    _write_laps(outside / "laps.parquet", 999)
    _make_directory_link(race / "laps.parquet", outside)

    featured = pd.DataFrame({"GP_Name": ["Melbourne"], "Driver": ["NOR"], "LapNumber": [1]})
    augmented = augment_featured_laps(featured, 2025, data_root=data_root)

    assert augmented.equals(featured)


def test_augmentation_skips_year_directory_outside_data_root(tmp_path):
    data_root = tmp_path / "data"
    outside = tmp_path / "outside"
    race = outside / "Melbourne"
    race.mkdir(parents=True)
    _write_laps(race / "laps.parquet", 999)
    _make_directory_link(data_root / "raw" / "2025", outside)

    featured = pd.DataFrame({"GP_Name": ["Melbourne"], "Driver": ["NOR"], "LapNumber": [1]})
    augmented = augment_featured_laps(featured, 2025, data_root=data_root)

    assert augmented.equals(featured)
