"""
Build the static team-radio dataset for one or more F1 seasons.

Wraps :class:`src.data_extraction.openf1.radio_dataset_builder.RadioDatasetBuilder`
in a multi-GP CLI loop. For every requested season the script asks OpenF1
for the full list of Race sessions, then iterates over each Grand Prix and
calls ``build_and_write`` to persist a per-GP parquet to the configured
output directory.

The output is the offline corpus the N29 Radio Agent will consume during
race replay. Two parquets are produced per GP: one for team radios (driver,
lap, recording_url) and one for race control messages (driver?, lap, flag,
category, message). Both are filtered with the same structural rule —
formation lap, race-start lap and chequered-flag lap dropped — so every
row left in either parquet belongs to a normal race lap and could
plausibly inform a strategy decision. No MP3 download or transcription
happens at this layer; only the OpenF1 metadata is persisted.

Usage:
    python scripts/build_radio_dataset.py                                    # builds 2025 only (default)
    python scripts/build_radio_dataset.py --gps Bahrain Australia            # subset of 2025
    python scripts/build_radio_dataset.py --years 2023 2024 2025             # historical full build
    python scripts/build_radio_dataset.py --output-dir data/processed/race_radios
    python scripts/build_radio_dataset.py --skip-existing                    # resume after a crash

Output layout:
    data/processed/race_radios/
        2025_bahrain.parquet              ← team radios (9 columns)
        2025_bahrain_rcm.parquet          ← race control messages (13 columns)
        2025_australia.parquet
        2025_australia_rcm.parquet
        ...
        2025_abu_dhabi.parquet
        2025_abu_dhabi_rcm.parquet

The radio parquets follow the 9-column ``OUTPUT_SCHEMA`` defined in
``radio_dataset_builder``: session_key, meeting_key, year, gp, total_laps,
driver_number, lap_number, date, recording_url.

The RCM parquets follow the 13-column ``RCM_OUTPUT_SCHEMA``: session_key,
meeting_key, year, gp, total_laps, driver_number, lap_number, date,
category, flag, scope, sector, message.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import requests

# Make ``src.*`` imports work whether the script is invoked as
# ``python scripts/build_radio_dataset.py`` or ``python -m scripts.build_radio_dataset``.
# scripts/ is a package but the parent ``src/`` package lives one level up,
# so the repo root must be on sys.path before any project import.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.data_extraction.openf1.radio_dataset_builder import (  # noqa: E402
    OPENF1_BASE,
    RadioDatasetBuilder,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default season used when the operator does not pass ``--years``. The N29
# Radio Agent and the lap-by-lap simulation only consume 2025 data, so a bare
# ``python scripts/build_radio_dataset.py`` builds just that year. Older
# seasons are still reachable on demand via ``--years 2023 2024 2025`` for
# historical NLP retraining or one-off analysis, but they are not part of
# the default critical path.
DEFAULT_YEARS: tuple[int, ...] = (2025,)


@dataclass
class BuildConfig:
    """Centralised configuration for the multi-GP radio dataset build.

    Grouping every tunable knob here keeps :class:`RadioDatasetCLI` thin and
    means the CLI argparse layer is the only place that maps user input onto
    runtime behaviour. Defaults match the convention used elsewhere in the
    project: per-season parquets under ``data/processed/race_radios``.

    Attributes:
        output_dir:   Directory where per-GP parquets will be written. Created
                      lazily by the underlying ``RadioDatasetBuilder`` on the
                      first successful write so a dry run does not pollute the
                      filesystem when every GP fails.
        http_timeout: Per-request timeout in seconds for the OpenF1 calls.
                      30 s matches the notebook prototype and gives the
                      ``/v1/laps`` endpoint enough headroom on slow links.
    """

    output_dir:   Path = field(
        default_factory=lambda: _REPO_ROOT / "data" / "processed" / "race_radios"
    )
    http_timeout: int = 30


CFG = BuildConfig()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("build_radio_dataset")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RaceMeta:
    """Identifying metadata for a single Race session discovered via OpenF1.

    Produced by :meth:`RadioDatasetCLI.discover_races` from the
    ``/v1/sessions`` payload, then consumed by the build loop. Carrying both
    ``session_key`` and ``country_name`` lets the loop log human-readable
    progress lines while still being able to call OpenF1 by key if a future
    optimisation needs it.

    Attributes:
        year:         Season the race belongs to. Used for the output filename
                      and to disambiguate the same circuit visited across
                      multiple seasons.
        country_name: Exact country string returned by OpenF1, used as the
                      ``country_name`` argument to ``RadioDatasetBuilder``.
                      Must be passed through unchanged because the builder
                      slugifies it for the parquet filename.
        session_key:  OpenF1 session identifier. Carried for log lines and as
                      a stable handle in case future versions of the script
                      need to fetch additional session-specific data.
    """

    year:         int
    country_name: str
    session_key:  int


@dataclass
class BuildResult:
    """Outcome of attempting to build a single GP's radio + RCM parquets.

    Captures enough state for the final summary log so the operator can tell
    at a glance which GPs were skipped (already on disk), which were built
    fresh, and which failed (and why). Failures are kept as strings instead
    of raised exceptions because the CLI loop wants to keep going past
    individual GP errors and only report at the end.

    Each successful build produces two parquets per GP — radios and RCMs —
    so this result tracks both row counts and both paths separately. The
    summary aggregates them into a single "(N radios, M RCMs)" line per GP
    and into season-wide totals at the bottom of the run.

    Attributes:
        race:       The :class:`RaceMeta` this result describes. Kept on
                    the instance so the summary can group results by year/GP
                    without a second pass over the source list.
        status:     One of ``"built"``, ``"skipped"``, or ``"failed"``.
                    Drives the summary counters and the per-row log line.
        radio_rows: Number of radio rows written to the radio parquet
                    (zero for skipped or failed runs).
        rcm_rows:   Number of RCM rows written to the RCM parquet
                    (zero for skipped or failed runs).
        radio_path: Path of the written radio parquet, or ``None`` for
                    skipped/failed runs.
        rcm_path:   Path of the written RCM parquet, or ``None`` for
                    skipped/failed runs.
        error:      Short error description for failed runs, ``None``
                    otherwise. Stored as a plain string so the summary can
                    be printed without re-raising or pickling exceptions.
    """

    race:       RaceMeta
    status:     str
    radio_rows: int            = 0
    rcm_rows:   int            = 0
    radio_path: Optional[Path] = None
    rcm_path:   Optional[Path] = None
    error:      Optional[str]  = None


# ---------------------------------------------------------------------------
# Multi-GP CLI orchestrator
# ---------------------------------------------------------------------------

class RadioDatasetCLI:
    """Multi-GP wrapper around :class:`RadioDatasetBuilder`.

    Owns the configuration, the shared ``requests.Session`` (so every OpenF1
    call across the full season build reuses the same TCP connection), and
    the orchestration loop that discovers races, applies the optional GP
    filter, calls the builder per GP, and produces the final summary. Kept
    as a class rather than a free function so unit tests can swap the
    ``RadioDatasetBuilder`` instance for a fake without monkey-patching the
    module.

    The orchestrator is deliberately fail-soft: a failure on one GP logs an
    error and produces a ``BuildResult`` with ``status="failed"`` instead of
    aborting the run. This matters for full-season builds where one slow or
    rate-limited request would otherwise force the operator to restart from
    scratch.
    """

    def __init__(self, cfg: BuildConfig) -> None:
        """Wire the CLI to its config and initialise the shared HTTP session.

        The ``RadioDatasetBuilder`` is constructed eagerly so the underlying
        ``requests.Session`` is reused across every GP in the loop, which is
        the main reason this script exists as a class instead of a one-shot
        function. The session is owned by the builder and closed implicitly
        when the process exits.
        """
        self._cfg     = cfg
        self._http    = requests.Session()
        self._builder = RadioDatasetBuilder(
            output_dir=cfg.output_dir,
            http_timeout=cfg.http_timeout,
            session=self._http,
        )

    # ── Race discovery ───────────────────────────────────────────────────────

    def discover_races(self, years: Iterable[int]) -> list[RaceMeta]:
        """Query OpenF1 for every Race session across the requested seasons.

        Issues one ``/v1/sessions?year=YYYY&session_type=Race`` call per year
        instead of looping per GP, which keeps the discovery phase under a
        handful of HTTP calls regardless of how many seasons the user asks
        for. Skips years that return an empty session list with a warning so
        the build can still continue with the remaining seasons.

        Returns the discovered races sorted by year ascending and then by
        OpenF1's natural calendar order within a season, so the build loop
        produces predictable, repeatable output across runs.
        """
        races: list[RaceMeta] = []
        for year in sorted(set(years)):
            log.info("Discovering Race sessions for %d ...", year)
            try:
                response = self._http.get(
                    f"{OPENF1_BASE}/sessions",
                    params={"year": year, "session_type": "Race"},
                    timeout=self._cfg.http_timeout,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                log.error("Failed to list sessions for %d: %s", year, exc)
                continue

            payload = response.json()
            if not payload:
                log.warning("OpenF1 returned no Race sessions for %d", year)
                continue

            year_count = 0
            for session in payload:
                country = session.get("country_name")
                key     = session.get("session_key")
                if country is None or key is None:
                    continue
                races.append(
                    RaceMeta(year=year, country_name=country, session_key=int(key))
                )
                year_count += 1

            log.info("  → found %d races for %d", year_count, year)

        return races

    # ── Filtering ────────────────────────────────────────────────────────────

    @staticmethod
    def filter_races(
        races:     list[RaceMeta],
        gp_filter: Optional[list[str]],
    ) -> list[RaceMeta]:
        """Restrict the discovered race list to a subset of country names.

        Case-insensitive match because the user may pass ``"bahrain"`` from
        the CLI even though OpenF1 stores ``"Bahrain"``. Returns the input
        list unchanged when ``gp_filter`` is ``None`` or empty so the
        ``--gps`` argument behaves as a no-op when the user does not pass it.

        Logs a warning for any GP name that did not match anything so a typo
        in ``--gps`` does not silently produce a zero-row run that the
        operator might mistake for a successful build.
        """
        if not gp_filter:
            return races

        wanted   = {name.lower() for name in gp_filter}
        filtered = [r for r in races if r.country_name.lower() in wanted]

        matched = {r.country_name.lower() for r in filtered}
        for name in wanted - matched:
            log.warning("--gps filter: no match for '%s'", name)

        return filtered

    # ── Build loop ───────────────────────────────────────────────────────────

    def build_all(
        self,
        races:         list[RaceMeta],
        skip_existing: bool,
    ) -> list[BuildResult]:
        """Iterate over every race and build both parquets, collecting results.

        Wraps each per-GP build in a try/except so a single failure (network
        blip, malformed payload, missing laps) cannot abort the rest of the
        run. For each GP it prepares the session bundle once and feeds it to
        both ``build_radio_table`` and ``build_rcm_table`` so OpenF1 only
        sees two shared fetches (sessions + laps) instead of four.

        The ``skip_existing`` flag short-circuits a GP only when **both**
        target parquets are already on disk. If only one is present (e.g.
        because an earlier build ran before the RCM extension landed), the
        GP is rebuilt in full so the on-disk corpus stays internally
        consistent. Re-building a GP that already has both parquets is
        idempotent — it simply overwrites the existing files with fresh
        data — so the worst case of skipping incorrectly is a wasted
        round trip, never data corruption.
        """
        results: list[BuildResult] = []
        for race in races:
            radio_target = self._radio_target_path(race)
            rcm_target   = self._rcm_target_path(race)

            if skip_existing and radio_target.exists() and rcm_target.exists():
                log.info(
                    "[%d %s] skipped — both parquets already exist",
                    race.year, race.country_name,
                )
                results.append(
                    BuildResult(
                        race=race,
                        status="skipped",
                        radio_path=radio_target,
                        rcm_path=rcm_target,
                    )
                )
                continue

            try:
                bundle = self._builder.prepare_session_bundle(
                    race.year, race.country_name,
                )
                radio_table = self._builder.build_radio_table(
                    race.year, race.country_name, bundle=bundle,
                )
                rcm_table = self._builder.build_rcm_table(
                    race.year, race.country_name, bundle=bundle,
                )
                radio_path = self._builder.write_parquet(
                    radio_table, race.year, race.country_name,
                )
                rcm_path = self._builder.write_rcm_parquet(
                    rcm_table, race.year, race.country_name,
                )
            except Exception as exc:
                log.error(
                    "[%d %s] build failed: %s",
                    race.year, race.country_name, exc,
                )
                results.append(
                    BuildResult(race=race, status="failed", error=str(exc))
                )
                continue

            results.append(
                BuildResult(
                    race=race,
                    status="built",
                    radio_rows=len(radio_table),
                    rcm_rows=len(rcm_table),
                    radio_path=radio_path,
                    rcm_path=rcm_path,
                )
            )

        return results

    def _radio_target_path(self, race: RaceMeta) -> Path:
        """Compute the radio parquet path the builder will write for a race.

        Mirrors :meth:`RadioDatasetBuilder.write_parquet` so the
        ``--skip-existing`` check can decide before doing any HTTP work
        whether the radio half of this GP is already covered. The slug rule
        is intentionally duplicated here rather than imported because the
        builder's filename scheme is part of its public contract — if it
        ever changes, this method must change in lockstep, and the
        duplication makes that coupling visible.
        """
        slug = race.country_name.lower().replace(" ", "_")
        return self._cfg.output_dir / f"{race.year}_{slug}.parquet"

    def _rcm_target_path(self, race: RaceMeta) -> Path:
        """Compute the RCM parquet path the builder will write for a race.

        The RCM analogue of :meth:`_radio_target_path` — same slug rule,
        same directory, but with the ``_rcm`` suffix that
        :meth:`RadioDatasetBuilder.write_rcm_parquet` appends. Both targets
        are checked together by the skip-existing logic so a GP is only
        skipped when both halves of its corpus are already on disk.
        """
        slug = race.country_name.lower().replace(" ", "_")
        return self._cfg.output_dir / f"{race.year}_{slug}_rcm.parquet"

    # ── Summary ──────────────────────────────────────────────────────────────

    @staticmethod
    def log_summary(results: list[BuildResult]) -> None:
        """Print a final summary of build, skip, and failure counts.

        Aggregates the per-GP outcomes into three buckets so the operator can
        tell at a glance whether the run was clean, partial, or broken.
        Reports radio and RCM totals separately because the two corpora have
        very different cardinalities (radios are sparse, RCMs scale with
        race chaos) and a single combined number would hide problems with
        either source. Lists every failed GP with its short error message
        so the next ``--years`` re-run can target only the missing slices
        via ``--gps``.
        """
        built   = [r for r in results if r.status == "built"]
        skipped = [r for r in results if r.status == "skipped"]
        failed  = [r for r in results if r.status == "failed"]

        total_radio_rows = sum(r.radio_rows for r in built)
        total_rcm_rows   = sum(r.rcm_rows   for r in built)

        log.info("")
        log.info("=" * 60)
        log.info("Build summary")
        log.info(
            "  built:   %3d GP  (%d radios, %d RCMs total)",
            len(built), total_radio_rows, total_rcm_rows,
        )
        log.info("  skipped: %3d GP  (already on disk)", len(skipped))
        log.info("  failed:  %3d GP", len(failed))
        log.info("=" * 60)

        if failed:
            log.info("Failed GPs:")
            for r in failed:
                log.info("  - %d %s: %s", r.race.year, r.race.country_name, r.error)

    # ── Top-level entry point ────────────────────────────────────────────────

    def run(
        self,
        years:         Iterable[int],
        gp_filter:     Optional[list[str]],
        skip_existing: bool,
    ) -> list[BuildResult]:
        """Discover races, filter them, build each GP, and log the summary.

        Convenience method that chains the four phases of the script into a
        single call so :func:`main` is the only place CLI arguments touch
        the orchestrator. Returns the full result list so a future test or
        Python-level caller can assert on the outcomes without scraping log
        output.
        """
        races = self.discover_races(years)
        if not races:
            log.error("No races discovered — nothing to build")
            return []

        races = self.filter_races(races, gp_filter)
        if not races:
            log.error("Race list is empty after applying --gps filter")
            return []

        log.info("Building %d races into %s", len(races), self._cfg.output_dir)
        results = self.build_all(races, skip_existing=skip_existing)
        self.log_summary(results)
        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and run the multi-GP radio dataset build.

    Maps every ``argparse`` value onto a fresh :class:`BuildConfig`
    instance so the CLI defaults stay co-located with the dataclass and the
    runtime ``RadioDatasetCLI`` only ever sees a fully-resolved config.
    """
    parser = argparse.ArgumentParser(
        description="Build the static OpenF1 team-radio dataset for one or more seasons.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(DEFAULT_YEARS),
        help=f"Seasons to build (default: {' '.join(str(y) for y in DEFAULT_YEARS)})",
    )
    parser.add_argument(
        "--gps",
        type=str,
        nargs="+",
        default=None,
        help="Optional list of country names to restrict the build (case-insensitive)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CFG.output_dir,
        help=f"Directory where per-GP parquets are written (default: {CFG.output_dir})",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip GPs whose parquet already exists on disk",
    )
    args = parser.parse_args()

    cfg = BuildConfig(
        output_dir=args.output_dir,
        http_timeout=CFG.http_timeout,
    )
    cli = RadioDatasetCLI(cfg)
    cli.run(
        years=args.years,
        gp_filter=args.gps,
        skip_existing=args.skip_existing,
    )


if __name__ == "__main__":
    main()
