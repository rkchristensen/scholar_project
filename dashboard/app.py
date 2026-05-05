"""
Google Scholar Citation Dashboard
Hosted on Streamlit Community Cloud, reads data from Google Sheets.
"""

import os
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Scholar Dashboard",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SCHOLAR_URL = "https://scholar.google.com/citations?user=-5aAUboAAAAJ&hl=en"
ROLLING_WINDOW = 4  # weeks for rolling average in surprise detection
SURPRISE_MULTIPLIER = 1.75  # gain > X × rolling avg triggers surprise flag

# ── Data loading ─────────────────────────────────────────────────────────────

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]


def _get_client():
    # Streamlit Cloud stores secrets as TOML; local dev uses env var
    if "gcp_service_account" in st.secrets:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=SCOPES
        )
    else:
        raw = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        if not raw:
            st.error("No Google credentials found. Set GOOGLE_CREDENTIALS_JSON or configure st.secrets.")
            st.stop()
        creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return gspread.authorize(creds)


def _sheet_id():
    if "GOOGLE_SHEET_ID" in st.secrets:
        return st.secrets["GOOGLE_SHEET_ID"]
    return os.environ.get("GOOGLE_SHEET_ID", "")


@st.cache_data(ttl=3600)
def load_data():
    client = _get_client()
    sid = _sheet_id()
    if not sid:
        st.error("GOOGLE_SHEET_ID not configured.")
        st.stop()
    spreadsheet = client.open_by_key(sid)

    snapshots = pd.DataFrame(spreadsheet.worksheet("snapshots").get_all_records())
    papers = pd.DataFrame(spreadsheet.worksheet("papers").get_all_records())

    snapshots["date"] = pd.to_datetime(snapshots["date"])
    papers["date"] = pd.to_datetime(papers["date"])
    papers["citations"] = pd.to_numeric(papers["citations"], errors="coerce").fillna(0).astype(int)
    papers["pub_year"] = pd.to_numeric(papers["pub_year"], errors="coerce")
    papers["coauthor_count"] = pd.to_numeric(papers["coauthor_count"], errors="coerce").fillna(1).astype(int)
    papers["coauthor_count"] = papers["coauthor_count"].clip(lower=1)

    return snapshots, papers


# ── Derived data helpers ──────────────────────────────────────────────────────

def compute_weekly_deltas(papers: pd.DataFrame) -> pd.DataFrame:
    """
    For each (paper_id, date) compute citation delta vs previous snapshot.
    Returns papers df with added 'delta' and 'prev_citations' columns.
    """
    papers = papers.sort_values(["paper_id", "date"])
    papers["prev_citations"] = papers.groupby("paper_id")["citations"].shift(1)
    papers["delta"] = papers["citations"] - papers["prev_citations"]
    return papers


def compute_surprise_flags(papers: pd.DataFrame) -> pd.DataFrame:
    """
    Flag papers whose delta this week exceeds SURPRISE_MULTIPLIER × rolling average delta.
    Adds 'rolling_avg_delta' and 'surprise' columns.
    """
    papers = papers.sort_values(["paper_id", "date"])
    papers["rolling_avg_delta"] = (
        papers.groupby("paper_id")["delta"]
        .transform(lambda s: s.shift(1).rolling(ROLLING_WINDOW, min_periods=1).mean())
    )
    papers["surprise"] = (
        (papers["delta"] > 0)
        & (papers["rolling_avg_delta"] > 0)
        & (papers["delta"] >= SURPRISE_MULTIPLIER * papers["rolling_avg_delta"])
    )
    return papers


def latest_snapshot_per_paper(papers: pd.DataFrame) -> pd.DataFrame:
    """Return the most recent row per paper."""
    return papers.sort_values("date").groupby("paper_id").last().reset_index()


# ── UI helpers ────────────────────────────────────────────────────────────────

def _fmt_delta(v):
    if pd.isna(v):
        return "—"
    v = int(v)
    return f"+{v}" if v >= 0 else str(v)


def _color_delta(v):
    if pd.isna(v) or v == 0:
        return "color: gray"
    return "color: green" if v > 0 else "color: red"


# ── Main dashboard ────────────────────────────────────────────────────────────

def main():
    st.title("📚 Google Scholar Citation Dashboard")
    st.markdown(
        f"Data from [Google Scholar profile]({SCHOLAR_URL}) · "
        "Refreshed weekly via GitHub Actions · "
        f"Rolling surprise window: {ROLLING_WINDOW} weeks"
    )

    with st.spinner("Loading data from Google Sheets…"):
        snapshots, papers_raw = load_data()

    if snapshots.empty or papers_raw.empty:
        st.warning("No data yet. Run the scraper at least once to populate the sheets.")
        st.stop()

    papers = compute_weekly_deltas(papers_raw)
    papers = compute_surprise_flags(papers)

    dates_available = sorted(papers["date"].unique(), reverse=True)
    latest_date = dates_available[0]
    prev_date = dates_available[1] if len(dates_available) > 1 else None

    # ── Top KPI row ──────────────────────────────────────────────────────────

    latest_snap = snapshots.sort_values("date").iloc[-1]
    prev_snap = snapshots.sort_values("date").iloc[-2] if len(snapshots) > 1 else None

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric(
        "Total Citations",
        f"{latest_snap['total_citations']:,}",
        delta=f"{int(latest_snap['total_citations'] - prev_snap['total_citations']):+,}" if prev_snap is not None else None,
    )
    k2.metric(
        "H-index",
        latest_snap["h_index"],
        delta=f"{int(latest_snap['h_index'] - prev_snap['h_index']):+}" if prev_snap is not None else None,
    )
    k3.metric(
        "i10-index",
        latest_snap["i10_index"],
        delta=f"{int(latest_snap['i10_index'] - prev_snap['i10_index']):+}" if prev_snap is not None else None,
    )
    k4.metric("Papers Tracked", papers["paper_id"].nunique())
    k5.metric(
        "Last Snapshot",
        latest_date.strftime("%b %d, %Y"),
    )

    st.divider()

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        ["📈 Citation Trends", "📋 Weekly Report", "⚡ Surprise Detector", "📰 Journal Analysis", "👥 Collaboration", "📊 H-index & Totals"]
    )

    # ── Tab 1: Citation Trajectory ───────────────────────────────────────────

    with tab1:
        st.subheader("Citation Trajectory per Paper")

        latest_per_paper = latest_snapshot_per_paper(papers)
        top_papers = latest_per_paper.nlargest(10, "citations")["title"].tolist()

        all_titles = sorted(papers["title"].unique())
        selected = st.multiselect(
            "Select papers to display (default: top 10 by citations)",
            options=all_titles,
            default=[t for t in top_papers if t in all_titles],
            key="traj_select",
        )

        if selected:
            df_plot = papers[papers["title"].isin(selected)].sort_values("date")
            fig = px.line(
                df_plot,
                x="date",
                y="citations",
                color="title",
                markers=True,
                labels={"citations": "Total Citations", "date": "Snapshot Date", "title": "Paper"},
                title="Cumulative Citations Over Time",
            )
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.5))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least one paper above.")

    # ── Tab 2: Weekly Report ─────────────────────────────────────────────────

    with tab2:
        st.subheader("Weekly Report")

        date_options = [d.strftime("%Y-%m-%d") for d in dates_available]
        selected_week = st.selectbox("Select week", options=date_options, index=0, key="weekly_date")
        selected_dt = pd.Timestamp(selected_week)

        week_papers = papers[papers["date"] == selected_dt].copy()

        if week_papers.empty:
            st.info("No data for this week.")
        else:
            week_papers_sorted = week_papers.sort_values("delta", ascending=False, na_position="last")

            st.markdown(f"**Snapshot date:** {selected_week}")

            gained = week_papers_sorted[week_papers_sorted["delta"] > 0]
            no_change = week_papers_sorted[week_papers_sorted["delta"] == 0]
            first_seen = week_papers_sorted[week_papers_sorted["prev_citations"].isna()]

            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Papers with new citations", len(gained))
            col_b.metric("Papers unchanged", len(no_change))
            col_c.metric("New papers (first snapshot)", len(first_seen))

            st.markdown("#### Citation Changes")
            display_cols = ["title", "journal", "pub_year", "citations", "delta"]
            display_df = week_papers_sorted[display_cols].rename(
                columns={
                    "title": "Paper",
                    "journal": "Journal",
                    "pub_year": "Year",
                    "citations": "Total Citations",
                    "delta": "Δ This Week",
                }
            )
            display_df["Δ This Week"] = display_df["Δ This Week"].apply(
                lambda v: f"+{int(v)}" if pd.notna(v) and v > 0 else ("—" if pd.isna(v) else str(int(v)))
            )
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            st.markdown("#### Delta Bar Chart")
            bar_data = week_papers_sorted.dropna(subset=["delta"]).nlargest(20, "delta")
            if not bar_data.empty:
                fig_bar = px.bar(
                    bar_data,
                    x="delta",
                    y="title",
                    orientation="h",
                    color="delta",
                    color_continuous_scale=["#d73027", "#fee090", "#1a9850"],
                    labels={"delta": "Citation Gain", "title": "Paper"},
                    title=f"Top 20 Papers by Citation Gain — Week of {selected_week}",
                )
                fig_bar.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)

    # ── Tab 3: Surprise Detector ─────────────────────────────────────────────

    with tab3:
        st.subheader("⚡ Surprise Detector")
        st.markdown(
            f"Papers flagged when this week's citation gain is **≥ {SURPRISE_MULTIPLIER}×** "
            f"their {ROLLING_WINDOW}-week rolling average gain."
        )

        latest_papers = papers[papers["date"] == latest_date].copy()
        surprised = latest_papers[latest_papers["surprise"] == True].sort_values("delta", ascending=False)

        if surprised.empty:
            st.success("No surprise movements in the most recent snapshot.")
        else:
            st.warning(f"{len(surprised)} paper(s) with unusual citation velocity this week!")
            for _, row in surprised.iterrows():
                with st.expander(f"📌 {row['title'][:90]}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Citations This Week", f"+{int(row['delta'])}")
                    c2.metric("Rolling Avg Gain", f"{row['rolling_avg_delta']:.1f}")
                    c3.metric("Surprise Ratio", f"{row['delta'] / row['rolling_avg_delta']:.1f}×")
                    c4.metric("Total Citations", int(row["citations"]))
                    st.caption(f"Journal: {row['journal'] or 'N/A'} · Published: {row['pub_year'] or 'N/A'}")

        st.markdown("#### All Papers — Gain vs Rolling Average")
        velocity_data = latest_papers.dropna(subset=["delta", "rolling_avg_delta"])
        if not velocity_data.empty:
            fig_vel = go.Figure()
            fig_vel.add_bar(
                x=velocity_data["title"].str[:50],
                y=velocity_data["delta"],
                name="This Week's Gain",
                marker_color="steelblue",
            )
            fig_vel.add_bar(
                x=velocity_data["title"].str[:50],
                y=velocity_data["rolling_avg_delta"],
                name=f"{ROLLING_WINDOW}-week Avg Gain",
                marker_color="orange",
                opacity=0.6,
            )
            fig_vel.update_layout(
                barmode="overlay",
                xaxis_tickangle=-45,
                legend=dict(orientation="h"),
                title="Citation Gain vs Rolling Average (Latest Week)",
            )
            st.plotly_chart(fig_vel, use_container_width=True)

    # ── Tab 4: Journal Analysis ──────────────────────────────────────────────

    with tab4:
        st.subheader("📰 Journal / Venue Analysis")
        st.markdown("Based on most recent citation counts per paper.")

        latest_per_paper = latest_snapshot_per_paper(papers)
        latest_per_paper["journal_clean"] = latest_per_paper["journal"].str.strip().replace("", "Unknown / Preprint")
        latest_per_paper["journal_clean"] = latest_per_paper["journal_clean"].fillna("Unknown / Preprint")

        journal_stats = (
            latest_per_paper.groupby("journal_clean")
            .agg(
                papers=("paper_id", "count"),
                total_citations=("citations", "sum"),
                avg_citations=("citations", "mean"),
                max_citations=("citations", "max"),
            )
            .reset_index()
            .rename(columns={"journal_clean": "Journal / Venue"})
            .sort_values("total_citations", ascending=False)
        )
        journal_stats["avg_citations"] = journal_stats["avg_citations"].round(1)

        min_papers = st.slider("Minimum papers per journal", 1, 5, 1, key="journal_slider")
        filtered = journal_stats[journal_stats["papers"] >= min_papers]

        st.dataframe(filtered, use_container_width=True, hide_index=True)

        col_j1, col_j2 = st.columns(2)

        with col_j1:
            top_journals = filtered.nlargest(15, "total_citations")
            fig_j1 = px.bar(
                top_journals,
                x="total_citations",
                y="Journal / Venue",
                orientation="h",
                color="papers",
                color_continuous_scale="Blues",
                title="Total Citations by Journal (Top 15)",
                labels={"total_citations": "Total Citations", "papers": "# Papers"},
            )
            fig_j1.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_j1, use_container_width=True)

        with col_j2:
            top_avg = filtered[filtered["papers"] >= 2].nlargest(15, "avg_citations")
            fig_j2 = px.bar(
                top_avg,
                x="avg_citations",
                y="Journal / Venue",
                orientation="h",
                color="avg_citations",
                color_continuous_scale="Greens",
                title="Avg Citations per Paper by Journal (≥2 papers)",
                labels={"avg_citations": "Avg Citations per Paper"},
            )
            fig_j2.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
            st.plotly_chart(fig_j2, use_container_width=True)

    # ── Tab 5: Collaboration ─────────────────────────────────────────────────

    with tab5:
        st.subheader("👥 Coauthor Count vs Citations")

        latest_per_paper = latest_snapshot_per_paper(papers)

        fig_co = px.scatter(
            latest_per_paper,
            x="coauthor_count",
            y="citations",
            color="pub_year",
            hover_data=["title", "journal"],
            trendline="ols",
            labels={
                "coauthor_count": "Number of Authors",
                "citations": "Total Citations",
                "pub_year": "Year Published",
            },
            title="Does Author Count Correlate with Citations?",
            color_continuous_scale="Viridis",
        )
        st.plotly_chart(fig_co, use_container_width=True)

        # Summary stats by coauthor bucket
        latest_per_paper["author_bucket"] = pd.cut(
            latest_per_paper["coauthor_count"],
            bins=[0, 1, 2, 3, 5, 10, 9999],
            labels=["Solo", "2 authors", "3 authors", "4–5 authors", "6–10 authors", "11+ authors"],
        )
        bucket_stats = (
            latest_per_paper.groupby("author_bucket", observed=True)["citations"]
            .agg(["count", "mean", "median", "sum"])
            .reset_index()
            .rename(columns={"author_bucket": "Author Count", "count": "Papers", "mean": "Avg Citations", "median": "Median Citations", "sum": "Total Citations"})
        )
        bucket_stats["Avg Citations"] = bucket_stats["Avg Citations"].round(1)
        bucket_stats["Median Citations"] = bucket_stats["Median Citations"].round(1)
        st.dataframe(bucket_stats, use_container_width=True, hide_index=True)

    # ── Tab 6: H-index & Totals ──────────────────────────────────────────────

    with tab6:
        st.subheader("📊 H-index Trend & Overall Citation History")

        snaps_sorted = snapshots.sort_values("date")

        col_h1, col_h2 = st.columns(2)

        with col_h1:
            fig_h = go.Figure()
            fig_h.add_scatter(
                x=snaps_sorted["date"],
                y=snaps_sorted["h_index"],
                mode="lines+markers",
                name="h-index (all time)",
                line=dict(color="steelblue", width=2),
            )
            fig_h.add_scatter(
                x=snaps_sorted["date"],
                y=snaps_sorted["h_index_5y"],
                mode="lines+markers",
                name="h-index (last 5 years)",
                line=dict(color="orange", width=2, dash="dot"),
            )
            fig_h.update_layout(
                title="H-index Over Time",
                yaxis_title="H-index",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_h, use_container_width=True)

        with col_h2:
            fig_cit = go.Figure()
            fig_cit.add_scatter(
                x=snaps_sorted["date"],
                y=snaps_sorted["total_citations"],
                mode="lines+markers",
                name="All-time Citations",
                line=dict(color="green", width=2),
                fill="tozeroy",
                fillcolor="rgba(0,200,100,0.1)",
            )
            fig_cit.add_scatter(
                x=snaps_sorted["date"],
                y=snaps_sorted["total_citations_5y"],
                mode="lines+markers",
                name="Citations (last 5 years)",
                line=dict(color="teal", width=2, dash="dot"),
            )
            fig_cit.update_layout(
                title="Total Citations Over Time",
                yaxis_title="Citations",
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig_cit, use_container_width=True)

        st.markdown("#### Citations by Publication Year")
        latest_per_paper = latest_snapshot_per_paper(papers)
        year_stats = (
            latest_per_paper.dropna(subset=["pub_year"])
            .groupby("pub_year")["citations"]
            .agg(["sum", "count", "mean"])
            .reset_index()
            .rename(columns={"pub_year": "Year", "sum": "Total Citations", "count": "Papers", "mean": "Avg Citations"})
            .sort_values("Year")
        )
        year_stats["Avg Citations"] = year_stats["Avg Citations"].round(1)

        fig_yr = px.bar(
            year_stats,
            x="Year",
            y="Total Citations",
            color="Papers",
            color_continuous_scale="Purples",
            title="Total Citations per Publication Year",
            hover_data=["Papers", "Avg Citations"],
        )
        st.plotly_chart(fig_yr, use_container_width=True)

        st.dataframe(year_stats.sort_values("Year", ascending=False), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
