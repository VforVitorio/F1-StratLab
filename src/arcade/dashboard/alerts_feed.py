"""Alerts feed — the last 10 ``agent_alerts`` entries with severity colour.

Each broadcast's ``latest.agent_alerts`` is a ``list[str]`` of intent
tags the Radio agent flagged on the current lap (``PROBLEM``,
``SAFETY_CAR``, ``VSC``, …). We cannot tell upstream whether a tag is
"new" vs "still firing", so we gate on ``(lap_number, tag)`` tuples —
if we already logged this pair we skip it, preventing a PROBLEM radio
spamming the list for every broadcast of the same lap.

Severity maps to the theme's DANGER/WARNING/INFO triad; unknown tags
fall through to TEXT_SECONDARY.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QSizePolicy

from src.arcade.dashboard.theme import (
    DANGER,
    INFO,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING,
    hex_str,
    severity_color,
)


class AlertsFeed(QListWidget):
    """Scroll-at-bottom list of the last 10 unique (lap, tag) alerts."""

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(110)
        self.setMaximumHeight(200)
        self.setStyleSheet(
            f"QListWidget {{ background-color: transparent; "
            f"border: 1px solid {hex_str(TEXT_SECONDARY)}; border-radius: 6px; "
            f"color: {hex_str(TEXT_PRIMARY)}; font-size: 11px; padding: 4px; }} "
            "QListWidget::item { padding: 3px 6px; border-radius: 4px; margin: 1px 0; } "
            "QListWidget::item:selected { background-color: rgba(167, 139, 250, 60); }"
        )
        self._seen: set[tuple[int, str]] = set()
        self._buffer: deque[tuple[int, str]] = deque(maxlen=10)

    def update_from(self, latest: dict[str, Any] | None) -> None:
        """Append any unseen (lap, tag) pairs from ``latest.agent_alerts``."""
        if not latest:
            return
        lap = latest.get("lap_number")
        if not isinstance(lap, int):
            return
        tags = latest.get("agent_alerts") or []
        if not tags:
            return
        for tag in tags:
            key = (lap, str(tag).upper())
            if key in self._seen:
                continue
            self._seen.add(key)
            self._buffer.append(key)
            self._append_row(lap, str(tag))
        # Evict rows above maxlen so the QListWidget mirrors the deque.
        while self.count() > self._buffer.maxlen:
            self.takeItem(0)
        self.scrollToBottom()

    def _append_row(self, lap: int, tag: str) -> None:
        label = tag.upper()
        colour = severity_color([label])
        item = QListWidgetItem(f"L{lap:>2}  {label}")
        item.setForeground(QBrush(QColor(*colour)))
        self.addItem(item)
