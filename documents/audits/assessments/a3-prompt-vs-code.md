# AUDIT A3: Prompt vs Code (agent prose rules vs deterministic and downstream enforcement)

Adversarial gate. Read-only audit, no LLM/API calls. Enumerates every behavioural rule
stated in prose inside the agent prompts (N25-N31) and checks whether code enforces it,
whether the exception sets match, and what happens when the LLM ignores a prompt-only rule.

Status: COMPLETE.

---

## Scope

- `src/agents/pit_strategy_agent.py` (N28), prompt ~L560-700 and full file
- `src/agents/tire_agent.py` (N26)
- `src/agents/race_situation_agent.py` (N27? / SC agent)
- `src/agents/pace_agent.py` (N25)
- `src/agents/radio_agent.py` (N29)
- `src/agents/rag_agent.py` (RAG tool agent)
- `src/agents/strategy_orchestrator.py` (N31)
- `src/strategy/inference/guard_rails.py` (the deterministic mirror)

## Already known (excluded from "new findings", but re-checked)

1. SC exception on early-race and minimum-stint bounds. Fixed today.
2. End-of-race bound intentionally has NO SC exception in code (Art. 55.17). Reasoning checked.
3. Damage/puncture/mechanical exception on early-race bound is NOT wired into code. Known and documented.

---

## Findings log (append-only, most recent at bottom until final ranking)

### F1: N28's "COMPOUND vs REMAINING LAPS" hard bound contradicts its recommended tool

Prompt (`pit_strategy_agent.py:654-658`, inside "## Strategic guard-rails (HARD constraints...)"):
```
COMPOUND vs REMAINING LAPS:
  SOFT: recommend only if remaining laps <= 15 (it won't last longer).
  MEDIUM: suitable for 12-30 remaining laps.
  HARD: suitable for 20+ remaining laps.
```
Also restated verbatim as N31's own guard-rail #5 (`strategy_orchestrator.py:1604-1605`):
```
5. Compound must fit remaining laps: SOFT only if <= 15 laps remain,
   MEDIUM for 12-30, HARD for 20+. Wrong compound forces an extra stop.
```

The only tool N28 is told to call for a compound suggestion is defined in `pit_strategy_agent.py:91`:
```python
_STINT_CAPACITY_LAPS: dict[str, int] = {"SOFT": 18, "MEDIUM": 30, "HARD": 38}
```
`recommend_compound_tool` uses this at `pit_strategy_agent.py:1255,1269,1273`. It sets SOFT capacity to 18 (not 15), MEDIUM to 30 (matching only the upper bound), and HARD to 38 (not 20+).

1. HARD rule per both prompts ("HARD constraints" / "STRATEGIC GUARD-RAILS (HARD...)").
2. Enforcement: **none in code for the stated 15/12-30/20+ bound.** No post-processing validates `COMPOUND:` against `remaining_laps`. `apply_guard_rails`, the deterministic mirror, has no compound-vs-laps check; it implements only the three known numeric bounds (early-race, end-of-race, and min-stint). A full grep of `guard_rails.py` (111 lines) found no compound/remaining-laps logic.
3. Exception sets: N/A because this is not a suspend/exempt rule. The two prompt copies agree on 15/12-30/20+, while the code that selects a compound by remaining-laps math uses 18/30/38. The tool's docstring calls these "Pirelli average stint capacities," a different and more realistic measure. It describes the tool as a *fallback/priority-2* heuristic, so the distinction may reflect intentional domain modelling: Pirelli capacity versus a stricter strategic margin. Neither prompt nor tool docstring explains that distinction. With 16 laps remaining, `recommend_compound_tool` returns `SOFT` because 18 >= 16, although the prompt's "HARD constraint" forbids SOFT above 15 laps. The conflict affects laps 16-17. For laps 21-29, the tool may prefer MEDIUM because its capacity is 30, while the prompt says HARD is suitable for 20+ without ruling MEDIUM out. That case is not a direct contradiction; only the SOFT boundary conflicts.
4. If the LLM trusts the tool over its guard-rail text, it can return a COMPOUND value that the "HARD constraint" forbids. Neither `strategy_orchestrator.py` nor `no_llm.py` validates `PitStrategyOutput.compound_recommendation` against `remaining_laps`; a grep found no post-hoc compound/laps check.

Severity: **MEDIUM**. The issue is non-deterministic and limited to laps 16-17 on SOFT, when the LLM follows the tool instead of the prompt. The likely cost is one avoidable extra stop, not a race-ending error. The prompt's HARD constraint still conflicts numerically with the code whose job is to select a compound by remaining laps.

---

### F2: Three copies of the end-of-race SC exception, with N28's prompt as the outlier

The audit brief says the deterministic code deliberately drops the SC exception on the end-of-race bound under Art. 55.17. Reading `guard_rails.py:68-76` confirmed this. The brief missed a third copy of the rule in N31's prompt, which already agrees with the code. **Only N28's prompt, the focus of the brief, is stale.**

N28 prompt (`pit_strategy_agent.py:626-628`):
```
PIT WINDOW — end of race:
  NEVER recommend PIT_NOW, UNDERCUT, or OVERCUT when remaining laps <= 3.
  Exception: tyre failure is imminent (laps_to_cliff P10 < 2) or Safety Car deployed.
```
N31 orchestrator's OWN restatement of the same guard-rail (`strategy_orchestrator.py:1598-1599`):
```
2. NO pit action when remaining laps <= 3 unless tyre failure imminent
   (cliff P10 < 2 laps). Pit cost ~22s vs ~1.5s recovery = ~13 positions lost.
```
Code (`guard_rails.py:98-99`, matches N31, not N28):
```python
if remaining_laps <= _NO_PIT_LAST_N_LAPS and cliff_p10 >= _CLIFF_P10_SAFE:
    return "STAY_OUT", f"guard-rail: too late to pit (<={_NO_PIT_LAST_N_LAPS} laps left)"
```
(`sc_active` is not referenced in this branch. Only the tyre-cliff exception survives, matching N31's wording rather than N28's.)

1. HARD rule, all three copies.
2. Enforced in `guard_rails.py`, but that code runs only on the **no-llm** path (`no_llm.py:293`) and in `decision_modes.py`'s evaluation harness. The live LLM pipeline never invokes it: `strategy_orchestrator.py` has no import or call to `apply_guard_rails` (grep returned zero hits).
3. Exception sets side by side:
   - N28 prompt: `{tyre failure imminent, SC deployed}`
   - N31 prompt: `{tyre failure imminent}`; SC dropped
   - `guard_rails.py`: `{tyre failure imminent}`; SC dropped (matches N31 and contradicts N28)
   The deliberate fix is present in N31's prompt and the deterministic mirror, but N28's prompt was not updated. **The live LLM path therefore has two conflicting sources of truth.** N28 tells its agent that SC exempts the bound. N31 tells the orchestrator that it does not, and instructs it to override any sub-agent action that "violates" its rules with STAY_OUT. N31 synthesizes the final `StrategyRecommendation`, so its version, which matches the code, probably determines the final decision. However, N28's `PitStrategyOutput.action` and `.reasoning` are inputs to N31 and also appear directly in the CLI/arcade/webapp pit block (`pit_block` at `strategy_orchestrator.py:1560-1568`). In the last 3 laps, they can show a PIT_NOW/UNDERCUT/OVERCUT recommendation justified by "SC deployed". N31 may then override it, but N28's displayed reasoning still teaches the wrong rule to readers of the CLI verbose output, arcade agents tab, or decision-memory accumulator inputs.
4. N31's instruction to "override to STAY_OUT and explain why" is the only backstop. It relies on the LLM recognizing that N28 followed a rule N31 no longer accepts. No code validates `PitStrategyOutput.action` against N31's guard-rails before N31 reads it.

Severity: **MEDIUM-HIGH**. The Art. 55.17 fix is active on the path that produces the final recommendation, so the feared race-ending regression that would recreate #464 is NOT reproduced end-to-end. N28's prompt still conflicts with the design, contaminates its `reasoning` field, and could silently reintroduce the SC exception if a future edit changes N31 to match N28.

---

### F3: N28 and N31 define REACTIVE_SC differently

N28 prompt (`pit_strategy_agent.py:660-666`):
```
REACTIVE_SC usage:
  REACTIVE_SC is for the rare in-between case where sc_prob is elevated but the
  Safety Car is NOT yet deployed.  When the prompt states "SC STATUS: SAFETY CAR
  DEPLOYED RIGHT NOW", prefer PIT_NOW directly.  Use REACTIVE_SC only when
  sc_prob >= 0.30 AND the prompt shows the legacy "SC probability" line.  A high
  sc_prob without confirmation is still a contingency — mention it in reasoning
  and set ACTION to STAY_OUT unless the SC is actually out.
```
→ REACTIVE_SC means: SC **NOT** confirmed, probability elevated (pre-emptive read). When SC **IS** confirmed, N28 is told to prefer **PIT_NOW**, not REACTIVE_SC.

N31 orchestrator's own guard-rail #3 (`strategy_orchestrator.py:1600-1601`):
```
3. REACTIVE_SC only when SC IS deployed (confirmed). High sc_prob is a
   contingency trigger, not a primary action — use STAY_OUT with SC contingency.
```
→ REACTIVE_SC means the SC **IS** confirmed. When only sc_prob is elevated, N31 says do **NOT** use REACTIVE_SC; use STAY_OUT instead.

These are the exact inverse of each other on both ends of the condition:
| Condition | N28 says | N31 says |
|---|---|---|
| SC confirmed deployed right now | prefer PIT_NOW (not REACTIVE_SC) | REACTIVE_SC is exactly this case |
| SC NOT confirmed, sc_prob >= 0.30 | REACTIVE_SC is exactly this case | not REACTIVE_SC; STAY_OUT with contingency |

1. Both prompts state the rule as HARD/authoritative. N28's REACTIVE_SC text sits under the `## Strategic guard-rails (HARD constraints — override any decision rule above)` header at line 616; no later subheading changes its status.
2. The live LLM path enforces neither definition. `guard_rails.py`'s `_PIT_ACTIONS` frozenset includes `"REACTIVE_SC"` as a pittable action subject to the three numeric bounds. It does not distinguish confirmed SC from elevated SC probability; that distinction appears only in the prompts.
3. Exception sets: see the table above. This is not an exception-set mismatch; the two prompts invert the core predicate.
4. If N28 follows its prompt and emits `REACTIVE_SC` while `sc_currently_active=False, sc_prob=0.35`, the call is valid under N28's text. N31 reads it in `pit_block` and may judge it a **violation of N31's guard-rails**, which define REACTIVE_SC as valid only when SC is deployed, then override it to STAY_OUT. If SC is confirmed and N28 emits PIT_NOW instead, N31 accepts that: its rule restricts when REACTIVE_SC may be used but does not require it under confirmed SC. The failure is asymmetric. N31 is primed to second-guess N28's elevated-but-unconfirmed SC calls.
    The only code artifact touching this concept is `sc_reactive` at `pit_strategy_agent.py:1592-1594` (`sc_currently_active or action=='REACTIVE_SC' or (sc_prob>=0.30 and action in ('PIT_NOW','UNDERCUT'))`). This boolean on `PitStrategyOutput` is not a validator. It neither corrects nor blocks the agents' interpretations; it records whether an SC signal informed the action for downstream consumers such as MC scoring and the memory block. Because it treats all three predicates as equivalent evidence of "SC-reactive", it cannot resolve the disagreement between N28 and N31.

Severity: **HIGH**. The audit brief says no test catches this LLM-only contradiction because the tests for these bounds sit behind a `data/models/` gate. The prompts invert a named enum value in the same call chain, and N31 is explicitly told to overrule N28 on this kind of disagreement. The likely bias is to suppress a legitimate pre-emptive SC read and return STAY_OUT when a Safety Car may be imminent.

N31's action schema clarifies the conflict. Its `action` field cannot be `REACTIVE_SC`: `strategy_orchestrator.py:252` declares `_ACTION_VALUES = Literal["STAY_OUT", "PIT_NOW", "UNDERCUT", "OVERCUT", "ALERT"]`, and the reasoning rubric repeats that list at `strategy_orchestrator.py:1676-1677` with the instruction "Do not invent new values". Guard-rail #3 therefore tells the orchestrator how to interpret `REACTIVE_SC` in N28's `pit_block`; N31 must map it to STAY_OUT or PIT_NOW. N28 defines the `PitStrategyOutput.action == 'REACTIVE_SC'` value one way, while N31 applies the opposite definition when choosing its own action.

---

### F4: N31's minimum-stint rule omits the SC exception in N28 and `guard_rails.py`

N28 prompt (`pit_strategy_agent.py:635-652`, full text quoted because the exception is load-bearing prose, not a one-liner):
```
MINIMUM STINT LENGTH before a pit makes sense:
  SOFT: current tyre_life must be >= 8 laps before recommending a stop.
  MEDIUM: >= 12 laps.  HARD: >= 15 laps.
  If the driver has NOT completed the minimum stint, recommend STAY_OUT (the current
  set still has useful life; pitting now wastes a tyre allocation).

  EXCEPTION — SC ACTIVE: when the prompt states "SC STATUS: SAFETY CAR DEPLOYED
  RIGHT NOW", the minimum stint constraint DOES NOT APPLY: a stop under a deployed
  SC is far cheaper because the field is delta-limited and queued behind the SC, so
  your RELATIVE loss shrinks.
  This makes pitting cheaper. It does NOT make it correct: weigh it against what a
  stop surrenders. [...] Decide on the race state, not on the SC alone.
```
Code, fixed today (`guard_rails.py:104-109`):
```python
min_life = _MIN_STINT_LAPS.get(compound, _DEFAULT_MIN_STINT)
if tyre_life < min_life and not sc_active:
    return (
        "STAY_OUT",
        f"guard-rail: minimum stint not reached ({compound} {tyre_life}/{min_life} laps)",
    )
```
→ suspended under SC, matching N28.

N31 orchestrator's own restatement (`strategy_orchestrator.py:1602-1603`):
```
4. Minimum stint before pit: SOFT >= 8 laps, MEDIUM >= 12, HARD >= 15.
   If tyre_life is below minimum, override to STAY_OUT (current set has life left).
```
→ **no SC exception at all.** Nothing in N31's guard-rail #4, nor anywhere else in the ~150-line prompt-builder function (`_build_orchestrator_prompt`, read in full, `strategy_orchestrator.py:1443-1707`), tells the orchestrator that a confirmed SC suspends the minimum-stint bound.

1. HARD rule, all three copies (same header logic as F2/F3).
2. Enforced in code (`guard_rails.py`), but only on the no-llm path, same caveat as F2.
3. Exception sets:
    - N28 prompt: `{SC active}` exempts. N28 is still told to weigh race state; the exception alone does not make a pit action correct.
    - `guard_rails.py`: `{SC active}` exempts, matching N28 and today's fix.
    - N31 prompt: `{}`; no exemption. This reverses F2. There, N31 matched the intentionally SC-blind code and N28 was stale. Here, N28 and the code correctly exempt SC, while **N31 is stale**. It describes the pre-#716 blanket minimum-stint bound without SC awareness, which today's `guard_rails.py` fix changed.
4. Downstream effect: N31 writes the final `StrategyRecommendation.action`. It instructs itself to override a sub-agent action to STAY_OUT when that action violates its rules. If N28 emits `PIT_NOW`/`UNDERCUT` under confirmed SC while `tyre_life` is below the compound minimum, its exception and the fixed `guard_rails.py` allow that action. N31's rule 4 has no SC clause, so it may treat the action as a violation and **override it to STAY_OUT**. That would restore the over-conservative-under-SC behavior that the `guard_rails.py` docstring (line 66) warns against: "a bound written to catch nonsense must not be what blocks the most valuable stop in racing". Unlike F2, **N31 could cancel today's fix at synthesis even though N28 and the deterministic mirror are correct.**

Severity: **HIGH**. This is the most direct consequence of the three prompt copies drifting. N31 can undo today's fix, which suspends the minimum-stint bound under SC, because its guard-rail text was not updated with `guard_rails.py` and N28. It is the same bug class, one pipeline layer downstream, so a change limited to `guard_rails.py` and N28's prompt would miss it.

---

### F5: N27 and N31's opening-lap threat discount cannot affect `threat_level`

Correction to my first pass: I checked only `strategy_orchestrator.py` and incorrectly treated this as a single-prompt rule. `race_situation_agent.py` (N27), which produces `threat_level`, contains matching prose. I missed it because its header says "Strategic guard-rails" without N31's "HARD" qualifier. Rechecking both prompts showed they agree. The problem is structural: neither LLM can set the field it is told to discount.

N27 prompt (`race_situation_agent.py:819-831`):
```
## Strategic guard-rails
- OPENING LAPS (laps 1-3): Race starts naturally inflate both overtake probability
  and SC risk due to first-lap chaos, bunched-up grid, and cold tyres. These are
  normal start dynamics, not genuine strategic threats. When reporting for laps 1-3:
   * Append "opening-lap inflation — discount for strategy decisions" to your reasoning.
  * Consider the effective threat ONE LEVEL LOWER than raw numbers suggest
    (HIGH → treat as MEDIUM, MEDIUM → treat as LOW for strategic purposes).
  * Note that DRS is typically not activated until lap 3, so overtake probability
    in laps 1-2 is inflated by models trained on DRS-enabled data.
```
N31 orchestrator prompt (`strategy_orchestrator.py:1606-1607`), consistent with N27:
```
6. Opening laps 1-3: threat levels from N27 are inflated by start chaos.
   Discount them one tier (HIGH→MEDIUM, MEDIUM→LOW) for decision-making.
```

The field both instructions target, `RaceSituationOutput.threat_level`, is declared `field(init=False)` and computed ENTIRELY in `__post_init__` (`race_situation_agent.py:305,312-318`):
```python
threat_level: str = field(init=False)
...


def __post_init__(self) -> None:
    if (
        self.sc_currently_active
        or self.overtake_prob >= CFG.high_overtake
        or self.sc_prob_3lap >= CFG.high_sc
    ):
        self.threat_level = "HIGH"
    elif self.overtake_prob >= CFG.medium_overtake or self.sc_prob_3lap >= CFG.medium_sc:
        self.threat_level = "MEDIUM"
    else:
        self.threat_level = "LOW"
```
No parameter here is `lap_number`. A full grep of `race_situation_agent.py` found no code path that reads the current lap and adjusts `overtake_prob`, `sc_prob_3lap`, `sc_currently_active`, or `threat_level` for laps 1-3. Since `threat_level` is `init=False`, the LLM cannot set it through its structured tool call. The dataclass derives it from the two probability values returned by N12/N14, which are also lap-blind at this point. `_build_overtake_features` does account for lap and neutralisation in its DRS-window feature (`drs_allowed = not _is_neutralised(...)` at line 917), but only for the SC/VSC case mentioned in that comment. It does not account for the separate "DRS not active until lap 3" case cited by the prompt.

1. N31 states the rule with HARD weight in an explicit header. N27 calls it a "guard-rail" without the HARD qualifier, using structurally identical wording: "Consider the effective threat ONE LEVEL LOWER".
2. Code enforcement: **none.** `threat_level` is derived without lap awareness. The code cannot enforce the discount because the field itself cannot represent it. The discount can appear only in free-text `reasoning`, which does not affect consumers of the structured `threat_level` enum, including MC scoring, `key_risks`, contingencies, and `DecisionMemory`.
3. Exception sets: N/A. This is not an exempt/suspend rule. It matches the "prose promises a behaviour the data model cannot express" pattern in `[[feedback_a_guard_that_asserts_nothing]]`: a prompt or docstring claim without structural support.
4. Downstream effect: on laps 1-3, `threat_level` is `'HIGH'` whenever `overtake_prob` meets `CFG.high_overtake` (0.65) or `sc_prob_3lap` meets `CFG.high_sc`, regardless of either LLM's `reasoning`. Consumers of the structured field, including MC scenario scoring, N31's `key_risks` instructions, and the memory accumulator, all see an undiscounted HIGH. A human or another LLM reading N27's prose may see the discount. N31 must then derive it again from a field it received undiscounted, without a numeric signal such as `lap_number <= 3` or raw and discounted values. N31's prompt does include the lap (`RACE CONTEXT: ... Lap: {race_state.lap}/{race_state.total_laps}`), so it has enough information to make that decision itself. Structurally, however, N27's discount remains narrative only.
   One factor currently limits the impact. The already-known `[[project_threat_level_threshold_scale_bug]]` (#450/#665, not repeated here) compares raw-scale thresholds with calibrated probabilities, making HIGH effectively unreachable in current practice. That finding observed 0/8171 and 0/1420 real laps. It masks this issue because `threat_level` rarely reaches HIGH at any lap, so the undiscounted-HIGH-on-lap-2 scenario has not been observed. This gap will matter if #450/#665 is fixed and HIGH becomes reachable again.

Severity: **MEDIUM** (currently latent behind an unrelated, already-tracked bug; would become live and HIGH-severity the moment #450/#665's threshold fix ships, because at that point an opening-lap HIGH would flow undiscounted into MC scoring and `key_risks` with only prose as a (non-functional, single-LLM-hop, easily-dropped) mitigation).

---

### F6: N27's prompt contradicts itself about `predict_overtake_tool`, and production gates by grid position

N27 prompt, three lines apart, same file:
```
## Workflow
1. If the gap to the car ahead is less than 2.5 seconds, call `predict_overtake_tool` [...]
   (race_situation_agent.py:805)

## Rules
- Always call BOTH tools before drawing conclusions.               (line 814)
- If gap ahead > 2.5s, skip overtake tool and assume P(overtake) = 0.0.   (line 815)
```
Line 814 ("Always call BOTH tools") contradicts line 815 ("skip overtake tool [if >2.5s]"). The conflict appears four lines apart in the same prompt, not across files. An LLM cannot follow both instructions.

Worse: on the production entry point (`run_from_state`, the one CLI/arcade/webapp/`/recommend` all use per the RSM `lap_state` contract in `CLAUDE.md` §6), the 2.5s gap is **never actually measured** before the LLM decides whether to call the tool. `rival_ahead` is computed purely by grid position (`race_situation_agent.py:1366-1370`):
```python
driver_pos = d.get("position")
rival_ahead = (
    next((r["driver"] for r in rivals if r.get("position") == driver_pos - 1), None)
    if driver_pos is not None
    else None
)
```
Then the human-turn message the LLM actually sees (`race_situation_agent.py:1438-1449`) is built from that POSITIONAL result only:
```python
if rival_ahead:
    message = f"... The car ahead is {rival_ahead}. Determine the overtaking probability ..."
else:
    message = f"... No car is within overtaking range (gap > 2.5s). ..."
```
The `else` branch's phrase "gap > 2.5s" is misleading. That branch runs when there is no car one position ahead, such as for the leader or an unresolvable position; it **never checks an actual time gap**. When a positional rival does exist, the LLM receives "the car ahead is X" but **no gap value**. It cannot follow "skip if gap > 2.5s" without calling the tool it may be expected to skip. `predict_overtake_tool` (`race_situation_agent.py:1104-1165`) has no gap-based short-circuit and always returns an N12 probability, even when the cars are far apart.

The `run()` docstring at `race_situation_agent.py:1268` says `rival_ahead — Abbreviation of the car directly ahead. None = skip overtake.` It assumes the caller applies the 2.5s gate first. The FastF1 session path follows that contract, but this audit did not verify the external caller because it is outside the agent files. **`run_from_state` does not follow the contract**: it builds `rival_ahead` from position without checking the gap.

1. The prompt presents this as a definite behavioral rule, using the imperatives "Always" and "skip". The instructions contradict each other, so the rule is broken as written rather than clearly HARD or advisory.
2. Code enforcement: **none, and the one code path that could gate it (`run_from_state`) uses a completely different, weaker signal (position, not gap) while echoing gap-based language in its fallback message.**
3. Exception sets: N/A. This is a same-prompt contradiction and a docstring/implementation mismatch: `run()`'s docstring promises a gap gate that `run_from_state` does not perform.
4. Downstream effect: the LLM will likely follow "Always call BOTH tools", the more general instruction and the one consistent with the tool-list wording used by other agents. As a result, it may call `predict_overtake_tool` for every positional rival regardless of gap. N12 was likely trained on a range of gaps, including large gaps associated with near-zero overtake probability, so its output may remain reasonable for distant rivals. That is a plausibility argument, not a verified guarantee; rerunning the N12 training data was out of scope. The current safeguard is the assumption that the model learned gap relevance, not the prompt's claimed skip rule.

Severity: **LOW-MEDIUM**. The contradictory prose forces an LLM to choose between adjacent rules. The likely failure is contained because the model's gap feature may compensate, rather than causing a visible race-affecting error. This same-file contradiction is easy to miss when reviewing a prompt as a specification.

---

### F7: N26's fresh-tyre and extended-stint rules are prompt-only; MEDIUM stint life also differs between agents

N26 prompt (`tire_agent.py:744-755`):
```
## Strategic guard-rails
- FRESH TYRES (tyre_life <= 3 laps): the TCN model extrapolates from minimal data
  and cliff predictions are unreliable. Always report STAY OUT regardless of raw
  model output — no tyre degrades to its cliff in the first 3 laps of a stint under
  normal dry conditions. [...]
- EXTENDED STINT: if tyre_life exceeds the compound's typical race life
  (SOFT ~18 laps, MEDIUM ~28 laps, HARD ~38 laps), the driver is extending
  beyond normal limits. [...] Consider bumping your warning level up by one tier
  (STAY OUT → MONITOR, MONITOR → PIT SOON)."
```
The two rules target the field defined at `tire_agent.py:392-406`:
```python
laps_to_cliff_p10: float
...
warning_level: str = field(init=False)


def __post_init__(self) -> None:
    if self.laps_to_cliff_p10 < pit_soon:
        self.warning_level = "PIT_SOON"
    elif self.laps_to_cliff_p10 < monitor:
        self.warning_level = "MONITOR"
    else:
        self.warning_level = "OK"
```
I checked the full `TireOutput` dataclass. It carries `laps_to_cliff_p10/p50/p90`, `deg_rate`, `warning_level`, `reasoning`, and `gp_name`; no `tyre_life` field feeds `__post_init__`. `pit_soon` and `monitor` come from `CFG.get_cliff_thresholds(gp_name)`. The GP/cluster/global lookup matches the prompt's 3/7 global fallback. Neither trigger condition (`tyre_life <= 3` or `tyre_life > {18,28,38}` by compound) appears in this derivation or elsewhere in the file. I grepped `predict_tire_deg_tool` and `estimate_laps_to_cliff_tool`, the only two tools at `tire_agent.py:1024,1065`, for tyre-life clamping of P10/P50/P90 or a confidence flag and found none. Both return raw MC-Dropout percentiles for the requested `tyre_life`, whether the tyre is fresh or not.

1. Both stated as "Strategic guard-rails" (same header pattern N27 and N28 use for their HARD rules) with imperative language ("Always report STAY OUT regardless of raw model output").
2. Code enforcement: **none.** As in F5, the field these rules claim to affect (`warning_level`) is `init=False` and derives only from `laps_to_cliff_p10` and GP-aware thresholds. Although the LLM passes `tyre_life` to the tools, that value does not reach the `warning_level` calculation. The tools also leave tyre-life uncertainty out of their percentiles: they do not widen P10 for `tyre_life<=3` or shift thresholds for extended stints.
3. Exception sets: N/A. These are one-directional overrides, not exemptions from a bound. The same pattern appears in F5: prose promises behavior that the data model cannot express.
4. Downstream: a 2-lap-old tyre could receive a P10 estimate below the `monitor`/`pit_soon` threshold. This is plausible just after a pit stop, while the TCN's short window still contains mostly padding. The already-known N26 zero-padding issue is tracked in project memory under `[[reference_f1_domain_knowledge]]` and notebook N09. In this case, `warning_level` would be `MONITOR` or `PIT_SOON` for a tyre too fresh to be near a cliff. Only the LLM's prose could override the value, leaving the same single point of failure as F5 in another agent.

Cross-checking N26's rule against N28's equivalent constant found a separate discrepancy. N26's "EXTENDED STINT" text gives typical compound life as **SOFT ~18 / MEDIUM ~28 / HARD ~38** laps. N28's `recommend_compound_tool` fallback table (`pit_strategy_agent.py:91`, quoted in F1) gives **SOFT 18 / MEDIUM 30 / HARD 38**. SOFT and HARD match; MEDIUM differs by 2 laps. The agents independently hardcode Pirelli's average MEDIUM stint capacity and cite no shared constant. A grep found no shared `MEDIUM_STINT_LAPS`-style constant in `src/agents/`.

Severity: **MEDIUM** for the fresh-tyre and extended-stint guard-rails. As in F5, the prompt promises a safeguard the data model cannot express, and N31 directly reads `tire_block` built from `TireOutput.warning_level`. Severity is **LOW** for the 28-vs-30 MEDIUM-life drift. The 2-lap difference is about 7% and changes compound selection only near the boundary.

---

### F8: N31 is told to cite the field N30's docstring warns against

This is a docstring/code contract violation, not a prompt conflict. It is the strongest finding in this audit.

`RegulationContext.answer` docstring, `rag_agent.py:74-79` (N30, quoted in full because the warning is explicit and unambiguous):
```
answer:
    LLM-generated summary of the relevant regulation articles — one to
    three sentences, enough for the Strategy Orchestrator to decide
    whether a proposed action is legal without reading the full passage.
    Do NOT use article numbers from this field for citations — the LLM
    may hallucinate them. Use the articles field instead.
```
and again for the safe field, `rag_agent.py:84-88`:
```
articles:
    Deduplicated list of article references extracted from chunk metadata
    (e.g. ["Article 48.3", "Article 55.1"]). Always use this field for
    citations in strategy log entries — chunk metadata is reliable;
    LLM answer text may hallucinate article numbers.
```
N30's system prompt (`rag_agent.py:118-128`) invites the failure described by its docstring. It tells the LLM that synthesizes `answer` to cite article numbers itself: `"3. Answer in 2-3 sentences, citing the exact article numbers (e.g. "Article 48.3")."` The LLM therefore generates the citations in `answer`, the field the dataclass docstring identifies as unreliable for citations.

Code, `strategy_orchestrator.py:1924-1929` (`_run_conditional_agents`, called once per lap when N30 is active):
```python
reg_out = run_rag_agent(question)
regulation_context = reg_out.answer  # <-- the field the docstring says NOT to cite from
rag_dict = {
    "question": reg_out.question,
    "answer": reg_out.answer,
    "articles": list(reg_out.articles),  # <-- the safe field: captured, but only for rag_dict
    "chunks": [...],
}
```
The function docstring (`strategy_orchestrator.py:1872-1880`) calls `regulation_context_str` "legacy" and says it is preserved for the orchestrator's LLM prompt and `StrategyRecommendation`, "neither of which depend on the structured shape." It routes `rag_dict["articles"]`, the safe list derived from chunks, only to consumers that need more than the answer string. The arcade dashboard uses those article references and chunk text in its RAG card. The safe field reaches the UI, not the LLM prompt.

`regulation_context` (== `reg_out.answer`) then flows straight into N31's own prompt as `reg_block` (`strategy_orchestrator.py:1506-1509`) and N31 is explicitly told, under its own reasoning rubric (`strategy_orchestrator.py:1658`):
```
3. If regulation_context is present, quote at least one article number.
```
So: N30's LLM free-text-cites an article number into `answer` (a field its own author flagged as hallucination-prone) → the orchestrator hands that exact string to N31 as `regulation_context` → N31's LLM is instructed to quote an article number *from it* into `StrategyRecommendation.reasoning`, the field surfaced to the pit wall / CLI / arcade / webapp as the human-facing justification for the strategy call. The one safe, chunk-metadata-backed `articles` list produced in the very same function call is discarded for this purpose three lines later.

1. N30's docstring states a HARD rule: "Do NOT... Always use...". N31's prompt construction, one function away in the same codebase, immediately contradicts it.
2. Code enforcement: **none; the code does the opposite.** It wires the discouraged field into an LLM-facing prompt that asks for a citation, creating the risk named in the docstring. The safe field is already computed in the same block and routed elsewhere.
3. Exception sets: N/A. This is a direct contract violation, not an exemption pattern, and no exception is stated.
4. Downstream check: **none.** No validator checks article numbers in `StrategyRecommendation.reasoning` against `rag_dict["articles"]` or the ground-truth `chunks[].article` metadata. N30 can invent an article number and N31 can repeat it in the driver-facing recommendation as confidently as a real, regulation-grounded citation.

Severity: **HIGH.** N30 can produce a citation in free text and N31 can repeat it. A safe alternative already exists, is computed, and is used by the arcade RAG card. The fix is to use `rag_dict['articles']` or `chunks[].article` in `reg_block` and N31's prompt, while keeping `reg_out.answer` for the prose summary. Users may trust citations such as Art. 55.17, the two-compound rule, or SC procedure without checking the source, making this risk more consequential than the numeric drifts above.

---

### F9: A numeric prompt literal duplicates a live config value without a linking test

N28's decision rule #4 (`pit_strategy_agent.py:611`) contains the literal `"4. If P(undercut_success) >= 0.522 for any rival → recommend UNDERCUT."`.

The actual comparison the tool performs uses a config value loaded from disk at runtime, not the literal (`pit_strategy_agent.py:230,1194`):
```python
self.undercut_threshold: float = uc_cfg["best_threshold"]  # from model_config_undercut_v1.json
...
verdict = "YES" if calib_proba >= agent.cfg.undercut_threshold else "NO"
```
The tool's own return string DOES report the live threshold correctly (`f'threshold={agent.cfg.undercut_threshold} | ... verdict={verdict}'`), so an LLM that reads the tool's `verdict` field (rather than re-deriving its own YES/NO from the hardcoded "0.522" in decision rule #4 against the raw `P(undercut_success)` number) gets the right answer regardless of drift. But the prompt states BOTH: a literal threshold ("0.522") the LLM could apply itself, AND a tool that supplies an authoritative `verdict`. Nothing forces the LLM to prefer the tool's `verdict` over doing its own comparison against the stale literal.

I could not verify whether `uc_cfg['best_threshold']` equals 0.522. The ignored `data/` directory, including `data/models/*.json`, is absent from this checkout. Section 0 of `CLAUDE.md` says model data comes from Hugging Face Hub. The same missing-data gate prevented earlier safety-car bound tests from running in CI. The four `"threshold=0.522"` strings at `tests/audit/test_pit_agent_hardening.py:110-139` are parser-test fixtures, not assertions such as `agent.cfg.undercut_threshold == 0.522` tying the prompt literal to `best_threshold`.

1. Guidance-level decision rule, outside the "HARD constraints" header. It is rule #4 in the base "Decision rules" list at `pit_strategy_agent.py:607-614`.
2. Code enforcement: the tool computes the correct live comparison and exposes it as `verdict`; the prompt ALSO gives the LLM a redundant, independently-stale-able literal it could use instead. No test enforces the two stay equal.
3. Exception sets: N/A.
4. Downstream check: none. If retraining N16 changes `best_threshold`, the prompt's "0.522" will no longer match the tool's `threshold=` output. The JSON `model_config_undercut_v1.json` can change across model versions, as did the N12/N14 thresholds found stale in #450/#665. Depending on which value the LLM follows, an `UNDERCUT` recommendation could change at the margin without detection. This has the same failure pattern as #450/#665: a tuned threshold is duplicated outside its source of truth. Current drift is unconfirmed.

Severity: **LOW (structural / unconfirmed)**. The risk matches the known pattern of tuned thresholds duplicated outside their source of truth (#450 and #665). The current drift remains unconfirmed because the model configuration is absent from this checkout. Add a fast check such as `abs(CFG.undercut_threshold - 0.522) < 1e-6`, then compare against the JSON value without loading a model. Replace the prompt's `0.522` literal with the tool's `verdict` field so the model cannot compare against a stale copy.

---

### F10: The prompt preserves negative degradation rates, but laps-to-cliff calculations discard the sign

N26 prompt (`tire_agent.py:739-740`, under "## Rules"):
```
- A negative degradation rate means the driver is improving pace on this stint
  (track evolution or fuel load reduction) — this is real, not an error.
```

Two different code paths handle "degradation rate" for two different purposes inside `estimate_laps_to_cliff_tool`, and they disagree on sign:

1. `predict_tire_deg_tool` (`tire_agent.py:1057`) reports the signed rate as `deg_rate = float(feat_df['DegradationRate'].iloc[-1])`, without `.abs()`. `_parse_tool_outputs` (`tire_agent.py:640-671`) takes the **first** regex match for `Degradation rate:` in the message history (`if m and key not in result`). The workflow calls `predict_tire_deg_tool` before `estimate_laps_to_cliff_tool` (prompt steps 1 and 2), so `TireOutput.deg_rate` receives the raw signed value. Fix #477 corrected the regex because negative rates, which the prompt calls "real and expected" in the inline comment at `tire_agent.py:659-662`, previously failed to parse and defaulted to 0.0. **This part is correct, as intended.**

2. `estimate_laps_to_cliff_tool` (`tire_agent.py:1118`), computing the P10/P50/P90 figures the prompt tells the LLM to base its recommendation on ("Base your recommendation on P10"), uses a DIFFERENT, sign-stripped rate for the actual division:
   ```python
   deg_rate = max(float(feat_df["DegradationRate"].abs().iloc[-1]), 0.001)
   ...
   p50 = min(remaining_budget / deg_rate, cliff_ceiling)
   p10 = min(max(0.0, (remaining_budget - total_std) / deg_rate), cliff_ceiling)
   p90 = min((remaining_budget + total_std) / deg_rate, cliff_ceiling)
   ```
The use of `.abs()` has no nearby explanation. Comments at `tire_agent.py:1123-1138` document the `max(..., 0.001)` floor, which prevents the divide-by-near-zero result that once produced "P50: 27375.2 laps, OK". They do not explain why the rate's sign is discarded.

1. Guidance-level prompt claim: "this is real, not an error." It is framed as a fact to report, not as a HARD constraint.
2. Code enforcement: **split**. #477 preserves the sign in `deg_rate`, the field named by the prompt. The derived `laps_to_cliff_p10` metric that drives the recommendation strips the sign in a neighboring function, with no comment explaining the difference.
3. Exception sets: N/A. This is not an exempt or suspend pattern. It is a sign-information loss within one tool call: `deg_rate` and `laps_to_cliff_*` appear together in the return string at `tire_agent.py:1156-1159`, including `"Laps to cliff — P10: ... | ... Degradation rate: {deg_rate:.4f} s/lap ..."`. The `laps_to_cliff` calculation treats those values differently.
4. Downstream check: none. The estimate uses `remaining_budget`, calculated as `max(0.0, threshold - mean_pred)` at line 1121. An improving tyre usually has a low or negative `mean_pred`, which leaves the remaining budget and P50 large despite the sign-stripped divisor. A short estimate is possible when the instantaneous rate is strongly negative and `mean_pred` has not caught up. This is a verified code-path inconsistency with a narrow, unconfirmed race trigger. Live inference was outside this read-only audit.

Severity: **MEDIUM**. The prompt's claim is honored for `deg_rate`, thanks to #477. However, the derived metric that drives the "STAY OUT / MONITOR / PIT SOON" decision uses a neighboring code path that restores the sign-blindness #477 fixed. This matches the "twin that never got the fix" pattern in project memory: #477 corrected the parser, but no one checked the adjacent computation, which has the same defect.

---

## Coverage note

I also read `pace_agent.py` (N25) and `radio_agent.py` (N29) in full and checked their guard-rail prose. I found no additional issues. N25 has a minimal prompt that says "never invent numbers, use only tool values" and contains no numeric bounds to cross-check. N29's correction/synthesis prompt says "Base your response only on the provided data"; that matches its structured-output design, and no code path bypasses it. I read and grepped all ~2426 lines of `strategy_orchestrator.py` for the remaining numbered guard-rails (1-6, covered across F1-F5), the reasoning rubric (F8), the action schema (F3), and `_assemble_recommendation`. At `strategy_orchestrator.py:2131`, the function says "The action is the synthesis's, always". The live path does not validate `action`, `compound_next`, or `pit_lap_target` against any of the six guard-rails. It only corrects `undercut_target` against `live_drivers` and clamps `expected_stint_end` through `_clamp_expected_stint_end` (#433).

---

## Severity ranking (all ten findings)

| # | Finding | Class | Severity |
|---|---|---|---|
| F3 | REACTIVE_SC has inverted definitions between N28 and N31 (SC-confirmed vs SC-not-confirmed) | prompt vs prompt (contradiction) | **HIGH** |
| F4 | N31's own minimum-stint guard-rail dropped the SC exception that N28 and today's `guard_rails.py` fix both carry — N31 can silently undo today's fix | prompt vs prompt (stale twin) | **HIGH** |
| F8 | N31 is told to quote FIA articles from N30's hallucination-prone `answer` field instead of the safe `articles` list N30's own docstring says to use | docstring vs code (contract violated by design) | **HIGH** |
| F2 | End-of-race SC exception: N28's prompt still has it, `guard_rails.py` and N31 both correctly dropped it (three-way split, not just prompt-vs-code) | prompt vs prompt vs code (stale twin, but the live path already has the fix) | **MEDIUM-HIGH** |
| F5 | Opening-lap threat discount (N27+N31 agree) has zero effect on `threat_level`, which is `init=False` and lap-blind; currently masked by the unrelated #450/#665 scale bug | prompt vs structure | **MEDIUM** (latent) |
| F7 | Fresh-tyre / extended-stint tire guard-rails are prompt-only; `warning_level` has no `tyre_life` term. Plus a minor 28-vs-30-lap MEDIUM-life constant drift vs N28 | prompt vs structure + minor numeric drift | **MEDIUM** / LOW |
| F10 | `estimate_laps_to_cliff_tool` strips the sign of `deg_rate` via `.abs()` for its P10/P50/P90 divisor, contradicting the prompt's "negative rate is real" claim; the reported `deg_rate` field itself is correctly signed (thanks to #477) | code vs code (the same #477 sign bug reintroduced in a sibling function) | **MEDIUM** |
| F1 | N28/N31's "COMPOUND vs REMAINING LAPS" hard bound (15/12-30/20+) contradicts `recommend_compound_tool`'s own numbers (18/30/38); no downstream validation of `compound_next` at all | prompt vs the tool the prompt tells the LLM to call | **MEDIUM** |
| F6 | N27 self-contradicts ("Always call BOTH tools" vs "skip overtake tool if gap>2.5s"); production `run_from_state` path gates by grid position, not gap, and mislabels its own fallback message as gap-based | prompt self-contradiction + docstring/impl mismatch | **LOW-MEDIUM** |
| F9 | N28's "0.522" undercut threshold is a prompt literal duplicating a live JSON config value with no test tying them together; could not confirm current drift (data/models/ gate) | structural risk, unconfirmed | **LOW** |

---

## Numbered fix list (ordered by value, cheapest/highest-leverage first)

1. **Sync N31's minimum-stint guard-rail (#4) with N28/`guard_rails.py` (F4).** Add the SC-active exception clause to `strategy_orchestrator.py:1602-1603`, matching `pit_strategy_agent.py:641-652`. This is the highest-value fix: it is the one place today's SC-exception fix can be silently undone by the very next pipeline layer.
2. **Resolve the REACTIVE_SC definition conflict (F3).** Choose one definition. N31's is preferable: REACTIVE_SC means confirmed SC, which fits its five-value action enum that does not include REACTIVE_SC. Rewrite N28's "REACTIVE_SC usage" section (`pit_strategy_agent.py:660-666`) to match. Clarify in N31's guard-rail #3 that it governs interpretation of N28's `action` field, since N31 cannot emit REACTIVE_SC.
3. **Fix the RAG citation source (F8).** In `_run_conditional_agents` (`strategy_orchestrator.py:1924-1929`), build `regulation_context` or a companion field from `reg_out.articles`/`chunks[].article` for citations requested by N31's reasoning rubric. Keep `reg_out.answer` for the prose summary. Update the docstring at `strategy_orchestrator.py:1878-1880`, which currently describes the violation as intentional.
4. **Update N28's own prompt to drop the SC exception on the end-of-race bound (F2)**, matching `guard_rails.py`'s Art. 55.17 reasoning and N31's already-correct wording, so all three copies agree. Lower urgency than #1 because the live path (N31) already has the correct behaviour; this is about not contaminating N28's own `reasoning` output and about safety for future edits to `guard_rails.py`/N31 that might "fix" toward N28's stale version instead of the other way around.
5. **Fix `estimate_laps_to_cliff_tool`'s sign-stripped divisor (F10)** at `tire_agent.py:1118`. Either remove `.abs()` so a negative rate pushes `p50`/`p10`/`p90` toward `cliff_ceiling` ("no cliff visible"), or handle negative rates explicitly and return the ceiling with a comment explaining why. Both options avoid reintroducing #477's fixed bug in a sibling function.
6. **Reconcile the COMPOUND-vs-remaining-laps numbers (F1).** Either change `_STINT_CAPACITY_LAPS` to 15/12-30/20+ to match both prompts' HARD constraint, or, preferably, update both prompts' "COMPOUND vs REMAINING LAPS" sections to match the more defensible Pirelli-sourced 18/30/38 values in the tool's docstring. Add a lightweight post-hoc check on `compound_next` and `remaining_laps` in `_assemble_recommendation` to log violations.
7. **Add a unit test for `undercut_threshold` and the prompt's "0.522" literal (F9).** Read `model_config_undercut_v1.json` directly without loading the model, then assert equality. This catches drift if N16 is retrained and the prompt is not updated.
8. **Fix N27's self-contradiction (F6).** Remove either "Always call BOTH tools" or the gap>2.5s skip clause. If retaining the gap check, pass `gap_ahead_s` into the `run_from_state` message so the LLM has the value needed to follow the rule. Correct the misleading "gap > 2.5s" fallback text in the position-only `rival_ahead` calculation.
9. **Reconcile the 28-vs-30-lap MEDIUM stint-life constants (F7)** between `tire_agent.py`'s prompt text and `pit_strategy_agent.py`'s `_STINT_CAPACITY_LAPS`, ideally by extracting one shared constant both agents import.
10. **Decide whether the fresh-tyre/extended-stint guard-rails (F7) and opening-lap threat discount (F5) need structural support.** Options include passing a `lap_context_multiplier` into `__post_init__` or documenting why narrative-only guidance is safe. This is lower priority because both issues are latent or masked, but the decision should be explicit.

---

## What I tried to break and could not

- I looked for a fourth copy of the pit guard-rails in `no_llm.py`, `decision_modes.py`, MCP tool schemas, and the arcade/CLI display layer. The `no_llm.py` call site and `decision_modes.py` invocation (`src/strategy/eval/decision_modes.py:193-210`) both call `apply_guard_rails` directly rather than re-deriving the bounds, as its docstring requires: "Anything that needs to MIRROR a rail must import it from here and, better still, call `apply_guard_rails`." I found no fourth independent copy. The only prose copies are N28's and N31's prompts, and I found their disagreements in F1-F4.
- I looked for code that validates N31's final `action`, `compound_next`, or `pit_lap_target` against the six guard-rails after the LLM call. None exists (`strategy_orchestrator.py:2131`: "The action is the synthesis's, always"). This is a deliberate, documented post-#464 choice to trust the LLM instead of a rail that could recreate #464's overreach. It is not itself a bug, but it leaves the prompt disagreements in F2-F4 without a code backstop. The outcome depends on which conflicting instruction the LLM follows.
- I could not confirm an F9 scale mismatch as I did for #450/#665 using real data. `data/models/model_config_undercut_v1.json` is absent from this checkout, so F9 remains a structural risk with an unconfirmed current value, not a proven live bug.
- I checked N26/N31 and N27/N31 for a REACTIVE_SC inversion. Both pairs have structural gaps in F5 and F7: each prompt requests a discount or override that the structured field cannot represent. Neither pair has a direct inversion of meaning. N26 and N27's guard-rail text agrees with N31, the opening-lap discount numbers match, and N26 has no minimum-stint rule for N31 to contradict.
- I could not reproduce F10 against a real-race value to raise its severity from MEDIUM to HIGH. Doing so requires live inference with `data/models/`, outside this read-only, no-model-load audit. F10 is reported as a verified code-path defect with a plausible but unconfirmed field trigger, not as a confirmed incident.
- The review found no hallucination-laundering path in N29's `CorrectionEntry` type and its `span` field. The code requires a verbatim substring from the radio message. No code path removes that check or substitutes free text for cited articles as the N30 path does with `answer` and `articles`.
