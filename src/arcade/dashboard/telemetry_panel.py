"""Live telemetry panel — 2×2 grid of pyqtgraph charts.

Layout mirrors the Streamlit "circuit comparison" page:

    ┌────────────────────┬────────────────────┐
    │ Delta Time         │ Speed              │
    │ (only 2-driver)    │ (main + rival)     │
    ├────────────────────┼────────────────────┤
    │ Brake Pressure     │ Throttle           │
    │ (main + rival)     │ (main + rival)     │
    └────────────────────┴────────────────────┘

Traces per chart:
- Main driver — INFO blue, solid, always present.
- Rival driver — WARNING amber, solid, only in two-driver mode.
- Delta (top-left) — ACCENT purple, main_t minus rival_t interpolated
  onto a common distance grid. Collapses to a placeholder text label
  when the arcade reports no rival.

All charts use X = distance (m) within the current lap. A per-lap
buffer drops old samples on lap change so each chart only shows the
ongoing lap. Speed is in km/h, throttle/brake in 0-100 % (normalised
upstream in ``_frame_to_telemetry``).
"""

from __future__ import annotations

import bisect
from typing import Any

import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
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
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WARNING,
    hex_str,
    qcolor,
)

# --- Sample buffer ------------------------------------------------------

# Keys are integer distance metres (bucket size 1 m) so duplicate frames
# from paused / rewind states overwrite instead of piling up.
Bucket = dict[int, tuple[float, float, float, float]]
# Order: (t, speed, throttle, brake)

_BUCKET_T, _BUCKET_S, _BUCKET_TH, _BUCKET_BR = 0, 1, 2, 3


class TelemetryPanel(QFrame):
    """2×2 pyqtgraph grid driven by ``{main, rival}`` telemetry blocks."""

    def __init__(self) -> None:
        super().__init__()
        self.setProperty("card", True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        grid = QGridLayout(self)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)

        self._delta_plot, self._delta_main, self._delta_rival = \
            self._make_plot("Δ Time (s)", ACCENT, second_trace_color=WARNING)
        # Delta has a single purple trace (main − rival) — hide the
        # second trace added by ``_make_plot`` and rebuild as a single
        # series managed separately.
        self._delta_plot.removeItem(self._delta_rival)
        self._delta_rival = None
        self._delta_placeholder = QLabel("single-driver mode")
        self._delta_placeholder.setAlignment(Qt.AlignCenter)
        self._delta_placeholder.setStyleSheet(
            f"color: {hex_str(TEXT_TERTIARY)}; font-style: italic; font-size: 12px;"
        )
        self._delta_placeholder.hide()
        delta_host = QFrame()
        delta_lay = QVBoxLayout(delta_host)
        delta_lay.setContentsMargins(0, 0, 0, 0)
        delta_lay.addWidget(self._delta_plot)
        delta_lay.addWidget(self._delta_placeholder)

        self._speed_plot,    self._speed_main,    self._speed_rival    = \
            self._make_plot("Speed (km/h)", INFO, second_trace_color=WARNING)
        self._brake_plot,    self._brake_main,    self._brake_rival    = \
            self._make_plot("Brake (%)", DANGER, second_trace_color=WARNING)
        self._throttle_plot, self._throttle_main, self._throttle_rival = \
            self._make_plot("Throttle (%)", SUCCESS, second_trace_color=WARNING)

        grid.addWidget(delta_host,           0, 0)
        grid.addWidget(self._speed_plot,     0, 1)
        grid.addWidget(self._brake_plot,     1, 0)
        grid.addWidget(self._throttle_plot,  1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)

        # Per-lap buffers keyed by driver role.
        self._main_buffer: Bucket = {}
        self._rival_buffer: Bucket = {}
        self._current_lap: int | None = None

    # --- Public update slot -----------------------------------------

    def update_from(self, telemetry: dict[str, Any] | None) -> None:
        """Ingest the ``{main, rival}`` block and refresh the four charts."""
        if not telemetry:
            self._reset()
            return
        main = telemetry.get("main")
        rival = telemetry.get("rival")
        if not main:
            self._reset()
            return

        lap = int(main.get("lap") or 0)
        if lap != self._current_lap:
            self._current_lap = lap
            self._main_buffer.clear()
            self._rival_buffer.clear()

        self._append(self._main_buffer, main)
        if rival:
            self._append(self._rival_buffer, rival)

        self._refresh_speed_brake_throttle()
        self._refresh_delta(has_rival=bool(rival))

    # --- Buffer ingestion -------------------------------------------

    @staticmethod
    def _append(buffer: Bucket, sample: dict[str, Any]) -> None:
        dist = sample.get("dist")
        if dist is None:
            return
        try:
            key = int(float(dist))
        except (TypeError, ValueError):
            return
        buffer[key] = (
            float(sample.get("t", 0.0) or 0.0),
            float(sample.get("speed", 0.0) or 0.0),
            float(sample.get("throttle", 0.0) or 0.0),
            float(sample.get("brake", 0.0) or 0.0),
        )

    # --- Chart refresh ----------------------------------------------

    def _refresh_speed_brake_throttle(self) -> None:
        main_xs, main_rows = self._sorted(self._main_buffer)
        rival_xs, rival_rows = self._sorted(self._rival_buffer)

        self._speed_main.setData(main_xs, [r[_BUCKET_S] for r in main_rows])
        self._brake_main.setData(main_xs, [r[_BUCKET_BR] for r in main_rows])
        self._throttle_main.setData(main_xs, [r[_BUCKET_TH] for r in main_rows])

        if rival_xs:
            self._speed_rival.setData(rival_xs, [r[_BUCKET_S] for r in rival_rows])
            self._brake_rival.setData(rival_xs, [r[_BUCKET_BR] for r in rival_rows])
            self._throttle_rival.setData(
                rival_xs, [r[_BUCKET_TH] for r in rival_rows]
            )
            for line in (self._speed_rival, self._brake_rival, self._throttle_rival):
                line.setVisible(True)
        else:
            for line in (self._speed_rival, self._brake_rival, self._throttle_rival):
                line.setVisible(False)

    def _refresh_delta(self, has_rival: bool) -> None:
        if not has_rival:
            self._delta_plot.hide()
            self._delta_placeholder.show()
            return
        self._delta_placeholder.hide()
        self._delta_plot.show()

        # Interpolate rival time onto main's distance grid; delta =
        # t_main − t_rival. Positive means main is behind (slower).
        main_xs, main_rows = self._sorted(self._main_buffer)
        rival_xs, rival_rows = self._sorted(self._rival_buffer)
        if len(main_xs) < 2 or len(rival_xs) < 2:
            self._delta_main.setData([], [])
            return
        rival_t_series = [r[_BUCKET_T] for r in rival_rows]
        deltas: list[float] = []
        xs_out: list[float] = []
        for i, x in enumerate(main_xs):
            interp = _lerp_sorted(rival_xs, rival_t_series, x)
            if interp is None:
                continue
            deltas.append(main_rows[i][_BUCKET_T] - interp)
            xs_out.append(x)
        self._delta_main.setData(xs_out, deltas)

    # --- Init helpers ----------------------------------------------

    @staticmethod
    def _make_plot(
        y_label: str,
        main_color: tuple[int, int, int],
        second_trace_color: tuple[int, int, int],
    ) -> tuple[pg.PlotWidget, pg.PlotDataItem, pg.PlotDataItem]:
        """Construct a ``PlotWidget`` with two PlotDataItems ready to fill.

        The rival trace is added in a different colour (always amber so
        the user can tell it apart from the per-chart main colour) and
        is hidden by default — ``update_from`` flips visibility based
        on whether the broadcast includes a rival block.
        """
        plot = pg.PlotWidget()
        plot.setBackground(qcolor(BG_COLOR))
        axis_pen = pg.mkPen(QColor(*BORDER_COLOR), width=1)
        for side in ("left", "bottom"):
            axis = plot.getAxis(side)
            axis.setPen(axis_pen)
            axis.setTextPen(QColor(*TEXT_SECONDARY))
        plot.setLabel("left", y_label, color="#d1d5db")
        plot.setLabel("bottom", "Distance (m)", color="#d1d5db")
        plot.getPlotItem().showGrid(x=True, y=True, alpha=0.15)
        plot.getPlotItem().enableAutoRange("xy", True)

        main_line = pg.PlotDataItem(pen=pg.mkPen(QColor(*main_color), width=2))
        rival_line = pg.PlotDataItem(
            pen=pg.mkPen(QColor(*second_trace_color), width=2, style=Qt.DashLine)
        )
        plot.addItem(main_line)
        plot.addItem(rival_line)
        rival_line.setVisible(False)
        return plot, main_line, rival_line

    # --- State reset ------------------------------------------------

    def _reset(self) -> None:
        self._main_buffer.clear()
        self._rival_buffer.clear()
        self._current_lap = None
        for line in (
            self._speed_main, self._brake_main, self._throttle_main,
            self._delta_main,
        ):
            line.setData([], [])
        for line in (
            self._speed_rival, self._brake_rival, self._throttle_rival,
        ):
            line.setVisible(False)

    @staticmethod
    def _sorted(buffer: Bucket) -> tuple[list[float], list[tuple[float, float, float, float]]]:
        if not buffer:
            return [], []
        xs = sorted(buffer.keys())
        rows = [buffer[x] for x in xs]
        return [float(x) for x in xs], rows


def _lerp_sorted(xs: list[float], ys: list[float], x: float) -> float | None:
    """Linear interpolation of ``ys`` at ``x`` given sorted ``xs``.

    Returns ``None`` when ``x`` is outside the ``[xs[0], xs[-1]]`` range
    so the delta chart does not plot extrapolated time values where the
    rival has not reached yet (or passed already into the next sector)."""
    if not xs or x < xs[0] or x > xs[-1]:
        return None
    idx = bisect.bisect_left(xs, x)
    if idx < len(xs) and xs[idx] == x:
        return ys[idx]
    if idx == 0:
        return ys[0]
    x0, x1 = xs[idx - 1], xs[idx]
    y0, y1 = ys[idx - 1], ys[idx]
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
