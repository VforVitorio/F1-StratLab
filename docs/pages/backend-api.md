# Backend API Reference (FastAPI)

## Overview

The backend is a FastAPI application at `src/telemetry/backend/`. It serves telemetry data, driver comparisons, chat (LM Studio proxy), voice (STT/TTS), and the N25–N31 strategy agent pipeline. All endpoints are prefixed with `/api/v1`.

Entry point: `backend/main.py` — creates the FastAPI app and registers all routers.

## Router map

| Router | Prefix | Tags | Source |
|---|---|---|---|
| auth | `/api/v1` | auth | `endpoints/auth.py` |
| telemetry | `/api/v1/telemetry` | telemetry | `endpoints/telemetry.py` |
| circuit_domination | `/api/v1` | circuit_domination | `endpoints/circuit_domination.py` |
| comparison | `/api/v1/comparison` | comparison | `endpoints/comparison.py` |
| chat | `/api/v1/chat` | chat | `endpoints/chat.py` |
| voice | `/api/v1/voice` | voice | `endpoints/voice.py` |
| strategy | `/api/v1/strategy` | strategy | `endpoints/strategy.py` |

## Telemetry endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/telemetry/data` | Fetch telemetry for year/gp/session/drivers |
| GET | `/api/v1/telemetry/gps` | List available GPs for a year |
| GET | `/api/v1/telemetry/sessions` | List sessions for a GP |
| GET | `/api/v1/telemetry/drivers` | List drivers for a session |

**Query parameters**: `year` (int), `gp` (str), `session` (str), `drivers` (comma-separated).

## Comparison endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/comparison/compare` | Compare fastest-lap telemetry between two drivers |

## Chat endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/chat/health` | LM Studio health check |
| GET | `/api/v1/chat/models` | List available LM Studio models |
| GET | `/api/v1/chat/status` | Current backend stage for a `request_id` (smart-spinner poll) |
| POST | `/api/v1/chat/message` | Non-streaming chat message (raw LLM, no tools) |
| POST | `/api/v1/chat/stream` | Streaming chat response (raw LLM, no tools) |
| POST | `/api/v1/chat/tool-message` | Tool-aware chat -- JSON response |
| POST | `/api/v1/chat/tool-message-stream` | Tool-aware chat -- Server-Sent Events stream |

Chat proxies the configured LLM provider (LM Studio local or OpenAI cloud, switchable via `F1_LLM_PROVIDER`). Tool-aware endpoints route through the **MCP-driven `chat_engine`** (see below); raw `/message` and `/stream` skip the tool layer and return whatever the model writes.

### MCP-Driven Tool Routing

`/chat/tool-message` and `/chat/tool-message-stream` are powered by `services/chatbot/chat_engine.py`. The engine pulls every tool from the FastMCP server (`backend.mcp_tools.mcp`) via the in-process `fastmcp.Client`, exposes them to the LLM as OpenAI-style `tools=[...]` schemas, and dispatches the model's chosen tool back through the MCP client. There is **no parallel keyword/regex registry** anymore -- tool definitions live in one place and the LLM sees the same schemas an external MCP client (Claude Desktop, Cursor) would see when it dials `/mcp`.

The flow per request:

1. **Pull tool catalog** -- `mcp_bridge.list_openai_tools()` returns every Phase 1 `@mcp.tool` plus the Phase 2 telemetry tools auto-mounted from the FastAPI OpenAPI spec, formatted as `{"type": "function", "function": {...}}`.
2. **First LLM call** -- with `tools=` populated. The model decides whether to call a tool or reply in plain text. Casual greetings, meta questions ("what tools do you have?"), and general F1 knowledge are answered directly without dispatching.
3. **Tool dispatch** (only when the model returned a `tool_call`) -- `mcp_bridge.call_mcp_tool(name, args)` runs the tool through the FastMCP client and returns the structured data.
4. **`tool_result` SSE event** -- the structured payload is wrapped in `{tool_name, display_type, data, summary}` and emitted so the frontend can render the right component (chart / metrics / strategy card / table / text).
5. **Second LLM call** -- without `tools=`, feeding the tool's output back as a `role=tool` message so the model summarises the data in the user's language.

The streaming endpoint emits four SSE event types in order: `stage` (every checkpoint, also reflected in `/chat/status`), `tool_result` (rich payload), `token` (LLM text chunks), `done` (final marker with provider metadata).

### Tool results and display hints

Each tool is mapped to a `DisplayType` hint via `TOOL_DISPLAY_MAP` (`models/tool_schemas.py`); the frontend's chat renderer chooses a component based on the hint:

| DisplayType | Used by |
|---|---|
| `METRICS` | `predict_pace`, `predict_situation` |
| `STRATEGY_CARD` | `predict_tire`, `predict_pit`, `recommend_strategy` |
| `TABLE` | `analyze_radio` |
| `TEXT` | `query_regulations`, `list_gps`, `list_drivers`, `get_lap_range` |
| `CHART` | `get_lap_times`, `get_telemetry`, `compare_drivers`, `get_race_data` |

`chat_engine._trim_for_llm` caps long arrays before they are sent back to the LLM for summarisation; the unmodified payload still reaches the frontend on `tool_result.data` so charts retain the full series. The four telemetry tools are wired to `CHART` so the frontend renders them as inline Plotly figures (see [Streamlit frontend → chat tool-result rendering](#/streamlit)).

### Smart-spinner stage tracker

The frontend mints a UUID, sends it on every chat request via the `X-Request-Id` header, and polls `/api/v1/chat/status?request_id=...` every second. The backend writes the current stage (`preparing_tools`, `model_choosing_tool`, `calling_<tool>`, `summarizing_with_llm`, ...) into a process-global tracker (`services/chatbot/stage_tracker.py`) at every checkpoint, cleared in a `try/finally` so the dict never leaks. The Streamlit chat page maps these stages to humanised labels so the spinner narrates the slow phases (model loading, tool execution).

### Module layout

`services/chatbot/` now contains only what the MCP-driven flow needs:

- `chat_engine.py` — async orchestrator (stream + sync entry points).
- `mcp_bridge.py` — async adapter to the FastMCP server (`list_openai_tools`, `call_mcp_tool`).
- `llm_service.py` — provider abstraction (LM Studio + OpenAI), now with `tools=` support.
- `stage_tracker.py` — per-request stage dict for the smart-spinner.
- `utils/` — empty placeholder; the legacy `tool_param_extractor`, `query_classifier`, `validators`, the per-handler files, the `router/` package and the `prompts/` directory were deleted along with the `/chat/query` endpoint.

## Voice endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/voice/transcribe` | Speech-to-text (Whisper) |
| POST | `/api/v1/voice/tts` | Text-to-speech |
| GET | `/api/v1/voice/health` | Voice service health check |

## Strategy endpoints (N25–N31)

All strategy endpoints live under `/api/v1/strategy/`. They accept JSON bodies and return `StrategyResponse` envelopes.

### Consumers

The `/api/v1/strategy/simulate` SSE endpoint is consumed by the Streamlit app and by `curl` / `TestClient` smoke tests. The arcade replay no longer calls this endpoint — as of Phase 3.5 Proceso B (April 2026), the arcade owns its own strategy pipeline via [`src/arcade/strategy_pipeline.py`](#/arcade-strategy-pipeline).

### Metadata (GET)

| Path | Description |
|---|---|
| `/api/v1/strategy/available-gps` | GP names in the featured parquet |
| `/api/v1/strategy/available-drivers` | Driver codes for a GP |
| `/api/v1/strategy/lap-range` | Min/max lap for a driver at a GP |
| `/api/v1/strategy/lap-state` | Build canonical lap_state dict from parquet |

### Agent endpoints (POST)

| Path | Request Body | Agent | Description |
|---|---|---|---|
| `/api/v1/strategy/pace` | `PaceRequest` | N25 | Lap time prediction + CI |
| `/api/v1/strategy/pace-range` | `PaceRangeRequest` | N25 | Batch predictions over lap range |
| `/api/v1/strategy/tire` | `TireRequest` | N26 | Tire cliff estimation |
| `/api/v1/strategy/situation` | `SituationRequest` | N27 | Overtake + SC probability |
| `/api/v1/strategy/pit` | `PitRequest` | N28 | Pit duration + undercut analysis |
| `/api/v1/strategy/radio` | `RadioRequest` | N29 | NLP radio pipeline |
| `/api/v1/strategy/rag` | `RagRequest` | N30 | Regulation retrieval |
| `/api/v1/strategy/recommend` | `RecommendRequest` | N31 | Full orchestrator pipeline |

### Request schemas

```python
class PaceRequest(BaseModel):
    lap_state: Dict[str, Any]

class TireRequest(BaseModel):
    lap_state: Dict[str, Any]

class SituationRequest(BaseModel):
    lap_state: Dict[str, Any]

class PitRequest(BaseModel):
    lap_state: Dict[str, Any]

class RadioRequest(BaseModel):
    lap_state: Dict[str, Any]
    radio_msgs: List[Dict[str, Any]] = []
    rcm_events: List[Dict[str, Any]] = []

class RagRequest(BaseModel):
    question: str

class RecommendRequest(BaseModel):
    lap_state: Dict[str, Any]
    gp_name: str = ""
    year: int = 2025
    gap_ahead_s: float = 2.0
    pace_delta_s: float = 0.0
    risk_tolerance: float = 0.5
    radio_msgs: Optional[List[Dict[str, Any]]] = None
    rcm_events: Optional[List[Dict[str, Any]]] = None
```

### Response schemas

All agent endpoints return `StrategyResponse`:

```python
class StrategyResponse(BaseModel):
    agent: str       # e.g. "pace", "tire", "orchestrator"
    result: Dict[str, Any]
```

### Error handling

Strategy endpoints return structured errors:

```json
{
  "error": "ValueError",
  "agent": "pace",
  "detail": "Missing feature: compound_id"
}
```

## CORS

The backend allows requests from the frontend URL (default `http://localhost:8501`) via `CORSMiddleware`.

## Swagger / OpenAPI

Auto-generated at `http://localhost:8000/docs` when the backend is running.
