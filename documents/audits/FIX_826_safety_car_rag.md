# #826 Safety Car regulation grounding

Date: 2026-09-15

## Result

The RAG path no longer relies on a character window that can separate a rule from
its applicability condition. It now keeps numbered regulation clauses together,
preserves the containing article label, and passes the passages used by N30 to
the Layer 3 prompt alongside the generated summary.

The Safety Car query also keeps the tyre question in scope and explicitly asks
N30 to distinguish an ordinary race deployment from a wet formation-lap start or
race resumption.

## Evidence

Before the change, the 2025 Sporting Regulations fragment for Article 30.5 n)
started with `er tyres`, ended with `at such times`, and was labelled `Article
54.3` because that number appeared in a cross-reference. The condition was absent
from the passage returned to the model.

After the change, the same passage is one 528-character chunk labelled `Article
30.5`. It contains the formation-lap condition, the race-resumption condition,
the wet-tyre requirement, and the Article 54.3d) penalty reference.

The rebuilt local index contains 2,167 chunks. A real BGE-M3 retrieval against
the 2025 corpus returned:

| rank | article | score | role |
|---:|---|---:|---|
| 1 | Article 58.10 | 0.7513 | Safety Car procedure |
| 2 | Article 49.4 | 0.7507 | formation-lap pit-lane procedure |
| 3 | Article 30.5 | 0.7469 | conditional wet-tyre rule |
| 5 | Article 55.12 | 0.7105 | pit entry under a deployed Safety Car |

The official rule is in the [2025 FIA Sporting Regulations, Issue 5](https://www.fia.com/sites/default/files/fia_2025_formula_1_sporting_regulations_-_issue_5_-_2025-04-30.pdf).
The Qatar 2025 stop pattern is independently visible in the [official Formula 1 pit-stop summary](https://www.formula1.com/en/results/2025/races/1275/qatar/pit-stop-summary).

## Verification

- The new chunking regression was red against the old implementation and is green
  after the change: 4 tests passed.
- The tool-provenance tests pass: 2 tests passed.
- The orchestrator prompt tests pass: 9 tests passed.
- The season-scope tests pass: 10 tests passed.
- The engine and argument-threading tests pass: 8 tests passed.
- Ruff check passes on the repository.
- The local Qdrant index was rebuilt from the PDFs and queried through the real
  retriever.
- The full non-data suite passes: 1,454 tests passed, 4 optional dependency
  checks skipped, and 29 warnings.

The rich LLM path was not run because the configured OpenAI account returns HTTP
429 for exhausted credits. The retriever, prompt, and provenance changes are
therefore verified; the post-fix LLM decision rate remains unmeasured.

## Scope boundary

The article-aware chunking mechanism is also the mechanism scoped by #323, the
RAG Phase 5 issue for the 2026 refresh and eval-gated index changes. This change
fixes the concrete #826 failure case without claiming that the wider 2026 refresh
or the complete RAG citation-faithfulness programme is finished.
