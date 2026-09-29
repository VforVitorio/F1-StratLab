"""Cheap guards for the versioned RAG evaluation contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.benchmark_rag_chunking import _decision, legacy_fixed_window_chunks
from scripts.build_rag_index import PDFDocument, _legacy_sliding_hashes, iter_chunks
from src.strategy.eval.rag import load_queries


@pytest.mark.unit
def test_2026_query_delta_has_verified_prefixed_articles() -> None:
    query_path = Path(__file__).resolve().parents[2] / "data" / "rag_eval" / "queries_2026.json"
    queries = load_queries(query_path)

    assert len(queries) == 5
    assert {query.year for query in queries} == {2026}
    assert all(query.article.startswith("B") for query in queries)


@pytest.mark.unit
def test_legacy_chunk_baseline_reproduces_the_v261_window_and_first_article_label() -> None:
    document = PDFDocument(
        path=Path("sporting_regs_2025.pdf"),
        doc_type="sporting_regs",
        year=2025,
        text=(
            "30.5 USE OF TYRES\nIf the formation lap is started behind the safety car "
            "in accordance with Article 49.1a, a penalty under Article 54.3d) applies.\n"
        ),
    )

    legacy = legacy_fixed_window_chunks(document)
    article_aware = list(iter_chunks(document))

    assert {chunk.chunk_hash for chunk in legacy} == _legacy_sliding_hashes(document)
    assert legacy[0].article == "Article 49.1"
    assert article_aware[0].article == "Article 30.5"


@pytest.mark.unit
def test_chunking_gate_rejects_quality_regression() -> None:
    baseline = {
        "precision_at_5": 0.217,
        "mrr": 0.679,
        "citation_match_rate": 0.829,
        "wrong_year_rate": 0.0,
    }
    candidate = {**baseline, "precision_at_5": 0.206, "latency_p95_ms": 38.7}

    assert _decision(baseline, candidate) == "KEEP_BASELINE"
