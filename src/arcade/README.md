# `src/arcade/` — race replay + strategy dashboard

2D race replay (pyglet via the `arcade` library) plus the PySide6
dashboard subprocess spawned from the same command. One invocation of
`f1-arcade` opens three top-level windows: the arcade replay, the
strategy dashboard (orchestrator card + six sub-agent cards + reasoning
tabs), and the live telemetry window (2×2 circuit-comparison grid).

## Run

```bash
f1-arcade --viewer --year 2025 --round 3 --driver VER \
          --team "Red Bull Racing" --driver2 LEC --strategy
```

Or without the strategy pipeline (replay-only):

```bash
f1-arcade --viewer --year 2025 --round 3 --driver VER --team "Red Bull Racing"
```

## Public docs

- **End-user quick start:** [`docs/arcade/quick-start.md`](../../docs/arcade/quick-start.md)
- **Dashboard architecture (developer deep dive):** [`docs/arcade/dashboard.md`](../../docs/arcade/dashboard.md)
- **Why the arcade duplicates the N31 orchestrator body:** [`docs/arcade/strategy-pipeline.md`](../../docs/arcade/strategy-pipeline.md)
- **Visual overview:** [`docs/diagrams/arcade_3window_architecture.drawio`](../../docs/diagrams/arcade_3window_architecture.drawio)

## Layout

```
src/arcade/
├── main.py              # CLI entry point (f1-arcade)
├── app.py               # F1ArcadeView — pyglet replay loop, TCP broadcast
├── data.py              # SessionLoader + SessionData + FrameData
├── config.py            # Palette, GP calendars, constants
├── strategy.py          # SimConnector + StrategyState + DTOs
├── strategy_pipeline.py # Arcade-local duplicate of the N31 orchestrator body
├── stream.py            # TelemetryStreamServer (stdlib TCP)
├── overlays.py          # WeatherPanel, LeaderboardPanel, DriverInfoPanel, …
├── track.py             # Track polyline renderer (DRS zones, cars)
├── views.py             # MenuView (interactive configurator)
└── dashboard/           # PySide6 subprocess (see docs/arcade/dashboard.md)
```

The arcade **does not depend on the FastAPI backend at runtime**. The
strategy pipeline runs in a background thread inside this process using
`RaceReplayEngine` + the featured-laps parquet + the local
`strategy_pipeline.run_strategy_pipeline` wrapper. See
[`docs/arcade/strategy-pipeline.md`](../../docs/arcade/strategy-pipeline.md)
for why the N31 body is duplicated here rather than extended upstream.
