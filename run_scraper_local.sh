#!/bin/bash
# Weekly Scholar scraper — runs from your Mac (residential IP, not blocked by Google).
# Called by launchd every Monday. Logs to ~/Library/Logs/scholar_scraper.log

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG="$HOME/Library/Logs/scholar_scraper.log"

echo "$(date): Starting scraper" >> "$LOG"

set -a
source "$SCRIPT_DIR/.env"
set +a

cd "$SCRIPT_DIR"
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 scraper/run_scraper.py >> "$LOG" 2>&1

echo "$(date): Scraper finished with exit code $?" >> "$LOG"
