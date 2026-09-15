"""Tests that RAG provenance follows the questions actually sent to the tool."""

from types import SimpleNamespace

import pytest


@pytest.mark.unit
def test_rag_context_rehydrates_the_tool_query_not_the_original_question(monkeypatch) -> None:
    from src.agents import rag_agent
    from src.rag.retriever import RegulationChunk

    calls: list[tuple[str, int | None]] = []

    class Agent:
        def invoke(self, *_args, **_kwargs):
            return {
                "messages": [
                    SimpleNamespace(
                        tool_calls=[
                            {
                                "name": "query_rag_tool",
                                "args": {"question": "rewritten safety car query"},
                            }
                        ]
                    ),
                    SimpleNamespace(content="summary"),
                ]
            }

    class Retriever:
        def query(self, question: str, year: int | None = None):
            calls.append((question, year))
            return [
                RegulationChunk(
                    text="verbatim retrieved rule",
                    article="Article 30.5",
                    doc_type="sporting_regs",
                    year=year or 0,
                    score=0.9,
                )
            ]

    monkeypatch.setattr(rag_agent, "get_rag_react_agent", lambda: Agent())
    monkeypatch.setattr(rag_agent, "get_retriever", lambda: Retriever())

    context = rag_agent.run_rag_agent("original question", year=2025)

    assert calls == [("rewritten safety car query", 2025)]
    assert context.answer == "summary"
    assert context.articles == ["Article 30.5"]
    assert context.chunks[0].text == "verbatim retrieved rule"


@pytest.mark.unit
def test_tool_query_extraction_ignores_other_or_malformed_calls() -> None:
    from src.agents.rag_agent import _extract_tool_queries

    messages = [
        SimpleNamespace(
            tool_calls=[
                {"name": "other_tool", "args": {"question": "ignore"}},
                {"name": "query_rag_tool", "args": {"question": "use this"}},
                {"name": "query_rag_tool", "args": {"question": "  "}},
                {"name": "query_rag_tool", "args": None},
            ]
        )
    ]

    assert _extract_tool_queries(messages) == ["use this"]
