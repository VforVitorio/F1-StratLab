"""Compare raw-lap and public-timing relative pace before sampled pit entries.

The measurement is deliberately offline. It uses the last completed lap before
the entry and public interval snapshots at or before the reconstructed entry.
It is a validation of an observable signal, not a strategy-quality label.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_public_timing_precut.json"
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_public_relative_pace.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_724_public_relative_pace.md"

MAX_SNAPSHOT_AGE_S = 10.0
MAX_PAIR_SKEW_S = 5.0


def _timestamp(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def _seconds(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timedelta):
        return float(value.total_seconds())
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _driver_row(laps: pd.DataFrame, driver_number: int, lap: int) -> pd.Series | None:
    rows = laps[(laps["LapNumber"] == lap) & (laps["DriverNumber"] == driver_number)]
    return None if rows.empty else rows.iloc[0]


def _public_snapshot(
    intervals: pd.DataFrame, session_key: int, driver_number: int, cutoff: pd.Timestamp
) -> pd.Series | None:
    rows = intervals[
        (intervals["session_key"] == session_key)
        & (intervals["driver_number"] == driver_number)
        & intervals["date"].notna()
        & intervals["gap_to_leader_seconds"].notna()
        & (intervals["date"] <= cutoff)
    ]
    return None if rows.empty else rows.sort_values("date").iloc[-1]


def _public_pair(
    intervals: pd.DataFrame,
    session_key: int,
    driver_number: int,
    ahead_number: int,
    cutoff: pd.Timestamp,
) -> dict[str, Any] | None:
    driver = _public_snapshot(intervals, session_key, driver_number, cutoff)
    ahead = _public_snapshot(intervals, session_key, ahead_number, cutoff)
    if driver is None or ahead is None:
        return None
    driver_date = _timestamp(driver["date"])
    ahead_date = _timestamp(ahead["date"])
    if pd.isna(driver_date) or pd.isna(ahead_date):
        return None
    return {
        "gap_s": float(driver["gap_to_leader_seconds"]) - float(ahead["gap_to_leader_seconds"]),
        "driver_date": driver_date,
        "ahead_date": ahead_date,
        "skew_s": abs(float((driver_date - ahead_date).total_seconds())),
        "freshness_s": max(
            float((cutoff - driver_date).total_seconds()),
            float((cutoff - ahead_date).total_seconds()),
        ),
    }


def measure_candidate(
    candidate: dict[str, Any], laps: pd.DataFrame, intervals: pd.DataFrame
) -> dict[str, Any]:
    """Measure one candidate using only completed and public pre-cutoff data."""
    result = {
        "event_id": candidate["event_id"],
        "race": candidate["race"],
        "driver": candidate["driver"],
        "driver_number": candidate["driver_number"],
        "session_key": candidate["session_key"],
        "pit_in_lap": candidate["pit_in_lap"],
        "review_status": candidate["review_status"],
        "review_disposition": candidate["review_disposition"],
        "status": "no_anchor",
        "completed_lap": None,
        "ahead_driver_number": None,
        "raw_relative_pace_s": None,
        "public_relative_pace_s": None,
        "public_current_gap_s": None,
        "public_previous_gap_s": None,
        "public_current_freshness_s": None,
        "public_previous_freshness_s": None,
        "public_current_skew_s": None,
        "public_previous_skew_s": None,
    }
    cutoff = _timestamp(candidate.get("pit_in_utc") or candidate.get("cutoff_utc"))
    if pd.isna(cutoff):
        return result

    completed_lap = int(candidate["pit_in_lap"]) - 1
    subject = _driver_row(laps, int(candidate["driver_number"]), completed_lap)
    if subject is None or pd.isna(subject.get("Position")):
        result["status"] = "no_pre_lap_position"
        return result
    position = int(subject["Position"])
    ahead_rows = laps[(laps["LapNumber"] == completed_lap) & (laps["Position"] == position - 1)]
    if ahead_rows.empty:
        result["status"] = "no_car_ahead"
        return result
    ahead = ahead_rows.iloc[0]
    subject_time = _seconds(subject.get("LapTime"))
    ahead_time = _seconds(ahead.get("LapTime"))
    if subject_time is None or ahead_time is None:
        result["status"] = "no_raw_pace"
        return result

    driver_number = int(candidate["driver_number"])
    ahead_number = int(ahead["DriverNumber"])
    current = _public_pair(
        intervals, int(candidate["session_key"]), driver_number, ahead_number, cutoff
    )
    if current is None:
        result["status"] = "no_public_pair"
        return result
    lap_duration = pd.Timedelta(seconds=subject_time)
    previous = _public_pair(
        intervals,
        int(candidate["session_key"]),
        driver_number,
        ahead_number,
        cutoff - lap_duration,
    )
    result.update(
        {
            "completed_lap": completed_lap,
            "ahead_driver_number": ahead_number,
            "raw_relative_pace_s": round(subject_time - ahead_time, 4),
            "public_current_gap_s": round(current["gap_s"], 4),
            "public_current_freshness_s": round(current["freshness_s"], 4),
            "public_current_skew_s": round(current["skew_s"], 4),
        }
    )
    if current["freshness_s"] > MAX_SNAPSHOT_AGE_S or current["skew_s"] > MAX_PAIR_SKEW_S:
        result["status"] = "public_current_stale_or_skewed"
        return result
    if previous is None:
        result["status"] = "no_previous_public_pair"
        return result
    result.update(
        {
            "public_previous_gap_s": round(previous["gap_s"], 4),
            "public_previous_freshness_s": round(previous["freshness_s"], 4),
            "public_previous_skew_s": round(previous["skew_s"], 4),
        }
    )
    if previous["freshness_s"] > MAX_SNAPSHOT_AGE_S or previous["skew_s"] > MAX_PAIR_SKEW_S:
        result["status"] = "public_previous_stale_or_skewed"
        return result

    current_midpoint = current["driver_date"] + (current["ahead_date"] - current["driver_date"]) / 2
    previous_midpoint = (
        previous["driver_date"] + (previous["ahead_date"] - previous["driver_date"]) / 2
    )
    elapsed_s = (current_midpoint - previous_midpoint).total_seconds()
    if elapsed_s <= 0:
        result["status"] = "invalid_public_time_order"
        return result
    result["public_relative_pace_s"] = round(
        (current["gap_s"] - previous["gap_s"]) / elapsed_s * subject_time,
        4,
    )
    result["status"] = "comparable_pre_cutoff_pair"
    return result


def load_laps(race: str) -> pd.DataFrame:
    """Load one raw race frame and normalise identity columns."""
    path = ROOT / "data" / "raw" / "2025" / race / "laps.parquet"
    frame = pd.read_parquet(path)
    frame["LapNumber"] = pd.to_numeric(frame["LapNumber"], errors="coerce")
    frame["DriverNumber"] = pd.to_numeric(frame["DriverNumber"], errors="coerce")
    frame["Position"] = pd.to_numeric(frame["Position"], errors="coerce")
    return frame


def load_intervals() -> pd.DataFrame:
    frames = [
        pd.read_parquet(
            path,
            columns=[
                "session_key",
                "driver_number",
                "date",
                "gap_to_leader_seconds",
            ],
        )
        for path in sorted((ROOT / "data" / "raw" / "2025").glob("*/intervals.parquet"))
    ]
    result = pd.concat(frames, ignore_index=True)
    result["session_key"] = pd.to_numeric(result["session_key"], errors="coerce")
    result["driver_number"] = pd.to_numeric(result["driver_number"], errors="coerce")
    result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce")
    return result


def build_measurement(source: dict[str, Any]) -> dict[str, Any]:
    intervals = load_intervals()
    rows = []
    for candidate in source["rows"]:
        if candidate["status"] != "precut_snapshot":
            continue
        rows.append(measure_candidate(candidate, load_laps(candidate["race"]), intervals))
    counts = Counter(row["status"] for row in rows)
    comparable = pd.DataFrame(
        [row for row in rows if row["status"] == "comparable_pre_cutoff_pair"]
    )
    if comparable.empty:
        agreement = {
            "entries": 0,
            "pearson_correlation": None,
            "spearman_correlation": None,
            "nonzero_sign_agreement": None,
        }
    else:
        raw = comparable["raw_relative_pace_s"]
        public = comparable["public_relative_pace_s"]
        nonzero = (raw.abs() > 1e-9) & (public.abs() > 1e-9)
        same_sign = raw[nonzero].map(lambda value: value > 0) == public[nonzero].map(
            lambda value: value > 0
        )
        agreement = {
            "entries": len(comparable),
            "pearson_correlation": round(float(raw.corr(public)), 4),
            "spearman_correlation": round(float(raw.rank().corr(public.rank())), 4),
            "nonzero_sign_agreement": round(float(same_sign.mean()), 4),
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": 2025,
        "source": str(INPUT_JSON.relative_to(ROOT)),
        "cutoff_rule": "all public interval dates <= approximate pit_in_utc",
        "completed_lap_rule": "pit_in_lap - 1",
        "max_snapshot_age_s": MAX_SNAPSHOT_AGE_S,
        "max_pair_skew_s": MAX_PAIR_SKEW_S,
        "input_entries": len(source["rows"]),
        "measured_entries": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "agreement": agreement,
        "rows": rows,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    sign_agreement = payload["agreement"]["nonzero_sign_agreement"]
    sign_agreement_text = "n/a" if sign_agreement is None else f"{sign_agreement:.1%}"
    lines = [
        "# Public relative pace before pit entry",
        "",
        "This is an offline comparison for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.",
        "It compares a raw completed-lap time difference with relative gap movement from public timing. It does not score the team's strategy and does not change the production scorer.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- source: `{payload['source']}`",
        f"- cutoff: `{payload['cutoff_rule']}`",
        f"- completed lap: `{payload['completed_lap_rule']}`",
        f"- maximum snapshot age: **{payload['max_snapshot_age_s']:.0f} seconds**",
        f"- maximum pair timestamp skew: **{payload['max_pair_skew_s']:.0f} seconds**",
        f"- input entries: **{payload['input_entries']}**",
        f"- measured entries: **{payload['measured_entries']}**",
        "",
        "## Status",
        "",
        "| status | entries |",
        "| --- | ---: |",
    ]
    for status, count in payload["status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    comparable = payload["status_counts"].get("comparable_pre_cutoff_pair", 0)
    lines.extend(
        [
            "",
            f"Only `comparable_pre_cutoff_pair` rows, **{comparable}**, can be used for a first agreement or correlation measure.",
            "The raw-lap value is `subject_lap_time - car_ahead_lap_time`, so negative means our car was faster. The public value is the change in the pair gap over approximately one subject lap, scaled to seconds per lap; positive means the subject lost relative time.",
            "",
            "## Agreement",
            "",
            f"- Pearson correlation: **{payload['agreement']['pearson_correlation']}**",
            f"- Spearman correlation: **{payload['agreement']['spearman_correlation']}**",
            f"- same non-zero sign: **{sign_agreement_text}**",
            "",
            "## Decision",
            "",
            "Keep the two signals as a shadow comparison until their sign and agreement are measured on the comparable rows. Do not add a traffic or rejoin cost to the scorer from this export alone. The retrospective rejoin benchmark remains a separate measure.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    payload = build_measurement(source)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(OUTPUT_MD)
    print(
        json.dumps(
            {
                "measured_entries": payload["measured_entries"],
                "status_counts": payload["status_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
