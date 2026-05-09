## Sub-agent latency (single lap fixture)

| agent | mean_ms | p50_ms | p95_ms | device | n_runs | notes |
|---|---|---|---|---|---|---|
| pace_agent | 487,359 | 481,216 | 588,363 | cuda | 10 | no external calls |
| tire_agent | 2828,972 | 2736,490 | 3236,852 | cuda | 10 | TCN MC dropout, no external calls |
| race_situation_agent | 2969,005 | 2844,565 | 4140,423 | cuda | 10 | LightGBM overtake + SC, may invoke LLM if configured |
| pit_strategy_agent | 3636,209 | 3537,718 | 4436,024 | cuda | 10 | HistGBT pit duration + LightGBM undercut, may invoke LLM |
| radio_agent | 1327,959 | 1212,610 | 1890,126 | cuda | 10 | BERT sentiment + SetFit intent + BERT NER, LLM synthesis when reachable |
| rag_agent | 4418,721 | 2353,850 | 13743,247 | cuda | 10 | Qdrant retrieval + LLM answer synthesis |
