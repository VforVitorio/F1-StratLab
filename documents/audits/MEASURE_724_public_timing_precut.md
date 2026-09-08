# Public timing before the pit-entry cutoff

This is a data-quality measurement for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.
It asks whether the cached public timing feed contains a latest snapshot at or before each sampled pit entry. It does not use later timing to explain the decision.

- generated `2026-09-08T18:39:55+00:00`
- source: `documents\audits\MEASURE_724_strategy_evidence_review.json`
- timing source: `data/raw/2025/*/intervals.parquet`
- cutoff: `date <= approximate pit_in_utc`
- freshness threshold for the primary set: **10 seconds**
- sampled entries: **77**

## Coverage

| status | entries |
| --- | ---: |
| `no_anchor` | 1 |
| `precut_snapshot` | 69 |
| `precut_snapshot_stale` | 7 |

`precut_snapshot` means that the public timing feed had an observation for the same driver no more than 10 seconds before the reconstructed entry. It does not prove that the team had already committed to stop, nor that the snapshot contains every rival.
`precut_snapshot_stale` has a valid pre-cutoff observation, but it is older than the primary freshness threshold and stays out of the first relative-pace comparison.
`no_anchor` is kept separate from missing public timing. OpenF1 lap start timestamps are approximate and six source entries remain unanchored in the evidence inventory.

## Decision

Use only the `precut_snapshot` rows, 69 of 77, in the next relative-pace comparison. Keep stale snapshots, the unanchored row, the rejoin benchmark, and any post-entry measurements separate. No production scorer change is justified by coverage alone.
