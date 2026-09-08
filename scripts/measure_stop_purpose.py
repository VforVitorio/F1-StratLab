"""Build the 2025 pit-entry purpose evidence inventory.

This is an evaluation artifact for epic #724. It uses local 2025 data only,
does not call an LLM or change the production scorer, and keeps uncertain
entries visible instead of turning them into strategic-stop ground truth.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.data_extraction.openf1.radio_dataset_builder import OPENF1_BASE, build_retry_session
from src.f1_strat_manager.rcm_events import RCMEvent, classify_rcm_event
from src.f1_strat_manager.tyre_stint_repair import repair_tyre_stints
from src.strategy.eval.decision_modes import SAMPLED_RACES
from src.strategy.eval.stop_purpose import build_stop_purpose_records, parse_rcm_message

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw" / "2025"
RCM_ROOT = ROOT / "data" / "processed" / "race_radios" / "2025"
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_stop_purpose.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_724_stop_purpose.md"
ANCHOR_ROOT = ROOT / "data" / "processed" / "stop_purpose" / "2025" / "openf1_laps"
RCM_ANCHOR_ROOT = ROOT / "data" / "processed" / "stop_purpose" / "2025" / "openf1_rcm"


def _openf1_laps(session: Any, session_key: int) -> pd.DataFrame:
    """Read one cached OpenF1 lap index, fetching it once when absent."""
    path = ANCHOR_ROOT / f"{session_key}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        response = session.get(
            f"{OPENF1_BASE}/laps",
            params={"session_key": session_key},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        ANCHOR_ROOT.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return pd.DataFrame(payload)


def _openf1_rcm(session: Any, session_key: int) -> pd.DataFrame:
    """Read one complete OpenF1 race-control index, fetching it when absent."""
    path = RCM_ANCHOR_ROOT / f"{session_key}.json"
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        response = session.get(
            f"{OPENF1_BASE}/race_control",
            params={"session_key": session_key},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        RCM_ANCHOR_ROOT.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return pd.DataFrame(payload)


def _sample_stops(laps: pd.DataFrame) -> set[tuple[str, int]]:
    """Reuse the existing green-flag sample definition instead of copying it."""
    from src.strategy.eval.projection import _neutralised_laps, green_flag_stops

    return {
        (str(driver), int(lap))
        for driver, stop_laps in green_flag_stops(laps, _neutralised_laps(laps)).items()
        for lap in stop_laps
    }


def _rcm_by_session() -> tuple[dict[int, pd.DataFrame], int]:
    """Load the local RCM mirrors keyed by their OpenF1 session key."""
    by_session: dict[int, pd.DataFrame] = {}
    total = 0
    for path in sorted(RCM_ROOT.glob("*/rcm.parquet")):
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        session_key = int(frame["session_key"].iloc[0])
        by_session[session_key] = frame
        total += len(frame)
    return by_session, total


def _summary(records: list[Any]) -> dict[str, Any]:
    def counts(attribute: str) -> dict[str, int]:
        return dict(sorted(Counter(getattr(record, attribute) for record in records).items()))

    return {
        "pit_entries": len(records),
        "in_715_sample": sum(record.in_715_sample for record in records),
        "labels": counts("primary_label"),
        "cohorts": counts("comparison_cohort"),
        "telemetry_set_change": counts("telemetry_set_change"),
        "tyre_change_resolved": counts("tyre_change_resolved"),
        "evidence_level": counts("evidence_level"),
        "evidence_timing": counts("evidence_timing"),
        "timestamp_alignment": counts("timestamp_alignment"),
        "pit_out_pair_status": counts("pit_out_pair_status"),
        "mixed_purpose": sum(record.mixed_purpose for record in records),
        "source_conflicts": sum(record.source_conflict for record in records),
        "decision_comparable": sum(record.decision_comparable for record in records),
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    labels = summary["labels"]
    telemetry = summary["telemetry_set_change"]
    lines = [
        "# 2025 pit-entry purpose evidence",
        "",
        "This is a retrospective evidence inventory for the decision-layer work.",
        "It does not change the scorer and it does not treat the team's observed",
        "pit entry as proof that the team's decision was optimal.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- races: {payload['races']}",
        f"- RAW lap rows: {payload['raw_lap_rows']}",
        f"- PitInTime entries: {summary['pit_entries']}",
        f"- entries in the current missed-pit-call green sample: {summary['in_715_sample']}",
        f"- complete OpenF1 RCM rows: {payload['rcm_rows']}",
        f"- filtered local RCM rows: {payload['local_rcm_rows']}",
        f"- messages containing `PENALTY`: {payload['penalty_messages']}",
        f"- penalty-text messages classified as generic collisions: {payload['penalty_as_collision']}",
        f"- non-null `LapStartDate` rows: {payload['lap_start_date_nonnull']}",
        f"- tyre metadata repair: {payload['repair']['races_changed']} races, "
        f"{payload['repair']['tyre_life_nulled']} ages made unknown",
        f"- OpenF1 lap-anchor sessions: {payload['anchor_sessions']} "
        f"({payload['anchor_rows']} rows, cached)",
        "- LLM and private telemetry calls: none",
        "",
        "## What the local evidence says",
        "",
        "| primary label | entries |",
        "| --- | ---: |",
    ]
    lines.extend(f"| `{label}` | {count} |" for label, count in labels.items())
    lines.extend(
        [
            "",
            "| telemetry set-change signal | entries |",
            "| --- | ---: |",
        ]
    )
    lines.extend(f"| `{label}` | {count} |" for label, count in telemetry.items())
    lines.extend(
        [
            "",
            f"The current data shows {telemetry.get('confirmed', 0)} entries with a",
            "telemetry set-change signal (compound change or age reset) after the pit",
            "entry, but that is only telemetry evidence. It does not prove the entry was",
            "strategic. Same-compound entries can mount a used set, and a drive-through",
            "can leave contradictory stint metadata.",
            "",
            "## Measurement contract",
            "",
            "Each entry receives one primary label and keeps secondary causes, evidence IDs,",
            "timing discretion, source conflicts, and whether it belongs to the current",
            "green-flag sample. The clean comparison cohort is intentionally conservative:",
            "strategic candidate, no mixed purpose, no source conflict, and a discretionary",
            "timing decision. Entries with unknown timing discretion remain candidates for",
            "review, not confirmed ground truth.",
            "",
            "## Limitations that remain visible",
            "",
            "- The local RCM parquet is the filtered runtime mirror; the complete pass uses",
            "  cached OpenF1 race-control rows and keeps the local mirror only for coverage",
            "  comparison.",
            "- RAW `LapStartDate` is empty. OpenF1 lap starts reconstruct UTC for the",
            f"  {summary['timestamp_alignment'].get('exact_openf1_lap', 0)}/{summary['pit_entries']} entries;",
            "  the remaining entries stay explicitly unanchored and are not silently",
            "  approximated.",
            "- Absence of a local message means no evidence in this corpus, not no penalty.",
            "- The classifier's generic event category is not a sanction ledger; a future",
            "  parser must preserve awarded, served, cancelled, investigated, and unresolved",
            "  states separately.",
            "",
            "## Adjudication check",
            "",
            "Monaco 2025 Russell is deliberately retained as a conflict: local telemetry",
            "shows a compound transition on lap 53, while the official race-control record",
            "announces a drive-through and the official pit summary lists entries on laps 53,",
            "62, and 68. The inventory therefore labels lap 53 as `PENALTY_SERVICE` with",
            "`source_conflict=true`; it does not silently trust the tyre columns. Sources:",
            "[FIA decision](https://www.fia.com/system/files/decision-document/2025_monaco_grand_prix_-_infringement_-_car_63_-_leaving_the_track_and_gaining_an_advantage.pdf),",
            "[race-control messages](https://api.fia.com/sites/default/files/2025_08_mon_f1_r0_timing_raceracecontrolmessages_v01.pdf),",
            "and [pit-stop summary](https://www.fia.com/sites/default/files/2025_08_mon_f1_r0_timing_racepitstopsummary_v01.pdf).",
            "",
            "## Decision",
            "",
            "Do not connect these labels to the production scorer yet. The complete",
            "2025 OpenF1 race-control pass is now cached. The next required step is",
            "manual adjudication of penalties, conflicts, mixed-purpose entries, and a",
            "stratified sample of strategic candidates before recalculating the no-call",
            "denominator.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if not RAW_ROOT.is_dir():
        raise FileNotFoundError(f"2025 raw data is missing: {RAW_ROOT}")

    _local_rcm_by_session, local_rcm_rows = _rcm_by_session()
    http = build_retry_session()
    complete_rcm_by_session: dict[int, pd.DataFrame] = {}
    records = []
    raw_lap_rows = 0
    lap_start_date_nonnull = 0
    races = 0
    repair_counts: Counter[str] = Counter()
    anchor_sessions: set[int] = set()
    anchor_rows = 0
    for year, race in SAMPLED_RACES:
        if year != 2025:
            continue
        race_dir = RAW_ROOT / race
        raw_laps = pd.read_parquet(race_dir / "laps.parquet")
        laps, repair_report = repair_tyre_stints(raw_laps)
        metadata = json.loads((race_dir / "metadata.json").read_text(encoding="utf-8"))
        session_key = int(metadata["session_key_openf1"])
        rcm = _openf1_rcm(http, session_key)
        openf1_laps = _openf1_laps(http, session_key)
        complete_rcm_by_session[session_key] = rcm
        anchor_sessions.add(session_key)
        anchor_rows += len(openf1_laps)
        meeting_key = None if rcm.empty else int(rcm["meeting_key"].iloc[0])
        sample = _sample_stops(raw_laps)
        records.extend(
            build_stop_purpose_records(
                laps,
                rcm,
                year=2025,
                race=race,
                session_key=session_key,
                meeting_key=meeting_key,
                sample_stops=sample,
                raw_laps=raw_laps,
                repair_applied=repair_report.changed_anything,
                openf1_laps=openf1_laps,
            )
        )
        races += 1
        raw_lap_rows += len(raw_laps)
        if "LapStartDate" in raw_laps:
            lap_start_date_nonnull += int(raw_laps["LapStartDate"].notna().sum())
        repair_counts["races_changed"] += int(repair_report.changed_anything)
        repair_counts["tyre_life_nulled"] += (
            repair_report.fabricated_ages_nulled + repair_report.republished_ages_nulled
        )

    summary = _summary(records)
    penalty_messages = 0
    penalty_as_collision = 0
    evidence: dict[str, dict[str, Any]] = {}
    for frame in complete_rcm_by_session.values():
        penalty_messages += int(
            frame["message"].astype(str).str.contains("PENALTY", case=False).sum()
        )
        for _, row in frame.iterrows():
            if "PENALTY" in str(row.get("message", "")).upper():
                structured_number = row.get("driver_number")
                driver_number = None if pd.isna(structured_number) else str(int(structured_number))
                classified = classify_rcm_event(
                    RCMEvent(
                        message=str(row.get("message", "")),
                        flag=str(row.get("flag", "") or ""),
                        category=str(row.get("category", "") or ""),
                        lap=int(row.get("lap_number", 0) or 0),
                        racing_number=driver_number,
                        scope=str(row.get("scope", "") or ""),
                    )
                )
                penalty_as_collision += classified == "CAR_COLLISION"
            parsed = parse_rcm_message(row)
            if parsed is not None:
                evidence[parsed.evidence_id] = {
                    "evidence_id": parsed.evidence_id,
                    "session_key": parsed.session_key,
                    "rcm_lap": parsed.rcm_lap,
                    "date": parsed.date,
                    "message": parsed.message,
                    "car_numbers": list(parsed.car_numbers),
                    "penalty_type": parsed.penalty_type,
                    "phase": parsed.phase,
                    "forced_entry": parsed.forced_entry,
                }

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": 2025,
        "races": races,
        "raw_lap_rows": raw_lap_rows,
        "rcm_rows": sum(len(frame) for frame in complete_rcm_by_session.values()),
        "local_rcm_rows": local_rcm_rows,
        "anchor_sessions": len(anchor_sessions),
        "anchor_rows": anchor_rows,
        "penalty_messages": penalty_messages,
        "penalty_as_collision": penalty_as_collision,
        "lap_start_date_nonnull": lap_start_date_nonnull,
        "repair": dict(repair_counts),
        "summary": summary,
        "evidence": sorted(evidence.values(), key=lambda item: item["evidence_id"]),
        "records": [record.as_dict() for record in records],
    }
    assert len(records) == 841, f"unexpected 2025 PitInTime population: {len(records)}"
    assert summary["in_715_sample"] == 573, (
        f"the current green-flag definition changed: {summary['in_715_sample']}"
    )
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(OUTPUT_MD)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
