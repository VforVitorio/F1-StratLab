# Public pair-state accuracy before pit entry

This is an offline state-quality measure for #724, the epic to make the deterministic decision layer able to prefer a stop.
It compares the raw directly-ahead pair with public timing available before the approximate pit entry. It does not score strategy and does not change production.

- generated `2026-09-09T07:41:27+00:00`
- source: `documents\audits\MEASURE_724_public_timing_precut.json`
- cutoff: `all public interval dates <= approximate pit_in_utc`
- raw reference: `pit_in_lap - 1, directly-ahead pair at the raw lap line`
- maximum snapshot age: **10 seconds**
- maximum pair timestamp skew: **5 seconds**
- input entries: **150**
- unique input events: **126**
- measured entries: **126**

## Status

| status | entries |
| --- | ---: |
| `comparable_pre_cutoff_pair` | 95 |
| `public_pair_stale_or_skewed` | 31 |

## Accuracy on comparable pairs

- comparable pairs: **95**
- public pair keeps the raw order: **0.9158**
- pair-order mismatches: **8**
- signed pair-gap error mean: **-0.4162 seconds**
- absolute pair-gap error median / p90: **0.65 / 3.0452 seconds**

The OpenF1 interval cache has no official absolute position column, so absolute public position error is intentionally not reported. Sorting all cars by gap-to-leader would mix asynchronous updates and lapped states. This pair-level measure is the strongest factual comparison supported by the cached fields.

## Decision

Keep this separate from the retrospective rejoin benchmark and from relative-pace correlation. Do not add a traffic, rejoin, or tyre-value term to the production scorer from this measure alone.
