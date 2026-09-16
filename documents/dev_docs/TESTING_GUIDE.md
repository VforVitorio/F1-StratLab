# F1 StratLab testing guide

This guide is the working contract for running, reviewing, and extending the
parent repository's tests. It complements `documents/audits/AUDIT_TESTING_QA.md`,
which records the audit findings and the remaining quality backlog.

## The short version

The pull-request gate runs the cheap, hermetic tests in parallel. Measurement
tests, data-backed tests, and external contracts remain available, but they are
selected explicitly so a normal review gets a quick and meaningful signal.

```powershell
# Fast PR-equivalent gate
uv run pytest -v -n 4 --dist=loadfile `
    -m "not data and not slow and not network" `
    --cov=src --cov-report=term-missing

# Full collected suite, useful before a release or test-boundary change
uv run pytest -v -n 4 --dist=loadfile --cov=src --cov-report=term-missing
```

On the 2026-09-16 baseline, the fast gate completed in 60.05 seconds locally.
The complete suite measured 276.82 seconds with four workers, compared with
383.27 seconds before the tier split. The serial complete-suite comparison was
525.48 seconds versus 670.47 seconds before the change. These are wall-clock
measurements on one development machine, not a promise about every runner.

The GitHub Actions comparison is measured from the two adjacent strategy-wake
and test-efficiency PRs. The PR test job fell from 127 seconds to 102 seconds.
The previous feature push also ran a duplicate 194-second test job; feature
branches no longer trigger that push workflow, so the two-run cost fell from
321 job-seconds to 102 job-seconds, a 68.2% reduction. Job-seconds are a CI
consumption proxy, not a billing statement.

## Test tiers

Markers are registered in `pyproject.toml` and should describe why a test is
expensive or unavailable, not merely what module it imports.

| Marker | Use it for | Where it runs |
|---|---|---|
| `unit` | Pure logic with no external artefact or service | Every PR |
| `contract` | API, schema, serialization, and fixture-backed boundaries | Every PR |
| `data` | HF datasets, model weights, or real measured tables | Local data runs |
| `gpu` | CUDA-only execution | A matching local machine |
| `llm` | A live or hermetic LLM backend | Explicitly selected runs |
| `slow` | Expensive measurements or real-path checks | Focused runs and nightly collection |
| `network` | Public services or external artefacts | `network-contracts.yml` |

The fast expression excludes `data`, `slow`, and `network`. It does not hide a
failure inside an included test. Pytest's `-ra` setting keeps skips visible;
when a data artefact is absent, the resulting skip means "not executed", not
"measurement passed".

Useful focused commands:

```powershell
# Measurement tests, including the MC-table regeneration comparison
uv run pytest tests/mc/test_mc_measured_tables.py -m slow -v

# Evaluation tests that need local model and holdout artefacts
uv run pytest tests/eval/ -v

# External publication contract
uv run pytest tests/audit/test_hf_cards_are_published.py -m network -v

# Collection-only guard used by CI
uv run pytest --co -q -m "not data and not slow and not network"
```

## What changed in the efficiency pass

- The MC-table regeneration test writes to `tmp_path` through the script's
  `--json-out` and `--eval-dir` options. It compares the generated JSON with
  the committed table without mutating `data/` or `data/eval/`.
- Expensive raw-data and model-recompute checks are marked `slow`.
- Hugging Face publication checking is marked `network` and runs in its own
  scheduled or manually dispatched workflow.
- Evaluation goldens call the specific measurement function they protect.
  The registry aggregator also has a cheap wiring test, so the focused tests do
  not recompute every metric just to prove that the registry joins its parts.
- `scripts/build_rag_index.py` keeps PDF, Qdrant, and embedding imports inside
  the functions that need them. Import smoke tests therefore do not load the
  RAG runtime merely to inspect the script.
- Six tautological or low-signal test cases were removed, and one tautological
  assertion was simplified. No complete test module was deleted: every
  remaining module still protects a distinct contract or regression surface.

## CI layout

`.github/workflows/ci.yml` has five jobs. `test` uses four xdist workers,
`--dist=loadfile`, coverage, and the fast marker expression. The collected-node
floor runs with the same expression, so a broken import or accidental mass
skip cannot make the fast gate look healthy. `lint`, `typecheck`, and the
PITWALL UI check remain separate jobs, while `pip-audit` remains advisory while
its dependency baseline is resolved.

The push trigger covers `main`, `dev`, and `test`. Feature branches rely on the
pull-request trigger, avoiding a duplicate push run for the same commit.
Changes to source, tests, scripts, data contracts, documentation, and workflow
configuration still activate the Python jobs because those paths can change
the effective test contract.

Two scheduled workflows complement the gate:

- `nightly-tests.yml` runs the complete collected parent suite with four
  workers and coverage, Monday to Friday at 03:00 UTC and on demand. The
  repository does not version its HF data or model weights, so data-gated tests
  still require a machine where those assets have been provisioned.
- `network-contracts.yml` checks that the published Hugging Face cards remain
  reachable, every Monday at 03:30 UTC and on demand.

The submodule has its own CI and remains a separate responsibility. Parent
changes must still respect the submodule's commit and pointer rules.

## Review rules

Prefer a small contract test over a broad fixture when a seam is the thing at
risk. Do not test a mock's implementation, add test-only methods to production,
or mock a dependency before reading how the production code calls it.

When deleting a test, record the reason in the PR and check that its behaviour
is covered by another assertion. Delete duplicated or tautological assertions;
keep tests that protect data boundaries, public schemas, numerical decisions,
or a previously escaped bug.

When changing production behaviour, update this guide or the relevant
development guide and the matching page under `docs/pages/` in the same PR.
If a test changes a generated artefact contract, document the producer command
and the output path beside the test.

## Reference material

- [pytest markers](https://docs.pytest.org/en/stable/example/markers.html)
- [pytest-xdist](https://pytest-xdist.readthedocs.io/en/stable/)
- [Coverage.py](https://coverage.readthedocs.io/en/latest/)
- [GitHub Actions workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
