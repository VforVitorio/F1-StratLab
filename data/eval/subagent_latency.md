## Sub-agent latency (single lap fixture)

| agent | mean_ms | p50_ms | p95_ms | device | n_runs | notes |
|---|---|---|---|---|---|---|
| pace_agent | 263,625 | 265,964 | 309,556 | cuda | 10 | no external calls |
| tire_agent | — | — | — | cuda | 0 | TCN MC dropout, no external calls — runtime error: OpenAIError('The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable') |
| race_situation_agent | — | — | — | cuda | 0 | LightGBM overtake + SC, may invoke LLM if configured — runtime error: OpenAIError('The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable') |
| pit_strategy_agent | — | — | — | cuda | 0 | HistGBT pit duration + LightGBM undercut, may invoke LLM — runtime error: OpenAIError('The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable') |
| radio_agent | 1,269 | 1,206 | 1,479 | cuda | 10 | BERT sentiment + SetFit intent + BERT NER, LLM synthesis when reachable |
| rag_agent | — | — | — | cuda | 0 | Qdrant retrieval + LLM answer synthesis — runtime error: OpenAIError('The api_key client option must be set either by passing api_key to the client or by setting the OPENAI_API_KEY environment variable') |
