"""The top-level Arcade window that composes every rendering layer.

Subsequent phases add the track, the cars, the playback engine, the SSE
stream drain, and the strategic overlays. Phase 0 ships only a black
window with a placeholder message so the dependency chain and the
`f1-arcade` console entry point can be validated end to end before any
real rendering work starts.
"""

from __future__ import annotations

import argparse

import arcade

from src.arcade.config import SCREEN_HEIGHT, SCREEN_WIDTH, WINDOW_TITLE


class F1ArcadeWindow(arcade.Window):
    """Main Arcade window for the race replay.

    Phase 0 renders only a centred placeholder. Later phases layer in
    the circuit (Phase 1), the cars and playback engine (Phase 2), the
    strategic overlays fed by the SSE stream (Phases 3–5), and the
    summary scene (Phase 5). The window is resizable so the upcoming
    world-to-screen transform can react to resize events.

    `arcade.Text` objects are created once in `__init__` and redrawn
    each frame: Arcade's `draw_text` is explicitly documented as slow
    and triggers a PerformanceWarning on every call.
    """

    def __init__(self, args: argparse.Namespace | None = None) -> None:
        super().__init__(
            width=SCREEN_WIDTH,
            height=SCREEN_HEIGHT,
            title=WINDOW_TITLE,
            resizable=True,
        )
        self._args = args
        arcade.set_background_color(arcade.color.BLACK)
        self._title_text = arcade.Text(
            text="F1 Strategy Manager — Race Replay",
            x=SCREEN_WIDTH // 2,
            y=SCREEN_HEIGHT // 2 + 30,
            color=arcade.color.WHITE,
            font_size=26,
            anchor_x="center",
            anchor_y="center",
            bold=True,
        )
        self._subtitle_text = arcade.Text(
            text="Phase 0 smoke test — press ESC to close",
            x=SCREEN_WIDTH // 2,
            y=SCREEN_HEIGHT // 2 - 20,
            color=arcade.color.LIGHT_GRAY,
            font_size=14,
            anchor_x="center",
            anchor_y="center",
        )

    def on_draw(self) -> None:
        """Clear the frame and render the layers enabled in the current phase."""
        self.clear()
        self._title_text.draw()
        self._subtitle_text.draw()

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        """Global key handler. ESC closes the window; later phases add more keys."""
        if symbol == arcade.key.ESCAPE:
            self.close()

    def on_resize(self, width: float, height: float) -> None:
        """Keep the placeholder text centred when the user resizes the window."""
        super().on_resize(width, height)
        self._title_text.x = int(width) // 2
        self._title_text.y = int(height) // 2 + 30
        self._subtitle_text.x = int(width) // 2
        self._subtitle_text.y = int(height) // 2 - 20
