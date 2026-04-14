# Frontend Documentation (Streamlit)

## Overview

The frontend is a multi-page Streamlit application at `src/telemetry/frontend/`. It communicates with the FastAPI backend via HTTP and renders telemetry visualizations, strategy recommendations, driver comparisons, and a chat interface.

Entry point: `frontend/app/main.py`.

## Page Map

| Page | File | Description |
|---|---|---|
| Dashboard | `pages/dashboard.py` | Telemetry charts for selected session/driver |
| Comparison | `pages/comparison.py` | Side-by-side telemetry for two drivers |
| Race Analysis | `pages/race_analysis.py` | Tire, gap, and radio analysis tabs |
| Strategy | `pages/strategy.py` | N25--N31 strategy advisor with agent tabs |
| Chat | `pages/chat.py` | LM Studio chat interface |
| Model Lab | `pages/model_lab.py` | Interactive ML model exploration |

## Directory Structure

```
frontend/
  app/
    main.py            -- Streamlit entry point, page routing, auth check
    setup_path.py      -- sys.path configuration
    styles.py          -- GLOBAL_CSS constant
    track_data.py      -- Track metadata
  pages/               -- One file per page
  components/
    auth/              -- Login form
    chatbot/           -- Chat UI components (history, input, message, sidebar,
                          tool_result_renderer, chart_builders)
    common/            -- Shared: driver_colors, chart_styles, loading, data_selectors
    comparison/        -- Driver comparison charts (+ legacy/ subfolder)
    dashboard/         -- Dashboard-specific CSS and selectors
    layout/            -- Navbar
    race_analysis/     -- Tire charts, gap charts, radio panel
    strategy/          -- Strategy card, scenario chart, agent tabs
    streamlit_audio_viz/ -- Custom React component for audio visualization
    telemetry/         -- Individual telemetry graphs (speed, brake, DRS, etc.)
    voice/             -- Voice input UI
  services/
    auth_service.py    -- Authentication HTTP client
    chat_service.py    -- Chat HTTP client
    strategy_service.py -- Strategy endpoints HTTP client
    telemetry_service.py -- Telemetry HTTP client
    voice_api.py       -- Voice HTTP client
  utils/
    audio_utils.py     -- Audio processing helpers
    chat_navigation.py -- Chat page navigation state
    chat_state.py      -- Chat session state management
    data_loaders.py    -- Data loading utilities
    race_processing.py -- Race data transformations
    race_viz.py        -- Race visualization helpers
    report_storage.py  -- Report persistence
    time_formatters.py -- Lap time formatting
  shared/
    img/               -- Static image assets
  config.py            -- BACKEND_URL, API_BASE_URL from env vars
```

## Authentication

The app uses a simple session-state authentication gate. When `st.session_state['authenticated']` is False, `render_auth_form()` is shown. After login, the navbar and page router are displayed.

## Navigation

Page routing uses `st.session_state['current_page']`. The navbar (`components/layout/navbar.py`) sets this value. Pages are rendered conditionally in `main.py`.

## Strategy Page

The Strategy page (`pages/strategy.py`) is the primary interface for the N25--N31 agent system:

1. **Selectors**: Year (hardcoded 2025), GP, Driver, Lap range, Analysis lap, Risk tolerance
2. **Run button**: calls `StrategyService.get_recommend()` which hits `/api/v1/strategy/recommend`
3. **Results**:
   - `render_strategy_card()` -- recommendation card with action, confidence, reasoning
   - `render_scenario_chart()` -- bar chart comparing MC scenario scores
   - `render_agent_tabs()` -- tabbed detail view for each sub-agent output

## Chat Tool-Result Rendering

The Chat page (`pages/chat.py`) consumes the MCP-style tool results returned by `/api/v1/chat/query`. Each tool result carries a `display_type` hint (see `TOOL_DISPLAY_MAP` in `src/telemetry/backend/models/tool_schemas.py`) that tells the frontend how to render the payload.

Dispatch lives in `components/chatbot/tool_result_renderer.py`:

```python
_RENDERERS = {
    "metrics":        _render_metrics,
    "strategy_card":  _render_strategy_card,
    "table":          _render_table,
    "text":           _render_text,
    "chart":          _render_chart,
}
```

### Inline Plotly charts (Phase 2 MCP telemetry tools)

The four telemetry tools (`get_lap_times`, `get_telemetry`, `compare_drivers`, `get_race_data`) are mapped to `DisplayType.CHART` and render as inline Plotly figures inside the chat bubble. `_render_chart(data, tool_name)` calls `build_figure(tool_name, data)` from `components/chatbot/chart_builders.py`, which dispatches to one of:

| Tool | Builder | Figure |
|---|---|---|
| `get_lap_times` | `build_lap_times_figure` | Lap-time line per driver |
| `get_telemetry` | `build_telemetry_figure` | Speed / throttle / brake traces for one lap |
| `compare_drivers` | `build_compare_drivers_figure` | Fastest-lap side-by-side comparison |
| `get_race_data` | `build_race_data_figure` | Full race overview (positions / gaps) |

Builders are Streamlit-free: they take the raw tool payload, pull per-driver colors via `get_driver_color` from `components/common/driver_colors.py`, and apply the shared dark theme through `_apply_base_layout()`. The renderer wraps the figure with `apply_telemetry_chart_styles()` so the chart inherits the purple-outlined chat bubble look, and falls back to `_render_text` if the builder returns `None` (unknown tool or malformed payload).

On the backend, `_execute_telemetry_tool` in `services/chatbot/handlers/strategy_handler.py` no longer mutates or trims the raw tool response; a separate `_trim_for_llm(raw)` static helper produces a 20-record-capped shallow copy that is passed only to the LLM summariser. The full payload is forwarded to the UI via `tool_result.data`, which is what enables the chart builders to plot complete series rather than a truncated LLM-view sample. As a side effect, the previous `compare_drivers` "N/A" rendering bug disappears because `_render_chart` reads `data.pilot1.lap_time` / `data.pilot2.lap_time` directly from the untrimmed payload.

## Services Layer

All HTTP calls go through service classes in `services/`. Each method returns a `(success: bool, data: dict | None, error: str | None)` triple so callers handle results consistently.

```python
class StrategyService:
    @staticmethod
    def get_pace(lap_state) -> Tuple[bool, Optional[Dict], Optional[str]]: ...
    @staticmethod
    def get_tire(lap_state) -> Tuple[bool, Optional[Dict], Optional[str]]: ...
    @staticmethod
    def get_recommend(...) -> Tuple[bool, Optional[Dict], Optional[str]]: ...
    # ... etc.
```

Timeout is set to 300 seconds because first-call model loading (RoBERTa + SetFit + BERT-large + BGE-M3) is slow.

## Configuration

Environment variables read by the frontend:

| Variable | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | FastAPI backend base URL |
| `FRONTEND_URL` | `http://localhost:8501` | Frontend self-reference |
