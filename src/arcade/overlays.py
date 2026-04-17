"""Strategic overlays and UI panels for Arcade race replay.

This module contains UI components and render functions for both
basic information displays (weather, leaderboard, driver info) and
SSE-derived strategy overlays (action badges, scenario bars, etc.).

Phase 2 UI panels (independent of SSE):
- WeatherPanel: track/air temperature, humidity, wind, rain
- LeaderboardPanel: driver standings with progress
- DriverInfoPanel: detailed telemetry for selected driver
- ProgressBar: lap counter and race timeline

Phases 3+ (SSE stream overlays):
- Tier A: action badge, scenario score bars, confidence bar, pace/risk chips
- Tier B: pit plan, guardrails, RCM banners, agent dots, radio alerts
- Tier C: pit animations, summary scene cards
"""

from __future__ import annotations

import logging

import arcade

from src.arcade.config import (
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    THEME_ACCENT,
    THEME_TEXT_PRIMARY,
    THEME_TEXT_SECONDARY,
    THEME_TEXT_TERTIARY,
    THEME_SUCCESS,
)

logger = logging.getLogger(__name__)

# Panel layout constants
LEFT_PANEL_X = 20
LEFT_PANEL_WIDTH = 280
LEFT_PANEL_TOP_OFFSET = 40

RIGHT_PANEL_X = SCREEN_WIDTH - 260
RIGHT_PANEL_WIDTH = 240

BOTTOM_PANEL_HEIGHT = 80
BOTTOM_PANEL_Y = BOTTOM_PANEL_HEIGHT


class WeatherPanel:
    """Displays track and ambient weather conditions.

    Rendered on left side of screen. Updates each frame from frame data.
    """

    def __init__(self, x: float = LEFT_PANEL_X, y: float = SCREEN_HEIGHT - LEFT_PANEL_TOP_OFFSET) -> None:
        self.x = x
        self.y = y
        self.width = LEFT_PANEL_WIDTH
        self.visible = True

    def draw(self, frame: dict | None) -> None:
        """Render weather panel with current frame data."""
        if not self.visible or not frame:
            return

        weather = frame.get("weather")
        if not weather:
            return

        y_pos = self.y
        arcade.draw_text(
            "Weather",
            int(self.x),
            int(y_pos),
            THEME_TEXT_PRIMARY,
            font_size=16,
            bold=True,
        )

        y_pos -= 25
        lines = [
            f"Track: {weather.get('track_temp', 0):.1f}°C",
            f"Air: {weather.get('air_temp', 0):.1f}°C",
            f"Humidity: {weather.get('humidity', 0):.0f}%",
            f"Wind: {weather.get('wind_speed', 0):.1f} km/h",
            f"Rain: {weather.get('rain_state', 'DRY')}",
        ]

        for line in lines:
            arcade.draw_text(
                line,
                int(self.x + 12),
                int(y_pos),
                THEME_TEXT_SECONDARY,
                font_size=12,
            )
            y_pos -= 18


class LeaderboardPanel:
    """Displays driver standings with positions and gaps.

    Rendered on right side of screen. Uses driver progress metrics
    from frame data to rank drivers.
    """

    def __init__(self, x: float = RIGHT_PANEL_X, y: float = SCREEN_HEIGHT - LEFT_PANEL_TOP_OFFSET) -> None:
        self.x = x
        self.y = y
        self.width = RIGHT_PANEL_WIDTH
        self.visible = True
        self.max_entries = 10  # Show top 10 drivers

    def draw(
        self,
        frame: dict | None,
        driver_colors: dict[str, tuple[int, int, int]] | None = None,
        track_ref_length: float = 0.0,
    ) -> None:
        """Render leaderboard with driver positions."""
        if not self.visible or not frame or "drivers" not in frame:
            return

        driver_colors = driver_colors or {}
        drivers = frame.get("drivers", {})

        # Compute progress for each driver (lap + projected distance along track)
        driver_progress = {}
        for code, pos_data in drivers.items():
            lap = pos_data.get("lap", 1)
            dist = pos_data.get("dist", 0.0)
            progress = (lap - 1) * track_ref_length + dist
            driver_progress[code] = progress

        # Sort by progress (descending)
        sorted_drivers = sorted(driver_progress.items(), key=lambda x: x[1], reverse=True)

        y_pos = self.y
        arcade.draw_text(
            "Leaderboard",
            int(self.x),
            int(y_pos),
            THEME_TEXT_PRIMARY,
            font_size=16,
            bold=True,
        )

        y_pos -= 25
        for rank, (code, progress) in enumerate(sorted_drivers[: self.max_entries], 1):
            color = driver_colors.get(code, THEME_TEXT_SECONDARY)
            arcade.draw_text(
                f"{rank}. {code}",
                int(self.x + 12),
                int(y_pos),
                color,
                font_size=12,
            )
            y_pos -= 18


class DriverInfoPanel:
    """Displays detailed telemetry for a selected driver.

    Shows speed, gear, DRS state, tyre compound, gaps to ahead/behind.
    """

    def __init__(self, x: float = LEFT_PANEL_X, y: float = SCREEN_HEIGHT - 300) -> None:
        self.x = x
        self.y = y
        self.width = LEFT_PANEL_WIDTH
        self.visible = True

    def draw(self, driver_code: str | None, frame: dict | None, driver_colors: dict | None = None) -> None:
        """Render driver info panel."""
        if not self.visible or not driver_code or not frame:
            return

        drivers = frame.get("drivers", {})
        if driver_code not in drivers:
            return

        driver_data = drivers[driver_code]
        driver_colors = driver_colors or {}
        color = driver_colors.get(driver_code, THEME_ACCENT)

        # Panel background
        panel_height = 160
        arcade.draw_rect_filled(
            arcade.XYWH(
                int(self.x + self.width // 2),
                int(self.y - panel_height // 2),
                int(self.width),
                int(panel_height),
            ),
            (30, 30, 40),
        )

        y_pos = self.y
        arcade.draw_text(
            f"Driver: {driver_code}",
            int(self.x + 12),
            int(y_pos),
            color,
            font_size=14,
            bold=True,
        )

        y_pos -= 22
        lines = [
            f"Speed: {driver_data.get('speed', 0):.0f} km/h",
            f"Gear: {driver_data.get('gear', 0)}",
            f"DRS: {'ON' if driver_data.get('drs') else 'OFF'}",
            f"Compound: {driver_data.get('compound', 'N/A')}",
            f"Lap: {driver_data.get('lap', 1)}",
        ]

        for line in lines:
            arcade.draw_text(
                line,
                int(self.x + 12),
                int(y_pos),
                THEME_TEXT_SECONDARY,
                font_size=11,
            )
            y_pos -= 18


class ProgressBar:
    """Race progress bar showing lap count and timeline.

    Renders at bottom of screen. Shows current lap, total laps, and
    a graphical bar representing race progress.
    """

    def __init__(
        self,
        x: float = 50,
        y: float = BOTTOM_PANEL_Y,
        width: float = SCREEN_WIDTH - 100,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.height = 40
        self.visible = True

    def draw(
        self,
        current_frame: int,
        total_frames: int,
        current_lap: int,
        total_laps: int | None = None,
    ) -> None:
        """Render progress bar."""
        if not self.visible or total_frames == 0:
            return

        # Bar background
        arcade.draw_rect_outline(
            arcade.XYWH(
                int(self.x + self.width // 2),
                int(self.y),
                int(self.width),
                int(self.height),
            ),
            THEME_TEXT_TERTIARY,
            2,
        )

        # Progress fill
        if total_frames > 0:
            fill_width = (current_frame / total_frames) * self.width
            if fill_width > 0:
                arcade.draw_rect_filled(
                    arcade.XYWH(
                        int(self.x + fill_width // 2),
                        int(self.y),
                        int(fill_width),
                        int(self.height),
                    ),
                    THEME_SUCCESS,
                )

        # Lap text
        lap_str = f"Lap {current_lap}"
        if total_laps:
            lap_str += f"/{total_laps}"

        arcade.draw_text(
            lap_str,
            int(self.x + 10),
            int(self.y - 12),
            THEME_TEXT_PRIMARY,
            font_size=12,
            bold=True,
        )

        # Progress percentage
        progress_pct = (current_frame / total_frames) * 100 if total_frames > 0 else 0
        arcade.draw_text(
            f"{progress_pct:.0f}%",
            int(self.x + self.width - 40),
            int(self.y - 12),
            THEME_TEXT_SECONDARY,
            font_size=11,
        )
