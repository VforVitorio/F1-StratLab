import hashlib
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import trace_pitwall_real_path
from scripts.trace_pitwall_real_path import (
    _evaluate_trace_checks,
    _matches_target,
    _sequence_advanced,
)
from scripts.verify_pitwall_trace import _resolve_screenshot_path, evaluate_trace_reports


def test_trace_matches_only_the_configured_real_decision_coordinates():
    tick = {
        "arcade": {"year": 2025, "location": "Lusail", "driver_main": "NOR", "lap": 7},
        "strategy": {"latest": {"lap_number": 7, "action": "STAY_OUT"}},
    }

    assert _matches_target(tick, 2025, "Lusail", "NOR", 7)
    assert not _matches_target(tick, 2024, "Lusail", "NOR", 7)
    assert not _matches_target(tick, 2025, "Lusail", "PIA", 7)
    assert not _matches_target(tick, 2025, "Lusail", "NOR", 8)


@pytest.mark.parametrize(
    "sequences,expected",
    [([10, 12], True), ([10, 10], False), ([10, 9], False), ([True, 12], False)],
)
def test_wire_sequence_progression_allows_gaps_but_requires_increase(sequences, expected):
    assert _sequence_advanced(sequences) is expected


def _coherent_trace():
    wire = {
        "seq": 3227,
        "arcade": {
            "year": 2025,
            "location": "Lusail",
            "driver_main": "NOR",
            "lap": 7,
            "total_laps": 57,
            "drivers": {"NOR": {"laps_completed": 6}},
        },
        "strategy": {
            "start": {"no_llm": True},
            "latest": {"lap_number": 7, "action": "STAY_OUT"},
        },
    }
    tick = deepcopy(wire)
    tick["seq"] = 3250
    agents = {
        "seq": 3268,
        "header": {
            "session": "Lusail · 2025",
            "driver": "NOR",
            "lap": "L 7/57",
            "connection": "Connected",
        },
        "orchestrator": {
            "action": "STAY OUT",
            "plan": "stint continues - no pit window yet",
        },
        "plan_timeline": {
            "current_lap": 7,
            "total_laps": 57,
            "caption": "stint continues - no pit window yet",
        },
    }
    routes = {
        "tick": tick,
        "agents": agents,
        "data_bulk": {
            "race": {"year": 2025, "location": "Lusail"},
            "available": True,
            "driver": {
                "number": "4",
                "laps_revealed": 6,
                "stops": 0,
                "laps": [{"lap": 6, "lap_time": 86.957}],
            },
            "error": None,
        },
        "data_live_lap": {
            "driver": {
                "lap": 7,
                "s1": 32.279,
                "v1": 234,
                "s2": 29.563,
                "v2": 286,
                "s3": 25.115,
                "vfl": 278,
            },
            "error": None,
        },
        "connection": {"label": "Connected"},
    }
    args = SimpleNamespace(year=2025, gp="Lusail", driver="NOR", lap=7)
    return args, wire, routes


@pytest.mark.parametrize("host_seq,agents_seq", [(3227, 3227), (3250, 3268), (3250, 1), (1, 3250)])
def test_trace_checks_accepts_independent_sequences_including_producer_restart(
    host_seq, agents_seq
):
    args, wire, routes = _coherent_trace()
    routes["tick"]["seq"] = host_seq
    routes["agents"]["seq"] = agents_seq

    checks = _evaluate_trace_checks(args, wire, routes)

    assert checks and all(checks.values()), checks


@pytest.mark.parametrize("channel", ["wire", "tick", "agents"])
@pytest.mark.parametrize("sequence", [0, True])
def test_trace_checks_rejects_invalid_sequences(channel, sequence):
    args, wire, routes = _coherent_trace()
    payload = wire if channel == "wire" else routes[channel]
    payload["seq"] = sequence

    assert not all(_evaluate_trace_checks(args, wire, routes).values())


def test_capture_routes_polls_each_window_without_using_the_other_sequence(monkeypatch):
    args, wire, routes = _coherent_trace()
    args.browser_host, args.browser_port = "127.0.0.1", 9999
    routes["agents"]["seq"] = 1
    requests = []
    responses = {
        "/api/tick?since=-1": routes["tick"],
        "/api/agents?since=-1&connection=Connected": routes["agents"],
        "/api/bulk?since=-1": {},
        "/api/live?since=-1": {},
        "/api/connection": routes["connection"],
    }

    def read_route(base_url, route):
        requests.append(route)
        return responses[route]

    monkeypatch.setattr(trace_pitwall_real_path, "_get_json", read_route)
    captured = trace_pitwall_real_path._capture_routes(args, wire)

    assert requests == list(responses)
    assert captured["correlation"]["host_tick_seq"] == 3250
    assert captured["correlation"]["agents_seq"] == 1


def test_trace_checks_rejects_null_or_mismatched_channels():
    corrupt = []

    args, wire, routes = _coherent_trace()
    case = deepcopy(wire)
    case["seq"] = None
    corrupt.append((args, case, routes))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["tick"]["arcade"]["lap"] = 8
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["agents"]["header"]["lap"] = "L 8/57"
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["tick"]["arcade"]["location"] = "Monza"
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["agents"]["orchestrator"]["action"] = "PIT NOW"
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(wire)
    case["strategy"]["start"]["no_llm"] = False
    corrupt.append((args, case, routes))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["data_bulk"]["driver"]["laps_revealed"] = 0
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["data_live_lap"]["driver"] = None
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["data_bulk"]["driver"]["laps"] = []
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["data_live_lap"]["driver"] = {"lap": 7}
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["agents"]["plan_timeline"]["current_lap"] = 6
    corrupt.append((args, wire, case))

    for args, wire, routes in corrupt:
        checks = _evaluate_trace_checks(args, wire, routes)
        assert not all(checks.values()), checks


def _sample_reports():
    wire = {
        "seq": 3227,
        "arcade": {
            "year": 2025,
            "location": "Lusail",
            "driver_main": "NOR",
            "lap": 7,
            "total_laps": 57,
            "race_order": ["PIA", "VER", "NOR"],
            "drivers": {"NOR": {"laps_completed": 6}},
        },
        "strategy": {
            "start": {"year": 2025, "gp": "Lusail", "driver": "NOR", "no_llm": True},
            "latest": {"lap_number": 7, "action": "STAY_OUT"},
        },
    }
    wire_bytes = json.dumps(wire, separators=(",", ":"), allow_nan=False).encode() + b"\n"
    driver = {
        "number": "4",
        "laps_revealed": 6,
        "stops": 0,
        "laps": [{"lap": 6, "lap_time": 86.957, "compound": "MEDIUM", "tyre_life": 6.0}],
    }
    live_driver = {
        "lap": 7,
        "s1": 32.279,
        "v1": 234,
        "s2": 29.563,
        "v2": 286,
        "s3": 25.115,
        "vfl": 278,
    }
    agents = {
        "seq": 3268,
        "header": {
            "session": "Lusail · 2025",
            "driver": "NOR",
            "lap": "L 7/57",
            "connection": "Connected",
        },
        "orchestrator": {"action": "STAY OUT", "plan": "stint continues - no pit window yet"},
        "plan_timeline": {
            "current_lap": 7,
            "total_laps": 57,
            "caption": "stint continues - no pit window yet",
        },
    }
    api_report = {
        "run_id": "trace-test",
        "status": "pass",
        "config": {"year": 2025, "gp": "Lusail", "driver": "NOR", "lap": 7},
        "wire": {
            "payload": wire,
            "sha256": hashlib.sha256(wire_bytes).hexdigest(),
            "bytes": len(wire_bytes),
        },
        "wire_sequence_samples": [3226, 3227],
        "host_routes": {
            "tick": deepcopy(wire),
            "agents": deepcopy(agents),
            "data_bulk": {
                "race": {"year": 2025, "location": "Lusail"},
                "available": True,
                "driver": deepcopy(driver),
                "error": None,
            },
            "data_live_lap": {"driver": deepcopy(live_driver), "error": None},
            "connection": {"label": "Connected"},
        },
    }
    browser_report = {
        "run_id": "trace-test",
        "status": "pass",
        "target": {"year": 2025, "gp": "Lusail", "driver": "NOR", "decision_lap": 7},
        "sequences": {"data_tick": 3290, "agents_view": 3312},
        "host_values": {
            "tick": deepcopy(wire),
            "bulk": {
                "available": True,
                "race": {"year": 2025, "location": "Lusail"},
                "drivers": {"NOR": deepcopy(driver)},
            },
            "live_lap": {"drivers": {"NOR": deepcopy(live_driver)}},
            "agents": deepcopy(agents),
        },
        "route_statuses": {
            "data": {"/api/tick": 200, "/api/bulk": 200, "/api/live": 200},
            "agents": {"/api/agents": 200},
        },
        "rendered": {
            "data": {
                "lap": "L 7/57",
                "connection": "Connected",
                "row": {
                    "position": "3",
                    "number": "4",
                    "driver": "NOR",
                    "sectors": ["32.279 234", "29.563 286", "25.115 278"],
                    "last": "1:26.957",
                    "tyre": "M 6",
                    "stops": "0",
                },
            },
            "agents": {
                "session": "Lusail · 2025",
                "driver": "NOR",
                "lap": "L 7/57",
                "connection": "Connected",
                "action": "STAY OUT",
                "plan": "stint continues - no pit window yet",
                "planTimeline": "Lap 7 of 57, medium laps 1 to 6",
            },
        },
        "errors": [],
        "screenshots": {"data": "data.png", "agents": "agents.png"},
    }
    api_report["host_routes"]["tick"]["seq"] = 3250
    browser_report["host_values"]["tick"]["seq"] = 3290
    browser_report["host_values"]["agents"]["seq"] = 3312
    return api_report, browser_report


def test_trace_report_verifier_accepts_independent_sequences_and_restart():
    api_report, browser_report = _sample_reports()
    payloads = (
        api_report["wire"]["payload"],
        api_report["host_routes"]["tick"],
        api_report["host_routes"]["agents"],
        browser_report["host_values"]["tick"],
        browser_report["host_values"]["agents"],
    )
    sequences = (3227, 3250, 1, 3290, 3312)
    for payload, sequence in zip(payloads, sequences):
        payload["seq"] = sequence
    browser_report["sequences"] = {"data_tick": sequences[3], "agents_view": sequences[4]}

    checks = evaluate_trace_reports(api_report, browser_report, {"data": 10, "agents": 10})

    assert checks and all(checks.values()), checks


def test_trace_report_verifier_rejects_invalid_sequence():
    api, browser = _sample_reports()
    browser["sequences"]["agents_view"] = 0
    checks = evaluate_trace_reports(api, browser, {"data": 10, "agents": 10})
    assert not all(checks.values()), checks


def test_trace_report_verifier_rejects_sequence_that_does_not_advance():
    api, browser = _sample_reports()
    api["wire_sequence_samples"] = [3226, 3227, 3227]
    checks = evaluate_trace_reports(api, browser, {"data": 10, "agents": 10})
    assert checks["wire_sequence_advanced"] is False


def test_screenshot_resolution_uses_the_audit_copy_for_stale_windows_paths():
    audit_dir = Path("documents/audits")
    screenshot = audit_dir / "TRACE_1252_trace-test_data.png"
    browser_report = {
        "screenshots": {
            "data": {
                "path": r"C:\Users\old-checkout\documents\audits\TRACE_1252_trace-test_data.png"
            }
        }
    }

    resolved = _resolve_screenshot_path(browser_report["screenshots"], "data", audit_dir)

    assert resolved == screenshot


def test_trace_report_verifier_rejects_stale_or_missing_evidence():
    cases = []

    api, browser = _sample_reports()
    browser["host_values"]["tick"]["seq"] = None
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["bulk"]["race"]["location"] = "Monza"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["bulk"]["drivers"]["NOR"]["laps"][0]["lap"] = 1
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    last = browser["host_values"]["bulk"]["drivers"]["NOR"]["laps"][0]
    last["compound"] = "HARD"
    last["tyre_life"] = 99
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["tick"]["arcade"]["year"] = 2024
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["agents"]["header"]["driver"] = "PIA"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["agents"]["header"]["lap"] = "L 1/57"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["agents"]["header"]["connection"] = "Disconnected"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["rendered"]["agents"]["planTimeline"] = "Lap 6 of 57"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    for field, value in (("position", "99"), ("number", "99"), ("driver", "PIA")):
        api, browser = _sample_reports()
        browser["rendered"]["data"]["row"][field] = value
        cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["rendered"]["data"]["row"]["sectors"] = []
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["live_lap"]["drivers"]["NOR"]["s1"] = 99.999
    browser["rendered"]["data"]["row"]["sectors"][0] = "99.999 234"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["rendered"]["data"]["row"]["last"] = "1:27.000"
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["host_values"]["live_lap"]["drivers"]["NOR"]["lap"] = 1
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    browser["errors"] = ["TypeError: render failed"]
    cases.append((api, browser, {"data": 10, "agents": 10}))

    api, browser = _sample_reports()
    cases.append((api, browser, {"data": 0, "agents": 10}))

    for api_report, browser_report, screenshot_sizes in cases:
        checks = evaluate_trace_reports(api_report, browser_report, screenshot_sizes)
        assert not all(checks.values()), checks
