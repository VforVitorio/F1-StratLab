# Arcade Dashboard Architecture

Developer-level reference for the PySide6 dashboard that ships alongside
the arcade replay. Written for someone who plans to extend or modify
either window (add a new sub-agent card, add a new telemetry chart,
retheme the palette, change the wire protocol).

Phase 3.5 Proceso B shipped thirteen files under
`src/arcade/dashboard/` plus a new `src/arcade/strategy_pipeline.py` and
the rewritten `src/arcade/strategy.py::SimConnector`. The arcade
autolaunches the dashboard subprocess when the user enables strategy
mode; the user never runs a second command.

---

## Three-window split

Three windows, two processes.

- **Arcade replay** — `pyglet`-backed, owned by `F1ArcadeView`.
  Drives the simulation loop (`RaceReplayEngine.replay()` in a
  background thread), owns the `StrategyState`, runs
  `TelemetryStreamServer` on `127.0.0.1:9998`, and renders the track.
- **Strategy dashboard** — `PySide6` `MainWindow`. Orchestrator card,
  six sub-agent cards with embedded `pyqtgraph` charts, scenario bars,
  six-tab reasoning panel.
- **Telemetry window** — `PySide6` `TelemetryWindow`. Standalone
  `QMainWindow` with a 2x2 grid of `pyqtgraph` plots (Delta, Speed,
  Brake, Throttle) in F1-broadcast style.

The pyglet window runs in the arcade process. The two Qt windows live
together inside one subprocess spawned by the arcade.

---

## Process topology

```
┌────────────────────────────────┐        ┌──────────────────────────────┐
│ Arcade process (pyglet)        │        │ Dashboard subprocess (Qt)    │
│                                │  TCP   │                              │
│  F1ArcadeView                  │◄──────►│  QApplication                │
│   ├─ RaceReplayEngine thread   │ 127.   │   ├─ MainWindow              │
│   ├─ StrategyState (_lock)     │ 0.0.1: │   │    + TelemetryStreamClt  │
│   └─ TelemetryStreamServer     │ 9998   │   └─ TelemetryWindow         │
│        accept thread           │        │         + TelemetryStreamClt │
└────────────────────────────────┘        └──────────────────────────────┘
```

Two processes, not three. Both Qt windows share the same
`QApplication` event loop and Python interpreter — spawning a third
process just to host the telemetry window would cost an extra Python
startup (roughly 300 ms), another TCP socket, and another set of
imported heavy modules (`torch`, `transformers`) with no gain. A single
`QApplication` can own many top-level windows; each window instantiates
its own `TelemetryStreamClient` (a `QThread` that opens its own TCP
socket to the same server), which means closing one window does not
cascade to the other.

The arcade process stays free of PySide6. Importing Qt into the pyglet
process would double the memory footprint and couple the two event
loops. Keeping Qt out of the arcade is the reason `stream.py` is
stdlib-only; the subprocess launch preserves that separation.

---

## Package layout tour

`src/arcade/dashboard/` groups the Qt-side code. Every file owns one
concern and does not import sibling files outside of documented
entry points.

### `theme.py`

Colour palette, compound pill colour map, flag chip styles, monospace
font stack, and the `apply_dark_palette(app)` helper. The palette
mirrors the arcade window's `styles.py` so the two processes look
unified even though they share no runtime code. Pirelli compound colours
use the canonical hexes (C1 white, C2 yellow, C3 red, INTERMEDIATE
green, WET blue). The `hex_str(color)` helper converts a `QColor` into
`#RRGGBB` for embedding in stylesheet strings.

### `stream_client.py`

`TelemetryStreamClient` is a `QThread` that opens a TCP socket to
`127.0.0.1:9998`, reads newline-delimited JSON payloads, and emits a
`data_received(dict)` Signal on the main Qt thread. Ported from Tom
Shaw's `f1_replay/f1-race-replay/src/services/stream_client.py` and
trimmed to match the arcade's broadcast shape. Reconnects automatically
with exponential backoff on socket errors; exposes
`connection_changed(str)` so the header bar can light a chip green/red.

### `window.py`

`MainWindow` composes the strategy surface. A header bar (40 px) shows
session label, driver, connection chip, playback chip, and lap counter.
A central `QSplitter(Qt.Horizontal)` holds two panels at `540 / 740`.
The status bar shows the last error from the stream client and the last
payload size. `MainWindow.on_data_received` is the fan-out router: it
pulls `latest.per_agent`, dispatches each sub-agent dict to the matching
card, drives the orchestrator card from `latest.recommendation`, feeds
the scenario bars from `latest.scenario_scores`, and appends to the
reasoning tabs from `latest.reasoning_per_agent`.

### `orchestrator_card.py`

The flagship card. Four visual elements:

- **Action badge** — large pill coloured by `classify_action`: green
  for STAY_OUT, amber for PIT_NOW, cyan for UNDERCUT, magenta for
  OVERCUT, red for ALERT.
- **Confidence bar** — `QProgressBar` with a `qlineargradient`
  stylesheet painting a traffic-light gradient (red→amber→green) from
  0 to 100, matching the CLI section 3 colour mapping.
- **Pace and Risk chips** — two smaller pills, recoloured per regime
  (PUSH / NEUTRAL / MANAGE / LIFT_AND_COAST for pace; AGGRESSIVE /
  BALANCED / DEFENSIVE for risk).
- **Plan strip** — one line: "Plan: PIT lap 28, fit C3, target UNDERCUT
  HAM". The compound is rendered as an inline pill using the
  `theme.compound_color(c)` map.
- **Guardrail line** — shown only when the orchestrator's MC winner was
  overridden by the no-LLM hard guard (covered in
  [`project_strategic_guardrails.md`](../memory/project_strategic_guardrails.md)).

### `agent_card.py`

Reusable widget: headline label, body `QLabel` (rich text with small
monospace), and a reserved chart slot that accepts any `QWidget`. The
Pace and Tire cards slot in their `pyqtgraph` plots via
`card.set_chart(widget)`. The Pit and RAG cards dim to 60 % opacity
when the conditional agent did not fire on the current lap.

### `agent_formatters.py`

Six pure functions:
`format_pace`, `format_tire`, `format_situation`, `format_pit`,
`format_radio`, `format_rag`. Each takes a sub-agent output dict and
returns `(headline: str, body_lines: list[str])`. The implementation
mirrors the CLI inference panel section rules (§1.1 through §1.6 in
`scripts/run_simulation_cli.py`); keeping the mapping pure means the
formatters are importable anywhere and unit-testable without Qt.

### `pace_chart.py` and `tire_chart.py`

`pyqtgraph.PlotWidget` subclasses embedded in their cards.

- `PaceChart` plots actual lap time, predicted lap time, and a
  shaded P10/P90 confidence band per lap. Accumulates history locally
  since the broadcast trims `per_agent` to the latest lap only.
- `TireChart` plots tyre life by compound with vertical lines at stint
  boundaries and horizontal dashed lines at the estimated cliff laps
  (`laps_to_cliff_p50` per compound).

Both charts scroll the x-axis to show the last 20 laps.

### `scenario_bars.py`

Four horizontal bars for STAY_OUT / PIT_NOW / UNDERCUT / OVERCUT. The
raw Monte Carlo scores are sometimes negative (when a candidate is
worse than the current-lap baseline). The widget shifts the minimum to
zero, then normalises to [0, 1], so the visual remains readable while
the tooltip exposes the raw score. The bar matching the orchestrator's
chosen action gets a brighter border.

### `reasoning_tabs.py`

`QTabWidget` with six tabs: Pace, Tire, Situation, Radio, Pit, RAG.
Each tab is a `QTextEdit` with a `QSyntaxHighlighter` subclass that
paints regex patterns in accent colours — compound codes (C1..C5,
INTERMEDIATE, WET), flag keywords (SAFETY CAR, VSC, YELLOW), numbers
with units (seconds, laps), and action verbs (pit, stay out, undercut).
The tabs render the `reasoning_per_agent` fields emitted by the
orchestrator.

### `telemetry_panel.py`

The 2x2 grid of telemetry plots. Lives in its own module so
`TelemetryWindow` can host it as the central widget without pulling in
the strategy-side imports.

### `telemetry_window.py`

Standalone `QMainWindow`. Owns its own `TelemetryStreamClient`, hosts a
`TelemetryPanel` as the central widget, and renders a header bar with
the same chip styling as `MainWindow`. Closing this window does not
close the strategy window; both react independently to the same
broadcast.

### `__main__.py`

Entry point for `python -m src.arcade.dashboard`. Boots a
`QApplication`, applies the dark palette, instantiates both windows,
positions them side by side (`strategy.move(40, 40)` and the telemetry
window to the right), and runs the event loop. The arcade process
spawns this module as a subprocess when strategy mode is enabled; a
developer can also run it directly for standalone iteration against any
arcade that is broadcasting on port 9998.

---

## Wire protocol

The arcade broadcasts one JSON dict per frame, roughly 10 Hz, as a
newline-terminated payload. The full shape:

```json
{
  "arcade": {
    "session": { "year": 2025, "round": 3, "location": "Suzuka", "lap": 18, "total_laps": 53 },
    "driver": { "code": "VER", "team": "Red Bull Racing", "position": 2 },
    "driver2": { "code": "LEC", "team": "Ferrari", "position": 4 },
    "telemetry": {
      "main":  { "speed": 312.4, "throttle": 0.98, "brake": 0.0, "gear": 7, "drs": true },
      "rival": { "speed": 308.1, "throttle": 0.95, "brake": 0.0, "gear": 7, "drs": false }
    },
    "delta_s": -0.412
  },
  "strategy": {
    "start": { "gp": "Suzuka", "year": 2025, "driver": "VER", "lap_start": 1, "lap_end": 53 },
    "latest": {
      "lap": 18,
      "recommendation": { "action": "STAY_OUT", "confidence": 0.73, "pace_mode": "NEUTRAL", "risk": "BALANCED", "plan": "..." },
      "scenario_scores": { "STAY_OUT": 0.21, "PIT_NOW": -0.14, "UNDERCUT": 0.08, "OVERCUT": -0.02 },
      "per_agent": {
        "pace":      { "lap_time_pred": 93.42, "ci_p10": 92.81, "ci_p90": 94.03, "delta_vs_prev": -0.18 },
        "tire":      { "laps_to_cliff_p50": 12, "laps_to_cliff_p10": 8, "laps_to_cliff_p90": 17, "warning_level": "MONITOR" },
        "situation": { "overtake_prob": 0.42, "sc_prob_3lap": 0.11, "threat_level": "MODERATE" },
        "radio":     { "alerts": [], "radio_events": [], "rcm_events": [] },
        "pit":       { "action": "HOLD", "compound_recommendation": "C3", "stop_duration_p50": 2.8, "undercut_prob": 0.31 },
        "rag":       { "answer": "", "articles": [] }
      },
      "reasoning_per_agent": { "pace": "...", "tire": "...", "situation": "...", "radio": "...", "pit": "...", "rag": "..." },
      "active": ["pit"],
      "guardrail_override": false
    }
  },
  "playback": { "state": "PLAY", "speed": 1.0 }
}
```

Top-level keys: `arcade`, `strategy`, `playback`. The dashboard's fan-out
router reads from these three roots and nothing else — extending the
protocol is additive (new fields are ignored by old clients).

The broadcast omits `per_agent` history on purpose; the dashboard
accumulates history locally in `PaceChart._history` and
`TireChart._history` to keep each frame small. The TCP framing is one
`json.dumps(dict).encode() + b"\n"` per frame, so clients read with
`sockfile.readline()`.

---

## Extension points

### Adding a new sub-agent card

1. Extend the wire protocol: add the new agent's output dict under
   `strategy.latest.per_agent.<name>`.
2. Add a formatter in `agent_formatters.py`
   (`format_<name>(payload) -> (headline, body_lines)`).
3. Instantiate an `AgentCard(title=...)` inside `MainWindow._build_right_panel`
   and add it to the `QGridLayout`.
4. In `MainWindow.on_data_received`, dispatch the new payload into the
   formatter and call `card.set_content(headline, body)`.
5. If the card needs a chart, create a `pyqtgraph` subclass following
   `pace_chart.py` and attach it with `card.set_chart(widget)`.

### Adding a new telemetry chart

The 2x2 grid in `telemetry_panel.py` is hard-coded for the broadcast
palette. To add a fifth plot (for example steering angle), extend it to
3x2 or replace the `QGridLayout` with a `QSplitter` of `QSplitter`s.
Each plot reads from `arcade.telemetry.main` / `arcade.telemetry.rival`
in `TelemetryPanel.on_data_received`; the new key has to be emitted on
the arcade side first.

### Changing the palette

`theme.py` is the only place colour literals live. Every widget imports
`ACCENT`, `DANGER`, `SUCCESS`, `WARNING`, `TEXT_SECONDARY`, and the
compound colour map from there. A full retheme means editing `theme.py`
plus the matching `styles.py` on the arcade side so both processes
agree.

### Changing the wire protocol

`src/arcade/strategy.py::SimConnector.build_snapshot_dict` assembles the
broadcast payload; `TelemetryStreamServer.broadcast` writes it.
Add new fields at the deepest nested level you can — the fan-out router
in `window.py` is tolerant of missing keys, so both sides can deploy
asynchronously.

---

## Threading model

Five threads cooperate.

- **Arcade main thread** (pyglet) — runs the `F1ArcadeView.on_update`
  tick, mutates the `StrategyState` under `_lock`, and calls
  `TelemetryStreamServer.broadcast(snapshot)`.
- **SimConnector background thread** — iterates
  `RaceReplayEngine.replay()` and calls
  `run_strategy_pipeline(race_state, laps_df)` per lap. Writes its
  output into the shared `StrategyState`. One thread, one lap at a time,
  so the main pyglet thread never blocks on LLM inference.
- **TelemetryStreamServer accept thread** — daemon thread inside the
  arcade process. Blocks on `server_socket.accept()` and appends
  accepted client sockets to `_clients`. Broadcast iterates and prunes
  dead sockets opportunistically.
- **Qt main thread** (dashboard subprocess) — runs `QApplication.exec()`.
  Receives `data_received` signals on this thread and drives all UI
  updates. Never touches the network.
- **QThread stream clients** (one per top-level Qt window) — each owns
  its own TCP socket, reads with `sockfile.readline()`, parses JSON,
  emits the `data_received(dict)` signal. Signals marshal onto the main
  thread automatically thanks to Qt's queued-connection semantics.

The `StrategyState._lock` is the only contended mutex. The pyglet
thread takes it to read (for the broadcast); the SimConnector thread
takes it to write. Neither holds it across I/O.

---

## Related reading

- [`docs/arcade-quick-start.md`](arcade-quick-start.md) — end-user
  launch instructions.
- [`docs/strategy-pipeline-arcade.md`](strategy-pipeline-arcade.md) —
  why the arcade keeps a local copy of the orchestrator body.
- [`docs/architecture.md`](architecture.md) — N25--N31 multi-agent
  architecture.
- [`src/agents/README.md`](../src/agents/README.md) — agent module map
  and output dataclasses.
- [`docs/diagrams/`](diagrams/) — drawio sources; the forthcoming
  `arcade_3window_architecture.drawio` visualises the process topology
  described above.
