"""Run the eval-gated RAG chunking A/B for issue #323.

The production collection is the baseline. The candidate collection is built
in a temporary Qdrant directory and is never written into ``data/rag``. The
candidate is adopted only when it improves the retrieval contract on the same
35-query set, including five 2026-specific questions.
"""

from __future__ import annotations

import gc
import tempfile
from pathlib import Path
from typing import Any

from scripts.build_rag_index import (
    embed_chunks,
    ensure_collection,
    iter_chunks,
    load_pdf_documents,
    upsert_chunks,
)
from src.f1_strat_manager.data_cache import _find_repo_root
from src.rag.retriever import CFG, RegulationChunk
from src.strategy.eval.rag import (
    RagEvalConfig,
    _markdown_table,
    evaluate_retriever,
    load_queries,
    summarise_rows,
)
from src.strategy.eval.report import build_header, write_report

REPORT_NAME = "rag_2026"
CANDIDATE_COLLECTION = "fia_regulations_article_aware_1024_v1"
CANDIDATE_CHUNK_SIZE = 1024
CANDIDATE_CHUNK_OVERLAP = 128


class _SharedQdrantRetriever:
    """Use one encoder for both sides of the A/B while matching production mapping."""

    def __init__(self, client: Any, collection_name: str, encoder: Any) -> None:
        self._client = client
        self._collection_name = collection_name
        self._encoder = encoder

    def query(
        self,
        question: str,
        top_k: int | None = None,
        year: int | None = None,
    ) -> list[RegulationChunk]:
        """Run the same filtered Qdrant lookup used by ``RagRetriever``."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = (
            Filter(must=[FieldCondition(key="year", match=MatchValue(value=int(year)))])
            if year is not None
            else None
        )
        vector = self._encoder.encode(question, normalize_embeddings=True).tolist()
        response = self._client.query_points(
            collection_name=self._collection_name,
            query=vector,
            limit=top_k or 10,
            with_payload=True,
            query_filter=query_filter,
        )
        if year is not None and not response.points:
            response = self._client.query_points(
                collection_name=self._collection_name,
                query=vector,
                limit=top_k or 10,
                with_payload=True,
            )
        return [
            RegulationChunk(
                text=point.payload.get("text", ""),
                article=" ".join(point.payload.get("article", "").split()),
                doc_type=point.payload.get("doc_type", "unknown"),
                year=point.payload.get("year", 0),
                score=round(float(point.score), 4),
                section_title=point.payload.get("section_title", ""),
            )
            for point in response.points
        ]


def _build_candidate(documents: list[Any], qdrant_path: Path) -> tuple[Any, Any, int]:
    """Build the candidate collection in a temporary local Qdrant store."""
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

    chunks = [
        chunk
        for document in documents
        for chunk in iter_chunks(
            document,
            chunk_size=CANDIDATE_CHUNK_SIZE,
            chunk_overlap=CANDIDATE_CHUNK_OVERLAP,
        )
    ]
    client = QdrantClient(path=str(qdrant_path))
    ensure_collection(client, CANDIDATE_COLLECTION, CFG.embedding_dim)
    encoder = SentenceTransformer(CFG.embedding_model)
    embeddings = embed_chunks(chunks, encoder)
    upsert_chunks(client, CANDIDATE_COLLECTION, chunks, embeddings)
    return client, encoder, len(chunks)


def _stored_chunk_keys(client: Any, collection_name: str) -> set[tuple[int, str]]:
    """Return the source identity carried by every stored production chunk."""
    keys: set[tuple[int, str]] = set()
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            limit=1000,
            offset=offset,
            with_payload=["year", "chunk_hash"],
            with_vectors=False,
        )
        keys.update(
            (int(point.payload["year"]), str(point.payload["chunk_hash"]))
            for point in points
            if point.payload and point.payload.get("year") and point.payload.get("chunk_hash")
        )
        if offset is None:
            return keys


def _assert_baseline_matches_source(client: Any, documents: list[Any]) -> None:
    """Reject an A/B run when production is not the expected local corpus."""
    expected = {
        (chunk.year, chunk.chunk_hash) for document in documents for chunk in iter_chunks(document)
    }
    actual = _stored_chunk_keys(client, CFG.collection_name)
    if actual != expected:
        missing = len(expected - actual)
        extra = len(actual - expected)
        raise RuntimeError(
            "Production collection does not match the local 512/64 corpus "
            f"(missing={missing}, extra={extra}); rebuild it before running the A/B."
        )


def _decision(baseline: dict[str, Any], candidate: dict[str, Any]) -> str:
    """Adopt only a non-regressing candidate with at least one quality gain."""
    quality_fields = ("precision_at_5", "mrr", "citation_match_rate", "wrong_year_rate")
    no_regression = all(
        candidate[field] >= baseline[field]
        if field != "wrong_year_rate"
        else candidate[field] <= baseline[field]
        for field in quality_fields
    )
    strict_gain = any(candidate[field] > baseline[field] for field in quality_fields[:3])
    return "ADOPT_CANDIDATE" if no_regression and strict_gain else "KEEP_BASELINE"


def main() -> int:
    """Build and report the chunking A/B without mutating the production index."""
    repo = _find_repo_root() or Path.cwd()
    docs_dir = repo / "data" / "rag" / "documents"
    query_paths = [
        repo / "data" / "rag_eval" / "queries_v2.json",
        repo / "data" / "rag_eval" / "queries_2026.json",
    ]
    queries = load_queries(query_paths)
    documents = load_pdf_documents(docs_dir)

    with tempfile.TemporaryDirectory(prefix="f1-rag-323-") as temp_dir:
        candidate_path = Path(temp_dir) / "qdrant_local"
        candidate_client, encoder, candidate_chunks = _build_candidate(documents, candidate_path)
        from qdrant_client import QdrantClient

        production_client = QdrantClient(path=str(CFG.qdrant_path))
        try:
            _assert_baseline_matches_source(production_client, documents)
            baseline_retriever = _SharedQdrantRetriever(
                production_client, CFG.collection_name, encoder
            )
            candidate_retriever = _SharedQdrantRetriever(
                candidate_client, CANDIDATE_COLLECTION, encoder
            )
            baseline_config = RagEvalConfig("Production article-aware 512/64", True)
            candidate_config = RagEvalConfig("Candidate article-aware 1024/128", True)
            baseline_rows = evaluate_retriever(
                baseline_retriever, queries, config=baseline_config, top_k=10
            )
            candidate_rows = evaluate_retriever(
                candidate_retriever, queries, config=candidate_config, top_k=10
            )
            baseline = summarise_rows(baseline_rows, baseline_config.name)
            candidate = summarise_rows(candidate_rows, candidate_config.name)
        finally:
            production_client.close()
            candidate_client.close()
            del encoder
            gc.collect()

    decision = _decision(baseline, candidate)
    header = build_header(
        dataset="RAG queries_v2 + 2026 delta, 35 FIA regulation queries",
        era_tag="FIA sporting corpus 2023-2026",
        artifacts={name: path for name, path in zip(("queries_v2", "queries_2026"), query_paths)},
    )
    body = (
        f"{_markdown_table((baseline, candidate))}\n\n"
        "## Experiment contract\n\n"
        f"- Candidate chunks built: {candidate_chunks}\n"
        f"- Decision: **{decision}**\n"
        "- The production collection is the baseline. The candidate uses the same BGE-M3 model, PDF corpus, season filters, top-k, and query set; only the article-aware soft target changes from 512/64 to 1024/128.\n"
        "- A candidate is adopted only when P@5, MRR, and retrieval-level citation match do not regress, at least one quality metric improves, and wrong-year rate does not increase.\n"
        "- This experiment does not call an LLM and does not modify the production Qdrant collection.\n"
    )
    md_path, json_path = write_report(
        REPORT_NAME,
        header,
        body,
        {
            "query_count": len(queries),
            "decision": decision,
            "candidate_chunks": candidate_chunks,
            "baseline": baseline,
            "candidate": candidate,
            "baseline_rows": baseline_rows,
            "candidate_rows": candidate_rows,
        },
    )
    print(f"rag-2026 -> {md_path}; decision={decision}; candidate_chunks={candidate_chunks}")
    print(f"json -> {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
