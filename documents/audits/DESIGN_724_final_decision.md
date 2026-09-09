# Final design for issue #724, the stop-decision epic

**Status:** design approved for implementation only after the final evidence contrast.

## Decision in plain language

The evidence does not justify adding a traffic or position term to the production
scorer. It also does not justify changing either five-lap horizon. The current
system must first finish separating real strategic choices from stops caused by
rules, penalties, damage, or missing timing evidence.

The safest design is therefore a staged change:

1. Freeze the 2025 evidence boundary and keep the 81 pending sample events out of
   the clean denominator.
2. Run the final contrast for issue #715, the diagnostic of real pit entries that
   the decision layer did not recommend, using only the resulting comparable
   cohort.
3. If the scorer still needs a change, add the missing terminal tyre liability:
   compare the best admissible later stop with running to the flag, using the
   already validated tyre-cost signal only when it is available.

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

## Proposed scorer change after the contrast

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

The later-stop option must use the same tyre-cost units already consumed by the
scorer. If the tyre reference is unavailable, the existing `FRESH_GAIN` fallback
remains in force. No new hand-tuned weight is introduced.

The implementation must apply the terminal comparison at the shared terminal
layer in both scorer paths. It must not charge a rival's pending stop as a normal
position loss, and it must not alter the existing cliff, pit-loss, margin-cap, or
random-number sequence.

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

## Verification required before implementation

The next implementation branch must prove all of the following:

1. The 2025 comparison is frozen before scorer edits.
2. The clean cohort, exclusions, missingness, and uncertainty are reported by
   reason, not hidden in one aggregate.
3. A no-residual candidate changes only because the terminal tyre comparison is
   active.
4. A mandatory-stop candidate does not receive a second stop obligation through
   the terminal term.
5. Missing tyre evidence follows the old fallback exactly.
6. The legacy and projection paths produce the same terminal decision for the
   same simplified state.
7. The real 2025 no-LLM simulation path still runs and its output is inspected.

The implementation is medium-high complexity: one shared scoring concept, two
existing scorer paths, their tests, the frozen evaluation report, and a real
simulation check. It needs one independent Astra review before the code is
merged. No new dependency or new abstraction is needed.

## Next issue

The next actionable item after this evidence gate is issue #376, the audit that
measures whether the circuit-cluster labels leak test-season information. It is
offline, does not alter production behaviour, and unblocks a paper claim. The
stop-decision epic remains open until the final contrast supports either the
terminal-liability change or a documented no-change decision.

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
