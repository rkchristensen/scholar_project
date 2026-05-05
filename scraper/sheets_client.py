"""
Reads and writes Scholar snapshots to Google Sheets.

Sheet layout:
  - 'snapshots' tab: one row per weekly scrape, profile-level metrics
  - 'papers' tab: one row per paper per weekly scrape

Credentials are read from GOOGLE_CREDENTIALS_JSON env var (JSON string of
the service account key file) and GOOGLE_SHEET_ID env var.
"""

import os
import json
import logging
import gspread
from google.oauth2.service_account import Credentials

log = logging.getLogger(__name__)

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

SNAPSHOT_HEADERS = [
    "date",
    "h_index",
    "h_index_5y",
    "i10_index",
    "i10_index_5y",
    "total_citations",
    "total_citations_5y",
]

PAPER_HEADERS = [
    "date",
    "paper_id",
    "title",
    "authors",
    "coauthor_count",
    "journal",
    "pub_year",
    "citations",
]


def _get_client() -> gspread.Client:
    raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    if not raw:
        raise EnvironmentError("GOOGLE_CREDENTIALS_JSON environment variable is not set.")
    creds_dict = json.loads(raw)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_worksheet(spreadsheet, name: str, headers: list[str]) -> gspread.Worksheet:
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        log.info(f"Creating worksheet '{name}'")
        ws = spreadsheet.add_worksheet(title=name, rows=10000, cols=len(headers) + 2)
        ws.append_row(headers, value_input_option="RAW")
    return ws


def append_snapshot(profile: dict, papers: list[dict]) -> None:
    client = _get_client()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    if not sheet_id:
        raise EnvironmentError("GOOGLE_SHEET_ID environment variable is not set.")

    spreadsheet = client.open_by_key(sheet_id)

    snapshots_ws = _ensure_worksheet(spreadsheet, "snapshots", SNAPSHOT_HEADERS)
    snapshots_ws.append_row(
        [profile[k] for k in SNAPSHOT_HEADERS],
        value_input_option="RAW",
    )
    log.info("Appended profile snapshot to 'snapshots' sheet.")

    papers_ws = _ensure_worksheet(spreadsheet, "papers", PAPER_HEADERS)
    rows = [[p[k] for k in PAPER_HEADERS] for p in papers]
    papers_ws.append_rows(rows, value_input_option="RAW")
    log.info(f"Appended {len(rows)} paper rows to 'papers' sheet.")


def load_snapshots() -> list[dict]:
    client = _get_client()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    spreadsheet = client.open_by_key(sheet_id)
    ws = spreadsheet.worksheet("snapshots")
    return ws.get_all_records()


def load_papers() -> list[dict]:
    client = _get_client()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    spreadsheet = client.open_by_key(sheet_id)
    ws = spreadsheet.worksheet("papers")
    return ws.get_all_records()
