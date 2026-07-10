from __future__ import annotations

import pandas as pd

from src.cohorts import build_cohort_table
from src.rfm import compute_rfm


def test_compute_rfm_scores_recent_frequent_high_value_customer_as_champion() -> None:
    rows = []
    for i in range(1, 6):
        for order_num in range(i):
            rows.append(
                {
                    "customer_id": f"c{i}",
                    "order_id": f"c{i}-o{order_num}",
                    "order_date": pd.Timestamp("2025-01-01") + pd.Timedelta(days=i * 10 + order_num),
                    "line_revenue": float(i * 100),
                }
            )
    orders = pd.DataFrame(rows)
    cfg = {"analysis": {"snapshot_date": "2025-04-01", "rfm_quantiles": 5}}

    result = compute_rfm(orders, cfg)
    top_customer = result.loc[result["customer_id"] == "c5"].iloc[0]

    assert top_customer["R"] == 5
    assert top_customer["F"] == 5
    assert top_customer["M"] == 5
    assert top_customer["segment"] == "Champions"


def test_filtered_cohorts_keep_global_first_purchase_month() -> None:
    full_orders = pd.DataFrame(
        {
            "customer_id": ["c1", "c1", "c2"],
            "order_id": ["o1", "o2", "o3"],
            "order_date": pd.to_datetime(["2025-01-15", "2025-02-15", "2025-02-20"]),
        }
    )
    filtered_orders = full_orders[full_orders["order_date"].dt.month == 2]

    retention, sizes = build_cohort_table(filtered_orders, acquisition_orders=full_orders)

    assert "2025-01" in retention.index
    assert "2025-02" in retention.index
    assert sizes.set_index("cohort_month").loc["2025-01", "cohort_size"] == 1
    assert retention.loc["2025-01", 1] == 100.0
