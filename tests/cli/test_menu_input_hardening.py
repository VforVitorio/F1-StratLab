"""Regression tests for race-scoped CLI selections and lap validation."""

import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest

from scripts import f1_cli, f1_sim
from scripts.cli import pickers


def test_driver_and_rival_pickers_use_the_selected_race(tmp_path, monkeypatch):
    parquet = tmp_path / "laps.parquet"
    parquet.touch()
    frame = pd.DataFrame(
        [
            {
                "Driver": "DOO",
                "Team": "Alpine",
                "LapNumber": 1,
                "LapTime": None,
                "Position": None,
                "TyreLife": 1,
            },
            {
                "Driver": "NOR",
                "Team": "McLaren",
                "LapNumber": 3,
                "LapTime": 90.0,
                "Position": 1,
                "TyreLife": 3,
            },
            {
                "Driver": "PIA",
                "Team": "McLaren",
                "LapNumber": 5,
                "LapTime": 91.0,
                "Position": 2,
                "TyreLife": 5,
            },
        ]
    )
    monkeypatch.setattr(pickers, "_resolve_raw_laps_path", lambda *_args: parquet)
    monkeypatch.setattr(pd, "read_parquet", lambda *_args, **_kwargs: frame.copy())
    selections = []

    def choose(_title, options):
        selections.append(options)
        return 1 if len(selections) == 1 else 0

    monkeypatch.setattr(pickers, "_arrow_pick", choose)

    assert pickers.pick_driver("Driver", tmp_path, "Miami_Gardens") == ("PIA", "McLaren")
    assert "DOO" not in pickers._load_driver_data(tmp_path, "Miami_Gardens")
    assert pickers.pick_rival_code(tmp_path, "Miami_Gardens", "PIA") == "NOR"
    assert selections == [
        ["NOR  ·  McLaren", "PIA  ·  McLaren"],
        ["NOR  ·  McLaren"],
    ]


def test_lap_bound_comes_from_raw_race_data(tmp_path, monkeypatch):
    race_dir = tmp_path / "raw" / "2025" / "Suzuka"
    race_dir.mkdir(parents=True)
    (race_dir / "laps.parquet").touch()
    raw_laps = pd.DataFrame(
        [
            {
                "Driver": "NOR",
                "Team": "McLaren",
                "LapNumber": 52,
                "LapTime": 92.0,
                "Position": 3,
                "TyreLife": 7,
            },
            {
                "Driver": "NOR",
                "Team": "McLaren",
                "LapNumber": 53,
                "LapTime": 93.0,
                "Position": 3,
                "TyreLife": 8,
            },
            {
                "Driver": "NOR",
                "Team": "McLaren",
                "LapNumber": 54,
                "LapTime": None,
                "Position": None,
                "TyreLife": 9,
            },
            {
                "Driver": "VER",
                "Team": "Red Bull",
                "LapNumber": 53,
                "LapTime": 91.0,
                "Position": 1,
                "TyreLife": 8,
            },
        ]
    )
    parquet_reads = []
    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda path, columns: parquet_reads.append((path, columns)) or raw_laps.copy(),
    )

    drivers = pickers._load_driver_data(tmp_path, "Suzuka", raw_dir=race_dir.parent)

    assert max(drivers["NOR"][1]) == 53
    assert max(drivers["VER"][1]) == 53
    assert drivers["NOR"][1] == frozenset({52, 53})
    assert "ZZZ" not in drivers
    assert "NOR" in drivers
    assert parquet_reads[0][0] == race_dir / "laps.parquet"


def test_pick_laps_reprompts_for_malformed_reversed_and_out_of_range_values(monkeypatch, capsys):
    answers = iter(["oops", "40-15", "9-11", "9" * 4301, "8-9", "5-7"])
    monkeypatch.setattr(pickers.Prompt, "ask", lambda *_args, **_kwargs: next(answers))

    assert pickers.pick_laps(max_lap=10, valid_laps=frozenset({1, 3, 5, 7, 10})) == "5-7"
    output = capsys.readouterr().out
    assert "positive lap" in output
    assert "greater than or equal" in output
    assert "ends at lap 10" in output
    assert "too large" in output
    assert "no complete lap" in output


@pytest.mark.parametrize(("answer", "expected"), [("7", "7"), ("all", None), ("", None)])
def test_pick_laps_accepts_single_lap_and_all(answer, expected, monkeypatch):
    monkeypatch.setattr(pickers.Prompt, "ask", lambda *_args, **_kwargs: answer)

    assert pickers.pick_laps(max_lap=10) == expected


def test_f1_strat_version_exits_before_the_wizard(monkeypatch, capsys):
    monkeypatch.setattr(f1_cli, "_run_wizard", lambda: pytest.fail("wizard started"))
    monkeypatch.setattr("sys.argv", ["f1-strat", "--version"])

    with pytest.raises(SystemExit) as exc:
        f1_cli.main()

    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("f1-strat ")


def test_f1_strat_rejects_unknown_arguments_before_the_wizard(monkeypatch, capsys):
    monkeypatch.setattr(f1_cli, "_run_wizard", lambda: pytest.fail("wizard started"))
    monkeypatch.setattr("sys.argv", ["f1-strat", "--not-a-menu-option"])

    with pytest.raises(SystemExit) as exc:
        f1_cli.main()

    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_f1_sim_version_and_bad_laps_exit_before_simulation_import():
    version = subprocess.run(
        [sys.executable, "scripts/f1_sim.py", "--version"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    help_output = subprocess.run(
        [sys.executable, "scripts/f1_sim.py", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    malformed = subprocess.run(
        [sys.executable, "scripts/f1_sim.py", "Melbourne", "NOR", "McLaren", "--laps", "oops"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    assert version.returncode == 0
    assert version.stdout.startswith("f1-sim ")
    assert help_output.returncode == 0
    assert "--no-llm" in help_output.stdout
    assert "--interval SECONDS" in help_output.stdout
    assert "--radio-every N" in help_output.stdout
    assert "f1-sim Sakhir NOR McLaren --laps 15-25" in help_output.stdout
    assert malformed.returncode == 2
    assert "--laps must be a positive lap number" in malformed.stderr
    assert "Traceback" not in malformed.stderr


def test_f1_sim_rejects_lap_numbers_beyond_python_integer_limit():
    parser = f1_sim.argparse.ArgumentParser(prog="f1-sim")

    with pytest.raises(SystemExit) as exc:
        f1_sim._parse_laps("9" * 4301, parser)

    assert exc.value.code == 2


def test_f1_sim_rejects_ranges_outside_driver_data(monkeypatch, capsys):
    parser = f1_sim.argparse.ArgumentParser(prog="f1-sim")
    lap_range = f1_sim._parse_laps("8-11", parser)
    assert lap_range == (8, 11)

    lookups = []

    def load_driver_data(*args):
        lookups.append(args)
        return {"NOR": ("McLaren", frozenset({1, 5, 10}))}

    monkeypatch.setattr(pickers, "_load_driver_data", load_driver_data)
    monkeypatch.setattr(
        "sys.argv",
        [
            "f1-sim",
            "Melbourne",
            "NOR",
            "McLaren",
            "--raw-dir",
            "custom-raw",
            "--featured",
            "custom-featured.parquet",
            "--laps",
            "8-11",
        ],
    )
    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    assert lookups[0][3] == Path("custom-raw")
    assert "this driver's data ends at lap 10" in capsys.readouterr().err


def test_f1_sim_rejects_ranges_without_a_complete_lap(monkeypatch, capsys):
    monkeypatch.setattr(
        pickers,
        "_load_driver_data",
        lambda *_args: {"NOR": ("McLaren", frozenset({1, 3, 10}))},
    )
    monkeypatch.setattr(
        "sys.argv",
        ["f1-sim", "Melbourne", "NOR", "McLaren", "--laps", "8-9"],
    )

    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    assert "contains no complete lap" in capsys.readouterr().err


def test_f1_sim_normalizes_driver_and_rival_codes_before_delegation():
    args = f1_sim.argparse.Namespace(
        gp_name="Melbourne",
        driver="nor",
        team="McLaren",
        year=2025,
        raw_dir=None,
        featured=None,
        no_first_run=True,
        laps="5",
        no_llm=True,
        provider=None,
        interval=0.0,
        radio_every=0,
        no_real_radios=True,
        whisper_model="turbo",
        rival="ver",
        verbose=False,
    )

    assert f1_sim._runner_arguments(args) == [
        "Melbourne",
        "NOR",
        "McLaren",
        "--no-first-run",
        "--laps",
        "5",
        "--no-llm",
        "--no-real-radios",
        "--rival",
        "VER",
    ]


def test_f1_sim_rejects_driver_missing_from_raw_race(monkeypatch, capsys):
    monkeypatch.setattr(
        pickers,
        "_load_driver_data",
        lambda *_args: {"NOR": ("McLaren", frozenset({1, 57}))},
    )
    monkeypatch.setattr("sys.argv", ["f1-sim", "Miami_Gardens", "ZZZ", "Alpine"])

    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    assert "driver ZZZ is not present at Miami_Gardens" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments,expected_error",
    [
        (["Silverstone", "BOR", "McLaren", "--laps", "3"], "does not match driver BOR"),
        (
            ["Silverstone", "BOR", "Kick Sauber", "--rival", "ZZZ"],
            "rival ZZZ is not present at Silverstone",
        ),
        (
            ["Silverstone", "BOR", "Kick Sauber", "--rival", ""],
            "the rival code cannot be empty",
        ),
        (
            ["Silverstone", "BOR", "Kick Sauber", "--rival", "bor"],
            "the rival must be a different driver",
        ),
    ],
)
def test_f1_sim_rejects_wrong_team_or_rival_before_runner(
    monkeypatch, capsys, arguments, expected_error
):
    monkeypatch.setattr(
        pickers,
        "_load_driver_data",
        lambda *_args: {
            "BOR": ("Kick Sauber", frozenset({1, 2, 3})),
            "VER": ("Red Bull Racing", frozenset({1, 2, 3})),
        },
    )
    monkeypatch.setattr("sys.argv", ["f1-sim", *arguments])
    runner = ModuleType("scripts.run_simulation_cli")
    runner.main = lambda: pytest.fail("invalid arguments reached the simulation runner")
    monkeypatch.setitem(sys.modules, "scripts.run_simulation_cli", runner)

    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    assert expected_error in capsys.readouterr().err


def test_f1_sim_reports_missing_raw_data_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(pickers, "_load_driver_data", lambda *_args: None)
    monkeypatch.setattr(
        "sys.argv",
        [
            "f1-sim",
            "Melbourne",
            "NOR",
            "McLaren",
            "--raw-dir",
            "missing-raw-root",
            "--laps",
            "5",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    output = capsys.readouterr().err
    assert "cannot read raw lap data for Melbourne" in output
    assert "Traceback" not in output
