"""Export a review queue for the 2025 strategic-stop evidence phase.

The export keeps the existing 573-entry sample unchanged. It adds the manual
dispositions already documented for the 36 doubtful entries, exposes the 537
remaining rows, and attaches every penalty message for the same car and race.
It is a review aid, not a new ground-truth label and not a scorer input.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_stop_purpose.json"
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_724_strategy_evidence_review.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_724_strategy_evidence_review.md"

EXCLUDE_NON_COMPARABLE = "exclude_non_comparable"
EXCLUDE_PENALTY_ONLY = "exclude_penalty_only"
EXCLUDE_MIXED_PENALTY = "exclude_mixed_penalty"
RETAIN_REGULATION_CONSTRAINED = "retain_regulation_constrained"
RETAIN_EXTERNAL_CANDIDATE = "retain_external_candidate"


def _event_key(record: dict[str, Any]) -> tuple[str, str, int]:
    return str(record["race"]), str(record["driver_code"]), int(record["pit_in_lap"])


def _add_dispositions(
    target: dict[tuple[str, str, int], str],
    disposition: str,
    race: str,
    driver: str,
    laps: tuple[int, ...],
) -> None:
    for lap in laps:
        target[(race, driver, lap)] = disposition


def manual_dispositions() -> dict[tuple[str, str, int], str]:
    """Return the fixed review map from the 36-row external adjudication."""
    result: dict[tuple[str, str, int], str] = {}
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Barcelona", "ALB", (26, 27))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Budapest", "BEA", (48,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Las_Vegas", "ALB", (35,))
    _add_dispositions(result, EXCLUDE_PENALTY_ONLY, "Lusail", "BEA", (40, 41))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Lusail", "HAD", (55,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Lusail", "STR", (55,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Melbourne", "BOR", (44,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Mexico_City", "ALO", (34,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Mexico_City", "HAM", (23,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Mexico_City", "HUL", (25,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Mexico_City", "LAW", (5,))
    _add_dispositions(result, EXCLUDE_PENALTY_ONLY, "Mexico_City", "SAI", (56,))
    _add_dispositions(result, RETAIN_EXTERNAL_CANDIDATE, "Miami_Gardens", "BOR", (19,))
    _add_dispositions(result, RETAIN_EXTERNAL_CANDIDATE, "Miami_Gardens", "HAD", (22,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Miami_Gardens", "LAW", (36,))
    _add_dispositions(result, RETAIN_EXTERNAL_CANDIDATE, "Miami_Gardens", "STR", (20,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Monaco", "GAS", (8,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Monaco", "RUS", (53,))
    _add_dispositions(result, RETAIN_REGULATION_CONSTRAINED, "Monaco", "RUS", (62,))
    _add_dispositions(result, RETAIN_REGULATION_CONSTRAINED, "Monaco", "SAI", (53,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Montréal", "LAW", (54,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Montréal", "STR", (51,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Monza", "ALO", (24,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Sakhir", "NOR", (10,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Sakhir", "SAI", (44,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Sakhir", "SAI", (45,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Shanghai", "ALO", (4,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Silverstone", "ANT", (23,))
    _add_dispositions(result, RETAIN_EXTERNAL_CANDIDATE, "Spa-Francorchamps", "BEA", (12,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "Spielberg", "ALB", (15,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "São_Paulo", "HAM", (32,))
    _add_dispositions(result, EXCLUDE_NON_COMPARABLE, "São_Paulo", "HAM", (37,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Yas_Island", "LAW", (21,))
    _add_dispositions(result, EXCLUDE_MIXED_PENALTY, "Yas_Island", "TSU", (32,))
    return result


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _stable_order_key(row: dict[str, Any]) -> str:
    """Give an event a deterministic order that does not follow driver or lap names."""
    return hashlib.sha256(str(row["event_id"]).encode("utf-8")).hexdigest()


def _lap_phase(lap: int) -> str:
    """Group controls into broad race phases without introducing a new model field."""
    if lap <= 20:
        return "early"
    if lap <= 40:
        return "middle"
    return "late"


def _penalty_history(
    record: dict[str, Any], evidence_by_driver: dict[tuple[int, int], list[dict[str, Any]]]
) -> dict[str, Any]:
    driver_number = record.get("driver_number")
    if driver_number is None:
        return {"all_ids": [], "pre_entry_ids": [], "post_entry_ids": [], "unlinked_ids": []}

    items = evidence_by_driver.get((int(record["session_key"]), int(driver_number)), [])
    pit_time = _parse_time(record.get("pit_in_utc"))
    linked_ids = set(record.get("evidence_refs") or [])
    pre_entry_ids: list[str] = []
    post_entry_ids: list[str] = []
    all_ids: list[str] = []
    for item in items:
        evidence_id = str(item["evidence_id"])
        all_ids.append(evidence_id)
        event_time = _parse_time(item.get("date"))
        if pit_time is not None and event_time is not None and event_time <= pit_time:
            pre_entry_ids.append(evidence_id)
        else:
            post_entry_ids.append(evidence_id)
    return {
        "all_ids": all_ids,
        "pre_entry_ids": pre_entry_ids,
        "post_entry_ids": post_entry_ids,
        "unlinked_ids": [item for item in all_ids if item not in linked_ids],
    }


def _review_row(
    record: dict[str, Any],
    disposition: str | None,
    penalty_history: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": record["event_id"],
        "race": record["race"],
        "session_key": record["session_key"],
        "meeting_key": record["meeting_key"],
        "driver": record["driver_code"],
        "driver_number": record["driver_number"],
        "pit_in_lap": record["pit_in_lap"],
        "pit_sequence": record["pit_sequence"],
        "pit_in_session_s": record["pit_in_session_s"],
        "pit_in_utc": record["pit_in_utc"],
        "review_disposition": disposition or "unreviewed",
        "review_status": "reviewed" if disposition else "unreviewed",
        "primary_label": record["primary_label"],
        "comparison_cohort": record["comparison_cohort"],
        "neutralisation_state": record["neutralisation_state"],
        "telemetry_set_change": record["telemetry_set_change"],
        "source_conflict": record["source_conflict"],
        "timing_discretion": record["timing_discretion"],
        "timestamp_alignment": record["timestamp_alignment"],
        "penalty_history": penalty_history,
    }


def _stratified_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Select priority events plus up to 44 balanced controls, all unique by event_id."""
    unreviewed = [row for row in rows if row["review_status"] == "unreviewed"]
    priority = [
        row
        for row in unreviewed
        if row["penalty_history"]["unlinked_ids"]
        or row["race"] in {"Monaco", "Lusail"}
        or not row["pit_in_utc"]
    ]
    selected: dict[str, dict[str, Any]] = {row["event_id"]: row for row in priority}

    controls = [row for row in unreviewed if row["event_id"] not in selected]
    control_strata: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in controls:
        stratum = (
            str(row["race"]),
            str(row["comparison_cohort"]),
            str(row["neutralisation_state"]),
            str(row["pit_sequence"]),
            _lap_phase(int(row["pit_in_lap"])),
        )
        control_strata[stratum].append(row)

    chosen_controls: list[dict[str, Any]] = []
    for stratum in sorted(control_strata):
        row = min(control_strata[stratum], key=_stable_order_key)
        chosen_controls.append(row)
    if len(chosen_controls) < 44:
        for row in sorted(controls, key=_stable_order_key):
            if row not in chosen_controls:
                chosen_controls.append(row)
            if len(chosen_controls) == 44:
                break
    for row in chosen_controls[:44]:
        selected[row["event_id"]] = row
    return sorted(selected.values(), key=_stable_order_key)


def build_export(source: dict[str, Any]) -> dict[str, Any]:
    records = [record for record in source["records"] if record["in_715_sample"]]
    dispositions = manual_dispositions()
    assert len(dispositions) == 36
    record_keys = {_event_key(record) for record in records}
    assert dispositions.keys() <= record_keys

    evidence_by_driver: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for item in source["evidence"]:
        if item["penalty_type"] == "unknown":
            continue
        for driver_number in item["car_numbers"]:
            evidence_by_driver[(int(item["session_key"]), int(driver_number))].append(item)

    rows = [
        _review_row(
            record,
            dispositions.get(_event_key(record)),
            _penalty_history(record, evidence_by_driver),
        )
        for record in records
    ]
    assert len({row["event_id"] for row in rows}) == len(rows)
    status_counts = Counter(row["review_disposition"] for row in rows)
    assert sum(status_counts.values()) == 573
    assert status_counts["unreviewed"] == 537
    sample = _stratified_sample(rows)
    unlinked = [row for row in rows if row["penalty_history"]["unlinked_ids"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": 2025,
        "source": str(INPUT_JSON.relative_to(ROOT)),
        "window_laps": 5,
        "decision_window_laps": 5,
        "sample_entries": len(rows),
        "reviewed_entries": sum(row["review_status"] == "reviewed" for row in rows),
        "unreviewed_entries": sum(row["review_status"] == "unreviewed" for row in rows),
        "disposition_counts": dict(sorted(status_counts.items())),
        "unlinked_penalty_rows": len(unlinked),
        "stratified_sample_entries": len(sample),
        "stratified_unique_event_ids": len({row["event_id"] for row in sample}),
        "priority_review_entries": len(
            [
                row
                for row in sample
                if row["penalty_history"]["unlinked_ids"]
                or row["race"] in {"Monaco", "Lusail"}
                or not row["pit_in_utc"]
            ]
        ),
        "control_review_entries": len(sample)
        - len(
            [
                row
                for row in sample
                if row["penalty_history"]["unlinked_ids"]
                or row["race"] in {"Monaco", "Lusail"}
                or not row["pit_in_utc"]
            ]
        ),
        "rows": rows,
        "stratified_sample": sample,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 2025 strategy-evidence review export",
        "",
        "This export is a review queue for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.",
        "It keeps the existing #715 sample, the missed-pit-call diagnostic population, unchanged and does not feed any field into the scorer.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- source: `{payload['source']}`",
        f"- `WINDOW_LAPS`: `{payload['window_laps']}`",
        f"- `DECISION_WINDOW_LAPS`: `{payload['decision_window_laps']}`",
        f"- sample entries: **{payload['sample_entries']}**",
        f"- reviewed entries: **{payload['reviewed_entries']}**",
        f"- unreviewed entries: **{payload['unreviewed_entries']}**",
        f"- rows with unlinked penalty history: **{payload['unlinked_penalty_rows']}**",
        f"- deterministic stratified sample: **{payload['stratified_sample_entries']}**",
        f"- unique event IDs in review sample: **{payload['stratified_unique_event_ids']}**",
        f"- priority events: **{payload['priority_review_entries']}**",
        f"- control events: **{payload['control_review_entries']}**",
        "",
        "## Review dispositions",
        "",
        "| disposition | entries |",
        "| --- | ---: |",
    ]
    for disposition, count in payload["disposition_counts"].items():
        lines.append(f"| `{disposition}` | {count} |")
    lines.extend(
        [
            "",
            "The 36 manually reviewed entries come from the external review in `REVIEW_1215_doubtful_cases.md`.",
            "The remaining 537 entries stay unreviewed even when their current primary label says `STRATEGIC_TYRE_CHANGE`.",
            "A tyre transition is evidence that a set changed, not proof that the timing was an elective strategic decision.",
            "",
            "## How to use the export",
            "",
            "The JSON contains one row per source event with its stable `event_id`, current evidence fields, all penalty evidence for the same car and session, and the IDs that were not attached by the current stop join.",
            "The review sample first includes every unreviewed event with unlinked penalty history, a Monaco or Lusail entry, or no UTC anchor. It then adds up to 44 deterministic controls from the other races, balancing cohort, neutralisation, stop sequence, and race phase. Event IDs are unique and selection uses a stable hash rather than lexical driver or lap order.",
            "",
            "Penalty timestamps use the existing approximate OpenF1 lap anchor when available. A pre-entry timestamp is evidence that race control had published the message before the reconstructed entry, not proof that the team had chosen that stop.",
            "",
            "## Next measurement",
            "",
            "Review the flagged penalty-history rows and the stratified sample manually. Then compare zero-cost relative pace with public timing estimates using the same pre-entry cutoff. Keep the retrospective rejoin benchmark separate from this decision-evidence measure.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    source = json.loads(INPUT_JSON.read_text(encoding="utf-8"))
    payload = build_export(source)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    OUTPUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(OUTPUT_MD)
    print(
        json.dumps(
            {
                key: payload[key]
                for key in (
                    "sample_entries",
                    "reviewed_entries",
                    "unreviewed_entries",
                    "disposition_counts",
                    "unlinked_penalty_rows",
                    "stratified_sample_entries",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
