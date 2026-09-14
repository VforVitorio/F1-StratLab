# Independent gate for the terminal tyre-liability design

**Date:** 2026-09-14  
**Reviewed commit:** `b574d785`  
**Verdict:** `NO-GO` for a production scorer change

This was an independent, read-only review of the terminal continuation design
for issue #724, the stop-decision epic. The reviewer did not edit files, commit,
use the internet, or call an external model.

## Findings

### P1: the evidence has no clean elective cohort

The 81 pending events remain 34 post-entry penalty records, three unanchored
Miami events, and 44 controls with `timing_discretion=unknown`. Excluding them
does not turn the remaining events into proof of an elective or optimal stop.
Consequently, the current 2025 run is a system baseline, not a strategic-truth
denominator.

### P1: `deg_cost_s` is not a future tyre forecast

The field is the current differential against an early same-stint reference. It
does not predict the next compound or the cost of carrying the current set to
the chequered flag. The existing 2025 quality gate reports 0.712 seconds per
lap mean absolute error and +0.221 seconds per lap signed bias for the gated
reference path. Those figures were not remeasured in this gate and remain a
separate measurement requirement before extrapolating the signal to a longer
horizon.

### P1: `mandatory_stop_pending=False` is not full admissibility

That field describes the currently modelled two-compound obligation. It does not
encode every circuit-specific requirement, the number of future stops, or the
legality of running to the flag at every race phase. A terminal option needs an
explicit continuation contract.

### P1: the two scorers do not share one terminal layer

The projection path adjusts `_terminal_gaps` in
`src/agents/position_projection.py`, while the legacy path aggregates candidate
outcomes in `src/agents/strategy_orchestrator.py`. A future implementation needs
one pure residual-cost rule with two adapters. Copying the formula into both
places would create another silent divergence.

### P2: future choices cannot use future outcomes

The continuation action must be selected before its outcome is sampled. It must
also represent more than one later stop when the race context requires it. An
`E[min(...)]` calculation that chooses the best future alternative after seeing
the draw is optimistic and is not a valid decision policy.

## Evidence executed by the gate

- 109 focused tests passed.
- Six real `RaceReplayEngine -> build_race_state -> run_lap(profile="no-llm")`
  checks passed across Budapest, Monaco, and Lusail.
- The checks exercised mandatory-stop states, unknown tyre cost, existing
  obligation netting, and the current production paths. They do not validate a
  terminal implementation, because none exists.

## Required before reopening the change

1. Measure future-horizon tyre error without fitting on 2025.
2. Define continuation admissibility for zero, one, and multiple required stops,
   including Monaco and Lusail rules.
3. Freeze continuation choices before sampling and retain the existing risk
   aggregation.
4. Add one pure residual-cost function with explicit projection and legacy
   adapters.
5. Test `True`, `False`, and `None` obligations, no legal continuation, SC/VSC,
   tyre ages, missing cost, negative cost, and real zero cost.
6. Re-run the real 2025 path and inspect the output before any scorer merge.

Until those conditions are met, keep the scorer unchanged, keep both horizons at
five laps, and keep the 81 pending evidence events outside the clean contrast.
