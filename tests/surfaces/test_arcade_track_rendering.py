"""Track rendering parity and resize invalidation in a hidden native GL window."""

from __future__ import annotations

import numpy as np
import pytest

import arcade
from src.arcade.config import (
    DRS_COLOR,
    DRS_WIDTH,
    FINISH_CHEQUER_SEGMENTS,
    FINISH_CHEQUER_WIDTH,
    TRACK_EDGE_COLOR,
    TRACK_EDGE_WIDTH,
)
from src.arcade.track import Track, track_viewport


@pytest.fixture
def window():
    """Use real GL without showing a desktop window; CI needs a display/GL driver."""
    import os
    import sys

    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        pytest.skip("Native GL rendering requires a display (for example, Xvfb)")
    window = arcade.Window(1280, 720, visible=False, vsync=False)
    yield window
    window.close()


def make_track() -> Track:
    """Return a small curved circuit with two separated DRS runs."""
    angle = np.linspace(0, 2 * np.pi, 100)
    flags = np.zeros(100)
    flags[10:25] = flags[55:75] = 12
    return Track(
        1800 * np.cos(angle),
        1000 * np.sin(angle),
        flags,
        rotation_deg=17,
        interp_ref=100,
        interp_edge=200,
    )


def draw_previous(track: Track, **style) -> None:
    """Render with the pre-cache primitives as a pixel oracle for this regression."""
    edge_color = style.get("edge_color", TRACK_EDGE_COLOR)
    edge_width = style.get("edge_width", TRACK_EDGE_WIDTH)
    for points in (track._screen_inner, track._screen_outer):
        if len(points) >= 2:
            arcade.draw_line_strip([tuple(p) for p in points], edge_color, edge_width)
    if style.get("show_drs", True):
        for points in track._screen_drs_segments:
            if len(points) >= 2:
                arcade.draw_line_strip(
                    [tuple(p) for p in points],
                    style.get("drs_color", DRS_COLOR),
                    style.get("drs_width", DRS_WIDTH),
                )
    if style.get("show_finish_line", True) and track._screen_finish is not None:
        (ix, iy), (ox, oy) = track._screen_finish
        for segment in range(FINISH_CHEQUER_SEGMENTS):
            t0 = segment / FINISH_CHEQUER_SEGMENTS
            t1 = (segment + 1) / FINISH_CHEQUER_SEGMENTS
            color = (255, 255, 255) if segment % 2 == 0 else (20, 20, 20)
            arcade.draw_line(
                ix + (ox - ix) * t0,
                iy + (oy - iy) * t0,
                ix + (ox - ix) * t1,
                iy + (oy - iy) * t1,
                color,
                FINISH_CHEQUER_WIDTH,
            )


def pixels(window, draw) -> np.ndarray:
    """Read the framebuffer after a completed draw, without a window screenshot."""
    window.clear()
    draw()
    window.ctx.finish()
    return np.frombuffer(window.ctx.screen.read(components=4), dtype=np.uint8).copy()


@pytest.mark.parametrize(
    "style",
    [
        {},
        {"show_drs": False},
        {"show_finish_line": False},
        {"show_drs": False, "show_finish_line": False},
        {"edge_color": (220, 30, 90), "edge_width": 1, "drs_color": (20, 210, 180), "drs_width": 4},
        {"edge_color": (220, 30, 90, 120), "drs_color": (20, 210, 180, 150)},
    ],
)
def test_cached_render_matches_previous_after_resize(window, style):
    track = make_track()
    for width, height in ((1280, 720), (1000, 800)):
        track.update_scaling(track_viewport(width, height))
        expected = pixels(window, lambda: draw_previous(track, **style))
        actual = pixels(window, lambda: track.draw(**style))
        np.testing.assert_array_equal(actual, expected)


def test_warm_draw_reuses_geometry_and_resize_rebuilds(window, monkeypatch):
    track = make_track()
    track.update_scaling(track_viewport(1280, 720))
    track.draw()
    batches = track._render_batches
    from arcade import shape_list

    with monkeypatch.context() as guard:

        def unexpected_build(*args, **kwargs):
            pytest.fail("A warm draw rebuilt static GPU geometry")

        guard.setattr(shape_list, "create_line_strip", unexpected_build)
        guard.setattr(shape_list, "create_line", unexpected_build)
        guard.setattr(arcade, "draw_line_strip", unexpected_build)
        guard.setattr(arcade, "draw_line", unexpected_build)
        track.draw(show_drs=False, show_finish_line=False)
        track.draw()
    assert track._render_batches is batches
    track.update_scaling(track_viewport(1000, 800))
    assert track._render_batches is None
    track.draw()
    assert track._render_batches is not batches
    np.testing.assert_array_equal(
        pixels(window, track.draw),
        pixels(window, lambda: draw_previous(track)),
    )


def test_style_change_updates_cached_geometry(window):
    track = make_track()
    track.update_scaling(track_viewport(1280, 720))
    track.draw()
    style = {
        "edge_color": (250, 70, 50),
        "edge_width": 5,
        "drs_color": (40, 100, 230),
        "drs_width": 1,
    }
    np.testing.assert_array_equal(
        pixels(window, lambda: track.draw(**style)),
        pixels(window, lambda: draw_previous(track, **style)),
    )


def test_empty_track_can_scale_and_draw_without_gl():
    track = Track(np.zeros(0), np.zeros(0), np.zeros(0))
    track.update_scaling(track_viewport(1280, 720))
    track.draw()
    assert track.project(10, 20) == (0.0, 0.0)
