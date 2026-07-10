from __future__ import annotations

import pandas as pd

from src.metrics import category_performance, kpis


def test_kpis_roll_up_order_level_metrics() -> None:
    orders = pd.DataFrame(
        {
            "order_id": ["o1", "o1", "o2", "o3"],
            "customer_id": ["c1", "c1", "c1", "c2"],
            "order_date": pd.to_datetime(["2025-01-05", "2025-01-05", "2025-02-01", "2025-02-03"]),
            "quantity": [1, 2, 1, 1],
            "line_revenue": [100.0, 50.0, 75.0, 25.0],
            "line_profit": [40.0, 20.0, 30.0, 5.0],
        }
    )

    result = kpis(orders)

    assert result["total_revenue"] == 250.0
    assert result["total_profit"] == 95.0
    assert result["orders"] == 3
    assert result["customers"] == 2
    assert result["aov"] == 83.33
    assert result["repeat_purchase_rate_pct"] == 50.0


def test_category_performance_handles_zero_revenue_without_inf() -> None:
    orders = pd.DataFrame(
        {
            "category": ["A", "B"],
            "order_id": ["o1", "o2"],
            "customer_id": ["c1", "c2"],
            "quantity": [1, 1],
            "line_revenue": [0.0, 0.0],
            "line_profit": [0.0, 0.0],
        }
    )

    result = category_performance(orders)

    assert result["margin_pct"].tolist() == [0.0, 0.0]
    assert result["revenue_share_pct"].tolist() == [0.0, 0.0]
