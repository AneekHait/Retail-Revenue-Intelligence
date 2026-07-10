"""Data cleaning and order-level enrichment."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import load_config


def load_raw(cfg: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = cfg or load_config()
    tx = pd.read_csv(cfg["data"]["raw_path"], parse_dates=["order_date"])
    customers = pd.read_csv(cfg["data"]["customers_path"], parse_dates=["signup_date"])
    products = pd.read_csv(cfg["data"]["products_path"])
    return tx, customers, products


def clean_transactions(
    tx: pd.DataFrame,
    customers: pd.DataFrame,
    products: pd.DataFrame,
    cfg: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """
    Clean line items and join dimensions.

    Returns cleaned frame plus a quality report dict.
    """
    cfg = cfg or load_config()
    min_qty = cfg["analysis"]["min_quantity"]
    min_price = cfg["analysis"]["min_unit_price"]

    report: dict = {"rows_raw": len(tx)}
    df = tx.copy()

    before = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = before - len(df)

    # Invalid quantity / price
    invalid = (df["quantity"] < min_qty) | (df["unit_price"] < min_price)
    report["invalid_line_items_removed"] = int(invalid.sum())
    df = df.loc[~invalid].copy()

    # Null key check
    null_keys = df[["order_id", "customer_id", "product_id", "order_date"]].isna().any(axis=1)
    report["null_key_rows_removed"] = int(null_keys.sum())
    df = df.loc[~null_keys].copy()

    # Join product & customer attributes
    df = df.merge(
        products[["product_id", "product_name", "category", "brand", "unit_cost"]],
        on="product_id",
        how="left",
    )
    df = df.merge(
        customers[["customer_id", "customer_tier", "signup_date", "age", "gender"]],
        on="customer_id",
        how="left",
    )

    orphan_prod = df["category"].isna().sum()
    orphan_cust = df["customer_tier"].isna().sum()
    report["orphan_product_rows"] = int(orphan_prod)
    report["orphan_customer_rows"] = int(orphan_cust)
    df = df.dropna(subset=["category", "customer_tier"])

    df["line_revenue"] = (df["quantity"] * df["unit_price"]).round(2)
    df["line_cost"] = (df["quantity"] * df["unit_cost"]).round(2)
    df["line_profit"] = (df["line_revenue"] - df["line_cost"]).round(2)
    df["year"] = df["order_date"].dt.year
    df["month"] = df["order_date"].dt.to_period("M").astype(str)
    df["year_month"] = df["order_date"].dt.to_period("M")
    df["week"] = df["order_date"].dt.to_period("W").astype(str)
    df["day_of_week"] = df["order_date"].dt.day_name()

    report["rows_clean"] = len(df)
    report["orders"] = int(df["order_id"].nunique())
    report["customers"] = int(df["customer_id"].nunique())
    report["products"] = int(df["product_id"].nunique())
    report["revenue_total"] = float(df["line_revenue"].sum())
    report["profit_total"] = float(df["line_profit"].sum())
    report["date_min"] = str(df["order_date"].min().date())
    report["date_max"] = str(df["order_date"].max().date())
    report["rows_removed_pct"] = round(
        100 * (report["rows_raw"] - report["rows_clean"]) / max(report["rows_raw"], 1), 3
    )

    return df, report


def save_clean(df: pd.DataFrame, cfg: dict | None = None) -> Path:
    cfg = cfg or load_config()
    path = Path(cfg["data"]["processed_path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out["year_month"] = out["year_month"].astype(str)
    out.to_csv(path, index=False)
    return path
