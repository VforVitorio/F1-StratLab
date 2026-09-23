"""Tests that RAG provenance follows the questions actually sent to the tool."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


def _tool_call(call_id: str, name: str = "query_rag_tool") -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": call_id,
                "name": name,
                "args": {"question": "rewritten safety car query"},
                "type": "tool_call",
            }
        ],
    )


def _tool_result(call_id: str, content, name: str = "query_rag_tool") -> ToolMessage:
    return ToolMessage(content=content, tool_call_id=call_id, name=name)


@pytest.mark.unit
def test_rag_context_uses_the_actual_tool_result_not_a_second_query(monkeypatch) -> None:
    from src.agents import rag_agent

    class Agent:
        def invoke(self, *_args, **_kwargs):
            return {
                "messages": [
                    _tool_call("call-1"),
                    _tool_result(
                        "call-1",
                        "[1] sporting_regs 2025 — Article 30.5  (score: 0.900)\n"
                        "verbatim retrieved rule",
                    ),
                    AIMessage(content="summary citing Article 30.5"),
                ]
            }

    monkeypatch.setattr(rag_agent, "get_rag_react_agent", lambda: Agent())

    context = rag_agent.run_rag_agent("original question", year=2025)

    assert context.answer == "summary citing Article 30.5"
    assert context.articles == ["Article 30.5"]
    assert context.chunks[0].text == "verbatim retrieved rule"
    assert context.citation_faithful


@pytest.mark.unit
def test_rag_context_flags_citations_absent_from_tool_results(monkeypatch) -> None:
    from src.agents import rag_agent

    class Agent:
        def invoke(self, *_args, **_kwargs):
            return {
                "messages": [
                    _tool_call("call-2"),
                    _tool_result(
                        "call-2",
                        "[1] sporting_regs 2025 — Article 30.5  (score: 0.900)\n"
                        "verbatim retrieved rule",
                    ),
                    AIMessage(content="summary citing Article 55.8"),
                ]
            }

    monkeypatch.setattr(rag_agent, "get_rag_react_agent", lambda: Agent())

    context = rag_agent.run_rag_agent("question", year=2025)

    assert context.citation_violations == ["article 55.8"]
    assert not context.citation_faithful


@pytest.mark.unit
def test_only_tool_messages_correlated_to_regulation_calls_are_sources() -> None:
    from src.agents.rag_agent import _tool_messages

    messages = [
        _tool_call("reg-1"),
        _tool_call("other-1", name="other_tool"),
        _tool_result("reg-1", "retrieved evidence"),
        _tool_result("other-1", "not regulation evidence", name="other_tool"),
        _tool_result("unmatched", "must not be attached"),
        HumanMessage(name="query_rag_tool", content="not a tool result"),
    ]

    assert _tool_messages(messages) == ["retrieved evidence"]


@pytest.mark.unit
def test_correlated_unnamed_tool_message_is_still_a_source() -> None:
    from src.agents.rag_agent import _tool_messages

    result = ToolMessage(content="retrieved", tool_call_id="call-1")

    assert _tool_messages([_tool_call("call-1"), result]) == ["retrieved"]


@pytest.mark.unit
def test_retriever_drops_hits_below_the_similarity_floor() -> None:
    from types import SimpleNamespace

    from src.rag.retriever import RagRetriever

    retriever = object.__new__(RagRetriever)
    retriever._top_k = 5
    retriever._similarity_floor = 0.50
    retriever._encode = lambda _question: [1.0]
    retriever._build_scope_filter = lambda _year, _doc_type: None
    retriever._search = lambda _vector, _limit, _scope: [
        SimpleNamespace(
            score=0.51,
            payload={"text": "kept", "article": "Article 1", "year": 2025},
        ),
        SimpleNamespace(
            score=0.49,
            payload={"text": "weak", "article": "Article 2", "year": 2025},
        ),
    ]

    chunks = retriever.query("q", year=2025)

    assert [chunk.text for chunk in chunks] == ["kept"]


@pytest.mark.unit
def test_tool_parser_keeps_bracketed_passage_text_and_article_suffixes() -> None:
    from src.agents.rag_agent import _parse_tool_result

    chunks = _parse_tool_result(
        "\n".join(
            [
                "[1] Sporting Regulations 2026 — Article B5.13.1  (score: 0.700)",
                "start",
                "",
                "[2] source numbered paragraph",
                "end",
                "[2] Sporting Regulations 2026 — Article B5.13.2  (score: 0.600)",
                "second passage",
            ]
        )
    )

    assert [chunk.article for chunk in chunks] == ["Article B5.13.1", "Article B5.13.2"]
    assert chunks[0].text == "start\n\n[2] source numbered paragraph\nend"
    assert len(chunks) == 2


@pytest.mark.unit
def test_malformed_score_header_does_not_leak_into_previous_passage() -> None:
    from src.agents.rag_agent import _parse_tool_result

    for invalid_score in ("-0.2", "nan", "inf", "1.2", "0..9", "9" * 400, ""):
        chunks = _parse_tool_result(
            "[1] Sporting Regulations 2026 — Article 30.5  (score: 0.9)\n"
            "good passage\n"
            f"[2] Sporting Regulations 2026 — Article 55.8  (score: {invalid_score})\n"
            "bad passage\n"
            "[3] Sporting Regulations 2026 — Article 57.1  (score: 0.8)\n"
            "final passage"
        )

        assert [chunk.article for chunk in chunks] == ["Article 30.5", "Article 57.1"]
        assert chunks[0].text == "good passage"
        assert chunks[1].text == "final passage"


@pytest.mark.unit
def test_citation_parser_handles_plural_and_enumerated_articles() -> None:
    from src.agents.rag_agent import _citation_violations

    assert _citation_violations("Articles 30.5 and 99.9 apply.", ["Article 30.5"]) == [
        "article 99.9"
    ]
    assert _citation_violations("Art. 99.9 applies.", ["Article 30.5"]) == ["article 99.9"]
    assert _citation_violations(
        "Articles 30.5, 30.6, and 99.9 apply.", ["Article 30.5", "Article 30.6"]
    ) == ["article 99.9"]
    assert _citation_violations(
        "Articles 30.5, 30.6 & 99.9 apply.", ["Article 30.5", "Article 30.6"]
    ) == ["article 99.9"]
    assert _citation_violations(
        "Articles 30.5; 30.6 or 99.9 apply.", ["Article 30.5", "Article 30.6"]
    ) == ["article 99.9"]
    assert _citation_violations("Arts. 30.5/99.9 apply.", ["Article 30.5"]) == ["article 99.9"]
    assert _citation_violations("Arts. 30.5 and 99.9 apply.", ["Article 30.5"]) == ["article 99.9"]
    assert _citation_violations("Article 30.5 (n) applies.", ["Article 30.5(n)"]) == []
    for malformed in ("30.5foo", "30.5.abc", "30.5(garbage"):
        assert _citation_violations(f"Article {malformed} applies.", ["Article 30.5"])


@pytest.mark.unit
def test_malformed_article_suffix_cannot_match_a_retrieved_prefix() -> None:
    from src.agents.rag_agent import _citation_violations

    for malformed in (
        "30.5foo",
        "30.5.abc",
        "30.5(garbage",
        "B5.13.1foo",
        "30.5..99",
        "30.5_99",
        "AB5.13.1",
        "-30.5",
    ):
        assert _citation_violations(
            f"Article {malformed} applies.", ["Article 30.5", "Article B5.13.1"]
        )
    assert _citation_violations("Article 30.5 (n) applies.", ["Article 30.5(n)"]) == []
    for citation in (
        "Arts. 30.5 and 99.9 apply.",
        "Articles 30.5, 30.6, and 99.9 apply.",
        "Articles 30.5, 30.6 & 99.9 apply.",
        "Articles 30.5/99.9 apply.",
    ):
        assert _citation_violations(citation, ["Article 30.5", "Article 30.6"]) == ["article 99.9"]
    for malformed in (
        "30.5foo",
        "30.5.abc",
        "30.5(garbage",
        "30.5bogus",
        "B5.13.1foo",
    ):
        assert _citation_violations(
            f"Article {malformed} applies.", ["Article 30.5", "Article B5.13.1"]
        )
    assert _citation_violations("Article 30.5 (n) applies.", ["Article 30.5(n)"]) == []


@pytest.mark.unit
def test_citation_parser_handles_markdown_ranges_and_numeric_prose() -> None:
    from src.agents.rag_agent import _citation_violations

    for answer in (
        "Article **99.9** applies.",
        "Article `99.9` applies.",
    ):
        assert _citation_violations(answer, ["Article 30.5"]) == ["article 99.9"]
    for answer in (
        "Articles **30.5**, **99.9** apply.",
        "Articles **30.5** and 99.9 apply.",
    ):
        assert _citation_violations(answer, ["Article 30.5"]) == ["article 99.9"]
    for malformed in ("30.5-99.9", "30.5-foo"):
        assert _citation_violations(f"Article {malformed} applies.", ["Article 30.5"])
    for malformed in ("30.5 - 99.9", "30.5 - B5.13.1", "30.5 – 99.9"):
        assert _citation_violations(f"Article {malformed} applies.", ["Article 30.5"])
    for answer in (
        "Articles **30.5**-99.9 apply.",
        "Articles **30.5** - **99.9** apply.",
        "Articles 30.5 - **99.9** apply.",
        "Articles **30.5** – 99.9 apply.",
        "Articles `30.5`-`99.9` apply.",
    ):
        assert _citation_violations(answer, ["Article 30.5"])
    for answer in (
        "Article 30.5, 80 km/h is allowed.",
        "Articles 30.5, 80 km/h are allowed.",
        "Article 30.5, 80.5 km/h is allowed.",
        "Articles 30.5, 80.5 km/h are allowed.",
        "Article 30.5, **80.5** km/h is allowed.",
        "Articles 30.5, **80.5** km/h are allowed.",
        "Article 30.5 and 80.5 km/h is allowed.",
        "Articles 30.5 and 80.5 km/h are allowed.",
        "Article 30.5 and **80.5** km/h is allowed.",
    ):
        assert _citation_violations(answer, ["Article 30.5"]) == []
    assert _citation_violations("Article 30.5, 99.9 apply.", ["Article 30.5"]) == ["article 99.9"]
    assert _citation_violations("Articles 1, 2 apply.", ["Article 1"]) == ["article 2"]


@pytest.mark.unit
def test_deduplication_keeps_same_text_with_distinct_article_sources() -> None:
    from src.agents.rag_agent import _retrieve_tool_passages

    chunks = _retrieve_tool_passages(
        [
            _tool_call("multi"),
            _tool_result(
                "multi",
                "[1] Sporting Regulations 2026 — Article B5.13.1  (score: 0.7)\n"
                "shared passage\n"
                "[2] Sporting Regulations 2026 — Article B5.13.2  (score: 0.7)\n"
                "shared passage",
            ),
        ]
    )

    assert [chunk.article for chunk in chunks] == ["Article B5.13.1", "Article B5.13.2"]


@pytest.mark.unit
def test_message_content_blocks_keep_string_and_text_parts() -> None:
    from src.agents.rag_agent import _message_text

    assert _message_text(["first", {"type": "text", "text": "second"}, 42]) == "first\nsecond"


@pytest.mark.unit
def test_message_text_flattens_langchain_text_blocks() -> None:
    from src.agents.rag_agent import _message_text

    assert _message_text(["Article 30.5", {"type": "text", "text": "Article B5.13.1"}]) == (
        "Article 30.5\nArticle B5.13.1"
    )


@pytest.mark.unit
def test_agent_context_accepts_langchain_string_and_block_content(monkeypatch) -> None:
    from src.agents import rag_agent

    class Agent:
        def invoke(self, *_args, **_kwargs):
            return {
                "messages": [
                    _tool_call("block-call"),
                    ToolMessage(
                        content=[
                            "[1] Sporting Regulations 2026 — Article B5.13.1  (score: 0.700)",
                            {"type": "text", "text": "retrieved passage"},
                        ],
                        tool_call_id="block-call",
                    ),
                    AIMessage(
                        content=[
                            {"type": "text", "text": "Article B5.13.1 applies."},
                            "Article 99.9 does not appear in the source.",
                        ]
                    ),
                ]
            }

    monkeypatch.setattr(rag_agent, "get_rag_react_agent", lambda: Agent())
    context = rag_agent.run_rag_agent("question", year=2026)

    assert context.answer == "Article B5.13.1 applies.\nArticle 99.9 does not appear in the source."
    assert context.articles == ["Article B5.13.1"]
    assert context.citation_violations == ["article 99.9"]
    assert not context.citation_faithful


@pytest.mark.unit
def test_configured_floor_has_no_singleton_factory_override() -> None:
    from inspect import signature

    from src.rag.retriever import RagConfig, get_retriever

    assert RagConfig(similarity_floor=0.7).similarity_floor == 0.7
    with pytest.raises(ValueError, match="similarity_floor"):
        RagConfig(similarity_floor=1.01)
    assert "similarity_floor" not in signature(get_retriever).parameters


@pytest.mark.unit
def test_floor_is_configured_on_rag_config_not_as_a_singleton_cache_key() -> None:
    from inspect import signature

    from src.rag.retriever import RagConfig, get_retriever

    assert RagConfig(similarity_floor=0.7).similarity_floor == 0.7
    with pytest.raises(ValueError, match="similarity_floor"):
        RagConfig(similarity_floor=1.1)
    assert "similarity_floor" not in signature(get_retriever).parameters
