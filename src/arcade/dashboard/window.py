"""Main dashboard window.

Subscribes to the arcade telemetry stream and routes updates to three
areas:

- Header bar (top, 40 px) — session label, driver, connection chip,
  playback chip, lap counter. Populated from ``arcade`` + ``strategy.start``
  + ``playback`` keys of each broadcast.
- Central ``QSplitter(Qt.Horizontal)`` — two content panels that future
  commits fill with the orchestrator card, the six sub-agent cards,
  charts, alerts feed and reasoning view.
- Status bar (bottom) — last error from the stream, last payload size.

The scaffold deliberately leaves the content panels empty so later
commits can add widgets one at a time without touching the window
class.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.arcade.dashboard.stream_client import TelemetryStreamClient
from src.arcade.dashboard.theme import (
    DANGER,
    SUCCESS,
    TEXT_SECONDARY,
    WARNING,
    hex_str,
)

logger = logging.getLogger(__name__)


class HeaderBar(QWidget):
    """Top 40 px strip: session · driver · conn · playback · lap counter."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedHeight(44)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(10)

        self._session = QLabel("--")
        self._session.setStyleSheet("font-size: 14px; font-weight: 600;")
        self._driver = QLabel("--")
        self._driver.setStyleSheet(
            f"color: {hex_str(TEXT_SECONDARY)}; font-size: 13px;"
        )
        self._conn = QLabel("Disconnected")
        self._conn.setObjectName("chip")
        self._playback = QLabel("-- × · --")
        self._playback.setObjectName("chip")
        self._lap = QLabel("L 0/0")
        self._lap.setObjectName("chip")

        layout.addWidget(self._session)
        layout.addSpacing(6)
        layout.addWidget(self._driver)
        layout.addStretch()
        layout.addWidget(self._conn)
        layout.addWidget(self._playback)
        layout.addWidget(self._lap)

    def update_from(self, data: dict[str, Any]) -> None:
        arcade = data.get("arcade") or {}
        strategy = data.get("strategy") or {}
        playback = data.get("playback") or {}
        start = strategy.get("start") or {}

        gp = start.get("gp") or arcade.get("gp_name") or "--"
        year = start.get("year") or arcade.get("year") or "--"
        self._session.setText(f"{gp} · {year}")
        self._driver.setText(str(start.get("driver") or arcade.get("driver_main") or "--"))

        lap = arcade.get("lap", 0)
        total = arcade.get("total_laps", 0)
        self._lap.setText(f"L {lap}/{total}")

        try:
            speed = float(playback.get("speed", 1.0))
        except (TypeError, ValueError):
            speed = 1.0
        paused = bool(playback.get("paused", False))
        self._playback.setText(f"{speed:.2f}× · {'PAUSED' if paused else 'PLAYING'}")

    def set_connection(self, status: str) -> None:
        self._conn.setText(status)
        color = {
            "Connected":    hex_str(SUCCESS),
            "Connecting...": hex_str(WARNING),
            "Disconnected": hex_str(DANGER),
        }.get(status, hex_str(TEXT_SECONDARY))
        self._conn.setStyleSheet(
            f"color: {color}; font-weight: 600; padding: 2px 10px; "
            f"border-radius: 10px; font-size: 11px;"
        )


class MainWindow(QMainWindow):
    """Dashboard shell with header + QSplitter + status bar.

    Placeholder widgets in the left / right panels expose a stable public
    API (``set_left_content`` / ``set_right_content``) that later commits
    use to inject the orchestrator card, agent grid and charts without
    having to touch this class.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("F1 Strategy Dashboard")
        self.resize(1280, 720)

        self._header = HeaderBar()

        self._left_host  = QWidget()
        self._right_host = QWidget()
        self._left_layout  = QVBoxLayout(self._left_host)
        self._right_layout = QVBoxLayout(self._right_host)
        for lay in (self._left_layout, self._right_layout):
            lay.setContentsMargins(10, 10, 10, 10)
            lay.setSpacing(8)

        self._left_placeholder  = QLabel("Orchestrator · scenarios · reasoning · alerts")
        self._right_placeholder = QLabel("Agent cards · charts")
        for lbl in (self._left_placeholder, self._right_placeholder):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                f"color: {hex_str(TEXT_SECONDARY)}; font-style: italic;"
            )
            lbl.setWordWrap(True)
        self._left_layout.addWidget(self._left_placeholder)
        self._right_layout.addWidget(self._right_placeholder)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._left_host)
        splitter.addWidget(self._right_host)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([540, 740])
        splitter.setHandleWidth(2)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._header)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)

        self.statusBar().showMessage("Waiting for arcade stream…")

        self._client = TelemetryStreamClient()
        self._client.data_received.connect(self._on_data)
        self._client.connection_status.connect(self._on_conn_status)
        self._client.error_occurred.connect(self._on_error)
        self._client.start()

    def _on_data(self, data: dict[str, Any]) -> None:
        """Router for incoming broadcasts — fans out to widgets."""
        self._header.update_from(data)
        # Later commits: call orchestrator_card.update(...), agent_cards...
        strategy = data.get("strategy") or {}
        err = strategy.get("error")
        if err:
            self.statusBar().showMessage(f"backend: {err}")
        else:
            lap = (data.get("arcade") or {}).get("lap", "?")
            self.statusBar().showMessage(f"lap {lap} · streaming", 1500)

    def _on_conn_status(self, status: str) -> None:
        self._header.set_connection(status)
        if status == "Connected":
            self.statusBar().showMessage("Stream connected", 2000)

    def _on_error(self, msg: str) -> None:
        self.statusBar().showMessage(msg, 4000)
        logger.warning(msg)

    def closeEvent(self, event: QCloseEvent) -> None:
        """Stop the client thread cleanly before the window dies."""
        if self._client.isRunning():
            self._client.stop()
            self._client.wait(2000)
        event.accept()
