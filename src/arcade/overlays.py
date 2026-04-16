"""Strategic draw functions — badges, bars, banners, animations, summary.

This module concentrates every draw call that renders information
derived from the SSE strategy stream. State mutation and rendering are
kept separate by design: `SimConnector` in `strategy.py` updates the
`StrategyState`, and the functions here consume an immutable snapshot
of that state without mutating it. Phases 3, 4, and 5 populate this
module tier by tier:

* Phase 3 — Tier A: action badge, scenario score bars, confidence bar,
  pace / risk chips, compound halo, gap readout.
* Phase 4 — Tier B: pit plan strip, undercut chip, guardrail banner,
  RCM event banner, radio alert flash, agent firing dots, reasoning
  text, error overlay.
* Phase 5 — Tier C and animations: `PitAnimation` three-phase
  entry / stop / rejoin, and `draw_summary_scene` for the end-of-run
  cards.
"""

from __future__ import annotations
