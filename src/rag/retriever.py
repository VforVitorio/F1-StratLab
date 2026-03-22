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
