# #1252 runtime record

`run_id`: `1252-lusail-nor-l7-20260924-run1`

The Arcade process ran with the local 2025 Qatar cache and `--no-llm`. The API
key was empty, and Hugging Face and Transformers were set offline. No model API
call was made.

Command:

```powershell
uv run --no-sync python -m src.arcade.main --viewer --year 2025 --round 23 --driver NOR --team McLaren --strategy --no-llm
```

Observed from the running process:

- FastF1 loaded the cached Lusail race session.
- `TelemetryStreamServer` listened on `127.0.0.1:55998`.
- Arcade spawned the PITWALL child process, PID 44804.
- `F1ArcadeView` reported strategy enabled for Lusail 2025 NOR.
- The PITWALL client connected to the stream.

The captured wire payload records `no_llm=true`, `seq=3227`, decision lap 7,
action `STAY_OUT`, and routed agents N28 and N30. The API and browser reports
and their screenshots use the same run ID:

- [API and wire trace](TRACE_1252_1252-lusail-nor-l7-20260924-run1.json)
- [Browser trace](TRACE_1252_1252-lusail-nor-l7-20260924-run1_browser.json)
- [DATA screenshot](TRACE_1252_1252-lusail-nor-l7-20260924-run1_data.png)
- [AGENTS screenshot](TRACE_1252_1252-lusail-nor-l7-20260924-run1_agents.png)
- [Strict cross-artifact verification](TRACE_1252_1252-lusail-nor-l7-20260924-run1_verified.json)
