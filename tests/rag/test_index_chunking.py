"""Regression tests for article-aware FIA regulation chunking."""

from pathlib import Path

import pytest

from scripts.build_rag_index import PDFDocument, extract_text_from_pdf, iter_chunks

_RULE_WITH_CROSS_REFERENCE = """30.5 Use of Tyres
n) If the formation lap is started behind the safety car in accordance with Article 49.1a,
or the race is resumed in accordance with Article 58.1, the use of wet-weather tyres is
compulsory. A penalty under Article 54.3d) will be imposed on any driver who changes
tyres to a different specification whilst the safety car is on the track at such times.
o) Additional tyre rules follow.
"""


def _document(text: str) -> PDFDocument:
    return PDFDocument(
        path=Path("sporting_regs_2025.pdf"),
        doc_type="sporting_regs",
        year=2025,
        text=text,
    )


@pytest.mark.unit
def test_clause_keeps_condition_and_rule_together() -> None:
    chunks = list(
        iter_chunks(_document(_RULE_WITH_CROSS_REFERENCE), chunk_size=80, chunk_overlap=16)
    )

    matches = [chunk for chunk in chunks if "Article 54.3d)" in chunk.text]

    assert len(matches) == 1
    assert "formation lap" in matches[0].text
    assert "resumed" in matches[0].text
    assert "different specification" in matches[0].text


@pytest.mark.unit
def test_article_label_comes_from_heading_not_cross_reference() -> None:
    chunks = list(
        iter_chunks(_document(_RULE_WITH_CROSS_REFERENCE), chunk_size=80, chunk_overlap=16)
    )

    matches = [chunk for chunk in chunks if "Article 54.3d)" in chunk.text]

    assert matches[0].article == "Article 30.5"
    assert matches[0].section_title == "30.5 Use of Tyres"


@pytest.mark.unit
def test_chunk_without_heading_does_not_infer_article_from_body_reference() -> None:
    chunks = list(
        iter_chunks(
            _document("A penalty under Article 54.3d) applies in this case."),
            chunk_size=80,
            chunk_overlap=16,
        )
    )

    assert chunks[0].article == ""


@pytest.mark.unit
def test_empty_rule_heading_is_kept_as_a_chunk() -> None:
    document = _document("34.3 Pit lane rule\n34.4 Next rule")

    chunks = list(iter_chunks(document, chunk_size=80, chunk_overlap=16))

    assert any(
        chunk.article == "Article 34.3" and chunk.text == "34.3 Pit lane rule" for chunk in chunks
    )


@pytest.mark.unit
def test_date_line_is_not_mistaken_for_an_article_heading() -> None:
    document = _document("30 Main rule\n31 December is the deadline.")

    chunks = list(iter_chunks(document, chunk_size=80, chunk_overlap=16))

    assert all(chunk.article != "Article 31" for chunk in chunks)


@pytest.mark.unit
def test_numeric_leading_rule_gets_its_own_article_label() -> None:
    document = _document(
        "43.1 Sprint start procedure\n"
        "43.2 30 minutes is required in this case.\n"
        "43.3 27 minutes applies in another case.\n"
        "43.4 The next rule."
    )

    chunks = list(iter_chunks(document, chunk_size=80, chunk_overlap=16))

    assert any(chunk.article == "Article 43.2" for chunk in chunks)
    assert any(chunk.article == "Article 43.3" for chunk in chunks)


@pytest.mark.unit
def test_numbered_rule_keeps_its_nested_exceptions_together() -> None:
    document = _document(
        "55.8 With the exception of the cases listed below, no driver may overtake "
        "until after the safety car has returned to the pits.\n"
        "The exceptions are:\n"
        "a) A driver is signalled to do so.\n"
        "b) The car is entering the pits.\n"
        "55.9 The next rule."
    )

    chunks = list(iter_chunks(document, chunk_size=80, chunk_overlap=16))
    rule = [chunk for chunk in chunks if chunk.article == "Article 55.8"]

    assert len(rule) == 1
    assert "after the safety car has returned" in rule[0].text
    assert "exceptions" in rule[0].text
    assert "entering the pits" in rule[0].text


@pytest.mark.unit
def test_2025_safety_car_clause_is_self_contained_when_corpus_is_available() -> None:
    pdf_path = Path("data/rag/documents/sporting_regs_2025.pdf")
    if not pdf_path.exists():
        pytest.skip("local FIA corpus is not available")

    document = _document(extract_text_from_pdf(pdf_path))
    chunks = list(iter_chunks(document))
    matches = [
        chunk
        for chunk in chunks
        if "different specification" in chunk.text.lower()
        and "safety car" in chunk.text.lower()
        and "54.3d" in chunk.text.lower()
    ]

    assert matches
    assert any(
        chunk.article == "Article 30.5"
        and "formation lap" in chunk.text.lower()
        and "resumed" in chunk.text.lower()
        for chunk in matches
    )
