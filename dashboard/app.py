"""
Retail Revenue Intelligence — interactive Streamlit dashboard.

Run from project root:
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cohorts import build_cohort_table
from src.config import load_config
from src.metrics import (
    category_performance,
    channel_performance,
    kpis,
    product_abc,
    region_performance,
    revenue_trend,
)
from src.rfm import segment_summary

st.set_page_config(
    page_title="Retail Revenue Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

SEGMENT_COLORS = {
    "Champions": "#148F77",
    "Loyal": "#1ABC9C",
    "Potential Loyalists": "#3498DB",
    "New Customers": "#5DADE2",
    "At Risk": "#E67E22",
    "Hibernating": "#95A5A6",
    "Lost": "#C0392B",
    "Need Attention": "#F39C12",
}


@st.cache_data(show_spinner="Loading processed data…")
def load_data():
    cfg = load_config()
    orders = pd.read_csv(cfg["data"]["processed_path"], parse_dates=["order_date", "signup_date"])
    rfm = pd.read_csv(cfg["data"]["rfm_path"])
    return orders, rfm, cfg


@st.cache_data(show_spinner=False)
def load_summary(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def money(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x/1e6:.2f}M"
    if abs(x) >= 1_000:
        return f"${x/1e3:.1f}K"
    return f"${x:,.0f}"


def pct_delta(current: float, previous: float) -> str | None:
    if previous == 0:
        return None
    return f"{((current - previous) / previous) * 100:+.1f}%"


def latest_period_delta(trend: pd.DataFrame, column: str) -> str | None:
    if len(trend) < 2:
        return None
    return pct_delta(float(trend[column].iloc[-1]), float(trend[column].iloc[-2]))


def segment_actions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("Champions", "Protect", "Early access, VIP support, no blanket discounts"),
            ("Loyal", "Grow", "Invite to subscription, bundles, and referral offers"),
            ("Potential Loyalists", "Nurture", "Second-purchase offer and category education"),
            ("New Customers", "Onboard", "First 30-day email/push sequence"),
            ("At Risk", "Win back", "Personalized offer based on historical value"),
            ("Need Attention", "Re-engage", "Reminder plus relevant replenishment or browse trigger"),
            ("Hibernating", "Suppress/test", "Low-cost reactivation test before paid spend"),
            ("Lost", "Limit spend", "Exclude from broad campaigns unless high monetary value"),
        ],
        columns=["Segment", "Priority", "Recommended action"],
    )


MONEY_COLUMNS = {
    "revenue": st.column_config.NumberColumn("Revenue", format="$%.0f"),
    "profit": st.column_config.NumberColumn("Profit", format="$%.0f"),
    "avg_monetary": st.column_config.NumberColumn("Avg monetary", format="$%.0f"),
    "avg_aov": st.column_config.NumberColumn("Avg AOV", format="$%.0f"),
    "aov": st.column_config.NumberColumn("AOV", format="$%.2f"),
}
PCT_COLUMNS = {
    "margin_pct": st.column_config.NumberColumn("Margin", format="%.2f%%"),
    "revenue_share_pct": st.column_config.NumberColumn("Revenue share", format="%.2f%%"),
    "customer_share_pct": st.column_config.NumberColumn("Customer share", format="%.2f%%"),
}


def main() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; }
        div[data-testid="stMetricValue"] { font-size: 1.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("Retail Revenue Intelligence")
    st.caption("Portfolio analytics dashboard · RFM · Cohorts · Product performance")

    try:
        orders, rfm, cfg = load_data()
    except FileNotFoundError:
        st.error(
            "Processed data not found. From the project root run:\n\n"
            "`python scripts/run_analysis.py`"
        )
        st.stop()

    # Sidebar filters
    st.sidebar.header("Filters")
    regions = sorted(orders["region"].dropna().unique())
    channels = sorted(orders["channel"].dropna().unique())
    categories = sorted(orders["category"].dropna().unique())

    sel_regions = st.sidebar.multiselect("Region", regions, default=regions)
    sel_channels = st.sidebar.multiselect("Channel", channels, default=channels)
    sel_categories = st.sidebar.multiselect("Category", categories, default=categories)
    date_min = orders["order_date"].min().date()
    date_max = orders["order_date"].max().date()
    date_range = st.sidebar.date_input("Date range", value=(date_min, date_max), min_value=date_min, max_value=date_max)

    if isinstance(date_range, tuple) and len(date_range) == 2:
        d0, d1 = date_range
    else:
        d0, d1 = date_min, date_max

    mask = (
        orders["region"].isin(sel_regions)
        & orders["channel"].isin(sel_channels)
        & orders["category"].isin(sel_categories)
        & (orders["order_date"].dt.date >= d0)
        & (orders["order_date"].dt.date <= d1)
    )
    f_orders = orders.loc[mask].copy()
    if f_orders.empty:
        st.warning("No rows match the current filters.")
        st.stop()

    # RFM filter by customers present in filtered orders
    f_customers = set(f_orders["customer_id"].unique())
    f_rfm = rfm[rfm["customer_id"].isin(f_customers)].copy()

    summary = load_summary(cfg["output"]["summary_path"])
    kpi = kpis(f_orders)
    trend = revenue_trend(f_orders, freq="M")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Revenue", money(kpi["total_revenue"]), latest_period_delta(trend, "revenue"))
    c2.metric("Profit", money(kpi["total_profit"]), latest_period_delta(trend, "profit"))
    c3.metric("Orders", f"{kpi['orders']:,}", latest_period_delta(trend, "orders"))
    c4.metric("Customers", f"{kpi['customers']:,}")
    c5.metric("AOV", f"${kpi['aov']:,.2f}")
    c6.metric("Repeat rate", f"{kpi['repeat_purchase_rate_pct']}%")

    tab_exec, tab_overview, tab_customers, tab_products, tab_cohorts = st.tabs(
        ["Executive Summary", "Overview", "Customers (RFM)", "Products", "Cohorts"]
    )

    with tab_exec:
        e1, e2, e3 = st.columns(3)
        e1.metric("Top segment", summary.get("top_segment", {}).get("segment", "n/a"))
        e2.metric("Top category", summary.get("top_category", "n/a"))
        e3.metric("At-risk customers", f"{summary.get('at_risk_customers', 0):,}")

        top_channel = summary.get("top_channel", "n/a")
        top_region = summary.get("top_region", "n/a")
        m1 = (summary.get("cohort") or {}).get("avg_m1_retention_pct", "n/a")
        champion_share = summary.get("champions_revenue_share", 0)

        st.subheader("What changed the business")
        st.markdown(
            "\n".join(
                [
                    f"- Champions drive **{champion_share:.1f}%** of segment revenue share.",
                    f"- **{top_channel}** leads channels and **{top_region}** leads regions.",
                    f"- Month-1 retention averages **{m1}%**, so early lifecycle work is the cleanest growth lever.",
                    f"- Filtered view currently spans **{kpi['date_start']}** to **{kpi['date_end']}**.",
                ]
            )
        )

        st.subheader("Segment playbook")
        st.dataframe(segment_actions(), use_container_width=True, hide_index=True)
        st.caption(f"RFM recency snapshot date: {cfg['analysis']['snapshot_date']}")

    with tab_overview:
        t1, t2 = st.columns(2)
        with t1:
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=trend["period"],
                    y=trend["revenue"],
                    mode="lines+markers",
                    name="Revenue",
                    line=dict(color="#1B4F72", width=3),
                    fill="tozeroy",
                    fillcolor="rgba(27,79,114,0.12)",
                )
            )
            fig.update_layout(title="Monthly revenue", height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with t2:
            ch = channel_performance(f_orders)
            fig = px.bar(
                ch,
                x="channel",
                y="revenue",
                color="margin_pct",
                title="Revenue by channel",
                color_continuous_scale="Teal",
                text_auto=".2s",
            )
            fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

        r1, r2 = st.columns(2)
        with r1:
            reg = region_performance(f_orders)
            fig = px.bar(
                reg,
                x="region",
                y="revenue",
                color="aov",
                title="Revenue by region (color = AOV)",
                color_continuous_scale="Teal",
            )
            fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)
        with r2:
            cat = category_performance(f_orders)
            fig = px.bar(
                cat.sort_values("revenue"),
                x="revenue",
                y="category",
                orientation="h",
                title="Category revenue",
                color="margin_pct",
                color_continuous_scale="Viridis",
            )
            fig.update_layout(height=380, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

    with tab_customers:
        if f_rfm.empty:
            st.info("No RFM rows for current filter.")
        else:
            seg = segment_summary(f_rfm)
            s1, s2 = st.columns(2)
            with s1:
                fig = px.bar(
                    seg.sort_values("customers"),
                    x="customers",
                    y="segment",
                    orientation="h",
                    title="Customers by RFM segment",
                    color="segment",
                    color_discrete_map=SEGMENT_COLORS,
                )
                fig.update_layout(showlegend=False, height=420, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True)
            with s2:
                fig = px.bar(
                    seg.sort_values("revenue"),
                    x="revenue",
                    y="segment",
                    orientation="h",
                    title="Revenue by RFM segment",
                    color="segment",
                    color_discrete_map=SEGMENT_COLORS,
                )
                fig.update_layout(showlegend=False, height=420, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True)

            sample = f_rfm.sample(min(2500, len(f_rfm)), random_state=42)
            fig = px.scatter(
                sample,
                x="frequency",
                y="monetary",
                color="segment",
                size="avg_order_value",
                hover_data=["customer_id", "recency_days", "RFM_score"],
                title="Customer value map (sample)",
                color_discrete_map=SEGMENT_COLORS,
                opacity=0.65,
            )
            fig.update_layout(height=480, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

            st.subheader("Segment summary table")
            st.dataframe(seg, use_container_width=True, hide_index=True)

    with tab_products:
        cat = category_performance(f_orders)
        st.dataframe(
            cat[
                [
                    "category",
                    "revenue",
                    "profit",
                    "margin_pct",
                    "revenue_share_pct",
                    "units",
                    "orders",
                    "abc",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={**MONEY_COLUMNS, **PCT_COLUMNS},
        )
        top = product_abc(f_orders, top_n=20)
        fig = px.bar(
            top.sort_values("revenue"),
            x="revenue",
            y="product_name",
            color="category",
            orientation="h",
            title="Top 20 products",
        )
        fig.update_layout(height=560, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.download_button(
            "Download category summary",
            cat.to_csv(index=False).encode("utf-8"),
            "category_summary.csv",
            "text/csv",
        )

    with tab_cohorts:
        retention, sizes = build_cohort_table(f_orders, acquisition_orders=orders)
        # Plotly heatmap of last 15 cohorts × 12 periods
        cols = [c for c in retention.columns if isinstance(c, (int,)) or str(c).isdigit()]
        cols = sorted(cols, key=lambda x: int(x))[:12]
        mat = retention[cols].tail(15)
        fig = px.imshow(
            mat,
            aspect="auto",
            color_continuous_scale="YlGnBu",
            labels=dict(x="Months since first purchase", y="Cohort", color="Retention %"),
            title="Cohort retention heatmap",
            text_auto=".0f",
        )
        fig.update_layout(height=520, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            f"Cohorts in view: {len(mat)} · Max period index: {cols[-1] if cols else 0} · "
            "Acquisition month is based on each customer's first purchase in the full dataset."
        )

    st.sidebar.download_button(
        "Download filtered orders",
        f_orders.to_csv(index=False).encode("utf-8"),
        "filtered_orders.csv",
        "text/csv",
    )
    st.sidebar.download_button(
        "Download filtered RFM",
        f_rfm.to_csv(index=False).encode("utf-8"),
        "filtered_rfm.csv",
        "text/csv",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"**Project:** {cfg['project']['name']}  \n"
        f"**Window:** {kpi['date_start']} → {kpi['date_end']}"
    )
    st.sidebar.markdown("[Re-run pipeline](../scripts/run_analysis.py) · `python scripts/run_analysis.py`")


if __name__ == "__main__":
    main()
