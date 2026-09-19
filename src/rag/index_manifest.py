"""Versioned metadata for the on-disk FIA regulation index."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MANIFEST_FILENAME = "index_manifest.json"
MANIFEST_SCHEMA_VERSION = 1
CHUNKER_VERSION = "article_clause_packing_v1"


class IndexManifestError(ValueError):
    """Raised when a manifest is malformed or incompatible with its consumer."""


@dataclass(frozen=True)
class ManifestDocument:
    """One source PDF recorded in an index manifest."""

    filename: str
    doc_type: str
    year: int
    sha256: str


@dataclass(frozen=True)
class IndexManifest:
    """Portable description of the corpus and parameters behind one index."""

    schema_version: int
    collection_name: str
    embedding_model: str
    embedding_dim: int
    distance: str
    chunker: str
    chunking_verified: bool
    chunk_size: int
    chunk_overlap: int
    documents: tuple[ManifestDocument, ...]
    indexed_years: tuple[int, ...]
    point_count: int
    built_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON representation used on disk."""
        payload = asdict(self)
        payload["documents"] = [asdict(document) for document in self.documents]
        payload["indexed_years"] = list(self.indexed_years)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "IndexManifest":
        """Parse a manifest and reject missing or structurally invalid fields."""
        required = (
            "schema_version",
            "collection_name",
            "embedding_model",
            "embedding_dim",
            "distance",
            "chunker",
            "chunking_verified",
            "chunk_size",
            "chunk_overlap",
            "documents",
            "indexed_years",
            "point_count",
            "built_at_utc",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise IndexManifestError(f"Manifest missing fields: {', '.join(missing)}")

        try:
            if not isinstance(payload["chunking_verified"], bool):
                raise TypeError("chunking_verified must be a boolean")
            documents = tuple(ManifestDocument(**document) for document in payload["documents"])
            indexed_years = tuple(int(year) for year in payload["indexed_years"])
            manifest = cls(
                schema_version=int(payload["schema_version"]),
                collection_name=str(payload["collection_name"]),
                embedding_model=str(payload["embedding_model"]),
                embedding_dim=int(payload["embedding_dim"]),
                distance=str(payload["distance"]),
                chunker=str(payload["chunker"]),
                chunking_verified=bool(payload["chunking_verified"]),
                chunk_size=int(payload["chunk_size"]),
                chunk_overlap=int(payload["chunk_overlap"]),
                documents=documents,
                indexed_years=indexed_years,
                point_count=int(payload["point_count"]),
                built_at_utc=str(payload["built_at_utc"]),
            )
        except (TypeError, ValueError) as exc:
            raise IndexManifestError(f"Manifest has invalid field types: {exc}") from exc

        if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
            raise IndexManifestError(
                f"Unsupported manifest schema {manifest.schema_version}; "
                f"expected {MANIFEST_SCHEMA_VERSION}"
            )
        if manifest.embedding_dim <= 0 or manifest.chunk_size <= 0:
            raise IndexManifestError("Manifest dimensions and chunk_size must be positive")
        if manifest.chunk_overlap < 0 or manifest.chunk_overlap >= manifest.chunk_size:
            raise IndexManifestError("Manifest chunk_overlap must be smaller than chunk_size")
        if manifest.point_count < 0:
            raise IndexManifestError("Manifest point_count cannot be negative")
        return manifest


def manifest_path(rag_dir: Path) -> Path:
    """Return the portable manifest location beside the Qdrant directory."""
    return Path(rag_dir) / MANIFEST_FILENAME


def sha256_file(path: Path) -> str:
    """Hash a file without loading a regulation PDF into memory."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    *,
    collection_name: str,
    embedding_model: str,
    embedding_dim: int,
    distance: str,
    chunk_size: int,
    chunk_overlap: int,
    documents: Iterable[ManifestDocument],
    indexed_years: Iterable[int],
    point_count: int,
    chunker: str = CHUNKER_VERSION,
    chunking_verified: bool = True,
    built_at_utc: str | None = None,
) -> IndexManifest:
    """Build a manifest with sorted documents and years for stable diffs."""
    return IndexManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        collection_name=collection_name,
        embedding_model=embedding_model,
        embedding_dim=embedding_dim,
        distance=distance,
        chunker=chunker,
        chunking_verified=chunking_verified,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        documents=tuple(sorted(documents, key=lambda item: item.filename)),
        indexed_years=tuple(sorted({int(year) for year in indexed_years})),
        point_count=int(point_count),
        built_at_utc=built_at_utc or datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def read_manifest(path: Path) -> IndexManifest:
    """Read and validate a manifest from disk."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexManifestError(f"Cannot read index manifest {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise IndexManifestError(f"Index manifest must be a JSON object: {path}")
    return IndexManifest.from_dict(payload)


def write_manifest(path: Path, manifest: IndexManifest) -> str:
    """Write a manifest only when its content changed and return its SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if path.exists():
        try:
            current = read_manifest(path)
        except IndexManifestError:
            current = None
        if current is not None:
            candidate = manifest.to_dict()
            candidate["built_at_utc"] = current.built_at_utc
            if current.to_dict() == candidate:
                return manifest_hash(path)
    path.write_text(payload, encoding="utf-8")
    return manifest_hash(path)


def manifest_hash(path: Path) -> str:
    """Return the full SHA-256 of the manifest file itself."""
    return sha256_file(Path(path))


def validate_manifest(
    manifest: IndexManifest,
    *,
    collection_name: str,
    embedding_model: str,
    embedding_dim: int | None = None,
    vector_dim: int | None = None,
) -> list[str]:
    """Return compatibility errors without changing the caller's state."""
    errors: list[str] = []
    if manifest.collection_name != collection_name:
        errors.append(f"collection_name={manifest.collection_name!r}, expected {collection_name!r}")
    if manifest.embedding_model != embedding_model:
        errors.append(f"embedding_model={manifest.embedding_model!r}, expected {embedding_model!r}")
    if embedding_dim is not None and manifest.embedding_dim != embedding_dim:
        errors.append(f"embedding_dim={manifest.embedding_dim}, expected {embedding_dim}")
    if vector_dim is not None and manifest.embedding_dim != vector_dim:
        errors.append(
            f"manifest embedding_dim={manifest.embedding_dim}, Qdrant vector_dim={vector_dim}"
        )
    return errors
