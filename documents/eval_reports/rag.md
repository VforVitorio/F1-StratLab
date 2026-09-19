# rag

- harness `c57fbd0f-dirty` · schema v1 · generated 2026-09-19T13:06:23+00:00
- era 2022-2025 · dataset RAG queries_v2.json, 30 FIA regulation queries · seed deterministic · llm none
- artifacts: query_set=`663d72013436`

| configuration | n | P@1 | P@3 | P@5 | hit@5 | content hit@5 | MRR | citation match | wrong-year | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BGE-M3 production, season scoped | 30 | 0.533 | 0.322 | 0.207 | 0.833 | 0.967 | 0.675 | 0.833 | 0.000 | 40.0 | 97.5 |
| BGE-M3 production, unscoped control | 30 | 0.267 | 0.178 | 0.153 | 0.700 | 0.867 | 0.439 | 0.733 | 0.640 | 26.5 | 28.0 |

## Metric contract

Query set: 30 manually verified questions from the 2023-2025 FIA Sporting Regulations.
Categories: drs, flags_penalties, pit_stops, safety_car, tyre_allocation.

P@k is conventional precision over the top k returned chunks. `hit@5` is the older binary benchmark measure and is retained for comparison with N30B.
A strict hit requires the expected season, article, and at least one verified keyword. Content hit@5 requires the expected season and keyword but ignores the article metadata field.
Citation match is retrieval-level article recall at five chunks. It does not claim that an LLM cited the article faithfully; that belongs to the grounding phase and must use the actual tool trace.
Wrong-year rate is the share of top-five chunks from a season different from the query. The scoped row is the production path. The unscoped row is a control for the season filter.
The evaluator calls the production `RagRetriever` directly, loads one embedding model, and does not spend LLM calls. Alternative embeddings and chunking remain in the historical N30B notebook until a separate A/B issue adopts them.
