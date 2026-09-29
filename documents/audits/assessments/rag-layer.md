# AUDIT - RAG layer (FIA regulation retrieval: index, retriever, N30 consumption)

> **Scope:** the retrieval-augmented layer over the FIA Sporting Regulations: `src/rag/retriever.py` (RagRetriever, `query_rag_tool`, RagConfig), `scripts/build_rag_index.py` (PDF to Qdrant ingestion), `scripts/download_fia_pdfs.py` (FIA scraper + known-URLs fallback), the on-disk Qdrant index (`data/rag/qdrant_local/`, `BAAI/bge-m3` embeddings), and how N30 (`src/agents/rag_agent.py`) and the orchestrator N31 (`src/agents/strategy_orchestrator.py`) consume it. Last code subsystem without a dedicated audit.
>
> **Inputs read:** `src/rag/{__init__,retriever}.py`, `scripts/build_rag_index.py`, `scripts/download_fia_pdfs.py`, `src/agents/rag_agent.py:100-230` (read-only, untouchable), `src/agents/strategy_orchestrator.py:717-760`, `src/f1_strat_manager/data_cache.py` (get_data_root + HF snapshot patterns), `data/rag/` contents, memory `project_rag_src_plan`, `reference_n31_bibliography`; cross-referenced (not duplicated): `2026-reg-concept-drift.md` F-10, `ml-agents-eval.md` E-11/R-9 (#205), `security.md` S-9/D1 (#223), `devex.md` DX-05 (#251).
>
> **Constraint:** the original audit was plan-only. The completed Phase 5 work
> remains outside `src/agents/`; every change landed in `src/rag/`, `scripts/`,
> tests, or the shared eval package.

## Current status after v2.7.0 promotion (2026-09-29)

The July audit below records the original findings. The implementation has
changed since then; these are the current boundaries.

| Area | Current state |
|---|---|
| Replay retrieval | N30 passes the race year to both retrievals. If the index has no points for that year, retrieval warns and falls back across indexed years. |
| Chat retrieval | `query_regulations` and `POST /api/v1/strategy/rag` accept an optional year. Omitting it keeps the historical unscoped lookup. |
| Index and evaluation | The manifest covers 2023-2026. Production uses article-aware 512/64 chunks and preserves headings such as `B5.13.1`. The 35-query A/B in `documents/eval_reports/rag_2026.{md,json}` rejected 1024/128 because P@5 and MRR were lower. |
| Answer grounding | N30 returns the passages from its actual tool trace, applies the similarity floor, and reports citations absent from the retrieved articles. The trace report is `documents/eval_reports/rag_agent_traces.json`; its `n=1`, 1/1 result is a path check, not a general answer-quality estimate. |
| No-LLM display | The N30 no-result crash from #1251 was fixed in PR #1255. |
| Fresh-environment build | `pypdf` is now declared in the project dependencies. |

Replay scoping (#320, PR #1197), shared retrieval evaluation (#321, PR #1247),
the index manifest (#1195, PR #1248), answer grounding (#322, PR #1254), and
the 2026 corpus and chunking comparison (#323, PRs #1249 and #1266) are on
`main` after promotion #1267. All five issues are closed. The 35-query
comparison uses a historical fixed-window 512/64 baseline; it does not validate
end-to-end application of conditional rules, which remains open as #826.

The 30-query retrieval set is `data/rag_eval/queries_v2.json`; its report is
`documents/eval_reports/rag.{md,json}`. The 2026 comparison adds five queries.

The chat default is still unscoped when callers omit `year`. The builder and
downloader remain source-checkout tools, while installed runs consume the
Hub-provided data root. Local Qdrant remains single-process. These limits are
not evidence that the season filter is absent from replay or explicitly scoped
chat requests.

---

## 1. Baseline executive summary (2026-07-07)

At the audit date, N30 used the LangGraph `@tool` wrapper `query_rag_tool` over one Qdrant collection (`fia_regulations`) with BGE-M3 embeddings. The findings below describe that baseline, not the current implementation.

1. **Season correctness is enforced nowhere at query time.** The index mixes 2023/2024/2025 chunks in one collection; `RagRetriever.query()` (`src/rag/retriever.py:208-255`) has no `year` or `doc_type` filter, even though the `RegulationChunk` docstring promises callers can filter by both (`retriever.py:106-113`). The orchestrator never passes the race's season into `_build_rag_question` (`strategy_orchestrator.py:717-738`), and the N30 system prompt hardcodes "Always prefer the most recent regulation year (2025)" (`rag_agent.py`, `_SYSTEM_PROMPT`). A 2023 replay can be answered with 2025 rules, and vice versa when a 2023 chunk simply scores higher. This is the query-time half of the 2026-reg audit's F-10 (which covers the ingest half: `download_fia_pdfs.py:68` caps `supported_years` at 2023-2025).
2. **Citation grounding is structurally loose.** `run_rag_agent` (`rag_agent.py:175-210`) lets the ReAct agent retrieve with its own rewritten queries, then re-queries the retriever with the *original* question to populate `RegulationContext.chunks/articles`. The chunks attached as evidence are not necessarily the passages the LLM actually read, so `ctx.articles` and the article numbers inside `ctx.answer` can diverge silently. There is also no similarity floor: `query_rag_tool` returns the top-5 whatever their scores, so an off-topic question still feeds five weak passages to a model instructed to cite articles.
3. **The index is unversioned and staleness is undetectable.** No manifest records which PDF issue, embedding model, or chunk parameters built the index. `health_check()` (`retriever.py:257-276`) reports a vector count but not year coverage or model stamp. Nothing ever triggers a reindex: `download_link` skips any existing file (`download_fia_pdfs.py:406-410`) and its docstring references a `--force` flag that does not exist in `main()` (only `--years`/`--dry-run`), so an FIA erratum requires a manual delete that nobody is prompted to do.
4. **Retrieval quality had one one-shot, unwired measurement.** N30B (15 queries, P@k/MRR, manual ground truth) existed as a notebook only, and the three canned production question shapes were not in it. Issue #321 now provides the shared `src/strategy/eval/` implementation and a 30-query set; the notebook remains a historical comparison.
5. **The build is broken on a fresh env and the docstrings have drifted.** `pypdf` is imported (`build_rag_index.py:34`) but not declared (DevEx DX-05, P1 there; cross-referenced, not re-owned). `extract_text_from_pdf`'s docstring says "using PyMuPDF" (`build_rag_index.py:201`), `ensure_collection`'s says the embeddings come from "all-MiniLM-L6-v2" (`build_rag_index.py:376`); both are relics of earlier model choices and will mislead the next maintainer.

The baseline already used `chunk_hash` and `get_existing_hashes` for incremental indexing. A missing collection raised an actionable error, and `lru_cache` kept the local Qdrant client from opening the same store twice in one process. The downloader had a known-URL fallback, and the indexer intentionally included Sporting Regulations only.

---

## 2. Baseline data flow

```
download_fia_pdfs.py            build_rag_index.py                 retriever.py
FIA site scrape + known URLs -> sporting_regs_<year>.pdf ->        RagRetriever.query()
(2023-2025 at audit opening)    512-char windows, 64 overlap,      top_k=5, cosine
                                regex article/section tags,   ->   query_rag_tool (@tool, string out)
                                sha256 dedup, upsert to                 |
                                data/rag/qdrant_local              rag_agent.py (N30, ReAct, 1 tool)
                                                                        |
                                                   strategy_orchestrator.py (N31): conditional
                                                   activation (SC / pit / radio PENALTY-WARNING),
                                                   _build_rag_question -> regulation_context field
```

Consumers: N30's `run_rag_agent` / `run_rag_agent_from_state`; N31 attaches the answer string as `StrategyRecommendation.regulation_context` (`strategy_orchestrator.py:399-400,465`); the chat surface exposes it as the `query_regulations` MCP tool (Security audit S-2/S-9 territory). Data distribution: `data/rag/**` is in the HF snapshot patterns as an optional artefact (`data_cache.py:120-122`), so a prebuilt index can ship from the Hub with no version pin.

---

## 3. Findings recorded at audit opening

| ID | Prio | Finding | Why it matters / size |
|---|---|---|---|
| **RAG-01** | **P1** | **No season scoping end to end.** One collection mixes years 2023-2025; `query()` exposes no `year`/`doc_type` filter (`retriever.py:208-243`) despite `RegulationChunk` docstrings promising both (`retriever.py:106-113`); `_build_rag_question` (`strategy_orchestrator.py:717-738`) never mentions the race season; N30's prompt hardcodes "prefer 2025" and "2023-2025" (`rag_agent.py` `_SYSTEM_PROMPT`). The Qatar demo's Article 36.3 citation is season-correct by luck of scoring, not by construction. Query-time complement of F-10 (`2026-reg-concept-drift.md:178`). | Wrong-season rule cited with full confidence in replays and, post-2026, guaranteed drift. Fix is additive: filter param + payload index + caller wiring. **M** |
| **RAG-02** | **P1** | **Evidence and answer can diverge.** `run_rag_agent` re-queries with the original question after the agent answered from its own (possibly rewritten) tool queries (`rag_agent.py:175-210`, the docstring documents the double retrieval); `ctx.chunks`/`ctx.articles` are therefore not guaranteed to be what the LLM read. No similarity threshold anywhere: `query_rag_tool` (`retriever.py:317-349`) formats top-5 regardless of score; "No relevant passages" is returned only for an empty hit list, never for a low-quality one. Nothing checks that articles cited in `answer` appear in the retrieved set (hallucinated-article risk, ML-eval R-9). | Citations are the product here (they reach the UI and the paper verbatim). Faithfulness must be checkable, then checked. Indirect-injection side of the same surface is owned by Security S-9/D1 (#223); not duplicated here. **M** |
| **RAG-03** | **P1** | **Fresh-env index build fails: `pypdf` undeclared.** `build_rag_index.py:34` imports it; pyproject declares only `qdrant-client`, `sentence-transformers`, `bs4` (pyproject.toml:43,74,108). **Owned by DevEx DX-05 (#251); tracked here only as a blocking dependency of every phase below.** | ModuleNotFoundError on `uv sync` + run. **S** (lands via #251) |
| **RAG-04** | **P2** | **Resolved by #1195/#323.** `data/rag/index_manifest.json` records source PDF hashes, model, dimension, distance, chunker identity, chunking parameters, indexed years, point count, and build time. The retriever validates model, collection, vector dimension, and the actual Qdrant point count before loading BGE-M3; missing manifests warn for compatibility with older HF copies. `health_check()` exposes years and the manifest hash. The refreshed local corpus contains 2023-2026 and 2,844 points. Schema-1 manifests without `chunking_verified` remain readable as unverified. | The Hub copy must stay synchronized with this manifest and the 2026 PDF whenever the index is republished. **M** |
| **RAG-05** | **P2** | **Resolved by #321.** The former N30B notebook-only measurement is now exposed as `uv run f1-eval rag`, using 30 manually verified queries and production question shapes. The report includes P@k, MRR, wrong-year rate, retrieval-level citation match, and latency. | `src/strategy/eval/rag.py` and `documents/eval_reports/rag.{md,json}`. Agent answer faithfulness remains Phase 4. **S-M** |
| **RAG-06** | **P2** | **Resolved by #323.** The builder now splits on article headings, packs clauses without crossing article boundaries, preserves numeric and `B`-prefixed 2026 identifiers, and records the chunker in the manifest. On the same 35 queries, article-aware 512/64 improved over the v2.6.1 fixed-window 512/64 baseline: P@5 0.109 to 0.217 (+100%), MRR 0.368 to 0.679 (+84.6%), and citation match 0.657 to 0.829 (+26.1%). The separate article-aware 1024/128 candidate was not adopted because P@5 fell from 0.217 to 0.211 and MRR from 0.679 to 0.672. | Production remains on article-aware 512/64. Reconsider 1024/128 only with a new verified query set and a non-regressing result. **M** |
| **RAG-07** | **P2** | **Build/runtime path split-brain.** The retriever resolves `data/rag/` through `get_data_root()` (env override `F1_STRAT_DATA_ROOT`, or `~/.f1-strat/data/` in the `uv tool install` flow; `retriever.py:60-75`), but the builder and downloader are hardwired repo-relative (`build_rag_index.py:79-90`, `download_fia_pdfs.py:73-86`) and ignore the override. In an installed-tool env, `build_rag_index.py` writes an index the retriever will never open. | Silent "collection not found" for exactly the users who followed the docs; one shared path helper fixes all three files. **S** |
| **RAG-08** | **P3** | **Qdrant local mode is single-process.** The embedded client holds a file lock; the `lru_cache` singleton (`retriever.py:284-297`) protects one process only, so backend + CLI + Streamlit running simultaneously against the same `qdrant_local/` raise `AlreadyLocked` for the latecomers. Undocumented in README/INSTALL. | Confusing failure the day two surfaces run at once; document now, consider a served Qdrant only if it ever actually bites. **S** |
| **RAG-09** | **P3** | **Docstring drift + minor ingest nits.** (a) "using PyMuPDF" (`build_rag_index.py:201`) vs actual `pypdf`; (b) "all-MiniLM-L6-v2" (`build_rag_index.py:376`) vs bge-m3; (c) `RegulationChunk` promises doc_type/year filtering that does not exist (RAG-01); (d) within-batch duplicate hashes are not deduped (`get_existing_hashes` covers only pre-existing points, `build_rag_index.py:565-569`), so the same passage in two PDFs indexed in one run creates two points; (e) sequential point IDs from `points_count` (`build_rag_index.py:583`) collide if points are ever deleted individually. | Cheap truth-restoring fixes; (d)/(e) matter only when the corpus grows. **S** |

At the July audit date, no P0 had been found. The later no-LLM crash was tracked separately as #1251 and fixed on `dev` through PR #1255.

---

## 4. Original phased plan

**Phase 1 - Truth and build integrity (S).**
Verify #251/DX-05 landed `pypdf` (else this phase carries it); fix the three drifted docstrings (RAG-09 a-c); delete or implement the phantom `--force` in `download_fia_pdfs.py` (prefer implement: re-download replaces the file); add within-batch hash dedup. Acceptance: `python scripts/build_rag_index.py --help` works on a fresh `uv sync`; no docstring names a component the code does not use.

**Phase 2 - Index manifest + season scoping (M).** *(RAG-01, RAG-04, RAG-07)*
Builder writes `data/rag/index_manifest.json` (source PDF sha256 + FIA issue title, embedding model + dim, chunk params, years indexed, build timestamp); retriever validates model/collection against it at init and `health_check()` reports year coverage + manifest hash. All three files resolve paths through one shared helper honouring `get_data_root()`. Add optional `year`/`doc_type` filter params to `RagRetriever.query()` and `query_rag_tool` (Qdrant payload filter, additive signature); wire the season from `lap_state.session_meta` into the RAG question path **additively** (new entry point or param default; `src/agents/` internals stay byte-identical, so the prompt's "prefer 2025" is superseded by filtered retrieval rather than edited). Include the manifest in the HF pin-manifest scheme. Acceptance: querying with `year=2023` never returns a 2025 chunk; retriever refuses (loud warning or raise) on model mismatch.

**Phase 3 - RAG eval inside the shared #205 package (M).**
The shared `rag` module in `src/strategy/eval/` ports the verified query method from N30B into the #205 report conventions. The v2 set has 30 queries covering the production question shapes, three seasons, and year-sensitive rules. Metrics are P@k, MRR, **wrong-year rate**, and **retrieval-level citation match**. Agent-level citation faithfulness remains Phase 4 because it needs the real tool trace. The benchmark is a local data command and writes one JSON report plus one Markdown report. Acceptance is met when one command re-runs the benchmark and the baseline is recorded before Phase 5 changes the corpus.

**Phase 4 - Grounding and citation faithfulness (M).** *(RAG-02)*
Additive N30 entry point that extracts the agent's *actual* tool calls/results from the LangGraph message history so `RegulationContext.chunks` = what the LLM read (drop the second retrieval); add a configurable similarity floor in `query_rag_tool` returning the explicit "no relevant passages" string below it; post-hoc citation check (cited articles as subset of retrieved articles) flagging violations on the `RegulationContext`. Security D1 (#223) owns delimiting retrieved text as untrusted data; this phase only verifies the wrapper cooperates. Acceptance: eval's citation-match rate computed on real agent traces; a below-threshold query yields the refusal string, not five weak chunks.

**Phase 5 - 2026 refresh + chunking experiment (M-L).** *(F-10 execution + RAG-06)*
Completed by #323. `supported_years` includes 2026, the official FIA Section B
Sporting Regulations Issue 08 PDF is tracked by URL and SHA-256, and the local
index was rebuilt with 2,844 article-aware 512/64 points after removing PDF
page headers from article detection. Five verified 2026 queries were added to
the same 30-query evaluation harness. The v2.6.1 fixed-window 512/64 baseline
was rebuilt in a temporary collection and compared with production article-aware
512/64 over the same 35 queries. P@5 rose from 0.109 to 0.217, MRR from 0.368
to 0.679, and citation match from 0.657 to 0.829; wrong-year rate stayed 0.000.
The separate article-aware 1024/128 candidate built 2,292 chunks, but the gate
kept 512/64: P@5 0.217 vs 0.211, MRR 0.679 vs 0.672, citation match 0.829 for
both, and wrong-year rate 0.000 for both.
The benchmark also rejects a production collection whose `(year, chunk_hash)`
set differs from the local baseline and preserves the retriever's unindexed-
season fallback. Acceptance is met without adopting a weaker chunking scheme.

Order rationale: 1 unblocks everything; 2 kills the silent wrong-season class before eval measures it as noise; 3 must exist before 4/5 so improvements are provable; 5 last because it is the only phase whose value depends on the FIA's calendar.

---

## 5. Open design questions

1. **Season default for chat:** the chat `query_regulations` tool accepts an optional year but has no race context. Omitted years still search all indexed seasons. Decide whether to preserve that behavior or use the latest indexed year.
2. **Technical Regulations:** deliberately excluded (`download_fia_pdfs.py:92-96`) yet half-supported everywhere (filename regex, title patterns, doc_type payloads). Keep the latent support or strip it?
3. **Build and runtime paths:** the index builder and PDF downloader use the source checkout's `data/rag/`; installed runs resolve data through `F1_STRAT_DATA_ROOT` and use the Hub artifact. Keep the scripts maintainer-only or make them share the runtime resolver?
4. **Qdrant processes:** local mode locks the store to one process. Keep the single-process limit documented or move to a Qdrant server if concurrent surfaces become a real use case?
5. **Ingestion trust policy** (Security #223 Q5): state in `src/rag/README.md` that only operator-vetted FIA PDFs belong in `data/rag/documents/`?

---

## 6. Verification protocol (how we will know it worked)

- RAG-01/Phase 2: eval query set with year-discriminating ground truth (rules that changed 2023 to 2025); wrong-year rate = 0 with the filter on, measured nonzero baseline with it off.
- RAG-04/Phase 2: delete the manifest or swap the model name; retriever init fails loudly with an actionable message. `health_check()` output includes `years` and `manifest_hash`.
- RAG-05/Phase 3: benchmark re-run twice gives identical retrieval metrics; report lands in `documents/eval_reports/` with the standard provenance header.
- RAG-02/Phase 4: trace-level test: agent answer citing an article absent from its retrieved set raises the faithfulness flag; injected-chunk fixture behaviour is asserted by Security's S-9 test (cross-check only).
- RAG-06/Phase 5: legacy fixed-window 512/64 vs article-aware 512/64, plus article-aware 1024/128 vs 512/64, with P@k/MRR/citation-match on the same 35 queries; both decisions are recorded in `documents/eval_reports/rag_2026.{md,json}`.
- RAG-07: `F1_STRAT_DATA_ROOT=<tmp>` set for both build and query in one test; index built and found in the same directory.

---

*Audit opened 2026-07-07. Current status refreshed 2026-09-29. Cross-references: F-10 (`2026-reg-concept-drift.md`), E-11/R-9 + #205 (`ml-agents-eval.md`), S-2/S-9/D1 + #223 (`security.md`), DX-05 + #251 (`devex.md`).*
