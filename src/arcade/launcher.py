"""PySide6 launcher — pre-replay form that configures the Arcade viewer.

The `QtLauncher` class implemented in Phase 6 opens a small QWidget
form that collects `year`, `round`, `driver`, `team`, `driver2`, lap
range, `risk_tolerance`, `no_llm` and `provider`. On submit it spawns a
child process with `f1-arcade --viewer ...` carrying the chosen
parameters, then closes itself so the Arcade window becomes the
foreground application.

PySide6 is an optional runtime dep: the `--viewer` flag bypasses this
module entirely, so environments where Qt cannot be installed can still
use the Arcade replay directly from the command line.
"""

from __future__ import annotations
