# 2025 pit-entry purpose evidence

This is a retrospective evidence inventory for the decision-layer work.
It does not change the scorer and it does not treat the team's observed
pit entry as proof that the team's decision was optimal.

- generated `2026-09-08T12:20:53+00:00`
- races: 24
- RAW lap rows: 26692
- PitInTime entries: 841
- entries in the current missed-pit-call green sample: 573
- local RCM rows: 1534
- messages containing `PENALTY`: 69
- penalty-text messages classified as generic collisions: 21
- non-null `LapStartDate` rows: 0
- tyre metadata repair: 2 races, 308 ages made unknown
- external API, LLM and private telemetry calls: none

## What the local evidence says

| primary label | entries |
| --- | ---: |
| `PENALTY_SERVICE` | 2 |
| `REGULATION_REQUIRED_STOP` | 34 |
| `STRATEGIC_TYRE_CHANGE` | 707 |
| `UNKNOWN` | 98 |

| telemetry set-change signal | entries |
| --- | ---: |
| `confirmed` | 709 |
| `none_observed` | 2 |
| `unknown` | 130 |

The current data shows 709 entries with a
telemetry set-change signal (compound change or age reset) after the pit
entry, but that is only telemetry evidence. It does not prove the entry was
strategic. Same-compound entries can mount a used set, and a drive-through
can leave contradictory stint metadata.

## Measurement contract

Each entry receives one primary label and keeps secondary causes, evidence IDs,
timing discretion, source conflicts, and whether it belongs to the current
green-flag sample. The clean comparison cohort is intentionally conservative:
strategic candidate, no mixed purpose, no source conflict, and a discretionary
timing decision. Entries with unknown timing discretion remain candidates for
review, not confirmed ground truth.

## Limitations that remain visible

- The local RCM parquet is the filtered runtime mirror; it removes unmapped
  messages, laps 0-1, and the final lap, so it is not the complete retrospective
  official record.
- RAW `LapStartDate` is empty, so this pass does not claim a global UTC join.
  Evidence links use session key, car number extracted from message text, and
  mapped lap as a provisional association.
- Absence of a local message means no evidence in this corpus, not no penalty.
- The classifier's generic event category is not a sanction ledger; a future
  parser must preserve awarded, served, cancelled, investigated, and unresolved
  states separately.

## Adjudication check

Monaco 2025 Russell is deliberately retained as a conflict: local telemetry
shows a compound transition on lap 53, while the official race-control record
announces a drive-through and the official pit summary lists entries on laps 53,
62, and 68. The inventory therefore labels lap 53 as `PENALTY_SERVICE` with
`source_conflict=true`; it does not silently trust the tyre columns. Sources:
[FIA decision](https://www.fia.com/system/files/decision-document/2025_monaco_grand_prix_-_infringement_-_car_63_-_leaving_the_track_and_gaining_an_advantage.pdf),
[race-control messages](https://api.fia.com/sites/default/files/2025_08_mon_f1_r0_timing_raceracecontrolmessages_v01.pdf),
and [pit-stop summary](https://www.fia.com/sites/default/files/2025_08_mon_f1_r0_timing_racepitstopsummary_v01.pdf).

## Decision

Do not connect these labels to the production scorer yet. The next required
step is to recover or reconcile the complete 2025 race-control record and
manually review penalties, conflicts, mixed-purpose entries, and a stratified
sample of strategic candidates before recalculating the no-call denominator.
