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
    ACCENT,
    BORDER_COLOR,
    COMPOUND_COLORS,
    COMPOUND_LETTERS,
    CONTENT_BG,
    DANGER,
    DRIVER_BOX_GAP,
    DRIVER_BOX_HEIGHT,
    DRIVER_BOX_WIDTH,
    DRIVER_HEADER_HEIGHT,
    DRIVER_ROW_GAP,
    FLAG_COLORS,
    FONT_BODY,
    FONT_TITLE,
    LEADERBOARD_N_SLOTS,
    LEADERBOARD_ROW_HEIGHT,
    LEADERBOARD_WIDTH,
    LEGEND_BOTTOM,
    LEGEND_X,
    PROGRESS_BAR_BOTTOM,
    PROGRESS_BAR_HEIGHT,
    STRATEGY_PANEL_HEIGHT,
    STRATEGY_PANEL_WIDTH,
    SUCCESS,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WARNING,
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
    """Top-left weather readout: track/air temp, humidity, wind, rain.

    Visual identity: translucent CONTENT_BG card with a 1 px BORDER outline and
    a 3 px ACCENT top-strip. Readings are Inter body text, label in TERTIARY
    and value in PRIMARY — same convention the Streamlit sidebar uses."""

    PANEL_PADDING: int = 12
    STRIP_H: int = 3

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
            "WEATHER", x, 0, ACCENT, 13, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._label = arcade.Text(
            "", 0, 0, TEXT_TERTIARY, 11, font_name=FONT_BODY,
            anchor_x="left", anchor_y="top",
        )
        self._value = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 11, font_name=FONT_BODY, bold=True,
            anchor_x="right", anchor_y="top",
        )

    def draw(self, frame: dict | None, window_height: int) -> None:
        weather = (frame or {}).get("weather") or {}
        top_y = window_height - self.top_offset
        rows: list[tuple[str, str]] = [
            ("Track", f"{weather.get('track_temp', 45.0):.1f} C"),
            ("Air", f"{weather.get('air_temp', 18.0):.1f} C"),
            ("Humidity", f"{weather.get('humidity', 55.0):.0f}%"),
            ("Wind", f"{weather.get('wind_speed', 0.0):.1f} km/h "
                     f"{_wind_dir(weather.get('wind_direction'))}"),
            ("Rain", f"{weather.get('rain_state', 'DRY')}"),
        ]
        panel_h = 26 + len(rows) * WEATHER_ROW_GAP + self.PANEL_PADDING
        self._draw_card(top_y, panel_h)

        self._title.x = self.x + self.PANEL_PADDING
        self._title.y = top_y - 10
        self._title.draw()

        y = top_y - 32
        for label, value in rows:
            self._label.text = label
            self._label.x = self.x + self.PANEL_PADDING
            self._label.y = y
            self._label.draw()
            self._value.text = value
            self._value.x = self.x + self.width - self.PANEL_PADDING
            self._value.y = y
            self._value.draw()
            y -= WEATHER_ROW_GAP
        self.bottom_y = y + WEATHER_ROW_GAP - 10

    def _draw_card(self, top_y: int, panel_h: int) -> None:
        cx = self.x + self.width / 2
        cy = top_y - panel_h / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width, panel_h), (*CONTENT_BG, 230)
        )
        arcade.draw_rect_outline(
            arcade.XYWH(cx, cy, self.width, panel_h), BORDER_COLOR, 1
        )
        strip_cy = top_y - self.STRIP_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, strip_cy, self.width, self.STRIP_H), ACCENT
        )


class DriverInfoPanel:
    """Telemetry box for one driver: speed, gear, DRS, compound, gaps.

    Redesigned vs f1_replay's filled team-colour header: we use a neutral
    CONTENT_BG card with a 3 px team-colour strip on top and the driver
    code rendered in team colour, which reads as the same product as the
    Streamlit pages instead of a clone of the reference app."""

    STRIP_H: int = 3
    PAD_X: int = 12

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
            driver_code, 0, 0, color, 15, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="center",
        )
        self._subheader = arcade.Text(
            "DRIVER", 0, 0, TEXT_TERTIARY, 9, bold=True,
            font_name=FONT_TITLE, anchor_x="right", anchor_y="center",
        )
        self._label = arcade.Text(
            "", 0, 0, TEXT_TERTIARY, 10, font_name=FONT_BODY,
            anchor_x="left", anchor_y="center",
        )
        self._value = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 11, font_name=FONT_BODY, bold=True,
            anchor_x="right", anchor_y="center",
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

        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width, self.height), (*CONTENT_BG, 230)
        )
        arcade.draw_rect_outline(
            arcade.XYWH(cx, cy, self.width, self.height), BORDER_COLOR, 1
        )
        strip_cy = self.top_y - self.STRIP_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, strip_cy, self.width, self.STRIP_H), self.color
        )
        header_cy = self.top_y - DRIVER_HEADER_HEIGHT / 2
        self._header.x = self.x + self.PAD_X
        self._header.y = header_cy
        self._header.draw()
        self._subheader.x = self.x + self.width - self.PAD_X
        self._subheader.y = header_cy
        self._subheader.draw()

        ahead, behind = self._neighbor_gaps(all_drivers_sorted)
        rows: list[tuple[str, str, tuple[int, int, int]]] = [
            ("Speed", f"{data.get('speed', 0):.0f} km/h", TEXT_PRIMARY),
            ("Gear", f"{data.get('gear', 0)}", TEXT_PRIMARY),
            ("DRS", self._drs_label(data.get("drs", 0)), self._drs_color(data.get("drs", 0))),
            ("Compound",
             COMPOUND_LETTERS.get(int(data.get("tyre", 1)), "?"),
             COMPOUND_COLORS.get(int(data.get("tyre", 1)), TEXT_PRIMARY)),
            ("Ahead", ahead, TEXT_SECONDARY),
            ("Behind", behind, TEXT_SECONDARY),
        ]
        y = self.top_y - DRIVER_HEADER_HEIGHT - 14
        for label, value, color in rows:
            self._label.text = label
            self._label.x = self.x + self.PAD_X
            self._label.y = y
            self._label.draw()
            self._value.text = value
            self._value.color = color
            self._value.x = self.x + self.width - self.PAD_X
            self._value.y = y
            self._value.draw()
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
            return "N/A", "N/A"
        codes = [c for c, _ in sorted_drivers]
        if self.code not in codes:
            return "N/A", "N/A"
        idx = codes.index(self.code)
        ahead = "LEADER" if idx == 0 else self._gap_value(
            "+", sorted_drivers[idx - 1], sorted_drivers[idx]
        )
        behind = "LAST" if idx == len(codes) - 1 else self._gap_value(
            "-", sorted_drivers[idx + 1], sorted_drivers[idx]
        )
        return ahead, behind

    @staticmethod
    def _gap_value(
        sign: str,
        other: tuple[str, float],
        self_entry: tuple[str, float],
    ) -> str:
        other_code, other_prog = other
        _, self_prog = self_entry
        dist = abs(other_prog - self_prog)
        time_s = dist / 55.56 if dist > 0 else 0.0
        return f"{other_code} {sign}{time_s:.2f}s"


class LeaderboardPanel:
    """Right-edge list of all drivers ranked by race-cumulative progress.

    Visual identity: same card language as Weather/DriverInfo — translucent
    CONTENT_BG, 1 px BORDER outline, 3 px ACCENT top-strip, rank numbers in
    TERTIARY, codes in team colour, compound letter in compound colour on the
    right edge. Selected row is filled with SECONDARY_BG instead of a bare
    grey rect."""

    STRIP_H: int = 3
    PAD_X: int = 10
    HEADER_H: int = 28

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
            "LEADERBOARD", x, top_y, ACCENT, 13, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._rank_texts = [
            arcade.Text("", 0, 0, TEXT_TERTIARY, 11, font_name=FONT_BODY,
                        anchor_x="left", anchor_y="top")
            for _ in range(n_slots)
        ]
        self._code_texts = [
            arcade.Text("", 0, 0, TEXT_PRIMARY, 12, bold=True,
                        font_name=FONT_BODY, anchor_x="left", anchor_y="top")
            for _ in range(n_slots)
        ]
        self._compound_texts = [
            arcade.Text("", 0, 0, TEXT_PRIMARY, 11, bold=True,
                        font_name=FONT_BODY, anchor_x="right", anchor_y="top")
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
        n_rows = min(len(ranked), len(self._rank_texts))
        panel_h = self.HEADER_H + n_rows * LEADERBOARD_ROW_HEIGHT + 8
        self._draw_card(panel_h)

        self._title.x = self.x + self.PAD_X
        self._title.y = self.top_y - 8
        self._title.draw()

        self._row_rects = []
        y = self.top_y - self.HEADER_H

        for i, (code, data, _) in enumerate(ranked[:n_rows]):
            color = driver_colors.get(code, TEXT_PRIMARY)
            is_highlighted = code in selected_drivers
            rect_cx = self.x + self.width / 2
            rect_cy = y - LEADERBOARD_ROW_HEIGHT / 2 + 6
            self._row_rects.append(
                (code, self.x, rect_cy - LEADERBOARD_ROW_HEIGHT / 2,
                 self.x + self.width, rect_cy + LEADERBOARD_ROW_HEIGHT / 2)
            )
            if is_highlighted:
                arcade.draw_rect_filled(
                    arcade.XYWH(rect_cx, rect_cy, self.width, LEADERBOARD_ROW_HEIGHT),
                    (*ACCENT, 70),
                )

            is_out = not data.get("active", True)
            rt = self._rank_texts[i]
            rt.text = f"{i + 1:>2}"
            rt.color = TEXT_TERTIARY
            rt.x = self.x + self.PAD_X
            rt.y = y
            rt.draw()

            ct = self._code_texts[i]
            ct.text = f"{code}{' OUT' if is_out else ''}"
            ct.color = color
            ct.x = self.x + self.PAD_X + 28
            ct.y = y
            ct.draw()

            compound = int(data.get("tyre", 1))
            pt = self._compound_texts[i]
            pt.text = COMPOUND_LETTERS.get(compound, "?")
            pt.color = COMPOUND_COLORS.get(compound, TEXT_PRIMARY)
            pt.x = self.x + self.width - self.PAD_X
            pt.y = y
            pt.draw()

            y -= LEADERBOARD_ROW_HEIGHT

    def _draw_card(self, panel_h: int) -> None:
        cx = self.x + self.width / 2
        cy = self.top_y - panel_h / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width, panel_h), (*CONTENT_BG, 230)
        )
        arcade.draw_rect_outline(
            arcade.XYWH(cx, cy, self.width, panel_h), BORDER_COLOR, 1
        )
        strip_cy = self.top_y - self.STRIP_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, strip_cy, self.width, self.STRIP_H), ACCENT
        )

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
            "1", 0, 0, TEXT_TERTIARY, 10, font_name=FONT_BODY,
            anchor_x="center", anchor_y="top"
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
    """Static bottom-left cheat sheet for keyboard bindings.

    Uses the same ACCENT title / TERTIARY body convention as the other
    panels so the legend reads as part of the UI instead of a debug
    overlay."""

    LINES: Final[tuple[tuple[str, str], ...]] = (
        ("SPACE", "Pause / Resume"),
        ("<- / ->", "Rewind / Fast-Forward"),
        ("Up / Down", "Speed +/-"),
        ("1 - 4", "0.5 / 1 / 2 / 4 x"),
        ("R", "Restart"),
        ("D", "Toggle DRS zones"),
        ("B", "Toggle progress bar"),
        ("ESC", "Close"),
    )

    def __init__(self, x: int = LEGEND_X, bottom: int = LEGEND_BOTTOM) -> None:
        self.x = x
        self.bottom = bottom
        self._header = arcade.Text(
            "CONTROLS", x, 0, ACCENT, 12, bold=True, font_name=FONT_TITLE,
            anchor_x="left", anchor_y="bottom",
        )
        self._key_texts = [
            arcade.Text(key, 0, 0, TEXT_PRIMARY, 10, bold=True,
                        font_name=FONT_BODY, anchor_x="left", anchor_y="bottom")
            for key, _ in self.LINES
        ]
        self._desc_texts = [
            arcade.Text(desc, 0, 0, TEXT_TERTIARY, 10,
                        font_name=FONT_BODY, anchor_x="left", anchor_y="bottom")
            for _, desc in self.LINES
        ]

    def draw(self) -> None:
        y = self.bottom
        rows = list(zip(self._key_texts, self._desc_texts))
        for i, (key, desc) in enumerate(reversed(rows)):
            key.x = self.x
            key.y = y + i * 14
            key.draw()
            desc.x = self.x + 70
            desc.y = y + i * 14
            desc.draw()
        self._header.x = self.x
        self._header.y = self.bottom + len(self.LINES) * 14 + 6
        self._header.draw()


class StrategyPanel:
    """Tier-A strategy readout: action, confidence, four MC scenarios, chips.

    Same visual language as the other panels (CONTENT_BG card, ACCENT
    top-strip, Exo 2 title). Renders only when `StrategyState.latest` is
    populated; when `state.error` is set, shows a red banner in place of
    the content. All text objects pre-allocated in `__init__` to keep the
    GL-glyph pool from leaking at 60 FPS."""

    STRIP_H: int = 3
    PAD_X: int = 12
    BADGE_H: int = 36
    CONF_H: int = 14
    SCENARIO_ROW_H: int = 18
    SCENARIO_BAR_W: int = 110
    SCENARIO_KEYS: Final[tuple[str, ...]] = (
        "STAY_OUT", "PIT_NOW", "UNDERCUT", "OVERCUT",
    )
    SCENARIO_LABELS: Final[dict[str, str]] = {
        "STAY_OUT": "STAY", "PIT_NOW": "PIT",
        "UNDERCUT": "UCUT", "OVERCUT": "OCUT",
    }

    def __init__(
        self,
        x: int,
        top_y: int,
        width: int = STRATEGY_PANEL_WIDTH,
        height: int = STRATEGY_PANEL_HEIGHT,
    ) -> None:
        self.x = x
        self.top_y = top_y
        self.width = width
        self.height = height

        self._title = arcade.Text(
            "STRATEGY", x + self.PAD_X, 0, ACCENT, 13, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._badge_text = arcade.Text(
            "--", 0, 0, TEXT_PRIMARY, 18, bold=True,
            font_name=FONT_TITLE, anchor_x="center", anchor_y="center",
        )
        self._conf_label = arcade.Text(
            "CONFIDENCE", 0, 0, TEXT_TERTIARY, 9, bold=True,
            font_name=FONT_BODY, anchor_x="left", anchor_y="bottom",
        )
        self._conf_value = arcade.Text(
            "0.00", 0, 0, TEXT_PRIMARY, 10, bold=True,
            font_name=FONT_BODY, anchor_x="right", anchor_y="bottom",
        )
        self._scenario_names = [
            arcade.Text("", 0, 0, TEXT_SECONDARY, 10, bold=True,
                        font_name=FONT_BODY, anchor_x="left", anchor_y="center")
            for _ in self.SCENARIO_KEYS
        ]
        self._scenario_values = [
            arcade.Text("", 0, 0, TEXT_PRIMARY, 10,
                        font_name=FONT_BODY, anchor_x="right", anchor_y="center")
            for _ in self.SCENARIO_KEYS
        ]
        self._chip_pace = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 10, bold=True,
            font_name=FONT_BODY, anchor_x="center", anchor_y="center",
        )
        self._chip_risk = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 10, bold=True,
            font_name=FONT_BODY, anchor_x="center", anchor_y="center",
        )
        self._gap_text = arcade.Text(
            "", 0, 0, TEXT_SECONDARY, 11, font_name=FONT_BODY,
            anchor_x="left", anchor_y="center",
        )
        self._alert_text = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 10, bold=True,
            font_name=FONT_BODY, anchor_x="center", anchor_y="center",
        )
        self._guardrail_text = arcade.Text(
            "", 0, 0, DANGER, 9, font_name=FONT_BODY,
            anchor_x="left", anchor_y="center",
        )
        self._offline_text = arcade.Text(
            "", 0, 0, TEXT_PRIMARY, 11, bold=True,
            font_name=FONT_BODY, anchor_x="center", anchor_y="center",
        )

    def draw(self, state) -> None:
        """Render the panel. `state` is a `StrategyState` — duck-typed to
        avoid importing `strategy` into `overlays` (keeps the import DAG
        one-way: overlays -> config, strategy -> config, app -> both).

        When there is nothing to render yet (no data, or backend offline)
        we shrink the card to a compact strip so the UI does not show a
        big empty rectangle next to a floating banner."""
        latest, error, _finished = state.snapshot()

        if error is not None:
            self._draw_compact_card(height=56)
            self._draw_title(compact=True)
            self._draw_offline_banner(error)
            return
        if latest is None:
            self._draw_compact_card(height=56)
            self._draw_title(compact=True)
            self._draw_waiting_banner()
            return

        self._draw_card()
        self._draw_title(compact=False)
        y_cursor = self.top_y - 32
        y_cursor = self._draw_action_badge(latest, y_cursor)
        y_cursor = self._draw_confidence(latest, y_cursor)
        y_cursor = self._draw_scenarios(latest, y_cursor)
        y_cursor = self._draw_chips(latest, y_cursor)
        y_cursor = self._draw_gap(latest, y_cursor)
        y_cursor = self._draw_alerts(latest, y_cursor)
        self._draw_guardrail(latest, y_cursor)

    def _draw_title(self, *, compact: bool) -> None:
        self._title.x = self.x + self.PAD_X
        self._title.y = self.top_y - (6 if compact else 8)
        self._title.draw()

    # --- Layout blocks ---------------------------------------------------

    def _draw_card(self) -> None:
        self._draw_compact_card(self.height)

    def _draw_compact_card(self, height: int) -> None:
        cx = self.x + self.width / 2
        cy = self.top_y - height / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width, height), (*CONTENT_BG, 245)
        )
        arcade.draw_rect_outline(
            arcade.XYWH(cx, cy, self.width, height), BORDER_COLOR, 1
        )
        strip_cy = self.top_y - self.STRIP_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, strip_cy, self.width, self.STRIP_H), ACCENT
        )

    def _draw_action_badge(self, latest, y: int) -> int:
        from src.arcade.strategy import classify_action
        color, label = classify_action(latest.action)
        cx = self.x + self.width / 2
        cy = y - self.BADGE_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width - 2 * self.PAD_X, self.BADGE_H), color
        )
        self._badge_text.text = label
        self._badge_text.x = cx
        self._badge_text.y = cy
        self._badge_text.draw()
        return y - self.BADGE_H - 10

    def _draw_confidence(self, latest, y: int) -> int:
        conf = max(0.0, min(1.0, latest.confidence))
        bar_left = self.x + self.PAD_X
        bar_right = self.x + self.width - self.PAD_X
        bar_w = bar_right - bar_left

        self._conf_label.x = bar_left
        self._conf_label.y = y - 10
        self._conf_label.draw()
        self._conf_value.text = f"{conf:.2f}"
        self._conf_value.x = bar_right
        self._conf_value.y = y - 10
        self._conf_value.draw()

        y_bar = y - 22
        cy_bar = y_bar - self.CONF_H / 2
        arcade.draw_rect_filled(
            arcade.XYWH(bar_left + bar_w / 2, cy_bar, bar_w, self.CONF_H),
            BORDER_COLOR,
        )
        if conf > 0:
            fill_color = self._confidence_color(conf)
            fw = max(2.0, conf * bar_w)
            arcade.draw_rect_filled(
                arcade.XYWH(bar_left + fw / 2, cy_bar, fw, self.CONF_H),
                fill_color,
            )
        return y_bar - self.CONF_H - 6

    def _draw_scenarios(self, latest, y: int) -> int:
        scores = latest.scenario_scores or {}
        winner = max(scores, key=lambda k: scores.get(k, 0.0), default=None)
        bar_left = self.x + self.PAD_X + 48
        bar_right = self.x + self.width - self.PAD_X - 36
        bar_w = max(20, bar_right - bar_left)

        for i, key in enumerate(self.SCENARIO_KEYS):
            score = float(scores.get(key, 0.0))
            row_y = y - i * self.SCENARIO_ROW_H - self.SCENARIO_ROW_H / 2
            is_winner = (key == winner and score > 0)

            name = self._scenario_names[i]
            name.text = self.SCENARIO_LABELS.get(key, key[:4])
            name.color = TEXT_PRIMARY if is_winner else TEXT_TERTIARY
            name.x = self.x + self.PAD_X
            name.y = row_y
            name.draw()

            cy = row_y
            arcade.draw_rect_filled(
                arcade.XYWH(bar_left + bar_w / 2, cy, bar_w, 8), BORDER_COLOR
            )
            if score > 0:
                fw = max(2.0, score * bar_w)
                color = ACCENT if is_winner else (*TEXT_TERTIARY, 180)
                arcade.draw_rect_filled(
                    arcade.XYWH(bar_left + fw / 2, cy, fw, 8), color
                )

            val = self._scenario_values[i]
            val.text = f"{score:.2f}"
            val.color = TEXT_PRIMARY if is_winner else TEXT_TERTIARY
            val.x = bar_right + 34
            val.y = row_y
            val.draw()

        return y - len(self.SCENARIO_KEYS) * self.SCENARIO_ROW_H - 8

    def _draw_chips(self, latest, y: int) -> int:
        pace = latest.pace_mode
        risk = latest.risk_posture
        if not pace and not risk:
            return y
        chip_w = (self.width - 3 * self.PAD_X) / 2
        cy = y - 11

        if pace:
            self._draw_chip(
                self.x + self.PAD_X, cy, chip_w,
                self._shorten_pace(pace), self._pace_color(pace),
                self._chip_pace,
            )
        if risk:
            self._draw_chip(
                self.x + self.PAD_X + chip_w + self.PAD_X, cy, chip_w,
                self._shorten_risk(risk), self._risk_color(risk),
                self._chip_risk,
            )
        return y - 28

    def _draw_chip(
        self, left: float, cy: float, w: float, label: str,
        color: tuple[int, int, int], text_obj: arcade.Text,
    ) -> None:
        arcade.draw_rect_filled(arcade.XYWH(left + w / 2, cy, w, 20), color)
        text_obj.text = label
        text_obj.x = left + w / 2
        text_obj.y = cy
        text_obj.draw()

    def _draw_gap(self, latest, y: int) -> int:
        gap = latest.gap_ahead_s
        if gap is None:
            return y
        self._gap_text.text = f"Gap ahead: +{gap:.2f}s"
        self._gap_text.x = self.x + self.PAD_X
        self._gap_text.y = y - 8
        self._gap_text.draw()
        return y - 18

    def _draw_alerts(self, latest, y: int) -> int:
        from src.arcade.strategy import classify_alerts
        cls = classify_alerts(latest.agent_alerts or [])
        if cls is None:
            return y
        text, color = cls
        cy = y - 11
        arcade.draw_rect_filled(
            arcade.XYWH(self.x + self.width / 2, cy,
                        self.width - 2 * self.PAD_X, 20),
            color,
        )
        self._alert_text.text = text
        self._alert_text.x = self.x + self.width / 2
        self._alert_text.y = cy
        self._alert_text.draw()
        return y - 26

    def _draw_guardrail(self, latest, y: int) -> None:
        if not latest.guardrail_reason:
            return
        self._guardrail_text.text = f"! {latest.guardrail_reason}"
        self._guardrail_text.x = self.x + self.PAD_X
        self._guardrail_text.y = y - 6
        self._guardrail_text.draw()

    def _draw_offline_banner(self, error: str) -> None:
        cx = self.x + self.width / 2
        cy = self.top_y - 38
        self._offline_text.text = error[:38]
        self._offline_text.x = cx
        self._offline_text.y = cy
        self._offline_text.color = TEXT_PRIMARY
        arcade.draw_rect_filled(
            arcade.XYWH(cx, cy, self.width - 2 * self.PAD_X, 22), DANGER
        )
        self._offline_text.draw()

    def _draw_waiting_banner(self) -> None:
        cx = self.x + self.width / 2
        cy = self.top_y - 38
        self._offline_text.text = "Waiting for backend..."
        self._offline_text.color = TEXT_TERTIARY
        self._offline_text.x = cx
        self._offline_text.y = cy
        self._offline_text.draw()

    # --- Tiny helpers ----------------------------------------------------

    @staticmethod
    def _confidence_color(conf: float) -> tuple[int, int, int]:
        if conf < 0.33:
            return DANGER
        if conf < 0.66:
            return WARNING
        return SUCCESS

    @staticmethod
    def _shorten_pace(pace: str) -> str:
        return {
            "PUSH": "PUSH", "NEUTRAL": "NTRL", "MANAGE": "MNGR",
            "LIFT_AND_COAST": "L&C",
        }.get(pace.upper(), pace[:4].upper())

    @staticmethod
    def _pace_color(pace: str) -> tuple[int, int, int]:
        return {
            "PUSH": DANGER, "NEUTRAL": ACCENT,
            "MANAGE": WARNING, "LIFT_AND_COAST": WARNING,
        }.get(pace.upper(), TEXT_TERTIARY)

    @staticmethod
    def _shorten_risk(risk: str) -> str:
        return {
            "AGGRESSIVE": "AGG", "BALANCED": "BAL", "DEFENSIVE": "DEF",
        }.get(risk.upper(), risk[:3].upper())

    @staticmethod
    def _risk_color(risk: str) -> tuple[int, int, int]:
        return {
            "AGGRESSIVE": DANGER, "BALANCED": ACCENT, "DEFENSIVE": SUCCESS,
        }.get(risk.upper(), TEXT_TERTIARY)
