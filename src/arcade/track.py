"""2D circuit geometry and rendering on the Arcade canvas.

The `Track` class implemented in Phase 1 builds a dense polyline from a
reference telemetry lap using `numpy.interp`, computes a KDTree
(`scipy.spatial.cKDTree`) for O(log N) projection of driver positions,
derives track normals from `numpy.gradient` plus the shoelace
orientation test, exposes a world-to-screen transform that honours a
rotation and left/right UI margins, and knows how to draw itself
(outline plus DRS zones plus finish line) at the current scale.

All of the underlying primitives (interpolation, KDTree, gradient,
shoelace) come from numpy / scipy — this module composes them into a
racing-line abstraction specific to this app.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import arcade
import numpy as np
from scipy.spatial import cKDTree

from src.arcade.config import SCREEN_HEIGHT, SCREEN_WIDTH

# Track status colors (from Tom Shaw f1-race-replay)
TRACK_STATUS_COLORS = {
    "GREEN": (150, 150, 150),  # Normal gray
    "YELLOW": (220, 180, 0),   # Caution yellow
    "RED": (200, 30, 30),      # Red flag
    "VSC": (200, 130, 50),     # Virtual safety car (amber)
    "SC": (180, 100, 30),      # Safety car (brown)
}

logger = logging.getLogger(__name__)


def plotDRSzones(example_lap) -> list[dict]:
    """Compute DRS zones from FastF1 example lap telemetry.

    Scans DRS column (values 10, 12, 14 = active) and identifies contiguous
    zones. Returns list of {start, end} coordinates.
    """
    x_val = example_lap["X"]
    y_val = example_lap["Y"]
    drs_zones = []
    drs_start = None

    for i, val in enumerate(example_lap["DRS"]):
        if val in [10, 12, 14]:  # DRS active
            if drs_start is None:
                drs_start = i
        else:  # DRS inactive
            if drs_start is not None:
                drs_end = i - 1
                zone = {
                    "start": {
                        "x": x_val.iloc[drs_start],
                        "y": y_val.iloc[drs_start],
                        "index": drs_start,
                    },
                    "end": {"x": x_val.iloc[drs_end], "y": y_val.iloc[drs_end], "index": drs_end},
                }
                drs_zones.append(zone)
                drs_start = None

    # Handle DRS zone extending to end of lap
    if drs_start is not None:
        drs_end = len(example_lap["DRS"]) - 1
        zone = {
            "start": {
                "x": x_val.iloc[drs_start],
                "y": y_val.iloc[drs_start],
                "index": drs_start,
            },
            "end": {"x": x_val.iloc[drs_end], "y": y_val.iloc[drs_end], "index": drs_end},
        }
        drs_zones.append(zone)

    return drs_zones


def build_track_from_example_lap(example_lap, track_width: float = 200) -> tuple:
    """Build track geometry from FastF1 example lap (fastest lap).

    Computes inner/outer track boundaries, world bounds, and DRS zones.
    Returns: (x_ref, y_ref, x_inner, y_inner, x_outer, y_outer,
              x_min, x_max, y_min, y_max, drs_zones)
    """
    drs_zones = plotDRSzones(example_lap)
    plot_x_ref = example_lap["X"]
    plot_y_ref = example_lap["Y"]

    # Compute tangent vectors (derivative of track)
    dx = np.gradient(plot_x_ref)
    dy = np.gradient(plot_y_ref)

    # Normalize tangents
    norm = np.sqrt(dx**2 + dy**2)
    norm[norm == 0] = 1.0
    dx /= norm
    dy /= norm

    # Compute normal vectors (perpendicular to tangent)
    nx = -dy
    ny = dx

    # Create inner/outer track boundaries
    x_outer = plot_x_ref + nx * (track_width / 2)
    y_outer = plot_y_ref + ny * (track_width / 2)
    x_inner = plot_x_ref - nx * (track_width / 2)
    y_inner = plot_y_ref - ny * (track_width / 2)

    # Compute world bounds
    x_min = min(plot_x_ref.min(), x_inner.min(), x_outer.min())
    x_max = max(plot_x_ref.max(), x_inner.max(), x_outer.max())
    y_min = min(plot_y_ref.min(), y_inner.min(), y_outer.min())
    y_max = max(plot_y_ref.max(), y_inner.max(), y_outer.max())

    return (
        plot_x_ref,
        plot_y_ref,
        x_inner,
        y_inner,
        x_outer,
        y_outer,
        x_min,
        x_max,
        y_min,
        y_max,
        drs_zones,
    )

# Rendering constants — unified with theme from config.py
# Inspired by Tom Shaw F1 broadcast graphics: white thick lines for track visibility
TRACK_LINE_WIDTH: float = 4.0  # Was 2.5, now thicker for prominence (Tom Shaw style)
TRACK_OUTLINE_COLOR: tuple[int, int, int] = (240, 240, 245)  # Off-white for prominence
DRS_ZONE_COLOR: tuple[int, int, int] = (16, 185, 129)  # Green (#10b981)
FINISH_LINE_COLOR: tuple[int, int, int] = (255, 255, 255)  # White
MARGIN_LEFT: float = 50.0
MARGIN_RIGHT: float = 50.0
MARGIN_TOP: float = 50.0
MARGIN_BOTTOM: float = 50.0


@dataclass
class DRSZone:
    """A DRS activation zone on the track.

    Defined by a start and end cumulative distance. When a driver reaches
    the start, they are within the DRS detection zone; the system draws
    a green highlight segment along the track.
    """

    start_distance_m: float
    end_distance_m: float


class Track:
    """2D circuit geometry with Tom Shaw-style inner/outer rendering.

    Builds track boundaries from reference lap (fastest), computes KDTree
    for efficient position projection, and renders as inner/outer track lines.
    """

    def __init__(
        self,
        reference_x: np.ndarray,
        reference_y: np.ndarray,
        reference_distance: np.ndarray,
        circuit_rotation_deg: float = 0.0,
        drs_zones: list[DRSZone] | None = None,
    ) -> None:
        """Initialize Track from reference lap coordinates.

        Args:
            reference_x: X coordinates (meters)
            reference_y: Y coordinates (meters)
            reference_distance: Cumulative distance (meters)
            circuit_rotation_deg: Rotation in degrees
            drs_zones: Optional DRS zone definitions (unused; computed from lap)
        """
        self.reference_x = reference_x
        self.reference_y = reference_y
        self.reference_distance = reference_distance
        self.circuit_rotation_deg = circuit_rotation_deg
        self.drs_zones = drs_zones or []

        # Build KDTree for position projection
        points = np.column_stack((reference_x, reference_y))
        self.kdtree = cKDTree(points)

        # World bounds
        self.world_min_x = float(np.min(reference_x))
        self.world_max_x = float(np.max(reference_x))
        self.world_min_y = float(np.min(reference_y))
        self.world_max_y = float(np.max(reference_y))

        # Pre-compute rotation values (Tom Shaw approach)
        self._rot_rad = float(np.deg2rad(circuit_rotation_deg))
        self._cos_rot = float(np.cos(self._rot_rad))
        self._sin_rot = float(np.sin(self._rot_rad))

        # Compute track orientation via shoelace formula (signed area)
        # Positive area = counterclockwise, Negative area = clockwise
        signed_area = 0.5 * float(
            np.sum(reference_x[:-1] * reference_y[1:] - reference_x[1:] * reference_y[:-1])
        )
        self.is_clockwise = signed_area < 0

        # Build inner/outer track lines from normals (Tom Shaw: track_width=200)
        self._build_inner_outer_lines(track_width=200)

        # Initialize scaling/transform (will be set by on_resize)
        self.scale = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.screen_inner_points: list[tuple[float, float]] = []
        self.screen_outer_points: list[tuple[float, float]] = []

        # Compute initial viewport
        self._compute_viewport()

        logger.info(
            f"Track initialised: {len(reference_x)} polyline points, "
            f"circuit rotation {circuit_rotation_deg}°, "
            f"is_clockwise={self.is_clockwise}"
        )

    def _build_inner_outer_lines(self, track_width: float = 200) -> None:
        """Build inner/outer track boundary lines from reference lap.

        Uses normal vectors to create parallel lines at ±track_width/2.
        """
        dx = np.gradient(self.reference_x)
        dy = np.gradient(self.reference_y)

        # Normalize tangents
        norm = np.sqrt(dx**2 + dy**2)
        norm[norm == 0] = 1.0
        dx /= norm
        dy /= norm

        # Normal vectors (perpendicular to tangent)
        nx = -dy
        ny = dx

        # Create inner/outer boundaries
        self.inner_x = self.reference_x - nx * (track_width / 2)
        self.inner_y = self.reference_y - ny * (track_width / 2)
        self.outer_x = self.reference_x + nx * (track_width / 2)
        self.outer_y = self.reference_y + ny * (track_width / 2)

        logger.info(f"Built inner/outer track lines (width={track_width}m)")

    def _compute_world_bounds_rotated(self) -> tuple[float, float, float, float]:
        """Compute rotated world bounds if circuit has rotation."""
        if not self._rot_rad:
            return self.world_min_x, self.world_max_x, self.world_min_y, self.world_max_y

        # Rotate all boundary points and recompute bounds
        world_cx = (self.world_min_x + self.world_max_x) / 2
        world_cy = (self.world_min_y + self.world_max_y) / 2

        # Sample points from inner/outer boundaries
        all_xs = list(self.inner_x) + list(self.outer_x) + list(self.reference_x)
        all_ys = list(self.inner_y) + list(self.outer_y) + list(self.reference_y)

        rotated_xs = []
        rotated_ys = []
        for x, y in zip(all_xs, all_ys):
            tx = x - world_cx
            ty = y - world_cy
            rx = tx * self._cos_rot - ty * self._sin_rot
            ry = tx * self._sin_rot + ty * self._cos_rot
            rotated_xs.append(rx + world_cx)
            rotated_ys.append(ry + world_cy)

        return min(rotated_xs), max(rotated_xs), min(rotated_ys), max(rotated_ys)

    def _compute_viewport(self) -> None:
        """Compute world-to-screen scale and pan based on window size.

        Uses Tom Shaw approach: accounts for rotated bounds and reserves
        UI margins. Called on initialization and resize.
        """
        self.update_scaling(SCREEN_WIDTH, SCREEN_HEIGHT)

    def update_scaling(self, screen_w: float, screen_h: float) -> None:
        """Recalculate scale and translation to fit track in screen dimensions.

        Accounts for circuit rotation and reserves left/right UI margins
        so overlays (HUD, leaderboard, etc.) don't overlap the track.
        Recomputes screen coordinates for all inner/outer track points.

        Args:
            screen_w: Screen width in pixels
            screen_h: Screen height in pixels
        """
        padding = 0.05
        world_cx = (self.world_min_x + self.world_max_x) / 2
        world_cy = (self.world_min_y + self.world_max_y) / 2

        def _rotate_about_center(x: float, y: float) -> tuple[float, float]:
            """Rotate point about world center."""
            tx = x - world_cx
            ty = y - world_cy
            rx = tx * self._cos_rot - ty * self._sin_rot
            ry = tx * self._sin_rot + ty * self._cos_rot
            return rx + world_cx, ry + world_cy

        # Build rotated extents from all track boundary points
        rotated_points = []
        for x, y in zip(self.inner_x, self.inner_y):
            rotated_points.append(_rotate_about_center(x, y))
        for x, y in zip(self.outer_x, self.outer_y):
            rotated_points.append(_rotate_about_center(x, y))

        xs = [p[0] for p in rotated_points]
        ys = [p[1] for p in rotated_points]
        world_x_min = min(xs) if xs else self.world_min_x
        world_x_max = max(xs) if xs else self.world_max_x
        world_y_min = min(ys) if ys else self.world_min_y
        world_y_max = max(ys) if ys else self.world_max_y

        world_w = max(1.0, world_x_max - world_x_min)
        world_h = max(1.0, world_y_max - world_y_min)

        # Reserve left/right UI margins so track never overlaps UI (leaderboard, etc.)
        left_ui_margin = MARGIN_LEFT
        right_ui_margin = MARGIN_RIGHT
        inner_w = max(1.0, screen_w - left_ui_margin - right_ui_margin)
        usable_w = inner_w * (1 - 2 * padding)
        usable_h = screen_h * (1 - 2 * padding)

        # Scale to fit whichever dimension is limiting
        scale_x = usable_w / world_w
        scale_y = usable_h / world_h
        self.scale = min(scale_x, scale_y)

        # Center world within available inner area (between left/right margins)
        screen_cx = left_ui_margin + inner_w / 2
        screen_cy = screen_h / 2

        self.pan_x = screen_cx - self.scale * world_cx
        self.pan_y = screen_cy - self.scale * world_cy

        # Update pre-computed screen coordinates
        self.screen_inner_points = [
            self.world_to_screen(x, y) for x, y in zip(self.inner_x, self.inner_y)
        ]
        self.screen_outer_points = [
            self.world_to_screen(x, y) for x, y in zip(self.outer_x, self.outer_y)
        ]

        logger.info(
            f"Scaling updated: screen=({screen_w:.0f}×{screen_h:.0f}), "
            f"scale={self.scale:.2f}, pan=({self.pan_x:.1f}, {self.pan_y:.1f})"
        )

    def world_to_screen(self, x: float, y: float) -> tuple[float, float]:
        """Convert world coords to screen coords with rotation support.

        Follows Tom Shaw approach: rotate about world center, then scale+translate.
        """
        # Rotate around track center if rotation is set
        if self._rot_rad:
            world_cx = (self.world_min_x + self.world_max_x) / 2
            world_cy = (self.world_min_y + self.world_max_y) / 2

            tx = x - world_cx
            ty = y - world_cy
            rx = tx * self._cos_rot - ty * self._sin_rot
            ry = tx * self._sin_rot + ty * self._cos_rot
            x, y = rx + world_cx, ry + world_cy

        # Scale and translate to screen
        screen_x = x * self.scale + self.pan_x
        screen_y = y * self.scale + self.pan_y
        return screen_x, screen_y

    def project_position(self, x: float, y: float) -> tuple[int, float]:
        """Find the nearest point on the track polyline to a given position.

        Uses KDTree for O(log N) lookup. Returns the index of the nearest
        point and the distance from the query point to that point.

        Args:
            x: World X coordinate
            y: World Y coordinate

        Returns:
            Tuple of (nearest_index, distance_to_track)
        """
        distance, index = self.kdtree.query([x, y])
        return int(index), float(distance)

    def on_resize(self, width: float, height: float) -> None:
        """Recompute viewport when window is resized.

        Args:
            width: New window width in pixels
            height: New window height in pixels
        """
        self._compute_viewport()

    def draw(self, track_status: str = "GREEN") -> None:
        """Render track with Tom Shaw style: inner/outer lines + DRS zones.

        Args:
            track_status: Track status ("GREEN", "YELLOW", "SC", "VSC", "RED")
        """
        # Get track color from status
        color = TRACK_STATUS_COLORS.get(track_status, TRACK_STATUS_COLORS["GREEN"])

        # Draw inner/outer track lines with world-to-screen transform
        if not self.screen_inner_points:
            # First time: compute screen coordinates for all inner/outer points
            self.screen_inner_points = [
                self.world_to_screen(x, y)
                for x, y in zip(self.inner_x, self.inner_y)
            ]
            self.screen_outer_points = [
                self.world_to_screen(x, y)
                for x, y in zip(self.outer_x, self.outer_y)
            ]

        # Draw inner track line
        if len(self.screen_inner_points) > 1:
            arcade.draw_line_strip(self.screen_inner_points, color, TRACK_LINE_WIDTH)

        # Draw outer track line
        if len(self.screen_outer_points) > 1:
            arcade.draw_line_strip(self.screen_outer_points, color, TRACK_LINE_WIDTH)

        # Draw DRS zones (green segments on outer edge)
        if self.drs_zones:
            drs_color = DRS_ZONE_COLOR
            for zone in self.drs_zones:
                start_idx = zone.get("start", {}).get("index", 0) if isinstance(zone, dict) else 0
                end_idx = zone.get("end", {}).get("index", len(self.outer_x)-1) if isinstance(zone, dict) else len(self.outer_x)-1

                # Extract DRS segment from outer track
                drs_segment = self.screen_outer_points[start_idx : end_idx + 1]
                if len(drs_segment) > 1:
                    arcade.draw_line_strip(drs_segment, drs_color, TRACK_LINE_WIDTH * 2)

        # Draw finish line (checkered pattern at start)
        self._draw_finish_line()

        logger.debug(
            f"Track drawn: status={track_status}, "
            f"inner_pts={len(self.screen_inner_points)}, "
            f"outer_pts={len(self.screen_outer_points)}, "
            f"drs_zones={len(self.drs_zones)}"
        )

    def _draw_finish_line(self) -> None:
        """Draw checkered finish line between inner/outer start points."""
        if not self.screen_inner_points or not self.screen_outer_points:
            return

        start_inner = self.screen_inner_points[0]
        start_outer = self.screen_outer_points[0]

        # Direction vector from inner to outer
        dx = start_outer[0] - start_inner[0]
        dy = start_outer[1] - start_inner[1]
        length = np.sqrt(dx**2 + dy**2)

        if length < 1:
            return

        # Normalize and extend
        dx_norm = dx / length
        dy_norm = dy / length
        extension = 20

        extended_inner = (start_inner[0] - extension * dx_norm, start_inner[1] - extension * dy_norm)
        extended_outer = (start_outer[0] + extension * dx_norm, start_outer[1] + extension * dy_norm)

        # Draw checkered pattern
        num_squares = 20
        for i in range(num_squares):
            t1 = i / num_squares
            t2 = (i + 1) / num_squares

            x1 = extended_inner[0] + t1 * (extended_outer[0] - extended_inner[0])
            y1 = extended_inner[1] + t1 * (extended_outer[1] - extended_inner[1])
            x2 = extended_inner[0] + t2 * (extended_outer[0] - extended_inner[0])
            y2 = extended_inner[1] + t2 * (extended_outer[1] - extended_inner[1])

            color = FINISH_LINE_COLOR if i % 2 == 0 else arcade.color.BLACK
            arcade.draw_line(x1, y1, x2, y2, color, TRACK_LINE_WIDTH)
