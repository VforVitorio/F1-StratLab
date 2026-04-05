# F1 Strategy Manager — Simulation & Debug Commands

Quick reference for running the agent pipeline without the HTTP layer.

---

## 1. Full system simulation (`run_simulation_cli.py`)

### Without LLM — ML + MC scores only (fast, no API key needed)

```bash
# All laps, Melbourne, NOR
python scripts/run_simulation_cli.py Melbourne NOR McLaren --no-llm

# Specific lap range
python scripts/run_simulation_cli.py Melbourne NOR McLaren --laps 15-35 --no-llm

# Another GP
python scripts/run_simulation_cli.py Bahrain HAM Mercedes --laps 20-40 --no-llm

# With full tracebacks on error
python scripts/run_simulation_cli.py Silverstone NOR McLaren --laps 1-57 --no-llm --verbose
```

### With LLM synthesis (LM Studio running or OpenAI API configured)

```bash
# Full pipeline — sub-agents (gpt-4.1-mini) + orchestrator (gpt-5.4-mini)
python scripts/run_simulation_cli.py Melbourne NOR McLaren --laps 20-30

# Custom featured parquet or raw dir
python scripts/run_simulation_cli.py Monaco LEC Ferrari --laps 50-78 \
    --raw-dir data/raw/2025 \
    --featured data/processed/laps_featured_2025.parquet
```

**Output columns:**

```
Lap | Cmpd | Life | Action     | Conf | STAY  / PIT   / UDCT  / OVCT  | Reasoning
```

---

## 2. Single-agent debug (`debug_agent.py`)

Runs one agent in isolation — no replay engine, no full pipeline.
Looks up real lap data from the featured parquet when available; falls back to synthetic defaults.

### Tire agent (N26)

```bash
# Real data lookup — Melbourne lap 20, NOR
python scripts/debug_agent.py --agent tire --gp Melbourne --lap 20 --driver NOR --team McLaren

# Force specific parameters with --override
python scripts/debug_agent.py --agent tire --gp Melbourne --lap 35 --driver NOR --team McLaren \
    --override tyre_life=28 compound=MEDIUM position=2
```

### Pace agent (N25)

```bash
python scripts/debug_agent.py --agent pace --gp Bahrain --lap 15 --driver HAM --team Mercedes
```

### Race situation agent (N27)

```bash
python scripts/debug_agent.py --agent situation --gp Monaco --lap 50 --driver VER --team "Red Bull Racing"
```

### Pit strategy agent (N28)

```bash
# Basic run
python scripts/debug_agent.py --agent pit --gp Silverstone --lap 28 --driver NOR --team McLaren

# Print full lap_state dict before running
python scripts/debug_agent.py --agent pit --gp Silverstone --lap 28 --driver NOR --team McLaren --print-state

# Override compound + tyre life
python scripts/debug_agent.py --agent pit --gp Bahrain --lap 20 --driver NOR --team McLaren \
    --override compound=MEDIUM tyre_life=18
```

### Radio agent (N29)

```bash
# With explicit radio message
python scripts/debug_agent.py --agent radio --gp Melbourne --lap 10 --driver NOR --team McLaren \
    --radio "Box box, tyres are gone completely"

# No radio message — exercises RCM path only
python scripts/debug_agent.py --agent radio --gp Bahrain --lap 25 --driver HAM --team Mercedes
```

### RAG agent (N30)

```bash
# Default query generated from gp_name
python scripts/debug_agent.py --agent rag --gp Melbourne --lap 20 --driver NOR --team McLaren

# Custom regulation query
python scripts/debug_agent.py --agent rag --gp Monaco --lap 50 --driver LEC --team Ferrari \
    --query "Can a driver change tyres twice in the same lap under VSC?"
```

### Full orchestrator (N31 — needs LLM)

```bash
python scripts/debug_agent.py --agent orchestrator --gp Melbourne --lap 20 --driver NOR --team McLaren
```

---

## 3. `--override` reference

Overrides any field in the `driver` dict of the lap state without touching the rest.
Multiple overrides in one call:

```bash
--override tyre_life=28 compound=MEDIUM position=3 lap_time_s=88.5
```

Supported fields: any key that appears in `driver` — `tyre_life`, `compound`, `compound_id`,
`position`, `lap_time_s`, `speed_st`, `fuel_load`, `stint`, `fresh_tyre`, `gap_to_leader_s`.

---

## 4. Tips

- **No parquet?** The script falls back to synthetic defaults (position=1, lap_time=91.0s, air_temp=28°C, etc.) and prints a warning.
- **Connection error during LLM call?** `_safe_call` in `run_simulation_cli.py` catches it and returns a stub output so the lap does not abort.
- **LM Studio not running?** Use `--no-llm` for the CLI or avoid `--agent orchestrator` in the debug script.
- **Slow startup?** NLP models (RoBERTa, BERT-large, SetFit) load at import time via `radio_agent`. First run always takes 20–40s regardless of which agent you test.
