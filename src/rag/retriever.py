"""
Run-time retrieval module for FIA regulation lookup.

Initialise ``RagRetriever`` once per process and call ``.query()`` on each
LLM tool invocation. The Qdrant collection must be populated first by
running ``scripts/build_rag_index.py``.

Public interface::

    from src.rag.retriever import RagRetriever, RegulationChunk, query_rag_tool
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from langchain_core.tools import tool


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------

@dataclass
class RegulationChunk:
    """A single regulation passage returned by a retrieval query.

    This is the atomic unit of information the RAG agent passes back to the
    orchestrator. Keeping article reference, document type and year alongside
    the raw text means downstream agents (e.g. N28 Pit Strategy) can filter
    by regulatory domain without having to re-parse the text themselves.

    Attributes:
        text:          The regulation passage itself — the verbatim paragraph
                       extracted from the FIA document after chunking.
        article:       The article or section identifier found inside the chunk
                       (e.g. ``"Article 48.3"``). Used by the LLM to cite the
                       source precisely and by callers to filter by article range.
                       Empty string when no reference could be extracted.
        doc_type:      Which FIA document the chunk comes from — distinguishes
                       sporting rules (race procedures, penalties) from technical
                       rules (equipment, pit stop mechanics). Callers can restrict
                       queries to a specific document type when the context is clear.
        year:          The regulation year the chunk belongs to. FIA rules change
                       annually, so a 2023 safety-car article may differ from 2025;
                       this field lets the agent pick the version that matches the
                       current race season.
        score:         Cosine similarity between the query embedding and this chunk,
                       in [0, 1]. Higher means more relevant. Exposed so callers can
                       apply a minimum threshold or rerank results if needed.
        section_title: The section heading from the source document when available.
                       Provides additional context about where in the regulations
                       the chunk sits without needing to read the full article.
    """

    text:          str
    article:       str
    doc_type:      str
    year:          int
    score:         float
    section_title: str = field(default="")

    def __repr__(self) -> str:
        preview = self.text[:80].replace("\n", " ")
        return (
            f"RegulationChunk("
            f"article={self.article!r}, "
            f"score={self.score:.3f}, "
            f"text={preview!r}...)"
        )
# ---------------------------------------------------------------------------
# Retriever
# ---------------------------------------------------------------------------

class RagRetriever:
    """Holds an initialised Qdrant client and sentence encoder, and answers
    natural-language queries against the FIA regulation collection.

    Both the Qdrant client and the embedding model are loaded eagerly on
    construction so that the first call to ``query()`` has no cold-start
    penalty. Instantiate once at module level (or via ``get_retriever()``)
    and reuse across all agent calls — re-creating the encoder on every query
    would add ~2–3 s of overhead per call.
    """

    def __init__(
        self,
        qdrant_path:     Path | str,
        collection_name: str,
        embedding_model: str,
        top_k:           int = 5,
    ) -> None:
        """Initialise the retriever and verify the Qdrant collection exists.

        Args:
            qdrant_path:     Path to the on-disk Qdrant storage directory created
                             by ``build_rag_index.py``. Accepts both ``Path`` and
                             plain string so callers can pass either without casting.
            collection_name: Name of the Qdrant collection to query. Must match
                             the name used during indexing; a mismatch raises a
                             ``RuntimeError`` with an actionable message rather than
                             a cryptic Qdrant error.
            embedding_model: Sentence-transformers model identifier used to encode
                             queries. Must be the same model used during indexing —
                             mixing models produces meaningless similarity scores.
            top_k:           Default number of chunks to return per query. Can be
                             overridden per call in ``query()`` when a broader or
                             narrower context window is needed.
        """
        self._qdrant_path     = Path(qdrant_path)
        self._collection_name = collection_name
        self._embedding_model = embedding_model
        self._top_k           = top_k

        self._client  = QdrantClient(path=str(self._qdrant_path))
        self._encoder = SentenceTransformer(embedding_model)

        existing = {c.name for c in self._client.get_collections().collections}
        if collection_name not in existing:
            raise RuntimeError(
                f"Qdrant collection '{collection_name}' not found in {qdrant_path}. "
                "Run `python scripts/build_rag_index.py` to build the index first."
            )

    def _encode(self, text: str) -> list[float]:
        """Encode a single text string into a normalised embedding vector.

        Normalisation (L2) is applied so that dot product and cosine similarity
        are equivalent in Qdrant, which is the convention used during indexing.
        Returns a plain Python list because that is what ``QdrantClient.search``
        expects — passing a numpy array causes a silent type error in some versions.

        Args:
            text: The string to embed. Typically a user query, but can also be
                  used to embed individual chunks during a reranking pass.
        """
        return self._encoder.encode(text, normalize_embeddings=True).tolist()
