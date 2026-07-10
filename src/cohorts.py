"""Cohort retention analysis."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import load_config


def build_cohort_table(
    orders: pd.DataFrame,
    acquisition_orders: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Monthly acquisition cohorts × months since first purchase.

    Returns:
        retention_pct: values 0–100
        cohort_sizes: customers per acquisition cohort
    """
    order_level = (
        orders.groupby(["customer_id", "order_id"], as_index=False)
        .agg(order_date=("order_date", "max"))
    )
    acquisition_source = orders if acquisition_orders is None else acquisition_orders
    acquisition_level = (
        acquisition_source.groupby(["customer_id", "order_id"], as_index=False)
        .agg(order_date=("order_date", "max"))
    )
    order_level["order_month"] = order_level["order_date"].dt.to_period("M")
    acquisition_level["order_month"] = acquisition_level["order_date"].dt.to_period("M")
    first = (
        acquisition_level.groupby("customer_id")["order_month"]
        .min()
        .rename("cohort_month")
    )
    order_level = order_level.join(first, on="customer_id")
    order_level = order_level.dropna(subset=["cohort_month"]).copy()
    order_level["period_number"] = (
        order_level["order_month"] - order_level["cohort_month"]
    ).apply(lambda x: x.n)

    cohort = (
        order_level.groupby(["cohort_month", "period_number"])["customer_id"]
        .nunique()
        .reset_index(name="customers")
    )
    sizes = (
        first.value_counts()
        .rename_axis("cohort_month")
        .rename("cohort_size")
        .to_frame()
        .sort_index()
    )

    matrix = cohort.pivot(index="cohort_month", columns="period_number", values="customers")
    retention = matrix.divide(sizes["cohort_size"], axis=0) * 100
    retention = retention.round(1)
    retention.index = retention.index.astype(str)

    sizes = sizes.reset_index()
    sizes["cohort_month"] = sizes["cohort_month"].astype(str)
    return retention, sizes


def save_cohorts(retention: pd.DataFrame, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    path = Path(cfg["data"]["cohorts_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    retention.to_csv(path)
    return path


def cohort_insights(retention: pd.DataFrame, sizes: pd.DataFrame) -> dict:
    """Extract headline retention metrics."""
    if retention.empty:
        return {}
    # Month-1 retention where available
    m1 = retention[1].dropna() if 1 in retention.columns else pd.Series(dtype=float)
    m3 = retention[3].dropna() if 3 in retention.columns else pd.Series(dtype=float)
    m6 = retention[6].dropna() if 6 in retention.columns else pd.Series(dtype=float)

    recent = sizes.tail(6)
    return {
        "avg_m1_retention_pct": round(float(m1.mean()), 1) if len(m1) else None,
        "avg_m3_retention_pct": round(float(m3.mean()), 1) if len(m3) else None,
        "avg_m6_retention_pct": round(float(m6.mean()), 1) if len(m6) else None,
        "largest_cohort": sizes.loc[sizes["cohort_size"].idxmax(), "cohort_month"],
        "largest_cohort_size": int(sizes["cohort_size"].max()),
        "recent_6m_avg_cohort_size": round(float(recent["cohort_size"].mean()), 1),
    }
