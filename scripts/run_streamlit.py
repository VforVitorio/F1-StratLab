"""``f1-streamlit`` console script wrapper.

Exposed via ``[project.scripts]`` in ``pyproject.toml`` so a
``uv tool install`` of the repo gives the user a single-command launcher
for the Streamlit post-race UI alongside ``f1-sim`` (CLI) and
``f1-arcade`` (race replay + PySide6 dashboards).

Running this module delegates to the bundled ``streamlit`` binary via
``python -m streamlit``, pointing at the canonical ``src/telemetry/frontend/app/main.py``.
Extra CLI arguments are forwarded verbatim (``--server.port``,
``--server.headless``, etc.) so existing streamlit knobs keep working.
"""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Launch the Streamlit post-race app with ``python -m streamlit``.

    Resolves the entrypoint relative to this file so the wrapper is
    location-independent — it works whether the package was installed
    via ``uv tool install`` (site-packages path) or run from a source
    checkout. Propagates the child process's exit code."""
    app_path = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "telemetry"
        / "frontend"
        / "app"
        / "main.py"
    )
    if not app_path.exists():
        print(
            f"f1-streamlit: cannot find Streamlit entrypoint at {app_path} — "
            "ensure the package was installed with the frontend assets.",
            file=sys.stderr,
        )
        return 2

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), *sys.argv[1:]]
    print(f"$ {' '.join(shlex.quote(arg) for arg in cmd)}", file=sys.stderr)
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
