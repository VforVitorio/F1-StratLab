"""Shared utilities for benchmark scripts.

All ``scripts/bench_*.py`` modules import from this helper to keep the
artefact format identical across the four benchmarks: a ``BenchResult``
dataclass for one row, ``render_results_table`` for the Rich console
output, ``export_markdown`` / ``export_csv`` for the on-disk artefacts
under ``data/eval/``, ``time_function`` for the warm-up + measured
latency loop, and ``make_start_panel`` for the opening Rich panel.

Numeric formatting follows the thesis convention: comma decimal
separator in the markdown output (target locale uses commas) and dot
decimal separator in the CSV (so the file is loadable with
``pd.read_csv`` and convertible to LaTeX with ``df.to_latex``).
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scripts.cli.theme import F1_AMBER, F1_GRAY, F1_RED, F1_WHITE


@dataclass(frozen=True)
class BenchResult:
    """One row of a benchmark table, agnostic to the metric set.

    Attributes:
        name: Free-form identifier for the row (model, agent, bucket,
            entry-point label, etc.). Renders as the first column in the
            Rich table and as the ``columns[0]`` value in the artefacts.
        metrics: Mapping from column name to numeric or string value.
            Strings are passed through unchanged (used for ``device``,
            ``notes``, etc.); floats are formatted per artefact (commas
            for markdown, dots for CSV).
    """

    name: str
    metrics: dict[str, Any]


def _format_value_md(value: Any) -> str:
    """Format ``value`` for the markdown table (comma decimal separator).

    Floats are rendered with three decimals; ints with no decimals;
    strings are passed through (only ``|`` is escaped to keep the
    markdown table parseable). ``None`` becomes the empty string so
    optional notes do not pollute the rendering.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        if not np.isfinite(value):
            return "—"
        return f"{value:.3f}".replace(".", ",")
    if isinstance(value, int):
        return str(value)
    return str(value).replace("|", "/")


def _format_value_csv(value: Any) -> str:
    """Format ``value`` for the CSV artefact (dot decimal separator).

    Mirrors :func:`_format_value_md` but keeps the dot decimal
    separator so the CSV is directly loadable by ``pd.read_csv``.
    Strings with commas pass through — the ``csv`` module quotes them
    automatically.
    """
    if value is None:
        return ""
    if isinstance(value, float):
        if not np.isfinite(value):
            return ""
        return f"{value:.6f}"
    if isinstance(value, int):
        return str(value)
    return str(value)


def render_results_table(
    results: list[BenchResult],
    title: str,
    columns: list[str],
) -> Table:
    """Build a Rich Table from ``results`` ready for console printing.

    The first column always carries ``name``; the remaining columns are
    looked up in ``metrics`` in the order given by ``columns``. Numeric
    values are right-aligned with three decimals, strings are
    left-aligned. The table header uses the F1 red palette so the
    output stays consistent with ``run_simulation_cli``.
    """
    table = Table(title=title, header_style=f"bold {F1_RED}", border_style=F1_GRAY)
    table.add_column(columns[0], style=F1_WHITE, no_wrap=True)
    for col in columns[1:]:
        table.add_column(col, style=F1_AMBER, justify="right")

    for result in results:
        row_cells: list[str] = [result.name]
        for col in columns[1:]:
            row_cells.append(_format_value_md(result.metrics.get(col)))
        table.add_row(*row_cells)
    return table


def export_markdown(
    results: list[BenchResult],
    path: Path,
    title: str,
    columns: list[str],
) -> None:
    """Write a markdown table to ``path`` with comma decimal separator.

    The first line is the H2 ``title``, followed by a blank line and
    then a GitHub-flavoured markdown table whose header row is the
    first ``columns`` entry. Floats use commas so the output drops
    straight into the target-locale thesis paragraph without any
    locale post-processing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = [f"## {title}", ""]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("|" + "|".join(["---"] * len(columns)) + "|")
    for result in results:
        cells = [_format_value_md(result.name)]
        for col in columns[1:]:
            cells.append(_format_value_md(result.metrics.get(col)))
        lines.append("| " + " | ".join(cells) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_csv(
    results: list[BenchResult],
    path: Path,
    columns: list[str],
) -> None:
    """Write a UTF-8 CSV with dot decimal separator and a header row.

    ``csv.writer`` handles quoting of strings containing commas, so the
    ``notes`` column can carry free text without breaking the layout.
    The ``columns`` argument is the ordered list of header names
    matching the keys in :class:`BenchResult.metrics` (plus the leading
    name column).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for result in results:
            row = [_format_value_csv(result.name)]
            for col in columns[1:]:
                row.append(_format_value_csv(result.metrics.get(col)))
            writer.writerow(row)


def time_function(
    fn: Callable[[], Any],
    n_warmup: int,
    n_runs: int,
) -> dict[str, float]:
    """Return P50, P95, mean, std latency in milliseconds for ``fn``.

    Runs ``fn`` ``n_warmup`` times to absorb JIT / first-call costs
    (the timings are discarded), then ``n_runs`` measured times
    captured with ``time.perf_counter``. Returns a dict with keys
    ``mean_ms``, ``p50_ms``, ``p95_ms``, ``std_ms`` and ``n_runs`` so
    callers can drop the values straight into a ``BenchResult.metrics``
    mapping. Returns NaN for the percentiles when ``n_runs`` is zero
    so a smoke run with ``--n-runs 0`` does not crash.
    """
    for _ in range(max(0, n_warmup)):
        fn()

    times_ms: list[float] = []
    for _ in range(max(0, n_runs)):
        start = time.perf_counter()
        fn()
        times_ms.append((time.perf_counter() - start) * 1000.0)

    if not times_ms:
        return {
            "mean_ms": float("nan"),
            "p50_ms": float("nan"),
            "p95_ms": float("nan"),
            "std_ms": float("nan"),
            "n_runs": 0,
        }

    arr = np.asarray(times_ms, dtype=float)
    return {
        "mean_ms": float(arr.mean()),
        "p50_ms":  float(np.percentile(arr, 50)),
        "p95_ms":  float(np.percentile(arr, 95)),
        "std_ms":  float(arr.std()),
        "n_runs":  int(len(arr)),
    }


def make_start_panel(script_name: str, target: str) -> Panel:
    """Return a Rich panel with the script name and a one-line target.

    Called once at the very start of every benchmark script so the
    operator can confirm at a glance which artefact the run is going
    to produce. Mirrors the colour scheme used by
    ``scripts/cli/theme.make_banner`` for visual consistency.
    """
    body = Text()
    body.append(f"{script_name}\n", style=f"bold {F1_RED}")
    body.append(target, style=F1_GRAY)
    return Panel(body, border_style=F1_RED, padding=(0, 2), title="F1 StratLab benchmarks")
