## Sub-agent latency (single lap fixture)

| agent | mean_ms | p50_ms | p95_ms | device | n_runs | notes |
|---|---|---|---|---|---|---|
| pace_agent | 270,196 | 265,260 | 330,721 | cuda | 10 | no external calls |
| tire_agent | 2634,599 | 2619,332 | 3317,678 | cuda | 10 | TCN MC dropout, no external calls |
| race_situation_agent | 2590,500 | 2375,010 | 3336,503 | cuda | 10 | LightGBM overtake + SC, may invoke LLM if configured |
| pit_strategy_agent | 3346,940 | 3374,115 | 3725,700 | cuda | 10 | HistGBT pit duration + LightGBM undercut, may invoke LLM |
| radio_agent | 1455,772 | 1447,952 | 1600,055 | cuda | 10 | BERT sentiment + SetFit intent + BERT NER, LLM synthesis when reachable |
| rag_agent | — | — | — | cuda | 0 | Qdrant retrieval + LLM answer synthesis — runtime error: RuntimeError('Storage folder C:\\Users\\victo\\Desktop\\Documents\\Cuarto Año\\TFG\\F1_Strat_Manager\\data\\rag\\qdrant_local is already accessed by another instance of Qdrant client. If you require concurrent access, use Qdrant server instead.') |
