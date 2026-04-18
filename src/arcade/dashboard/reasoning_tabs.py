"""Tabbed reasoning panel.

Replaces the single N31-only reasoning box with a tabbed widget:

    Orchestrator (N31) · Pace · Tire · Situation · Radio · Pit

Each tab is a read-only ``QTextEdit`` with the same regex syntax
highlighter as before (lap refs pink, quantiles magenta, percentages
yellow, time deltas cyan, action keywords bold yellow). ``update_from``
routes ``latest.reasoning`` to the Orchestrator tab and
``per_agent.<agent>.reasoning`` to the others, so users can click a tab
to read any sub-agent's narrative without hovering or opening a new
view. The RAG agent has no LLM reasoning (it retrieves regulation text
instead) so it is not surfaced here — the RAG card already shows the
retrieved snippet inline.
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
from PySide6.QtWidgets import (
    QSizePolicy,
    QTabWidget,
    QTextEdit,
)

from src.arcade.dashboard.theme import (
    ACCENT,
    BORDER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    hex_str,
)

# --- Highlight colours (mirror the CLI Rich palette) ------------------
_LAP_COLOR:    QColor = QColor(244, 114, 182)
_QUANT_COLOR:  QColor = QColor(217, 70, 239)
_PCT_COLOR:    QColor = QColor(250, 204, 21)
_DELTA_COLOR:  QColor = QColor(34, 211, 238)
_ACTION_COLOR: QColor = QColor(250, 204, 21)


class _ReasoningHighlighter(QSyntaxHighlighter):
    """Five regex rules, compiled once, reused across every tab."""

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


def _make_editor() -> QTextEdit:
    editor = QTextEdit()
    editor.setReadOnly(True)
    editor.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    editor.setLineWrapMode(QTextEdit.WidgetWidth)
    editor.setStyleSheet(
        "QTextEdit { background-color: transparent; border: none; "
        f"color: {hex_str(TEXT_PRIMARY)}; padding: 8px; "
        "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; }"
    )
    return editor


class ReasoningTabs(QTabWidget):
    """QTabWidget with one tab per reasoning source."""

    # (tab label, per_agent key or "orchestrator") — order controls tab order.
    _TABS: tuple[tuple[str, str], ...] = (
        ("Orchestrator", "orchestrator"),
        ("Pace",         "pace"),
        ("Tire",         "tire"),
        ("Situation",    "situation"),
        ("Radio",        "radio"),
        ("Pit",          "pit"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(180)
        self.setDocumentMode(True)
        border = hex_str(BORDER_COLOR)
        secondary = hex_str(TEXT_SECONDARY)
        accent = hex_str(ACCENT)
        self.setStyleSheet(
            "QTabWidget::pane { border: 1px solid " + border + "; "
            "border-radius: 6px; top: -1px; } "
            "QTabBar::tab { background: transparent; color: " + secondary + "; "
            "padding: 6px 12px; font-size: 11px; font-weight: 600; "
            "letter-spacing: 0.5px; text-transform: uppercase; } "
            "QTabBar::tab:selected { color: " + accent + "; "
            "border-bottom: 2px solid " + accent + "; }"
        )
        self._editors: dict[str, QTextEdit] = {}
        for label, key in self._TABS:
            editor = _make_editor()
            _ReasoningHighlighter(editor.document())
            self.addTab(editor, label)
            self._editors[key] = editor

    def update_from(self, latest: dict[str, Any] | None) -> None:
        """Push the N31 reasoning into the Orchestrator tab and each
        sub-agent's reasoning into its own tab.

        Sub-agents that did not produce a reasoning (conditional agent
        not fired, or missing field) get the ``"— no reasoning —"`` idle
        marker so the tab never looks broken."""
        if not latest:
            for ed in self._editors.values():
                ed.setPlainText("")
            return

        self._set_editor("orchestrator", _clean(latest.get("reasoning")))
        per = latest.get("per_agent") or {}
        for _, key in self._TABS:
            if key == "orchestrator":
                continue
            agent_out = per.get(key) or {}
            self._set_editor(key, _clean(agent_out.get("reasoning")))

    def _set_editor(self, key: str, text: str) -> None:
        editor = self._editors.get(key)
        if editor is None:
            return
        editor.setPlainText(text or "— no reasoning —")


def _clean(raw: Any) -> str:
    """Collapse newlines and truncate to 600 chars so the tab body never
    grows an internal scrollbar. 600 chars is enough for the
    structured-output LLMs we target (gpt-4.1-mini reasoning averages
    ~180 chars)."""
    if not raw:
        return ""
    text = " ".join(str(raw).split())
    if len(text) > 600:
        text = text[:597] + "…"
    return text
