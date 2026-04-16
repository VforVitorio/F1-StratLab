"""FastF1 session loading, per-driver telemetry resampling and pkl caching.

The `SessionLoader` class implemented in Phase 1 wraps FastF1's session
fetching and parallel per-driver telemetry processing, producing a list
of frames resampled to a common 25 Hz timeline alongside the
track-status and weather timelines. Results are persisted to
`data/cache/arcade/<gp>_<year>_race.pkl` so subsequent launches of the
same GP complete in under five seconds.

FastF1 is the data source; the resampling logic is a straight-forward
application of `numpy.interp` over the driver-indexed telemetry arrays.
Phase 1 fills this module.
"""

from __future__ import annotations
