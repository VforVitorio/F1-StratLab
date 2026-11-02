from __future__ import annotations

import pandas as pd
import pytest

from src.data_extraction.openf1 import intervals_extractor


def test_interval_numeric_fallback_does_not_swallow_keyboard_interrupt(monkeypatch):
    frame = pd.DataFrame({"mixed": ["1.2", "LAP"]})

    def interrupt_conversion(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(intervals_extractor, "fetch_openf1_intervals", lambda *_args: frame)
    monkeypatch.setattr(pd, "to_numeric", interrupt_conversion)
    monkeypatch.setattr(pd.DataFrame, "to_parquet", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pd.DataFrame, "to_csv", lambda *_args, **_kwargs: None)

    with pytest.raises(KeyboardInterrupt):
        intervals_extractor.extract_openf1_intervals(2025, "Test GP")
