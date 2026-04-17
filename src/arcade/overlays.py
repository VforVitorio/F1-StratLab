"""UI panels for the Arcade race replay.

Five independent components consumed by `F1ArcadeWindow.on_draw`: weather,
leaderboard, driver info, progress bar, controls legend. Every `arcade.Text`
is pre-allocated in each panel's `__init__` (which runs after the Window's
GL context is active); `draw()` only mutates `.text / .x / .y / .color`.
Creating `Text` inside `draw()` would leak glyph textures at 60 FPS × 20
rows — a bug that bit both the reference and our earlier attempts.
"""

from __future__ import annotations

import logging
from typing import Any, Final

import arcade

from src.arcade.config import (
    COMPOUND_COLORS,
    COMPOUND_LETTERS,
    DRIVER_BOX_GAP,
    DRIVER_BOX_HEIGHT,
    DRIVER_BOX_WIDTH,
    DRIVER_HEADER_HEIGHT,
    DRIVER_ROW_GAP,
    FLAG_COLORS,
    LEADERBOARD_N_SLOTS,
    LEADERBOARD_ROW_HEIGHT,
    LEADERBOARD_WIDTH,
    LEGEND_BOTTOM,
    LEGEND_X,
    PROGRESS_BAR_BOTTOM,
    PROGRESS_BAR_HEIGHT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WEATHER_LEFT,
    WEATHER_ROW_GAP,
    WEATHER_TOP_OFFSET,
    WEATHER_WIDTH,
)

logger = logging.getLogger(__name__)

_COMPASS: Final[tuple[str, ...]] = (
    "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
    "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW",
)


def _wind_dir(deg: float | None) -> str:
    if deg is None:
        return "N/A"
    return _COMPASS[int(((deg % 360) / 22.5) + 0.5) % 16]


class WeatherPanel:
    """Top-left weather readout: track/air temp, humidity, wind, rain."""

    def __init__(
        self,
        x: int = WEATHER_LEFT,
        top_offset: int = WEATHER_TOP_OFFSET,
        width: int = WEATHER_WIDTH,
    ) -> None:
        self.x = x
        self.top_offset = top_offset
        self.width = width
        self.bottom_y: int = 0
        self._title = arcade.Text(
            "Weather", x, 0, TEXT_PRIMARY, 16, bold=True,
            anchor_x="left", anchor_y="top",
        )
        self._line = arcade.Text(
            "", x + 12, 0, TEXT_SECONDARY, 12,
            anchor_x="left", anchor_y="top",
        )

    def draw(self, frame: dict | None, window_height: int) -> None:
        weather = (frame or {}).get("weather") or {}
        top_y = window_height - self.top_offset
        self._title.x = self.x
        self._title.y = top_y
        self._title.draw()

        lines = [
            f"Track: {weather.get('track_temp', 45.0):.1f} C",
            f"Air: {weather.get('air_temp', 18.0):.1f} C",
            f"Humidity: {weather.get('humidity', 55.0):.0f}%",
            f"Wind: {weather.get('wind_speed', 0.0):.1f} km/h "
            f"{_wind_dir(weather.get('wind_direction'))}",
            f"Rain: {weather.get('rain_state', 'DRY')}",
        ]
        y = top_y - 24
        for line in lines:
            self._line.text = line
            self._line.x = self.x + 12
            self._line.y = y
            self._line.draw()
            y -= WEATHER_ROW_GAP
        self.bottom_y = y + WEATHER_ROW_GAP - 10


class DriverInfoPanel:
    """Telemetry box for one driver: speed, gear, DRS, ahead/behind gaps."""

    BG_COLOR: tuple[int, int, int, int] = (0, 0, 0, 200)
    HEADER_TEXT: tuple[int, int, int] = (15, 15, 20)

    def __init__(
        self,
        x: int,
        top_y: int,
        width: int,
        height: int,
        driver_code: str,
        color: tuple[int, int, int],
    ) -> None:
        self.x = x
        self.top_y = top_y
        self.width = width
        self.height = height
        self.code = driver_code
        self.color = color
        self._header = arcade.Text(
            f"Driver: {driver_code}", 0, 0, self.HEADER_TEXT, 13, bold=True,
            anchor_x="left", anchor_y="center",
        )
        self._line = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 12, anchor_x="left", anchor_y="center"
        )

    def set_top(self, top_y: int) -> None:
        self.top_y = top_y

    def draw(
        self,
        frame: dict,
        all_drivers_sorted: list[tuple[str, float]] | None = None,
    ) -> None:
        data = (frame.get("drivers") or {}).get(self.code)
        if not data:
            return
        cx = self.x + self.width / 2
        cy = self.top_y - self.height / 2

        arcade.draw_rect_filled(arcade.XYWH(cx, cy, self.width, self.height), self.BG_COLOR)
        arcade.draw_rect_outline(
            arcade.XYWH(cx, cy, self.width, self.height), self.color, 2
        )
        header_cy = self.top_y - DRIVER_HEADER_HEIGHT / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, header_cy, self.width, DRIVER_HEADER_HEIGHT), self.color
        )
        self._header.x = self.x + 10
        self._header.y = header_cy
        self._header.draw()

        ahead, behind = self._neighbor_gaps(all_drivers_sorted)
        rows = [
            (f"Speed: {data.get('speed', 0):.0f} km/h", TEXT_PRIMARY),
            (f"Gear: {data.get('gear', 0)}", TEXT_PRIMARY),
            (f"DRS: {self._drs_label(data.get('drs', 0))}", self._drs_color(data.get("drs", 0))),
            (f"Compound: {COMPOUND_LETTERS.get(int(data.get('tyre', 1)), '?')}",
             COMPOUND_COLORS.get(int(data.get("tyre", 1)), TEXT_PRIMARY)),
            (ahead, TEXT_SECONDARY),
            (behind, TEXT_SECONDARY),
        ]
        y = self.top_y - DRIVER_HEADER_HEIGHT - 16
        for text, color in rows:
            self._line.text = text
            self._line.color = color
            self._line.x = self.x + 12
            self._line.y = y
            self._line.draw()
            y -= DRIVER_ROW_GAP

    @staticmethod
    def _drs_label(drs: int) -> str:
        drs = int(drs)
        if drs in (10, 12, 14):
            return "ON"
        if drs == 8:
            return "AVAIL"
        return "OFF"

    @staticmethod
    def _drs_color(drs: int) -> tuple[int, int, int]:
        drs = int(drs)
        if drs in (10, 12, 14):
            return (0, 220, 0)
        if drs == 8:
            return (255, 210, 50)
        return TEXT_TERTIARY

    def _neighbor_gaps(
        self, sorted_drivers: list[tuple[str, float]] | None
    ) -> tuple[str, str]:
        if not sorted_drivers:
            return "Ahead: N/A", "Behind: N/A"
        codes = [c for c, _ in sorted_drivers]
        if self.code not in codes:
            return "Ahead: N/A", "Behind: N/A"
        idx = codes.index(self.code)
        ahead_txt = "Ahead: LEADER" if idx == 0 else self._gap_line(
            "Ahead", sorted_drivers[idx - 1], sorted_drivers[idx]
        )
        behind_txt = "Behind: LAST" if idx == len(codes) - 1 else self._gap_line(
            "Behind", sorted_drivers[idx + 1], sorted_drivers[idx]
        )
        return ahead_txt, behind_txt

    @staticmethod
    def _gap_line(
        label: str,
        other: tuple[str, float],
        self_entry: tuple[str, float],
    ) -> str:
        other_code, other_prog = other
        _, self_prog = self_entry
        dist = abs(other_prog - self_prog)
        time_s = dist / 55.56 if dist > 0 else 0.0
        sign = "+" if label == "Ahead" else "-"
        return f"{label} ({other_code}): {sign}{time_s:.2f}s ({dist:.0f}m)"


class LeaderboardPanel:
    """Right-edge list of all drivers ranked by race-cumulative progress."""

    def __init__(
        self,
        x: int,
        top_y: int,
        width: int = LEADERBOARD_WIDTH,
        n_slots: int = LEADERBOARD_N_SLOTS,
    ) -> None:
        self.x = x
        self.top_y = top_y
        self.width = width
        self._row_rects: list[tuple[str, float, float, float, float]] = []
        self._title = arcade.Text(
            "Leaderboard", x, top_y, TEXT_PRIMARY, 16, bold=True,
            anchor_x="left", anchor_y="top",
        )
        self._rank_texts = [
            arcade.Text("", 0, 0, TEXT_PRIMARY, 13,
                        anchor_x="left", anchor_y="top")
            for _ in range(n_slots)
        ]
        self._compound_texts = [
            arcade.Text("", 0, 0, TEXT_PRIMARY, 12, bold=True,
                        anchor_x="right", anchor_y="top")
            for _ in range(n_slots)
        ]

    def set_top(self, top_y: int) -> None:
        self.top_y = top_y

    def draw(
        self,
        frame: dict,
        driver_colors: dict[str, tuple[int, int, int]],
        track_len: float,
        selected_drivers: set[str] | None = None,
    ) -> None:
        selected_drivers = selected_drivers or set()
        ranked = self._rank_drivers(frame, track_len)
        self._title.x = self.x
        self._title.y = self.top_y
        self._title.draw()
        self._row_rects = []

        y = self.top_y - 26
        for i, (code, data, _) in enumerate(ranked[: len(self._rank_texts)]):
            color = driver_colors.get(code, TEXT_PRIMARY)
            is_highlighted = code in selected_drivers
            rect_cx = self.x + self.width / 2
            rect_cy = y - LEADERBOARD_ROW_HEIGHT / 2 + 8
            self._row_rects.append(
                (code, self.x, rect_cy - LEADERBOARD_ROW_HEIGHT / 2,
                 self.x + self.width, rect_cy + LEADERBOARD_ROW_HEIGHT / 2)
            )
            if is_highlighted:
                arcade.draw_rect_filled(
                    arcade.XYWH(rect_cx, rect_cy, self.width, LEADERBOARD_ROW_HEIGHT),
                    (70, 70, 80),
                )

            out_flag = "  OUT" if not data.get("active", True) else ""
            rt = self._rank_texts[i]
            rt.text = f"{i + 1}. {code}{out_flag}"
            rt.color = color
            rt.x = self.x + 8
            rt.y = y
            rt.draw()

            compound = int(data.get("tyre", 1))
            ct = self._compound_texts[i]
            ct.text = COMPOUND_LETTERS.get(compound, "?")
            ct.color = COMPOUND_COLORS.get(compound, TEXT_PRIMARY)
            ct.x = self.x + self.width - 8
            ct.y = y
            ct.draw()

            y -= LEADERBOARD_ROW_HEIGHT

    def sorted_progress(
        self, frame: dict, track_len: float
    ) -> list[tuple[str, float]]:
        ranked = self._rank_drivers(frame, track_len)
        return [(code, progress) for code, _, progress in ranked]

    def hit_test(self, mx: float, my: float) -> str | None:
        for code, left, bottom, right, top in self._row_rects:
            if left <= mx <= right and bottom <= my <= top:
                return code
        return None

    @staticmethod
    def _rank_drivers(frame: dict, track_len: float) -> list[tuple[str, dict, float]]:
        drivers = (frame or {}).get("drivers") or {}
        out: list[tuple[str, dict, float]] = []
        for code, data in drivers.items():
            lap = max(1, int(data.get("lap", 1) or 1))
            dist = float(data.get("dist", 0.0) or 0.0)
            progress = (lap - 1) * max(track_len, 1.0) + dist
            out.append((code, data, progress))
        out.sort(key=lambda e: e[2], reverse=True)
        return out


class ProgressBar:
    """Bottom timeline with lap ticks, flag events, playhead, and click-to-seek."""

    def __init__(
        self,
        total_frames: int,
        total_laps: int,
        events: list[dict[str, Any]] | None = None,
        left_margin: int = 340,
        right_margin: int = 260,
        bottom: int = PROGRESS_BAR_BOTTOM,
        height: int = PROGRESS_BAR_HEIGHT,
    ) -> None:
        self.total_frames = max(1, int(total_frames))
        self.total_laps = max(1, int(total_laps))
        self.events = events or []
        self.left_margin = left_margin
        self.right_margin = right_margin
        self.bottom = bottom
        self.height = height
        self._bar_left = left_margin
        self._bar_width = 1
        self._lap_label = arcade.Text(
            "1", 0, 0, TEXT_SECONDARY, 10, anchor_x="center", anchor_y="top"
        )

    def on_resize(self, window_width: int) -> None:
        self._bar_width = max(100, window_width - self.left_margin - self.right_margin)

    def draw(self, window_width: int, current_frame: int) -> None:
        self.on_resize(window_width)
        cy = self.bottom + self.height / 2
        bg_rect = arcade.XYWH(
            self._bar_left + self._bar_width / 2, cy, self._bar_width, self.height
        )
        arcade.draw_rect_filled(bg_rect, FLAG_COLORS["background"])
        arcade.draw_rect_outline(bg_rect, FLAG_COLORS["lap_marker"], 1)

        prog = max(0.0, min(1.0, current_frame / self.total_frames))
        fill_w = prog * self._bar_width
        if fill_w > 0:
            arcade.draw_rect_filled(
                arcade.XYWH(
                    self._bar_left + fill_w / 2, cy, fill_w, self.height - 4
                ),
                FLAG_COLORS["progress_fill"],
            )

        for lap in range(1, self.total_laps + 1):
            lx = self._frame_to_x(int(lap / self.total_laps * self.total_frames))
            arcade.draw_line(
                lx, self.bottom + 2, lx, self.bottom + self.height - 2,
                FLAG_COLORS["lap_marker"], 1,
            )
            if lap == 1 or lap == self.total_laps or lap % 10 == 0:
                self._lap_label.text = str(lap)
                self._lap_label.x = lx
                self._lap_label.y = self.bottom - 4
                self._lap_label.draw()

        for event in self.events:
            self._draw_event(event)

        px = self._frame_to_x(int(current_frame))
        arcade.draw_line(
            px, self.bottom - 2, px, self.bottom + self.height + 2,
            FLAG_COLORS["playhead"], 3,
        )

    def on_mouse_press(self, x: float, y: float) -> int | None:
        if not (self._bar_left <= x <= self._bar_left + self._bar_width):
            return None
        if not (self.bottom - 5 <= y <= self.bottom + self.height + 5):
            return None
        return self._x_to_frame(x)

    def _frame_to_x(self, f: int) -> float:
        f = max(0, min(f, self.total_frames))
        return self._bar_left + (f / self.total_frames) * self._bar_width

    def _x_to_frame(self, x: float) -> int:
        return int(max(0, min(
            self.total_frames - 1,
            ((x - self._bar_left) / max(1, self._bar_width)) * self.total_frames,
        )))

    def _draw_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type", "")
        color = FLAG_COLORS.get(event_type)
        if color is None:
            return
        sf = int(event.get("frame", 0))
        ef = int(event.get("end_frame", sf + 100))
        sx = self._frame_to_x(sf)
        ex = self._frame_to_x(ef)
        w = max(4.0, ex - sx)
        arcade.draw_rect_filled(
            arcade.XYWH(sx + w / 2, self.bottom + self.height + 5, w, 5), color
        )


class ControlsLegend:
    """Static bottom-left cheat sheet for keyboard bindings."""

    LINES: Final[tuple[str, ...]] = (
        "[SPACE] Pause/Resume",
        "[<- / ->] Rewind / Fast-Forward",
        "[Up/Down] Speed +/- (0.25, 0.5, 1, 2, 4, 8x)",
        "[1-4] 0.5 / 1 / 2 / 4x",
        "[R] Restart",
        "[D] Toggle DRS Zones",
        "[B] Toggle Progress Bar",
        "[ESC] Close",
    )

    def __init__(self, x: int = LEGEND_X, bottom: int = LEGEND_BOTTOM) -> None:
        self.x = x
        self.bottom = bottom
        self._header = arcade.Text(
            "Controls:", x, 0, TEXT_PRIMARY, 12, bold=True,
            anchor_x="left", anchor_y="bottom",
        )
        self._lines = [
            arcade.Text(line, 0, 0, TEXT_SECONDARY, 10,
                        anchor_x="left", anchor_y="bottom")
            for line in self.LINES
        ]

    def draw(self) -> None:
        y = self.bottom
        for i, txt in enumerate(reversed(self._lines)):
            txt.x = self.x
            txt.y = y + i * 14
            txt.draw()
        self._header.x = self.x
        self._header.y = self.bottom + len(self._lines) * 14 + 4
        self._header.draw()
