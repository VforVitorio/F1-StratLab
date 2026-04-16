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
