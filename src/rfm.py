"""RFM scoring and customer segmentation."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import load_config

def _score_quantile(series: pd.Series, q: int, higher_is_better: bool) -> pd.Series:
    """Assign 1..q scores via quantiles. Higher score is always better for the business."""
    # rank: larger rank → higher score after qcut
    # higher_is_better=True  → large raw values get large ranks
    # higher_is_better=False → small raw values get large ranks (e.g. recency days)
    ranks = series.rank(method="first", ascending=higher_is_better)
    try:
        scores = pd.qcut(ranks, q=q, labels=False, duplicates="drop") + 1
    except ValueError:
        scores = pd.cut(ranks, bins=q, labels=False, include_lowest=True) + 1
    return scores.astype(int)


def compute_rfm(orders: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    snapshot = pd.Timestamp(cfg["analysis"]["snapshot_date"])
    q = int(cfg["analysis"]["rfm_quantiles"])

    # Order-level first (unique order_id)
    order_level = (
        orders.groupby(["customer_id", "order_id"], as_index=False)
        .agg(
            order_date=("order_date", "max"),
            order_revenue=("line_revenue", "sum"),
        )
    )

    rfm = order_level.groupby("customer_id").agg(
        recency_days=("order_date", lambda s: (snapshot - s.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("order_revenue", "sum"),
        avg_order_value=("order_revenue", "mean"),
        first_purchase=("order_date", "min"),
        last_purchase=("order_date", "max"),
    )
    rfm = rfm.reset_index()

    # R: fewer days since last order is better → higher_is_better=False
    # F/M: larger values are better
    rfm["R"] = _score_quantile(rfm["recency_days"], q, higher_is_better=False)
    rfm["F"] = _score_quantile(rfm["frequency"], q, higher_is_better=True)
    rfm["M"] = _score_quantile(rfm["monetary"], q, higher_is_better=True)
    rfm["RFM_score"] = rfm["R"].astype(str) + rfm["F"].astype(str) + rfm["M"].astype(str)
    rfm["RFM_sum"] = rfm["R"] + rfm["F"] + rfm["M"]
    rfm["segment"] = rfm.apply(_assign_segment, axis=1)

    # Enrich with demographics if present
    if "customer_tier" in orders.columns:
        tier = orders.groupby("customer_id")["customer_tier"].first().reset_index()
        rfm = rfm.merge(tier, on="customer_id", how="left")
    if "region" in orders.columns:
        reg = orders.groupby("customer_id")["region"].first().reset_index()
        rfm = rfm.merge(reg, on="customer_id", how="left")
    if "age" in orders.columns:
        age = orders.groupby("customer_id")["age"].first().reset_index()
        rfm = rfm.merge(age, on="customer_id", how="left")
    if "gender" in orders.columns:
        gen = orders.groupby("customer_id")["gender"].first().reset_index()
        rfm = rfm.merge(gen, on="customer_id", how="left")

    return rfm.sort_values("monetary", ascending=False).reset_index(drop=True)


def _assign_segment(row: pd.Series) -> str:
    """Priority-ordered RFM personas (first match wins)."""
    r, f, m = int(row["R"]), int(row["F"]), int(row["M"])

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3 and m >= 3:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "New Customers"
    if r >= 3 and f <= 3 and m <= 3:
        return "Potential Loyalists"
    if r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 2 and f >= 2 and m >= 2:
        return "Need Attention"
    if r <= 2 and f <= 2 and m <= 2:
        return "Hibernating"
    if r <= 2:
        return "Lost"
    return "Need Attention"


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    summary = (
        rfm.groupby("segment", as_index=False)
        .agg(
            customers=("customer_id", "count"),
            revenue=("monetary", "sum"),
            avg_recency=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
            avg_aov=("avg_order_value", "mean"),
        )
        .sort_values("revenue", ascending=False)
    )
    summary["revenue_share_pct"] = (100 * summary["revenue"] / summary["revenue"].sum()).round(2)
    summary["customer_share_pct"] = (100 * summary["customers"] / summary["customers"].sum()).round(2)
    summary["avg_recency"] = summary["avg_recency"].round(1)
    summary["avg_frequency"] = summary["avg_frequency"].round(2)
    summary["avg_monetary"] = summary["avg_monetary"].round(2)
    summary["avg_aov"] = summary["avg_aov"].round(2)
    return summary


def save_rfm(rfm: pd.DataFrame, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    path = Path(cfg["data"]["rfm_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    out = rfm.copy()
    out["first_purchase"] = out["first_purchase"].astype(str)
    out["last_purchase"] = out["last_purchase"].astype(str)
    out.to_csv(path, index=False)
    return path
