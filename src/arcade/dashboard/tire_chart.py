"""Tire chart — tyre_life over laps + cliff projection lines.

Embedded inside the Tire N26 AgentCard (chart slot reserved in C5).
Two items on the plot:

- Actual ``tyre_life`` line coloured by compound (COMPOUND_NAMES map).
  Stint boundaries (compound changes between adjacent laps) show up as
  vertical grey InfiniteLines.
- Three horizontal InfiniteLines at ``current_lap + laps_to_cliff_p10 /
  p50 / p90``, coloured red / amber / green so the distance to the
  cliff is visible at a glance next to the actual series.

Data model (fed by ``MainWindow._tire_history``):

    [{lap: int, tyre_life: float, compound: str}, ...]

The chart keeps no state of its own — window rebuilds it on every
update. At ≤30 points per series the cost is negligible (<1 ms).
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from src.arcade.dashboard.theme import (
    BG_COLOR,
    BORDER_COLOR,
    COMPOUND_NAMES,
    DANGER,
    SUCCESS,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WARNING,
    qcolor,
)


class TireChart(pg.PlotWidget):
    """PlotWidget with tyre_life series + cliff-projection lines."""

    def __init__(self) -> None:
        super().__init__()
        self.setBackground(qcolor(BG_COLOR))
        self.setMinimumHeight(140)

        axis_pen = pg.mkPen(QColor(*BORDER_COLOR), width=1)
        for side in ("left", "bottom"):
            axis = self.getAxis(side)
            axis.setPen(axis_pen)
            axis.setTextPen(QColor(*TEXT_SECONDARY))
        self.setLabel("left", "Tyre life (laps)", color="#d1d5db")
        self.setLabel("bottom", "Lap", color="#d1d5db")
        self.getPlotItem().showGrid(x=True, y=True, alpha=0.15)
        self.getPlotItem().enableAutoRange("y", True)

        # Actual tyre_life — one PlotDataItem, colour set per update.
        self._tyre = pg.PlotDataItem(pen=pg.mkPen(QColor(*TEXT_SECONDARY), width=2))
        self.addItem(self._tyre)

        # Stint-boundary InfiniteLines are added/removed dynamically because
        # their count depends on how many compound changes the window sees.
        self._stint_lines: list[pg.InfiniteLine] = []

        # Cliff projection lines — pre-allocated at p10/p50/p90.
        self._cliff_p10 = self._make_cliff_line(DANGER)
        self._cliff_p50 = self._make_cliff_line(WARNING)
        self._cliff_p90 = self._make_cliff_line(SUCCESS)
        for ln in (self._cliff_p10, self._cliff_p50, self._cliff_p90):
            ln.setVisible(False)
            self.addItem(ln)

    def update_from(
        self,
        history: list[dict[str, Any]],
        current_lap: int | None,
        tire_out: dict[str, Any] | None,
    ) -> None:
        """Rebuild the tyre_life series + cliff lines.

        ``history`` is a chronological list of per-lap tyre snapshots.
        ``current_lap`` anchors the cliff-projection lines; ``tire_out``
        carries ``laps_to_cliff_p10/p50/p90`` from the current TireOutput.
        Missing data hides the cliff lines without clearing the series.
        """
        self._clear_stint_lines()

        if not history:
            self._tyre.setData([], [])
        else:
            xs = [float(row.get("lap", 0)) for row in history]
            ys = [float(row.get("tyre_life", 0.0)) for row in history]
            last_compound = str(history[-1].get("compound") or "MEDIUM").upper()
            colour = QColor(*COMPOUND_NAMES.get(last_compound, (200, 200, 200)))
            self._tyre.setData(xs, ys, pen=pg.mkPen(colour, width=2))

            # Vertical stint-boundary line whenever compound changes between
            # two adjacent history points.
            prev = None
            for row in history:
                comp = str(row.get("compound") or "").upper()
                if prev is not None and comp and comp != prev:
                    line = pg.InfiniteLine(
                        pos=float(row.get("lap", 0)),
                        angle=90,
                        pen=pg.mkPen(QColor(*TEXT_TERTIARY), width=1, style=Qt.DashLine),
                    )
                    self.addItem(line)
                    self._stint_lines.append(line)
                prev = comp or prev

        if current_lap is None or not tire_out:
            for ln in (self._cliff_p10, self._cliff_p50, self._cliff_p90):
                ln.setVisible(False)
            return

        cur = float(current_lap)
        for attr, ln in (
            ("laps_to_cliff_p10", self._cliff_p10),
            ("laps_to_cliff_p50", self._cliff_p50),
            ("laps_to_cliff_p90", self._cliff_p90),
        ):
            val = tire_out.get(attr)
            if val is None:
                ln.setVisible(False)
                continue
            ln.setValue(cur + float(val))
            ln.setVisible(True)

    @staticmethod
    def _make_cliff_line(rgb: tuple[int, int, int]) -> pg.InfiniteLine:
        colour = QColor(*rgb)
        colour.setAlpha(180)
        return pg.InfiniteLine(
            pos=0.0,
            angle=90,
            pen=pg.mkPen(colour, width=2, style=Qt.DotLine),
        )

    def _clear_stint_lines(self) -> None:
        for ln in self._stint_lines:
            self.removeItem(ln)
        self._stint_lines.clear()
