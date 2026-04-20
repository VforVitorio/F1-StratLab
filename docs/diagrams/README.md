# `docs/diagrams/` — draw.io sources

Architecture and data-flow diagrams for the F1 Strategy Manager TFG.
Open any `.drawio` file with [draw.io desktop](https://www.drawio.com/)
or [diagrams.net](https://app.diagrams.net/). The same files render as
PNG on demand via `File → Export as → PNG` inside the editor.

| File | What it shows | Related doc |
|---|---|---|
| [`arcade_3window_architecture.drawio`](arcade_3window_architecture.drawio) | Three windows spawned by `f1-arcade --strategy`: pyglet replay, PySide6 strategy dashboard, PySide6 live telemetry. Arrows mark the TCP broadcast on `127.0.0.1:9998` and the `subprocess.Popen` spawn. | [`docs/arcade/dashboard.md`](../arcade/dashboard.md) |
| [`strategy_pipeline_flow.drawio`](strategy_pipeline_flow.drawio) | N31 orchestrator three layers — always-on sub-agents (N25/26/27/29), routing diamond, conditional agents (N28/30), Monte Carlo simulation, LLM synthesis. | [`docs/architecture.md`](../architecture.md) |
| [`tcp_broadcast_dataflow.drawio`](tcp_broadcast_dataflow.drawio) | Six-step data flow from FastF1 load → SessionLoader → pipeline → broadcast → two Qt subscribers. JSON payload shape inset. | [`docs/arcade/dashboard.md`](../arcade/dashboard.md) |
| [`system_architecture.drawio`](system_architecture.drawio) | Top-level map: CLI · Arcade · Streamlit surfaces over the shared agents, replay engine, and data tree. LLM provider block flags OpenAI / LM Studio / never Anthropic. | [`README.md`](../../README.md) |
| [`subprocess_launch_sequence.drawio`](subprocess_launch_sequence.drawio) | UML sequence from `python -m src.arcade.main --strategy` through session load → strategy driver warmup → replay loop → 10 Hz broadcast. | [`docs/arcade/quick-start.md`](../arcade/quick-start.md) |
| [`multi_agent_flow.drawio`](multi_agent_flow.drawio) | Predates Phase 3.5 — multi-agent flow at the FastAPI layer. | [`docs/architecture.md`](../architecture.md) |
| [`backend_api.drawio`](backend_api.drawio) | FastAPI route + router layout. | [`docs/backend-api.md`](../backend-api.md) |
| [`chat_mcp_flow.drawio`](chat_mcp_flow.drawio) | Chat endpoint + FastMCP tool exposure. | [`docs/backend-api.md`](../backend-api.md) |
| [`data_pipeline.drawio`](data_pipeline.drawio) | Raw data → processed parquets → model training. | Notebook N01-N04 |
| [`docker_deployment.drawio`](docker_deployment.drawio) | Docker Compose for backend + frontend (Streamlit path only). | [`INSTALL.md`](../../INSTALL.md) |
| [`frontend_pages.drawio`](frontend_pages.drawio) | Streamlit page tree + components layout. | [`docs/streamlit-frontend.md`](../streamlit-frontend.md) |
