"""Dashboard entry point: ``python -m src.arcade.dashboard``.

Spawned as a subprocess by ``F1ArcadeView._init_strategy_layer`` once
that wiring lands (commit 8) but fully runnable standalone during
development — connect to any arcade replay listening on the stream
host/port (``F1_STREAM_HOST`` / ``F1_STREAM_PORT`` env overrides
supported) and the window populates from there.
"""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from src.arcade.dashboard.theme import apply_dark_palette
from src.arcade.dashboard.window import MainWindow


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("F1 Strategy Dashboard")
    apply_dark_palette(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
