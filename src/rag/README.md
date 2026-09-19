# src/rag: FIA Regulation Retrieval

**Status: Active**, imported by N30 and N31.

Provides runtime retrieval-augmented generation (RAG) over FIA regulation PDFs.
The Qdrant index and its `data/rag/index_manifest.json` metadata must exist before
any query. Older indexes without a manifest remain readable with a warning.

---

## Public API

| Symbol | Type | Description |
|---|---|---|
| `RagConfig` | dataclass | Centralised config: collection name, embedding model, dimension, top-k, derived paths |
| `CFG` | `RagConfig` | Module-level singleton config; edit this to change defaults |
| `RegulationChunk` | dataclass | Single retrieved passage with `text`, `article`, `doc_type`, `year`, `score`, `section_title` |
| `RagRetriever` | class | Holds Qdrant client + sentence encoder; call `.query()` per request |
| `get_retriever()` | function | Returns the process-level `RagRetriever` singleton (lazy init, loads model once) |
| `query_rag_tool` | `@tool` | LangGraph-compatible tool wrapper; returns formatted string for the LLM. Takes the season from the RunnableConfig key `configurable.season`, never as a tool argument, so the model cannot choose which rulebook it reads |

### `RagRetriever` methods

- `__init__(qdrant_path, collection_name, embedding_model, top_k, embedding_dim)`, validates the manifest before loading the encoder; raises `RuntimeError` for a present but incompatible manifest
- `query(question, top_k=None, year=None, doc_type=None) -> list[RegulationChunk]`, cosine similarity search, ordered by descending score. `year` restricts the search to one season's rulebook; a season the index does not hold falls back to an unscoped search with one warning rather than returning nothing
- `health_check() -> dict`, returns collection, vector count, vector dimension, indexed years, manifest status/hash, and paths for diagnostics

---

## Usage

```python
from src.rag.retriever import query_rag_tool, get_retriever

# As a LangGraph tool (N31 Orchestrator)
result_str = query_rag_tool.invoke({"question": "pit lane speed limit"})

# Direct retrieval (N30 RAG agent, diagnostics)
retriever = get_retriever()
chunks = retriever.query("safety car restart procedure", top_k=10)

# Scoped to one season. The same article is renumbered and reworded between
# rulebooks, so an unscoped query mixes them: 43 of 75 top-5 hits on the tracked
# gold set come from a season other than the one asked about.
chunks = retriever.query("safety car restart procedure", year=2025)
for c in chunks:
    print(c.article, c.score, c.text[:80])

# Startup health check. A valid manifest reports the corpus years and hash.
print(retriever.health_check())
```

---

## Key dependencies

- `qdrant-client`, local on-disk vector store at `data/rag/qdrant_local/`
- `sentence-transformers`, embedding model `BAAI/bge-m3` (1024-dim, ~8 GB VRAM)
- `langchain-core`: `@tool` decorator for LangGraph integration

---

## Pre-requisites

The Qdrant collection must exist before calling `get_retriever()`:

```bash
python scripts/build_rag_index.py
```

To create or refresh only the metadata, without loading BGE-M3 or changing
Qdrant points:

```bash
uv run python scripts/build_rag_index.py --manifest-only
```

The manifest records the source PDF hashes, collection, embedding model and
dimension, distance, chunker identity, chunking parameters, indexed years, point
count, and build time. When the existing payload hashes identify the historical
sliding-window index, the manifest records that fact instead of pretending it
was built with the current article-aware code. A missing manifest is a
compatibility warning. A present mismatch stops startup so a stale or
wrong-model index cannot be used silently.

FIA PDFs are downloaded by `scripts/download_fia_pdfs.py` into `data/rag/documents/`.
The maintained Sporting Regulations corpus currently covers 2023-2026. The 2026
PDF uses `B5.13.1`-style article identifiers; the builder preserves those
identifiers instead of treating them as page metadata. The source is the
[official FIA regulations page](https://www.fia.com/regulations/category/110).

---

## Developed in

[`notebooks/agents/N30_rag_agent.ipynb`](../../notebooks/agents/N30_rag_agent.ipynb)
