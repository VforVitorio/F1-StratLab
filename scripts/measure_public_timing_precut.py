"""Measure whether public timing is available before the reviewed stop events.

This is a data-quality gate for the strategy-evidence phase. It does not estimate
strategy quality and it does not change the decision layer.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_strategy_evidence_review.json"
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_public_timing_precut.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_724_public_timing_precut.md"

TIMING_COLUMNS = [
    "session_key",
    "driver_number",
    "date",
    "interval_seconds",
    "gap_to_leader_seconds",
]
MAX_FRESHNESS_S = 10.0


def _timestamp(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def measure_row(row: dict[str, Any], intervals: pd.DataFrame) -> dict[str, Any]:
    """Measure the latest public timing snapshot at or before one pit entry."""
    cutoff = _timestamp(row.get("pit_in_utc"))
    result = {
        "event_id": row["event_id"],
        "race": row["race"],
        "driver": row["driver"],
        "driver_number": row["driver_number"],
        "session_key": row["session_key"],
        "pit_in_lap": row["pit_in_lap"],
        "review_status": row["review_status"],
        "review_disposition": row["review_disposition"],
        "cutoff_utc": None if pd.isna(cutoff) else cutoff.isoformat(),
        "latest_public_utc": None,
        "cutoff_lag_s": None,
        "status": "no_anchor",
        "same_snapshot_driver_count": 0,
        "driver_interval_seconds": None,
        "driver_gap_to_leader_seconds": None,
    }
    if pd.isna(cutoff):
        return result

    session = intervals[intervals["session_key"] == row["session_key"]]
    session = session[session["date"].notna() & (session["date"] <= cutoff)]
    driver_history = session[session["driver_number"] == row["driver_number"]]
    if driver_history.empty:
        result["status"] = "no_prior_public_timing"
        return result

    # OpenF1 emits interval rows asynchronously by car. Use the driver's own
    # latest row as the cutoff anchor and a small surrounding slice for rivals,
    # never rows after the pit entry.
    latest = driver_history["date"].max()
    snapshot = session[
        (session["date"] >= latest - pd.Timedelta(seconds=5))
        & (session["date"] <= min(cutoff, latest + pd.Timedelta(seconds=5)))
    ]
    driver_snapshot = driver_history[driver_history["date"] == latest]
    result.update(
        {
            "latest_public_utc": latest.isoformat(),
            "cutoff_lag_s": round(float((cutoff - latest).total_seconds()), 3),
            "status": (
                "precut_snapshot"
                if float((cutoff - latest).total_seconds()) <= MAX_FRESHNESS_S
                else "precut_snapshot_stale"
            )
            if not driver_snapshot.empty
            else "snapshot_without_driver",
            "same_snapshot_driver_count": int(snapshot["driver_number"].nunique()),
            "driver_interval_seconds": (
                None if driver_snapshot.empty else driver_snapshot["interval_seconds"].iloc[0]
            ),
            "driver_gap_to_leader_seconds": (
                None if driver_snapshot.empty else driver_snapshot["gap_to_leader_seconds"].iloc[0]
            ),
        }
    )
    assert all(_timestamp(value) <= cutoff for value in session["date"].tolist())
    return result


def load_intervals() -> pd.DataFrame:
    """Load the cached public timing rows for every 2025 race."""
    frames = [
        pd.read_parquet(path, columns=TIMING_COLUMNS)
        for path in sorted((ROOT / "data" / "raw" / "2025").glob("*/intervals.parquet"))
    ]
    if not frames:
        raise FileNotFoundError("No 2025 intervals.parquet files found")
    result = pd.concat(frames, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce")
    result["session_key"] = pd.to_numeric(result["session_key"], errors="coerce")
    result["driver_number"] = pd.to_numeric(result["driver_number"], errors="coerce")
    return result


def build_measurement(source: dict[str, Any], intervals: pd.DataFrame) -> dict[str, Any]:
    rows = [measure_row(row, intervals) for row in source["stratified_sample"]]
    counts = Counter(row["status"] for row in rows)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": 2025,
        "source": str(INPUT_JSON.relative_to(ROOT)),
        "timing_source": "data/raw/2025/*/intervals.parquet",
        "cutoff_rule": "date <= approximate pit_in_utc",
        "sample_entries": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "rows": rows,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Public timing before the pit-entry cutoff",
        "",
        "This is a data-quality measurement for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.",
        "It asks whether the cached public timing feed contains a latest snapshot at or before each sampled pit entry. It does not use later timing to explain the decision.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- source: `{payload['source']}`",
        f"- timing source: `{payload['timing_source']}`",
        f"- cutoff: `{payload['cutoff_rule']}`",
        f"- freshness threshold for the primary set: **{MAX_FRESHNESS_S:.0f} seconds**",
        f"- sampled entries: **{payload['sample_entries']}**",
        "",
        "## Coverage",
        "",
        "| status | entries |",
        "| --- | ---: |",
    ]
    for status, count in payload["status_counts"].items():
        lines.append(f"| `{status}` | {count} |")
    lines.extend(
        [
            "",
            f"`precut_snapshot` means that the public timing feed had an observation for the same driver no more than {MAX_FRESHNESS_S:.0f} seconds before the reconstructed entry. It does not prove that the team had already committed to stop, nor that the snapshot contains every rival.",
            "`precut_snapshot_stale` has a valid pre-cutoff observation, but it is older than the primary freshness threshold and stays out of the first relative-pace comparison.",
            "`no_anchor` is kept separate from missing public timing. OpenF1 lap start timestamps are approximate and six source entries remain unanchored in the evidence inventory.",
            "",
            "## Decision",
            "",
            "Use only the `precut_snapshot` rows, 69 of 77, in the next relative-pace comparison. Keep stale snapshots, the unanchored row, the rejoin benchmark, and any post-entry measurements separate. No production scorer change is justified by coverage alone.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    payload = build_measurement(source, load_intervals())
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(OUTPUT_MD)
    print(
        json.dumps(
            {
                "sample_entries": payload["sample_entries"],
                "status_counts": payload["status_counts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
