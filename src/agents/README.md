# src/agents — Legacy Rule-Based Strategy Engine

**Status: Legacy** — superseded by the LangGraph multi-agent system (N25–N31).

This package implements the original Experta-based expert system that was the first
version of the strategy engine. It is kept for reference; it is not used in the
current agent architecture.

---

## What is here

| File | Description |
|---|---|
| `base_agent.py` | Experta `Fact` subclasses (`TelemetryFact`, `DegradationFact`, `GapFact`, `RadioFact`, `RaceStatusFact`, `StrategyRecommendation`) and `F1StrategyEngine` base engine; also contains data-transform helpers for tire/lap/gap/radio facts |
| `strategy_agent.py` | `F1CompleteStrategyEngine` — unified engine combining degradation, lap-time, NLP, and gap rule sub-engines via multiple inheritance; imports from `src.agents.rules.*` |
| `rules/` | Domain rule modules (`degradation_rules.py`, `laptime_rules.py`, `nlp_rules.py`, `gap_rules.py`) |

---

## Why superseded

The Experta rule engine (CLIPS-style forward chaining) was replaced by a LangGraph
ReAct multi-agent architecture in N25–N31. The new system uses trained ML models
(LightGBM, TCN, calibrated probabilities) as tool calls rather than hand-coded rules,
and coordinates via a Supervisor Orchestrator (N31).

---

## Do not use in new code

Import from `notebooks/agents/` or from `src/rag/` instead.
For the production entry point see [`notebooks/agents/N31_orchestrator.ipynb`](../../notebooks/agents/N31_orchestrator.ipynb).
