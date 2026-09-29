# Final correctness gate for the shared race-state builder

Audit date: 2026-08-02. Scope: PR #784, fix #788, and part of #789. Parent branch: `refactor/single-source-race-state-builder`; telemetry submodule: `7f394a8`.

This gate records executed checks from the pre-push checkout. Findings are historical; check the current branch before reopening one.

## Verified behavior

- The CLI change had two hunks. A byte comparison confirmed the radio and RCM loop after line 1400 was unchanged.
- CLI, Arcade, and the backend shim referenced the same `build_race_state` function. Importing the shim loaded none of LangChain, LangGraph, Torch, XGBoost, LightGBM, Transformers, or Whisper.
- `reading_or_default` matched the previous pace-agent guard for absent keys, `None`, 0.0, booleans, NaN, and numeric values.
- Compound and tyre-life normalization changed no sane TCN prediction in the tested data. The 379 rows with compound `nan` and 53 rows with `None` all had NaN `TyreLife`; both old and new paths produced an empty window and the conservative stub. The new path stopped the crash on 451 reachable 2025 rows.
- `UNKNOWN` still mapped to `C3`. Builder-first and tire-agent-first imports completed without a cycle.
- The weather-column inventory, 71 readable weather files, temperature medians, and tyre-life range were rechecked against the data.

## Test results

- `tests/agents/test_race_state_builder.py`: 29 passed.
- `tests/agents`, `tests/audit`, and `tests/simulation`: 192 passed.
- The report has no result for `tests/engine`, `tests/mc`, `tests/surfaces`, or `tests/infra`. The implementation log had not rerun the engine and MC suites after the `no_llm.py` change.
- The builder tests covered `RaceState`, but no test covered the changed raw-lap-state adapters with present-`None` weather. That remained a coverage gap.

## Findings at the time of the gate

| ID | Severity | Finding |
|---|---|---|
| F1 | Medium | Comments in `scripts/run_simulation_cli.py:1290-1296` and `src/arcade/strategy.py:~600-612` said the backend still used a separate builder. The committed `7f394a8` shim and parent pointer made `backend.utils.race_state_builder.build_race_state` identical to the canonical function. The CLI docstring below the comment already said the backend shared it. `src/agents/race_state_builder.py:49` also retained future tense for the landed shim. |
| F2 | Medium | Tests did not cover `reading_or_default`, agent-side compound/tyre-life normalization, or present-`None` weather in raw adapters. |
| F3 | Tracked | N27's `TyreLife` NaN crash remained on 451 2025 rows and was tracked by issue #790. This gate did not reopen it. |
| F4 | Low | `pace_agent.py:650` still read rainfall with `wx.get('rainfall', 0)` while sibling adapters used `reading_or_default`. The shipped producers did not emit `None`. |
| F5 | Low | A test docstring said all three old builders failed via `float(None)`. The CLI builder passed `None` to Pydantic, which rejected it; Arcade and backend called `float(None)`. |
| F6 | Historical hygiene | `notebooks/strategy/overtake_probability/outputs/n12b_scoreboard.png` was untracked in the gated checkout. It should not have been added with `git add -A`. |
| F7 | Resolved later | The sweep initially described the tyre-life and compound reads as unfixed. Its addendum dated 2026-08-02 records that both were fixed after the sweep. See `../sweeps/present-none-traps.md`. |

## Submodule check

`backend/utils/race_state_builder.py` at `7f394a8` is a 24-line re-export of the canonical function. Searches in that submodule found no references to the removed normalization and targeting helpers. The submodule had local untracked directories `.claude/` and `docs/migration/streamlit-reference/`; they were not part of the pointer change.

## Attempts to break the change

- Compared `reading_or_default` with the old inline guard across eight inputs, including 0.0, `False`, and NaN. Results matched.
- Searched featured and raw 2025 data for a sane prediction changed by compound or tyre-life normalization. The degraded rows all produced empty stint windows; no changed TCN input was found.
- Imported the builder before and after `tire_agent` in fresh interpreters. No cycle or heavyweight import occurred.
- Compared the CLI tail byte-for-byte, rechecked the temperature inventory and medians, and tested `Series <= None` on pandas 2.3.3. The CLI block stayed intact; the comparison returned all-False without raising.
- Ran the orchestrator's synthetic state through `normalise_compound`. `UNKNOWN` stayed `UNKNOWN`, and tyre life 0 stayed 0.

## Not verified in this gate

- A real HTTP `/recommend` run with the LLM profile. OpenAI connectivity failed; the deterministic profile exercised the crash site in the implementation log.
- The 2.3-lap cliff figure, inherited from the Qatar gate and not remeasured here.
- The telemetry submodule suite in a submodule-local virtual environment; the implementation log records a `fastmcp` skip.
