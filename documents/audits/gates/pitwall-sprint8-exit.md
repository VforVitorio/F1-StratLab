# PITWALL sprint 8 exit gate

Audit date: 2026-08-17. Branch: `sprint8-integration`, ten commits ahead of `origin/dev` (17 files, +673/-144). The review covered the 1,312-line diff, PRs #969 and #971, and claims A-H.

The gate ran `uv run pytest tests/surfaces/ -q` (218 passed), `npm run build` (agents bundle 9.56 kB), `node scripts/smoke-agents.mjs` (19 checks), `node scripts/smoke-data.mjs` (147 checks), and the scratchpad `gate_exit_attacks.py`.

## Findings

### F1 (P1): Unknown enacted action restores the vetoed winner

At `decision.py:252`, an enacted action missing from the score map falls back to the highest-scoring candidate. `build_scenarios({"PIT_NOW": 0.71, "STAY_OUT": 0.29}, "ALERT")` returned PIT_NOW with `is_enacted=True`, an empty note, bar color `#a78bfa`, and 100.0% fill. ALERT is a legal fifth action in `strategy_orchestrator.py:273`. The panel therefore disagrees with the action badge and reports false `is_enacted` data. Leave the row unhighlighted when the enacted action has no score, or render a separate chip.

### F2 (P2): A top-score tie marks both candidates as vetoed

`max(raw, key=raw.get)` breaks ties by insertion order; `span = (hi - lo) or 1.0` then maps both scores to the 6% floor. `build_scenarios({"STAY_OUT": 0.50, "PIT_NOW": 0.50}, "PIT_NOW")` returned `STAY_OUT: winner=True, note='VETOED', fill=6.0` and `PIT_NOW: enacted=True, fill=6.0`. Neither score was higher. Treat equal scores as indistinguishable and set `vetoed_key` only when the winner's score is strictly greater.

### F3 (P1): The stop-lap spike falls outside the chart range

`charts.py:211` calculates `y_range` from the smoothed trend. Laps 14-22 sit near 81 s; the 103.4 s in-lap is inside the 30-200 s sanity window. `build_tire_series` returned `[78.53, 94.9]`, so ECharts clips that raw point. The trend ends at 88.72 s on lap 22 and 92.4 s on lap 23. After the stop, a 16 s range also renders a real 0.05 s/lap degradation at about 4 px on a 150 px plot. The proposed fix bounds the axis around the median of plotted values by about 2.5 s, or removes outlier in-laps from both the data and axis. The current test uses a synthetic point and checks the wrong series.

### F4 (P3): A non-integer lap number can label the wrong call

`decision.py:133-136` filters prior calls only when the current lap is an integer. With `lap_number=23.0` or `"23"`, the chip reports the PIT_NOW call on lap 23 as the previous call. A float in a tail row suppresses the chip instead. The live wire currently supplies an integer, so reachability is low. A previous row with `confidence=None` also fabricates `0.00`; omit the confidence when absent.

### F5 (P2): Card body inserts unescaped wire text

`AgentCard.tsx:141,149` sends `card.headline` and `line.text` to `dangerouslySetInnerHTML`. `format_radio` interpolates `radio_events[].message`, `rcm_events[].message`, and driver radio text without escaping. The nine `html.escape` calls found in the module were inside tooltip builders, not body lines. A radio message containing markup can disappear or inject DOM. Escape free-text interpolation in the body formatters or use typed text segments.

### F6 (P2): The token test misses two boot colors

`AgentsWindow.tsx:79,134,148` adds `action_text_colour: "#121127"` and `cursor_colour: "#9ca3af"`, but `BOOT_SLOTS` omits them. The subset assertion at `test_pitwall_tokens.py:213-230` cannot detect an unlisted color. Changing the action text to `#ffffff`, the 2.72:1 contrast failure fixed by #971, still passes. Add both slots and consider asserting exact set equality.

### F7 (P2): No test guards the chart range or shared cursor

The y-range has no test, and `smoke-agents.mjs` carries the new fields without checking the rendered extent. Setting `charts.py:211` to `None` leaves all 218 tests and 19 + 147 smoke checks green. A producer test should assert that a flat stint stays within about 7 s and contains its data, that pace and tyre charts share `x_range`, and that `current_lap` matches the lap. A smoke check can read the rendered ECharts axis extent.

### F8 (P3): The shared lap axis can crop pace history

The builder passes the tyre chart's `x_range` to pace unconditionally. With pace laps 10-23 and valid pace predictions, but tyre data only on laps 10-14, the range becomes `[14.5, 26.0]`; five pace points fall outside it. Derive the shared range from both series.

### F9 (P3): Two docstrings name deleted functions

`agent_formatters.py:365,558` refer to `radio_tooltip_html` and `rag_tooltip_html`, renamed in the same change to `radio_tooltip` and `rag_tooltip`. The `format_radio` docstring also describes a QLabel, while the text now appears in the card body.

### F10 (P3): The current-lap mark is duplicated

`useEChart.ts::currentLapMark` serves PaceChart, while TireChart inlines the same mark. Both currently agree, but later changes can leave the charts inconsistent. Build the tyre mark from the shared helper.

### F11 (P3): The veto note shortens one candidate's bar

In `s3-guardrail.png`, the PIT track ends about 45 px before the STAY track, whose border spans x=77-460. The note sits inside the flex row and reduces the vetoed row's available width. Overlay the note or reserve the same space on each row.

### F12 (P2, process): Eleven design findings had no issue

The issue listing contained 50 issues. #962-#968 and #960 covered the sprint; #974 covered the `guardrail_reason` wire gap. No issue covered S7-S14, L3, L5 or L6: stub wording and missing radio/RCM/SC output; pit-state styling and duration; radio priority; button-like decision styling; ARIA and color; inconsistent pills and wire hex; stub chart headline; missing RAG reasoning tab; 11 px confidence text; 540 px pin; or scroll access. File an issue that links these findings, or track S8, S9 and S13 separately.

## Claim results

| Claim | Result |
| --- | --- |
| A | Unknown enacted actions and ties can mark the wrong row (F1, F2). |
| B | The 6% floor is visible at 1485x833; unscored rows have no track. |
| C | Passing colors survive the sweep; two boot literals lack test slots (F6). |
| D | Fresh renders at both viewports showed no phantom charts or clipping. |
| E | The +22 s in-lap is clipped and the chart range lacks a guard (F3, F7). |
| F | Tooltip text is escaped; adjacent card body text is not (F5). |
| G | The tooltip rendered on the real wire; non-integer laps can select the wrong prior call (F4). |
| H | Bars encode rank, not score margin; exact ties remain hard to distinguish (F2). |

## Checks that held

- A 32,768-color sweep of `legible_fill` and `readable_on` converged within 12 steps and did not alter a passing color. Compound pills stayed at or above 4.87:1, and SOFT remained red.
- The scenario floor stayed at 6.0% minimum with 0.1% rounding. Missing scores produced trackless rows with `--`; empty input produced no crown or veto mark.
- `_previous_call` handled integer, duplicate and future laps. It suppressed the chip on lap one, with no history, or when `plan_changed=False`. At lap 22, `memory_block` and history both reported `STAY_OUT` with confidence 0.62. The history update and latest-call write occur under one lock at `strategy.py:439-440`.
- Tooltip tests covered the payload shape, uncapped message, `None` sentinel, four-chunk cap and footer. Both call sites passed `dict | None`; the UI rendered text nodes.
- Fresh bundle renders at 1485x833 and 1200x700 showed both charts without phantom boxes. The smoke checked the built bundle and overflow guard.
- Axis-label checks kept 12.5 and 78.53 out of the rendered tick labels. Chart restart behavior and fixture action/confidence stayed consistent. Idle text measured 6.88:1; the other contrast ratios reproduced under `contrast_ratio`: SUCCESS 7.29, ACCENT 6.80, WARNING 8.61 and DANGER 4.92.

## Not verified

The gate did not run the real pywebview window against a live arcade producer or replay a race. Rendering used the built bundle and states from `PitwallHost`. The reported measurement over 40 real-race lap pairs was not rerun.
