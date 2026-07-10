"""Business metrics, product analytics, and insight generation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import load_config
from src.cohorts import cohort_insights
from src.rfm import segment_summary


def _pct(numerator: pd.Series | float, denominator: pd.Series | float) -> pd.Series | float:
    """Return a percent while avoiding inf/nan from zero denominators."""
    if isinstance(denominator, pd.Series):
        return np.where(denominator.ne(0), 100 * numerator / denominator, 0)
    if isinstance(numerator, pd.Series):
        return pd.Series(0, index=numerator.index, dtype=float) if denominator == 0 else 100 * numerator / denominator
    return 100 * numerator / denominator if denominator else 0


def kpis(orders: pd.DataFrame) -> dict:
    order_level = (
        orders.groupby("order_id", as_index=False)
        .agg(
            order_date=("order_date", "max"),
            customer_id=("customer_id", "first"),
            revenue=("line_revenue", "sum"),
            profit=("line_profit", "sum"),
            items=("quantity", "sum"),
        )
    )
    total_rev = float(order_level["revenue"].sum())
    total_profit = float(order_level["profit"].sum())
    n_orders = len(order_level)
    n_customers = int(order_level["customer_id"].nunique())
    aov = total_rev / n_orders if n_orders else 0
    freq = order_level.groupby("customer_id").size()
    repeat_rate = float((freq > 1).mean() * 100)

    monthly = (
        order_level.assign(month=order_level["order_date"].dt.to_period("M").astype(str))
        .groupby("month")["revenue"]
        .sum()
    )
    mom = monthly.pct_change().iloc[-1] * 100 if len(monthly) > 1 else 0

    return {
        "total_revenue": round(total_rev, 2),
        "total_profit": round(total_profit, 2),
        "profit_margin_pct": round(_pct(total_profit, total_rev), 2),
        "orders": n_orders,
        "customers": n_customers,
        "aov": round(aov, 2),
        "items_sold": int(orders["quantity"].sum()),
        "repeat_purchase_rate_pct": round(repeat_rate, 2),
        "avg_orders_per_customer": round(n_orders / n_customers, 2) if n_customers else 0,
        "last_month_revenue": round(float(monthly.iloc[-1]), 2) if len(monthly) else 0,
        "mom_revenue_change_pct": round(float(mom), 2) if pd.notna(mom) else 0,
        "date_start": str(orders["order_date"].min().date()),
        "date_end": str(orders["order_date"].max().date()),
    }


def revenue_trend(orders: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    order_level = (
        orders.groupby("order_id", as_index=False)
        .agg(
            order_date=("order_date", "max"),
            revenue=("line_revenue", "sum"),
            profit=("line_profit", "sum"),
        )
    )
    order_level = order_level.set_index("order_date").sort_index()
    # 'ME' month-end for newer pandas; fall back handled by resample alias
    rule = {"M": "ME", "W": "W", "D": "D"}.get(freq, freq)
    try:
        trend = order_level.resample(rule).agg(
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
            orders=("revenue", "count"),
        )
    except ValueError:
        trend = order_level.resample(freq).agg(
            revenue=("revenue", "sum"),
            profit=("profit", "sum"),
            orders=("revenue", "count"),
        )
    trend = trend.reset_index()
    trend["period"] = pd.to_datetime(trend["order_date"]).dt.strftime("%Y-%m")
    return trend


def category_performance(orders: pd.DataFrame) -> pd.DataFrame:
    cat = (
        orders.groupby("category", as_index=False)
        .agg(
            revenue=("line_revenue", "sum"),
            profit=("line_profit", "sum"),
            units=("quantity", "sum"),
            orders=("order_id", "nunique"),
            customers=("customer_id", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    revenue_total = cat["revenue"].sum()
    cat["margin_pct"] = _pct(cat["profit"], cat["revenue"]).round(2)
    cat["revenue_share_pct"] = _pct(cat["revenue"], revenue_total).round(2)
    cat["cum_share"] = cat["revenue"].cumsum() / revenue_total if revenue_total else 0
    cat["abc"] = pd.cut(cat["cum_share"], bins=[0, 0.8, 0.95, 1.01], labels=["A", "B", "C"])
    return cat


def product_abc(orders: pd.DataFrame, top_n: int = 25) -> pd.DataFrame:
    prod = (
        orders.groupby(["product_id", "product_name", "category"], as_index=False)
        .agg(
            revenue=("line_revenue", "sum"),
            units=("quantity", "sum"),
            profit=("line_profit", "sum"),
        )
        .sort_values("revenue", ascending=False)
    )
    revenue_total = prod["revenue"].sum()
    prod["cum_share"] = prod["revenue"].cumsum() / revenue_total if revenue_total else 0
    prod["abc"] = np.where(
        prod["cum_share"] <= 0.80,
        "A",
        np.where(prod["cum_share"] <= 0.95, "B", "C"),
    )
    return prod.head(top_n)


def channel_performance(orders: pd.DataFrame) -> pd.DataFrame:
    ch = (
        orders.groupby("channel", as_index=False)
        .agg(
            revenue=("line_revenue", "sum"),
            profit=("line_profit", "sum"),
            orders=("order_id", "nunique"),
            customers=("customer_id", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    ch["aov"] = np.where(ch["orders"].ne(0), ch["revenue"] / ch["orders"], 0).round(2)
    ch["margin_pct"] = _pct(ch["profit"], ch["revenue"]).round(2)
    ch["revenue_share_pct"] = _pct(ch["revenue"], ch["revenue"].sum()).round(2)
    return ch


def region_performance(orders: pd.DataFrame) -> pd.DataFrame:
    reg = (
        orders.groupby("region", as_index=False)
        .agg(
            revenue=("line_revenue", "sum"),
            profit=("line_profit", "sum"),
            orders=("order_id", "nunique"),
            customers=("customer_id", "nunique"),
        )
        .sort_values("revenue", ascending=False)
    )
    reg["aov"] = np.where(reg["orders"].ne(0), reg["revenue"] / reg["orders"], 0).round(2)
    reg["revenue_share_pct"] = _pct(reg["revenue"], reg["revenue"].sum()).round(2)
    return reg


def monthly_category_heatmap_data(orders: pd.DataFrame) -> pd.DataFrame:
    g = (
        orders.assign(month=orders["order_date"].dt.to_period("M").astype(str))
        .groupby(["month", "category"])["line_revenue"]
        .sum()
        .reset_index()
    )
    return g.pivot(index="category", columns="month", values="line_revenue").fillna(0)


def _fmt_money(x: float) -> str:
    if abs(x) >= 1_000_000:
        return f"${x / 1_000_000:.2f}M"
    if abs(x) >= 1_000:
        return f"${x / 1_000:.1f}K"
    return f"${x:,.0f}"


def build_insights(
    orders: pd.DataFrame,
    rfm: pd.DataFrame,
    retention: pd.DataFrame,
    sizes: pd.DataFrame,
    quality: dict,
    cfg: dict | None = None,
) -> tuple[dict, str]:
    """Compile executive metrics + markdown narrative."""
    cfg = cfg or load_config()
    kpi = kpis(orders)
    seg = segment_summary(rfm)
    cats = category_performance(orders)
    channels = channel_performance(orders)
    regions = region_performance(orders)
    coh = cohort_insights(retention, sizes)

    champions = seg[seg["segment"] == "Champions"]
    at_risk = seg[seg["segment"].isin(["At Risk", "Lost", "Hibernating"])]
    top_cat = cats.iloc[0]
    top_channel = channels.iloc[0]
    top_region = regions.iloc[0]

    summary = {
        "kpis": kpi,
        "data_quality": quality,
        "cohort": coh,
        "top_segment": seg.iloc[0].to_dict() if len(seg) else {},
        "champions_revenue_share": float(champions["revenue_share_pct"].sum()) if len(champions) else 0,
        "at_risk_customers": int(at_risk["customers"].sum()) if len(at_risk) else 0,
        "top_category": top_cat["category"],
        "top_category_revenue_share": float(top_cat["revenue_share_pct"]),
        "top_channel": top_channel["channel"],
        "top_region": top_region["region"],
        "segments": seg.to_dict(orient="records"),
        "categories": cats.to_dict(orient="records"),
        "channels": channels.to_dict(orient="records"),
        "regions": regions.to_dict(orient="records"),
    }

    md = _render_markdown(summary, seg, cats)
    return summary, md


def _render_markdown(summary: dict, seg: pd.DataFrame, cats: pd.DataFrame) -> str:
    k = summary["kpis"]
    coh = summary.get("cohort") or {}
    aov_str = f"${k['aov']:,.2f}"
    m1 = coh.get("avg_m1_retention_pct", "n/a")
    m3 = coh.get("avg_m3_retention_pct", "n/a")

    lines = [
        "# Executive Insights — Retail Revenue Intelligence",
        "",
        f"**Analysis window:** {k['date_start']} → {k['date_end']}",
        "",
        "## Headline KPIs",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Total revenue | {_fmt_money(k['total_revenue'])} |",
        f"| Total profit | {_fmt_money(k['total_profit'])} |",
        f"| Profit margin | {k['profit_margin_pct']}% |",
        f"| Orders | {k['orders']:,} |",
        f"| Customers | {k['customers']:,} |",
        f"| Average order value | {aov_str} |",
        f"| Repeat purchase rate | {k['repeat_purchase_rate_pct']}% |",
        f"| Avg orders / customer | {k['avg_orders_per_customer']} |",
        f"| MoM revenue change (latest) | {k['mom_revenue_change_pct']}% |",
        "",
        "## Key Findings",
        "",
        (
            f"1. **Revenue concentration:** Champions account for "
            f"**{summary['champions_revenue_share']:.1f}%** of segment revenue share; "
            f"the top category **{summary['top_category']}** contributes "
            f"**{summary['top_category_revenue_share']}%** of category revenue."
        ),
        (
            f"2. **Channel mix:** **{summary['top_channel']}** is the leading channel; "
            f"**{summary['top_region']}** leads geographically."
        ),
        (
            f"3. **Retention:** Average month-1 cohort retention is **{m1}%**; "
            f"month-3 is **{m3}%**."
        ),
        (
            f"4. **Risk:** **{summary['at_risk_customers']:,}** customers sit in "
            f"At Risk / Lost / Hibernating segments — prime targets for win-back campaigns."
        ),
        (
            f"5. **Data quality:** Removed **{summary['data_quality'].get('rows_removed_pct', 0)}%** "
            f"of raw rows (duplicates, invalid qty/price, orphans) before analysis."
        ),
        "",
        "## Segment Snapshot",
        "",
        "| Segment | Customers | Revenue share | Avg frequency | Avg monetary |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, r in seg.iterrows():
        mon = f"${r['avg_monetary']:,.0f}"
        lines.append(
            f"| {r['segment']} | {int(r['customers']):,} | {r['revenue_share_pct']}% | "
            f"{r['avg_frequency']} | {mon} |"
        )

    lines += [
        "",
        "## Category Performance",
        "",
        "| Category | Revenue share | Margin | ABC |",
        "|---|---:|---:|:---:|",
    ]
    for _, r in cats.iterrows():
        lines.append(
            f"| {r['category']} | {r['revenue_share_pct']}% | {r['margin_pct']}% | {r['abc']} |"
        )

    lines += [
        "",
        "## Recommended Actions",
        "",
        "1. **Protect Champions** — exclusive early access and VIP support; they punch above their headcount in revenue.",
        "2. **Win-back At Risk** — personalized offers within 14 days of inactivity threshold, prioritized by historical monetary value.",
        "3. **Grow high-margin attach rate** — bundle Beauty/Fashion accessories with high-AOV Electronics baskets.",
        "4. **Improve early retention** — onboarding email/push sequence in the first 30 days; measure lift on M1 retention.",
        "5. **Channel optimization** — double down on top-converting channel creatives while testing Marketplace assortment gaps.",
        "",
        "---",
        "*Generated by the Retail Revenue Intelligence pipeline.*",
        "",
    ]
    return "\n".join(lines)


def save_summary(summary: dict, markdown: str, cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    Path(cfg["output"]["summary_path"]).parent.mkdir(parents=True, exist_ok=True)
    with open(cfg["output"]["summary_path"], "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    with open(cfg["output"]["insights_path"], "w", encoding="utf-8") as f:
        f.write(markdown)
