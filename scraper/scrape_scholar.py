"""
Scrapes a Google Scholar profile and returns structured snapshot data.
Handles rate limiting with exponential backoff and retries per publication.
"""

import time
import logging
from datetime import datetime
from scholarly import scholarly

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCHOLAR_ID = "-5aAUboAAAAJ"
RETRY_DELAY = 10  # seconds between retries
MAX_RETRIES = 3


def _fill_with_retry(pub):
    for attempt in range(MAX_RETRIES):
        try:
            return scholarly.fill(pub)
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_DELAY * (2 ** attempt)
                log.warning(f"Retry {attempt + 1} for publication after error: {e}. Waiting {wait}s.")
                time.sleep(wait)
            else:
                log.error(f"Failed to fill publication after {MAX_RETRIES} attempts: {e}")
                return pub  # return unfilled rather than crashing
    return pub


def _count_coauthors(authors_str: str) -> int:
    if not authors_str:
        return 0
    return len([a.strip() for a in authors_str.split(" and ") if a.strip()])


def scrape_profile() -> tuple[dict, list[dict]]:
    """
    Returns (profile_snapshot, papers_list).
    profile_snapshot: dict with date and profile-level metrics.
    papers_list: list of dicts, one per publication.
    """
    log.info(f"Fetching Scholar profile: {SCHOLAR_ID}")
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])

    snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")

    profile = {
        "date": snapshot_date,
        "h_index": author.get("hindex", 0),
        "h_index_5y": author.get("hindex5y", 0),
        "i10_index": author.get("i10index", 0),
        "i10_index_5y": author.get("i10index5y", 0),
        "total_citations": author.get("citedby", 0),
        "total_citations_5y": author.get("citedby5y", 0),
    }
    log.info(f"Profile snapshot: h={profile['h_index']}, citations={profile['total_citations']}")

    papers = []
    pubs = author.get("publications", [])
    log.info(f"Filling {len(pubs)} publications (this takes a few minutes)...")

    for i, pub in enumerate(pubs):
        filled = _fill_with_retry(pub)
        bib = filled.get("bib", {})

        authors_str = bib.get("author", "")
        journal = (
            bib.get("journal")
            or bib.get("booktitle")
            or bib.get("venue")
            or ""
        )

        papers.append(
            {
                "date": snapshot_date,
                "paper_id": filled.get("author_pub_id", f"unknown_{i}"),
                "title": bib.get("title", ""),
                "authors": authors_str,
                "coauthor_count": _count_coauthors(authors_str),
                "journal": journal.strip(),
                "pub_year": bib.get("pub_year", ""),
                "citations": filled.get("num_citations", 0),
            }
        )

        if (i + 1) % 10 == 0:
            log.info(f"  {i + 1}/{len(pubs)} publications filled")
        time.sleep(1)  # gentle rate limiting

    log.info(f"Done. {len(papers)} papers scraped.")
    return profile, papers
