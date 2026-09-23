# Decision-layer diagnostic

This is an offline diagnostic of the current production projection path.
It compares the five laps before each real stop. Both `WINDOW_LAPS` and
`DECISION_WINDOW_LAPS` remain 5. It is not a fix and
it does not claim that the real pit wall was strategically correct.

`PitInTime` identifies a pit entry, not its purpose. The population can include
penalties, event-specific tyre rules, and other non-elective entries, so these
figures describe scorer behaviour and are not a pure elective-stop accuracy rate.

- generated `2026-09-08T09:25:46+00:00`
- races: 2025 Austin, 2025 Baku, 2025 Barcelona, 2025 Budapest, 2025 Imola, 2025 Jeddah, 2025 Las_Vegas, 2025 Lusail, 2025 Marina_Bay, 2025 Melbourne, 2025 Mexico_City, 2025 Miami_Gardens, 2025 Monaco, 2025 Montréal, 2025 Monza, 2025 Sakhir, 2025 Shanghai, 2025 Silverstone, 2025 Spa-Francorchamps, 2025 Spielberg, 2025 Suzuka, 2025 São_Paulo, 2025 Yas_Island, 2025 Zandvoort
- projection calls: 8298
- verdicts: 573
- LLM/API calls: none

| bucket | windows | evaluated laps | driver mandatory T/F/U | rival pending T/F/U | deg known | PIT preferred | STAY_OUT dominates | mean PIT-STAY |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |
| `closing_laps` | 4 | 20 | 5/15/0 | 9/330/0 | 19 | 5 | 15 | -0.94895 |
| `min_stint` | 16 | 79 | 21/45/13 | 450/719/204 | 24 | 16 | 63 | -3.282949 |
| `no_boundary_in_window` | 121 | 603 | 583/20/0 | 5685/5283/0 | 486 | 574 | 29 | 1.257607 |
| `no_call_in_window` | 224 | 1120 | 381/719/20 | 7110/11987/360 | 493 | 6 | 1114 | -3.973429 |
| `opening_laps` | 4 | 4 | 4/0/0 | 74/2/0 | 0 | 1 | 3 | -1.5255 |
| `overlap_in_window` | 1 | 5 | 0/5/0 | 0/95/0 | 0 | 1 | 4 | -2.6654 |
| `scored` | 203 | 1015 | 810/200/5 | 9556/8411/80 | 600 | 450 | 565 | -0.499601 |

The next decision is based on this comparison. A positive `PIT-STAY` means
the best eligible pit candidate beat `STAY_OUT` on that evaluated lap.

In `no_call_in_window`, the driver's mandatory stop was pending on 381/1120 laps (34.0%). `STAY_OUT` dominated on 1114/1120 laps (99.5%); the best pit candidate won on 6/1120 (0.5%).
In `scored`, the driver's mandatory stop was pending on 810/1015 laps (79.8%); the best pit candidate won on 450/1015 (44.3%).
