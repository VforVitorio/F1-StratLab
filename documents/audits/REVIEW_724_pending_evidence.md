# Pending evidence decision for issue #724, the stop-decision epic

**Date:** 2026-09-14

This note freezes the treatment of the 81 unresolved events in the 150-event
review sample. It does not alter the 573-event source inventory and it does not
feed any label into the production scorer.

## Decision

No pending event is promoted to a clean elective-strategy stop.

| pending group | events | treatment |
| --- | ---: | --- |
| penalty evidence published after the reconstructed entry | 34 | keep unresolved; post-entry facts cannot be used at the decision boundary |
| Miami entries without a recoverable UTC lap anchor | 3 | keep outside timing-based denominators |
| controls without established timing discretion | 44 | keep unresolved; a tyre change alone does not prove an elective decision |
| **total** | **81** | **excluded from the clean contrast** |

The three unanchored entries are:

- `2025:10033:31:23:1` OCO lap 23
- `2025:10033:12:25:1` ANT lap 25
- `2025:10033:55:25:1` SAI lap 25

The stable event records and their evidence fields remain in
`MEASURE_724_strategy_evidence_review.json`. This note records the decision
without rewriting that source export.

## What the official sources can and cannot establish

The official Formula 1 race reports and pit-stop summaries confirm the published
stop lap and, for several pending contexts, describe a later penalty, damage,
or a normal tyre strategy. They are retrospective summaries. They do not state
the complete information available to the team immediately before the
reconstructed pit entry, so they cannot turn a post-entry observation into
pre-entry ground truth.

Examples from the pending contexts:

- [Miami 2025 race report](https://www.formula1.com/en/latest/article/piastri-wins-from-norris-and-russell-as-mclaren-seal-commanding-1-2-in-miami.6Vfaf5zEMOKmPHzHdkGdof) and [Miami pit-stop summary](https://www.formula1.com/en/results/2025/races/1259/miami/pit-stop-summary) confirm the published stop laps, but do not provide a complete pre-entry decision record.
- [Baku 2025 race report](https://www.formula1.com/en/latest/article/verstappen-claims-dominant-azerbaijan-win-over-russell-and-sainz-after.gT4fbKTwpl3dI79nDmrHS.gT4fbKTwpl3dI79nDmrHS) separates the race events from the later incident context, but the summary remains retrospective.
- [Spanish Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/piastri-leads-mclaren-1-2-from-norris-in-spanish-gp-amid-late-race-drama-for.2t1WkW9NVeMzJbOIkpM8u8), [British Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-dramatic-wet-dry-british-gp-from-piastri-and-hulkenberg.1puOD82avOZ8I0sca7fvLJ), and [Austrian Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/norris-fends-off-piastri-for-austrian-gp-victory-in-thrilling-race-long.2CH71wVvRP1FaU8s04Tj7f) describe damage, changing conditions, or penalties that make a clean timing comparison unsafe for the affected entries.
- [São Paulo 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-thrilling-sao-paulo-gp-from-antonelli-as-verstappen-climbs-to.4T0Y5xGNn1MOVegzhGTqAx4T0Y5xGNn1MOVegzhGTqAx), [Las Vegas 2025 race report](https://www.formula1.com/en/latest/article/verstappen-beats-norris-for-dominant-las-vegas-gp-victory-as-piastri.6u1Op0SO7YQa2bwJOq8DVI), and [Dutch Grand Prix 2025 race report](https://www.formula1.com/en/latest/article/piastri-wins-as-norris-faces-late-race-retirement-in-dramatic-dutch-grand.5gVVQeQH0zjZk9hl6k6wvv) likewise confirm race incidents and stop contexts without exposing the team's full pre-entry information set.

This is enough to exclude unsafe cases. It is not enough to assert that the
remaining controls were optimal or even elective. That distinction is the
reason the clean denominator stays conservative.

## Consequence for the final contrast

The final contrast for issue #715, the diagnostic of real pit entries that the
decision layer did not recommend, must report the 81-event exclusion explicitly.
It may use the existing frozen 2025 decision-modes run as the system baseline,
but it must not present the 81 events as validated strategy labels.

The scorer remains unchanged for this phase. Keep `WINDOW_LAPS = 5` and
`DECISION_WINDOW_LAPS = 5`. If a later implementation is justified, the
candidate remains the terminal tyre-liability comparison documented in
`DESIGN_724_final_decision.md`; it must be reviewed independently before code
changes.
