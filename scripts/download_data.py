"""
Download F1 strategy dataset from Hugging Face Hub.

Dataset: https://huggingface.co/datasets/VforVitorio/f1-strategy-dataset
Contains:
  - data/raw/      : Raw FastF1 parquets (2023, 2024, 2025 seasons)
  - data/processed/: Feature-engineered parquets (N04 output)

Usage:
    python scripts/download_data.py
"""

from huggingface_hub import snapshot_download
from pathlib import Path

REPO_ID = "VforVitorio/f1-strategy-dataset"
LOCAL_DIR = Path(__file__).parent.parent / "data"

if __name__ == "__main__":
    print(f"Downloading dataset from {REPO_ID} ...")
    snapshot_download(
        repo_id=REPO_ID,
        repo_type="dataset",
        local_dir=str(LOCAL_DIR),
    )
    print(f"Done. Data saved to {LOCAL_DIR}")
