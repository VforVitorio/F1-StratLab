# PR5 overtake-domain gate

Audit date: 2026-08-05. Parent branch: `fix/overtake-domain-gate`. Telemetry submodule: `fix/overtake-domain-nullable`.

This gate checked claims A-I, the new inference helper, and consumers of `overtake_prob`. It records that branch's results; verify the current code before treating the findings as open. Earlier evidence is in `data-wiring.md`, `801-artefacts.md`, `../implementation/pr3-gp-keyspace-sweep.md`, and `../implementation/pr4-pace-inputs.md`.

## Claim results

| Claim | Result |
|---|---|
| A. 2.5 s training bound | Confirmed. The pair builder, calibrator, and temporal split use the same bounded dataset. |
| B. 43.1% outside the bound | Reproduced on the served 2025 frame: 8,816 of 20,449 position-adjacent pairs. |
| C. No numeric `overtake_prob` input to MC | Confirmed by consumer sweep. The MC reads SC and VSC fields only. |
| D. Neutralisation override | Confirmed. Neutralised laps use 0.0 before output construction, even when the parsed probability is `None`. |
| E. Out-of-domain effect | Confirmed as down-only. Of 8,816 pairs, 57 could lose MEDIUM; none could lose HIGH. |
| F. N12 feature parity | Refuted in part. The arithmetic matches, but the helper uses a different lap series. |
| G. Cluster `-1` sentinel | Confirmed. LightGBM treats it as missing, not cluster 0. |
| H. Parser | Found cross-call field tearing when the model calls the tool more than once. |
| I. Webapp route scope | The `/situation` route passes a season-wide frame; lookups select the first GP in frame order. |

## Measurements and defects

### Training and served populations

N11 drops pairs beyond 2.5 s before labeling (`.nb_py/N11_overtake_eda.py:233-235`). The exported parquet contains 28,494 rows, has a maximum gap of 2.5 s, and has no rows beyond the bound. N12 fits Platt calibration on 2024 and tests on 2025 using that same dataset (`.nb_py/N12_overtake_model.py:655-657`).

The served-frame reproduction used `augment_featured_laps(laps_featured_2025, 2025)`: 22,760 rows across 24 GPs, with no NaN in `Time_s` or `LapTime_s`. It produced 20,449 position-adjacent pairs, 8,816 outside 2.5 s (43.1%). Both `race_situation_agent.run_from_state` and `no_llm.py` pair by `position == driver_pos - 1` without a gap filter, matching the measured population.

The PR table's median 2.06 s and p90 9.11 s describe the full adjacent-pair population. For the outside-bound subset, the median is 5.16 s and p90 is 15.13 s.

### Out-of-domain scores

The real model and calibrator scored all 8,816 out-of-domain 2025 pairs. Calibrated probability ranged from 0.002 to 0.554, with median 0.003. No pair reached `high_overtake=0.65`; 57 reached `medium_overtake=0.40` (0.65% of the out-of-domain set). Those pairs can move from MEDIUM to LOW under the new gate unless the SC term raises the band independently. In-domain rates were 8.10% at 0.40 and 3.34% at 0.65.

The Platt floor is 0.001831, which prints as `0.002`. A literal `P(overtake) = 0.000` cannot come from this model and did not provide a reachable parser attack.

### Rolling features differ from N12

N12 computes rolling features over the labeled battle series: laps where the cars were position-adjacent, within 2.5 s, and had valid times. `_pair_rolling_features` uses every lap where both drivers have rows (`race_situation_agent.py:455-482`).

For a pair that closes from 4.0 s to 2.0 s over laps 8-10, the helper returns `rolling3=-1.500`, `gap_trend=-1.000`. N12 has only lap 10 in its labeled series and returns `rolling3=-2.000`, `gap_trend=0.000`.

On 11,633 in-domain 2025 pairs:

- `rolling3` used different windows on 3,425 pairs (29.44%); `gap_trend` used a different prior lap on 2,109 (18.13%).
- Absolute `rolling3` difference averaged 0.113 s (p95 0.683, max 12.97). `gap_trend` difference averaged 0.323 s (p95 1.464, max 47.05).
- Calibrated probability changed by 0.0062 on average (p95 0.0294, max 0.480); 409 pairs changed by more than 0.05. Eighty-one pairs crossed the 0.40 band and 38 crossed 0.65.

The helper also includes shared laps after a position swap-back, where x is ahead of y and `_pair_gap_seconds` clamps the gap to 0.0. N11 has no such row for that ordered pair. A NaT lap can poison `rolling3`; N11 drops it. Current featured frames have no NaN `LapTime_s`, and the FastF1 path uses `pick_accurate()`.

The existing test at `tests/agents/test_overtake_domain.py:217-258` pins the shared-lap rule, not N12's battle series. It must change with the helper. The measured mean probability effect was 0.0062, so the mismatch is HIGH for the parity claim and MEDIUM for average served effect.

### Parser and missing-value behavior

The marker-only string cannot match the overtake regex because the pattern requires digits after `= `. Gap and pace still parse from the marker; refused and never-called paths leave probability as `None`.

The executed cross-call case was `[SC, marker(gap=9.11, pace=0.300), scored(0.412, gap=1.20, pace=-0.150)]`. It produced probability 0.412 with gap 9.11 and pace 0.300, mixing the second call's probability with the first call's measurements (`race_situation_agent.py:961`). This needs LLM mode and at least two tool calls; no-LLM makes one call. Parse all three fields from the same accepted tool response.

The `-1` cluster cast becomes categorical NaN. Its prediction matched explicit NaN (raw 0.3076, calibrated 0.0180) and differed from cluster 0 (raw 0.4402, calibrated 0.0472). No fill occurs between cast and `predict_proba` (`race_situation_agent.py:1339-1363`).

### Webapp uses an unscoped season frame

`POST /situation` passes all 24 races from `require_laps_df(year)` to `run_race_situation_agent_from_state` (`backend/api/v1/endpoints/strategy.py:1141-1155`). The agent looks up `(Driver, LapNumber)` without GP scoping. In the augmented 2025 frame, `(VER, lap 20)` appears in 21 GPs and `iloc[0]` selects Austin. A Qatar request can therefore report Austin's gap and overtake decision.

This predates the branch. CLI and Arcade paths scope upstream; the tyre-evaluation route in the same strategy endpoint uses the `gp_df` pattern at `:1019-1026`. Apply the same GP scoping to per-agent routes before using their Model Lab output.

### Other findings

| Severity | Finding | Location |
|---|---|---|
| LOW | `no_llm.py` still says the parser defaults the probability to 0.0; this branch returns `None` when the tool declines or does not run. | `src/strategy/inference/no_llm.py:156` |
| LOW | `pd.notna(gap)` cannot catch NaN after `max(0.0, gap_ahead_s)` converts it to 0.0. Current featured frames have no NaN lap times. | `race_situation_agent.py:1096,1350` |
| LOW | `gap_ahead_s` and `pace_delta_s` still default to 0.0, so an unmeasured value can render as a real zero beside `overtake —`. | `race_situation_agent.py:944-946` |
| INFO | Arcade `reasoning_tabs._situation_lines` handles `None` via `_pct(None)` but omits the out-of-range explanation shown by its sibling formatter. | `src/arcade/dashboard/reasoning_tabs.py:132` |

## Corrective actions recorded by the gate

1. Scope `/situation`, `/pace`, `/pit`, `/tire`, and `/radio` to the requested GP, following the existing `gp_df` pattern.
2. Restrict `_pair_rolling_features` to the battle series and update the parity test.
3. Keep probability, gap, and pace fields from the same accepted tool response.
4. Update the `no_llm.py` docstring and preserve NaN before the domain gate.
5. Consider matching the Arcade out-of-range label to the other formatter and correct the PR's median/p90 description.

## Checks that held

- Neutralisation forces 0.0 before output construction; `_fmt_prob` handles the override without a `None` error.
- No swept consumer performs arithmetic or formatting on `None`. CLI, Arcade, backend, MCP, webapp, and chat either serialize null or skip the gauge. The MC reads SC/VSC fields, not `overtake_prob`.
- A legitimate 0.000 value is unreachable because the calibrator floor prints as 0.002.
- Adding NaN to `__post_init__` left bands LOW and did not crash. Removing an OR term did not suppress SC contribution.
- Ruff, webapp `tsc --noEmit`, and the branch test suite passed at the time of the gate (13/13).
