# Testing & QA

F1 StratLab keeps the pull-request gate fast without deleting the tests that
need real data, expensive measurement, or an external service. The gate runs
the hermetic tiers in parallel; scheduled and local commands cover the rest.

## Run the suite

```bash
# The fast PR-equivalent gate
uv run pytest -v -n 4 --dist=loadfile \
  -m "not data and not slow and not network" \
  --cov=src --cov-report=term-missing

# The complete collected suite
uv run pytest -v -n 4 --dist=loadfile \
  --cov=src --cov-report=term-missing
```

## RAG retrieval evaluation

The shared `f1-eval rag` command evaluates the production BGE-M3 retriever over
the 30 manually verified queries in
[`data/rag_eval/queries_v2.json`](https://github.com/VforVitorio/F1-StratLab/blob/dev/data/rag_eval/queries_v2.json):

```bash
uv run f1-eval rag
```

It reports conventional P@1/P@3/P@5, hit@5 for comparison with the historical
N30B notebook, MRR, retrieval-level citation match, wrong-year rate, and P50/P95
latency. The command runs the season-scoped production path and an unscoped
control. It loads BGE-M3 once and makes no LLM calls. The Markdown and JSON
reports land in `documents/eval_reports/rag.{md,json}`. The complete run needs
the local FIA PDFs and Qdrant index, so it stays outside the fast CI gate.

The fast gate took **56.24 seconds** on the development machine used for the
2026-09-16 audit. The complete suite took **245.64 seconds** with four workers,
down from **276.82 seconds** before this cleanup and **383.27 seconds** before
the tier split. The earlier serial comparison fell from **670.47 seconds** to
**525.48 seconds**. These figures are local wall-clock
measurements, so they are not a promise about every runner. On GitHub, the PR
test job fell from **127 seconds** to **100 seconds**. The previous feature push
also ran a duplicate **194-second** test job; feature branches no longer trigger
that push workflow, reducing the two-run cost from **321** to **100
job-seconds**, a **68.8%** reduction.

## Markers

Markers are declared in `pyproject.toml`. They explain why a test is excluded,
not whether the test is less important.

| Marker | Meaning | Default gate |
|---|---|---|
| `unit` | Pure hermetic logic | Included |
| `contract` | API, schema, serialization, or fixture boundary | Included |
| `data` | HF dataset, model weights, or measured tables | Excluded |
| `gpu` | CUDA-dependent execution | Excluded |
| `llm` | Live or hermetic LLM backend | Excluded until a stubbed tier exists |
| `slow` | Expensive measurement or real-path check | Excluded |
| `network` | Public service or external artefact | Excluded |

Pytest's `-ra` setting prints skipped tests. A skipped data test means that its
artefacts were not present and that measurement did not run.

## CI and scheduled checks

The `test` job in [`ci.yml`](https://github.com/VforVitorio/F1-StratLab/blob/main/.github/workflows/ci.yml)
uses four xdist workers, `--dist=loadfile`, coverage, and the fast marker
expression. Its collection floor uses the same expression, guarding against a
broken import or accidental mass skip. The push trigger covers `main`, `dev`,
and `test`; feature branches use the pull-request trigger, so one commit does
not run both workflows.

The excluded checks remain explicit:

- `nightly-tests.yml` runs the complete collected parent suite with coverage,
  Monday to Friday at 03:00 UTC and on demand.
- `network-contracts.yml` checks the published Hugging Face cards every Monday
  at 03:30 UTC and on demand.
- Data-backed evaluation runs locally on a machine with the HF dataset and
  model artefacts. Those files are intentionally not committed to the repo.

## What the efficiency pass changed

- MC-table regeneration now writes into pytest's temporary directory through
  `--json-out` and `--eval-dir`, so tests do not mutate committed artefacts.
- Raw-data and model-recompute measurements are marked `slow`.
- The registry tests call the specific metric they protect and use a cheap
  aggregator-wiring test for the join itself.
- The RAG-index script lazily imports PDF, Qdrant, and embedding dependencies,
  keeping import smoke tests lightweight.
- Six low-signal test cases were removed, plus one tautological assertion. No
  whole test module was removed.
- The parent repository carries a deterministic `mini_race.parquet` fixture;
  the telemetry submodule carries the FakeOpenAI server and recorded SSE
  fixtures. Its latest hermetic run is 107 passed, 4 skipped, with no warnings.
- Interactive voice I/O is retired from the active tree. Team-radio audio and
  Whisper transcription remain active because they feed N29; the former voice
  implementation is preserved on the submodule's [`legacy_version` branch](https://github.com/VforVitorio/F1_Telemetry_Manager/tree/legacy_version).

## Dependency cleanup

The parent lock updates `accelerate` to 1.15.0 and `pytorch-lightning` to 2.6.6,
and removes unused `passlib` and `bcrypt`. Test environments use `httpx2` for
Starlette's current `TestClient`. The latest local pip-audit run reports 37
findings in Pillow 11.3.0 and setuptools 81.0.0. Their fixes remain constrained
by the Arcade and CUDA PyTorch graphs; the exact waivers stay in
`osv-scanner.toml`.

When a production contract changes, update the matching guide under
`documents/dev_docs/` and this page in the same pull request. When deleting a
test, state which remaining assertion protects the behaviour and why the old
case was redundant.

Treat `src/agents/` as a protected path. Do not edit it for routine cleanup or
simplification. A feature change may touch it only after its impact is mapped,
the scope is minimal, and extra regression checks cover the affected contract.

## Further reading

- [pytest markers](https://docs.pytest.org/en/stable/example/markers.html)
- [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/)
- [Coverage.py](https://coverage.readthedocs.io/en/latest/)
