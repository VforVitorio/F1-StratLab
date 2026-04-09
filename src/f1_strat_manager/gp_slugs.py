"""Friendly GP name → on-disk corpus slug mapping (single source of truth).

The static OpenF1 radio builder writes per-GP folders under
``data/processed/race_radios/{year}/{slug}/`` and
``data/raw/radio_audio/{year}/{slug}/`` where ``slug`` is computed by
``RadioDatasetBuilder._compute_slug``: lowercased country for single-race
countries (``bahrain``, ``united_kingdom``, ...) and ``country_circuit``
for the multi-race countries Italy and United States (``italy_imola``,
``italy_monza``, ``united_states_miami``, ``united_states_austin``,
``united_states_las_vegas``).

The CLI / featured-laps parquet, however, uses **friendly** GP names that
do not necessarily match the country (``Sakhir``, ``Imola``, ``Marina Bay``,
``Yas Island``, ...). This module is the *one* place that translates from
those friendly names to the on-disk slugs, so the runner, the FastAPI
endpoints, and the lazy first-run downloader (``data_cache``) all stay in
sync. Both ``src/nlp/radio_runner.py`` and
``src/f1_strat_manager/data_cache.py`` import the resolver from here —
keeping it in this module (not under ``src/agents/`` or ``src/nlp/``)
avoids dragging the radio-NLP package init (Whisper, librosa, the
sentiment / intent / NER classifiers) into the lightweight data-bootstrap
path on first run.
"""

from __future__ import annotations

# Map from the friendly GP names used by the CLI / featured-laps parquet to
# the on-disk slug produced by ``RadioDatasetBuilder._compute_slug``. Single
# entries for single-race countries, distinct entries per circuit for the
# two double-header countries (Italy = Imola + Monza, United States = Miami
# + Austin + Las Vegas). Adding another double-header country in a future
# season is a one-line change here followed by a Phase 0 rebuild of the
# affected GPs — no agent code needs to know.
COUNTRY_SLUG_BY_GP: dict[str, str] = {
    # Single-race countries — slug is just the lowercased country name
    "Sakhir":            "bahrain",
    "Jeddah":            "saudi_arabia",
    "Melbourne":         "australia",
    "Suzuka":            "japan",
    "Shanghai":          "china",
    "Monaco":            "monaco",
    "Barcelona":         "spain",
    "Montréal":          "canada",
    "Montreal":          "canada",            # ASCII fallback for CLI input
    "Spielberg":         "austria",
    "Silverstone":       "united_kingdom",
    "Budapest":          "hungary",
    "Spa-Francorchamps": "belgium",
    "Zandvoort":         "netherlands",
    "Baku":              "azerbaijan",
    "Marina Bay":        "singapore",
    "Mexico City":       "mexico",
    "São Paulo":         "brazil",
    "Sao Paulo":         "brazil",            # ASCII fallback for CLI input
    "Lusail":            "qatar",
    "Yas Island":        "united_arab_emirates",
    # Multi-race countries — slug carries the circuit suffix from Phase 0
    "Imola":             "italy_imola",
    "Monza":             "italy_monza",
    "Miami":             "united_states_miami",
    "Austin":            "united_states_austin",
    "Las Vegas":         "united_states_las_vegas",
}


def resolve_gp_slug(gp_name: str) -> str:
    """Translate a friendly GP name into the on-disk corpus slug.

    Accepts the names the CLI passes (``"Sakhir"``, ``"Imola"``,
    ``"Marina Bay"``, ...) and returns the slug used by the static
    builder for the corpus directories under
    ``data/processed/race_radios/{year}/`` and
    ``data/raw/radio_audio/{year}/``. Falls through silently when the
    input is *already* a slug, which keeps callers reentrant — passing
    the canonical form a second time is a no-op instead of an error,
    which matters for ``ensure_radio_corpus`` retrying after a partial
    download.

    Raises :class:`ValueError` listing the known GP names whenever the
    input matches neither a friendly name nor an existing slug, so a
    typo at the CLI surfaces immediately instead of producing a silent
    zero-radio simulation.
    """
    if gp_name in COUNTRY_SLUG_BY_GP:
        return COUNTRY_SLUG_BY_GP[gp_name]
    if gp_name in set(COUNTRY_SLUG_BY_GP.values()):
        return gp_name
    raise ValueError(
        f"Unknown GP {gp_name!r}. Known: {sorted(COUNTRY_SLUG_BY_GP)}"
    )
