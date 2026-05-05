# Setup Guide

## What you're building

- **Scraper**: Python script that reads your Google Scholar profile weekly
- **Storage**: Google Sheet with two tabs (`snapshots` + `papers`)
- **Scheduler**: GitHub Actions runs the scraper every Monday at 6am UTC
- **Dashboard**: Streamlit app auto-deployed from this repo

---

## Step 1 — Google Cloud: Create a Service Account

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable two APIs:
   - **Google Sheets API** (search for it in the API Library)
   - **Google Drive API**
4. Go to **IAM & Admin → Service Accounts → Create Service Account**
   - Name: `scholar-dashboard`
   - Role: no role needed (click Continue)
5. Click the service account → **Keys → Add Key → Create new key → JSON**
6. Save the downloaded `.json` file — you'll need its contents in Steps 3 and 4

---

## Step 2 — Create the Google Sheet

1. Go to [sheets.google.com](https://sheets.google.com) and create a blank spreadsheet
2. Name it `Scholar Dashboard` (or anything you like)
3. Copy the **Sheet ID** from the URL:
   `https://docs.google.com/spreadsheets/d/THIS_IS_THE_ID/edit`
4. Share the spreadsheet with the **service account email**
   (looks like `scholar-dashboard@your-project.iam.gserviceaccount.com`)
   — give it **Editor** access

The scraper will automatically create `snapshots` and `papers` tabs on first run.

---

## Step 3 — GitHub Repository Setup

1. Push this folder to a new GitHub repository (can be private)
2. Go to **Settings → Secrets and variables → Actions → New repository secret**

Add two secrets:

| Name | Value |
|---|---|
| `GOOGLE_CREDENTIALS_JSON` | The entire contents of the JSON key file from Step 1 (paste as-is) |
| `GOOGLE_SHEET_ID` | The Sheet ID from Step 2 |

---

## Step 4 — Run the Scraper for the First Time

In the GitHub repo, go to **Actions → Weekly Scholar Scraper → Run workflow**.

This does the first scrape. It takes 5–15 minutes depending on how many papers you have.
After it completes, check your Google Sheet — you should see rows in both tabs.

The scraper will then run automatically every Monday at 6am UTC.

---

## Step 5 — Deploy the Dashboard on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app**
   - Repository: your GitHub repo
   - Branch: `main`
   - Main file path: `dashboard/app.py`
3. Click **Advanced settings → Secrets** and paste:

```toml
GOOGLE_SHEET_ID = "your-sheet-id-here"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----\n"
client_email = "scholar-dashboard@your-project.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
```

Copy all of these fields from the JSON key file downloaded in Step 1.
The `private_key` field needs `\n` to stay as literal `\n` (not actual newlines) — Streamlit handles it correctly.

4. Click **Deploy** — your app will be live at a `*.streamlit.app` URL within a minute.

---

## Local Development

```bash
cd scholar-dashboard
pip install -r requirements.txt

# Copy secrets template
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Edit .streamlit/secrets.toml with your real values

# Run dashboard locally
streamlit run dashboard/app.py

# Run scraper locally (uses env vars instead of st.secrets)
export GOOGLE_CREDENTIALS_JSON='{ ... paste JSON key contents ... }'
export GOOGLE_SHEET_ID='your-sheet-id'
python scraper/run_scraper.py
```

---

## Dashboard Tabs

| Tab | What it shows |
|---|---|
| 📈 Citation Trends | Line chart of cumulative citations per paper; select which papers to display |
| 📋 Weekly Report | Pick any past week; see citation deltas per paper + bar chart |
| ⚡ Surprise Detector | Papers whose citation gain exceeded 1.75× their 4-week rolling average |
| 📰 Journal Analysis | Total + avg citations grouped by journal/venue |
| 👥 Collaboration | Scatter: author count vs citations, with regression line + bucket table |
| 📊 H-index & Totals | H-index trend, total citations over time, citations by publication year |
