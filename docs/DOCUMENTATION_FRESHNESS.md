# Documentation freshness queue

Updated 2026-09-09 during the telemetry dependency migration.

This register separates live instructions from historical migration material.
The live entries must be updated before starting new feature work. Historical
entries stay available for provenance, but must not be used as current setup
instructions.

## Live documentation updated in this worktree

| File | Finding addressed |
| --- | --- |
| `docs/pages/setup.md` | Docker now documents Python 3.11, the pinned uv binary, the frozen dependency layer, CPU PyTorch on Linux, and writable cache mounts. |
| `docs/pages/ci-cd.md` | The parent and telemetry CI workflows are now described separately, including the lightweight uv group. |
| `docs/llms.txt` | React is now the active post-race webapp and Streamlit is marked as legacy. |
| `src/telemetry/README.md` | Versions and local commands now match `pyproject.toml`, `uv.lock`, and the current runtime. |
| `src/telemetry/webapp/README.md` | The current `webapp/` directory and port 8501 are documented. |
| `src/telemetry/docs/instructions/INSTALL_INSTRUCTIONS.md` | The retired voice and pip guide was replaced with the current uv-based setup. |

## Historical documentation to label and retain

| File or area | Reason |
| --- | --- |
| `src/telemetry/docs/telemetry-architecture.md` | Describes the pre-cutover Streamlit architecture and old repository tree. |
| `src/telemetry/docs/multimodal-implementation.md` | Contains the former Streamlit execution path. |
| `src/telemetry/docs/audits/AUDIT_P1_BACKEND.md` | Snapshot audit from July 2026. Its packaging findings are superseded by this migration. |
| `src/telemetry/docs/migration/**` | Migration decisions and design history. Preserve the original claims and dates. |
| `src/telemetry/docs/archived/**` | Archived implementation plans. Do not convert them into live instructions. |

## Validation gate

After the live pages are updated, search again for active references to
`pip install`, `openai-whisper`, the removed `frontend/` tree, and the old
backend Docker flow. Any remaining match must either be current or explicitly
inside a historical document.
