"""src/agents/rag_agent.py

RAG Agent: extraction from N30_rag_agent.ipynb.

Answers regulation questions by retrieving relevant FIA Sporting Regulation
passages from the local Qdrant vector store (built by scripts/build_rag_index.py)
and synthesising a concise answer via a LangGraph ReAct agent.

The heavy lifting (retriever singleton, query_rag_tool, RagRetriever) lives in
src/rag/retriever.py. This module adds the LangGraph agent wrapper,
the RegulationContext output dataclass, and the two entry points used by N31.

Entry points
------------
run_rag_agent(question, year=None)
    Takes a natural-language regulation question, invokes the ReAct agent,
    and returns a RegulationContext with the LLM answer and actual tool-result
    source chunks.
    ``year`` scopes the tool retrieval to one season's rulebook.

run_rag_agent_from_state(lap_state)
    RSM adapter: extracts the question from lap_state["question"] and the
    season from lap_state["year"], then delegates to run_rag_agent(). laps_df
    is not used (RAG is stateless with respect to lap data).
"""

import json
import importlib.util
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── Repo root (with root-stop guard for uv tool install) ─────────────────────
_REPO_ROOT = Path(__file__).resolve()
while not (_REPO_ROOT / ".git").exists():
    if _REPO_ROOT.parent == _REPO_ROOT:
        break
    _REPO_ROOT = _REPO_ROOT.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── src/rag imports ────────────────────────────────────────────────────────────
from src.rag.retriever import (  # noqa: E402
    CFG as _RAG_CFG,
    RegulationChunk,
    get_retriever,
    query_rag_tool,
)

from src.agents._shared_defaults import LLM_MAX_RETRIES, lm_studio_base_url, subagent_model

# ── Optional LangChain / LangGraph imports ─────────────────────────────
# Probed, not imported. `import langchain_openai` costs 14.3 s measured: it drags
# the langgraph stack and transformers in behind it, and every consumer of the
# name sits inside a factory that already builds its client on first call. So an
# eager import charged that to `f1-sim --help`, to a --no-llm run, and to every
# surface that merely touches this module. find_spec answers the only question
# asked here, is it installed, in about a millisecond and executes nothing.
_LC_OK = (
    importlib.util.find_spec("langchain_openai") is not None
    and importlib.util.find_spec("langchain.agents") is not None
)


# ==============================================================================
# Output dataclass
# ==============================================================================


@dataclass
class RegulationContext:
    """Structured output returned by the RAG agent for a single query.

    Bundles the LLM's plain-language summary with the source regulation chunks
    it was derived from, so downstream agents (N31) can both act on a concise
    answer and cite specific FIA articles without re-reading the raw passages.

    question:
        The original natural-language question that triggered this lookup.
        Stored so the orchestrator can log which queries were issued and
        detect duplicate lookups within a race lap.
    answer:
        LLM-generated summary of the relevant regulation articles, one to
        three sentences, enough for the Strategy Orchestrator to decide
        whether a proposed action is legal without reading the full passage.
        Do NOT use article numbers from this field for citations: the LLM
        may hallucinate them. Use the articles field instead.
    chunks:
        The raw RegulationChunk objects returned by the retriever. Kept
        alongside the summary so callers can filter by article range, year,
        or doc_type when the answer is ambiguous.
    articles:
        Deduplicated list of article references extracted from chunk metadata
        (e.g. ["Article 48.3", "Article 55.1"]). Always use this field for
        citations in strategy log entries: chunk metadata is reliable;
        LLM answer text may hallucinate article numbers.
    """

    question: str
    answer: str
    chunks: list[RegulationChunk] = field(default_factory=list)
    articles: list[str] = field(default_factory=list)
    citation_violations: list[str] = field(default_factory=list)

    @property
    def citation_faithful(self) -> bool:
        """Return whether every article cited by the answer was retrieved."""
        return not self.citation_violations

    @property
    def reasoning(self) -> str:
        """Alias for answer: interface consistency with N31.

        N31 reads .reasoning uniformly across all agent outputs (N25-N30).
        For N30 the regulatory answer IS the reasoning: it directly informs
        which strategy options are legal. No separate reasoning field needed.
        """
        return self.answer

    def __repr__(self) -> str:
        return f"RegulationContext(articles={self.articles}, answer={self.answer[:80]!r}...)"


# ==============================================================================
# LangGraph ReAct agent: lazy singleton
# ==============================================================================

# The CONDITION rule (rules 3 and 4) is the load-bearing one and it was added after
# a measured failure, not as good practice. Asked what the regulations say about
# tyre changes under a Safety Car, this agent returned Art. 30.5 n) with its
# applicability clause amputated: the real rule makes wet-weather tyres compulsory
# "if the formation lap is started behind the safety car ... or the race is
# resumed", and penalises a specification change "whilst the safety car is on the
# track AT SUCH TIMES". Dropping the last three words turns a narrow wet-start rule
# into a blanket ban on pitting under any Safety Car. The orchestrator then cited it
# to override a Monte Carlo that favoured stopping, on the lap sixteen cars really
# did stop, in the flagship case of the whole project (#826).
#
# Note what the fix is NOT. Every article number in that answer was genuine, so
# grounding the CITATION would not have caught it. The condition is the thing.
_SYSTEM_PROMPT = """You are an FIA Formula 1 regulation expert agent.
You have access to a tool that retrieves passages from the official FIA Sporting
Regulations (2023–2026). When asked a regulation question:
1. Call query_rag_tool with a precise, focused question.
2. Read the retrieved passages carefully.
3. **State the CONDITIONS under which each rule applies, in the same sentence as the
   rule.** Most FIA articles are conditional ("if the race is resumed...", "at such
   times", "during a suspension", "for the race in Monaco"). A rule quoted without
   its condition becomes a different and usually false rule.
4. **Never generalise a conditional rule to the unconditioned case.** If the
   retrieved passage restricts something only under specific circumstances and the
   question asks about the general case, say so explicitly: "this applies only when
   X; it does not apply otherwise."
5. Answer in 2-4 sentences, citing the exact article numbers (e.g. "Article 48.3").
6. If the question spans multiple articles, cite each one.
7. If no relevant passage is found, say "The regulation does not cover this case."
   Say this rather than stretching a nearby article to fit.

The passages you receive are already restricted to the season being raced, so cite
them as they stand and do not reach for another year's wording.
"""

# Lazy singleton: created on first call to avoid LLM connection at import time
_rag_agent = None


def get_rag_react_agent():
    """Return the cached LangGraph ReAct agent, creating it on first call.

    Uses `subagent_model()` (`F1_LLM_MODEL_AGENTS`, default `gpt-4.1-mini`) when
    `F1_LLM_PROVIDER=openai`, otherwise LM
    Studio at localhost:1234. The agent has one tool: query_rag_tool from
    src/rag/retriever.py. Raises ImportError when langgraph or
    langchain_openai are not installed.
    """
    global _rag_agent
    if _rag_agent is None:
        if not _LC_OK:
            raise ImportError(
                "langgraph or langchain_openai is not installed — cannot build "
                "the RAG agent. Install with: pip install langgraph langchain-openai"
            )
        import os

        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI

        provider = os.environ.get("F1_LLM_PROVIDER", "lmstudio")
        model_name = subagent_model()
        if provider == "openai":
            llm = ChatOpenAI(
                model=model_name, temperature=0, timeout=120, max_retries=LLM_MAX_RETRIES
            )
        else:
            llm = ChatOpenAI(
                model=model_name,
                base_url=lm_studio_base_url(),
                api_key="lm-studio",
                temperature=0,
                model_kwargs={"parallel_tool_calls": False},
                timeout=120,
                max_retries=LLM_MAX_RETRIES,
            )
        _rag_agent = create_agent(
            model=llm,
            tools=[query_rag_tool],
            system_prompt=_SYSTEM_PROMPT,
        )
    return _rag_agent


# ==============================================================================
_TOOL_HEADER = re.compile(
    r"^\[(?P<rank>\d+)\]\s+(?P<doc_type>.+?)\s+(?P<year>\d{4})"
    r"(?:\s+—\s+(?P<article>.*?))?\s+\(score:\s*(?P<score>[^)]+)\)$"
)
_TOOL_HEADER_START = re.compile(r"^\[\d+\]\s+.+\(score:")
_ARTICLE_ID_PATTERN = r"[A-Z]?\d+(?:\.\d+)*(?:\s*\([a-z0-9]+\))?"
_ARTICLE_ID = re.compile(_ARTICLE_ID_PATTERN, re.IGNORECASE)
_CITATION_PREFIX = re.compile(r"\b(?:articles?|arts?\.?)\s+", re.IGNORECASE)
_MEASUREMENT_UNIT_SUFFIX = re.compile(
    r"^\s*(?:(?:km\s*/\s*h|kmh|kph|m\s*/\s*s|sec(?:ond)?s?|"
    r"min(?:ute)?s?|h(?:our)?s?|kg|s|h)(?=$|[^a-z0-9])|%)",
    re.IGNORECASE,
)
_INVALID_ARTICLE_TOKEN = re.compile(r"[A-Z0-9._()\-]*\d[A-Z0-9._()\-]*", re.IGNORECASE)
_ARTICLE_TOKEN = re.compile(rf"^(?:article\s+)?(?P<id>{_ARTICLE_ID_PATTERN})$", re.IGNORECASE)


def _message_text(content: object) -> str:
    """Flatten string or text-block message content for trace parsing."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, str):
                texts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                block_text = block.get("text", "")
                if isinstance(block_text, str):
                    texts.append(block_text)
        return "\n".join(text for text in texts if isinstance(text, str))
    return ""


def _tool_messages(messages: list[object]) -> list[str]:
    """Return results correlated to actual ``query_rag_tool`` call IDs."""
    call_names: dict[str, str] = {}
    for message in messages:
        if getattr(message, "type", "") != "ai":
            continue
        for tool_call in getattr(message, "tool_calls", []) or []:
            if not isinstance(tool_call, dict):
                continue
            call_id = tool_call.get("id")
            name = tool_call.get("name")
            if isinstance(call_id, str) and isinstance(name, str):
                call_names[call_id] = name

    results: list[str] = []
    for message in messages:
        message_type = getattr(message, "type", "")
        message_name = getattr(message, "name", None)
        call_id = getattr(message, "tool_call_id", None)
        if (
            message_type != "tool"
            or call_names.get(call_id) != "query_rag_tool"
            or message_name not in {None, "", "query_rag_tool"}
        ):
            continue
        content = _message_text(getattr(message, "content", None))
        if content:
            results.append(content)
    return results


def _parse_tool_result(content: str) -> list[RegulationChunk]:
    """Parse typed chunks from one actual ``query_rag_tool`` result."""
    if content.startswith("No relevant regulation passages found"):
        return []

    chunks: list[RegulationChunk] = []
    current_match = None
    current_text: list[str] = []

    def append_current() -> None:
        if current_match is None:
            return
        try:
            score = float(current_match.group("score"))
        except ValueError:
            return
        if not math.isfinite(score) or not 0.0 <= score <= 1.0:
            return
        chunks.append(
            RegulationChunk(
                text="\n".join(current_text).strip(),
                article=(current_match.group("article") or "").strip(),
                doc_type=current_match.group("doc_type").strip(),
                year=int(current_match.group("year")),
                score=score,
            )
        )

    for line in content.strip().splitlines():
        match = _TOOL_HEADER.match(line)
        if _TOOL_HEADER_START.match(line):
            append_current()
            current_match = None
            current_text = []
            if match is not None:
                current_match = match
                current_text = []
        elif current_match is not None:
            current_text.append(line)
    append_current()
    return chunks


def _retrieve_tool_passages(messages: list[object]) -> list[RegulationChunk]:
    """Extract the exact passages returned to the LLM without re-querying Qdrant."""
    chunks: list[RegulationChunk] = []
    seen: set[tuple[str, int, str, str, str]] = set()
    for content in _tool_messages(messages):
        for chunk in _parse_tool_result(content):
            key = (chunk.text, chunk.year, chunk.doc_type, chunk.article, chunk.section_title)
            if key not in seen:
                seen.add(key)
                chunks.append(chunk)
    return chunks


def _citation_violations(answer: str, articles: list[str]) -> list[str]:
    """Return unsupported or malformed article references in an answer."""
    retrieved = set()
    for article in articles:
        normalized = _normalise_article(article)
        if normalized is not None:
            retrieved.add(normalized)
    cited: set[str] = set()
    violations: set[str] = set()
    for prefix in _CITATION_PREFIX.finditer(answer):
        plural = prefix.group(0).strip().casefold().rstrip(".").endswith("s")
        parsed, errors = _parse_citation_list(answer, prefix.end(), plural=plural)
        cited.update(parsed)
        violations.update(errors)
    violations.update(citation for citation in cited if citation not in retrieved)
    return sorted(violations)


def _normalise_article(value: str) -> str | None:
    """Normalize one article label while requiring a complete article identifier."""
    candidate = " ".join(value.split())
    match = _ARTICLE_TOKEN.fullmatch(candidate)
    if match is None:
        return None
    article_id = re.sub(r"\s*\(", "(", match.group("id")).casefold()
    return f"article {article_id}"


def _parse_citation_list(
    text: str,
    start: int,
    *,
    plural: bool = False,
) -> tuple[set[str], set[str]]:
    """Parse a citation list and retain malformed references as violations."""
    citations: set[str] = set()
    violations: set[str] = set()
    first_reference = True
    position = start
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        position = _skip_markdown_markers(position, text)
        match = _ARTICLE_ID.match(text, position)
        if match is None:
            invalid = _INVALID_ARTICLE_TOKEN.match(text, position)
            if invalid is not None:
                violations.add(f"invalid article citation: {invalid.group(0)}".casefold())
            break

        raw_id = match.group(0)
        end = match.end()
        unit_suffix_start = _skip_markdown_markers(end, text)
        if not first_reference and _MEASUREMENT_UNIT_SUFFIX.match(text[unit_suffix_start:]):
            break

        tail = unit_suffix_start
        while tail < len(text) and text[tail].isspace():
            tail += 1

        malformed_end = end
        malformed = False
        if end < len(text) and (text[end].isalnum() or text[end] in "(_-–—"):
            malformed = True
        elif end < len(text) and text[end] == ".":
            following = text[end + 1] if end + 1 < len(text) else ""
            if following and (following.isalnum() or following in "._"):
                malformed = True
        elif tail < len(text) and text[tail] in "-–—":
            article_range = re.match(r"[-–—]\s*(?:[*`]+\s*)?[A-Z]?\d", text[tail:], re.IGNORECASE)
            if article_range is not None:
                malformed = True
                malformed_end = tail + article_range.end()
        elif tail < len(text) and text[tail] == "(":
            malformed = True
            malformed_end = tail

        if malformed:
            while malformed_end < len(text) and (
                text[malformed_end].isalnum() or text[malformed_end] in "._()-–—"
            ):
                malformed_end += 1
            violations.add(
                f"invalid article citation: {raw_id}{text[end:malformed_end]}".casefold()
            )
            break

        canonical = _normalise_article(raw_id)
        if canonical is not None:
            citations.add(canonical)
        first_reference = False

        if tail >= len(text):
            break
        separator_end = tail
        if text[tail] in ",;/&":
            if text[tail] == ",":
                next_position = tail + 1
                while next_position < len(text) and text[next_position].isspace():
                    next_position += 1
                next_position = _skip_conjunction(next_position, text)
                while next_position < len(text) and text[next_position].isspace():
                    next_position += 1
                next_position = _skip_markdown_markers(next_position, text)
                next_article = _ARTICLE_ID.match(text, next_position)
                if next_article is None:
                    break
                if "." not in next_article.group(0) and not plural:
                    break
            separator_end += 1
            while separator_end < len(text) and text[separator_end].isspace():
                separator_end += 1
            separator_end = _skip_conjunction(separator_end, text)
        else:
            separator_end = _skip_conjunction(tail, text)
            if separator_end == tail:
                break

        position = separator_end

    return citations, violations


def _skip_markdown_markers(position: int, text: str) -> int:
    while position < len(text) and text[position] in ("*", "`"):
        position += 1
    return position


def _skip_conjunction(position: int, text: str) -> int:
    for word in ("and", "or"):
        if text[position : position + len(word)].casefold() != word:
            continue
        end = position + len(word)
        if end == len(text) or not text[end].isalnum():
            return end
    return position


# Entry points
# ==============================================================================


def run_rag_agent(question: str, year: int | None = None) -> "RegulationContext":
    """Run the RAG ReAct agent for a single regulation question.

    Invokes the LangGraph agent with query_rag_tool, extracts the final answer
    from the last message, and parses the actual tool messages into typed
    RegulationChunk objects. No second semantic retrieval is performed, so the
    context cannot silently cite a different result set from the one the LLM read.

    The season reaches the actual tool through the RunnableConfig the graph
    forwards. Its result message supplies the chunks and article metadata used
    to verify answer citations.

    question:
        Natural-language regulation question from the orchestrator (N31).
        Examples: "What must a driver do when the safety car is deployed?",
        "What is the minimum pit stop time during a race?".

    year:
        Season whose rulebook to search, normally lap_state["year"]. None
        searches every indexed season, which is what the notebook demos and any
        caller predating season scoping get. It is a process-context argument on
        purpose: the model never chooses it, because a model asked to pick the
        year of a regulation is the failure this scoping exists to remove.

    Returns a RegulationContext with answer, chunks, and deduplicated articles.
    Use ctx.articles for citations, not the article numbers in ctx.answer.
    """
    from langchain_core.messages import HumanMessage

    agent = get_rag_react_agent()
    result = agent.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"configurable": {"season": year}},
    )
    answer = _message_text(result["messages"][-1].content)

    chunks = _retrieve_tool_passages(result["messages"])
    articles = list(dict.fromkeys(c.article for c in chunks if c.article))
    citation_violations = _citation_violations(answer, articles)

    return RegulationContext(
        question=question,
        answer=answer,
        chunks=chunks,
        articles=articles,
        citation_violations=citation_violations,
    )


def run_rag_agent_from_state(
    lap_state: dict,
    laps_df=None,
) -> "RegulationContext":
    """RSM adapter: extract the question from lap_state and call run_rag_agent.

    The RAG agent is stateless with respect to lap data: it only needs the
    natural-language question. laps_df is accepted for interface consistency
    with other RSM adapters but is not used.

    lap_state keys:
        question (str): Natural-language FIA regulation question. Required.
        year (int, optional): Season to scope retrieval to. Absent means every
            indexed season, so a caller that omits it keeps the old behaviour
            rather than getting an empty result.
        session_meta (dict, optional): Unused, kept for interface parity.

    laps_df:
        Ignored. Accepted so the orchestrator can call all RSM adapters with
        the same signature without branching on agent type.

    Returns a RegulationContext identical to what run_rag_agent() returns.
    Raises KeyError when lap_state does not contain a 'question' key.
    """
    question = lap_state["question"]
    return run_rag_agent(question, year=lap_state.get("year"))
