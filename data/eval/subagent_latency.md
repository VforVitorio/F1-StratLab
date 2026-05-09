## Sub-agent latency (single lap fixture)

| agent | mean_ms | p50_ms | p95_ms | device | n_runs | notes |
|---|---|---|---|---|---|---|
| pace_agent | 425,109 | 432,545 | 448,583 | cuda | 5 | no external calls |
| tire_agent | — | — | — | cuda | 0 | TCN MC dropout, no external calls — runtime error: APIConnectionError('Connection error.') |
| race_situation_agent | — | — | — | cuda | 0 | LightGBM overtake + SC, may invoke LLM if configured — runtime error: APIConnectionError('Connection error.') |
| pit_strategy_agent | — | — | — | cuda | 0 | HistGBT pit duration + LightGBM undercut, may invoke LLM — runtime error: APIConnectionError('Connection error.') |
| radio_agent | 13593,288 | 13622,456 | 13661,315 | cuda | 5 | BERT sentiment + SetFit intent + BERT NER, LLM synthesis when reachable |
| rag_agent | — | — | — | cuda | 0 | Qdrant retrieval + LLM answer synthesis — runtime error: APIConnectionError('Connection error.') |
