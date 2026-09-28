# PITWALL data window design gate

Audit date: 2026-08-18. Repository: `dev` at `d4ef7cf` (merge of PR #977). The audit ran before Sprint 9 work.

The live loopback server served `dist/assets/data-DWGt9GtQ.js` (24.6 KB), `data-DAzFNt-6.css` (9.6 KB), and `qt-base-86dNR9Zk.css`. No rebuild ran during measurement. The session was Melbourne 2025 at about lap 24, produced by `scripts/dev_pitwall_producer.py`, and served at `http://127.0.0.1:62712/data.html`.

The review covered the data-window UI, bridge and producer, live endpoints, nine screenshots, and `MEASURED-BASELINE.md`. It checked the status strip, timing tower, BESTS, traces, track ring, radio, pace grid, footer, tabs, and waiting, stale, safety-car, and empty states. The gate tests whether a strategist can read the window at its measured sizes. It does not score fidelity to the older Qt window.

Each finding below cites the served bundle, code, payload, or screenshot used to verify it. The recommendations remain a record of the 2026-08-18 checkout; check the current implementation before reopening one.

The temporary probe named in the original audit was not present in this branch. The report does not include it.

## Findings

### D1 (P1): Pit-lane passes are counted as tyre stops

- Where: `src/pitwall/session_data.py:447` (`"stops": sum(1 for row in revealed if row["pit_in"])`), rendered at `src/pitwall/ui/src/features/data/TimingTower.tsx:155`.
- Impact: the false 3-stop count can mislead undercut and overcut decisions. The 17 cars kept the same tyres through lap 4.
- Executed evidence:
-  - `laps.parquet` Melbourne 2025: `PitInTime` is set for **17 cars on laps 2, 3, and 4** while the safety car leads the field through the pit lane. NOR keeps the INTERMEDIATE compound and tyre life counts 2, 3, and 4 across those passes. FastF1 opens a new `Stint` each time, producing four stints by lap 24 despite zero tyre changes.
-  - Live probe at lap 31: every running row shows `col-stops = "3"` beside `col-tyre = "I 30"`.
  - The pace grid (D7) paints the same three laps as full-field `IN PIT` rows plus a full-field `OUT` row, in DANGER red.
- Defect: `session_data.py:420` says `stops` counts in-laps and agrees with `max(stint) - 1` on a healthy race. Both formulas return 3 here, but Melbourne's three pit-lane passes did not change tyres. Matching formulas do not make this a tyre-stop count.
- Prescription: count a stop as a **tyre-set transition**, which is already computable from fields on the wire: consecutive `LapRow`s where `compound` changes or `tyre_life` resets downward (`laps[i+1].tyre_life < laps[i].tyre_life`). Do it producer-side in `_driver_view` (one reduction, masked rows only) and correct the docstring; the wire shape does not change. No new palette constant, no new field.

### D2 (P1): Safety-car status has low visual salience

- Where: `StatusStrip.tsx:37-40` + `.strip-chip` (`data.css`).
- Impact: the 1465x28 status strip changes only the outline chip's text between GREEN and SAFETY CAR. Operators can miss the change during a pit call.
- Evidence: the live probe measured GREEN at 54.3x18 px and Connected at 76.9x18 px. The safety-car and green captures show no other visual change. Each tick already carries `track_status_label` and `track_status_color`.
- Change: fill the chip for non-green states and tint the strip border with the existing `track_status_color`; keep `NO STATUS` dim.

### D3 (P1): Stopped producer leaves stale telemetry labelled as live

- Where: `DataWindow.tsx:70-71` (`live` latches true forever after the first tick, so `StatusStrip` keeps the last tick), `StatusStrip.tsx:127-130` (`playbackLabel` renders the LAST tick's `2x`), plus every panel holding its final values.
- Impact: after the feed stops, the screen keeps the last lap, green flag, and PLAYBACK 2x. A strategist can mistake stale data for a live race.
- Executed evidence: `state-dead.png` shows a populated window, a `Disconnected` chip, and an empty footer. The probe reproduces this state.
- Change: when `useConnection` returns `"Disconnected"`, render `PLAYBACK —`, dim `.data-main`, and show `DATA FROZEN · last tick L28` in the status bar. `useStatusText` supports persistent text, and the client already knows the connection state.

### D4 (P0): Pace labels clip at 1265x593

- Where: `.pace-table` (`data.css`: `font-size: 9px`, `table-layout: fixed`, cell `overflow: hidden`, padding `0 1px`) at the 1265x593 client; scrollbars globally hidden (`qt-base.css`).
- Impact: at 1265x593, lap times lose their tenths and `IN PIT` becomes `IN PI` in the grid.
- Executed evidence: at 1265x593 on lap 31, **495 of 514 populated cells clip** (`scrollWidth 35 > clientWidth 28`). `pace-1265x593.png` shows `IN PIIN PI`. The baseline measured 411/520 on lap 24.
- Prescription: the cell needs ~7 px it cannot get at 583 px over 20 columns, so change the CONTENT, not the box: below a measured column-width threshold render the width-aware form `m:ss` (a 4-glyph label measures ~22 px at 9 px mono) and say so once in `.pace-subtitle` ("times to the second at this width"). The tone already carries the ranking, which is the panel's stated design; the value shown is then a true value, just coarser. Client-only; no wire change. A degraded-but-honest cell beats a silently wrong one.

### D5 (P1): BESTS rows and the theoretical footer clip at 1265x593

- Where: `.left-column` uses `grid-template-rows: auto minmax(0, 1fr)`. The tower takes 437 px of a 510 px column, leaving 63 px for a 151 px BESTS card. Scrollbars are hidden and there is no overflow indicator.
- Impact: at 1265x593, no full BESTS row fits and the THEORETICAL footer is hidden.
- Executed evidence: at 1265x593 the BESTS card ends at 650 px and the column clips at 560 px, cutting **90 px**. `visibleCount` is 0 of 12 complete rows; row 1's text is still readable in `pace-1265x593.png`.
- Change: set `RANKED = 1` at short client sizes and keep THEORETICAL visible. `BestsPanel.tsx:29` already controls the row count. Client-only.

### D6 (P1): Safety-car queue order determines pace colors in 213 of 776 cells

- Where: `lib/racePace.ts` (`rankedByLap`/`tone`) ranks every non-pit lap. `lib/bridge.ts:111` types `track_status` on each row, but the only consumer is the arcade-level chip in `StatusStrip.tsx:38`.
- Impact: on safety-car laps, pace colors track queue order rather than speed. They cannot support tyre-life or driver-form comparisons.
- Executed evidence (past the baseline's counts, to the mechanism): recomputed on the parquet: 776 ranked rows, 213 on SC laps, SC lap times 86.4-148.2 s (median 131.6) vs green median 91.9. Then, per SC lap, Spearman correlation between lap-time rank and running position: **|rho| >= 0.75 on 11 of 17 measurable SC laps**, flipping sign with the accordion phase (lap 1: +1.00; lap 7: -1.00; laps 39-41: -0.88 to -0.98; laps 49-51: -0.79 to -0.96). The thirds are queue order wearing pace colours, in both directions.
- Prescription: mark the lap from the dead field: a glyph or amber lap number in `.pace-lapcol` for any lap where the majority of rows carry a `4` digit (SC), and an ECharts `markArea` over the same lap ranges on the race trace's x-axis (which also explains that chart's laps-5-8 V shape on screen). The label converts a lie into a caption; client-only; the field already crosses the bridge on every row.

### D7 (P2): The pace grid and tower use `OUT` for different states

- Where: `lib/racePace.ts:246` (`if (row.pit_out) return { text: "OUT", tone: "out" }`) vs `TimingTower.tsx:227-233` (`lastCell`: retired → `OUT`, out-lap → `PIT EXIT`; its docstring: *"an out-lap says PIT EXIT rather than borrowing the same word for a car that is very much still racing"*) and the ring legend's `○ out` (retired).
- Impact: the pace grid labels BEA's racing out-lap `OUT`, while the tower uses `OUT` for retired cars. The safety-car pit pass also produces a full red row that looks like mass retirement.
- Executed evidence: at lap 31 the grid has 19 `OUT` and 51 `IN PIT` cells. The tower's `col-last` simultaneously shows three `OUT` values for retired cars; the grid still uses the same label for an out-lap.
- Related: `#ef4444` is the DANGER red used for the `Disconnected` chip. The routine pit tone measures 4.25:1 on the banded columns at 9 px, below the 4.5:1 floor. Laps 2-4 show full-field red rows.
- Change: label out-laps `PIT EXIT` (or `P.EXIT`) in `racePace.ts`. Reserve red for in-laps and use WARNING amber for out-laps.

### D8 (P2): Radio feed does not render its safety-car and flag fields

- Where: `lib/bridge.ts:164-165` types and populates `category` and `flag`. `RadioFeed.tsx` renders only `kind`, `lap`, `driver`, and `text`.
- Impact: Safety-car and double-yellow messages look like routine stewards notices in the same ten-row radio fold.
- Executed evidence: `/api/bulk` at lap 31 returned 39 RCM events with `category` counts Other 23, Flag 13, SafetyCar 2, and Drs 1. It also returned flags CLEAR 8, BLUE 4, and DOUBLE YELLOW 1. The renderer discards those fields; `state-safetycar.png` shows 9 of 11 visible rows as steward notices.
- Dead-wire census while here: `LapRow.position`, `LapRow.stint`, `LapRow.pb` and `DriverLaps.theoretical` also cross the bridge and are read by nothing in this window (grep over `features/data` + `lib`). `pb` and per-driver `theoretical` are documented as deliberately recomputed/unused; `position` and `stint` are just freight.
- Change: render a compact `SC`, `FLAG`, or `DRS` chip using existing tones, and combine consecutive identical RCM lines with a count such as `x4`. Client-only.

### D9 (P2): Radio history cannot be reached by scrolling

- Where: `.radio-list` / `.radio-feed` (`data.css`: both `overflow: hidden`).
- Impact: about 36 of 46 radio events sit below the visible fold, and users cannot scroll to them. Other hidden-scrollbar panels still support scrolling.
- Executed evidence: `listOverflowY` is `hidden`; the list height is 344 px for 1379 px of content, with 10 of 46 rows visible. Setting `scrollTop` programmatically works, but users cannot scroll.
- Change: set `.radio-list` to `overflow-y: auto`. Existing styles hide the scrollbar.

### D10 (P2): Rival traces obscure the own-car series

- Where: `TraceChart.tsx:100-119` declares `[main, rival]`, so ECharts paints the rival on top. `lib/raceTrace.ts:269-270` deliberately paints the own car last in the race trace.
- Impact: when the lines overlap, the rival's dashed trace covers the own-car line on the Speed and Throttle charts.
- Executed evidence: the series order at `TraceChart.tsx:100-119` (main first, rival second; ECharts z-order is declaration order), plus the capture above.
- Change: declare the rival first and own-car series second. Move the `markLine` because it currently attaches to series index 0. No palette or wire change.

### D11 (P2): Unused space pushes the newest pace row down the card

- Where: `.pace-scroll` (no flex-grow: the scroller is content-sized inside a 720 px card), `RacePaceGrid.tsx:73-77` (the `scrollTop = scrollHeight` pin).
- Impact: the latest row moves down as laps accumulate, although 348 px of the 720 px card is empty at lap 30. The scroll pin does not activate until about lap 55.
- Executed evidence: at lap 30, the 720 px card contains a 372 px table and 348 px of empty space. `scrollable` is false. `.pace-scroll` has no flex-grow, so the table and bottom pin do not fill the card.
- Change: make `.pace-scroll` a column flex container and set `.pace-table { margin-top: auto; }`. Add a subtle style to the last row. CSS-only.

### D12 (P2): Four of twenty driver codes fail contrast requirements

- Where: three render sites (baseline confirmed): `TimingTower.tsx:266-269` (`driverColour`, 11 px bold code), `RaceTraceChart.tsx:52-59` + `endLabel` at 9 px (its own docstring: *"the end label is the only thing that tells two team-mates apart"*), `TrackRing.tsx:62-64`.
- Impact: VER and LAW are difficult to read in the tower and their race-trace end labels are the only line identifiers.
- Executed evidence: recomputed WCAG ratios (independent implementation, agrees with the baseline to the second decimal): VER/LAW 1.88 (panel) / 1.72 (elevated); ALO/STR 2.55 / 2.33; HAM/LEC 3.71 / 3.39. Four of twenty fail even the 3.0:1 large-text floor; text sizes here are 9-11 px, so 4.5:1 applies.
- Change: keep team colors for fills. Add a 3 px team-color swatch beside tower codes and render the codes in `--qt-fg-1`. Use AXIS_TEXT (`#d1d5db`, 11.9:1) for race-trace end labels. Leave ring dots unchanged and update the token test.

### D13 (P3): Two formatters retain the lap-time rounding bug

- Where: `TimingTower.tsx:252-257` and `BestsPanel.tsx:96-101` contain duplicate formatters. `lib/racePace.ts:139-144` has the round-first fix.
- Executed evidence: Node returned `60.000` for 59.9996 seconds and `1:60.000` for 119.9996. The bug window is 0.5 ms per minute at three decimals; no lap in this session hit it.
- Impact: the issue is rare in this session, but two duplicate formatters still contain the rounding defect fixed in `paceLabel`.
- Prescription: one `formatSeconds(seconds, decimals)` in `lib/` with `paceLabel`'s round-first arithmetic; the three call sites import it.

### D14 (P3): Tower omits tyre compound on lap 1

- Where: `TimingTower.tsx:245-249` (`tyreCell` reads the last COMPLETED bulk row; null until lap 1 completes) vs the tick's `drivers[code].compound` (int) + `tyre_life`, which are on every tick from frame 0.
- Impact: the lap-1 tower shows no compounds, even though the producer has each car's fitted compound on every tick.
- Constraint: `compound` is an integer decoded by `src/arcade/palette.py` (`COMPOUND_COLORS`, keys 0-4). Decoding it in the client would duplicate that mapping. Publish a compound name on each tick and let `tyreCell` use it until the first bulk row arrives.
- Prescription: producer: `drivers[code].compound_name` beside the int (one lookup it already owns); client: fallback in `tyreCell`. Until then the dash is at least honest.

### D15 (P3): Retired car remains in the ring's blind list

- Where: `TrackRing.tsx:83-95` adds any car with `rel_dist === null`. HAD has no telemetry rows in this race, so its line appears from lap 1 to lap 57.
- Impact: a retired car keeps the blind indicator on for the whole race, so the ring cannot distinguish that state from a running car with missing telemetry.
- Executed evidence: every one of the nine captures shows `NO POSITION: HAD`; HAD's status is `out` from lap 1 (tower row 20, `driverStatus` = out).
- Change: exclude cars where `driverStatus(car) === "out"`; the legend and tower already identify retired cars.

### D16 (P3): Controls are only 15-22 px high

- Where: `.ref` (`data.css`: 9 px font, `padding: 1px 6px`) and `.tab` (10 px font, `padding: 3px 10px`).
- Executed evidence: reference buttons measure 50.2x15 (`LEADER`), 44.2x15 (`FIELD`), and 32.1x15 (`NOR`). Tabs measure 64-91x22.
- Impact: the 15 px controls are smaller than common 28-32 px mouse targets.
- Change: set `.ref` padding to `4px 8px` and `.tab` to `5px 12px`. Both headers have room at the tested sizes.

### D17 (P3): Amber represents four unrelated states

- Where: `#f59e0b` is simultaneously: BROADCAST tier (rival trace + rival chip + `.radio-tier`), the PROVISIONAL warning chip, the tower's "slower than own best" sector tone, and the pace grid's slowest third (`is-t3`). `data.css`'s `.radio-tier` comment asserts: *"the same WARNING the rival chip uses, so one colour means one tier across the whole window."*
- Defect: the comment says WARNING has one meaning because the rival chip and radio tag share it. Amber also marks slow sectors and the slowest pace band, so the comment overstates the palette's consistency.
- Impact: local labels disambiguate amber uses, but the safety-car state competes with three other amber annotations.
- Prescription: fix the comment now (cheap, stops the claim propagating); when D2 lands, let non-green track status own the FILLED-amber treatment so weight, not hue, separates "state of the race" from "annotation".

---

## Recommended implementation order

| Order | Finding | Change |
|---:|---|---|
| 1 | D9 | Allow scrolling in `.radio-list`. |
| 2 | D10 | Draw the own-car series last. |
| 3 | D7 | Use `PIT EXIT` for an out-lap; reserve red for in-laps. |
| 4 | D2 | Make non-green track status more visible. |
| 5 | D6 | Mark safety-car laps in the pace grid and race trace. |
| 6 | D3 | Show frozen data when the producer stops. |
| 7 | D11 | Anchor the latest pace row at the bottom. |
| 8 | D1 | Count tyre-set changes as stops. |
| 9 | D4 | Fit lap-time labels at narrow widths. |
| 10 | D5 | Reduce BESTS rows at short client sizes. |
| 11 | D12 | Improve driver-code contrast. |
| 12 | D8 | Render radio category and flag fields. |
| 13 | D15 | Exclude retired cars from the ring's blind list. |
| 14 | D16 | Increase control hit areas. |
| 15 | D13 | Share the round-first time formatter. |
| 16 | D14 | Send `compound_name` and show it on lap 1. |
| 17 | D17 | Correct the `.radio-tier` comment. |

---

## Corrections to the measured baseline

- BESTS clipping: the live measurement was 90 px, not 80. The card ends at 650 px and the column clips at 560 px. No complete row fits at this size, although row 1's text remains readable.
- Row overflow: only LAP ranks 2-3 exceed the 146 px box, at 153 px. The other ten rows fit.
- Pace clipping: 411/520 was a lap-24 count. At lap 31, 495/514 populated cells clipped. At 1265x593, six-character labels lose about 7 px.
- Pace pin: the claim holds. The scroller is content-sized (`flex: 0 1 auto`) and is not scrollable at either measured client size.
- Driver contrast and SC-row counts: both baseline measurements reproduced. The independent D6 rank analysis shows that SC cells encode queue order, not pace.

---

## Checks that held under attempts to break them

- `gapCell` returned `LEADER`, `+N LAPS`, two-decimal gaps, and `OUT` for retired cars. It returned a dash for lap 1; no branch-order error appeared.
- The tower, BESTS panel, and pace grid agreed on fastest-lap data. A three-decimal sector tie could produce two purple tower cells, but none occurred in this session.
- The reveal mask exposed no future data. A rewind was not tested because the producer was shared with the author's session; the existing smoke test covers cache eviction.
- `stableColumns` kept car numbers in strict order, including rows with unknown positions. The cyclic-comparator failure did not recur.
- Waiting and unknown states stayed visibly uncertain: `NO STATUS`, blank values, and no green state for missing data.
- The one-lap RCM delay is tracked under #931/#842 and documented in `radio_feed.py`; it was not reopened here.
- Rival traces begin empty at the start of each lap, as required by the distance-keyed store. Mixing laps would add a measured 4-6 s spike.
- The locked `[-3, 3]` delta range clips rival lines beyond 3 s. The tower still shows the gap, and the gate left the Qt axis behavior unchanged.

---

## Findings by severity

| Severity | Count | Ids |
|---|---|---|
| P0 | 1 | D4 |
| P1 | 5 | D1 D2 D3 D5 D6 |
| P2 | 6 | D7 D8 D9 D10 D11 D12 |
| P3 | 5 | D13 D14 D15 D16 D17 |

Bundle measured: `data-DWGt9GtQ.js` and `data-DAzFNt-6.css` on the live loopback server, Melbourne 2025, laps 24-32.
