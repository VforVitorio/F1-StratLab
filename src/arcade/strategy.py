"""SSE consumer and strategic state machine.

The `SimConnector` class implemented in Phase 3 spawns a background
thread that POSTs to the backend `/api/v1/strategy/simulate` endpoint,
parses the event stream, and pushes `StartEvent` / `LapDecision` /
`ErrorEvent` / `RunSummary` payloads into a thread-safe queue. The
`StrategyState` dataclass aggregates the latest decision plus histories
(MC confidence, action sequence, agent firings) so that the overlay
draw functions in `overlays.py` can be pure and stateless.

Keeping the network I/O off the Arcade frame thread is load-bearing:
the backend produces roughly one event per simulated lap plus a
heartbeat every 15 laps, while Arcade runs at 25 FPS; a blocking read
would stall the render loop.
"""

from __future__ import annotations
