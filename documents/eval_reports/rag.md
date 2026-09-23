# rag

- harness `f423ce29-dirty` · schema v1 · generated 2026-09-23T07:37:06+00:00
- era 2022-2025 · dataset RAG queries_v2.json, 30 FIA regulation queries · seed deterministic · llm none
- artifacts: query_set=`663d72013436`, agent_trace_set=`829faa5a124e`

| configuration | n | P@1 | P@3 | P@5 | hit@5 | content hit@5 | MRR | citation match | wrong-year | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BGE-M3 production, season scoped | 30 | 0.533 | 0.322 | 0.207 | 0.833 | 0.967 | 0.675 | 0.833 | 0.000 | 85.0 | 220.8 |
| BGE-M3 production, unscoped control | 30 | 0.233 | 0.178 | 0.153 | 0.700 | 0.867 | 0.421 | 0.733 | 0.647 | 63.3 | 81.9 |

## Metric contract

Query set: 30 manually verified questions from the 2023-2025 FIA Sporting Regulations.
Categories: drs, flags_penalties, pit_stops, safety_car, tyre_allocation.

P@k is conventional precision over the top k returned chunks. `hit@5` is the older binary benchmark measure and is retained for comparison with N30B.
A strict hit requires the expected season, article, and at least one verified keyword. Content hit@5 requires the expected season and keyword but ignores the article metadata field.
Citation match in the main table is retrieval-level article recall at five chunks. It does not claim that an LLM cited the article faithfully.
The separate agent-trace section measures answer citations against article metadata in recorded real LangGraph tool traces. It makes no model calls.
Wrong-year rate is the share of top-five chunks from a season different from the query. The scoped row is the production path. The unscoped row is a control for the season filter.
The evaluator calls the production `RagRetriever` directly, loads one embedding model, and does not spend LLM calls. Alternative embeddings and chunking remain in the historical N30B notebook until a separate A/B issue adopts them.

## Agent-trace citation match

| trace | year | model | matched citations | unsupported articles |
|---|---:|---|---:|---|
| rag-20260923-pit-lane-speed | 2025 | gpt-4.1-mini | 1/1 | none |

Citation-instance match: 1/1 (1.000). Fully matched traces: 1/1 (1.000).
This is an observed real-trace sample; n=1 is not a stable estimate of general answer quality.
