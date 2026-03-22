"""
One-shot ingestion script: PDF → chunks → embeddings → Qdrant.

Run this script once to build (or incrementally update) the local Qdrant index
from FIA regulation PDFs. Subsequent runs are idempotent — each chunk is hashed
and skipped if it already exists in the collection, so adding a new PDF only
indexes the new content without rebuilding from scratch.

Usage:
    python scripts/build_rag_index.py
    python scripts/build_rag_index.py --docs-dir data/rag/documents
    python scripts/build_rag_index.py --force-rebuild

PDF naming convention (required):
    <doc_type>_<year>.pdf
    e.g.  sporting_regs_2025.pdf   technical_regs_2024.pdf

Supported doc_types : sporting_regs, technical_regs
Supported years     : 2023, 2024, 2025
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Paths + config
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

DOCS_DIR        = _REPO_ROOT / "data" / "rag" / "documents"
QDRANT_PATH     = _REPO_ROOT / "data" / "rag" / "qdrant_local"
COLLECTION_NAME = "fia_regulations"
# BGE-M3: MTEB ~67 vs ~57 for all-MiniLM-L6-v2, 1024-dim, fits in 8 GB VRAM (~2 GB usage).
# Produces significantly better retrieval on technical/legal text like FIA regulations.
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM   = 1024

# Chunk size in characters. 512 chars ≈ 80–120 words, which fits comfortably
# inside the encoder's 256-token limit while keeping each chunk semantically
# coherent (typically one or two regulation sub-articles).
CHUNK_SIZE       = 512
CHUNK_OVERLAP    = 64
EMBED_BATCH_SIZE = 64   # larger batches are faster but use more RAM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PDFDocument:
    """Represents a single FIA PDF file before chunking.

    Carries the raw extracted text alongside the metadata derived from the
    filename so that every chunk created from this document inherits the
    correct ``doc_type`` and ``year`` without re-parsing the filename.

    Attributes:
        path:     Absolute path to the source PDF, kept for error messages and
                  logging so failures can be traced back to a specific file.
        doc_type: Regulatory domain of the document — either ``"sporting_regs"``
                  or ``"technical_regs"``. Derived from the filename prefix and
                  stored on every chunk so downstream agents can filter by domain.
        year:     Season the document applies to (2023–2025). F1 regulations
                  change annually, so the year determines which rule version is
                  authoritative for a given race.
        text:     Full plain-text content extracted from the PDF. May contain
                  artefacts from PDF rendering (hyphenation, ligatures) that are
                  cleaned during chunking.
    """

    path:     Path
    doc_type: str
    year:     int
    text:     str = field(default="", repr=False)


@dataclass
class TextChunk:
    """A single chunk of regulation text ready for embedding and indexing.

    Produced by splitting a ``PDFDocument`` into overlapping windows. Each chunk
    is self-contained enough to be returned as a retrieval result without the
    surrounding context, which is why the source metadata (doc_type, year,
    article reference) is duplicated here rather than kept only on the parent
    document.

    Attributes:
        text:          The regulation passage itself, trimmed and normalised.
                       This is the string that gets embedded and stored as the
                       Qdrant payload — what the RAG agent returns to the LLM.
        doc_type:      Inherited from the parent ``PDFDocument``. Lets callers
                       filter retrieval results by regulatory domain without
                       parsing the text.
        year:          Inherited from the parent ``PDFDocument``. Determines
                       which season's rules apply — critical when regulations
                       changed between years (e.g. cost-cap rules 2023 vs 2025).
        article:       Article or section reference extracted by regex from the
                       chunk text (e.g. ``"Article 48.3"``). Empty string when
                       no reference is found. Stored in the Qdrant payload so
                       the LLM can cite the exact article without re-parsing.
        section_title: Nearest section heading found above this chunk in the
                       document, when available. Provides coarse context about
                       which part of the regulations the chunk belongs to.
        chunk_hash:    SHA-256 of the normalised text, used for idempotent
                       upserts — chunks already present in Qdrant are skipped
                       so re-running the script only indexes new content.
    """

    text:          str
    doc_type:      str
    year:          int
    article:       str = ""
    section_title: str = ""
    chunk_hash:    str = ""


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"^(?P<doc_type>sporting_regs|technical_regs)_(?P<year>20\d{2})\.pdf$"
)


def parse_pdf_filename(path: Path) -> tuple[str, int] | None:
    """Extract doc_type and year from a PDF filename following the naming convention.

    Returns ``None`` for files that do not match the expected pattern so the
    caller can skip them with a warning rather than raising an exception — this
    lets the script process a directory that may contain unrelated files without
    aborting the whole run.

    Args:
        path: Path to the PDF file. Only the filename (not the full path) is
              matched against the pattern, so the file does not need to exist.
    """
    match = _FILENAME_RE.match(path.name)
    if match is None:
        return None
    return match.group("doc_type"), int(match.group("year"))


def extract_text_from_pdf(path: Path) -> str:
    """Extract all plain text from a PDF file using PyMuPDF.

    Concatenates text from every page separated by a newline so that page
    boundaries do not create artificial word splits during chunking. PyMuPDF
    preserves the reading order of multi-column layouts better than most
    alternatives, which matters for regulation documents that use numbered
    sub-articles in narrow columns.

    Args:
        path: Path to the PDF file to read. Raises ``FileNotFoundError`` if
              the file does not exist — callers should validate the path first.
    """
    doc   = fitz.open(str(path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


def load_pdf_documents(docs_dir: Path) -> list[PDFDocument]:
    """Discover and load all FIA PDFs in a directory into ``PDFDocument`` objects.

    Skips files whose names do not match the naming convention and logs a
    warning for each skipped file so the operator knows what was ignored.
    Also logs an error (without raising) if a PDF cannot be opened, allowing
    the rest of the batch to continue.

    Args:
        docs_dir: Directory to scan for PDF files. Non-PDF files are silently
                  ignored; only the naming convention check produces a warning.
    """
    documents: list[PDFDocument] = []

    for pdf_path in sorted(docs_dir.glob("*.pdf")):
        parsed = parse_pdf_filename(pdf_path)
        if parsed is None:
            log.warning("Skipping %s — does not match naming convention", pdf_path.name)
            continue

        doc_type, year = parsed
        try:
            text = extract_text_from_pdf(pdf_path)
            documents.append(PDFDocument(path=pdf_path, doc_type=doc_type, year=year, text=text))
            log.info("Loaded %s  (%d chars)", pdf_path.name, len(text))
        except Exception as exc:
            log.error("Failed to read %s: %s", pdf_path.name, exc)

    return documents


# ---------------------------------------------------------------------------
# Text cleaning + chunking
# ---------------------------------------------------------------------------

_ARTICLE_RE      = re.compile(r"Article\s+\d+[\.\d]*", re.IGNORECASE)
_SECTION_HEAD_RE = re.compile(r"^\s{0,4}(\d+[\.\d]*\s+[A-Z][A-Z\s]{4,})\s*$", re.MULTILINE)


def clean_text(text: str) -> str:
    """Normalise raw PDF text for embedding.

    Collapses runs of whitespace and removes hyphenation artefacts introduced
    by PDF line-wrapping (``word-\\nnext`` → ``wordnext``). Does not strip
    newlines entirely because the section-heading regex relies on line structure.

    Args:
        text: Raw text as returned by ``extract_text_from_pdf``.
    """
    text = re.sub(r"-\n", "", text)          # dehyphenate wrapped words
    text = re.sub(r"[ \t]{2,}", " ", text)   # collapse horizontal whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)   # collapse blank lines
    return text.strip()


def extract_article_reference(text: str) -> str:
    """Find the first FIA article reference in a chunk of text.

    Searches for patterns like ``Article 48``, ``Article 48.3``, or
    ``ARTICLE 28.6`` (case-insensitive). Returns only the first match because
    a 512-character chunk rarely spans more than one article, and having a
    single authoritative reference is more useful for citation than a list.
    Returns an empty string when no reference is found so the field is always
    a valid string and never ``None``.

    Args:
        text: The regulation chunk to search. Typically 512 characters but can
              be shorter for the last chunk of a document section.
    """
    match = _ARTICLE_RE.search(text)
    return match.group(0) if match else ""


def extract_section_title(text: str) -> str:
    """Find the nearest section heading inside a chunk of text.

    Matches lines that look like numbered section headings in FIA documents:
    a number followed by all-caps words, e.g. ``"48 SAFETY CAR PROCEDURE"``.
    Returns the first match found, or an empty string when none is present.
    This is a best-effort heuristic — not every chunk will have a heading.

    Args:
        text: The regulation chunk to search.
    """
    match = _SECTION_HEAD_RE.search(text)
    return match.group(1).strip() if match else ""


def compute_hash(text: str) -> str:
    """Compute a stable SHA-256 hash of a text string for idempotent indexing.

    The hash is computed on the UTF-8 encoded text before any further
    processing so that two identical passages from different PDFs produce the
    same hash and are deduplicated in Qdrant. This prevents the collection
    from growing with duplicate content if the same article appears in both
    the sporting and technical regulations.

    Args:
        text: Normalised chunk text. Must be the same string that will be
              stored in the payload, otherwise the hash check will miss
              already-indexed chunks.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def iter_chunks(
    document: PDFDocument,
    chunk_size:    int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> Iterator[TextChunk]:
    """Yield overlapping text chunks from a ``PDFDocument``.

    Uses a sliding window over the cleaned document text. The overlap ensures
    that regulation sentences which fall at a chunk boundary appear in full in
    at least one chunk, preventing the retriever from returning a truncated
    article mid-sentence. Each chunk carries its own article reference and
    section title extracted by regex so retrieval results are self-contained.

    Args:
        document:      The source document to chunk. Its ``doc_type`` and
                       ``year`` are inherited by every produced chunk.
        chunk_size:    Window size in characters. Smaller windows give more
                       precise retrieval but require more Qdrant storage and
                       more embedding calls; 512 chars is a good default.
        chunk_overlap: Number of characters to repeat at the start of each
                       new window. Must be smaller than ``chunk_size``.
    """
    text   = clean_text(document.text)
    start  = 0
    stride = chunk_size - chunk_overlap

    while start < len(text):
        end        = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            yield TextChunk(
                text=chunk_text,
                doc_type=document.doc_type,
                year=document.year,
                article=extract_article_reference(chunk_text),
                section_title=extract_section_title(chunk_text),
                chunk_hash=compute_hash(chunk_text),
            )

        start += stride


# ---------------------------------------------------------------------------
# Qdrant management
# ---------------------------------------------------------------------------

def ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    """Create the Qdrant collection if it does not already exist.

    Uses cosine distance to match the L2-normalised embeddings produced by
    ``all-MiniLM-L6-v2``. Does nothing if the collection already exists, making
    this function safe to call on every script run without risk of wiping the
    existing index.

    Args:
        client: An initialised ``QdrantClient`` pointing to the local storage.
        name:   Name of the collection to create. Must match ``COLLECTION_NAME``
                used in ``retriever.py`` or queries will hit the wrong collection.
        dim:    Embedding dimension. Must match the output size of the model
                used during indexing — mismatches cause silent wrong results.
    """
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        log.info("Created collection '%s'  (dim=%d, distance=COSINE)", name, dim)
    else:
        log.info("Collection '%s' already exists — skipping creation", name)


def get_existing_hashes(client: QdrantClient, name: str) -> set[str]:
    """Retrieve all chunk hashes currently stored in a Qdrant collection.

    Used to determine which chunks are new before embedding — skipping already-
    indexed chunks avoids redundant embedding calls and prevents duplicates.
    Scrolls through the full collection in pages of 1000 to handle large indexes
    without loading everything into memory at once.

    Args:
        client: An initialised ``QdrantClient`` pointing to the local storage.
        name:   Collection name to scroll. Must exist before calling this function.
    """
    hashes: set[str] = set()
    offset = None

    while True:
        results, next_offset = client.scroll(
            collection_name=name,
            scroll_filter=None,
            limit=1000,
            offset=offset,
            with_payload=["chunk_hash"],
            with_vectors=False,
        )
        for point in results:
            h = point.payload.get("chunk_hash")
            if h:
                hashes.add(h)
        if next_offset is None:
            break
        offset = next_offset

    return hashes


# ---------------------------------------------------------------------------
# Embedding + upsert
# ---------------------------------------------------------------------------

def embed_chunks(
    chunks:  list[TextChunk],
    encoder: SentenceTransformer,
) -> np.ndarray:
    """Embed a list of chunks in batches and return the embedding matrix.

    Processes chunks in batches of ``EMBED_BATCH_SIZE`` to keep GPU/CPU memory
    usage bounded. Normalisation is applied so cosine similarity equals dot
    product, consistent with how the retriever queries the collection.

    Args:
        chunks:  The chunks to embed. Their ``text`` field is used as input;
                 all other fields are preserved separately as Qdrant payload.
        encoder: A loaded ``SentenceTransformer`` instance. Passed explicitly
                 rather than re-loaded here so the caller controls when the
                 model is loaded (typically once at script startup).
    """
    texts = [c.text for c in chunks]
    return encoder.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=len(texts) > EMBED_BATCH_SIZE,
    )


def upsert_chunks(
    client:     QdrantClient,
    name:       str,
    chunks:     list[TextChunk],
    embeddings: np.ndarray,
    id_offset:  int = 0,
) -> int:
    """Upsert a list of chunks and their embeddings into a Qdrant collection.

    Each chunk becomes one Qdrant point whose payload mirrors the ``TextChunk``
    fields exactly, making the stored payload compatible with the ``RegulationChunk``
    dataclass in ``retriever.py`` without any transformation at query time.
    Uses upsert (not insert) so re-running the script after a partial failure
    overwrites incomplete points rather than creating duplicates.

    Args:
        client:     An initialised ``QdrantClient`` pointing to the local storage.
        name:       Collection name to upsert into.
        chunks:     List of ``TextChunk`` objects to store. Order must match
                    ``embeddings`` row order.
        embeddings: Float32 matrix of shape ``(len(chunks), EMBEDDING_DIM)``.
        id_offset:  Integer offset added to the chunk's list index to produce
                    a unique point ID. Pass the current collection size to avoid
                    ID collisions when adding new documents incrementally.

    Returns:
        Number of points successfully upserted.
    """
    points = [
        PointStruct(
            id=id_offset + i,
            vector=embeddings[i].tolist(),
            payload={
                "text":          chunk.text,
                "doc_type":      chunk.doc_type,
                "year":          chunk.year,
                "article":       chunk.article,
                "section_title": chunk.section_title,
                "chunk_hash":    chunk.chunk_hash,
            },
        )
        for i, chunk in enumerate(chunks)
    ]
    client.upsert(collection_name=name, points=points)
    return len(points)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def build_index(
    docs_dir:      Path = DOCS_DIR,
    qdrant_path:   Path = QDRANT_PATH,
    force_rebuild: bool = False,
) -> None:
    """Orchestrate the full PDF → Qdrant pipeline.

    Loads all PDFs, chunks them, skips already-indexed chunks (unless
    ``force_rebuild`` is set), embeds the new ones, and upserts them into
    Qdrant. Prints a summary at the end with the total number of indexed,
    skipped, and failed chunks.

    Args:
        docs_dir:      Directory containing the FIA PDFs. Must exist and contain
                       at least one file matching the naming convention.
        qdrant_path:   On-disk Qdrant storage directory. Created automatically
                       if it does not exist.
        force_rebuild: When ``True``, deletes and recreates the collection before
                       indexing so all chunks are re-embedded from scratch. Use
                       this when the embedding model changes or the chunking
                       parameters are modified.
    """
    if not docs_dir.exists() or not any(docs_dir.glob("*.pdf")):
        log.error("No PDFs found in %s — add regulation PDFs and retry", docs_dir)
        sys.exit(1)

    qdrant_path.mkdir(parents=True, exist_ok=True)
    client  = QdrantClient(path=str(qdrant_path))
    encoder = SentenceTransformer(EMBEDDING_MODEL)

    if force_rebuild:
        existing = {c.name for c in client.get_collections().collections}
        if COLLECTION_NAME in existing:
            client.delete_collection(COLLECTION_NAME)
            log.info("Deleted existing collection '%s' (--force-rebuild)", COLLECTION_NAME)

    ensure_collection(client, COLLECTION_NAME, EMBEDDING_DIM)
    existing_hashes = get_existing_hashes(client, COLLECTION_NAME)
    log.info("Existing indexed chunks: %d", len(existing_hashes))

    documents = load_pdf_documents(docs_dir)
    if not documents:
        log.error("No valid PDFs loaded — check naming convention")
        sys.exit(1)

    all_chunks: list[TextChunk] = []
    for doc in documents:
        for chunk in iter_chunks(doc):
            if chunk.chunk_hash not in existing_hashes:
                all_chunks.append(chunk)

    skipped = sum(
        1 for doc in documents
        for chunk in iter_chunks(doc)
        if chunk.chunk_hash in existing_hashes
    )
    log.info("New chunks to index: %d  |  skipped (already indexed): %d", len(all_chunks), skipped)

    if not all_chunks:
        log.info("Nothing to do — index is up to date")
        return

    log.info("Embedding %d chunks with '%s'...", len(all_chunks), EMBEDDING_MODEL)
    embeddings = embed_chunks(all_chunks, encoder)

    id_offset = client.get_collection(COLLECTION_NAME).points_count or 0
    n_upserted = upsert_chunks(client, COLLECTION_NAME, all_chunks, embeddings, id_offset)

    total = (client.get_collection(COLLECTION_NAME).points_count or 0)
    log.info("Done. Upserted: %d  |  Total in collection: %d", n_upserted, total)


def main() -> None:
    """Parse CLI arguments and run the ingestion pipeline."""
    parser = argparse.ArgumentParser(
        description="Build the FIA regulation Qdrant index from PDF documents."
    )
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=DOCS_DIR,
        help=f"Directory containing FIA PDFs (default: {DOCS_DIR})",
    )
    parser.add_argument(
        "--force-rebuild",
        action="store_true",
        help="Delete and recreate the collection before indexing",
    )
    args = parser.parse_args()

    build_index(
        docs_dir=args.docs_dir,
        force_rebuild=args.force_rebuild,
    )


if __name__ == "__main__":
    main()
