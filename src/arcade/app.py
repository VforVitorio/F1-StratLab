"""The Arcade Window orchestrating playback, car rendering, and UI panels.

Construction contract (enforced by `main.py`): `session_data` and `track` are
already loaded and built in the main thread before `arcade.Window.__init__`
runs. That way every `arcade.Text` allocated here and in child panels has an
active GL context, avoiding the pyglet 0x1282 errors we hit when loading
asynchronously.
"""

from __future__ import annotations

import logging

import arcade

from src.arcade.config import (
    ACCENT,
    BG_COLOR,
    CAR_BORDER_COLOR,
    CAR_BORDER_WIDTH,
    CAR_LABEL_FONT_SIZE,
    CAR_RADIUS,
    DEFAULT_SPEED_IDX,
    DRIVER_BOX_GAP,
    DRIVER_BOX_HEIGHT,
    DRIVER_BOX_WIDTH,
    FONT_BODY,
    FONT_TITLE,
    FPS,
    LEADERBOARD_RIGHT_MARGIN,
    LEADERBOARD_WIDTH,
    MARGIN_BOTTOM,
    MARGIN_LEFT,
    MARGIN_RIGHT,
    MARGIN_TOP,
    PLAYBACK_SPEEDS,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SEEK_RATE_MULTIPLIER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
    WINDOW_TITLE,
)
from src.arcade.data import FrameData, SessionData
from src.arcade.overlays import (
    ControlsLegend,
    DriverInfoPanel,
    LeaderboardPanel,
    ProgressBar,
    WeatherPanel,
)
from src.arcade.track import Track

logger = logging.getLogger(__name__)


class F1ArcadeWindow(arcade.Window):
    """Renders the race replay and owns the playback state machine."""

    def __init__(
        self,
        session_data: SessionData,
        track: Track,
        driver_main: str,
        driver_rival: str | None = None,
        year: int = 2024,
    ) -> None:
        super().__init__(
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            title=WINDOW_TITLE,
            resizable=True,
        )
        arcade.set_background_color(BG_COLOR)

        self._session = session_data
        self._track = track
        self._driver_main = driver_main
        self._driver_rival = driver_rival
        self._year = year

        self._frame_index: float = 0.0
        self._speed_idx: int = DEFAULT_SPEED_IDX
        self._is_paused: bool = False
        self._is_rewinding: bool = False
        self._is_forwarding: bool = False
        self._was_paused_before_hold: bool = False
        self._show_progress_bar: bool = True
        self._show_drs_zones: bool = True
        self._selected_drivers: set[str] = {driver_main}
        if driver_rival:
            self._selected_drivers.add(driver_rival)

        self._track.update_scaling(
            SCREEN_WIDTH, SCREEN_HEIGHT,
            margin_left=MARGIN_LEFT, margin_right=MARGIN_RIGHT,
            margin_bottom=MARGIN_BOTTOM, margin_top=MARGIN_TOP,
        )

        self._lap_label = arcade.Text(
            "LAP", 20, SCREEN_HEIGHT - 20, ACCENT, 11, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._lap_text = arcade.Text(
            "1/58", 20, SCREEN_HEIGHT - 36, TEXT_PRIMARY, 22, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._time_text = arcade.Text(
            "00:00:00  x1.0", 20, SCREEN_HEIGHT - 66,
            TEXT_TERTIARY, 12, font_name=FONT_BODY,
            anchor_x="left", anchor_y="top",
        )

        self._weather = WeatherPanel()
        self._leaderboard = LeaderboardPanel(
            x=SCREEN_WIDTH - LEADERBOARD_RIGHT_MARGIN,
            top_y=SCREEN_HEIGHT - 20,
            width=LEADERBOARD_WIDTH,
        )
        self._driver_info_main = DriverInfoPanel(
            x=20, top_y=SCREEN_HEIGHT - 200, width=DRIVER_BOX_WIDTH,
            height=DRIVER_BOX_HEIGHT, driver_code=driver_main,
            color=self._color_for(driver_main),
        )
        self._driver_info_rival: DriverInfoPanel | None = None
        if driver_rival:
            self._driver_info_rival = DriverInfoPanel(
                x=20, top_y=SCREEN_HEIGHT - 200 - DRIVER_BOX_HEIGHT - DRIVER_BOX_GAP,
                width=DRIVER_BOX_WIDTH, height=DRIVER_BOX_HEIGHT,
                driver_code=driver_rival, color=self._color_for(driver_rival),
            )

        self._progress_bar = ProgressBar(
            total_frames=session_data.total_frames,
            total_laps=session_data.max_lap_number,
            events=session_data.events,
            left_margin=MARGIN_LEFT, right_margin=MARGIN_RIGHT,
        )
        self._progress_bar.on_resize(SCREEN_WIDTH)
        self._controls_legend = ControlsLegend()

        self._car_label_main = arcade.Text(
            driver_main, 0, 0, self._color_for(driver_main),
            CAR_LABEL_FONT_SIZE, bold=True, font_name=FONT_BODY,
            anchor_x="center", anchor_y="bottom",
        )
        self._car_label_rival = arcade.Text(
            driver_rival or "", 0, 0,
            self._color_for(driver_rival) if driver_rival else TEXT_SECONDARY,
            CAR_LABEL_FONT_SIZE, bold=True, font_name=FONT_BODY,
            anchor_x="center", anchor_y="top",
        )

        logger.info(
            "F1ArcadeWindow ready: %s vs %s, %d drivers, %d frames",
            driver_main, driver_rival, len(session_data.frames_by_driver),
            session_data.total_frames,
        )

    # --- Arcade event loop -----------------------------------------------

    def on_update(self, delta_time: float) -> None:
        seek_rate = SEEK_RATE_MULTIPLIER * max(1.0, self.playback_speed)
        max_f = float(self._session.total_frames - 1)

        if self._is_rewinding:
            self._frame_index = max(0.0, self._frame_index - delta_time * FPS * seek_rate)
        elif self._is_forwarding:
            self._frame_index = min(max_f, self._frame_index + delta_time * FPS * seek_rate)

        if self._is_paused:
            return
        self._frame_index += delta_time * FPS * self.playback_speed
        self._frame_index = max(0.0, min(max_f, self._frame_index))

    def on_draw(self) -> None:
        self.clear()
        self._track.draw(show_drs=self._show_drs_zones)
        frame_idx = int(self._frame_index)
        frame = self._build_frame_dict(frame_idx)

        self._draw_car(self._driver_main, self._car_label_main, above=True)
        if self._driver_rival:
            self._draw_car(self._driver_rival, self._car_label_rival, above=False)

        track_len = self._session.circuit_length_m or 5300.0
        self._leaderboard.draw(
            frame, self._session.driver_colors, track_len, self._selected_drivers
        )
        self._weather.draw(frame, self.height)
        sorted_progress = self._leaderboard.sorted_progress(frame, track_len)
        self._driver_info_main.set_top(self._weather.bottom_y - 10)
        self._driver_info_main.draw(frame, sorted_progress)
        if self._driver_info_rival:
            self._driver_info_rival.set_top(
                self._weather.bottom_y - 10 - DRIVER_BOX_HEIGHT - DRIVER_BOX_GAP
            )
            self._driver_info_rival.draw(frame, sorted_progress)

        if self._show_progress_bar:
            self._progress_bar.draw(self.width, frame_idx)
        self._controls_legend.draw()
        self._update_hud(frame)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            self.close()
        elif symbol == arcade.key.SPACE:
            self._is_paused = not self._is_paused
        elif symbol == arcade.key.LEFT:
            self._was_paused_before_hold = self._is_paused
            self._is_rewinding = True
            self._is_paused = True
        elif symbol == arcade.key.RIGHT:
            self._was_paused_before_hold = self._is_paused
            self._is_forwarding = True
            self._is_paused = True
        elif symbol == arcade.key.UP:
            self._speed_idx = min(len(PLAYBACK_SPEEDS) - 1, self._speed_idx + 1)
        elif symbol == arcade.key.DOWN:
            self._speed_idx = max(0, self._speed_idx - 1)
        elif symbol == arcade.key.KEY_1:
            self._speed_idx = PLAYBACK_SPEEDS.index(0.5)
        elif symbol == arcade.key.KEY_2:
            self._speed_idx = PLAYBACK_SPEEDS.index(1.0)
        elif symbol == arcade.key.KEY_3:
            self._speed_idx = PLAYBACK_SPEEDS.index(2.0)
        elif symbol == arcade.key.KEY_4:
            self._speed_idx = PLAYBACK_SPEEDS.index(4.0)
        elif symbol == arcade.key.R:
            self._frame_index = 0.0
            self._speed_idx = DEFAULT_SPEED_IDX
            self._is_paused = False
        elif symbol == arcade.key.D:
            self._show_drs_zones = not self._show_drs_zones
        elif symbol == arcade.key.B:
            self._show_progress_bar = not self._show_progress_bar

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.LEFT:
            self._is_rewinding = False
            self._is_paused = self._was_paused_before_hold
        elif symbol == arcade.key.RIGHT:
            self._is_forwarding = False
            self._is_paused = self._was_paused_before_hold

    def on_mouse_press(self, x: int, y: int, button: int, modifiers: int) -> None:
        seek = self._progress_bar.on_mouse_press(x, y)
        if seek is not None:
            self._frame_index = float(seek)
            return
        code = self._leaderboard.hit_test(x, y)
        if code is None:
            return
        if modifiers & arcade.key.MOD_SHIFT:
            self._selected_drivers ^= {code}
        else:
            self._selected_drivers = {code}

    def on_resize(self, width: float, height: float) -> None:
        super().on_resize(width, height)
        self._track.update_scaling(
            int(width), int(height),
            margin_left=MARGIN_LEFT, margin_right=MARGIN_RIGHT,
            margin_bottom=MARGIN_BOTTOM, margin_top=MARGIN_TOP,
        )
        self._leaderboard.x = int(width) - LEADERBOARD_RIGHT_MARGIN
        self._leaderboard.set_top(int(height) - 20)
        self._lap_label.y = int(height) - 20
        self._lap_text.y = int(height) - 36
        self._time_text.y = int(height) - 66
        self._progress_bar.on_resize(int(width))

    # --- Helpers ---------------------------------------------------------

    @property
    def playback_speed(self) -> float:
        return PLAYBACK_SPEEDS[self._speed_idx]

    def _color_for(self, code: str | None) -> tuple[int, int, int]:
        if not code:
            return TEXT_SECONDARY
        return self._session.driver_colors.get(code, TEXT_PRIMARY)

    def _build_frame_dict(self, frame_idx: int) -> dict:
        drivers_dict: dict[str, dict] = {}
        main_frame: FrameData | None = None
        for code, frames in self._session.frames_by_driver.items():
            if not frames or frame_idx >= len(frames):
                continue
            f = frames[frame_idx]
            drivers_dict[code] = {
                "x": f.x, "y": f.y, "speed": f.speed, "gear": f.gear,
                "drs": f.drs, "throttle": f.throttle, "brake": f.brake,
                "lap": f.lap, "dist": f.dist, "rel_dist": f.rel_dist,
                "tyre": f.tyre, "tyre_life": f.tyre_life, "active": f.active,
            }
            if code == self._driver_main:
                main_frame = f

        return {
            "lap": main_frame.lap if main_frame else 1,
            "t": main_frame.t if main_frame else 0.0,
            "drivers": drivers_dict,
            "weather": {
                "track_temp": 45.0, "air_temp": 18.0, "humidity": 55.0,
                "wind_speed": 12.0, "wind_direction": 180.0, "rain_state": "DRY",
            },
        }

    def _draw_car(self, code: str, label: arcade.Text, above: bool) -> None:
        frames = self._session.frames_by_driver.get(code)
        if not frames:
            return
        idx = int(self._frame_index)
        if idx >= len(frames):
            return
        f = frames[idx]
        if not f.active:
            return
        sx, sy = self._track.project(f.x, f.y)
        color = self._color_for(code)
        arcade.draw_circle_filled(sx, sy, CAR_RADIUS, color)
        arcade.draw_circle_outline(sx, sy, CAR_RADIUS, CAR_BORDER_COLOR, CAR_BORDER_WIDTH)
        # Main driver label sits above the dot, rival below, so they never
        # overlap when the two cars are side by side.
        label.x = sx
        label.y = sy + CAR_RADIUS + 4 if above else sy - CAR_RADIUS - 4
        label.draw()

    def _update_hud(self, frame: dict) -> None:
        lap = frame.get("lap", 1)
        total = self._session.max_lap_number
        self._lap_text.text = f"{lap}/{total}"
        t = frame.get("t", 0.0)
        hh = int(t // 3600)
        mm = int((t % 3600) // 60)
        ss = int(t % 60)
        paused = "  PAUSED" if self._is_paused else ""
        self._time_text.text = (
            f"{hh:02d}:{mm:02d}:{ss:02d}  x{self.playback_speed}{paused}"
        )
        self._lap_label.draw()
        self._lap_text.draw()
        self._time_text.draw()
