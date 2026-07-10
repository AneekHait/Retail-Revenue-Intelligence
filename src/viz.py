"""Publication-quality static charts for the portfolio report."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
import seaborn as sns

from src.config import load_config
from src.metrics import (
    category_performance,
    channel_performance,
    monthly_category_heatmap_data,
    product_abc,
    region_performance,
    revenue_trend,
)
from src.rfm import segment_summary

# Consistent portfolio palette
COLORS = {
    "primary": "#1B4F72",
    "accent": "#148F77",
    "warm": "#D35400",
    "alert": "#C0392B",
    "muted": "#7F8C8D",
    "light": "#ECF0F1",
    "gold": "#F39C12",
    "blue": "#3498DB",
}

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


def setup_style(cfg: dict | None = None) -> None:
    cfg = cfg or load_config()
    sns.set_theme(style=cfg["viz"].get("style", "whitegrid"), context="notebook")
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#BDC3C7",
            "axes.labelcolor": "#2C3E50",
            "text.color": "#2C3E50",
            "xtick.color": "#34495E",
            "ytick.color": "#34495E",
            "font.family": "DejaVu Sans",
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "figure.dpi": cfg["viz"].get("dpi", 160),
            "savefig.dpi": cfg["viz"].get("dpi", 160),
            "savefig.bbox": "tight",
        }
    )


def _money_formatter(x, _pos=None):
    if abs(x) >= 1_000_000:
        return f"${x/1e6:.1f}M"
    if abs(x) >= 1_000:
        return f"${x/1e3:.0f}K"
    return f"${x:.0f}"


def _save(fig: plt.Figure, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor="white")
    plt.close(fig)
    return path


def plot_revenue_trend(orders: pd.DataFrame, out_dir: Path) -> Path:
    trend = revenue_trend(orders, freq="M")
    fig, ax = plt.subplots(figsize=(13, 5.5))
    ax.fill_between(range(len(trend)), trend["revenue"], alpha=0.15, color=COLORS["primary"])
    ax.plot(range(len(trend)), trend["revenue"], color=COLORS["primary"], linewidth=2.4, marker="o", markersize=4)
    ax2 = ax.twinx()
    ax2.bar(range(len(trend)), trend["orders"], alpha=0.25, color=COLORS["accent"], label="Orders")
    ax2.set_ylabel("Orders", color=COLORS["accent"])
    ax.set_xticks(range(0, len(trend), max(1, len(trend) // 12)))
    ax.set_xticklabels(trend["period"].iloc[:: max(1, len(trend) // 12)], rotation=45, ha="right")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))
    ax.set_title("Monthly Revenue & Order Volume")
    ax.set_ylabel("Revenue")
    ax.set_xlabel("Month")
    sns.despine(ax=ax, right=False)
    return _save(fig, out_dir / "01_revenue_trend.png")


def plot_segment_mix(rfm: pd.DataFrame, out_dir: Path) -> Path:
    seg = segment_summary(rfm)
    order = seg.sort_values("revenue", ascending=True)
    colors = [SEGMENT_COLORS.get(s, COLORS["muted"]) for s in order["segment"]]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    axes[0].barh(order["segment"], order["customers"], color=colors, edgecolor="white")
    axes[0].set_title("Customers by Segment")
    axes[0].set_xlabel("Customers")
    for i, v in enumerate(order["customers"]):
        axes[0].text(v + max(order["customers"]) * 0.01, i, f"{int(v):,}", va="center", fontsize=9)

    axes[1].barh(order["segment"], order["revenue"], color=colors, edgecolor="white")
    axes[1].set_title("Revenue by Segment")
    axes[1].set_xlabel("Revenue")
    axes[1].xaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))

    fig.suptitle("RFM Customer Segmentation", fontsize=15, fontweight="bold", y=1.02)
    fig.tight_layout()
    return _save(fig, out_dir / "02_rfm_segments.png")


def plot_rfm_scatter(rfm: pd.DataFrame, out_dir: Path) -> Path:
    sample = rfm.sample(min(3000, len(rfm)), random_state=42)
    fig, ax = plt.subplots(figsize=(10, 7))
    for seg, g in sample.groupby("segment"):
        ax.scatter(
            g["frequency"],
            g["monetary"],
            s=np.clip(80 / (1 + g["recency_days"] / 60), 12, 90),
            alpha=0.55,
            label=seg,
            c=SEGMENT_COLORS.get(seg, COLORS["muted"]),
            edgecolors="white",
            linewidths=0.3,
        )
    ax.set_xlabel("Frequency (orders)")
    ax.set_ylabel("Monetary (total spend)")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))
    ax.set_title("Customer Value Map — Frequency × Monetary\n(bubble size ∝ recency freshness)")
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", frameon=False, fontsize=9)
    sns.despine()
    fig.tight_layout()
    return _save(fig, out_dir / "03_rfm_scatter.png")


def plot_cohort_heatmap(retention: pd.DataFrame, out_dir: Path) -> Path:
    # Show last 18 cohorts, first 12 periods for readability
    mat = retention.copy()
    cols = [c for c in mat.columns if isinstance(c, (int, np.integer)) or str(c).isdigit()]
    cols = sorted(cols, key=lambda x: int(x))[:12]
    mat = mat[cols].tail(18)

    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(
        mat,
        ax=ax,
        cmap="YlGnBu",
        annot=True,
        fmt=".0f",
        linewidths=0.4,
        linecolor="white",
        cbar_kws={"label": "Retention %"},
        annot_kws={"size": 8},
    )
    ax.set_title("Monthly Cohort Retention (%)")
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Acquisition cohort")
    fig.tight_layout()
    return _save(fig, out_dir / "04_cohort_retention.png")


def plot_category_performance(orders: pd.DataFrame, out_dir: Path) -> Path:
    cat = category_performance(orders).sort_values("revenue", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(cat["category"], cat["revenue"], color=COLORS["primary"], alpha=0.9)
    # Color by ABC
    color_map = {"A": COLORS["accent"], "B": COLORS["blue"], "C": COLORS["muted"]}
    for bar, abc in zip(bars, cat["abc"]):
        bar.set_color(color_map.get(str(abc), COLORS["primary"]))
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))
    ax.set_title("Category Revenue (ABC classification: green=A, blue=B, gray=C)")
    ax.set_xlabel("Revenue")
    # margin labels
    for i, (_, r) in enumerate(cat.iterrows()):
        ax.text(
            r["revenue"] * 0.01 + r["revenue"],
            i,
            f"  {r['margin_pct']:.0f}% margin",
            va="center",
            fontsize=9,
            color=COLORS["muted"],
        )
    sns.despine()
    fig.tight_layout()
    return _save(fig, out_dir / "05_category_revenue.png")


def plot_channel_region(orders: pd.DataFrame, out_dir: Path) -> Path:
    ch = channel_performance(orders)
    reg = region_performance(orders)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    axes[0].pie(
        ch["revenue"],
        labels=ch["channel"],
        autopct="%1.1f%%",
        colors=[COLORS["primary"], COLORS["accent"], COLORS["gold"]],
        startangle=90,
        wedgeprops={"linewidth": 1, "edgecolor": "white"},
        textprops={"fontsize": 10},
    )
    axes[0].set_title("Revenue by Channel")

    axes[1].bar(reg["region"], reg["revenue"], color=COLORS["primary"], edgecolor="white")
    axes[1].set_title("Revenue by Region")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].yaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))
    for i, v in enumerate(reg["aov"]):
        axes[1].text(i, reg["revenue"].iloc[i], f"AOV ${v:,.0f}", ha="center", va="bottom", fontsize=8)
    sns.despine(ax=axes[1])
    fig.tight_layout()
    return _save(fig, out_dir / "06_channel_region.png")


def plot_top_products(orders: pd.DataFrame, out_dir: Path) -> Path:
    top = product_abc(orders, top_n=15).sort_values("revenue", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = [COLORS["accent"] if a == "A" else COLORS["blue"] if a == "B" else COLORS["muted"] for a in top["abc"]]
    ax.barh(top["product_name"], top["revenue"], color=colors)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(_money_formatter))
    ax.set_title("Top 15 Products by Revenue")
    ax.set_xlabel("Revenue")
    sns.despine()
    fig.tight_layout()
    return _save(fig, out_dir / "07_top_products.png")


def plot_monthly_category_heatmap(orders: pd.DataFrame, out_dir: Path) -> Path:
    heat = monthly_category_heatmap_data(orders)
    # last 18 months
    heat = heat.iloc[:, -18:]
    fig, ax = plt.subplots(figsize=(14, 6))
    sns.heatmap(heat, cmap="mako", ax=ax, linewidths=0.3, linecolor="white", cbar_kws={"label": "Revenue"})
    ax.set_title("Category × Month Revenue Heatmap")
    ax.set_xlabel("Month")
    ax.set_ylabel("")
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    return _save(fig, out_dir / "08_category_month_heatmap.png")


def plot_kpi_cards(kpi: dict, out_dir: Path) -> Path:
    cards = [
        ("Revenue", _money_formatter(kpi["total_revenue"]), COLORS["primary"]),
        ("Profit", _money_formatter(kpi["total_profit"]), COLORS["accent"]),
        ("Orders", f"{kpi['orders']:,}", COLORS["blue"]),
        ("Customers", f"{kpi['customers']:,}", COLORS["warm"]),
        ("AOV", f"${kpi['aov']:,.2f}", COLORS["gold"]),
        ("Repeat Rate", f"{kpi['repeat_purchase_rate_pct']}%", COLORS["alert"]),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(12, 5))
    for ax, (label, value, color) in zip(axes.ravel(), cards):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        ax.add_patch(
            plt.Rectangle((0.05, 0.15), 0.9, 0.7, facecolor=color, alpha=0.12, edgecolor=color, linewidth=2, joinstyle="round")
        )
        ax.text(0.5, 0.58, value, ha="center", va="center", fontsize=18, fontweight="bold", color=color)
        ax.text(0.5, 0.32, label, ha="center", va="center", fontsize=11, color=COLORS["muted"])
    fig.suptitle("Executive KPI Snapshot", fontsize=15, fontweight="bold")
    fig.tight_layout()
    return _save(fig, out_dir / "00_kpi_snapshot.png")


def generate_all_figures(
    orders: pd.DataFrame,
    rfm: pd.DataFrame,
    retention: pd.DataFrame,
    kpi: dict,
    cfg: dict | None = None,
) -> list[Path]:
    cfg = cfg or load_config()
    setup_style(cfg)
    out_dir = Path(cfg["output"]["figures_dir"])
    paths = [
        plot_kpi_cards(kpi, out_dir),
        plot_revenue_trend(orders, out_dir),
        plot_segment_mix(rfm, out_dir),
        plot_rfm_scatter(rfm, out_dir),
        plot_cohort_heatmap(retention, out_dir),
        plot_category_performance(orders, out_dir),
        plot_channel_region(orders, out_dir),
        plot_top_products(orders, out_dir),
        plot_monthly_category_heatmap(orders, out_dir),
    ]
    for p in paths:
        print(f"  figure → {p}")
    return paths
