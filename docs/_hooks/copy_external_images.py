"""Mkdocs hook that mirrors ``documents/images/`` into the docs build.

The thesis figures live at ``documents/images/05_results/`` (the location
referenced by chapter 5 of the LaTeX memoria). Mkdocs only serves files
inside ``docs_dir`` by default, so without this hook the figures would
have to be duplicated under ``docs/``. The hook copies them once at the
start of every build into a virtual ``_external_images/`` directory
inside the build site, so markdown can reference them as
``_external_images/05_results/<file>.png`` regardless of platform.

Wired in ``mkdocs.yml`` via:

    hooks:
      - docs/_hooks/copy_external_images.py
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def on_pre_build(config: dict[str, Any], **_: Any) -> None:
    """Copy ``documents/images/`` into ``docs/_external_images/`` before mkdocs scans files."""
    repo_root = Path(config["config_file_path"]).resolve().parent
    src = repo_root / "documents" / "images"
    dst = Path(config["docs_dir"]) / "_external_images"

    if not src.exists():
        return

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
