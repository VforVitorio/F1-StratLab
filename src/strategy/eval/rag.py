"""Reproducible retrieval metrics for the FIA regulation RAG layer.

The evaluator measures the retriever directly. It does not call an LLM, so a
run is deterministic apart from the machine's embedding latency. The query
set is versioned under ``data/rag_eval/`` and every item carries its expected
article, season, and source PDF.

The scoped run is the production path. The unscoped run is a control that
keeps the wrong-season regression visible after season filtering was added.
Agent answer faithfulness belongs to the later grounding phase because it
requires the actual LangGraph tool trace.
"""

from __future__ import annotations

import json
import re
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from src.f1_strat_manager.data_cache import _find_repo_root
from src.rag.retriever import CFG, RegulationChunk, RagRetriever
from src.strategy.eval.report import build_header, write_report

QUERY_SET_NAME = "queries_v2.json"
REPORT_NAME = "rag"
TOP_K = 10
REPORT_K = 5


class Retriever(Protocol):
    """Small seam used by the metric tests and the production retriever."""

    def query(
        self,
        question: str,
        top_k: int | None = None,
        year: int | None = None,
    ) -> list[RegulationChunk]:
        """Return ranked regulation chunks for one query."""


@dataclass(frozen=True)
class RagEvalQuery:
    """One manually verified question in the RAG evaluation set."""

    query_id: str
    year: int
    question: str
    category: str
    source_pdf: str
    article: str
    expected_keywords: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RagEvalQuery":
        """Build a query and reject incomplete ground truth early."""
        ground_truth = value.get("ground_truth")
        if not isinstance(ground_truth, dict):
            raise ValueError(f"{value.get('id', '<unknown>')} has no ground_truth object")

        required = ("id", "year", "query", "category", "source_pdf")
        missing = [name for name in required if not value.get(name)]
        missing += [name for name in ("article", "expected_keywords") if not ground_truth.get(name)]
        if missing:
            raise ValueError(f"{value.get('id', '<unknown>')} is missing: {', '.join(missing)}")
        keywords = ground_truth["expected_keywords"]
        if not isinstance(keywords, list) or not all(
            isinstance(keyword, str) for keyword in keywords
        ):
            raise ValueError(f"{value['id']} expected_keywords must be a list of strings")

        source_pdf = Path(str(value["source_pdf"]))
        if source_pdf.name != str(value["source_pdf"]):
            raise ValueError(f"{value['id']} source_pdf must be a filename, not a path")
        expected_pdf = f"sporting_regs_{int(value['year'])}.pdf"
        if source_pdf.name != expected_pdf:
            raise ValueError(f"{value['id']} source_pdf must match its query year: {expected_pdf}")

        return cls(
            query_id=str(value["id"]),
            year=int(value["year"]),
            question=str(value["query"]),
            category=str(value["category"]),
            source_pdf=source_pdf.name,
            article=str(ground_truth["article"]),
            expected_keywords=tuple(keywords),
        )


@dataclass(frozen=True)
class RagEvalConfig:
    """One retriever mode included in the report."""

    name: str
    season_scoped: bool


def default_query_path() -> Path:
    """Return the checked-in query set for this checkout."""
    repo = _find_repo_root()
    base = repo if repo is not None else Path.cwd()
    return base / "data" / "rag_eval" / QUERY_SET_NAME


def load_queries(path: Path | None = None) -> list[RagEvalQuery]:
    """Load and validate the versioned RAG query set."""
    query_path = Path(path) if path is not None else default_query_path()
    payload = json.loads(query_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"RAG query set must be a non-empty JSON list: {query_path}")

    queries = [RagEvalQuery.from_dict(item) for item in payload]
    ids = [query.query_id for query in queries]
    if len(ids) != len(set(ids)):
        raise ValueError("RAG query ids must be unique")
    return queries


def _normalise_text(value: str) -> str:
    """Normalise PDF line wrapping without changing the words being scored."""
    text = (value or "").casefold().replace("\\n", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s*-\s*", "-", text).strip()


def _normalise_article(value: str) -> str:
    """Compare article numbers while accepting payload labels such as Article 55.7."""
    text = _normalise_text(value)
    text = re.sub(r"\barticles?\b|\bart\.\b", "", text)
    return re.sub(r"\s+", "", text)


def article_matches(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Return whether a chunk identifies the expected article in its metadata or text."""
    expected = _normalise_article(query.article)
    metadata = _normalise_article(chunk.article)
    text = _normalise_text(chunk.text)
    return bool(expected) and (expected in metadata or expected in text)


def keyword_matches(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Return whether a chunk contains at least one verified ground-truth keyword."""
    text = _normalise_text(chunk.text)
    return any(_normalise_text(keyword) in text for keyword in query.expected_keywords)


def _same_year(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Keep wrong-season chunks from counting as relevant retrievals."""
    return int(chunk.year) == query.year


def _strict_hit(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Return the headline relevance decision for one retrieved chunk."""
    return (
        _same_year(chunk, query) and article_matches(chunk, query) and keyword_matches(chunk, query)
    )


def _content_hit(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Return content relevance while ignoring the article-tagging field."""
    return _same_year(chunk, query) and keyword_matches(chunk, query)


def _article_hit(chunk: RegulationChunk, query: RagEvalQuery) -> bool:
    """Return article relevance for the retrieval-level citation metric."""
    return _same_year(chunk, query) and article_matches(chunk, query)


def _hit_at(values: Sequence[bool], k: int) -> float:
    """Return binary hit@k, used alongside conventional precision@k."""
    return float(any(values[:k]))


def _precision_at(values: Sequence[bool], k: int) -> float:
    """Return conventional precision@k with a fixed denominator."""
    return sum(values[:k]) / k


def _reciprocal_rank(values: Sequence[bool]) -> float:
    """Return the reciprocal rank of the first relevant chunk."""
    return next((1.0 / rank for rank, value in enumerate(values, start=1) if value), 0.0)


def _query_row(
    query: RagEvalQuery,
    chunks: list[RegulationChunk],
    elapsed_ms: float,
    config: RagEvalConfig,
) -> dict[str, Any]:
    """Convert one ranked retrieval into stable, JSON-serialisable metrics."""
    strict = [_strict_hit(chunk, query) for chunk in chunks]
    content = [_content_hit(chunk, query) for chunk in chunks]
    articles = [_article_hit(chunk, query) for chunk in chunks]
    top_five = chunks[:REPORT_K]
    wrong_year_hits = sum(int(chunk.year != query.year) for chunk in top_five)
    top_year = chunks[0].year if chunks else None
    return {
        "config": config.name,
        "query_id": query.query_id,
        "category": query.category,
        "expected_year": query.year,
        "expected_article": query.article,
        "retrieved_years_at_5": [int(chunk.year) for chunk in top_five],
        "retrieved_articles_at_5": [chunk.article for chunk in top_five],
        "wrong_year_hits_at_5": wrong_year_hits,
        "wrong_year_top1": bool(top_year is not None and top_year != query.year),
        "precision_at_1": _precision_at(strict, 1),
        "precision_at_3": _precision_at(strict, 3),
        "precision_at_5": _precision_at(strict, 5),
        "hit_at_1": _hit_at(strict, 1),
        "hit_at_3": _hit_at(strict, 3),
        "hit_at_5": _hit_at(strict, 5),
        "content_hit_at_5": _hit_at(content, REPORT_K),
        "citation_match_at_5": _hit_at(articles, REPORT_K),
        "mrr": _reciprocal_rank(strict),
        "latency_ms": round(elapsed_ms, 3),
    }


def evaluate_retriever(
    retriever: Retriever,
    queries: Sequence[RagEvalQuery],
    *,
    config: RagEvalConfig,
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """Evaluate one retriever mode without loading an LLM or duplicating retrieval logic."""
    rows: list[dict[str, Any]] = []
    for query in queries:
        year = query.year if config.season_scoped else None
        started = time.perf_counter()
        chunks = retriever.query(query.question, top_k=top_k, year=year)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        rows.append(_query_row(query, chunks, elapsed_ms, config))
    return rows


def _percentile(values: Sequence[float], probability: float) -> float:
    """Return an inclusive percentile without adding a numerical dependency."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    return float(
        statistics.quantiles(values, n=100, method="inclusive")[int(probability * 100) - 1]
    )


def summarise_rows(rows: Sequence[dict[str, Any]], config_name: str) -> dict[str, Any]:
    """Aggregate per-query rows into the report table's one-row-per-mode contract."""
    if not rows:
        raise ValueError("Cannot summarise an empty RAG evaluation")
    count = len(rows)
    return {
        "config": config_name,
        "query_count": count,
        "precision_at_1": sum(row["precision_at_1"] for row in rows) / count,
        "precision_at_3": sum(row["precision_at_3"] for row in rows) / count,
        "precision_at_5": sum(row["precision_at_5"] for row in rows) / count,
        "hit_at_5": sum(row["hit_at_5"] for row in rows) / count,
        "content_hit_at_5": sum(row["content_hit_at_5"] for row in rows) / count,
        "mrr": sum(row["mrr"] for row in rows) / count,
        "citation_match_rate": sum(row["citation_match_at_5"] for row in rows) / count,
        "wrong_year_rate": sum(row["wrong_year_hits_at_5"] for row in rows) / (count * REPORT_K),
        "wrong_year_query_rate": sum(row["wrong_year_top1"] for row in rows) / count,
        "latency_p50_ms": statistics.median(row["latency_ms"] for row in rows),
        "latency_p95_ms": _percentile([row["latency_ms"] for row in rows], 0.95),
    }


def _markdown_table(summaries: Sequence[dict[str, Any]]) -> str:
    """Render the comparison table consumed by the shared report writer."""
    lines = [
        "| configuration | n | P@1 | P@3 | P@5 | hit@5 | content hit@5 | MRR | citation match | wrong-year | P50 ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            f"| {summary['config']} | {summary['query_count']} | "
            f"{summary['precision_at_1']:.3f} | {summary['precision_at_3']:.3f} | "
            f"{summary['precision_at_5']:.3f} | {summary['hit_at_5']:.3f} | "
            f"{summary['content_hit_at_5']:.3f} | {summary['mrr']:.3f} | "
            f"{summary['citation_match_rate']:.3f} | {summary['wrong_year_rate']:.3f} | "
            f"{summary['latency_p50_ms']:.1f} | {summary['latency_p95_ms']:.1f} |"
        )
    return "\n".join(lines)


def _report_notes(queries: Sequence[RagEvalQuery]) -> str:
    """Explain the metric boundaries and the control run in the report."""
    categories = ", ".join(sorted({query.category for query in queries}))
    return "\n".join(
        [
            f"Query set: {len(queries)} manually verified questions from the 2023-2025 FIA Sporting Regulations.",
            f"Categories: {categories}.",
            "",
            "P@k is conventional precision over the top k returned chunks. `hit@5` is the older binary benchmark measure and is retained for comparison with N30B.",
            "A strict hit requires the expected season, article, and at least one verified keyword. Content hit@5 requires the expected season and keyword but ignores the article metadata field.",
            "Citation match is retrieval-level article recall at five chunks. It does not claim that an LLM cited the article faithfully; that belongs to the grounding phase and must use the actual tool trace.",
            "Wrong-year rate is the share of top-five chunks from a season different from the query. The scoped row is the production path. The unscoped row is a control for the season filter.",
            "The evaluator calls the production `RagRetriever` directly, loads one embedding model, and does not spend LLM calls. Alternative embeddings and chunking remain in the historical N30B notebook until a separate A/B issue adopts them.",
        ]
    )


def build_rag_report(query_path: Path | None = None) -> dict[str, Any]:
    """Run the scoped production benchmark and write the shared RAG report."""
    path = Path(query_path) if query_path is not None else default_query_path()
    queries = load_queries(path)
    retriever = RagRetriever(
        qdrant_path=CFG.qdrant_path,
        collection_name=CFG.collection_name,
        embedding_model=CFG.embedding_model,
        top_k=TOP_K,
    )
    configs = (
        RagEvalConfig("BGE-M3 production, season scoped", True),
        RagEvalConfig("BGE-M3 production, unscoped control", False),
    )
    query_results = [
        row
        for config in configs
        for row in evaluate_retriever(retriever, queries, config=config, top_k=TOP_K)
    ]
    summaries = [
        summarise_rows(
            [row for row in query_results if row["config"] == config.name],
            config.name,
        )
        for config in configs
    ]
    header = build_header(
        dataset=f"RAG {path.name}, {len(queries)} FIA regulation queries",
        artifacts={"query_set": path},
    )
    table = _markdown_table(summaries)
    body = f"{table}\n\n## Metric contract\n\n{_report_notes(queries)}"
    md_path, json_path = write_report(
        REPORT_NAME,
        header,
        body,
        {
            "query_set": path.name,
            "query_count": len(queries),
            "configs": [asdict(config) for config in configs],
            "summaries": summaries,
            "query_results": query_results,
        },
    )
    return {
        "md_path": str(md_path),
        "json_path": str(json_path),
        "query_count": len(queries),
        "summaries": summaries,
        "query_results": query_results,
    }
