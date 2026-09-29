from types import SimpleNamespace

from scripts.measure_715_diagnostic import _attach_laps, _canonical_race


def _record(lap: int, race: str = "Las Vegas") -> dict:
    return {
        "year": 2025,
        "race": race,
        "driver": "NOR",
        "lap": lap,
        "mandatory_stop_pending": "false",
        "rival_pending_true": 1,
        "rival_pending_false": 2,
        "rival_pending_unknown": 0,
        "deg_cost_known": True,
        "pit_minus_stay": -1.0,
        "stay_dominates": True,
    }


def test_diagnostic_uses_the_shared_gp_keyspace():
    assert _canonical_race("Las_Vegas") == "Las Vegas"
    assert _canonical_race("Miami_Gardens") == "Miami"


def test_diagnostic_joins_aliases_and_excludes_post_stop_laps():
    verdict = SimpleNamespace(
        year=2025,
        race="Las_Vegas",
        driver="NOR",
        actual_lap=30,
        bucket="no_call_in_window",
    )

    rows = _attach_laps([_record(25), _record(29), _record(30), _record(35)], [verdict])

    assert rows[0]["evaluated_laps"] == 2
    assert rows[0]["mandatory_stop_pending"]["false"] == 2
    assert rows[0]["rival_pending"]["true"] == 2
