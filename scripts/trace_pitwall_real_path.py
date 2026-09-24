"""Capture one measured Arcade tick through the live PITWALL TCP and host routes.

Run this while ``f1-arcade --strategy --no-llm`` is replaying the selected race.
The browser port must match ``F1_PITWALL_BROWSER_PORT`` in the Arcade process.
The report contains one complete wire message and the corresponding host/API
values; browser-rendered evidence is captured separately with the Playwright page probe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from src.arcade.config import STREAM_HOST, STREAM_PORT
from src.pitwall.webserver import BROWSER_HOST, BROWSER_PORT

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


def _matches_target(payload: dict[str, Any], year: int, gp: str, driver: str, lap: int) -> bool:
    """Return whether this serialized tick contains the measured decision."""
    arcade = payload.get("arcade") or {}
    latest = (payload.get("strategy") or {}).get("latest") or {}
    return (
        arcade.get("year") == year
        and str(arcade.get("location", "")).casefold() == gp.casefold()
        and str(arcade.get("driver_main", "")).upper() == driver.upper()
        and latest.get("lap_number") == lap
    )


def _read_target_tick(args: argparse.Namespace) -> tuple[bytes, dict[str, Any]]:
    """Read newline-delimited JSON until the real stream carries the target lap."""
    deadline = time.monotonic() + args.timeout
    buffer = b""
    with socket.create_connection((args.stream_host, args.stream_port), timeout=10) as sock:
        sock.settimeout(1)
        while time.monotonic() < deadline:
            try:
                chunk = sock.recv(1 << 16)
            except TimeoutError:
                continue
            if not chunk:
                raise ConnectionError("Arcade closed the TCP stream before the target tick")
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                if not line:
                    continue
                payload = json.loads(line)
                if _matches_target(payload, args.year, args.gp, args.driver, args.lap):
                    return line, payload
    raise TimeoutError(
        f"No {args.gp} {args.year} {args.driver} decision for lap {args.lap} "
        f"arrived within {args.timeout}s"
    )


def _get_json(base_url: str, route: str) -> Any:
    """Capture one production BrowserServer endpoint or its exact failure."""
    try:
        with urlopen(f"{base_url}{route}", timeout=5) as response:
            body = response.read()
        return json.loads(body)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {exc.code}: {detail}"}
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _capture_routes(args: argparse.Namespace, wire: dict[str, Any]) -> dict[str, Any]:
    base_url = f"http://{args.browser_host}:{args.browser_port}"
    tick = _get_json(base_url, "/api/tick?since=-1")
    seq = tick.get("seq") if isinstance(tick, dict) else None
    agents_since = seq - 1 if isinstance(seq, int) else -1
    agents = _get_json(
        base_url,
        f"/api/agents?since={agents_since}&connection=Connected",
    )
    bulk = _get_json(base_url, "/api/bulk?since=-1")
    live = _get_json(base_url, "/api/live?since=-1")
    connection = _get_json(base_url, "/api/connection")

    wire_latest = (wire.get("strategy") or {}).get("latest") or {}
    wire_start = (wire.get("strategy") or {}).get("start") or {}
    tick_start = ((tick.get("strategy") or {}).get("start") or {}) if isinstance(tick, dict) else {}
    tick_latest = (
        ((tick.get("strategy") or {}).get("latest") or {}) if isinstance(tick, dict) else {}
    )
    agents_orchestrator = agents.get("orchestrator") or {} if isinstance(agents, dict) else {}
    data_drivers = bulk.get("drivers") or {} if isinstance(bulk, dict) else {}
    live_drivers = live.get("drivers") or {} if isinstance(live, dict) else {}

    return {
        "tick": tick,
        "agents": agents,
        "data_bulk": {
            "race": bulk.get("race") if isinstance(bulk, dict) else None,
            "available": bulk.get("available") if isinstance(bulk, dict) else None,
            "driver": data_drivers.get(args.driver.upper()),
            "error": bulk.get("error") if isinstance(bulk, dict) else bulk,
        },
        "data_live_lap": {
            "driver": live_drivers.get(args.driver.upper()),
            "error": live.get("error") if isinstance(live, dict) else live,
        },
        "connection": connection,
        "correlation": {
            "wire_seq": wire.get("seq"),
            "host_tick_seq": tick.get("seq") if isinstance(tick, dict) else None,
            "agents_seq": agents.get("seq") if isinstance(agents, dict) else None,
            "wire_decision_lap": wire_latest.get("lap_number"),
            "host_decision_lap": tick_latest.get("lap_number"),
            "wire_no_llm": wire_start.get("no_llm"),
            "host_no_llm": tick_start.get("no_llm"),
            "agents_action": agents_orchestrator.get("action"),
            "source_action": wire_latest.get("action"),
            "same_wire_host_action": wire_latest.get("action") == tick_latest.get("action"),
            "same_wire_host_seq": isinstance(tick, dict) and tick.get("seq") == wire.get("seq"),
            "same_host_agents_seq": (
                isinstance(tick, dict)
                and isinstance(agents, dict)
                and tick.get("seq") == agents.get("seq")
            ),
        },
    }


def _evaluate_trace_checks(
    args: argparse.Namespace, wire: dict[str, Any], routes: dict[str, Any]
) -> dict[str, bool]:
    """Require the captured channels to describe one real tick and its display values."""
    tick = routes.get("tick") if isinstance(routes.get("tick"), dict) else {}
    agents = routes.get("agents") if isinstance(routes.get("agents"), dict) else {}
    bulk = routes.get("data_bulk") if isinstance(routes.get("data_bulk"), dict) else {}
    live = routes.get("data_live_lap") if isinstance(routes.get("data_live_lap"), dict) else {}
    connection = routes.get("connection") if isinstance(routes.get("connection"), dict) else {}
    wire_arcade = wire.get("arcade") if isinstance(wire.get("arcade"), dict) else {}
    wire_strategy = wire.get("strategy") if isinstance(wire.get("strategy"), dict) else {}
    wire_start = wire_strategy.get("start") if isinstance(wire_strategy.get("start"), dict) else {}
    wire_latest = (
        wire_strategy.get("latest") if isinstance(wire_strategy.get("latest"), dict) else {}
    )
    tick_arcade = tick.get("arcade") if isinstance(tick.get("arcade"), dict) else {}
    tick_strategy = tick.get("strategy") if isinstance(tick.get("strategy"), dict) else {}
    tick_start = tick_strategy.get("start") if isinstance(tick_strategy.get("start"), dict) else {}
    tick_latest = (
        tick_strategy.get("latest") if isinstance(tick_strategy.get("latest"), dict) else {}
    )
    agent_header = agents.get("header") if isinstance(agents.get("header"), dict) else {}
    agent_orchestrator = (
        agents.get("orchestrator") if isinstance(agents.get("orchestrator"), dict) else {}
    )
    bulk_race = bulk.get("race") if isinstance(bulk.get("race"), dict) else {}
    bulk_driver = bulk.get("driver") if isinstance(bulk.get("driver"), dict) else {}
    bulk_laps = bulk_driver.get("laps") if isinstance(bulk_driver.get("laps"), list) else []
    bulk_last = bulk_laps[-1] if bulk_laps and isinstance(bulk_laps[-1], dict) else {}
    live_driver = live.get("driver") if isinstance(live.get("driver"), dict) else {}
    wire_car = (wire_arcade.get("drivers") or {}).get(args.driver.upper())
    wire_laps = wire_car.get("laps_completed") if isinstance(wire_car, dict) else None
    source_action = wire_latest.get("action")
    action_label = ACTION_LABELS.get(str(source_action).upper(), source_action)
    wire_seq = wire.get("seq")
    host_seq = tick.get("seq")
    agents_seq = agents.get("seq")

    def valid_sequence(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    def is_location(value: Any) -> bool:
        return str(value or "").casefold() == args.gp.casefold()

    return {
        "wire_seq_valid": valid_sequence(wire_seq),
        "host_seq_matches_wire": valid_sequence(host_seq) and host_seq == wire_seq,
        "agents_seq_matches_wire": valid_sequence(agents_seq) and agents_seq == wire_seq,
        "wire_identity_matches_target": (
            wire_arcade.get("year") == args.year
            and is_location(wire_arcade.get("location"))
            and str(wire_arcade.get("driver_main", "")).upper() == args.driver.upper()
        ),
        "host_identity_matches_wire": (
            tick_arcade.get("year") == wire_arcade.get("year")
            and tick_arcade.get("location") == wire_arcade.get("location")
            and tick_arcade.get("driver_main") == wire_arcade.get("driver_main")
        ),
        "wire_and_host_decision_match": (
            wire_latest.get("lap_number") == args.lap
            and tick_latest.get("lap_number") == wire_latest.get("lap_number")
            and tick_latest.get("action") == source_action
        ),
        "no_llm_confirmed_on_wire_and_host": (
            wire_start.get("no_llm") is True and tick_start.get("no_llm") is True
        ),
        "agents_header_matches_wire": (
            agent_header.get("session") == f"{args.gp} · {args.year}"
            and agent_header.get("driver") == args.driver.upper()
            and agent_header.get("lap")
            == f"L {wire_arcade.get('lap')}/{wire_arcade.get('total_laps')}"
            and agent_header.get("connection") == "Connected"
        ),
        "agents_action_matches_wire": (
            isinstance(source_action, str) and agent_orchestrator.get("action") == action_label
        ),
        "data_bulk_matches_wire": (
            bulk.get("available") is True
            and bulk.get("error") is None
            and bulk_race.get("year") == wire_arcade.get("year")
            and bulk_race.get("location") == wire_arcade.get("location")
            and isinstance(bulk_driver.get("laps_revealed"), int)
            and isinstance(wire_laps, int)
            and bulk_driver.get("laps_revealed") == wire_laps
            and bool(bulk_laps)
            and bulk_last.get("lap") == bulk_driver.get("laps_revealed")
            and isinstance(bulk_last.get("lap_time"), (int, float))
            and isinstance(bulk_driver.get("number"), str)
            and isinstance(bulk_driver.get("stops"), int)
        ),
        "data_live_matches_wire": (
            live.get("error") is None
            and isinstance(live_driver.get("lap"), int)
            and live_driver.get("lap") == wire_arcade.get("lap")
            and all(
                isinstance(live_driver.get(field), (int, float))
                for field in ("s1", "v1", "s2", "v2", "s3", "vfl")
            )
        ),
        "connection_connected": connection.get("label") == "Connected",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--gp", default="Lusail")
    parser.add_argument("--driver", default="NOR")
    parser.add_argument("--lap", type=int, default=7)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stream-host", default=STREAM_HOST)
    parser.add_argument("--stream-port", type=int, default=STREAM_PORT)
    parser.add_argument("--browser-host", default=BROWSER_HOST)
    parser.add_argument("--browser-port", type=int, default=BROWSER_PORT)
    parser.add_argument("--out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.run_id = args.run_id or f"1252-{stamp}-{args.gp.lower()}-{args.driver.lower()}-l{args.lap}"
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", args.run_id):
        raise ValueError(
            "run_id may contain only ASCII letters, numbers, periods, underscores, and dashes"
        )
    out = args.out or REPO_ROOT / "documents" / "audits" / f"TRACE_1252_{args.run_id}.json"
    if out.exists():
        raise FileExistsError(f"Trace output already exists: {out}")

    report: dict[str, Any] = {
        "run_id": args.run_id,
        "status": "failed",
        "config": {
            "year": args.year,
            "gp": args.gp,
            "driver": args.driver.upper(),
            "lap": args.lap,
            "stream": f"{args.stream_host}:{args.stream_port}",
            "browser": f"{args.browser_host}:{args.browser_port}",
        },
        "provenance": {
            "wire": "one raw NDJSON message read from TelemetryStreamServer over TCP",
            "host": "live BrowserServer routes backed by ArcadeStreamClient and PitwallHost",
            "data": "get_bulk/get_live_lap from the running DATA host path",
            "agents": "get_agents_view from the running AGENTS host path",
        },
    }
    try:
        wire_line, wire = _read_target_tick(args)
        report["wire"] = {
            "sha256": hashlib.sha256(wire_line + b"\n").hexdigest(),
            "bytes": len(wire_line) + 1,
            "payload": wire,
        }
        report["host_routes"] = _capture_routes(args, wire)
        routes = report["host_routes"]
        checks = _evaluate_trace_checks(args, wire, routes)
        report["checks"] = checks
        failures = [name for name, passed in checks.items() if not passed]
        if failures:
            report["failure"] = "Failed checks: " + ", ".join(failures)
        report["status"] = "pass" if not failures else "fail"
    except Exception as exc:
        report["failure"] = f"{type(exc).__name__}: {exc}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": args.run_id, "status": report["status"], "out": str(out)}))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
