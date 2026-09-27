# draw.io diagram sources

Editable `.drawio` sources for the project's architecture diagrams. Open them with [diagrams.net](https://app.diagrams.net/) or the VS Code extension.

## Status, refreshed 2026-09-27

Several diagrams still described the 2026-05-13 architecture, before v2.0.0 retired the Streamlit frontend and voice surface and v2.1.0 rewrote the Monte Carlo decision layer. The inventory below distinguishes refreshed diagrams from retained historical assets.

| Diagram | State |
|---|---|
| `system_architecture` | updated 2026-08-26 (#1090): Surface 2's windows 2 and 3 said `Dashboard (Qt)` and `Telemetry (Qt)` over a description reading `pyglet Arcade + PySide6 dashboard`. They are the two PITWALL webview windows in one process. Surface 3 is the React web app, not Streamlit |
| `backend_api` | updated: the `/voice` router and its two endpoints removed |
| `chat_mcp_flow` | updated: voice input path removed, the chat UI is the React tab |
| `docker_deployment` | updated: `f1_webapp` on nginx, host 8501 to container 80 |
| `webapp_structure` | **new**: the React app's feature folders and how they reach the backend |
| `frontend_pages_streamlit_legacy` | **renamed and marked retired**: it is the Streamlit page tree, kept as a record of a surface that no longer exists |
| `arcade_3window_architecture_qt_legacy` | **renamed and marked retired**: it is the PySide6 pair PITWALL replaced in sprint 7. Not relabelled into the new topology, because that is not a relabel - the DATA window is not shaped like the Qt telemetry window. The live picture is the Mermaid graph in `docs/pages/multi-agent.md` |
| `multi_agent_architecture` | refreshed for #1253 as an 8-node overview of data, race context, N25-N30, N31, recommendation and delivery surfaces. Removed volatile model scores and corpus counts; N30 provides regulation context, not a universal action filter |
| `multi_agent_flow` | refreshed for #1253 to separate N25-N28 Monte Carlo distributions from N29 radio reasoning and N30 regulation context. Finite rival-gap inputs use `payoff(project_positions(rivals))`, with the legacy seconds path otherwise. The output identifies the 14-field recommendation |
| `strategy_pipeline_flow` | detailed engineering view, not a slide export; refreshed for #1253 to remove volatile benchmarks, document the conditional projection path and fallback, and replace `plan` / `guardrail_flag` with the 14-field output summary |
| `subprocess_launch_sequence` | updated 2026-08-26 (#1090): the actor columns already said PITWALL while four messages still described the Qt pair. Step 6b spawned `src.arcade.telemetry`, a module that does not exist, and step 14 sent a second TCP tick to it; `app.py:501` opens ONE subprocess and `src/pitwall/__main__.py` builds ONE `ArcadeStreamClient` for both windows, so both arrows now start at the PITWALL column. Step 7 is `PitwallHost(ArcadeStreamClient)`, and step 15's "tabs" went with the reasoning panel in #1020 |
| `tcp_broadcast_dataflow` | refreshed for #1253 as an 8-node schema-v2 view: one producer, one server, one PITWALL host, and sibling DATA / AGENTS views. It shows per-driver maps, the 30-entry `history_tail` cap without `per_agent`, and the separate `get_agents_view` contract. The retired Qt diagram remains in `arcade_3window_architecture_qt_legacy` |
| `data_pipeline` | current on the surfaces; note the FastF1 cache is one directory now, not two |
| `agents/` | one per sub-agent (N25 to N30) plus the `StrategyRecommendation` schema; N30 shows the optional season filter and unscoped fallback, while the score summary includes eligibility, target and null scores |

The related Mermaid diagrams in `docs/pages/multi-agent.md`,
`docs/pages/arcade-strategy-pipeline.md` and `docs/pages/pitwall.md` were also
checked against their live routes. The Arcade pipeline label now names the
shared engine; the pipeline page distinguishes `/recommend` from `/simulate`;
PITWALL shows DATA and AGENTS as sibling views of one stream with independent
polls.

**Fidelity ledger.** The architecture overview omits volatile model metrics and
corpus counts. The detailed pipeline preserves distribution sampling but
describes projection scoring only when finite rival gaps are available. The
wire diagram is based on [the payload producer](../../../src/arcade/app.py#L662),
[the history-tail cap](../../../src/arcade/config.py#L313), and [the AGENTS view
adapter](../../../src/pitwall/host.py#L297). The recommendation schema follows
[the public field table](../../../docs/pages/agents-api.md#L124). N28 fills
`pit_lap_target` and `compound_next` only when the LLM leaves them empty; a
supplied N28 `undercut_target` takes precedence. N30 provides
retrieved regulation evidence and context to synthesis, as shown in
[the prompt builder](../../../src/agents/strategy_orchestrator.py#L1744). The
per-agent N30 diagram follows [the season-aware RAG wrapper](../../../src/agents/rag_agent.py#L510)
and [the retrieval default](../../../src/rag/retriever.py#L67), including the
[empty-scope fallback](../../../src/rag/retriever.py#L451), rather than a
particular build's point count.

`exports/` contains current 16:9 HTML and SVG views: [architecture HTML](exports/architecture-overview.html) ·
[architecture SVG](exports/architecture-overview.svg) · [orchestrator HTML](exports/orchestrator-flow.html) ·
[orchestrator SVG](exports/orchestrator-flow.svg) · [PITWALL HTML](exports/pitwall-transport.html) ·
[PITWALL SVG](exports/pitwall-transport.svg). The editable `.drawio` files remain the sources.
`strategy_pipeline_flow` keeps its detailed engineering layout and is not used as a slide export.

The 20 editable diagrams were inventoried by parsing labels and edges, not by searching raw XML. The six files changed for #1253 were re-parsed after editing; the existing surface test still rejects live diagrams that name the retired Qt toolkit.

The three diagrams that named the retired Qt surface were redrawn in #1090, and the rule they broke is
now checked rather than asserted: `tests/surfaces/test_diagrams_no_retired_surface.py` parses the
`value=` attributes of every diagram outside the `*_legacy.drawio` files and fails on
`PySide6`, `QApplication`, `QMainWindow`, `QThread`, `pyqtSignal` or `src.arcade.telemetry`. A box
whose own label carries the word RETIRED is exempt. The Qt comparison now lives only in
`arcade_3window_architecture_qt_legacy.drawio`; the live wire diagram no longer mixes that branch
with the current payload. The test also fails a diagram that yields no labels at all, which is
what a compressed draw.io save looks like from the outside.

The check is the parse half only. Whether a diagram means what the code does still requires a
cross-check against the producer and its consumers. For example, the `multi_agent_flow` edge from
sub-agent outputs to Monte Carlo remains valid because Monte Carlo samples those distributions;
the projected position payoff is the score applied to each draw.

**How this audit is made.** Labels are parsed out of the `value=` attributes and the tab names, never grepped from the raw XML. A grep counts matches inside style attributes and colour names, which both over-reports (a file whose only hit is a colour) and under-reports (`docker_deployment`, whose defect was a container named `f1_telemetry_frontend`, containing neither search word). Each figure is then checked against the code it describes rather than against a sibling diagram, because the drift runs in both directions.

## These are not what the docs site renders

The site at docs.f1stratlab.com renders **Mermaid**, written directly into `docs/pages/*.md` as fenced code blocks. It has no draw.io renderer, so a diagram here reaches a reader only if someone exports it to SVG and embeds the image.

That split is deliberate. Mermaid is text: it diffs in review, it cannot drift out of sync with the page it sits in, and it renders live. draw.io is where a diagram goes when it needs a layout Mermaid cannot express, or when it is meant to be edited visually.

If you fix one of these, consider whether the diagram also belongs in `docs/pages/` as Mermaid. Several describe things the docs site has no diagram for.

## Also here

`site/diagrams/` at the repo root holds byte-identical copies of the pre-2026-07-26 versions. It is **not tracked by git**, being the build output of an older docs site. Do not edit it and do not treat it as a second source.
