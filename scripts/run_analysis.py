#!/usr/bin/env python3
"""
End-to-end Retail Revenue Intelligence pipeline.

Usage (from project root):
    python scripts/run_analysis.py
    python scripts/run_analysis.py --skip-generate   # reuse existing raw data
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Project root on path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.cleaning import clean_transactions, load_raw, save_clean
from src.cohorts import build_cohort_table, save_cohorts
from src.config import load_config
from src.generate_data import run as generate_data
from src.metrics import build_insights, kpis, save_summary
from src.rfm import compute_rfm, save_rfm, segment_summary
from src.viz import generate_all_figures


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Retail Revenue Intelligence analysis")
    parser.add_argument("--skip-generate", action="store_true", help="Skip synthetic data generation")
    parser.add_argument("--config", default=None, help="Optional path to config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    t0 = time.time()

    print("=" * 60)
    print("  Retail Revenue Intelligence — Analysis Pipeline")
    print("=" * 60)

    if not args.skip_generate:
        print("\n[1/6] Generating synthetic e-commerce dataset…")
        generate_data(cfg)
    else:
        print("\n[1/6] Skipping generation (using existing raw data)")

    print("\n[2/6] Loading & cleaning…")
    tx, customers, products = load_raw(cfg)
    orders, quality = clean_transactions(tx, customers, products, cfg)
    clean_path = save_clean(orders, cfg)
    print(f"  clean rows: {quality['rows_clean']:,}  (removed {quality['rows_removed_pct']}%)")
    print(f"  saved → {clean_path}")

    print("\n[3/6] RFM segmentation…")
    rfm = compute_rfm(orders, cfg)
    rfm_path = save_rfm(rfm, cfg)
    seg = segment_summary(rfm)
    print(seg.to_string(index=False))
    print(f"  saved → {rfm_path}")

    print("\n[4/6] Cohort retention…")
    retention, sizes = build_cohort_table(orders)
    coh_path = save_cohorts(retention, cfg)
    print(f"  cohorts: {len(sizes)}  | periods: {retention.shape[1]}")
    print(f"  saved → {coh_path}")

    print("\n[5/6] KPIs, insights & figures…")
    kpi = kpis(orders)
    for key in ("total_revenue", "orders", "customers", "aov", "repeat_purchase_rate_pct"):
        print(f"  {key}: {kpi[key]}")
    summary, markdown = build_insights(orders, rfm, retention, sizes, quality, cfg)
    save_summary(summary, markdown, cfg)
    print(f"  insights → {cfg['output']['insights_path']}")

    print("\n[6/6] Rendering charts…")
    generate_all_figures(orders, rfm, retention, kpi, cfg)

    elapsed = time.time() - t0
    print("\n" + "=" * 60)
    print(f"  Done in {elapsed:.1f}s")
    print(f"  Figures:  {cfg['output']['figures_dir']}")
    print(f"  Insights: {cfg['output']['insights_path']}")
    print(f"  Dashboard: streamlit run dashboard/app.py")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
