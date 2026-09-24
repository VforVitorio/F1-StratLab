import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

from scripts.trace_pitwall_real_path import _evaluate_trace_checks, _matches_target
from scripts.verify_pitwall_trace import evaluate_trace_reports


def test_trace_matches_only_the_configured_real_decision_coordinates():
    tick = {
        "arcade": {"year": 2025, "location": "Lusail", "driver_main": "NOR"},
        "strategy": {"latest": {"lap_number": 7, "action": "STAY_OUT"}},
    }

    assert _matches_target(tick, 2025, "Lusail", "NOR", 7)
    assert not _matches_target(tick, 2024, "Lusail", "NOR", 7)
    assert not _matches_target(tick, 2025, "Lusail", "PIA", 7)
    assert not _matches_target(tick, 2025, "Lusail", "NOR", 8)


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
    agents = {
        "seq": 3227,
        "header": {
            "session": "Lusail · 2025",
            "driver": "NOR",
            "lap": "L 7/57",
            "connection": "Connected",
        },
        "orchestrator": {"action": "STAY OUT"},
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


def test_trace_checks_accepts_one_coherent_wire_host_data_and_agents_tick():
    args, wire, routes = _coherent_trace()

    checks = _evaluate_trace_checks(args, wire, routes)

    assert checks and all(checks.values()), checks


def test_trace_checks_rejects_null_or_mismatched_channels():
    corrupt = []

    args, wire, routes = _coherent_trace()
    case = deepcopy(wire)
    case["seq"] = None
    corrupt.append((args, case, routes))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["tick"]["seq"] = 3228
    corrupt.append((args, wire, case))

    args, wire, routes = _coherent_trace()
    case = deepcopy(routes)
    case["agents"]["seq"] = 3228
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
        "seq": 3227,
        "header": {
            "session": "Lusail · 2025",
            "driver": "NOR",
            "lap": "L 7/57",
            "connection": "Connected",
        },
        "orchestrator": {"action": "STAY OUT"},
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
        "target": {"gp": "Lusail", "driver": "NOR", "decision_lap": 7},
        "sequences": {"data_tick": 3227, "agents_view": 3227, "same_seq": True},
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
            },
        },
        "errors": [],
        "screenshots": {"data": "data.png", "agents": "agents.png"},
    }
    return api_report, browser_report


def test_trace_report_verifier_accepts_correlated_values_and_real_page_evidence():
    api_report, browser_report = _sample_reports()

    checks = evaluate_trace_reports(api_report, browser_report, {"data": 10, "agents": 10})

    assert checks and all(checks.values()), checks


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
