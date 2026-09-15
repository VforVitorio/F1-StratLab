"""Shared skip-guards for tests that need Hugging-Face-hosted model weights or data.

``tests/README``-equivalent for this file: most of the suite runs against
``data/`` (models + processed parquet), which is fetched from Hugging Face on
first use and absent on CI runners by design (see CLAUDE.md section 9 /
"Data / models are NOT in git"). Individual test files used to each hand-roll
their own ``_HAS_MODELS = (path).exists()`` + ``pytest.mark.skipif(...)`` pair
-- 22 near-identical copies of the tire-degradation-routing-config check alone
(21 module-level ``skipif`` guards plus one fixture-scope ``pytest.skip``), two
of which had already drifted to ``.is_file()`` instead of ``.exists()``.
Import the constants below instead of restating the check.

Tests that gate on a DIFFERENT model artifact (overtake, pit prediction, lap
time) are intentionally NOT covered here -- collapsing those into one boolean
would hide the fact that they need a different file present, which is real
information, not duplication.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    # The arcade tests do not exercise gamepad input. Disabling pyglet's
    # process-wide XInput polling thread keeps it out of later test teardown.
    try:
        import pyglet
    except ImportError:
        pass
    else:
        pyglet.options["win32_disable_xinput"] = True
        pyglet.options["audio"] = ("silent",)

ROOT = Path(__file__).parent.parent

HAS_TIRE_MODELS = (ROOT / "data" / "models" / "tire_degradation" / "routing_config.json").exists()
skip_no_tire_models = pytest.mark.skipif(
    not HAS_TIRE_MODELS,
    reason="data/models/ not present (CI runner without model weights)",
)
