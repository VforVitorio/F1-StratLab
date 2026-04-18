"""The Arcade race replay view orchestrating playback, cars, and panels.

Refactored from a root `arcade.Window` into an `arcade.View` so the menu
view can spawn a fresh replay whenever the user confirms a configuration.
Construction contract: the caller creates the `arcade.Window` first, loads
`SessionData` + `Track` in the main thread, and hands them plus the window
reference to this view so every `arcade.Text` allocated here (and in child
panels) has an active GL context from the start.
"""

from __future__ import annotations

import logging
import os

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
    SEEK_RATE_MULTIPLIER,
    STREAM_BROADCAST_EVERY_N_FRAMES,
    STREAM_HISTORY_TAIL,
    STREAM_HOST,
    STREAM_PORT,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_TERTIARY,
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


class F1ArcadeView(arcade.View):
    """Renders the race replay and owns the playback state machine.

    Lives inside a `arcade.Window` provided by `main.py`. The window is
    passed in so self.window is populated immediately — every arcade.Text
    created in this __init__ or its child panels sees the active GL context
    right away. Call via `window.show_view(F1ArcadeView(window, ...))`."""

    def __init__(
        self,
        window: arcade.Window,
        session_data: SessionData,
        track: Track,
        driver_main: str,
        driver_rival: str | None = None,
        year: int = 2024,
        strategy_enabled: bool = False,
        team: str | None = None,
    ) -> None:
        super().__init__(window=window)
        arcade.set_background_color(BG_COLOR)

        self._session = session_data
        self._track = track
        self._driver_main = driver_main
        self._driver_rival = driver_rival
        self._year = year
        self._strategy_enabled = strategy_enabled
        self._team = team
        self._strategy_connector = None  # set by __init__ if strategy_enabled
        self._strategy_state = None
        self._stream_server = None
        self._broadcast_tick: int = 0

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

        w, h = window.width, window.height
        self._track.update_scaling(
            w, h,
            margin_left=MARGIN_LEFT, margin_right=MARGIN_RIGHT,
            margin_bottom=MARGIN_BOTTOM, margin_top=MARGIN_TOP,
        )

        self._lap_label = arcade.Text(
            "LAP", 20, h - 20, ACCENT, 11, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._lap_text = arcade.Text(
            "1/58", 20, h - 36, TEXT_PRIMARY, 22, bold=True,
            font_name=FONT_TITLE, anchor_x="left", anchor_y="top",
        )
        self._time_text = arcade.Text(
            "00:00:00  x1.0", 20, h - 66,
            TEXT_TERTIARY, 12, font_name=FONT_BODY,
            anchor_x="left", anchor_y="top",
        )

        self._weather = WeatherPanel()
        self._leaderboard = LeaderboardPanel(
            x=w - LEADERBOARD_RIGHT_MARGIN,
            top_y=h - 20,
            width=LEADERBOARD_WIDTH,
        )
        self._driver_info_main = DriverInfoPanel(
            x=20, top_y=h - 200, width=DRIVER_BOX_WIDTH,
            height=DRIVER_BOX_HEIGHT, driver_code=driver_main,
            color=self._color_for(driver_main),
        )
        self._driver_info_rival: DriverInfoPanel | None = None
        if driver_rival:
            self._driver_info_rival = DriverInfoPanel(
                x=20, top_y=h - 200 - DRIVER_BOX_HEIGHT - DRIVER_BOX_GAP,
                width=DRIVER_BOX_WIDTH, height=DRIVER_BOX_HEIGHT,
                driver_code=driver_rival, color=self._color_for(driver_rival),
            )

        self._progress_bar = ProgressBar(
            total_frames=session_data.total_frames,
            total_laps=session_data.max_lap_number,
            events=session_data.events,
            left_margin=MARGIN_LEFT, right_margin=MARGIN_RIGHT,
        )
        self._progress_bar.on_resize(w)
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

        if self._strategy_enabled:
            self._init_strategy_layer()

        logger.info(
            "F1ArcadeView ready: %s vs %s, %d drivers, %d frames, strategy=%s",
            driver_main, driver_rival, len(session_data.frames_by_driver),
            session_data.total_frames, self._strategy_enabled,
        )

    def _init_strategy_layer(self) -> None:
        """Start the local strategy driver and the TCP broadcast server.

        The strategy UI lives entirely in the dashboard subprocess — the
        arcade replay keeps the track, leaderboard and car animations
        (the replay-first concerns) and broadcasts merged
        arcade+strategy state over TCP so the dashboard can render the
        orchestrator card, the six sub-agent cards and the charts."""
        from src.arcade.strategy import SimConnector, SimulateRequestDTO, StrategyState
        from src.arcade.stream import TelemetryStreamServer

        gp_name = self._resolve_gp_name()
        # Provider defaults to OpenAI (what the agents load with
        # ``F1_LLM_PROVIDER=openai`` — ChatOpenAI model=gpt-4.1-mini for
        # N25-N30 and the orchestrator model for N31). ``F1_LLM_PROVIDER``
        # env wins so a user running LM Studio locally (set it to
        # "lmstudio") keeps working without a code edit.
        provider = os.environ.get("F1_LLM_PROVIDER") or "openai"
        request = SimulateRequestDTO(
            year=self._year,
            gp=gp_name,
            driver=self._driver_main,
            team=self._team or "",
            driver2=self._driver_rival,
            risk_tolerance=0.5,
            no_llm=False,
            provider=provider,
            interval_s=0.0,
        )
        self._strategy_state = StrategyState()
        self._strategy_connector = SimConnector(
            request=request, state=self._strategy_state
        )
        self._strategy_connector.start()

        try:
            self._stream_server = TelemetryStreamServer(
                host=STREAM_HOST, port=STREAM_PORT
            )
            self._stream_server.start()
        except OSError as exc:
            logger.warning("Stream server failed to bind %s:%d (%s)",
                           STREAM_HOST, STREAM_PORT, exc)
            self._stream_server = None

    def _resolve_gp_name(self) -> str:
        """Return the GP label fed to the strategy pipeline.

        Prefers the FastF1 Location (``Suzuka``, ``Melbourne``, …) because
        that is what the ``data/raw/<year>/`` folders use. Falls back to
        ``get_gp_names(year)`` (sourced from the canonical per-year
        calendar JSON) and finally to ``GP_TO_LOCATION`` for menu inputs
        that still carry a country-style label from the legacy table."""
        from src.arcade.config import GP_TO_LOCATION, get_gp_names
        if self._session.location:
            return self._session.location
        gp_name = self._session.gp_name or get_gp_names(self._year).get(1, "Sakhir")
        return GP_TO_LOCATION.get(gp_name, gp_name)

    def on_hide_view(self) -> None:
        """Tear down the SSE connector and stream server on view swap/close."""
        if self._strategy_connector is not None:
            self._strategy_connector.stop()
        if self._stream_server is not None:
            self._stream_server.stop()
            self._stream_server = None

    # --- Arcade event loop -----------------------------------------------

    def on_update(self, delta_time: float) -> None:
        seek_rate = SEEK_RATE_MULTIPLIER * max(1.0, self.playback_speed)
        max_f = float(self._session.total_frames - 1)

        if self._is_rewinding:
            self._frame_index = max(0.0, self._frame_index - delta_time * FPS * seek_rate)
        elif self._is_forwarding:
            self._frame_index = min(max_f, self._frame_index + delta_time * FPS * seek_rate)

        if not self._is_paused:
            self._frame_index += delta_time * FPS * self.playback_speed
            self._frame_index = max(0.0, min(max_f, self._frame_index))

        self._broadcast_if_due()

    def _broadcast_if_due(self) -> None:
        """Throttle the TCP broadcast to ~10 Hz regardless of arcade FPS."""
        if self._stream_server is None or self._strategy_state is None:
            return
        self._broadcast_tick = (self._broadcast_tick + 1) % STREAM_BROADCAST_EVERY_N_FRAMES
        if self._broadcast_tick != 0:
            return
        if self._stream_server.client_count() == 0:
            return  # no subscriber, skip the serialisation cost
        frame_idx = int(self._frame_index)
        payload = {
            "arcade": self._build_arcade_snapshot(frame_idx),
            "strategy": self._strategy_state.snapshot_dict(STREAM_HISTORY_TAIL),
            "playback": {
                "speed": self.playback_speed,
                "paused": self._is_paused,
                "frame_index": frame_idx,
                "total_frames": self._session.total_frames,
            },
        }
        self._stream_server.broadcast(payload)

    def _build_arcade_snapshot(self, frame_idx: int) -> dict:
        """Compact version of the per-frame dict the dashboard needs.

        Lighter than the internal `_build_frame_dict` consumed by the
        panels: we drop fields the dashboard does not use (rel_dist,
        throttle, brake, active flag) to keep the broadcast JSON small."""
        drivers: dict[str, dict] = {}
        for code, frames in self._session.frames_by_driver.items():
            if not frames or frame_idx >= len(frames):
                continue
            f = frames[frame_idx]
            drivers[code] = {
                "lap": f.lap,
                "dist": round(f.dist, 1),
                "speed": round(f.speed, 1),
                "compound": f.tyre,
                "tyre_life": round(f.tyre_life, 1),
            }
        main_frame = None
        main_frames = self._session.frames_by_driver.get(self._driver_main)
        if main_frames and frame_idx < len(main_frames):
            main_frame = main_frames[frame_idx]
        return {
            "gp_name": self._session.gp_name,
            "year": self._year,
            "lap": main_frame.lap if main_frame else 1,
            "t": main_frame.t if main_frame else 0.0,
            "total_laps": self._session.max_lap_number,
            "driver_main": self._driver_main,
            "driver_rival": self._driver_rival,
            "drivers": drivers,
        }

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
        self._weather.draw(frame, self.window.height)
        sorted_progress = self._leaderboard.sorted_progress(frame, track_len)
        self._driver_info_main.set_top(self._weather.bottom_y - 10)
        self._driver_info_main.draw(frame, sorted_progress)
        if self._driver_info_rival:
            self._driver_info_rival.set_top(
                self._weather.bottom_y - 10 - DRIVER_BOX_HEIGHT - DRIVER_BOX_GAP
            )
            self._driver_info_rival.draw(frame, sorted_progress)

        if self._show_progress_bar:
            self._progress_bar.draw(self.window.width, frame_idx)
        self._controls_legend.draw()
        self._update_hud(frame)

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        if symbol == arcade.key.ESCAPE:
            self.window.close()
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
