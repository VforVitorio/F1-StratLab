"""Retrospective 2025 pit-entry purpose evidence for the decision-layer audit.

``PitInTime`` proves that a car entered the pit lane. It does not prove a tyre
change, a strategic choice, or a penalty service. This module keeps those facts
separate and deliberately leaves unresolved cases visible for review.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from src.f1_strat_manager.rcm_events import RCMEvent, extract_car_numbers, parse_penalty_event

PENALTY_SERVICE = "PENALTY_SERVICE"
REGULATION_REQUIRED_STOP = "REGULATION_REQUIRED_STOP"
STRATEGIC_TYRE_CHANGE = "STRATEGIC_TYRE_CHANGE"
DAMAGE_MECHANICAL_OTHER = "DAMAGE_MECHANICAL_OTHER"
UNKNOWN = "UNKNOWN"

_RELEVANT_TERMS = (
    "PENALTY",
    "PIT LANE",
    "THROUGH THE PIT",
    "DAMAGE",
    "PUNCTURE",
    "MECHANICAL",
    "RETIRED",
    "UNDER INVESTIGATION",
    "NO FURTHER INVESTIGATION",
)


@dataclass(frozen=True)
class RCMEvidence:
    """One relevant race-control message, retaining raw text and provenance."""

    evidence_id: str
    session_key: int | None
    rcm_lap: int | None
    date: str | None
    message: str
    car_numbers: tuple[int, ...]
    penalty_type: str
    phase: str
    forced_entry: bool


@dataclass(frozen=True)
class PenaltyLifecycle:
    """One penalty state sequence and its conservative pit-entry candidates."""

    penalty_id: str
    session_key: int | None
    driver_number: int
    penalty_type: str
    awarded_evidence_id: str
    served_evidence_id: str | None
    candidate_event_ids: tuple[str, ...]
    status: str
    review_note: str


@dataclass(frozen=True)
class StopPurposeRecord:
    """One observed pit entry and the evidence currently attached to it."""

    event_id: str
    year: int
    session_key: int
    meeting_key: int | None
    race: str
    driver_number: int | None
    driver_code: str
    pit_sequence: int
    pit_in_lap: int
    pit_out_lap: int | None
    pit_in_session_s: float | None
    pit_out_session_s: float | None
    pit_in_utc: str | None
    pit_out_utc: str | None
    openf1_lap_date_start_utc: str | None
    intra_lap_offset_s: float | None
    anchor_source: str | None
    anchor_precision: str | None
    timestamp_alignment: str
    pit_out_pair_status: str
    neutralisation_state: str
    raw_compound_in: str | None
    raw_compound_out: str | None
    raw_tyre_life_in: float | None
    raw_tyre_life_out: float | None
    raw_stint_in: float | None
    raw_stint_out: float | None
    repaired_compound_in: str | None
    repaired_compound_out: str | None
    repaired_tyre_life_in: float | None
    repaired_tyre_life_out: float | None
    repaired_stint_in: float | None
    repaired_stint_out: float | None
    repair_applied: bool
    telemetry_set_change: str
    tyre_change_resolved: str
    source_conflict: bool
    primary_label: str
    secondary_label: str | None
    penalty_type: str
    penalty_served: str
    regulation_constraint: str
    timing_discretion: str
    decision_comparable: bool
    mixed_purpose: bool
    evidence_level: str
    evidence_timing: str
    evidence_refs: tuple[str, ...]
    in_715_sample: bool
    comparison_cohort: str
    review_note: str

    def as_dict(self) -> dict[str, Any]:
        """Return JSON-safe fields for the committed audit artifact."""
        return asdict(self)


def _text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _lap(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _seconds(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timedelta):
        return round(value.total_seconds(), 6)
    return _number(value)


def _openf1_lap_starts(openf1_laps: pd.DataFrame | None) -> dict[tuple[int, int], pd.Timestamp]:
    """Index OpenF1 lap starts by car and lap for temporal event anchoring."""
    if openf1_laps is None or openf1_laps.empty:
        return {}
    starts: dict[tuple[int, int], pd.Timestamp] = {}
    for _, row in openf1_laps.iterrows():
        driver = _driver_number(row.get("driver_number"))
        lap = _lap(row.get("lap_number"))
        if driver is None or lap is None:
            continue
        start = pd.to_datetime(row.get("date_start"), utc=True, errors="coerce")
        if pd.notna(start):
            starts[(driver, lap)] = start
    return starts


def _event_utc(
    row: Any, column: str, lap_starts: dict[tuple[int, int], pd.Timestamp]
) -> tuple[str | None, str | None, float | None]:
    """Convert a session-relative event and retain its approximate anchor."""
    driver = _driver_number(row.get("DriverNumber"))
    lap = _lap(row.get("LapNumber"))
    event_s = _seconds(row.get(column))
    lap_start_s = _seconds(row.get("LapStartTime"))
    lap_start = None if driver is None or lap is None else lap_starts.get((driver, lap))
    if lap_start is None or event_s is None or lap_start_s is None:
        return None, None, None
    offset_s = round(event_s - lap_start_s, 6)
    return (
        (lap_start + pd.to_timedelta(offset_s, unit="s")).isoformat(),
        lap_start.isoformat(),
        offset_s,
    )


def _same_text(value: Any) -> str | None:
    result = _text(value).upper()
    return result or None


def _driver_number(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(number)


def _message_id(session_key: int | None, date: Any, message: str) -> str:
    raw = f"{session_key}|{_text(date)}|{message}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def parse_rcm_message(row: Any) -> RCMEvidence | None:
    """Parse one RCM row when it can inform stop-purpose classification."""
    message = _text(row.get("message"))
    upper = message.upper()
    if not message or not any(term in upper for term in _RELEVANT_TERMS):
        return None
    session_key = _driver_number(row.get("session_key"))
    rcm_lap = _lap(row.get("lap_number"))
    event = RCMEvent(
        message=message,
        flag=_text(row.get("flag")),
        category=_text(row.get("category")),
        lap=rcm_lap or 0,
        racing_number=_text(row.get("driver_number")) or None,
        scope=_text(row.get("scope")),
    )
    penalty = parse_penalty_event(event)
    penalty_type = "unknown" if penalty is None else penalty.penalty_type
    phase = "unknown" if penalty is None else penalty.phase
    car_numbers = extract_car_numbers(event)
    forced_entry = "THROUGH THE PIT" in upper or "MUST ENTER THE PIT LANE" in upper
    return RCMEvidence(
        evidence_id=_message_id(session_key, row.get("date"), message),
        session_key=session_key,
        rcm_lap=rcm_lap,
        date=None if pd.isna(row.get("date")) else str(row.get("date")),
        message=message,
        car_numbers=car_numbers,
        penalty_type=penalty_type,
        phase=phase,
        forced_entry=forced_entry,
    )


def _driver_code(row: Any) -> str:
    return _text(row.get("Driver")) or f"CAR_{_text(row.get('DriverNumber'))}"


def _neutralisation_state(value: Any) -> str:
    status = _text(value)
    if "5" in status:
        return "red"
    if "4" in status:
        return "sc"
    if "6" in status or "7" in status:
        return "vsc"
    return "green"


def _next_out_row(group: pd.DataFrame, pit_lap: int) -> Any | None:
    candidates = group[group["LapNumber"].map(_lap).fillna(-1) > pit_lap]
    if "PitOutTime" not in candidates:
        return None
    candidates = candidates[candidates["PitOutTime"].notna()]
    if candidates.empty:
        return None
    return candidates.sort_values("LapNumber").iloc[0]


def _telemetry_change(pit_row: Any, out_row: Any | None) -> tuple[str, str]:
    if out_row is None:
        return "unknown", "unknown"
    compound_in = _same_text(pit_row.get("Compound"))
    compound_out = _same_text(out_row.get("Compound"))
    if compound_in and compound_out and compound_in != compound_out:
        return "confirmed", "true"
    life_in = _number(pit_row.get("TyreLife"))
    life_out = _number(out_row.get("TyreLife"))
    stint_in = _number(pit_row.get("Stint"))
    stint_out = _number(out_row.get("Stint"))
    if (
        compound_in
        and compound_out
        and compound_in == compound_out
        and life_in is not None
        and life_out is not None
        and abs(life_out - life_in - 1) < 0.01
        and stint_in == stint_out
    ):
        return "none_observed", "false"
    if (
        compound_in
        and compound_out
        and life_in is not None
        and life_out is not None
        and life_out < life_in
    ):
        return "confirmed", "true"
    return "unknown", "unknown"


def _linked_evidence(
    evidence: Iterable[RCMEvidence],
    driver_number: int | None,
    pit_lap: int,
    pit_in_utc: str | None,
) -> list[RCMEvidence]:
    pit_timestamp = pd.to_datetime(pit_in_utc, utc=True, errors="coerce")
    linked: list[RCMEvidence] = []
    for item in evidence:
        targeted = driver_number is not None and driver_number in item.car_numbers
        if not targeted and not (
            not item.car_numbers and item.forced_entry and item.rcm_lap == pit_lap
        ):
            continue
        if item.phase == "served":
            if item.rcm_lap == pit_lap:
                linked.append(item)
            elif pit_timestamp is not None:
                evidence_timestamp = pd.to_datetime(item.date, utc=True, errors="coerce")
                if (
                    pd.notna(evidence_timestamp)
                    and abs((evidence_timestamp - pit_timestamp).total_seconds()) <= 60
                ):
                    linked.append(item)
            continue
        evidence_timestamp = pd.to_datetime(item.date, utc=True, errors="coerce")
        if pd.notna(pit_timestamp) and pd.notna(evidence_timestamp):
            delta_s = abs((evidence_timestamp - pit_timestamp).total_seconds())
            if delta_s <= 900:
                linked.append(item)
        elif item.rcm_lap is None or abs(item.rcm_lap - pit_lap) <= 8:
            linked.append(item)
    return linked


def _penalty_link(
    evidence: Iterable[RCMEvidence], pit_lap: int, pit_in_utc: str | None
) -> RCMEvidence | None:
    pit_timestamp = pd.to_datetime(pit_in_utc, utc=True, errors="coerce")
    candidates = []
    for item in evidence:
        if item.penalty_type == "unknown" or item.rcm_lap is None:
            continue
        evidence_timestamp = pd.to_datetime(item.date, utc=True, errors="coerce")
        if pd.notna(pit_timestamp) and pd.notna(evidence_timestamp):
            delta_s = (pit_timestamp - evidence_timestamp).total_seconds()
            matches = -900 <= delta_s <= 900 if item.phase == "served" else 0 <= delta_s <= 900
        elif item.phase == "served":
            matches = item.rcm_lap == pit_lap
        else:
            matches = False
        if matches:
            candidates.append(item)
        elif (
            pd.isna(pit_timestamp)
            and item.phase == "awarded"
            and (
                (item.penalty_type in {"drive_through", "stop_go"} and item.rcm_lap == pit_lap)
                or (
                    item.penalty_type in {"5s", "10s", "other"} and 0 <= pit_lap - item.rcm_lap <= 8
                )
            )
        ):
            candidates.append(item)
    return min(candidates, key=lambda item: abs((item.rcm_lap or pit_lap) - pit_lap), default=None)


def _has_damage(evidence: Iterable[RCMEvidence], pit_lap: int) -> bool:
    terms = ("DAMAGE", "PUNCTURE", "MECHANICAL", "REPAIR", "RETIRED")
    return any(
        any(term in item.message.upper() for term in terms)
        and item.rcm_lap is not None
        and abs(item.rcm_lap - pit_lap) <= 1
        for item in evidence
    )


def _evidence_timing(evidence: Iterable[RCMEvidence], pit_lap: int, pit_in_utc: str | None) -> str:
    pit_timestamp = pd.to_datetime(pit_in_utc, utc=True, errors="coerce")
    if pd.notna(pit_timestamp):
        before = any(
            pd.notna(pd.to_datetime(item.date, utc=True, errors="coerce"))
            and pd.to_datetime(item.date, utc=True) < pit_timestamp
            for item in evidence
        )
        after = any(
            pd.notna(pd.to_datetime(item.date, utc=True, errors="coerce"))
            and pd.to_datetime(item.date, utc=True) > pit_timestamp
            for item in evidence
        )
    else:
        before = any(item.rcm_lap is not None and item.rcm_lap < pit_lap for item in evidence)
        after = any(item.rcm_lap is not None and item.rcm_lap > pit_lap for item in evidence)
    if before and after:
        return "both"
    if after:
        return "post_entry_only"
    if before:
        return "pre_entry"
    return "unknown"


def _timestamp(value: str | None) -> pd.Timestamp:
    return pd.to_datetime(value, utc=True, errors="coerce")


def _penalty_reason(message: str) -> str:
    """Return the official reason suffix used to distinguish repeated penalties."""
    normalised = " ".join(message.upper().split())
    match = re.search(r"\bFOR CAR\s+\d+\s*(?:\([^)]+\))?\s*-\s*(.+)$", normalised)
    return "" if match is None else match.group(1).strip(" .")


def build_penalty_lifecycle(
    records: Iterable[StopPurposeRecord], evidence: Iterable[RCMEvidence]
) -> list[PenaltyLifecycle]:
    """Pair penalty announcements with confirmations without guessing a stop."""
    records_by_driver: dict[tuple[int | None, int], list[StopPurposeRecord]] = {}
    for record in records:
        records_by_driver.setdefault((record.session_key, record.driver_number), []).append(record)

    grouped: dict[tuple[int | None, int, str], dict[str, list[RCMEvidence]]] = {}
    for item in evidence:
        if item.penalty_type == "unknown" or not item.car_numbers:
            continue
        for driver_number in item.car_numbers:
            key = (item.session_key, driver_number, item.penalty_type)
            grouped.setdefault(key, {"awarded": [], "served": []})
            if item.phase == "awarded":
                grouped[key]["awarded"].append(item)
            elif item.phase == "served":
                grouped[key]["served"].append(item)

    lifecycles: list[PenaltyLifecycle] = []
    for (session_key, driver_number, penalty_type), phases in sorted(grouped.items()):
        awards = sorted(phases["awarded"], key=lambda item: (item.rcm_lap or 0, item.date or ""))
        served = sorted(phases["served"], key=lambda item: (item.rcm_lap or 0, item.date or ""))
        used_served: set[str] = set()
        driver_records = records_by_driver.get((session_key, driver_number), [])
        for sequence, award in enumerate(awards, start=1):
            award_timestamp = _timestamp(award.date)
            eligible_served = [
                item
                for item in served
                if item.evidence_id not in used_served
                and (
                    pd.isna(award_timestamp)
                    or pd.isna(_timestamp(item.date))
                    or _timestamp(item.date) >= award_timestamp
                )
            ]
            award_reason = _penalty_reason(award.message)
            if award_reason:
                contextual_served = [
                    item
                    for item in eligible_served
                    if _penalty_reason(item.message) == award_reason
                ]
                if len(contextual_served) == 1:
                    served_item = contextual_served[0]
                elif (
                    not contextual_served
                    and len(eligible_served) == 1
                    and not _penalty_reason(eligible_served[0].message)
                ):
                    # Some official confirmations omit the reason. A sole
                    # reason-less confirmation is still safe to pair; multiple
                    # candidates remain unresolved rather than guessed.
                    served_item = eligible_served[0]
                else:
                    served_item = None
            else:
                served_item = eligible_served[0] if len(eligible_served) == 1 else None
            if served_item is not None:
                used_served.add(served_item.evidence_id)

            candidates = []
            for record in driver_records:
                if penalty_type not in {"drive_through", "stop_go"}:
                    continue
                if (
                    award.rcm_lap is not None
                    and not award.rcm_lap <= record.pit_in_lap <= award.rcm_lap + 3
                ):
                    continue
                pit_timestamp = _timestamp(record.pit_in_utc)
                if pd.notna(award_timestamp) and pd.notna(pit_timestamp):
                    if pit_timestamp < award_timestamp - pd.Timedelta(seconds=60):
                        continue
                    if served_item is not None:
                        served_timestamp = _timestamp(served_item.date)
                        if pd.notna(
                            served_timestamp
                        ) and pit_timestamp > served_timestamp + pd.Timedelta(seconds=60):
                            continue
                candidates.append(record)

            if penalty_type not in {"drive_through", "stop_go"}:
                status = "served_without_pit_assignment" if served_item else "unresolved"
                note = "time penalty may be served during a tyre stop or added to the result"
            elif len(candidates) == 1 and served_item is not None:
                status = "resolved_with_conflict" if candidates[0].source_conflict else "resolved"
                note = "one compatible entry between award and served confirmation"
            elif len(candidates) > 1:
                status = "ambiguous"
                note = "multiple compatible entries; no nearest-entry guess"
            elif len(candidates) == 1:
                status = "candidate_without_confirmation"
                note = "compatible entry found but no served confirmation in the feed"
            else:
                status = "unresolved"
                note = "no compatible entry can be established from the available evidence"

            lifecycles.append(
                PenaltyLifecycle(
                    penalty_id=f"{session_key}:{driver_number}:{penalty_type}:{sequence}",
                    session_key=session_key,
                    driver_number=driver_number,
                    penalty_type=penalty_type,
                    awarded_evidence_id=award.evidence_id,
                    served_evidence_id=None if served_item is None else served_item.evidence_id,
                    candidate_event_ids=tuple(record.event_id for record in candidates),
                    status=status,
                    review_note=note,
                )
            )
    return lifecycles


def _labels(
    telemetry_change: str,
    penalty: RCMEvidence | None,
    forced_entry: bool,
    damage: bool,
) -> tuple[str, str | None, str, str, str, str, bool, bool, bool]:
    """Resolve labels while preserving mixed causes and telemetry conflicts."""
    tyre_change = telemetry_change == "confirmed"
    source_conflict = (
        penalty is not None and penalty.penalty_type in {"drive_through", "stop_go"} and tyre_change
    )
    time_penalty_mixed = (
        penalty is not None and penalty.penalty_type in {"5s", "10s"} and tyre_change
    )

    if penalty is not None and penalty.penalty_type in {"drive_through", "stop_go"}:
        primary = PENALTY_SERVICE
        secondary = None
        cohort = "penalty_only"
        discretion = "forced_window"
    elif forced_entry:
        primary = REGULATION_REQUIRED_STOP
        secondary = STRATEGIC_TYRE_CHANGE if tyre_change else None
        cohort = "regulation_forced"
        discretion = "forced_lap"
    elif damage:
        primary = DAMAGE_MECHANICAL_OTHER
        secondary = STRATEGIC_TYRE_CHANGE if tyre_change else None
        cohort = "damage_other"
        discretion = "unknown"
    elif tyre_change:
        primary = STRATEGIC_TYRE_CHANGE
        secondary = PENALTY_SERVICE if time_penalty_mixed else None
        cohort = "strategic_candidate"
        discretion = "unknown"
    else:
        primary = UNKNOWN
        secondary = None
        cohort = "unknown"
        discretion = "unknown"

    mixed = secondary is not None
    comparable = (
        primary == STRATEGIC_TYRE_CHANGE
        and not mixed
        and not source_conflict
        and discretion == "discretionary"
    )
    evidence_level = (
        "corroborated"
        if penalty is not None or forced_entry or damage
        else "telemetry_only"
        if tyre_change
        else "insufficient"
    )
    penalty_type = penalty.penalty_type if penalty is not None else "none"
    penalty_served = "true" if penalty is not None and penalty.phase == "served" else "unknown"
    regulation = "forced_entry" if forced_entry else "none"
    return (
        primary,
        secondary,
        penalty_type,
        penalty_served,
        regulation,
        discretion,
        comparable,
        mixed,
        source_conflict,
    )


def build_stop_purpose_records(
    laps: pd.DataFrame,
    rcm: pd.DataFrame,
    *,
    year: int,
    race: str,
    session_key: int,
    meeting_key: int | None,
    sample_stops: set[tuple[str, int]],
    raw_laps: pd.DataFrame | None = None,
    repair_applied: bool = False,
    openf1_laps: pd.DataFrame | None = None,
) -> list[StopPurposeRecord]:
    """Build one conservative evidence record per ``PitInTime`` row."""
    if "PitInTime" not in laps.columns:
        return []

    parsed = [item for _, row in rcm.iterrows() if (item := parse_rcm_message(row)) is not None]
    records: list[StopPurposeRecord] = []
    source_laps = laps if raw_laps is None else raw_laps
    lap_starts = _openf1_lap_starts(openf1_laps)
    raw_by_driver = {
        str(driver): group.sort_values("LapNumber")
        for driver, group in source_laps.groupby("Driver", dropna=False)
    }
    for driver_code, group in laps.groupby("Driver", dropna=False):
        ordered = group.sort_values("LapNumber")
        pit_rows = ordered[ordered["PitInTime"].notna()]
        for sequence, (_, pit_row) in enumerate(pit_rows.iterrows(), start=1):
            pit_lap = _lap(pit_row.get("LapNumber"))
            if pit_lap is None:
                continue
            driver = _text(driver_code)
            driver_number = _driver_number(pit_row.get("DriverNumber"))
            out_row = _next_out_row(ordered, pit_lap)
            raw_group = raw_by_driver.get(driver, ordered)
            raw_pit_rows = raw_group[raw_group["LapNumber"].map(_lap).fillna(-1) == pit_lap]
            raw_pit_row = raw_pit_rows.iloc[0] if not raw_pit_rows.empty else pit_row
            raw_out_row = _next_out_row(raw_group, pit_lap)
            pit_in_utc, openf1_lap_start, intra_lap_offset_s = _event_utc(
                pit_row, "PitInTime", lap_starts
            )
            pit_out_utc = (
                None if out_row is None else _event_utc(out_row, "PitOutTime", lap_starts)[0]
            )
            telemetry_change, tyre_change = _telemetry_change(pit_row, out_row)
            linked = _linked_evidence(parsed, driver_number, pit_lap, pit_in_utc)
            penalty = _penalty_link(linked, pit_lap, pit_in_utc)
            forced = any(item.forced_entry and item.rcm_lap == pit_lap for item in linked)
            damage = _has_damage(linked, pit_lap)
            (
                primary,
                secondary,
                penalty_type,
                penalty_served,
                regulation,
                discretion,
                comparable,
                mixed,
                source_conflict,
            ) = _labels(telemetry_change, penalty, forced, damage)
            comparable = comparable and (driver, pit_lap) in sample_stops
            records.append(
                StopPurposeRecord(
                    event_id=f"{year}:{session_key}:{driver_number or driver}:{pit_lap}:{sequence}",
                    year=year,
                    session_key=session_key,
                    meeting_key=meeting_key,
                    race=race,
                    driver_number=driver_number,
                    driver_code=driver,
                    pit_sequence=sequence,
                    pit_in_lap=pit_lap,
                    pit_out_lap=None if out_row is None else _lap(out_row.get("LapNumber")),
                    pit_in_session_s=_seconds(pit_row.get("PitInTime")),
                    pit_out_session_s=None
                    if out_row is None
                    else _seconds(out_row.get("PitOutTime")),
                    pit_in_utc=pit_in_utc,
                    pit_out_utc=pit_out_utc,
                    openf1_lap_date_start_utc=openf1_lap_start,
                    intra_lap_offset_s=intra_lap_offset_s,
                    anchor_source="openf1_v1_laps" if pit_in_utc is not None else None,
                    anchor_precision="approximate" if pit_in_utc is not None else None,
                    timestamp_alignment=(
                        "anchored_openf1_lap_approximate"
                        if pit_in_utc is not None
                        else "missing_fastf1_time"
                        if _seconds(pit_row.get("PitInTime")) is None
                        else "missing_openf1_lap"
                    ),
                    pit_out_pair_status=(
                        "missing"
                        if out_row is None
                        else "consecutive_entry"
                        if pd.notna(out_row.get("PitInTime"))
                        else "paired"
                    ),
                    neutralisation_state=_neutralisation_state(pit_row.get("TrackStatus")),
                    raw_compound_in=_same_text(raw_pit_row.get("Compound")),
                    raw_compound_out=None
                    if raw_out_row is None
                    else _same_text(raw_out_row.get("Compound")),
                    raw_tyre_life_in=_number(raw_pit_row.get("TyreLife")),
                    raw_tyre_life_out=None
                    if raw_out_row is None
                    else _number(raw_out_row.get("TyreLife")),
                    raw_stint_in=_number(raw_pit_row.get("Stint")),
                    raw_stint_out=None
                    if raw_out_row is None
                    else _number(raw_out_row.get("Stint")),
                    repaired_compound_in=_same_text(pit_row.get("Compound")),
                    repaired_compound_out=None
                    if out_row is None
                    else _same_text(out_row.get("Compound")),
                    repaired_tyre_life_in=_number(pit_row.get("TyreLife")),
                    repaired_tyre_life_out=None
                    if out_row is None
                    else _number(out_row.get("TyreLife")),
                    repaired_stint_in=_number(pit_row.get("Stint")),
                    repaired_stint_out=None if out_row is None else _number(out_row.get("Stint")),
                    repair_applied=repair_applied,
                    telemetry_set_change=telemetry_change,
                    tyre_change_resolved=tyre_change,
                    source_conflict=source_conflict,
                    primary_label=primary,
                    secondary_label=secondary,
                    penalty_type=penalty_type,
                    penalty_served=penalty_served,
                    regulation_constraint=regulation,
                    timing_discretion=discretion,
                    decision_comparable=comparable,
                    mixed_purpose=mixed,
                    evidence_level=(
                        "corroborated"
                        if penalty is not None or forced or damage
                        else "telemetry_only"
                        if telemetry_change == "confirmed"
                        else "insufficient"
                    ),
                    evidence_timing=_evidence_timing(linked, pit_lap, pit_in_utc),
                    evidence_refs=tuple(item.evidence_id for item in linked),
                    in_715_sample=(driver, pit_lap) in sample_stops,
                    comparison_cohort=(
                        "comparable_clean"
                        if comparable
                        else "mixed"
                        if mixed
                        else "strategic_candidate"
                        if primary == STRATEGIC_TYRE_CHANGE
                        else {
                            PENALTY_SERVICE: "penalty_only",
                            REGULATION_REQUIRED_STOP: "regulation_forced",
                            DAMAGE_MECHANICAL_OTHER: "damage_other",
                        }.get(primary, "unknown")
                    ),
                    review_note=(
                        "telemetry and penalty evidence conflict"
                        if source_conflict
                        else "manual review required"
                        if primary in {STRATEGIC_TYRE_CHANGE, UNKNOWN}
                        else ""
                    ),
                )
            )
    return records
