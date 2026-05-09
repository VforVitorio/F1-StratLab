## NLP pipeline latency (CPU vs GPU)

| row | device | entry_point | mean_ms | p50_ms | p95_ms | n_runs | notes |
|---|---|---|---|---|---|---|---|
| cpu/run_pipeline | cpu | run_pipeline | 490,014 | 483,998 | 557,682 | 16 | 8 messages x N runs, sentiment + intent + NER |
| cpu/run_rcm_pipeline | cpu | run_rcm_pipeline | 0,006 | 0,006 | 0,007 | 16 | 8 RCM rows x N runs, rule-based parser only |
