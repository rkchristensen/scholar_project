"""
Scrapes a Google Scholar profile via SerpAPI (serpapi.com).
Free tier: 100 searches/month — sufficient for weekly scraping.
Requires SERPAPI_KEY environment variable.
"""

import os
import time
import logging
from datetime import datetime
from serpapi import GoogleSearch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCHOLAR_ID = "-5aAUboAAAAJ"


def _api_key():
    key = os.environ.get("SERPAPI_KEY", "")
    if not key:
        raise EnvironmentError("SERPAPI_KEY environment variable is not set.")
    return key


def _count_coauthors(authors_str: str) -> int:
    if not authors_str:
        return 0
    return len([a.strip() for a in authors_str.split(",") if a.strip()])


def scrape_profile() -> tuple[dict, list[dict]]:
    """
    Returns (profile_snapshot, papers_list) using SerpAPI.
    """
    key = _api_key()
    snapshot_date = datetime.utcnow().strftime("%Y-%m-%d")

    # Fetch all articles (paginated, 100 per page)
    all_articles = []
    start = 0
    while True:
        params = {
            "engine": "google_scholar_author",
            "author_id": SCHOLAR_ID,
            "api_key": key,
            "num": 100,
            "start": start,
            "sort": "pubdate",
        }
        results = GoogleSearch(params).get_dict()

        articles = results.get("articles", [])
        if not articles:
            break

        all_articles.extend(articles)
        log.info(f"  Fetched {len(all_articles)} articles so far...")

        if len(articles) < 100:
            break
        start += 100
        time.sleep(1)

    # Profile-level metrics from the last response
    author_info = results.get("author", {})
    cited_by = results.get("cited_by", {})
    table = cited_by.get("table", [])

    def _metric(label):
        for row in table:
            if row.get("citations", {}).get("all") is not None and label == "citations":
                return row["citations"]["all"]
            if row.get("h_index", {}).get("all") is not None and label == "h_index":
                return row["h_index"]["all"]
            if row.get("i10_index", {}).get("all") is not None and label == "i10_index":
                return row["i10_index"]["all"]
        return 0

    def _metric_5y(label):
        for row in table:
            if row.get("citations", {}).get("since_2021") is not None and label == "citations":
                return row["citations"]["since_2021"]
            if row.get("h_index", {}).get("since_2021") is not None and label == "h_index":
                return row["h_index"]["since_2021"]
            if row.get("i10_index", {}).get("since_2021") is not None and label == "i10_index":
                return row["i10_index"]["since_2021"]
        return 0

    # SerpAPI returns a flat cited_by table; easier to read graph data
    graph = cited_by.get("graph", [])
    total_citations = sum(g.get("citations", 0) for g in graph) if graph else _metric("citations")
    # Use the summary table for h-index / i10
    summary = cited_by.get("table", [])
    h_index = 0
    h_index_5y = 0
    i10_index = 0
    i10_index_5y = 0
    total_citations_all = 0
    total_citations_5y = 0
    for row in summary:
        if "citations" in row:
            total_citations_all = row["citations"].get("all", 0)
            total_citations_5y = row["citations"].get("since_2021", 0)
        if "h_index" in row:
            h_index = row["h_index"].get("all", 0)
            h_index_5y = row["h_index"].get("since_2021", 0)
        if "i10_index" in row:
            i10_index = row["i10_index"].get("all", 0)
            i10_index_5y = row["i10_index"].get("since_2021", 0)

    profile = {
        "date": snapshot_date,
        "h_index": h_index,
        "h_index_5y": h_index_5y,
        "i10_index": i10_index,
        "i10_index_5y": i10_index_5y,
        "total_citations": total_citations_all,
        "total_citations_5y": total_citations_5y,
    }
    log.info(f"Profile: h={h_index}, citations={total_citations_all}, papers={len(all_articles)}")

    papers = []
    for article in all_articles:
        authors_str = article.get("authors", "")
        journal = article.get("publication", "")
        # publication field often looks like "Journal Name, year" — strip year
        if journal and "," in journal:
            parts = journal.rsplit(",", 1)
            if parts[-1].strip().isdigit():
                journal = parts[0].strip()

        papers.append({
            "date": snapshot_date,
            "paper_id": article.get("citation_id", article.get("title", "")[:40]),
            "title": article.get("title", ""),
            "authors": authors_str,
            "coauthor_count": _count_coauthors(authors_str),
            "journal": journal,
            "pub_year": article.get("year", ""),
            "citations": article.get("cited_by", {}).get("value", 0),
        })

    log.info(f"Done. {len(papers)} papers scraped.")
    return profile, papers
