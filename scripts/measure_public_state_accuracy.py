"""Measure public pair-order and gap accuracy before sampled pit entries.

OpenF1's cached ``intervals`` feed has timing gaps and lapped flags, but no
official absolute position column. This report therefore measures the factual
state that the cache can support: whether the car that was directly ahead in
the raw lap remains ahead publicly, and the error in their pair gap.
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
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_public_state_accuracy.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_724_public_state_accuracy.md"

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
        return float(value)
    except (TypeError, ValueError):
        return None


def _driver_row(laps: pd.DataFrame, driver_number: int, lap: int) -> pd.Series | None:
    rows = laps[(laps["LapNumber"] == lap) & (laps["DriverNumber"] == driver_number)]
    return None if rows.empty else rows.iloc[0]


def _raw_pair(
    laps: pd.DataFrame, driver_number: int, completed_lap: int
) -> tuple[pd.Series, pd.Series, float] | None:
    """Return the subject, its directly-ahead car, and the raw line gap."""
    subject = _driver_row(laps, driver_number, completed_lap)
    if subject is None or pd.isna(subject.get("Position")):
        return None
    position = int(subject["Position"])
    if position <= 1:
        return None
    ahead_rows = laps[
        (laps["LapNumber"] == completed_lap)
        & (laps["Position"] == position - 1)
        & laps["Time"].notna()
    ]
    if ahead_rows.empty:
        return None
    ahead = ahead_rows.iloc[0]
    subject_time = _seconds(subject.get("Time"))
    ahead_time = _seconds(ahead.get("Time"))
    if subject_time is None or ahead_time is None:
        return None
    raw_gap = subject_time - ahead_time
    if raw_gap < 0:
        return None
    return subject, ahead, raw_gap


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
    subject = _public_snapshot(intervals, session_key, driver_number, cutoff)
    ahead = _public_snapshot(intervals, session_key, ahead_number, cutoff)
    if subject is None or ahead is None:
        return None
    subject_date = _timestamp(subject["date"])
    ahead_date = _timestamp(ahead["date"])
    if pd.isna(subject_date) or pd.isna(ahead_date):
        return None
    return {
        "gap_s": float(subject["gap_to_leader_seconds"]) - float(ahead["gap_to_leader_seconds"]),
        "subject_date": subject_date,
        "ahead_date": ahead_date,
        "freshness_s": max(
            float((cutoff - subject_date).total_seconds()),
            float((cutoff - ahead_date).total_seconds()),
        ),
        "skew_s": abs(float((subject_date - ahead_date).total_seconds())),
        "subject_lapped": bool(subject.get("is_lapped", False)),
        "ahead_lapped": bool(ahead.get("is_lapped", False)),
    }


def measure_candidate(
    candidate: dict[str, Any], laps: pd.DataFrame, intervals: pd.DataFrame
) -> dict[str, Any]:
    """Compare one raw pair with public timing available by the cutoff."""
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
        "raw_position": None,
        "ahead_driver_number": None,
        "raw_pair_gap_s": None,
        "public_pair_gap_s": None,
        "public_pair_order_matches": None,
        "pair_gap_error_s": None,
        "public_freshness_s": None,
        "public_pair_skew_s": None,
    }
    cutoff = _timestamp(candidate.get("pit_in_utc") or candidate.get("cutoff_utc"))
    if pd.isna(cutoff):
        return result

    completed_lap = int(candidate["pit_in_lap"]) - 1
    raw = _raw_pair(laps, int(candidate["driver_number"]), completed_lap)
    if raw is None:
        result["status"] = "no_pre_lap_pair"
        return result
    subject, ahead, raw_gap = raw
    ahead_number = int(ahead["DriverNumber"])
    result.update(
        {
            "completed_lap": completed_lap,
            "raw_position": int(subject["Position"]),
            "ahead_driver_number": ahead_number,
            "raw_pair_gap_s": round(raw_gap, 4),
        }
    )

    public = _public_pair(
        intervals,
        int(candidate["session_key"]),
        int(candidate["driver_number"]),
        ahead_number,
        cutoff,
    )
    if public is None:
        result["status"] = "no_public_pair"
        return result
    result.update(
        {
            "public_pair_gap_s": round(public["gap_s"], 4),
            "public_freshness_s": round(public["freshness_s"], 4),
            "public_pair_skew_s": round(public["skew_s"], 4),
        }
    )
    if public["freshness_s"] > MAX_SNAPSHOT_AGE_S or public["skew_s"] > MAX_PAIR_SKEW_S:
        result["status"] = "public_pair_stale_or_skewed"
        return result
    if public["subject_lapped"] or public["ahead_lapped"]:
        result["status"] = "public_pair_lapped"
        return result

    result.update(
        {
            "public_pair_order_matches": public["gap_s"] >= 0,
            "pair_gap_error_s": round(public["gap_s"] - raw_gap, 4),
            "status": "comparable_pre_cutoff_pair",
        }
    )
    return result


def load_laps(race: str) -> pd.DataFrame:
    """Load one raw race frame and normalise the pair identity columns."""
    frame = pd.read_parquet(ROOT / "data" / "raw" / "2025" / race / "laps.parquet")
    for column in ("LapNumber", "DriverNumber", "Position"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def load_intervals() -> pd.DataFrame:
    """Load public interval rows used by the pair comparison."""
    columns = [
        "session_key",
        "driver_number",
        "date",
        "gap_to_leader_seconds",
        "is_lapped",
    ]
    frames = [
        pd.read_parquet(path, columns=columns)
        for path in sorted((ROOT / "data" / "raw" / "2025").glob("*/intervals.parquet"))
    ]
    if not frames:
        raise FileNotFoundError("No 2025 intervals.parquet files found")
    result = pd.concat(frames, ignore_index=True)
    result["session_key"] = pd.to_numeric(result["session_key"], errors="coerce")
    result["driver_number"] = pd.to_numeric(result["driver_number"], errors="coerce")
    result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce", format="mixed")
    return result


def build_measurement(source: dict[str, Any]) -> dict[str, Any]:
    intervals = load_intervals()
    candidates: dict[str, dict[str, Any]] = {}
    for candidate in source["rows"]:
        if candidate["status"] == "precut_snapshot":
            candidates.setdefault(str(candidate["event_id"]), candidate)
    laps_by_race: dict[str, pd.DataFrame] = {}
    rows = []
    for candidate in sorted(candidates.values(), key=lambda row: str(row["event_id"])):
        laps = laps_by_race.setdefault(candidate["race"], load_laps(candidate["race"]))
        rows.append(measure_candidate(candidate, laps, intervals))

    counts = Counter(row["status"] for row in rows)
    comparable = pd.DataFrame(
        [row for row in rows if row["status"] == "comparable_pre_cutoff_pair"]
    )
    if comparable.empty:
        accuracy = {
            "entries": 0,
            "pair_order_accuracy": None,
            "pair_order_mismatches": None,
            "pair_gap_signed_mean_s": None,
            "pair_gap_abs_median_s": None,
            "pair_gap_abs_p90_s": None,
        }
    else:
        gap_error = comparable["pair_gap_error_s"]
        accuracy = {
            "entries": len(comparable),
            "pair_order_accuracy": round(float(comparable["public_pair_order_matches"].mean()), 4),
            "pair_order_mismatches": int((~comparable["public_pair_order_matches"]).sum()),
            "pair_gap_signed_mean_s": round(float(gap_error.mean()), 4),
            "pair_gap_abs_median_s": round(float(gap_error.abs().median()), 4),
            "pair_gap_abs_p90_s": round(float(gap_error.abs().quantile(0.9)), 4),
        }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": 2025,
        "source": str(INPUT_JSON.relative_to(ROOT)),
        "cutoff_rule": "all public interval dates <= approximate pit_in_utc",
        "raw_reference_rule": "pit_in_lap - 1, directly-ahead pair at the raw lap line",
        "public_position_available": False,
        "max_snapshot_age_s": MAX_SNAPSHOT_AGE_S,
        "max_pair_skew_s": MAX_PAIR_SKEW_S,
        "input_entries": len(source["rows"]),
        "unique_input_entries": len(candidates),
        "measured_entries": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "accuracy": accuracy,
        "rows": rows,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    accuracy = payload["accuracy"]
    lines = [
        "# Public pair-state accuracy before pit entry",
        "",
        "This is an offline state-quality measure for #724, the epic to make the deterministic decision layer able to prefer a stop.",
        "It compares the raw directly-ahead pair with public timing available before the approximate pit entry. It does not score strategy and does not change production.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- source: `{payload['source']}`",
        f"- cutoff: `{payload['cutoff_rule']}`",
        f"- raw reference: `{payload['raw_reference_rule']}`",
        f"- maximum snapshot age: **{payload['max_snapshot_age_s']:.0f} seconds**",
        f"- maximum pair timestamp skew: **{payload['max_pair_skew_s']:.0f} seconds**",
        f"- input entries: **{payload['input_entries']}**",
        f"- unique input events: **{payload['unique_input_entries']}**",
        f"- measured entries: **{payload['measured_entries']}**",
        "",
        "## Status",
        "",
        "| status | entries |",
        "| --- | ---: |",
    ]
    for status, count in payload["status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            "## Accuracy on comparable pairs",
            "",
            f"- comparable pairs: **{accuracy['entries']}**",
            f"- public pair keeps the raw order: **{accuracy['pair_order_accuracy']}**",
            f"- pair-order mismatches: **{accuracy['pair_order_mismatches']}**",
            f"- signed pair-gap error mean: **{accuracy['pair_gap_signed_mean_s']} seconds**",
            f"- absolute pair-gap error median / p90: **{accuracy['pair_gap_abs_median_s']} / {accuracy['pair_gap_abs_p90_s']} seconds**",
            "",
            "The OpenF1 interval cache has no official absolute position column, so absolute public position error is intentionally not reported. Sorting all cars by gap-to-leader would mix asynchronous updates and lapped states. This pair-level measure is the strongest factual comparison supported by the cached fields.",
            "",
            "## Decision",
            "",
            "Keep this separate from the retrospective rejoin benchmark and from relative-pace correlation. Do not add a traffic, rejoin, or tyre-value term to the production scorer from this measure alone.",
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
                "accuracy": payload["accuracy"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
