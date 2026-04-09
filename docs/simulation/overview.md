# src/simulation — Race Replay Engine

## Purpose

Offline replay of a race from a stored parquet snapshot. Emits `lap_state` dicts — the canonical data contract consumed by all seven strategy agents.

This is the **demo path** for the thesis defense. The live path (Kafka consumer feeding real telemetry) will replace the iterator in v0.14+ without touching any agent code, because agents only see `lap_state` dicts regardless of source.

## Architecture

```
data/raw/2025/<GP>/
  laps.parquet        ← loaded by RaceReplayEngine
  weather.parquet     ← loaded if present
  metadata.json       ← gp_name, year

RaceReplayEngine
  └── RaceStateManager          ← data boundary enforcement
        ├── get_driver_state()  ← full telemetry (our car)
        ├── get_rival_states()  ← timing-screen only (rivals)
        ├── get_weather_state() ← track + weather snapshot
        └── get_lap_state()     ← merges all into lap_state dict
              ↓
    lap_state dict → all 7 agents → strategy orchestrator
              ↓
    to_arcade_frame() → WebSocket /ws/replay → Arcade UI
```

## Data Boundary (architectural constraint)

The single most important design decision in this module.

| Field | Our driver | Rivals |
|---|---|---|
| LapTime | yes | yes |
| Sector1/2/3 | yes | NO |
| SpeedI1, SpeedI2, SpeedFL | yes | NO |
| SpeedST | yes | yes |
| TyreLife | yes | yes (broadcast) |
| Compound | yes | yes |
| FuelLoad | yes (estimated) | NO |
| Position | yes | yes |
| gap_to_leader | yes | yes |
| interval_to_driver | yes | yes |

Rivals get only what appears on the FIA live timing screen. This mirrors the real information asymmetry a strategy engineer faces on the pit wall.

## Gap Computation

Gaps are derived from cumulative `LapTime` differences rather than from the intervals OpenF1 API feed. This is the standard F1 analytics approach (see TUMFTM race-simulation methodology).

```
gap_to_leader[driver, lap] = cum_time[driver, lap] - cum_time[leader, lap]
interval_to_driver[rival, lap] = cum_time[rival, lap] - cum_time[our_driver, lap]
```

Known limitations (acceptable for thesis demo):
- Safety car bunching is not reflected accurately.
- Lapped cars show large positive gaps, not "lapped" flag.

## Files

| File | Responsibility |
|---|---|
| `race_state_manager.py` | Data boundary, per-lap state construction |
| `replay_engine.py` | Parquet loading, lap iterator, Arcade frame builder |
| `__main__.py` | Terminal CLI for quick testing |

## Running

```bash
# All laps, no delay
python -m src.simulation Melbourne NOR McLaren

# Specific lap range
python -m src.simulation Monaco HAM Mercedes --laps 30-50

# 2s between laps (simulates real-time ingestion)
python -m src.simulation Melbourne NOR McLaren --interval 2

# Different season
python -m src.simulation Silverstone VER "Red Bull Racing" --data-dir data/raw/2024
```

### Example output — `python -m src.simulation Melbourne NOR McLaren --interval 2`

```
------------------------------------------------------------------------
  F1 Strategy - Race Replay   Melbourne  |  NOR / McLaren  |  57 laps
------------------------------------------------------------------------
   Lap  Pos      Compound   LapTime  Gap Leader                     Ahead                    Behind
------------------------------------------------------------------------
     1    1  INT( 1L)  1:57.099    +0.000s                            P2:VER INT( 1L)  +2.293s
     2    1  INT( 2L)    ---.-     +0.000s                            P2:VER INT( 2L)  +4.586s [IN]
    ...
    20    1  INT(20L)  1:30.710    +0.000s                            P2:PIA INT(20L) +13.836s
    34    1  INT(34L)  2:02.273    +0.000s                            P2:PIA INT(34L) +19.398s [IN]
    35    1  HAR( 2L)  2:03.448    +0.000s                            P2:PIA HAR( 2L) +19.731s [OUT]
    44    6  HAR(11L)  1:45.587   +34.252s  P5:LEC HAR(11L) +56.481s  P7:LAW MED(11L) +79.194s [IN]
    46    3  INT( 2L)  1:31.567   -62.788s  P2:LEC HAR(13L) +56.205s  P4:TSU MED(13L) +62.387s
    57    1  INT(13L)  1:27.126    +0.000s                            P2:VER INT(11L) -18.289s
------------------------------------------------------------------------
  Replay complete - 57 laps shown.
```

**Reading the output:**

| Column | Meaning |
|---|---|
| `Lap` | Lap number |
| `Pos` | Our driver's position |
| `Compound` | Tyre compound abbreviation + laps on tyre — `INT(20L)` = Intermediate, 20 laps; `HAR(2L)` = Hard, 2 laps; `MED` = Medium; `SOF` = Soft |
| `LapTime` | Lap time in M:SS.mmm. `---.-` = deleted lap (red flag, pit-in lap, etc.) |
| `Gap Leader` | Our gap to P1 in seconds. `+0.000` = we are the leader. Negative means we are leading by that margin after a VSC/SC reset |
| `Ahead / Behind` | Rival directly ahead/behind in position: driver code, compound, laps on tyre, gap to us |
| `[IN]` | Driver pitted this lap (in-lap) |
| `[OUT]` | Driver exiting the pits (out-lap) |

**Melbourne 2025 highlights visible in the replay:**
- Laps 1-7: NOR leads from the start on Intermediates, VER 2.3s behind
- Lap 17: VER drops to P3, PIA now P2 — 14.1s gap
- Lap 34: NOR pits → `[IN]`, exits on Hards lap 35 → `[OUT]`
- Lap 44: NOR temporarily P6 (+34s gap) as rivals haven't pitted yet — this is the undercut working out
- Lap 46: NOR recovers to P3, then P1 by lap 47 after rivals pit on rain
- Lap 57: NOR wins by ~18s over VER

## lap_state Schema

```python
{
    "lap_number": int,
    "driver": {
        # Timing
        "lap_time_s": float | None,
        "sector1_s": float | None,
        "sector2_s": float | None,
        "sector3_s": float | None,
        # Position
        "position": int | None,
        "gap_to_leader_s": float | None,
        # Tyre
        "compound": str,          # "SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"
        "compound_id": int | None, # 0-4
        "tyre_life": int | None,
        "stint": int | None,
        "fresh_tyre": bool,
        # Speed traps
        "speed_i1": float | None,
        "speed_i2": float | None,
        "speed_fl": float | None,
        "speed_st": float | None,
        # Other
        "fuel_load": float | None,  # 0.0–1.0 fraction
        "track_status": str,        # "1"=green, "2"=yellow, "4"=SC, "5"=red
        "is_in_lap": bool,
        "is_out_lap": bool,
    },
    "rivals": [                     # sorted by position
        {
            "driver": str,
            "team": str,
            "position": int | None,
            "lap_time_s": float | None,
            "compound": str,
            "tyre_life": int | None,
            "stint": int | None,
            "speed_st": float | None,
            "gap_to_leader_s": float | None,
            "interval_to_driver_s": float | None,  # + = ahead of us, - = behind us
            "is_pitting": bool,
        },
        ...
    ],
    "weather": {
        "track_status": str,
        "air_temp": float | None,
        "track_temp": float | None,
        "humidity": float | None,
        "wind_speed": float | None,
        "rainfall": bool,
    },
    "session_meta": {
        "gp_name": str,
        "year": int,
        "driver": str,
        "team": str,
        "total_laps": int,
    }
}
```

## Arcade Frame Schema

Output of `RaceReplayEngine.to_arcade_frame()`. Sent over `/ws/replay` WebSocket.

```json
{
    "lap": 25,
    "gp": "Melbourne",
    "total_laps": 57,
    "cars": [
        {
            "driver": "NOR", "team": "McLaren",
            "position": 1, "compound": "INTERMEDIATE",
            "tyre_life": 25, "gap_to_leader": 0.0,
            "interval": 0.0, "is_our_driver": true
        },
        {
            "driver": "PIA", "team": "McLaren",
            "position": 2, "compound": "INTERMEDIATE",
            "tyre_life": 25, "gap_to_leader": 12.693,
            "interval": 12.693, "is_our_driver": false
        }
    ],
    "weather": {"track_status": "1", "air_temp": 15.4, ...},
    "recommendation": {
        "action": "STAY",
        "rationale": "Gap to PIA comfortable, no undercut threat.",
        "confidence": 0.84,
        "tyre": "INTERMEDIATE",
        "laps_remaining_on_tyre": 12,
        "risk_flags": []
    },
    "agent_outputs": {
        "pace": {"lap_time_pred": 90.1, "delta_vs_median": -0.6},
        "tire": {"deg_rate": 0.21, "laps_to_cliff": 14},
        "sc_prob": 0.07,
        "overtake_prob": 0.18
    }
}
```

`recommendation` and `agent_outputs` are absent when `None` is passed to `to_arcade_frame()`.

## Future: Kafka Integration (v0.14)

Replace `RaceReplayEngine.replay()` with a `LiveKafkaConsumer.consume_lap()` iterator that emits the same `lap_state` dict from a live Kafka topic. Zero changes to agents or orchestrator.

```python
# Current (offline)
for lap_state in engine.replay():
    ...

# Future (live)
for lap_state in kafka_consumer.consume_lap():
    ...
```
