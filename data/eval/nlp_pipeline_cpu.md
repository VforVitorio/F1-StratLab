## NLP pipeline latency (CPU vs GPU)

| row | device | entry_point | mean_ms | p50_ms | p95_ms | n_runs | notes |
|---|---|---|---|---|---|---|---|
| cpu/run_pipeline | cpu | run_pipeline | 335,831 | 334,824 | 364,060 | 80 | 8 messages x N runs, sentiment + intent + NER |
| cpu/run_rcm_pipeline | cpu | run_rcm_pipeline | 0,004 | 0,004 | 0,005 | 80 | 8 RCM rows x N runs, rule-based parser only |
| cuda/run_pipeline | cuda | run_pipeline | 42,069 | 41,834 | 44,246 | 80 | 8 messages x N runs, sentiment + intent + NER |
| cuda/run_rcm_pipeline | cuda | run_rcm_pipeline | 0,002 | 0,002 | 0,003 | 80 | 8 RCM rows x N runs, rule-based parser only |
