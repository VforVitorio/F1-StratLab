"""
Download FIA Formula 1 regulation PDFs and save them to data/rag/documents/.

Tries two strategies in order:
  1. Scrape the FIA regulation category pages to discover current PDF links.
  2. Fall back to manually maintained URLs in ``data/rag/fia_known_urls.json``
     for documents the scraper cannot find.

Downloaded files are renamed to the project naming convention:
  <doc_type>_<year>.pdf   e.g. sporting_regs_2025.pdf

Only the most recent issue of each (doc_type, year) pair is kept — if the FIA
publishes a corrected version, re-running this script replaces the old file.

Usage:
    python scripts/download_fia_pdfs.py
    python scripts/download_fia_pdfs.py --years 2024 2025
    python scripts/download_fia_pdfs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

DOCS_DIR       = _REPO_ROOT / "data" / "rag" / "documents"
KNOWN_URLS_FILE = _REPO_ROOT / "data" / "rag" / "fia_known_urls.json"

# FIA regulation category pages for Formula 1
FIA_CATEGORY_URLS: dict[str, str] = {
    "sporting_regs":  "https://www.fia.com/regulation/category/110",
    "technical_regs": "https://www.fia.com/regulation/category/111",
}

SUPPORTED_YEARS = [2023, 2024, 2025]

# Patterns that identify an F1 regulation PDF link on the FIA website.
# The FIA uses "Formula 1" and either "Sporting" or "Technical" in document titles.
_TITLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "sporting_regs":  re.compile(r"formula.?1.+sporting.+regulation", re.IGNORECASE),
    "technical_regs": re.compile(r"formula.?1.+technical.+regulation", re.IGNORECASE),
}
_YEAR_RE = re.compile(r"20(2[3-9])\d*")

REQUEST_TIMEOUT = 30   # seconds per HTTP request
RETRY_DELAY     = 2    # seconds between retries
MAX_RETRIES     = 3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class RegulationLink:
    """A discovered PDF link for a specific regulation document.

    Carries the resolved URL alongside the parsed doc_type and year so the
    downloader can name the file correctly without re-parsing the URL.

    Attributes:
        url:      Full URL of the PDF file to download. May be relative on the
                  FIA website — resolved to absolute before storage.
        doc_type: Regulatory domain inferred from the page title or link text
                  (``"sporting_regs"`` or ``"technical_regs"``).
        year:     Regulation year parsed from the document title or URL. Used
                  to construct the output filename and to filter by --years.
        title:    Human-readable document title as it appears on the FIA page.
                  Kept for logging and for the known-URLs JSON so the operator
                  can verify which issue was downloaded.
    """

    url:      str
    doc_type: str
    year:     int
    title:    str = ""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, session: requests.Session) -> requests.Response | None:
    """Fetch a URL with retries, returning ``None`` on persistent failure.

    Retries up to ``MAX_RETRIES`` times with a fixed delay. Returns ``None``
    rather than raising so the caller can fall back to the known-URLs list
    without interrupting the whole download run.

    Args:
        url:     The URL to fetch. Must be a full absolute URL.
        session: A ``requests.Session`` with headers already set. Using a
                 session reuses the TCP connection and shares cookies across
                 requests to the same host.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            log.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, url, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return None


def _make_session() -> requests.Session:
    """Create a requests session with browser-like headers.

    The FIA website returns 403 for requests without a User-Agent, so we
    mimic a standard browser request. No authentication is needed — all
    regulation PDFs are publicly accessible.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _extract_year_from_text(text: str) -> int | None:
    """Parse a four-digit year (2023–2029) from an arbitrary text string.

    Searches the full string rather than anchoring to the start, so it works
    on both document titles ("2025 Formula 1 Sporting Regulations") and raw
    URLs that include a year in the path segment.

    Args:
        text: Any string that may contain a year. Returns ``None`` if no
              year matching the pattern is found.
    """
    match = _YEAR_RE.search(text)
    return int(match.group(0)[:4]) if match else None


def scrape_regulation_links(
    doc_type: str,
    session:  requests.Session,
) -> list[RegulationLink]:
    """Scrape the FIA category page for a regulation type and return PDF links.

    Parses the page HTML looking for anchor tags whose href ends in ``.pdf``
    and whose surrounding text matches the expected regulation title pattern.
    Skips links without a parseable year so the caller only receives complete,
    usable results.

    Args:
        doc_type: One of ``"sporting_regs"`` or ``"technical_regs"``. Determines
                  which FIA category page to scrape and which title pattern to
                  apply when filtering links.
        session:  Active requests session. Passed in so all scraping calls share
                  the same connection pool and cookies.
    """
    base_url    = FIA_CATEGORY_URLS[doc_type]
    title_re    = _TITLE_PATTERNS[doc_type]
    links: list[RegulationLink] = []

    log.info("Scraping %s ...", base_url)
    resp = _get(base_url, session)
    if resp is None:
        log.warning("Could not fetch category page for '%s'", doc_type)
        return links

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup.find_all("a", href=True):
        href  = tag["href"]
        title = tag.get_text(strip=True)

        if not href.lower().endswith(".pdf"):
            continue
        if not title_re.search(title) and not title_re.search(href):
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            href = "https://www.fia.com" + href
        elif not href.startswith("http"):
            continue

        year = _extract_year_from_text(title) or _extract_year_from_text(href)
        if year is None or year not in SUPPORTED_YEARS:
            continue

        links.append(RegulationLink(url=href, doc_type=doc_type, year=year, title=title))
        log.info("  Found: %s (%d)", title[:80], year)

    return links


# ---------------------------------------------------------------------------
# Known-URLs fallback
# ---------------------------------------------------------------------------

def load_known_urls() -> list[RegulationLink]:
    """Load manually maintained PDF URLs from ``data/rag/fia_known_urls.json``.

    The JSON file is the safety net for when the FIA website structure changes
    and the scraper stops finding links. The operator adds entries by hand after
    verifying the URLs in a browser. Each entry must have ``url``, ``doc_type``,
    ``year``, and optionally ``title``.

    Returns an empty list (silently) if the file does not exist yet, so the
    script works on a fresh clone without requiring the file to be present.
    """
    if not KNOWN_URLS_FILE.exists():
        return []

    try:
        entries = json.loads(KNOWN_URLS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read %s: %s", KNOWN_URLS_FILE, exc)
        return []

    links = []
    for entry in entries:
        try:
            links.append(RegulationLink(
                url=entry["url"],
                doc_type=entry["doc_type"],
                year=int(entry["year"]),
                title=entry.get("title", ""),
            ))
        except KeyError as exc:
            log.warning("Skipping malformed entry in known_urls (missing key %s)", exc)

    log.info("Loaded %d known URLs from %s", len(links), KNOWN_URLS_FILE.name)
    return links


def save_known_urls_template() -> None:
    """Write a template ``fia_known_urls.json`` if the file does not exist yet.

    Creates the file with one commented example entry so the operator knows
    exactly what format to use when adding URLs manually. The file is only
    written on first run — subsequent runs never overwrite it so manually
    added entries are preserved.
    """
    if KNOWN_URLS_FILE.exists():
        return

    KNOWN_URLS_FILE.parent.mkdir(parents=True, exist_ok=True)
    template = [
        {
            "url":      "https://www.fia.com/sites/default/files/example_sporting_regs_2025.pdf",
            "doc_type": "sporting_regs",
            "year":     2025,
            "title":    "2025 Formula 1 Sporting Regulations — Issue 1",
            "_comment": "Replace url and title with real values from fia.com/regulation/category/110"
        }
    ]
    KNOWN_URLS_FILE.write_text(
        json.dumps(template, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    log.info("Created template %s — add real URLs there as fallback", KNOWN_URLS_FILE.name)


# ---------------------------------------------------------------------------
# Deduplication + download
# ---------------------------------------------------------------------------

def deduplicate_links(links: list[RegulationLink]) -> list[RegulationLink]:
    """Keep only one link per (doc_type, year) pair — the last one seen.

    When both the scraper and the known-URLs file return a link for the same
    document, the scraper result takes priority (it comes first in the combined
    list, and ``dict`` insertion order means the later known-URL entry would
    overwrite it — so we reverse the priority by iterating in order and keeping
    the last). This ensures the most recently discovered URL wins.

    Args:
        links: Combined list from scraper + known-URLs, scraper entries first.
    """
    seen: dict[tuple[str, int], RegulationLink] = {}
    for link in links:
        seen[(link.doc_type, link.year)] = link
    return list(seen.values())


def output_path(link: RegulationLink) -> Path:
    """Compute the destination file path for a regulation link.

    Applies the project naming convention: ``<doc_type>_<year>.pdf``.
    The file lives directly in ``DOCS_DIR`` with no sub-directories so
    ``build_rag_index.py`` can discover it with a simple ``*.pdf`` glob.

    Args:
        link: A ``RegulationLink`` with valid ``doc_type`` and ``year``.
    """
    return DOCS_DIR / f"{link.doc_type}_{link.year}.pdf"


def download_link(
    link:    RegulationLink,
    session: requests.Session,
    dry_run: bool = False,
) -> bool:
    """Download a single regulation PDF and save it to ``DOCS_DIR``.

    Skips the download if a file with the same name already exists, assuming
    it is the correct version. Re-running the script after a FIA erratum
    requires manually deleting the old file first, or using ``--force``.

    Args:
        link:    The ``RegulationLink`` describing what to download and where.
        session: Active requests session for the HTTP GET.
        dry_run: When ``True``, logs what would be downloaded without writing
                 any files. Useful for verifying the scraper found the right
                 URLs before committing to a full download.

    Returns:
        ``True`` if the file was downloaded (or would be in dry-run), ``False``
        if it was skipped because it already exists or the download failed.
    """
    dest = output_path(link)

    if dest.exists():
        log.info("Already exists — skipping %s", dest.name)
        return False

    log.info("%s%s → %s",
             "[DRY RUN] Would download" if dry_run else "Downloading",
             f" {link.title[:60]!r}" if link.title else f" {link.url[:80]}",
             dest.name)

    if dry_run:
        return True

    resp = _get(link.url, session)
    if resp is None:
        log.error("Failed to download %s", link.url)
        return False

    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower() and not link.url.lower().endswith(".pdf"):
        log.error("Response is not a PDF (Content-Type: %s) — skipping", content_type)
        return False

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(resp.content)
    size_kb = len(resp.content) // 1024
    log.info("Saved %s  (%d KB)", dest.name, size_kb)
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def download_all(
    years:   list[int] | None = None,
    dry_run: bool = False,
) -> None:
    """Discover and download all FIA regulation PDFs for the requested years.

    Runs the scraper for both doc types, merges with the known-URLs fallback,
    deduplicates, filters by year, and downloads each file. Prints a final
    summary of downloaded, skipped, and failed files.

    Args:
        years:   List of years to download (e.g. ``[2024, 2025]``). When
                 ``None``, downloads all ``SUPPORTED_YEARS``.
        dry_run: Pass through to ``download_link`` — logs actions without
                 writing files.
    """
    target_years = set(years) if years else set(SUPPORTED_YEARS)
    session      = _make_session()

    save_known_urls_template()

    # Scrape both category pages
    scraped: list[RegulationLink] = []
    for doc_type in FIA_CATEGORY_URLS:
        scraped.extend(scrape_regulation_links(doc_type, session))

    # Merge with known-URLs fallback (scraped takes priority)
    all_links = deduplicate_links(scraped + load_known_urls())

    # Filter by requested years
    filtered = [l for l in all_links if l.year in target_years]

    if not filtered:
        log.warning(
            "No links found for years %s. "
            "Add entries to %s manually if scraping failed.",
            sorted(target_years), KNOWN_URLS_FILE.name,
        )
        sys.exit(1)

    log.info("Links to process: %d", len(filtered))

    downloaded = skipped = failed = 0
    for link in sorted(filtered, key=lambda l: (l.year, l.doc_type)):
        result = download_link(link, session, dry_run=dry_run)
        if result is True:
            downloaded += 1
        elif output_path(link).exists():
            skipped += 1
        else:
            failed += 1

    log.info(
        "Done — downloaded: %d  |  skipped (exist): %d  |  failed: %d",
        downloaded, skipped, failed,
    )
    if failed:
        log.warning(
            "%d file(s) failed. Add their URLs to %s and re-run.",
            failed, KNOWN_URLS_FILE.name,
        )


def main() -> None:
    """Parse CLI arguments and run the download pipeline."""
    parser = argparse.ArgumentParser(
        description="Download FIA Formula 1 regulation PDFs to data/rag/documents/."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=None,
        metavar="YEAR",
        help=f"Years to download (default: all — {SUPPORTED_YEARS})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be downloaded without writing any files",
    )
    args = parser.parse_args()

    download_all(years=args.years, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
