"""Cheap contract tests for the shared RAG evaluator.

These tests use real ``RegulationChunk`` values and a tiny recording retriever.
They do not load Qdrant, model weights, PDFs, or an LLM. The real benchmark is
an explicit local data run, not part of the pull-request gate.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.rag.retriever import RegulationChunk
from src.strategy.eval.rag import (
    RagEvalConfig,
    RagEvalQuery,
    _normalise_text,
    _strict_hit,
    article_matches,
    evaluate_retriever,
    keyword_matches,
    load_queries,
    summarise_rows,
)


def _query(*, year: int = 2025) -> RagEvalQuery:
    return RagEvalQuery(
        query_id="QTEST",
        year=year,
        question="which rule applies?",
        category="test",
        source_pdf=f"sporting_regs_{year}.pdf",
        article="30.2",
        expected_keywords=("thirteen (13) sets",),
    )


def _chunk(*, year: int = 2025, article: str = "Article 30.2", text: str = "thirteen (13) sets"):
    return RegulationChunk(
        text=text,
        article=article,
        doc_type="sporting_regs",
        year=year,
        score=0.9,
    )


@pytest.mark.unit
def test_query_set_v2_has_thirty_unique_entries() -> None:
    queries = load_queries(Path("data/rag_eval/queries_v2.json"))

    assert len(queries) == 30
    assert len({query.query_id for query in queries}) == 30
    assert {query.year for query in queries} == {2023, 2024, 2025}


@pytest.mark.unit
def test_load_queries_rejects_duplicate_ids(tmp_path: Path) -> None:
    value = {
        "id": "Q01",
        "year": 2025,
        "query": "q",
        "category": "cat",
        "source_pdf": "sporting_regs_2025.pdf",
        "ground_truth": {"article": "1", "expected_keywords": ["x"]},
    }
    path = tmp_path / "queries.json"
    path.write_text(json.dumps([value, value]), encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        load_queries(path)


@pytest.mark.unit
def test_load_queries_rejects_a_source_pdf_from_another_year(tmp_path: Path) -> None:
    value = {
        "id": "Q01",
        "year": 2025,
        "query": "q",
        "category": "cat",
        "source_pdf": "sporting_regs_2024.pdf",
        "ground_truth": {"article": "1", "expected_keywords": ["x"]},
    }
    path = tmp_path / "queries.json"
    path.write_text(json.dumps([value]), encoding="utf-8")

    with pytest.raises(ValueError, match="match its query year"):
        load_queries(path)


@pytest.mark.unit
def test_strict_matching_requires_year_article_and_keyword() -> None:
    query = _query()

    assert article_matches(_chunk(), query)
    assert keyword_matches(_chunk(), query)
    assert not article_matches(_chunk(article="Article 55.7"), query)
    assert not keyword_matches(_chunk(text="a different clause"), query)
    assert not _strict_hit(_chunk(year=2024), query)


@pytest.mark.unit
def test_evaluate_retriever_uses_year_scope_and_keeps_wrong_year_visible() -> None:
    class RecordingRetriever:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int | None, int | None]] = []

        def query(self, question: str, top_k: int | None = None, year: int | None = None):
            self.calls.append((question, top_k, year))
            return [_chunk(year=2024), _chunk(), _chunk(article="Article 55.7")]

    retriever = RecordingRetriever()
    rows = evaluate_retriever(
        retriever,
        [_query()],
        config=RagEvalConfig("scoped", season_scoped=True),
    )

    assert retriever.calls == [("which rule applies?", 10, 2025)]
    assert rows[0]["wrong_year_hits_at_5"] == 1
    assert rows[0]["precision_at_1"] == 0.0
    assert rows[0]["precision_at_3"] == pytest.approx(1 / 3)
    assert rows[0]["mrr"] == pytest.approx(1 / 2)
    assert rows[0]["citation_match_at_5"] == 1.0


@pytest.mark.unit
def test_unscoped_control_does_not_pass_a_year_to_the_retriever() -> None:
    class RecordingRetriever:
        def query(self, question: str, top_k: int | None = None, year: int | None = None):
            assert question == "which rule applies?"
            assert top_k == 10
            assert year is None
            return []

    rows = evaluate_retriever(
        RecordingRetriever(),
        [_query()],
        config=RagEvalConfig("unscoped", season_scoped=False),
    )

    assert rows[0]["hit_at_5"] == 0.0
    assert rows[0]["wrong_year_top1"] is False


@pytest.mark.unit
def test_summary_uses_conventional_precision_and_reports_controls() -> None:
    rows = [
        {
            "precision_at_1": 1.0,
            "precision_at_3": 1 / 3,
            "precision_at_5": 1 / 5,
            "hit_at_5": 1.0,
            "content_hit_at_5": 1.0,
            "mrr": 1.0,
            "citation_match_at_5": 1.0,
            "wrong_year_hits_at_5": 0,
            "wrong_year_top1": False,
            "latency_ms": 10.0,
        },
        {
            "precision_at_1": 0.0,
            "precision_at_3": 0.0,
            "precision_at_5": 0.0,
            "hit_at_5": 0.0,
            "content_hit_at_5": 1.0,
            "mrr": 0.0,
            "citation_match_at_5": 1.0,
            "wrong_year_hits_at_5": 2,
            "wrong_year_top1": True,
            "latency_ms": 20.0,
        },
    ]

    summary = summarise_rows(rows, "control")

    assert summary["query_count"] == 2
    assert summary["precision_at_5"] == pytest.approx(0.1)
    assert summary["citation_match_rate"] == 1.0
    assert summary["wrong_year_rate"] == pytest.approx(0.2)
    assert summary["wrong_year_query_rate"] == 0.5
    assert summary["latency_p50_ms"] == 15.0
    assert summary["latency_p95_ms"] == pytest.approx(19.5)


@pytest.mark.unit
def test_pdf_text_normalisation_handles_wrapped_hyphenated_words() -> None:
    assert _normalise_text("dry -weather\n tyres") == "dry-weather tyres"
