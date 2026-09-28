# Audit A5: Repeated constants and prompt rules

Scope: `src/agents/`, `src/strategy/`, `src/simulation/`, `scripts/`, and `tests/`.

This checkout had six rules repeated between code, model prompts, configuration, or evaluation data. Four copies agreed at the time of the audit; the compound boundary disagreed in two prompts. F7 is a lower-priority default, not a decision threshold. Verify each cited path against the current branch before treating this report as a live defect list.

## Findings

### F1. Undercut threshold in the pit-agent prompt

N16 exports `best_threshold = 0.522` to `model_config_undercut_v1.json`; `PitAgentCFG` loads it as `undercut_threshold` (`src/agents/pit_strategy_agent.py:230`). The tool compares calibrated probability against that field and returns the active threshold (`:1194-1200`). The plain-string `_PIT_STRATEGY_SYSTEM_PROMPT` repeats `0.522` at `:611`.

The values matched in the audited model and notebook, and both sides use calibrated probabilities. No test checked the prompt against the loaded value. A retrain can update the JSON while leaving the prompt stale. The tool's response exposes the active threshold, so the mismatch is visible to the model, but its system rule still teaches the old value. Build this part of the prompt from the agent configuration. The prompt is currently module-level and is created before a `PitAgentCFG` instance exists, so construction must move to agent initialization or a lazy builder.

### F2. Safety-car response cutoff

`OrchestratorCFG.sc_prob_threshold` is `0.30` (`src/agents/strategy_orchestrator.py:127`), and the orchestrator uses it at `:587` and `:1919`. The pit agent repeats the cutoff in `sc_reactive` (`src/agents/pit_strategy_agent.py:1592-1593`) and twice in its plain-string prompt (`:612`, `:664`). These independent values matched in the audited checkout. The pit agent does not import the orchestrator configuration, and no test tied its flag or prompt text to the configured threshold.

The cutoff also lacks a measured firing rate. N27's `high_sc` band is `0.0864`, but the pit flag uses `0.30`; that may be an intentional stricter gate for the N30 RAG call. Measure the rate before changing the value. Then centralize the cutoff and render it into both prompts. Check the `>` versus `>=` comparison at the exact boundary when adding coverage.

### F3. Tyre-cliff bands in the tire-agent prompt

The global config and `TireAgentCFG` use 3 laps for `PIT_SOON` and 7 for `MONITOR` (`src/agents/tire_agent.py:203-204`; `data/models/agents/tire_agent_config_v1.json`). `TireOutput` reads `get_cliff_thresholds(gp_name)` at `:399-406`. The plain-string `_TIRE_SYSTEM_PROMPT` repeats 3 and 7 at `:720`, `:732-734`.

The live config had no `cluster_aware_thresholds` block, so the values matched for every GP in that checkout. The classifier supports GP and cluster overrides, but the import-time prompt cannot follow them. Build the prompt after the GP and configuration are known if those overrides are enabled.

### F4/F5. Compound boundary disagrees in both prompts

`recommend_compound_tool` uses `_STINT_CAPACITY_LAPS = {SOFT: 18, MEDIUM: 30, HARD: 38}` (`src/agents/pit_strategy_agent.py:91,1255,1268-1271`). The tool docstring agrees (`:1213-1215`). The pit-agent prompt instead says SOFT is suitable up to 15 laps, MEDIUM for 12-30, and HARD from 20 (`:654-658`). The N31 orchestrator repeats those same limits as hard guard rails (`src/agents/strategy_orchestrator.py:1594-1605`).

At 16 laps remaining, the tool returns SOFT because 18 is the capacity bound; both prompts prohibit SOFT above 15. Between 21 and 30 laps, the prompt says HARD is suitable while the tool still selects MEDIUM. These are live disagreements in the audited code, not drift risks. The prompts tell the model that the text overrides tool advice, and tests did not compare either prompt with the tool boundary.

Remove the duplicate compound prose and let the tool decide, or render the prompt limits from `_STINT_CAPACITY_LAPS`. The other pit guard rails match `src/strategy/inference/guard_rails.py` (`_NO_PIT_BEFORE_LAP=5`, `_NO_PIT_LAST_N_LAPS=3`, `_CLIFF_P10_SAFE=2`, minimum stint 8/12/15). Keep those checks distinct from compound suitability.

### F6. Monte Carlo horizon is repeated across three modules

The five-lap horizon appears in `strategy_orchestrator.WINDOW_LAPS` (`src/agents/strategy_orchestrator.py:625`), `decision_modes.DECISION_WINDOW_LAPS` (`src/strategy/eval/decision_modes.py:76`), and `scripts/measure_mc_tables.py:83`. The committed `data/mc_measured_v1.json` also records five laps. All four values agreed in the audited checkout. `decision_modes.py` documents that its value must match the runtime horizon, but imports do not enforce it. The test at `tests/mc/test_mc_measured_tables.py:63` checks only that the JSON says `5`.

If the runtime horizon changes without regenerating the measured tables, the engine scores over a different window from the one used for `sc_window`, `stop_hazard`, and `gap_density`. Use one lightweight source for the three consumers and have a test compare the measured horizon with the runtime horizon. Avoid importing the full orchestrator if that loads agent modules; a small shared module may be needed.

### F7. Repeated `risk_tolerance` default

The default `risk_tolerance=0.5` appears at about eleven call sites. This is a default, not a threshold or live guard. Leave it alone unless those call sites are already being changed; then consider one shared default.

## Checks that did not produce findings

- `guard_rails.py` is imported by `no_llm.py`, `decision_modes.py`, and `stint_lengths.py`; `tests/eval/test_stint_lengths.py:126` checks identity for `_MIN_STINT_LAPS`.
- N27 keeps calibrated threat bands separate from raw classifier thresholds. Its prompt reads `CFG`, and `tests/audit/test_race_situation_hardening.py` checks effects and base-rate behavior.
- Regulation rails and neutralization state are computed in shared code; tests assert the resulting behavior rather than restating the numbers.
- `GAP_UNKNOWN_FALLBACK_S` is shared with the backend. The OpenF1 interval extractor under `src/data_extraction/` is archival; live DRS timing is in `src/shared/data_extraction/openf1_extractor.py`.
- `_STINT_CAPACITY_LAPS` and the pit tool's docstring agree. The mismatch is confined to the two prompt copies described in F4/F5.
- The orchestrator's dynamic sub-agent summaries read live output values. `pace_agent.py` and `radio_agent.py` had no duplicated numeric thresholds in the prompts checked.
- `test_mc_measured_tables.py:63` was the only discovered-set test without an emptiness guard; `test_stint_lengths.py` already has one.
