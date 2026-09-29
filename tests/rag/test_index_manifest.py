"""Hermetic tests for the RAG index manifest contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.rag.index_manifest import (
    IndexManifest,
    IndexManifestError,
    ManifestDocument,
    build_manifest,
    manifest_hash,
    read_manifest,
    sha256_file,
    validate_manifest,
    write_manifest,
)
from src.rag.retriever import RagRetriever


def _manifest() -> IndexManifest:
    return build_manifest(
        collection_name="fia_regulations",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        distance="Cosine",
        chunk_size=512,
        chunk_overlap=64,
        documents=(
            ManifestDocument("sporting_regs_2025.pdf", "sporting_regs", 2025, "b" * 64),
            ManifestDocument("sporting_regs_2023.pdf", "sporting_regs", 2023, "a" * 64),
        ),
        indexed_years=(2025, 2023),
        point_count=2279,
        built_at_utc="2026-09-19T12:00:00+00:00",
    )


@pytest.mark.unit
def test_manifest_round_trip_is_sorted_and_hashable(tmp_path: Path) -> None:
    path = tmp_path / "index_manifest.json"
    write_manifest(path, _manifest())

    loaded = read_manifest(path)

    assert [document.filename for document in loaded.documents] == [
        "sporting_regs_2023.pdf",
        "sporting_regs_2025.pdf",
    ]
    assert loaded.indexed_years == (2023, 2025)
    assert loaded.chunking_verified is True
    assert sha256_file(path) == manifest_hash(path)
    assert json.loads(path.read_text(encoding="utf-8"))["point_count"] == 2279


@pytest.mark.unit
def test_manifest_without_chunking_verification_stays_readable() -> None:
    payload = _manifest().to_dict()
    payload.pop("chunking_verified")

    loaded = IndexManifest.from_dict(payload)

    assert loaded.chunking_verified is False


@pytest.mark.unit
def test_manifest_write_is_idempotent_for_the_same_index(tmp_path: Path) -> None:
    path = tmp_path / "index_manifest.json"
    manifest = _manifest()

    first_hash = write_manifest(path, manifest)
    first_text = path.read_text(encoding="utf-8")
    second_hash = write_manifest(path, manifest)

    assert first_hash == second_hash
    assert path.read_text(encoding="utf-8") == first_text


@pytest.mark.unit
def test_validation_reports_model_collection_and_dimension_mismatches() -> None:
    errors = validate_manifest(
        _manifest(),
        collection_name="other_collection",
        embedding_model="other-model",
        embedding_dim=384,
        vector_dim=768,
    )

    assert len(errors) == 4
    assert any("collection_name" in error for error in errors)
    assert any("embedding_model" in error for error in errors)
    assert any("expected 384" in error for error in errors)
    assert any("Qdrant vector_dim=768" in error for error in errors)


@pytest.mark.unit
def test_validation_reports_a_stale_point_count() -> None:
    errors = validate_manifest(
        _manifest(), collection_name="fia_regulations", embedding_model="BAAI/bge-m3", point_count=1
    )

    assert errors == ["manifest point_count=2279, Qdrant point_count=1"]


@pytest.mark.unit
def test_malformed_manifest_fails_loudly() -> None:
    with pytest.raises(IndexManifestError, match="missing fields"):
        from src.rag.index_manifest import IndexManifest

        IndexManifest.from_dict({"schema_version": 1})


@pytest.mark.unit
def test_retriever_keeps_old_indexes_compatible_when_manifest_is_absent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    retriever = object.__new__(RagRetriever)
    retriever._manifest_path = tmp_path / "missing.json"
    retriever._manifest = None
    retriever._manifest_status = "valid"

    with caplog.at_level("WARNING", logger="src.rag.retriever"):
        retriever._load_and_validate_manifest(1024)

    assert retriever._manifest_status == "missing"
    assert "manifest missing" in caplog.text
