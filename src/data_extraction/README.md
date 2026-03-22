# src/data_extraction — Data Extraction Utilities (reference scripts)

**Status: Jupytext export / reference** — superseded by `scripts/download_data.py` and N01-N04 notebooks.

Early-stage scripts for pulling raw race data. The project's canonical data
pipeline is now in the `notebooks/data_engineering/` notebooks (N01–N04) and
`scripts/download_data.py`, which cover all seasons (2023–2025) and all circuits.

---

## Files

| File | Description |
|---|---|
| `data_extraction.py` | `extract_f1_data(year, gp, session_type)` — FastF1 session loader; saves laps, pit stops, weather as Parquet under `data/raw/`; initially scoped to Spain 2023 |
| `extract_openf1_intervals.py` | `fetch_openf1_intervals(year, gp_name)` + `get_session_key(year, gp_name)` — pulls inter-car interval data from OpenF1 REST API; currently only maps session key for Spain 2023 |
| `video_extraction.py` | `download_f1_video(url, filename)` — yt-dlp wrapper for downloading F1 highlight videos (Creative Commons); used in early vision experiments |
| `data_augmentation.py` | Albumentations pipeline for the F1 team car image dataset (YOLO format); augments to 250 samples per team class; uses an absolute path from the original dev machine |

---

## Limitations

- `data_augmentation.py` contains a hard-coded absolute path (`C:\Users\victo\...`) from the developer's machine — not portable.
- `extract_openf1_intervals.py` only has a hard-coded `session_key` for Spain 2023; other races require manual lookup.
- These scripts predate the project's `data/cache/fastf1/` caching strategy.

---

## Current data pipeline

For downloading race data use:

```bash
python scripts/download_data.py
```

For FIA regulation PDFs (RAG):

```bash
python scripts/download_fia_pdfs.py
```

---

## Developed in

[`notebooks/data_engineering/N01_data_download.ipynb`](../../notebooks/data_engineering/N01_data_download.ipynb)
