"""Hermetic checks for the terminal tyre-liability measurement primitives."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.measure_terminal_tyre_liability import (
    attach_references,
    continuation_contract,
    measure_future_cost,
)

ROOT = Path(__file__).resolve().parents[2]
MODEL_ROUTING = ROOT / "data" / "models" / "tire_degradation" / "routing_config.json"


def _predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stint": ["2023|Test|1|1.0"] * 5,
            "year": [2023] * 5,
            "gp_name": ["Test"] * 5,
            "driver_number": [1] * 5,
            "stint_number": [1.0] * 5,
            "tyre_life": [1.0, 2.0, 3.0, 4.0, 5.0],
            "pred": [0.0, 0.1, 0.2, 1.6, 1.6],
            "target": [0.0, 0.1, 0.2, 1.0, 1.5],
        }
    )


def _metadata() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stint": ["2023|Test|1|1.0"] * 5,
            "tyre_life": [1.0, 2.0, 3.0, 4.0, 5.0],
            "lap_number": [1, 2, 3, 4, 5],
            "race_last_lap": [5] * 5,
            "lap_time_s": [100.0] * 5,
            "fastest_lap_s": [100.0] * 5,
            "is_final_stint": [True] * 5,
            "reaches_race_end": [True] * 5,
            "duplicate_tyre_life": [False] * 5,
        }
    )


def test_future_cost_uses_only_laps_after_the_cutoff():
    measured = measure_future_cost(_predictions(), _metadata())

    row = measured.loc[measured["tyre_life"] == 4.0].iloc[0]
    assert row["future_observed_laps"] == 1
    assert row["predicted_cost_s"] == pytest.approx(1.4)
    assert row["actual_cost_s"] == pytest.approx(1.3)
    assert row["error_s"] == pytest.approx(0.1)
    assert not (measured["tyre_life"] <= 3).any()


def test_future_rows_do_not_change_the_fresh_reference():
    before = attach_references(_predictions())
    changed = _predictions()
    changed.loc[changed["tyre_life"] == 5.0, "pred"] = 99.0
    after = attach_references(changed)

    assert before.loc[before["tyre_life"] == 4.0, "reference_pred"].iloc[0] == pytest.approx(
        after.loc[after["tyre_life"] == 4.0, "reference_pred"].iloc[0]
    )


def test_continuation_contract_does_not_infer_legality_from_one_boolean():
    contract = {row["state"]: row for row in continuation_contract()}

    assert contract["monaco_2025"]["run_to_flag"] == "inadmissible"
    assert contract["lusail_2025"]["required_stops"] == 2
    assert contract["unknown_obligation"]["run_to_flag"] == "abstain"


@pytest.mark.skipif(
    not MODEL_ROUTING.exists(), reason="the production reference gate needs the local TCN bundle"
)
def test_contaminated_fresh_reference_is_not_used():
    predictions = _predictions()
    metadata = _metadata()
    metadata.loc[metadata["tyre_life"] == 3.0, "lap_time_s"] = 120.0

    measured = measure_future_cost(predictions, metadata, max_reference_pct=1.10)

    row = measured.loc[measured["tyre_life"] == 4.0].iloc[0]
    assert row["predicted_cost_s"] == pytest.approx(1.5)
