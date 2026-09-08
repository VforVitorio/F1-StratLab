# Public relative pace before pit entry

This is an offline comparison for the strategy-evidence phase of #724, the epic to make the deterministic decision layer able to prefer a stop.
It compares a raw completed-lap time difference with relative gap movement from public timing. It does not score the team's strategy and does not change the production scorer.

- generated `2026-09-08T18:50:04+00:00`
- source: `documents\audits\MEASURE_724_public_timing_precut.json`
- cutoff: `all public interval dates <= approximate pit_in_utc`
- completed lap: `pit_in_lap - 1`
- maximum snapshot age: **10 seconds**
- maximum pair timestamp skew: **5 seconds**
- input entries: **77**
- measured entries: **69**

## Status

| status | entries |
| --- | ---: |
| `comparable_pre_cutoff_pair` | 48 |
| `public_current_stale_or_skewed` | 17 |
| `public_previous_stale_or_skewed` | 4 |

Only `comparable_pre_cutoff_pair` rows, **48**, can be used for a first agreement or correlation measure.
The raw-lap value is `subject_lap_time - car_ahead_lap_time`, so negative means our car was faster. The public value is the change in the pair gap over approximately one subject lap, scaled to seconds per lap; positive means the subject lost relative time.

## Agreement

- Pearson correlation: **-0.1493**
- Spearman correlation: **0.3982**
- same non-zero sign: **66.7%**

## Decision

Keep the two signals as a shadow comparison until their sign and agreement are measured on the comparable rows. Do not add a traffic or rejoin cost to the scorer from this export alone. The retrospective rejoin benchmark remains a separate measure.
