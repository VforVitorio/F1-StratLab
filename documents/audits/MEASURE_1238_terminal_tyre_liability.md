# Issue #1238 measurement: terminal tyre continuation

**Date:** 2026-09-14
**Instrument:** `scripts/measure_terminal_tyre_liability.py`
**Decision:** `NO-GO` for consuming this value in the production scorer

## What was measured

The instrument asks one narrow question: if the current tyre cost is held
constant, how close is it to the model's own target cost over the later observed
laps of a final stint that reaches the race end?

```text
predicted cost = current wear prediction x future observed laps
target cost    = sum of future same-stint target wear
error          = predicted cost - target cost
```

The current row is the observation. Future rows are used only as the evaluation
target, never to build the fresh reference or the current prediction. The fresh
reference uses the same early-stint prediction and the same race-pace quality
gate as production `deg_cost_s`. Stints with duplicate tyre-life values are
excluded because their chronological order is not reliable.

The measurement covers 2023-2024 as the development distribution and 2025 as a
held-out check. It is deliberately limited to final stints that reach the end of
the observed race data. `future_observed_laps` is not silently renamed to full
race laps when neutralised or invalid rows are absent.

## Results

| split | cutoffs | stints | mean absolute error | median absolute error | signed bias | p95 | p99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2023-2024 | 11,950 | 528 | 11.396 s | 6.061 s | -4.045 s | 40.086 s | 71.701 s |
| 2025 holdout | 6,776 | 289 | 12.850 s | 7.803 s | -5.415 s | 41.505 s | 77.916 s |

Cluster-bootstrap 95% intervals for the mean absolute error are 10.363-12.348
seconds on 2023-2024 and 11.337-14.517 seconds on 2025. A p99 bound fitted on
2023-2024 covers 98.69% of the 2025 cutoffs, but its 71.701-second size is too
wide to be a useful scorer term.

The error grows with the remaining horizon:

| future observed laps | 2023-2024 MAE | 2025 MAE |
| ---: | ---: | ---: |
| 1-3 | 1.124 s | 2.077 s |
| 4-5 | 2.389 s | 4.459 s |
| 6-10 | 4.614 s | 7.284 s |
| 11-20 | 11.407 s | 12.657 s |
| 21-50 | 26.305 s | 26.051 s |
| 51+ | 95.580 s | 87.966 s |

The five-lap window is locally measurable. The problem appears when the current
wear value is carried beyond that local horizon. The 2025 result is not a safe
future forecast, even though the early bands are smaller.

## Continuation contract

The measurement records the states explicitly instead of inferring legality from
`mandatory_stop_pending`:

| state | run to flag | required stops | rule |
| --- | --- | ---: | --- |
| no known event requirement | candidate only | 0 | still needs tyre and race-end evidence |
| one required stop | inadmissible | 1 | model at least one later stop |
| Monaco 2025 | inadmissible | 2 | two stops and three tyre sets |
| Lusail 2025 | inadmissible | 2 | event stop and tyre-life constraints |
| unknown obligation | abstain | unknown | do not invent a continuation |

This is a contract definition, not yet a complete multi-stop simulator. A future
implementation must choose the continuation before sampling, include every
required later stop, and evaluate the same terminal horizon for every candidate.

## Decision

Do not add terminal tyre liability to either scorer. The current `deg_cost_s`
value is useful over the short window it was measured for, but the simple
constant extrapolation is too inaccurate over a race distance. The existing
five-lap horizons stay unchanged, and the scorer remains untouched.

Before reopening the design, the project needs a future-horizon model or a
measured continuation curve, explicit multi-stop legality, and one residual-cost
contract with adapters for the projection and legacy scorers. The JSON output is
the machine-readable record:
`documents/audits/MEASURE_1238_terminal_tyre_liability.json`.

## Verification

- `uv run python scripts/measure_terminal_tyre_liability.py`
- `uv run pytest -q tests/eval/test_terminal_tyre_measurement.py`
- `uvx ruff check scripts/measure_terminal_tyre_liability.py tests/eval/test_terminal_tyre_measurement.py`
- `uvx ruff format --check scripts/measure_terminal_tyre_liability.py tests/eval/test_terminal_tyre_measurement.py`
- three hermetic tests passed

The real TCN was used for both seasons. No production scorer, model, dependency,
or five-lap horizon was changed.
