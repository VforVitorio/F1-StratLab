# Evaluation reports

This folder holds agent-assisted evaluations and their generated outputs. A report describes a particular run and dataset; it is not ground truth or a claim about every race.

- Read the Markdown report for scope, method, caveats, and interpretation. Keep its paired JSON when tools or later reviews depend on the structured result.
- The paired JSON records counts and source JSONL paths. The session log records run context, but these artifacts do not identify the exact source commit for each measurement.
- Treat proxy judgments as proxies. For example, `alert_llm` evaluates model judgments on unlabeled radio messages; it is not an accuracy measurement against human labels.
- `llm_2025/REPORT.md` is the current report; `REPORT_partial.md` records an earlier incomplete run and is retained as cited history.
- `rag_agent_traces.json` is a test fixture, not a generated evaluation report.

`metrics_registry.md` defines the evaluation metrics used across reports. Keep limitations and provenance beside results when regenerating them.

Running `scripts/report_llm_2025.py` rewrites the combined `_merged_llm.jsonl` and `_merged_det.jsonl` files, the selected Markdown report, and its JSON sidecar. It writes the report to `REPORT.md` unless `--out` selects another path.
