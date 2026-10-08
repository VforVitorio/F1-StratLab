# scripts/cli — Interactive CLI launcher

Interactive arrow-key wrapper around `scripts/f1_sim.py`, which validates the
arguments before delegating to `scripts/run_simulation_cli.py`. Driver and rival
menus use participants from the selected race's
`data/raw/<year>/<gp>/laps.parquet`; team and lap limits come from those same
rows. No simulation logic lives here.

## How to run

```
python scripts/f1_cli.py
```

## Modes

- **Single Driver** — full per-lap simulation for one driver in one race.
- **Head-to-Head** — full simulation for Driver 1; Driver 2 is tracked as a
  rival in the *same* run via the `--rival` flag passed to
  `run_simulation_cli.py` (no second subprocess).

## Module layout

- `theme.py` — F1 brand palette (`F1_RED`, `F1_AMBER`, `F1_GREEN`, `F1_WHITE`,
  `F1_GRAY`), shared Rich `console` singleton, and the ASCII welcome banner.
- `pickers.py` — `_arrow_pick` primitive (Windows `msvcrt` + POSIX `termios`
  branches), all interactive prompts (`pick_mode`, `pick_race`, `pick_driver`,
  `pick_rival_code`, `pick_laps`, `pick_provider`,
  `ask_again`), plus `discover_races(repo_root, year)` and the
  race-scoped `_load_driver_data(repo_root, gp_name)` parquet lookup.
- `runner.py` — `build_sim_cmd(...)` builds the argv for
  `f1_sim.py`, `run_subprocess(cmd)` executes it with
  `PYTHONIOENCODING=utf-8` + `PYTHONUTF8=1`, and `run_single` / `run_h2h` are
  the two wizard flows.
- `../f1_cli.py` — top-level entry point. Loops `pick_mode` →
  `run_single` / `run_h2h` until the user picks Quit.

## Adding a new picker

1. Write the prompt helper in `pickers.py` (use `_arrow_pick` for menus, or
   `Prompt.ask` for free-text).
2. Wire the call into `runner.py:run_single` and/or `run_h2h`, and forward
   the value into `build_sim_cmd` as a new kwarg + corresponding `cmd.extend`.

## Windows note

The package enables VT-100 processing on Windows via `ctypes`
`SetConsoleMode(GetStdHandle(-11), 7)` so ANSI escape codes (cursor moves,
colors, the red `❯` cursor) render correctly in `cmd.exe` and Windows
Terminal. The call is a no-op on non-Windows platforms.
