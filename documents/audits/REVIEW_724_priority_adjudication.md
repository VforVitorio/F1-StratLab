# First-pass adjudication of the 2025 strategy-evidence queue

This is the conservative first pass for #724, the epic that tests whether the
deterministic decision layer can validly prefer a pit stop. It reviews the 150
unique events selected by `MEASURE_724_strategy_evidence_review.json`.

This report is a review aid, not a production label and not a claim that an
observed stop was optimal. The source inventory remains unchanged.

## Result

| proposed disposition | entries | meaning |
| --- | ---: | --- |
| `retain_regulation_constrained` | 51 | Real stop candidates in Monaco or Lusail, where the 2025 race rules constrained pit timing. Keep separate from elective strategy. |
| `exclude_mixed_penalty` | 18 | A pre-entry penalty or a documented penalty service is attached to the stop context. The strategic tyre decision cannot be isolated safely. |
| `needs_more_evidence` | 81 | A post-entry penalty, missing time anchor, or unknown timing discretion remains. Do not place these in the clean denominator. |
| **Total** | **150** | No event is promoted to a clean elective-strategy cohort. |

## How the 150 split was obtained

The queue has 55 entries from Monaco or Lusail, 48 entries outside those races
with unlinked penalty history, 3 entries without a UTC anchor, and 44 controls.
The categories above are deliberately based on the evidence boundary rather
than on the existing `STRATEGIC_TYRE_CHANGE` label.

### Monaco and Lusail

The 2025 Monaco race required two pit visits and three tyre sets. The official
Formula 1 report describes the mandatory format and the race's strategic effect,
while the official pit-stop summary lists the published stop laps. Those entries
remain regulation-constrained even when the tyre transition is real.

Sources:

- [Monaco 2025 race report](https://www.formula1.com/en/latest/article/norris-takes-victory-over-leclerc-and-piastri-in-gripping-monaco-grand-prix.4B7frXOoDY8UvKMu25Daoa)
- [Monaco 2025 pit-stop summary](https://www.formula1.com/en/results/2025/races/1261/monaco/pit-stop-summary)
- [Formula 1 explanation of the Monaco two-stop rule](https://www.formula1.com/en/latest/article/explained-what-is-the-new-two-stop-rule-for-the-monaco-grand-prix-and-how.1qropbdmR05S3BqgYsHtpE)

The 33 Monaco entries produce 32 regulation-constrained candidates and one
mixed-penalty case, George Russell lap 68. The latter has a pre-entry
drive-through record in the local official race-control evidence and is not an
isolated tyre decision.

The 2025 Lusail race had two mandatory pit stops and a 25-lap tyre limit after
the early Safety Car. The official Formula 1 race report describes the first
mandatory stop, the 25-lap limit, and the McLaren timing split. It also records
Bearman's unsafe-condition stop-and-go penalty and the retirements. The 22
selected entries produce 19 regulation-constrained candidates and three mixed
penalty cases:

- Bearman lap 32, unsafe-condition stop-and-go context
- Ocon lap 34, pre-entry false-start penalty
- Stroll lap 49, pit-lane-speeding penalty in the third-stop context

Sources:

- [Qatar 2025 race report](https://www.formula1.com/en/latest/article/verstappen-wins-qatar-gp-as-title-battle-goes-to-abu-dhabi-with-oscar-piastri.5KlYT7q8OcrJ7AnMALjkxJ)
- [Qatar 2025 team reports](https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-qatar-2025.5YOtPlFnoG66V0rN5oqXxj)

### Unlinked penalty history outside the special races

The 48 entries with unlinked penalty history all have a paired telemetry stop,
but that does not make them strategic. Fourteen have at least one official
penalty message timestamped before the reconstructed pit entry. They are
`exclude_mixed_penalty` because the penalty context was already available at the
decision boundary and the local tyre signal cannot separate the causes.

The remaining 34 have penalty evidence only after the reconstructed pit entry.
That evidence cannot be used to rewrite the earlier decision retrospectively.
They remain `needs_more_evidence` until the penalty lifecycle and the stop timing
are checked against the official pit summary and race context. A late penalty is
not proof that the earlier stop was forced, and it is not proof that the stop was
elective either.

The local race-control evidence is the official sanction source for this pass.
For example, the Formula 1 Mexico City report confirms Sainz's later
drive-through for repeated pit-lane speeding, which is why his penalty history
cannot be attached blindly to an earlier tyre stop.

Source:

- [Mexico City 2025 race report](https://www.formula1.com/en/latest/article/norris-seals-commanding-win-in-action-packed-mexico-city-gp-to-take-world.5ztiajHhdtqagu0qQLx0vS)

### Missing anchors and controls

Three priority entries from Miami have no UTC anchor: Ocon lap 23, Antonelli
lap 25, and Sainz lap 25. They remain `needs_more_evidence` because the public
pre-entry cutoff cannot be reconstructed honestly.

The 44 controls are all paired telemetry entries with no linked penalty history
in this export. They remain `needs_more_evidence` because a clean tyre change
does not prove that the team had timing discretion or that the observed lap was
optimal.

## Decision

Do not recalculate the #715 denominator, the diagnostic of real pit entries that
the decision layer did not recommend, from this first pass. The 51
regulation-constrained entries must stay separate, the 18 mixed-penalty entries
must stay excluded, and the 81 pending entries need a temporal adjudication
before they can support a clean contrast.

The public relative-pace and factual-state measures remain shadow evidence. No
traffic, rejoin, or tyre-value term is justified by this queue alone. Both
five-lap horizons remain unchanged.

## Next step

Resolve the 81 pending entries in two passes:

1. Use official pit-stop summaries and race reports to resolve the 34
   post-entry penalty rows without leaking post-entry facts into the decision
   boundary.
2. Adjudicate timing discretion for those rows and the 44 controls from
   pre-entry evidence only. Keep the 3 unanchored Miami rows outside any
   timing-based denominator unless a valid anchor is recovered.

Only after that review should the development protocol be frozen on 2023-2024
and the final contrast be run on frozen 2025 data.
