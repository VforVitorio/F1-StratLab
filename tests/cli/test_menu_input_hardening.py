"""Regression tests for race-scoped CLI selections and lap validation."""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from scripts import f1_cli, f1_sim
from scripts.cli import pickers


def test_driver_and_rival_pickers_use_the_selected_race(tmp_path, monkeypatch):
    parquet = tmp_path / "laps.parquet"
    parquet.touch()
    frame = pd.DataFrame(
        [
            {"GP_Name": "Miami", "Driver": "NOR", "Team": "McLaren"},
            {"GP_Name": "Miami", "Driver": "PIA", "Team": "McLaren"},
            {"GP_Name": "Silverstone", "Driver": "VER", "Team": "Red Bull"},
        ]
    )
    monkeypatch.setattr(pickers, "_resolve_laps_parquet_path", lambda *_args: parquet)
    monkeypatch.setattr(pd, "read_parquet", lambda *_args, **_kwargs: frame.copy())
    selections = []

    def choose(_title, options):
        selections.append(options)
        return 1 if len(selections) == 1 else 0

    monkeypatch.setattr(pickers, "_arrow_pick", choose)

    assert pickers.pick_driver("Driver", tmp_path, "Miami_Gardens") == ("PIA", "McLaren")
    assert pickers.pick_rival_code(tmp_path, "Miami_Gardens", "NOR") == "PIA"
    assert selections == [["NOR  ·  McLaren", "PIA  ·  McLaren"], ["PIA  ·  McLaren"]]


def test_lap_bound_comes_from_raw_race_data(tmp_path, monkeypatch):
    race_dir = tmp_path / "raw" / "2025" / "Suzuka"
    race_dir.mkdir(parents=True)
    (race_dir / "laps.parquet").touch()
    raw_laps = pd.DataFrame(
        [
            {"Driver": "NOR", "LapNumber": 52},
            {"Driver": "NOR", "LapNumber": 53},
            {"Driver": "VER", "LapNumber": 53},
        ]
    )
    parquet_reads = []
    monkeypatch.setattr(
        pd,
        "read_parquet",
        lambda path, columns: parquet_reads.append((path, columns)) or raw_laps.copy(),
    )

    assert pickers.max_lap_for_driver(tmp_path, "Suzuka", "NOR", raw_dir=race_dir.parent) == 53
    assert pickers.max_lap_for_driver(tmp_path, "Suzuka", "ZZZ", raw_dir=race_dir.parent) == 0
    assert parquet_reads[0][0] == race_dir / "laps.parquet"


def test_pick_laps_reprompts_for_malformed_reversed_and_out_of_range_values(monkeypatch, capsys):
    answers = iter(["oops", "40-15", "9-11", "5-7"])
    monkeypatch.setattr(pickers.Prompt, "ask", lambda *_args, **_kwargs: next(answers))

    assert pickers.pick_laps(max_lap=10) == "5-7"
    output = capsys.readouterr().out
    assert "positive lap" in output
    assert "greater than or equal" in output
    assert "ends at lap 10" in output


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
    assert malformed.returncode == 2
    assert "--laps must be a positive lap number" in malformed.stderr
    assert "Traceback" not in malformed.stderr


def test_f1_sim_rejects_ranges_outside_driver_data(monkeypatch, capsys):
    parser = f1_sim.argparse.ArgumentParser(prog="f1-sim")
    lap_range = f1_sim._parse_laps("8-11", parser)
    assert lap_range == (8, 11)

    lookups = []

    monkeypatch.setattr(pickers, "_load_driver_data", lambda *_args: {"NOR": "McLaren"})

    def max_lap(*args):
        lookups.append(args)
        return 10

    monkeypatch.setattr(pickers, "max_lap_for_driver", max_lap)
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
    assert lookups[0][4] == Path("custom-raw")
    assert "this driver's data ends at lap 10" in capsys.readouterr().err


def test_f1_sim_rejects_driver_missing_from_raw_race(monkeypatch, capsys):
    monkeypatch.setattr(pickers, "_load_driver_data", lambda *_args: {"NOR": "McLaren"})
    monkeypatch.setattr("sys.argv", ["f1-sim", "Miami_Gardens", "DOO", "Alpine"])

    with pytest.raises(SystemExit) as exc:
        f1_sim.main()

    assert exc.value.code == 2
    assert "driver DOO is not present at Miami_Gardens" in capsys.readouterr().err
