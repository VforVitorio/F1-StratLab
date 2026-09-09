# Public relative pace before pit entry

This is an offline comparison for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.
It compares a raw completed-lap time difference with relative gap movement from public timing. It does not score the team's strategy and does not change the production scorer.

- generated `2026-09-09T07:34:15+00:00`
- source: `documents\audits\MEASURE_724_public_timing_precut.json`
- cutoff: `all public interval dates <= approximate pit_in_utc`
- completed lap: `pit_in_lap - 1`
- maximum snapshot age: **10 seconds**
- maximum pair timestamp skew: **5 seconds**
- maximum absolute pair-gap change: **5 seconds**
- input entries: **150**
- unique input events: **126**
- measured entries: **126**

## Status

| status | entries |
| --- | ---: |
| `comparable_pre_cutoff_pair` | 81 |
| `pre_lap_pair_has_pit_transition` | 10 |
| `public_current_stale_or_skewed` | 29 |
| `public_gap_discontinuity` | 2 |
| `public_pair_order_changed` | 2 |
| `public_previous_stale_or_skewed` | 2 |

Only `comparable_pre_cutoff_pair` rows, **81**, can be used for a first agreement or correlation measure.
The raw-lap value is `subject_lap_time - car_ahead_lap_time`, so negative means our car was faster. The public value is the change in the pair gap over approximately one subject lap, scaled to seconds per lap; positive means the subject lost relative time.

## Agreement

- Pearson correlation: **0.5851**
- Spearman correlation: **0.4699**
- same non-zero sign: **63.0%**

## Anchor sensitivity

Moving the approximate cutoff 2 seconds earlier leaves **78** paired comparable entries and changes the non-zero public-sign result on **10** of them.
This is a stability check, not a correction to the OpenF1 anchor. It limits how strongly this shadow signal can be interpreted.

## Decision

Rows involving an in-lap or out-lap transition, a public order change, or a pair-gap discontinuity stay out of the agreement calculation. Keep the two signals as shadow evidence and do not add a traffic or rejoin cost to the scorer from this export alone. The retrospective rejoin benchmark remains a separate measure.
