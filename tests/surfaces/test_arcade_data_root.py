"""Arcade strategy reads race artifacts from the shared data cache."""

from __future__ import annotations

import pandas as pd

from src.arcade import strategy as arcade_strategy
from src.arcade.strategy import SimConnector


def test_arcade_strategy_uses_the_shared_data_root(tmp_path, monkeypatch):
    data_root = tmp_path / "shared-data"
    monkeypatch.setenv("F1_STRAT_DATA_ROOT", str(data_root))

    featured_path = data_root / "processed" / "laps_featured_2024.parquet"
    featured_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "GP_Name": ["Test GP"],
            "Driver": ["VER"],
            "LapNumber": [2],
            "Time_s": [95.0],
        }
    ).to_parquet(featured_path, index=False)

    connector = object.__new__(SimConnector)
    real_augment = arcade_strategy.augment_featured_laps
    forwarded_roots = []

    def record_data_root(frame, year, *, data_root=None):
        forwarded_roots.append(data_root)
        return real_augment(frame, year, data_root=data_root)

    monkeypatch.setattr(arcade_strategy, "augment_featured_laps", record_data_root)
    laps = connector._load_laps_df(2024)

    assert laps is not None
    assert laps[["GP_Name", "Driver", "LapNumber"]].to_dict("records") == [
        {"GP_Name": "Test GP", "Driver": "VER", "LapNumber": 2}
    ]
    assert forwarded_roots == [data_root]

    race_dir = data_root / "raw" / "2099" / "Melbourne"
    race_dir.mkdir(parents=True)
    assert connector._resolve_race_dir(2099, "Australia") == race_dir
