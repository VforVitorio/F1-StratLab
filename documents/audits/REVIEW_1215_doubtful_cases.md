# Review of doubtful 2025 pit entries

This report is the manual evidence follow-up for issue #1215, the 2025 pit-entry purpose inventory. It reviews the 36 entries from the existing #715 sample that were still unknown, mixed, penalty-related, or in conflict.

The question is not whether a driver entered the pit lane. The question is whether the entry is valid evidence for comparing a strategic decision with the deterministic decision layer. An official pit-stop record confirms an entry, but it does not by itself prove that the timing was elective or that the stop was optimal.

Generated 2026-09-08. Sources checked were the local 2025 evidence JSON, official FIA race-control or steward documents where available, and official Formula 1 race reports, team reports, videos, and pit-stop summaries.

## Result

| disposition | entries | meaning |
| --- | ---: | --- |
| `exclude_non_comparable` | 19 | Damage, retirement, a late pit-lane return, or a local row that is not an independent tyre stop. |
| `exclude_mixed_penalty` | 11 | A real tyre stop is mixed with a penalty or a forced service, so its strategic meaning cannot be isolated. |
| `retain_regulation_constrained` | 2 | Real tyre stops at Monaco, but the 2025 two-stop rule constrained the event. Timing remains a separate question. |
| `retain_external_candidate` | 4 | The official record confirms a real stop and there is no identified sanction or failure, but timing discretion is not proven. |
| **Total reviewed** | **36** | No entry is promoted to the clean comparable cohort. |

The clean denominator remains unchanged. These cases do not justify a new decline rate for #715, the diagnostic of real pit entries that the decision layer did not recommend.

## Case register

The lap numbers below are the local `PitInTime` rows. A pair such as `26/27` means two source rows that must remain visible, even when the evidence says that only one physical stop or one retirement sequence occurred.

| race | driver and local lap | local signal | external evidence | recommended disposition |
| --- | --- | --- | --- | --- |
| Barcelona | ALB 26/27 | 10-second penalty; consecutive entry; no tyre-set change resolved | F1 reports front-wing damage, a 10-second penalty, a return to the track, and a later retirement. The official pit summary lists the tyre stop on lap 26. | `exclude_non_comparable`; keep 26 as damage/penalty and 27 as the retirement sequence. |
| Budapest | BEA 48 | No paired out-lap | F1 records Bearman as the only DNF after floor damage. The official pit summary has no Bearman stop at lap 48. | `exclude_non_comparable`. |
| Las Vegas | ALB 35 | 5-second penalty already served; no paired out-lap | The local evidence links the row to a penalty. The race report describes Albon's damage and penalty, not an elective tyre decision. | `exclude_non_comparable`. |
| Lusail | BEA 40/41 | Stop-and-go penalty; consecutive entry | FIA race control records the unsafe-condition investigation, the 10-second stop-and-go award, and service. F1 reports the unsafe release and Bearman's later retirement. | `exclude_mixed_penalty`; do not count either row as strategy. |
| Lusail | HAD 55 | No paired out-lap | F1 reports a late puncture and damaged car after the front-wheel deflector broke. | `exclude_non_comparable`. |
| Lusail | STR 55 | No paired out-lap | The official pit summary records Stroll's stops on laps 7, 24, and 49, not lap 55. The F1 team report describes an offset strategy and a pit-lane penalty. | `exclude_non_comparable`; retain the source row as a late or non-independent pit event. |
| Melbourne | BOR 44 | Intermediate-tyre change mixed with a 5-second penalty | The official pit summary confirms a lap-44 stop. FIA race control records the unsafe-release penalty and its service. | `exclude_mixed_penalty`. |
| Mexico City | ALO 34 | No paired out-lap | F1 reports Alonso stopping with a suspected brake issue and retiring. | `exclude_non_comparable`. |
| Mexico City | HAM 23 | Tyre change mixed with a 10-second penalty | F1 reports Hamilton's lap-23 stop and the 10-second penalty being served during the stop. | `exclude_mixed_penalty`. |
| Mexico City | HUL 25 | No paired out-lap | F1 reports Hulkenberg retiring in the pits with a power-unit issue on lap 28. The official pit summary records the earlier tyre stop on lap 24, not this row. | `exclude_non_comparable`. |
| Mexico City | LAW 5 | No paired out-lap | F1 reports Lawson pitting for a new front wing after lap-1 contact and retiring because the damage was too extensive. The official pit summary records lap 2. | `exclude_non_comparable`. |
| Mexico City | SAI 56 | Drive-through penalty | F1 reports a second pit-lane-speeding penalty escalated to a drive-through, followed by Sainz's late retirement. | `exclude_mixed_penalty`; this is a penalty service, not a tyre decision. |
| Miami | BOR 19 | No tyre metadata in the local row | The official pit summary confirms Bortoleto's lap-19 stop. F1's DHL pit-stop video identifies a medium-to-hard change. | `retain_external_candidate`; do not call it clean until timing discretion is adjudicated. |
| Miami | HAD 22 | No tyre metadata in the local row | The official pit summary confirms Hadjar's lap-22 stop. No race-control penalty or damage is attached to this entry. | `retain_external_candidate`. |
| Miami | LAW 36 | No paired out-lap | F1 reports Lawson retiring after lap-1 contact and damage. The official race result records a 36-lap DNF. | `exclude_non_comparable`. |
| Miami | STR 20 | No tyre metadata in the local row | The official pit summary confirms Stroll's lap-20 stop. No race-control penalty or damage is attached to this entry. | `retain_external_candidate`. |
| Monaco | GAS 8 | No paired out-lap | The official pit summary records Gasly's first-lap stop. F1 reports his lap-9 collision and retirement. | `exclude_non_comparable`. |
| Monaco | RUS 53 | Drive-through plus tyre transition in local telemetry | FIA Document 47 says the penalty was a drive-through. The FIA pit summary records a 19.482-second lap-53 entry, consistent with service rather than a tyre stop. | `exclude_mixed_penalty`; keep the source conflict visible. |
| Monaco | RUS 62 | Same-compound local transition; no tyre change resolved | The FIA pit summary confirms a lap-62 tyre stop. Monaco required two stops and three tyre sets in 2025, so this is regulation-constrained even though the lap itself was chosen by the team. | `retain_regulation_constrained`; never fold into the clean elective cohort. |
| Monaco | SAI 53 | Same-compound local transition; no tyre change resolved | The FIA pit summary confirms a lap-53 stop. The F1 race report describes the mandatory two-stop rule and the late tyre-stop phase. | `retain_regulation_constrained`; timing may be studied separately from the obligation. |
| Montréal | LAW 54 | No paired out-lap | F1 reports Lawson heading to the pits to retire, with a power-unit cooling problem and a lap-57 DNF. | `exclude_non_comparable`. |
| Montréal | STR 51 | Tyre change mixed with a 10-second penalty | The local RCM evidence links the row to the penalty lifecycle. The official pit summary and race report do not turn it into a clean elective decision. | `exclude_mixed_penalty`. |
| Monza | ALO 24 | No paired out-lap | The official pit summary records Alonso's tyre stop on lap 20. F1 reports a later return to the pits and retirement after suspension failure. | `exclude_non_comparable`. |
| Sakhir | NOR 10 | Tyre change mixed with a 5-second false-start penalty | FIA race control records the penalty service. F1 reports that Norris served it during his first tyre stop, with the local and published lap labels offset by one. | `exclude_mixed_penalty`. |
| Sakhir | SAI 44 | Tyre change mixed with a 10-second penalty | The official pit summary confirms Sainz's lap-44 stop. F1 reports the 10-second penalty and damage during the race. | `exclude_mixed_penalty`. |
| Sakhir | SAI 45 | No paired out-lap; same penalty context | F1 reports Sainz retiring after the penalty and damage sequence. | `exclude_non_comparable`. |
| Shanghai | ALO 4 | No paired out-lap | F1 reports Alonso's lap-4 brake failure and retirement. | `exclude_non_comparable`. |
| Silverstone | ANT 23 | No paired out-lap | The official pit summary records Antonelli's stops on laps 2, 9, and 20. F1 reports him as the final retiree after the wet-race incident. | `exclude_non_comparable`. |
| Spa-Francorchamps | BEA 12 | Same-compound local transition; no set change resolved | The official pit summary confirms Bearman's lap-12 stop. F1 reports all cars starting on intermediates and most switching at the dry crossover, so the local compound fields are not sufficient to identify the change. | `retain_external_candidate`; weather and data-quality evidence must stay attached. |
| Spielberg | ALB 15 | No paired out-lap | The official pit summary records Albon's stop on lap 13, not lap 15. | `exclude_non_comparable`; treat lap 15 as a row-alignment or non-independent event. |
| São Paulo | HAM 32 | Same-compound local transition mixed with a 5-second penalty | The official pit summary confirms Hamilton's lap-32 stop. F1 reports that he pitted to serve the penalty and later retired. | `exclude_mixed_penalty`. |
| São Paulo | HAM 37 | No paired out-lap; same penalty context | The official race result records Hamilton's 37-lap DNF. The official pit summary has no independent Hamilton stop at lap 37. | `exclude_non_comparable`. |
| Yas Island | LAW 21 | Tyre change mixed with a 5-second penalty in the local join | The official pit summary confirms Lawson's lap-21 stop. Race-control evidence awards a 5-second penalty and later records service, so the tyre and penalty causes cannot be separated safely. | `exclude_mixed_penalty`. |
| Yas Island | TSU 32 | Tyre change mixed with a 5-second penalty | The official pit summary confirms Tsunoda's lap-32 stop. F1 reports his offset strategy and the five-second penalty served at his own stop. | `exclude_mixed_penalty`. |

## What this changes

The doubtful queue was not a hidden group of 36 missed strategic calls.

- 19 rows have a documented damage, retirement, late-return, or row-alignment explanation.
- 11 rows are real entries but include a sanction or forced service.
- 2 Monaco rows are real tyre stops under the event's mandatory two-stop rule.
- 4 rows are credible strategic candidates, but the available evidence does not establish that the exact lap was discretionary.

The four external candidates are Miami BOR lap 19, Miami HAD lap 22, Miami STR lap 20, and Spa BEA lap 12. The two Monaco rows should be analysed in a separate regulation-constrained cohort. None should be silently added to the clean denominator.

## Proposed next step

1. Add a review-only disposition field to the evidence export, without changing the production scorer.
2. Remove the 30 penalty, damage, retirement, and row-alignment entries from any future clean-cohort calculation while keeping them in the full inventory.
3. Keep the four external candidates and two Monaco regulation-constrained candidates in a review queue.
4. For those six rows, adjudicate timing discretion from pre-entry evidence only. The sources above prove what happened, not that the team had a free strategic choice at that exact lap.
5. Recompute the #715 comparison only after the clean cohort is non-empty and its denominator is reported beside the full 573-entry sample.

This report does not change labels in `MEASURE_724_stop_purpose.json`. It records the external adjudication so a later implementation can be reviewed against a fixed decision map.

## Sources

- [Official 2025 Spanish Grand Prix pit-stop summary](https://www.formula1.com/en/results/2025/races/1262/spain/pit-stop-summary) and [official Spanish Grand Prix race report](https://www.formula1.com/en/latest/article/piastri-leads-mclaren-1-2-from-norris-in-spanish-gp-amid-late-race-drama-for.2t1WkW9NVeMzJbOIkpM8u8)
- [Official 2025 Miami Grand Prix pit-stop summary](https://www.formula1.com/en/results/2025/races/1259/miami/pit-stop-summary), [Miami team report](https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-miami-2025.1Yz75nLpjVhChSzeU8XtHv), and [DHL fastest pit stop video](https://www.formula1.com/en/video/dhl-fastest-pit-stop-2025-miami-grand-prix.1831286162974566560)
- [Official 2025 Monaco pit-stop summary](https://www.fia.com/sites/default/files/2025_08_mon_f1_r0_timing_racepitstopsummary_v01.pdf), [FIA Document 47 for Russell](https://www.fia.com/system/files/decision-document/2025_monaco_grand_prix_-_infringement_-_car_63_-_leaving_the_track_and_gaining_an_advantage.pdf), and [Monaco race report](https://www.formula1.com/en/latest/article/norris-takes-victory-over-leclerc-and-piastri-in-gripping-monaco-grand-prix.4B7frXOoDY8UvKMu25Daoa)
- [Official 2025 Qatar pit-stop summary](https://www.formula1.com/en/results/2025/races/1275/qatar/pit-stop-summary), [FIA Qatar race-control messages](https://api.fia.com/sites/default/files/race_control_messages_3.pdf), and [Qatar team report](https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-qatar-2025.5YOtPlFnoG66V0rN5oqXxj)
- [Official 2025 Mexico pit-stop summary](https://www.formula1.com/en/results/2025/races/1272/mexico/pit-stop-summary), [Mexico race report](https://www.formula1.com/en/latest/article/norris-seals-commanding-win-in-action-packed-mexico-city-gp-to-take-world.5ztiajHhdtqagu0qQLx0vS), and [Sainz and Williams report](https://www.formula1.com/en/latest/article/far-too-many-issues-for-sainz-to-score-in-mexico-city-as-something-not.bzCICfS0wb8G2cHqtYVTC)
- [Official 2025 Bahrain pit-stop summary](https://www.formula1.com/en/results/2025/races/1257/bahrain/pit-stop-summary), [Bahrain race report](https://www.formula1.com/en/latest/article/piastri-storms-to-controlled-victory-in-bahrain-grand-prix-ahead-of-russell.47YQh0Ex2gkZcx58fRaRqJ), and [Bahrain FIA race-control messages](https://www.fia.com/sites/default/files/2025_04_brn_f1_r0_timing_raceracecontrolmessages_v01.pdf)
- [Official 2025 São Paulo pit-stop summary](https://www.formula1.com/en/results/2025/races/1273/brazil/pit-stop-summary) and [São Paulo race report](https://www.formula1.com/en/latest/article/norris-wins-thrilling-sao-paulo-gp-from-antonelli-as-verstappen-climbs-to.4T0Y5xGNn1MOVegzhGTqAx)
- [Official 2025 Abu Dhabi pit-stop summary](https://www.formula1.com/en/results/2025/races/1276/abu-dhabi/pit-stop-summary), [Abu Dhabi race report](https://www.formula1.com/en/latest/article/norris-secures-maiden-f1-title-in-abu-dhabi-with-podium-finish-behind.EMJtmvRA0uzmzUC4MZgmw), and [Tsunoda's post-race report](https://www.formula1.com/en/latest/article/tsunoda-gave-it-everything-until-the-end-as-he-rues-frustrating-penalty-in.2aQcJRzuFkWhUvPnFaT3u1)
- [Official 2025 Belgian pit-stop summary](https://www.formula1.com/en/results/2025/races/1265/belgium/pit-stop-summary) and [Belgian Grand Prix race report](https://www.formula1.com/en/latest/article/piastri-wins-wet-dry-belgian-gp-at-spa-after-late-pressure-from-title-rival-and.7QmPcUP90MvR5iX0w3j91)
- [Official 2025 Canadian pit-stop summary](https://www.formula1.com/en/results/2025/races/1263/canada/pit-stop-summary), [Canadian Grand Prix race report](https://www.formula1.com/en/latest/article/russell-takes-solid-victory-as-piastri-and-norris-collide-late-on-in.2cri9oFCALqhfsbvpqDfBq), and [Lawson's official video](https://www.formula1.com/en/video/lawson-reveals-cooling-issue-forced-him-to-retire-from-the-canadian-grand-prix.1835025091618839348)
- [Official 2025 British pit-stop summary](https://www.formula1.com/en/results/2025/races/1277/great-britain/pit-stop-summary) and [British Grand Prix race report](https://www.formula1.com/en/latest/article/norris-wins-dramatic-wet-dry-british-gp-from-piastri-as-hulkenberg-claims.1puOD82avOZ8I0sca7fvLJ)
- [Official 2025 Austrian pit-stop summary](https://www.formula1.com/en/results/2025/races/1264/austria/pit-stop-summary)
- [Official 2025 Hungarian race result](https://www.formula1.com/en/results/2025/races/1266/hungary/race-result) and [Haas report on Bearman's floor damage](https://www.formula1.com/en/latest/article/ocon-says-haas-need-consistency-after-difficult-hungary-weekend-as-bearman.5r6rV8sjtlEzTFpdsWkGok)
- [Official 2025 Italian pit-stop summary](https://www.formula1.com/en/results/2025/races/1268/italy/pit-stop-summary) and [Italian team report](https://www.formula1.com/en/latest/article/what-the-teams-said-race-day-in-italy-2025.2lj5NmrwbAdbZekiI39SLL)
- [Official 2025 Chinese pit-stop summary](https://www.formula1.com/en/results/2025/races/1255/china/pit-stop-summary) and [Alonso's official brake-failure video](https://www.formula1.com/en/video/chinese-grand-prix-ends-early-for-alonso-after-super-scary-brake-failure.1827369204273108970)
- [Official 2025 Las Vegas pit-stop summary](https://www.formula1.com/en/results/2025/races/1274/las-vegas/pit-stop-summary) and [Las Vegas race report](https://www.formula1.com/en/latest/article/verstappen-beats-norris-for-dominant-las-vegas-gp-victory-as-piastri.6u1Op0SO7YQa2bwJOq8DVI)
