"""Live telemetry panel — speed / throttle / brake / DRS / gear for the
main driver, updated at the broadcast rate (~10 Hz).

Two halves side by side:

- Left: an F1-broadcast-style numeric HUD with SPD kph, THR %, BRK %,
  GEAR, DRS on/off. Updated each broadcast, no accumulation.
- Right: a pyqtgraph ``PlotWidget`` with three traces plotted over
  ``dist`` (metres, 0 → circuit length): speed in km/h (INFO blue),
  throttle in % (SUCCESS green), brake in % (DANGER red). A buffer
  keyed by ``(lap, dist_bucket)`` drops old samples when the lap
  changes so the chart always shows the ongoing lap only.

The broadcast payload adds ``arcade.telemetry`` — ``update_from`` reads
that block directly. Missing fields collapse gracefully to an idle
state (empty chart, dashes in the HUD).
"""

from __future__ import annotations

from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
)

from src.arcade.dashboard.theme import (
    ACCENT,
    BG_COLOR,
    BORDER_COLOR,
    DANGER,
    INFO,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    hex_str,
    qcolor,
)


class TelemetryPanel(QFrame):
    """Numeric HUD + live speed/throttle/brake chart for the main driver."""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(160)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(14)

        # --- Left: numeric HUD ------------------------------------------
        hud = QFrame()
        hud.setFixedWidth(200)
        hud_lay = QVBoxLayout(hud)
        hud_lay.setContentsMargins(0, 0, 0, 0)
        hud_lay.setSpacing(4)

        title = QLabel("LIVE TELEMETRY")
        title.setStyleSheet(
            f"color: {hex_str(TEXT_SECONDARY)}; font-size: 11px; "
            "font-weight: 700; letter-spacing: 1px;"
        )
        hud_lay.addWidget(title)

        self._spd = self._make_metric("SPD", "— kph", INFO)
        self._thr = self._make_metric("THR", "—%",   SUCCESS)
        self._brk = self._make_metric("BRK", "—%",   DANGER)
        gear_row = QHBoxLayout()
        gear_row.setSpacing(12)
        self._gear = self._make_metric("GEAR", "—", TEXT_PRIMARY)
        self._drs  = self._make_metric("DRS",  "OFF", TEXT_TERTIARY)
        gear_row.addWidget(self._gear)
        gear_row.addWidget(self._drs)
        gear_row.addStretch()

        for w in (self._spd, self._thr, self._brk):
            hud_lay.addWidget(w)
        hud_lay.addLayout(gear_row)
        hud_lay.addStretch()
        outer.addWidget(hud)

        # --- Right: chart ----------------------------------------------
        self._plot = pg.PlotWidget()
        self._plot.setBackground(qcolor(BG_COLOR))
        axis_pen = pg.mkPen(QColor(*BORDER_COLOR), width=1)
        for side in ("left", "bottom"):
            axis = self._plot.getAxis(side)
            axis.setPen(axis_pen)
            axis.setTextPen(QColor(*TEXT_SECONDARY))
        self._plot.setLabel("bottom", "Distance (m)", color="#d1d5db")
        self._plot.getPlotItem().showGrid(x=True, y=True, alpha=0.15)
        self._plot.setYRange(0, 320)   # kph upper bound for speed trace

        self._speed_line = pg.PlotDataItem(pen=pg.mkPen(QColor(*INFO), width=2))
        self._thr_line   = pg.PlotDataItem(pen=pg.mkPen(QColor(*SUCCESS), width=1))
        self._brk_line   = pg.PlotDataItem(pen=pg.mkPen(QColor(*DANGER), width=1))
        self._plot.addItem(self._speed_line)
        self._plot.addItem(self._thr_line)
        self._plot.addItem(self._brk_line)
        outer.addWidget(self._plot, 1)

        # --- Sample buffer ---------------------------------------------
        # Keyed by ``dist_bucket`` so duplicate frames (arcade rewinds,
        # paused state) overwrite the sample instead of piling up.
        self._current_lap: int | None = None
        self._buffer: dict[int, tuple[float, float, float]] = {}

    def update_from(self, telemetry: dict[str, Any] | None) -> None:
        if not telemetry:
            self._set_idle()
            return
        lap = telemetry.get("lap")
        dist = telemetry.get("dist")
        speed = telemetry.get("speed")
        throttle = telemetry.get("throttle")
        brake = telemetry.get("brake")
        gear = telemetry.get("gear")
        drs = telemetry.get("drs")

        # HUD
        self._set_metric(self._spd, f"{speed:.0f} kph" if speed is not None else "— kph")
        self._set_metric(
            self._thr,
            f"{throttle * 100:.0f}%" if throttle is not None else "—%",
        )
        self._set_metric(
            self._brk,
            f"{brake * 100:.0f}%" if brake is not None else "—%",
        )
        self._set_metric(self._gear, str(gear) if gear is not None else "—")
        drs_on = bool(drs)
        self._set_metric(self._drs, "ON" if drs_on else "OFF")
        self._drs.findChild(QLabel, "value").setStyleSheet(
            f"color: {hex_str(SUCCESS if drs_on else TEXT_TERTIARY)}; "
            "font-size: 18px; font-weight: 800;"
        )

        # Chart
        if lap is None or dist is None or speed is None:
            return
        if lap != self._current_lap:
            self._current_lap = lap
            self._buffer.clear()
        self._buffer[int(dist)] = (
            float(speed),
            float(throttle or 0.0) * 100.0,
            float(brake or 0.0) * 100.0,
        )
        xs = sorted(self._buffer.keys())
        spd = [self._buffer[x][0] for x in xs]
        thr = [self._buffer[x][1] for x in xs]
        brk = [self._buffer[x][2] for x in xs]
        self._speed_line.setData(xs, spd)
        self._thr_line.setData(xs, thr)
        self._brk_line.setData(xs, brk)

    # --- HUD helpers -------------------------------------------------

    @staticmethod
    def _make_metric(label: str, initial: str, rgb: tuple[int, int, int]) -> QFrame:
        host = QFrame()
        host.setStyleSheet("QFrame { background: transparent; }")
        lay = QHBoxLayout(host)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {hex_str(TEXT_TERTIARY)}; font-size: 11px; "
            "font-weight: 600; letter-spacing: 1px;"
        )
        lbl.setFixedWidth(40)
        value = QLabel(initial)
        value.setObjectName("value")
        value.setStyleSheet(
            f"color: {hex_str(rgb)}; font-size: 18px; font-weight: 800;"
        )
        lay.addWidget(lbl)
        lay.addWidget(value, 1)
        return host

    @staticmethod
    def _set_metric(host: QFrame, value_text: str) -> None:
        lbl = host.findChild(QLabel, "value")
        if lbl is not None:
            lbl.setText(value_text)

    def _set_idle(self) -> None:
        self._set_metric(self._spd, "— kph")
        self._set_metric(self._thr, "—%")
        self._set_metric(self._brk, "—%")
        self._set_metric(self._gear, "—")
        self._set_metric(self._drs, "OFF")
        self._speed_line.setData([], [])
        self._thr_line.setData([], [])
        self._brk_line.setData([], [])
        self._buffer.clear()
        self._current_lap = None
