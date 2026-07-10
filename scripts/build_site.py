#!/usr/bin/env python3
"""Build a static GitHub Pages site from analysis outputs.

Generates docs/ with index.html, copies figures and insights.md so the
project can be published at https://<user>.github.io/<repo>/.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES_DIR = ROOT / "reports" / "figures"
INSIGHTS = ROOT / "reports" / "insights.md"
SUMMARY = ROOT / "reports" / "executive_summary.json"
DOCS = ROOT / "docs"
ASSETS = DOCS / "assets"
FIG_DEST = ASSETS / "figures"


FIGURE_ORDER = [
    ("00_kpi_snapshot.png", "KPI snapshot"),
    ("01_revenue_trend.png", "Revenue trend"),
    ("02_rfm_segments.png", "RFM segments"),
    ("03_rfm_scatter.png", "RFM scatter"),
    ("04_cohort_retention.png", "Cohort retention"),
    ("05_category_revenue.png", "Category revenue"),
    ("06_channel_region.png", "Channel & region"),
    ("07_top_products.png", "Top products"),
    ("08_category_month_heatmap.png", "Category × month heatmap"),
]

KPI_CARDS = [
    ("Total revenue", "${:,.0f}".format),
    ("Total profit", "${:,.0f}".format),
    ("Profit margin", "{:.1f}%".format),
    ("Orders", "{:,.0f}".format),
    ("Customers", "{:,.0f}".format),
    ("Avg order value", "${:,.2f}".format),
    ("Repeat purchase rate", "{:.1f}%".format),
    ("Avg orders / customer", "{:.2f}".format),
]


def build() -> None:
    DOCS.mkdir(exist_ok=True)
    ASSETS.mkdir(exist_ok=True)
    FIG_DEST.mkdir(exist_ok=True)

    summary = json.loads(SUMMARY.read_text())
    kpis = summary["kpis"]

    kpi_html = "\n".join(
        '      <div class="card"><div class="label">{}</div><div class="value">{}</div></div>'.format(
            label, value
        )
        for label, value in _kpi_pairs(kpis)
    )

    figures_html = "\n".join(
        '      <figure><img src="assets/figures/{}" alt="{}" loading="lazy"><figcaption>{}</figcaption></figure>'.format(
            fn, cap, cap
        )
        for fn, cap in FIGURE_ORDER
        if (FIGURES_DIR / fn).exists()
    )

    html = _PAGE_TEMPLATE.format(
        title=summary.get("project", {}).get("name", "Retail Revenue Intelligence")
        if isinstance(summary.get("project"), dict)
        else "Retail Revenue Intelligence",
        kpis=kpi_html,
        figures=figures_html,
        generated=_today(),
    )

    (DOCS / "index.html").write_text(html)
    shutil.copy(INSIGHTS, ASSETS / "insights.md")

    for fn, _ in FIGURE_ORDER:
        src = FIGURES_DIR / fn
        if src.exists():
            shutil.copy(src, FIG_DEST / fn)

    print(f"Built site at {DOCS}")


def _kpi_pairs(kpis):
    mapping = [
        ("Total revenue", "total_revenue", "${:,.0f}"),
        ("Total profit", "total_profit", "${:,.0f}"),
        ("Profit margin", "profit_margin_pct", "{:.1f}%"),
        ("Orders", "orders", "{:,.0f}"),
        ("Customers", "customers", "{:,.0f}"),
        ("Avg order value", "aov", "${:,.2f}"),
        ("Repeat purchase rate", "repeat_purchase_rate_pct", "{:.1f}%"),
        ("Avg orders / customer", "avg_orders_per_customer", "{:.2f}"),
    ]
    out = []
    for label, key, fmt in mapping:
        if key in kpis:
            out.append((label, fmt.format(kpis[key])))
    return out


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      --primary:#1B4F72; --accent:#148F77; --bg:#f7f9fa; --card:#fff;
      --text:#1c2733; --muted:#5b6b7a; --border:#e3e8ec;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
      background:var(--bg); color:var(--text); line-height:1.6; }}
    header {{ background:linear-gradient(135deg,var(--primary),var(--accent)); color:#fff; padding:48px 24px; text-align:center; }}
    header h1 {{ margin:0 0 8px; font-size:2rem; }}
    header p {{ margin:0; opacity:.9; }}
    main {{ max-width:1080px; margin:0 auto; padding:32px 24px 64px; }}
    h2 {{ color:var(--primary); border-bottom:2px solid var(--border); padding-bottom:8px; margin-top:48px; }}
    .kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-top:24px; }}
    .card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:18px; text-align:center;
      box-shadow:0 1px 3px rgba(0,0,0,.05); }}
    .card .label {{ font-size:.8rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }}
    .card .value {{ font-size:1.5rem; font-weight:700; color:var(--primary); margin-top:6px; }}
    .figures {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(420px,1fr)); gap:24px; margin-top:24px; }}
    figure {{ margin:0; background:var(--card); border:1px solid var(--border); border-radius:12px; overflow:hidden; }}
    figure img {{ width:100%; display:block; }}
    figcaption {{ padding:12px 16px; font-size:.9rem; color:var(--muted); border-top:1px solid var(--border); }}
    #insights {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:24px 32px; margin-top:24px; }}
    #insights table {{ border-collapse:collapse; width:100%; margin:16px 0; }}
    #insights th, #insights td {{ border:1px solid var(--border); padding:8px 12px; text-align:left; }}
    #insights th {{ background:#eef3f6; }}
    #insights pre {{ background:#0f1b24; color:#e6edf3; padding:16px; border-radius:8px; overflow:auto; }}
    footer {{ text-align:center; color:var(--muted); font-size:.85rem; padding:24px; }}
    a {{ color:var(--accent); }}
  </style>
</head>
<body>
  <header>
    <h1>{title}</h1>
    <p>End-to-end e-commerce analytics — executive KPIs, RFM, cohorts &amp; product intelligence</p>
  </header>
  <main>
    <h2>Headline KPIs</h2>
    <section class="kpis">
{kpis}
    </section>

    <h2>Visual Analysis</h2>
    <section class="figures">
{figures}
    </section>

    <h2>Executive Insights</h2>
    <div id="insights">Loading insights…</div>

    <footer>Built {generated} · Source: Retail Revenue Intelligence analytics pipeline</footer>
  </main>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script>
    fetch('assets/insights.md')
      .then(r => r.ok ? r.text() : Promise.reject(r.status))
      .then(md => {{ document.getElementById('insights').innerHTML = marked.parse(md); }})
      .catch(() => {{ document.getElementById('insights').textContent = 'Insights unavailable.'; }});
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
