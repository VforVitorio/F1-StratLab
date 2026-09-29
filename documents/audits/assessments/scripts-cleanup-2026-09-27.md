# Scripts cleanup audit, 2026-09-27

This audit accompanied [PR #1258](https://github.com/VforVitorio/F1-StratLab/pull/1258). It reviewed `scripts/` for dead or low-value measurement scripts. No deletion met the evidence threshold.

## Scope and result

The directory contains 53 files, 48 Python files, and 12 `measure_*.py` scripts. Two disjoint review passes checked measurement tools, command-line entry points, benchmarks, trace utilities, tests, reports, and current issue references.

Removed: 0 files and 0 lines. Each measurement script had a distinct current use in an issue, report, test, reproducibility check, or diagnostic flow. The other scripts likewise had active callers or independent validation roles.

## Duplicated helpers retained

- `measure_fresh_reference_gate_2025.py` and `measure_tyre_reference.py` contain a duplicated helper of about eight lines. Keeping them separate preserves independent reproducibility for the frozen measurements.
- `trace_pitwall_real_path.py` and `verify_pitwall_trace.py` repeat an approximately eight-line field map. The first captures runtime evidence; the second validates it. Sharing the map would couple separate tools without removing a dead path.

## Related cleanup history

[PR #1243](https://github.com/VforVitorio/F1-StratLab/pull/1243) and [PR #1244](https://github.com/VforVitorio/F1-StratLab/pull/1244), merged on 2026-09-16, split and completed the testing tiers. #1243 also changed `measure_mc_tables.py`; neither PR removed measurement scripts. The earlier [PR #777](https://github.com/VforVitorio/F1-StratLab/pull/777) cleanup fixed fragile repository-root discovery in eight scripts.
