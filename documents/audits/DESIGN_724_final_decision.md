# Final design for issue #724, the stop-decision epic

**Status:** `NO-GO` for a scorer change after the final evidence contrast and
independent review on 2026-09-14.

## Decision in plain language

The evidence does not justify adding a traffic or position term to the production
scorer. It also does not justify changing either five-lap horizon. The final
review still cannot separate a clean elective strategy cohort from stops caused
by rules, penalties, damage, or missing timing evidence.

The safest design is therefore a staged change:

1. Freeze the 2025 evidence boundary and keep the 81 pending sample events out of
   the clean denominator.
2. Keep the full 2025 decision-modes run as a reproducible system baseline, not as
   proof that the observed stops were optimal.
3. Do not change the scorer until a separate measurement validates the admissible
   continuation and the tyre model's future-horizon error.

This is a candidate scorer change, not permission to ship it before the contrast.

## What the evidence says

The first adjudication of the 150-event review sample found:

| result | events | treatment |
| --- | ---: | --- |
| regulation-constrained | 51 | retain as a separate Monaco or Lusail cohort |
| mixed with penalty context | 18 | exclude from the elective-strategy cohort |
| still unresolved | 81 | keep outside every clean denominator |

The 81 unresolved events contain 34 post-entry penalty records, three Miami
entries without a recoverable UTC anchor, and 44 controls for which timing
discretion is not established. Official Formula 1 race reports and pit-stop
summaries were checked for the pending race contexts. They confirm published
stops and, in several cases, damage or penalty services, but a retrospective
summary cannot prove what information was available at the reconstructed
pre-entry cutoff.

That uncertainty is not a reason to guess. A tyre transition proves that the set
changed. It does not prove that the timing was elective or optimal.

## Candidate scorer change after the missing measurements

The remaining structural gap is terminal tyre value. The current wear term prices
the laps immediately around the candidate decision, but an elective stop can also
be valuable because it avoids carrying a worn set to the end of the race.

For every candidate with no residual mandatory stop:

```text
terminal_cost(plan) = min(
    cost of the best admissible later stop,
    cost of running the current set to the flag
)
```

The later-stop option must start from the tyre state at the end of the current
window and use a forecast validated for the remaining race, not merely the
current `deg_cost_s` reading. If the required tyre evidence is unavailable, the
terminal increment stays disabled and the existing `FRESH_GAIN` fallback remains
in force. No new hand-tuned weight is introduced.

The implementation must apply the terminal comparison at the shared terminal
layer in both scorer paths. It must not charge a rival's pending stop as a normal
position loss, and it must not alter the existing cliff, pit-loss, margin-cap, or
random-number sequence.

## Independent review

An independent high-reasoning review inspected the repository and evidence
package. The verdict was `NO-GO` for implementation:

- Excluding the 81 pending events does not create a clean elective cohort; the
  remaining controls still have `timing_discretion=unknown`.
- `deg_cost_s` is a current differential against an early same-stint reference,
  not a validated forecast of the next tyre set or of the remaining race.
- `mandatory_stop_pending=False` only says that the currently modelled
  two-compound obligation is not pending. It does not prove that running to the
  flag is legal or strategically admissible at every circuit and race phase.
- There is no single shared terminal layer today. The projection path applies
  `_terminal_gaps`, while the legacy path aggregates in
  `_run_mc_simulation`; they need adapters around one pure residual-cost rule,
  not a superficial copy of the same formula.
- A continuation cannot choose the best future outcome after seeing the future.
  The admissible action and its risk aggregation must be fixed before the
  simulated outcome is known, including the possibility of more than one later
  stop.

The independent review also executed 109 focused tests and six real no-LLM
race-lap checks. Those checks validate the current code paths, not an
implementation that does not yet exist.

## Explicit non-goals

- Do not widen `WINDOW_LAPS` or `DECISION_WINDOW_LAPS` from five.
- Do not tune `deg_cost_s` against the old missed-stop rate.
- Do not add absolute position or traffic cost while the public feed lacks an
  authoritative absolute position field and the pre-entry relative-pace result is
  anchor-sensitive.
- Do not use post-entry penalties, later damage, or the final race result as
  information available before the stop.
- Do not recalculate issue #715 from the old 198-stop or 65% figures. Those are
  retired baselines.

## Measurements required before implementation

The next implementation branch must prove all of the following:

1. Measure future-horizon tyre error from the end of a decision window to the
   chequered flag, with 2025 kept out of calibration.
2. Define admissible continuation states explicitly: no obligation, one
   obligation, circuit-required stops, and more than one future stop.
3. Freeze the action choice before sampling the continuation outcome and preserve
   the existing E/P10/P90 risk aggregation.
4. Verify the same residual-cost function through both scorer adapters without
   demanding equality of their different currencies.
5. Prove missing tyre evidence, negative readings, and a real zero reading remain
   distinct.
6. Run the real 2025 no-LLM path and inspect the output after the measurement,
   before any production change.

The future implementation is high complexity: a new validated continuation
measurement, one pure residual-cost rule, two scorer adapters, legality and
obligation tests, and a real simulation check. No code branch should be opened
until those measurements pass. No new dependency is needed.

## Current position

Issue #376, the circuit-cluster test-season leak measurement, and issue #729, the
decision-window measurement, are already complete in `dev`. The next work remains
inside issue #724 and issue #715: measure the missing future-horizon tyre and
continuation contracts before deciding whether any scorer change is warranted.

The pending evidence decision is recorded in
`REVIEW_724_pending_evidence.md`. The 2025 run is reproducible in
`documents/eval_reports/decision_modes.{md,json}` and reproduced the committed
semantic results: 573 eligible events, 203 scored, 34.0% within one lap, and
`masked` coverage.

## Official source set consulted

- [Miami 2025 race report](https://www.formula1.com/en/latest/article/piastri-wins-from-norris-and-russell-as-mclaren-seal-commanding-1-2-in-miami.6Vfaf5zEMOKmPHzHdkGdof)
- [Miami 2025 pit-stop summary](https://www.formula1.com/en/results/2025/races/1259/miami/pit-stop-summary)
- [Baku 2025 race report](https://www.formula1.com/en/latest/article/verstappen-claims-dominant-azerbaijan-win-over-russell-and-sainz-after.gT4fbKTwpl3dI79nDmrHS.gT4fbKTwpl3dI79nDmrHS)
- [Bahrain 2025 race report](https://www.formula1.com/en/latest/article/piastri-storms-to-controlled-victory-in-bahrain-grand-prix-ahead-of-russell.47YQh0Ex2gkZcx58fRaRqJ)
- [China 2025 race report](https://www.formula1.com/en/latest/article/piastri-beats-norris-and-russell-to-victory-in-chinese-grand-prix-with.CpcwOmMwzcZGjM33Wkv8V)
- [British Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-dramatic-wet-dry-british-gp-from-piastri-and-hulkenberg.1puOD82avOZ8I0sca7fvLJ)
- [Austrian Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/norris-fends-off-piastri-for-austrian-gp-victory-in-thrilling-race-long.2CH71wVvRP1FaU8s04Tj7f)
- [São Paulo 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-thrilling-sao-paulo-gp-from-antonelli-as-verstappen-climbs-to.4T0Y5xGNn1MOVegzhGTqAx4T0Y5xGNn1MOVegzhGTqAx)
- [Las Vegas 2025 race report](https://www.formula1.com/en/latest/article/verstappen-beats-norris-for-dominant-las-vegas-gp-victory-as-piastri.6u1Op0SO7YQa2bwJOq8DVI)
- [Monaco 2025 race report](https://www.formula1.com/en/latest/article/norris-takes-victory-over-leclerc-and-piastri-in-gripping-monaco-grand-prix.4B7frXOoDY8UvKMu25Daoa)
- [Qatar 2025 race report](https://www.formula1.com/en/latest/article/verstappen-wins-qatar-gp-as-title-battle-goes-to-abu-dhabi-with-oscar-piastri.5KlYT7q8OcrJ7AnMALjkxJ)
