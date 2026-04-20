# Contributing

Short guide for anyone cloning the TFG to experiment, fix a bug, or
propose a change.

## Development setup

```bash
git clone https://github.com/VforVitorio/F1_Strat_Manager.git
cd F1_Strat_Manager
git submodule update --init --recursive     # src/telemetry/ is a submodule
uv sync                                      # installs every dependency
cp .env.example .env                         # add OPENAI_API_KEY here
```

Run once to pre-populate the data cache on first launch:

```bash
python -c "from f1_strat_manager.data_cache import ensure_setup; ensure_setup(show_progress=True)"
```

Three entry points after install (`pyproject.toml::[project.scripts]`):

| Command | What it runs |
|---|---|
| `f1-sim` | CLI strategy simulation with Rich live panel |
| `f1-arcade --strategy` | 2D replay + PySide6 dashboard + telemetry |
| `f1-streamlit` | Post-race analysis + chat UI |

## Code style

- **Classes for stateful logic, pure functions for stateless helpers.**
  One responsibility per helper; if a function passes 50 lines or mixes
  concerns, split it.
- **English only** in source, docstrings, comments, and commit
  messages.
- **Prose docstrings** explaining WHY + WHAT and what each field
  enables for downstream code. No code examples inline.
- **No floating logic at module level** — only imports, setup,
  constants. Anything else belongs inside a function or class.
- **Type hints everywhere** on public function signatures; annotate
  variables only when the type is non-obvious.
- **Comments only when the WHY is non-obvious** — hidden constraints,
  subtle invariants, workarounds. Do not narrate what well-named code
  already says.

The conventions are enforced informally by review, not by a hard
linter pipeline. `ruff` and `mypy` are configured in `pyproject.toml`
with exclusions for `legacy/`, `notebooks/`, and the submodule paths;
they exist to catch regressions, not to style-police.

## What NOT to touch

Some code carries hard rules set by the TFG author:

- **`scripts/run_simulation_cli.py`** — the TFG's PMV (first working
  CLI). Duplicate before modifying; do not refactor in-place.
- **`src/agents/` internals** — stable contract for the CLI + Streamlit
  + Arcade paths. Additive entry points are welcome (see the verbose
  variant in `src/arcade/strategy_pipeline.py`), but do not refactor
  existing ones.
- **`notebooks/**`** and **`legacy/**`** — exploration / historical
  archive, different conventions.

## Pull request checklist

- [ ] Branch off `dev` (`main` is release-only).
- [ ] `pytest tests/ -x` green.
- [ ] If you touched `src/telemetry/*`, commit inside the submodule and
      bump the submodule pointer in the parent repo.
- [ ] `ROADMAP.md` and the relevant `docs/` file updated when behaviour
      changes.
- [ ] One logical change per commit; imperative subject line; no
      co-authored trailers unless you actually pair-programmed.
- [ ] If you added a new sub-agent output, update
      `docs/agents-api-reference.md`.

## Issue templates

File an issue via the GitHub UI. Three templates are available under
[.github/ISSUE_TEMPLATE/](.github/ISSUE_TEMPLATE): bug report, feature
request, data issue.

## Related reading

- [`README.md`](README.md) — project overview.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — one-page topology.
- [`INSTALL.md`](INSTALL.md) — deep-dive install per surface.
- [`ROADMAP.md`](ROADMAP.md) — release plan and completed phases.
