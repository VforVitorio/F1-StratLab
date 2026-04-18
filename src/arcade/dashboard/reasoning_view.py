"""N31 reasoning view — read-only QTextEdit with the orchestrator's
structured-output ``reasoning`` string, highlighted by regex rules
mirroring the CLI's Rich rendering (see
``c:/tmp/arcade_analysis/06_cli_inference_panel.md`` §6):

- Lap references (``lap 12``, ``laps 8-10``) → pink
- Quantiles (``P10``, ``p50``, ``P90``) → magenta
- Percentages (``62%``) → yellow
- Time deltas (``+1.2s``, ``-0.47s``) → cyan
- Actions (``PIT_NOW``, ``STAY_OUT``, ``UNDERCUT``, ``OVERCUT``) → bold yellow

The highlighter runs on every ``setPlainText`` via ``QSyntaxHighlighter``'s
``rehighlight`` so callers only need to push the raw string.
"""

from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import QSizePolicy, QTextEdit

from src.arcade.dashboard.theme import (
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    hex_str,
)

# --- Highlight colours (not in theme.py because they are local to this
#     narrow highlighter; mirrors the CLI's Rich palette 1:1) ------------
_LAP_COLOR:    QColor = QColor(244, 114, 182)   # pink
_QUANT_COLOR:  QColor = QColor(217, 70, 239)    # magenta
_PCT_COLOR:    QColor = QColor(250, 204, 21)    # yellow
_DELTA_COLOR:  QColor = QColor(34, 211, 238)    # cyan
_ACTION_COLOR: QColor = QColor(250, 204, 21)    # bold yellow


class _ReasoningHighlighter(QSyntaxHighlighter):
    """Five regex rules applied in priority order. Actions are bold; the
    rest are normal weight. Rules are compiled once at construction."""

    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []

        def _fmt(colour: QColor, bold: bool = False) -> QTextCharFormat:
            f = QTextCharFormat()
            f.setForeground(colour)
            if bold:
                f.setFontWeight(QFont.Bold)
            return f

        self._rules.append((re.compile(r"\blaps?\s+\d+(?:[-–]\d+)?\b"), _fmt(_LAP_COLOR)))
        self._rules.append((re.compile(r"\b[Pp]\d{2}\b"), _fmt(_QUANT_COLOR)))
        self._rules.append((re.compile(r"\b\d+(?:\.\d+)?%"), _fmt(_PCT_COLOR)))
        self._rules.append((re.compile(r"[+\-]\d+\.\d+\s*s\b"), _fmt(_DELTA_COLOR)))
        self._rules.append((
            re.compile(r"\b(PIT_NOW|STAY_OUT|UNDERCUT|OVERCUT)\b"),
            _fmt(_ACTION_COLOR, bold=True),
        ))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class ReasoningView(QTextEdit):
    """Read-only QTextEdit with the orchestrator reasoning + highlighter."""

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(90)
        self.setMaximumHeight(180)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setStyleSheet(
            f"QTextEdit {{ background-color: transparent; "
            f"border: 1px solid {hex_str(TEXT_SECONDARY)}; border-radius: 6px; "
            f"color: {hex_str(TEXT_PRIMARY)}; padding: 8px; "
            "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; }}"
        )
        self._highlighter = _ReasoningHighlighter(self.document())

    def update_from(self, latest: dict[str, Any] | None) -> None:
        """Replace the buffer with the current reasoning string."""
        text = ""
        if latest:
            raw = str(latest.get("reasoning") or "").strip()
            # Collapse newlines and clip to ~300 chars so the card never
            # scrolls mid-race. The LLM tends to return <180 chars anyway
            # (structured-output constraint) so this is a safety cap.
            text = " ".join(raw.split())
            if len(text) > 300:
                text = text[:297] + "…"
        self.setPlainText(text)
