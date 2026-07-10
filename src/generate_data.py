"""
Generate a realistic multi-year e-commerce dataset.

The data is synthetic but structured like production retail systems:
customers, products, and line-item transactions with seasonality,
category preferences, and churn-like purchase gaps.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import load_config

REGIONS = {
    "North America": 0.38,
    "Europe": 0.28,
    "Asia Pacific": 0.22,
    "Latin America": 0.08,
    "Middle East & Africa": 0.04,
}

CHANNELS = {"Web": 0.52, "Mobile App": 0.35, "Marketplace": 0.13}

CATEGORIES = {
    "Electronics": {"share": 0.18, "price_mu": 4.2, "price_sigma": 0.55, "margin": 0.22},
    "Home & Kitchen": {"share": 0.16, "price_mu": 3.6, "price_sigma": 0.50, "margin": 0.35},
    "Fashion": {"share": 0.20, "price_mu": 3.5, "price_sigma": 0.45, "margin": 0.48},
    "Beauty": {"share": 0.10, "price_mu": 3.1, "price_sigma": 0.40, "margin": 0.55},
    "Sports & Outdoors": {"share": 0.12, "price_mu": 3.7, "price_sigma": 0.48, "margin": 0.38},
    "Books & Media": {"share": 0.08, "price_mu": 2.6, "price_sigma": 0.35, "margin": 0.42},
    "Grocery": {"share": 0.10, "price_mu": 2.4, "price_sigma": 0.30, "margin": 0.18},
    "Toys & Games": {"share": 0.06, "price_mu": 3.2, "price_sigma": 0.42, "margin": 0.40},
}

BRANDS = [
    "Northline", "Aether", "Solara", "Peakform", "Lumen", "Harbor & Co",
    "Nimbus", "Vivid", "Crestwood", "Orbit", "Kinetic", "Maple & Oak",
]


def _weighted_choice(rng: np.random.Generator, options: dict[str, float], size: int) -> np.ndarray:
    keys = list(options.keys())
    probs = np.array(list(options.values()), dtype=float)
    probs = probs / probs.sum()
    return rng.choice(keys, size=size, p=probs)


def generate_customers(n: int, rng: np.random.Generator) -> pd.DataFrame:
    regions = _weighted_choice(rng, REGIONS, n)
    signup_offsets = rng.integers(0, 1000, size=n)
    base = pd.Timestamp("2022-06-01")
    signups = base + pd.to_timedelta(signup_offsets, unit="D")

    # Customer value tiers influence order frequency later
    tiers = rng.choice(["Bronze", "Silver", "Gold", "Platinum"], size=n, p=[0.45, 0.30, 0.18, 0.07])
    age = rng.integers(18, 72, size=n)

    return pd.DataFrame(
        {
            "customer_id": [f"C{i:05d}" for i in range(1, n + 1)],
            "region": regions,
            "signup_date": signups,
            "customer_tier": tiers,
            "age": age,
            "gender": rng.choice(["F", "M", "Other"], size=n, p=[0.51, 0.47, 0.02]),
        }
    )


def generate_products(n: int, rng: np.random.Generator) -> pd.DataFrame:
    cat_names = list(CATEGORIES.keys())
    cat_probs = np.array([CATEGORIES[c]["share"] for c in cat_names])
    cat_probs = cat_probs / cat_probs.sum()
    categories = rng.choice(cat_names, size=n, p=cat_probs)

    rows = []
    for i, cat in enumerate(categories, start=1):
        meta = CATEGORIES[cat]
        unit_price = float(np.round(np.exp(rng.normal(meta["price_mu"], meta["price_sigma"])), 2))
        unit_price = max(2.99, min(unit_price, 2499.0))
        cost = round(unit_price * (1 - meta["margin"] * rng.uniform(0.85, 1.15)), 2)
        brand = rng.choice(BRANDS)
        rows.append(
            {
                "product_id": f"P{i:04d}",
                "product_name": f"{brand} {cat.split()[0]} {i:03d}",
                "category": cat,
                "brand": brand,
                "unit_price": unit_price,
                "unit_cost": max(0.5, cost),
            }
        )
    return pd.DataFrame(rows)


def _seasonality_weight(dates: pd.DatetimeIndex) -> np.ndarray:
    """Higher demand around Nov–Dec and summer lifestyle months."""
    month = dates.month
    w = np.ones(len(dates), dtype=float)
    w = np.where(month == 11, 1.45, w)
    w = np.where(month == 12, 1.70, w)
    w = np.where(month == 1, 0.85, w)
    w = np.where(np.isin(month, [6, 7, 8]), 1.15, w)
    # Mild weekly pattern: weekends slightly higher
    w *= np.where(dates.dayofweek >= 5, 1.12, 1.0)
    return w


def generate_transactions(
    customers: pd.DataFrame,
    products: pd.DataFrame,
    start: str,
    end: str,
    rng: np.random.Generator,
) -> pd.DataFrame:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    days = pd.date_range(start_ts, end_ts, freq="D")
    day_weights = _seasonality_weight(days)
    day_weights = day_weights / day_weights.sum()

    # Expected orders per customer over the full window, by tier
    tier_rate = {"Bronze": 4.5, "Silver": 8.0, "Gold": 14.0, "Platinum": 22.0}
    cust = customers.copy()
    cust["expected_orders"] = cust["customer_tier"].map(tier_rate)
    # Some customers churn early / never activate fully
    cust["activity"] = rng.beta(2.2, 1.4, size=len(cust))
    cust["n_orders"] = rng.poisson(cust["expected_orders"] * cust["activity"]).clip(0, 80)

    # Preferred category per customer
    cats = list(CATEGORIES.keys())
    cust["pref_cat"] = rng.choice(cats, size=len(cust))

    order_rows: list[dict] = []
    order_id = 1
    products_by_cat = {c: products[products["category"] == c] for c in cats}

    for _, c in cust.iterrows():
        n_orders = int(c["n_orders"])
        if n_orders == 0:
            continue
        # First order after signup
        signup = pd.Timestamp(c["signup_date"])
        eligible_mask = days >= max(signup, start_ts)
        if not eligible_mask.any():
            continue
        eligible_days = days[eligible_mask]
        eligible_w = day_weights[eligible_mask]
        eligible_w = eligible_w / eligible_w.sum()

        order_dates = rng.choice(eligible_days, size=n_orders, replace=True, p=eligible_w)
        order_dates = np.sort(order_dates)

        for od in order_dates:
            channel = _weighted_choice(rng, CHANNELS, 1)[0]
            # Basket size correlates with tier
            basket_mu = {"Bronze": 1.6, "Silver": 2.1, "Gold": 2.8, "Platinum": 3.6}[c["customer_tier"]]
            n_items = max(1, int(rng.poisson(basket_mu)))

            # Prefer preferred category ~55% of items
            for _ in range(n_items):
                if rng.random() < 0.55:
                    cat = c["pref_cat"]
                else:
                    cat = rng.choice(cats)
                pool = products_by_cat[cat]
                prod = pool.iloc[int(rng.integers(0, len(pool)))]
                qty = int(max(1, rng.poisson(1.3)))
                # Occasional discount
                discount = 0.0
                if rng.random() < 0.18:
                    discount = float(rng.choice([0.05, 0.10, 0.15, 0.20, 0.25]))
                unit_price = float(prod["unit_price"]) * (1 - discount)
                # Rare bad rows for cleaning demo (~0.4%)
                if rng.random() < 0.004:
                    qty = int(rng.choice([0, -1]))
                if rng.random() < 0.002:
                    unit_price = 0.0

                order_rows.append(
                    {
                        "order_id": f"O{order_id:07d}",
                        "order_date": pd.Timestamp(od),
                        "customer_id": c["customer_id"],
                        "product_id": prod["product_id"],
                        "quantity": qty,
                        "unit_price": round(unit_price, 2),
                        "discount_rate": discount,
                        "channel": channel,
                        "region": c["region"],
                    }
                )
            order_id += 1

    # Inject a few fully duplicate rows for cleaning demo
    tx = pd.DataFrame(order_rows)
    if len(tx) > 100:
        dups = tx.sample(min(40, len(tx) // 200), random_state=0)
        tx = pd.concat([tx, dups], ignore_index=True)

    return tx.sort_values(["order_date", "order_id"]).reset_index(drop=True)


def run(config: dict | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = config or load_config()
    seed = int(cfg["data"]["seed"])
    rng = np.random.default_rng(seed)

    customers = generate_customers(int(cfg["data"]["n_customers"]), rng)
    products = generate_products(int(cfg["data"]["n_products"]), rng)
    transactions = generate_transactions(
        customers,
        products,
        cfg["data"]["start_date"],
        cfg["data"]["end_date"],
        rng,
    )

    raw_path = Path(cfg["data"]["raw_path"])
    cust_path = Path(cfg["data"]["customers_path"])
    prod_path = Path(cfg["data"]["products_path"])
    raw_path.parent.mkdir(parents=True, exist_ok=True)

    transactions.to_csv(raw_path, index=False)
    customers.to_csv(cust_path, index=False)
    products.to_csv(prod_path, index=False)

    print(f"Wrote {len(transactions):,} transaction rows → {raw_path}")
    print(f"Wrote {len(customers):,} customers → {cust_path}")
    print(f"Wrote {len(products):,} products → {prod_path}")
    return transactions, customers, products


if __name__ == "__main__":
    run()
