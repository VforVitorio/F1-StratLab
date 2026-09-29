"""Diagnose no-call decision windows across the 2025 holdout without LLM calls.

The report compares the same production projection path on windows that the
decision metric scored and declined. It records inputs and score margins only;
it does not change the scorer or the committed decision-modes report.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.f1_strat_manager.gp_slugs import normalise_gp_key  # noqa: E402
from src.strategy.eval.decision_modes import SAMPLED_RACES  # noqa: E402

RACES = SAMPLED_RACES
OUTPUT_JSON = ROOT / "documents" / "audits" / "MEASURE_715_decision_diagnostic.json"
OUTPUT_MD = ROOT / "documents" / "audits" / "MEASURE_715_decision_diagnostic.md"


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _obligation(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def _canonical_race(value: Any) -> str:
    """Use the project's friendly GP key for every cross-report comparison."""
    return normalise_gp_key(str(value or ""))


def _instrument(races: tuple[tuple[int, str], ...]) -> tuple[list[dict], list[Any]]:
    import src.agents.strategy_orchestrator as orchestrator
    import src.strategy.eval.decision_modes as decision_modes
    import src.strategy.inference.engine as inference_engine

    records: list[dict] = []
    scope: dict[str, Any] = {}
    original_projection = orchestrator._run_projection_mc
    original_run_lap = inference_engine.run_lap
    original_window = decision_modes._decisions_in_window

    def scoped_window(engine, laps_df, driver, low, high, risk_tolerance=0.5):
        scope["year"] = int(getattr(engine.rsm, "year", 2025))
        scope["race"] = str(getattr(engine.rsm, "gp_name", ""))
        scope["driver"] = driver
        return original_window(engine, laps_df, driver, low, high, risk_tolerance)

    def instrumented_run_lap(*args, **kwargs):
        race_state = args[0]
        scope["driver"] = race_state.driver
        scope["lap"] = int(race_state.lap)
        start = len(records)
        recommendation, outputs, timings = original_run_lap(*args, **kwargs)
        for record in records[start:]:
            record["action"] = recommendation.action
        return recommendation, outputs, timings

    def instrumented_projection(*args, **kwargs):
        result = original_projection(*args, **kwargs)
        scores = {name: _finite(cell.get("score")) for name, cell in result.items()}
        stay = scores.get("STAY_OUT")
        pit_scores = [scores[name] for name in ("PIT_NOW", "UNDERCUT", "OVERCUT")]
        pit_scores = [score for score in pit_scores if score is not None]
        best_pit = max(pit_scores) if pit_scores else None
        context = kwargs.get("pit_context") or {}
        rival_counts = Counter(
            _obligation(value) for value in (context.get("rival_stop_pending") or {}).values()
        )
        if not rival_counts:
            rival_counts = Counter(
                _obligation(rival.get("stop_pending")) for rival in (kwargs.get("rivals") or [])
            )
        records.append(
            {
                "year": scope.get("year"),
                "race": _canonical_race(scope.get("race")),
                "driver": scope.get("driver"),
                "lap": scope.get("lap"),
                "action": None,
                "mandatory_stop_pending": _obligation(context.get("mandatory_stop_pending")),
                "rival_pending_true": rival_counts["true"],
                "rival_pending_false": rival_counts["false"],
                "rival_pending_unknown": rival_counts["unknown"],
                "deg_cost_known": kwargs.get("deg_cost_s") is not None,
                "deg_cost_s": _finite(kwargs.get("deg_cost_s")),
                "stay_score": stay,
                "best_pit_score": best_pit,
                "pit_minus_stay": None
                if stay is None or best_pit is None
                else round(best_pit - stay, 6),
                "stay_dominates": stay is not None and all(stay >= score for score in pit_scores),
                "best_mc": orchestrator.best_mc_candidate(result),
            }
        )
        return result

    decision_modes._decisions_in_window = scoped_window
    inference_engine.run_lap = instrumented_run_lap
    orchestrator._run_projection_mc = instrumented_projection
    try:
        _, verdicts = decision_modes.measure_decision_agreement(races=races)
    finally:
        decision_modes._decisions_in_window = original_window
        inference_engine.run_lap = original_run_lap
        orchestrator._run_projection_mc = original_projection
    return records, verdicts


def _attach_laps(records: list[dict], verdicts: list[Any]) -> list[dict]:
    """Attach only pre-stop observations to each real stop verdict.

    The captured records retain the whole replay window, but post-stop laps have
    already observed the real tyre change and cannot explain whether to stop.
    """
    rows: list[dict] = []
    for verdict in verdicts:
        matching = [
            record
            for record in records
            if record["year"] == verdict.year
            and _canonical_race(record["race"]) == _canonical_race(verdict.race)
            and record["driver"] == verdict.driver
            and verdict.actual_lap - 5 <= record["lap"] < verdict.actual_lap
        ]
        rows.append(
            {
                "year": verdict.year,
                "race": verdict.race,
                "driver": verdict.driver,
                "actual_lap": verdict.actual_lap,
                "bucket": verdict.bucket,
                "evaluated_laps": len(matching),
                "mandatory_stop_pending": Counter(
                    record["mandatory_stop_pending"] for record in matching
                ),
                "rival_pending": {
                    state: sum(record[f"rival_pending_{state}"] for record in matching)
                    for state in ("true", "false", "unknown")
                },
                "deg_cost_known": sum(record["deg_cost_known"] for record in matching),
                "pit_preferred": sum((record["pit_minus_stay"] or 0) > 0 for record in matching),
                "stay_dominates": sum(record["stay_dominates"] for record in matching),
                "margins": [
                    record["pit_minus_stay"]
                    for record in matching
                    if record["pit_minus_stay"] is not None
                ],
            }
        )
    return rows


def _bucket_summary(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["bucket"]].append(row)
    summary: dict[str, dict] = {}
    for bucket, bucket_rows in sorted(grouped.items()):
        margins = [margin for row in bucket_rows for margin in row["margins"]]
        obligations = Counter(
            obligation
            for row in bucket_rows
            for obligation, count in row["mandatory_stop_pending"].items()
            for _ in range(count)
        )
        rival_pending = {
            state: sum(row["rival_pending"][state] for row in bucket_rows)
            for state in ("true", "false", "unknown")
        }
        evaluated = sum(row["evaluated_laps"] for row in bucket_rows)
        summary[bucket] = {
            "windows": len(bucket_rows),
            "evaluated_laps": evaluated,
            "mandatory_stop_pending": dict(sorted(obligations.items())),
            "rival_pending": rival_pending,
            "deg_known_laps": sum(row["deg_cost_known"] for row in bucket_rows),
            "pit_preferred_laps": sum(row["pit_preferred"] for row in bucket_rows),
            "stay_dominates_laps": sum(row["stay_dominates"] for row in bucket_rows),
            "pit_minus_stay_mean": round(mean(margins), 6) if margins else None,
            "pit_minus_stay_min": min(margins) if margins else None,
            "pit_minus_stay_max": max(margins) if margins else None,
        }
    return summary


def _render_markdown(payload: dict) -> str:
    no_call = payload["bucket_summary"]["no_call_in_window"]
    scored = payload["bucket_summary"]["scored"]
    no_call_laps = no_call["evaluated_laps"]
    scored_laps = scored["evaluated_laps"]
    no_call_pending = no_call["mandatory_stop_pending"].get("true", 0)
    scored_pending = scored["mandatory_stop_pending"].get("true", 0)
    lines = [
        "# Decision-layer diagnostic",
        "",
        "This is an offline diagnostic of the current production projection path.",
        "It compares the five laps before each real stop. Both `WINDOW_LAPS` and",
        "`DECISION_WINDOW_LAPS` remain 5. It is not a fix and",
        "it does not claim that the real pit wall was strategically correct.",
        "",
        "`PitInTime` identifies a pit entry, not its purpose. The population can include",
        "penalties, event-specific tyre rules, and other non-elective entries, so these",
        "figures describe scorer behaviour and are not a pure elective-stop accuracy rate.",
        "",
        f"- generated `{payload['generated_at']}`",
        f"- races: {', '.join(payload['races'])}",
        f"- projection calls: {payload['projection_calls']}",
        f"- verdicts: {payload['verdicts']}",
        "- LLM/API calls: none",
        "",
        "| bucket | windows | evaluated laps | driver mandatory T/F/U | rival pending T/F/U | "
        "deg known | PIT preferred | STAY_OUT dominates | mean PIT-STAY |",
        "| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for bucket, row in payload["bucket_summary"].items():
        obligations = row["mandatory_stop_pending"]
        lines.append(
            f"| `{bucket}` | {row['windows']} | {row['evaluated_laps']} | "
            f"{obligations.get('true', 0)}/{obligations.get('false', 0)}/"
            f"{obligations.get('unknown', 0)} | "
            f"{row['rival_pending']['true']}/{row['rival_pending']['false']}/"
            f"{row['rival_pending']['unknown']} | {row['deg_known_laps']} | "
            f"{row['pit_preferred_laps']} | {row['stay_dominates_laps']} | "
            f"{row['pit_minus_stay_mean']} |"
        )
    lines.extend(
        [
            "",
            "The next decision is based on this comparison. A positive `PIT-STAY` means",
            "the best eligible pit candidate beat `STAY_OUT` on that evaluated lap.",
            "",
            f"In `no_call_in_window`, the driver's mandatory stop was pending on "
            f"{no_call_pending}/{no_call_laps} laps ({no_call_pending / no_call_laps:.1%}). "
            f"`STAY_OUT` dominated on {no_call['stay_dominates_laps']}/{no_call_laps} "
            f"laps ({no_call['stay_dominates_laps'] / no_call_laps:.1%}); the best pit "
            f"candidate won on {no_call['pit_preferred_laps']}/{no_call_laps} "
            f"({no_call['pit_preferred_laps'] / no_call_laps:.1%}).",
            f"In `scored`, the driver's mandatory stop was pending on "
            f"{scored_pending}/{scored_laps} laps ({scored_pending / scored_laps:.1%}); "
            f"the best pit candidate won on {scored['pit_preferred_laps']}/{scored_laps} "
            f"({scored['pit_preferred_laps'] / scored_laps:.1%}).",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    records, verdicts = _instrument(RACES)
    for index, record in enumerate(records):
        record["lap"] = int(record["lap"])
        record["record_id"] = index
    rows = _attach_laps(records, verdicts)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "races": [f"{year} {race}" for year, race in RACES],
        "window_laps": 5,
        "decision_window_laps": 5,
        "projection_calls": len(records),
        "verdicts": len(verdicts),
        "buckets": dict(Counter(verdict.bucket for verdict in verdicts)),
        "bucket_summary": _bucket_summary(rows),
        "records": records,
    }
    assert sum(payload["buckets"].values()) == len(verdicts)
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(_render_markdown(payload), encoding="utf-8")
    print(OUTPUT_MD)
    print(json.dumps(payload["bucket_summary"], indent=2))


if __name__ == "__main__":
    main()
