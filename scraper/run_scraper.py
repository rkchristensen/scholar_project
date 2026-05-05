"""
Entry point for the weekly scraper job.
Run directly: python scraper/run_scraper.py
Or via GitHub Actions (see .github/workflows/weekly_scraper.yml).
"""

import sys
import logging
from scrape_scholar import scrape_profile
from sheets_client import append_snapshot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    log.info("=== Scholar scraper starting ===")
    try:
        profile, papers = scrape_profile()
        append_snapshot(profile, papers)
        log.info("=== Scraper finished successfully ===")
    except Exception as e:
        log.error(f"Scraper failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
