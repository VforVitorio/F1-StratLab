# 2025 strategy-evidence review export

This export is a review queue for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.
It keeps the existing #715 sample, the missed-pit-call diagnostic population, unchanged and does not feed any field into the scorer.

- generated `2026-09-09T07:30:11+00:00`
- source: `documents\audits\MEASURE_724_stop_purpose.json`
- `WINDOW_LAPS`: `5`
- `DECISION_WINDOW_LAPS`: `5`
- sample entries: **573**
- reviewed entries: **36**
- unreviewed entries: **537**
- rows with unlinked penalty history: **70**
- deterministic stratified sample: **150**
- unique event IDs in review sample: **150**
- priority events: **106**
- control events: **44**

## Review dispositions

| disposition | entries |
| --- | ---: |
| `exclude_mixed_penalty` | 9 |
| `exclude_non_comparable` | 18 |
| `exclude_penalty_only` | 3 |
| `retain_external_candidate` | 4 |
| `retain_regulation_constrained` | 2 |
| `unreviewed` | 537 |

The 36 manually reviewed entries come from the external review in `REVIEW_1215_doubtful_cases.md`.
The remaining 537 entries stay unreviewed even when their current primary label says `STRATEGIC_TYRE_CHANGE`.
A tyre transition is evidence that a set changed, not proof that the timing was an elective strategic decision.

## How to use the export

The JSON contains one row per source event with its stable `event_id`, current evidence fields, all penalty evidence for the same car and session, and the IDs that were not attached by the current stop join.
The review sample first includes every unreviewed event with unlinked penalty history, a Monaco or Lusail entry, or no UTC anchor. It then adds up to 44 deterministic controls from the other races, balancing cohort, neutralisation, stop sequence, and race phase. Event IDs are unique and selection uses a stable hash rather than lexical driver or lap order.

Penalty timestamps use the existing approximate OpenF1 lap anchor when available. A pre-entry timestamp is evidence that race control had published the message before the reconstructed entry, not proof that the team had chosen that stop.

## Next measurement

Review the flagged penalty-history rows and the stratified sample manually. Then compare zero-cost relative pace with public timing estimates using the same pre-entry cutoff. Keep the retrospective rejoin benchmark separate from this decision-evidence measure.
