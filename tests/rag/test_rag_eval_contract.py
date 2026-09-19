"""Cheap guards for the versioned RAG evaluation contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.benchmark_rag_chunking import _decision
from src.strategy.eval.rag import load_queries


@pytest.mark.unit
def test_2026_query_delta_has_verified_prefixed_articles() -> None:
    query_path = Path(__file__).resolve().parents[2] / "data" / "rag_eval" / "queries_2026.json"
    queries = load_queries(query_path)

    assert len(queries) == 5
    assert {query.year for query in queries} == {2026}
    assert all(query.article.startswith("B") for query in queries)


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
