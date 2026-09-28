# Issue #322 grounding and citation faithfulness

**Branch:** `feat/322-rag-grounding`
**Base:** `f423ce29`
**Decision:** wrapper changes pass and one live trace passes; keep #322 open until independent re-review. The trace sample is `n=1`, so it is evidence of the path, not a stable estimate of general citation-match performance.

## Baseline

The retriever already receives the season through `RunnableConfig`, but N30
rehydrated `RegulationContext.chunks` by running a second semantic query. That
could produce different passages from the `ToolMessage` the model actually
read. There was no minimum similarity floor and no check that article numbers
in the answer belonged to the retrieved article metadata.

## Changes

- `RegulationContext` now parses the actual `query_rag_tool` result blocks from
  the LangGraph message history. No second semantic query is used for evidence.
- `citation_violations` and `citation_faithful` record whether every `Article`
  reference in the answer exists in the retrieved metadata.
- `f1-eval rag` now aggregates a versioned real-trace set into citation-instance
  and fully matched trace rates, separate from retrieval-level citation recall.
  The trace loader rejects mismatched tool-call/result IDs, question arguments,
  article headers, answer references, and invalid faithfulness fields.
- Parsing correlates each tool result with its AI tool-call ID, preserves string
  and text-block content, distinguishes equal passages with different article
  metadata, and rejects malformed or out-of-range scores without merging their
  text into the previous source.
- Citation parsing accepts article lists joined by commas, `and`, `or`, `&`,
  `/`, or semicolons, including Oxford commas. Malformed suffixes and prefix
  collisions are violations. Markdown-wrapped article numbers and hyphenated
  ranges are handled without accepting a retrieved prefix as the full citation;
  numeric measurements such as `80 km/h` or `80.5 km/h` after a list connector
  are not treated as articles.
- `RagConfig.similarity_floor` is configurable and defaults to `0.50`.
  The scoped 30-query set has a minimum hit score of `0.5085`; unrelated local
  probes peaked at `0.4640`. Below-floor results produce the existing explicit
  no-relevant-passages response.

## Verification

- `tests/rag/` and `tests/eval/test_rag.py`: 59 passed, 1 skipped because the
  worktree has no local FIA PDFs for the index-chunking test.
- Ruff check, Ruff format check, `git diff --check`, and `uv run mypy src/rag/` passed.
- Real local index query: relevant 2025 tyre query returned five passages with
  scores `0.6312` through `0.6127`.
- Real local index query: `banana engine cloud` returned zero passages and
  `No relevant regulation passages found for this query.`
- `f1-eval rag`: 30 queries, scoped P@5 `0.207`, wrong-year rate `0.000`.
- The real-trace sample is versioned in
  `documents/eval_reports/rag_agent_traces.json`; `f1-eval rag` now reports its
  answer-level rate separately from retrieval-level citation match. The live
  sample has 1/1 matched citation instances and 1/1 fully matched traces
  (`n=1`). The regenerated `rag.md/json` records both metrics.
- Live agent trace, 2026-09-23: the retained scoped 2025 pit-lane-speed run returned one `query_rag_tool` message correlated to call ID `call_PTejRXibyWTR9ZdpiH56Veme`. Its exact final answer is saved in `documents/eval_reports/rag_agent_traces.json`; it cites `Article 34.7` once, and the five retrieved article headers are saved with their scores. The validator returned no violations and `citation_faithful` was true. The saved ToolMessage ID/name and SHA-256 are paired with the call ID, and a local query replay with the same tool arguments reproduced the full content hash. The retained record includes a short Article 34.7 excerpt rather than copying all retrieved regulation text.
- The retained run used `gpt-4.1-mini`: 2,111 input tokens and 113 output tokens across two API requests, with estimated standard-rate upper-bound cost `$0.0010252`. One earlier validation invocation used 1,721 input and 142 output tokens, estimated at `$0.0009156`; total estimated upper bound across both invocations was `$0.0019408` before cached-input discounts. Both runs disabled retries and limited the LangGraph recursion count to five. No model calls were made after these two invocations.
- Earlier Astra high reviews confirmed the wrapper contract and blocked closure
  first on the lack of a real trace, then on a summary record without underlying
  answer/tool-message evidence. The newer trace artifact and replayed hash now
  address that evidence gap. The final independent trace-preservation review
  returned GO for the written real-trace metric criterion; its report is at
  `C:\Users\victo\.claude\plans\F1_322_astra_trace_evidence_20260923.md`.

The retrieval benchmark's citation-match column measures article metadata in
retrieved chunks; it remains distinct from the live answer citation-match sample
above. No cached real N30 answer/tool-trace corpus was found, so the sample was
generated through the actual LangGraph path. The citation flags are present on
`RegulationContext`; the downstream N31 payload does not yet serialize them, so
callers of that payload cannot inspect violations.

No Qdrant rebuild, scorer change, telemetry-submodule change, or production
deployment was performed.
