"""
Scrapes academic profile and citation data via the OpenAlex API (openalex.org).
Free, no API key required, no CAPTCHA, no IP blocking.
Author: Robert K. Christensen — OpenAlex ID A5059965749
"""

import time
import logging
import urllib.request
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

OPENALEX_AUTHOR_ID = "A5059965749"
HEADERS = {"User-Agent": "mailto:rkchristensen@gmail.com"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _fetch_all_works(author_id: str) -> list[dict]:
    """Paginate through all works for this author using cursor pagination."""
    works = []
    cursor = "*"
    page = 1
    while True:
        url = (
            f"https://api.openalex.org/works"
            f"?filter=author.id:{author_id}"
            f"&per_page=200&cursor={cursor}"
            f"&select=id,title,publication_year,cited_by_count,authorships,primary_location,biblio"
        )
        data = _get(url)
        batch = data.get("results", [])
        works.extend(batch)
        log.info(f"  Page {page}: {len(batch)} works (total so far: {len(works)})")

        next_cursor = data.get("meta", {}).get("next_cursor")
        if not next_cursor or len(batch) == 0:
            break
        cursor = next_cursor
        page += 1
        time.sleep(0.5)

    return works


def _coauthor_count(work: dict, author_id: str) -> int:
    """Count all authors on the paper."""
    return len(work.get("authorships", []))


def _journal(work: dict) -> str:
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    return source.get("display_name", "")


def _authors_str(work: dict) -> str:
    names = []
    for a in work.get("authorships", []):
        name = a.get("author", {}).get("display_name", "")
        if name:
            names.append(name)
    return ", ".join(names)


def scrape_profile() -> tuple[dict, list[dict]]:
    """
    Returns (profile_snapshot, papers_list) using OpenAlex.
    """
    snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")

    log.info(f"Fetching author profile from OpenAlex: {OPENALEX_AUTHOR_ID}")
    author_url = f"https://api.openalex.org/authors/{OPENALEX_AUTHOR_ID}"
    author = _get(author_url)

    stats = author.get("summary_stats", {})
    profile = {
        "date": snapshot_date,
        "h_index": stats.get("h_index", 0),
        "h_index_5y": stats.get("h_index", 0),       # OpenAlex doesn't split by 5y
        "i10_index": stats.get("i10_index", 0),
        "i10_index_5y": stats.get("i10_index", 0),
        "total_citations": author.get("cited_by_count", 0),
        "total_citations_5y": author.get("cited_by_count", 0),
    }
    log.info(f"Profile: h={profile['h_index']}, citations={profile['total_citations']}, papers={author.get('works_count')}")

    log.info("Fetching all works...")
    raw_works = _fetch_all_works(OPENALEX_AUTHOR_ID)

    papers = []
    for w in raw_works:
        papers.append({
            "date": snapshot_date,
            "paper_id": w.get("id", "").replace("https://openalex.org/", ""),
            "title": w.get("title", ""),
            "authors": _authors_str(w),
            "coauthor_count": _coauthor_count(w, OPENALEX_AUTHOR_ID),
            "journal": _journal(w),
            "pub_year": w.get("publication_year", ""),
            "citations": w.get("cited_by_count", 0),
        })

    log.info(f"Done. {len(papers)} papers scraped.")
    return profile, papers
