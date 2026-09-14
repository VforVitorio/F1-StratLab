"""Measure whether the current tyre signal can be carried to the race finish.

The production scorer currently knows the tyre cost at the decision lap, but it
does not have a measured bound for multiplying that cost across the remaining
race. This instrument measures the simplest continuation first: hold the
current set until the observed end of a final stint that reaches the race end.

The predicted cost is ``current_wear * future_observed_laps``. The target is the
sum of the model's own fuel-adjusted wear target over those future laps. Both
values use the per-stint fresh reference already used by ``deg_cost_s``. Future
rows are targets only; no future value is used to build the observation at the
cutoff.

This is a measurement of a continuation primitive, not a claim that a driver
should run to the flag. Monaco and Lusail therefore remain explicit contract
cases rather than being inferred from ``mandatory_stop_pending``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRAINING_YEARS = (2023, 2024)
HOLDOUT_YEAR = 2025
FRESH_MAX_TYRE_LIFE = 3
BOOTSTRAP_DRAWS = 500
BOOTSTRAP_SEED = 1238
HORIZON_BINS = [0, 3, 5, 10, 20, 50, np.inf]
HORIZON_LABELS = ["1-3", "4-5", "6-10", "11-20", "21-50", "51+"]


def _stint_id(frame: pd.DataFrame) -> pd.Series:
    """Build the stable key shared by the prediction and source frames."""
    return frame[["Year", "GP_Name", "DriverNumber", "Stint"]].astype(str).agg("|".join, axis=1)


def build_metadata(laps: pd.DataFrame) -> pd.DataFrame:
    """Return one source row per stint and tyre-life value.

    Duplicate tyre-life values are retained as a flag and excluded by the
    measurement. They occur around restart and timing-feed anomalies where a
    single stint number does not identify one chronological tyre sequence.
    """
    source = laps.copy()
    source["stint"] = _stint_id(source)
    source["max_stint"] = source.groupby(["Year", "GP_Name", "DriverNumber"])["Stint"].transform(
        "max"
    )
    source["race_last_lap"] = source.groupby(["Year", "GP_Name"])["LapNumber"].transform("max")
    source["fastest_lap_s"] = source.groupby(["Year", "GP_Name"])["LapTime_s"].transform("min")
    stint_last_lap = source.groupby("stint")["LapNumber"].transform("max")
    source["is_final_stint"] = source["Stint"].eq(source["max_stint"])
    source["reaches_race_end"] = stint_last_lap.ge(source["race_last_lap"] - 1)
    duplicate_counts = source.groupby(["stint", "TyreLife"])["LapNumber"].transform("size")
    source["duplicate_tyre_life"] = duplicate_counts.gt(1)

    return (
        source.groupby(["stint", "TyreLife"], as_index=False)
        .agg(
            lap_number=("LapNumber", "max"),
            race_last_lap=("race_last_lap", "max"),
            lap_time_s=("LapTime_s", "max"),
            fastest_lap_s=("fastest_lap_s", "max"),
            is_final_stint=("is_final_stint", "all"),
            reaches_race_end=("reaches_race_end", "all"),
            duplicate_tyre_life=("duplicate_tyre_life", "any"),
        )
        .rename(columns={"TyreLife": "tyre_life"})
    )


def normalise_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Normalise the two existing prediction instruments to one schema."""
    result = predictions.copy()
    parts = result["stint"].astype(str).str.split("|", expand=True)
    result["year"] = parts[0].astype(int)
    result["gp_name"] = parts[1]
    result["driver_number"] = parts[2].astype(int)
    result["stint_number"] = parts[3].astype(float)
    result["tyre_life"] = result["tyre_life"].astype(float)
    return result[
        ["stint", "year", "gp_name", "driver_number", "stint_number", "tyre_life", "pred", "target"]
    ]


def attach_references(
    predictions: pd.DataFrame,
    metadata: pd.DataFrame | None = None,
    max_reference_pct: float | None = None,
) -> pd.DataFrame:
    """Attach the live fresh reference, optionally using production gating."""
    result = predictions.sort_values(["stint", "tyre_life"]).copy()
    if metadata is not None:
        result = result.merge(metadata, on=["stint", "tyre_life"], how="left")
    fresh = result[result["tyre_life"] <= FRESH_MAX_TYRE_LIFE]
    if max_reference_pct is not None:
        required = {"lap_time_s", "fastest_lap_s"}
        if not required <= set(fresh.columns):
            raise ValueError(
                "metadata must carry lap_time_s and fastest_lap_s for the reference gate"
            )
        from src.agents.tire_agent import _reject_contaminated_laps

        clean_groups = []
        for _, group in fresh.groupby("stint", sort=False):
            clean_groups.append(
                _reject_contaminated_laps(
                    group.rename(columns={"lap_time_s": "LapTime_s"}),
                    float(group["fastest_lap_s"].iloc[0]),
                    max_reference_pct,
                )
            )
        fresh = pd.concat(clean_groups, ignore_index=False) if clean_groups else fresh.iloc[0:0]
    reference_pred = fresh.groupby("stint")["pred"].last()
    reference_target = fresh.groupby("stint")["target"].last()
    result["reference_pred"] = result["stint"].map(reference_pred)
    result["reference_target"] = result["stint"].map(reference_target)
    result["wear_pred"] = result["pred"] - result["reference_pred"]
    result["wear_target"] = result["target"] - result["reference_target"]
    return result


def measure_future_cost(
    predictions: pd.DataFrame,
    metadata: pd.DataFrame,
    max_reference_pct: float | None = None,
) -> pd.DataFrame:
    """Measure constant-current-wear cost against future same-set target cost."""
    frame = attach_references(predictions, metadata, max_reference_pct)
    final_stint = frame["is_final_stint"].astype("boolean").fillna(False)
    reaches_end = frame["reaches_race_end"].astype("boolean").fillna(False)
    duplicate_life = frame["duplicate_tyre_life"].astype("boolean").fillna(True)
    eligible = frame[
        final_stint
        & reaches_end
        & ~duplicate_life
        & (frame["tyre_life"] > FRESH_MAX_TYRE_LIFE)
        & frame["wear_pred"].notna()
        & frame["wear_target"].notna()
    ].copy()

    rows: list[dict[str, Any]] = []
    for stint, group in eligible.groupby("stint", sort=False):
        ordered = group.sort_values(["lap_number", "tyre_life"])
        future_wear = ordered["wear_target"].to_numpy(dtype=float)
        future_laps = ordered["lap_number"].to_numpy(dtype=float)
        for index, (_, current) in enumerate(ordered.iterrows()):
            later_wear = future_wear[index + 1 :]
            later_laps = future_laps[index + 1 :]
            if not len(later_wear):
                continue
            predicted_cost = float(current["wear_pred"]) * len(later_wear)
            actual_cost = float(np.sum(later_wear))
            rows.append(
                {
                    "stint": stint,
                    "year": int(current["year"]),
                    "gp_name": current["gp_name"],
                    "lap_number": int(current["lap_number"]),
                    "tyre_life": float(current["tyre_life"]),
                    "future_observed_laps": int(len(later_wear)),
                    "future_race_laps": int(
                        max(0.0, current["race_last_lap"] - current["lap_number"])
                    ),
                    "predicted_cost_s": predicted_cost,
                    "actual_cost_s": actual_cost,
                    "error_s": predicted_cost - actual_cost,
                    "continuation_state": "run_to_observed_race_end",
                    "future_last_lap": int(later_laps.max()),
                }
            )
    return pd.DataFrame(rows)


def _bootstrap_ci(frame: pd.DataFrame) -> tuple[float, float]:
    """Cluster-bootstrap mean absolute error by stint for a stable uncertainty band."""
    per_stint = (
        frame.assign(abs_error=frame["error_s"].abs())
        .groupby("stint")
        .agg(
            abs_sum=("abs_error", "sum"),
            n=("abs_error", "size"),
        )
    )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    sampled = rng.integers(0, len(per_stint), size=(BOOTSTRAP_DRAWS, len(per_stint)))
    abs_sum = per_stint["abs_sum"].to_numpy()[sampled].sum(axis=1)
    count = per_stint["n"].to_numpy()[sampled].sum(axis=1)
    samples = abs_sum / count
    return float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))


def summarise(frame: pd.DataFrame) -> dict[str, Any]:
    """Summarise error, bound candidates, horizon bands, and race spread."""
    if frame.empty:
        return {"n": 0, "stints": 0}
    absolute = frame["error_s"].abs()
    horizon = pd.cut(frame["future_observed_laps"], HORIZON_BINS, labels=HORIZON_LABELS)
    by_horizon = frame.assign(horizon=horizon).groupby("horizon", observed=True)
    by_race = frame.groupby(["year", "gp_name"])
    ci_low, ci_high = _bootstrap_ci(frame)
    return {
        "n": int(len(frame)),
        "stints": int(frame["stint"].nunique()),
        "mean_abs_error_s": round(float(absolute.mean()), 4),
        "median_abs_error_s": round(float(absolute.median()), 4),
        "signed_bias_s": round(float(frame["error_s"].mean()), 4),
        "p95_abs_error_s": round(float(absolute.quantile(0.95)), 4),
        "p99_abs_error_s": round(float(absolute.quantile(0.99)), 4),
        "mean_abs_error_ci95_s": [round(ci_low, 4), round(ci_high, 4)],
        "by_future_laps": {
            str(label): {
                "n": int(len(group)),
                "mean_abs_error_s": round(float(group["error_s"].apply(abs).mean()), 4),
                "signed_bias_s": round(float(group["error_s"].mean()), 4),
            }
            for label, group in by_horizon
        },
        "by_race": {
            f"{int(year)}:{gp}": {
                "n": int(len(group)),
                "mean_abs_error_s": round(float(group["error_s"].apply(abs).mean()), 4),
                "signed_bias_s": round(float(group["error_s"].mean()), 4),
            }
            for (year, gp), group in by_race
        },
    }


def continuation_contract() -> list[dict[str, Any]]:
    """Return explicit continuation states instead of inferring them from one boolean."""
    return [
        {
            "state": "no_known_event_requirement",
            "run_to_flag": "candidate",
            "required_stops": 0,
            "decision": "needs tyre and race-end evidence",
        },
        {
            "state": "one_required_stop",
            "run_to_flag": "inadmissible",
            "required_stops": 1,
            "decision": "model at least one later stop",
        },
        {
            "state": "monaco_2025",
            "run_to_flag": "inadmissible",
            "required_stops": 2,
            "decision": "apply the two-stop and three-set event rule",
        },
        {
            "state": "lusail_2025",
            "run_to_flag": "inadmissible",
            "required_stops": 2,
            "decision": "apply the event stop and tyre-life constraints",
        },
        {
            "state": "unknown_obligation",
            "run_to_flag": "abstain",
            "required_stops": None,
            "decision": "do not invent a continuation",
        },
    ]


def _load_predictions(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the existing TCN instruments and their matching source parquet."""
    if year == HOLDOUT_YEAR:
        from scripts.measure_fresh_reference_gate_2025 import predict_2025_stints

        predictions = predict_2025_stints()
        source_path = ROOT / "data" / "processed" / "laps_featured_2025.parquet"
    else:
        from scripts.measure_tyre_reference import predict_training_stints

        predictions = predict_training_stints()
        source_path = ROOT / "data" / "processed" / "laps_tiredeg.parquet"
    source = pd.read_parquet(source_path)
    source = source[source["Year"].eq(year)]
    return normalise_predictions(
        predictions[predictions["stint"].astype(str).str.startswith(f"{year}|")]
    ), build_metadata(source)


def run_measurement() -> dict[str, Any]:
    """Run training and holdout measurements and derive a training-only p99 bound."""
    from src.agents.tire_agent import CFG

    reference_gate_pct = CFG.fresh_reference_max_pct_of_fastest
    measured: dict[int, pd.DataFrame] = {}
    for year in (*TRAINING_YEARS, HOLDOUT_YEAR):
        predictions, metadata = _load_predictions(year)
        measured[year] = measure_future_cost(predictions, metadata, reference_gate_pct)

    training = pd.concat([measured[year] for year in TRAINING_YEARS], ignore_index=True)
    holdout = measured[HOLDOUT_YEAR]
    training_bound = float(training["error_s"].abs().quantile(0.99)) if not training.empty else None
    holdout_coverage = None
    if training_bound is not None and not holdout.empty:
        holdout_coverage = float((holdout["error_s"].abs() <= training_bound).mean())

    return {
        "generated_by": "scripts/measure_terminal_tyre_liability.py",
        "training_years": list(TRAINING_YEARS),
        "holdout_year": HOLDOUT_YEAR,
        "fresh_max_tyre_life": FRESH_MAX_TYRE_LIFE,
        "fresh_reference_max_pct_of_fastest": reference_gate_pct,
        "prediction": "current_wear * future_observed_laps",
        "target": "sum of future same-stint model-target wear",
        "uses_future_rows_for_observation": False,
        "continuation_contract": continuation_contract(),
        "training": summarise(training),
        "holdout_2025": summarise(holdout),
        "training_p99_abs_error_s": None if training_bound is None else round(training_bound, 4),
        "holdout_coverage_under_training_p99": None
        if holdout_coverage is None
        else round(holdout_coverage, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "documents" / "audits" / "MEASURE_1238_terminal_tyre_liability.json",
    )
    args = parser.parse_args()
    payload = run_measurement()
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
