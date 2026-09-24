"""Cross-check one TCP capture against the browser API responses and rendered DOM."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTION_LABELS = {
    "STAY_OUT": "STAY OUT",
    "PIT_NOW": "PIT NOW",
    "UNDERCUT": "UNDERCUT",
    "OVERCUT": "OVERCUT",
    "ALERT": "ALERT",
    "DNF": "DNF",
    "ERROR": "ERROR",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _same_race(value: Any, year: int, gp: str) -> bool:
    race = _mapping(value)
    return race.get("year") == year and str(race.get("location", "")).casefold() == gp.casefold()


def _screenshot_path(screenshots: dict[str, Any], name: str) -> str:
    value = screenshots.get(name)
    return str(value.get("path", "")) if isinstance(value, dict) else str(value or "")


def _row_from_text(text: str, driver: str) -> list[str] | None:
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) >= 10 and fields[0].strip() == driver:
            return fields
    return None


def _seconds(text: str) -> float:
    parts = text.strip().split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float("nan")


def _sector_matches(text: str, lap: dict[str, Any], time_key: str, speed_key: str) -> bool:
    values = [float(value) for value in re.findall(r"\d+(?:\.\d+)?", text)]
    lap_time, speed = lap.get(time_key), lap.get(speed_key)
    index = 0
    if lap_time is not None:
        if not values or abs(values[index] - float(lap_time)) > 0.0005:
            return False
        index += 1
    if speed is not None:
        if len(values) <= index or values[index] != float(speed):
            return False
        index += 1
    return len(values) == index


def evaluate_trace_reports(
    api_report: dict[str, Any],
    browser_report: dict[str, Any],
    screenshot_sizes: dict[str, int],
) -> dict[str, bool]:
    """Fail closed unless wire, host, DATA, AGENTS, and saved screenshots agree."""
    run_id = api_report.get("run_id")
    config = _mapping(api_report.get("config"))
    year, gp, driver, target_lap = (
        config.get("year"),
        config.get("gp"),
        str(config.get("driver", "")).upper(),
        config.get("lap"),
    )
    wire_report = _mapping(api_report.get("wire"))
    wire = _mapping(wire_report.get("payload"))
    wire_arcade = _mapping(wire.get("arcade"))
    wire_strategy = _mapping(wire.get("strategy"))
    wire_start = _mapping(wire_strategy.get("start"))
    wire_latest = _mapping(wire_strategy.get("latest"))
    routes = _mapping(api_report.get("host_routes"))
    host_tick = _mapping(routes.get("tick"))
    host_arcade = _mapping(host_tick.get("arcade"))
    host_strategy = _mapping(host_tick.get("strategy"))
    host_start = _mapping(host_strategy.get("start"))
    host_latest = _mapping(host_strategy.get("latest"))
    host_agents = _mapping(routes.get("agents"))
    host_header = _mapping(host_agents.get("header"))
    host_orchestrator = _mapping(host_agents.get("orchestrator"))
    data_summary = _mapping(routes.get("data_bulk"))
    data_driver = _mapping(data_summary.get("driver"))
    data_live_summary = _mapping(routes.get("data_live_lap"))
    data_live_driver = _mapping(data_live_summary.get("driver"))
    connection = _mapping(routes.get("connection"))

    browser_target = _mapping(browser_report.get("target"))
    browser_sequences = _mapping(browser_report.get("sequences"))
    browser_values = _mapping(browser_report.get("host_values"))
    browser_tick = _mapping(browser_values.get("tick"))
    browser_arcade = _mapping(browser_tick.get("arcade"))
    browser_strategy = _mapping(browser_tick.get("strategy"))
    browser_start = _mapping(browser_strategy.get("start"))
    browser_latest = _mapping(browser_strategy.get("latest"))
    browser_bulk = _mapping(browser_values.get("bulk"))
    browser_bulk_race = _mapping(browser_bulk.get("race"))
    browser_driver = _mapping(_mapping(browser_bulk.get("drivers")).get(driver))
    browser_laps = (
        browser_driver.get("laps") if isinstance(browser_driver.get("laps"), list) else []
    )
    browser_last_lap = _mapping(browser_laps[-1]) if browser_laps else {}
    browser_live = _mapping(browser_values.get("live_lap"))
    browser_live_driver = _mapping(_mapping(browser_live.get("drivers")).get(driver))
    browser_agents = _mapping(browser_values.get("agents"))
    browser_header = _mapping(browser_agents.get("header"))
    browser_orchestrator = _mapping(browser_agents.get("orchestrator"))
    rendered = _mapping(browser_report.get("rendered"))
    rendered_data = _mapping(rendered.get("data"))
    rendered_agents = _mapping(rendered.get("agents"))
    rendered_row = _mapping(rendered_data.get("row"))
    row_fields = _row_from_text(str(rendered_data.get("text", "")), driver)

    wire_seq = wire.get("seq")
    action = wire_latest.get("action")
    expected_action = ACTION_LABELS.get(str(action).upper(), action)
    laps_completed = _mapping(wire_arcade.get("drivers")).get(driver, {})
    laps_completed = _mapping(laps_completed).get("laps_completed")
    last_lap = (data_driver.get("laps") or [{}])[-1]
    last_lap = _mapping(last_lap)
    expected_last_time = last_lap.get("lap_time")
    rendered_last_time = rendered_row.get("last")
    if not rendered_last_time and row_fields:
        rendered_last_time = row_fields[6]
    expected_tyre = (
        f"{str(last_lap.get('compound'))[0]}"
        f"{' ' + str(round(float(last_lap['tyre_life']))) if last_lap.get('tyre_life') is not None else ''}"
        if last_lap.get("compound")
        else "—"
    )
    rendered_tyre = rendered_row.get("tyre") or (row_fields[8] if row_fields else None)
    rendered_stops = rendered_row.get("stops") or (row_fields[9] if row_fields else None)
    rendered_sectors = rendered_row.get("sectors") or (row_fields[3:6] if row_fields else None)
    live_laps = (browser_live_driver.get("lap"), data_live_driver.get("lap"))
    route_statuses = _mapping(browser_report.get("route_statuses"))
    data_statuses = _mapping(route_statuses.get("data"))
    agents_statuses = _mapping(route_statuses.get("agents"))
    screenshots = _mapping(browser_report.get("screenshots"))

    canonical_wire = json.dumps(wire, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    row_data_matches = bool(row_fields or rendered_row)
    if row_data_matches and expected_last_time is not None:
        try:
            row_data_matches = (
                abs(_seconds(str(rendered_last_time)) - float(expected_last_time)) <= 0.0005
            )
        except (TypeError, ValueError):
            row_data_matches = False
    if row_data_matches:
        row_data_matches = (
            rendered_tyre == expected_tyre
            and str(rendered_stops) == str(data_driver.get("stops"))
            and data_driver.get("laps_revealed") == laps_completed
            and bool(rendered_sectors)
            and len(rendered_sectors) == 3
        )
    if row_data_matches and rendered_row:
        race_order = wire_arcade.get("race_order")
        expected_position = (
            race_order.index(driver) + 1
            if isinstance(race_order, list) and driver in race_order
            else None
        )
        row_data_matches = (
            rendered_row.get("driver") == driver
            and rendered_row.get("number") == str(browser_driver.get("number"))
            and expected_position is not None
            and str(rendered_row.get("position")) == str(expected_position)
        )
    if row_data_matches and rendered_sectors:
        sectors = _mapping(browser_live_driver)
        row_data_matches = all(
            _sector_matches(text, sectors, time_key, speed_key)
            for text, time_key, speed_key in zip(
                rendered_sectors,
                ("s1", "s2", "s3"),
                ("v1", "v2", "vfl"),
            )
        )

    checks = {
        "run_ids_match": bool(run_id) and browser_report.get("run_id") == run_id,
        "both_reports_claim_pass": api_report.get("status") == "pass"
        and browser_report.get("status") == "pass",
        "wire_hash_and_size_match_payload": (
            isinstance(wire_report.get("sha256"), str)
            and hashlib.sha256(canonical_wire).hexdigest() == wire_report.get("sha256")
            and len(canonical_wire) == wire_report.get("bytes")
        ),
        "all_five_sequences_match": (
            isinstance(wire_seq, int)
            and not isinstance(wire_seq, bool)
            and wire_seq > 0
            and host_tick.get("seq") == wire_seq
            and host_agents.get("seq") == wire_seq
            and browser_tick.get("seq") == wire_seq
            and browser_agents.get("seq") == wire_seq
            and browser_sequences.get("same_seq") is True
        ),
        "browser_target_matches_api_trace": (
            browser_target.get("gp") == gp
            and browser_target.get("driver") == driver
            and browser_target.get("decision_lap") == target_lap
        ),
        "scenario_and_no_llm_match": (
            year == 2025
            and str(gp).casefold() == str(wire_arcade.get("location", "")).casefold()
            and host_arcade.get("year") == wire_arcade.get("year")
            and wire_arcade.get("driver_main") == driver
            and browser_arcade.get("year") == wire_arcade.get("year")
            and browser_arcade.get("location") == wire_arcade.get("location")
            and browser_arcade.get("driver_main") == driver
            and wire_arcade.get("lap") == target_lap
            and wire_latest.get("lap_number") == target_lap
            and host_latest.get("lap_number") == target_lap
            and browser_latest.get("lap_number") == target_lap
            and browser_latest.get("action") == action
            and wire_start.get("no_llm") is True
            and host_start.get("no_llm") is True
            and browser_start.get("no_llm") is True
            and browser_arcade.get("location") == wire_arcade.get("location")
            and browser_arcade.get("driver_main") == driver
        ),
        "host_and_agents_values_match_wire": (
            host_arcade.get("location") == wire_arcade.get("location")
            and host_arcade.get("driver_main") == driver
            and host_latest.get("action") == action
            and host_orchestrator.get("action") == expected_action
            and browser_orchestrator.get("action") == expected_action
            and rendered_agents.get("action") == expected_action
            and host_header.get("session") == f"{gp} · {year}"
            and browser_header.get("session") == host_header.get("session")
            and rendered_agents.get("session") == host_header.get("session")
            and browser_header.get("lap") == host_header.get("lap")
            and browser_header.get("connection") == "Connected"
            and host_header.get("driver") == driver
            and browser_header.get("driver") == driver
            and rendered_agents.get("driver") == driver
            and host_header.get("lap")
            == f"L {wire_arcade.get('lap')}/{wire_arcade.get('total_laps')}"
            and rendered_agents.get("lap") == host_header.get("lap")
            and host_header.get("connection") == "Connected"
            and connection.get("label") == "Connected"
            and rendered_agents.get("connection") == "Connected"
        ),
        "data_routes_match_wire_and_display": (
            data_summary.get("available") is True
            and data_summary.get("error") is None
            and data_live_summary.get("error") is None
            and _same_race(data_summary.get("race"), year, gp)
            and browser_bulk.get("available") is True
            and _same_race(browser_bulk_race, year, gp)
            and data_driver.get("laps_revealed") == laps_completed
            and browser_driver.get("laps_revealed") == laps_completed
            and browser_driver.get("number") == data_driver.get("number")
            and browser_driver.get("stops") == data_driver.get("stops")
            and browser_last_lap.get("lap_time") == expected_last_time
            and browser_last_lap.get("lap") == last_lap.get("lap")
            and browser_last_lap.get("compound") == last_lap.get("compound")
            and browser_last_lap.get("tyre_life") == last_lap.get("tyre_life")
            and all(
                browser_live_driver.get(field) == data_live_driver.get(field)
                for field in ("s1", "v1", "s2", "v2", "s3", "vfl")
            )
            and live_laps == (wire_arcade.get("lap"), wire_arcade.get("lap"))
            and browser_live_driver.get("lap") == wire_arcade.get("lap")
            and rendered_data.get("lap")
            == f"L {wire_arcade.get('lap')}/{wire_arcade.get('total_laps')}"
            and rendered_data.get("connection") == "Connected"
            and row_data_matches
        ),
        "all_browser_routes_succeeded": all(
            status == 200
            for status in (
                data_statuses.get("/api/tick"),
                data_statuses.get("/api/bulk"),
                data_statuses.get("/api/live"),
                agents_statuses.get("/api/agents"),
            )
        ),
        "browser_has_no_errors": browser_report.get("errors") == [],
        "screenshots_exist_and_are_nonempty": all(
            bool(_screenshot_path(screenshots, name))
            and (not isinstance(screenshots.get(name), dict) or screenshots[name].get("ok") is True)
            and screenshot_sizes.get(name, 0) > 0
            for name in ("data", "agents")
        ),
    }
    return checks


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.run_id):
        raise ValueError(
            "run_id may contain only ASCII letters, numbers, periods, underscores, and dashes"
        )

    audit_dir = REPO_ROOT / "documents" / "audits"
    api_path = audit_dir / f"TRACE_1252_{args.run_id}.json"
    browser_path = audit_dir / f"TRACE_1252_{args.run_id}_browser.json"
    api_report = _read_json(api_path)
    browser_report = _read_json(browser_path)
    screenshots = _mapping(browser_report.get("screenshots"))
    screenshot_sizes = {}
    for name in ("data", "agents"):
        path = Path(_screenshot_path(screenshots, name))
        screenshot_sizes[name] = path.stat().st_size if path.is_file() else 0

    checks = evaluate_trace_reports(api_report, browser_report, screenshot_sizes)
    failures = [name for name, passed in checks.items() if not passed]
    report = {
        "run_id": args.run_id,
        "status": "pass" if not failures else "fail",
        "sequence": _mapping(_mapping(api_report.get("wire")).get("payload")).get("seq"),
        "decision": {
            "lap_number": _mapping(
                _mapping(_mapping(api_report.get("wire")).get("payload")).get("strategy")
            )
            .get("latest", {})
            .get("lap_number"),
            "action": _mapping(
                _mapping(_mapping(api_report.get("wire")).get("payload")).get("strategy")
            )
            .get("latest", {})
            .get("action"),
            "no_llm": _mapping(
                _mapping(_mapping(api_report.get("wire")).get("payload")).get("strategy")
            )
            .get("start", {})
            .get("no_llm"),
        },
        "checks": checks,
        "failures": failures,
        "inputs": {"api": str(api_path), "browser": str(browser_path)},
        "screenshots": {name: _screenshot_path(screenshots, name) for name in screenshots},
    }
    out = args.out or audit_dir / f"TRACE_1252_{args.run_id}_verified.json"
    if not out.is_absolute():
        out = REPO_ROOT / out
    if out.exists():
        raise FileExistsError(f"Verification output already exists: {out}")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "status": report["status"], "out": str(out)}))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
